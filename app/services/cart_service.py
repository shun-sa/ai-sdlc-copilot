"""カートサービス (FR-006 / FR-007)。

カート投入時は在庫を減算しない (業務ルール / FR-006制約)。
在庫減算は注文確定時 (OrderService) に行う。
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.errors import NotSaleableError, OutOfStockError, ValidationError
from app.models.cart import CartItem
from app.models.product import Product
from app.repositories.cart_repository import CartRepository
from app.repositories.product_repository import ProductRepository
from app.schemas.commerce import AddToCartInput


@dataclass
class CartLine:
    item: CartItem
    product: Product
    subtotal: int


@dataclass
class CartView:
    lines: list[CartLine]
    total: int
    has_unorderable: bool


class CartService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.carts = CartRepository(db)
        self.products = ProductRepository(db)

    def add(self, user_id: int, data: AddToCartInput) -> None:
        product = self.products.get_visible(data.product_id)
        if product is None:
            raise NotSaleableError("対象の商品は購入できません。")
        # C-DATA-002 / ERR-004: 販売期間外・非公開は不可
        if not ProductRepository.is_saleable(product):
            raise NotSaleableError("この商品は現在購入できません。")

        cart = self.carts.get_or_create_by_user(user_id)
        existing = self.carts.get_item(cart.id, product.id)
        current_qty = existing.quantity if existing else 0
        new_qty = current_qty + data.quantity

        # C-DATA-003 / ERR-003: 在庫超過不可
        if product.stock <= 0:
            raise OutOfStockError("この商品は在庫がありません。")
        if new_qty > product.stock:
            raise OutOfStockError("在庫数を超える数量は追加できません。")

        if existing:
            existing.quantity = new_qty
            self.db.flush()
        else:
            self.carts.add_item(
                CartItem(cart_id=cart.id, product_id=product.id, quantity=data.quantity)
            )
        self.db.commit()

    def update_item(self, user_id: int, item_id: int, quantity: int) -> None:
        cart = self.carts.get_or_create_by_user(user_id)
        item = self.carts.get_item_by_id(item_id)
        # ADR-005: 本人カートのアイテムのみ操作可
        if item is None or item.cart_id != cart.id:
            raise ValidationError("対象のカート項目が見つかりません。")

        if quantity == 0:
            self.carts.delete_item(item)  # 0は削除扱い (FR-007)
            self.db.commit()
            return

        product = self.products.get_visible(item.product_id)
        if product is None or quantity > product.stock:
            raise OutOfStockError("在庫数を超える数量には変更できません。")
        item.quantity = quantity
        self.db.flush()
        self.db.commit()

    def view(self, user_id: int) -> CartView:
        cart = self.carts.get_or_create_by_user(user_id)
        lines: list[CartLine] = []
        total = 0
        has_unorderable = False
        for item in cart.items:
            product = self.products.get_visible(item.product_id)
            if product is None or not ProductRepository.is_saleable(product):
                has_unorderable = True
                if product is not None:
                    lines.append(CartLine(item=item, product=product, subtotal=0))
                continue
            if item.quantity > product.stock:
                has_unorderable = True
            subtotal = product.price_tax_included * item.quantity
            total += subtotal
            lines.append(CartLine(item=item, product=product, subtotal=subtotal))
        return CartView(lines=lines, total=total, has_unorderable=has_unorderable)
