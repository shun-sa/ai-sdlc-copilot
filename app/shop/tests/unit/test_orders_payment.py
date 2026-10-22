# trace: FR-031, ADDR-009, ADDR-013
"""支払（模擬決済）（FR-031）と決済ゲートウェイ境界の単体テスト。

期待値は FR-031 6.16.4 の処理手順・事後条件、6.16.9（手順5の状態判定から結果反映までの単位）、
IF-01（決済サービス連携）、ADDR-009、ADDR-013 から導出する。
外部ネットワークへは接続しない（模擬実装または差し替えたゲートウェイを用いる）。
"""
from datetime import timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from shop.common import timeutils
from shop.common.errors import (
    InvalidStatusTransitionError,
    NotFoundError,
    PaymentDeclinedError,
    PaymentServiceError,
    ValidationError,
)
from shop.models import PaymentRecord, PaymentResult, PurchaseOrder, PurchaseOrderStatus, StockUnit
from shop.payments import client as payment_client
from shop.payments.gateway import (
    APPROVE,
    DECLINE,
    DECLINED_REASON_CODE,
    RESULT_APPROVED,
    RESULT_DECLINED,
    PaymentGatewayError,
    PaymentRequest,
    PaymentResponse,
)
from shop.payments.mock import MockPaymentGateway
from shop.services import orders
from shop.tests.unit import _helpers

pytestmark = pytest.mark.django_db


# trace: FR-031
def _order(buyer, stock_unit, status=PurchaseOrderStatus.CREATED):
    """試験用の注文を1件作成する。"""
    return _helpers.make_order(buyer, stock_unit, quantity=2, status=status)


# trace: FR-031
def test_pay_order_approves_and_updates_status(buyer, stock_unit):
    """承認時は決済記録を登録し、注文を支払済へ遷移させる（ST-PO-02）。"""
    order = _order(buyer, stock_unit)

    result = orders.pay_order(buyer, order.purchase_order_id, APPROVE)

    updated = PurchaseOrder.objects.get(pk=order.pk)
    record = PaymentRecord.objects.get()
    assert result["status"] == PurchaseOrderStatus.PAID
    assert updated.status == PurchaseOrderStatus.PAID
    assert updated.paid_at is not None
    assert record.result == PaymentResult.APPROVED
    assert record.amount == updated.total
    assert record.transaction_ref.startswith("MOCK-")
    history = updated.status_history.order_by("status_history_id").last()
    assert (history.from_status, history.to_status) == (PurchaseOrderStatus.CREATED, PurchaseOrderStatus.PAID)


# trace: FR-031
def test_pay_order_defaults_to_approve(buyer, stock_unit):
    """模擬決済指示を省略した場合は承認として扱う。"""
    order = _order(buyer, stock_unit)

    orders.pay_order(buyer, order.purchase_order_id, None)

    assert PurchaseOrder.objects.get(pk=order.pk).status == PurchaseOrderStatus.PAID


# trace: FR-031
def test_pay_order_does_not_change_stock(buyer, stock_unit):
    """支払では在庫数量を変更しない。"""
    order = _order(buyer, stock_unit)
    before = StockUnit.objects.get(pk=stock_unit.pk).quantity

    orders.pay_order(buyer, order.purchase_order_id, APPROVE)

    assert StockUnit.objects.get(pk=stock_unit.pk).quantity == before


# trace: FR-031
def test_pay_order_declined_keeps_order_created(buyer, stock_unit):
    """否認時は決済記録（否認）だけを登録し、注文は注文受付のままとする（E-031-06）。"""
    order = _order(buyer, stock_unit)

    with pytest.raises(PaymentDeclinedError) as exc:
        orders.pay_order(buyer, order.purchase_order_id, DECLINE)

    updated = PurchaseOrder.objects.get(pk=order.pk)
    record = PaymentRecord.objects.get()
    assert exc.value.http_status == 409
    assert updated.status == PurchaseOrderStatus.CREATED
    assert updated.paid_at is None
    assert record.result == PaymentResult.DECLINED
    assert record.transaction_ref is None
    assert updated.status_history.filter(to_status=PurchaseOrderStatus.PAID).count() == 0


# trace: FR-031
def test_pay_order_can_be_retried_after_decline(buyer, stock_unit):
    """否認後も同じ注文に再度支払える。"""
    order = _order(buyer, stock_unit)
    with pytest.raises(PaymentDeclinedError):
        orders.pay_order(buyer, order.purchase_order_id, DECLINE)

    orders.pay_order(buyer, order.purchase_order_id, APPROVE)

    assert PurchaseOrder.objects.get(pk=order.pk).status == PurchaseOrderStatus.PAID
    assert PaymentRecord.objects.count() == 2


