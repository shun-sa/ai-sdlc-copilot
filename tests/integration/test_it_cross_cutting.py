# trace: FR-001, FR-002, FR-020, FR-021, FR-024, FR-030, FR-031, FR-033, FR-034, FR-040
# trace: FR-042, FR-043, NFR-SC-10
# trace: ADDR-003, ADDR-011
"""共通エラー応答・判定順序・システムエラーの結合試験（IT-AI-INIT-156〜159）。

検証対象の連携は 共通例外ハンドラ → API エラー応答、各APIの判定順序、
トランザクション → PostgreSQL（異常終了時のロールバック）。

期待結果は Steering 6章「Error Response」（応答形式）・7.1（判定順序）、提供済みAPI契約 6.2
（エラーコードとHTTPステータスの対応）、ERR-01〜ERR-08、CMN-14/CMN-21、NFR-SC-10
（内部情報を返さない）、ADDR-011（例外写像）から導出する。
"""

from __future__ import annotations

import datetime as dt

import pytest

from carts import services as cart_services
from catalog.models import Item, StockUnit
from common import timeutils
from orders.models import PurchaseOrder
from payments import services as payment_services
from payments.gateway import PaymentGatewayError

pytestmark = pytest.mark.django_db

SHIPPING = {
    "recipient_name": "結合 受取人",
    "postal_code": "1234567",
    "prefecture_code": "13",
    "address_line1": "千代田区1-1-1",
    "address_line2": "結合ビル101",
    "phone_number": "09012345678",
}


# trace: FR-030
def place_order(client, f, *, price: int = 1000, quantity: int = 1) -> dict:
    """注文受付の注文を1件作る（試験前提データの準備）。"""
    unit = f.sellable(price=price, quantity=quantity + 10)
    client.post("/api/cart/lines", {"stock_unit_id": unit.pk, "quantity": quantity}, format="json")
    response = client.post("/api/checkout", SHIPPING, format="json")
    assert response.status_code == 201
    return response.json()


# trace: FR-001, FR-020, FR-021, FR-033, FR-040, ADDR-011, NFR-SC-10
def test_it_ai_init_156_error_response_uses_common_envelope(api, api_as, buyer, f):
    """IT-AI-INIT-156 / COV-142：エラー応答は error 封筒の code/message/details/context 形式で返る。"""
    client = api_as(buyer)
    unit = f.sellable(price=1000, quantity=1)

    responses = {
        "VALIDATION_ERROR": api.post("/api/auth/register", {"email": "bad"}, format="json"),
        "AUTHENTICATION_REQUIRED": api.get("/api/cart"),
        "PERMISSION_DENIED": client.get("/api/admin/stock-units"),
        "NOT_FOUND": client.get("/api/purchase-orders/999999"),
        "INSUFFICIENT_STOCK": client.post(
            "/api/cart/lines", {"stock_unit_id": unit.pk, "quantity": 5}, format="json"
        ),
    }

    for code, response in responses.items():
        body = response.json()

        assert set(body) == {"error"}, code
        error = body["error"]
        assert set(error) == {"code", "message", "details", "context"}, code
        assert error["code"] == code
        assert isinstance(error["message"], str) and error["message"].strip()
        assert isinstance(error["details"], list)
        assert isinstance(error["context"], dict)
        for detail in error["details"]:
            assert set(detail) == {"field", "reason"}, code
        for forbidden in ("Traceback", "SELECT", "psycopg", "File \""):
            assert forbidden not in str(body), code

    assert responses["AUTHENTICATION_REQUIRED"].json()["error"]["details"] == []
    assert responses["AUTHENTICATION_REQUIRED"].json()["error"]["context"] == {}
    assert responses["VALIDATION_ERROR"].json()["error"]["context"] == {}
    assert responses["INSUFFICIENT_STOCK"].json()["error"]["details"] == []


