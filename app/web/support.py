# trace: ADDR-006
"""ログインセッションの取り扱いとエラー表示の共通処理（画面側）。"""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any

from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from accounts.models import ROLE_ADMIN, ROLE_BUYER, User
from common.exceptions import (
    AuthenticationRequired,
    InternalError,
    MiniCommerceError,
    NotFoundError,
    PermissionDeniedError,
)

SESSION_USER_ID = "login_user_id"
SESSION_NEXT_PATH = "next_path"
SESSION_FLASH = "flash_message"

ERROR_NOT_FOUND = "not_found"
ERROR_PERMISSION = "permission_denied"
ERROR_INTERNAL = "internal"

ERROR_TEXTS = {
    ERROR_NOT_FOUND: (
        "お探しのページ・データが見つかりません",
        "指定されたページまたはデータは存在しないか、表示できません。一覧から選び直してください。",
    ),
    ERROR_PERMISSION: (
        "この画面・操作を利用する権限がありません",
        "権限のある利用者でログインしてください。",
    ),
    ERROR_INTERNAL: (
        "システムエラーが発生しました",
        "時間をおいて再度操作してください。解消しない場合は当社までお問い合わせください。",
    ),
}


def current_user(request: HttpRequest) -> User | None:
    """ログインセッションから利用者を取得する。"""
    user = getattr(request, "login_user", None)
    if user is not None:
        return user
    user_id = request.session.get(SESSION_USER_ID)
    if not user_id:
        return None
    user = User.objects.filter(pk=user_id).first()
    request.login_user = user
    return user


def start_session(request: HttpRequest, user: User) -> None:
    """ログイン成功時にセッション識別子を再発行して利用者を保持する。"""
    request.session.cycle_key()
    request.session[SESSION_USER_ID] = user.pk
    request.login_user = user


def end_session(request: HttpRequest) -> None:
    """ログアウト時にセッションを破棄する。"""
    request.session.flush()
    request.login_user = None


def set_flash(request: HttpRequest, message: str) -> None:
    """次の画面のメッセージ領域へ表示する文言を保持する。"""
    request.session[SESSION_FLASH] = message


def pop_flash(request: HttpRequest) -> str | None:
    """メッセージ領域の文言を取り出す（1回だけ表示する）。"""
    return request.session.pop(SESSION_FLASH, None)


def query_prefix(request: HttpRequest) -> str:
    """ページ移動のリンクへ引き継ぐ検索条件のクエリ文字列を組み立てる（UI-13）。"""
    params = request.GET.copy()
    params.pop("page", None)
    encoded = params.urlencode()
    return f"{encoded}&" if encoded else ""


def remember_next_path(request: HttpRequest) -> None:
    """ログイン後の復帰先（自サイト内の相対パス）を保持する。"""
    if request.method != "GET":
        # 更新要求そのものは復帰先にしない（再ログイン後に更新を実行しないため）。
        return
    path = request.get_full_path()
    if path.startswith("/") and not path.startswith("//"):
        request.session[SESSION_NEXT_PATH] = path


def remember_path(request: HttpRequest, path: str) -> None:
    """更新操作からの復帰先（表示していた画面）を明示的に保持する。"""
    if path.startswith("/") and not path.startswith("//"):
        request.session[SESSION_NEXT_PATH] = path


def pop_next_path(request: HttpRequest) -> str | None:
    """保持した復帰先を取り出す（外部URLは受け付けない）。"""
    path = request.session.pop(SESSION_NEXT_PATH, None)
    if path and path.startswith("/") and not path.startswith("//"):
        return path
    return None


def render_error(request: HttpRequest, kind: str, status: int) -> HttpResponse:
    """SCR-901（エラー）を表示する（内部情報は表示しない）。"""
    heading, message = ERROR_TEXTS[kind]
    return render(request, "error.html", {"heading": heading, "error_body": message}, status=status)


def require_login(request: HttpRequest) -> User:
    """ログイン済みであることを要求する（未ログインは認証エラー）。"""
    user = current_user(request)
    if user is None:
        raise AuthenticationRequired()
    return user


def require_buyer(request: HttpRequest) -> User:
    """購入者であることを要求する。"""
    user = require_login(request)
    if user.role != ROLE_BUYER:
        raise PermissionDeniedError()
    return user


def require_admin(request: HttpRequest) -> User:
    """管理者であることを要求する。"""
    user = require_login(request)
    if user.role != ROLE_ADMIN:
        raise PermissionDeniedError()
    return user


def screen(view: Callable[..., HttpResponse]) -> Callable[..., HttpResponse]:
    """認証・権限・対象なし・システムエラーを画面の振る舞いへ写像する。"""

    @wraps(view)
    def wrapper(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        try:
            return view(request, *args, **kwargs)
        except AuthenticationRequired as error:
            remember_next_path(request)
            set_flash(request, error.message)
            return redirect("web-login")
        except PermissionDeniedError:
            return render_error(request, ERROR_PERMISSION, 403)
        except NotFoundError:
            return render_error(request, ERROR_NOT_FOUND, 404)
        except InternalError:
            return render_error(request, ERROR_INTERNAL, 500)
        except MiniCommerceError:
            raise

    return wrapper
