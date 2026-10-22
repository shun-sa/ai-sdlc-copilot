# trace: ADDR-001, ADDR-009
"""購入者の注文画面（SCR-006〜SCR-010）。FR-030〜FR-034 を画面から実行する。"""
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from shop.common.errors import AppError, ValidationError
from shop.services import carts, orders
from shop.web import messages, session
from shop.web.prefectures import PREFECTURES
from shop.web.support import handle_app_errors, page_range, require_buyer

CHECKOUT_TEMPLATE = "web/checkout.html"
ADDRESS_FIELDS = (
    "recipient_name",
    "postal_code",
    "prefecture_code",
    "address_line1",
    "address_line2",
    "phone_number",
)


# trace: ADDR-001
def _checkout_context(
    request: HttpRequest,
    cart: dict,
    form: dict,
    details: list,
    error_message: str | None,
    error_message_items: list[str] | None = None,
) -> dict:
    """SCR-006 注文手続きの表示情報を組み立てる。"""
    return {
        "page_title": "注文手続き",
        "cart": cart,
        "form": form,
        "details": details,
        "error_message": error_message,
        "error_message_items": error_message_items or [],
        "prefectures": PREFECTURES,
    }


# trace: ADDR-001
@handle_app_errors
@require_http_methods(["GET"])
def checkout_form(request: HttpRequest) -> HttpResponse:
    """SCR-006 注文手続き（配送先入力）を表示する。"""
    user = require_buyer(request)
    cart = carts.view_cart(user)
    return render(request, CHECKOUT_TEMPLATE, _checkout_context(request, cart, {}, [], None))


# trace: ADDR-001
@handle_app_errors
@require_http_methods(["POST"])
def checkout(request: HttpRequest) -> HttpResponse:
    """注文確定（FR-030）。確認ダイアログで承諾した場合のみ実行する。"""
    user = require_buyer(request)
    form = {name: request.POST.get(name, "") for name in ADDRESS_FIELDS}
    try:
        order = orders.checkout(user, form)
    except ValidationError as error:
        cart = carts.view_cart(user)
        context = _checkout_context(request, cart, form, error.details, None)
        return render(request, CHECKOUT_TEMPLATE, context, status=400)
    except AppError as error:
        if error.code == "CART_EMPTY":
            session.set_flash(request, messages.CART_EMPTY_ON_CHECKOUT_MESSAGE)
            return redirect("/cart")
        if error.code in {
            "ITEM_NOT_AVAILABLE",
            "QUANTITY_LIMIT_EXCEEDED",
            "INSUFFICIENT_STOCK",
            "COUPON_NOT_YET_VALID",
            "COUPON_EXPIRED",
            "COUPON_MIN_SPEND_NOT_MET",
        }:
            cart = carts.view_cart(user)
            error_message, error_message_items = messages.checkout_message(error, cart)
            context = _checkout_context(request, cart, form, [], error_message, error_message_items)
            return render(request, CHECKOUT_TEMPLATE, context, status=error.http_status)
        raise
    return redirect(f"/purchase-orders/{order['purchase_order_id']}/complete")


# trace: ADDR-001
@handle_app_errors
@require_http_methods(["GET"])
def order_complete(request: HttpRequest, purchase_order_id: str) -> HttpResponse:
    """SCR-007 注文完了。注文番号と合計を表示する。"""
    user = require_buyer(request)
    order = orders.get_order_detail(user, purchase_order_id)
    return render(request, "web/order_complete.html", {"page_title": "注文完了", "order": order})


# trace: ADDR-009
PAY_OPERATION = "支払"
MOCK_RESULTS = ("approve", "decline")
DEFAULT_MOCK_RESULT = "approve"


# trace: ADDR-009
def _selected_mock_result(request: HttpRequest) -> str:
    """選択した模擬決済の結果を保持する（SCR-008-IN01、CMN-17）。選択肢以外は初期値（承認）とする。"""
    value = request.POST.get("mock_result", "")
    return value if value in MOCK_RESULTS else DEFAULT_MOCK_RESULT


