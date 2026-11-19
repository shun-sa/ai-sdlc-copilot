# trace: ADDR-007, ADDR-001
"""コード値の定義（ADDR-007 INV-001：1か所で定義し、画面・API・一括投入・モデルが参照する）。

保持値・Web API・定義ファイルで同じ英小文字 snake_case の値を用い、表示名は要件の日本語名とする。
"""

from django.db import models


# trace: ADDR-007
class UserType(models.TextChoices):
    """CD-01 利用者区分（CODE-001）。"""

    BUYER = "buyer", "購入者"
    ADMIN = "admin", "管理者"


# trace: ADDR-007
class OrderStatus(models.TextChoices):
    """CD-02 注文状態（CODE-002）。表示名は MSG-06。"""

    ACCEPTED = "accepted", "注文受付"
    PAID = "paid", "支払済"
    SHIPPED = "shipped", "出荷済"
    DELIVERED = "delivered", "配達完了"
    CANCELLED = "cancelled", "キャンセル済"


# trace: ADDR-007
class DiscountType(models.TextChoices):
    """CD-03 割引方式（CODE-003）。"""

    FIXED_AMOUNT = "fixed_amount", "定額"
    PERCENTAGE = "percentage", "定率"


# trace: ADDR-007
class CartStatus(models.TextChoices):
    """CD-04 カート状態（CODE-004）。"""

    ACTIVE = "active", "利用中"
    ORDERED = "ordered", "注文済"


# trace: ADDR-007
class PaymentResult(models.TextChoices):
    """CD-05 決済結果（CODE-005）。"""

    APPROVED = "approved", "承認"
    DECLINED = "declined", "否認"
    INTEGRATION_ERROR = "integration_error", "連携エラー"


# trace: ADDR-007
class AuditEventType(models.TextChoices):
    """CD-07 監査イベント種別（CODE-007）。"""

    LOGIN_SUCCESS = "login_success", "ログイン成功"
    LOGIN_FAILURE = "login_failure", "ログイン失敗"
    LOGOUT = "logout", "ログアウト"
    INITIAL_DATA_LOAD = "initial_data_load", "初期データ一括投入"


# trace: ADDR-007
class AuditResult(models.TextChoices):
    """CD-08 監査ログの結果（CODE-008）。"""

    SUCCESS = "success", "成功"
    FAILURE = "failure", "失敗"


# trace: ADDR-001
class Visibility(models.TextChoices):
    """商品の公開状態の外部表現（ADDR-001 4.3 の9 R-4、ADDR-009 4.3 の4）。"""

    PUBLIC = "public", "公開"
    PRIVATE = "private", "非公開"


# trace: ADDR-007
class MockInstruction(models.TextChoices):
    """模擬決済指示（ADDR-008 DD-007：approved・declined）。"""

    APPROVED = "approved", "承認"
    DECLINED = "declined", "否認"


# CD-06 都道府県（JIS X 0401。2桁の文字列 01〜47）
PREFECTURES: tuple[tuple[str, str], ...] = (
    ("01", "北海道"),
    ("02", "青森県"),
    ("03", "岩手県"),
    ("04", "宮城県"),
    ("05", "秋田県"),
    ("06", "山形県"),
    ("07", "福島県"),
    ("08", "茨城県"),
    ("09", "栃木県"),
    ("10", "群馬県"),
    ("11", "埼玉県"),
    ("12", "千葉県"),
    ("13", "東京都"),
    ("14", "神奈川県"),
    ("15", "新潟県"),
    ("16", "富山県"),
    ("17", "石川県"),
    ("18", "福井県"),
    ("19", "山梨県"),
    ("20", "長野県"),
    ("21", "岐阜県"),
    ("22", "静岡県"),
    ("23", "愛知県"),
    ("24", "三重県"),
    ("25", "滋賀県"),
    ("26", "京都府"),
    ("27", "大阪府"),
    ("28", "兵庫県"),
    ("29", "奈良県"),
    ("30", "和歌山県"),
    ("31", "鳥取県"),
    ("32", "島根県"),
    ("33", "岡山県"),
    ("34", "広島県"),
    ("35", "山口県"),
    ("36", "徳島県"),
    ("37", "香川県"),
    ("38", "愛媛県"),
    ("39", "高知県"),
    ("40", "福岡県"),
    ("41", "佐賀県"),
    ("42", "長崎県"),
    ("43", "熊本県"),
    ("44", "大分県"),
    ("45", "宮崎県"),
    ("46", "鹿児島県"),
    ("47", "沖縄県"),
)
PREFECTURE_NAMES: dict[str, str] = dict(PREFECTURES)

# 業務エラーの種類（ADDR-001 4.3 の12：ERR-02 の12種に1対1）
REASON_EMAIL_ALREADY_REGISTERED = "email_already_registered"
REASON_QUANTITY_LIMIT_EXCEEDED = "quantity_limit_exceeded"
REASON_INSUFFICIENT_STOCK = "insufficient_stock"
REASON_UNAVAILABLE_PRODUCT = "unavailable_product"
REASON_CART_EMPTY = "cart_empty"
REASON_COUPON_ALREADY_APPLIED = "coupon_already_applied"
REASON_COUPON_NOT_FOUND = "coupon_not_found"
REASON_COUPON_NOT_YET_VALID = "coupon_not_yet_valid"
REASON_COUPON_EXPIRED = "coupon_expired"
REASON_BELOW_MINIMUM_PURCHASE_AMOUNT = "below_minimum_purchase_amount"
REASON_INVALID_STATUS = "invalid_status"
REASON_PAYMENT_DECLINED = "payment_declined"

# 入力エラーの理由（ADDR-001 4.3 の12 fields[].reason）
FIELD_REQUIRED = "required"
FIELD_INVALID_TYPE = "invalid_type"
FIELD_INVALID_LENGTH = "invalid_length"
FIELD_INVALID_FORMAT = "invalid_format"
FIELD_INVALID_CHOICE = "invalid_choice"
FIELD_OUT_OF_RANGE = "out_of_range"
FIELD_MISMATCH = "mismatch"
FIELD_INVALID_RANGE = "invalid_range"
FIELD_UNKNOWN_REFERENCE = "unknown_reference"

# クーポンの適用不可理由（ADDR-001 4.3 の10 not_applicable_reason）
NOT_APPLICABLE_EMPTY_CART = "empty_cart"
NOT_APPLICABLE_NOT_YET_VALID = "not_yet_valid"
NOT_APPLICABLE_EXPIRED = "expired"
NOT_APPLICABLE_BELOW_MINIMUM = "below_minimum_purchase_amount"

NOT_APPLICABLE_LABELS: dict[str, str] = {
    NOT_APPLICABLE_EMPTY_CART: "カートに商品がありません",
    NOT_APPLICABLE_NOT_YET_VALID: "有効期間の開始前です",
    NOT_APPLICABLE_EXPIRED: "有効期間が終了しています",
    NOT_APPLICABLE_BELOW_MINIMUM: "小計が最低購入金額に達していません",
}

# 商品一覧の並び順（ADDR-001 4.3 の11）
SORT_NEWEST = "newest"
SORT_PRICE_ASC = "price_asc"
SORT_PRICE_DESC = "price_desc"
SORT_NAME = "name"
SORT_CHOICES: tuple[tuple[str, str], ...] = (
    (SORT_NEWEST, "新着順"),
    (SORT_PRICE_ASC, "価格の安い順"),
    (SORT_PRICE_DESC, "価格の高い順"),
    (SORT_NAME, "商品名順"),
)
