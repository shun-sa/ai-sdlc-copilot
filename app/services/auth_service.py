from sqlalchemy.orm import Session

from app.constants import UserStatus
from app.errors import AuthFailureError, InputInvalidError
from app.models.session import SessionRecord
from app.models.user import User
from app.repositories.session_repository import SessionRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import LoginInput, RegisterInput
from app.security import hash_password, verify_password


class AuthService:
    """FR-001/FR-002。認証・セッション確立とパスワードハッシュ照合を担う（ADR-004/005）。"""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._users = UserRepository(session)
        self._sessions = SessionRepository(session)

    def register(self, data: RegisterInput) -> User:
        # 重複メールは項目単位エラー（ERR-001）。Userは作成しない。
        if self._users.exists_email(str(data.email)):
            raise InputInvalidError(
                "このメールアドレスは既に登録されています。",
                field_errors={"email": "このメールアドレスは既に登録されています。"},
            )
        user = User(
            name=data.name,
            email=str(data.email),
            password_hash=hash_password(data.password),  # ADR-004: bcryptハッシュ保存
            status=UserStatus.ACTIVE,
        )
        self._users.add(user)
        self._session.commit()
        return user

    def authenticate(self, data: LoginInput) -> User:
        # ERR-002/NFR-SEC-006: 失敗時は汎用文言。存在可否を推測させない。
        user = self._users.get_by_email(str(data.email))
        if user is None or not verify_password(data.password, user.password_hash):
            raise AuthFailureError()
        if user.status != UserStatus.ACTIVE:
            raise AuthFailureError()
        return user

    def create_session(self, user_id: int) -> SessionRecord:
        record = self._sessions.create(user_id)
        self._session.commit()
        return record

    def resolve_user(self, token: str | None) -> User | None:
        if not token:
            return None
        record = self._sessions.get(token)
        if record is None:
            return None
        return self._users.get_by_id(record.user_id)

    def logout(self, token: str | None) -> None:
        if token:
            self._sessions.delete(token)
            self._session.commit()
