# trace: ADDR-007
"""日時の共通処理（CMN-29。基準は JST、判定は秒単位）。"""
from datetime import datetime

from django.utils import timezone


# trace: ADDR-007
def now() -> datetime:
    """ミリ秒以下を切り捨てた現在時刻（JST 基準の aware な日時）を返す。"""
    return timezone.localtime(timezone.now()).replace(microsecond=0)


# trace: ADDR-007
def jst(value: datetime | None) -> datetime | None:
    """日時を JST（+09:00）へ変換する。応答では ISO 8601 として出力される。"""
    if value is None:
        return None
    return timezone.localtime(value)


# trace: ADDR-007
def to_iso(value: datetime | None) -> str | None:
    """日時を ISO 8601（+09:00 付き）の文字列へ変換する。"""
    if value is None:
        return None
    return timezone.localtime(value).isoformat()
