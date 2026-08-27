import enum


class ErrorCategory(str, enum.Enum):
    """AC-COM-006 / ADR-010 の5分類。"""

    INPUT_INVALID = "INPUT_INVALID"          # 入力不備（ERR-001）
    STOCK_SHORTAGE = "STOCK_SHORTAGE"        # 在庫不足（ERR-003）
    PERMISSION_DENIED = "PERMISSION_DENIED"  # 権限不足（ERR-004）
    AUTH_FAILURE = "AUTH_FAILURE"            # 認証失敗（ERR-002）
    OUT_OF_SALES_PERIOD = "OUT_OF_SALES_PERIOD"  # 販売期間外（ERR-004）


# 各分類の表示メッセージと遷移先（ADR-010）。認証失敗は存在可否を推測させない汎用文言（NFR-SEC-006）。
ERROR_MESSAGES: dict[ErrorCategory, str] = {
    ErrorCategory.INPUT_INVALID: "入力内容に誤りがあります。",
    ErrorCategory.STOCK_SHORTAGE: "在庫が不足しているため処理できません。",
    ErrorCategory.PERMISSION_DENIED: "この操作を行う権限がありません。",
    ErrorCategory.AUTH_FAILURE: "メールアドレスまたはパスワードが正しくありません。",
    ErrorCategory.OUT_OF_SALES_PERIOD: "販売期間外のため購入できません。",
}


class AppError(Exception):
    """業務エラーの基底。分類・メッセージ・項目別エラーを保持する。"""

    category: ErrorCategory = ErrorCategory.INPUT_INVALID

    def __init__(
        self,
        message: str | None = None,
        *,
        field_errors: dict[str, str] | None = None,
    ) -> None:
        self.message = message or ERROR_MESSAGES[self.category]
        self.field_errors = field_errors or {}
        super().__init__(self.message)


class InputInvalidError(AppError):
    category = ErrorCategory.INPUT_INVALID


class StockShortageError(AppError):
    category = ErrorCategory.STOCK_SHORTAGE


class PermissionDeniedError(AppError):
    category = ErrorCategory.PERMISSION_DENIED


class AuthFailureError(AppError):
    category = ErrorCategory.AUTH_FAILURE


class OutOfSalesPeriodError(AppError):
    category = ErrorCategory.OUT_OF_SALES_PERIOD


class NotFoundError(AppError):
    """非公開・存在しないリソースは表示不可として扱う（ERR-004準拠）。"""

    category = ErrorCategory.PERMISSION_DENIED


class AuthenticationRequiredError(Exception):
    """未認証で要認証機能へアクセスした場合（C-AUTH-003）。ログイン画面へ遷移させる。"""
