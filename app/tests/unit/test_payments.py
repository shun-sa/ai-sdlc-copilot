# trace: FR-031, NFR-EN-05, NFR-LG-05, NFR-SC-24, ADDR-008
"""決済要求（payments.client）・決済サービス（模擬）（payments.mock）・ゲートウェイ境界の単体テスト。

期待値：FR-031 6.16.4 手順6・7（送信内容、10秒の待機、正しい形式の決済結果＝応答検証、応答不正）、
NFR-EN-05（実在の決済サービスへ接続しない）、NFR-LG-05（カード情報を入力・保存・送信しない）、
NFR-SC-24（決済要求に個人情報を含めない：送信項目は注文番号・決済金額・通貨・模擬決済指示）、ADDR-008。
ゲートウェイを差し替えるテストは DB を使わない（MOCK）。模擬機能の試験用状態の読取りは CONTAINER。
"""

import dataclasses
import threading
from unittest import mock

import pytest

from payments import client, gateway
from payments import mock as mock_gateway
from tests.unit.conftest import jst


# trace: FR-031, ADDR-008
class _FakeGateway(gateway.PaymentGateway):
    def __init__(self, send):
        self.send = send
        self.requests: list[gateway.PaymentRequest] = []

    def prepare(self, request):
        self.requests.append(request)
        return self.send


# trace: FR-031, ADDR-008
def _approved():
    return {
        "result": "approved",
        "transaction_ref": "MOCK-AbCdEf0123456789",
        "processed_at": "2027-04-20T14:30:05+09:00",
    }


# ---------------------------------------------------------------------------
# 応答検証（6.16.4 手順7）
# ---------------------------------------------------------------------------


# trace: FR-031, ADDR-008
def test_validate_response_accepts_approved_with_reference_and_time():
    outcome = client.validate_response(_approved())
    assert outcome.result == "approved"
    assert outcome.transaction_ref == "MOCK-AbCdEf0123456789"
    assert outcome.processed_at == jst(2027, 4, 20, 14, 30, 5)


# trace: FR-031, ADDR-008
def test_validate_response_accepts_declined_with_reason():
    outcome = client.validate_response(
        {"result": "declined", "decline_reason": "否認", "processed_at": "2027-04-20T14:30:05.900+09:00"}
    )
    assert outcome.result == "declined" and outcome.transaction_ref is None
    assert outcome.processed_at.microsecond == 0


# trace: FR-031, ADDR-008
@pytest.mark.parametrize(
    "response",
    [
        None,
        "approved",
        {**_approved(), "result": "unknown"},
        {k: v for k, v in _approved().items() if k != "result"},
        {k: v for k, v in _approved().items() if k != "processed_at"},
        {**_approved(), "processed_at": "2027-04-20T14:30:05"},  # オフセットなし
        {**_approved(), "processed_at": "not-a-date"},
        {**_approved(), "processed_at": 1234},
        {**_approved(), "processed_at": "0001-01-01T00:00:00+09:00"},  # 協定世界時へ変換できない
        {k: v for k, v in _approved().items() if k != "transaction_ref"},
        {**_approved(), "transaction_ref": "MOCK-INVALID"},
        {**_approved(), "transaction_ref": "MOCK-AbCdEf012345678!"},
        {**_approved(), "transaction_ref": "PAY-AbCdEf0123456789"},
        {"result": "declined", "processed_at": "2027-04-20T14:30:05+09:00"},
        {"result": "declined", "decline_reason": "", "processed_at": "2027-04-20T14:30:05+09:00"},
    ],
    ids=[
        "none",
        "string",
        "unknown-result",
        "missing-result",
        "missing-time",
        "naive-time",
        "bad-time",
        "numeric-time",
        "time-out-of-range",
        "missing-ref",
        "short-ref",
        "symbol-ref",
        "wrong-prefix",
        "missing-reason",
        "empty-reason",
    ],
)
def test_validate_response_rejects_malformed_results(response):
    assert client.validate_response(response) is None


# ---------------------------------------------------------------------------
# 送信と待機（6.16.4 手順6、ADDR-008 DD-008・DD-009）
# ---------------------------------------------------------------------------


# trace: FR-031, NFR-SC-24, NFR-LG-05, ADDR-008
def test_request_payment_sends_only_four_items_once_and_logs(app_logs):
    fake = _FakeGateway(lambda: _approved())
    with mock.patch.object(client, "get_gateway", return_value=fake):
        outcome = client.request_payment("PO-00000012", 6044, "approved")
    assert outcome.result == "approved"
    assert len(fake.requests) == 1
    assert dataclasses.asdict(fake.requests[0]) == {
        "order_number": "PO-00000012",
        "amount": 6044,
        "currency": "JPY",
        "mock_instruction": "approved",
    }
    assert [f.name for f in dataclasses.fields(gateway.PaymentRequest)] == [
        "order_number",
        "amount",
        "currency",
        "mock_instruction",
    ]
    logs = [r for r in app_logs.records() if r["log_type"] == "LOG-06"]
    assert [r["phase"] for r in logs] == ["request", "response"]
    assert logs[1]["result"] == "approved" and logs[1]["transaction_ref"] == "MOCK-AbCdEf0123456789"
    assert logs[0]["order_number"] == "PO-00000012" and logs[0]["currency"] == "JPY"


