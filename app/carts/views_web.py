# trace: ADDR-012, ADDR-004, ADDR-001
"""カートの画面（SCR-005 カート、SCR-002 の「カートに入れる」）。"""

from typing import Any

from django.contrib import messages
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.views.decorators.http import require_GET, require_POST

from carts import services
from catalog import services as catalog_services
from common.errors import ServiceError
from common.normalize import is_ascii_digits
from common.submit_token import run_with_token
from common.web import common_error_response, field_errors, render_page, require_buyer, run

CART_PATH = "/cart/"


# trace: ADDR-012, ADDR-001
def _render_cart(request: HttpRequest, extra: dict[str, Any] | None = None, status: int = 200) -> HttpResponse:
    try:
        cart = run(request, "FR-020 cart", lambda: services.get_cart(require_buyer(request, "E-020")))
    except ServiceError as exc:
        response = common_error_response(request, exc, CART_PATH)
        if response is not None:
            return response
        raise
    context: dict[str, Any] = {
        "page_title": "カート",
        "cart": cart,
        "shortage_ids": services.shortage_item_ids(cart),
        "errors": {},
        "item_errors": {},
    }
    if extra:
        context.update(extra)
    return render_page(request, "carts/cart.html", context, status=status)


# trace: ADDR-012
@require_GET
def cart_view(request: HttpRequest) -> HttpResponse:
    """SCR-005 カート（FR-020）。"""
    return _render_cart(request)


# trace: ADDR-012, ADDR-004
@require_POST
def cart_add_view(request: HttpRequest) -> HttpResponse:
    """SCR-002 の「カートに入れる」（FR-021）。成功・失敗とも SCR-002 に留まる。"""
    product_id = request.POST.get("product_id", "")
    detail_path = f"/products/{product_id}/" if is_ascii_digits(product_id) else "/"
    stock_unit_id = request.POST.get("stock_unit_id")
    quantity = request.POST.get("quantity")
    try:
        user = require_buyer(request, "E-021")
        run_with_token(
            "cart_add",
            request.POST.get("submit_token"),
            lambda ctx: run(request, "FR-021 cart-add", lambda: services.add_item(user, stock_unit_id, quantity, ctx)),
            lambda _result: {"status": "success", "redirect": detail_path},
        )
    except ServiceError as exc:
        response = common_error_response(request, exc, detail_path)
        if response is not None:
            return response
        return _render_product_with_error(request, product_id, exc)
    variant = _variant_name(product_id, stock_unit_id)
    messages.success(request, f"カートに追加しました（{variant}、{str(quantity).strip()}個）。")
    return HttpResponseRedirect(detail_path)


# trace: ADDR-012
def _variant_name(product_id: str, stock_unit_id: Any) -> str:
    try:
        product = catalog_services.get_product_detail(product_id)
    except ServiceError:
        return ""
    for unit in product["stock_units"]:
        if str(unit["stock_unit_id"]) == str(stock_unit_id).strip():
            return unit["variant_name"]
    return ""


# trace: ADDR-012
def _render_product_with_error(request: HttpRequest, product_id: str, exc: ServiceError) -> HttpResponse:
    try:
        product = catalog_services.get_product_detail(product_id)
    except ServiceError as inner:
        response = common_error_response(request, inner, None)
        if response is not None:
            return response
        raise
    in_stock = [s for s in product["stock_units"] if s["is_in_stock"]]
    context = {
        "page_title": "商品詳細",
        "product": product,
        "can_add_to_cart": True,
        "all_out_of_stock": not in_stock,
        "default_stock_unit_id": in_stock[0]["stock_unit_id"] if in_stock else None,
        "values": {
            "stock_unit_id": request.POST.get("stock_unit_id", ""),
            "quantity": request.POST.get("quantity", ""),
        },
        "errors": field_errors(exc),
        "error_message": exc.message if exc.error_type != "input_error" else None,
    }
    return render_page(request, "catalog/product_detail.html", context, status=exc.http_status)


# trace: ADDR-012, ADDR-004
def _cart_action(
    request: HttpRequest, operation: str, label: str, action: Any, success_message: str, item_id: str | None = None
) -> HttpResponse:
    try:
        run_with_token(
            operation,
            request.POST.get("submit_token"),
            lambda _ctx: run(request, label, action),
            lambda _result: {"status": "success", "redirect": CART_PATH},
        )
    except ServiceError as exc:
        response = common_error_response(request, exc, CART_PATH)
        if response is not None:
            return response
        extra: dict[str, Any] = {"error_message": exc.message}
        if item_id is not None:
            # 入力エラー（E-022-03）は数量の理由を明細に表示する（6.10.7「項目名（数量）と理由」、CMN-34）
            reasons = field_errors(exc).get("quantity") if exc.error_type == "input_error" else None
            extra["item_errors"] = {item_id: " ".join(reasons) if reasons else exc.message}
            extra["item_values"] = {item_id: request.POST.get("quantity", "")}
            extra["error_message"] = None
        if operation == "coupon_apply":
            extra["errors"] = field_errors(exc)
            extra["coupon_value"] = request.POST.get("coupon_code", "")
            if exc.error_type == "input_error":
                extra["error_message"] = None
        return _render_cart(request, extra, status=exc.http_status)
    messages.success(request, success_message)
    return HttpResponseRedirect(CART_PATH)


# trace: ADDR-012, ADDR-004
@require_POST
def cart_quantity_view(request: HttpRequest, cart_item_id: str) -> HttpResponse:
    """SCR-005 の「数量を変更」（FR-022）。"""
    return _cart_action(
        request,
        "cart_quantity",
        "FR-022 cart-quantity",
        lambda: services.change_quantity(require_buyer(request, "E-022"), cart_item_id, request.POST.get("quantity")),
        "数量を変更しました。",
        item_id=cart_item_id,
    )


# trace: ADDR-012, ADDR-004
@require_POST
def cart_delete_view(request: HttpRequest, cart_item_id: str) -> HttpResponse:
    """SCR-005 の「削除」（FR-023。確認に承諾した場合のみ送信される）。"""
    return _cart_action(
        request,
        "cart_delete",
        "FR-023 cart-delete",
        lambda: services.delete_item(require_buyer(request, "E-023"), cart_item_id),
        "カートから削除しました。",
    )


# trace: ADDR-012, ADDR-004
@require_POST
def coupon_apply_view(request: HttpRequest) -> HttpResponse:
    """SCR-005 の「適用する」（FR-024）。"""
    return _cart_action(
        request,
        "coupon_apply",
        "FR-024 coupon-apply",
        lambda: services.apply_coupon(require_buyer(request, "E-024"), request.POST.get("coupon_code")),
        "クーポンを適用しました。",
    )


# trace: ADDR-012, ADDR-004
@require_POST
def coupon_remove_view(request: HttpRequest) -> HttpResponse:
    """SCR-005 の「解除する」（FR-025）。"""
    return _cart_action(
        request,
        "coupon_remove",
        "FR-025 coupon-remove",
        lambda: services.remove_coupon(require_buyer(request, "E-025")),
        "クーポンを解除しました。",
    )
