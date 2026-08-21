"""Ticket Repository (FR-009 / FR-010)。"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.ticket import TicketPurchase


class TicketRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, purchase: TicketPurchase) -> TicketPurchase:
        self.db.add(purchase)
        self.db.flush()
        return purchase

    def exists_purchase_number(self, purchase_number: str) -> bool:
        return (
            self.db.execute(
                select(TicketPurchase.id).where(
                    TicketPurchase.purchase_number == purchase_number
                )
            ).scalar_one_or_none()
            is not None
        )

    def list_by_user(
        self, user_id: int, *, limit: int, offset: int
    ) -> tuple[list[TicketPurchase], int]:
        # C-AUTH-004 / NFR-SEC-003: 本人分のみ。購入日降順 (FR-010)。
        stmt = (
            select(TicketPurchase)
            .where(TicketPurchase.user_id == user_id)
            .options(selectinload(TicketPurchase.items))
            .order_by(TicketPurchase.purchased_at.desc(), TicketPurchase.id.desc())
            .limit(limit)
            .offset(offset)
        )
        total = self.db.execute(
            select(func.count())
            .select_from(TicketPurchase)
            .where(TicketPurchase.user_id == user_id)
        ).scalar_one()
        return list(self.db.execute(stmt).scalars()), total