# trace: FR-031
def test_pay_order_records_payment_service_error(buyer, stock_unit, monkeypatch):
    """連携エラー時は決済記録（連携エラー）を登録し、注文を変更しない（E-031-07）。"""
    order = _order(buyer, stock_unit)

    def raise_gateway_error(request):
        raise PaymentGatewayError("連携エラー")

    monkeypatch.setattr(payment_client, "authorize", raise_gateway_error)

    with pytest.raises(PaymentServiceError) as exc:
        orders.pay_order(buyer, order.purchase_order_id, APPROVE)

    record = PaymentRecord.objects.get()
    assert exc.value.http_status == 502
    assert record.result == PaymentResult.ERROR
    assert record.transaction_ref is None
    assert PurchaseOrder.objects.get(pk=order.pk).status == PurchaseOrderStatus.CREATED


# trace: FR-031
@pytest.mark.parametrize("mock_result", ["", "APPROVE", "unknown", "approved"])
def test_pay_order_rejects_invalid_mock_result(buyer, stock_unit, mock_result):
    """模擬決済指示が approve・decline のいずれでもない場合は入力エラーとする（E-031-03）。"""
    order = _order(buyer, stock_unit)

    if mock_result == "":
        orders.pay_order(buyer, order.purchase_order_id, mock_result)
        return

    with pytest.raises(ValidationError) as exc:
        orders.pay_order(buyer, order.purchase_order_id, mock_result)

    assert exc.value.details[0]["field"] == "mock_result"
    assert PaymentRecord.objects.count() == 0


# trace: FR-031
def test_pay_order_strips_mock_result(buyer, stock_unit):
    """模擬決済指示は前後の空白を除去して判定する。"""
    order = _order(buyer, stock_unit)

    orders.pay_order(buyer, order.purchase_order_id, "  approve  ")

    assert PurchaseOrder.objects.get(pk=order.pk).status == PurchaseOrderStatus.PAID


# trace: FR-031
@pytest.mark.parametrize(
    "status",
    [
        PurchaseOrderStatus.PAID,
        PurchaseOrderStatus.SHIPPED,
        PurchaseOrderStatus.DELIVERED,
        PurchaseOrderStatus.CANCELLED,
    ],
)
def test_pay_order_rejects_non_created_status(buyer, stock_unit, status):
    """注文受付以外の状態では支払できず、決済要求も送信しない（E-031-05）。"""
    order = _order(buyer, stock_unit, status=status)

    with pytest.raises(InvalidStatusTransitionError) as exc:
        orders.pay_order(buyer, order.purchase_order_id, APPROVE)

    assert exc.value.context["current_status"] == status
    assert PaymentRecord.objects.count() == 0


# trace: FR-031
def test_pay_order_rejects_other_buyers_order(buyer, other_buyer, stock_unit):
    """他の購入者の注文は対象なしとする（E-031-04）。"""
    order = _order(buyer, stock_unit)

    with pytest.raises(NotFoundError):
        orders.pay_order(other_buyer, order.purchase_order_id, APPROVE)


# trace: FR-031
@pytest.mark.parametrize("raw_order_id", ["abc", "", None, 999999])
def test_pay_order_rejects_unknown_order(buyer, raw_order_id):
    """識別子として解釈できない値・存在しない注文は対象なしとする。"""
    with pytest.raises(NotFoundError):
        orders.pay_order(buyer, raw_order_id, APPROVE)


# trace: FR-031
def test_mock_gateway_returns_approved_response():
    """模擬実装は approve で承認・MOCK-＋英数字16桁の取引参照番号を返す。"""
    response = MockPaymentGateway().authorize(
        PaymentRequest(order_number="PO-00000001", amount=1000, currency="JPY", mock_result=APPROVE)
    )

    assert response.result == RESULT_APPROVED
    assert response.declined_reason_code is None
    assert response.transaction_ref.startswith("MOCK-")
    assert len(response.transaction_ref) == len("MOCK-") + 16
    assert response.transaction_ref[5:].isalnum()
    assert response.processed_at is not None


# trace: FR-031
def test_mock_gateway_returns_declined_response():
    """模擬実装は decline で否認・否認理由コード DECLINED を返す。"""
    response = MockPaymentGateway().authorize(
        PaymentRequest(order_number="PO-00000001", amount=1000, currency="JPY", mock_result=DECLINE)
    )

    assert response.result == RESULT_DECLINED
    assert response.transaction_ref is None
    assert response.declined_reason_code == DECLINED_REASON_CODE


# trace: FR-031
def test_mock_gateway_generates_unique_transaction_refs():
    """取引参照番号は要求ごとに異なる値を生成する。"""
    gateway = MockPaymentGateway()
    request = PaymentRequest(order_number="PO-00000001", amount=1000, currency="JPY", mock_result=APPROVE)

    refs = {gateway.authorize(request).transaction_ref for _ in range(3)}

    assert len(refs) == 3


