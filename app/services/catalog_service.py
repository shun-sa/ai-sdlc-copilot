from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.constants import DEFAULT_PAGE_SIZE
from app.errors import NotFoundError
from app.models.movie import Movie
from app.models.product import Product
from app.models.screening import Screening
from app.repositories.movie_repository import MovieRepository
from app.repositories.product_repository import ProductRepository
from app.repositories.screening_repository import ScreeningRepository
from app.schemas.catalog import MovieSearchParams, ProductSearchParams


@dataclass
class Paginated:
    items: list
    total: int
    page: int
    page_size: int


@dataclass
class MovieDetail:
    movie: Movie
    products: list[Product] = field(default_factory=list)
    screenings: list[Screening] = field(default_factory=list)


class CatalogService:
    """FR-003/004/005。映画・商品・上映回の検索/閲覧。公開制御を適用する（C-DATA-001）。"""

    def __init__(self, session: Session) -> None:
        self._movies = MovieRepository(session)
        self._products = ProductRepository(session)
        self._screenings = ScreeningRepository(session)

    def search_movies(self, params: MovieSearchParams) -> Paginated:
        offset = (params.page - 1) * DEFAULT_PAGE_SIZE
        rows, total = self._movies.search(
            keyword=params.keyword,
            genre=params.genre,
            sort=params.sort,
            offset=offset,
            limit=DEFAULT_PAGE_SIZE,
        )
        return Paginated(items=rows, total=total, page=params.page, page_size=DEFAULT_PAGE_SIZE)

    def get_movie_detail(self, movie_id: int) -> MovieDetail:
        movie = self._movies.get_published(movie_id)
        if movie is None:
            raise NotFoundError()  # C-DATA-001 / ERR-004: 非公開・存在しない作品は表示不可
        products = self._products.list_by_movie(movie_id)
        screenings = self._screenings.list_by_movie(movie_id)
        return MovieDetail(movie=movie, products=products, screenings=screenings)

    def search_products(self, params: ProductSearchParams) -> Paginated:
        offset = (params.page - 1) * DEFAULT_PAGE_SIZE
        rows, total = self._products.search(
            keyword=params.keyword,
            movie_id=params.movie_id,
            in_stock_only=params.in_stock_only,
            offset=offset,
            limit=DEFAULT_PAGE_SIZE,
        )
        return Paginated(items=rows, total=total, page=params.page, page_size=DEFAULT_PAGE_SIZE)

    def get_product_detail(self, product_id: int) -> Product:
        product = self._products.get_published(product_id)
        if product is None:
            raise NotFoundError()
        return product
