# trace: ADDR-004, ADDR-005, FILE-001
"""初期データ定義ファイルの読込・検証・投入（FR-060）。

トップレベルのキーは users・suppliers・collections・items・stock_units・coupons の6つに限る
（ADDR-004 INV-001）。ファイルはBOM付きUTF-8を許容して1回だけ全体を読み込み、
値域→一意性→参照整合性の順に全件の違反を収集してから一括で確定する（ADDR-005 DD-003）。
"""

from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import dataclass, field
from typing import Any

from django.db import transaction

from accounts.models import EVENT_INITIAL_DATA_LOAD, RESULT_FAILURE, RESULT_SUCCESS, ROLE_ADMIN, ROLE_BUYER, User
from accounts.services import hash_password, record_audit
from carts.models import DISCOUNT_FIXED, DISCOUNT_PERCENTAGE, Cart, CartLine, Coupon
from catalog.models import Collection, Item, ItemCollection, StockUnit, Supplier
from common import timeutils
from common.validators import is_email_format, normalize_text, password_violations
from orders.models import (
    OrderNumberSequence,
    PaymentRecord,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseOrderStatusHistory,
    ShippingAddress,
)

KEY_USERS = "users"
KEY_SUPPLIERS = "suppliers"
KEY_COLLECTIONS = "collections"
KEY_ITEMS = "items"
KEY_STOCK_UNITS = "stock_units"
KEY_COUPONS = "coupons"
TOP_LEVEL_KEYS = (KEY_USERS, KEY_SUPPLIERS, KEY_COLLECTIONS, KEY_ITEMS, KEY_STOCK_UNITS, KEY_COUPONS)

FIELDS: dict[str, tuple[str, ...]] = {
    KEY_USERS: ("email", "password", "full_name", "role"),
    KEY_SUPPLIERS: ("supplier_code", "name"),
    KEY_COLLECTIONS: ("collection_code", "name", "parent_collection_code", "sort_order"),
    KEY_ITEMS: ("item_code", "name", "description", "is_public", "collection_codes", "created_at"),
    KEY_STOCK_UNITS: ("sku", "item_code", "supplier_code", "variant_name", "price", "quantity"),
    KEY_COUPONS: (
        "code",
        "name",
        "discount_type",
        "discount_value",
        "min_spend",
        "valid_from",
        "valid_until",
    ),
}

SUPPLIER_CODE_PATTERN = re.compile(r"^[A-Z0-9-]{1,20}$")
COLLECTION_CODE_PATTERN = re.compile(r"^[a-z0-9-]{1,30}$")
ITEM_CODE_PATTERN = re.compile(r"^[A-Z0-9-]{1,20}$")
SKU_PATTERN = re.compile(r"^[A-Z0-9-]{1,32}$")
COUPON_CODE_PATTERN = re.compile(r"^[A-Z0-9-]{1,20}$")

MAX_DEPTH = 3

ERROR_FILE_NOT_READABLE = "E-060-02"
ERROR_FILE_NOT_PARSABLE = "E-060-03"
ERROR_VALUE_RANGE = "E-060-04"
ERROR_CONSISTENCY = "E-060-05"


# trace: ADDR-005
@dataclass(frozen=True)
class Violation:
    """定義ファイルの違反1件（項目の値は保持しない）。"""

    data_name: str
    row_number: int
    field_name: str
    reason: str

    def format(self) -> str:
        return f"{self.data_name} 行{self.row_number} {self.field_name}: {self.reason}"


# trace: ADDR-005
@dataclass
class SeedError(Exception):
    """初期データ一括投入の失敗（監査ログへ失敗を記録して終了する）。"""

    code: str
    message: str
    violations: list[Violation] = field(default_factory=list)

    def __str__(self) -> str:
        return self.message


# trace: ADDR-005
@dataclass
class LoadResult:
    """投入件数（標準出力へ表示する）。"""

    counts: dict[str, int]

    def summary(self) -> str:
        return ", ".join(f"{name}={count}" for name, count in self.counts.items())


