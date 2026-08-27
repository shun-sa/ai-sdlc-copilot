"""OrderService の単体テスト（使い捨て in-memory SQLite）。

Requirement: FR-008 / C-DATA-004 / ERR-003 / ERR-005 / NFR-AVL-001 / NFR-AVL-003
ADR: ADR-007（トランザクション整合）/ ADR-008（スナップショット）/ ADR-011（支払方法）
Criteria: normal-case, exception, database
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.constants import PaymentMethod
from app.errors import InputInvalidError, StockShortageError
from app.models.order import Order
from app.models.product import Product
from app.repositories.cart_repository import CartRepository
from app.schemas.commerce import CartAddInput, OrderInput
from app.services.cart_service import CartService
from app.services.order_service import OrderService

from .conftest import make_product, make_user


def _order_input(**overrides: object) -> OrderInput:
    data = {
        "recipient_name": "受取太郎",
        "postal_code": "150-0001",
        "prefecture": "東京都",
        "city_address": "渋谷区1-1-1",
        "phone": "03-1234-5678",
        "payment_method": PaymentMethod.CREDIT_CARD_MOCK,
    }
    data.update(overrides)
    return OrderInput(**data)


def _fill_cart(db_session: Session, user_id: int, product_id: int, quantity: int) -> None:
    CartService(db_session).add_to_cart(
        user_id, CartAddInput(product_id=product_id, quantity=quantity)
    )


class TestPlaceOrderNormal:
    def test_order_number_issued_and_total_computed(self, db_session: Session) -> None:
        # FR-008: 注文確定・注文番号発行・合計算出。
        user = make_user(db_session)
        product = make_product(db_session, price=1980, stock=10)
        _fill_cart(db_session, user.id, product.id, 2)
        order = OrderService(db_session).place_order(user.id, _order_input())
        assert order.order_number
        assert order.total_amount == 1980 * 2

    def test_stock_decremented_on_confirm(self, db_session: Session) -> None:
        # NFR-AVL-001: 注文登録と在庫減算の整合。
        user = make_user(db_session)
        product = make_product(db_session, stock=10)
        _fill_cart(db_session, user.id, product.id, 3)
        OrderService(db_session).place_order(user.id, _order_input())
        assert db_session.get(Product, product.id).stock == 7

    def test_cart_cleared_after_confirm(self, db_session: Session) -> None:
        # FR-008: 確定後にカートをクリアする。
        user = make_user(db_session)
        product = make_product(db_session, stock=10)
        _fill_cart(db_session, user.id, product.id, 1)
        OrderService(db_session).place_order(user.id, _order_input())
        # 永続状態を再読込して検証（本番は後続リクエストの新規セッションで再取得される）。
        db_session.expire_all()
        cart = CartRepository(db_session).get_cart(user.id)
        assert cart is not None
        assert list(cart.items) == []

    def test_snapshot_persisted_and_immutable_after_master_change(self, db_session: Session) -> None:
        # C-DATA-004 / ADR-008: 確定時点の商品名・単価を明細スナップショットで保持し、
        # 後日のマスタ変更に影響されない。
        user = make_user(db_session)
        product = make_product(db_session, name="旧名称", price=1000, stock=10)
        _fill_cart(db_session, user.id, product.id, 2)
        order = OrderService(db_session).place_order(user.id, _order_input())
        item = order.items[0]
        assert item.product_snapshot_name == "旧名称"
        assert item.unit_price == 1000

        # マスタの名称・価格を変更しても、既存明細スナップショットは不変。
        product.name = "新名称"
        product.price_tax_included = 9999
        db_session.commit()
        stored = db_session.get(Order, order.id)
        assert stored.items[0].product_snapshot_name == "旧名称"
        assert stored.items[0].unit_price == 1000


class TestPlaceOrderFailure:
    def test_empty_cart_rejected(self, db_session: Session) -> None:
        user = make_user(db_session)
        with pytest.raises(InputInvalidError):
            OrderService(db_session).place_order(user.id, _order_input())

    def test_out_of_stock_rolls_back(self, db_session: Session) -> None:
        # ERR-003: 在庫不足で注文失敗。在庫が更新途中で減った状況を再現。
        user = make_user(db_session)
        product = make_product(db_session, stock=5)
        _fill_cart(db_session, user.id, product.id, 5)
        # カート投入後に在庫が 3 に減少（別注文などを想定）。
        product.stock = 3
        db_session.commit()
        with pytest.raises(StockShortageError):
            OrderService(db_session).place_order(user.id, _order_input())
        # ERR-005 / NFR-AVL-003: 失敗時は不整合を残さない（在庫は減算されない）。
        assert db_session.get(Product, product.id).stock == 3

    def test_atomic_rollback_on_partial_shortage(self, db_session: Session) -> None:
        # NFR-AVL-001/003 / ADR-007: 複数明細のうち一部が在庫不足なら全体をロールバックし、
        # 先行商品の在庫も減算されない。
        user = make_user(db_session)
        p_ok = make_product(db_session, name="在庫十分", stock=10)
        p_ng = make_product(db_session, name="在庫不足", stock=1)
        service = CartService(db_session)
        service.add_to_cart(user.id, CartAddInput(product_id=p_ok.id, quantity=2))
        service.add_to_cart(user.id, CartAddInput(product_id=p_ng.id, quantity=1))
        # 追加後に在庫不足商品の在庫を 0 にする。
        p_ng.stock = 0
        db_session.commit()
        with pytest.raises(StockShortageError):
            OrderService(db_session).place_order(user.id, _order_input())
        # 先行して処理された在庫十分商品の在庫も元のまま。
        assert db_session.get(Product, p_ok.id).stock == 10
        assert db_session.get(Product, p_ng.id).stock == 0
        # 注文は 1 件も作成されない。
        assert db_session.query(Order).count() == 0
