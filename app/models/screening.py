from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.constants import TicketType
from app.database import Base
from app.time_utils import ensure_aware, is_within_period, now_utc


class Screening(Base):
    """DM-006: Screening。座席指定はなく残席数のみ管理する（CON-004）。"""

    __tablename__ = "screenings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id"), nullable=False, index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    theater_name: Mapped[str] = mapped_column(String(100), nullable=False)
    screen_name: Mapped[str] = mapped_column(String(50), nullable=False)
    seats_remaining: Mapped[int] = mapped_column(Integer, nullable=False)
    sales_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sales_end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    prices: Mapped[list["ScreeningTicketPrice"]] = relationship(
        back_populates="screening", cascade="all, delete-orphan", lazy="selectin"
    )

    def is_on_sale(self, reference: datetime | None = None) -> bool:
        # C-DATA-002 / FR-009: 販売期間内かつ上映開始前のみ購入可。
        reference = reference or now_utc()
        if not is_within_period(reference, self.sales_start_at, self.sales_end_at):
            return False
        return ensure_aware(reference) < ensure_aware(self.starts_at)

    def has_seats(self, quantity: int) -> bool:
        return self.seats_remaining >= quantity


class ScreeningTicketPrice(Base):
    """ADR-012: 券種ごとの単価を上映回に紐づく価格設定データとして保持する。"""

    __tablename__ = "screening_ticket_prices"
    __table_args__ = (UniqueConstraint("screening_id", "ticket_type", name="uq_screening_ticket_type"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    screening_id: Mapped[int] = mapped_column(ForeignKey("screenings.id"), nullable=False, index=True)
    ticket_type: Mapped[TicketType] = mapped_column(
        Enum(TicketType, native_enum=False, length=20), nullable=False
    )
    unit_price: Mapped[int] = mapped_column(Integer, nullable=False)

    screening: Mapped["Screening"] = relationship(back_populates="prices")
