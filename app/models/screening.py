"""Screening (DM-006)。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Screening(Base):
    __tablename__ = "screenings"

    id: Mapped[int] = mapped_column(primary_key=True)
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id"), nullable=False, index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    theater_name: Mapped[str] = mapped_column(String(100), nullable=False)
    screen_name: Mapped[str] = mapped_column(String(100), nullable=False)
    # 座席指定は行わず残席数のみ管理 (CON-004)
    seats_remaining: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sales_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sales_end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
