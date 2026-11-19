# trace: FR-026, FR-030, FR-031, FR-032, FR-033, FR-034, NFR-SC-10, ADDR-001, ADDR-004, ADDR-005, ADDR-007
# trace: ADDR-008, ADDR-011, ADDR-013
"""結合試験：注文確定・支払・注文照会・購入者キャンセル（Web API→業務処理→決済（模擬）→DB）。

IT-023〜IT-032（AI INITIAL）。期待結果は FR-026・FR-030〜FR-034、CMN-18〜CMN-26、8.1 状態遷移、MSG-04、
ADDR-001（電文・エラー）・ADDR-004（トランザクション・ロック）・ADDR-005（注文番号）・ADDR-008（決済要求）・
ADDR-011（試験用状態）・ADDR-013（LOG-02）から導出する。
"""

import re
import time
from datetime import timedelta

import pytest

from tests.integration._helpers import ADDRESS, add_item, api, body, error_of, field_names, jst, order_of, pay, place

pytestmark = pytest.mark.django_db

ORDER_NUMBER = re.compile(r"^PO-\d{8}$")
TRANSACTION_REF = re.compile(r"^MOCK-[A-Za-z0-9]{16}$")
INTERNALS = ("Traceback", "Exception", "SELECT", "INSERT", "UPDATE ", ".py", "psycopg", "django", "File ")


# trace: FR-030, FR-031, ADDR-004
def _stock(unit):
    from catalog.models import StockUnit

    return StockUnit.objects.get(pk=unit.pk).stock_quantity


# trace: FR-030, FR-026, ADDR-001, ADDR-004, ADDR-005
def test_it_023_place_order_persistence(api_client, buyer, other_buyer, bearer, catalog):
    """IT-023 注文確定の DB 連携（在庫引当・注文・明細・配送先・履歴・カート・注文番号）。"""
    from carts.models import Cart
    from orders.models import Order, OrderItem, OrderStatusHistory, ShippingAddress

    a = catalog.stock_unit(catalog.product("マグ"), price=1200, stock=5, variant_name="白")
    b = catalog.stock_unit(catalog.product("皿"), price=800, stock=3, variant_name="青")
    token = bearer(buyer)
    assert add_item(api_client, token, b.pk, 1).status_code == 200
    assert add_item(api_client, token, a.pk, 2).status_code == 200
    cart_id = Cart.objects.get(buyer=buyer, status="active").pk
    address = {
        "recipient_name": "  山田 花子 ",
        "postal_code": "123-4567",
        "prefecture": "13",
        "address_line1": " 千代田区1-1 ",
        "address_line2": "",
        "phone_number": "03-1234-5678",
    }
    response = place(api_client, token, address)
    assert response.status_code == 201, response.content
    data = body(response)
    assert data["status"] == "accepted" and ORDER_NUMBER.match(data["order_number"])
    assert data["amounts"] == {
        "subtotal": 3200,
        "discount_amount": 0,
        "discounted_subtotal": 3200,
        "shipping_fee": 500,
        "tax_amount": 370,
        "total_amount": 4070,
    }
    assert [i["stock_unit_id"] for i in data["items"]] == [b.pk, a.pk]
    assert data["paid_at"] is None and data["shipped_at"] is None and data["tracking_number"] is None

    order = Order.objects.get(pk=data["order_id"])
    assert order.buyer_id == buyer.pk and order.status == "accepted" and order.total_amount == 4070
    assert _stock(a) == 3 and _stock(b) == 2
    items = list(OrderItem.objects.filter(order=order).order_by("pk"))
    assert [
        (i.stock_unit_id, i.sku, i.product_name, i.variant_name, i.unit_price, i.quantity, i.line_amount) for i in items
    ] == [(b.pk, b.sku, "皿", "青", 800, 1, 800), (a.pk, a.sku, "マグ", "白", 1200, 2, 2400)]
    assert sum(i.line_amount for i in items) == order.subtotal
    address_row = ShippingAddress.objects.get(order=order)
    assert (
        address_row.recipient_name,
        address_row.postal_code,
        address_row.prefecture,
        address_row.address_line1,
        address_row.address_line2,
        address_row.phone_number,
    ) == ("山田 花子", "1234567", "13", "千代田区1-1", None, "0312345678")
    history = list(OrderStatusHistory.objects.filter(order=order))
    assert len(history) == 1
    assert (history[0].from_status, history[0].to_status, history[0].actor_id, history[0].actor_user_type) == (
        None,
        "accepted",
        buyer.pk,
        "buyer",
    )
    assert history[0].changed_at == order.ordered_at
    cart = Cart.objects.get(pk=cart_id)
    assert cart.status == "ordered" and cart.ordered_at == order.ordered_at
    assert not Cart.objects.filter(buyer=buyer, status="active").exists()

    second = order_of(api_client, bearer(other_buyer), [(a, 1)])
    assert int(second["order_number"][3:]) > int(data["order_number"][3:])


