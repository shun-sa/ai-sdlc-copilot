# trace: ADDR-012, ADDR-004, ADDR-001, ADDR-008
"""注文の画面（SCR-006〜SCR-010）と注文管理の画面（SCR-102・SCR-103）。"""

from typing import Any

from django.contrib import messages
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from carts import services as cart_services
from common.codes import PREFECTURES, OrderStatus
from common.errors import ServiceError
from common.submit_token import run_with_token
from common.web import (
    common_error_response,
    field_errors,
    pagination_context,
    render_page,
    require_admin,
    require_buyer,
    run,
)
from orders import services

ADMIN_QUERY_SESSION_KEY = "mc_admin_order_query"
CART_PATH = "/cart/"


# trace: ADDR-012
def _common_or_raise(request: HttpRequest, exc: ServiceError, next_url: str | None) -> HttpResponse:
    response = common_error_response(request, exc, next_url)
    if response is not None:
        return response
    raise exc


# ---------------------------------------------------------------------------
# SCR-006 注文手続き・SCR-007 注文完了
# ---------------------------------------------------------------------------


# trace: ADDR-012, ADDR-004, ADDR-001
@require_http_methods(["GET", "POST"])
def checkout_view(request: HttpRequest) -> HttpResponse:
    """SCR-006 注文手続き（配送先入力・確認）。表示は FR-020、確定は FR-030。"""
    try:
        user = require_buyer(request, "E-030" if request.method == "POST" else "E-020")
    except ServiceError as exc:
        return _common_or_raise(request, exc, "/checkout/")
    values = {key: request.POST.get(key, "") for key in services.ADDRESS_FIELDS}
    if request.method == "GET":
        values["recipient_name"] = user.name
        return _render_checkout(request, values)

    def body(_ctx: Any) -> dict[str, Any]:
        return run(request, "FR-030 order-place", lambda: services.place_order(user, values))

    try:
        order = run_with_token(
            "order_place",
            request.POST.get("submit_token"),
            body,
            lambda res: {"status": "success", "redirect": f"/orders/{res['order_id']}/complete/"},
        )
    except ServiceError as exc:
        response = common_error_response(request, exc, "/checkout/")
        if response is not None:
            return response
        if exc.code == "E-030-04":
            messages.error(request, "カートに商品がありません。")
            return HttpResponseRedirect(CART_PATH)
        extra = {"errors": field_errors(exc), "error_message": exc.message if exc.error_type != "input_error" else None}
        return _render_checkout(request, values, extra, status=exc.http_status)
    return HttpResponseRedirect(f"/orders/{order['order_id']}/complete/")


# trace: ADDR-012, ADDR-001
def _render_checkout(
    request: HttpRequest, values: dict[str, Any], extra: dict[str, Any] | None = None, status: int = 200
) -> HttpResponse:
    try:
        cart = run(request, "FR-020 cart", lambda: cart_services.get_cart(require_buyer(request, "E-020")))
    except ServiceError as exc:
        return _common_or_raise(request, exc, "/checkout/")
    if not cart["items"]:
        messages.error(request, "カートに商品がありません。")
        return HttpResponseRedirect(CART_PATH)
    context: dict[str, Any] = {
        "page_title": "注文手続き（配送先入力・確認）",
        "cart": cart,
        "values": values,
        "errors": {},
        "prefectures": PREFECTURES,
    }
    if extra:
        context.update(extra)
    return render_page(request, "orders/checkout.html", context, status=status)


# trace: ADDR-012, ADDR-001
def _buyer_order(request: HttpRequest, order_id: str, next_url: str) -> Any:
    user = require_buyer(request, "E-033")
    return run(request, "FR-033 order", lambda: services.get_my_order(user, order_id))


# trace: ADDR-012, ADDR-001
@require_GET
def complete_view(request: HttpRequest, order_id: str) -> HttpResponse:
    """SCR-007 注文完了（FR-033。再表示で注文確定は再実行されない）。"""
    path = f"/orders/{order_id}/complete/"
    try:
        order = _buyer_order(request, order_id, path)
    except ServiceError as exc:
        return _common_or_raise(request, exc, path)
    return render_page(request, "orders/complete.html", {"page_title": "注文完了", "order": order})


# ---------------------------------------------------------------------------
# SCR-008 支払（模擬決済）
# ---------------------------------------------------------------------------


