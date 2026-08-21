"""TicketPurchase / TicketPurchaseItem (DM-007)。

明細は購入時点スナップショット (券種/単価/上映情報) を保持する
(ADR-008)。履歴表示はマスタ再参照ではなくスナップショットを用いる。
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TicketPurchase(Base):
    __tablename__ = "ticket_purchases"

    id: Mapped[int] = mapped_column(primary_key=True)
    purchase_number: Mapped[str] = mapped_column(
        String(32), unique=True, nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    purchased_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    total_amount: Mapped[int] = mapped_column(Integer, nullable=False)

    items: Mapped[list["TicketPurchaseItem"]] = relationship(
        back_populates="purchase", cascade="all, delete-orphan"
    )


class TicketPurchaseItem(Base):
    __tablename__ = "ticket_purchase_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    purchase_id: Mapped[int] = mapped_column(
        ForeignKey("ticket_purchases.id"), nullable=False, index=True
    )
    screening_id: Mapped[int] = mapped_column(ForeignKey("screenings.id"), nullable=False)
    ticket_type: Mapped[str] = mapped_column(String(30), nullable=False)
    unit_price: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    subtotal: Mapped[int] = mapped_column(Integer, nullable=False)
    # 上映スナップショット (ADR-008): 履歴表示で映画名/上映日時を再現
    movie_title_snapshot: Mapped[str] = mapped_column(String(200), nullable=False)
    screening_starts_at_snapshot: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    theater_name_snapshot: Mapped[str] = mapped_column(String(100), nullable=False)

    purchase: Mapped["TicketPurchase"] = relationship(back_populates="items")