# trace: FR-030, ADDR-001
def test_it_024_place_order_input_errors(api_client, buyer, bearer, catalog):
    """IT-024 注文確定の配送先入力エラー（全項目）と無変更。"""
    from carts.models import CartItem
    from orders.models import Order

    unit = catalog.stock_unit(stock=5)
    token = bearer(buyer)
    add_item(api_client, token, unit.pk, 2)
    bad = {
        "recipient_name": "   ",
        "postal_code": "12-34567",
        "prefecture": "48",
        "address_line1": "あ" * 101,
        "address_line2": "",
        "phone_number": "031234567",
    }
    response = place(api_client, token, bad)
    assert response.status_code == 400
    assert error_of(response)["type"] == "input_error"
    assert {
        "shipping_address.recipient_name",
        "shipping_address.postal_code",
        "shipping_address.prefecture",
        "shipping_address.address_line1",
        "shipping_address.phone_number",
    } <= field_names(response)
    assert Order.objects.count() == 0 and _stock(unit) == 5
    assert list(CartItem.objects.filter(cart__buyer=buyer).values_list("quantity", flat=True)) == [2]


# trace: FR-030, ADDR-004, ADDR-011
def test_it_025_place_order_business_error_order_no_change(
    api_client, buyer, other_buyer, bearer, catalog, make_coupon, set_state
):
    """IT-025 注文確定の業務エラー判定順序（非公開→クーポン→在庫）と無変更。"""
    from carts.models import Cart, CartItem
    from catalog.models import Product
    from orders.models import Order
    from promotions.models import Coupon

    coupon = make_coupon(
        "APRIL-100", discount_value=100, valid_from=jst(2027, 4, 1), valid_to=jst(2027, 4, 10, 23, 59, 59)
    )
    p = catalog.stock_unit(catalog.product("非公開化"), stock=10)
    q = catalog.stock_unit(stock=3)
    r = catalog.stock_unit(stock=1)
    set_state(fixed_now=jst(2027, 4, 5, 10, 0, 0))
    token, other = bearer(buyer), bearer(other_buyer)
    for unit, quantity in ((p, 1), (q, 2), (r, 1)):
        assert add_item(api_client, token, unit.pk, quantity).status_code == 200
    assert api(api_client, "post", "/api/cart/coupon/", token, {"coupon_code": "APRIL-100"}).status_code == 200
    order_of(api_client, other, [(q, 2), (r, 1)])
    assert _stock(q) == 1 and _stock(r) == 0
    Product.objects.filter(pk=p.product_id).update(is_public=False)

    set_state(fixed_now=jst(2027, 4, 20, 12, 0, 0))
    token = bearer(buyer)

    def unchanged():
        assert Order.objects.filter(buyer=buyer).count() == 0
        assert (_stock(p), _stock(q), _stock(r)) == (10, 1, 0)
        cart = Cart.objects.get(buyer=buyer, status="active")
        assert cart.coupon_id == coupon.pk
        assert list(
            CartItem.objects.filter(cart=cart).order_by("added_at", "pk").values_list("stock_unit_id", "quantity")
        ) == [(p.pk, 1), (q.pk, 2), (r.pk, 1)]

    first = place(api_client, token)
    assert first.status_code == 422 and error_of(first)["reason"] == "unavailable_product"
    assert error_of(first)["values"]["unavailable_stock_unit_ids"] == [p.pk]
    unchanged()

    Product.objects.filter(pk=p.product_id).update(is_public=True)
    second = place(api_client, token)
    assert second.status_code == 422 and error_of(second)["reason"] == "coupon_expired"
    assert error_of(second)["values"]["valid_from"] == "2027-04-01T00:00:00+09:00"
    assert error_of(second)["values"]["valid_to"] == "2027-04-10T23:59:59+09:00"
    unchanged()

    Coupon.objects.filter(pk=coupon.pk).update(valid_to=jst(2027, 4, 30, 23, 59, 59))
    third = place(api_client, token)
    assert third.status_code == 422 and error_of(third)["reason"] == "insufficient_stock"
    assert error_of(third)["values"]["stock_units"] == [
        {"stock_unit_id": q.pk, "sku": q.sku, "requested_quantity": 2, "stock_quantity": 1},
        {"stock_unit_id": r.pk, "sku": r.sku, "requested_quantity": 1, "stock_quantity": 0},
    ]
    unchanged()


