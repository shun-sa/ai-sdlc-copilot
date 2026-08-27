from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.cart import Cart, CartItem


class CartRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_or_create_cart(self, user_id: int) -> Cart:
        stmt = select(Cart).where(Cart.user_id == user_id)
        cart = self._session.scalars(stmt).first()
        if cart is None:
            cart = Cart(user_id=user_id)
            self._session.add(cart)
            self._session.flush()
        return cart

    def get_cart(self, user_id: int) -> Cart | None:
        stmt = select(Cart).where(Cart.user_id == user_id)
        return self._session.scalars(stmt).first()

    def get_item(self, cart_id: int, product_id: int) -> CartItem | None:
        stmt = select(CartItem).where(CartItem.cart_id == cart_id, CartItem.product_id == product_id)
        return self._session.scalars(stmt).first()

    def get_item_by_id(self, item_id: int) -> CartItem | None:
        return self._session.get(CartItem, item_id)

    def add_item(self, cart_id: int, product_id: int, quantity: int) -> CartItem:
        item = CartItem(cart_id=cart_id, product_id=product_id, quantity=quantity)
        self._session.add(item)
        self._session.flush()
        return item

    def remove_item(self, item: CartItem) -> None:
        self._session.delete(item)
        self._session.flush()

    def clear(self, cart: Cart) -> None:
        for item in list(cart.items):
            self._session.delete(item)
        self._session.flush()
