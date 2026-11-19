# trace: ADDR-012, ADDR-002, ADDR-004, ADDR-013
"""画面（Django テンプレート）側の共通変換部品（ADDR-012 4.3 の2：画面は業務処理層の薄い呼出し側）。"""

from collections.abc import Callable
from typing import Any
from urllib.parse import urlencode

from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.utils.http import url_has_allowed_host_and_scheme

from common.codes import UserType
from common.errors import ServiceError, authentication_required, permission_denied
from common.logging import log_error, log_operation, operation_log
from common.normalize import has_unstorable_chars
from common.submit_token import issue_token

LOGIN_PATH = "/login/"
# SCR-901（エラー）の表示中であることを示す要求の属性（共通表示の合計点数の扱い：ADDR-001 ASM-002）
ERROR_PAGE_ATTR = "mc_error_page"

ERROR_PAGES: dict[str, tuple[int, str, str]] = {
    "not_found": (
        404,
        "お探しのページ・データが見つかりません",
        "指定されたページまたはデータは存在しないか、表示できません。一覧から選び直してください。",
    ),
    "permission_denied": (
        403,
        "この画面・操作を利用する権限がありません",
        "権限のある利用者でログインしてください。",
    ),
    "system_error": (
        500,
        "システムエラーが発生しました",
        "時間をおいて再度操作してください。解消しない場合は当社までお問い合わせください。",
    ),
}


# trace: ADDR-012
def error_page(request: HttpRequest, kind: str, status: int | None = None) -> HttpResponse:
    """SCR-901（エラー）を表示する。対象なしは存在しない・他の購入者の注文を区別しない。"""
    default_status, heading, message = ERROR_PAGES[kind]
    setattr(request, ERROR_PAGE_ATTR, True)
    return render(
        request,
        "common/error.html",
        {"page_title": "エラー", "heading": heading, "message": message, "kind": kind},
        status=status or default_status,
    )


# trace: ADDR-002
def safe_next(raw: Any) -> str | None:
    """戻り先は同一サイト内の相対パスに限る（ADDR-002 6章 拒否時の振る舞い）。"""
    if not isinstance(raw, str) or not raw.startswith("/") or raw.startswith("//") or "\\" in raw:
        return None
    if has_unstorable_chars(raw):
        # データベースが受理しない文字（NUL 等）を含む戻り先は指定なしとして扱う（送信トークンの結果に記録しない）
        return None
    if not url_has_allowed_host_and_scheme(raw, allowed_hosts=None, require_https=False):
        return None
    return raw


# trace: ADDR-002
def redirect_to_login(next_url: str | None) -> HttpResponseRedirect:
    """SCR-004 へ遷移し、ログイン後に元の画面へ戻す（CMN-02、UI-16・UI-17）。"""
    params = {"required": "1"}
    target = safe_next(next_url)
    if target:
        params["next"] = target
    return HttpResponseRedirect(f"{LOGIN_PATH}?{urlencode(params)}")


# trace: ADDR-002, ADDR-012
def current_user(request: HttpRequest) -> Any:
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return None
    return user


# trace: ADDR-002, ADDR-012
def require_web_user(request: HttpRequest, code_prefix: str, role: str | None) -> Any:
    """認証（①）→ 利用者区分（②）の順に判定する（CMN-14）。"""
    user = current_user(request)
    if user is None:
        raise authentication_required(f"{code_prefix}-01")
    if role is not None and user.user_type != role:
        raise permission_denied(f"{code_prefix}-02")
    return user


# trace: ADDR-002, ADDR-012
def require_buyer(request: HttpRequest, code_prefix: str) -> Any:
    return require_web_user(request, code_prefix, UserType.BUYER)


# trace: ADDR-002, ADDR-012
def require_admin(request: HttpRequest, code_prefix: str) -> Any:
    return require_web_user(request, code_prefix, UserType.ADMIN)


# trace: ADDR-012, ADDR-013
def common_error_response(request: HttpRequest, exc: ServiceError, next_url: str | None) -> HttpResponse | None:
    """画面に共通の通知（認証エラー・権限エラー・対象なし・システムエラー）。

    入力エラー・業務エラー・認証失敗・外部連携エラーは各画面で表示するため None を返す（MSG-03）。
    業務処理の実行前（認証・利用者区分の判定）に通知するエラーもここで LOG-01 に出力する。
    """
    if not getattr(exc, "mc_logged", False):
        user = current_user(request)
        log_operation(request.path, "end", exc.error_type, user.pk if user else None)
    if exc.error_type == "authentication_required":
        return redirect_to_login(next_url)
    if exc.error_type == "permission_denied":
        return error_page(request, "permission_denied")
    if exc.error_type == "not_found":
        return error_page(request, "not_found")
    if exc.error_type == "system_error":
        user = current_user(request)
        log_error("system_error", exc, user.pk if user else None)
        return error_page(request, "system_error")
    return None


# trace: ADDR-013
def run(request: HttpRequest, operation: str, func: Callable[[], Any]) -> Any:
    """業務処理を1回実行し LOG-01 を出力する。"""
    user = current_user(request)
    with operation_log(operation, user.pk if user else None):
        return func()


# trace: ADDR-012, ADDR-004
def render_page(request: HttpRequest, template: str, context: dict[str, Any], status: int = 200) -> HttpResponse:
    """画面を表示する。更新フォームを持つ画面には表示ごとに新しい送信トークンを埋め込む（ADDR-004 DD-010）。"""
    context = dict(context)
    context.setdefault("submit_token", issue_token())
    return render(request, template, context, status=status)


# trace: ADDR-012
def field_errors(exc: ServiceError) -> dict[str, list[str]]:
    """入力エラーを項目ごとの理由に変換する（UI-29：対象項目を識別できるように表示）。"""
    result: dict[str, list[str]] = {}
    for item in exc.fields:
        result.setdefault(item.field.replace(".", "__"), []).append(item.message)
    return result


# trace: ADDR-012
def pagination_context(request: HttpRequest, page_info: dict[str, Any] | None) -> dict[str, Any]:
    """ページ移動（UI-13：前後2ページ以内・先頭・最終。検索条件を引き継ぐ）の表示用の値。"""
    if not page_info:
        return {"page_info": None, "page_numbers": [], "page_query": ""}
    params = request.GET.copy()
    params.pop("page", None)
    query = params.urlencode()
    page = page_info["page"]
    total = page_info["total_pages"]
    numbers = [n for n in range(page - 2, page + 3) if 1 <= n <= total]
    offset = (page - 1) * page_info["page_size"]
    item_count = len(page_info.get("items") or [])
    return {
        "page_info": page_info,
        "page_numbers": numbers,
        "page_query": f"{query}&" if query else "",
        "first_index": offset + 1,
        "last_index": offset + item_count,
    }
