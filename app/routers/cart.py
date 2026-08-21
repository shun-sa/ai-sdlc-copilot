"""カートルーター (FR-006 追加 / FR-007 変更)。要認証 (C-AUTH-002)。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_session, require_user, verify_csrf
from app.errors import AppError
from app.models.session import SessionRecord
from app.models.user import User
from app.schemas.commerce import AddToCartInput, UpdateCartItemInput
from app.services.cart_service import CartService
from app.templating import render

router = APIRouter(prefix="/cart")


@router.get("")
def view_cart(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    session: SessionRecord | None = Depends(get_current_session),
):
    view = CartService(db).view(user.id)
    return render(
        request,
        "cart/view.html",
        {
            "user": user,
            "cart": view,
            "csrf_token": session.csrf_token if session else "",
            "message": request.query_params.get("message"),
        },
    )


@router.post("/add")
def add_to_cart(
    request: Request,
    product_id: int = Form(...),
    quantity: int = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    _: None = Depends(verify_csrf),
):
    try:
        data = AddToCartInput(product_id=product_id, quantity=quantity)
        CartService(db).add(user.id, data)
    except AppError as exc:
        return RedirectResponse(
            url=f"/products/{product_id}?error={exc.message}", status_code=303
        )
    except Exception:  # noqa: BLE001 - 入力型不正
        return RedirectResponse(
            url=f"/products/{product_id}?error=入力値が正しくありません。", status_code=303
        )
    return RedirectResponse(url="/cart?message=カートに追加しました。", status_code=303)


@router.post("/items/{item_id}")
def update_item(
    request: Request,
    item_id: int,
    quantity: int = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    _: None = Depends(verify_csrf),
):
    try:
        data = UpdateCartItemInput(quantity=quantity)
        CartService(db).update_item(user.id, item_id, data.quantity)
    except AppError as exc:
        return RedirectResponse(url=f"/cart?message={exc.message}", status_code=303)
    except Exception:  # noqa: BLE001
        return RedirectResponse(url="/cart?message=入力値が正しくありません。", status_code=303)
    return RedirectResponse(url="/cart?message=カートを更新しました。", status_code=303)
