from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.errors import NotFoundError, StockShortageError
from app.models.product import Product
from app.repositories.cart_repository import CartRepository
from app.repositories.product_repository import ProductRepository
from app.schemas.commerce import CartAddInput, CartUpdateInput


@dataclass
class CartLineView:
    item_id: int
    product_id: int
    name: str
    unit_price: int
    quantity: int
    subtotal: int


@dataclass
class CartView:
    lines: list[CartLineView]
    total: int


class CartService:
    """FR-006/FR-007。カート投入・変更。投入時に在庫は減算しない（業務ルール）。"""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._carts = CartRepository(session)
        self._products = ProductRepository(session)

    def add_to_cart(self, user_id: int, data: CartAddInput) -> None:
        product = self._products.get_published(data.product_id)
        if product is None:
            raise NotFoundError()
        cart = self._carts.get_or_create_cart(user_id)
        existing = self._carts.get_item(cart.id, product.id)
        # 同一商品は数量加算（FR-006）。在庫超過はカート追加を失敗（ERR-003）。
        new_quantity = (existing.quantity if existing else 0) + data.quantity
        if new_quantity > product.stock:
            raise StockShortageError()
        if existing is not None:
            existing.quantity = new_quantity
        else:
            self._carts.add_item(cart.id, product.id, data.quantity)
        self._session.commit()

    def update_item(self, user_id: int, item_id: int, data: CartUpdateInput) -> None:
        item = self._carts.get_item_by_id(item_id)
        cart = self._carts.get_cart(user_id)
        # ADR-006: 本人カートの明細のみ変更可。
        if item is None or cart is None or item.cart_id != cart.id:
            raise NotFoundError()
        if data.quantity == 0:
            self._carts.remove_item(item)  # FR-007: 0は削除扱い
            self._session.commit()
            return
        product = self._products.get_published(item.product_id)
        if product is None:
            raise NotFoundError()
        if data.quantity > product.stock:
            raise StockShortageError()
        item.quantity = data.quantity
        self._session.commit()

    def get_cart_view(self, user_id: int) -> CartView:
        cart = self._carts.get_cart(user_id)
        if cart is None:
            return CartView(lines=[], total=0)
        lines: list[CartLineView] = []
        total = 0
        for item in cart.items:
            product = self._products.get_published(item.product_id)
            if product is None:
                continue
            subtotal = product.price_tax_included * item.quantity
            total += subtotal
            lines.append(
                CartLineView(
                    item_id=item.id,
                    product_id=product.id,
                    name=product.name,
                    unit_price=product.price_tax_included,
                    quantity=item.quantity,
                    subtotal=subtotal,
                )
            )
        return CartView(lines=lines, total=total)