# trace: FR-030, ADDR-004
def test_it_026_place_order_empty_cart_and_resend(api_client, buyer, bearer, catalog):
    """IT-026 空カートの注文確定と同一カートの再送信。"""
    from orders.models import Order

    unit = catalog.stock_unit(stock=5)
    token = bearer(buyer)
    add_item(api_client, token, unit.pk, 1)
    assert place(api_client, token).status_code == 201
    again = place(api_client, token)
    assert again.status_code == 422
    err = error_of(again)
    assert err["type"] == "business_error" and err["reason"] == "cart_empty"
    assert Order.objects.filter(buyer=buyer).count() == 1 and _stock(unit) == 4

    invalid = place(api_client, token, {**ADDRESS, "postal_code": "abc"})
    assert invalid.status_code == 400 and error_of(invalid)["type"] == "input_error"


# trace: FR-030, NFR-SC-10, ADDR-004, ADDR-011, ADDR-013
def test_it_027_place_order_fault_rollback(api_client, buyer, bearer, catalog, set_state, app_logs):
    """IT-027 注文確定途中のシステム障害で全取消し（障害注入点）。"""
    from carts.models import Cart, CartItem
    from orders.models import Order, OrderItem, OrderStatusHistory, ShippingAddress

    unit = catalog.stock_unit(stock=5)
    token = bearer(buyer)
    add_item(api_client, token, unit.pk, 2)
    cart = Cart.objects.get(buyer=buyer, status="active")
    for point in ("after_stock_decrement", "after_order_insert"):
        set_state(order_fault_point=point)
        response = place(api_client, token)
        assert response.status_code == 500, point
        err = error_of(response)
        assert err["type"] == "system_error" and err["fields"] == [] and err["values"] == {}
        raw = response.content.decode("utf-8")
        assert not any(word in raw for word in INTERNALS), raw
        assert _stock(unit) == 5
        assert Order.objects.count() == 0 and OrderItem.objects.count() == 0
        assert ShippingAddress.objects.count() == 0 and OrderStatusHistory.objects.count() == 0
        cart.refresh_from_db()
        assert cart.status == "active" and cart.ordered_at is None
        assert list(CartItem.objects.filter(cart=cart).values_list("quantity", flat=True)) == [2]
    errors = [r for r in app_logs.records() if r["log_type"] == "LOG-02"]
    assert len(errors) >= 2 and all(r.get("error_type") == "system_error" for r in errors)

    set_state(order_fault_point="none")
    assert place(api_client, token).status_code == 201


