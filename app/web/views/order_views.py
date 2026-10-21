# trace: ADDR-010
"""注文手続き（SCR-006）〜注文詳細（SCR-010）の画面（FR-030〜FR-034）。"""

from __future__ import annotations

from typing import Any

from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from carts import serializers as cart_serializers
from carts import services as cart_services
from catalog import services as catalog_services
from common.exceptions import (
    BusinessError,
    CartEmpty,
    InvalidStatusTransition,
    PaymentServiceError,
    ValidationFailed,
)
from common.pagination import page_range
from orders import serializers as order_serializers
from orders import services as order_services
from orders.models import STATUS_CREATED
from web.prefectures import PREFECTURES
from web.support import query_prefix, require_buyer, screen, set_flash
from web.views.cart_views import enrich_cart
from web.views.messages import (
    OPERATION_CANCEL,
    OPERATION_PAY,
    REFUND_NOTICE_BUYER,
    business_message,
    checkout_message,
    field_errors,
    invalid_status_message,
    status_transition_message,
)


def enrich_order(payload: dict[str, Any]) -> dict[str, Any]:
    """表示用に税込単価を補う（注文確定時の金額は再計算しない）。"""
    for line in payload["lines"]:
        line["unit_price_incl_tax"] = catalog_services.price_incl_tax(line["unit_price"])
    return payload


@screen
@require_http_methods(["GET", "POST"])
def checkout(request: HttpRequest) -> HttpResponse:
    """SCR-006 注文手続き。FR-020 で内容を表示し、FR-030 で確定する。"""
    user = require_buyer(request)
    view = cart_services.show_cart(user)
    cart_payload = enrich_cart(cart_serializers.cart_payload(view))
    if not cart_payload["lines"]:
        set_flash(request, "カートに商品がありません。")
        return redirect("web-cart")

    form = {
        "recipient_name": user.full_name,
        "postal_code": "",
        "prefecture_code": "",
        "address_line1": "",
        "address_line2": "",
        "phone_number": "",
    }
    context: dict[str, Any] = {"cart": cart_payload, "prefectures": PREFECTURES, "form": form}
    if request.method == "GET":
        return render(request, "buyer/checkout.html", context)

    form = {key: request.POST.get(key, "") for key in form}
    context["form"] = form
    try:
        order = order_services.checkout(user, form)
    except ValidationFailed as error:
        context["field_errors"] = field_errors(error)
        return render(request, "buyer/checkout.html", context, status=400)
    except CartEmpty:
        set_flash(request, "カートに商品がありません。")
        return redirect("web-cart")
    except BusinessError as error:
        context["error_message"] = checkout_message(error, cart_payload["lines"])
        return render(request, "buyer/checkout.html", context, status=409)

    return redirect("web-order-complete", purchase_order_id=order.pk)


@screen
@require_http_methods(["GET"])
def order_complete(request: HttpRequest, purchase_order_id: str) -> HttpResponse:
    """SCR-007 注文完了。FR-033 を実行する。"""
    user = require_buyer(request)
    order = order_services.get_buyer_order(user, purchase_order_id)
    payload = enrich_order(order_serializers.buyer_order_payload(order))
    return render(request, "buyer/order_complete.html", {"order": payload})


@screen
@require_http_methods(["GET", "POST"])
def payment(request: HttpRequest, purchase_order_id: str) -> HttpResponse:
    """SCR-008 支払（模擬決済）。FR-031 を実行する。"""
    user = require_buyer(request)
    order = order_services.get_buyer_order(user, purchase_order_id)
    payload = enrich_order(order_serializers.buyer_order_payload(order))
    if payload["status"] != STATUS_CREATED:
        set_flash(request, status_transition_message(payload["status"], OPERATION_PAY))
        return redirect("web-order-detail", purchase_order_id=purchase_order_id)

    context: dict[str, Any] = {"order": payload, "mock_result": "approve"}
    if request.method == "GET":
        return render(request, "buyer/payment.html", context)

    mock_result = request.POST.get("mock_result", "approve")
    context["mock_result"] = mock_result
    try:
        order_services.pay(user, purchase_order_id, {"mock_result": mock_result})
    except ValidationFailed as error:
        context["field_errors"] = field_errors(error)
        return render(request, "buyer/payment.html", context, status=400)
    except InvalidStatusTransition as error:
        set_flash(request, invalid_status_message(error, OPERATION_PAY))
        return redirect("web-order-detail", purchase_order_id=purchase_order_id)
    except BusinessError as error:
        context["error_message"] = business_message(error)
        return render(request, "buyer/payment.html", context, status=409)
    except PaymentServiceError as error:
        context["error_message"] = error.message
        return render(request, "buyer/payment.html", context, status=502)

    set_flash(request, "支払が完了しました。")
    return redirect("web-order-detail", purchase_order_id=purchase_order_id)


@screen
@require_http_methods(["GET"])
def order_history(request: HttpRequest) -> HttpResponse:
    """SCR-009 注文履歴一覧。FR-032 を実行する。"""
    user = require_buyer(request)
    try:
        orders, meta = order_services.list_buyer_orders(user, request.GET.dict())
    except ValidationFailed:
        return render(
            request,
            "buyer/order_history.html",
            {"orders": [], "meta": None, "error_message": "ページの指定に誤りがあります。"},
            status=400,
        )
    context = {
        "orders": [order_serializers.order_summary_payload(order) for order in orders],
        "meta": meta,
        "page_numbers": page_range(meta),
        "range_from": (meta["page"] - 1) * meta["page_size"] + 1 if meta["total_count"] else 0,
        "range_to": min(meta["page"] * meta["page_size"], meta["total_count"]),
        "query_prefix": query_prefix(request),
    }
    return render(request, "buyer/order_history.html", context)


@screen
@require_http_methods(["GET"])
def order_detail(request: HttpRequest, purchase_order_id: str) -> HttpResponse:
    """SCR-010 注文詳細。FR-033 を実行する。"""
    user = require_buyer(request)
    order = order_services.get_buyer_order(user, purchase_order_id)
    payload = enrich_order(order_serializers.buyer_order_payload(order))
    return render(request, "buyer/order_detail.html", {"order": payload})


@screen
@require_http_methods(["POST"])
def cancel_order(request: HttpRequest, purchase_order_id: str) -> HttpResponse:
    """FR-034 注文キャンセル（購入者）。"""
    user = require_buyer(request)
    try:
        order = order_services.cancel_by_buyer(user, purchase_order_id)
    except InvalidStatusTransition as error:
        set_flash(request, invalid_status_message(error, OPERATION_CANCEL))
        return redirect("web-order-detail", purchase_order_id=purchase_order_id)
    except BusinessError as error:
        set_flash(request, business_message(error))
        return redirect("web-order-detail", purchase_order_id=purchase_order_id)
    # 支払済だった注文は、返金の取り扱いを併記する（SCR-010-OP02）。
    message = "注文をキャンセルしました。"
    if order.paid_at is not None:
        message = f"{message}{REFUND_NOTICE_BUYER}"
    set_flash(request, message)
    return redirect("web-order-detail", purchase_order_id=purchase_order_id)
