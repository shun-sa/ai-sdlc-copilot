# trace: FR-OUT-01, FR-OUT-02, FR-OUT-03, FR-OUT-04, FR-OUT-05, FR-OUT-06, FR-OUT-07, FR-OUT-08
# trace: FR-OUT-09, FR-OUT-10, FR-OUT-11, FR-OUT-12, FR-OUT-13, FR-OUT-14, FR-OUT-15, FR-OUT-16
# trace: NFR-SC-13, NFR-SC-14, NFR-SC-17, NFR-SC-27, NFR-SC-28, NFR-LG-04, NFR-LG-06
# trace: FR-001, FR-002, FR-004, FR-011, FR-012, FR-020, FR-021, FR-024, FR-030, FR-031
# trace: FR-032, FR-034, FR-040, FR-041, FR-043, FR-044
# trace: ADDR-001, ADDR-002, ADDR-006, ADDR-007, ADDR-008, ADDR-009
"""対象外機能（機能要件定義書 2.3 FR-OUT-01〜FR-OUT-16）が実装されていないことの結合試験。

期待結果は、機能要件定義書 2.3「対象外とする機能」の各行の「対象外とする機能」「理由」「代替手段・担当」と、
非機能要件定義書 8.1 の NFR-SC-13・NFR-SC-14・NFR-SC-17・NFR-SC-27・NFR-SC-28（いずれも
「該当なし」＝機能を設けない。根拠欄で FR-OUT-09・FR-OUT-11・FR-OUT-13 を参照）、
11章 NFR-LG-04（特定商取引法の表示は本システムの対象外）から導出する。

「実装されていないこと」は、該当する操作経路（Web API のルーティング・画面・モデル・外部連携）を
実際に通し、代替手段として定められた経路だけが動作することで確認する。
"""
import json
import re
import socket
from dataclasses import asdict
from datetime import timedelta

import pytest
from django.apps import apps
from django.core import mail
from django.db import models
from django.test import Client

from shop.common import timeutils
from shop.models import (
    AuditEventType,
    AuditLog,
    Cart,
    PaymentRecord,
    PaymentResult,
    PurchaseOrder,
    PurchaseOrderStatus,
    ShippingAddress,
    StockUnit,
    User,
)
from shop.payments import client as payment_client
from shop.payments import mock as payment_mock
from tests.integration import _helpers

pytestmark = pytest.mark.django_db

# 注文状態（CD-02）。返品・返金・部分出荷・分割配送の状態を持たない（FR-OUT-04）。
EXPECTED_ORDER_STATUSES = {"created", "paid", "shipped", "delivered", "cancelled"}

# 配送先（D-12）の保持項目。配送日時指定・配送業者の項目を持たない（FR-OUT-07）。
EXPECTED_SHIPPING_ADDRESS_FIELDS = {
    "purchase_order",
    "recipient_name",
    "postal_code",
    "prefecture_code",
    "address_line1",
    "address_line2",
    "phone_number",
}

FORM_TAG = re.compile(r"<form\b[^>]*>", re.I)
FORM_METHOD = re.compile(r'method="([^"]*)"', re.I)
FORM_ACTION = re.compile(r'action="([^"]*)"', re.I)


# trace: FR-OUT-01
def _block_external_network(monkeypatch):
    """外部ネットワークへの接続を遮断する（接続を試みた時点で失敗させる）。"""

    def refuse(*args, **kwargs):
        """接続要求を拒否する。"""
        raise AssertionError(f"外部ネットワークへ接続しようとした: {args[1:]}")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


# trace: FR-OUT-02
def _form_targets(html):
    """画面に含まれる <form> の (メソッド, 送信先) を返す。"""
    targets = []
    for tag in FORM_TAG.findall(html):
        method = FORM_METHOD.search(tag)
        action = FORM_ACTION.search(tag)
        targets.append(
            (
                (method.group(1) if method else "get").lower(),
                action.group(1) if action else "",
            )
        )
    return targets


# trace: FR-OUT-02, FR-OUT-03
def _master_counts():
    """マスタ（仕入先・商品分類・商品・在庫単位・クーポン）の件数を返す。"""
    return {
        name: apps.get_model("shop", name).objects.count()
        for name in ("Supplier", "Collection", "Item", "ItemCollection", "StockUnit", "Coupon")
    }


