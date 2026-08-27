"""ドメイン層（購入可否判定・モデル状態判定）の単体テスト。

Requirement: C-DATA-001/002/003 / FR-006/008/009 / ERR-003/004
ADR: ADR-010（エラー分類）
Criteria: normal-case, boundary-value, invalid-input, exception
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.constants import MovieStatus, PublishStatus
from app.errors import NotFoundError, OutOfSalesPeriodError, StockShortageError
from app.models.movie import Movie
from app.models.product import Product
from app.models.screening import Screening
from app.services.availability import (
    ensure_product_orderable,
    ensure_screening_purchasable,
)

UTC = timezone.utc
NOW = datetime(2026, 6, 15, 12, 0, tzinfo=UTC)


def _product(
    *,
    publish: PublishStatus = PublishStatus.PUBLISHED,
    stock: int = 10,
    start: datetime | None = None,
    end: datetime | None = None,
) -> Product:
    return Product(
        name="商品",
        price_tax_included=1000,
        stock=stock,
        publish_status=publish,
        sales_start_at=start if start is not None else NOW - timedelta(days=1),
        sales_end_at=end if end is not None else NOW + timedelta(days=1),
    )


def _screening(
    *,
    seats: int = 20,
    starts_at: datetime | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
) -> Screening:
    return Screening(
        movie_id=1,
        starts_at=starts_at if starts_at is not None else NOW + timedelta(days=1),
        theater_name="T",
        screen_name="S",
        seats_remaining=seats,
        sales_start_at=start if start is not None else NOW - timedelta(days=1),
        sales_end_at=end if end is not None else NOW + timedelta(hours=12),
    )


class TestProductModelState:
    def test_published(self) -> None:
        assert _product().is_published() is True

    def test_unpublished(self) -> None:
        assert _product(publish=PublishStatus.UNPUBLISHED).is_published() is False

    def test_in_stock_true(self) -> None:
        assert _product(stock=1).is_in_stock() is True

    def test_in_stock_zero_false(self) -> None:
        # C-DATA-003: 在庫0は購入不可。
        assert _product(stock=0).is_in_stock() is False

    def test_on_sale_within_period(self) -> None:
        assert _product().is_on_sale(NOW) is True

    def test_on_sale_start_boundary_inclusive(self) -> None:
        start = NOW
        assert _product(start=start).is_on_sale(NOW) is True

    def test_on_sale_before_start(self) -> None:
        # C-DATA-002: 販売開始前は購入不可。
        assert _product(start=NOW + timedelta(seconds=1)).is_on_sale(NOW) is False


class TestMovieModelState:
    def test_published(self) -> None:
        assert Movie(title="t", status=MovieStatus.PUBLISHED).is_published() is True

    def test_unpublished(self) -> None:
        assert Movie(title="t", status=MovieStatus.UNPUBLISHED).is_published() is False


class TestScreeningModelState:
    def test_on_sale_before_start_of_screening(self) -> None:
        assert _screening().is_on_sale(NOW) is True

    def test_not_on_sale_after_screening_started(self) -> None:
        # FR-009: 上映開始後は購入不可。
        s = _screening(starts_at=NOW - timedelta(seconds=1))
        assert s.is_on_sale(NOW) is False

    def test_not_on_sale_at_screening_start_boundary(self) -> None:
        # 上映開始時刻ちょうどは購入不可（reference < starts_at が条件）。
        s = _screening(starts_at=NOW)
        assert s.is_on_sale(NOW) is False

    def test_has_seats_boundary(self) -> None:
        assert _screening(seats=2).has_seats(2) is True
        assert _screening(seats=2).has_seats(3) is False


class TestEnsureProductOrderable:
    def test_orderable(self) -> None:
        assert ensure_product_orderable(_product(stock=5), 5, NOW) is not None

    def test_none_raises_not_found(self) -> None:
        with pytest.raises(NotFoundError):
            ensure_product_orderable(None, 1, NOW)

    def test_unpublished_raises_not_found(self) -> None:
        # C-DATA-001 / ERR-004: 非公開は表示不可。
        with pytest.raises(NotFoundError):
            ensure_product_orderable(_product(publish=PublishStatus.UNPUBLISHED), 1, NOW)

    def test_out_of_period_raises(self) -> None:
        # C-DATA-002 / ERR-004: 販売期間外。
        with pytest.raises(OutOfSalesPeriodError):
            ensure_product_orderable(_product(end=NOW - timedelta(seconds=1)), 1, NOW)

    def test_shortage_raises(self) -> None:
        # ERR-003: 在庫不足。
        with pytest.raises(StockShortageError):
            ensure_product_orderable(_product(stock=1), 2, NOW)

    def test_stock_exact_boundary_orderable(self) -> None:
        # 境界: 在庫ちょうどの数量は注文可能。
        assert ensure_product_orderable(_product(stock=3), 3, NOW) is not None


class TestEnsureScreeningPurchasable:
    def test_purchasable(self) -> None:
        assert ensure_screening_purchasable(_screening(seats=5), 5, NOW) is not None

    def test_none_raises_not_found(self) -> None:
        with pytest.raises(NotFoundError):
            ensure_screening_purchasable(None, 1, NOW)

    def test_out_of_period_raises(self) -> None:
        with pytest.raises(OutOfSalesPeriodError):
            ensure_screening_purchasable(_screening(end=NOW - timedelta(seconds=1)), 1, NOW)

    def test_after_screening_started_raises(self) -> None:
        # FR-009: 上映開始後は購入不可（is_on_sale=False → OutOfSalesPeriod）。
        with pytest.raises(OutOfSalesPeriodError):
            ensure_screening_purchasable(_screening(starts_at=NOW - timedelta(seconds=1)), 1, NOW)

    def test_insufficient_seats_raises(self) -> None:
        # ERR-003: 残席不足。
        with pytest.raises(StockShortageError):
            ensure_screening_purchasable(_screening(seats=1), 2, NOW)

    def test_seats_exact_boundary_purchasable(self) -> None:
        assert ensure_screening_purchasable(_screening(seats=4), 4, NOW) is not None
