"""注文ルーター (FR-008)。要認証 (C-AUTH-002)。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.orm import Session

from app.constants import DEFAULT_PAYMENT_METHOD, PAYMENT_METHODS
from app.database import get_db
from app.dependencies import get_current_session, require_user, verify_csrf
from app.errors import AppError
from app.models.session import SessionRecord
from app.models.user import User
from app.payment import get_payment_gateway
from app.schemas.commerce import OrderInput
from app.services.cart_service import CartService
from app.services.order_service import OrderService
from app.templating import render

router = APIRouter(prefix="/orders")


@router.get("/new")
def order_form(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    session: SessionRecord | None = Depends(get_current_session),
):
    # NFR-USAB-003: 確定前に配送先・支払・金額を確認可能
    cart = CartService(db).view(user.id)
    return render(
        request,
        "orders/new.html",
        {
            "user": user,
            "cart": cart,
            "payment_methods": PAYMENT_METHODS,
            "default_payment": DEFAULT_PAYMENT_METHOD,
            "csrf_token": session.csrf_token if session else "",
            "errors": {},
            "values": {},
        },
    )


@router.post("")
def place_order(
    request: Request,
    name: str = Form(""),
    postal_code: str = Form(""),
    prefecture: str = Form(""),
    address_line: str = Form(""),
    phone: str = Form(""),
    payment_method: str = Form(DEFAULT_PAYMENT_METHOD),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    _: None = Depends(verify_csrf),
    session: SessionRecord | None = Depends(get_current_session),
):
    values = {
        "name": name,
        "postal_code": postal_code,
        "prefecture": prefecture,
        "address_line": address_line,
        "phone": phone,
        "payment_method": payment_method,
    }
    cart_service = CartService(db)
    try:
        data = OrderInput(**values)
    except PydanticValidationError as exc:
        return _order_error(request, user, session, cart_service, values, _field_errors(exc))

    service = OrderService(db, get_payment_gateway())
    try:
        order = service.place_order(user.id, data)
    except AppError as exc:
        return _order_error(
            request, user, session, cart_service, values, {"_general": exc.message}
        )
    return RedirectResponse(url=f"/orders/{order.id}/complete", status_code=303)


@router.get("/{order_id}/complete")
def order_complete(
    request: Request,
    order_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    from app.services.history_service import HistoryService

    order = HistoryService(db).order_detail(user.id, order_id)  # 所有者検証 (ADR-005)
    return render(request, "orders/complete.html", {"user": user, "order": order})


def _order_error(request, user, session, cart_service, values, errors):
    cart = cart_service.view(user.id)
    return render(
        request,
        "orders/new.html",
        {
            "user": user,
            "cart": cart,
            "payment_methods": PAYMENT_METHODS,
            "default_payment": DEFAULT_PAYMENT_METHOD,
            "csrf_token": session.csrf_token if session else "",
            "errors": errors,
            "values": values,
        },
        status_code=400,
    )


def _field_errors(exc: PydanticValidationError) -> dict:
    errors: dict[str, str] = {}
    for err in exc.errors():
        loc = err["loc"]
        field = str(loc[-1]) if loc else "form"
        errors[field] = err.get("msg", "入力値が正しくありません。")
    return errors