# trace: FR-030, FR-031
def _ordered(api, token, unit, quantity=2):
    """カートへ明細を追加して注文を1件確定し、注文IDを返す。"""
    added = api.post("/api/cart/lines", {"stock_unit_id": unit.stock_unit_id, "quantity": quantity}, token=token)
    assert added.status_code == 200, added.content
    created = api.post("/api/checkout", dict(_helpers.VALID_ADDRESS), token=token)
    assert created.status_code == 201, created.content
    return created.json()["purchase_order_id"]


# trace: FR-002
def _buyer(api, email="buyer@example.com"):
    """購入者を1件作成してログインし、認証トークンを返す。"""
    _helpers.make_user(email=email)
    return api.login(email)


# trace: FR-002
def _admin(api, email="admin@example.com"):
    """管理者を1件作成してログインし、認証トークンを返す。"""
    _helpers.make_admin(email=email)
    return api.login(email)


# trace: FR-OUT-01, FR-031, ADDR-009
@pytest.mark.case("IT-AI-GF-029")
def test_payment_is_completed_by_in_process_mock_without_external_service(api, monkeypatch):
    """支払は本システム内の模擬決済だけで完結し、実在の決済サービスへ接続しない（FR-OUT-01）。"""
    token = _buyer(api)
    _item, unit = _helpers.catalog()
    order_id = _ordered(api, token, unit)
    captured = {}
    original = payment_mock.MockPaymentGateway.authorize

    def capture(self, request):
        """決済ゲートウェイの実装と決済要求の項目を記録する。"""
        captured["gateway"] = type(self)
        captured["request"] = request
        return original(self, request)

    monkeypatch.setattr(payment_mock.MockPaymentGateway, "authorize", capture)
    _block_external_network(monkeypatch)

    paid = api.post(f"/api/purchase-orders/{order_id}/pay", {"mock_result": "approve"}, token=token)

    assert paid.status_code == 200, paid.content
    assert isinstance(payment_client.get_gateway(), payment_mock.MockPaymentGateway)
    assert captured["gateway"] is payment_mock.MockPaymentGateway
    # 決済要求は IF-01-DAT-01〜04 の4項目だけで、接続先・資格情報を持たない（代替手段：模擬決済）。
    assert set(asdict(captured["request"])) == {"order_number", "amount", "currency", "mock_result"}
    record = PaymentRecord.objects.get()
    assert record.result == PaymentResult.APPROVED
    assert record.transaction_ref.startswith("MOCK-")
    assert PurchaseOrder.objects.get(purchase_order_id=order_id).status == PurchaseOrderStatus.PAID


# trace: FR-OUT-02, ADDR-007
@pytest.mark.case("IT-AI-GF-030")
def test_master_maintenance_is_not_provided_by_api_or_screen(api):
    """商品・分類・仕入先・在庫単位・クーポンの登録・更新・削除の手段が無い（FR-OUT-02）。

    要件は「マスタ保守の手段を設けない」ことだけを定め、未対応の経路・メソッドに対する
    HTTP ステータスは要件・api-contract に規定が無い。このため期待結果は
    「成功応答（2xx）を返さないこと」と「マスタの件数・内容が変わらないこと」とする。
    """
    admin_token = _admin(api)
    supplier = _helpers.make_supplier()
    item = _helpers.make_item()
    unit = _helpers.make_stock_unit(item, supplier)
    _helpers.make_coupon()
    before = _master_counts()

    requests = [
        ("post", "/api/items", {"item_code": "ITEM-999", "name": "追加商品"}),
        ("patch", f"/api/items/{item.item_id}", {"name": "変更後"}),
        ("delete", f"/api/items/{item.item_id}", None),
        ("post", "/api/collections", {"collection_code": "new", "name": "追加分類"}),
        ("post", "/api/suppliers", {"supplier_code": "SUP-999", "name": "追加仕入先"}),
        ("post", "/api/stock-units", {"sku": "SKU-999", "price": 100, "quantity": 1}),
        ("patch", f"/api/stock-units/{unit.stock_unit_id}", {"price": 1}),
        ("post", "/api/coupons", {"code": "NEW1000", "discount_value": 1000}),
        ("post", "/api/admin/items", {"item_code": "ITEM-998", "name": "追加商品"}),
        ("post", "/api/admin/stock-units", {"sku": "SKU-998", "price": 100, "quantity": 1}),
        ("patch", f"/api/admin/stock-units/{unit.stock_unit_id}", {"price": 1}),
        ("post", "/api/admin/collections", {"collection_code": "new2", "name": "追加分類"}),
        ("post", "/api/admin/suppliers", {"supplier_code": "SUP-998", "name": "追加仕入先"}),
        ("post", "/api/admin/coupons", {"code": "NEW2000", "discount_value": 2000}),
    ]
    for method, path, body in requests:
        caller = getattr(api, method)
        response = caller(path, token=admin_token) if body is None else caller(path, body, token=admin_token)
        assert response.status_code >= 400, f"{method.upper()} {path} -> {response.status_code}"

    assert _master_counts() == before
    item.refresh_from_db()
    unit.refresh_from_db()
    assert item.name == "サンプル商品"
    assert unit.price == 1000
    # 管理者画面にもマスタ保守の送信先が無い（更新操作はログアウトのみ）。
    screen = Client()
    assert screen.post("/login", {"email": "admin@example.com", "password": _helpers.TEST_PASSWORD}).status_code == 302
    html = screen.get("/admin/stock-units").content.decode()
    assert [action for method, action in _form_targets(html) if method == "post"] == ["/logout"]


