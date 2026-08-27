"""CartService の単体テスト（使い捨て in-memory SQLite）。

Requirement: FR-006 / FR-007 / C-DATA-003 / ERR-003 / NFR-SEC-003 / C-AUTH-004
ADR: ADR-006（本人リソース所有チェック）
Criteria: normal-case, boundary-value, exception, security, database
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.constants import PublishStatus
from app.errors import NotFoundError, StockShortageError
from app.schemas.commerce import CartAddInput, CartUpdateInput
from app.services.cart_service import CartService

from .conftest import make_product, make_user


class TestAddToCart:
    def test_add_creates_item(self, db_session: Session) -> None:
        # FR-006: 商品をカートに追加できる。
        user = make_user(db_session)
        product = make_product(db_session, stock=10)
        service = CartService(db_session)
        service.add_to_cart(user.id, CartAddInput(product_id=product.id, quantity=2))
        view = service.get_cart_view(user.id)
        assert len(view.lines) == 1
        assert view.lines[0].quantity == 2

    def test_same_product_quantity_accumulates(self, db_session: Session) -> None:
        # FR-006: 同一商品は数量加算。
        user = make_user(db_session)
        product = make_product(db_session, stock=10)
        service = CartService(db_session)
        service.add_to_cart(user.id, CartAddInput(product_id=product.id, quantity=2))
        service.add_to_cart(user.id, CartAddInput(product_id=product.id, quantity=3))
        view = service.get_cart_view(user.id)
        assert view.lines[0].quantity == 5

    def test_add_up_to_stock_boundary(self, db_session: Session) -> None:
        # 境界: 在庫ちょうどまで追加可能。
        user = make_user(db_session)
        product = make_product(db_session, stock=5)
        service = CartService(db_session)
        service.add_to_cart(user.id, CartAddInput(product_id=product.id, quantity=5))
        assert service.get_cart_view(user.id).lines[0].quantity == 5

    def test_add_over_stock_rejected(self, db_session: Session) -> None:
        # ERR-003: 在庫超過はカート追加を失敗させる。
        user = make_user(db_session)
        product = make_product(db_session, stock=5)
        service = CartService(db_session)
        with pytest.raises(StockShortageError):
            service.add_to_cart(user.id, CartAddInput(product_id=product.id, quantity=6))

    def test_accumulated_over_stock_rejected(self, db_session: Session) -> None:
        # ERR-003: 加算後の合計が在庫超過なら失敗。
        user = make_user(db_session)
        product = make_product(db_session, stock=5)
        service = CartService(db_session)
        service.add_to_cart(user.id, CartAddInput(product_id=product.id, quantity=3))
        with pytest.raises(StockShortageError):
            service.add_to_cart(user.id, CartAddInput(product_id=product.id, quantity=3))

    def test_unpublished_product_not_found(self, db_session: Session) -> None:
        # C-DATA-001 / ERR-004: 非公開商品はカート追加不可。
        user = make_user(db_session)
        product = make_product(db_session, publish_status=PublishStatus.UNPUBLISHED)
        service = CartService(db_session)
        with pytest.raises(NotFoundError):
            service.add_to_cart(user.id, CartAddInput(product_id=product.id, quantity=1))


class TestUpdateItem:
    def test_update_quantity(self, db_session: Session) -> None:
        # FR-007: 数量変更できる。
        user = make_user(db_session)
        product = make_product(db_session, stock=10)
        service = CartService(db_session)
        service.add_to_cart(user.id, CartAddInput(product_id=product.id, quantity=2))
        item_id = service.get_cart_view(user.id).lines[0].item_id
        service.update_item(user.id, item_id, CartUpdateInput(quantity=4))
        assert service.get_cart_view(user.id).lines[0].quantity == 4

    def test_update_quantity_zero_removes_item(self, db_session: Session) -> None:
        # FR-007: 0 は削除扱い。
        user = make_user(db_session)
        product = make_product(db_session, stock=10)
        service = CartService(db_session)
        service.add_to_cart(user.id, CartAddInput(product_id=product.id, quantity=2))
        item_id = service.get_cart_view(user.id).lines[0].item_id
        service.update_item(user.id, item_id, CartUpdateInput(quantity=0))
        # 永続状態を再読込して検証（本番は後続リクエストの新規セッションで再取得される）。
        db_session.expire_all()
        assert service.get_cart_view(user.id).lines == []

    def test_update_over_stock_rejected(self, db_session: Session) -> None:
        # ERR-003: 在庫超過は変更不可。
        user = make_user(db_session)
        product = make_product(db_session, stock=5)
        service = CartService(db_session)
        service.add_to_cart(user.id, CartAddInput(product_id=product.id, quantity=1))
        item_id = service.get_cart_view(user.id).lines[0].item_id
        with pytest.raises(StockShortageError):
            service.update_item(user.id, item_id, CartUpdateInput(quantity=6))

    def test_update_other_users_item_rejected(self, db_session: Session) -> None:
        # NFR-SEC-003 / ADR-006 / C-AUTH-004: 他会員のカート明細は変更できない。
        owner = make_user(db_session, email="owner@example.com")
        attacker = make_user(db_session, email="attacker@example.com")
        product = make_product(db_session, stock=10)
        service = CartService(db_session)
        service.add_to_cart(owner.id, CartAddInput(product_id=product.id, quantity=2))
        item_id = service.get_cart_view(owner.id).lines[0].item_id
        with pytest.raises(NotFoundError):
            service.update_item(attacker.id, item_id, CartUpdateInput(quantity=1))


class TestCartView:
    def test_empty_cart(self, db_session: Session) -> None:
        user = make_user(db_session)
        service = CartService(db_session)
        view = service.get_cart_view(user.id)
        assert view.lines == []
        assert view.total == 0

    def test_total_is_sum_of_subtotals(self, db_session: Session) -> None:
        # C-UI-004 相当: 小計・合計の再計算。
        user = make_user(db_session)
        p1 = make_product(db_session, name="A", price=1000, stock=10)
        p2 = make_product(db_session, name="B", price=500, stock=10)
        service = CartService(db_session)
        service.add_to_cart(user.id, CartAddInput(product_id=p1.id, quantity=2))
        service.add_to_cart(user.id, CartAddInput(product_id=p2.id, quantity=3))
        view = service.get_cart_view(user.id)
        assert view.total == 1000 * 2 + 500 * 3
