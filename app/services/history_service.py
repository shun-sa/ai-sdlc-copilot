"""購入履歴サービス (FR-010)。

本人分のみ参照 (C-AUTH-004 / NFR-SEC-003 / ADR-005)。
表示はスナップショット参照 (ADR-008)。マスタ再算出しない。
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.constants import HISTORY_PAGE_SIZE
from app.errors import ForbiddenError
from app.models.order import Order
from app.repositories.order_repository import OrderRepository
from app.repositories.ticket_repository import TicketRepository
from app.services.catalog_service import PageResult


class HistoryService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.orders = OrderRepository(db)
        self.tickets = TicketRepository(db)

    def order_history(self, user_id: int, page: int = 1) -> PageResult:
        offset = (page - 1) * HISTORY_PAGE_SIZE
        rows, total = self.orders.list_by_user(
            user_id, limit=HISTORY_PAGE_SIZE, offset=offset
        )
        return PageResult(items=rows, total=total, page=page, page_size=HISTORY_PAGE_SIZE)

    def ticket_history(self, user_id: int, page: int = 1) -> PageResult:
        offset = (page - 1) * HISTORY_PAGE_SIZE
        rows, total = self.tickets.list_by_user(
            user_id, limit=HISTORY_PAGE_SIZE, offset=offset
        )
        return PageResult(items=rows, total=total, page=page, page_size=HISTORY_PAGE_SIZE)

    def order_detail(self, user_id: int, order_id: int) -> Order:
        # ADR-005: 所有者スコープ強制。本人以外はアクセス不可 (ERR-004)。
        order = self.orders.get_owned(order_id, user_id)
        if order is None:
            raise ForbiddenError("この履歴は参照できません。")
        return order
