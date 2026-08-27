"""app.errors のエラー5分類マッピングの単体テスト。

Requirement: AC-COM-006 / ERR-001..004 / NFR-SEC-006
ADR: ADR-010（5分類の表示・遷移方針）
Criteria: normal-case, security
"""

from __future__ import annotations

import pytest

from app.errors import (
    ERROR_MESSAGES,
    AppError,
    AuthFailureError,
    ErrorCategory,
    InputInvalidError,
    NotFoundError,
    OutOfSalesPeriodError,
    PermissionDeniedError,
    StockShortageError,
)


class TestErrorCategories:
    @pytest.mark.parametrize(
        ("error_cls", "expected_category"),
        [
            (InputInvalidError, ErrorCategory.INPUT_INVALID),
            (StockShortageError, ErrorCategory.STOCK_SHORTAGE),
            (PermissionDeniedError, ErrorCategory.PERMISSION_DENIED),
            (AuthFailureError, ErrorCategory.AUTH_FAILURE),
            (OutOfSalesPeriodError, ErrorCategory.OUT_OF_SALES_PERIOD),
        ],
    )
    def test_category_mapping(self, error_cls: type[AppError], expected_category: ErrorCategory) -> None:
        # AC-COM-006 / ADR-010: 5分類が定義済みカテゴリへ対応付けられている。
        assert error_cls().category is expected_category

    def test_all_five_categories_have_messages(self) -> None:
        # ADR-010: 5分類すべてに表示メッセージが定義されている。
        for category in ErrorCategory:
            assert category in ERROR_MESSAGES
            assert ERROR_MESSAGES[category].strip()


class TestDefaultMessage:
    def test_default_message_from_category(self) -> None:
        assert InputInvalidError().message == ERROR_MESSAGES[ErrorCategory.INPUT_INVALID]

    def test_custom_message_overrides_default(self) -> None:
        err = InputInvalidError("独自メッセージ")
        assert err.message == "独自メッセージ"

    def test_field_errors_retained(self) -> None:
        # ERR-001: 項目単位のエラーメッセージを保持する。
        err = InputInvalidError(field_errors={"email": "重複"})
        assert err.field_errors == {"email": "重複"}


class TestAuthFailureMessageDoesNotLeakExistence:
    def test_auth_failure_message_is_generic(self) -> None:
        # NFR-SEC-006 / ERR-002 / ADR-010: 認証失敗の文言はアカウント存在可否を推測させない。
        message = AuthFailureError().message
        assert message == "メールアドレスまたはパスワードが正しくありません。"
        assert "存在しません" not in message
        assert "登録されていません" not in message


class TestNotFoundMapping:
    def test_not_found_maps_to_permission_denied_category(self) -> None:
        # ERR-004: 非公開・存在しないリソースは表示不可（権限不足と同一挙動）。
        assert NotFoundError().category is ErrorCategory.PERMISSION_DENIED