# trace: ADDR-005
def read_definition_file(path: str) -> dict[str, Any]:
    """定義ファイルを1回だけ読み込み、JSON として解釈する（BOM付きUTF-8を許容）。"""
    try:
        with open(path, "rb") as stream:
            raw = stream.read()
    except OSError:
        raise SeedError(ERROR_FILE_NOT_READABLE, f"定義ファイルを読み取れません: {path}")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise SeedError(ERROR_FILE_NOT_PARSABLE, "定義ファイルの文字コードが UTF-8 ではありません。")
    try:
        document = json.loads(text)
    except json.JSONDecodeError:
        raise SeedError(ERROR_FILE_NOT_PARSABLE, "定義ファイルを JSON として解釈できません。")
    return document


# trace: ADDR-004
def extract_datasets(document: Any) -> dict[str, list[dict[str, Any]]]:
    """トップレベル構造を判定し、6種類のデータの行の並びを取り出す。"""
    if not isinstance(document, dict):
        raise SeedError(ERROR_FILE_NOT_PARSABLE, "定義ファイルの最上位がオブジェクトではありません。")
    unknown = [key for key in document if key not in TOP_LEVEL_KEYS]
    if unknown:
        raise SeedError(
            ERROR_FILE_NOT_PARSABLE,
            f"定義ファイルに未知のキーがあります: {', '.join(sorted(unknown))}",
        )
    datasets: dict[str, list[dict[str, Any]]] = {}
    for key in TOP_LEVEL_KEYS:
        rows = document.get(key, [])
        if not isinstance(rows, list):
            raise SeedError(ERROR_FILE_NOT_PARSABLE, f"{key} が行の並び（配列）ではありません。")
        for row in rows:
            if not isinstance(row, dict):
                raise SeedError(ERROR_FILE_NOT_PARSABLE, f"{key} の行がオブジェクトではありません。")
        datasets[key] = rows
    return datasets


# trace: ADDR-004
def unknown_field_violations(datasets: dict[str, list[dict[str, Any]]]) -> list[Violation]:
    """項目名の別名・大文字小文字違い・未知の項目名を値域違反として収集する。"""
    violations: list[Violation] = []
    for key, rows in datasets.items():
        allowed = FIELDS[key]
        for index, row in enumerate(rows, start=1):
            for name in row:
                if name not in allowed:
                    violations.append(Violation(key, index, name, "定義されていない項目名です。"))
    return violations


# trace: ADDR-005
def text_value(row: dict[str, Any], name: str, *, strip: bool = True) -> Any:
    """行から文字列項目を取り出す（パスワード以外は前後の空白を除去する）。"""
    value = row.get(name)
    if value is None or not isinstance(value, str):
        return value
    return normalize_text(value) if strip else value


# trace: ADDR-005
def validate_string(
    violations: list[Violation],
    data_name: str,
    row_number: int,
    field_name: str,
    value: Any,
    *,
    required: bool,
    max_length: int,
    pattern: re.Pattern[str] | None = None,
    min_length: int = 1,
) -> str | None:
    """文字列項目の値域を判定する。"""
    if value is None or value == "":
        if required:
            violations.append(Violation(data_name, row_number, field_name, "必須項目が指定されていません。"))
            return None
        return ""
    if not isinstance(value, str):
        violations.append(Violation(data_name, row_number, field_name, "文字列で指定してください。"))
        return None
    if len(value) < min_length or len(value) > max_length:
        violations.append(
            Violation(data_name, row_number, field_name, f"{min_length}〜{max_length}文字で指定してください。")
        )
        return None
    if pattern is not None and not pattern.match(value):
        violations.append(Violation(data_name, row_number, field_name, "使用できない文字が含まれています。"))
        return None
    return value


# trace: ADDR-005
def validate_integer(
    violations: list[Violation],
    data_name: str,
    row_number: int,
    field_name: str,
    value: Any,
    *,
    required: bool,
    minimum: int,
    maximum: int,
    default: int | None = None,
) -> int | None:
    """整数項目の値域を判定する。"""
    if value is None:
        if required:
            violations.append(Violation(data_name, row_number, field_name, "必須項目が指定されていません。"))
            return None
        return default
    if isinstance(value, bool) or not isinstance(value, int):
        violations.append(Violation(data_name, row_number, field_name, "整数で指定してください。"))
        return None
    if value < minimum or value > maximum:
        violations.append(
            Violation(data_name, row_number, field_name, f"{minimum}以上{maximum}以下で指定してください。")
        )
        return None
    return value


