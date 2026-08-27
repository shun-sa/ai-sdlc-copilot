import secrets

from sqlalchemy.orm import Session

from app.constants import PAYMENT_METHOD_LABELS
from app.errors import InputInvalidError
from app.models.order import Order, OrderItem
from app.payment import MockPayment
from app.repositories.cart_repository import CartRepository
from app.repositories.order_repository import OrderRepository
from app.repositories.product_repository import ProductRepository
from app.schemas.commerce import OrderInput
from app.services.availability import ensure_product_orderable


class OrderService:
    """FR-008。注文確定・在庫減算・スナップショット保持を単一トランザクションで行う（ADR-007/008）。"""

    def __init__(self, session: Session, payment: MockPayment | None = None) -> None:
        self._session = session
        self._orders = OrderRepository(session)
        self._products = ProductRepository(session)
        self._carts = CartRepository(session)
        self._payment = payment or MockPayment()

    def place_order(self, user_id: int, data: OrderInput) -> Order:
        cart = self._carts.get_cart(user_id)
        if cart is None or not cart.items:
            raise InputInvalidError("カートが空です。")

        try:
            total = 0
            order = Order(
                order_number=self._generate_order_number(),
                user_id=user_id,
                shipping_address=self._compose_address(data),
                recipient_name=data.recipient_name,
                postal_code=data.postal_code,
                prefecture=data.prefecture,
                city_address=data.city_address,
                phone=data.phone,
                payment_method=data.payment_method,
                total_amount=0,
            )

            for cart_item in list(cart.items):
                # ADR-007: 在庫行を悲観ロックで取得し、確認から減算までを同一トランザクションで実行。
                product = self._products.get_for_update(cart_item.product_id)
                ensure_product_orderable(product, cart_item.quantity)
                assert product is not None
                subtotal = product.price_tax_included * cart_item.quantity
                total += subtotal
                product.stock -= cart_item.quantity  # 注文確定時に在庫減算
                order.items.append(
                    OrderItem(
                        product_id=product.id,
                        product_snapshot_name=product.name,  # ADR-008: 確定時点スナップショット
                        unit_price=product.price_tax_included,
                        quantity=cart_item.quantity,
                        subtotal=subtotal,
                    )
                )

            order.total_amount = total
            self._payment.charge(data.payment_method, total)  # CON-002: 模擬決済（常に成功）
            self._orders.add(order)
            self._carts.clear(cart)  # 確定後にカートをクリア（FR-008）
            self._session.commit()
            return order
        except Exception:
            # ERR-005 / NFR-AVL-003: 失敗時はロールバックし不完全データを残さない。
            self._session.rollback()
            raise

    @staticmethod
    def _compose_address(data: OrderInput) -> str:
        return f"〒{data.postal_code} {data.prefecture}{data.city_address}"

    def _generate_order_number(self) -> str:
        for _ in range(5):
            candidate = "ORD-" + secrets.token_hex(8).upper()
            if not self._orders.exists_order_number(candidate):
                return candidate
        raise RuntimeError("注文番号の採番に失敗しました。")


# 支払方法ラベル参照の露出（確認画面用）。
PAYMENT_LABELS = PAYMENT_METHOD_LABELS
