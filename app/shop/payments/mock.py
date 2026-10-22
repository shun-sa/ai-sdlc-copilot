# trace: ADDR-009
"""決済サービスの模擬実装（EXT-01 MOCK）。外部ネットワークへ接続しない。"""
import secrets
import string

from django.utils import timezone

from shop.payments.gateway import (
    APPROVE,
    DECLINED_REASON_CODE,
    RESULT_APPROVED,
    RESULT_DECLINED,
    PaymentRequest,
    PaymentResponse,
)

TRANSACTION_REF_PREFIX = "MOCK-"
TRANSACTION_REF_LENGTH = 16


# trace: ADDR-009
class MockPaymentGateway:
    """模擬決済指示に従って承認・否認を返す模擬実装。待機・外部I/Oを行わない。"""

    def authorize(self, request: PaymentRequest) -> PaymentResponse:
        """模擬決済指示が approve なら承認、decline なら否認の応答を返す。"""
        processed_at = timezone.localtime(timezone.now()).replace(microsecond=0)
        if request.mock_result == APPROVE:
            return PaymentResponse(
                result=RESULT_APPROVED,
                transaction_ref=_generate_transaction_ref(),
                declined_reason_code=None,
                processed_at=processed_at,
            )
        return PaymentResponse(
            result=RESULT_DECLINED,
            transaction_ref=None,
            declined_reason_code=DECLINED_REASON_CODE,
            processed_at=processed_at,
        )


# trace: ADDR-009
def _generate_transaction_ref() -> str:
    """取引参照番号（MOCK- ＋英数字16桁）を生成する。"""
    alphabet = string.ascii_uppercase + string.digits
    suffix = "".join(secrets.choice(alphabet) for _ in range(TRANSACTION_REF_LENGTH))
    return f"{TRANSACTION_REF_PREFIX}{suffix}"