# trace: ADDR-005
def validate_datetime(
    violations: list[Violation],
    data_name: str,
    row_number: int,
    field_name: str,
    value: Any,
    *,
    required: bool,
    default: dt.datetime | None = None,
) -> dt.datetime | None:
    """日時項目を JST の日時として解釈する。"""
    if value is None or value == "":
        if required:
            violations.append(Violation(data_name, row_number, field_name, "必須項目が指定されていません。"))
            return None
        return default
    if not isinstance(value, str):
        violations.append(Violation(data_name, row_number, field_name, "日時は文字列で指定してください。"))
        return None
    parsed = timeutils.parse_datetime(value)
    if parsed is None:
        violations.append(Violation(data_name, row_number, field_name, "日時として解釈できません。"))
        return None
    return parsed


# trace: ADDR-005
def validate_users(rows: list[dict[str, Any]], violations: list[Violation], loaded_at: dt.datetime) -> list[dict]:
    """利用者の値域を判定する。"""
    prepared: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        email_raw = text_value(row, "email")
        email = email_raw.lower() if isinstance(email_raw, str) else email_raw
        email = validate_string(violations, KEY_USERS, index, "email", email, required=True, max_length=254)
        if email and not is_email_format(email):
            violations.append(Violation(KEY_USERS, index, "email", "メールアドレスの形式ではありません。"))
            email = None
        password = row.get("password")
        if password is None or password == "":
            violations.append(Violation(KEY_USERS, index, "password", "必須項目が指定されていません。"))
            password = None
        elif not isinstance(password, str):
            violations.append(Violation(KEY_USERS, index, "password", "文字列で指定してください。"))
            password = None
        else:
            reasons = password_violations(password, email or "")
            for reason in reasons:
                violations.append(Violation(KEY_USERS, index, "password", reason))
            if reasons:
                password = None
        full_name = validate_string(
            violations, KEY_USERS, index, "full_name", text_value(row, "full_name"), required=True, max_length=50
        )
        role = text_value(row, "role")
        if role not in (ROLE_BUYER, ROLE_ADMIN):
            violations.append(Violation(KEY_USERS, index, "role", "buyer または admin を指定してください。"))
            role = None
        if email and password and full_name and role:
            prepared.append(
                {
                    "row": index,
                    "email": email,
                    "password": password,
                    "full_name": full_name,
                    "role": role,
                    "registered_at": loaded_at,
                }
            )
        elif email:
            prepared.append({"row": index, "email": email, "invalid": True})
    return prepared


# trace: ADDR-005
def validate_suppliers(rows: list[dict[str, Any]], violations: list[Violation]) -> list[dict]:
    """仕入先の値域を判定する。"""
    prepared: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        code = validate_string(
            violations,
            KEY_SUPPLIERS,
            index,
            "supplier_code",
            text_value(row, "supplier_code"),
            required=True,
            max_length=20,
            pattern=SUPPLIER_CODE_PATTERN,
        )
        name = validate_string(
            violations, KEY_SUPPLIERS, index, "name", text_value(row, "name"), required=True, max_length=100
        )
        prepared.append({"row": index, "supplier_code": code, "name": name})
    return prepared


# trace: ADDR-005
def validate_collections(rows: list[dict[str, Any]], violations: list[Violation]) -> list[dict]:
    """商品分類の値域を判定する。"""
    prepared: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        code = validate_string(
            violations,
            KEY_COLLECTIONS,
            index,
            "collection_code",
            text_value(row, "collection_code"),
            required=True,
            max_length=30,
            pattern=COLLECTION_CODE_PATTERN,
        )
        name = validate_string(
            violations, KEY_COLLECTIONS, index, "name", text_value(row, "name"), required=True, max_length=50
        )
        parent_code = validate_string(
            violations,
            KEY_COLLECTIONS,
            index,
            "parent_collection_code",
            text_value(row, "parent_collection_code"),
            required=False,
            max_length=30,
            pattern=COLLECTION_CODE_PATTERN,
        )
        sort_order = validate_integer(
            violations,
            KEY_COLLECTIONS,
            index,
            "sort_order",
            row.get("sort_order"),
            required=False,
            minimum=0,
            maximum=999,
            default=0,
        )
        prepared.append(
            {
                "row": index,
                "collection_code": code,
                "name": name,
                "parent_collection_code": parent_code or None,
                "sort_order": sort_order if sort_order is not None else 0,
            }
        )
    return prepared


