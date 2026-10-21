# trace: ADDR-006, ADDR-011
"""会員登録（SCR-003）・ログイン（SCR-004）・ログアウト。"""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from accounts import services
from accounts.models import ROLE_ADMIN
from common.exceptions import BusinessError, InvalidCredentials, ValidationFailed
from web.support import current_user, end_session, pop_next_path, screen, set_flash, start_session
from web.views.messages import business_message, field_errors


# trace: ADDR-011
@screen
@require_http_methods(["GET", "POST"])
def register(request: HttpRequest) -> HttpResponse:
    """SCR-003 会員登録。FR-001 を実行する（自動ログインしない）。"""
    context: dict = {"form": {}}
    if request.method == "GET":
        return render(request, "buyer/register.html", context)

    form = {
        "email": request.POST.get("email", ""),
        "full_name": request.POST.get("full_name", ""),
    }
    context["form"] = form
    payload = {
        "email": request.POST.get("email"),
        "password": request.POST.get("password"),
        "password_confirmation": request.POST.get("password_confirmation"),
        "full_name": request.POST.get("full_name"),
    }
    try:
        services.register_user(payload)
    except ValidationFailed as error:
        context["field_errors"] = field_errors(error)
        return render(request, "buyer/register.html", context, status=400)
    except BusinessError as error:
        context["error_message"] = business_message(error)
        return render(request, "buyer/register.html", context, status=409)

    set_flash(request, "会員登録が完了しました。ログインしてください。")
    return redirect("web-login")


# trace: ADDR-006
@screen
@require_http_methods(["GET", "POST"])
def login(request: HttpRequest) -> HttpResponse:
    """SCR-004 ログイン。FR-002 を実行し、ログインセッションを開始する。"""
    context: dict = {"form": {}}
    if request.method == "GET":
        return render(request, "buyer/login.html", context)

    email = request.POST.get("email", "")
    context["form"] = {"email": email}
    try:
        user = services.authenticate(email, request.POST.get("password"))
    except ValidationFailed as error:
        context["field_errors"] = field_errors(error)
        return render(request, "buyer/login.html", context, status=400)
    except InvalidCredentials as error:
        context["error_message"] = error.message
        return render(request, "buyer/login.html", context, status=401)

    start_session(request, user)
    next_path = pop_next_path(request)
    if next_path:
        return redirect(next_path)
    if user.role == ROLE_ADMIN:
        return redirect("web-admin-orders")
    return redirect("web-items")


# trace: ADDR-006
@screen
@require_http_methods(["POST"])
def logout(request: HttpRequest) -> HttpResponse:
    """ログアウト。FR-003 を実行し、ログインセッションを破棄する。"""
    user = current_user(request)
    if user is not None:
        services.logout_session(user)
    end_session(request)
    set_flash(request, "ログアウトしました。")
    return redirect("web-items")
