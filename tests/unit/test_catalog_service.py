"""カタログ参照サービス単体テスト (FR-003 / FR-004 / FR-005)。

対象: app/services/catalog_service.py
検証Requirement:
- FR-003 映画検索 / FR-005 商品検索 (検索・絞り込み・ページング)
- FR-004 映画詳細 (関連商品/上映回)
- C-DATA-001 (非公開は顧客画面に表示しない)
- C-DATA-003 (在庫ありのみ絞り込み)
- NFR-PERF-003 (1ページ標準件数)
DB Strategy: CONTAINER (使い捨てSQLite。検索SQLと可視フィルタを実DBで検証)。
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.movie import Movie
from app.models.product import Product
from app.models.screening import Screening
from app.schemas.search import MovieSearchQuery, ProductSearchQuery
from app.services.catalog_service import CatalogService


class TestMovieSearch:
    # FR-003 正常系: 公開映画がキーワード検索で取得できる
    def test_search_returns_published(
        self, db: Session, make_movie: Callable[..., Movie]
    ) -> None:
        make_movie(title="スペース大戦")
        result = CatalogService(db).search_movies(MovieSearchQuery(keyword="スペース"))
        assert result.total == 1
        assert result.items[0].title == "スペース大戦"

    # C-DATA-001: 非公開映画は検索結果に含めない
    def test_unpublished_excluded(
        self, db: Session, make_movie: Callable[..., Movie]
    ) -> None:
        make_movie(title="公開作", status="published")
        make_movie(title="非公開作", status="unpublished")
        result = CatalogService(db).search_movies(MovieSearchQuery())
        titles = {m.title for m in result.items}
        assert "公開作" in titles
        assert "非公開作" not in titles
        assert result.total == 1

    # FR-004 / C-DATA-001: 非公開映画の詳細は取得できない
    def test_detail_unpublished_returns_none(
        self, db: Session, make_movie: Callable[..., Movie]
    ) -> None:
        movie = make_movie(status="unpublished")
        assert CatalogService(db).movie_detail(movie.id) is None

    # FR-004: 公開映画の詳細は関連商品・上映回を含めて取得できる
    def test_detail_published(
        self,
        db: Session,
        make_movie: Callable[..., Movie],
        make_product: Callable[..., Product],
    ) -> None:
        movie = make_movie(title="対象作")
        make_product(name="関連商品", movie_id=movie.id)
        detail = CatalogService(db).movie_detail(movie.id)
        assert detail is not None
        assert detail.movie.title == "対象作"
        assert any(p.name == "関連商品" for p in detail.products)

    # FR-004: 上映終了回(開始時刻経過)は購入導線を非表示にするため is_saleable=False を付与する
    def test_detail_finished_screening_not_saleable(
        self,
        db: Session,
        make_movie: Callable[..., Movie],
        make_screening: Callable[..., Screening],
    ) -> None:
        movie = make_movie(title="上映終了含む作")
        now = datetime.now(timezone.utc)
        make_screening(movie_id=movie.id, starts_at=now - timedelta(hours=1))
        detail = CatalogService(db).movie_detail(movie.id)
        assert detail is not None
        assert len(detail.screenings) == 1
        # 上映開始後の回は購入不可 (購入導線非表示)
        assert detail.screenings[0].is_saleable is False

    # FR-004: 上映開始前かつ販売期間内の回は is_saleable=True を付与する
    def test_detail_upcoming_screening_saleable(
        self,
        db: Session,
        make_movie: Callable[..., Movie],
        make_screening: Callable[..., Screening],
    ) -> None:
        movie = make_movie(title="上映予定作")
        now = datetime.now(timezone.utc)
        make_screening(movie_id=movie.id, starts_at=now + timedelta(days=1))
        detail = CatalogService(db).movie_detail(movie.id)
        assert detail is not None
        assert len(detail.screenings) == 1
        # 上映開始前かつ販売期間内は購入可 (購入導線表示)
        assert detail.screenings[0].is_saleable is True

    # FR-004: 詳細の各上映回は ScreeningView として販売可否が個別付与される
    def test_detail_screening_saleability_is_per_screening(
        self,
        db: Session,
        make_movie: Callable[..., Movie],
        make_screening: Callable[..., Screening],
    ) -> None:
        movie = make_movie(title="混在作")
        now = datetime.now(timezone.utc)
        make_screening(movie_id=movie.id, starts_at=now - timedelta(hours=2))
        make_screening(movie_id=movie.id, starts_at=now + timedelta(days=2))
        detail = CatalogService(db).movie_detail(movie.id)
        assert detail is not None
        # starts_at 昇順: 先頭=上映終了回(不可), 末尾=上映予定回(可)
        saleability = [view.is_saleable for view in detail.screenings]
        assert saleability == [False, True]

    # FR-003: タイトル昇順ソートが適用される
    def test_sort_title_asc(self, db: Session, make_movie: Callable[..., Movie]) -> None:
        make_movie(title="B作品")
        make_movie(title="A作品")
        result = CatalogService(db).search_movies(MovieSearchQuery(sort="title_asc"))
        assert [m.title for m in result.items] == ["A作品", "B作品"]

    # FR-003: ジャンル絞り込みが適用される
    def test_genre_filter(self, db: Session, make_movie: Callable[..., Movie]) -> None:
        action = make_movie(title="アクション作")
        action.genre = "action"
        drama = make_movie(title="ドラマ作")
        drama.genre = "drama"
        db.commit()
        result = CatalogService(db).search_movies(MovieSearchQuery(genre="action"))
        assert {m.title for m in result.items} == {"アクション作"}


class TestProductSearch:
    # FR-005 / C-DATA-001: 非公開商品は検索結果に含めない
    def test_unpublished_excluded(
        self, db: Session, make_product: Callable[..., Product]
    ) -> None:
        make_product(name="公開商品", publish_status="published")
        make_product(name="非公開商品", publish_status="unpublished")
        result = CatalogService(db).search_products(ProductSearchQuery())
        names = {p.name for p in result.items}
        assert "公開商品" in names
        assert "非公開商品" not in names

    # FR-005 / C-DATA-003: 在庫ありのみ絞り込みは在庫0を除外する
    def test_in_stock_only_filter(
        self, db: Session, make_product: Callable[..., Product]
    ) -> None:
        make_product(name="在庫あり", stock=5)
        make_product(name="在庫なし", stock=0)
        result = CatalogService(db).search_products(ProductSearchQuery(in_stock_only=True))
        names = {p.name for p in result.items}
        assert names == {"在庫あり"}

    # FR-005: 商品詳細は非公開なら取得できない
    def test_product_detail_unpublished_none(
        self, db: Session, make_product: Callable[..., Product]
    ) -> None:
        product = make_product(publish_status="unpublished")
        assert CatalogService(db).product_detail(product.id) is None


class TestPagination:
    # NFR-PERF-003: 1ページ標準件数(20)でページングされる
    def test_page_size_and_total(
        self, db: Session, make_product: Callable[..., Product]
    ) -> None:
        for i in range(25):
            make_product(name=f"商品{i}", stock=1)
        page1 = CatalogService(db).search_products(ProductSearchQuery(page=1))
        page2 = CatalogService(db).search_products(ProductSearchQuery(page=2))
        assert page1.total == 25
        assert len(page1.items) == 20
        assert len(page2.items) == 5
        assert page1.total_pages == 2
