"""Cart Repository (FR-006 / FR-007)。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.cart import Cart, CartItem


class CartRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_or_create_by_user(self, user_id: int) -> Cart:
        cart = self.db.execute(
            select(Cart).where(Cart.user_id == user_id).options(selectinload(Cart.items))
        ).scalar_one_or_none()
        if cart is None:
            cart = Cart(user_id=user_id)
            self.db.add(cart)
            self.db.flush()
        return cart

    def get_item(self, cart_id: int, product_id: int) -> CartItem | None:
        return self.db.execute(
            select(CartItem).where(
                CartItem.cart_id == cart_id, CartItem.product_id == product_id
            )
        ).scalar_one_or_none()

    def get_item_by_id(self, item_id: int) -> CartItem | None:
        return self.db.get(CartItem, item_id)

    def add_item(self, item: CartItem) -> CartItem:
        self.db.add(item)
        self.db.flush()
        return item

    def delete_item(self, item: CartItem) -> None:
        self.db.delete(item)
        self.db.flush()

    def clear(self, cart: Cart) -> None:
        for item in list(cart.items):
            self.db.delete(item)
        self.db.flush()
