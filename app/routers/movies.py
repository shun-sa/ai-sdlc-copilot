from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.routers import render
from app.schemas.catalog import MovieSearchParams
from app.services.catalog_service import CatalogService

router = APIRouter()


@router.get("/movies")
def search_movies(
    request: Request,
    keyword: str | None = None,
    genre: str | None = None,
    sort: str | None = None,
    page: int = 1,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
):
    params = MovieSearchParams(keyword=keyword, genre=genre, sort=sort, page=max(page, 1))
    result = CatalogService(db).search_movies(params)
    query_prefix = ""
    if keyword:
        query_prefix += f"keyword={keyword}&"
    if genre:
        query_prefix += f"genre={genre}&"
    if sort:
        query_prefix += f"sort={sort}&"
    return render(
        request, "movies.html", current_user,
        params=params, result=result, query_prefix=query_prefix,
    )


@router.get("/movies/{movie_id}")
def movie_detail(
    request: Request,
    movie_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
):
    detail = CatalogService(db).get_movie_detail(movie_id)  # 非公開はNotFoundError
    return render(request, "movie_detail.html", current_user, detail=detail)
