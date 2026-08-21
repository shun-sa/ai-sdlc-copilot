"""商品注文サービス単体テスト (FR-008)。

対象: app/services/order_service.py
検証Requirement:
- FR-008 注文確定 (在庫減算, 注文番号発行, カートクリア)
- C-DATA-004 / ADR-008 (購入時スナップショット保持・確定後不変)
- ADR-007 / NFR-AVL-001 (在庫確認と減算の原子性)
- ERR-003 (在庫不足で注文失敗)
- ERR-005 / NFR-AVL-003 (更新失敗時に不整合を残さない)
DB Strategy: CONTAINER (使い捨てSQLite。トランザクション整合性の実挙動を検証)。
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.errors import OutOfStockError, ValidationError
from app.models.order import Order
from app.models.product import Product
from app.models.user import User
from app.payment import PaymentGateway
from app.schemas.commerce import AddToCartInput, OrderInput
from app.services.cart_service import CartService
from app.services.order_service import OrderService


def _order_input(**overrides: object) -> OrderInput:
    data = {
        "name": "山田太郎",
        "postal_code": "150-0001",
        "prefecture": "東京都",
        "address_line": "渋谷区1-2-3",
        "phone": "03-1234-5678",
        "payment_method": "mock_credit_card",
    }
    data.update(overrides)
    return OrderInput(**data)  # type: ignore[arg-type]


def _add_to_cart(db: Session, user_id: int, product_id: int, quantity: int) -> None:
    CartService(db).add(user_id, AddToCartInput(product_id=product_id, quantity=quantity))


def _order_count(db: Session) -> int:
    return db.execute(select(func.count()).select_from(Order)).scalar_one()


class TestPlaceOrderNormal:
    # FR-008 正常系: 注文確定で注文番号が発行される
    def test_order_number_issued(
        self,
        db: Session,
        payment: PaymentGateway,
        make_user: Callable[..., User],
        make_product: Callable[..., Product],
    ) -> None:
        user = make_user()
        product = make_product(stock=10, price=1000)
        _add_to_cart(db, user.id, product.id, 2)

        order = OrderService(db, payment).place_order(user.id, _order_input())
        assert order.order_number.startswith("ORD-")
        assert order.total_amount == 2000
        assert order.status == "confirmed"

    # FR-008 / NFR-AVL-001: 注文確定時に在庫を減算する
    def test_stock_decremented(
        self,
        db: Session,
        payment: PaymentGateway,
        make_user: Callable[..., User],
        make_product: Callable[..., Product],
    ) -> None:
        user = make_user()
        product = make_product(stock=10)
        _add_to_cart(db, user.id, product.id, 3)

        OrderService(db, payment).place_order(user.id, _order_input())
        db.refresh(product)
        assert product.stock == 7  # 10 - 3

    # FR-008: 注文完了でカートがクリアされる
    def test_cart_cleared(
        self,
        db: Session,
        payment: PaymentGateway,
        make_user: Callable[..., User],
        make_product: Callable[..., Product],
    ) -> None:
        user = make_user()
        product = make_product(stock=10)
        _add_to_cart(db, user.id, product.id, 2)

        OrderService(db, payment).place_order(user.id, _order_input())
        db.expire_all()  # コミット済みDB状態を再取得 (本番はリクエスト毎に新セッション)
        assert CartService(db).view(user.id).lines == []

    # C-DATA-004 / ADR-008: 注文明細に購入時点スナップショットを保持する
    def test_snapshot_saved(
        self,
        db: Session,
        payment: PaymentGateway,
        make_user: Callable[..., User],
        make_product: Callable[..., Product],
    ) -> None:
        user = make_user()
        product = make_product(stock=10, price=1500, name="限定グッズ")
        _add_to_cart(db, user.id, product.id, 2)

        order = OrderService(db, payment).place_order(user.id, _order_input())
        item = order.items[0]
        assert item.product_snapshot_name == "限定グッズ"
        assert item.unit_price == 1500
        assert item.quantity == 2
        assert item.subtotal == 3000

    # ADR-008: 確定後にマスタ価格を変更してもスナップショットは不変
    def test_snapshot_immutable_after_master_change(
        self,
        db: Session,
        payment: PaymentGateway,
        make_user: Callable[..., User],
        make_product: Callable[..., Product],
    ) -> None:
        user = make_user()
        product = make_product(stock=10, price=1000, name="旧名称")
        _add_to_cart(db, user.id, product.id, 1)
        order = OrderService(db, payment).place_order(user.id, _order_input())

        product.price_tax_included = 9999
        product.name = "新名称"
        db.commit()
        db.refresh(order)

        assert order.items[0].unit_price == 1000
        assert order.items[0].product_snapshot_name == "旧名称"


class TestPlaceOrderFailure:
    # FR-008: 空カートは注文不可
    def test_empty_cart_rejected(
        self, db: Session, payment: PaymentGateway, make_user: Callable[..., User]
    ) -> None:
        user = make_user()
        with pytest.raises(ValidationError):
            OrderService(db, payment).place_order(user.id, _order_input())

    # ERR-003 / ERR-005 / NFR-AVL-003: 在庫不足時は注文失敗し不整合を残さない
    def test_out_of_stock_rolls_back(
        self,
        db: Session,
        payment: PaymentGateway,
        make_user: Callable[..., User],
        make_product: Callable[..., Product],
    ) -> None:
        user = make_user()
        product = make_product(stock=10)
        _add_to_cart(db, user.id, product.id, 5)

        # カート投入後に在庫が減少 (確定時点で不足)
        product.stock = 3
        db.commit()

        with pytest.raises(OutOfStockError):
            OrderService(db, payment).place_order(user.id, _order_input())

        # ERR-005: 注文レコードは残らない / 在庫は変化しない
        assert _order_count(db) == 0
        db.refresh(product)
        assert product.stock == 3

    # ADR-007 / NFR-AVL-001: 複数明細で一部在庫不足なら全体をロールバック
    def test_atomic_rollback_on_partial_shortage(
        self,
        db: Session,
        payment: PaymentGateway,
        make_user: Callable[..., User],
        make_product: Callable[..., Product],
    ) -> None:
        user = make_user()
        product_a = make_product(name="A", stock=10)
        product_b = make_product(name="B", stock=10)
        _add_to_cart(db, user.id, product_a.id, 2)
        _add_to_cart(db, user.id, product_b.id, 5)

        # Bの在庫のみ確定時点で不足させる
        product_b.stock = 1
        db.commit()

        with pytest.raises(OutOfStockError):
            OrderService(db, payment).place_order(user.id, _order_input())

        # 原子性: どちらの在庫も減算されず、注文も作成されない
        assert _order_count(db) == 0
        db.refresh(product_a)
        db.refresh(product_b)
        assert product_a.stock == 10
        assert product_b.stock == 1

    # ERR-004 / ERR-005: 販売不可商品を含む注文は失敗しロールバック
    def test_unsaleable_product_rolls_back(
        self,
        db: Session,
        payment: PaymentGateway,
        make_user: Callable[..., User],
        make_product: Callable[..., Product],
    ) -> None:
        user = make_user()
        product = make_product(stock=10)
        _add_to_cart(db, user.id, product.id, 2)

        # 確定前に非公開化 (販売不可)
        product.publish_status = "unpublished"
        db.commit()

        with pytest.raises(ValidationError):
            OrderService(db, payment).place_order(user.id, _order_input())
        assert _order_count(db) == 0