# trace: FR-OUT-03, FR-030, FR-031, FR-043, FR-044
@pytest.mark.case("IT-AI-GF-031")
def test_stock_replenishment_is_not_provided(api):
    """入荷・在庫補充を登録する手段が無く、在庫数量は購入導線以外で増えない（FR-OUT-03）。"""
    buyer_token = _buyer(api)
    admin_token = _admin(api)
    item, unit = _helpers.catalog(quantity=10)
    order_id = _ordered(api, buyer_token, unit, quantity=2)

    for method, path, body in [
        ("post", f"/api/admin/stock-units/{unit.stock_unit_id}/restock", {"quantity": 5}),
        ("patch", f"/api/admin/stock-units/{unit.stock_unit_id}", {"quantity": 99}),
        ("post", "/api/admin/inbound", {"sku": unit.sku, "quantity": 5}),
        ("post", f"/api/stock-units/{unit.stock_unit_id}/receive", {"quantity": 5}),
    ]:
        response = getattr(api, method)(path, body, token=admin_token)
        assert response.status_code >= 400, f"{method.upper()} {path} -> {response.status_code}"
        assert StockUnit.objects.get(stock_unit_id=unit.stock_unit_id).quantity == 8, path

    assert api.post(
        f"/api/purchase-orders/{order_id}/pay", {"mock_result": "approve"}, token=buyer_token
    ).status_code == 200
    assert api.post(
        f"/api/admin/purchase-orders/{order_id}/ship", {"tracking_number": "TRK-0001"}, token=admin_token
    ).status_code == 200
    assert api.post(f"/api/admin/purchase-orders/{order_id}/deliver", token=admin_token).status_code == 200

    # 出荷・配達完了を経ても在庫数量は引当後のまま（補充されない）。
    assert StockUnit.objects.get(stock_unit_id=unit.stock_unit_id).quantity == 8
    assert item.stock_units.count() == 1