# trace: ADDR-005
def validate_items(rows: list[dict[str, Any]], violations: list[Violation], loaded_at: dt.datetime) -> list[dict]:
    """商品の値域を判定する。"""
    prepared: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        code = validate_string(
            violations,
            KEY_ITEMS,
            index,
            "item_code",
            text_value(row, "item_code"),
            required=True,
            max_length=20,
            pattern=ITEM_CODE_PATTERN,
        )
        name = validate_string(
            violations, KEY_ITEMS, index, "name", text_value(row, "name"), required=True, max_length=100
        )
        description = validate_string(
            violations,
            KEY_ITEMS,
            index,
            "description",
            text_value(row, "description"),
            required=False,
            max_length=2000,
            min_length=0,
        )
        is_public = row.get("is_public")
        if is_public is None:
            is_public = True
        elif not isinstance(is_public, bool):
            violations.append(Violation(KEY_ITEMS, index, "is_public", "真偽値で指定してください。"))
            is_public = None
        collection_codes = row.get("collection_codes")
        codes: list[str] = []
        if collection_codes is None:
            collection_codes = []
        if not isinstance(collection_codes, list):
            violations.append(Violation(KEY_ITEMS, index, "collection_codes", "分類コードの配列で指定してください。"))
        else:
            for code_value in collection_codes:
                if not isinstance(code_value, str) or not COLLECTION_CODE_PATTERN.match(normalize_text(code_value)):
                    violations.append(
                        Violation(KEY_ITEMS, index, "collection_codes", "分類コードの形式ではありません。")
                    )
                else:
                    codes.append(normalize_text(code_value))
        created_at = validate_datetime(
            violations, KEY_ITEMS, index, "created_at", row.get("created_at"), required=False, default=loaded_at
        )
        prepared.append(
            {
                "row": index,
                "item_code": code,
                "name": name,
                "description": description or "",
                "is_public": is_public,
                "collection_codes": codes,
                "created_at": created_at or loaded_at,
            }
        )
    return prepared


# trace: ADDR-005
def validate_stock_units(rows: list[dict[str, Any]], violations: list[Violation]) -> list[dict]:
    """在庫単位の値域を判定する。"""
    prepared: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        sku = validate_string(
            violations,
            KEY_STOCK_UNITS,
            index,
            "sku",
            text_value(row, "sku"),
            required=True,
            max_length=32,
            pattern=SKU_PATTERN,
        )
        item_code = validate_string(
            violations,
            KEY_STOCK_UNITS,
            index,
            "item_code",
            text_value(row, "item_code"),
            required=True,
            max_length=20,
            pattern=ITEM_CODE_PATTERN,
        )
        supplier_code = validate_string(
            violations,
            KEY_STOCK_UNITS,
            index,
            "supplier_code",
            text_value(row, "supplier_code"),
            required=True,
            max_length=20,
            pattern=SUPPLIER_CODE_PATTERN,
        )
        variant_name = validate_string(
            violations,
            KEY_STOCK_UNITS,
            index,
            "variant_name",
            text_value(row, "variant_name"),
            required=True,
            max_length=50,
        )
        price = validate_integer(
            violations, KEY_STOCK_UNITS, index, "price", row.get("price"), required=True, minimum=0, maximum=9999999
        )
        quantity = validate_integer(
            violations, KEY_STOCK_UNITS, index, "quantity", row.get("quantity"), required=True, minimum=0, maximum=99999
        )
        prepared.append(
            {
                "row": index,
                "sku": sku,
                "item_code": item_code,
                "supplier_code": supplier_code,
                "variant_name": variant_name,
                "price": price,
                "quantity": quantity,
            }
        )
    return prepared


