"""映画・商品カタログ参照サービス (FR-003 / FR-004 / FR-005)。"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.movie import Movie
from app.models.product import Product
from app.models.screening import Screening
from app.repositories.movie_repository import MovieRepository
from app.repositories.product_repository import ProductRepository
from app.repositories.screening_repository import ScreeningRepository
from app.schemas.search import MovieSearchQuery, ProductSearchQuery


@dataclass
class PageResult:
    items: list
    total: int
    page: int
    page_size: int

    @property
    def total_pages(self) -> int:
        return max(1, (self.total + self.page_size - 1) // self.page_size)


@dataclass
class ScreeningView:
    screening: Screening
    is_saleable: bool  # FR-004: 上映終了回/販売期間外は購入導線を表示しない


@dataclass
class MovieDetail:
    movie: Movie
    products: list[Product]
    screenings: list[ScreeningView]


class CatalogService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.movies = MovieRepository(db)
        self.products = ProductRepository(db)
        self.screenings = ScreeningRepository(db)

    def search_movies(self, query: MovieSearchQuery) -> PageResult:
        size = get_settings().page_size
        offset = (query.page - 1) * size
        rows, total = self.movies.search(
            keyword=query.keyword,
            genre=query.genre,
            sort=query.sort,
            limit=size,
            offset=offset,
        )
        return PageResult(items=rows, total=total, page=query.page, page_size=size)

    def movie_detail(self, movie_id: int) -> MovieDetail | None:
        # C-DATA-001: 非公開は表示しない (get_visibleで担保)
        movie = self.movies.get_visible(movie_id)
        if movie is None:
            return None
        products = self.products.list_by_movie(movie_id)
        # FR-004: 上映終了回は購入導線を非表示にするため販売可否を付与する
        screenings = [
            ScreeningView(screening=s, is_saleable=ScreeningRepository.is_saleable(s))
            for s in self.screenings.list_by_movie(movie_id)
        ]
        return MovieDetail(movie=movie, products=products, screenings=screenings)

    def search_products(self, query: ProductSearchQuery) -> PageResult:
        size = get_settings().page_size
        offset = (query.page - 1) * size
        rows, total = self.products.search(
            keyword=query.keyword,
            category=query.category,
            movie_id=query.movie_id,
            in_stock_only=query.in_stock_only,
            limit=size,
            offset=offset,
        )
        return PageResult(items=rows, total=total, page=query.page, page_size=size)

    def product_detail(self, product_id: int) -> Product | None:
        return self.products.get_visible(product_id)
