# trace: FR-030, FR-031, FR-034, FR-043, FR-045, NFR-PF-07, NFR-LG-06
# trace: ADDR-004, ADDR-005, ADDR-008, ADDR-011
"""結合試験：AI GAP_FILL（同時実行。Revision 2 の Required Coverage と、INITIAL の確認漏れの補完）。

GF-012・GF-016・GF-019〜GF-021（origin=AI_GENERATED、generation_stage=GAP_FILL）。
AI INITIAL（IT-039〜IT-047）は変更しない。
ADDR-011 DD-010 に従い transaction=True（コミット方式）で、各要求を別スレッド・別の DB 接続から送る。
期待結果は AC-UC-006-020・AC-UC-007-019・AC-UC-012-009〜011、NFR-PF-07（10並列×10試行）、
ADDR-004（ロック順序）・ADDR-005（注文番号の一意・確定順・欠番）から導出する。
- 各 AC の測定条件（注文を作り直して10試行）に従い、真に同時の10試行を行い、全試行で Then を確認する。
- あわせて、同時の2要求が行ロック待ちに入った状態で解放する順序を固定し、(a)(b) 両方の逐次順序の Then を必ず確認する。
- 注文状態履歴の並び（変更日時→記録順）を判定するため、現在日時を試験用状態で固定する（ADDR-011）。
"""

import pytest

from tests.integration._helpers import (
    add_item,
    api,
    body,
    error_of,
    in_lock_order,
    install_recording_gateway,
    jst,
    order_of,
    parallel,
    pay,
    place,
)

pytestmark = pytest.mark.django_db(transaction=True)

TRIALS = 10
NOW = jst(2027, 4, 10, 10, 0, 0)


# trace: FR-030, ADDR-004
def _stock(unit):
    from catalog.models import StockUnit

    return StockUnit.objects.get(pk=unit.pk).stock_quantity


# trace: FR-031, FR-034, FR-043, FR-045, ADDR-004
def _admin_detail(admin_token, order_id):
    from rest_framework.test import APIClient

    response = api(APIClient(), "get", f"/api/admin/orders/{order_id}/", admin_token)
    assert response.status_code == 200, response.content
    return body(response)


# trace: FR-031, FR-034, FR-045, ADDR-004
def _transitions(detail):
    return [(h["from_status"], h["to_status"], h["actor_user_type"]) for h in detail["status_history"]]


# trace: FR-031, FR-045, ADDR-004, ADDR-008
def _check_admin_cancel_and_pay(cancel, paid, detail, stock_delta):
    """AC-UC-012-011 の Then（(a) キャンセル先着／(b) 支払先着）。どちらの分岐かを返す。"""
    assert cancel.status_code == 200, cancel.content
    assert detail["status"] == "cancelled" and stock_delta == 2
    assert (detail["can_ship"], detail["can_deliver"], detail["can_cancel"]) == (False, False, False)
    if paid.status_code == 422:
        err = error_of(paid)
        assert err["reason"] == "invalid_status" and err["values"]["current_status"] == "cancelled"
        assert detail["payments"] == [] and detail["paid_at"] is None
        assert _transitions(detail) == [(None, "accepted", "buyer"), ("accepted", "cancelled", "admin")]
        return "a"
    assert paid.status_code == 200, paid.content
    assert [(p["result"], p["amount"]) for p in detail["payments"]] == [("approved", 5500)]
    assert detail["paid_at"] is not None
    assert _transitions(detail) == [
        (None, "accepted", "buyer"),
        ("accepted", "paid", "buyer"),
        ("paid", "cancelled", "admin"),
    ]
    return "b"