# trace: ADDR-005
def validate_coupons(rows: list[dict[str, Any]], violations: list[Violation]) -> list[dict]:
    """クーポンの値域を判定する。"""
    prepared: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        code = validate_string(
            violations,
            KEY_COUPONS,
            index,
            "code",
            text_value(row, "code"),
            required=True,
            max_length=20,
            pattern=COUPON_CODE_PATTERN,
        )
        name = validate_string(
            violations, KEY_COUPONS, index, "name", text_value(row, "name"), required=True, max_length=50
        )
        discount_type = text_value(row, "discount_type")
        if discount_type not in (DISCOUNT_FIXED, DISCOUNT_PERCENTAGE):
            violations.append(
                Violation(KEY_COUPONS, index, "discount_type", "fixed または percentage を指定してください。")
            )
            discount_type = None
        maximum = 100 if discount_type == DISCOUNT_PERCENTAGE else 9999999
        discount_value = validate_integer(
            violations,
            KEY_COUPONS,
            index,
            "discount_value",
            row.get("discount_value"),
            required=True,
            minimum=1,
            maximum=maximum,
        )
        min_spend = validate_integer(
            violations,
            KEY_COUPONS,
            index,
            "min_spend",
            row.get("min_spend"),
            required=False,
            minimum=0,
            maximum=9999999,
            default=0,
        )
        valid_from = validate_datetime(
            violations, KEY_COUPONS, index, "valid_from", row.get("valid_from"), required=True
        )
        valid_until = validate_datetime(
            violations, KEY_COUPONS, index, "valid_until", row.get("valid_until"), required=True
        )
        if valid_from and valid_until and valid_from > valid_until:
            violations.append(
                Violation(KEY_COUPONS, index, "valid_until", "有効開始日時以降の日時を指定してください。")
            )
        prepared.append(
            {
                "row": index,
                "code": code,
                "name": name,
                "discount_type": discount_type,
                "discount_value": discount_value,
                "min_spend": min_spend if min_spend is not None else 0,
                "valid_from": valid_from,
                "valid_until": valid_until,
            }
        )
    return prepared


# trace: ADDR-005
def check_unique(
    prepared: list[dict[str, Any]],
    data_name: str,
    field_name: str,
    existing: set[str],
    violations: list[Violation],
) -> None:
    """業務キーの重複（定義ファイル内・登録済みデータとの重複）を判定する。"""
    seen: set[str] = set()
    for row in prepared:
        value = row.get(field_name)
        if not value:
            continue
        if value in seen or value in existing:
            violations.append(Violation(data_name, row["row"], field_name, "業務キーが重複しています。"))
        seen.add(value)


# trace: ADDR-005
def check_collection_structure(
    collections: list[dict[str, Any]],
    existing_parents: dict[str, str | None],
    existing_names: set[tuple[str | None, str]],
    violations: list[Violation],
) -> dict[str, int]:
    """商品分類の親子関係（深さ・循環）と同じ親の中の分類名の一意性を判定する。"""
    parents: dict[str, str | None] = dict(existing_parents)
    for row in collections:
        code = row.get("collection_code")
        if code:
            parents[code] = row.get("parent_collection_code")

    names: set[tuple[str | None, str]] = set(existing_names)
    for row in collections:
        code = row.get("collection_code")
        name = row.get("name")
        if not code or not name:
            continue
        key = (row.get("parent_collection_code"), name)
        if key in names:
            violations.append(
                Violation(KEY_COLLECTIONS, row["row"], "name", "同じ親分類の中で分類名が重複しています。")
            )
        names.add(key)

    depths: dict[str, int] = {}
    for row in collections:
        code = row.get("collection_code")
        if not code:
            continue
        depth = 0
        current: str | None = code
        visited: set[str] = set()
        while current is not None:
            if current in visited:
                violations.append(
                    Violation(KEY_COLLECTIONS, row["row"], "parent_collection_code", "親分類が循環しています。")
                )
                depth = -1
                break
            visited.add(current)
            depth += 1
            parent = parents.get(current, "__missing__")
            if parent == "__missing__":
                violations.append(
                    Violation(KEY_COLLECTIONS, row["row"], "parent_collection_code", "参照先の分類が存在しません。")
                )
                depth = -1
                break
            current = parent
        if depth > MAX_DEPTH:
            violations.append(
                Violation(KEY_COLLECTIONS, row["row"], "parent_collection_code", "分類の深さが3を超えています。")
            )
        if depth > 0:
            depths[code] = depth
    return depths


# trace: ADDR-005
def check_references(
    items: list[dict[str, Any]],
    stock_units: list[dict[str, Any]],
    collection_codes: set[str],
    item_codes: set[str],
    supplier_codes: set[str],
    violations: list[Violation],
) -> None:
    """商品の所属分類、在庫単位の商品・仕入先の参照整合性を判定する。"""
    for row in items:
        seen: set[str] = set()
        for code in row.get("collection_codes", []):
            if code not in collection_codes:
                violations.append(Violation(KEY_ITEMS, row["row"], "collection_codes", "参照先の分類が存在しません。"))
            if code in seen:
                violations.append(Violation(KEY_ITEMS, row["row"], "collection_codes", "同じ分類が重複しています。"))
            seen.add(code)
    for row in stock_units:
        if row.get("item_code") and row["item_code"] not in item_codes:
            violations.append(Violation(KEY_STOCK_UNITS, row["row"], "item_code", "参照先の商品が存在しません。"))
        if row.get("supplier_code") and row["supplier_code"] not in supplier_codes:
            violations.append(Violation(KEY_STOCK_UNITS, row["row"], "supplier_code", "参照先の仕入先が存在しません。"))


