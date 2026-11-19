# trace: FR-030, FR-031, FR-033, FR-034, FR-040, FR-041, FR-042, FR-043, FR-044, FR-045, ADDR-001, ADDR-004
# trace: ADDR-007, ADDR-012
"""結合試験：管理者の在庫・注文管理（Web API／画面→業務処理→DB）と注文状態遷移。

IT-033〜IT-038（AI INITIAL）。期待結果は FR-040〜FR-045、FR-033・FR-034、8.1 状態遷移、CMN-26/35/36、
UI-27、ADDR-001（項目キー・検索条件の外部値）・ADDR-004（ロック・状態判定）・ADDR-007（コード値）から導出する。
"""

import pytest

from tests.integration._helpers import api, body, error_of, form_fields, jst, order_of, pay, text

pytestmark = pytest.mark.django_db


# trace: FR-040, FR-043, ADDR-004
def _stock(unit):
    from catalog.models import StockUnit

    return StockUnit.objects.get(pk=unit.pk).stock_quantity


# trace: FR-040, FR-030, FR-034, ADDR-001, ADDR-004
def test_it_033_stock_unit_list_filters_and_reflects_orders(api_client, buyer, admin, bearer, catalog):
    """IT-033 在庫単位一覧（管理）の対象・検索・低在庫・ページングと在庫変動の反映。"""
    s1 = catalog.supplier("SUP-A", "仕入先A")
    s2 = catalog.supplier("SUP-B", "仕入先B")
    public = catalog.product("Plain Plate")
    private = catalog.product("Hidden Bowl", is_public=False)
    cup = catalog.product("Kitchen CUP")
    units = {}
    for n in range(1, 51):
        product = private if n % 10 == 0 else public
        sku = f"AB-{n:03d}"
        units[sku] = catalog.stock_unit(product, sku=sku, stock=0 if n == 2 else 10, supplier=s1)
    units["KC-0101-BL"] = catalog.stock_unit(cup, sku="KC-0101-BL", stock=5, supplier=s2)
    units["KC-0102-WH"] = catalog.stock_unit(cup, sku="KC-0102-WH", stock=6, supplier=s2)
    token = bearer(admin)

    def query(params):
        response = api(api_client, "get", f"/api/admin/stock-units/?{params}", token)
        assert response.status_code == 200, (params, response.content)
        return body(response)

    first = query("")
    assert (first["page"], first["page_size"], first["total_count"], first["total_pages"]) == (1, 50, 52, 2)
    all_skus = sorted(units)
    assert [i["sku"] for i in first["items"]] == all_skus[:50]
    row = next(i for i in first["items"] if i["sku"] == "AB-010")
    assert row["visibility"] == "private" and row["product_name"] == "Hidden Bowl" and row["supplier_name"] == "仕入先A"
    assert row["is_low_stock"] is False
    assert next(i for i in first["items"] if i["sku"] == "AB-002")["is_low_stock"] is True
    second = query("page=2")
    assert [i["sku"] for i in second["items"]] == all_skus[50:]
    assert query("page=3")["items"] == []

    assert [i["sku"] for i in query("sku=kc-01")["items"]] == ["KC-0101-BL", "KC-0102-WH"]
    assert [i["sku"] for i in query("product_name=cup")["items"]] == ["KC-0101-BL", "KC-0102-WH"]
    assert [i["sku"] for i in query("supplier_code=SUP-B")["items"]] == ["KC-0101-BL", "KC-0102-WH"]
    low = query("low_stock_only=true")
    assert [i["sku"] for i in low["items"]] == ["AB-002", "KC-0101-BL"]
    assert all(i["is_low_stock"] for i in low["items"])
    assert [i["sku"] for i in query("sku=kc&low_stock_only=true")["items"]] == ["KC-0101-BL"]
    assert query("sku=kc&supplier_code=SUP-A")["items"] == []

    buyer_token = bearer(buyer)
    order = order_of(api_client, buyer_token, [(units["AB-001"], 2)])
    assert query("sku=AB-001")["items"][0]["stock_quantity"] == 8
    assert api(api_client, "post", f"/api/orders/{order['order_id']}/cancel/", buyer_token).status_code == 200
    assert query("sku=AB-001")["items"][0]["stock_quantity"] == 10


