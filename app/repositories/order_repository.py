"""Order Repository (FR-008 / FR-010)。"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.order import Order


class OrderRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, order: Order) -> Order:
        self.db.add(order)
        self.db.flush()
        return order

    def exists_order_number(self, order_number: str) -> bool:
        return (
            self.db.execute(
                select(Order.id).where(Order.order_number == order_number)
            ).scalar_one_or_none()
            is not None
        )

    def list_by_user(self, user_id: int, *, limit: int, offset: int) -> tuple[list[Order], int]:
        # C-AUTH-004 / NFR-SEC-003: 本人分のみ。注文日降順 (FR-010)。
        stmt = (
            select(Order)
            .where(Order.user_id == user_id)
            .options(selectinload(Order.items))
            .order_by(Order.ordered_at.desc(), Order.id.desc())
            .limit(limit)
            .offset(offset)
        )
        total = self.db.execute(
            select(func.count()).select_from(Order).where(Order.user_id == user_id)
        ).scalar_one()
        return list(self.db.execute(stmt).scalars()), total

    def get_owned(self, order_id: int, user_id: int) -> Order | None:
        """所有者スコープ強制で取得する (ADR-005: IDOR防止)。"""
        return self.db.execute(
            select(Order)
            .where(Order.id == order_id, Order.user_id == user_id)
            .options(selectinload(Order.items))
        ).scalar_one_or_none()