# trace: FR-OUT-04, FR-030, FR-031, FR-043, FR-044, ADDR-001
@pytest.mark.case("IT-AI-GF-032")
def test_return_refund_and_partial_shipment_are_not_provided(api):
    """返品・返金・部分出荷・分割配送の状態も操作も持たない（FR-OUT-04）。"""
    assert set(PurchaseOrderStatus.values) == EXPECTED_ORDER_STATUSES

    buyer_token = _buyer(api)
    admin_token = _admin(api)
    supplier = _helpers.make_supplier()
    item = _helpers.make_item()
    first = _helpers.make_stock_unit(item, supplier, sku="SKU-001", price=1000, quantity=10)
    second = _helpers.make_stock_unit(item, supplier, sku="SKU-002", price=2000, quantity=10)
    for unit in (first, second):
        added = api.post("/api/cart/lines", {"stock_unit_id": unit.stock_unit_id, "quantity": 1}, token=buyer_token)
        assert added.status_code == 200, added.content
    created = api.post("/api/checkout", dict(_helpers.VALID_ADDRESS), token=buyer_token)
    assert created.status_code == 201, created.content
    order_id = created.json()["purchase_order_id"]
    assert api.post(
        f"/api/purchase-orders/{order_id}/pay", {"mock_result": "approve"}, token=buyer_token
    ).status_code == 200

    # 明細単位の出荷指定を送っても、注文単位で一括して出荷済となる（部分出荷・分割配送が無い）。
    shipped = api.post(
        f"/api/admin/purchase-orders/{order_id}/ship",
        {"tracking_number": "TRK-0001", "lines": [first.stock_unit_id], "shipped_quantity": 1},
        token=admin_token,
    )
    assert shipped.status_code == 200, shipped.content
    detail = api.get(f"/api/admin/purchase-orders/{order_id}", token=admin_token).json()
    assert detail["status"] == "shipped"
    assert len(detail["lines"]) == 2
    assert detail["tracking_number"] == "TRK-0001"
    assert api.post(f"/api/admin/purchase-orders/{order_id}/deliver", token=admin_token).status_code == 200

    for path in [
        f"/api/purchase-orders/{order_id}/return",
        f"/api/purchase-orders/{order_id}/refund",
        f"/api/admin/purchase-orders/{order_id}/return",
        f"/api/admin/purchase-orders/{order_id}/refund",
        f"/api/admin/purchase-orders/{order_id}/partial-ship",
    ]:
        assert api.post(path, {}, token=admin_token).status_code in (404, 405), path

    # 配達完了後のキャンセル（返金を伴う取消）も行えない。
    cancelled = api.post(f"/api/admin/purchase-orders/{order_id}/cancel", token=admin_token)
    assert cancelled.status_code == 409
    assert _helpers.error_code(cancelled) == "INVALID_STATUS_TRANSITION"
    assert [record.result for record in PaymentRecord.objects.all()] == [PaymentResult.APPROVED]


# trace: FR-OUT-05, FR-024, FR-030, NFR-LG-06, ADDR-007
@pytest.mark.case("IT-AI-GF-033")
def test_multiple_coupons_cannot_be_combined(api):
    """クーポンは1枚までで、併用・ポイント等の併用割引は行えない（FR-OUT-05）。"""
    token = _buyer(api)
    _item, unit = _helpers.catalog(price=3000, quantity=10)
    _helpers.make_coupon(code="SAVE1000", discount_value=1000)
    _helpers.make_coupon(code="SAVE500", name="500円割引", discount_value=500)
    assert api.post("/api/cart/lines", {"stock_unit_id": unit.stock_unit_id, "quantity": 1}, token=token).status_code == 200

    first = api.post("/api/cart/apply-coupon", {"code": "SAVE1000"}, token=token)
    second = api.post("/api/cart/apply-coupon", {"code": "SAVE500"}, token=token)

    assert first.status_code == 200, first.content
    assert second.status_code == 409
    assert _helpers.error_code(second) == "COUPON_ALREADY_APPLIED"
    cart = api.get("/api/cart", token=token).json()
    assert cart["coupon"]["code"] == "SAVE1000"
    assert cart["amounts"]["discount_amount"] == 1000
    assert Cart.objects.get().coupon.code == "SAVE1000"

    created = api.post("/api/checkout", dict(_helpers.VALID_ADDRESS), token=token)
    assert created.status_code == 201, created.content
    order = PurchaseOrder.objects.get()
    assert order.coupon_code == "SAVE1000"
    assert order.discount_amount == 1000


