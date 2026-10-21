# trace: FR-002, FR-003, FR-021, FR-040, NFR-SC-03, NFR-SC-10, NFR-SC-19, NFR-US-04, ADDR-006, ADDR-010, ADDR-011
"""画面のログインセッション・共通エラー表示（web.support）の単体テスト。

期待結果は FR-002／FR-003（ログインセッションの開始・破棄）、NFR-SC-03（未ログイン・権限なしの
判定をサーバー側で行う）、NFR-SC-19（ログイン成功時のセッション識別子の再発行）、
UI-13（検索条件の引継ぎ）、UI-17（ログイン後の復帰先）、SCR-901（エラー画面）から導出する。
"""

from __future__ import annotations

import pytest
from _helpers import make_admin, make_user
from common.exceptions import (
    AuthenticationRequired,
    CartEmpty,
    InternalError,
    NotFoundError,
    PermissionDeniedError,
)
from django.contrib.sessions.backends.db import SessionStore
from django.http import HttpResponse
from django.test import RequestFactory
from web import support

pytestmark = pytest.mark.django_db


# trace: FR-002, ADDR-006
def build_request(path: str = "/", method: str = "get", **params):
    """セッション付きの要求を組み立てる（テスト補助）。"""
    request = getattr(RequestFactory(), method)(path, params)
    request.session = SessionStore()
    return request


# trace: NFR-SC-19
def test_start_session_rotates_session_key_and_stores_user():
    """NFR-SC-19：ログイン成功時にセッション識別子を再発行して利用者を保持する。"""
    user = make_user()
    request = build_request()
    request.session.create()
    before = request.session.session_key

    support.start_session(request, user)

    assert request.session.session_key != before
    assert request.session[support.SESSION_USER_ID] == user.pk
    assert request.login_user is user


# trace: FR-002
def test_current_user_reads_user_from_session():
    """ログインセッションから利用者を取得する。"""
    user = make_user()
    request = build_request()
    request.session[support.SESSION_USER_ID] = user.pk

    assert support.current_user(request).pk == user.pk


# trace: NFR-SC-03
def test_current_user_returns_none_without_session():
    """未ログインの場合は利用者を返さない。"""
    assert support.current_user(build_request()) is None


# trace: FR-003
def test_end_session_discards_session():
    """FR-003：ログアウト時にログインセッションを破棄する。"""
    user = make_user()
    request = build_request()
    support.start_session(request, user)

    support.end_session(request)

    assert support.SESSION_USER_ID not in request.session
    assert request.login_user is None


# trace: NFR-US-04
def test_flash_message_is_shown_only_once():
    """画面上部のメッセージ領域の文言は1回だけ表示する。"""
    request = build_request()

    support.set_flash(request, "保存しました。")

    assert support.pop_flash(request) == "保存しました。"
    assert support.pop_flash(request) is None


# trace: FR-040
def test_query_prefix_keeps_search_conditions_without_page():
    """UI-13：ページ移動のリンクへ検索条件を引き継ぐ（ページ番号は除く）。"""
    request = build_request("/admin-console/stock-units/", sku="KC", page="3")

    prefix = support.query_prefix(request)

    assert prefix.startswith("sku=KC")
    assert "page" not in prefix
    assert prefix.endswith("&")


# trace: FR-040
def test_query_prefix_is_empty_without_conditions():
    """検索条件がない場合は何も引き継がない。"""
    assert support.query_prefix(build_request("/")) == ""


# trace: NFR-SC-03
def test_remember_next_path_keeps_only_internal_get_path():
    """UI-17：復帰先は自サイト内の相対パス（GET）に限る。"""
    request = build_request("/items/1/")

    support.remember_next_path(request)

    assert support.pop_next_path(request) == "/items/1/"


# trace: NFR-SC-03
def test_remember_next_path_ignores_update_request():
    """更新要求そのものは復帰先にしない（再ログイン後に更新を実行しない）。"""
    request = build_request("/cart/lines/add/", method="post")

    support.remember_next_path(request)

    assert support.pop_next_path(request) is None


