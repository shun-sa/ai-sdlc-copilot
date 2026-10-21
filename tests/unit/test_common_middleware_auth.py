# trace: FR-002, FR-021, NFR-SC-03, NFR-SC-06, NFR-SC-12, NFR-OM-11, ADDR-002, ADDR-007
"""共通ミドルウェア（相関ID・アクセスログ）と認証・認可の単体テスト。

期待結果は NFR-SC-03（未ログインは401、権限なしは403をサーバー側で判定）、
NFR-SC-06（path にクエリ文字列を含めない）、ADDR-002（Bearer トークン認証）、
ADDR-007（相関ID X-Request-ID の採番・引継ぎ）から導出する。
"""

from __future__ import annotations

import logging

import pytest
from accounts.models import ROLE_ADMIN, ROLE_BUYER
from common.authentication import BearerTokenAuthentication
from common.exceptions import AuthenticationRequired, PermissionDeniedError
from common.logging import current_request_id
from common.middleware import REQUEST_ID_HEADER, RequestLogMiddleware
from common.permissions import IsAdmin, IsAuthenticated, IsBuyer
from django.http import HttpResponse
from django.test import RequestFactory


# trace: NFR-SC-03
class StubUser:
    """ロール判定だけを行うための利用者（DBを使わない）。"""

    def __init__(self, role: str, user_id: int = 1) -> None:
        self.role = role
        self.id = user_id


# trace: FR-002
class StubToken:
    """認証トークンの代替（解決結果の持ち回りだけを確認する）。"""


RESOLVED = (StubUser(ROLE_BUYER, 42), StubToken())


# trace: FR-002
def resolve_ok(raw_token: str):
    """有効なトークンを解決する差し替え関数。"""
    assert raw_token == "valid-token"
    return RESOLVED


# trace: FR-002
def resolve_none(raw_token: str):
    """無効・期限切れのトークンを表す差し替え関数。"""
    return None


# trace: NFR-OM-11
def test_middleware_generates_request_id_when_header_is_absent():
    """要求に相関IDがない場合は採番し、応答ヘッダーへ返す。"""
    middleware = RequestLogMiddleware(lambda request: HttpResponse("ok"))

    response = middleware(RequestFactory().get("/api/items"))

    assert response[REQUEST_ID_HEADER]
    assert len(response[REQUEST_ID_HEADER]) == 32


# trace: NFR-OM-11
def test_middleware_takes_over_request_id_from_header():
    """要求の X-Request-ID を引き継ぎ、処理中の全ログ行へ同じ値を出力する。"""
    observed = {}

    def view(request):
        observed["request_id"] = current_request_id()
        return HttpResponse("ok")

    middleware = RequestLogMiddleware(view)

    response = middleware(RequestFactory().get("/api/items", **{"HTTP_X_REQUEST_ID": " given-id "}))

    assert response[REQUEST_ID_HEADER] == "given-id"
    assert observed["request_id"] == "given-id"
    assert current_request_id() == ""


# trace: NFR-SC-06
def test_access_log_path_excludes_query_string(caplog):
    """NFR-SC-06：アクセスログの path にクエリ文字列を含めない。"""
    middleware = RequestLogMiddleware(lambda request: HttpResponse("ok"))

    with caplog.at_level(logging.INFO, logger="minicommerce.request"):
        middleware(RequestFactory().get("/api/admin/purchase-orders?buyer_email=user@example.test"))

    record = caplog.records[-1]
    assert record.path == "/api/admin/purchase-orders"
    assert "buyer_email" not in record.path
    assert record.status == 200
    assert record.method == "GET"


# trace: NFR-OM-11
def test_access_log_records_login_user_id(caplog):
    """アクセスログには利用者ID（未ログインは null）を出力する。"""
    def view(request):
        request.login_user = StubUser(ROLE_BUYER, 7)
        return HttpResponse("ok")

    middleware = RequestLogMiddleware(view)

    with caplog.at_level(logging.INFO, logger="minicommerce.request"):
        middleware(RequestFactory().get("/api/cart"))

    assert caplog.records[-1].user_id == 7


# trace: NFR-OM-11
def test_middleware_logs_and_reraises_unhandled_exception(caplog):
    """未捕捉例外はエラーログを出力したうえで再送出する（応答は上位で組み立てる）。"""

    def view(request):
        raise RuntimeError("内部エラー")

    middleware = RequestLogMiddleware(view)

    with caplog.at_level(logging.ERROR, logger="minicommerce.request"), pytest.raises(RuntimeError):
        middleware(RequestFactory().get("/api/items"))

    assert caplog.records[-1].status == 500
    assert current_request_id() == ""


