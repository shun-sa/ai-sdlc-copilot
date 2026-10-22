# trace: ADDR-001, ADDR-007
"""カート画面（SCR-005）と購入者のカート操作（FR-020〜FR-025）。"""
from typing import Any

from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from shop.common.errors import AppError
from shop.services import carts
from shop.web import messages, session
from shop.web.support import handle_app_errors, require_buyer, safe_internal_path
from shop.web.views_catalog import render_item_detail

CART_PATH = "/cart"
CART_TEMPLATE = "web/cart.html"


# trace: ADDR-001
def _render_cart(
    request: HttpRequest,
    cart: dict,
    error_message: str | None = None,
    status: int = 200,
    *,
    details: list[dict[str, str]] | None = None,
    error_line_id: Any = None,
    error_quantity: Any = None,
    coupon_code: Any = None,
) -> HttpResponse:
    """SCR-005 カートを表示する（失敗時は入力した数量・クーポンコードを保持して再表示する）。"""
    return render(
        request,
        CART_TEMPLATE,
        {
            "page_title": "カート",
            "cart": cart,
            "error_message": error_message,
            "details": details or [],
            "error_line_id": error_line_id,
            "error_quantity": error_quantity,
            "coupon_code": coupon_code or "",
        },
        status=status,
    )


# trace: ADDR-001
@handle_app_errors
@require_http_methods(["GET"])
def cart(request: HttpRequest) -> HttpResponse:
    """SCR-005 カート（FR-020）。"""
    user = require_buyer(request)
    return _render_cart(request, carts.view_cart(user))


# trace: ADDR-001
@handle_app_errors
@require_http_methods(["POST"])
def add_line(request: HttpRequest) -> HttpResponse:
    """カート明細追加（FR-021）。商品詳細画面（SCR-002）から実行する。"""
    user = require_buyer(request)
    stock_unit_id = request.POST.get("stock_unit_id", "")
    quantity = request.POST.get("quantity", "")
    item_id = request.POST.get("item_id", "")
    try:
        result = carts.add_line(user, stock_unit_id, quantity)
    except AppError as error:
        if error.code in {"VALIDATION_ERROR", "QUANTITY_LIMIT_EXCEEDED", "INSUFFICIENT_STOCK"}:
            return render_item_detail(
                request,
                item_id,
                selected_stock_unit_id=stock_unit_id,
                quantity=quantity,
                error_message=None if error.code == "VALIDATION_ERROR" else messages.cart_line_message(error),
                details=error.details,
                status=error.http_status,
            )
        raise
    session.set_flash(request, _added_message(result, stock_unit_id, quantity))
    return redirect(safe_internal_path(request, request.POST.get("return_to"), CART_PATH))


# trace: ADDR-001
def _added_message(cart_data: dict, stock_unit_id: Any, quantity: Any) -> str:
    """カート追加の完了メッセージ（SCR-002-OP01）を組み立てる。"""
    variant_name = ""
    for line in cart_data["lines"]:
        if str(line["stock_unit_id"]) == str(stock_unit_id):
            variant_name = line["variant_name"]
            break
    return f"カートに追加しました（{variant_name}、{quantity}個）。"


# trace: ADDR-001
@handle_app_errors
@require_http_methods(["POST"])
def update_line(request: HttpRequest, cart_line_id: str) -> HttpResponse:
    """カート明細数量変更（FR-022）。"""
    user = require_buyer(request)
    quantity = request.POST.get("quantity", "")
    try:
        carts.update_line_quantity(user, cart_line_id, quantity)
    except AppError as error:
        if error.code in {"VALIDATION_ERROR", "QUANTITY_LIMIT_EXCEEDED", "INSUFFICIENT_STOCK"}:
            return _render_cart(
                request,
                carts.view_cart(user),
                None if error.code == "VALIDATION_ERROR" else messages.cart_line_message(error),
                status=error.http_status,
                details=error.details,
                error_line_id=str(cart_line_id),
                error_quantity=quantity,
            )
        raise
    session.set_flash(request, "数量を変更しました。")
    return redirect(CART_PATH)


# trace: ADDR-001
@handle_app_errors
@require_http_methods(["POST"])
def remove_line(request: HttpRequest, cart_line_id: str) -> HttpResponse:
    """カート明細削除（FR-023）。確認ダイアログで承諾した場合のみ実行する。"""
    user = require_buyer(request)
    carts.remove_line(user, cart_line_id)
    session.set_flash(request, "カートから削除しました。")
    return redirect(CART_PATH)


# trace: ADDR-001
@handle_app_errors
@require_http_methods(["POST"])
def apply_coupon(request: HttpRequest) -> HttpResponse:
    """クーポン適用（FR-024）。"""
    user = require_buyer(request)
    code = request.POST.get("code", "")
    try:
        carts.apply_coupon(user, request.POST.get("code"))
    except AppError as error:
        if error.code.startswith("COUPON_") or error.code in {"VALIDATION_ERROR", "CART_EMPTY"}:
            cart_data = carts.view_cart(user)
            applied_coupon_code = (cart_data.get("coupon") or {}).get("code")
            is_validation_error = error.code == "VALIDATION_ERROR"
            return _render_cart(
                request,
                cart_data,
                # 入力エラーはクーポンコード欄の近傍にだけ表示する（SCR-005-OP03）。
                None if is_validation_error else messages.coupon_message(error, applied_coupon_code),
                status=error.http_status,
                details=messages.field_error_details(error) if is_validation_error else [],
                coupon_code=code,
            )
        raise
    session.set_flash(request, "クーポンを適用しました。")
    return redirect(CART_PATH)


# trace: ADDR-001
@handle_app_errors
@require_http_methods(["POST"])
def remove_coupon(request: HttpRequest) -> HttpResponse:
    """クーポン解除（FR-025）。"""
    user = require_buyer(request)
    carts.remove_coupon(user)
    session.set_flash(request, "クーポンを解除しました。")
    return redirect(CART_PATH)
