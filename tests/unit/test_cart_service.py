"""カートサービス単体テスト (FR-006 / FR-007)。

対象: app/services/cart_service.py
検証Requirement:
- FR-006 カート追加 (在庫超過不可 ERR-003, 販売期間外/非公開不可 ERR-004,
  カート投入時は在庫非減算, 同一商品は数量加算)
- FR-007 カート変更 (0は削除, 在庫超過不可)
- ADR-005 / C-AUTH-004 / NFR-SEC-003 (本人カートのみ操作可)
DB Strategy: CONTAINER (使い捨てSQLite。カート永続と在庫参照を伴う)。
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from app.errors import NotSaleableError, OutOfStockError, ValidationError
from app.models.product import Product
from app.models.user import User
from app.repositories.cart_repository import CartRepository
from app.schemas.commerce import AddToCartInput
from app.services.cart_service import CartService


class TestAddToCart:
    # FR-006 正常系: カートに商品が追加される
    def test_add_creates_item(
        self, db: Session, make_user: Callable[..., User], make_product: Callable[..., Product]
    ) -> None:
        user = make_user()
        product = make_product(stock=10)
        service = CartService(db)
        service.add(user.id, AddToCartInput(product_id=product.id, quantity=3))

        view = service.view(user.id)
        assert len(view.lines) == 1
        assert view.lines[0].item.quantity == 3

    # FR-006 業務ルール: カート投入時に在庫(Product.stock)を減算しない
    def test_add_does_not_decrement_stock(
        self, db: Session, make_user: Callable[..., User], make_product: Callable[..., Product]
    ) -> None:
        user = make_user()
        product = make_product(stock=10)
        service = CartService(db)
        service.add(user.id, AddToCartInput(product_id=product.id, quantity=3))

        db.refresh(product)
        assert product.stock == 10  # 減算されていない

    # FR-006: 同一商品を再追加すると数量が加算される
    def test_add_same_product_accumulates(
        self, db: Session, make_user: Callable[..., User], make_product: Callable[..., Product]
    ) -> None:
        user = make_user()
        product = make_product(stock=10)
        service = CartService(db)
        service.add(user.id, AddToCartInput(product_id=product.id, quantity=2))
        service.add(user.id, AddToCartInput(product_id=product.id, quantity=3))

        view = service.view(user.id)
        assert len(view.lines) == 1
        assert view.lines[0].item.quantity == 5

    # ERR-003 / C-DATA-003 境界: 在庫ちょうどまでは追加可
    def test_add_up_to_stock_boundary(
        self, db: Session, make_user: Callable[..., User], make_product: Callable[..., Product]
    ) -> None:
        user = make_user()
        product = make_product(stock=5)
        service = CartService(db)
        service.add(user.id, AddToCartInput(product_id=product.id, quantity=5))  # 上限=在庫OK
        assert service.view(user.id).lines[0].item.quantity == 5

    # ERR-003: 在庫超過は追加不可
    def test_add_over_stock_rejected(
        self, db: Session, make_user: Callable[..., User], make_product: Callable[..., Product]
    ) -> None:
        user = make_user()
        product = make_product(stock=5)
        service = CartService(db)
        with pytest.raises(OutOfStockError):
            service.add(user.id, AddToCartInput(product_id=product.id, quantity=6))

    # ERR-003 / C-DATA-003: 在庫0は追加不可
    def test_add_out_of_stock_rejected(
        self, db: Session, make_user: Callable[..., User], make_product: Callable[..., Product]
    ) -> None:
        user = make_user()
        product = make_product(stock=0)
        service = CartService(db)
        with pytest.raises(OutOfStockError):
            service.add(user.id, AddToCartInput(product_id=product.id, quantity=1))

    # ERR-004 / C-DATA-001: 非公開商品は追加不可
    def test_add_unpublished_rejected(
        self, db: Session, make_user: Callable[..., User], make_product: Callable[..., Product]
    ) -> None:
        user = make_user()
        product = make_product(stock=10, publish_status="unpublished")
        service = CartService(db)
        with pytest.raises(NotSaleableError):
            service.add(user.id, AddToCartInput(product_id=product.id, quantity=1))

    # ERR-004 / C-DATA-002: 販売期間外(販売開始前)は追加不可
    def test_add_before_sales_start_rejected(
        self, db: Session, make_user: Callable[..., User], make_product: Callable[..., Product]
    ) -> None:
        user = make_user()
        future = datetime.now(timezone.utc) + timedelta(days=1)
        product = make_product(stock=10, sales_start_at=future)
        service = CartService(db)
        with pytest.raises(NotSaleableError):
            service.add(user.id, AddToCartInput(product_id=product.id, quantity=1))


class TestUpdateCart:
    # FR-007: 数量0は削除扱い
    def test_update_zero_deletes_item(
        self, db: Session, make_user: Callable[..., User], make_product: Callable[..., Product]
    ) -> None:
        user = make_user()
        product = make_product(stock=10)
        service = CartService(db)
        service.add(user.id, AddToCartInput(product_id=product.id, quantity=2))
        item_id = service.view(user.id).lines[0].item.id

        service.update_item(user.id, item_id, 0)
        db.expire_all()  # コミット済みDB状態を再取得 (本番はリクエスト毎に新セッション)
        assert service.view(user.id).lines == []

    # FR-007 正常系: 数量変更で小計が再計算される
    def test_update_changes_quantity(
        self, db: Session, make_user: Callable[..., User], make_product: Callable[..., Product]
    ) -> None:
        user = make_user()
        product = make_product(stock=10, price=1000)
        service = CartService(db)
        service.add(user.id, AddToCartInput(product_id=product.id, quantity=2))
        item_id = service.view(user.id).lines[0].item.id

        service.update_item(user.id, item_id, 4)
        view = service.view(user.id)
        assert view.lines[0].item.quantity == 4
        assert view.lines[0].subtotal == 4000
        assert view.total == 4000

    # FR-007 / ERR-003: 在庫超過への変更は不可
    def test_update_over_stock_rejected(
        self, db: Session, make_user: Callable[..., User], make_product: Callable[..., Product]
    ) -> None:
        user = make_user()
        product = make_product(stock=5)
        service = CartService(db)
        service.add(user.id, AddToCartInput(product_id=product.id, quantity=2))
        item_id = service.view(user.id).lines[0].item.id
        with pytest.raises(OutOfStockError):
            service.update_item(user.id, item_id, 6)

    # ADR-005 / NFR-SEC-003: 他会員のカート項目は操作不可
    def test_update_other_users_item_rejected(
        self, db: Session, make_user: Callable[..., User], make_product: Callable[..., Product]
    ) -> None:
        owner = make_user(email="owner@example.com")
        attacker = make_user(email="attacker@example.com")
        product = make_product(stock=10)
        service = CartService(db)
        service.add(owner.id, AddToCartInput(product_id=product.id, quantity=2))
        owner_item_id = service.view(owner.id).lines[0].item.id

        # 攻撃者が他人のカート項目IDを直接指定 (IDOR)
        with pytest.raises(ValidationError):
            service.update_item(attacker.id, owner_item_id, 1)

        # 所有者のカート項目は改変されていない
        cart = CartRepository(db).get_or_create_by_user(owner.id)
        item = CartRepository(db).get_item(cart.id, product.id)
        assert item is not None and item.quantity == 2


class TestCartView:
    # FR-007: 販売不可商品を含む場合は has_unorderable=True
    def test_view_flags_unorderable(
        self, db: Session, make_user: Callable[..., User], make_product: Callable[..., Product]
    ) -> None:
        user = make_user()
        product = make_product(stock=10)
        service = CartService(db)
        service.add(user.id, AddToCartInput(product_id=product.id, quantity=2))

        # 追加後に販売停止 (非公開化)
        product.publish_status = "unpublished"
        db.commit()

        view = service.view(user.id)
        assert view.has_unorderable is True
