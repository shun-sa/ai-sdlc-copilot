# trace: ADDR-002, ADDR-004, ADDR-012
"""会員・認証の画面（SCR-003 会員登録、SCR-004 ログイン、ログアウト）。"""

from typing import Any

from django.contrib import messages
from django.contrib.auth import login as django_login
from django.contrib.auth import logout as django_logout
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.views.decorators.http import require_http_methods, require_POST

from accounts import services
from accounts.models import User
from common import clock
from common.codes import UserType
from common.errors import ServiceError
from common.middleware import SESSION_LAST_SEEN_KEY
from common.submit_token import run_with_token
from common.web import common_error_response, current_user, field_errors, render_page, run, safe_next

HOME_BUYER = "/"
HOME_ADMIN = "/manage/orders/"


# trace: ADDR-004, ADDR-012
@require_http_methods(["GET", "POST"])
def register_view(request: HttpRequest) -> HttpResponse:
    """SCR-003 会員登録（FR-001）。成功時は SCR-004 へ遷移する（自動ログインしない）。"""
    context: dict[str, Any] = {"page_title": "会員登録", "values": {}, "errors": {}}
    if request.method == "GET":
        return render_page(request, "accounts/register.html", context)
    values = {"email": request.POST.get("email", ""), "name": request.POST.get("name", "")}
    try:
        run_with_token(
            "register",
            request.POST.get("submit_token"),
            lambda _ctx: run(
                request,
                "FR-001 register",
                lambda: services.register(
                    request.POST.get("email"),
                    request.POST.get("password"),
                    request.POST.get("password_confirmation"),
                    request.POST.get("name"),
                ),
            ),
            lambda _result: {"status": "success", "redirect": "/login/"},
        )
    except ServiceError as exc:
        response = common_error_response(request, exc, "/register/")
        if response is not None:
            return response
        context.update({"values": values, "errors": field_errors(exc), "error_message": exc.message})
        return render_page(request, "accounts/register.html", context, status=exc.http_status)
    messages.success(request, "会員登録が完了しました。ログインしてください。")
    return HttpResponseRedirect("/login/")


# trace: ADDR-002, ADDR-012
def _home_for(user_type: str) -> str:
    return HOME_ADMIN if user_type == UserType.ADMIN else HOME_BUYER


# trace: ADDR-002, ADDR-004, ADDR-012
@require_http_methods(["GET", "POST"])
def login_view(request: HttpRequest) -> HttpResponse:
    """SCR-004 ログイン（FR-002）。戻り先がある場合はその画面へ、ない場合は利用者区分の画面へ遷移する。"""
    next_url = safe_next(request.POST.get("next") if request.method == "POST" else request.GET.get("next"))
    context: dict[str, Any] = {
        "page_title": "ログイン",
        "next": next_url or "",
        "login_required": request.GET.get("required") == "1",
        "values": {},
        "errors": {},
    }
    if request.method == "GET":
        return render_page(request, "accounts/login.html", context)

    def start_session(user: User) -> None:
        django_login(request, user, backend="accounts.backends.SessionUserBackend")
        request.session[SESSION_LAST_SEEN_KEY] = int(clock.now_seconds().timestamp())
        request.session.save()

    def body(ctx: Any) -> dict[str, Any]:
        user = run(
            request,
            "FR-002 login",
            lambda: services.login_web(request.POST.get("email"), request.POST.get("password"), ctx, start_session),
        )
        if user is None:
            return {"redirect": (ctx.prior or {}).get("redirect") or HOME_BUYER}
        return {"redirect": next_url or _home_for(user.user_type)}

    try:
        result = run_with_token(
            "login",
            request.POST.get("submit_token"),
            body,
            lambda res: {"status": "success", "redirect": res["redirect"]},
        )
    except ServiceError as exc:
        response = common_error_response(request, exc, None)
        if response is not None:
            return response
        context.update(
            {
                "values": {"email": request.POST.get("email", "")},
                "errors": field_errors(exc),
                "error_message": exc.message,
            }
        )
        return render_page(request, "accounts/login.html", context, status=exc.http_status)
    return HttpResponseRedirect(safe_next(result["redirect"]) or HOME_BUYER)


# trace: ADDR-002, ADDR-004, ADDR-012
@require_POST
def logout_view(request: HttpRequest) -> HttpResponse:
    """ログアウト（FR-003）。SCR-001 へ遷移し「ログアウトしました。」を表示する（UI-20）。"""
    user = current_user(request)
    try:
        run_with_token(
            "logout",
            request.POST.get("submit_token"),
            lambda ctx: run(
                request,
                "FR-003 logout",
                lambda: services.logout_web(user, lambda: django_logout(request), ctx),
            ),
            lambda _result: {"status": "success", "redirect": HOME_BUYER},
        )
    except ServiceError as exc:
        response = common_error_response(request, exc, None)
        if response is not None:
            return response
        raise
    messages.success(request, "ログアウトしました。")
    return HttpResponseRedirect(HOME_BUYER)
