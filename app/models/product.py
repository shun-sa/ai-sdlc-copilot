from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.constants import PublishStatus
from app.database import Base
from app.time_utils import is_within_period, now_utc


class Product(Base):
    """DM-003: Product。"""

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    price_tax_included: Mapped[int] = mapped_column(Integer, nullable=False)
    stock: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    publish_status: Mapped[PublishStatus] = mapped_column(
        Enum(PublishStatus, native_enum=False, length=20), default=PublishStatus.PUBLISHED, nullable=False
    )
    sales_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sales_end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    movie_id: Mapped[int | None] = mapped_column(ForeignKey("movies.id"), nullable=True, index=True)

    def is_published(self) -> bool:
        # C-DATA-001: 非公開/削除済みは表示しない。
        return self.publish_status == PublishStatus.PUBLISHED

    def is_on_sale(self, reference: datetime | None = None) -> bool:
        # C-DATA-002: 販売開始前/終了後は購入不可。
        reference = reference or now_utc()
        return is_within_period(reference, self.sales_start_at, self.sales_end_at)

    def is_in_stock(self) -> bool:
        # C-DATA-003: 在庫0は購入不可。
        return self.stock > 0

    def is_purchasable(self, reference: datetime | None = None) -> bool:
        return self.is_published() and self.is_on_sale(reference) and self.is_in_stock()
