# trace: ADDR-001, ADDR-012
"""商品カタログ・在庫単位一覧の Web API（FR-010・FR-011・FR-012・FR-040）。"""

from rest_framework.request import Request
from rest_framework.response import Response

from catalog import services
from common.api import BaseApiView, require_admin, run


# trace: ADDR-001
class CategoryListApi(BaseApiView):
    """FR-010 GET /api/categories/（全件を items で返しページング項目を持たない）。"""

    def get(self, request: Request) -> Response:
        return run(request, "FR-010 categories", lambda: {"items": services.list_categories()})


# trace: ADDR-001, ADDR-012
class ProductListApi(BaseApiView):
    """FR-011 GET /api/products/（category_id・keyword・sort・page）。"""

    def get(self, request: Request) -> Response:
        query = request.query_params
        return run(
            request,
            "FR-011 products",
            lambda: services.search_products(
                query.get("category_id"), query.get("keyword"), query.get("sort"), query.get("page")
            ),
        )


# trace: ADDR-001
class ProductDetailApi(BaseApiView):
    """FR-012 GET /api/products/商品ID/。"""

    def get(self, request: Request, product_id: str) -> Response:
        return run(request, "FR-012 product", lambda: services.get_product_detail(product_id))


# trace: ADDR-001, ADDR-012
class StockUnitListApi(BaseApiView):
    """FR-040 GET /api/admin/stock-units/（管理者のみ）。"""

    def get(self, request: Request) -> Response:
        query = request.query_params

        def action() -> dict:
            require_admin(request, "E-040")
            return services.list_stock_units(
                query.get("sku"),
                query.get("product_name"),
                query.get("supplier_code"),
                query.get("low_stock_only"),
                query.get("page"),
            )

        return run(request, "FR-040 stock-units", action)