# trace: FR-031, ADDR-008, ADDR-004, ADDR-007
def test_it_028_payment_approve_decline_retry(api_client, buyer, bearer, catalog):
    """IT-028 支払（模擬決済）の承認・否認・再支払。"""
    from orders.models import Order, OrderStatusHistory, PaymentRecord

    unit = catalog.stock_unit(price=2000, stock=10)
    token = bearer(buyer)
    first = order_of(api_client, token, [(unit, 1)])
    second = order_of(api_client, token, [(unit, 2)])
    assert _stock(unit) == 7

    declined = pay(api_client, token, first["order_id"], "declined")
    assert declined.status_code == 422
    assert error_of(declined)["type"] == "business_error" and error_of(declined)["reason"] == "payment_declined"
    order = Order.objects.get(pk=first["order_id"])
    assert order.status == "accepted" and order.paid_at is None
    records = list(PaymentRecord.objects.filter(order=order))
    assert [(p.result, p.transaction_ref, p.amount) for p in records] == [("declined", None, order.total_amount)]

    approved = pay(api_client, token, first["order_id"])
    assert approved.status_code == 200
    data = body(approved)
    assert data["status"] == "paid" and data["paid_at"] is not None
    assert "payments" not in data and "MOCK-" not in approved.content.decode("utf-8")
    assert body(pay(api_client, token, second["order_id"], "approved"))["status"] == "paid"

    order.refresh_from_db()
    assert order.status == "paid" and order.paid_at is not None
    records = list(PaymentRecord.objects.filter(order=order).order_by("pk"))
    assert [p.result for p in records] == ["declined", "approved"]
    assert TRANSACTION_REF.match(records[1].transaction_ref) and records[1].amount == order.total_amount
    paid = OrderStatusHistory.objects.filter(order=order, to_status="paid").get()
    assert (paid.from_status, paid.actor_id, paid.actor_user_type) == ("accepted", buyer.pk, "buyer")
    assert paid.changed_at == order.paid_at
    assert _stock(unit) == 7


# trace: FR-031, ADDR-008, ADDR-011, ADDR-013
def test_it_029_payment_integration_errors(api_client, buyer, bearer, catalog, set_state, app_logs):
    """IT-029 支払の連携エラー（10秒超過・応答不正）。"""
    from orders.models import Order, OrderStatusHistory, PaymentRecord

    unit = catalog.stock_unit(stock=10)
    token = bearer(buyer)
    order = order_of(api_client, token, [(unit, 1)])
    order_id = order["order_id"]

    set_state(payment_delay_seconds=10.5, payment_mode="normal")
    started = time.monotonic()
    slow = pay(api_client, token, order_id)
    elapsed = time.monotonic() - started
    assert slow.status_code == 502
    assert error_of(slow)["type"] == "integration_error"
    assert 9.5 <= elapsed < 10.5 + 5

    set_state(payment_delay_seconds=0)
    modes = ("invalid_result", "missing_transaction_ref", "invalid_transaction_ref", "connection_error")
    for mode in modes:
        set_state(payment_mode=mode)
        response = pay(api_client, token, order_id)
        assert response.status_code == 502, mode
        assert error_of(response)["type"] == "integration_error"

    row = Order.objects.get(pk=order_id)
    assert row.status == "accepted" and row.paid_at is None
    records = list(PaymentRecord.objects.filter(order_id=order_id))
    assert len(records) == 1 + len(modes)
    assert all(r.result == "integration_error" and r.transaction_ref is None for r in records)
    assert OrderStatusHistory.objects.filter(order_id=order_id).count() == 1
    assert any(r["log_type"] == "LOG-02" and r.get("error_type") == "integration_error" for r in app_logs.records())

    set_state(payment_mode="normal")
    assert body(pay(api_client, token, order_id))["status"] == "paid"


