# trace: FR-002, FR-012, FR-021, FR-030, FR-031, FR-043, FR-044, FR-060
# trace: NFR-OM-11, NFR-OM-18, NFR-SC-24, NFR-EN-05, NFR-US-10, NFR-PF-17
# trace: ADDR-002, ADDR-004, ADDR-005, ADDR-006, ADDR-008, ADDR-010, ADDR-011, ADDR-012, ADDR-013
"""結合試験：AI GAP_FILL（画面・決済連携・採番・削除指定の連携。Revision 2 の Required Coverage）。

GF-013〜GF-015・GF-017・GF-018・GF-034・GF-038（origin=AI_GENERATED、generation_stage=GAP_FILL）。
AI INITIAL は変更しない。期待結果は AC-UC-003-018・AC-UC-004-024・AC-UC-007-016・AC-UC-006-022・AC-UC-013-004、
NFR-OM-11・NFR-OM-18・NFR-SC-24・NFR-EN-05・NFR-US-10・NFR-PF-17、ADDR-002（削除指定時のログイン状態）・
ADDR-004（送信トークン）・ADDR-005（欠番・巻き戻し禁止）・ADDR-006（識別子の再利用禁止）・ADDR-008（送信項目・境界）・
ADDR-013（要求の識別子・LOG-06）から導出する。試験データは架空の値だけで作る。
"""

import copy
import dataclasses
import inspect
import json
import re
import socket
from datetime import datetime
from urllib.parse import parse_qs, urlparse

import pytest
from django.core.management import execute_from_command_line

from tests.integration._helpers import (
    ADDRESS,
    JST,
    PASSWORD,
    add_item,
    api,
    body,
    error_of,
    form_fields,
    install_recording_gateway,
    order_of,
    pay,
    place,
    text,
)

pytestmark = pytest.mark.django_db

UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
SUBSTITUTE_REF = "MOCK-SUBST00000000001"


# trace: FR-002, FR-012, ADDR-002, ADDR-012
def _web_login(client, email, password=PASSWORD, next_url=None):
    page = client.get("/login/" if next_url is None else f"/login/?next={next_url}")
    fields = form_fields(text(page), "/login/")
    fields.update({"email": email, "password": password})
    return client.post("/login/", fields)


# trace: FR-012, FR-021, FR-002, ADDR-002, ADDR-012
def test_gf_013_visitor_cart_add_login_return(web, buyer, catalog):
    """GF-013 来訪者の「カートに入れる」→ログイン画面→ログイン後に商品詳細へ戻り、カートは不変。"""
    from carts.models import Cart, CartItem
    from catalog.models import StockUnit

    product = catalog.product("ステンレスマグ")
    unit = catalog.stock_unit(product, price=1500, stock=20, variant_name="ブルー")
    carts_before, items_before = Cart.objects.count(), CartItem.objects.count()
    detail_path = f"/products/{product.pk}/"

    client = web()
    detail = text(client.get(detail_path))
    fields = form_fields(detail, "/cart/items/add/")
    fields.update({"stock_unit_id": str(unit.pk), "quantity": "1"})
    response = client.post("/cart/items/add/", fields)
    assert response.status_code == 302
    location = urlparse(response["Location"])
    query = parse_qs(location.query)
    assert location.path == "/login/" and query.get("required") == ["1"] and query.get("next") == [detail_path]
    assert (Cart.objects.count(), CartItem.objects.count()) == (carts_before, items_before)
    assert StockUnit.objects.get(pk=unit.pk).stock_quantity == 20

    login_page = text(client.get(response["Location"]))
    assert "ログインが必要です" in login_page
    login_fields = form_fields(login_page, "/login/")
    assert login_fields["next"] == detail_path
    login_fields.update({"email": buyer.email, "password": PASSWORD})
    back = client.post("/login/", login_fields)
    assert back.status_code == 302 and back["Location"] == detail_path
    page = client.get(detail_path)
    html = text(page)
    assert page.status_code == 200 and "<h1>ステンレスマグ</h1>" in html
    assert "カート（0点）" in html
    assert CartItem.objects.filter(cart__buyer=buyer).count() == 0
    assert StockUnit.objects.get(pk=unit.pk).stock_quantity == 20