# trace: ADDR-005
def delete_all_except_audit_logs() -> None:
    """監査ログ以外の全データを削除する（全削除指定。NFR-SC-23）。"""
    PurchaseOrderStatusHistory.objects.all().delete()
    PaymentRecord.objects.all().delete()
    ShippingAddress.objects.all().delete()
    PurchaseOrderLine.objects.all().delete()
    PurchaseOrder.objects.all().delete()
    OrderNumberSequence.objects.all().delete()
    CartLine.objects.all().delete()
    Cart.objects.all().delete()
    ItemCollection.objects.all().delete()
    StockUnit.objects.all().delete()
    Item.objects.all().delete()
    Collection.objects.all().delete()
    Supplier.objects.all().delete()
    Coupon.objects.all().delete()
    User.objects.all().delete()


# trace: ADDR-005, FILE-001
def load_initial_data(path: str, *, reset: bool) -> LoadResult:
    """定義ファイルの内容を検証し、違反がなければ一括で投入する（FR-060）。"""
    loaded_at = timeutils.now()
    document = read_definition_file(path)
    datasets = extract_datasets(document)

    violations: list[Violation] = unknown_field_violations(datasets)
    users = validate_users(datasets[KEY_USERS], violations, loaded_at)
    suppliers = validate_suppliers(datasets[KEY_SUPPLIERS], violations)
    collections = validate_collections(datasets[KEY_COLLECTIONS], violations)
    items = validate_items(datasets[KEY_ITEMS], violations, loaded_at)
    stock_units = validate_stock_units(datasets[KEY_STOCK_UNITS], violations)
    coupons = validate_coupons(datasets[KEY_COUPONS], violations)

    if reset:
        existing_emails: set[str] = set()
        existing_supplier_codes: set[str] = set()
        existing_collection_codes: set[str] = set()
        existing_item_codes: set[str] = set()
        existing_skus: set[str] = set()
        existing_coupon_codes: set[str] = set()
        existing_parents: dict[str, str | None] = {}
        existing_names: set[tuple[str | None, str]] = set()
    else:
        existing_emails = set(User.objects.values_list("email", flat=True))
        existing_supplier_codes = set(Supplier.objects.values_list("supplier_code", flat=True))
        existing_collection_codes = set(Collection.objects.values_list("collection_code", flat=True))
        existing_item_codes = set(Item.objects.values_list("item_code", flat=True))
        existing_skus = set(StockUnit.objects.values_list("sku", flat=True))
        existing_coupon_codes = set(Coupon.objects.values_list("code", flat=True))
        existing_parents = {}
        existing_names = set()
        parent_codes = {
            collection.pk: collection.collection_code
            for collection in Collection.objects.all().only("id", "collection_code")
        }
        for collection in Collection.objects.all().only("id", "collection_code", "name", "parent_id"):
            parent_code = parent_codes.get(collection.parent_id) if collection.parent_id else None
            existing_parents[collection.collection_code] = parent_code
            existing_names.add((parent_code, collection.name))

    check_unique(users, KEY_USERS, "email", existing_emails, violations)
    check_unique(suppliers, KEY_SUPPLIERS, "supplier_code", existing_supplier_codes, violations)
    check_unique(collections, KEY_COLLECTIONS, "collection_code", existing_collection_codes, violations)
    check_unique(items, KEY_ITEMS, "item_code", existing_item_codes, violations)
    check_unique(stock_units, KEY_STOCK_UNITS, "sku", existing_skus, violations)
    check_unique(coupons, KEY_COUPONS, "code", existing_coupon_codes, violations)

    depths = check_collection_structure(collections, existing_parents, existing_names, violations)
    collection_codes = existing_collection_codes | {
        row["collection_code"] for row in collections if row.get("collection_code")
    }
    item_codes = existing_item_codes | {row["item_code"] for row in items if row.get("item_code")}
    supplier_codes = existing_supplier_codes | {
        row["supplier_code"] for row in suppliers if row.get("supplier_code")
    }
    check_references(items, stock_units, collection_codes, item_codes, supplier_codes, violations)

    if violations:
        raise SeedError(ERROR_VALUE_RANGE, "定義ファイルに違反があります。", violations)

    with transaction.atomic():
        if reset:
            delete_all_except_audit_logs()
        counts = persist(users, suppliers, collections, items, stock_units, coupons, depths, loaded_at)
        record_audit(
            event_type=EVENT_INITIAL_DATA_LOAD,
            result=RESULT_SUCCESS,
            user_id=None,
            detail=", ".join(f"{name}={count}" for name, count in counts.items()),
            occurred_at=loaded_at,
        )
    return LoadResult(counts=counts)