# trace: FR-031, ADDR-001, ADDR-004
def test_it_030_payment_invalid_status_ownership_permission(api_client, buyer, other_buyer, admin, bearer, catalog):
    """IT-030 支払の状態不正・所有・権限・入力の判定順序。"""
    from orders.models import PaymentRecord

    unit = catalog.stock_unit(stock=20)
    mine, theirs, admin_token = bearer(buyer), bearer(other_buyer), bearer(admin)
    paid = order_of(api_client, mine, [(unit, 1)])
    shipped = order_of(api_client, mine, [(unit, 1)])
    cancelled = order_of(api_client, mine, [(unit, 1)])
    others = order_of(api_client, theirs, [(unit, 1)])
    assert pay(api_client, mine, paid["order_id"]).status_code == 200
    assert pay(api_client, mine, shipped["order_id"]).status_code == 200
    assert api(api_client, "post", f"/api/admin/orders/{shipped['order_id']}/ship/", admin_token, {}).status_code == 200
    assert api(api_client, "post", f"/api/orders/{cancelled['order_id']}/cancel/", mine).status_code == 200
    before = PaymentRecord.objects.count()

    for order, status in ((paid, "paid"), (shipped, "shipped"), (cancelled, "cancelled")):
        response = pay(api_client, mine, order["order_id"])
        assert response.status_code == 422, status
        err = error_of(response)
        assert err["reason"] == "invalid_status" and err["values"]["current_status"] == status
    assert PaymentRecord.objects.count() == before

    for target in (others["order_id"], 99999999, "abc"):
        missing = pay(api_client, mine, target)
        assert missing.status_code == 404 and error_of(missing)["type"] == "not_found"
    assert error_of(pay(api_client, mine, others["order_id"])) == error_of(pay(api_client, mine, 99999999))

    invalid = pay(api_client, mine, others["order_id"], "maybe")
    assert invalid.status_code == 400 and "mock_instruction" in field_names(invalid)

    denied = pay(api_client, admin_token, others["order_id"])
    assert denied.status_code == 403 and error_of(denied)["type"] == "permission_denied"
    assert PaymentRecord.objects.count() == before