# trace: ADDR-012, ADDR-004, ADDR-008
@require_http_methods(["GET", "POST"])
def payment_view(request: HttpRequest, order_id: str) -> HttpResponse:
    """SCR-008 支払（FR-031）。表示は注文受付の注文のみ。"""
    path = f"/orders/{order_id}/payment/"
    detail_path = f"/orders/{order_id}/"
    if request.method == "GET":
        try:
            order = _buyer_order(request, order_id, path)
        except ServiceError as exc:
            return _common_or_raise(request, exc, path)
        if order["status"] != OrderStatus.ACCEPTED:
            messages.error(request, f"この注文は支払できません（現在の状態：{order['status_label']}）。")
            return HttpResponseRedirect(detail_path)
        return render_page(
            request,
            "orders/payment.html",
            {"page_title": "支払（模擬決済）", "order": order, "values": {}, "errors": {}},
        )
    instruction = request.POST.get("mock_instruction")
    try:
        user = require_buyer(request, "E-031")
        run_with_token(
            "order_pay",
            request.POST.get("submit_token"),
            lambda ctx: run(request, "FR-031 order-pay", lambda: services.pay_order(user, order_id, instruction, ctx)),
            lambda _res: {"status": "success", "redirect": detail_path},
        )
    except ServiceError as exc:
        response = common_error_response(request, exc, path)
        if response is not None:
            return response
        if exc.code == "E-031-05":
            messages.error(request, exc.message)
            return HttpResponseRedirect(detail_path)
        try:
            order = _buyer_order(request, order_id, path)
        except ServiceError as inner:
            return _common_or_raise(request, inner, path)
        context = {
            "page_title": "支払（模擬決済）",
            "order": order,
            "values": {"mock_instruction": instruction or ""},
            "errors": field_errors(exc),
            "error_message": exc.message if exc.error_type != "input_error" else None,
        }
        return render_page(request, "orders/payment.html", context, status=exc.http_status)
    messages.success(request, "支払が完了しました。")
    return HttpResponseRedirect(detail_path)


# ---------------------------------------------------------------------------
# SCR-009 注文履歴一覧・SCR-010 注文詳細
# ---------------------------------------------------------------------------


# trace: ADDR-012, ADDR-001
@require_GET
def history_view(request: HttpRequest) -> HttpResponse:
    """SCR-009 注文履歴一覧（FR-032）。"""
    context: dict[str, Any] = {"page_title": "注文履歴一覧", "errors": {}}
    try:
        user = require_buyer(request, "E-032")
        result = run(request, "FR-032 orders", lambda: services.list_my_orders(user, request.GET.get("page")))
    except ServiceError as exc:
        response = common_error_response(request, exc, request.get_full_path())
        if response is not None:
            return response
        context.update({"result": None, "errors": field_errors(exc), "error_message": exc.message})
        return render_page(request, "orders/history.html", context, status=exc.http_status)
    context.update({"result": result, **pagination_context(request, result)})
    return render_page(request, "orders/history.html", context)


# trace: ADDR-012, ADDR-001
@require_GET
def detail_view(request: HttpRequest, order_id: str) -> HttpResponse:
    """SCR-010 注文詳細（FR-033）。決済記録は表示しない。"""
    path = f"/orders/{order_id}/"
    try:
        order = _buyer_order(request, order_id, path)
    except ServiceError as exc:
        return _common_or_raise(request, exc, path)
    return render_page(request, "orders/detail.html", {"page_title": "注文詳細", "order": order})


# trace: ADDR-012, ADDR-004
@require_POST
def cancel_view(request: HttpRequest, order_id: str) -> HttpResponse:
    """SCR-010 の「キャンセルする」（FR-034。確認に承諾した場合のみ送信される）。"""
    path = f"/orders/{order_id}/"
    try:
        user = require_buyer(request, "E-034")
        order = run_with_token(
            "order_cancel",
            request.POST.get("submit_token"),
            lambda _ctx: run(request, "FR-034 order-cancel", lambda: services.cancel_my_order(user, order_id)),
            lambda _res: {"status": "success", "redirect": path},
        )
    except ServiceError as exc:
        response = common_error_response(request, exc, path)
        if response is not None:
            return response
        messages.error(request, exc.message)
        return HttpResponseRedirect(path)
    text = "注文をキャンセルしました。"
    if order.get("paid_at"):
        text += "返金は当社が5営業日以内に行います。"
    messages.success(request, text)
    return HttpResponseRedirect(path)


# ---------------------------------------------------------------------------
# SCR-102 注文一覧（管理）・SCR-103 注文詳細（管理）
# ---------------------------------------------------------------------------