# trace: FR-002, ADDR-002
def test_bearer_authentication_returns_none_without_authorization_header():
    """Authorization ヘッダーがない要求は認証なしとして扱う（認可で判定する）。"""
    request = RequestFactory().get("/api/cart")

    assert BearerTokenAuthentication().authenticate(request) is None


# trace: FR-002
@pytest.mark.parametrize(
    "header",
    ["Token abc", "Bearer", "Bearer ", "Bearer a b", "bearer abc"],
)
def test_bearer_authentication_rejects_malformed_header(header, settings):
    """形式が異なる認証情報は認証エラー（AUTHENTICATION_REQUIRED）とする。"""
    settings.AUTH_TOKEN_RESOLVER = "test_common_middleware_auth.resolve_ok"
    request = RequestFactory().get("/api/cart", **{"HTTP_AUTHORIZATION": header})

    with pytest.raises(AuthenticationRequired):
        BearerTokenAuthentication().authenticate(request)


# trace: FR-002
def test_bearer_authentication_rejects_unresolvable_token(settings):
    """無効・期限切れ・無効化済みのトークンは認証エラーとする。"""
    settings.AUTH_TOKEN_RESOLVER = "test_common_middleware_auth.resolve_none"
    request = RequestFactory().get("/api/cart", **{"HTTP_AUTHORIZATION": "Bearer expired-token"})

    with pytest.raises(AuthenticationRequired):
        BearerTokenAuthentication().authenticate(request)


# trace: NFR-SC-12
def test_bearer_authentication_resolves_user_and_token(settings):
    """有効なトークンは利用者と認証トークンへ解決し、ログ用に利用者を保持する。"""
    settings.AUTH_TOKEN_RESOLVER = "test_common_middleware_auth.resolve_ok"
    request = RequestFactory().get("/api/cart", **{"HTTP_AUTHORIZATION": "Bearer valid-token"})

    user, token = BearerTokenAuthentication().authenticate(request)

    assert (user, token) == RESOLVED
    assert request.login_user is RESOLVED[0]
    assert BearerTokenAuthentication().authenticate_header(request) == "Bearer"


# trace: NFR-SC-03
def test_is_authenticated_rejects_anonymous_request():
    """未ログインの要求は認証エラー（401）とする。"""

    class Request:
        user = None

    with pytest.raises(AuthenticationRequired):
        IsAuthenticated().has_permission(Request(), None)


# trace: NFR-SC-03
def test_is_authenticated_allows_logged_in_user():
    """ログイン済みの利用者（購入者・管理者）は利用できる。"""

    class Request:
        user = StubUser(ROLE_ADMIN)

    assert IsAuthenticated().has_permission(Request(), None) is True


# trace: NFR-SC-03
def test_is_buyer_rejects_admin_with_permission_denied():
    """購入者専用機能を管理者が要求した場合は権限エラー（403）とする。"""

    class Request:
        user = StubUser(ROLE_ADMIN)

    with pytest.raises(PermissionDeniedError):
        IsBuyer().has_permission(Request(), None)


# trace: NFR-SC-03
def test_is_buyer_allows_buyer_and_rejects_anonymous():
    """購入者は利用でき、未ログインは認証エラーとする。"""

    class BuyerRequest:
        user = StubUser(ROLE_BUYER)

    class AnonymousRequest:
        user = None

    assert IsBuyer().has_permission(BuyerRequest(), None) is True
    with pytest.raises(AuthenticationRequired):
        IsBuyer().has_permission(AnonymousRequest(), None)


# trace: NFR-SC-03
def test_is_admin_rejects_buyer_with_permission_denied():
    """管理者専用機能を購入者が要求した場合は権限エラー（403）とする。"""

    class Request:
        user = StubUser(ROLE_BUYER)

    with pytest.raises(PermissionDeniedError):
        IsAdmin().has_permission(Request(), None)


# trace: NFR-SC-03
def test_is_admin_allows_admin_and_rejects_anonymous():
    """管理者は利用でき、未ログインは認証エラーとする。"""

    class AdminRequest:
        user = StubUser(ROLE_ADMIN)

    class AnonymousRequest:
        user = None

    assert IsAdmin().has_permission(AdminRequest(), None) is True
    with pytest.raises(AuthenticationRequired):
        IsAdmin().has_permission(AnonymousRequest(), None)
