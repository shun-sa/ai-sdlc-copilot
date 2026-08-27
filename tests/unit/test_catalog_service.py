"""CatalogService の単体テスト（使い捨て in-memory SQLite）。

Requirement: FR-003 / FR-004 / FR-005 / C-DATA-001 / NFR-PERF-003 / ERR-004
Criteria: normal-case, exception, database, boundary-value
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.constants import MovieStatus, PublishStatus
from app.errors import NotFoundError
from app.schemas.catalog import MovieSearchParams, ProductSearchParams
from app.services.catalog_service import CatalogService

from .conftest import make_movie, make_product, make_screening


class TestSearchMovies:
    def test_returns_only_published(self, db_session: Session) -> None:
        # C-DATA-001: 非公開作品は表示しない。
        make_movie(db_session, title="公開作", status=MovieStatus.PUBLISHED)
        make_movie(db_session, title="非公開作", status=MovieStatus.UNPUBLISHED)
        result = CatalogService(db_session).search_movies(MovieSearchParams())
        titles = [m.title for m in result.items]
        assert "公開作" in titles
        assert "非公開作" not in titles

    def test_keyword_filter(self, db_session: Session) -> None:
        make_movie(db_session, title="スペース大戦")
        make_movie(db_session, title="海の物語")
        result = CatalogService(db_session).search_movies(MovieSearchParams(keyword="スペース"))
        assert result.total == 1
        assert result.items[0].title == "スペース大戦"

    def test_zero_hit_returns_empty(self, db_session: Session) -> None:
        # FR-003: 0件時。
        make_movie(db_session, title="唯一作")
        result = CatalogService(db_session).search_movies(MovieSearchParams(keyword="存在しない"))
        assert result.total == 0
        assert result.items == []

    def test_pagination_page_size_20(self, db_session: Session) -> None:
        # NFR-PERF-003: 1ページ20件。
        for i in range(25):
            make_movie(db_session, title=f"映画{i:02d}")
        result = CatalogService(db_session).search_movies(MovieSearchParams(page=1))
        assert result.total == 25
        assert len(result.items) == 20
        assert result.page_size == 20

    def test_pagination_second_page(self, db_session: Session) -> None:
        for i in range(25):
            make_movie(db_session, title=f"映画{i:02d}")
        result = CatalogService(db_session).search_movies(MovieSearchParams(page=2))
        assert len(result.items) == 5


class TestMovieDetail:
    def test_returns_movie_with_related(self, db_session: Session) -> None:
        movie = make_movie(db_session, title="対象作")
        make_product(db_session, name="関連商品", movie_id=movie.id)
        make_screening(db_session, movie_id=movie.id)
        detail = CatalogService(db_session).get_movie_detail(movie.id)
        assert detail.movie.id == movie.id
        assert len(detail.products) == 1
        assert len(detail.screenings) == 1

    def test_unpublished_raises_not_found(self, db_session: Session) -> None:
        # C-DATA-001 / ERR-004: 非公開作品は表示不可。
        movie = make_movie(db_session, status=MovieStatus.UNPUBLISHED)
        with pytest.raises(NotFoundError):
            CatalogService(db_session).get_movie_detail(movie.id)

    def test_missing_raises_not_found(self, db_session: Session) -> None:
        with pytest.raises(NotFoundError):
            CatalogService(db_session).get_movie_detail(9999)


class TestSearchProducts:
    def test_returns_only_published(self, db_session: Session) -> None:
        make_product(db_session, name="公開商品", publish_status=PublishStatus.PUBLISHED)
        make_product(db_session, name="非公開商品", publish_status=PublishStatus.UNPUBLISHED)
        result = CatalogService(db_session).search_products(ProductSearchParams())
        names = [p.name for p in result.items]
        assert "公開商品" in names
        assert "非公開商品" not in names

    def test_in_stock_only_filter(self, db_session: Session) -> None:
        # FR-005: 在庫ありのみ。
        make_product(db_session, name="在庫あり", stock=5)
        make_product(db_session, name="在庫なし", stock=0)
        result = CatalogService(db_session).search_products(ProductSearchParams(in_stock_only=True))
        names = [p.name for p in result.items]
        assert "在庫あり" in names
        assert "在庫なし" not in names

    def test_get_product_detail_missing_raises(self, db_session: Session) -> None:
        with pytest.raises(NotFoundError):
            CatalogService(db_session).get_product_detail(9999)