# trace: ADDR-005
def persist(
    users: list[dict[str, Any]],
    suppliers: list[dict[str, Any]],
    collections: list[dict[str, Any]],
    items: list[dict[str, Any]],
    stock_units: list[dict[str, Any]],
    coupons: list[dict[str, Any]],
    depths: dict[str, int],
    loaded_at: dt.datetime,
) -> dict[str, int]:
    """検証済みのデータを登録する（仕入先→商品分類→商品→所属→在庫単位→クーポン→利用者）。"""
    supplier_map = {
        supplier.supplier_code: supplier for supplier in Supplier.objects.all().only("id", "supplier_code")
    }
    for row in suppliers:
        supplier = Supplier.objects.create(supplier_code=row["supplier_code"], name=row["name"])
        supplier_map[supplier.supplier_code] = supplier

    collection_map = {
        collection.collection_code: collection
        for collection in Collection.objects.all().only("id", "collection_code")
    }
    pending = list(collections)
    while pending:
        progressed = False
        remaining: list[dict[str, Any]] = []
        for row in pending:
            parent_code = row["parent_collection_code"]
            if parent_code and parent_code not in collection_map:
                remaining.append(row)
                continue
            collection = Collection.objects.create(
                collection_code=row["collection_code"],
                name=row["name"],
                parent=collection_map.get(parent_code) if parent_code else None,
                depth=depths.get(row["collection_code"], 1),
                sort_order=row["sort_order"],
            )
            collection_map[collection.collection_code] = collection
            progressed = True
        pending = remaining
        if not progressed:
            break

    item_map = {item.item_code: item for item in Item.objects.all().only("id", "item_code")}
    item_collection_count = 0
    for row in items:
        item = Item.objects.create(
            item_code=row["item_code"],
            name=row["name"],
            description=row["description"],
            is_public=row["is_public"],
            created_at=row["created_at"],
        )
        item_map[item.item_code] = item
        for code in row["collection_codes"]:
            ItemCollection.objects.create(item=item, collection=collection_map[code])
            item_collection_count += 1

    for row in stock_units:
        StockUnit.objects.create(
            item=item_map[row["item_code"]],
            supplier=supplier_map[row["supplier_code"]],
            sku=row["sku"],
            variant_name=row["variant_name"],
            price=row["price"],
            quantity=row["quantity"],
            updated_at=loaded_at,
        )

    for row in coupons:
        Coupon.objects.create(
            code=row["code"],
            name=row["name"],
            discount_type=row["discount_type"],
            discount_value=row["discount_value"],
            min_spend=row["min_spend"],
            valid_from=row["valid_from"],
            valid_until=row["valid_until"],
        )

    for row in users:
        User.objects.create(
            email=row["email"],
            password_hash=hash_password(row["password"]),
            full_name=row["full_name"],
            role=row["role"],
            registered_at=row["registered_at"],
        )

    return {
        KEY_USERS: len(users),
        KEY_SUPPLIERS: len(suppliers),
        KEY_COLLECTIONS: len(collections),
        KEY_ITEMS: len(items),
        "item_collections": item_collection_count,
        KEY_STOCK_UNITS: len(stock_units),
        KEY_COUPONS: len(coupons),
    }


# trace: ADDR-005
def record_failure(occurred_at: dt.datetime | None = None) -> None:
    """失敗時の監査ログ（結果＝失敗）を1件記録する。"""
    record_audit(
        event_type=EVENT_INITIAL_DATA_LOAD,
        result=RESULT_FAILURE,
        user_id=None,
        detail="",
        occurred_at=occurred_at,
    )
