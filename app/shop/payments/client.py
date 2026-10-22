# trace: ADDR-009
"""決済ゲートウェイの選択と、応答待ち・応答検証の制御（IF-01-PRF-05、IF-01-EXC-04）。"""
import logging
import re
import time

from django.conf import settings

from shop.common.logging import build_extra
from shop.payments.gateway import (
    RESULT_APPROVED,
    RESULT_DECLINED,
    PaymentGateway,
    PaymentGatewayError,
    PaymentRequest,
    PaymentResponse,
)
from shop.payments.mock import MockPaymentGateway

logger = logging.getLogger("shop.payments")

TRANSACTION_REF_PATTERN = re.compile(r"^MOCK-[A-Za-z0-9]{16}$")


# trace: ADDR-009
def get_gateway() -> PaymentGateway:
    """設定で指定された決済ゲートウェイ実装を返す（既定は模擬実装）。"""
    name = getattr(settings, "PAYMENT_GATEWAY", "mock")
    if name == "mock":
        return MockPaymentGateway()
    raise PaymentGatewayError("未対応の決済ゲートウェイ設定です。")


# trace: ADDR-009
def authorize(request: PaymentRequest) -> PaymentResponse:
    """決済要求を1回だけ送信し、締切と応答項目を検証した応答を返す。

    締切超過・呼び出し失敗・応答不正は連携エラー（PaymentGatewayError）とする。自動再送は行わない。
    """
    deadline = float(getattr(settings, "PAYMENT_TIMEOUT_SECONDS", 10))
    started_at = time.monotonic()
    try:
        response = get_gateway().authorize(request)
    except PaymentGatewayError:
        raise
    except Exception as exc:  # 呼び出し自体の失敗は連携エラーとして扱う（IF-01-EXC-03）
        raise PaymentGatewayError("決済サービスの呼び出しに失敗しました。") from exc
    duration = time.monotonic() - started_at
    logger.info(
        "payment_authorize",
        extra=build_extra(
            event="payment_authorize",
            order_number=request.order_number,
            result=getattr(response, "result", None),
            duration_ms=int(duration * 1000),
        ),
    )
    if duration > deadline:
        raise PaymentGatewayError("決済サービスの応答が制限時間を超えました。")
    _validate_response(response)
    return response


# trace: ADDR-009
def _validate_response(response: PaymentResponse) -> None:
    """応答項目を IF-01-EXC-04 の全条件で検証する。"""
    if response.result not in {RESULT_APPROVED, RESULT_DECLINED}:
        raise PaymentGatewayError("決済サービスの応答が不正です。")
    if response.processed_at is None:
        raise PaymentGatewayError("決済サービスの応答が不正です。")
    if response.result == RESULT_APPROVED:
        if not response.transaction_ref or not TRANSACTION_REF_PATTERN.match(response.transaction_ref):
            raise PaymentGatewayError("決済サービスの応答が不正です。")
    elif not response.declined_reason_code:
        raise PaymentGatewayError("決済サービスの応答が不正です。")
