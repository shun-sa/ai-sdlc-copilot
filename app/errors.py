"""アプリケーション共通の例外/エラー定義 (エラー仕様 ERR-001〜005)。"""

from __future__ import annotations


class AppError(Exception):
    """業務エラーの基底。"""

    def __init__(self, message: str, code: str) -> None:
        super().__init__(message)
        self.message = message
        self.code = code


class ValidationError(AppError):
    """入力不備/形式不正 (ERR-001)。"""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="VALIDATION")


class AuthError(AppError):
    """認証失敗 (ERR-002 / NFR-SEC-006)。

    アカウント存在有無を推測させない汎用メッセージを用いる。
    """

    def __init__(self) -> None:
        super().__init__("メールアドレスまたはパスワードが正しくありません。", code="AUTH")


class OutOfStockError(AppError):
    """在庫不足/残席不足 (ERR-003)。"""

    def __init__(self, message: str = "在庫が不足しています。") -> None:
        super().__init__(message, code="OUT_OF_STOCK")


class NotSaleableError(AppError):
    """販売期間外/非公開/権限不足 (ERR-004)。"""

    def __init__(self, message: str = "この操作は現在ご利用いただけません。") -> None:
        super().__init__(message, code="NOT_SALEABLE")


class ForbiddenError(AppError):
    """所有者スコープ違反 (ERR-004 / NFR-SEC-003 / ADR-005)。"""

    def __init__(self, message: str = "この操作は許可されていません。") -> None:
        super().__init__(message, code="FORBIDDEN")


class ConflictError(AppError):
    """一意制約違反等の競合 (ERR-005)。"""

    def __init__(
        self, message: str = "処理が競合しました。時間をおいて再度お試しください。"
    ) -> None:
        super().__init__(message, code="CONFLICT")
