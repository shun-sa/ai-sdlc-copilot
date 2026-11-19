# trace: FILE-001, ADDR-009, ADDR-010, ADDR-004, ADDR-002, ADDR-003, ADDR-006, ADDR-007
# trace: ENT-001, ENT-002, ENT-003, ENT-004, ENT-005, ENT-006, ENT-007, ENT-015
"""初期データ一括投入（FR-060）の業務処理。定義ファイル（FILE-001）の記載形式は ADDR-009 に従う。

処理順（ADDR-010 4.3 の3）：読込み（E-060-02）→ 記載形式の解釈（E-060-03）→ 値域の全件判定（E-060-04）
→ アドバイザリロック取得後に一意性・参照整合性の全件判定（E-060-05）→ 削除・登録・成功の監査ログを1トランザクション。
失敗時は全体をロールバックした後、別のトランザクションで失敗の監査ログを1件記録する（ADDR-004 DD-007・DD-008）。
違反の提示・ログに項目の値（パスワード・メールアドレス・氏名を含む）を出さない（ADDR-009 DD-006、ADDR-010 DD-005）。
"""

import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from django.contrib.auth.hashers import make_password
from django.db import DatabaseError, IntegrityError, connection, transaction

from accounts.models import User
from accounts.services import delete_all_login_states, email_violations, name_violations, password_violations
from audit import services as audit
from carts.models import Cart, CartItem
from catalog.models import Category, Product, ProductCategory, StockUnit, Supplier
from common import clock
from common.codes import DiscountType, UserType, Visibility
from common.logging import log_error, log_job
from common.normalize import has_surrogates, has_unstorable_chars
from orders.models import Order, OrderItem, OrderStatusHistory, PaymentRecord, ShippingAddress
from promotions.models import Coupon

# 一括投入どうしを直列化する固定キー（ADDR-004 DD-008。注文番号・送信トークンのキーと区別する）
INITIAL_DATA_LOCK_KEY = 7_013_000_002

DATA_KEYS = ("users", "suppliers", "categories", "products", "stock_units", "coupons")
DATA_LABELS = {
    "users": "利用者",
    "suppliers": "仕入先",
    "categories": "商品分類",
    "products": "商品",
    "stock_units": "在庫単位",
    "coupons": "クーポン",
}
FIELD_LABELS: dict[str, dict[str, str]] = {
    "users": {"email": "メールアドレス", "password": "パスワード", "name": "氏名", "user_type": "利用者区分"},
    "suppliers": {"supplier_code": "仕入先コード", "name": "仕入先名"},
    "categories": {
        "category_code": "分類コード",
        "name": "分類名",
        "parent_category_code": "親分類",
        "display_order": "表示順",
    },
    "products": {
        "product_code": "商品コード",
        "name": "商品名",
        "description": "商品説明",
        "visibility": "公開状態",
        "category_codes": "所属分類",
        "registered_at": "登録日時",
    },
    "stock_units": {
        "sku": "SKU",
        "product_code": "商品",
        "supplier_code": "仕入先",
        "variant_name": "規格名",
        "price_excluding_tax": "税抜価格",
        "stock_quantity": "在庫数量",
    },
    "coupons": {
        "coupon_code": "クーポンコード",
        "name": "表示名",
        "discount_type": "割引方式",
        "discount_value": "割引値",
        "minimum_purchase_amount": "最低購入金額",
        "valid_from": "有効開始日時",
        "valid_to": "有効終了日時",
    },
}
COUNT_KEYS = ("users", "suppliers", "categories", "products", "product_categories", "stock_units", "coupons")
COUNT_LABELS = {**DATA_LABELS, "product_categories": "商品分類所属"}

_UPPER_CODE = re.compile(r"^[A-Z0-9-]+\Z")
_LOWER_CODE = re.compile(r"^[a-z0-9-]+\Z")
_DATETIME = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\+09:00)?\Z")
_WHITESPACE = " \t\r\n\u3000"

