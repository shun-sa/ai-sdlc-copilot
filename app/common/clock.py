# trace: ADDR-011, ADDR-002
"""判定・記録に用いる現在日時の唯一の取得点（ADDR-011 4.3 の3・5、INV-001、ADDR-002 INV-001）。

開発用機能フラグが有効で試験支援モジュールが組み込まれている場合だけ、試験用状態の固定の現在日時を読む。
試験用状態の読取りは要求を処理しているスレッドの接続で行い、失敗した場合は実時刻へ切り替えずに例外とする。
10秒の打切り・処理時間の計測は本モジュールではなく実時間の単調増加の時計（time.monotonic）を用いる。
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from django.apps import apps
from django.conf import settings

JST = ZoneInfo("Asia/Tokyo")


# trace: ADDR-011
def _fixed_now() -> datetime | None:
    if not getattr(settings, "MINICOMMERCE_DEV_FEATURES", False):
        return None
    if not apps.is_installed("test_support"):
        return None
    from test_support.state import read_fixed_now

    return read_fixed_now()


# trace: ADDR-011, ADDR-002
def now() -> datetime:
    """現在日時（日本時間、秒未満を含む）。"""
    fixed = _fixed_now()
    if fixed is not None:
        return fixed.astimezone(JST)
    return datetime.now(tz=JST)


# trace: ADDR-011, ADDR-002
def now_seconds() -> datetime:
    """処理時刻（日本時間、ミリ秒以下を切り捨てた秒単位。CMN-29）。"""
    return truncate_seconds(now())


# trace: ADDR-002
def truncate_seconds(value: datetime) -> datetime:
    return value.replace(microsecond=0)


# trace: ADDR-011
def to_jst(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.astimezone(JST)


# trace: ADDR-011
def format_display(value: datetime | None) -> str:
    """通知文言の日時表記「YYYY/MM/DD HH:MM」（UI-23）。"""
    if value is None:
        return "－"
    return value.astimezone(JST).strftime("%Y/%m/%d %H:%M")