# trace: FR-045, FR-031, ADDR-004, ADDR-008, ADDR-011
def test_gf_012_concurrent_admin_cancel_and_pay(api_client, buyer, admin, bearer, catalog, set_state):
    """GF-012 管理者キャンセルと購入者の支払の同時実行（AC-UC-012-011、10試行＋両順序の固定）。"""
    from orders.models import PaymentRecord

    set_state(fixed_now=NOW)
    unit = catalog.stock_unit(price=2500, stock=100)
    buyer_token, admin_token = bearer(buyer), bearer(admin)

    def fresh_order():
        order = order_of(api_client, buyer_token, [(unit, 2)])
        assert order["amounts"]["total_amount"] == 5500
        return order["order_id"], _stock(unit)

    def cancel_call(oid):
        return lambda c: api(c, "post", f"/api/admin/orders/{oid}/cancel/", admin_token)

    def pay_call(oid):
        return lambda c: pay(c, buyer_token, oid, "approved")

    branches = []
    for _ in range(TRIALS):
        oid, before = fresh_order()
        cancel, paid = parallel(cancel_call(oid), pay_call(oid))
        branches.append(
            _check_admin_cancel_and_pay(cancel, paid, _admin_detail(admin_token, oid), _stock(unit) - before)
        )
        assert PaymentRecord.objects.filter(order_id=oid).count() == (0 if branches[-1] == "a" else 1)
    assert len(branches) == TRIALS

    oid, before = fresh_order()
    cancel, paid = in_lock_order(oid, cancel_call(oid), pay_call(oid))
    assert _check_admin_cancel_and_pay(cancel, paid, _admin_detail(admin_token, oid), _stock(unit) - before) == "a"

    oid, before = fresh_order()
    paid, cancel = in_lock_order(oid, pay_call(oid), cancel_call(oid))
    assert _check_admin_cancel_and_pay(cancel, paid, _admin_detail(admin_token, oid), _stock(unit) - before) == "b"


# trace: FR-030, NFR-PF-07, NFR-LG-06, ADDR-004, ADDR-005
def _commit_order(order_ids):
    """注文の行を登録したトランザクションのコミット時刻の順に注文番号を返す（track_commit_timestamp=on）。"""
    from django.db import connection

    from orders.models import Order

    with connection.cursor() as cursor:
        cursor.execute("SHOW track_commit_timestamp")
        assert cursor.fetchone()[0] == "on", "試験用 DB の track_commit_timestamp が on でない（環境の準備誤り）"
        cursor.execute(
            f"SELECT order_number, pg_xact_commit_timestamp(xmin) FROM {Order._meta.db_table} "  # noqa: S608
            "WHERE id = ANY(%s) ORDER BY pg_xact_commit_timestamp(xmin), order_number",
            [list(order_ids)],
        )
        rows = cursor.fetchall()
    assert all(ts is not None for _, ts in rows)
    return [number for number, _ in rows], [ts for _, ts in rows]


# trace: FR-030, NFR-PF-07, NFR-LG-06, ADDR-004, ADDR-005
def test_gf_016_ten_parallel_ten_trials_order_numbers(api_client, make_user, bearer, catalog):
    """GF-016 在庫数量5への10並列の注文確定を10回（NFR-PF-07）と注文番号の一意・確定順の増加（ADDR-005）。"""
    from django.db.models import Sum

    from orders.models import Order, OrderItem

    successful_ids = []
    for trial in range(TRIALS):
        unit = catalog.stock_unit(stock=5)
        tokens = [bearer(make_user()) for _ in range(10)]
        for token in tokens:
            assert add_item(api_client, token, unit.pk, 1).status_code == 200
        results = parallel(*[lambda c, t=t: place(c, t) for t in tokens])
        codes = [r.status_code for r in results]
        assert codes.count(201) == 5 and codes.count(422) == 5, (trial, codes)
        for response in results:
            if response.status_code == 422:
                err = error_of(response)
                assert err["reason"] == "insufficient_stock"
                assert err["values"]["stock_units"][0]["stock_quantity"] == 0
        assert _stock(unit) == 0
        reserved = OrderItem.objects.filter(stock_unit=unit).aggregate(total=Sum("quantity"))["total"]
        assert reserved == 5, (trial, reserved)
        successful_ids += [body(r)["order_id"] for r in results if r.status_code == 201]

    assert len(successful_ids) == 50 and Order.objects.count() == 50
    numbers = list(Order.objects.filter(pk__in=successful_ids).values_list("order_number", flat=True))
    assert len(set(numbers)) == 50
    in_commit_order, stamps = _commit_order(successful_ids)
    assert stamps == sorted(stamps)
    assert in_commit_order == sorted(in_commit_order), "注文番号がコミットの順に増加していない"
    assert all(n.startswith("PO-") and len(n) == 11 for n in in_commit_order)


