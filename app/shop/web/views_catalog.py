# trace: ADDR-002, ADDR-006
"""来訪者・購入者向けのカタログ画面と会員登録・ログイン画面（SCR-001〜SCR-004）。"""
from typing import Any

from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from shop.common.errors import AppError, ValidationError
from shop.services import accounts, catalog
from shop.web import messages, session
from shop.web.support import handle_app_errors, page_range, safe_internal_path

ITEM_DETAIL_TEMPLATE = "web/item_detail.html"


# trace: ADDR-006
@handle_app_errors
@require_http_methods(["GET"])
def item_list(request: HttpRequest) -> HttpResponse:
    """SCR-001 商品一覧。商品分類一覧（FR-010）と商品一覧検索（FR-011）を表示する。"""
    context = {
        "page_title": "商品一覧",
        "collections": catalog.list_collections(),
        "keyword": request.GET.get("keyword", ""),
        "sort": request.GET.get("sort", catalog.SORT_NEW),
        "selected_collection_id": request.GET.get("collection_id", ""),
        "details": [],
    }
    try:
        result = catalog.search_items(
            raw_collection_id=request.GET.get("collection_id"),
            raw_keyword=request.GET.get("keyword"),
            raw_sort=request.GET.get("sort"),
            raw_page=request.GET.get("page"),
        )
    except ValidationError as error:
        context["details"] = error.details
        context["page_data"] = {"results": [], "page": 1, "page_size": 20, "total_count": 0, "total_pages": 0}
        context["page_numbers"] = []
        return render(request, "web/item_list.html", context, status=400)

    context["page_data"] = result
    context["page_numbers"] = page_range(result["page"], result["total_pages"])
    return render(request, "web/item_list.html", context)


# trace: ADDR-006
def render_item_detail(
    request: HttpRequest,
    raw_item_id: Any,
    *,
    selected_stock_unit_id: Any = None,
    quantity: Any = None,
    error_message: str | None = None,
    details: list[dict[str, str]] | None = None,
    status: int = 200,
) -> HttpResponse:
    """SCR-002 を表示する（カート投入の失敗時は入力値を保持して再表示する）。"""
    item = catalog.get_item_detail(raw_item_id)
    units = item["stock_units"]
    in_stock_ids = [unit["stock_unit_id"] for unit in units if unit["in_stock"]]
    selected = selected_stock_unit_id if selected_stock_unit_id not in (None, "") else None
    if selected is None and in_stock_ids:
        selected = in_stock_ids[0]
    return render(
        request,
        ITEM_DETAIL_TEMPLATE,
        {
            "page_title": "商品詳細",
            "item": item,
            "any_in_stock": bool(in_stock_ids),
            "selected_stock_unit_id": str(selected) if selected is not None else "",
            "quantity": quantity if quantity not in (None, "") else 1,
            "error_message": error_message,
            "details": details or [],
        },
        status=status,
    )


# trace: ADDR-006
@handle_app_errors
@require_http_methods(["GET"])
def item_detail(request: HttpRequest, item_id: str) -> HttpResponse:
    """SCR-002 商品詳細（FR-012）。管理者にはカート投入の操作を表示しない。"""
    return render_item_detail(request, item_id)


# trace: ADDR-002
@handle_app_errors
@require_http_methods(["GET", "POST"])
def register(request: HttpRequest) -> HttpResponse:
    """SCR-003 会員登録（FR-001）。登録後は自動ログインしない。"""
    context = {"page_title": "会員登録", "details": [], "form": {}, "error_message": None}
    if request.method == "GET":
        return render(request, "web/register.html", context)

    form = {
        "email": request.POST.get("email", ""),
        "full_name": request.POST.get("full_name", ""),
    }
    context["form"] = form
    try:
        accounts.register_user(
            email=request.POST.get("email", ""),
            password=request.POST.get("password", ""),
            password_confirmation=request.POST.get("password_confirmation", ""),
            full_name=request.POST.get("full_name", ""),
        )
    except ValidationError as error:
        context["details"] = error.details
        return render(request, "web/register.html", context, status=400)
    except AppError as error:
        if error.code == "EMAIL_ALREADY_REGISTERED":
            context["error_message"] = messages.EMAIL_ALREADY_REGISTERED_MESSAGE
            return render(request, "web/register.html", context, status=409)
        raise

    session.set_flash(request, messages.REGISTERED_MESSAGE)
    return redirect("/login")


# trace: ADDR-002
@handle_app_errors
@require_http_methods(["GET", "POST"])
def login(request: HttpRequest) -> HttpResponse:
    """SCR-004 ログイン（FR-002）。成功時はログインセッションを開始する。"""
    next_path = request.GET.get("next") or request.POST.get("next") or ""
    context = {
        "page_title": "ログイン",
        "details": [],
        "form": {"email": request.POST.get("email", "")},
        "error_message": None,
        "next": next_path,
    }
    if request.method == "GET":
        return render(request, "web/login.html", context)

    try:
        user = accounts.login_for_session(request.POST.get("email", ""), request.POST.get("password", ""))
    except ValidationError as error:
        context["details"] = error.details
        return render(request, "web/login.html", context, status=400)
    except AppError as error:
        if error.code == "INVALID_CREDENTIALS":
            context["error_message"] = messages.INVALID_CREDENTIALS_MESSAGE
            return render(request, "web/login.html", context, status=401)
        raise

    session.login(request, user)
    default_path = "/admin/purchase-orders" if accounts.is_admin(user) else "/"
    return redirect(safe_internal_path(request, next_path, default_path))


# trace: ADDR-002
@handle_app_errors
@require_http_methods(["POST"])
def logout(request: HttpRequest) -> HttpResponse:
    """ログアウト（FR-003）。ログインセッションを破棄する。"""
    user = session.current_user(request)
    if user is not None:
        accounts.logout_session(user)
    session.logout(request)
    return redirect("/")
