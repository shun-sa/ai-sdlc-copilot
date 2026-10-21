# trace: ADDR-009
"""決済サービス（模擬）の実装。外部ネットワークへ接続しない（NFR-EN-05）。"""

from __future__ import annotations

import secrets
import string

from common import timeutils
from payments.gateway import (
    DECLINE_REASON_CODE,
    MOCK_DECLINE,
    RESULT_APPROVED,
    RESULT_DECLINED,
    PaymentGateway,
    PaymentRequest,
    PaymentResult,
)

TRANSACTION_REF_PREFIX = "MOCK-"
TRANSACTION_REF_LENGTH = 16
TRANSACTION_REF_ALPHABET = string.ascii_uppercase + string.digits


class MockPaymentGateway(PaymentGateway):
    """模擬決済。指示が decline の場合は否認、それ以外は承認を1秒以内に返す。"""

    def authorize(self, request: PaymentRequest, *, timeout_seconds: int) -> PaymentResult:
        processed_at = timeutils.now()
        if request.mock_result == MOCK_DECLINE:
            return PaymentResult(
                result=RESULT_DECLINED,
                processed_at=processed_at,
                decline_reason_code=DECLINE_REASON_CODE,
            )
        reference = "".join(secrets.choice(TRANSACTION_REF_ALPHABET) for _ in range(TRANSACTION_REF_LENGTH))
        return PaymentResult(
            result=RESULT_APPROVED,
            processed_at=processed_at,
            transaction_ref=f"{TRANSACTION_REF_PREFIX}{reference}",
        )
