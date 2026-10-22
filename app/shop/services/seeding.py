# trace: ADDR-008, ADDR-010, FILE-001
"""初期データ一括投入（FR-060）の読込・検証・登録。

定義ファイルの構造・参照項目名・日時表記は ADDR-010 で確定した仕様に従う（FILE-001）。
違反が1件でもある場合は削除も登録も行わない。
"""
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from django.db import transaction
from django.utils import timezone

from shop.common import timeutils
from shop.common.validators import EMAIL_PATTERN, UPPER_CODE_PATTERN, normalize_email, strip_value
from shop.models import Collection, Coupon, Item, ItemCollection, Role, StockUnit, Supplier, User
from shop.services import audit
from shop.services.accounts import hash_password
from shop.services.audit import RESULT_FAILURE, RESULT_SUCCESS

TOP_LEVEL_KEYS = ("users", "suppliers", "collections", "items", "stock_units", "coupons")
LOWER_CODE_PATTERN = re.compile(r"^[a-z0-9-]+$")
DATETIME_PATTERN = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?([+-][0-9]{2}:[0-9]{2}|Z)?$"
)
MAX_DEPTH = 3
DATA_LABELS = {
    "users": "利用者",
    "suppliers": "仕入先",
    "collections": "商品分類",
    "items": "商品",
    "item_collections": "商品分類所属",
    "stock_units": "在庫単位",
    "coupons": "クーポン",
}


# trace: ADDR-010
class SeedFileError(Exception):
    """定義ファイルの構造・文字コードの違反（E-060-03）。"""


# trace: ADDR-010
@dataclass
class Violation:
    """違反1件（データ名・行番号・項目名・理由）。項目の値は保持しない。"""

    data_name: str
    line_number: int
    field_name: str
    reason: str

    def format(self) -> str:
        """標準エラー出力へ表示する1行を組み立てる。"""
        return f"{self.data_name} 行{self.line_number} 項目={self.field_name} 理由={self.reason}"


# trace: ADDR-010
@dataclass
class LoadResult:
    """投入結果（データ別の件数と違反の一覧）。"""

    counts: dict[str, int] = field(default_factory=dict)
    violations: list[Violation] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """違反が0件かどうかを返す。"""
        return not self.violations

    def detail_text(self) -> str:
        """監査ログの詳細（データ別件数）を組み立てる。"""
        return ", ".join(f"{DATA_LABELS[key]}={self.counts.get(key, 0)}" for key in DATA_LABELS)


# trace: ADDR-010
def read_definition_file(path: str) -> dict[str, list[dict[str, Any]]]:
    """定義ファイルを UTF-8 の JSON として読み込み、構造を判定する（手順3）。"""
    try:
        with open(path, "rb") as stream:
            raw = stream.read()
    except OSError as exc:
        raise FileNotFoundError(str(path)) from exc

    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SeedFileError("定義ファイルを UTF-8 として解釈できません。") from exc
    try:
        document = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SeedFileError("定義ファイルを JSON として解釈できません。") from exc

    if not isinstance(document, dict):
        raise SeedFileError("定義ファイルのトップレベルは JSON オブジェクトで記載してください。")
    unknown = [key for key in document if key not in TOP_LEVEL_KEYS]
    if unknown:
        raise SeedFileError(f"定義ファイルに未知のキーがあります：{', '.join(sorted(unknown))}")

    data: dict[str, list[dict[str, Any]]] = {}
    for key in TOP_LEVEL_KEYS:
        rows = document.get(key, [])
        if not isinstance(rows, list):
            raise SeedFileError(f"{DATA_LABELS[key]}は行の並びとして記載してください。")
        for row in rows:
            if not isinstance(row, dict):
                raise SeedFileError(f"{DATA_LABELS[key]}の各行はオブジェクトで記載してください。")
        data[key] = rows
    return data


# trace: ADDR-010
def _parse_datetime(value: Any) -> datetime | None:
    """ISO 8601 の日付時刻だけを受理する（オフセット省略時は JST とする）。"""
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not DATETIME_PATTERN.match(text):
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


