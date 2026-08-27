"""app.time_utils の表示整形・販売期間判定の単体テスト。

Requirement: C-UI-004（金額表記）/ C-UI-005（日時表記）/ C-DATA-002（販売期間）
Criteria: normal-case, boundary-value
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.time_utils import format_datetime, format_yen, is_within_period

UTC = timezone.utc


class TestFormatYen:
    def test_thousands_separator(self) -> None:
        # C-UI-004: 3桁区切り円表記（例: 1,980円）。
        assert format_yen(1980) == "1,980円"

    def test_millions(self) -> None:
        assert format_yen(1234567) == "1,234,567円"

    def test_zero(self) -> None:
        assert format_yen(0) == "0円"

    def test_below_thousand_no_separator(self) -> None:
        assert format_yen(980) == "980円"


class TestFormatDatetime:
    def test_format_pattern(self) -> None:
        # C-UI-005: YYYY/MM/DD HH:mm 形式。
        value = datetime(2026, 1, 9, 8, 5, tzinfo=UTC)
        assert format_datetime(value) == "2026/01/09 08:05"

    def test_naive_datetime_treated_as_utc(self) -> None:
        value = datetime(2026, 12, 31, 23, 59)
        assert format_datetime(value) == "2026/12/31 23:59"


class TestIsWithinPeriod:
    def test_inside_period(self) -> None:
        ref = datetime(2026, 6, 15, tzinfo=UTC)
        start = datetime(2026, 6, 1, tzinfo=UTC)
        end = datetime(2026, 6, 30, tzinfo=UTC)
        assert is_within_period(ref, start, end) is True

    def test_before_start_excluded(self) -> None:
        # C-DATA-002: 販売開始前は期間外。
        ref = datetime(2026, 5, 31, 23, 59, tzinfo=UTC)
        start = datetime(2026, 6, 1, tzinfo=UTC)
        assert is_within_period(ref, start, None) is False

    def test_at_start_boundary_inclusive(self) -> None:
        # 境界: 開始時刻ちょうどは期間内（inclusive）。
        start = datetime(2026, 6, 1, tzinfo=UTC)
        assert is_within_period(start, start, None) is True

    def test_at_end_boundary_inclusive(self) -> None:
        # 境界: 終了時刻ちょうどは期間内（inclusive）。
        end = datetime(2026, 6, 30, tzinfo=UTC)
        assert is_within_period(end, None, end) is True

    def test_after_end_excluded(self) -> None:
        # C-DATA-002: 販売終了後は期間外。
        end = datetime(2026, 6, 30, tzinfo=UTC)
        ref = datetime(2026, 7, 1, tzinfo=UTC)
        assert is_within_period(ref, None, end) is False

    def test_no_bounds_always_inside(self) -> None:
        assert is_within_period(datetime(2026, 1, 1, tzinfo=UTC), None, None) is True
