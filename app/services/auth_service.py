"""認証サービス (FR-001 / FR-002 / ADR-004 / ADR-006)。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.errors import AuthError, ValidationError
from app.models.session import SessionRecord
from app.models.user import User
from app.repositories.session_repository import SessionRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import LoginInput, RegisterInput
from app.security import generate_token, hash_password, verify_password


class AuthService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.users = UserRepository(db)
        self.sessions = SessionRepository(db)

    # --- 会員登録 (FR-001) ---
    def register(self, data: RegisterInput) -> User:
        if self.users.exists_email(str(data.email)):
            # ERR-001: 重複メール不可
            raise ValidationError("このメールアドレスは既に登録されています。")
        user = User(
            name=data.name,
            email=str(data.email),
            password_hash=hash_password(data.password),  # ADR-006
        )
        try:
            self.users.add(user)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            # email一意制約による競合 (ERR-005 / 二重登録防止)
            raise ValidationError("このメールアドレスは既に登録されています。") from exc
        self.db.refresh(user)
        return user

    # --- ログイン認証 (FR-002) ---
    def authenticate(self, data: LoginInput) -> User:
        user = self.users.get_by_email(str(data.email))
        # NFR-SEC-006 / ERR-002: 存在有無で分岐せず汎用エラー。
        # ユーザー不在でもダミー検証で計時差を抑える。
        if user is None:
            verify_password(data.password, _DUMMY_HASH)
            raise AuthError()
        if not verify_password(data.password, user.password_hash):
            raise AuthError()
        if user.status != "active":
            raise AuthError()
        return user

    # --- セッション生成 (ADR-004) ---
    def create_session(self, user_id: int | None) -> SessionRecord:
        settings = get_settings()
        record = SessionRecord(
            id=generate_token(),  # CSPRNG
            user_id=user_id,
            csrf_token=generate_token(),
            expires_at=datetime.now(timezone.utc)
            + timedelta(seconds=settings.session_max_age_seconds),
        )
        self.sessions.add(record)
        self.db.commit()
        return record

    def login(self, data: LoginInput, existing_session_id: str | None) -> SessionRecord:
        """認証しセッションを新規発行する。ログイン成功時にセッションIDを再生成する。"""
        user = self.authenticate(data)
        # ADR-004: ログイン成功時に既存セッションを破棄し再生成する
        if existing_session_id:
            old = self.sessions.get(existing_session_id)
            if old is not None:
                self.sessions.delete(old)
        return self.create_session(user.id)

    def logout(self, session_id: str | None) -> None:
        if not session_id:
            return
        record = self.sessions.get(session_id)
        if record is not None:
            self.sessions.delete(record)
            self.db.commit()

    def get_session(self, session_id: str | None) -> SessionRecord | None:
        if not session_id:
            return None
        record = self.sessions.get(session_id)
        if record is None:
            return None
        if record.is_expired():
            self.sessions.delete(record)
            self.db.commit()
            return None
        return record


# ユーザー不在時のタイミング差を抑えるためのダミーハッシュ (bcrypt形式)。
# 実在パスワードではなく計時攻撃対策用のプレースホルダ (NFR-SEC-006)。
_DUMMY_HASH = "$2b$12$abcdefghijklmnopqrstuuMspeUyfQjTLZLm8lJZ8s5Y5b3v6q9Zi"
