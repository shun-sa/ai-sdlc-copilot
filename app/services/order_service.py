"""商品注文サービス (FR-008)。

注文確定・在庫減算・番号発行を単一トランザクションで実行する (ADR-007)。
明細は購入時点スナップショットを保持する (C-DATA-004 / ADR-008)。
決済は模擬決済インターフェース経由 (ADR-009)。
失敗時は全体ロールバックし不整合を残さない (ERR-005 / NFR-AVL-001/003)。
"""

from __future__ import annotations

import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import ConflictError, OutOfStockError, ValidationError
from app.models.order import Order, OrderItem
from app.payment import PaymentGateway
from app.repositories.cart_repository import CartRepository
from app.repositories.order_repository import OrderRepository
from app.repositories.product_repository import ProductRepository
from app.schemas.commerce import OrderInput


class OrderService:
    def __init__(self, db: Session, payment: PaymentGateway) -> None:
        self.db = db
        self.payment = payment
        self.carts = CartRepository(db)
        self.products = ProductRepository(db)
        self.orders = OrderRepository(db)

    def place_order(self, user_id: int, data: OrderInput) -> Order:
        cart = self.carts.get_or_create_by_user(user_id)
        if not cart.items:
            raise ValidationError("カートが空です。")

        # 明細を一意な商品単位でまとめて取得（順序固定でデッドロック回避）
        wanted: dict[int, int] = {}
        for item in cart.items:
            wanted[item.product_id] = wanted.get(item.product_id, 0) + item.quantity

        order_items: list[OrderItem] = []
        total = 0
        try:
            # ADR-007: 在庫確認と減算を同一トランザクション内で行う
            for product_id in sorted(wanted):
                quantity = wanted[product_id]
                product = self.products.get_for_update(product_id)  # 悲観ロック
                if product is None or not ProductRepository.is_saleable(product):
                    raise ValidationError("注文できない商品が含まれています。")
                if product.stock < quantity:
                    # ERR-003: 在庫不足で注文失敗
                    raise OutOfStockError(
                        f"「{product.name}」の在庫が不足しています。"
                    )
                product.stock -= quantity  # 注文確定時に減算 (FR-008)
                unit_price = product.price_tax_included
                subtotal = unit_price * quantity
                total += subtotal
                order_items.append(
                    OrderItem(
                        product_id=product.id,
                        # ADR-008: 確定時点のスナップショット
                        product_snapshot_name=product.name,
                        unit_price=unit_price,
                        quantity=quantity,
                        subtotal=subtotal,
                    )
                )

            # ADR-009: 模擬決済（常に成功）
            self.payment.charge(total, data.payment_method)

            order = Order(
                order_number=_generate_number("ORD"),
                user_id=user_id,
                status="confirmed",
                shipping_address=_format_address(data),
                payment_method=data.payment_method,
                total_amount=total,
                items=order_items,
            )
            self.orders.add(order)
            self.carts.clear(cart)  # 注文完了でカートクリア (FR-008)
            self.db.commit()
        except (OutOfStockError, ValidationError):
            self.db.rollback()  # ERR-005: 不整合を残さない
            raise
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError() from exc
        self.db.refresh(order)
        return order


def _generate_number(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:16].upper()}"


def _format_address(data: OrderInput) -> str:
    return f"〒{data.postal_code} {data.prefecture}{data.address_line} {data.name} {data.phone}"
