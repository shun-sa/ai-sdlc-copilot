# trace: FR-030, FR-031, FR-034, FR-043, FR-044, NFR-SC-06, FR-OUT-01
# trace: ADDR-003, ADDR-009, ADDR-010
"""支払（模擬決済）の結合試験（IT-AI-INIT-104〜116）。

検証対象の連携は 注文Service → 決済サービス（模擬Gateway） → 決済記録(DB)、
トランザクション・同時実行制御 → PostgreSQL、画面 → Service → DB。

期待結果は FR-031（処理内容・例外・排他）、外部インターフェース要件 IF-01（決済要求の内容・
IF-01-EXC-01/02/04）、ST-PO-02、提供済みAPI契約 6.2（PAYMENT_DECLINED／PAYMENT_SERVICE_ERROR／
INVALID_STATUS_TRANSITION）、ADDR-009（決済要求はトランザクション外で1回だけ送信する）
から導出する。
"""

from __future__ import annotations

import socket
import time

import pytest
from rest_framework.test import APIClient

from orders.models import (
    PAYMENT_APPROVED,
    PAYMENT_DECLINED,
    PAYMENT_ERROR,
    STATUS_CANCELLED,
    STATUS_CREATED,
    STATUS_DELIVERED,
    STATUS_PAID,
    STATUS_SHIPPED,
    PaymentRecord,
    PurchaseOrder,
)
from payments import services as payment_services
from payments.gateway import PaymentGateway, PaymentResult

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
    assert (
        client.post(
            "/api/cart/lines", {"stock_unit_id": unit.pk, "quantity": quantity}, format="json"
        ).status_code
        == 200
    )
    response = client.post("/api/checkout", SHIPPING, format="json")
    assert response.status_code == 201
    return response.json()


# trace: FR-031, ADDR-009
class RecordingGateway(PaymentGateway):
    """決済要求の内容を記録する決済ゲートウェイ（模擬実装の差し替え）。"""

    def __init__(self, result: PaymentResult | None = None, delay: float = 0.0) -> None:
        self.requests: list = []
        self.result = result
        self.delay = delay

    def authorize(self, request, *, timeout_seconds: int) -> PaymentResult:
        self.requests.append(request)
        if self.delay:
            time.sleep(self.delay)
        if self.result is not None:
            return self.result
        from payments.mock import MockPaymentGateway

        return MockPaymentGateway().authorize(request, timeout_seconds=timeout_seconds)


