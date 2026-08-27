from datetime import datetime

from sqlalchemy import Date, Enum, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.constants import MovieStatus
from app.database import Base


class Movie(Base):
    """DM-002: Movie。"""

    __tablename__ = "movies"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    synopsis: Mapped[str] = mapped_column(Text, default="", nullable=False)
    genre: Mapped[str] = mapped_column(String(100), default="", nullable=False, index=True)
    release_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    runtime_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[MovieStatus] = mapped_column(
        Enum(MovieStatus, native_enum=False, length=20), default=MovieStatus.PUBLISHED, nullable=False
    )

    def is_published(self) -> bool:
        # C-DATA-001: 非公開作品は顧客向け画面に表示しない。
        return self.status == MovieStatus.PUBLISHED
