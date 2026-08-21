"""商品ルーター (FR-005 検索・詳細)。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_session, get_optional_user
from app.models.session import SessionRecord
from app.models.user import User
from app.repositories.product_repository import ProductRepository
from app.schemas.search import ProductSearchQuery
from app.services.catalog_service import CatalogService
from app.templating import render

router = APIRouter()


@router.get("/products")
def product_search(
    request: Request,
    keyword: str | None = Query(default=None, max_length=200),
    category: str | None = Query(default=None, max_length=50),
    movie_id: int | None = Query(default=None, ge=1),
    in_stock_only: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    query = ProductSearchQuery(
        keyword=keyword,
        category=category,
        movie_id=movie_id,
        in_stock_only=in_stock_only,
        page=page,
    )
    result = CatalogService(db).search_products(query)
    return render(
        request,
        "products/list.html",
        {"user": user, "result": result, "query": query},
    )


@router.get("/products/{product_id}")
def product_detail(
    request: Request,
    product_id: int,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
    session: SessionRecord | None = Depends(get_current_session),
):
    product = CatalogService(db).product_detail(product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="商品が見つかりません。")
    saleable = ProductRepository.is_saleable(product)
    return render(
        request,
        "products/detail.html",
        {
            "user": user,
            "product": product,
            "saleable": saleable,
            "csrf_token": session.csrf_token if session else "",
        },
    )