# trace: NFR-SC-03
@pytest.mark.parametrize("path", ["//evil.example.test/", "https://evil.example.test/"])
def test_pop_next_path_rejects_external_url(path):
    """外部URLへの復帰は受け付けない（オープンリダイレクト対策）。"""
    request = build_request()
    request.session[support.SESSION_NEXT_PATH] = path

    assert support.pop_next_path(request) is None


# trace: FR-021
def test_remember_path_keeps_internal_path():
    """更新操作からの復帰先（表示していた画面）を保持する。"""
    request = build_request()

    support.remember_path(request, "/items/5/")
    support.remember_path(request, "//evil.example.test/")

    assert support.pop_next_path(request) == "/items/5/"


# trace: NFR-SC-03
def test_require_login_rejects_anonymous():
    """未ログインの画面操作は認証エラーとする。"""
    with pytest.raises(AuthenticationRequired):
        support.require_login(build_request())


# trace: NFR-SC-03
def test_require_buyer_rejects_admin():
    """購入者専用画面を管理者が要求した場合は権限エラーとする。"""
    request = build_request()
    support.start_session(request, make_admin())

    with pytest.raises(PermissionDeniedError):
        support.require_buyer(request)


# trace: NFR-SC-03
def test_require_admin_rejects_buyer():
    """管理者専用画面を購入者が要求した場合は権限エラーとする。"""
    request = build_request()
    support.start_session(request, make_user())

    with pytest.raises(PermissionDeniedError):
        support.require_admin(request)


# trace: NFR-SC-03
def test_require_buyer_and_admin_allow_their_roles():
    """購入者・管理者はそれぞれの画面を利用できる。"""
    buyer_request = build_request()
    support.start_session(buyer_request, make_user())
    admin_request = build_request()
    support.start_session(admin_request, make_admin())

    assert support.require_buyer(buyer_request).is_buyer is True
    assert support.require_admin(admin_request).is_admin is True


# trace: NFR-SC-10, ADDR-011
def test_screen_redirects_to_login_on_authentication_error():
    """E-0xx-01：未ログインは SCR-004（ログイン）へ遷移し、復帰先と文言を保持する。"""

    @support.screen
    def view(request):
        raise AuthenticationRequired()

    request = build_request("/cart/")
    response = view(request)

    assert response.status_code == 302
    assert response["Location"] == "/login/"
    assert request.session[support.SESSION_NEXT_PATH] == "/cart/"
    assert support.pop_flash(request)


# trace: NFR-SC-10, ADDR-011
@pytest.mark.parametrize(
    ("exception", "expected_status", "expected_heading"),
    [
        (PermissionDeniedError(), 403, "この画面・操作を利用する権限がありません"),
        (NotFoundError(), 404, "お探しのページ・データが見つかりません"),
        (InternalError(), 500, "システムエラーが発生しました"),
    ],
)
def test_screen_renders_error_page(exception, expected_status, expected_heading):
    """SCR-901：権限なし・対象なし・システムエラーをエラー画面で表示する。"""

    @support.screen
    def view(request):
        raise exception

    response = view(build_request("/"))

    assert response.status_code == expected_status
    assert expected_heading in response.content.decode()


# trace: NFR-SC-10, ADDR-011
def test_screen_does_not_convert_business_error():
    """業務エラーは各画面で表示するため、共通処理では変換しない。"""

    @support.screen
    def view(request):
        raise CartEmpty()

    with pytest.raises(CartEmpty):
        view(build_request("/"))


# trace: NFR-SC-10, ADDR-011
def test_screen_returns_response_of_successful_view():
    """正常終了した画面の応答はそのまま返す。"""

    @support.screen
    def view(request):
        return HttpResponse("ok")

    assert view(build_request("/")).content == b"ok"


# trace: NFR-SC-10, ADDR-011
def test_render_error_does_not_show_internal_details():
    """SCR-901：内部情報（スタックトレース・SQL）は表示しない。"""
    response = support.render_error(build_request("/"), support.ERROR_INTERNAL, 500)

    body = response.content.decode()
    assert "Traceback" not in body
    assert "SELECT" not in body