# trace: FR-031, FR-034, ADDR-004, ADDR-008
def _check_pay_and_cancel(paid, cancelled, order_id, stock_delta, recorder, order_number):
    """AC-UC-007-019 の Then。どちらの分岐かを返す。"""
    from orders.models import Order, OrderStatusHistory, PaymentRecord

    row = Order.objects.get(pk=order_id)
    assert cancelled.status_code == 200, cancelled.content
    assert row.status == "cancelled" and stock_delta == 2
    history = [
        (h.from_status, h.to_status)
        for h in OrderStatusHistory.objects.filter(order_id=order_id).order_by("changed_at", "pk")
    ]
    sent = [r for r in recorder.requests if r.order_number == order_number]
    if paid.status_code == 422:
        err = error_of(paid)
        assert err["reason"] == "invalid_status" and err["values"]["current_status"] == "cancelled"
        assert PaymentRecord.objects.filter(order_id=order_id).count() == 0
        assert history == [(None, "accepted"), ("accepted", "cancelled")]
        assert sent == []
        return "a"
    assert paid.status_code == 200, paid.content
    assert list(PaymentRecord.objects.filter(order_id=order_id).values_list("result", flat=True)) == ["approved"]
    assert history == [(None, "accepted"), ("accepted", "paid"), ("paid", "cancelled")]
    assert len(sent) == 1
    return "b"


# trace: FR-031, FR-034, ADDR-004, ADDR-008, ADDR-011
def test_gf_019_pay_and_buyer_cancel_ten_trials(api_client, buyer, bearer, catalog, set_state, monkeypatch):
    """GF-019 支払とキャンセル（購入者）の同時実行の Then 全項目（AC-UC-007-019、IT-042 の補完）。"""
    set_state(fixed_now=NOW)
    recorder = install_recording_gateway(monkeypatch)
    unit = catalog.stock_unit(price=2500, stock=100)
    token = bearer(buyer)

    def fresh_order():
        order = order_of(api_client, token, [(unit, 2)])
        return order["order_id"], order["order_number"], _stock(unit)

    def pay_call(oid):
        return lambda c: pay(c, token, oid, "approved")

    def cancel_call(oid):
        return lambda c: api(c, "post", f"/api/orders/{oid}/cancel/", token)

    branches = []
    for _ in range(TRIALS):
        oid, number, before = fresh_order()
        paid, cancelled = parallel(pay_call(oid), cancel_call(oid))
        branches.append(_check_pay_and_cancel(paid, cancelled, oid, _stock(unit) - before, recorder, number))
    assert len(branches) == TRIALS

    oid, number, before = fresh_order()
    cancelled, paid = in_lock_order(oid, cancel_call(oid), pay_call(oid))
    assert _check_pay_and_cancel(paid, cancelled, oid, _stock(unit) - before, recorder, number) == "a"
    oid, number, before = fresh_order()
    paid, cancelled = in_lock_order(oid, pay_call(oid), cancel_call(oid))
    assert _check_pay_and_cancel(paid, cancelled, oid, _stock(unit) - before, recorder, number) == "b"


# trace: FR-034, FR-045, ADDR-004
def _check_two_cancels(admin_resp, buyer_resp, order_id, stock_delta):
    """AC-UC-012-009 の Then。完了した側（admin／buyer）を返す。"""
    from orders.models import OrderStatusHistory

    assert sorted([admin_resp.status_code, buyer_resp.status_code]) == [200, 422]
    assert stock_delta == 2
    late = admin_resp if admin_resp.status_code == 422 else buyer_resp
    err = error_of(late)
    assert err["reason"] == "invalid_status" and err["values"]["current_status"] == "cancelled"
    assert err["message"] == "この注文はキャンセルできません（現在の状態：キャンセル済）。"
    winner = "admin" if admin_resp.status_code == 200 else "buyer"
    cancelled = list(OrderStatusHistory.objects.filter(order_id=order_id, to_status="cancelled"))
    assert len(cancelled) == 1 and cancelled[0].actor_user_type == winner
    return winner


