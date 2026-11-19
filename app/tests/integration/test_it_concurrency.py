# trace: FR-001, FR-020, FR-021, FR-030, FR-031, FR-034, FR-043, FR-045, ADDR-004, ADDR-008, ADDR-011
"""結合試験：同時実行（複数の DB 接続・スレッド→業務処理→行ロック・一意制約）。

IT-039〜IT-047（AI INITIAL）。ADDR-011 DD-010 に従い transaction=True（試験データ・試験用状態をコミットして
全接続から見えるようにする方式）で実行する。各スレッドは独立した DB 接続を持ち、Barrier で同時に要求を送る。
期待結果は CMN-19〜CMN-23、各 FR の 6.x.9（排他・同時実行）、NFR-PF-07、
ADDR-004（ロック順序・条件付き一意制約）から導出する。
"""

import threading

import pytest

from tests.integration._helpers import add_item, api, body, error_of, order_of, pay, place

pytestmark = pytest.mark.django_db(transaction=True)


# trace: FR-030, FR-031, ADDR-004
def _parallel(*calls):
    """各呼出しを別スレッド（別の DB 接続）で同時に開始し、応答を呼出し順に返す。"""
    from django.db import connection
    from rest_framework.test import APIClient

    barrier = threading.Barrier(len(calls))
    results = [None] * len(calls)
    errors = []

    def worker(index, call):
        try:
            client = APIClient()
            barrier.wait(timeout=30)
            results[index] = call(client)
        except Exception as exc:  # noqa: BLE001 - スレッド内の例外をテストへ返す
            errors.append(exc)
        finally:
            connection.close()

    threads = [threading.Thread(target=worker, args=(i, c)) for i, c in enumerate(calls)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=120)
    assert not errors, errors
    assert all(not t.is_alive() for t in threads)
    return results


# trace: FR-030, ADDR-004
def _stock(unit):
    from catalog.models import StockUnit

    return StockUnit.objects.get(pk=unit.pk).stock_quantity


# trace: FR-030, ADDR-004, ADDR-011
def test_it_039_concurrent_place_order_stock_one(api_client, make_user, bearer, catalog):
    """IT-039 在庫数量1の在庫単位を2名が同時に注文確定。"""
    from carts.models import CartItem
    from orders.models import Order

    unit = catalog.stock_unit(stock=1)
    users = [make_user(), make_user()]
    tokens = [bearer(u) for u in users]
    for token in tokens:
        assert add_item(api_client, token, unit.pk, 1).status_code == 200

    results = _parallel(*[lambda c, t=t: place(c, t) for t in tokens])
    codes = sorted(r.status_code for r in results)
    assert codes == [201, 422]
    loser_index = next(i for i, r in enumerate(results) if r.status_code == 422)
    err = error_of(results[loser_index])
    assert err["reason"] == "insufficient_stock"
    assert err["values"]["stock_units"] == [
        {"stock_unit_id": unit.pk, "sku": unit.sku, "requested_quantity": 1, "stock_quantity": 0}
    ]
    assert Order.objects.count() == 1 and _stock(unit) == 0
    loser = users[loser_index]
    assert list(
        CartItem.objects.filter(cart__buyer=loser, cart__status="active").values_list("quantity", flat=True)
    ) == [1]


# trace: FR-030, ADDR-004
def test_it_040_ten_parallel_place_orders(api_client, make_user, bearer, catalog):
    """IT-040 同一在庫単位に対する10並列の注文確定。"""
    from django.db.models import Sum

    from orders.models import Order, OrderItem

    unit = catalog.stock_unit(stock=5)
    tokens = [bearer(make_user()) for _ in range(10)]
    for token in tokens:
        assert add_item(api_client, token, unit.pk, 1).status_code == 200

    results = _parallel(*[lambda c, t=t: place(c, t) for t in tokens])
    codes = [r.status_code for r in results]
    assert codes.count(201) == 5 and codes.count(422) == 5
    assert all(error_of(r)["reason"] == "insufficient_stock" for r in results if r.status_code == 422)
    assert _stock(unit) == 0
    assert Order.objects.count() == 5
    assert OrderItem.objects.filter(stock_unit=unit).aggregate(total=Sum("quantity"))["total"] == 5