R_REQUIRED = "必須項目が指定されていません"
R_STRING = "文字列で指定してください"
R_NUMBER = "数値として解釈できない値です"
R_DATETIME = "日時として解釈できない値です"
R_CHOICE = "選択肢以外の値です"
R_CHARSET_UPPER = "英大文字・数字・ハイフン以外の文字が含まれています"
R_CHARSET_LOWER = "英小文字・数字・ハイフン以外の文字が含まれています"
R_PERIOD = "有効開始日時が有効終了日時より後です"
R_DUP_FILE = "業務キーが定義ファイル内で重複しています"
R_DUP_DB = "業務キーが登録済みのデータと重複しています"
R_DUP_NAME = "同じ親分類の中で分類名が重複しています"
R_DUP_CATEGORY = "同じ商品で所属分類が重複して指定されています"
R_MISSING_REF = "参照先が存在しません"
R_TOO_DEEP = "分類の階層が4階層目以降になります"
R_CYCLE = "親分類をたどると循環しています（最上位の分類に到達しません）"
R_UNSTORABLE = "使用できない文字（制御文字等）が含まれています"


# trace: FILE-001, ADDR-009
@dataclass(frozen=True)
class Violation:
    """違反1件（データ名・行番号・項目名・理由。値は持たない）。"""

    data: str
    row: int
    field_key: str
    reason: str
    kind: str  # value（E-060-04）/ integrity（E-060-05）

    def text(self) -> str:
        label = FIELD_LABELS[self.data].get(self.field_key, self.field_key)
        return f"{DATA_LABELS[self.data]} {self.row}行目 {label}（{self.field_key}）：{self.reason}"

    def as_log(self) -> dict[str, Any]:
        return {
            "data": DATA_LABELS[self.data],
            "row": self.row,
            "field": f"{FIELD_LABELS[self.data].get(self.field_key, self.field_key)}（{self.field_key}）",
            "reason": self.reason,
        }


