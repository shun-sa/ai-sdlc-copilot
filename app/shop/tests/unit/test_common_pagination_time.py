# trace: FR-011, FR-030, FR-032, NFR-OM-01, ADDR-003, ADDR-007
"""ページング・日時処理・注文番号採番の単体テスト。

期待値は CMN-29（日時）、CMN-35（ページング）、ADDR-003（注文番号）から導出する。
"""
from datetime import UTC, datetime, timedelta

import pytest

from shop.common import timeutils
from shop.common.errors import ValidationError
from shop.common.pagination import paginate, parse_page
from shop.models import Item
from shop.services.order_numbers import ORDER_NUMBER_MAX, next_order_number
from shop.tests.unit import _helpers


# trace: FR-011
@pytest.mark.parametrize(("raw_page", "expected"), [(None, 1), ("", 1), ("1", 1), (" 2 ", 2), (3, 3)])
def test_parse_page_accepts_valid_values(raw_page, expected):
    """ページ番号は省略時1、1以上の整数を受け付ける。"""
    assert parse_page(raw_page) == expected


# trace: FR-011
@pytest.mark.parametrize("raw_page", ["0", "-1", "abc", "1.5", []])
def test_parse_page_rejects_invalid_values(raw_page):
    """ページ番号が1以上の整数でない場合は入力エラーとする（境界の外側）。"""
    with pytest.raises(ValidationError) as exc:
        parse_page(raw_page)

    assert exc.value.details[0]["field"] == "page"


# trace: FR-011
@pytest.mark.django_db
def test_paginate_returns_requested_page(supplier):
    """指定ページの要素と総件数・総ページ数を返す。"""
    for index in range(5):
        _helpers.make_item(f"ITEM-{index:03d}", f"商品{index:03d}")
    queryset = Item.objects.order_by("item_code")

    first = paginate(queryset, 1, 2)
    last = paginate(queryset, 3, 2)

    assert [item.item_code for item in first["results"]] == ["ITEM-000", "ITEM-001"]
    assert (first["total_count"], first["total_pages"], first["page_size"]) == (5, 3, 2)
    assert [item.item_code for item in last["results"]] == ["ITEM-004"]


# trace: FR-011
@pytest.mark.django_db
def test_paginate_returns_empty_results_beyond_last_page(supplier):
    """総ページ数を超えるページ番号は0件を返す（エラーにしない）。"""
    _helpers.make_item("ITEM-001", "商品")

    result = paginate(Item.objects.all(), 2, 20)

    assert result["results"] == []
    assert result["total_pages"] == 1


# trace: FR-011
@pytest.mark.django_db
def test_paginate_returns_zero_pages_when_empty(db):
    """総件数0件の場合は総ページ数0を返す。"""
    result = paginate(Item.objects.all(), 1, 20)

    assert (result["total_count"], result["total_pages"]) == (0, 0)


# trace: NFR-OM-01
def test_now_truncates_microseconds():
    """現在時刻はミリ秒以下を切り捨てた JST の日時を返す（CMN-29）。"""
    now = timeutils.now()

    assert now.microsecond == 0
    assert now.utcoffset() == timedelta(hours=9)


# trace: NFR-OM-01
def test_jst_converts_to_japan_standard_time():
    """日時は JST（+09:00）へ変換する。"""
    utc_value = datetime(2026, 5, 1, 3, 0, 0, tzinfo=UTC)

    converted = timeutils.jst(utc_value)

    assert converted.utcoffset() == timedelta(hours=9)
    assert converted.hour == 12
    assert timeutils.jst(None) is None


# trace: NFR-OM-01
def test_to_iso_outputs_iso8601_with_offset():
    """日時は ISO 8601（+09:00 付き）の文字列へ変換する。"""
    utc_value = datetime(2026, 5, 1, 3, 0, 0, tzinfo=UTC)

    assert timeutils.to_iso(utc_value) == "2026-05-01T12:00:00+09:00"
    assert timeutils.to_iso(None) is None


# trace: FR-030, ADDR-003
@pytest.mark.django_db
def test_next_order_number_format_and_sequence():
    """注文番号は PO-＋8桁のゼロ埋めで、採番のたびに大きくなる。"""
    first = next_order_number()
    second = next_order_number()

    assert first.startswith("PO-")
    assert len(first) == 11
    assert first[3:].isdigit()
    assert int(second[3:]) == int(first[3:]) + 1


# trace: FR-030, ADDR-003
def test_order_number_upper_limit_is_eight_digits():
    """注文番号の上限は8桁（99,999,999）である。"""
    assert ORDER_NUMBER_MAX == 99999999