# trace: FR-OUT-06, FR-012, FR-030
@pytest.mark.case("IT-AI-GF-034")
def test_multi_currency_language_and_overseas_delivery_are_not_supported(api):
    """通貨は日本円、表示は日本語のみで、国外の配送先を受け付けない（FR-OUT-06）。"""
    token = _buyer(api)
    item, unit = _helpers.catalog(price=1000, quantity=10)

    default = api.get(f"/api/items/{item.item_id}")
    with_currency = api.get(f"/api/items/{item.item_id}", {"currency": "USD", "lang": "en"})
    assert default.status_code == 200
    assert with_currency.json() == default.json()
    assert default.json()["stock_units"][0]["price"] == 1000
    assert default.json()["stock_units"][0]["price_incl_tax"] == 1100

    screen = Client()
    response = screen.get("/", headers={"accept-language": "en-US,en;q=0.9"})
    html = response.content.decode()
    assert response.status_code == 200
    assert '<html lang="ja">' in html
    assert "商品一覧" in html
    assert "（税込）" in html

    assert api.post("/api/cart/lines", {"stock_unit_id": unit.stock_unit_id, "quantity": 1}, token=token).status_code == 200
    overseas = dict(_helpers.VALID_ADDRESS, prefecture_code="99")
    rejected = api.post("/api/checkout", overseas, token=token)
    assert rejected.status_code == 400
    assert _helpers.error_fields(rejected) == {"prefecture_code"}
    assert PurchaseOrder.objects.count() == 0


# trace: FR-OUT-07, FR-030, ADDR-001
@pytest.mark.case("IT-AI-GF-035")
def test_carrier_integration_address_check_and_regional_shipping_fee_are_absent(api):
    """配送業者連携・住所検証・配送日時指定・送料の地域別設定を持たない（FR-OUT-07）。"""
    assert {field.name for field in ShippingAddress._meta.get_fields()} == EXPECTED_SHIPPING_ADDRESS_FIELDS

    supplier = _helpers.make_supplier()
    item = _helpers.make_item()
    unit = _helpers.make_stock_unit(item, supplier, price=1000, quantity=10)
    totals = {}
    for email, prefecture in (("hokkaido@example.com", "01"), ("okinawa@example.com", "47")):
        token = _buyer(api, email=email)
        added = api.post("/api/cart/lines", {"stock_unit_id": unit.stock_unit_id, "quantity": 1}, token=token)
        assert added.status_code == 200, added.content
        address = dict(
            _helpers.VALID_ADDRESS,
            prefecture_code=prefecture,
            postal_code="9999999",
            address_line1="架空町9-9-9",
        )
        created = api.post(
            "/api/checkout",
            dict(address, delivery_date="2027-04-10", delivery_time_slot="am", carrier_code="XX"),
            token=token,
        )
        assert created.status_code == 201, created.content
        totals[prefecture] = created.json()["amounts"]

    # 送料は地域によらず同額（割引後小計5,000円未満は500円）。
    assert totals["01"]["shipping_fee"] == totals["47"]["shipping_fee"] == 500
    assert totals["01"]["total"] == totals["47"]["total"]
    # 配送日時指定・配送業者の指定は保存されない（存在しない住所でも受け付ける）。
    for address in ShippingAddress.objects.all():
        assert address.postal_code == "9999999"
        assert not hasattr(address, "delivery_date")


# trace: FR-OUT-08, FR-001, FR-030, FR-031, FR-034, FR-043
@pytest.mark.case("IT-AI-GF-036")
def test_no_notification_is_sent_to_users(api):
    """会員登録・注文・支払・出荷・キャンセルのいずれでも通知を送信しない（FR-OUT-08）。"""
    mail.outbox.clear()
    registered = api.post(
        "/api/auth/register",
        {
            "email": "new-buyer@example.com",
            "password": _helpers.TEST_PASSWORD,
            "password_confirmation": _helpers.TEST_PASSWORD,
            "full_name": "新規 購入者",
        },
    )
    assert registered.status_code == 201, registered.content
    token = api.login("new-buyer@example.com")
    admin_token = _admin(api)
    _item, unit = _helpers.catalog(quantity=10)
    paid_order = _ordered(api, token, unit, quantity=1)
    assert api.post(
        f"/api/purchase-orders/{paid_order}/pay", {"mock_result": "approve"}, token=token
    ).status_code == 200
    assert api.post(
        f"/api/admin/purchase-orders/{paid_order}/ship", {"tracking_number": "TRK-0002"}, token=admin_token
    ).status_code == 200
    cancelled_order = _ordered(api, token, unit, quantity=1)
    assert api.post(f"/api/purchase-orders/{cancelled_order}/cancel", token=token).status_code == 200

    assert mail.outbox == []