# trace: FILE-001, ADDR-010
class LoadError(Exception):
    """初期データ一括投入の失敗（E-060-01〜E-060-06）。"""

    def __init__(self, code: str, message: str, violations: list[Violation] | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.message = message
        self.violations = list(violations or [])


# trace: FILE-001, ADDR-009
@dataclass
class Row:
    number: int
    values: dict[str, Any] = field(default_factory=dict)
    invalid: set[str] = field(default_factory=set)


# trace: FILE-001, ADDR-010
def zero_counts() -> dict[str, int]:
    return {key: 0 for key in COUNT_KEYS}


# trace: FILE-001, ADDR-010
def counts_text(counts: dict[str, int]) -> str:
    return "、".join(f"{COUNT_LABELS[key]} {counts.get(key, 0)}件" for key in COUNT_KEYS)


# ---------------------------------------------------------------------------
# 読込み・記載形式の解釈（E-060-02・E-060-03）
# ---------------------------------------------------------------------------


# trace: FILE-001, ADDR-010
def read_file(path: str) -> bytes:
    """引数で受け取ったパスだけを開く（シェル・OS コマンドを経由しない：ADDR-010 DD-008）。"""
    try:
        with open(path, "rb") as handle:
            return handle.read()
    except OSError:
        raise LoadError(
            "E-060-02", f"定義ファイルが見つからない、または読み込めません（指定された定義ファイル：{path}）。"
        ) from None


# trace: FILE-001, ADDR-009
def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


# trace: FILE-001, ADDR-009
def _reject_constant(_name: str) -> Any:
    raise ValueError("non-standard JSON constant")


# trace: FILE-001, ADDR-009
def parse_document(raw: bytes) -> dict[str, list[dict[str, Any]]]:
    """UTF-8（BOM 可）の JSON を解釈し、6種類のデータの行オブジェクトの配列を取り出す（ADDR-009 DD-001〜DD-003）。"""
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise LoadError("E-060-03", "定義ファイルを解釈できません（理由：文字コードの誤り）。") from None
    format_error = LoadError("E-060-03", "定義ファイルを解釈できません（理由：記載形式の誤り）。")
    try:
        document = json.loads(text, object_pairs_hook=_reject_duplicates, parse_constant=_reject_constant)
    except (ValueError, RecursionError):
        raise format_error from None
    if not isinstance(document, dict):
        raise format_error
    result: dict[str, list[dict[str, Any]]] = {}
    for key, rows in document.items():
        if key not in DATA_KEYS or not isinstance(rows, list):
            raise format_error
        for row in rows:
            if not isinstance(row, dict):
                raise format_error
            if any(column not in FIELD_LABELS[key] for column in row):
                raise format_error
        result[key] = rows
    for key in DATA_KEYS:
        result.setdefault(key, [])
    return result


# ---------------------------------------------------------------------------
# 値域の判定（E-060-04）
# ---------------------------------------------------------------------------


# trace: FILE-001, ADDR-009
class _Checker:
    def __init__(self) -> None:
        self.violations: list[Violation] = []

    def add(self, data: str, row: Row, key: str, reason: str) -> None:
        row.invalid.add(key)
        self.violations.append(Violation(data, row.number, key, reason, "value"))

    def text(self, data: str, row: Row, source: dict[str, Any], key: str, max_len: int, *, required: bool) -> None:
        value = source.get(key)
        if value is None:
            if required:
                self.add(data, row, key, R_REQUIRED)
            else:
                row.values[key] = None
            return
        if not isinstance(value, str):
            self.add(data, row, key, R_STRING)
            return
        if has_unstorable_chars(value):
            self.add(data, row, key, R_UNSTORABLE)
            return
        value = value.strip(_WHITESPACE)
        minimum = 1 if required else 0
        if not minimum <= len(value) <= max_len:
            self.add(data, row, key, f"文字数が範囲外です（{minimum}〜{max_len}文字）")
            return
        row.values[key] = value

    def code(
        self,
        data: str,
        row: Row,
        source: dict[str, Any],
        key: str,
        max_len: int,
        pattern: re.Pattern[str],
        charset_reason: str,
        *,
        required: bool = True,
    ) -> None:
        self.text(data, row, source, key, max_len, required=required)
        value = row.values.get(key)
        if isinstance(value, str) and value and not pattern.match(value):
            row.values.pop(key, None)
            self.add(data, row, key, charset_reason)

    def integer(
        self, data: str, row: Row, source: dict[str, Any], key: str, low: int, high: int, *, default: int | None
    ) -> None:
        value = source.get(key)
        if value is None:
            if default is None:
                self.add(data, row, key, R_REQUIRED)
            else:
                row.values[key] = default
            return
        if isinstance(value, bool) or not isinstance(value, int):
            self.add(data, row, key, R_NUMBER)
            return
        if not low <= value <= high:
            self.add(data, row, key, f"数値の範囲外です（{low:,}〜{high:,}）")
            return
        row.values[key] = value

    def choice(
        self, data: str, row: Row, source: dict[str, Any], key: str, choices: list[str], *, default: str | None
    ) -> None:
        value = source.get(key)
        if value is None:
            if default is None:
                self.add(data, row, key, R_REQUIRED)
            else:
                row.values[key] = default
            return
        if not isinstance(value, str):
            self.add(data, row, key, R_STRING)
            return
        value = value.strip(_WHITESPACE)
        if value not in choices:
            self.add(data, row, key, R_CHOICE)
            return
        row.values[key] = value

    def moment(self, data: str, row: Row, source: dict[str, Any], key: str, *, default: datetime | None) -> None:
        value = source.get(key)
        if value is None:
            if default is None:
                self.add(data, row, key, R_REQUIRED)
            else:
                row.values[key] = default
            return
        if not isinstance(value, str):
            self.add(data, row, key, R_DATETIME)
            return
        value = value.strip(_WHITESPACE)
        if not _DATETIME.match(value):
            self.add(data, row, key, R_DATETIME)
            return
        try:
            parsed = datetime.strptime(value[:19], "%Y-%m-%dT%H:%M:%S")
            moment_value = parsed.replace(tzinfo=clock.JST)
            # 協定世界時へ変換できない日時（0001-01-01T09:00:00 より前）はデータベースから読み戻せないため
            # 日時として解釈できない値とする（保存後の照会・画面表示での範囲外を防ぐ：NFR-SC-04）
            moment_value.astimezone(UTC)
        except (ValueError, OverflowError):
            self.add(data, row, key, R_DATETIME)
            return
        row.values[key] = moment_value


# trace: FILE-001, ADDR-009, ADDR-003, ENT-001
def _check_users(checker: _Checker, rows: list[dict[str, Any]]) -> list[Row]:
    result = []
    for number, source in enumerate(rows, 1):
        row = Row(number)
        email = source.get("email")
        if isinstance(email, str):
            email = email.strip(_WHITESPACE).lower()
        violations = email_violations(email)
        if violations:
            reason_code, _ = violations[0]
            reason = {
                "required": R_REQUIRED,
                "invalid_type": R_STRING,
                "invalid_length": "文字数が範囲外です（1〜254文字）",
            }.get(reason_code, "メールアドレスの形式ではありません")
            if has_unstorable_chars(email):
                reason = R_UNSTORABLE
            checker.add("users", row, "email", reason)
        else:
            row.values["email"] = email
        password = source.get("password")
        password_issues = password_violations(password, row.values.get("email"))
        if password_issues:
            reason_code, _ = password_issues[0]
            reason = {"required": R_REQUIRED, "invalid_type": R_STRING}.get(
                reason_code,
                "パスワードの条件（8〜64文字、英字と数字を各1文字以上、メールアドレスと異なる）を満たしていません",
            )
            if has_surrogates(password):
                reason = R_UNSTORABLE
            checker.add("users", row, "password", reason)
        else:
            row.values["password"] = password
        name = source.get("name")
        if isinstance(name, str):
            name = name.strip(_WHITESPACE)
        name_issues = name_violations(name)
        if name_issues:
            reason_code, _ = name_issues[0]
            reason = {"required": R_REQUIRED, "invalid_type": R_STRING}.get(
                reason_code, "文字数が範囲外です（1〜50文字）"
            )
            if has_unstorable_chars(name):
                reason = R_UNSTORABLE
            checker.add("users", row, "name", reason)
        else:
            row.values["name"] = name
        checker.choice("users", row, source, "user_type", list(UserType.values), default=None)
        result.append(row)
    return result


# trace: FILE-001, ADDR-009, ENT-002
def _check_suppliers(checker: _Checker, rows: list[dict[str, Any]]) -> list[Row]:
    result = []
    for number, source in enumerate(rows, 1):
        row = Row(number)
        checker.code("suppliers", row, source, "supplier_code", 20, _UPPER_CODE, R_CHARSET_UPPER)
        checker.text("suppliers", row, source, "name", 100, required=True)
        result.append(row)
    return result


# trace: FILE-001, ADDR-009, ENT-003
def _check_categories(checker: _Checker, rows: list[dict[str, Any]]) -> list[Row]:
    result = []
    for number, source in enumerate(rows, 1):
        row = Row(number)
        checker.code("categories", row, source, "category_code", 30, _LOWER_CODE, R_CHARSET_LOWER)
        checker.text("categories", row, source, "name", 50, required=True)
        if source.get("parent_category_code") is None:
            row.values["parent_category_code"] = None
        else:
            checker.code("categories", row, source, "parent_category_code", 30, _LOWER_CODE, R_CHARSET_LOWER)
        checker.integer("categories", row, source, "display_order", 0, 999, default=0)
        result.append(row)
    return result


# trace: FILE-001, ADDR-009, ENT-004, ENT-005
def _check_products(checker: _Checker, rows: list[dict[str, Any]], now: datetime) -> list[Row]:
    result = []
    for number, source in enumerate(rows, 1):
        row = Row(number)
        checker.code("products", row, source, "product_code", 20, _UPPER_CODE, R_CHARSET_UPPER)
        checker.text("products", row, source, "name", 100, required=True)
        checker.text("products", row, source, "description", 2000, required=False)
        if row.values.get("description") is None and "description" not in row.invalid:
            row.values["description"] = ""
        checker.choice("products", row, source, "visibility", list(Visibility.values), default=Visibility.PUBLIC)
        codes_value = source.get("category_codes")
        if codes_value is None:
            row.values["category_codes"] = []
        elif not isinstance(codes_value, list):
            checker.add("products", row, "category_codes", "分類コードの並びとして解釈できない値です")
        else:
            normalized: list[str] = []
            bad = False
            for item in codes_value:
                if not isinstance(item, str):
                    bad = True
                    continue
                item = item.strip(_WHITESPACE)
                if not 1 <= len(item) <= 30 or not _LOWER_CODE.match(item):
                    bad = True
                    continue
                normalized.append(item)
            if bad:
                checker.add("products", row, "category_codes", "分類コードとして解釈できない値が含まれています")
            else:
                row.values["category_codes"] = normalized
        checker.moment("products", row, source, "registered_at", default=now)
        result.append(row)
    return result


# trace: FILE-001, ADDR-009, ENT-006
def _check_stock_units(checker: _Checker, rows: list[dict[str, Any]]) -> list[Row]:
    result = []
    for number, source in enumerate(rows, 1):
        row = Row(number)
        checker.code("stock_units", row, source, "sku", 32, _UPPER_CODE, R_CHARSET_UPPER)
        checker.code("stock_units", row, source, "product_code", 20, _UPPER_CODE, R_CHARSET_UPPER)
        checker.code("stock_units", row, source, "supplier_code", 20, _UPPER_CODE, R_CHARSET_UPPER)
        checker.text("stock_units", row, source, "variant_name", 50, required=True)
        checker.integer("stock_units", row, source, "price_excluding_tax", 0, 9_999_999, default=None)
        checker.integer("stock_units", row, source, "stock_quantity", 0, 99_999, default=None)
        result.append(row)
    return result


# trace: FILE-001, ADDR-009, ADDR-007, ENT-007
def _check_coupons(checker: _Checker, rows: list[dict[str, Any]]) -> list[Row]:
    result = []
    for number, source in enumerate(rows, 1):
        row = Row(number)
        checker.code("coupons", row, source, "coupon_code", 20, _UPPER_CODE, R_CHARSET_UPPER)
        checker.text("coupons", row, source, "name", 50, required=True)
        checker.choice("coupons", row, source, "discount_type", list(DiscountType.values), default=None)
        discount_type = row.values.get("discount_type")
        if discount_type == DiscountType.PERCENTAGE:
            checker.integer("coupons", row, source, "discount_value", 1, 100, default=None)
        elif discount_type == DiscountType.FIXED_AMOUNT:
            checker.integer("coupons", row, source, "discount_value", 1, 9_999_999, default=None)
        else:
            checker.integer("coupons", row, source, "discount_value", 1, 9_999_999, default=None)
        checker.integer("coupons", row, source, "minimum_purchase_amount", 0, 9_999_999, default=0)
        checker.moment("coupons", row, source, "valid_from", default=None)
        checker.moment("coupons", row, source, "valid_to", default=None)
        start, end = row.values.get("valid_from"), row.values.get("valid_to")
        if start is not None and end is not None and start > end:
            checker.add("coupons", row, "valid_from", R_PERIOD)
        result.append(row)
    return result


# trace: FILE-001, ADDR-009
@dataclass
class Parsed:
    users: list[Row]
    suppliers: list[Row]
    categories: list[Row]
    products: list[Row]
    stock_units: list[Row]
    coupons: list[Row]
    violations: list[Violation]


# trace: FILE-001, ADDR-009
def check_values(document: dict[str, list[dict[str, Any]]], now: datetime) -> Parsed:
    """全データの全行の値域を判定し、違反を中断せずに全件記録する（E-060-04）。"""
    checker = _Checker()
    parsed = Parsed(
        users=_check_users(checker, document["users"]),
        suppliers=_check_suppliers(checker, document["suppliers"]),
        categories=_check_categories(checker, document["categories"]),
        products=_check_products(checker, document["products"], now),
        stock_units=_check_stock_units(checker, document["stock_units"]),
        coupons=_check_coupons(checker, document["coupons"]),
        violations=[],
    )
    parsed.violations = checker.violations
    return parsed


# ---------------------------------------------------------------------------
# 一意性・参照整合性の判定（E-060-05）
# ---------------------------------------------------------------------------


# trace: FILE-001, ADDR-009, ENT-001, ENT-002, ENT-003, ENT-004, ENT-006, ENT-007
def check_integrity(parsed: Parsed, reset: bool) -> tuple[list[Violation], dict[str, int]]:
    """業務キーの重複・分類名の重複・所属分類の重複・参照先の存在・分類の階層を判定する。

    戻り値の2つ目はファイル内の分類コードごとの深さ（登録に用いる）。
    """
    violations: list[Violation] = []

    def add(data: str, row: Row, key: str, reason: str) -> None:
        violations.append(Violation(data, row.number, key, reason, "integrity"))

    def unique(data: str, rows: list[Row], key: str, existing: set[str]) -> set[str]:
        seen: set[str] = set()
        for row in rows:
            value = row.values.get(key)
            if not isinstance(value, str) or key in row.invalid:
                continue
            if value in seen:
                add(data, row, key, R_DUP_FILE)
            elif value in existing:
                add(data, row, key, R_DUP_DB)
            seen.add(value)
        return seen

    def db(values: Any) -> set[str]:
        return set() if reset else set(values)

    unique("users", parsed.users, "email", db(User.objects.values_list("email", flat=True)))
    supplier_codes = unique(
        "suppliers", parsed.suppliers, "supplier_code", db(Supplier.objects.values_list("supplier_code", flat=True))
    )
    db_categories: dict[str, tuple[str | None, int, str]] = {}
    if not reset:
        parents = dict(Category.objects.values_list("pk", "category_code"))
        for code, parent_id, depth, name in Category.objects.values_list("category_code", "parent_id", "depth", "name"):
            db_categories[code] = (parents.get(parent_id), depth, name)
    category_codes = unique("categories", parsed.categories, "category_code", set(db_categories))
    product_codes = unique(
        "products", parsed.products, "product_code", db(Product.objects.values_list("product_code", flat=True))
    )
    unique("stock_units", parsed.stock_units, "sku", db(StockUnit.objects.values_list("sku", flat=True)))
    unique("coupons", parsed.coupons, "coupon_code", db(Coupon.objects.values_list("coupon_code", flat=True)))

    # 分類：同じ親分類の中の分類名の一意性（最上位どうしを含む）
    db_names = {(parent, name) for parent, _depth, name in db_categories.values()}
    seen_names: set[tuple[str | None, str]] = set()
    for row in parsed.categories:
        name = row.values.get("name")
        if not isinstance(name, str) or "parent_category_code" in row.invalid:
            continue
        group = (row.values.get("parent_category_code"), name)
        parent = group[0]
        if group in seen_names:
            add("categories", row, "name", R_DUP_NAME)
        elif (parent is None or parent in db_categories) and group in db_names:
            add("categories", row, "name", R_DUP_NAME)
        seen_names.add(group)

    # 分類：親分類の参照・階層・循環
    file_parents: dict[str, str | None] = {}
    for row in parsed.categories:
        code = row.values.get("category_code")
        if isinstance(code, str) and code not in file_parents and code not in db_categories:
            file_parents[code] = row.values.get("parent_category_code")
    known_codes = set(file_parents) | set(db_categories)
    depths: dict[str, int] = {}
    state: dict[str, str] = {}

    def resolve(code: str) -> int | str:
        if code in db_categories:
            return db_categories[code][1]
        if code in depths:
            return depths[code]
        if state.get(code) == "visiting":
            return "cycle"
        if code not in file_parents:
            return "missing"
        state[code] = "visiting"
        parent = file_parents[code]
        if parent is None:
            result: int | str = 1
        else:
            upper = resolve(parent)
            result = upper if isinstance(upper, str) else upper + 1
        state[code] = "done"
        if isinstance(result, int):
            depths[code] = result
        return result

    for row in parsed.categories:
        code = row.values.get("category_code")
        parent = row.values.get("parent_category_code")
        if not isinstance(code, str) or "parent_category_code" in row.invalid:
            continue
        if parent is not None and parent not in known_codes:
            add("categories", row, "parent_category_code", R_MISSING_REF)
            continue
        if code in db_categories or file_parents.get(code, "\0") != parent:
            continue
        outcome = resolve(code)
        if outcome == "cycle":
            add("categories", row, "parent_category_code", R_CYCLE)
        elif isinstance(outcome, int) and outcome > 3:
            add("categories", row, "parent_category_code", R_TOO_DEEP)

    # 商品：所属分類の重複指定・参照先
    for row in parsed.products:
        codes_value = row.values.get("category_codes")
        if not isinstance(codes_value, list):
            continue
        listed: set[str] = set()
        for code in codes_value:
            if code in listed:
                add("products", row, "category_codes", R_DUP_CATEGORY)
                break
            listed.add(code)
        if any(code not in category_codes and code not in db_categories for code in codes_value):
            add("products", row, "category_codes", R_MISSING_REF)

    # 在庫単位：商品・仕入先の参照先
    db_products = db(Product.objects.values_list("product_code", flat=True))
    db_suppliers = db(Supplier.objects.values_list("supplier_code", flat=True))
    for row in parsed.stock_units:
        product = row.values.get("product_code")
        if isinstance(product, str) and product not in product_codes and product not in db_products:
            add("stock_units", row, "product_code", R_MISSING_REF)
        supplier = row.values.get("supplier_code")
        if isinstance(supplier, str) and supplier not in supplier_codes and supplier not in db_suppliers:
            add("stock_units", row, "supplier_code", R_MISSING_REF)
    return violations, depths


# ---------------------------------------------------------------------------
# 削除・登録（全件成功か無変更）
# ---------------------------------------------------------------------------


# trace: FILE-001, ADDR-004, ADDR-006, ADDR-002
def delete_existing_data() -> None:
    """監査ログ以外の全データを DELETE で削除する（TRUNCATE・採番の巻き戻しをしない：ADDR-006 DD-002）。

    削除した利用者のログイン状態（API・画面）も同じトランザクションで削除する（ADDR-002 DD-006）。
    """
    for model in (PaymentRecord, OrderStatusHistory, ShippingAddress, OrderItem, Order, CartItem, Cart):
        model.objects.all()._raw_delete(model.objects.db)
    delete_all_login_states()
    for model in (ProductCategory, StockUnit, Product, Category, Supplier, Coupon, User):
        model.objects.all()._raw_delete(model.objects.db)


# trace: FILE-001, ADDR-003, ADDR-006, ENT-001, ENT-002, ENT-003, ENT-004, ENT-005, ENT-006, ENT-007
def insert_rows(parsed: Parsed, depths: dict[str, int], now: datetime) -> dict[str, int]:
    """定義ファイルの記載順に登録する（商品分類は親を先に登録する）。データ間の参照は業務キーで関連付ける（CMN-39、FILE-RULE-005）。"""
    counts = zero_counts()
    users = [
        User(
            email=row.values["email"],
            name=row.values["name"],
            user_type=row.values["user_type"],
            registered_at=now,
            password=make_password(row.values["password"]),
        )
        for row in parsed.users
    ]
    User.objects.bulk_create(users)
    counts["users"] = len(users)

    suppliers = [Supplier(supplier_code=r.values["supplier_code"], name=r.values["name"]) for r in parsed.suppliers]
    Supplier.objects.bulk_create(suppliers)
    counts["suppliers"] = len(suppliers)

    # 親分類から順に（階層の浅い順に）親を設定して登録する。同じ親の中の分類名の一意制約（最上位どうしを含む）を
    # 登録途中でも満たすため、親を後から設定する方式はとらない（IDF-ENT-003-003）
    category_map: dict[str, Category] = {c.category_code: c for c in Category.objects.all()}
    ordered_rows = sorted(parsed.categories, key=lambda r: depths[r.values["category_code"]])
    for depth in sorted({depths[r.values["category_code"]] for r in ordered_rows}):
        level = [
            Category(
                category_code=r.values["category_code"],
                name=r.values["name"],
                parent=(
                    category_map[r.values["parent_category_code"]]
                    if r.values.get("parent_category_code") is not None
                    else None
                ),
                depth=depth,
                display_order=r.values["display_order"],
            )
            for r in ordered_rows
            if depths[r.values["category_code"]] == depth
        ]
        Category.objects.bulk_create(level)
        category_map.update({c.category_code: c for c in level})
    category_map = {c.category_code: c for c in Category.objects.all()}
    counts["categories"] = len(parsed.categories)

    products = [
        Product(
            product_code=r.values["product_code"],
            name=r.values["name"],
            description=r.values["description"],
            is_public=r.values["visibility"] == Visibility.PUBLIC,
            registered_at=r.values["registered_at"],
        )
        for r in parsed.products
    ]
    Product.objects.bulk_create(products)
    product_map = {p.product_code: p for p in Product.objects.all()}
    memberships = [
        ProductCategory(product=product_map[r.values["product_code"]], category=category_map[code])
        for r in parsed.products
        for code in r.values["category_codes"]
    ]
    ProductCategory.objects.bulk_create(memberships)
    counts["products"] = len(products)
    counts["product_categories"] = len(memberships)

    supplier_map = {s.supplier_code: s for s in Supplier.objects.all()}
    stock_units = [
        StockUnit(
            sku=r.values["sku"],
            product=product_map[r.values["product_code"]],
            supplier=supplier_map[r.values["supplier_code"]],
            variant_name=r.values["variant_name"],
            price_excluding_tax=r.values["price_excluding_tax"],
            stock_quantity=r.values["stock_quantity"],
            updated_at=now,
        )
        for r in parsed.stock_units
    ]
    StockUnit.objects.bulk_create(stock_units)
    counts["stock_units"] = len(stock_units)

    coupons = [
        Coupon(
            coupon_code=r.values["coupon_code"],
            name=r.values["name"],
            discount_type=r.values["discount_type"],
            discount_value=r.values["discount_value"],
            minimum_purchase_amount=r.values["minimum_purchase_amount"],
            valid_from=r.values["valid_from"],
            valid_to=r.values["valid_to"],
        )
        for r in parsed.coupons
    ]
    Coupon.objects.bulk_create(coupons)
    counts["coupons"] = len(coupons)
    return counts


# ---------------------------------------------------------------------------
# 実行（1回の操作）
# ---------------------------------------------------------------------------


# trace: FILE-001, ADDR-010, ADDR-004
@dataclass
class LoadResult:
    counts: dict[str, int]


# trace: FILE-001, ADDR-010, ADDR-004, ENT-015
def record_failure(started_at: datetime) -> None:
    """失敗の監査ログを別のトランザクションで1件記録する（記録できない障害の場合は記録しない）。"""
    try:
        with transaction.atomic():
            audit.record_initial_data_load(False, zero_counts(), started_at)
    except DatabaseError as exc:
        log_error("system_error", exc, None)


# trace: FILE-001, ADDR-010, ADDR-004, ADDR-009, ENT-015
def run_load(path: str, reset: bool, started_at: datetime) -> LoadResult:
    """FR-060 手順2〜11。失敗時は LoadError を送出する（監査ログ・LOG-05 は呼出し側で出力）。"""
    raw = read_file(path)
    document = parse_document(raw)
    parsed = check_values(document, started_at)
    try:
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(%s)", [INITIAL_DATA_LOCK_KEY])
            integrity, depths = check_integrity(parsed, reset)
            violations = parsed.violations + integrity
            if violations:
                code = "E-060-04" if parsed.violations else "E-060-05"
                raise LoadError(code, "定義ファイルに違反があります。", sorted(violations, key=_violation_order))
            if reset:
                delete_existing_data()
            counts = insert_rows(parsed, depths, started_at)
            audit.record_initial_data_load(True, counts, started_at)
    except LoadError:
        raise
    except IntegrityError as exc:
        # 同時の会員登録が先に確定したメールアドレスとの重複（ADDR-004 DD-008：E-060-05 に変換する）
        log_error("system_error", exc, None)
        raise LoadError(
            "E-060-05",
            "定義ファイルに違反があります（登録済みのデータと業務キーが重複しました）。",
            _concurrent_conflicts(parsed),
        ) from None
    except DatabaseError as exc:
        log_error("system_error", exc, None)
        raise LoadError("E-060-06", "システム障害のため何も投入しませんでした。") from None
    return LoadResult(counts)


# trace: FILE-001, ADDR-004, ENT-001
def _concurrent_conflicts(parsed: Parsed) -> list[Violation]:
    """投入中に他の要求が先に確定した利用者のメールアドレスを違反として示す。"""
    emails = [row.values.get("email") for row in parsed.users if isinstance(row.values.get("email"), str)]
    try:
        existing = set(User.objects.filter(email__in=emails).values_list("email", flat=True))
    except DatabaseError:
        return []
    return [
        Violation("users", row.number, "email", R_DUP_DB, "integrity")
        for row in parsed.users
        if row.values.get("email") in existing
    ]


# trace: FILE-001, ADDR-009
def _violation_order(item: Violation) -> tuple[int, int, int]:
    data_index = DATA_KEYS.index(item.data)
    field_index = (
        list(FIELD_LABELS[item.data]).index(item.field_key) if item.field_key in FIELD_LABELS[item.data] else 99
    )
    return data_index, item.row, field_index


# trace: FILE-001, ADDR-010
def log_result(success: bool, counts: dict[str, int], violations: list[Violation]) -> None:
    log_job("success" if success else "failure", counts, [v.as_log() for v in violations])