# trace: ADDR-009
def _pay_context(order: dict, mock_result: str) -> dict:
    """SCR-008 支払（模擬決済）の表示情報を組み立てる。"""
    return {
        "page_title": "支払",
        "order": order,
        "error_message": None,
        "details": [],
        "mock_results": MOCK_RESULTS,
        "mock_result": mock_result,
    }


# trace: ADDR-009
@handle_app_errors
@require_http_methods(["GET", "POST"])
def pay(request: HttpRequest, purchase_order_id: str) -> HttpResponse:
    """SCR-008 支払（模擬決済）（FR-031）。"""
    user = require_buyer(request)
    order = orders.get_order_detail(user, purchase_order_id)
    detail_path = f"/purchase-orders/{purchase_order_id}"
    if not order["can_pay"]:
        # 状態が注文受付以外は SCR-010 へ遷移する（SCR-008 の表示条件）。状態の判定は services の can_pay に従う。
        session.set_flash(request, messages.operation_unavailable_message(order["status"], PAY_OPERATION))
        return redirect(detail_path)

    if request.method == "GET":
        return render(request, "web/pay.html", _pay_context(order, DEFAULT_MOCK_RESULT))

    try:
        orders.pay_order(user, purchase_order_id, request.POST.get("mock_result"))
    except AppError as error:
        if error.code == "INVALID_STATUS_TRANSITION":
            session.set_flash(request, messages.status_transition_message(error, PAY_OPERATION))
            return redirect(detail_path)
        if error.code in {"PAYMENT_DECLINED", "PAYMENT_SERVICE_ERROR", "VALIDATION_ERROR"}:
            context = _pay_context(orders.get_order_detail(user, purchase_order_id), _selected_mock_result(request))
            if error.code == "VALIDATION_ERROR":
                context["details"] = messages.field_error_details(error)
            else:
                context["error_message"] = messages.payment_message(error)
            return render(request, "web/pay.html", context, status=error.http_status)
        raise
    session.set_flash(request, "支払が完了しました。")
    return redirect(detail_path)


# trace: ADDR-001
@handle_app_errors
@require_http_methods(["GET"])
def order_list(request: HttpRequest) -> HttpResponse:
    """SCR-009 注文履歴一覧（FR-032）。"""
    user = require_buyer(request)
    try:
        page_data = orders.list_orders(user, request.GET.get("page"))
    except ValidationError as error:
        return render(
            request,
            "web/order_list.html",
            {"page_title": "注文履歴", "details": error.details, "page_data": None, "page_numbers": []},
            status=400,
        )
    return render(
        request,
        "web/order_list.html",
        {
            "page_title": "注文履歴",
            "page_data": page_data,
            "page_numbers": page_range(page_data["page"], page_data["total_pages"]),
            "details": [],
        },
    )


# trace: ADDR-001
@handle_app_errors
@require_http_methods(["GET"])
def order_detail(request: HttpRequest, purchase_order_id: str) -> HttpResponse:
    """SCR-010 注文詳細（FR-033）。"""
    user = require_buyer(request)
    order = orders.get_order_detail(user, purchase_order_id)
    return render(
        request,
        "web/order_detail.html",
        {"page_title": "注文詳細", "order": order, "error_message": None},
    )


# trace: ADDR-001
@handle_app_errors
@require_http_methods(["POST"])
def cancel(request: HttpRequest, purchase_order_id: str) -> HttpResponse:
    """注文キャンセル（FR-034）。確認ダイアログで承諾した場合のみ実行する。"""
    user = require_buyer(request)
    try:
        order = orders.cancel_order(user, purchase_order_id)
    except AppError as error:
        if error.code == "INVALID_STATUS_TRANSITION":
            return render(
                request,
                "web/order_detail.html",
                {
                    "page_title": "注文詳細",
                    "order": orders.get_order_detail(user, purchase_order_id),
                    "error_message": messages.status_transition_message(error, "キャンセル"),
                },
                status=error.http_status,
            )
        raise
    session.set_flash(request, messages.buyer_cancel_message(order))
    return redirect(f"/purchase-orders/{purchase_order_id}")
