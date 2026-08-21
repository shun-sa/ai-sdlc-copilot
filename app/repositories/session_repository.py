"""Session Repository (サーバーサイドセッション / ADR-004)。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.session import SessionRecord


class SessionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, session_id: str) -> SessionRecord | None:
        return self.db.get(SessionRecord, session_id)

    def add(self, record: SessionRecord) -> SessionRecord:
        self.db.add(record)
        self.db.flush()
        return record

    def delete(self, record: SessionRecord) -> None:
        self.db.delete(record)
        self.db.flush()
