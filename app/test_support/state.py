# trace: ADDR-011
"""試験用状態の読取り・設定（ADDR-011 4.3 の2〜4）。

読取りは要求を処理しているスレッドのデータベース接続（業務処理と同じ接続）でだけ行う（DD-003）。
自動テストは本モジュールの設定関数を pytest のフィクスチャから呼び、各テストの終了時に必ず clear する（INV-003）。
"""

from datetime import datetime

from test_support.models import ORDER_FAULT_POINTS, PAYMENT_MODES, TestState

SINGLETON_ID = 1
_PAYMENT_MODE_VALUES = {value for value, _ in PAYMENT_MODES}
_FAULT_VALUES = {value for value, _ in ORDER_FAULT_POINTS}


# trace: ADDR-011
def _row() -> TestState | None:
    return TestState.objects.filter(pk=SINGLETON_ID).first()


# trace: ADDR-011
def read_fixed_now() -> datetime | None:
    row = _row()
    return row.fixed_now if row is not None else None


# trace: ADDR-011
def read_payment_settings() -> tuple[float, str]:
    row = _row()
    if row is None:
        return 0.0, "normal"
    return float(row.payment_delay_seconds), row.payment_mode


# trace: ADDR-011
def read_order_fault_point() -> str:
    row = _row()
    return row.order_fault_point if row is not None else "none"


# trace: ADDR-011
def set_state(
    *,
    fixed_now: datetime | None = None,
    payment_delay_seconds: float | None = None,
    payment_mode: str | None = None,
    order_fault_point: str | None = None,
) -> TestState:
    """指定した項目だけを更新する（未指定の項目は現在の値を保つ）。"""
    if payment_mode is not None and payment_mode not in _PAYMENT_MODE_VALUES:
        raise ValueError("unknown payment_mode")
    if order_fault_point is not None and order_fault_point not in _FAULT_VALUES:
        raise ValueError("unknown order_fault_point")
    if payment_delay_seconds is not None and payment_delay_seconds < 0:
        raise ValueError("payment_delay_seconds must be >= 0")
    row, _ = TestState.objects.get_or_create(pk=SINGLETON_ID)
    if fixed_now is not None:
        if fixed_now.tzinfo is None:
            raise ValueError("fixed_now must be timezone-aware")
        row.fixed_now = fixed_now
    if payment_delay_seconds is not None:
        row.payment_delay_seconds = payment_delay_seconds
    if payment_mode is not None:
        row.payment_mode = payment_mode
    if order_fault_point is not None:
        row.order_fault_point = order_fault_point
    row.save()
    return row


# trace: ADDR-011
def clear_state() -> None:
    """全項目を既定値（実時刻・遅延なし・通常応答・障害なし）に戻す。"""
    TestState.objects.filter(pk=SINGLETON_ID).delete()


# trace: ADDR-011
def show_state() -> dict[str, object]:
    row = _row()
    if row is None:
        return {"fixed_now": None, "payment_delay_seconds": 0.0, "payment_mode": "normal", "order_fault_point": "none"}
    return {
        "fixed_now": row.fixed_now.isoformat() if row.fixed_now else None,
        "payment_delay_seconds": row.payment_delay_seconds,
        "payment_mode": row.payment_mode,
        "order_fault_point": row.order_fault_point,
    }
