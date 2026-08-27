import secrets

from sqlalchemy.orm import Session

from app.models.session import SessionRecord


class SessionRepository:
    """サーバー側セッションストア（ADR-005）。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, user_id: int) -> SessionRecord:
        record = SessionRecord(token=secrets.token_urlsafe(32), user_id=user_id)
        self._session.add(record)
        self._session.flush()
        return record

    def get(self, token: str) -> SessionRecord | None:
        return self._session.get(SessionRecord, token)

    def delete(self, token: str) -> None:
        record = self._session.get(SessionRecord, token)
        if record is not None:
            self._session.delete(record)
            self._session.flush()