# trace: FR-031, ADDR-004, ADDR-008
def test_it_041_concurrent_payment_single_approval(api_client, buyer, bearer, catalog, set_state):
    """IT-041 同一注文への同時支払。"""
    from orders.models import OrderStatusHistory, PaymentRecord

    unit = catalog.stock_unit(stock=5)
    order = order_of(api_client, bearer(buyer), [(unit, 1)])
    tokens = [bearer(buyer), bearer(buyer)]
    set_state(payment_delay_seconds=1.0)

    results = _parallel(*[lambda c, t=t: pay(c, t, order["order_id"]) for t in tokens])
    assert sorted(r.status_code for r in results) == [200, 422]
    loser = next(r for r in results if r.status_code == 422)
    assert error_of(loser)["reason"] == "invalid_status" and error_of(loser)["values"]["current_status"] == "paid"
    assert PaymentRecord.objects.filter(order_id=order["order_id"]).count() == 1
    assert PaymentRecord.objects.filter(order_id=order["order_id"], result="approved").count() == 1
    assert OrderStatusHistory.objects.filter(order_id=order["order_id"], to_status="paid").count() == 1


# trace: FR-031, FR-034, ADDR-004
def test_it_042_concurrent_payment_and_cancel(api_client, buyer, bearer, catalog, set_state):
    """IT-042 同一注文への支払とキャンセルの同時実行。"""
    from orders.models import Order, PaymentRecord

    unit = catalog.stock_unit(stock=5)
    order = order_of(api_client, bearer(buyer), [(unit, 2)])
    oid = order["order_id"]
    assert _stock(unit) == 3
    pay_token, cancel_token = bearer(buyer), bearer(buyer)
    set_state(payment_delay_seconds=1.0)

    paid, cancelled = _parallel(
        lambda c: pay(c, pay_token, oid),
        lambda c: api(c, "post", f"/api/orders/{oid}/cancel/", cancel_token),
    )
    row = Order.objects.get(pk=oid)
    assert cancelled.status_code == 200 and row.status == "cancelled"
    assert _stock(unit) == 5
    if paid.status_code == 200:
        # 支払→キャンセルの順：支払済からのキャンセル（決済記録は承認1件のまま）
        assert list(PaymentRecord.objects.filter(order_id=oid).values_list("result", flat=True)) == ["approved"]
        assert row.paid_at is not None
    else:
        # キャンセル→支払の順：支払は状態不正で決済要求を送らない
        assert paid.status_code == 422
        assert (
            error_of(paid)["reason"] == "invalid_status" and error_of(paid)["values"]["current_status"] == "cancelled"
        )
        assert PaymentRecord.objects.filter(order_id=oid).count() == 0 and row.paid_at is None


# trace: FR-034, FR-045, ADDR-004
def test_it_043_concurrent_cancels_restore_once(api_client, buyer, admin, bearer, catalog):
    """IT-043 同時キャンセル（購入者×購入者、管理者×購入者）で在庫は1回だけ戻る。"""
    from orders.models import OrderStatusHistory

    unit = catalog.stock_unit(stock=10)
    o1 = order_of(api_client, bearer(buyer), [(unit, 2)])
    o2 = order_of(api_client, bearer(buyer), [(unit, 3)])
    assert _stock(unit) == 5

    t1, t2 = bearer(buyer), bearer(buyer)
    first = _parallel(
        lambda c: api(c, "post", f"/api/orders/{o1['order_id']}/cancel/", t1),
        lambda c: api(c, "post", f"/api/orders/{o1['order_id']}/cancel/", t2),
    )
    assert sorted(r.status_code for r in first) == [200, 422]
    assert error_of(next(r for r in first if r.status_code == 422))["reason"] == "invalid_status"
    assert _stock(unit) == 7

    admin_token, buyer_token = bearer(admin), bearer(buyer)
    second = _parallel(
        lambda c: api(c, "post", f"/api/admin/orders/{o2['order_id']}/cancel/", admin_token),
        lambda c: api(c, "post", f"/api/orders/{o2['order_id']}/cancel/", buyer_token),
    )
    assert sorted(r.status_code for r in second) == [200, 422]
    assert _stock(unit) == 10
    for order in (o1, o2):
        assert OrderStatusHistory.objects.filter(order_id=order["order_id"], to_status="cancelled").count() == 1


