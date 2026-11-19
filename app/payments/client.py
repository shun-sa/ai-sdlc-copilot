# trace: ADDR-008, ADDR-013, ADDR-004
"""決済要求（IFR-001）の呼出し側（ADDR-008 4.3 の3・4・7）。

送信操作を別スレッドで実行し、実時間（単調増加の時計）で10秒まで待って打ち切る。打切り後の結果は破棄する。
応答検証（IF-01-EXC-04 の全条件）とエラー検知を呼出し側で行う。自動再送しない（DD-009）。
送信時と受信時（10秒超過・応答不正を含む）に LOG-06 を要求の識別子付きで出力する（DD-008）。
"""

import queue
import re
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from common import codes
from common.logging import log_integration, monotonic_ms
from payments.gateway import CURRENCY_JPY, PaymentRequest, get_gateway

TIMEOUT_SECONDS = 10.0
_TRANSACTION_REF = re.compile(r"^MOCK-[A-Za-z0-9]{16}\Z")


# trace: ADDR-008
@dataclass(frozen=True)
class PaymentOutcome:
    result: str  # approved / declined / integration_error
    transaction_ref: str | None = None
    processed_at: datetime | None = None
    error: BaseException | None = None


# trace: ADDR-008
def _parse_processed_at(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is not None:
            # 協定世界時へ変換できない日時（年の範囲外）は保存・照会できないため応答不正とする
            parsed.astimezone(UTC)
    except (ValueError, OverflowError):
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.replace(microsecond=0)


# trace: ADDR-008
def validate_response(response: Any) -> PaymentOutcome | None:
    """IF-01-EXC-04 の応答検証。正しい形式なら承認・否認の結果、応答不正なら None。"""
    if not isinstance(response, dict):
        return None
    result = response.get("result")
    processed_at = _parse_processed_at(response.get("processed_at"))
    if result not in (codes.PaymentResult.APPROVED, codes.PaymentResult.DECLINED) or processed_at is None:
        return None
    if result == codes.PaymentResult.APPROVED:
        reference = response.get("transaction_ref")
        if not isinstance(reference, str) or not _TRANSACTION_REF.match(reference):
            return None
        return PaymentOutcome(codes.PaymentResult.APPROVED, reference, processed_at)
    reason = response.get("decline_reason")
    if not isinstance(reason, str) or not reason:
        return None
    return PaymentOutcome(codes.PaymentResult.DECLINED, None, processed_at)


# trace: ADDR-008, ADDR-013
def request_payment(order_number: str, amount: int, mock_instruction: str) -> PaymentOutcome:
    """決済要求を1回送信し、最大10秒待って結果を返す。"""
    request = PaymentRequest(order_number, amount, CURRENCY_JPY, mock_instruction)
    send = get_gateway().prepare(request)
    results: queue.Queue = queue.Queue(maxsize=1)

    def worker() -> None:
        try:
            results.put(("ok", send()))
        except BaseException as exc:  # noqa: BLE001 - 接続不可等は連携エラーとして扱う
            results.put(("error", exc))

    start = time.monotonic()
    log_integration("request", order_number, amount, CURRENCY_JPY)
    thread = threading.Thread(target=worker, name="mock-payment-send", daemon=True)
    thread.start()
    try:
        kind, payload = results.get(timeout=TIMEOUT_SECONDS)
    except queue.Empty:
        log_integration(
            "response", order_number, amount, CURRENCY_JPY, result="integration_error", duration_ms=monotonic_ms(start)
        )
        return PaymentOutcome(codes.PaymentResult.INTEGRATION_ERROR, error=TimeoutError("payment timeout"))
    if kind == "error":
        log_integration(
            "response", order_number, amount, CURRENCY_JPY, result="integration_error", duration_ms=monotonic_ms(start)
        )
        return PaymentOutcome(codes.PaymentResult.INTEGRATION_ERROR, error=payload)
    outcome = validate_response(payload)
    if outcome is None:
        log_integration(
            "response", order_number, amount, CURRENCY_JPY, result="integration_error", duration_ms=monotonic_ms(start)
        )
        return PaymentOutcome(codes.PaymentResult.INTEGRATION_ERROR, error=ValueError("invalid payment response"))
    log_integration(
        "response",
        order_number,
        amount,
        CURRENCY_JPY,
        result=outcome.result,
        transaction_ref=outcome.transaction_ref,
        duration_ms=monotonic_ms(start),
    )
    return outcome