# trace: FR-001, FR-002, FR-020, FR-021, FR-024, FR-030, FR-031, FR-033, FR-040, FR-042, ADDR-011
def test_it_ai_init_157_error_codes_map_to_http_status(
    api, api_as, buyer, other_buyer, admin_user, f, monkeypatch, err
):
    """IT-AI-INIT-157 / COV-143：エラーコードとHTTPステータスの対応が提供済みAPI契約どおりである。"""
    client = api_as(buyer)
    observed: dict[str, int] = {}

    def record(response) -> None:
        observed[err.code(response)] = response.status_code

    f.user(email="dup-status@example.test")
    record(
        api.post(
            "/api/auth/register",
            {
                "email": "dup-status@example.test",
                "password": "Passw0rdA",
                "password_confirmation": "Passw0rdA",
                "full_name": "重複 太郎",
            },
            format="json",
        )
    )
    record(api.post("/api/auth/register", {"email": "bad"}, format="json"))
    record(api.post("/api/auth/login", {"email": "none@example.test", "password": "Passw0rdA"}, format="json"))
    record(api.get("/api/cart"))
    record(client.get("/api/admin/stock-units"))
    record(client.get("/api/purchase-orders/999999"))

    limit_unit = f.sellable(price=1000, quantity=50)
    client.post("/api/cart/lines", {"stock_unit_id": limit_unit.pk, "quantity": 10}, format="json")
    record(client.post("/api/cart/lines", {"stock_unit_id": limit_unit.pk, "quantity": 1}, format="json"))
    short_unit = f.sellable(price=1000, quantity=1)
    record(client.post("/api/cart/lines", {"stock_unit_id": short_unit.pk, "quantity": 2}, format="json"))

    f.coupon(code="STATUSCPN1", discount_value=100)
    f.coupon(code="STATUSCPN2", discount_value=100)
    f.coupon(code="MINCPN1", discount_value=100, min_spend=1000000)
    now = timeutils.now()
    f.coupon(
        code="PASTCPN1",
        discount_value=100,
        valid_from=now - dt.timedelta(days=10),
        valid_until=now - dt.timedelta(days=1),
    )
    f.coupon(
        code="FUTURECPN1",
        discount_value=100,
        valid_from=now + dt.timedelta(days=1),
        valid_until=now + dt.timedelta(days=10),
    )
    record(client.post("/api/cart/apply-coupon", {"code": "NOTEXIST99"}, format="json"))
    record(client.post("/api/cart/apply-coupon", {"code": "PASTCPN1"}, format="json"))
    record(client.post("/api/cart/apply-coupon", {"code": "FUTURECPN1"}, format="json"))
    record(client.post("/api/cart/apply-coupon", {"code": "MINCPN1"}, format="json"))
    client.post("/api/cart/apply-coupon", {"code": "STATUSCPN1"}, format="json")
    record(client.post("/api/cart/apply-coupon", {"code": "STATUSCPN2"}, format="json"))
    client.post("/api/cart/remove-coupon", format="json")

    hidden_unit = f.sellable(price=1000, quantity=10)
    client.post("/api/cart/lines", {"stock_unit_id": hidden_unit.pk, "quantity": 1}, format="json")
    Item.objects.filter(pk=hidden_unit.item_id).update(is_public=False)
    record(client.post("/api/checkout", SHIPPING, format="json"))

    empty_client = api_as(other_buyer)
    empty_client.get("/api/cart")
    record(empty_client.post("/api/checkout", SHIPPING, format="json"))

    order = place_order(empty_client, f)
    order_id = order["purchase_order_id"]
    record(
        empty_client.post(
            f"/api/purchase-orders/{order_id}/pay", {"mock_result": "decline"}, format="json"
        )
    )
    empty_client.post(f"/api/purchase-orders/{order_id}/pay", {"mock_result": "approve"}, format="json")
    record(empty_client.post(f"/api/purchase-orders/{order_id}/pay", {"mock_result": "approve"}, format="json"))

    gateway_order = place_order(empty_client, f)

    def failing_gateway():
        class Failing:
            def authorize(self, request, *, timeout_seconds):
                raise PaymentGatewayError("stub")

        return Failing()

    monkeypatch.setattr(payment_services, "get_payment_gateway", failing_gateway)
    record(
        empty_client.post(
            f"/api/purchase-orders/{gateway_order['purchase_order_id']}/pay",
            {"mock_result": "approve"},
            format="json",
        )
    )
    monkeypatch.undo()

    def boom(*args, **kwargs):
        raise RuntimeError("unexpected failure")

    monkeypatch.setattr(cart_services, "calculate_amounts", boom)
    record(api_as(admin_user).get("/api/admin/purchase-orders/999999"))
    internal_client = api_as(buyer)
    record(internal_client.get("/api/cart"))
    monkeypatch.undo()

    assert observed == {
        "VALIDATION_ERROR": 400,
        "EMAIL_ALREADY_REGISTERED": 409,
        "QUANTITY_LIMIT_EXCEEDED": 409,
        "INSUFFICIENT_STOCK": 409,
        "ITEM_NOT_AVAILABLE": 409,
        "CART_EMPTY": 409,
        "COUPON_ALREADY_APPLIED": 409,
        "COUPON_NOT_FOUND": 409,
        "COUPON_NOT_YET_VALID": 409,
        "COUPON_EXPIRED": 409,
        "COUPON_MIN_SPEND_NOT_MET": 409,
        "INVALID_STATUS_TRANSITION": 409,
        "PAYMENT_DECLINED": 409,
        "PERMISSION_DENIED": 403,
        "AUTHENTICATION_REQUIRED": 401,
        "INVALID_CREDENTIALS": 401,
        "NOT_FOUND": 404,
        "PAYMENT_SERVICE_ERROR": 502,
        "INTERNAL_ERROR": 500,
    }


