"""External Integration Test Cases: カート（IT-021〜IT-028）。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models.cart import CartItem
from app.models.order import Order
from app.models.product import Product
from tests.integration._helpers import (
    add_to_cart,
    cart_item_id_of,
    login,
    make_product,
    make_user,
    place_order,
    update_cart_item,
)

UTC = timezone.utc


def _member(session_factory, email="cart-member@example.com"):
    with session_factory() as s:
        user = make_user(s, email=email)
        s.commit()
        return user.id


def _cart_items(session_factory, user_id):
    with session_factory() as s:
        from app.repositories.cart_repository import CartRepository

        cart = CartRepository(s).get_cart(user_id)
        if cart is None:
            return []
        return [(i.product_id, i.quantity) for i in cart.items]


# IT-021: カート追加：正常（FR-006 / C-AUTH-002）
def test_it_021_cart_add_success(client, session_factory):
    uid = _member(session_factory)
    with session_factory() as s:
        pid = make_product(s, name="カート商品", stock=10).id
        s.commit()
    login(client, "cart-member@example.com")

    res = add_to_cart(client, pid, 2)
    assert res.status_code == 200
    assert _cart_items(session_factory, uid) == [(pid, 2)]
    assert "カート商品" in client.get("/cart").text


# IT-022: カート追加：同一商品（FR-006）
def test_it_022_cart_add_merge(client, session_factory):
    uid = _member(session_factory)
    with session_factory() as s:
        pid = make_product(s, name="加算商品", stock=10).id
        s.commit()
    login(client, "cart-member@example.com")

    add_to_cart(client, pid, 2)
    add_to_cart(client, pid, 3)
    items = _cart_items(session_factory, uid)
    assert items == [(pid, 5)]  # 別明細を作らず数量加算


# IT-023: カート追加時は在庫減算しない（FR-006 / NFR-AVL-001）
def test_it_023_cart_add_no_stock_decrement(client, session_factory):
    _member(session_factory)
    with session_factory() as s:
        pid = make_product(s, name="在庫維持商品", stock=7).id
        s.commit()
    login(client, "cart-member@example.com")

    add_to_cart(client, pid, 3)
    with session_factory() as s:
        product = s.get(Product, pid)
        assert product.stock == 7  # カート追加では在庫が減らない


# IT-024: カート追加：在庫超過（FR-006 / ERR-003 / AC-COM-006）
def test_it_024_cart_add_stock_shortage(client, session_factory):
    uid = _member(session_factory)
    with session_factory() as s:
        pid = make_product(s, name="少在庫商品", stock=2).id
        s.commit()
    login(client, "cart-member@example.com")

    res = add_to_cart(client, pid, 5, follow_redirects=False)
    assert res.status_code == 409  # 在庫不足で失敗
    assert _cart_items(session_factory, uid) == []


# IT-025: カート数量変更（FR-007）
def test_it_025_cart_update_quantity(client, session_factory):
    uid = _member(session_factory)
    with session_factory() as s:
        pid = make_product(s, name="数量変更商品", price=1000, stock=10).id
        s.commit()
    login(client, "cart-member@example.com")
    add_to_cart(client, pid, 1)

    with session_factory() as s:
        item_id = cart_item_id_of(s, uid, pid)
    res = update_cart_item(client, item_id, 4)
    assert res.status_code == 200
    assert _cart_items(session_factory, uid) == [(pid, 4)]
    assert "4,000円" in client.get("/cart").text  # 小計・合計が再計算


# IT-026: カート数量0（FR-007）
def test_it_026_cart_update_zero_removes(client, session_factory):
    uid = _member(session_factory)
    with session_factory() as s:
        pid = make_product(s, name="削除対象商品", stock=10).id
        s.commit()
    login(client, "cart-member@example.com")
    add_to_cart(client, pid, 2)

    with session_factory() as s:
        item_id = cart_item_id_of(s, uid, pid)
    update_cart_item(client, item_id, 0)
    assert _cart_items(session_factory, uid) == []  # 0は削除扱い


# IT-027: カート更新：在庫超過（FR-007 / ERR-003）
def test_it_027_cart_update_stock_shortage(client, session_factory):
    uid = _member(session_factory)
    with session_factory() as s:
        pid = make_product(s, name="更新超過商品", stock=3).id
        s.commit()
    login(client, "cart-member@example.com")
    add_to_cart(client, pid, 1)

    with session_factory() as s:
        item_id = cart_item_id_of(s, uid, pid)
    res = update_cart_item(client, item_id, 10, follow_redirects=False)
    assert res.status_code == 409
    assert _cart_items(session_factory, uid) == [(pid, 1)]  # 不正数量は保存されない


# IT-028: カート内商品が注文不可へ変化（FR-007 / C-DATA-002）
def test_it_028_cart_item_becomes_unorderable(client, session_factory):
    uid = _member(session_factory)
    now = datetime.now(UTC)
    with session_factory() as s:
        pid = make_product(s, name="期間内商品", stock=10).id
        s.commit()
    login(client, "cart-member@example.com")
    add_to_cart(client, pid, 1)

    # カート投入後に販売期間外へ変化させる
    with session_factory() as s:
        product = s.get(Product, pid)
        product.sales_end_at = now - timedelta(days=1)
        s.commit()

    res = place_order(client, follow_redirects=False)
    assert res.status_code == 409  # 注文手続きへ進めない（販売期間外）
    with session_factory() as s:
        assert list(s.scalars(select(Order).where(Order.user_id == uid))) == []
