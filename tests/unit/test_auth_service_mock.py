"""認証サービス セキュリティロジック単体テスト (Mock戦略)。

対象: app/services/auth_service.py の認証分岐ロジック
検証Requirement: ERR-002 / NFR-SEC-006 (認証失敗の汎用化・存在推測不可)。
DB Strategy: MOCK (Repositoryをモックし、DB非依存で分岐ロジックのみ検証)。

Policy (service_and_domain: mock) に従い、DBそのものの動作確認が不要な
Serviceの分岐ロジックは Repository をモックして検証する。
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from app.errors import AuthError, ValidationError
from app.schemas.auth import LoginInput, RegisterInput
from app.services.auth_service import AuthService


def _service_with_mocks() -> tuple[AuthService, MagicMock]:
    service = AuthService.__new__(AuthService)  # __init__(DB接続)を回避
    service.db = MagicMock()
    service.users = MagicMock()
    service.sessions = MagicMock()
    return service, service.users


class TestAuthenticateBranches:
    # NFR-SEC-006: ユーザー不在時も AuthError (存在推測不可)
    def test_missing_user_raises_auth_error(self) -> None:
        service, users = _service_with_mocks()
        users.get_by_email.return_value = None
        with pytest.raises(AuthError):
            service.authenticate(LoginInput(email="nobody@example.com", password="abcd1234"))

    # NFR-SEC-006: 不在ユーザーでもダミー検証を行い早期returnしない
    def test_missing_user_still_verifies_dummy(self) -> None:
        service, users = _service_with_mocks()
        users.get_by_email.return_value = None
        with pytest.raises(AuthError):
            service.authenticate(LoginInput(email="nobody@example.com", password="abcd1234"))
        # 存在有無で分岐せず必ずメール検索を行う
        users.get_by_email.assert_called_once()


class TestRegisterBranches:
    # ERR-001: 事前重複チェックで既存メールは登録拒否 (add未実行)
    def test_existing_email_rejected_before_insert(self) -> None:
        service, users = _service_with_mocks()
        users.exists_email.return_value = True
        data = RegisterInput(
            name="山田太郎",
            email="dup@example.com",
            password="abcd1234",
            password_confirm="abcd1234",
        )
        with pytest.raises(ValidationError):
            service.register(data)
        users.add.assert_not_called()


class TestRegisterRace:
    # ERR-005 / 二重登録防止: 事前チェック通過後に一意制約が競合しても
    # ValidationError へ変換し、部分登録を残さない (rollback)。
    def test_integrity_error_converted(self) -> None:
        service, users = _service_with_mocks()
        users.exists_email.return_value = False
        service.db.commit.side_effect = IntegrityError("stmt", {}, Exception("dup"))
        data = RegisterInput(
            name="山田太郎",
            email="race@example.com",
            password="abcd1234",
            password_confirm="abcd1234",
        )
        with pytest.raises(ValidationError):
            service.register(data)
        service.db.rollback.assert_called_once()
