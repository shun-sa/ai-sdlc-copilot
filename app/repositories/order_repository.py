from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.order import Order


class OrderRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, order: Order) -> Order:
        self._session.add(order)
        self._session.flush()
        return order

    def exists_order_number(self, order_number: str) -> bool:
        stmt = select(Order.id).where(Order.order_number == order_number)
        return self._session.scalars(stmt).first() is not None

    def list_by_user(self, user_id: int, *, offset: int = 0, limit: int = 20) -> tuple[list[Order], int]:
        # ADR-006: 常に本人user_idで絞り込む。ADR-013: 注文日降順・20件ページング。
        conditions = [Order.user_id == user_id]
        total = len(self._session.scalars(select(Order.id).where(*conditions)).all())
        stmt = (
            select(Order)
            .where(*conditions)
            .order_by(Order.ordered_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(self._session.scalars(stmt).all()), total

    def get_owned(self, order_id: int, user_id: int) -> Order | None:
        stmt = select(Order).where(Order.id == order_id, Order.user_id == user_id)
        return self._session.scalars(stmt).first()