# trace: FR-031, ADDR-008
def test_request_payment_connection_failure_is_integration_error():
    def send():
        raise ConnectionError("unreachable")

    with mock.patch.object(client, "get_gateway", return_value=_FakeGateway(send)):
        outcome = client.request_payment("PO-1", 1, "approved")
    assert outcome.result == "integration_error" and isinstance(outcome.error, ConnectionError)


# trace: FR-031, ADDR-008
def test_request_payment_invalid_response_is_integration_error():
    with mock.patch.object(client, "get_gateway", return_value=_FakeGateway(lambda: {"result": "approved"})):
        outcome = client.request_payment("PO-1", 1, "approved")
    assert outcome.result == "integration_error" and isinstance(outcome.error, ValueError)


# trace: FR-031, ADDR-008
def test_request_payment_gives_up_after_timeout_and_discards_late_result(app_logs):
    """10秒（TIMEOUT_SECONDS）を超えた場合は連携エラーとし、その後に届いた結果は反映しない。"""
    release = threading.Event()

    def slow_send():
        release.wait(5)
        return _approved()

    assert client.TIMEOUT_SECONDS == 10.0
    with mock.patch.object(client, "TIMEOUT_SECONDS", 0.2):
        with mock.patch.object(client, "get_gateway", return_value=_FakeGateway(slow_send)):
            outcome = client.request_payment("PO-1", 100, "approved")
    release.set()
    assert outcome.result == "integration_error" and isinstance(outcome.error, TimeoutError)
    response_log = [r for r in app_logs.records() if r.get("phase") == "response"][-1]
    assert response_log["result"] == "integration_error"


# trace: NFR-EN-05, ADDR-008
def test_gateway_is_fixed_to_internal_mock():
    """NFR-EN-05：実在の決済サービスへ接続しない（使用する実装はプログラム内の既定で模擬機能に固定）。"""
    assert isinstance(gateway.get_gateway(), mock_gateway.MockPaymentGateway)


# ---------------------------------------------------------------------------
# 決済サービス（模擬）（ADDR-008 4.3 の2、ADDR-011 の試験用状態）
# ---------------------------------------------------------------------------


# trace: FR-031, ADDR-008
@pytest.mark.django_db
def test_mock_gateway_returns_instruction_with_valid_reference(freeze):
    freeze(jst(2027, 4, 20, 14, 30, 5))
    approved = mock_gateway.MockPaymentGateway().prepare(gateway.PaymentRequest("PO-1", 100, "JPY", "approved"))()
    assert client.validate_response(approved).transaction_ref == approved["transaction_ref"]
    assert approved["processed_at"] == "2027-04-20T14:30:05+09:00"
    declined = mock_gateway.MockPaymentGateway().prepare(gateway.PaymentRequest("PO-1", 100, "JPY", "declined"))()
    assert client.validate_response(declined).result == "declined"
    refs = {mock_gateway._transaction_ref() for _ in range(50)}
    assert len(refs) == 50  # 暗号論的乱数による一意な取引参照番号


# trace: FR-031, ADDR-008
@pytest.mark.django_db
@pytest.mark.parametrize(
    "mode",
    [
        "invalid_result",
        "missing_result",
        "missing_processed_at",
        "missing_transaction_ref",
        "invalid_transaction_ref",
        "missing_decline_reason",
    ],
)
def test_mock_gateway_abnormal_modes_produce_invalid_responses(test_state, mode):
    test_state(payment_mode=mode)
    send = mock_gateway.MockPaymentGateway().prepare(gateway.PaymentRequest("PO-1", 100, "JPY", "approved"))
    assert client.validate_response(send()) is None


# trace: FR-031, ADDR-008
@pytest.mark.django_db
def test_mock_gateway_connection_error_and_delay(test_state):
    test_state(payment_mode="connection_error")
    with pytest.raises(ConnectionError):
        mock_gateway.MockPaymentGateway().prepare(gateway.PaymentRequest("PO-1", 1, "JPY", "approved"))()
    test_state(payment_mode="normal", payment_delay_seconds=0.01)
    assert mock_gateway._test_settings() == (0.01, "normal")
    send = mock_gateway.MockPaymentGateway().prepare(gateway.PaymentRequest("PO-1", 1, "JPY", "approved"))
    assert send()["result"] == "approved"


# trace: FR-031, ADDR-008
def test_mock_gateway_ignores_test_state_when_dev_features_disabled(settings):
    settings.MINICOMMERCE_DEV_FEATURES = False
    assert mock_gateway._test_settings() == (0.0, "normal")
