"""映画ルーター (FR-003 検索 / FR-004 詳細)。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_optional_user
from app.models.user import User
from app.schemas.search import MovieSearchQuery
from app.services.catalog_service import CatalogService
from app.templating import render

router = APIRouter()


@router.get("/movies")
def movie_search(
    request: Request,
    keyword: str | None = Query(default=None, max_length=200),
    genre: str | None = Query(default=None, max_length=50),
    sort: str = Query(default="release_date_desc", max_length=30),
    page: int = Query(default=1, ge=1),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    query = MovieSearchQuery(keyword=keyword, genre=genre, sort=sort, page=page)
    result = CatalogService(db).search_movies(query)
    return render(
        request,
        "movies/list.html",
        {"user": user, "result": result, "query": query},
    )


@router.get("/movies/{movie_id}")
def movie_detail(
    request: Request,
    movie_id: int,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    detail = CatalogService(db).movie_detail(movie_id)
    if detail is None:
        # C-DATA-001: 非公開/存在しない作品は表示しない
        raise HTTPException(status_code=404, detail="作品が見つかりません。")
    return render(
        request,
        "movies/detail.html",
        {"user": user, "detail": detail},
    )