# trace: ADDR-010
def _check_text(
    value: Any,
    *,
    required: bool,
    min_length: int,
    max_length: int,
    pattern: re.Pattern[str] | None = None,
    strip: bool = True,
) -> tuple[str | None, str | None]:
    """文字列項目を判定し、(整形後の値, 違反理由) を返す。"""
    if value is None:
        if required:
            return None, "必須項目が指定されていません。"
        return "", None
    if not isinstance(value, str):
        return None, "文字列で指定してください。"
    text = strip_value(value) if strip else value
    if text == "" and required:
        return None, "必須項目が指定されていません。"
    if len(text) < min_length and required:
        return None, f"{min_length}文字以上で指定してください。"
    if len(text) > max_length:
        return None, f"{max_length}文字以下で指定してください。"
    if pattern is not None and text != "" and not pattern.match(text):
        return None, "使用できない文字が含まれています。"
    return text, None


# trace: ADDR-010
def _check_int(value: Any, *, required: bool, minimum: int, maximum: int, default: int | None = None):
    """整数項目を判定し、(値, 違反理由) を返す。"""
    if value is None:
        if required:
            return None, "必須項目が指定されていません。"
        return default, None
    if isinstance(value, bool) or not isinstance(value, int):
        return None, "整数で指定してください。"
    if value < minimum or value > maximum:
        return None, f"{minimum}以上{maximum}以下で指定してください。"
    return value, None


# trace: ADDR-008, ADDR-010
def _validate_password(value: Any, normalized_email: str) -> str | None:
    """定義ファイルの平文パスワードの条件を判定する（違反理由を返す）。"""
    if value is None:
        return "必須項目が指定されていません。"
    if not isinstance(value, str):
        return "文字列で指定してください。"
    if not 8 <= len(value) <= 64:
        return "8文字以上64文字以下で指定してください。"
    if not any(char.isascii() and char.isalpha() for char in value):
        return "英字を1文字以上含めてください。"
    if not any(char.isascii() and char.isdigit() for char in value):
        return "数字を1文字以上含めてください。"
    if value.lower() == normalized_email:
        return "メールアドレスと同じ値は使用できません。"
    return None