# trace: FR-032, FR-033, FR-030, ADDR-001
def test_it_031_history_and_detail_contents(api_client, buyer, other_buyer, bearer, catalog, make_coupon, set_state):
    """IT-031 注文履歴一覧・注文詳細（購入者）の内容と確定時点の単価。"""
    from catalog.models import StockUnit

    x = catalog.stock_unit(catalog.product("椀"), price=1000, stock=100, variant_name="朱")
    y = catalog.stock_unit(catalog.product("箸"), price=300, stock=100, variant_name="黒")
    make_coupon("HIST-10", discount_type="percentage", discount_value=10)
    base = jst(2027, 4, 10, 9, 0, 0)
    created = []
    for i in range(21):
        set_state(fixed_now=base + timedelta(minutes=i // 2))
        token = bearer(buyer)
        if i == 0:
            add_item(api_client, token, x.pk, 2)
            add_item(api_client, token, y.pk, 1)
            assert api(api_client, "post", "/api/cart/coupon/", token, {"coupon_code": "HIST-10"}).status_code == 200
            created.append(order_of(api_client, token, []))
        else:
            created.append(order_of(api_client, token, [(y, 1)]))
    set_state(fixed_now=base + timedelta(hours=1))
    other_order = order_of(api_client, bearer(other_buyer), [(y, 1)])
    token = bearer(buyer)
    assert pay(api_client, token, created[0]["order_id"]).status_code == 200
    StockUnit.objects.filter(pk=x.pk).update(price_excluding_tax=5000)

    expected = sorted(created, key=lambda o: (o["ordered_at"], o["order_number"]), reverse=True)
    page1 = body(api(api_client, "get", "/api/orders/", token))
    page2 = body(api(api_client, "get", "/api/orders/?page=2", token))
    page3 = body(api(api_client, "get", "/api/orders/?page=3", token))
    assert (page1["page"], page1["page_size"], page1["total_count"], page1["total_pages"]) == (1, 20, 21, 2)
    assert [o["order_id"] for o in page1["items"] + page2["items"]] == [o["order_id"] for o in expected]
    assert page3["items"] == [] and page3["total_pages"] == 2
    assert other_order["order_id"] not in [o["order_id"] for o in page1["items"] + page2["items"]]
    head = page1["items"][0]
    assert set(head) >= {"order_id", "order_number", "ordered_at", "status", "total_amount", "total_quantity"}
    assert api(api_client, "get", "/api/orders/?page=0", token).status_code == 400

    detail = body(api(api_client, "get", f"/api/orders/{created[0]['order_id']}/", token))
    assert [
        (i["stock_unit_id"], i["unit_price_excluding_tax"], i["quantity"], i["line_amount"]) for i in detail["items"]
    ] == [(x.pk, 1000, 2, 2000), (y.pk, 300, 1, 300)]
    assert detail["amounts"] == {
        "subtotal": 2300,
        "discount_amount": 230,
        "discounted_subtotal": 2070,
        "shipping_fee": 500,
        "tax_amount": 257,
        "total_amount": 2827,
    }
    assert {k: detail["coupon"][k] for k in ("coupon_code", "discount_type", "discount_value")} == {
        "coupon_code": "HIST-10",
        "discount_type": "percentage",
        "discount_value": 10,
    }
    assert detail["coupon"]["discount_type_label"] == "定率"
    assert [(h["from_status"], h["to_status"], h["actor_user_type"]) for h in detail["status_history"]] == [
        (None, "accepted", "buyer"),
        ("accepted", "paid", "buyer"),
    ]
    assert detail["shipping_address"]["postal_code"] == ADDRESS["postal_code"]
    assert detail["shipped_at"] is None and detail["delivered_at"] is None and detail["cancelled_at"] is None
    assert detail["tracking_number"] is None
    assert detail["can_pay"] is False and detail["can_cancel"] is True
    assert "payments" not in detail and "buyer" not in detail
    unpaid = body(api(api_client, "get", f"/api/orders/{created[1]['order_id']}/", token))
    assert unpaid["coupon"] is None and unpaid["can_pay"] is True and unpaid["can_cancel"] is True
    hidden = api(api_client, "get", f"/api/orders/{other_order['order_id']}/", token)
    assert hidden.status_code == 404 and error_of(hidden)["type"] == "not_found"


# trace: FR-034, ADDR-004
def test_it_032_buyer_cancel_and_invalid_status(api_client, buyer, admin, bearer, catalog):
    """IT-032 購入者キャンセル（注文受付・支払済）と不正状態。"""
    from orders.models import OrderStatusHistory, PaymentRecord

    a = catalog.stock_unit(stock=10)
    b = catalog.stock_unit(stock=10)
    token, admin_token = bearer(buyer), bearer(admin)
    accepted = order_of(api_client, token, [(a, 2), (b, 1)])
    paid = order_of(api_client, token, [(a, 3)])
    shipped = order_of(api_client, token, [(b, 4)])
    pay(api_client, token, paid["order_id"])
    pay(api_client, token, shipped["order_id"])
    api(api_client, "post", f"/api/admin/orders/{shipped['order_id']}/ship/", admin_token, {})
    assert (_stock(a), _stock(b)) == (5, 5)
    paid_records = list(PaymentRecord.objects.filter(order_id=paid["order_id"]).values_list("pk", "result", "amount"))

    first = api(api_client, "post", f"/api/orders/{accepted['order_id']}/cancel/", token)
    assert first.status_code == 200
    assert body(first)["status"] == "cancelled" and body(first)["cancelled_at"] is not None
    assert (_stock(a), _stock(b)) == (7, 6)
    last = OrderStatusHistory.objects.filter(order_id=accepted["order_id"]).order_by("pk").last()
    assert (last.from_status, last.to_status, last.actor_id, last.actor_user_type) == (
        "accepted",
        "cancelled",
        buyer.pk,
        "buyer",
    )

    second = api(api_client, "post", f"/api/orders/{paid['order_id']}/cancel/", token)
    assert second.status_code == 200 and body(second)["status"] == "cancelled"
    assert _stock(a) == 10
    assert (
        list(PaymentRecord.objects.filter(order_id=paid["order_id"]).values_list("pk", "result", "amount"))
        == paid_records
    )

    refused = api(api_client, "post", f"/api/orders/{shipped['order_id']}/cancel/", token)
    assert refused.status_code == 422
    assert (
        error_of(refused)["reason"] == "invalid_status" and error_of(refused)["values"]["current_status"] == "shipped"
    )
    twice = api(api_client, "post", f"/api/orders/{accepted['order_id']}/cancel/", token)
    assert twice.status_code == 422 and error_of(twice)["values"]["current_status"] == "cancelled"
    assert (_stock(a), _stock(b)) == (10, 6)
