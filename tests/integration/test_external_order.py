"""External Integration Test Cases: 商品注文（IT-029〜IT-034, IT-036）。

IT-035（注文更新失敗時のロールバック）は execution_type=NOT_AUTOMATABLE のため
plan には含めず external_case_disposition に記録する（AI 側で rollback を自動検証）。
"""

from __future__ import annotations

from sqlalchemy import select

from app.models.order import Order, OrderItem
from app.models.product import Product
from tests.integration._helpers import (
    add_to_cart,
    login,
    make_product,
    make_user,
    place_order,
)


def _member(session_factory, email="order-member@example.com"):
    with session_factory() as s:
        uid = make_user(s, email=email).id
        s.commit()
        return uid


def _orders(session_factory, user_id):
    with session_factory() as s:
        return list(s.scalars(select(Order).where(Order.user_id == user_id)))


def _cart_empty(session_factory, user_id) -> bool:
    with session_factory() as s:
        from app.repositories.cart_repository import CartRepository

        cart = CartRepository(s).get_cart(user_id)
        return cart is None or not cart.items


# IT-029: 商品注文：単一商品（FR-008 / AC-COM-003 / NFR-USAB-003）
def test_it_029_order_single(client, session_factory):
    uid = _member(session_factory)
    with session_factory() as s:
        pid = make_product(s, name="単一注文商品", price=1500, stock=5).id
        s.commit()
    login(client, "order-member@example.com")
    add_to_cart(client, pid, 1)

    res = place_order(client)
    assert res.status_code == 200

    with session_factory() as s:
        orders = list(s.scalars(select(Order).where(Order.user_id == uid)))
        assert len(orders) == 1
        order = orders[0]
        assert order.order_number.startswith("ORD-")
        assert len(order.items) == 1
        assert order.total_amount == 1500
        assert s.get(Product, pid).stock == 4  # 在庫減算
    assert _cart_empty(session_factory, uid)  # カートクリア


# IT-030: 商品注文：複数商品（FR-008 / AC-COM-003 / C-DATA-004）
def test_it_030_order_multiple_products(client, session_factory):
    uid = _member(session_factory)
    with session_factory() as s:
        pid1 = make_product(s, name="商品甲", price=1000, stock=5).id
        pid2 = make_product(s, name="商品乙", price=2000, stock=5).id
        s.commit()
    login(client, "order-member@example.com")
    add_to_cart(client, pid1, 1)
    add_to_cart(client, pid2, 2)

    place_order(client)
    with session_factory() as s:
        order = s.scalars(select(Order).where(Order.user_id == uid)).one()
        assert len(order.items) == 2
        assert order.total_amount == 1000 + 2000 * 2
        names = {i.product_snapshot_name for i in order.items}
        assert names == {"商品甲", "商品乙"}  # 購入時スナップショット


# IT-031: 商品注文：同一商品複数量（FR-008 / AC-COM-003）
def test_it_031_order_same_product_multiple_quantity(client, session_factory):
    uid = _member(session_factory)
    with session_factory() as s:
        pid = make_product(s, name="複数量商品", price=800, stock=10).id
        s.commit()
    login(client, "order-member@example.com")
    add_to_cart(client, pid, 3)

    place_order(client)
    with session_factory() as s:
        order = s.scalars(select(Order).where(Order.user_id == uid)).one()
        item = order.items[0]
        assert item.quantity == 3
        assert item.subtotal == 2400
        assert order.total_amount == 2400
        assert s.get(Product, pid).stock == 7  # 指定数量分だけ減算


# IT-032: 注文：配送先入力不備（FR-008 / ERR-001 / NFR-SEC-004 / AC-COM-006）
def test_it_032_order_invalid_shipping(client, session_factory):
    uid = _member(session_factory)
    with session_factory() as s:
        pid = make_product(s, name="配送不備商品", stock=5).id
        s.commit()
    login(client, "order-member@example.com")
    add_to_cart(client, pid, 1)

    res = place_order(
        client,
        postal_code="abc",  # 形式不正
        phone="not-a-phone",
        recipient_name="",  # 必須未入力
        follow_redirects=False,
    )
    assert res.status_code == 400
    assert _orders(session_factory, uid) == []  # 注文は確定しない


# IT-033: 注文確定直前の在庫不足（FR-008 / ERR-003 / NFR-AVL-001）
def test_it_033_order_stock_shortage_at_confirm(client, session_factory):
    uid = _member(session_factory)
    with session_factory() as s:
        pid = make_product(s, name="直前在庫不足商品", stock=5).id
        s.commit()
    login(client, "order-member@example.com")
    add_to_cart(client, pid, 3)

    # カート投入後に在庫を不足状態へ変更
    with session_factory() as s:
        s.get(Product, pid).stock = 1
        s.commit()

    res = place_order(client, follow_redirects=False)
    assert res.status_code == 409  # 在庫不足で失敗
    assert _orders(session_factory, uid) == []
    with session_factory() as s:
        assert s.get(Product, pid).stock == 1  # 不整合が残らない（減算されない）


# IT-034: 注文登録と在庫減算の原子性（FR-008 / NFR-AVL-001）
def test_it_034_order_atomicity(client, session_factory):
    uid = _member(session_factory)
    with session_factory() as s:
        pid = make_product(s, name="原子性商品", price=1200, stock=5).id
        s.commit()
    login(client, "order-member@example.com")
    add_to_cart(client, pid, 2)

    place_order(client)
    with session_factory() as s:
        order = s.scalars(select(Order).where(Order.user_id == uid)).one()
        product = s.get(Product, pid)
        # 注文登録と在庫減算が整合した一つの結果として完了
        assert order.total_amount == 2400
        assert product.stock == 3


# IT-036: 注文後の商品変更とスナップショット（FR-008 / C-DATA-004 / ADR-008）
def test_it_036_order_snapshot_immutable(client, session_factory):
    uid = _member(session_factory)
    with session_factory() as s:
        pid = make_product(s, name="旧商品名", price=1000, stock=5).id
        s.commit()
    login(client, "order-member@example.com")
    add_to_cart(client, pid, 1)
    place_order(client)

    # 注文後に元商品の名称・価格を変更
    with session_factory() as s:
        product = s.get(Product, pid)
        product.name = "新商品名"
        product.price_tax_included = 9999
        s.commit()

    history = client.get("/history")
    assert "旧商品名" in history.text  # 購入時点スナップショット
    assert "新商品名" not in history.text
    with session_factory() as s:
        item = s.scalars(select(OrderItem)).one()
        assert item.product_snapshot_name == "旧商品名"
        assert item.unit_price == 1000
