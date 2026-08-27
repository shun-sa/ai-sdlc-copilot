"""AuthService の単体テスト（使い捨て in-memory SQLite）。

Requirement: FR-001 / FR-002 / NFR-SEC-001 / NFR-SEC-006 / ERR-001 / ERR-002
ADR: ADR-004（bcrypt）/ ADR-005（セッション）
Criteria: normal-case, exception, security, database
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.constants import UserStatus
from app.errors import AuthFailureError, InputInvalidError
from app.schemas.auth import LoginInput, RegisterInput
from app.services.auth_service import AuthService

from .conftest import make_user


def _register_input(**overrides: object) -> RegisterInput:
    data = {
        "name": "会員太郎",
        "email": "new@example.com",
        "password": "password123",
        "password_confirm": "password123",
    }
    data.update(overrides)
    return RegisterInput(**data)


class TestRegister:
    def test_register_creates_user(self, db_session: Session) -> None:
        # FR-001: 会員登録が完了する。
        service = AuthService(db_session)
        user = service.register(_register_input())
        assert user.id is not None
        assert user.email == "new@example.com"
        assert user.status is UserStatus.ACTIVE

    def test_password_stored_hashed_not_plaintext(self, db_session: Session) -> None:
        # NFR-SEC-001 / ADR-004: パスワードはハッシュ化保存。平文を保存しない。
        service = AuthService(db_session)
        user = service.register(_register_input(password="password123", password_confirm="password123"))
        assert user.password_hash != "password123"
        assert user.password_hash.startswith("$2")

    def test_duplicate_email_rejected(self, db_session: Session) -> None:
        # ERR-001: 重複メールは項目単位エラー。二重登録しない。
        service = AuthService(db_session)
        service.register(_register_input(email="dup@example.com"))
        with pytest.raises(InputInvalidError) as exc:
            service.register(_register_input(email="dup@example.com"))
        assert "email" in exc.value.field_errors


class TestAuthenticate:
    def test_authenticate_success(self, db_session: Session) -> None:
        # FR-002: 正しい資格情報でログインできる。
        make_user(db_session, email="member@example.com", password="password123")
        service = AuthService(db_session)
        user = service.authenticate(LoginInput(email="member@example.com", password="password123"))
        assert user.email == "member@example.com"

    def test_wrong_password_raises_auth_failure(self, db_session: Session) -> None:
        make_user(db_session, email="member@example.com", password="password123")
        service = AuthService(db_session)
        with pytest.raises(AuthFailureError):
            service.authenticate(LoginInput(email="member@example.com", password="wrongpass1"))

    def test_nonexistent_email_raises_same_generic_error(self, db_session: Session) -> None:
        # ERR-002 / NFR-SEC-006: 存在しないメールでも同じ汎用エラー。存在可否を推測させない。
        service = AuthService(db_session)
        with pytest.raises(AuthFailureError) as exc_missing:
            service.authenticate(LoginInput(email="nobody@example.com", password="password123"))

        make_user(db_session, email="exists@example.com", password="password123")
        with pytest.raises(AuthFailureError) as exc_wrong:
            service.authenticate(LoginInput(email="exists@example.com", password="wrongpass1"))

        # 同一の汎用メッセージであること（アカウント存在有無を判別できない）。
        assert exc_missing.value.message == exc_wrong.value.message

    def test_inactive_user_rejected(self, db_session: Session) -> None:
        make_user(
            db_session,
            email="inactive@example.com",
            password="password123",
            status=UserStatus.INACTIVE,
        )
        service = AuthService(db_session)
        with pytest.raises(AuthFailureError):
            service.authenticate(LoginInput(email="inactive@example.com", password="password123"))


class TestSession:
    def test_create_and_resolve_session(self, db_session: Session) -> None:
        # ADR-005: セッショントークンから user を解決できる。
        user = make_user(db_session, email="s@example.com")
        service = AuthService(db_session)
        record = service.create_session(user.id)
        resolved = service.resolve_user(record.token)
        assert resolved is not None
        assert resolved.id == user.id

    def test_resolve_none_token_returns_none(self, db_session: Session) -> None:
        service = AuthService(db_session)
        assert service.resolve_user(None) is None

    def test_resolve_unknown_token_returns_none(self, db_session: Session) -> None:
        service = AuthService(db_session)
        assert service.resolve_user("unknown-token") is None

    def test_logout_invalidates_session(self, db_session: Session) -> None:
        user = make_user(db_session, email="lo@example.com")
        service = AuthService(db_session)
        record = service.create_session(user.id)
        service.logout(record.token)
        assert service.resolve_user(record.token) is None