# trace: FR-041, ADDR-001
def test_it_034_admin_order_search(api_client, make_user, admin, bearer, catalog, set_state):
    """IT-034 注文一覧検索（管理者）の条件と並び順。"""
    alice = make_user("alice.buyer@example.test", name="有栖 花子")
    bob = make_user("bob@example.test", name="坊 太郎")
    unit = catalog.stock_unit(price=1000, stock=50)
    plan = [
        (alice, jst(2027, 4, 9, 23, 59, 59), 1, None),
        (bob, jst(2027, 4, 10, 0, 0, 0), 2, "paid"),
        (alice, jst(2027, 4, 10, 23, 59, 59), 3, "shipped"),
        (bob, jst(2027, 4, 11, 0, 0, 0), 1, "cancelled"),
    ]
    orders = []
    for user, at, quantity, final in plan:
        set_state(fixed_now=at)
        token, admin_token = bearer(user), bearer(admin)
        order = order_of(api_client, token, [(unit, quantity)])
        if final in ("paid", "shipped"):
            assert pay(api_client, token, order["order_id"]).status_code == 200
        if final == "shipped":
            assert (
                api(api_client, "post", f"/api/admin/orders/{order['order_id']}/ship/", admin_token, {}).status_code
                == 200
            )
        if final == "cancelled":
            assert api(api_client, "post", f"/api/orders/{order['order_id']}/cancel/", token).status_code == 200
        orders.append(order)
    o1, o2, o3, o4 = (o["order_id"] for o in orders)
    set_state(fixed_now=jst(2027, 4, 12, 9, 0, 0))
    token = bearer(admin)

    def search(params=""):
        response = api(api_client, "get", f"/api/admin/orders/?{params}", token)
        assert response.status_code == 200, (params, response.content)
        return body(response)

    everything = search()
    assert [i["order_id"] for i in everything["items"]] == [o4, o3, o2, o1]
    top = everything["items"][1]
    assert top["buyer_email"] == "alice.buyer@example.test" and top["buyer_name"] == "有栖 花子"
    assert (
        top["status"] == "shipped"
        and top["total_quantity"] == 3
        and top["total_amount"] == orders[2]["amounts"]["total_amount"]
    )
    assert everything["page_size"] == 20 and everything["total_count"] == 4
    assert [i["order_id"] for i in search(f"order_number={orders[1]['order_number']}")["items"]] == [o2]
    assert [i["order_id"] for i in search("status=paid&status=shipped")["items"]] == [o3, o2]
    assert [i["order_id"] for i in search("order_date_from=2027-04-10&order_date_to=2027-04-10")["items"]] == [o3, o2]
    assert [i["order_id"] for i in search("buyer_email=ALICE")["items"]] == [o3, o1]
    assert [i["order_id"] for i in search("buyer_email=alice&status=shipped&order_date_from=2027-04-10")["items"]] == [
        o3
    ]


