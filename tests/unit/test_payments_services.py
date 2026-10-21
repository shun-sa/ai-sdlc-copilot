# trace: FR-031, NFR-EN-05, NFR-SC-24, ADDR-009
"""決済サービス（模擬）IF-01 の単体テスト。

期待結果は機能要件 6.16.4 手順6〜7・6.16.5（決済要求の内容、正しい形式の決済結果）、
NFR-EN-05（外部ネットワークへ接続しない模擬機能）、ADDR-009（1回だけ送信・自動再送なし・
決済要求に個人情報を渡さない）から導出する。DBは使用しない。
"""

from __future__ import annotations

import datetime as dt
import re

import pytest
from payments import services
from payments.factory import get_payment_gateway, payment_timeout_seconds
from payments.gateway import (
    CURRENCY_JPY,
    DECLINE_REASON_CODE,
    MOCK_APPROVE,
    MOCK_DECLINE,
    RESULT_APPROVED,
    RESULT_DECLINED,
    PaymentGateway,
    PaymentGatewayError,
    PaymentRequest,
    PaymentResult,
)
from payments.mock import MockPaymentGateway

TRANSACTION_REF = re.compile(r"^MOCK-[A-Z0-9]{16}$")
APPROVED_REF = "MOCK-ABCDEFGH12345678"
PROCESSED_AT = dt.datetime(2027, 4, 10, tzinfo=dt.UTC)


# trace: FR-031
class RecordingGateway(PaymentGateway):
    """決済要求の内容と送信回数を記録する差し替え実装。"""

    def __init__(self, result: PaymentResult | object) -> None:
        self.result = result
        self.requests: list[PaymentRequest] = []
        self.timeouts: list[int] = []

    def authorize(self, request: PaymentRequest, *, timeout_seconds: int):
        self.requests.append(request)
        self.timeouts.append(timeout_seconds)
        return self.result


# trace: FR-031
@pytest.mark.parametrize(
    ("value", "expected"),
    [("approve", True), ("decline", True), ("APPROVE", False), ("", False), ("ok", False)],
)
def test_is_valid_mock_result_requires_exact_lowercase_value(value, expected):
    """FR-031 手順3：模擬決済指示は approve／decline と完全一致する値のみ受け付ける。"""
    assert services.is_valid_mock_result(value) is expected


# trace: FR-031
def test_mock_gateway_approves_and_returns_transaction_reference():
    """FR-031 手順7：承認の決済結果は「MOCK-」＋英数字16桁と処理日時を含む。"""
    result = MockPaymentGateway().authorize(
        PaymentRequest(order_number="PO-00000001", amount=5500, currency=CURRENCY_JPY, mock_result=MOCK_APPROVE),
        timeout_seconds=10,
    )

    assert result.result == RESULT_APPROVED
    assert result.approved is True
    assert TRANSACTION_REF.match(result.transaction_ref)
    assert len(result.transaction_ref) == 21
    assert isinstance(result.processed_at, dt.datetime)


# trace: FR-031
def test_mock_gateway_declines_with_reason_code():
    """FR-031 手順7：否認の決済結果は否認理由コード（DECLINED）と処理日時を含む。"""
    result = MockPaymentGateway().authorize(
        PaymentRequest(order_number="PO-00000002", amount=1000, currency=CURRENCY_JPY, mock_result=MOCK_DECLINE),
        timeout_seconds=10,
    )

    assert result.result == RESULT_DECLINED
    assert result.approved is False
    assert result.decline_reason_code == DECLINE_REASON_CODE
    assert result.transaction_ref is None


# trace: NFR-EN-05
def test_mock_gateway_issues_different_transaction_reference_each_time():
    """決済ごとに異なる取引参照番号を払い出す（本システム内の模擬機能）。"""
    gateway = MockPaymentGateway()
    request = PaymentRequest(order_number="PO-00000003", amount=100, currency=CURRENCY_JPY, mock_result=MOCK_APPROVE)

    first = gateway.authorize(request, timeout_seconds=10)
    second = gateway.authorize(request, timeout_seconds=10)

    assert first.transaction_ref != second.transaction_ref


