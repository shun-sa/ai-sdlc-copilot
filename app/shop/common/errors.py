# trace: ADDR-007
"""エラーコード・HTTPステータスの対応表と業務例外の定義（api-contract 6.2・6.3）。

応答の組み立ては行わない。応答への変換は単一の例外ハンドラだけが行う（ADDR-007 DD-002）。
"""
from typing import Any

# api-contract 6.2 のエラーコードとHTTPステータスの対応表。この表に無いコードを追加しない。
# trace: ADDR-007
ERROR_STATUS: dict[str, int] = {
    "VALIDATION_ERROR": 400,
    "EMAIL_ALREADY_REGISTERED": 409,
    "QUANTITY_LIMIT_EXCEEDED": 409,
    "INSUFFICIENT_STOCK": 409,
    "ITEM_NOT_AVAILABLE": 409,
    "CART_EMPTY": 409,
    "COUPON_ALREADY_APPLIED": 409,
    "COUPON_NOT_FOUND": 409,
    "COUPON_NOT_YET_VALID": 409,
    "COUPON_EXPIRED": 409,
    "COUPON_MIN_SPEND_NOT_MET": 409,
    "INVALID_STATUS_TRANSITION": 409,
    "PAYMENT_DECLINED": 409,
    "PERMISSION_DENIED": 403,
    "AUTHENTICATION_REQUIRED": 401,
    "INVALID_CREDENTIALS": 401,
    "NOT_FOUND": 404,
    "PAYMENT_SERVICE_ERROR": 502,
    "INTERNAL_ERROR": 500,
}


# trace: ADDR-007
class AppError(Exception):
    """業務例外の基底クラス。code・http_status・message・details・context を持つ。"""

    code = "INTERNAL_ERROR"
    message = "処理を完了できませんでした。時間をおいて再実行してください。"

    def __init__(
        self,
        message: str | None = None,
        details: list[dict[str, str]] | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        """エラー内容を保持する。"""
        self.message = message or self.message
        self.details = details or []
        self.context = context or {}
        super().__init__(self.message)

    @property
    def http_status(self) -> int:
        """エラーコードに対応するHTTPステータスを返す。"""
        return ERROR_STATUS[self.code]

    def to_payload(self) -> dict[str, Any]:
        """応答本文の error オブジェクトを組み立てる（内部情報は含めない）。"""
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
                "context": self.context,
            }
        }


# trace: ADDR-007
class ValidationError(AppError):
    """入力エラー（ERR-01）。不備のある全項目を details に列挙する。"""

    code = "VALIDATION_ERROR"
    message = "入力内容に誤りがあります。入力内容を確認してください。"


# trace: ADDR-007
class AuthenticationRequiredError(AppError):
    """認証エラー（ERR-04）。"""

    code = "AUTHENTICATION_REQUIRED"
    message = "ログインが必要です。ログインしていないか、30分間操作がなかったためログインが切れています。"


# trace: ADDR-007
class InvalidCredentialsError(AppError):
    """認証失敗（ERR-05）。メールアドレスとパスワードのどちらが誤りかを区別しない。"""

    code = "INVALID_CREDENTIALS"
    message = "メールアドレスまたはパスワードが誤っています。"


# trace: ADDR-007
class PermissionDeniedError(AppError):
    """権限エラー（ERR-03）。"""

    code = "PERMISSION_DENIED"
    message = "この操作を行う権限がありません。"


# trace: ADDR-007
class NotFoundError(AppError):
    """対象なしエラー（ERR-06）。存在有無を明かさない。"""

    code = "NOT_FOUND"
    message = "指定した対象が見つかりません。"


# trace: ADDR-007
class EmailAlreadyRegisteredError(AppError):
    """会員登録の重複（FR-001 E-001-02）。"""

    code = "EMAIL_ALREADY_REGISTERED"
    message = "入力したメールアドレスは既に登録されています。別のメールアドレスを入力してください。"


# trace: ADDR-007
class QuantityLimitExceededError(AppError):
    """同一在庫単位の数量上限超過（FR-021、FR-022、FR-030）。"""

    code = "QUANTITY_LIMIT_EXCEEDED"
    message = "同じ規格はカート1つにつき10個までです。数量を減らしてください。"


# trace: ADDR-007
class InsufficientStockError(AppError):
    """在庫不足（FR-021、FR-022、FR-030）。"""

    code = "INSUFFICIENT_STOCK"
    message = "在庫が不足しています。数量を減らすか、時間をおいて再実行してください。"


# trace: ADDR-007
class ItemNotAvailableError(AppError):
    """非公開商品を含む注文確定（FR-030 E-030-05）。"""

    code = "ITEM_NOT_AVAILABLE"
    message = "現在販売していない商品が含まれています。カートから削除してください。"


# trace: ADDR-007
class CartEmptyError(AppError):
    """カートが空（FR-024、FR-030）。"""

    code = "CART_EMPTY"
    message = "カートに商品がありません。商品をカートに入れてください。"


# trace: ADDR-007
class CouponAlreadyAppliedError(AppError):
    """クーポンが適用済み（FR-024 E-024-05）。"""

    code = "COUPON_ALREADY_APPLIED"
    message = "クーポンは1枚まで適用できます。別のクーポンを適用するには、適用中のクーポンを解除してください。"


# trace: ADDR-007
class CouponNotFoundError(AppError):
    """クーポンが存在しない（FR-024 E-024-06）。"""

    code = "COUPON_NOT_FOUND"
    message = "入力したクーポンコードのクーポンが見つかりません。クーポンコードを確認してください。"


# trace: ADDR-007
class CouponNotYetValidError(AppError):
    """クーポンの有効期間前（FR-024、FR-030）。"""

    code = "COUPON_NOT_YET_VALID"
    message = "このクーポンはまだ利用できません。有効期間を確認してください。"


# trace: ADDR-007
class CouponExpiredError(AppError):
    """クーポンの有効期間終了（FR-024、FR-030）。"""

    code = "COUPON_EXPIRED"
    message = "このクーポンは有効期間が終了しています。別のクーポンを入力してください。"


# trace: ADDR-007
class CouponMinSpendNotMetError(AppError):
    """最低購入金額未達（FR-024、FR-030）。"""

    code = "COUPON_MIN_SPEND_NOT_MET"
    message = "小計がクーポンの最低購入金額に達していません。商品を追加してください。"


# trace: ADDR-007
class InvalidStatusTransitionError(AppError):
    """状態不正（FR-031、FR-034、FR-043〜FR-045）。"""

    code = "INVALID_STATUS_TRANSITION"
    message = "現在の注文状態ではこの操作を行えません。注文状態を確認してください。"


# trace: ADDR-007
class PaymentDeclinedError(AppError):
    """決済否認（FR-031 E-031-06）。"""

    code = "PAYMENT_DECLINED"
    message = "支払が承認されませんでした。再度支払をお試しください。"


# trace: ADDR-007
class PaymentServiceError(AppError):
    """決済連携エラー（FR-031 E-031-07）。"""

    code = "PAYMENT_SERVICE_ERROR"
    message = "決済サービスとの通信に失敗しました。時間をおいて再度支払をお試しください。"


# trace: ADDR-007
class InternalError(AppError):
    """システムエラー（ERR-08）。内部の詳細は応答に含めない。"""

    code = "INTERNAL_ERROR"
    message = "処理を完了できませんでした。時間をおいて再実行し、解消しない場合は問い合わせてください。"
