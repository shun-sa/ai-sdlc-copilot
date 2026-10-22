# trace: ADDR-001, ADDR-006
"""管理者画面（SCR-101〜SCR-103）。FR-040〜FR-045 を画面から実行する。"""
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from shop.common.errors import AppError, ValidationError
from shop.services import admin_orders
from shop.web import messages, session
from shop.web.support import handle_app_errors, page_range, require_admin

ORDER_DETAIL_TEMPLATE = "web/admin_order_detail.html"


# trace: ADDR-006
@handle_app_errors
@require_http_methods(["GET"])
def stock_unit_list(request: HttpRequest) -> HttpResponse:
    """SCR-101 在庫単位一覧（管理）（FR-040）。"""
    require_admin(request)
    context = {
        "page_title": "在庫単位一覧",
        "suppliers": admin_orders.list_suppliers(),
        "form": {
            "sku": request.GET.get("sku", ""),
            "item_name": request.GET.get("item_name", ""),
            "supplier_id": request.GET.get("supplier_id", ""),
            "low_stock_only": request.GET.get("low_stock_only", ""),
        },
        "details": [],
    }
    try:
        page_data = admin_orders.search_stock_units(
            raw_sku=request.GET.get("sku"),
            raw_item_name=request.GET.get("item_name"),
            raw_supplier_id=request.GET.get("supplier_id"),
            raw_low_stock_only=request.GET.get("low_stock_only"),
            raw_page=request.GET.get("page"),
        )
    except ValidationError as error:
        context["details"] = error.details
        context["page_data"] = None
        context["page_numbers"] = []
        return render(request, "web/admin_stock_units.html", context, status=400)

    context["page_data"] = page_data
    context["page_numbers"] = page_range(page_data["page"], page_data["total_pages"])
    return render(request, "web/admin_stock_units.html", context)


# trace: ADDR-006
@handle_app_errors
@require_http_methods(["GET"])
def order_list(request: HttpRequest) -> HttpResponse:
    """SCR-102 注文一覧（管理）（FR-041）。"""
    require_admin(request)
    selected_statuses = request.GET.getlist("status")
    context = {
        "page_title": "注文一覧",
        "statuses": admin_orders.list_order_statuses(),
        "selected_statuses": selected_statuses,
        "form": {
            "order_number": request.GET.get("order_number", ""),
            "ordered_from": request.GET.get("ordered_from", ""),
            "ordered_to": request.GET.get("ordered_to", ""),
            "buyer_email": request.GET.get("buyer_email", ""),
        },
        "details": [],
    }
    try:
        page_data = admin_orders.search_orders(
            raw_order_number=request.GET.get("order_number"),
            raw_statuses=selected_statuses,
            raw_ordered_from=request.GET.get("ordered_from"),
            raw_ordered_to=request.GET.get("ordered_to"),
            raw_buyer_email=request.GET.get("buyer_email"),
            raw_page=request.GET.get("page"),
        )
    except ValidationError as error:
        context["details"] = error.details
        context["page_data"] = None
        context["page_numbers"] = []
        return render(request, "web/admin_order_list.html", context, status=400)

    context["page_data"] = page_data
    context["page_numbers"] = page_range(page_data["page"], page_data["total_pages"])
    return render(request, "web/admin_order_list.html", context)


# trace: ADDR-001
@handle_app_errors
@require_http_methods(["GET"])
def order_detail(request: HttpRequest, purchase_order_id: str) -> HttpResponse:
    """SCR-103 注文詳細（管理）（FR-042）。"""
    require_admin(request)
    order = admin_orders.get_order_detail(purchase_order_id)
    return render(
        request,
        ORDER_DETAIL_TEMPLATE,
        {
            "page_title": "注文詳細（管理）",
            "order": order,
            "error_message": None,
            "details": [],
            "form": {"tracking_number": ""},
        },
    )


# trace: ADDR-001
def _render_detail_with_error(
    request: HttpRequest, purchase_order_id: str, error: AppError, operation: str
) -> HttpResponse:
    """業務エラー・入力エラーを SCR-103 に表示する（状態不正は SCR-103-OP01〜OP03 の文言とする）。

    入力エラーは配送伝票番号欄の近傍に SCR-103-OP01 の文言で表示し、入力値を保持する（CMN-17）。
    """
    order = admin_orders.get_order_detail(purchase_order_id)
    is_validation_error = error.code == "VALIDATION_ERROR"
    return render(
        request,
        ORDER_DETAIL_TEMPLATE,
        {
            "page_title": "注文詳細（管理）",
            "order": order,
            "error_message": None if is_validation_error else messages.status_transition_message(error, operation),
            "details": messages.field_error_details(error) if is_validation_error else [],
            "form": {"tracking_number": request.POST.get("tracking_number", "")},
        },
        status=error.http_status,
    )


# trace: ADDR-001
@handle_app_errors
@require_http_methods(["POST"])
def ship(request: HttpRequest, purchase_order_id: str) -> HttpResponse:
    """出荷登録（FR-043）。確認ダイアログで承諾した場合のみ実行する。"""
    admin = require_admin(request)
    try:
        admin_orders.ship_order(admin, purchase_order_id, request.POST.get("tracking_number"))
    except AppError as error:
        if error.code in {"VALIDATION_ERROR", "INVALID_STATUS_TRANSITION"}:
            return _render_detail_with_error(request, purchase_order_id, error, "出荷登録")
        raise
    session.set_flash(request, messages.SHIPPED_MESSAGE)
    return redirect(f"/admin/purchase-orders/{purchase_order_id}")


# trace: ADDR-001
@handle_app_errors
@require_http_methods(["POST"])
def deliver(request: HttpRequest, purchase_order_id: str) -> HttpResponse:
    """配達完了登録（FR-044）。確認ダイアログで承諾した場合のみ実行する。"""
    admin = require_admin(request)
    try:
        admin_orders.deliver_order(admin, purchase_order_id)
    except AppError as error:
        if error.code == "INVALID_STATUS_TRANSITION":
            return _render_detail_with_error(request, purchase_order_id, error, "配達完了登録")
        raise
    session.set_flash(request, messages.DELIVERED_MESSAGE)
    return redirect(f"/admin/purchase-orders/{purchase_order_id}")


# trace: ADDR-001
@handle_app_errors
@require_http_methods(["POST"])
def cancel(request: HttpRequest, purchase_order_id: str) -> HttpResponse:
    """注文キャンセル（管理者）（FR-045）。確認ダイアログで承諾した場合のみ実行する。"""
    admin = require_admin(request)
    try:
        admin_orders.cancel_order(admin, purchase_order_id)
    except AppError as error:
        if error.code == "INVALID_STATUS_TRANSITION":
            return _render_detail_with_error(request, purchase_order_id, error, "キャンセル")
        raise
    session.set_flash(request, messages.ADMIN_ORDER_CANCELLED_MESSAGE)
    return redirect(f"/admin/purchase-orders/{purchase_order_id}")
