# trace: ADDR-008, ADDR-011
"""決済サービス（模擬）（ADDR-008 4.3 の2）。外部へ通信せず、指示どおりの結果を1秒以内に返す。

承認時は MOCK-＋暗号論的乱数の英数字16文字の取引参照番号と処理日時（時刻提供点の時刻、秒単位）を返す。
開発用機能フラグが有効なときだけ、試験用状態（遅延秒数・応答モード：ADDR-011）を送信前に読み取って反映する。
"""

import secrets
import string
import time
from collections.abc import Callable
from typing import Any

from django.apps import apps
from django.conf import settings

from common import clock
from payments.gateway import PaymentGateway, PaymentRequest

_ALPHANUMERIC = string.ascii_letters + string.digits


# trace: ADDR-008
def _transaction_ref() -> str:
    return "MOCK-" + "".join(secrets.choice(_ALPHANUMERIC) for _ in range(16))


# trace: ADDR-011
def _test_settings() -> tuple[float, str]:
    """試験用状態（遅延秒数・応答モード）。フラグ無効時は参照しない。"""
    if not getattr(settings, "MINICOMMERCE_DEV_FEATURES", False) or not apps.is_installed("test_support"):
        return 0.0, "normal"
    from test_support.state import read_payment_settings

    return read_payment_settings()


# trace: ADDR-008, ADDR-011
class MockPaymentGateway(PaymentGateway):
    def prepare(self, request: PaymentRequest) -> Callable[[], dict[str, Any]]:
        delay, mode = _test_settings()
        processed_at = clock.now_seconds().isoformat()
        instruction = request.mock_instruction
        reference = _transaction_ref()

        def send() -> dict[str, Any]:
            # 送信スレッドはデータベースに接続しない（読み取り済みの不変の値だけを使う）
            if delay > 0:
                time.sleep(delay)
            if mode == "connection_error":
                raise ConnectionError("mock payment service unavailable")
            response: dict[str, Any] = {"result": instruction, "processed_at": processed_at}
            if instruction == "approved":
                response["transaction_ref"] = reference
            else:
                response["decline_reason"] = "模擬決済で否認が指示されました"
            if mode == "invalid_result":
                response["result"] = "unknown"
            elif mode == "missing_result":
                response.pop("result", None)
            elif mode == "missing_processed_at":
                response.pop("processed_at", None)
            elif mode == "missing_transaction_ref":
                response["result"] = "approved"
                response.pop("transaction_ref", None)
            elif mode == "invalid_transaction_ref":
                response["result"] = "approved"
                response["transaction_ref"] = "MOCK-INVALID"
            elif mode == "missing_decline_reason":
                response["result"] = "declined"
                response.pop("decline_reason", None)
                response.pop("transaction_ref", None)
            return response

        return send
