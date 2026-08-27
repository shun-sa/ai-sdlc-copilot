from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.constants import DEFAULT_PAGE_SIZE
from app.models.order import Order
from app.models.ticket import TicketPurchase
from app.repositories.order_repository import OrderRepository
from app.repositories.ticket_repository import TicketRepository


@dataclass
class HistoryView:
    orders: list[Order]
    orders_total: int
    tickets: list[TicketPurchase]
    tickets_total: int
    page: int
    page_size: int


class HistoryService:
    """FR-010。本人分の購入履歴のみをスナップショットで降順表示する（ADR-005/006/008/013）。"""

    def __init__(self, session: Session) -> None:
        self._orders = OrderRepository(session)
        self._tickets = TicketRepository(session)

    def list_history(self, user_id: int, page: int = 1) -> HistoryView:
        offset = (page - 1) * DEFAULT_PAGE_SIZE
        # ADR-006: 常に本人user_idで絞り込み、他会員データを返さない。
        orders, orders_total = self._orders.list_by_user(
            user_id, offset=offset, limit=DEFAULT_PAGE_SIZE
        )
        tickets, tickets_total = self._tickets.list_by_user(
            user_id, offset=offset, limit=DEFAULT_PAGE_SIZE
        )
        return HistoryView(
            orders=orders,
            orders_total=orders_total,
            tickets=tickets,
            tickets_total=tickets_total,
            page=page,
            page_size=DEFAULT_PAGE_SIZE,
        )
