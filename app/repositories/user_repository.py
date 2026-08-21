"""User Repository。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User


class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_email(self, email: str) -> User | None:
        return self.db.execute(select(User).where(User.email == email)).scalar_one_or_none()

    def get_by_id(self, user_id: int) -> User | None:
        return self.db.get(User, user_id)

    def exists_email(self, email: str) -> bool:
        return (
            self.db.execute(select(User.id).where(User.email == email)).scalar_one_or_none()
            is not None
        )

    def add(self, user: User) -> User:
        self.db.add(user)
        self.db.flush()
        return user