# trace: FR-043, FR-045, ADDR-004
def test_it_044_concurrent_ship_and_cancel_vs_ship(api_client, buyer, admin, bearer, catalog):
    """IT-044 同時出荷登録、管理者キャンセルと出荷登録の同時実行。"""
    from orders.models import Order, OrderStatusHistory

    unit = catalog.stock_unit(stock=10)
    token = bearer(buyer)
    o1 = order_of(api_client, token, [(unit, 1)])
    o2 = order_of(api_client, token, [(unit, 2)])
    pay(api_client, token, o1["order_id"])
    pay(api_client, token, o2["order_id"])
    a1, a2 = bearer(admin), bearer(admin)

    ships = _parallel(
        lambda c: api(c, "post", f"/api/admin/orders/{o1['order_id']}/ship/", a1, {"tracking_number": "A-1"}),
        lambda c: api(c, "post", f"/api/admin/orders/{o1['order_id']}/ship/", a2, {"tracking_number": "B-2"}),
    )
    assert sorted(r.status_code for r in ships) == [200, 422]
    assert error_of(next(r for r in ships if r.status_code == 422))["values"]["current_status"] == "shipped"
    assert OrderStatusHistory.objects.filter(order_id=o1["order_id"], to_status="shipped").count() == 1
    winner = next(r for r in ships if r.status_code == 200)
    assert Order.objects.get(pk=o1["order_id"]).tracking_number == body(winner)["tracking_number"]

    cancel, ship = _parallel(
        lambda c: api(c, "post", f"/api/admin/orders/{o2['order_id']}/cancel/", a1),
        lambda c: api(c, "post", f"/api/admin/orders/{o2['order_id']}/ship/", a2, {}),
    )
    assert sorted([cancel.status_code, ship.status_code]) == [200, 422]
    row = Order.objects.get(pk=o2["order_id"])
    if cancel.status_code == 200:
        assert row.status == "cancelled" and _stock(unit) == 9
        assert error_of(ship)["values"]["current_status"] == "cancelled"
    else:
        assert row.status == "shipped" and _stock(unit) == 7
        assert error_of(cancel)["values"]["current_status"] == "shipped"


# trace: FR-001, ADDR-004
def test_it_045_concurrent_register_same_email(api_client):
    """IT-045 同一メールアドレスの同時会員登録。"""
    from accounts.models import User

    def register(email):
        return lambda c: api(
            c,
            "post",
            "/api/auth/register/",
            data={
                "email": email,
                "password": "Passw0rdIt1",
                "password_confirmation": "Passw0rdIt1",
                "name": "同時 登録",
            },
        )

    results = _parallel(register("Same@Example.test"), register("same@example.TEST"))
    assert sorted(r.status_code for r in results) == [201, 422]
    assert error_of(next(r for r in results if r.status_code == 422))["reason"] == "email_already_registered"
    assert User.objects.filter(email="same@example.test").count() == 1
    assert User.objects.count() == 1


# trace: FR-021, FR-020, ADDR-004
def test_it_046_concurrent_cart_get_and_add(api_client, buyer, bearer, catalog):
    """IT-046 同一在庫単位の同時カート追加と同時カート照会。"""
    from carts.models import Cart, CartItem

    unit = catalog.stock_unit(stock=20)
    t1, t2 = bearer(buyer), bearer(buyer)
    gets = _parallel(lambda c: api(c, "get", "/api/cart/", t1), lambda c: api(c, "get", "/api/cart/", t2))
    assert [r.status_code for r in gets] == [200, 200]
    assert Cart.objects.filter(buyer=buyer, status="active").count() == 1

    adds = _parallel(lambda c: add_item(c, t1, unit.pk, 6), lambda c: add_item(c, t2, unit.pk, 6))
    assert sorted(r.status_code for r in adds) == [200, 422]
    assert error_of(next(r for r in adds if r.status_code == 422))["reason"] == "quantity_limit_exceeded"
    assert list(CartItem.objects.filter(cart__buyer=buyer).values_list("quantity", flat=True)) == [6]


# trace: FR-030, ADDR-004
def test_it_047_concurrent_place_same_cart(api_client, buyer, bearer, catalog):
    """IT-047 同一カートの同時注文確定。"""
    from orders.models import Order

    unit = catalog.stock_unit(stock=5)
    t1, t2 = bearer(buyer), bearer(buyer)
    assert add_item(api_client, t1, unit.pk, 1).status_code == 200
    results = _parallel(lambda c: place(c, t1), lambda c: place(c, t2))
    assert sorted(r.status_code for r in results) == [201, 422]
    assert error_of(next(r for r in results if r.status_code == 422))["reason"] == "cart_empty"
    assert Order.objects.count() == 1 and _stock(unit) == 4