# trace: FR-031
def test_payment_client_uses_configured_gateway(settings):
    """決済ゲートウェイの実装は設定で選択し、既定は模擬実装とする。"""
    settings.PAYMENT_GATEWAY = "mock"

    assert isinstance(payment_client.get_gateway(), MockPaymentGateway)


# trace: FR-031
def test_payment_client_rejects_unsupported_gateway(settings):
    """未対応の決済ゲートウェイ設定は連携エラーとする。"""
    settings.PAYMENT_GATEWAY = "external"

    with pytest.raises(PaymentGatewayError):
        payment_client.get_gateway()


# trace: FR-031
@pytest.mark.parametrize(
    "response",
    [
        PaymentResponse(
            result="unknown",
            transaction_ref="MOCK-ABCDEFGHIJ123456",
            declined_reason_code=None,
            processed_at=None,
        ),
        PaymentResponse(result=RESULT_APPROVED, transaction_ref=None, declined_reason_code=None, processed_at=None),
        PaymentResponse(
            result=RESULT_APPROVED,
            transaction_ref="BAD-REF",
            declined_reason_code=None,
            processed_at=None,
        ),
        PaymentResponse(result=RESULT_DECLINED, transaction_ref=None, declined_reason_code=None, processed_at=None),
    ],
)
def test_payment_client_rejects_invalid_response(monkeypatch, settings, response):
    """応答が IF-01-EXC-04 の条件を満たさない場合は連携エラーとする。"""

    class _Gateway:
        def authorize(self, request):
            processed = response
            if processed.processed_at is None and processed.result in {RESULT_APPROVED, RESULT_DECLINED}:
                return PaymentResponse(
                    result=processed.result,
                    transaction_ref=processed.transaction_ref,
                    declined_reason_code=processed.declined_reason_code,
                    processed_at=None,
                )
            return processed

    monkeypatch.setattr(payment_client, "get_gateway", lambda: _Gateway())

    with pytest.raises(PaymentGatewayError):
        payment_client.authorize(
            PaymentRequest(order_number="PO-00000001", amount=1000, currency="JPY", mock_result=APPROVE)
        )


# trace: FR-031
def test_payment_client_accepts_valid_declined_response(monkeypatch):
    """否認応答は否認理由コードと処理日時があれば正しい応答として扱う。"""

    class _Gateway:
        def authorize(self, request):
            return PaymentResponse(
                result=RESULT_DECLINED,
                transaction_ref=None,
                declined_reason_code=DECLINED_REASON_CODE,
                processed_at=timeutils.now(),
            )

    monkeypatch.setattr(payment_client, "get_gateway", lambda: _Gateway())

    response = payment_client.authorize(
        PaymentRequest(order_number="PO-00000001", amount=1000, currency="JPY", mock_result=DECLINE)
    )

    assert response.result == RESULT_DECLINED


# trace: FR-031
def test_payment_client_converts_unexpected_exception_to_gateway_error(monkeypatch):
    """呼び出し自体の失敗は連携エラーとして扱う（IF-01-EXC-03）。"""

    class _Gateway:
        def authorize(self, request):
            raise RuntimeError("接続失敗")

    monkeypatch.setattr(payment_client, "get_gateway", lambda: _Gateway())

    with pytest.raises(PaymentGatewayError):
        payment_client.authorize(
            PaymentRequest(order_number="PO-00000001", amount=1000, currency="JPY", mock_result=APPROVE)
        )


# trace: FR-031
def test_payment_client_rejects_response_after_deadline(monkeypatch, settings):
    """応答が制限時間（10秒）を超えた場合は連携エラーとし、結果を反映しない（IF-01-PRF-05）。"""
    settings.PAYMENT_TIMEOUT_SECONDS = 10
    elapsed = [0.0, 10.5]

    def fake_monotonic():
        return elapsed.pop(0) if elapsed else 10.5

    monkeypatch.setattr(payment_client.time, "monotonic", fake_monotonic)

    class _Gateway:
        def authorize(self, request):
            return PaymentResponse(
                result=RESULT_APPROVED,
                transaction_ref="MOCK-ABCDEFGHIJ123456",
                declined_reason_code=None,
                processed_at=timeutils.now(),
            )

    monkeypatch.setattr(payment_client, "get_gateway", lambda: _Gateway())

    with pytest.raises(PaymentGatewayError):
        payment_client.authorize(
            PaymentRequest(order_number="PO-00000001", amount=1000, currency="JPY", mock_result=APPROVE)
        )


