# trace: FR-002, FR-003, FR-011, FR-021, NFR-SC-03, NFR-SC-04, NFR-SC-06, NFR-SC-09, ADDR-002
"""画面共通の支援処理（遷移先の検証・権限判定・ページ番号表示・セッション）の単体テスト。

期待値は NFR-SC-04（外部サイトへの遷移を許さない）、CMN-02・CMN-03（認証・権限）、
ADDR-002 の画面セッション方式から導出する。
"""
import pytest
from django.contrib.sessions.middleware import SessionMiddleware
from django.http import HttpResponse
from django.test import RequestFactory

from shop.common.errors import AuthenticationRequiredError, NotFoundError, PermissionDeniedError
from shop.web import session, support


# trace: NFR-SC-04
def _request(path="/cart", method="get", data=None, with_session=False):
    """セッションを持つ（または持たない）要求を組み立てる。"""
    factory = RequestFactory()
    request = getattr(factory, method)(path, data or {})
    if with_session:
        middleware = SessionMiddleware(lambda req: HttpResponse())
        middleware.process_request(request)
        request.session.save()
    return request


# trace: NFR-SC-03, NFR-SC-04
@pytest.mark.parametrize(
    "candidate",
    [
        "https://example.net/phishing",
        "//example.net/phishing",
        "http://localhost/evil",
        "javascript:alert(1)",
        "",
        None,
        123,
    ],
)
def test_safe_internal_path_rejects_external_destinations(candidate):
    """自サイト内の相対パス以外は遷移先として採用しない（オープンリダイレクト対策）。"""
    assert support.safe_internal_path(_request(), candidate) == "/"


# trace: NFR-SC-04
@pytest.mark.parametrize("candidate", ["/cart", "/purchase-orders/1", "/items/5?x=1"])
def test_safe_internal_path_accepts_internal_paths(candidate):
    """自サイト内の相対パスはそのまま遷移先とする。"""
    assert support.safe_internal_path(_request(), candidate) == candidate


# trace: NFR-SC-04
def test_safe_internal_path_uses_given_fallback():
    """遷移先が不正な場合は指定した既定の遷移先を返す。"""
    assert support.safe_internal_path(_request(), "https://example.net", "/cart") == "/cart"


# trace: NFR-SC-04
def test_login_return_path_for_get_request():
    """GET ではログイン後に元の画面へ戻す。"""
    request = _request("/cart?page=2")

    assert support.login_return_path(request) == "/cart?page=2"


# trace: NFR-SC-04
def test_login_return_path_for_post_uses_return_to():
    """更新操作では指定された自サイト内の戻り先を使う。"""
    request = _request("/cart/lines", method="post", data={"return_to": "/cart"})

    assert support.login_return_path(request) == "/cart"


# trace: NFR-SC-04
def test_login_return_path_ignores_external_return_to():
    """更新操作の戻り先が外部サイトの場合は採用しない。"""
    request = _request("/cart/lines", method="post", data={"return_to": "https://example.net"})

    assert support.login_return_path(request) == "/"


# trace: NFR-SC-04
def test_login_return_path_uses_referer_of_same_host():
    """戻り先の指定が無い場合は同一ホストの参照元の画面へ戻す。"""
    factory = RequestFactory()
    request = factory.post("/cart/lines", {}, headers={"referer": "http://testserver/items/1"})

    assert support.login_return_path(request) == "/items/1"


# trace: NFR-SC-04
def test_login_return_path_ignores_external_referer():
    """参照元が別ホストの場合は既定の画面へ戻す。"""
    factory = RequestFactory()
    request = factory.post("/cart/lines", {}, headers={"referer": "http://example.net/items/1"})

    assert support.login_return_path(request) == "/"


# trace: NFR-SC-03
@pytest.mark.django_db
def test_require_buyer_and_require_admin_use_session_user(buyer, admin_user):
    """画面の権限判定はログインセッションの利用者で行う。"""
    request = _request(with_session=True)
    session.login(request, buyer)

    assert support.require_buyer(request).user_id == buyer.user_id
    with pytest.raises(PermissionDeniedError):
        support.require_admin(request)


# trace: NFR-SC-03
@pytest.mark.django_db
def test_require_buyer_rejects_anonymous():
    """未ログインの画面操作は認証エラーとする。"""
    request = _request(with_session=True)

    with pytest.raises(AuthenticationRequiredError):
        support.require_buyer(request)


# trace: FR-002, ADDR-002
@pytest.mark.django_db
def test_session_login_sets_user_and_cycles_key(buyer):
    """ログイン時にセッション識別子を再発行し、利用者を記録する（セッション固定攻撃対策）。"""
    request = _request(with_session=True)
    before = request.session.session_key

    session.login(request, buyer)

    assert request.session[session.SESSION_USER_KEY] == buyer.user_id
    assert request.session.session_key != before


