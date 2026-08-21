"""表示ヘルパの単体テスト (C-UI-004 / C-UI-005 / ADR-012)。

対象: app/templating.py の純粋な表示整形関数 (yen / jdatetime / jdate)。
検証Requirement:
- C-UI-004: 金額は税込・3桁区切り円表記で表示する（例: 1,980円）
- C-UI-005: 日時は YYYY/MM/DD HH:mm 形式で表示する
DB Strategy: NOT_APPLICABLE (純粋関数)。
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from app.templating import jdate, jdatetime, yen


class TestYen:
    # C-UI-004: 3桁区切り + 円 表記 (要件の例 1,980円)
    def test_thousands_separator(self) -> None:
        assert yen(1980) == "1,980円"

    # C-UI-004: 3桁を超える桁でも区切りを付与する
    def test_large_amount(self) -> None:
        assert yen(1234567) == "1,234,567円"

    # C-UI-004: 3桁以下は区切り無し
    def test_small_amount(self) -> None:
        assert yen(0) == "0円"
        assert yen(999) == "999円"

    # 値が無い場合は空文字 (表示なし)
    def test_none_is_empty(self) -> None:
        assert yen(None) == ""


class TestJdatetime:
    # C-UI-005: YYYY/MM/DD HH:mm 形式で表示する
    def test_format(self) -> None:
        value = datetime(2026, 8, 21, 9, 5, tzinfo=timezone.utc)
        assert jdatetime(value) == "2026/08/21 09:05"

    # C-UI-005: naive datetime は UTC とみなして整形する
    def test_naive_treated_as_utc(self) -> None:
        value = datetime(2026, 1, 2, 3, 4)
        assert jdatetime(value) == "2026/01/02 03:04"

    # 値が無い場合は空文字 (表示なし)
    def test_none_is_empty(self) -> None:
        assert jdatetime(None) == ""


class TestJdate:
    # 日付は YYYY/MM/DD 形式で表示する
    def test_format(self) -> None:
        assert jdate(date(2026, 8, 21)) == "2026/08/21"

    # 値が無い場合は空文字 (表示なし)
    def test_none_is_empty(self) -> None:
        assert jdate(None) == ""