# trace: FR-031, ADDR-009
def test_it_ai_init_104_approved_payment_marks_order_paid(api_as, buyer, f):
    """IT-AI-INIT-104 / COV-090：承認された支払は注文を支払済にし、決済記録と状態履歴を残す（ST-PO-02）。"""
    client = api_as(buyer)
    order = place_order(client, f)

    response = client.post(
        f"/api/purchase-orders/{order['purchase_order_id']}/pay",
        {"mock_result": "approve"},
        format="json",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == STATUS_PAID
    assert body["paid_at"] is not None
    assert body["can_pay"] is False

    record = PaymentRecord.objects.get(purchase_order_id=order["purchase_order_id"])
    assert record.result == PAYMENT_APPROVED
    assert record.amount == order["amounts"]["total"]
    assert record.transaction_ref
    history = [(row["from_status"], row["to_status"]) for row in body["status_history"]]
    assert history == [(None, STATUS_CREATED), (STATUS_CREATED, STATUS_PAID)]


# trace: FR-031, ADDR-009
def test_it_ai_init_105_mock_result_defaults_to_approve(api_as, buyer, f):
    """IT-AI-INIT-105 / COV-090：mock_result を省略した支払は承認として処理する。"""
    client = api_as(buyer)
    order = place_order(client, f)

    response = client.post(f"/api/purchase-orders/{order['purchase_order_id']}/pay", {}, format="json")

    assert response.status_code == 200
    assert response.json()["status"] == STATUS_PAID
    assert (
        PaymentRecord.objects.get(purchase_order_id=order["purchase_order_id"]).result
        == PAYMENT_APPROVED
    )


# trace: FR-031, ADDR-009
def test_it_ai_init_106_declined_payment_keeps_order_created(api_as, buyer, f, err):
    """IT-AI-INIT-106 / COV-091：否認は注文受付のままとし、否認の決済記録を残す（IF-01-EXC-01）。"""
    client = api_as(buyer)
    order = place_order(client, f)

    response = client.post(
        f"/api/purchase-orders/{order['purchase_order_id']}/pay",
        {"mock_result": "decline"},
        format="json",
    )

    assert response.status_code == 409
    assert err.code(response) == "PAYMENT_DECLINED"
    stored = PurchaseOrder.objects.get(pk=order["purchase_order_id"])
    assert stored.status == STATUS_CREATED
    assert stored.paid_at is None
    records = list(PaymentRecord.objects.filter(purchase_order_id=stored.pk))
    assert len(records) == 1
    assert records[0].result == PAYMENT_DECLINED
    assert records[0].transaction_ref is None


# trace: FR-031, ADDR-009
def test_it_ai_init_107_retry_after_decline_succeeds(api_as, buyer, f):
    """IT-AI-INIT-107 / COV-091：否認後に承認で再支払すると支払済になる。"""
    client = api_as(buyer)
    order = place_order(client, f)
    client.post(
        f"/api/purchase-orders/{order['purchase_order_id']}/pay",
        {"mock_result": "decline"},
        format="json",
    )

    retried = client.post(
        f"/api/purchase-orders/{order['purchase_order_id']}/pay",
        {"mock_result": "approve"},
        format="json",
    )

    assert retried.status_code == 200
    assert retried.json()["status"] == STATUS_PAID
    results = sorted(
        record.result for record in PaymentRecord.objects.filter(purchase_order_id=order["purchase_order_id"])
    )
    assert results == [PAYMENT_APPROVED, PAYMENT_DECLINED]


# trace: FR-031, FR-034, FR-043, FR-044
def test_it_ai_init_108_payment_is_rejected_for_other_statuses(api_as, buyer, admin_user, f, err):
    """IT-AI-INIT-108 / COV-092：支払済・出荷済・配達完了・キャンセル済への支払は状態遷移エラーとする。"""
    client = api_as(buyer)
    admin_client = api_as(admin_user)

    paid = place_order(client, f)
    client.post(f"/api/purchase-orders/{paid['purchase_order_id']}/pay", {}, format="json")
    shipped = place_order(client, f)
    client.post(f"/api/purchase-orders/{shipped['purchase_order_id']}/pay", {}, format="json")
    admin_client.post(f"/api/admin/purchase-orders/{shipped['purchase_order_id']}/ship", {}, format="json")
    delivered = place_order(client, f)
    client.post(f"/api/purchase-orders/{delivered['purchase_order_id']}/pay", {}, format="json")
    admin_client.post(f"/api/admin/purchase-orders/{delivered['purchase_order_id']}/ship", {}, format="json")
    admin_client.post(
        f"/api/admin/purchase-orders/{delivered['purchase_order_id']}/deliver", {}, format="json"
    )
    cancelled = place_order(client, f)
    client.post(f"/api/purchase-orders/{cancelled['purchase_order_id']}/cancel", {}, format="json")

    expected = {
        paid["purchase_order_id"]: STATUS_PAID,
        shipped["purchase_order_id"]: STATUS_SHIPPED,
        delivered["purchase_order_id"]: STATUS_DELIVERED,
        cancelled["purchase_order_id"]: STATUS_CANCELLED,
    }
    for order_id, status in expected.items():
        before_records = PaymentRecord.objects.filter(purchase_order_id=order_id).count()

        response = client.post(
            f"/api/purchase-orders/{order_id}/pay", {"mock_result": "approve"}, format="json"
        )

        assert response.status_code == 409, status
        assert err.code(response) == "INVALID_STATUS_TRANSITION"
        assert err.context(response) == {"current_status": status}
        assert PurchaseOrder.objects.get(pk=order_id).status == status
        assert PaymentRecord.objects.filter(purchase_order_id=order_id).count() == before_records


# trace: FR-031
def test_it_ai_init_109_invalid_mock_result_precedes_other_checks(
    api_as, buyer, other_buyer, f, err
):
    """IT-AI-INIT-109 / COV-093：mock_result の範囲外は所有・状態判定より先に入力エラーとする（CMN-14）。"""
    client = api_as(buyer)
    other_client = api_as(other_buyer)
    others_order = place_order(other_client, f)
    own_paid = place_order(client, f)
    client.post(f"/api/purchase-orders/{own_paid['purchase_order_id']}/pay", {}, format="json")

    for order_id in (others_order["purchase_order_id"], own_paid["purchase_order_id"]):
        response = client.post(
            f"/api/purchase-orders/{order_id}/pay", {"mock_result": "invalid"}, format="json"
        )

        assert response.status_code == 400, order_id
        assert err.code(response) == "VALIDATION_ERROR"
        assert "mock_result" in err.fields(response)

    assert PurchaseOrder.objects.get(pk=others_order["purchase_order_id"]).status == STATUS_CREATED
    assert PaymentRecord.objects.filter(purchase_order_id=others_order["purchase_order_id"]).count() == 0


# trace: FR-031
def test_it_ai_init_110_payment_for_unknown_order_is_not_found(api_as, buyer, other_buyer, f, err):
    """IT-AI-INIT-110 / COV-094：他人の注文・存在しない注文への支払は対象なしとする（PRM-01）。"""
    other_order = place_order(api_as(other_buyer), f)
    client = api_as(buyer)

    responses = [
        client.post(
            f"/api/purchase-orders/{other_order['purchase_order_id']}/pay",
            {"mock_result": "approve"},
            format="json",
        ),
        client.post("/api/purchase-orders/999999/pay", {"mock_result": "approve"}, format="json"),
    ]

    messages = set()
    for response in responses:
        assert response.status_code == 404
        assert err.code(response) == "NOT_FOUND"
        messages.add(err.message(response))
    assert len(messages) == 1
    assert PurchaseOrder.objects.get(pk=other_order["purchase_order_id"]).status == STATUS_CREATED


# trace: FR-031
def test_it_ai_init_111_payment_requires_buyer(api, api_as, buyer, admin_user, f, err):
    """IT-AI-INIT-111 / COV-095：管理者は権限エラー、未ログインは認証エラーとする。"""
    client = api_as(buyer)
    order = place_order(client, f)
    path = f"/api/purchase-orders/{order['purchase_order_id']}/pay"

    administrator = api_as(admin_user).post(path, {"mock_result": "approve"}, format="json")
    anonymous = api.post(path, {"mock_result": "approve"}, format="json")

    assert administrator.status_code == 403
    assert err.code(administrator) == "PERMISSION_DENIED"
    assert anonymous.status_code == 401
    assert err.code(anonymous) == "AUTHENTICATION_REQUIRED"
    assert PurchaseOrder.objects.get(pk=order["purchase_order_id"]).status == STATUS_CREATED


# trace: FR-031, ADDR-003
@pytest.mark.django_db(transaction=True)
def test_it_ai_init_112_concurrent_payment_records_single_approval(f, token_for, run_parallel):
    """IT-AI-INIT-112 / COV-096：同一注文への同時支払で承認済み決済記録は1件だけとなる（CMN-23）。"""
    buyer = f.user(email="race-pay@example.test")
    token = token_for(buyer)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    order = place_order(client, f)
    order_id = order["purchase_order_id"]

    def pay():
        worker = APIClient()
        worker.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        return worker.post(f"/api/purchase-orders/{order_id}/pay", {"mock_result": "approve"}, format="json")

    try:
        results = run_parallel(pay, pay)

        statuses = sorted(response.status_code for response in results)
        assert statuses == [200, 409]
        failed = next(response for response in results if response.status_code == 409)
        body = failed.json()
        assert (body.get("error") or body)["code"] == "INVALID_STATUS_TRANSITION"
        assert PaymentRecord.objects.filter(purchase_order_id=order_id, result=PAYMENT_APPROVED).count() == 1
        assert PurchaseOrder.objects.get(pk=order_id).status == STATUS_PAID
    finally:
        PaymentRecord.objects.all().delete()
        PurchaseOrder.objects.all().delete()


# trace: FR-031, ADDR-009
def test_it_ai_init_113_payment_timeout_is_service_error(api_as, buyer, f, monkeypatch, settings, err):
    """IT-AI-INIT-113 / COV-097：応答待ち時間を超えた決済は外部連携エラーとする（IF-01-EXC-02）。"""
    client = api_as(buyer)
    order = place_order(client, f)
    settings.PAYMENT_TIMEOUT_SECONDS = 0
    gateway = RecordingGateway(delay=0.05)
    monkeypatch.setattr(payment_services, "get_payment_gateway", lambda: gateway)

    response = client.post(
        f"/api/purchase-orders/{order['purchase_order_id']}/pay",
        {"mock_result": "approve"},
        format="json",
    )

    assert response.status_code == 502
    assert err.code(response) == "PAYMENT_SERVICE_ERROR"
    stored = PurchaseOrder.objects.get(pk=order["purchase_order_id"])
    assert stored.status == STATUS_CREATED
    assert stored.paid_at is None
    records = list(PaymentRecord.objects.filter(purchase_order_id=stored.pk))
    assert len(records) == 1
    assert records[0].result == PAYMENT_ERROR
    assert len(gateway.requests) == 1  # 自動再送しない


# trace: FR-031, ADDR-009
def test_it_ai_init_114_invalid_payment_response_is_service_error(api_as, buyer, f, monkeypatch, err):
    """IT-AI-INIT-114 / COV-097：承認・否認以外の応答は外部連携エラーとする（IF-01-EXC-04）。"""
    from common import timeutils

    client = api_as(buyer)
    order = place_order(client, f)
    gateway = RecordingGateway(
        result=PaymentResult(result="unknown", processed_at=timeutils.now(), transaction_ref=None)
    )
    monkeypatch.setattr(payment_services, "get_payment_gateway", lambda: gateway)

    response = client.post(
        f"/api/purchase-orders/{order['purchase_order_id']}/pay",
        {"mock_result": "approve"},
        format="json",
    )

    assert response.status_code == 502
    assert err.code(response) == "PAYMENT_SERVICE_ERROR"
    stored = PurchaseOrder.objects.get(pk=order["purchase_order_id"])
    assert stored.status == STATUS_CREATED
    assert PaymentRecord.objects.get(purchase_order_id=stored.pk).result == PAYMENT_ERROR


# trace: FR-031, ADDR-009, NFR-SC-06, FR-OUT-01
def test_it_ai_init_115_payment_request_contains_only_required_values(
    api_as, buyer, f, monkeypatch, settings
):
    """IT-AI-INIT-115 / COV-098：決済要求は注文番号・金額・通貨・模擬決済指示だけを渡す（IF-01）。

    併せて、支払処理中に外部ネットワークへの接続が発生しないことを確認する。
    """
    client = api_as(buyer)
    order = place_order(client, f, price=2000, quantity=2)
    gateway = RecordingGateway()
    monkeypatch.setattr(payment_services, "get_payment_gateway", lambda: gateway)

    connected: list = []
    original_connect = socket.socket.connect

    def recording_connect(self, address):  # pragma: no cover - 失敗時のみ内容を参照する
        connected.append(address)
        return original_connect(self, address)

    monkeypatch.setattr(socket.socket, "connect", recording_connect)

    response = client.post(
        f"/api/purchase-orders/{order['purchase_order_id']}/pay",
        {"mock_result": "approve"},
        format="json",
    )

    assert response.status_code == 200
    assert len(gateway.requests) == 1
    request = gateway.requests[0]
    assert request.order_number == order["order_number"]
    assert request.amount == order["amounts"]["total"]
    assert request.currency == "JPY"
    assert request.mock_result == "approve"
    assert not hasattr(request, "shipping_address")
    assert buyer.email not in str(request)
    assert settings.PAYMENT_GATEWAY.startswith("payments.")
    remote_hosts = [
        address
        for address in connected
        if isinstance(address, tuple) and address[0] not in ("127.0.0.1", "::1", "localhost")
    ]
    assert remote_hosts == []


# trace: FR-031, ADDR-010
def test_it_ai_init_116_screen_payment_moves_to_order_detail(screen_as, api_as, buyer, f):
    """IT-AI-INIT-116 / COV-100：画面から承認で支払うと支払済となり注文詳細画面へ遷移する。"""
    order = place_order(api_as(buyer), f, price=3000, quantity=1)
    client = screen_as(buyer)
    order_id = order["purchase_order_id"]

    form = client.get(f"/orders/{order_id}/pay/")
    assert form.status_code == 200

    response = client.post(f"/orders/{order_id}/pay/", {"mock_result": "approve"})

    assert response.status_code == 302
    assert response["Location"] == f"/orders/{order_id}/"
    detail = client.get(response["Location"])
    body = detail.content.decode()
    assert "支払済" in body
    assert PurchaseOrder.objects.get(pk=order_id).status == STATUS_PAID
    assert "支払日時" in body