# trace: NFR-OM-18, NFR-OM-11, FR-031, ADDR-008, ADDR-011, ADDR-013
def test_gf_014_payment_request_id_trace(api_client, buyer, bearer, catalog, app_logs, set_state):
    """GF-014 支払要求の要求の識別子で LOG-01〜LOG-03・LOG-06 を漏れなく抽出（NFR-OM-18）。"""
    from orders.models import PaymentRecord

    unit = catalog.stock_unit(price=2500, stock=10)
    token = bearer(buyer)
    order = order_of(api_client, token, [(unit, 2)])
    oid, number = order["order_id"], order["order_number"]

    app_logs.lines.clear()
    paid = pay(api_client, token, oid, "approved")
    assert paid.status_code == 200
    rid = paid["X-Request-ID"]
    assert UUID.match(rid)
    records = app_logs.records()
    assert records and all(r["request_id"] == rid for r in records), records
    assert {r["log_type"] for r in records} == {"LOG-01", "LOG-03", "LOG-06"}
    for record in records:
        assert {"timestamp", "level", "log_type", "request_id"} <= set(record)
        assert datetime.fromisoformat(record["timestamp"]).utcoffset() == JST.utcoffset(datetime(2027, 1, 1))
    operations = [r for r in records if r["log_type"] == "LOG-01"]
    assert [r["event"] for r in operations] == ["start", "end"] and operations[-1]["result"] == "success"
    assert all(r["user_id"] == buyer.pk for r in operations)
    access = [r for r in records if r["log_type"] == "LOG-03"]
    assert len(access) == 1
    assert (access[0]["method"], access[0]["path"], access[0]["status"], access[0]["user_id"]) == (
        "POST",
        f"/api/orders/{oid}/payment/",
        200,
        buyer.pk,
    )
    assert isinstance(access[0]["duration_ms"], int) and access[0]["duration_ms"] >= 0
    integration = [r for r in records if r["log_type"] == "LOG-06"]
    assert [r["phase"] for r in integration] == ["request", "response"]
    for r in integration:
        assert (r["order_number"], r["amount"], r["currency"]) == (number, 5500, "JPY")
    record = PaymentRecord.objects.get(order_id=oid)
    assert integration[1]["result"] == "approved" and integration[1]["transaction_ref"] == record.transaction_ref
    assert isinstance(integration[1]["duration_ms"], int)
    dump = "\n".join(app_logs.lines)
    for secret in (buyer.email, buyer.name, token.split()[1], ADDRESS["recipient_name"], ADDRESS["phone_number"]):
        assert secret not in dump, secret

    failing = order_of(api_client, token, [(unit, 1)])
    set_state(payment_mode="connection_error")
    app_logs.lines.clear()
    failed = pay(api_client, token, failing["order_id"], "approved")
    assert failed.status_code == 502 and error_of(failed)["type"] == "integration_error"
    rid2 = failed["X-Request-ID"]
    records = app_logs.records()
    assert records and all(r["request_id"] == rid2 for r in records), records
    assert {r["log_type"] for r in records} == {"LOG-01", "LOG-02", "LOG-03", "LOG-06"}
    error = next(r for r in records if r["log_type"] == "LOG-02")
    assert error["error_type"] == "integration_error" and error["exception_class"] and error["location"]
    response = [r for r in records if r["log_type"] == "LOG-06" and r["phase"] == "response"]
    assert len(response) == 1 and response[0]["result"] == "integration_error"


