"""トップページ (NFR-USAB-001: 主要機能への遷移)。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_optional_user
from app.models.user import User
from app.schemas.search import MovieSearchQuery
from app.services.catalog_service import CatalogService
from app.templating import render

router = APIRouter()


@router.get("/")
def index(
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    movies = CatalogService(db).search_movies(MovieSearchQuery(page=1))
    return render(request, "index.html", {"user": user, "movies": movies})
