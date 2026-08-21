"""リポジトリ層 単体テスト (DB固有動作)。

対象: app/repositories/*
検証Requirement:
- DM-001 (email一意制約), DM-004 (cart_id+product_id一意制約)
- C-DATA-001 (可視フィルタ: 公開のみ)
- ADR-005 (所有者スコープ get_owned)
- FR-010 (本人分ページング)
DB Strategy: CONTAINER (使い捨てSQLite。SQL/制約/マッピングを実DBで検証)。
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.cart import Cart, CartItem
from app.models.product import Product
from app.models.user import User
from app.payment import PaymentGateway
from app.repositories.cart_repository import CartRepository
from app.repositories.order_repository import OrderRepository
from app.repositories.product_repository import ProductRepository
from app.repositories.ticket_repository import TicketRepository
from app.repositories.user_repository import UserRepository
from app.schemas.commerce import AddToCartInput, OrderInput, TicketPurchaseInput
from app.services.cart_service import CartService
from app.services.order_service import OrderService
from app.services.ticket_service import TicketService


class TestUserRepository:
    # DM-001: email は一意。重複INSERTは制約違反
    def test_email_unique_constraint(
        self, db: Session, make_user: Callable[..., User]
    ) -> None:
        make_user(email="unique@example.com")
        db.add(User(name="別人", email="unique@example.com", password_hash="x"))
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()

    # 正常系: メールでユーザーを取得できる
    def test_get_by_email(self, db: Session, make_user: Callable[..., User]) -> None:
        make_user(email="find@example.com")
        repo = UserRepository(db)
        assert repo.get_by_email("find@example.com") is not None
        assert repo.exists_email("find@example.com") is True
        assert repo.get_by_email("nobody@example.com") is None
        assert repo.exists_email("nobody@example.com") is False


class TestProductRepository:
    # C-DATA-001: get_visible は非公開商品を返さない
    def test_get_visible_excludes_unpublished(
        self, db: Session, make_product: Callable[..., Product]
    ) -> None:
        published = make_product(publish_status="published")
        unpublished = make_product(publish_status="unpublished")
        repo = ProductRepository(db)
        assert repo.get_visible(published.id) is not None
        assert repo.get_visible(unpublished.id) is None

    # ADR-007: get_for_update は対象行を取得する (悲観ロック取得)
    def test_get_for_update_returns_row(
        self, db: Session, make_product: Callable[..., Product]
    ) -> None:
        product = make_product()
        got = ProductRepository(db).get_for_update(product.id)
        assert got is not None and got.id == product.id


class TestCartConstraint:
    # DM-004: 同一カート内で同一商品の重複行は許可されない
    def test_cart_item_unique(
        self,
        db: Session,
        make_user: Callable[..., User],
        make_product: Callable[..., Product],
    ) -> None:
        user = make_user()
        product = make_product()
        cart = Cart(user_id=user.id)
        db.add(cart)
        db.flush()
        db.add(CartItem(cart_id=cart.id, product_id=product.id, quantity=1))
        db.flush()
        db.add(CartItem(cart_id=cart.id, product_id=product.id, quantity=2))
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()

    # 正常系: get_or_create_by_user は初回にカートを作成し再取得で同一を返す
    def test_get_or_create_cart(
        self, db: Session, make_user: Callable[..., User]
    ) -> None:
        user = make_user()
        repo = CartRepository(db)
        cart1 = repo.get_or_create_by_user(user.id)
        cart2 = repo.get_or_create_by_user(user.id)
        assert cart1.id == cart2.id


class TestOrderTicketRepository:
    # FR-010 / ADR-005: 注文は本人分のみ取得。注文番号存在判定と所有者スコープ。
    def test_order_list_and_number(
        self,
        db: Session,
        payment: PaymentGateway,
        make_user: Callable[..., User],
        make_product: Callable[..., Product],
    ) -> None:
        user = make_user()
        product = make_product(stock=100)
        CartService(db).add(user.id, AddToCartInput(product_id=product.id, quantity=1))
        order = OrderService(db, payment).place_order(
            user.id,
            OrderInput(
                name="山田太郎",
                postal_code="150-0001",
                prefecture="東京都",
                address_line="渋谷区1-2-3",
                phone="03-1234-5678",
                payment_method="mock_credit_card",
            ),
        )
        repo = OrderRepository(db)
        rows, total = repo.list_by_user(user.id, limit=20, offset=0)
        assert total == 1 and len(rows) == 1
        assert repo.exists_order_number(order.order_number) is True
        assert repo.exists_order_number("ORD-UNKNOWN") is False
        assert repo.get_owned(order.id, user.id) is not None
        assert repo.get_owned(order.id, user.id + 999) is None

    # FR-010: チケット購入は本人分のみ取得。購入番号存在判定。
    def test_ticket_list_and_number(
        self,
        db: Session,
        payment: PaymentGateway,
        make_user: Callable[..., User],
        make_screening: Callable[..., object],
    ) -> None:
        user = make_user()
        screening = make_screening(seats_remaining=10)
        purchase = TicketService(db, payment).purchase(
            user.id,
            TicketPurchaseInput(
                screening_id=screening.id,
                ticket_type="general",
                quantity=1,
                payment_method="mock_credit_card",
            ),
        )
        repo = TicketRepository(db)
        rows, total = repo.list_by_user(user.id, limit=20, offset=0)
        assert total == 1 and len(rows) == 1
        assert repo.exists_purchase_number(purchase.purchase_number) is True
        assert repo.exists_purchase_number("TKT-UNKNOWN") is False
