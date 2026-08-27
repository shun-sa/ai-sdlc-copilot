"""Repository 層の単体テスト（使い捨て in-memory SQLite）。

DB 固有動作（UNIQUE 制約、公開フィルタ、悲観ロック取得、本人絞り込み・
降順ページング、価格参照）を検証する。

Requirement: DM-001/003/004 / C-DATA-001 / NFR-SEC-003 / ADR-013
ADR: ADR-003（使い捨てDB）/ ADR-006 / ADR-007 / ADR-012
Criteria: database, boundary-value, exception
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.constants import PublishStatus, TicketType
from app.models.cart import Cart, CartItem
from app.models.order import Order, OrderItem
from app.models.user import User
from app.repositories.cart_repository import CartRepository
from app.repositories.order_repository import OrderRepository
from app.repositories.product_repository import ProductRepository
from app.repositories.screening_repository import ScreeningRepository
from app.repositories.user_repository import UserRepository

from .conftest import make_movie, make_product, make_screening, make_user

UTC = timezone.utc


class TestUserRepository:
    def test_get_by_email(self, db_session: Session) -> None:
        make_user(db_session, email="find@example.com")
        repo = UserRepository(db_session)
        assert repo.get_by_email("find@example.com") is not None
        assert repo.get_by_email("missing@example.com") is None

    def test_email_unique_constraint(self, db_session: Session) -> None:
        # DM-001: email は一意。重複挿入は DB 制約で拒否される。
        make_user(db_session, email="dup@example.com")
        db_session.add(
            User(name="別人", email="dup@example.com", password_hash="x")
        )
        with pytest.raises(IntegrityError):
            db_session.flush()
        db_session.rollback()


class TestProductRepository:
    def test_get_published_excludes_unpublished(self, db_session: Session) -> None:
        # C-DATA-001: 非公開商品は取得しない。
        published = make_product(db_session, name="公開", publish_status=PublishStatus.PUBLISHED)
        unpublished = make_product(db_session, name="非公開", publish_status=PublishStatus.UNPUBLISHED)
        repo = ProductRepository(db_session)
        assert repo.get_published(published.id) is not None
        assert repo.get_published(unpublished.id) is None

    def test_get_for_update_returns_row(self, db_session: Session) -> None:
        # ADR-007: 在庫行を悲観ロックで取得（SQLite ではロック句は無視されるが行取得は機能する）。
        product = make_product(db_session, name="ロック対象", stock=5)
        repo = ProductRepository(db_session)
        row = repo.get_for_update(product.id)
        assert row is not None
        assert row.id == product.id

    def test_search_in_stock_only(self, db_session: Session) -> None:
        make_product(db_session, name="在庫あり", stock=3)
        make_product(db_session, name="在庫なし", stock=0)
        repo = ProductRepository(db_session)
        rows, total = repo.search(in_stock_only=True)
        assert total == 1
        assert rows[0].name == "在庫あり"


class TestCartConstraint:
    def test_cart_item_unique_per_product(self, db_session: Session) -> None:
        # DM-004: (cart_id, product_id) は一意。
        user = make_user(db_session)
        product = make_product(db_session)
        cart = Cart(user_id=user.id)
        db_session.add(cart)
        db_session.flush()
        db_session.add(CartItem(cart_id=cart.id, product_id=product.id, quantity=1))
        db_session.flush()
        db_session.add(CartItem(cart_id=cart.id, product_id=product.id, quantity=2))
        with pytest.raises(IntegrityError):
            db_session.flush()
        db_session.rollback()

    def test_get_or_create_is_idempotent(self, db_session: Session) -> None:
        user = make_user(db_session)
        repo = CartRepository(db_session)
        cart1 = repo.get_or_create_cart(user.id)
        cart2 = repo.get_or_create_cart(user.id)
        assert cart1.id == cart2.id


class TestOrderRepository:
    def _order(self, user_id: int, number: str, ordered_at: datetime, product_id: int) -> Order:
        order = Order(
            order_number=number,
            user_id=user_id,
            ordered_at=ordered_at,
            shipping_address="住所",
            recipient_name="受取",
            postal_code="150-0001",
            prefecture="東京都",
            city_address="渋谷区1-1-1",
            phone="0312345678",
            payment_method="CREDIT_CARD_MOCK",
            total_amount=1000,
        )
        order.items.append(
            OrderItem(product_id=product_id, product_snapshot_name="商品", unit_price=1000, quantity=1, subtotal=1000)
        )
        return order

    def test_list_by_user_filters_and_orders_desc(self, db_session: Session) -> None:
        # ADR-006: 本人絞り込み。ADR-013: 注文日降順。
        me = make_user(db_session, email="me@example.com")
        other = make_user(db_session, email="other@example.com")
        product = make_product(db_session)
        base = datetime(2026, 1, 1, tzinfo=UTC)
        db_session.add(self._order(me.id, "ORD-OLD", base, product.id))
        db_session.add(self._order(me.id, "ORD-NEW", base + timedelta(days=1), product.id))
        db_session.add(self._order(other.id, "ORD-OTHER", base, product.id))
        db_session.flush()
        repo = OrderRepository(db_session)
        rows, total = repo.list_by_user(me.id)
        assert total == 2
        assert [o.order_number for o in rows] == ["ORD-NEW", "ORD-OLD"]

    def test_order_number_unique_constraint(self, db_session: Session) -> None:
        # DM-005: order_number は一意。
        me = make_user(db_session)
        product = make_product(db_session)
        db_session.add(self._order(me.id, "ORD-DUP", datetime.now(UTC), product.id))
        db_session.flush()
        db_session.add(self._order(me.id, "ORD-DUP", datetime.now(UTC), product.id))
        with pytest.raises(IntegrityError):
            db_session.flush()
        db_session.rollback()


class TestScreeningRepository:
    def test_get_price_returns_configured_price(self, db_session: Session) -> None:
        # ADR-012: 券種ごとの単価を価格設定データから取得。
        movie = make_movie(db_session)
        screening = make_screening(
            db_session, movie_id=movie.id, prices={TicketType.GENERAL: 1900, TicketType.STUDENT: 1500}
        )
        repo = ScreeningRepository(db_session)
        assert repo.get_price(screening.id, TicketType.GENERAL).unit_price == 1900
        assert repo.get_price(screening.id, TicketType.STUDENT).unit_price == 1500

    def test_get_price_missing_returns_none(self, db_session: Session) -> None:
        movie = make_movie(db_session)
        screening = make_screening(db_session, movie_id=movie.id, prices={TicketType.GENERAL: 1900})
        repo = ScreeningRepository(db_session)
        assert repo.get_price(screening.id, TicketType.SENIOR) is None