# trace: FR-OUT-09, NFR-SC-17, FR-001, ADDR-008
@pytest.mark.case("IT-AI-GF-037")
def test_profile_change_password_reset_and_withdrawal_are_not_provided(api):
    """会員情報の変更・パスワード再設定・退会の手段が無い（FR-OUT-09、NFR-SC-17）。"""
    token = _buyer(api)
    user = User.objects.get()
    before = (user.email, user.full_name, user.password_hash)

    for method, path, body in [
        ("patch", "/api/auth/me", {"full_name": "変更後"}),
        ("delete", "/api/auth/me", None),
        ("post", "/api/auth/password", {"password": "NewPassw0rd1"}),
        ("post", "/api/auth/password-reset", {"email": "buyer@example.com"}),
        ("post", "/api/auth/password-reset/confirm", {"token": "x", "password": "NewPassw0rd1"}),
        ("post", "/api/auth/withdraw", {}),
        ("delete", f"/api/users/{user.user_id}", None),
    ]:
        caller = getattr(api, method)
        response = caller(path, token=token) if body is None else caller(path, body, token=token)
        assert response.status_code >= 400, f"{method.upper()} {path} -> {response.status_code}"

    screen = Client()
    for path in ("/password-reset", "/account", "/withdraw"):
        assert screen.get(path).status_code == 404, path
    login_html = screen.get("/login").content.decode()
    register_html = screen.get("/register").content.decode()
    for word in ("パスワードを忘れ", "パスワード再設定", "退会"):
        assert word not in login_html, word
        assert word not in register_html, word

    user.refresh_from_db()
    assert (user.email, user.full_name, user.password_hash) == before
    assert User.objects.count() == 1


# trace: FR-OUT-10, FR-020, FR-030, ADDR-002
@pytest.mark.case("IT-AI-GF-038")
def test_guest_purchase_is_not_possible(api):
    """未ログインではカート・注文を利用できない（FR-OUT-10。カート・注文はログイン必須）。"""
    _item, unit = _helpers.catalog()

    unauthenticated = [
        api.get("/api/cart"),
        api.post("/api/cart/lines", {"stock_unit_id": unit.stock_unit_id, "quantity": 1}),
        api.post("/api/checkout", dict(_helpers.VALID_ADDRESS)),
        api.get("/api/purchase-orders"),
    ]
    for response in unauthenticated:
        assert response.status_code == 401
        assert _helpers.error_code(response) == "AUTHENTICATION_REQUIRED"

    screen = Client()
    for path in ("/cart", "/checkout"):
        response = screen.get(path)
        assert response.status_code == 302, path
        assert response["Location"].startswith("/login?next="), path
    posted = screen.post("/cart/lines", {"stock_unit_id": unit.stock_unit_id, "quantity": 1})
    assert posted.status_code == 302
    assert posted["Location"].startswith("/login?next=")

    assert Cart.objects.count() == 0
    assert PurchaseOrder.objects.count() == 0


# trace: FR-OUT-11, NFR-SC-14, FR-002, ADDR-002
@pytest.mark.case("IT-AI-GF-039")
def test_account_is_not_locked_after_repeated_login_failures(api):
    """認証失敗が続いてもアカウントロック・試行回数制限を行わない（FR-OUT-11、NFR-SC-14）。"""
    _helpers.make_user(email="buyer@example.com")

    for attempt in range(10):
        failed = api.post("/api/auth/login", {"email": "buyer@example.com", "password": "WrongPass1"})
        assert failed.status_code == 401, attempt
        assert _helpers.error_code(failed) == "INVALID_CREDENTIALS"

    succeeded = api.post("/api/auth/login", {"email": "buyer@example.com", "password": _helpers.TEST_PASSWORD})

    assert succeeded.status_code == 200, succeeded.content
    assert api.get("/api/auth/me", token=succeeded.json()["token"]).status_code == 200
    # 失敗は監査ログに残す（NFR-SC-22）が、ロック状態は作らない。
    assert AuditLog.objects.filter(event_type=AuditEventType.LOGIN_FAILURE).count() == 10
    assert AuditLog.objects.filter(event_type=AuditEventType.LOGIN_SUCCESS).count() == 1

    screen = Client()
    assert screen.post("/login", {"email": "buyer@example.com", "password": _helpers.TEST_PASSWORD}).status_code == 302