# trace: NFR-SC-24, ADDR-009
def test_authorize_sends_request_once_without_personal_information(monkeypatch, settings):
    """ADDR-009 INV-004：決済要求は注文番号・金額・通貨・模擬決済指示だけを1回送信する。"""
    gateway = RecordingGateway(
        PaymentResult(
            result=RESULT_APPROVED,
            processed_at=dt.datetime.now(dt.UTC),
            transaction_ref=APPROVED_REF,
        )
    )
    monkeypatch.setattr(services, "get_payment_gateway", lambda: gateway)
    settings.PAYMENT_TIMEOUT_SECONDS = 10

    result = services.authorize("PO-00000010", 5500, MOCK_APPROVE)

    assert len(gateway.requests) == 1
    request = gateway.requests[0]
    assert request == PaymentRequest(
        order_number="PO-00000010", amount=5500, currency=CURRENCY_JPY, mock_result=MOCK_APPROVE
    )
    assert set(vars(request)) == {"order_number", "amount", "currency", "mock_result"}
    assert result.approved is True


# trace: FR-031
def test_authorize_passes_configured_timeout(monkeypatch, settings):
    """FR-031 手順6：決済結果の応答待ちは最大10秒とする。"""
    gateway = RecordingGateway(
        PaymentResult(
            result=RESULT_DECLINED,
            processed_at=dt.datetime.now(dt.UTC),
            decline_reason_code=DECLINE_REASON_CODE,
        )
    )
    monkeypatch.setattr(services, "get_payment_gateway", lambda: gateway)
    settings.PAYMENT_TIMEOUT_SECONDS = 10

    services.authorize("PO-00000011", 100, MOCK_DECLINE)

    assert gateway.timeouts == [10]


# trace: FR-031
def test_authorize_rejects_result_received_after_timeout(monkeypatch, settings):
    """FR-031 手順11：応答待ちの上限を超えて受信した決済結果は反映しない。"""
    settings.PAYMENT_TIMEOUT_SECONDS = 0
    gateway = RecordingGateway(
        PaymentResult(
            result=RESULT_APPROVED,
            processed_at=dt.datetime.now(dt.UTC),
            transaction_ref=APPROVED_REF,
        )
    )
    monkeypatch.setattr(services, "get_payment_gateway", lambda: gateway)
    times = iter([0.0, 1.0])
    monkeypatch.setattr(services.time, "monotonic", lambda: next(times))

    with pytest.raises(PaymentGatewayError):
        services.authorize("PO-00000012", 100, MOCK_APPROVE)


# trace: FR-031
@pytest.mark.parametrize(
    "result",
    [
        "not-a-payment-result",
        PaymentResult(result="unknown", processed_at=PROCESSED_AT),
        PaymentResult(result=RESULT_APPROVED, processed_at=None, transaction_ref=APPROVED_REF),
        PaymentResult(result=RESULT_APPROVED, processed_at=PROCESSED_AT, transaction_ref=None),
        PaymentResult(result=RESULT_APPROVED, processed_at=PROCESSED_AT, transaction_ref="REF-1"),
        PaymentResult(result=RESULT_APPROVED, processed_at=PROCESSED_AT, transaction_ref="MOCK-SHORT"),
        PaymentResult(result=RESULT_DECLINED, processed_at=PROCESSED_AT, decline_reason_code=None),
    ],
)
def test_validate_result_rejects_malformed_payment_result(result):
    """FR-031 手順7：正しい形式でない決済結果は応答不正（外部連携エラー）とする。"""
    with pytest.raises(PaymentGatewayError):
        services.validate_result(result)


# trace: FR-031
def test_validate_result_accepts_well_formed_results():
    """承認・否認それぞれの正しい形式の決済結果は受け入れる。"""
    approved = PaymentResult(
        result=RESULT_APPROVED,
        processed_at=dt.datetime(2027, 4, 10, tzinfo=dt.UTC),
        transaction_ref="MOCK-ABCDEFGH12345678",
    )
    declined = PaymentResult(
        result=RESULT_DECLINED,
        processed_at=dt.datetime(2027, 4, 10, tzinfo=dt.UTC),
        decline_reason_code=DECLINE_REASON_CODE,
    )

    assert services.validate_result(approved) is None
    assert services.validate_result(declined) is None


# trace: FR-031, ADDR-009
def test_gateway_implementation_is_resolved_from_settings(settings):
    """ADDR-009 DD-002：決済ゲートウェイ実装は設定値で解決する（要求内容では切り替えない）。"""
    settings.PAYMENT_GATEWAY = "payments.mock.MockPaymentGateway"
    settings.PAYMENT_TIMEOUT_SECONDS = 10

    assert isinstance(get_payment_gateway(), MockPaymentGateway)
    assert payment_timeout_seconds() == 10


# trace: FR-031
def test_payment_gateway_interface_requires_authorize():
    """IF-01：決済ゲートウェイは authorize を実装する抽象インターフェースとする。"""
    with pytest.raises(TypeError):
        PaymentGateway()
