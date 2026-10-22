# trace: ADDR-002, ADDR-007
"""画面共通の支援処理（エラー変換・遷移先の検証・共通表示情報）。

権限判定は services 層（accounts）の単一実装へ委譲する（ADDR-004 DD-002、DD-003、INV-001）。
"""
from collections.abc import Callable
from functools import wraps
from typing import Any
from urllib.parse import quote, urlparse

from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from shop.common.errors import (
    AppError,
    AuthenticationRequiredError,
    NotFoundError,
    PermissionDeniedError,
)
from shop.services import accounts
from shop.web import messages, session

ERROR_TEMPLATE = "web/error.html"
LOGIN_PATH = "/login"


# trace: ADDR-002
def safe_internal_path(request: HttpRequest, candidate: Any, fallback: str = "/") -> str:
    """利用者が指定した遷移先を自サイト内の相対パスに限定する（NFR-SC-04、VUL-01）。"""
    if not isinstance(candidate, str) or candidate == "":
        return fallback
    if not candidate.startswith("/") or candidate.startswith("//"):
        return fallback
    if not url_has_allowed_host_and_scheme(
        url=candidate, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return fallback
    return candidate


# trace: ADDR-002
def login_return_path(request: HttpRequest) -> str:
    """ログイン後に戻る画面の URL を求める（更新操作では表示できる画面へ戻す）。"""
    if request.method == "GET":
        return request.get_full_path()
    candidate = safe_internal_path(request, request.POST.get("return_to", ""), "")
    if candidate:
        return candidate
    referer = request.headers.get("Referer", "")
    if referer:
        parsed = urlparse(referer)
        if not parsed.netloc or parsed.netloc == request.get_host():
            return safe_internal_path(request, parsed.path or "/")
    return "/"


# trace: ADDR-007
def render_error(request: HttpRequest, error: AppError) -> HttpResponse:
    """SCR-901（エラー）を区分ごとの見出し・メッセージで表示する。内部情報は表示しない。"""
    title, message = messages.error_screen_text(error)
    return render(
        request,
        ERROR_TEMPLATE,
        {"page_title": title, "error_message": message},
        status=error.http_status,
    )


# trace: ADDR-002, ADDR-007
def handle_app_errors(view: Callable[..., HttpResponse]) -> Callable[..., HttpResponse]:
    """認証・権限・対象なし・システムエラーを画面の振る舞いへ変換する。"""

    @wraps(view)
    def wrapper(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        try:
            return view(request, *args, **kwargs)
        except AuthenticationRequiredError as error:
            session.set_flash(request, error.message)
            return redirect(f"{LOGIN_PATH}?next={quote(login_return_path(request))}")
        except PermissionDeniedError as error:
            return render_error(request, error)
        except NotFoundError as error:
            return render_error(request, error)
        except AppError as error:
            if error.code == "INTERNAL_ERROR":
                return render_error(request, error)
            raise

    return wrapper


# trace: ADDR-002
def require_buyer(request: HttpRequest) -> Any:
    """購入者のみが利用できる画面の権限判定を行う（判定は services の単一実装）。"""
    return accounts.require_buyer(session.current_user(request))


# trace: ADDR-002
def require_admin(request: HttpRequest) -> Any:
    """管理者のみが利用できる画面の権限判定を行う（判定は services の単一実装）。"""
    return accounts.require_admin(session.current_user(request))


# trace: ADDR-007
def page_range(page: int, total_pages: int) -> list[int]:
    """表示するページ番号（現在ページの前後2ページ・先頭・最終）を返す。"""
    if total_pages <= 1:
        return []
    numbers = {1, total_pages}
    for offset in range(-2, 3):
        candidate = page + offset
        if 1 <= candidate <= total_pages:
            numbers.add(candidate)
    return sorted(numbers)
