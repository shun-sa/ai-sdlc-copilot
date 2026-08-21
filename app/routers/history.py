"""購入履歴ルーター (FR-010)。要認証・本人分のみ (C-AUTH-004 / ADR-005)。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_user
from app.models.user import User
from app.services.history_service import HistoryService
from app.templating import render

router = APIRouter(prefix="/history")


@router.get("")
def history(
    request: Request,
    page: int = Query(default=1, ge=1),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    service = HistoryService(db)
    orders = service.order_history(user.id, page)
    tickets = service.ticket_history(user.id, page)
    return render(
        request,
        "history/list.html",
        {"user": user, "orders": orders, "tickets": tickets},
    )


@router.get("/orders/{order_id}")
def order_detail(
    request: Request,
    order_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    # ADR-005: 本人以外は ForbiddenError となり操作不可 (ERR-004)
    order = HistoryService(db).order_detail(user.id, order_id)
    return render(request, "history/order_detail.html", {"user": user, "order": order})
