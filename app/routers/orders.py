from fastapi import APIRouter, Depends, Form, Request
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_user
from app.errors import InputInvalidError
from app.models.user import User
from app.routers import render
from app.routers.auth import _field_errors
from app.schemas.commerce import OrderInput
from app.services.cart_service import CartService
from app.services.order_service import OrderService

router = APIRouter()


@router.get("/orders/new")
def order_form(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
):
    cart = CartService(db).get_cart_view(current_user.id)
    if not cart.lines:
        return render(request, "cart.html", current_user, cart=cart)
    # NFR-USAB-003: 確定前に配送先・支払・金額を確認可能。
    return render(request, "order_form.html", current_user, cart=cart, form=None, field_errors={})


@router.post("/orders")
def place_order(
    request: Request,
    recipient_name: str = Form(""),
    postal_code: str = Form(""),
    prefecture: str = Form(""),
    city_address: str = Form(""),
    phone: str = Form(""),
    payment_method: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
):
    cart = CartService(db).get_cart_view(current_user.id)
    form = {
        "recipient_name": recipient_name, "postal_code": postal_code,
        "prefecture": prefecture, "city_address": city_address, "phone": phone,
    }
    try:
        data = OrderInput(
            recipient_name=recipient_name, postal_code=postal_code, prefecture=prefecture,
            city_address=city_address, phone=phone, payment_method=payment_method,
        )
    except ValidationError as exc:
        # ERR-001: 入力不備は項目単位表示。
        return render(
            request, "order_form.html", current_user,
            status_code=400, cart=cart, form=form, field_errors=_field_errors(exc),
        )

    order = OrderService(db).place_order(current_user.id, data)
    return render(request, "order_done.html", current_user, order=order)