# trace: FR-OUT-12, FR-030, FR-031, ADDR-001
@pytest.mark.case("IT-AI-GF-040")
def test_unpaid_order_is_not_cancelled_automatically(api):
    """未払いの注文は時間が経過しても自動キャンセルされない（FR-OUT-12）。"""
    token = _buyer(api)
    _item, unit = _helpers.catalog(quantity=10)
    order_id = _ordered(api, token, unit, quantity=1)
    PurchaseOrder.objects.filter(purchase_order_id=order_id).update(
        ordered_at=timeutils.now() - timedelta(days=30)
    )

    detail = api.get(f"/api/purchase-orders/{order_id}", token=token)

    assert detail.status_code == 200, detail.content
    assert detail.json()["status"] == "created"
    assert detail.json()["can_pay"] is True
    assert PurchaseOrder.objects.filter(status=PurchaseOrderStatus.CANCELLED).count() == 0
    paid = api.post(f"/api/purchase-orders/{order_id}/pay", {"mock_result": "approve"}, token=token)
    assert paid.status_code == 200, paid.content
    assert PurchaseOrder.objects.get(purchase_order_id=order_id).status == PurchaseOrderStatus.PAID


# trace: FR-OUT-13, NFR-SC-28, FR-012, FR-001
@pytest.mark.case("IT-AI-GF-041")
def test_item_images_reviews_favorites_and_file_upload_are_absent(api):
    """商品画像・レビュー・お気に入り・おすすめ表示とファイル投稿の手段が無い（FR-OUT-13、NFR-SC-28）。"""
    token = _buyer(api)
    item, _unit = _helpers.catalog()

    detail = api.get(f"/api/items/{item.item_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert set(body) == {"item_id", "item_code", "name", "description", "collections", "stock_units"}
    serialized = json.dumps(body, ensure_ascii=False)
    for word in ("image", "review", "rating", "favorite", "recommend"):
        assert word not in serialized.lower(), word

    for method, path in [
        ("get", f"/api/items/{item.item_id}/reviews"),
        ("post", f"/api/items/{item.item_id}/reviews"),
        ("get", f"/api/items/{item.item_id}/image"),
        ("post", "/api/favorites"),
        ("get", "/api/recommendations"),
    ]:
        response = getattr(api, method)(path, token=token) if method == "get" else api.post(path, {}, token=token)
        assert response.status_code in (404, 405), path

    html = Client().get(f"/items/{item.item_id}").content.decode()
    assert "<img" not in html
    for word in ("レビュー", "お気に入り", "おすすめ"):
        assert word not in html, word

    # ファイルを保存する項目を持たない（アップロード機能が無い）。
    for model in apps.get_app_config("shop").get_models():
        for field in model._meta.get_fields():
            assert not isinstance(field, models.FileField), f"{model.__name__}.{field.name}"


# trace: FR-OUT-14, FR-011, FR-012
@pytest.mark.case("IT-AI-GF-042")
def test_no_smartphone_specific_screen_is_provided(api):
    """スマートフォン専用画面を持たず、PC向け画面を同一内容で返す（FR-OUT-14）。"""
    _helpers.catalog()
    screen = Client()
    pc_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0 Safari/537.36"
    mobile_agent = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148"

    pc = screen.get("/", headers={"user-agent": pc_agent})
    mobile = screen.get("/", headers={"user-agent": mobile_agent})

    assert pc.status_code == 200
    assert mobile.status_code == 200
    assert mobile.content == pc.content
    assert [template.name for template in mobile.templates] == [template.name for template in pc.templates]
    for path in ("/m", "/m/", "/sp", "/mobile"):
        assert screen.get(path, headers={"user-agent": mobile_agent}).status_code == 404, path


# trace: FR-OUT-15, FR-032, FR-040, FR-041
@pytest.mark.case("IT-AI-GF-043")
def test_file_export_of_lists_is_not_provided(api):
    """一覧の帳票（PDF・CSV を含むファイル出力）の手段が無い（FR-OUT-15）。"""
    buyer_token = _buyer(api)
    admin_token = _admin(api)
    _item, unit = _helpers.catalog(quantity=10)
    _ordered(api, buyer_token, unit, quantity=1)

    for path, token in [
        ("/api/items", None),
        ("/api/purchase-orders", buyer_token),
        ("/api/admin/purchase-orders", admin_token),
        ("/api/admin/stock-units", admin_token),
    ]:
        for query in ({}, {"format": "csv"}, {"export": "csv"}, {"format": "pdf"}, {"download": "1"}):
            response = api.get(path, query, token=token)
            content_type = response.headers.get("Content-Type", "")
            assert "csv" not in content_type and "pdf" not in content_type, f"{path} {query}"
            assert "attachment" not in response.headers.get("Content-Disposition", ""), f"{path} {query}"

    for path, token in [
        ("/api/admin/purchase-orders/export", admin_token),
        ("/api/purchase-orders/export", buyer_token),
        ("/api/admin/stock-units.csv", admin_token),
    ]:
        response = api.get(path, token=token)
        assert response.status_code >= 400, f"{path} -> {response.status_code}"
        assert "csv" not in response.headers.get("Content-Type", ""), path

    screen = Client()
    assert screen.post("/login", {"email": "admin@example.com", "password": _helpers.TEST_PASSWORD}).status_code == 302
    for path in ("/admin/purchase-orders", "/admin/stock-units"):
        response = screen.get(path)
        assert response.headers["Content-Type"].startswith("text/html"), path
        html = response.content.decode()
        for word in (".csv", ".pdf", "ダウンロード", "出力する"):
            assert word not in html, f"{path} {word}"


# trace: FR-OUT-16, NFR-LG-04
@pytest.mark.case("IT-AI-GF-044")
def test_specified_commercial_transactions_page_is_out_of_scope(api):
    """「特定商取引法に基づく表記」等の静的ページを本システムが持たない（FR-OUT-16、NFR-LG-04）。"""
    _helpers.catalog()
    screen = Client()

    for path in ("/legal", "/tokushoho", "/terms", "/privacy", "/company", "/about", "/law"):
        response = screen.get(path)
        assert response.status_code == 404, path
        assert "特定商取引" not in response.content.decode(), path

    for path in ("/", "/login", "/register"):
        html = screen.get(path).content.decode()
        for word in ("特定商取引", "/legal", "/tokushoho"):
            assert word not in html, f"{path} {word}"


# trace: NFR-SC-13, FR-002, FR-004, ADDR-002
@pytest.mark.case("IT-AI-GF-045")
def test_authentication_completes_with_single_factor(api):
    """認証はメールアドレスとパスワードの1段階で完了する（NFR-SC-13 多要素認証は該当なし）。"""
    _helpers.make_user(email="buyer@example.com")

    response = api.post("/api/auth/login", {"email": "buyer@example.com", "password": _helpers.TEST_PASSWORD})

    assert response.status_code == 200, response.content
    assert set(response.json()) == {"token", "expires_at", "user"}
    token = response.json()["token"]
    # 追加の確認手順（確認コードの入力等）を経ずにそのまま利用できる。
    assert api.get("/api/auth/me", token=token).status_code == 200

    screen = Client()
    logged_in = screen.post("/login", {"email": "buyer@example.com", "password": _helpers.TEST_PASSWORD})
    assert logged_in.status_code == 302
    assert logged_in["Location"] == "/"
    assert screen.get("/cart").status_code == 200


# trace: NFR-SC-27, FR-002, FR-011, FR-020
@pytest.mark.case("IT-AI-GF-046")
def test_request_rate_is_not_limited(api):
    """送信元単位のリクエスト数の制限を行わない（NFR-SC-27 は該当なし）。"""
    token = _buyer(api)
    _helpers.catalog()

    public_statuses = {api.get("/api/items").status_code for _ in range(60)}
    authenticated_statuses = {api.get("/api/cart", token=token).status_code for _ in range(30)}
    failed_login_statuses = {
        api.post("/api/auth/login", {"email": "buyer@example.com", "password": "WrongPass1"}).status_code
        for _ in range(20)
    }

    assert public_statuses == {200}
    assert authenticated_statuses == {200}
    assert failed_login_statuses == {401}
