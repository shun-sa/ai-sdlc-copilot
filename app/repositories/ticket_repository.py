from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ticket import TicketPurchase


class TicketRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, purchase: TicketPurchase) -> TicketPurchase:
        self._session.add(purchase)
        self._session.flush()
        return purchase

    def exists_purchase_number(self, purchase_number: str) -> bool:
        stmt = select(TicketPurchase.id).where(TicketPurchase.purchase_number == purchase_number)
        return self._session.scalars(stmt).first() is not None

    def list_by_user(
        self, user_id: int, *, offset: int = 0, limit: int = 20
    ) -> tuple[list[TicketPurchase], int]:
        # ADR-006: 本人絞り込み。ADR-013: 購入日降順・20件ページング。
        conditions = [TicketPurchase.user_id == user_id]
        total = len(self._session.scalars(select(TicketPurchase.id).where(*conditions)).all())
        stmt = (
            select(TicketPurchase)
            .where(*conditions)
            .order_by(TicketPurchase.purchased_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(self._session.scalars(stmt).all()), total

    def get_owned(self, purchase_id: int, user_id: int) -> TicketPurchase | None:
        stmt = select(TicketPurchase).where(
            TicketPurchase.id == purchase_id, TicketPurchase.user_id == user_id
        )
        return self._session.scalars(stmt).first()