# trace: FR-031
def test_payment_client_accepts_response_within_deadline(monkeypatch, settings):
    """制限時間内の応答は正常な決済結果として扱う（境界の内側）。"""
    settings.PAYMENT_TIMEOUT_SECONDS = 10
    elapsed = [0.0, 9.9]

    def fake_monotonic():
        return elapsed.pop(0) if elapsed else 9.9

    monkeypatch.setattr(payment_client.time, "monotonic", fake_monotonic)

    class _Gateway:
        def authorize(self, request):
            return PaymentResponse(
                result=RESULT_APPROVED,
                transaction_ref="MOCK-ABCDEFGHIJ123456",
                declined_reason_code=None,
                processed_at=timeutils.now(),
            )

    monkeypatch.setattr(payment_client, "get_gateway", lambda: _Gateway())

    response = payment_client.authorize(
        PaymentRequest(order_number="PO-00000001", amount=1000, currency="JPY", mock_result=APPROVE)
    )

    assert response.result == RESULT_APPROVED


# trace: FR-031
def test_payment_request_carries_order_amount_and_currency(buyer, stock_unit, monkeypatch):
    """決済要求には注文番号・注文の合計・通貨 JPY・模擬決済指示を渡す（再計算しない）。"""
    order = _order(buyer, stock_unit)
    captured = {}

    def capture(request):
        captured["request"] = request
        return PaymentResponse(
            result=RESULT_APPROVED,
            transaction_ref="MOCK-ABCDEFGHIJ123456",
            declined_reason_code=None,
            processed_at=timeutils.now(),
        )

    monkeypatch.setattr(payment_client, "authorize", capture)

    orders.pay_order(buyer, order.purchase_order_id, APPROVE)

    request = captured["request"]
    assert request.order_number == order.order_number
    assert request.amount == order.total
    assert request.currency == "JPY"
    assert request.mock_result == APPROVE


# trace: FR-031
def test_pay_order_keeps_processed_at_from_gateway(buyer, stock_unit, monkeypatch):
    """決済記録の処理日時は決済結果の処理日時を用いる。"""
    order = _order(buyer, stock_unit)
    processed_at = timeutils.now() - timedelta(minutes=1)

    monkeypatch.setattr(
        payment_client,
        "authorize",
        lambda request: PaymentResponse(
            result=RESULT_APPROVED,
            transaction_ref="MOCK-ABCDEFGHIJ123456",
            declined_reason_code=None,
            processed_at=processed_at,
        ),
    )

    orders.pay_order(buyer, order.purchase_order_id, APPROVE)

    assert PaymentRecord.objects.get().processed_at == processed_at


# trace: FR-031, ADDR-013
@pytest.mark.parametrize(
    "status",
    [
        PurchaseOrderStatus.PAID,
        PurchaseOrderStatus.SHIPPED,
        PurchaseOrderStatus.DELIVERED,
        PurchaseOrderStatus.CANCELLED,
    ],
)
def test_pay_order_does_not_send_payment_request_when_status_is_not_created(
    buyer, stock_unit, monkeypatch, status
):
    """注文受付以外の状態では決済要求を送信しない（FR-031 6.16.4 手順5・E-031-05、ADDR-013 DD-002）。"""
    order = _order(buyer, stock_unit, status=status)
    requests: list[PaymentRequest] = []

    def record_request(request):
        requests.append(request)
        return PaymentResponse(
            result=RESULT_APPROVED,
            transaction_ref="MOCK-ABCDEFGHIJ123456",
            declined_reason_code=None,
            processed_at=timeutils.now(),
        )

    monkeypatch.setattr(payment_client, "authorize", record_request)

    with pytest.raises(InvalidStatusTransitionError):
        orders.pay_order(buyer, order.purchase_order_id, APPROVE)

    assert requests == []
    assert PaymentRecord.objects.count() == 0
    assert PurchaseOrder.objects.get(pk=order.pk).status == status


# trace: FR-031, ADDR-013
def test_pay_order_sends_payment_request_while_holding_order_lock(buyer, stock_unit, monkeypatch):
    """決済要求は注文行のロック取得後に送信する（FR-031 6.16.9、ADDR-013 DD-001・DD-003）。"""
    order = _order(buyer, stock_unit)
    gateway_authorize = payment_client.authorize
    statements_before_send: list[str] = []

    def authorize_after_lock(request):
        statements_before_send.extend(query["sql"] for query in connection.queries)
        return gateway_authorize(request)

    monkeypatch.setattr(payment_client, "authorize", authorize_after_lock)

    with CaptureQueriesContext(connection):
        orders.pay_order(buyer, order.purchase_order_id, APPROVE)

    assert any(
        "FOR UPDATE" in statement.upper() and "PURCHASE_ORDER" in statement.upper()
        for statement in statements_before_send
    )
    assert PurchaseOrder.objects.get(pk=order.pk).status == PurchaseOrderStatus.PAID
