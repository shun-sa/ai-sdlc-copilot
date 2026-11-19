# trace: ADDR-012, ADDR-001
"""商品カタログの画面（SCR-001 商品一覧、SCR-002 商品詳細）と在庫単位一覧（SCR-101）。"""

from typing import Any

from django.http import HttpRequest, HttpResponse
from django.views.decorators.http import require_GET

from catalog import services
from common.errors import ServiceError
from common.web import (
    common_error_response,
    current_user,
    field_errors,
    pagination_context,
    render_page,
    require_admin,
    run,
)


# trace: ADDR-012, ADDR-001
@require_GET
def product_list_view(request: HttpRequest) -> HttpResponse:
    """SCR-001 商品一覧（FR-010 商品分類一覧＋FR-011 商品一覧検索）。"""
    query = request.GET
    context: dict[str, Any] = {
        "page_title": "商品一覧",
        "keyword": query.get("keyword", ""),
        "category_id": query.get("category_id", ""),
        "sort": query.get("sort", "newest"),
        "header_keyword": query.get("keyword", ""),
        "header_category_id": query.get("category_id", ""),
        "header_sort": query.get("sort", ""),
        "sort_choices": services_sort_choices(),
        "errors": {},
    }
    try:
        context["categories"] = run(request, "FR-010 categories", services.list_categories)
        result = run(
            request,
            "FR-011 products",
            lambda: services.search_products(
                query.get("category_id"), query.get("keyword"), query.get("sort"), query.get("page")
            ),
        )
    except ServiceError as exc:
        response = common_error_response(request, exc, None)
        if response is not None:
            return response
        context.update({"errors": field_errors(exc), "error_message": exc.message, "result": None})
        context.setdefault("categories", [])
        if "keyword" in context["errors"] and len(context["errors"]) == 1:
            context["error_message"] = None
        return render_page(request, "catalog/product_list.html", context, status=exc.http_status)
    selected = next((c for c in context["categories"] if str(c["category_id"]) == context["category_id"]), None)
    context.update(
        {
            "result": result,
            "selected_category": selected,
            **pagination_context(request, result),
        }
    )
    return render_page(request, "catalog/product_list.html", context)


# trace: ADDR-001
def services_sort_choices() -> list[tuple[str, str]]:
    from common.codes import SORT_CHOICES

    return list(SORT_CHOICES)


# trace: ADDR-012, ADDR-001
@require_GET
def product_detail_view(request: HttpRequest, product_id: str) -> HttpResponse:
    """SCR-002 商品詳細（FR-012）。管理者には規格・数量の選択と「カートに入れる」を表示しない。"""
    try:
        product = run(request, "FR-012 product", lambda: services.get_product_detail(product_id))
    except ServiceError as exc:
        response = common_error_response(request, exc, None)
        if response is not None:
            return response
        raise
    user = current_user(request)
    in_stock_units = [s for s in product["stock_units"] if s["is_in_stock"]]
    context = {
        "page_title": "商品詳細",
        "product": product,
        "can_add_to_cart": not (user is not None and user.user_type == "admin"),
        "all_out_of_stock": not in_stock_units,
        "default_stock_unit_id": in_stock_units[0]["stock_unit_id"] if in_stock_units else None,
        "values": {"quantity": "1"},
        "errors": {},
    }
    return render_page(request, "catalog/product_detail.html", context)


# trace: ADDR-012, ADDR-001
@require_GET
def stock_unit_list_view(request: HttpRequest) -> HttpResponse:
    """SCR-101 在庫単位一覧（管理）（FR-040）。"""
    query = request.GET
    context: dict[str, Any] = {
        "page_title": "在庫単位一覧（管理）",
        "values": {
            "sku": query.get("sku", ""),
            "product_name": query.get("product_name", ""),
            "supplier_code": query.get("supplier_code", ""),
            "low_stock_only": query.get("low_stock_only", "false"),
        },
        "errors": {},
    }
    try:
        result = run(
            request,
            "FR-040 stock-units",
            lambda: (
                require_admin(request, "E-040"),
                services.list_stock_units(
                    query.get("sku"),
                    query.get("product_name"),
                    query.get("supplier_code"),
                    query.get("low_stock_only"),
                    query.get("page"),
                ),
            )[1],
        )
    except ServiceError as exc:
        response = common_error_response(request, exc, request.get_full_path())
        if response is not None:
            return response
        context.update(
            {
                "suppliers": services.list_suppliers(),
                "errors": field_errors(exc),
                "error_message": exc.message,
                "result": None,
            }
        )
        return render_page(request, "catalog/admin_stock_units.html", context, status=exc.http_status)
    context.update({"suppliers": services.list_suppliers(), "result": result, **pagination_context(request, result)})
    return render_page(request, "catalog/admin_stock_units.html", context)
