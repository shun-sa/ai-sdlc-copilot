from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_user
from app.models.user import User
from app.routers import render
from app.schemas.commerce import CartAddInput, CartUpdateInput
from app.services.cart_service import CartService

router = APIRouter()


@router.get("/cart")
def view_cart(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
):
    cart = CartService(db).get_cart_view(current_user.id)
    return render(request, "cart.html", current_user, cart=cart)


@router.post("/cart/add")
def add_to_cart(
    product_id: int = Form(...),
    quantity: int = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
):
    data = CartAddInput(product_id=product_id, quantity=quantity)
    CartService(db).add_to_cart(current_user.id, data)
    return RedirectResponse(url="/cart", status_code=303)


@router.post("/cart/items/{item_id}")
def update_cart_item(
    item_id: int,
    quantity: int = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
):
    data = CartUpdateInput(quantity=quantity)
    CartService(db).update_item(current_user.id, item_id, data)
    return RedirectResponse(url="/cart", status_code=303)
