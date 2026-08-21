"""購入履歴サービス単体テスト (FR-010)。

対象: app/services/history_service.py
検証Requirement:
- FR-010 購入履歴 (本人分のみ, 注文日/購入日降順, スナップショット表示)
- C-AUTH-004 / NFR-SEC-003 / ADR-005 (本人以外の履歴参照不可 = IDOR防止)
- ERR-004 (他人の履歴アクセスは操作不可)
DB Strategy: CONTAINER (使い捨てSQLite。所有者スコープSQLと降順を実DBで検証)。
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from sqlalchemy.orm import Session

from app.errors import ForbiddenError
from app.models.product import Product
from app.models.user import User
from app.payment import PaymentGateway
from app.schemas.commerce import AddToCartInput, OrderInput
from app.services.cart_service import CartService
from app.services.history_service import HistoryService
from app.services.order_service import OrderService


def _place_order(
    db: Session, payment: PaymentGateway, user_id: int, product_id: int, quantity: int = 1
):
    CartService(db).add(user_id, AddToCartInput(product_id=product_id, quantity=quantity))
    data = OrderInput(
        name="山田太郎",
        postal_code="150-0001",
        prefecture="東京都",
        address_line="渋谷区1-2-3",
        phone="03-1234-5678",
        payment_method="mock_credit_card",
    )
    return OrderService(db, payment).place_order(user_id, data)


class TestOrderHistory:
    # FR-010 / NFR-SEC-003: 本人分の注文のみ表示する
    def test_only_own_orders(
        self,
        db: Session,
        payment: PaymentGateway,
        make_user: Callable[..., User],
        make_product: Callable[..., Product],
    ) -> None:
        owner = make_user(email="owner@example.com")
        other = make_user(email="other@example.com")
        product = make_product(stock=100)
        _place_order(db, payment, owner.id, product.id)

        assert HistoryService(db).order_history(owner.id).total == 1
        assert HistoryService(db).order_history(other.id).total == 0

    # FR-010: 注文日降順で表示する (新しい注文が先頭)
    def test_orders_descending(
        self,
        db: Session,
        payment: PaymentGateway,
        make_user: Callable[..., User],
        make_product: Callable[..., Product],
    ) -> None:
        user = make_user()
        product = make_product(stock=100)
        first = _place_order(db, payment, user.id, product.id)
        second = _place_order(db, payment, user.id, product.id)

        rows = HistoryService(db).order_history(user.id).items
        assert [o.id for o in rows] == [second.id, first.id]

    # FR-010 / ADR-008: 履歴はスナップショットを表示する
    def test_history_shows_snapshot(
        self,
        db: Session,
        payment: PaymentGateway,
        make_user: Callable[..., User],
        make_product: Callable[..., Product],
    ) -> None:
        user = make_user()
        product = make_product(stock=100, price=1200, name="パンフレット")
        _place_order(db, payment, user.id, product.id, quantity=2)

        order = HistoryService(db).order_history(user.id).items[0]
        assert order.items[0].product_snapshot_name == "パンフレット"
        assert order.items[0].unit_price == 1200


class TestOrderDetailAuthorization:
    # ADR-005: 所有者は自分の注文詳細を参照できる
    def test_owner_can_access_detail(
        self,
        db: Session,
        payment: PaymentGateway,
        make_user: Callable[..., User],
        make_product: Callable[..., Product],
    ) -> None:
        owner = make_user(email="owner@example.com")
        product = make_product(stock=100)
        order = _place_order(db, payment, owner.id, product.id)

        detail = HistoryService(db).order_detail(owner.id, order.id)
        assert detail.id == order.id

    # ADR-005 / NFR-SEC-003 / ERR-004: 他会員の注文詳細は参照不可 (IDOR防止)
    def test_other_user_forbidden(
        self,
        db: Session,
        payment: PaymentGateway,
        make_user: Callable[..., User],
        make_product: Callable[..., Product],
    ) -> None:
        owner = make_user(email="owner@example.com")
        attacker = make_user(email="attacker@example.com")
        product = make_product(stock=100)
        order = _place_order(db, payment, owner.id, product.id)

        with pytest.raises(ForbiddenError):
            HistoryService(db).order_detail(attacker.id, order.id)