# trace: ADDR-012, ADDR-001
@require_GET
def admin_list_view(request: HttpRequest) -> HttpResponse:
    """SCR-102 注文一覧（管理）（FR-041）。検索条件・ページは SCR-103 からの戻りで再利用する。"""
    query = request.GET
    context: dict[str, Any] = {
        "page_title": "注文一覧（管理）",
        "values": {
            "order_number": query.get("order_number", ""),
            "status": query.getlist("status"),
            "order_date_from": query.get("order_date_from", ""),
            "order_date_to": query.get("order_date_to", ""),
            "buyer_email": query.get("buyer_email", ""),
        },
        "status_choices": OrderStatus.choices,
        "errors": {},
    }
    try:
        require_admin(request, "E-041")
        result = run(
            request,
            "FR-041 admin-orders",
            lambda: services.admin_list_orders(
                query.get("order_number"),
                query.getlist("status"),
                query.get("order_date_from"),
                query.get("order_date_to"),
                query.get("buyer_email"),
                query.get("page"),
            ),
        )
    except ServiceError as exc:
        response = common_error_response(request, exc, request.get_full_path())
        if response is not None:
            return response
        context.update({"result": None, "errors": field_errors(exc), "error_message": exc.message})
        return render_page(request, "orders/admin_list.html", context, status=exc.http_status)
    request.session[ADMIN_QUERY_SESSION_KEY] = query.urlencode()
    context.update({"result": result, **pagination_context(request, result)})
    return render_page(request, "orders/admin_list.html", context)


# trace: ADDR-012
def _admin_back_url(request: HttpRequest) -> str:
    saved = request.session.get(ADMIN_QUERY_SESSION_KEY)
    return f"/manage/orders/?{saved}" if isinstance(saved, str) and saved else "/manage/orders/"


# trace: ADDR-012, ADDR-001
def _render_admin_detail(
    request: HttpRequest, order_id: str, extra: dict[str, Any] | None = None, status: int = 200
) -> HttpResponse:
    path = f"/manage/orders/{order_id}/"
    try:
        require_admin(request, "E-042")
        order = run(request, "FR-042 admin-order", lambda: services.admin_get_order(order_id))
    except ServiceError as exc:
        return _common_or_raise(request, exc, path)
    context: dict[str, Any] = {
        "page_title": "注文詳細（管理）",
        "order": order,
        "back_url": _admin_back_url(request),
        "values": {},
        "errors": {},
    }
    if extra:
        context.update(extra)
    return render_page(request, "orders/admin_detail.html", context, status=status)


# trace: ADDR-012
@require_GET
def admin_detail_view(request: HttpRequest, order_id: str) -> HttpResponse:
    """SCR-103 注文詳細（管理）（FR-042）。"""
    return _render_admin_detail(request, order_id)


# trace: ADDR-012, ADDR-004
def _admin_action(
    request: HttpRequest, order_id: str, operation: str, label: str, code_prefix: str, action: Any, success: str
) -> HttpResponse:
    path = f"/manage/orders/{order_id}/"
    try:
        admin = require_admin(request, code_prefix)
        run_with_token(
            operation,
            request.POST.get("submit_token"),
            lambda _ctx: run(request, label, lambda: action(admin)),
            lambda _res: {"status": "success", "redirect": path},
        )
    except ServiceError as exc:
        response = common_error_response(request, exc, path)
        if response is not None:
            return response
        if exc.error_type == "input_error":
            return _render_admin_detail(
                request,
                order_id,
                {"errors": field_errors(exc), "values": {"tracking_number": request.POST.get("tracking_number", "")}},
                status=exc.http_status,
            )
        messages.error(request, exc.message)
        return HttpResponseRedirect(path)
    messages.success(request, success)
    return HttpResponseRedirect(path)


# trace: ADDR-012, ADDR-004
@require_POST
def admin_ship_view(request: HttpRequest, order_id: str) -> HttpResponse:
    """SCR-103 の「出荷登録」（FR-043）。"""
    return _admin_action(
        request,
        order_id,
        "order_ship",
        "FR-043 admin-ship",
        "E-043",
        lambda admin: services.ship_order(admin, order_id, request.POST.get("tracking_number")),
        "出荷登録しました。",
    )


# trace: ADDR-012, ADDR-004
@require_POST
def admin_deliver_view(request: HttpRequest, order_id: str) -> HttpResponse:
    """SCR-103 の「配達完了登録」（FR-044）。"""
    return _admin_action(
        request,
        order_id,
        "order_deliver",
        "FR-044 admin-deliver",
        "E-044",
        lambda admin: services.deliver_order(admin, order_id),
        "配達完了を登録しました。",
    )


# trace: ADDR-012, ADDR-004
@require_POST
def admin_cancel_view(request: HttpRequest, order_id: str) -> HttpResponse:
    """SCR-103 の「キャンセル」（FR-045）。"""
    return _admin_action(
        request,
        order_id,
        "order_admin_cancel",
        "FR-045 admin-cancel",
        "E-045",
        lambda admin: services.admin_cancel_order(admin, order_id),
        "注文をキャンセルしました。在庫を戻しました。",
    )
