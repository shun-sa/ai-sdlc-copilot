"""Product (DM-003)。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    # 税込価格・整数円 (C-UI-004)
    price_tax_included: Mapped[int] = mapped_column(Integer, nullable=False)
    stock: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # published / unpublished (C-DATA-001)
    publish_status: Mapped[str] = mapped_column(
        String(20), default="published", nullable=False, index=True
    )
    sales_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sales_end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    category: Mapped[str] = mapped_column(String(50), default="", nullable=False, index=True)
    movie_id: Mapped[int | None] = mapped_column(ForeignKey("movies.id"), nullable=True, index=True)
