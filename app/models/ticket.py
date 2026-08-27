from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.constants import TicketType
from app.database import Base
from app.time_utils import now_utc


class TicketPurchase(Base):
    """DM-007: TicketPurchase（購入ヘッダ）。"""

    __tablename__ = "ticket_purchases"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    purchase_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    purchased_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    total_amount: Mapped[int] = mapped_column(Integer, nullable=False)

    items: Mapped[list["TicketPurchaseItem"]] = relationship(
        back_populates="purchase", cascade="all, delete-orphan", lazy="selectin"
    )


class TicketPurchaseItem(Base):
    """DM-007: TicketPurchaseItem。確定時点のスナップショットを保持する（ADR-008）。"""

    __tablename__ = "ticket_purchase_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    purchase_id: Mapped[int] = mapped_column(ForeignKey("ticket_purchases.id"), nullable=False, index=True)
    screening_id: Mapped[int] = mapped_column(ForeignKey("screenings.id"), nullable=False)
    movie_title_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    screening_starts_at_snapshot: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ticket_type: Mapped[TicketType] = mapped_column(
        Enum(TicketType, native_enum=False, length=20), nullable=False
    )
    unit_price: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    subtotal: Mapped[int] = mapped_column(Integer, nullable=False)

    purchase: Mapped["TicketPurchase"] = relationship(back_populates="items")
