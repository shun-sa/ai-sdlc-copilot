# trace: ADDR-009
"""決済サービス（模擬）の呼出し（支払処理から利用する公開関数）。

決済要求はDBトランザクションの外で1回だけ送信し、自動再送を行わない
（ADDR-009 DD-004, DD-005）。
"""

from __future__ import annotations

import time

from payments.factory import get_payment_gateway, payment_timeout_seconds
from payments.gateway import (
    CURRENCY_JPY,
    MOCK_RESULT_CHOICES,
    RESULT_APPROVED,
    RESULT_DECLINED,
    PaymentGatewayError,
    PaymentRequest,
    PaymentResult,
)

TRANSACTION_REF_PREFIX = "MOCK-"


def is_valid_mock_result(value: str) -> bool:
    """模擬決済指示が approve／decline と完全一致するか判定する。"""
    return value in MOCK_RESULT_CHOICES


def authorize(order_number: str, amount: int, mock_result: str) -> PaymentResult:
    """決済要求を1回送信し、正しい形式の決済結果だけを返す。"""
    gateway = get_payment_gateway()
    timeout = payment_timeout_seconds()
    request = PaymentRequest(
        order_number=order_number,
        amount=amount,
        currency=CURRENCY_JPY,
        mock_result=mock_result,
    )
    started = time.monotonic()
    result = gateway.authorize(request, timeout_seconds=timeout)
    if time.monotonic() - started > timeout:
        # 応答待ちの上限を超えて受信した決済結果は反映しない（自動再送も行わない）。
        raise PaymentGatewayError("payment gateway timeout")
    validate_result(result)
    return result


def validate_result(result: PaymentResult) -> None:
    """決済結果が正しい形式か判定する（不正な応答は外部連携エラーとして扱う）。"""
    if not isinstance(result, PaymentResult):
        raise PaymentGatewayError("invalid payment result")
    if result.result not in (RESULT_APPROVED, RESULT_DECLINED):
        raise PaymentGatewayError("invalid payment result status")
    if result.processed_at is None:
        raise PaymentGatewayError("invalid payment result processed_at")
    if result.result == RESULT_APPROVED:
        reference = result.transaction_ref or ""
        if not reference.startswith(TRANSACTION_REF_PREFIX) or len(reference) != 21:
            raise PaymentGatewayError("invalid transaction reference")
    elif result.result == RESULT_DECLINED and not result.decline_reason_code:
        raise PaymentGatewayError("invalid decline reason code")
