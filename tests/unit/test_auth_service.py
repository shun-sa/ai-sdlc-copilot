"""認証サービス単体テスト (FR-001 / FR-002)。

対象: app/services/auth_service.py
検証Requirement:
- FR-001 会員登録 (重複メール不可 ERR-001, パスワードハッシュ化 NFR-SEC-001/ADR-006)
- FR-002 ログイン認証 (認証失敗の汎用化 ERR-002/NFR-SEC-006)
- ADR-004 セッション生成/再生成
DB Strategy: CONTAINER (使い捨てSQLite。登録/認証はDB永続を伴うため実DBで検証)。
期待結果は Requirements / ADR から導出する。
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from sqlalchemy.orm import Session

from app.errors import AuthError, ValidationError
from app.models.user import User
from app.schemas.auth import LoginInput, RegisterInput
from app.services.auth_service import AuthService


def _register_input(**overrides: object) -> RegisterInput:
    data = {
        "name": "山田太郎",
        "email": "taro@example.com",
        "password": "abcd1234",
        "password_confirm": "abcd1234",
    }
    data.update(overrides)
    return RegisterInput(**data)  # type: ignore[arg-type]


class TestRegister:
    # FR-001 正常系: 会員登録でUserが作成される
    def test_register_creates_user(self, db: Session) -> None:
        service = AuthService(db)
        user = service.register(_register_input())
        assert user.id is not None
        assert user.email == "taro@example.com"
        assert user.status == "active"

    # NFR-SEC-001 / ADR-006: パスワードは平文で保存されない
    def test_password_not_stored_in_plaintext(self, db: Session) -> None:
        service = AuthService(db)
        user = service.register(_register_input(password="abcd1234", password_confirm="abcd1234"))
        assert user.password_hash != "abcd1234"
        assert user.password_hash.startswith("$2")  # bcrypt

    # ERR-001 / FR-001: 重複メールは登録不可
    def test_duplicate_email_rejected(self, db: Session) -> None:
        service = AuthService(db)
        service.register(_register_input(email="dup@example.com"))
        with pytest.raises(ValidationError):
            service.register(
                _register_input(email="dup@example.com", name="別人")
            )


class TestAuthenticate:
    # FR-002 正常系: 正しい資格情報で認証成功
    def test_authenticate_success(self, db: Session, make_user: Callable[..., User]) -> None:
        make_user(email="login@example.com", password="abcd1234")
        service = AuthService(db)
        user = service.authenticate(LoginInput(email="login@example.com", password="abcd1234"))
        assert user.email == "login@example.com"

    # FR-002 / ERR-002: パスワード誤りは AuthError
    def test_wrong_password(self, db: Session, make_user: Callable[..., User]) -> None:
        make_user(email="login@example.com", password="abcd1234")
        service = AuthService(db)
        with pytest.raises(AuthError):
            service.authenticate(LoginInput(email="login@example.com", password="wrongpass"))

    # NFR-SEC-006 / ERR-002: 存在しないメールでも AuthError。
    # 存在有無を推測させないため、誤パスワードと同一メッセージであること。
    def test_nonexistent_email_generic_error(
        self, db: Session, make_user: Callable[..., User]
    ) -> None:
        make_user(email="exists@example.com", password="abcd1234")
        service = AuthService(db)

        with pytest.raises(AuthError) as missing:
            service.authenticate(LoginInput(email="nobody@example.com", password="abcd1234"))
        with pytest.raises(AuthError) as wrong:
            service.authenticate(LoginInput(email="exists@example.com", password="wrongpass"))

        # アカウント存在可否を推測させない同一の汎用メッセージ
        assert missing.value.message == wrong.value.message

    # FR-002: 非activeユーザーは認証不可
    def test_inactive_user_rejected(self, db: Session, make_user: Callable[..., User]) -> None:
        make_user(email="inactive@example.com", password="abcd1234", status="suspended")
        service = AuthService(db)
        with pytest.raises(AuthError):
            service.authenticate(LoginInput(email="inactive@example.com", password="abcd1234"))


class TestSession:
    # ADR-004: ログイン成功でセッションが発行される
    def test_login_creates_session(self, db: Session, make_user: Callable[..., User]) -> None:
        make_user(email="s@example.com", password="abcd1234")
        service = AuthService(db)
        session = service.login(LoginInput(email="s@example.com", password="abcd1234"), None)
        assert session.id
        assert session.user_id is not None
        assert session.csrf_token

    # ADR-004: ログイン成功時に既存セッションを破棄し再生成する
    def test_login_regenerates_session(
        self, db: Session, make_user: Callable[..., User]
    ) -> None:
        make_user(email="s2@example.com", password="abcd1234")
        service = AuthService(db)
        first = service.create_session(user_id=1)
        old_id = first.id
        new = service.login(LoginInput(email="s2@example.com", password="abcd1234"), old_id)
        assert new.id != old_id
        # 旧セッションは破棄されている
        assert service.get_session(old_id) is None

    # ADR-004: ログアウトでセッションが失効する
    def test_logout_removes_session(self, db: Session) -> None:
        service = AuthService(db)
        session = service.create_session(user_id=1)
        service.logout(session.id)
        assert service.get_session(session.id) is None