# trace: FR-020, FR-021, FR-030, FR-031, FR-034, FR-043, ADDR-011
def test_it_ai_init_158_error_precedence_is_consistent(
    api, api_as, buyer, other_buyer, admin_user, f, err
):
    """IT-AI-INIT-158 / COV-144：認証→権限→入力→対象→状態→業務の順に先に該当したエラーのみ返る（CMN-14）。"""
    client = api_as(buyer)
    admin_client = api_as(admin_user)
    other_client = api_as(other_buyer)

    # ①認証（未ログイン＋不正入力）
    unauthenticated = api.post("/api/cart/lines", {"stock_unit_id": "abc", "quantity": -1}, format="json")
    assert unauthenticated.status_code == 401
    assert err.code(unauthenticated) == "AUTHENTICATION_REQUIRED"

    # ②権限（管理者トークン＋不正入力）
    forbidden = admin_client.post("/api/cart/lines", {"stock_unit_id": "abc", "quantity": -1}, format="json")
    assert forbidden.status_code == 403
    assert err.code(forbidden) == "PERMISSION_DENIED"

    # ③入力（不正入力＋存在しない対象）
    invalid_input = client.post("/api/cart/lines", {"stock_unit_id": 999999, "quantity": 0}, format="json")
    assert invalid_input.status_code == 400
    assert err.code(invalid_input) == "VALIDATION_ERROR"

    # ④対象（存在しない対象＋状態不正になり得る操作）
    others_shipped = place_order(other_client, f)
    other_client.post(
        f"/api/purchase-orders/{others_shipped['purchase_order_id']}/pay", {}, format="json"
    )
    admin_client.post(
        f"/api/admin/purchase-orders/{others_shipped['purchase_order_id']}/ship", {}, format="json"
    )
    not_found = client.post(
        f"/api/purchase-orders/{others_shipped['purchase_order_id']}/cancel", {}, format="json"
    )
    assert not_found.status_code == 404
    assert err.code(not_found) == "NOT_FOUND"

    # ⑤状態（自分の出荷済注文のキャンセル）
    own = place_order(client, f)
    client.post(f"/api/purchase-orders/{own['purchase_order_id']}/pay", {}, format="json")
    admin_client.post(f"/api/admin/purchase-orders/{own['purchase_order_id']}/ship", {}, format="json")
    invalid_status = client.post(
        f"/api/purchase-orders/{own['purchase_order_id']}/cancel", {}, format="json"
    )
    assert invalid_status.status_code == 409
    assert err.code(invalid_status) == "INVALID_STATUS_TRANSITION"

    # ⑥業務（状態は正しいが業務ルールに反する）
    unit = f.sellable(price=1000, quantity=1)
    client.post("/api/cart/lines", {"stock_unit_id": unit.pk, "quantity": 1}, format="json")
    StockUnit.objects.filter(pk=unit.pk).update(quantity=0)
    business = client.post("/api/checkout", SHIPPING, format="json")
    assert business.status_code == 409
    assert err.code(business) == "INSUFFICIENT_STOCK"


# trace: FR-021, FR-030, ADDR-011, NFR-SC-10
def test_it_ai_init_159_internal_error_is_hidden_and_rolled_back(
    api_as, buyer, f, monkeypatch, err
):
    """IT-AI-INIT-159 / COV-148：未処理例外は内部情報なしのシステムエラーとし、データ変更を残さない（CMN-21）。"""
    client = api_as(buyer)
    unit = f.sellable(price=1000, quantity=10)
    client.post("/api/cart/lines", {"stock_unit_id": unit.pk, "quantity": 2}, format="json")

    def boom(*args, **kwargs):
        raise RuntimeError("unexpected failure in service layer")

    monkeypatch.setattr(cart_services, "calculate_amounts", boom)

    response = client.post("/api/checkout", SHIPPING, format="json")

    assert response.status_code == 500
    assert err.code(response) == "INTERNAL_ERROR"
    body = str(response.json())
    assert "unexpected failure in service layer" not in body
    assert "Traceback" not in body
    assert "SELECT" not in body
    assert not PurchaseOrder.objects.exists()
    unit.refresh_from_db()
    assert unit.quantity == 10
    monkeypatch.undo()
    assert client.get("/api/cart").json()["lines"][0]["quantity"] == 2
