from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.routers import render
from app.schemas.catalog import ProductSearchParams
from app.services.catalog_service import CatalogService

router = APIRouter()


@router.get("/products")
def search_products(
    request: Request,
    keyword: str | None = None,
    movie_id: int | None = None,
    in_stock_only: bool = False,
    page: int = 1,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
):
    params = ProductSearchParams(
        keyword=keyword, movie_id=movie_id, in_stock_only=in_stock_only, page=max(page, 1)
    )
    result = CatalogService(db).search_products(params)
    query_prefix = ""
    if keyword:
        query_prefix += f"keyword={keyword}&"
    if in_stock_only:
        query_prefix += "in_stock_only=true&"
    return render(
        request, "products.html", current_user,
        params=params, result=result, query_prefix=query_prefix,
    )


@router.get("/products/{product_id}")
def product_detail(
    request: Request,
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
):
    product = CatalogService(db).get_product_detail(product_id)
    return render(request, "product_detail.html", current_user, product=product)
