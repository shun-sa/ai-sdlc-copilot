from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import PublishStatus
from app.models.product import Product


class ProductRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_published(self, product_id: int) -> Product | None:
        stmt = select(Product).where(
            Product.id == product_id, Product.publish_status == PublishStatus.PUBLISHED
        )
        return self._session.scalars(stmt).first()

    def get_for_update(self, product_id: int) -> Product | None:
        """在庫行を悲観ロックで取得する（ADR-007）。"""
        stmt = (
            select(Product)
            .where(Product.id == product_id, Product.publish_status == PublishStatus.PUBLISHED)
            .with_for_update()
        )
        return self._session.scalars(stmt).first()

    def list_by_movie(self, movie_id: int) -> list[Product]:
        stmt = select(Product).where(
            Product.movie_id == movie_id, Product.publish_status == PublishStatus.PUBLISHED
        )
        return list(self._session.scalars(stmt).all())

    def search(
        self,
        *,
        keyword: str | None = None,
        movie_id: int | None = None,
        in_stock_only: bool = False,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Product], int]:
        conditions = [Product.publish_status == PublishStatus.PUBLISHED]
        if keyword:
            conditions.append(Product.name.contains(keyword))
        if movie_id is not None:
            conditions.append(Product.movie_id == movie_id)
        if in_stock_only:
            conditions.append(Product.stock > 0)

        base = select(Product).where(*conditions).order_by(Product.name.asc())
        total = len(self._session.scalars(select(Product).where(*conditions)).all())
        rows = self._session.scalars(base.offset(offset).limit(limit)).all()
        return list(rows), total
