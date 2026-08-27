"""app.schemas.catalog の検索パラメータ検証テスト。

Requirement: FR-003 / FR-005 / NFR-PERF-003
Criteria: normal-case, invalid-input, boundary-value
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.catalog import MovieSearchParams, ProductSearchParams


class TestMovieSearchParams:
    def test_defaults(self) -> None:
        params = MovieSearchParams()
        assert params.page == 1
        assert params.keyword is None

    def test_page_min_1(self) -> None:
        assert MovieSearchParams(page=1).page == 1

    def test_page_below_1_rejected(self) -> None:
        with pytest.raises(ValidationError):
            MovieSearchParams(page=0)

    def test_keyword_over_max_rejected(self) -> None:
        with pytest.raises(ValidationError):
            MovieSearchParams(keyword="あ" * 101)


class TestProductSearchParams:
    def test_defaults(self) -> None:
        params = ProductSearchParams()
        assert params.in_stock_only is False
        assert params.page == 1

    def test_movie_id_below_1_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ProductSearchParams(movie_id=0)

    def test_in_stock_only_flag(self) -> None:
        assert ProductSearchParams(in_stock_only=True).in_stock_only is True
