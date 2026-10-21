# trace: ADDR-003
"""日時の取り扱い（JST・秒単位）に関する共通処理。"""

from __future__ import annotations

import datetime as dt

from django.utils import timezone

JST = dt.timezone(dt.timedelta(hours=9), "JST")


def now() -> dt.datetime:
    """処理時刻を返す（秒単位。ミリ秒以下は切り捨てる。CMN-29）。"""
    return timezone.now().replace(microsecond=0)


def to_jst(value: dt.datetime | None) -> dt.datetime | None:
    """日時を JST へ変換する。"""
    if value is None:
        return None
    return value.astimezone(JST)


def to_iso(value: dt.datetime | None) -> str | None:
    """日時を ISO 8601（+09:00 付き）の文字列へ変換する。"""
    converted = to_jst(value)
    if converted is None:
        return None
    return converted.replace(microsecond=0).isoformat()


def parse_date(value: str) -> dt.date | None:
    """YYYY-MM-DD 形式の日付を解釈する（解釈できない場合は None）。"""
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        return None


def parse_datetime(value: str) -> dt.datetime | None:
    """JST の日時として解釈する（解釈できない場合は None）。"""
    text = value.strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = dt.datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=JST)
    return parsed.replace(microsecond=0)


def start_of_day(value: dt.date) -> dt.datetime:
    """指定日の 00:00:00（JST）を返す。"""
    return dt.datetime.combine(value, dt.time.min, tzinfo=JST)


def start_of_next_day(value: dt.date) -> dt.datetime:
    """指定日の翌日 00:00:00（JST）を返す。"""
    return start_of_day(value) + dt.timedelta(days=1)