# trace: FR-031, NFR-SC-24, NFR-EN-05, ADDR-008
def test_gf_015_payment_request_contents_no_external(api_client, buyer, bearer, catalog, monkeypatch):
    """GF-015 決済サービス（模擬）が受けた決済要求の内容と外部通信0件（AC-UC-007-016）。"""
    from orders.models import PaymentRecord

    recorder = install_recording_gateway(monkeypatch)
    attempts = []
    real_connect, real_connect_ex = socket.socket.connect, socket.socket.connect_ex
    real_create = socket.create_connection

    def record_connect(sock, address):
        attempts.append(address)
        return real_connect(sock, address)

    def record_connect_ex(sock, address):
        attempts.append(address)
        return real_connect_ex(sock, address)

    def record_create(address, *args, **kwargs):
        attempts.append(address)
        return real_create(address, *args, **kwargs)

    unit = catalog.stock_unit(price=2500, stock=10)
    token = bearer(buyer)
    order = order_of(api_client, token, [(unit, 2)], {**ADDRESS, "recipient_name": "決済 秘匿"})
    monkeypatch.setattr(socket.socket, "connect", record_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", record_connect_ex)
    monkeypatch.setattr(socket, "create_connection", record_create)
    paid = pay(api_client, token, order["order_id"], "approved")
    monkeypatch.undo()

    assert paid.status_code == 200
    assert len(recorder.requests) == 1
    sent = dataclasses.asdict(recorder.requests[0])
    assert sent == {
        "order_number": order["order_number"],
        "amount": 5500,
        "currency": "JPY",
        "mock_instruction": "approved",
    }
    assert order["amounts"]["total_amount"] == 5500
    dump = json.dumps(sent, ensure_ascii=False)
    for personal in (buyer.email, buyer.name, "決済 秘匿", ADDRESS["phone_number"], ADDRESS["address_line1"]):
        assert personal not in dump
    assert attempts == []
    assert len(recorder.durations) == 1 and recorder.durations[0] <= 1.0
    assert list(PaymentRecord.objects.filter(order_id=order["order_id"]).values_list("result", "amount")) == [
        ("approved", 5500)
    ]


# trace: FR-030, ADDR-005, ADDR-011
def test_gf_017_fault_order_number_gap(api_client, buyer, bearer, catalog, set_state):
    """GF-017 注文番号の払い出し後の障害で取り消された番号は欠番となり再使用されない（ADDR-005 DD-003）。"""
    from catalog.models import StockUnit
    from orders.models import Order

    unit = catalog.stock_unit(stock=10)
    token = bearer(buyer)
    first = order_of(api_client, token, [(unit, 1)])
    first_value = int(first["order_number"][3:])

    assert add_item(api_client, token, unit.pk, 1).status_code == 200
    set_state(order_fault_point="after_order_insert")
    failed = place(api_client, token)
    assert failed.status_code == 500 and error_of(failed)["type"] == "system_error"
    assert Order.objects.count() == 1 and StockUnit.objects.get(pk=unit.pk).stock_quantity == 9

    set_state(order_fault_point="none")
    second = place(api_client, token)
    assert second.status_code == 201
    second_value = int(body(second)["order_number"][3:])
    assert second_value == first_value + 2, (first_value, second_value)
    assert not Order.objects.filter(order_number=f"PO-{first_value + 1:08d}").exists()
    assert StockUnit.objects.get(pk=unit.pk).stock_quantity == 8


# trace: FR-060, ADDR-010
def _cli(capsys, *args):
    capsys.readouterr()
    code = 0
    try:
        execute_from_command_line(["manage.py", "load_initial_data", *args])
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
    captured = capsys.readouterr()
    return code, captured.out, captured.err


RESET_DEFINITION = {
    "users": [
        {"email": "reset.admin@example.test", "password": "Kanri01Pass", "name": "再投入 管理", "user_type": "admin"},
        {"email": "reset.buyer@example.test", "password": "Kounyu01Pass", "name": "再投入 購入", "user_type": "buyer"},
    ],
    "suppliers": [{"supplier_code": "SUP-RESET", "name": "再投入仕入先"}],
    "categories": [{"category_code": "reset-top", "name": "再投入分類"}],
    "products": [{"product_code": "RESET-P1", "name": "再投入商品", "category_codes": ["reset-top"]}],
    "stock_units": [
        {
            "sku": "RESET-P1-01",
            "product_code": "RESET-P1",
            "supplier_code": "SUP-RESET",
            "variant_name": "標準",
            "price_excluding_tax": 1000,
            "stock_quantity": 10,
        }
    ],
    "coupons": [
        {
            "coupon_code": "RESET-CPN",
            "name": "再投入クーポン",
            "discount_type": "fixed_amount",
            "discount_value": 100,
            "valid_from": "2026-01-01T00:00:00+09:00",
            "valid_to": "2099-12-31T23:59:59+09:00",
        }
    ],
}


# trace: FR-060, ADDR-005, ADDR-006
def _max_ids():
    from accounts.models import ApiLoginState, User
    from audit.models import AuditLog
    from carts.models import Cart, CartItem
    from catalog.models import Category, Product, ProductCategory, StockUnit, Supplier
    from orders.models import Order, OrderItem, OrderStatusHistory, PaymentRecord, ShippingAddress
    from promotions.models import Coupon

    models = (
        User,
        ApiLoginState,
        Supplier,
        Category,
        Product,
        ProductCategory,
        StockUnit,
        Coupon,
        Cart,
        CartItem,
        Order,
        OrderItem,
        ShippingAddress,
        PaymentRecord,
        OrderStatusHistory,
        AuditLog,
    )
    return {m.__name__: (m.objects.order_by("-pk").values_list("pk", flat=True).first() or 0) for m in models}


# trace: FR-060, ADDR-002, ADDR-005, ADDR-006, ADDR-010
@pytest.mark.django_db(transaction=True)
def test_gf_018_reset_no_rewind_and_web_session(api_client, web, buyer, catalog, make_coupon, tmp_path, capsys):
    """GF-018 --reset 後も注文番号・識別子を巻き戻さず再利用しない、削除前の画面のログイン状態も無効。"""
    from django.contrib.sessions.models import Session

    from accounts.models import ApiLoginState
    from catalog.models import StockUnit
    from orders.models import Order

    browser = web()
    assert _web_login(browser, buyer.email).status_code == 302
    assert browser.get("/cart/").status_code == 200
    session_key = browser.cookies["sessionid"].value
    assert Session.objects.filter(session_key=session_key).exists()

    login = body(api(api_client, "post", "/api/auth/login/", data={"email": buyer.email, "password": PASSWORD}))
    token = f"Bearer {login['token']}"
    make_coupon("OLD-CPN")
    unit = catalog.stock_unit(stock=10)
    old = order_of(api_client, token, [(unit, 1)])
    assert pay(api_client, token, old["order_id"], "approved").status_code == 200
    assert add_item(api_client, token, unit.pk, 1).status_code == 200
    before = _max_ids()
    old_number = int(old["order_number"][3:])

    path = tmp_path / "reset.json"
    path.write_text(json.dumps(RESET_DEFINITION, ensure_ascii=False), encoding="utf-8")
    code, out, err = _cli(capsys, str(path), "--reset")
    assert code == 0, err
    assert Order.objects.count() == 0 and ApiLoginState.objects.count() == 0
    assert not Session.objects.filter(session_key=session_key).exists()
    protected = browser.get("/cart/")
    assert protected.status_code == 302 and urlparse(protected["Location"]).path == "/login/"
    assert api(api_client, "get", "/api/auth/me/", token).status_code == 401

    loaded = _max_ids()
    for name in ("User", "Supplier", "Category", "Product", "ProductCategory", "StockUnit", "Coupon"):
        assert loaded[name] > before[name], (name, before[name], loaded[name])

    relogin = body(
        api(
            api_client,
            "post",
            "/api/auth/login/",
            data={"email": "reset.buyer@example.test", "password": "Kounyu01Pass"},
        )
    )
    new_token = f"Bearer {relogin['token']}"
    new_unit = StockUnit.objects.get(sku="RESET-P1-01")
    new_order = order_of(api_client, new_token, [(new_unit, 1)])
    assert pay(api_client, new_token, new_order["order_id"], "approved").status_code == 200
    assert int(new_order["order_number"][3:]) > old_number
    after = _max_ids()
    for name in (
        "ApiLoginState",
        "Cart",
        "CartItem",
        "Order",
        "OrderItem",
        "ShippingAddress",
        "PaymentRecord",
        "OrderStatusHistory",
        "AuditLog",
    ):
        assert after[name] > before[name], (name, before[name], after[name])


# trace: NFR-US-10, FR-030, FR-031, ADDR-004, ADDR-008, ADDR-012
def test_gf_034_double_submit_place_pay(api_client, web, buyer, bearer, catalog, monkeypatch):
    """GF-034 注文確定・支払を先着の応答後に同じ送信トークンで逐次に再送しても注文・決済記録は1件（NFR-US-10）。

    2回目は1回目の送信前に複製した Cookie・フォーム値を持つ別のクライアントから、1回目の応答を受け取った後に送る
    （使用済みトークンの判定経路）。処理中の同時再送（送信トークンのロック待ち）は GF-039〜GF-043 が確認する。
    否認後の新しい支払画面からの支払は新たな操作として受け付ける。
    """
    from orders.models import Order, PaymentRecord

    recorder = install_recording_gateway(monkeypatch)
    unit = catalog.stock_unit(price=1000, stock=10)
    token = bearer(buyer)
    assert add_item(api_client, token, unit.pk, 1).status_code == 200
    client = web()
    client.force_login(buyer, backend="accounts.backends.SessionUserBackend")

    fields = form_fields(text(client.get("/checkout/")), "/checkout/")
    fields.update(ADDRESS)
    repeated = web()
    repeated.cookies = copy.deepcopy(client.cookies)
    first = client.post("/checkout/", fields)
    second = repeated.post("/checkout/", fields)
    assert Order.objects.filter(buyer=buyer).count() == 1
    order = Order.objects.get(buyer=buyer)
    assert first.status_code == 302 and first["Location"] == f"/orders/{order.pk}/complete/"
    # 使用済みトークンの注文確定は再判定の結果（カートが空）をそのまま通知する（ADDR-004 DD-010・DD-013、AC-UC-006-021）
    assert second.status_code == 302 and second["Location"] == "/cart/"

    pay_path = f"/orders/{order.pk}/payment/"
    pay_fields = form_fields(text(client.get(pay_path)), pay_path)
    pay_fields["mock_instruction"] = "approved"
    repeated = web()
    repeated.cookies = copy.deepcopy(client.cookies)
    paid_first = client.post(pay_path, pay_fields)
    paid_second = repeated.post(pay_path, pay_fields)
    assert paid_first.status_code == 302 and paid_second.status_code == 302
    assert list(PaymentRecord.objects.filter(order=order).values_list("result", flat=True)) == ["approved"]
    assert [r.order_number for r in recorder.requests] == [order.order_number]

    assert add_item(api_client, token, unit.pk, 1).status_code == 200
    fields = form_fields(text(client.get("/checkout/")), "/checkout/")
    fields.update(ADDRESS)
    assert client.post("/checkout/", fields).status_code == 302
    second_order = Order.objects.filter(buyer=buyer).exclude(pk=order.pk).get()
    pay_path = f"/orders/{second_order.pk}/payment/"
    declined_fields = form_fields(text(client.get(pay_path)), pay_path)
    declined_fields["mock_instruction"] = "declined"
    client.post(pay_path, declined_fields)
    retry_fields = form_fields(text(client.get(pay_path)), pay_path)
    retry_fields["mock_instruction"] = "approved"
    assert client.post(pay_path, retry_fields).status_code == 302
    assert list(PaymentRecord.objects.filter(order=second_order).order_by("pk").values_list("result", flat=True)) == [
        "declined",
        "approved",
    ]
    assert [r.order_number for r in recorder.requests].count(second_order.order_number) == 2
    second_order.refresh_from_db()
    assert second_order.status == "paid"


# trace: NFR-PF-17, FR-031, FR-043, FR-044, ADDR-008
def test_gf_038_gateway_substitution(api_client, buyer, admin, bearer, catalog, make_coupon, monkeypatch):
    """GF-038 決済連携部分（ゲートウェイの実装）だけを差し替えても注文・在庫・金額・状態遷移の処理は変更なしで動く。"""
    from catalog.models import StockUnit
    from orders import services as order_services
    from orders.models import Order, OrderStatusHistory, PaymentRecord
    from payments import client as payment_client
    from payments.gateway import PaymentGateway

    class SubstituteGateway(PaymentGateway):
        """後続フェーズの実決済連携を想定した別実装（境界の型だけに依存）。"""

        def __init__(self):
            self.requests = []

        def prepare(self, request):
            self.requests.append(request)

            def send():
                return {
                    "result": "approved",
                    "transaction_ref": SUBSTITUTE_REF,
                    "processed_at": datetime(2027, 4, 10, 10, 0, 0, tzinfo=JST).isoformat(),
                }

            return send

    source = inspect.getsource(order_services)
    assert "payments.mock" not in source and "MockPaymentGateway" not in source

    substitute = SubstituteGateway()
    monkeypatch.setattr(payment_client, "get_gateway", lambda: substitute)
    make_coupon("SUB-10", discount_type="percentage", discount_value=10)
    first, second = catalog.stock_unit(price=1800, stock=10), catalog.stock_unit(price=700, stock=10)
    token, admin_token = bearer(buyer), bearer(admin)
    assert add_item(api_client, token, first.pk, 2).status_code == 200
    assert add_item(api_client, token, second.pk, 1).status_code == 200
    assert api(api_client, "post", "/api/cart/coupon/", token, {"coupon_code": "SUB-10"}).status_code == 200
    placed = place(api_client, token)
    assert placed.status_code == 201
    order = body(placed)
    amounts = order["amounts"]
    # FR-026：小計4,300円、10%引き430円、割引後3,870円（5,000円未満）→送料500円、消費税額 (3,870+500)×10% 切捨て 437円
    assert amounts == {
        "subtotal": 4300,
        "discount_amount": 430,
        "discounted_subtotal": 3870,
        "shipping_fee": 500,
        "tax_amount": 437,
        "total_amount": 4807,
    }

    paid = pay(api_client, token, order["order_id"], "approved")
    assert paid.status_code == 200 and body(paid)["status"] == "paid"
    assert [dataclasses.asdict(r) for r in substitute.requests] == [
        {
            "order_number": order["order_number"],
            "amount": amounts["total_amount"],
            "currency": "JPY",
            "mock_instruction": "approved",
        }
    ]
    record = PaymentRecord.objects.get(order_id=order["order_id"])
    assert (record.result, record.amount, record.transaction_ref) == ("approved", 4807, SUBSTITUTE_REF)
    stocks = (StockUnit.objects.get(pk=first.pk).stock_quantity, StockUnit.objects.get(pk=second.pk).stock_quantity)
    assert stocks == (8, 9)
    oid = order["order_id"]
    assert api(api_client, "post", f"/api/admin/orders/{oid}/ship/", admin_token, {}).status_code == 200
    assert api(api_client, "post", f"/api/admin/orders/{oid}/deliver/", admin_token).status_code == 200
    assert Order.objects.get(pk=oid).status == "delivered"
    assert list(OrderStatusHistory.objects.filter(order_id=oid).order_by("pk").values_list("to_status", flat=True)) == [
        "accepted",
        "paid",
        "shipped",
        "delivered",
    ]