# trace: FR-042, FR-043, FR-044, ADDR-001, ADDR-004, ADDR-007
def test_it_035_admin_detail_ship_deliver(api_client, buyer, admin, bearer, catalog):
    """IT-035 注文詳細（管理者）と出荷登録→配達完了登録。"""
    from orders.models import OrderStatusHistory, PaymentRecord

    unit = catalog.stock_unit(stock=10)
    token, admin_token = bearer(buyer), bearer(admin)
    first = order_of(api_client, token, [(unit, 1)])
    second = order_of(api_client, token, [(unit, 2)])
    pay(api_client, token, first["order_id"])
    pay(api_client, token, second["order_id"])
    payments = list(PaymentRecord.objects.order_by("pk").values_list("pk", "result", "amount", "transaction_ref"))

    detail = body(api(api_client, "get", f"/api/admin/orders/{first['order_id']}/", admin_token))
    assert detail["buyer"] == {"user_id": buyer.pk, "email": buyer.email, "name": buyer.name}
    assert [(p["result"], p["amount"]) for p in detail["payments"]] == [("approved", first["amounts"]["total_amount"])]
    assert detail["payments"][0]["transaction_ref"].startswith("MOCK-")
    assert [h["actor_user_id"] for h in detail["status_history"]] == [buyer.pk, buyer.pk]
    assert detail["can_ship"] is True and detail["can_deliver"] is False

    shipped = api(
        api_client, "post", f"/api/admin/orders/{first['order_id']}/ship/", admin_token, {"tracking_number": "TRK-0001"}
    )
    assert shipped.status_code == 200
    data = body(shipped)
    assert data["status"] == "shipped" and data["shipped_at"] is not None and data["tracking_number"] == "TRK-0001"
    assert data["can_ship"] is False and data["can_deliver"] is True
    no_tracking = api(api_client, "post", f"/api/admin/orders/{second['order_id']}/ship/", admin_token, {})
    assert no_tracking.status_code == 200 and body(no_tracking)["tracking_number"] is None

    delivered = api(api_client, "post", f"/api/admin/orders/{first['order_id']}/deliver/", admin_token)
    assert delivered.status_code == 200
    assert body(delivered)["status"] == "delivered" and body(delivered)["delivered_at"] is not None
    history = list(OrderStatusHistory.objects.filter(order_id=first["order_id"]).order_by("pk"))
    assert [(h.from_status, h.to_status, h.actor_id, h.actor_user_type) for h in history] == [
        (None, "accepted", buyer.pk, "buyer"),
        ("accepted", "paid", buyer.pk, "buyer"),
        ("paid", "shipped", admin.pk, "admin"),
        ("shipped", "delivered", admin.pk, "admin"),
    ]
    assert _stock(unit) == 7
    assert (
        list(PaymentRecord.objects.order_by("pk").values_list("pk", "result", "amount", "transaction_ref")) == payments
    )


# trace: FR-045, FR-033, ADDR-004
def test_it_036_admin_cancel_visible_to_buyer(api_client, buyer, admin, bearer, catalog):
    """IT-036 管理者キャンセルと購入者からの確認。"""
    from orders.models import PaymentRecord

    unit = catalog.stock_unit(stock=10)
    token, admin_token = bearer(buyer), bearer(admin)
    accepted = order_of(api_client, token, [(unit, 2)])
    paid = order_of(api_client, token, [(unit, 3)])
    pay(api_client, token, paid["order_id"])
    assert _stock(unit) == 5
    records = list(PaymentRecord.objects.values_list("pk", "result", "amount"))

    for order, stock in ((accepted, 7), (paid, 10)):
        response = api(api_client, "post", f"/api/admin/orders/{order['order_id']}/cancel/", admin_token)
        assert response.status_code == 200
        assert body(response)["status"] == "cancelled" and body(response)["cancelled_at"] is not None
        assert _stock(unit) == stock
    assert list(PaymentRecord.objects.values_list("pk", "result", "amount")) == records

    seen = body(api(api_client, "get", f"/api/orders/{paid['order_id']}/", token))
    assert seen["status"] == "cancelled" and seen["status_history"][-1]["to_status"] == "cancelled"
    assert seen["status_history"][-1]["actor_user_type"] == "admin"
    assert "actor_user_id" not in seen["status_history"][-1]
    assert seen["can_pay"] is False and seen["can_cancel"] is False


