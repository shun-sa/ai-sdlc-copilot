# trace: ADDR-013, ADDR-014, ADDR-002, ADDR-012
"""要求ごとの共通処理（要求の識別子・アクセスログ・HTTPS の強制・無操作タイムアウト・例外の変換）。"""

import codecs
import time
from collections.abc import Callable

from django.conf import settings
from django.contrib.auth import logout as django_logout
from django.http import HttpRequest, HttpResponse

from common import clock
from common.logging import (
    log_access,
    log_error,
    monotonic_ms,
    new_request_id,
    request_scope,
)

API_PREFIX = "/api/"
IDLE_TIMEOUT_SECONDS = 30 * 60
SESSION_LAST_SEEN_KEY = "mc_last_seen"
SESSION_EXPIRED_ATTR = "mc_session_expired"
# WSGI の入口で文字列でない文字コード指定を取り除いた要求の印
# （config.wsgi が付け、RequestCharsetMiddleware が 400 とする）
INVALID_CHARSET_ENVIRON_KEY = "minicommerce.invalid_charset"


# trace: ADDR-012
def is_api_request(request: HttpRequest) -> bool:
    return request.path.startswith(API_PREFIX)


# trace: ADDR-013
class RequestIdMiddleware:
    """要求ごとにサーバーで UUID を生成し、全ログに付けて X-Request-ID で返す（ADDR-013 DD-002）。"""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request_id = new_request_id()
        with request_scope(request_id):
            request.request_id = request_id
            response = self.get_response(request)
            response["X-Request-ID"] = request_id
            return response


# trace: ADDR-013
class AccessLogMiddleware:
    """LOG-03 アクセスログ（要求先は検索条件を除いたパスだけ：ADDR-013 DD-005）。"""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        start = time.monotonic()
        response = self.get_response(request)
        log_access(request.method or "", request.path, response.status_code, _user_id(request), monotonic_ms(start))
        return response


# trace: ADDR-013, ADDR-002
def _user_id(request: HttpRequest) -> int | None:
    if is_api_request(request):
        return getattr(request, "api_user_id", None)
    user = request.__dict__.get("user")
    if user is None:
        return None
    try:
        return user.pk if user.is_authenticated else None
    except Exception:  # noqa: BLE001 - ログ出力のための参照失敗で応答を失敗させない
        return None


# trace: ADDR-014
class HttpsOnlyMiddleware:
    """本番では HTTPS でない要求を業務処理の前に拒否する（転送しない：ADDR-014 DD-003）。"""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if settings.IS_PRODUCTION and not request.is_secure():
            return HttpResponse("HTTPS で接続してください。", status=403, content_type="text/plain; charset=utf-8")
        return self.get_response(request)


# trace: ADDR-012
class RequestCharsetMiddleware:
    """要求の Content-Type の文字コード指定（charset）が文字列の符号化方式でない要求を入力エラー（400）とする。

    rot13・zlib・base64 等の文字列を返さない・圧縮の符号化方式が指定されると、クエリ・フォーム・本文の解釈で
    例外となるため、CSRF 検証・業務処理より前に拒否する（ADDR-001 4.3 の7、NFR-SC-04。LOG-02 に記録しない）。
    クエリ文字列を伴う場合は Django が要求の生成時に失敗するため、WSGI の入口（config.wsgi）で指定を取り除き印を付ける。
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if request.META.get(INVALID_CHARSET_ENVIRON_KEY) or is_unusable_charset(request.encoding):
            from common import views

            return views.bad_request(request)
        return self.get_response(request)


# trace: ADDR-012
def is_unusable_charset(encoding: str | None) -> bool:
    """文字コード指定が文字列の符号化方式でない（rot13・zlib・base64 等）か判定する。

    未指定・未知の名前は Django が無視して既定の UTF-8 で解釈するため対象外とする。
    """
    if not encoding:
        return False
    try:
        info = codecs.lookup(encoding)
    except LookupError:
        return False
    return not getattr(info, "_is_text_encoding", True)


# trace: ADDR-002
class IdleTimeoutMiddleware:
    """画面のログイン状態の無操作30分の切断（ADDR-002 DD-004）。

    判定時刻（秒）− 最後の画面要求の受付時刻 ≧ 30分 なら当該セッションを破棄し、
    以後の処理は来訪者として行う（ログインが必要な画面は SCR-004 へ遷移する）。
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if not is_api_request(request):
            self._check(request)
        return self.get_response(request)

    def _check(self, request: HttpRequest) -> None:
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return
        now = int(clock.now_seconds().timestamp())
        last_seen = request.session.get(SESSION_LAST_SEEN_KEY)
        if isinstance(last_seen, int) and now - last_seen >= IDLE_TIMEOUT_SECONDS:
            django_logout(request)
            setattr(request, SESSION_EXPIRED_ATTR, True)
            return
        request.session[SESSION_LAST_SEEN_KEY] = now


# trace: ADDR-013, ADDR-012
class WebExceptionMiddleware:
    """画面・API の処理中の想定外の例外を LOG-02 に記録し、内部情報を含まない応答に変える。"""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        return self.get_response(request)

    def process_exception(self, request: HttpRequest, exception: Exception) -> HttpResponse | None:
        from django.core.exceptions import PermissionDenied
        from django.http import Http404

        from common import views
        from common.errors import is_request_parse_error

        if isinstance(exception, Http404 | PermissionDenied):
            return None
        if is_request_parse_error(exception):
            # クエリ・フォームの項目数・大きさの上限超過、不正なマルチパート等は入力エラー（400。LOG-02 に記録しない）
            return views.bad_request(request, exception)
        log_error("system_error", exception, _user_id(request))
        return views.system_error_response(request)