# trace: FR-034, FR-045, ADDR-004, ADDR-011
def test_gf_020_admin_and_buyer_cancel_ten_trials(api_client, buyer, admin, bearer, catalog, set_state):
    """GF-020 管理者キャンセルと購入者キャンセルの同時実行の Then 全項目（AC-UC-012-009、IT-043 の補完）。"""
    set_state(fixed_now=NOW)
    unit = catalog.stock_unit(price=2500, stock=100)
    buyer_token, admin_token = bearer(buyer), bearer(admin)

    def fresh_order():
        order = order_of(api_client, buyer_token, [(unit, 2)])
        return order["order_id"], _stock(unit)

    def admin_call(oid):
        return lambda c: api(c, "post", f"/api/admin/orders/{oid}/cancel/", admin_token)

    def buyer_call(oid):
        return lambda c: api(c, "post", f"/api/orders/{oid}/cancel/", buyer_token)

    winners = []
    for _ in range(TRIALS):
        oid, before = fresh_order()
        admin_resp, buyer_resp = parallel(admin_call(oid), buyer_call(oid))
        winners.append(_check_two_cancels(admin_resp, buyer_resp, oid, _stock(unit) - before))
    assert len(winners) == TRIALS

    oid, before = fresh_order()
    admin_resp, buyer_resp = in_lock_order(oid, admin_call(oid), buyer_call(oid))
    assert _check_two_cancels(admin_resp, buyer_resp, oid, _stock(unit) - before) == "admin"
    oid, before = fresh_order()
    buyer_resp, admin_resp = in_lock_order(oid, buyer_call(oid), admin_call(oid))
    assert _check_two_cancels(admin_resp, buyer_resp, oid, _stock(unit) - before) == "buyer"


# trace: FR-043, FR-045, ADDR-004
def _check_cancel_and_ship(cancel, ship, order_id, stock_delta, history_before):
    """AC-UC-012-010 の Then。完了した側（cancel／ship）を返す。"""
    from orders.models import Order, OrderStatusHistory, PaymentRecord

    row = Order.objects.get(pk=order_id)
    assert sorted([cancel.status_code, ship.status_code]) == [200, 422]
    assert OrderStatusHistory.objects.filter(order_id=order_id).count() == history_before + 1
    assert list(PaymentRecord.objects.filter(order_id=order_id).values_list("result", flat=True)) == ["approved"]
    if cancel.status_code == 200:
        err = error_of(ship)
        assert err["reason"] == "invalid_status" and err["values"]["current_status"] == "cancelled"
        assert err["message"] == "この注文は出荷登録できません（現在の状態：キャンセル済）。"
        assert row.status == "cancelled" and stock_delta == 3
        assert row.shipped_at is None and row.tracking_number is None
        return "cancel"
    err = error_of(cancel)
    assert err["reason"] == "invalid_status" and err["values"]["current_status"] == "shipped"
    assert err["message"] == "この注文はキャンセルできません（現在の状態：出荷済）。"
    assert row.status == "shipped" and row.tracking_number == "TRK-Y" and stock_delta == 0
    assert row.cancelled_at is None
    return "ship"


# trace: FR-043, FR-045, ADDR-004, ADDR-011
def test_gf_021_admin_cancel_and_ship_ten_trials(api_client, buyer, admin, make_user, bearer, catalog, set_state):
    """GF-021 管理者キャンセルと出荷登録の同時実行の Then 全項目（AC-UC-012-010、IT-044 の補完）。"""
    from orders.models import OrderStatusHistory

    set_state(fixed_now=NOW)
    unit = catalog.stock_unit(price=1200, stock=100)
    buyer_token = bearer(buyer)
    admin_x, admin_y = bearer(admin), bearer(make_user(name="管理者 Y", user_type="admin"))

    def fresh_order():
        order = order_of(api_client, buyer_token, [(unit, 3)])
        assert pay(api_client, buyer_token, order["order_id"], "approved").status_code == 200
        oid = order["order_id"]
        return oid, _stock(unit), OrderStatusHistory.objects.filter(order_id=oid).count()

    def cancel_call(oid):
        return lambda c: api(c, "post", f"/api/admin/orders/{oid}/cancel/", admin_x)

    def ship_call(oid):
        return lambda c: api(c, "post", f"/api/admin/orders/{oid}/ship/", admin_y, {"tracking_number": "TRK-Y"})

    winners = []
    for _ in range(TRIALS):
        oid, before, history = fresh_order()
        assert history == 2
        cancel, ship = parallel(cancel_call(oid), ship_call(oid))
        winners.append(_check_cancel_and_ship(cancel, ship, oid, _stock(unit) - before, history))
    assert len(winners) == TRIALS

    oid, before, history = fresh_order()
    cancel, ship = in_lock_order(oid, cancel_call(oid), ship_call(oid))
    assert _check_cancel_and_ship(cancel, ship, oid, _stock(unit) - before, history) == "cancel"
    oid, before, history = fresh_order()
    ship, cancel = in_lock_order(oid, ship_call(oid), cancel_call(oid))
    assert _check_cancel_and_ship(cancel, ship, oid, _stock(unit) - before, history) == "ship"