# trace: ADDR-010
class SeedLoader:
    """定義ファイルの検証と登録を行う（FR-060 手順4〜13）。"""

    def __init__(self, data: dict[str, list[dict[str, Any]]], reset: bool) -> None:
        """読み込んだ定義ファイルの内容と全削除指定を保持する。"""
        self.data = data
        self.reset = reset
        self.violations: list[Violation] = []
        self.loaded_at = timeutils.now()
        self.users: list[dict[str, Any]] = []
        self.suppliers: list[dict[str, Any]] = []
        self.collections: list[dict[str, Any]] = []
        self.items: list[dict[str, Any]] = []
        self.stock_units: list[dict[str, Any]] = []
        self.coupons: list[dict[str, Any]] = []
        self.item_collection_count = 0

    def add_violation(self, data_key: str, line_number: int, field_name: str, reason: str) -> None:
        """違反を記録する（判定は中断しない）。"""
        self.violations.append(Violation(DATA_LABELS[data_key], line_number, field_name, reason))

    def validate(self) -> None:
        """値域・一意性・参照整合性を全件判定する（手順5〜7）。"""
        self._validate_users()
        self._validate_suppliers()
        self._validate_collections()
        self._validate_items()
        self._validate_stock_units()
        self._validate_coupons()
        self._validate_uniqueness()
        self._validate_references()

    def _validate_users(self) -> None:
        """利用者の値域を判定する。"""
        for index, row in enumerate(self.data["users"], start=1):
            email_raw = row.get("email")
            normalized = normalize_email(email_raw) if isinstance(email_raw, str) else ""
            if not isinstance(email_raw, str) or normalized == "":
                self.add_violation("users", index, "email", "必須項目が指定されていません。")
            elif len(normalized) > 254 or not EMAIL_PATTERN.match(normalized):
                self.add_violation("users", index, "email", "メールアドレスの形式で指定してください。")

            password_reason = _validate_password(row.get("password"), normalized)
            if password_reason:
                self.add_violation("users", index, "password", password_reason)

            full_name, reason = _check_text(row.get("full_name"), required=True, min_length=1, max_length=50)
            if reason:
                self.add_violation("users", index, "full_name", reason)

            role = row.get("role")
            if role not in {Role.BUYER.value, Role.ADMIN.value}:
                self.add_violation("users", index, "role", "buyer または admin で指定してください。")

            self.users.append(
                {
                    "line": index,
                    "email": normalized,
                    "password": row.get("password") if isinstance(row.get("password"), str) else "",
                    "full_name": full_name or "",
                    "role": role,
                }
            )

    def _validate_suppliers(self) -> None:
        """仕入先の値域を判定する。"""
        for index, row in enumerate(self.data["suppliers"], start=1):
            code, reason = _check_text(
                row.get("supplier_code"), required=True, min_length=1, max_length=20, pattern=UPPER_CODE_PATTERN
            )
            if reason:
                self.add_violation("suppliers", index, "supplier_code", reason)
            name, reason = _check_text(row.get("name"), required=True, min_length=1, max_length=100)
            if reason:
                self.add_violation("suppliers", index, "name", reason)
            self.suppliers.append({"line": index, "supplier_code": code or "", "name": name or ""})

    def _validate_collections(self) -> None:
        """商品分類の値域を判定する。"""
        for index, row in enumerate(self.data["collections"], start=1):
            code, reason = _check_text(
                row.get("collection_code"), required=True, min_length=1, max_length=30, pattern=LOWER_CODE_PATTERN
            )
            if reason:
                self.add_violation("collections", index, "collection_code", reason)
            name, reason = _check_text(row.get("name"), required=True, min_length=1, max_length=50)
            if reason:
                self.add_violation("collections", index, "name", reason)
            parent_code, reason = _check_text(
                row.get("parent_collection_code"),
                required=False,
                min_length=0,
                max_length=30,
                pattern=LOWER_CODE_PATTERN,
            )
            if reason:
                self.add_violation("collections", index, "parent_collection_code", reason)
            sort_order, reason = _check_int(row.get("sort_order"), required=False, minimum=0, maximum=999, default=0)
            if reason:
                self.add_violation("collections", index, "sort_order", reason)
            self.collections.append(
                {
                    "line": index,
                    "collection_code": code or "",
                    "name": name or "",
                    "parent_collection_code": parent_code or None,
                    "sort_order": sort_order if sort_order is not None else 0,
                }
            )

    def _validate_items(self) -> None:
        """商品の値域を判定する。"""
        for index, row in enumerate(self.data["items"], start=1):
            code, reason = _check_text(
                row.get("item_code"), required=True, min_length=1, max_length=20, pattern=UPPER_CODE_PATTERN
            )
            if reason:
                self.add_violation("items", index, "item_code", reason)
            name, reason = _check_text(row.get("name"), required=True, min_length=1, max_length=100)
            if reason:
                self.add_violation("items", index, "name", reason)
            description, reason = _check_text(row.get("description"), required=False, min_length=0, max_length=2000)
            if reason:
                self.add_violation("items", index, "description", reason)

            is_public = row.get("is_public", True)
            if not isinstance(is_public, bool):
                self.add_violation("items", index, "is_public", "真偽値で指定してください。")
                is_public = True

            collection_codes = row.get("collection_codes", [])
            if not isinstance(collection_codes, list) or any(not isinstance(code_, str) for code_ in collection_codes):
                self.add_violation("items", index, "collection_codes", "分類コードの配列で指定してください。")
                collection_codes = []
            else:
                collection_codes = [strip_value(code_) for code_ in collection_codes]

            created_at_raw = row.get("created_at")
            created_at = self.loaded_at
            if created_at_raw is not None:
                parsed = _parse_datetime(created_at_raw)
                if parsed is None:
                    self.add_violation("items", index, "created_at", "日時として解釈できません。")
                else:
                    created_at = parsed

            self.items.append(
                {
                    "line": index,
                    "item_code": code or "",
                    "name": name or "",
                    "description": description or "",
                    "is_public": is_public,
                    "collection_codes": collection_codes,
                    "created_at": created_at,
                }
            )

    def _validate_stock_units(self) -> None:
        """在庫単位の値域を判定する。"""
        for index, row in enumerate(self.data["stock_units"], start=1):
            sku, reason = _check_text(
                row.get("sku"), required=True, min_length=1, max_length=32, pattern=UPPER_CODE_PATTERN
            )
            if reason:
                self.add_violation("stock_units", index, "sku", reason)
            item_code, reason = _check_text(
                row.get("item_code"), required=True, min_length=1, max_length=20, pattern=UPPER_CODE_PATTERN
            )
            if reason:
                self.add_violation("stock_units", index, "item_code", reason)
            supplier_code, reason = _check_text(
                row.get("supplier_code"), required=True, min_length=1, max_length=20, pattern=UPPER_CODE_PATTERN
            )
            if reason:
                self.add_violation("stock_units", index, "supplier_code", reason)
            variant_name, reason = _check_text(row.get("variant_name"), required=True, min_length=1, max_length=50)
            if reason:
                self.add_violation("stock_units", index, "variant_name", reason)
            price, reason = _check_int(row.get("price"), required=True, minimum=0, maximum=9999999)
            if reason:
                self.add_violation("stock_units", index, "price", reason)
            quantity, reason = _check_int(row.get("quantity"), required=True, minimum=0, maximum=99999)
            if reason:
                self.add_violation("stock_units", index, "quantity", reason)
            self.stock_units.append(
                {
                    "line": index,
                    "sku": sku or "",
                    "item_code": item_code or "",
                    "supplier_code": supplier_code or "",
                    "variant_name": variant_name or "",
                    "price": price if price is not None else 0,
                    "quantity": quantity if quantity is not None else 0,
                }
            )

    def _validate_coupons(self) -> None:
        """クーポンの値域を判定する。"""
        for index, row in enumerate(self.data["coupons"], start=1):
            code, reason = _check_text(
                row.get("code"), required=True, min_length=1, max_length=20, pattern=UPPER_CODE_PATTERN
            )
            if reason:
                self.add_violation("coupons", index, "code", reason)
            name, reason = _check_text(row.get("name"), required=True, min_length=1, max_length=50)
            if reason:
                self.add_violation("coupons", index, "name", reason)

            discount_type = row.get("discount_type")
            if discount_type not in {"fixed", "percentage"}:
                self.add_violation("coupons", index, "discount_type", "fixed または percentage で指定してください。")
            maximum = 100 if discount_type == "percentage" else 9999999
            discount_value, reason = _check_int(row.get("discount_value"), required=True, minimum=1, maximum=maximum)
            if reason:
                self.add_violation("coupons", index, "discount_value", reason)
            min_spend, reason = _check_int(row.get("min_spend"), required=False, minimum=0, maximum=9999999, default=0)
            if reason:
                self.add_violation("coupons", index, "min_spend", reason)

            valid_from = _parse_datetime(row.get("valid_from"))
            if valid_from is None:
                self.add_violation("coupons", index, "valid_from", "日時として解釈できません。")
            valid_until = _parse_datetime(row.get("valid_until"))
            if valid_until is None:
                self.add_violation("coupons", index, "valid_until", "日時として解釈できません。")
            if valid_from and valid_until and valid_from > valid_until:
                self.add_violation("coupons", index, "valid_until", "有効開始日時以降の日時を指定してください。")

            self.coupons.append(
                {
                    "line": index,
                    "code": code or "",
                    "name": name or "",
                    "discount_type": discount_type,
                    "discount_value": discount_value if discount_value is not None else 0,
                    "min_spend": min_spend if min_spend is not None else 0,
                    "valid_from": valid_from,
                    "valid_until": valid_until,
                }
            )

    def _validate_uniqueness(self) -> None:
        """業務キーと分類名の一意性を判定する（手順6）。"""
        self._check_unique_key("users", self.users, "email")
        self._check_unique_key("suppliers", self.suppliers, "supplier_code")
        self._check_unique_key("collections", self.collections, "collection_code")
        self._check_unique_key("items", self.items, "item_code")
        self._check_unique_key("stock_units", self.stock_units, "sku")
        self._check_unique_key("coupons", self.coupons, "code")

        seen_names: set[tuple[str | None, str]] = set()
        for row in self.collections:
            key = (row["parent_collection_code"], row["name"])
            if key in seen_names:
                self.add_violation("collections", row["line"], "name", "同じ親分類の中で分類名が重複しています。")
            seen_names.add(key)

        for row in self.items:
            seen_codes: set[str] = set()
            for code in row["collection_codes"]:
                if code in seen_codes:
                    self.add_violation("items", row["line"], "collection_codes", "所属分類が重複して指定されています。")
                seen_codes.add(code)

        if not self.reset:
            self._check_existing("users", self.users, "email", User, "email")
            self._check_existing("suppliers", self.suppliers, "supplier_code", Supplier, "supplier_code")
            self._check_existing("collections", self.collections, "collection_code", Collection, "collection_code")
            self._check_existing("items", self.items, "item_code", Item, "item_code")
            self._check_existing("stock_units", self.stock_units, "sku", StockUnit, "sku")
            self._check_existing("coupons", self.coupons, "code", Coupon, "code")
            self._check_existing_collection_names()

    def _check_existing_collection_names(self) -> None:
        """同じ親分類を持つ登録済みの分類との分類名の重複を判定する（手順6。全削除指定が無い場合）。"""
        rows = [row for row in self.collections if row["name"]]
        if not rows:
            return
        existing = set(
            Collection.objects.filter(name__in={row["name"] for row in rows}).values_list(
                "parent_collection__collection_code", "name"
            )
        )
        for row in rows:
            if (row["parent_collection_code"], row["name"]) in existing:
                self.add_violation(
                    "collections", row["line"], "name", "同じ親分類の登録済みの分類と分類名が重複しています。"
                )

    def _check_unique_key(self, data_key: str, rows: list[dict[str, Any]], field_name: str) -> None:
        """定義ファイル内の業務キーの重複を判定する。"""
        seen: set[str] = set()
        for row in rows:
            value = row[field_name]
            if value == "":
                continue
            if value in seen:
                self.add_violation(data_key, row["line"], field_name, "定義ファイル内で重複しています。")
            seen.add(value)

    def _check_existing(
        self, data_key: str, rows: list[dict[str, Any]], field_name: str, model: Any, column: str
    ) -> None:
        """登録済みデータとの業務キーの重複を判定する（全削除指定が無い場合）。"""
        values = [row[field_name] for row in rows if row[field_name] != ""]
        if not values:
            return
        existing = set(model.objects.filter(**{f"{column}__in": values}).values_list(column, flat=True))
        for row in rows:
            if row[field_name] in existing:
                self.add_violation(data_key, row["line"], field_name, "登録済みのデータと重複しています。")

    def _validate_references(self) -> None:
        """参照整合性と商品分類の深さ・循環を判定する（手順7）。"""
        file_collection_codes = {row["collection_code"] for row in self.collections if row["collection_code"]}
        file_item_codes = {row["item_code"] for row in self.items if row["item_code"]}
        file_supplier_codes = {row["supplier_code"] for row in self.suppliers if row["supplier_code"]}

        existing_collection_codes: set[str] = set()
        existing_item_codes: set[str] = set()
        existing_supplier_codes: set[str] = set()
        if not self.reset:
            existing_collection_codes = set(Collection.objects.values_list("collection_code", flat=True))
            existing_item_codes = set(Item.objects.values_list("item_code", flat=True))
            existing_supplier_codes = set(Supplier.objects.values_list("supplier_code", flat=True))

        known_collections = file_collection_codes | existing_collection_codes
        known_items = file_item_codes | existing_item_codes
        known_suppliers = file_supplier_codes | existing_supplier_codes

        parents = {row["collection_code"]: row["parent_collection_code"] for row in self.collections}
        for row in self.collections:
            parent = row["parent_collection_code"]
            if parent and parent not in known_collections:
                self.add_violation("collections", row["line"], "parent_collection_code", "参照先の分類がありません。")
                continue
            depth = self._collection_depth(row["collection_code"], parents, existing_collection_codes)
            if depth is None:
                self.add_violation(
                    "collections", row["line"], "parent_collection_code", "親分類の参照が循環しています。"
                )
            elif depth > MAX_DEPTH:
                self.add_violation("collections", row["line"], "parent_collection_code", "階層が3を超えています。")

        for row in self.items:
            for code in row["collection_codes"]:
                if code not in known_collections:
                    self.add_violation("items", row["line"], "collection_codes", "参照先の分類がありません。")

        for row in self.stock_units:
            if row["item_code"] and row["item_code"] not in known_items:
                self.add_violation("stock_units", row["line"], "item_code", "参照先の商品がありません。")
            if row["supplier_code"] and row["supplier_code"] not in known_suppliers:
                self.add_violation("stock_units", row["line"], "supplier_code", "参照先の仕入先がありません。")

    def _collection_depth(
        self, code: str, parents: dict[str, str | None], existing_codes: set[str]
    ) -> int | None:
        """分類の深さを求める（循環時は None を返す）。"""
        depth = 1
        seen = {code}
        current = parents.get(code)
        while current:
            if current in seen:
                return None
            seen.add(current)
            depth += 1
            if depth > MAX_DEPTH + 1:
                return depth
            if current in parents:
                current = parents.get(current)
            elif current in existing_codes:
                existing = Collection.objects.filter(collection_code=current).first()
                return depth + (existing.depth - 1) if existing else depth
            else:
                return depth
        return depth

    def load(self) -> LoadResult:
        """削除・登録・監査ログを1トランザクションで確定する（手順9〜12）。"""
        counts: dict[str, int] = {}
        with transaction.atomic():
            if self.reset:
                self._delete_all()
            counts = self._insert_all()
            result = LoadResult(counts=counts)
            audit.record_initial_data_load(RESULT_SUCCESS, result.detail_text())
        return result

    def _delete_all(self) -> None:
        """監査ログ以外の全データとログインセッションを削除する（手順9）。"""
        from django.contrib.sessions.models import Session

        from shop.models import (
            Cart,
            CartLine,
            PaymentRecord,
            PurchaseOrder,
            PurchaseOrderLine,
            PurchaseOrderStatusHistory,
            ShippingAddress,
        )

        PurchaseOrderStatusHistory.objects.all().delete()
        PaymentRecord.objects.all().delete()
        ShippingAddress.objects.all().delete()
        PurchaseOrderLine.objects.all().delete()
        PurchaseOrder.objects.all().delete()
        CartLine.objects.all().delete()
        Cart.objects.all().delete()
        ItemCollection.objects.all().delete()
        StockUnit.objects.all().delete()
        Item.objects.all().delete()
        for depth in range(MAX_DEPTH, 0, -1):
            Collection.objects.filter(depth=depth).delete()
        Supplier.objects.all().delete()
        Coupon.objects.all().delete()
        User.objects.all().delete()
        Session.objects.all().delete()

    def _insert_all(self) -> dict[str, int]:
        """定義ファイルのデータを登録する（手順10）。"""
        suppliers = {
            row["supplier_code"]: Supplier.objects.create(supplier_code=row["supplier_code"], name=row["name"])
            for row in self.suppliers
        }

        collections: dict[str, Collection] = {}
        pending = list(self.collections)
        while pending:
            progressed = False
            remaining: list[dict[str, Any]] = []
            for row in pending:
                parent_code = row["parent_collection_code"]
                if parent_code is None:
                    parent = None
                elif parent_code in collections:
                    parent = collections[parent_code]
                else:
                    parent = Collection.objects.filter(collection_code=parent_code).first()
                    if parent is None:
                        remaining.append(row)
                        continue
                depth = 1 if parent is None else parent.depth + 1
                collections[row["collection_code"]] = Collection.objects.create(
                    collection_code=row["collection_code"],
                    name=row["name"],
                    parent_collection=parent,
                    depth=depth,
                    sort_order=row["sort_order"],
                )
                progressed = True
            if not progressed:
                break
            pending = remaining

        items: dict[str, Item] = {}
        item_collection_count = 0
        for row in self.items:
            item = Item.objects.create(
                item_code=row["item_code"],
                name=row["name"],
                description=row["description"],
                is_public=row["is_public"],
                created_at=row["created_at"],
            )
            items[row["item_code"]] = item
            for code in row["collection_codes"]:
                collection = collections.get(code) or Collection.objects.filter(collection_code=code).first()
                if collection is not None:
                    ItemCollection.objects.create(item=item, collection=collection)
                    item_collection_count += 1

        for row in self.stock_units:
            item = items.get(row["item_code"]) or Item.objects.filter(item_code=row["item_code"]).first()
            supplier = suppliers.get(row["supplier_code"]) or Supplier.objects.filter(
                supplier_code=row["supplier_code"]
            ).first()
            StockUnit.objects.create(
                item=item,
                supplier=supplier,
                sku=row["sku"],
                variant_name=row["variant_name"],
                price=row["price"],
                quantity=row["quantity"],
                updated_at=self.loaded_at,
            )

        for row in self.coupons:
            Coupon.objects.create(
                code=row["code"],
                name=row["name"],
                discount_type=row["discount_type"],
                discount_value=row["discount_value"],
                min_spend=row["min_spend"],
                valid_from=row["valid_from"],
                valid_until=row["valid_until"],
            )

        for row in self.users:
            User.objects.create(
                email=row["email"],
                password_hash=hash_password(row["password"]),
                full_name=row["full_name"],
                role=row["role"],
                registered_at=self.loaded_at,
            )

        return {
            "users": len(self.users),
            "suppliers": len(self.suppliers),
            "collections": len(self.collections),
            "items": len(self.items),
            "item_collections": item_collection_count,
            "stock_units": len(self.stock_units),
            "coupons": len(self.coupons),
        }


# trace: ADDR-010
def record_failure(detail: str) -> None:
    """失敗時の監査ログを1件記録する（CMN-21 のただし書き）。"""
    audit.record_initial_data_load(RESULT_FAILURE, detail)
