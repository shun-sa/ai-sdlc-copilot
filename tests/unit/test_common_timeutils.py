# trace: FR-011, FR-026, FR-031, FR-033, FR-041, ADDR-003
"""日時の取り扱い（CMN-29 秒単位・JST）の単体テスト。

期待結果は共通機能要件 CMN-29（処理時刻は秒単位）、FR-041 6.21.3（注文日の解釈）、
および応答の日時表現（ISO 8601・+09:00）から導出する。
"""

from __future__ import annotations

import datetime as dt

import pytest
from common import timeutils
from django.utils import timezone


# trace: FR-026
def test_now_truncates_microseconds(monkeypatch):
    """CMN-29：処理時刻はミリ秒以下を切り捨てた秒単位とする。"""
    monkeypatch.setattr(
        timezone, "now", lambda: dt.datetime(2027, 4, 10, 3, 4, 5, 987654, tzinfo=dt.UTC)
    )

    assert timeutils.now() == dt.datetime(2027, 4, 10, 3, 4, 5, tzinfo=dt.UTC)


# trace: FR-031
def test_to_jst_converts_to_plus_nine_hours():
    """UTC の日時を JST（+09:00）へ変換する。"""
    value = dt.datetime(2027, 4, 10, 0, 0, 0, tzinfo=dt.UTC)

    converted = timeutils.to_jst(value)

    assert converted.utcoffset() == dt.timedelta(hours=9)
    assert converted.hour == 9


# trace: FR-031
def test_to_jst_returns_none_for_none():
    """未設定の日時は未設定のまま返す。"""
    assert timeutils.to_jst(None) is None


# trace: FR-033
def test_to_iso_returns_iso8601_with_jst_offset():
    """日時は ISO 8601（+09:00 付き・秒単位）で表す。"""
    value = dt.datetime(2027, 4, 10, 12, 34, 56, 123456, tzinfo=timeutils.JST)

    assert timeutils.to_iso(value) == "2027-04-10T12:34:56+09:00"


# trace: FR-033
def test_to_iso_returns_none_for_none():
    """未設定の日時は null として表す。"""
    assert timeutils.to_iso(None) is None


# trace: FR-041
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2027-04-10", dt.date(2027, 4, 10)),
        ("2027-02-30", None),
        ("2027/04/10", None),
        ("", None),
        ("abc", None),
    ],
)
def test_parse_date_accepts_only_existing_iso_dates(value, expected):
    """FR-041 6.21.3：YYYY-MM-DD 形式の実在する日付だけを受け付ける。"""
    assert timeutils.parse_date(value) == expected


# trace: FR-011
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2027-04-10T12:00:00+09:00", dt.datetime(2027, 4, 10, 12, 0, 0, tzinfo=timeutils.JST)),
        ("2027-04-10T03:00:00Z", dt.datetime(2027, 4, 10, 3, 0, 0, tzinfo=dt.UTC)),
        ("2027-04-10T12:00:00", dt.datetime(2027, 4, 10, 12, 0, 0, tzinfo=timeutils.JST)),
        ("2027-04-10T12:00:00.987654+09:00", dt.datetime(2027, 4, 10, 12, 0, 0, tzinfo=timeutils.JST)),
        ("不正な日時", None),
    ],
)
def test_parse_datetime_interprets_values_as_jst_when_offset_is_absent(value, expected):
    """タイムゾーンなしの日時は JST として解釈し、ミリ秒以下は切り捨てる。"""
    assert timeutils.parse_datetime(value) == expected


# trace: FR-041
def test_start_of_day_is_midnight_jst():
    """注文日（開始）は指定日の 00:00:00（JST）以降を対象とする。"""
    assert timeutils.start_of_day(dt.date(2027, 4, 30)) == dt.datetime(
        2027, 4, 30, 0, 0, 0, tzinfo=timeutils.JST
    )


# trace: FR-041
def test_start_of_next_day_is_midnight_of_following_day_jst():
    """注文日（終了）は翌日 00:00:00（JST）より前を対象とする。"""
    assert timeutils.start_of_next_day(dt.date(2027, 4, 30)) == dt.datetime(
        2027, 5, 1, 0, 0, 0, tzinfo=timeutils.JST
    )
