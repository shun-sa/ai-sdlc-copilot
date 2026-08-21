"""販売可否判定 (is_saleable) 単体テスト。

対象: ProductRepository.is_saleable / ScreeningRepository.is_saleable
検証Requirement: C-DATA-001 (非公開非表示), C-DATA-002 (販売期間外は購入不可),
FR-009 (上映開始前/販売期間内のみ購入可), ERR-004。
DB Strategy: NOT_APPLICABLE (静的な純粋判定ロジック)。
境界の Inclusive/Exclusive は Repository 実装が参照する Requirement から導出。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.models.product import Product
from app.models.screening import Screening
from app.repositories.product_repository import ProductRepository
from app.repositories.screening_repository import ScreeningRepository

_NOW = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)


def _product(**kwargs: object) -> Product:
    base = {
        "name": "商品",
        "price_tax_included": 1000,
        "stock": 10,
        "publish_status": "published",
        "sales_start_at": None,
        "sales_end_at": None,
    }
    base.update(kwargs)
    return Product(**base)  # type: ignore[arg-type]


class TestProductSaleable:
    # 正常系: 公開かつ販売期間指定なしは販売可
    def test_published_no_window(self) -> None:
        assert ProductRepository.is_saleable(_product(), now=_NOW) is True

    # C-DATA-001: 非公開は販売不可
    def test_unpublished_not_saleable(self) -> None:
        assert (
            ProductRepository.is_saleable(_product(publish_status="unpublished"), now=_NOW) is False
        )

    # C-DATA-002 境界: 販売開始時刻ちょうどは販売可 (start <= now)
    def test_sales_start_boundary_inclusive(self) -> None:
        assert ProductRepository.is_saleable(_product(sales_start_at=_NOW), now=_NOW) is True

    # C-DATA-002: 販売開始前 (start > now) は販売不可
    def test_before_sales_start_not_saleable(self) -> None:
        assert (
            ProductRepository.is_saleable(
                _product(sales_start_at=_NOW + timedelta(seconds=1)), now=_NOW
            )
            is False
        )

    # C-DATA-002 境界: 販売終了時刻ちょうどは販売可 (end >= now)
    def test_sales_end_boundary_inclusive(self) -> None:
        assert ProductRepository.is_saleable(_product(sales_end_at=_NOW), now=_NOW) is True

    # C-DATA-002: 販売終了後 (end < now) は販売不可
    def test_after_sales_end_not_saleable(self) -> None:
        assert (
            ProductRepository.is_saleable(
                _product(sales_end_at=_NOW - timedelta(seconds=1)), now=_NOW
            )
            is False
        )


def _screening(**kwargs: object) -> Screening:
    base = {
        "movie_id": 1,
        "starts_at": _NOW + timedelta(days=1),
        "theater_name": "シアター1",
        "screen_name": "A",
        "seats_remaining": 10,
        "sales_start_at": None,
        "sales_end_at": None,
    }
    base.update(kwargs)
    return Screening(**base)  # type: ignore[arg-type]


class TestScreeningSaleable:
    # FR-009 正常系: 上映開始前かつ販売期間内は販売可
    def test_before_start_saleable(self) -> None:
        assert ScreeningRepository.is_saleable(_screening(), now=_NOW) is True

    # FR-009 境界: 上映開始時刻ちょうどは購入不可 (starts <= now は不可)
    def test_at_start_not_saleable(self) -> None:
        assert ScreeningRepository.is_saleable(_screening(starts_at=_NOW), now=_NOW) is False

    # FR-009: 上映開始後は購入不可
    def test_after_start_not_saleable(self) -> None:
        assert (
            ScreeningRepository.is_saleable(
                _screening(starts_at=_NOW - timedelta(seconds=1)), now=_NOW
            )
            is False
        )

    # C-DATA-002: 販売開始前は購入不可
    def test_before_sales_start_not_saleable(self) -> None:
        assert (
            ScreeningRepository.is_saleable(
                _screening(sales_start_at=_NOW + timedelta(hours=1)), now=_NOW
            )
            is False
        )

    # C-DATA-002: 販売終了後は購入不可
    def test_after_sales_end_not_saleable(self) -> None:
        assert (
            ScreeningRepository.is_saleable(
                _screening(sales_end_at=_NOW - timedelta(seconds=1)), now=_NOW
            )
            is False
        )