# trace: FR-031, FR-034, FR-043, FR-044, FR-045, ADDR-004
def test_it_037_invalid_transitions_matrix(api_client, buyer, admin, bearer, catalog):
    """IT-037 注文状態の不正な遷移の網羅（Web API）。"""
    from orders.models import Order, OrderStatusHistory, PaymentRecord

    unit = catalog.stock_unit(stock=50)
    token, admin_token = bearer(buyer), bearer(admin)
    states = {}
    for name in ("accepted", "paid", "shipped", "delivered", "cancelled"):
        order = order_of(api_client, token, [(unit, 1)])
        oid = order["order_id"]
        if name in ("paid", "shipped", "delivered"):
            pay(api_client, token, oid)
        if name in ("shipped", "delivered"):
            api(api_client, "post", f"/api/admin/orders/{oid}/ship/", admin_token, {})
        if name == "delivered":
            api(api_client, "post", f"/api/admin/orders/{oid}/deliver/", admin_token)
        if name == "cancelled":
            api(api_client, "post", f"/api/orders/{oid}/cancel/", token)
        states[name] = oid
    snapshot = (
        list(Order.objects.order_by("pk").values()),
        _stock(unit),
        OrderStatusHistory.objects.count(),
        PaymentRecord.objects.count(),
    )

    def operations(oid):
        return {
            "pay": lambda: pay(api_client, token, oid),
            "buyer_cancel": lambda: api(api_client, "post", f"/api/orders/{oid}/cancel/", token),
            "admin_cancel": lambda: api(api_client, "post", f"/api/admin/orders/{oid}/cancel/", admin_token),
            "ship": lambda: api(api_client, "post", f"/api/admin/orders/{oid}/ship/", admin_token, {}),
            "deliver": lambda: api(api_client, "post", f"/api/admin/orders/{oid}/deliver/", admin_token),
        }

    forbidden = {
        "accepted": ("ship", "deliver"),
        "paid": ("deliver", "pay"),
        "shipped": ("ship", "pay", "buyer_cancel", "admin_cancel"),
        "delivered": ("pay", "buyer_cancel", "admin_cancel", "ship", "deliver"),
        "cancelled": ("pay", "buyer_cancel", "admin_cancel", "ship", "deliver"),
    }
    for state, ops in forbidden.items():
        actions = operations(states[state])
        for op in ops:
            response = actions[op]()
            assert response.status_code == 422, (state, op, response.content)
            err = error_of(response)
            assert err["reason"] == "invalid_status" and err["values"]["current_status"] == state, (state, op)
    assert snapshot == (
        list(Order.objects.order_by("pk").values()),
        _stock(unit),
        OrderStatusHistory.objects.count(),
        PaymentRecord.objects.count(),
    )


# trace: FR-041, FR-042, FR-043, FR-044, FR-045, ADDR-012, ADDR-004
def test_it_038_web_admin_order_operations(api_client, web, buyer, admin, bearer, catalog):
    """IT-038 管理画面での注文一覧→詳細→出荷→配達完了、キャンセル。"""
    unit = catalog.stock_unit(stock=10)
    token = bearer(buyer)
    first = order_of(api_client, token, [(unit, 1)])
    second = order_of(api_client, token, [(unit, 2)])
    pay(api_client, token, first["order_id"])
    pay(api_client, token, second["order_id"])
    client = web()
    client.force_login(admin, backend="accounts.backends.SessionUserBackend")

    listing = text(client.get("/manage/orders/"))
    assert first["order_number"] in listing and second["order_number"] in listing and "支払済" in listing

    path = f"/manage/orders/{first['order_id']}/"
    detail = text(client.get(path))
    assert buyer.email in detail and buyer.name in detail and "承認" in detail and "注文受付" in detail
    fields = form_fields(detail, f"{path}ship/")
    fields["tracking_number"] = "TRK-WEB-1"
    shipped = client.post(f"{path}ship/", fields)
    assert shipped.status_code == 302 and shipped["Location"] == path
    detail = text(client.get(path))
    assert "出荷登録しました。" in detail and "出荷済" in detail and "TRK-WEB-1" in detail

    fields = form_fields(detail, f"{path}deliver/")
    delivered = client.post(f"{path}deliver/", fields)
    assert delivered.status_code == 302
    detail = text(client.get(path))
    assert "配達完了を登録しました。" in detail and "配達完了" in detail

    other = f"/manage/orders/{second['order_id']}/"
    fields = form_fields(text(client.get(other)), f"{other}cancel/")
    cancelled = client.post(f"{other}cancel/", fields)
    assert cancelled.status_code == 302
    page = text(client.get(other))
    assert "注文をキャンセルしました" in page and "キャンセル済" in page
    assert _stock(unit) == 9
