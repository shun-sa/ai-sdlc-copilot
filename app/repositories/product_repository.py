"""Product Repository (FR-005 / FR-004)。"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.models.product import Product


class ProductRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _visible(self) -> Select:
        # C-DATA-001: 非公開商品は顧客画面に表示しない
        return select(Product).where(Product.publish_status == "published")

    def search(
        self,
        *,
        keyword: str | None,
        category: str | None,
        movie_id: int | None,
        in_stock_only: bool,
        limit: int,
        offset: int,
    ) -> tuple[list[Product], int]:
        stmt = self._visible()
        count_stmt = (
            select(func.count())
            .select_from(Product)
            .where(Product.publish_status == "published")
        )

        def apply(s):
            if keyword:
                s = s.where(Product.name.ilike(f"%{keyword}%"))
            if category:
                s = s.where(Product.category == category)
            if movie_id:
                s = s.where(Product.movie_id == movie_id)
            if in_stock_only:
                s = s.where(Product.stock > 0)
            return s

        stmt = apply(stmt).order_by(Product.id.desc())
        count_stmt = apply(count_stmt)

        total = self.db.execute(count_stmt).scalar_one()
        rows = list(self.db.execute(stmt.limit(limit).offset(offset)).scalars())
        return rows, total

    def get_visible(self, product_id: int) -> Product | None:
        return self.db.execute(
            self._visible().where(Product.id == product_id)
        ).scalar_one_or_none()

    def list_by_movie(self, movie_id: int) -> list[Product]:
        return list(
            self.db.execute(
                self._visible().where(Product.movie_id == movie_id).order_by(Product.id.desc())
            ).scalars()
        )

    def get_for_update(self, product_id: int) -> Product | None:
        """在庫更新用に対象行を悲観ロックで取得する (ADR-007)。"""
        stmt = select(Product).where(Product.id == product_id).with_for_update()
        return self.db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def is_saleable(product: Product, now: datetime | None = None) -> bool:
        """販売可能かを判定する (C-DATA-002)。"""
        now = now or datetime.now(timezone.utc)
        if product.publish_status != "published":
            return False
        if product.sales_start_at and _aware(product.sales_start_at) > now:
            return False
        if product.sales_end_at and _aware(product.sales_end_at) < now:
            return False
        return True


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