# trace: FR-002, ADDR-002
@pytest.mark.django_db
def test_session_current_user_returns_logged_in_user(buyer):
    """セッションの利用者IDから利用者を取得する。"""
    request = _request(with_session=True)
    session.login(request, buyer)

    assert session.current_user(request).user_id == buyer.user_id


# trace: FR-002, ADDR-002
@pytest.mark.django_db
def test_session_current_user_returns_none_when_not_logged_in():
    """未ログインのセッションでは None を返す。"""
    request = _request(with_session=True)

    assert session.current_user(request) is None


# trace: FR-002, ADDR-002
@pytest.mark.django_db
def test_session_current_user_flushes_session_for_deleted_user(buyer):
    """セッションの利用者が存在しない場合はセッションを破棄して None を返す。"""
    request = _request(with_session=True)
    session.login(request, buyer)
    buyer.delete()

    assert session.current_user(request) is None
    assert session.SESSION_USER_KEY not in request.session


# trace: FR-003, ADDR-002
@pytest.mark.django_db
def test_session_logout_clears_session(buyer):
    """ログアウトでログインセッションを破棄する。"""
    request = _request(with_session=True)
    session.login(request, buyer)

    session.logout(request)

    assert session.SESSION_USER_KEY not in request.session


# trace: NFR-SC-09
def test_session_cookie_timeout_and_httponly_settings():
    """ログインセッションは無操作30分で無効化し、Cookie に HttpOnly を付与する（NFR-SC-09）。

    SESSION_SAVE_EVERY_REQUEST により、最後の操作からの無操作時間で期限を数える。
    Secure 属性は環境変数で切り替える（本番環境＝ENV-02 で付与する）。
    """
    from django.conf import settings

    assert settings.SESSION_COOKIE_AGE == 30 * 60
    assert settings.SESSION_SAVE_EVERY_REQUEST is True
    assert settings.SESSION_COOKIE_HTTPONLY is True
    assert settings.SESSION_EXPIRE_AT_BROWSER_CLOSE is False


# trace: FR-021, ADDR-002
@pytest.mark.django_db
def test_flash_message_is_shown_once():
    """完了メッセージは1回だけ取り出せる。"""
    request = _request(with_session=True)
    session.set_flash(request, "保存しました。")

    assert session.pop_flash(request) == "保存しました。"
    assert session.pop_flash(request) is None


# trace: FR-011
@pytest.mark.parametrize(
    ("page", "total_pages", "expected"),
    [
        (1, 0, []),
        (1, 1, []),
        (1, 3, [1, 2, 3]),
        (5, 10, [1, 3, 4, 5, 6, 7, 10]),
        (10, 10, [1, 8, 9, 10]),
    ],
)
def test_page_range(page, total_pages, expected):
    """ページ番号の表示は現在ページの前後2ページと先頭・最終を含む。"""
    assert support.page_range(page, total_pages) == expected


# trace: NFR-SC-06
@pytest.mark.django_db
def test_handle_app_errors_renders_error_screen_for_permission_denied():
    """権限エラーは権限なしの画面（403）を表示する。"""

    @support.handle_app_errors
    def view(request):
        raise PermissionDeniedError()

    response = view(_request(with_session=True))

    assert response.status_code == 403


# trace: NFR-SC-06
@pytest.mark.django_db
def test_handle_app_errors_renders_error_screen_for_not_found():
    """対象なしエラーは対象なしの画面（404）を表示する。"""

    @support.handle_app_errors
    def view(request):
        raise NotFoundError()

    response = view(_request(with_session=True))

    assert response.status_code == 404


# trace: NFR-SC-06
@pytest.mark.django_db
def test_handle_app_errors_redirects_to_login_for_authentication_error():
    """認証エラーはログイン画面へ遷移させ、元の画面へ戻す情報を付ける。"""

    @support.handle_app_errors
    def view(request):
        raise AuthenticationRequiredError()

    response = view(_request("/cart", with_session=True))

    assert response.status_code == 302
    assert response["Location"].startswith("/login?next=")


# trace: NFR-SC-06
@pytest.mark.django_db
def test_handle_app_errors_renders_system_error():
    """システムエラーはシステムエラーの画面（500）を表示する。"""
    from shop.common.errors import InternalError

    @support.handle_app_errors
    def view(request):
        raise InternalError()

    response = view(_request(with_session=True))

    assert response.status_code == 500


# trace: NFR-SC-06
@pytest.mark.django_db
def test_handle_app_errors_reraises_business_errors():
    """業務エラー（入力・業務ルール）は各画面で扱うため再送出する。"""
    from shop.common.errors import CartEmptyError

    @support.handle_app_errors
    def view(request):
        raise CartEmptyError()

    with pytest.raises(CartEmptyError):
        view(_request(with_session=True))
