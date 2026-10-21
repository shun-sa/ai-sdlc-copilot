# trace: ADDR-010
"""管理者向け画面（SCR-101〜SCR-103）。FR-040〜FR-045 を実行する。"""

from __future__ import annotations

from typing import Any

from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from catalog import serializers as catalog_serializers
from catalog import services as catalog_services
from common.exceptions import BusinessError, InvalidStatusTransition, ValidationFailed
from common.pagination import page_range
from orders import serializers as order_serializers
from orders import services as order_services
from orders.models import STATUS_CHOICES
from web.support import query_prefix, require_admin, screen, set_flash
from web.views.messages import (
    OPERATION_CANCEL,
    OPERATION_DELIVER,
    OPERATION_SHIP,
    business_message,
    field_errors,
    invalid_status_message,
)
from web.views.order_views import enrich_order


def list_context(meta: dict[str, int], request: HttpRequest) -> dict[str, Any]:
    """一覧画面のページ情報を組み立てる。"""
    return {
        "meta": meta,
        "page_numbers": page_range(meta),
        "range_from": (meta["page"] - 1) * meta["page_size"] + 1 if meta["total_count"] else 0,
        "range_to": min(meta["page"] * meta["page_size"], meta["total_count"]),
        "query_prefix": query_prefix(request),
    }


@screen
@require_http_methods(["GET"])
def stock_unit_list(request: HttpRequest) -> HttpResponse:
    """SCR-101 在庫単位一覧（管理）。FR-040 を実行する。"""
    require_admin(request)
    suppliers = catalog_services.list_suppliers()
    context: dict[str, Any] = {
        "suppliers": suppliers,
        "form": {
            "sku": request.GET.get("sku", ""),
            "item_name": request.GET.get("item_name", ""),
            "supplier_id": request.GET.get("supplier_id", ""),
            "low_stock_only": request.GET.get("low_stock_only", ""),
        },
    }
    try:
        stock_units, meta, conditions = catalog_services.search_stock_units(request.GET.dict())
    except ValidationFailed as error:
        context["field_errors"] = field_errors(error)
        context["error_message"] = "検索条件に誤りがあります。条件を指定し直してください。"
        return render(request, "admin/stock_unit_list.html", context, status=400)

    context["stock_units"] = [catalog_serializers.admin_stock_unit_payload(unit) for unit in stock_units]
    context["conditions"] = conditions
    context.update(list_context(meta, request))
    return render(request, "admin/stock_unit_list.html", context)


@screen
@require_http_methods(["GET"])
def order_list(request: HttpRequest) -> HttpResponse:
    """SCR-102 注文一覧（管理）。FR-041 を実行する。"""
    require_admin(request)
    params = request.GET.dict()
    params["status"] = request.GET.getlist("status")
    context: dict[str, Any] = {
        "status_choices": STATUS_CHOICES,
        "form": {
            "order_number": request.GET.get("order_number", ""),
            "statuses": request.GET.getlist("status"),
            "ordered_from": request.GET.get("ordered_from", ""),
            "ordered_to": request.GET.get("ordered_to", ""),
            "buyer_email": request.GET.get("buyer_email", ""),
        },
    }
    try:
        orders, meta, conditions = order_services.admin_search_orders(params)
    except ValidationFailed as error:
        context["field_errors"] = field_errors(error)
        return render(request, "admin/order_list.html", context, status=400)

    context["orders"] = [order_serializers.admin_order_summary_payload(order) for order in orders]
    context["conditions"] = conditions
    context.update(list_context(meta, request))
    return render(request, "admin/order_list.html", context)


@screen
@require_http_methods(["GET"])
def order_detail(request: HttpRequest, purchase_order_id: str) -> HttpResponse:
    """SCR-103 注文詳細（管理）。FR-042 を実行する。"""
    require_admin(request)
    order = order_services.get_admin_order(purchase_order_id)
    payload = enrich_order(order_serializers.admin_order_payload(order))
    return render(request, "admin/order_detail.html", {"order": payload, "form": {"tracking_number": ""}})


@screen
@require_http_methods(["POST"])
def ship(request: HttpRequest, purchase_order_id: str) -> HttpResponse:
    """FR-043 出荷登録。"""
    admin_user = require_admin(request)
    tracking_number = request.POST.get("tracking_number")
    try:
        order_services.ship(admin_user, purchase_order_id, {"tracking_number": tracking_number})
    except ValidationFailed as error:
        # 理由は配送伝票番号欄の近傍へ表示し、入力値を保持して再表示する（SCR-103-OP01、CMN-17）。
        order = order_services.get_admin_order(purchase_order_id)
        payload = enrich_order(order_serializers.admin_order_payload(order))
        return render(
            request,
            "admin/order_detail.html",
            {
                "order": payload,
                "field_errors": field_errors(error),
                "form": {"tracking_number": "" if tracking_number is None else tracking_number},
            },
            status=400,
        )
    except InvalidStatusTransition as error:
        set_flash(request, invalid_status_message(error, OPERATION_SHIP))
        return redirect("web-admin-order-detail", purchase_order_id=purchase_order_id)
    except BusinessError as error:
        set_flash(request, business_message(error))
        return redirect("web-admin-order-detail", purchase_order_id=purchase_order_id)
    set_flash(request, "出荷登録しました。")
    return redirect("web-admin-order-detail", purchase_order_id=purchase_order_id)


@screen
@require_http_methods(["POST"])
def deliver(request: HttpRequest, purchase_order_id: str) -> HttpResponse:
    """FR-044 配達完了登録。"""
    admin_user = require_admin(request)
    try:
        order_services.deliver(admin_user, purchase_order_id)
    except InvalidStatusTransition as error:
        set_flash(request, invalid_status_message(error, OPERATION_DELIVER))
        return redirect("web-admin-order-detail", purchase_order_id=purchase_order_id)
    except BusinessError as error:
        set_flash(request, business_message(error))
        return redirect("web-admin-order-detail", purchase_order_id=purchase_order_id)
    set_flash(request, "配達完了を登録しました。")
    return redirect("web-admin-order-detail", purchase_order_id=purchase_order_id)


@screen
@require_http_methods(["POST"])
def cancel(request: HttpRequest, purchase_order_id: str) -> HttpResponse:
    """FR-045 注文キャンセル（管理者）。"""
    admin_user = require_admin(request)
    try:
        order_services.cancel_by_admin(admin_user, purchase_order_id)
    except InvalidStatusTransition as error:
        set_flash(request, invalid_status_message(error, OPERATION_CANCEL))
        return redirect("web-admin-order-detail", purchase_order_id=purchase_order_id)
    except BusinessError as error:
        set_flash(request, business_message(error))
        return redirect("web-admin-order-detail", purchase_order_id=purchase_order_id)
    set_flash(request, "注文をキャンセルしました。在庫を戻しました。")
    return redirect("web-admin-order-detail", purchase_order_id=purchase_order_id)
