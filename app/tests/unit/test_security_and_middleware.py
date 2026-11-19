# trace: NFR-SC-04, NFR-SC-02, NFR-SC-10, NFR-SC-05, NFR-SC-19, FR-060
# trace: ADDR-001, ADDR-002, ADDR-011, ADDR-012, ADDR-013, ADDR-014
"""入力値検証・インジェクション対策・内部情報の非表示・HTTPS 強制・本番設定（共通処理・ミドルウェア・設定）の
単体テスト。

期待値：NFR-SC-04（全外部入力をシステムが検証し、SQL・OS コマンドインジェクションが成立しない。形式不正の外部入力は
入力エラー＝ERR-01 400 であり、データベースの操作のエラー・システムエラーにしない：ADDR-001 4.3 の7・INV-002）、
NFR-SC-10（エラー応答に内部情報を含めない、本番でデバッグ情報を表示しない）、NFR-SC-02（本番は HTTPS のみ）、
NFR-SC-05（CSRF 失敗は拒否）、NFR-SC-19（セッション識別子の保護）、ADDR-011（試験支援は開発用機能フラグ有効時のみ）、
ADDR-013（LOG-02・LOG-03）、ADDR-014 DD-002・DD-003・DD-011（本番プロファイルの強制）。
DB Test Strategy：CONTAINER（要求を DB まで通し DB 例外が起きないことを確認）。設定の読込みは DB を使わない。
"""

import importlib.util
import io
import json
import sys
from pathlib import Path
from unittest import mock

import pytest
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, RequestFactory

from accounts.models import User
from common import clock, faults, middleware, views
from common.context_processors import site_header
from common.sessions import SessionStore
from initial_data import loader

# ---------------------------------------------------------------------------
# NUL 等のデータベースが受理しない文字・攻撃文字列（NFR-SC-04、VUL-04）
# ---------------------------------------------------------------------------

NUL = "\x00"
SQLI = "' OR '1'='1' --"


# trace: NFR-SC-04, ADDR-001
def _status(client, method, path, auth=None, body=None):
    kwargs = {"HTTP_AUTHORIZATION": auth} if auth else {}
    if body is not None:
        kwargs["data"] = json.dumps(body)
        kwargs["content_type"] = "application/json"
    response = getattr(client, method)(path, **kwargs)
    return response.status_code, response


# trace: NFR-SC-04, ADDR-001
@pytest.mark.django_db
def test_nul_and_unstorable_inputs_are_rejected_without_database_errors(
    api_client, bearer, buyer, admin, catalog, app_logs
):
    """全入力項目に NUL を含めても 400（入力エラー）・401・404 となり、500（システムエラー）・LOG-02 にならない。"""
    client = Client()
    buyer_auth, admin_auth = bearer(buyer), bearer(admin)
    unit = catalog.stock_unit()
    cases = [
        (
            "post",
            "/api/auth/register/",
            None,
            {"email": f"a{NUL}@b.c", "password": "Passw0rd", "password_confirmation": "Passw0rd", "name": f"n{NUL}"},
            400,
        ),
        ("post", "/api/auth/login/", None, {"email": f"a{NUL}@b.c", "password": f"p{NUL}"}, 401),
        ("get", f"/api/products/?keyword=a{NUL}", None, None, 400),
        ("get", f"/api/products/?sort=new{NUL}", None, None, 400),
        ("get", f"/api/products/?category_id=1{NUL}", None, None, 400),
        ("get", f"/api/products/?page=1{NUL}", None, None, 400),
        ("get", f"/api/products/1{NUL}/", None, None, 404),
        ("post", "/api/cart/items/", buyer_auth, {"stock_unit_id": f"{unit.pk}{NUL}", "quantity": 1}, 400),
        ("post", "/api/cart/coupon/", buyer_auth, {"coupon_code": f"A{NUL}"}, 400),
        ("patch", f"/api/cart/items/1{NUL}/", buyer_auth, {"quantity": 1}, 404),
        (
            "post",
            "/api/orders/",
            buyer_auth,
            {
                "shipping_address": {
                    "recipient_name": f"r{NUL}",
                    "postal_code": f"123{NUL}4567",
                    "prefecture": f"13{NUL}",
                    "address_line1": f"a{NUL}",
                    "address_line2": f"b{NUL}",
                    "phone_number": f"03{NUL}",
                }
            },
            400,
        ),
        ("post", "/api/orders/1/payment/", buyer_auth, {"mock_instruction": f"approved{NUL}"}, 400),
        (
            "get",
            f"/api/admin/stock-units/?sku=a{NUL}&product_name=b{NUL}&supplier_code=c{NUL}&low_stock_only=t{NUL}",
            admin_auth,
            None,
            400,
        ),
        (
            "get",
            f"/api/admin/orders/?order_number=PO{NUL}&status=paid{NUL}&order_date_from=2027{NUL}&buyer_email=x{NUL}",
            admin_auth,
            None,
            400,
        ),
        ("post", "/api/admin/orders/1/ship/", admin_auth, {"tracking_number": f"T{NUL}"}, 400),
    ]
    for method, path, auth, body, expected in cases:
        status, response = _status(api_client if auth or body is not None else client, method, path, auth, body)
        assert status == expected, (path, status, response.content[:200])
    assert not [r for r in app_logs.records() if r["log_type"] == "LOG-02"]


# trace: NFR-SC-04, ADDR-001, ADDR-002
@pytest.mark.django_db
def test_nul_in_web_form_and_session_cookie_is_not_a_system_error(login_web, buyer, app_logs):
    client = Client()
    response = client.post(
        "/register/",
        {"email": f"a{NUL}@b.c", "password": "Passw0rd", "password_confirmation": "Passw0rd", "name": "n"},
    )
    assert response.status_code == 400
    response = client.post("/login/", {"email": f"a{NUL}", "password": "x", "next": f"/{NUL}"})
    assert response.status_code == 401
    response = client.get(f"/?keyword={NUL}")
    assert response.status_code == 400
    cookie_client = Client()
    cookie_client.cookies[settings.SESSION_COOKIE_NAME] = f"abc{NUL}def"
    assert cookie_client.get("/").status_code == 200  # 存在しないセッションとして来訪者で処理する
    assert not [r for r in app_logs.records() if r["log_type"] == "LOG-02"]


# trace: NFR-SC-02, ADDR-002
def test_session_store_rejects_keys_with_unstorable_characters():
    store = SessionStore()
    assert store._validate_session_key("a" * 32) is True
    assert store._validate_session_key("a" * 16 + NUL + "a" * 15) is False


# trace: NFR-SC-04, ADDR-001
@pytest.mark.django_db
def test_sql_injection_strings_are_treated_as_plain_values(api_client, bearer, admin, buyer, catalog):
    product = catalog.product("安全な商品")
    catalog.stock_unit(product)
    response = api_client.get("/api/products/", {"keyword": SQLI})
    assert response.status_code == 200 and response.json()["total_count"] == 0
    assert api_client.get("/api/products/", {"category_id": "1 OR 1=1"}).status_code == 400
    assert api_client.get("/api/products/1;DROP TABLE catalog_product/").status_code == 404
    response = api_client.post("/api/auth/login/", {"email": SQLI, "password": SQLI}, format="json")
    assert response.status_code == 401
    response = api_client.get("/api/admin/orders/", {"buyer_email": SQLI}, HTTP_AUTHORIZATION=bearer(admin))
    assert response.status_code == 200 and response.json()["items"] == []
    response = api_client.get(
        "/api/admin/stock-units/", {"sku": "%' --", "product_name": SQLI}, HTTP_AUTHORIZATION=bearer(admin)
    )
    assert response.status_code == 200 and response.json()["total_count"] == 0
    assert User.objects.filter(pk=buyer.pk).exists() and product.__class__.objects.count() == 1


# trace: NFR-SC-04, FR-060, ADDR-012
@pytest.mark.django_db
def test_definition_file_path_is_not_passed_to_a_shell():
    """OS コマンドインジェクション：引数のパスだけを開き、シェル・OS コマンドを経由しない（ADDR-010 DD-008）。"""
    with (
        mock.patch("subprocess.run") as run,
        mock.patch("os.system") as system,
        mock.patch("subprocess.Popen") as popen,
    ):
        with pytest.raises(loader.LoadError) as info:
            loader.run_load("missing.json; echo pwned > pwned.txt", False, clock.now_seconds())
    assert info.value.code == "E-060-02"
    run.assert_not_called()
    system.assert_not_called()
    popen.assert_not_called()
    assert not Path("pwned.txt").exists()


# ---------------------------------------------------------------------------
# 文字コード指定の不正（NFR-SC-04。既知の未解決 UNRESOLVED-6de5eec64599b907 の該当ケースを含む）
# ---------------------------------------------------------------------------


# trace: NFR-SC-04, ADDR-001, ADDR-012
def _wsgi_status(environ_extra):
    from config.wsgi import application

    environ = {
        "REQUEST_METHOD": "GET",
        "PATH_INFO": "/api/products/",
        "QUERY_STRING": "",
        "SERVER_NAME": "localhost",
        "SERVER_PORT": "80",
        "HTTP_HOST": "localhost",
        "wsgi.url_scheme": "http",
        "wsgi.input": io.BytesIO(b""),
        "wsgi.errors": io.StringIO(),
        "wsgi.version": (1, 0),
        "wsgi.multithread": False,
        "wsgi.multiprocess": False,
        "wsgi.run_once": False,
    }
    environ.update(environ_extra)
    captured = {}

    def start_response(status, headers, exc_info=None):
        captured["status"] = int(status.split(" ", 1)[0])
        return lambda data: None

    # 試験用 DB のトランザクションを保つため、Django の試験用 Client と同様に接続の自動切断を外して呼び出す
    from django.core.signals import request_finished, request_started
    from django.db import close_old_connections

    request_started.disconnect(close_old_connections)
    request_finished.disconnect(close_old_connections)
    try:
        body = b"".join(application(environ, start_response))
    except Exception as exc:  # noqa: BLE001 - 例外がアプリケーション外へ送出された事実を結果として返す
        return f"raised {type(exc).__name__}", b""
    finally:
        request_started.connect(close_old_connections)
        request_finished.connect(close_old_connections)
    return captured["status"], body


# trace: NFR-SC-04, ADDR-012
@pytest.mark.django_db
@pytest.mark.parametrize(
    ("path", "query"), [("/api/products/", "keyword=%41"), ("/", "keyword=%41"), ("/no-such/", "a=b")]
)
def test_non_text_charset_with_query_is_400(path, query):
    status, body = _wsgi_status(
        {"PATH_INFO": path, "QUERY_STRING": query, "CONTENT_TYPE": "text/plain; charset=rot13"}
    )
    assert status == 400
    assert b"Traceback" not in body


# trace: NFR-SC-04, ADDR-012
@pytest.mark.django_db
@pytest.mark.parametrize(
    ("path", "query", "charset"),
    [
        ("/api/products/", "keyword=%41", "undefined"),
        ("/", "keyword=%41", "undefined"),
        ("/api/admin/orders/", "status=paid", "undefined"),
        ("/no-such/", "a=b", "undefined"),
    ],
)
def test_undecodable_text_charset_with_query_is_input_error_400(path, query, charset):
    """外部入力（Content-Type の文字コード指定）の誤りは ERR-01 入力エラー（400）とし、
    500・アプリ外への例外にしない。"""
    status, body = _wsgi_status(
        {"PATH_INFO": path, "QUERY_STRING": query, "CONTENT_TYPE": f"text/plain; charset={charset}"}
    )
    assert status == 400
    assert b"Traceback" not in body


# trace: NFR-SC-04, ADDR-012
@pytest.mark.django_db
@pytest.mark.parametrize("charset", ["idna", "undefined"])
@pytest.mark.parametrize("path", ["/login/", "/register/"])
def test_multipart_with_undecodable_charset_is_input_error_400(charset, path, app_logs):
    body = b'--xx\r\nContent-Disposition: form-data; name="email"\r\n\r\na@b.c\r\n--xx--\r\n'
    status, _ = _wsgi_status(
        {
            "REQUEST_METHOD": "POST",
            "PATH_INFO": path,
            "CONTENT_TYPE": f"multipart/form-data; boundary=xx; charset={charset}",
            "CONTENT_LENGTH": str(len(body)),
            "HTTP_COOKIE": "csrftoken=" + "a" * 32,  # 形式上有効な CSRF Cookie（本文の解釈まで進む条件）
            "wsgi.input": io.BytesIO(body),
        }
    )
    assert status == 400


# trace: NFR-SC-04, ADDR-012
@pytest.mark.parametrize(
    ("encoding", "unusable"),
    [
        (None, False),
        ("utf-8", False),
        ("no-such-codec", False),
        ("rot13", True),
        ("zlib", True),
        ("base64", True),
    ],
)
def test_is_unusable_charset(encoding, unusable):
    assert middleware.is_unusable_charset(encoding) is unusable


# trace: NFR-SC-04, ADDR-001
@pytest.mark.django_db
def test_too_many_fields_is_400_not_system_error(app_logs, settings):
    settings.DATA_UPLOAD_MAX_NUMBER_FIELDS = 3
    response = Client().post("/login/", {f"f{n}": "x" for n in range(10)})
    assert response.status_code == 400
    response = Client().get("/api/products/", {f"f{n}": "x" for n in range(10)})
    assert response.status_code == 400
    assert not [r for r in app_logs.records() if r["log_type"] == "LOG-02"]


# ---------------------------------------------------------------------------
# 内部情報の非表示・共通エラー画面（NFR-SC-10）
# ---------------------------------------------------------------------------


# trace: NFR-SC-10, ADDR-012, ADDR-013
@pytest.mark.django_db
def test_unexpected_web_error_shows_system_error_page_without_details(app_logs):
    secret = "relation catalog_product does not exist /srv/minicommerce/app/catalog/services.py"
    with mock.patch("catalog.services.list_categories", side_effect=RuntimeError(secret)):
        response = Client().get("/")
    assert response.status_code == 500
    text = response.content.decode()
    assert "システムエラーが発生しました" in text and "catalog_product" not in text and "Traceback" not in text
    errors_logged = [r for r in app_logs.records() if r["log_type"] == "LOG-02"]
    assert errors_logged and errors_logged[-1]["exception_class"] == "builtins.RuntimeError"
    assert secret not in json.dumps(errors_logged)


# trace: NFR-SC-10, ADDR-012
@pytest.mark.django_db
def test_error_views_for_api_and_web():
    factory = RequestFactory()
    api_request, web_request = factory.get("/api/x/"), factory.get("/x/")
    assert views.not_found(api_request).status_code == 404 and views.not_found(web_request).status_code == 404
    assert views.bad_request(api_request).status_code == 400 and views.bad_request(web_request).status_code == 400
    assert views.permission_denied_view(api_request).status_code == 403
    assert views.permission_denied_view(web_request).status_code == 403
    assert views.server_error(api_request).status_code == 500 and views.server_error(web_request).status_code == 500
    assert views.csrf_failure(web_request).status_code == 403
    with mock.patch.object(views, "error_page", side_effect=RuntimeError("template broken")):
        fallback = views.system_error_response(web_request)
    assert fallback.status_code == 500 and fallback.content.decode() == views.MSG_SYSTEM_ERROR


# trace: NFR-SC-10, ADDR-012
@pytest.mark.django_db
def test_web_exception_middleware_passes_through_404_and_permission_denied():
    from django.core.exceptions import PermissionDenied, SuspiciousOperation
    from django.http import Http404

    instance = middleware.WebExceptionMiddleware(lambda r: None)
    request = RequestFactory().get("/x/")
    assert instance.process_exception(request, Http404()) is None
    assert instance.process_exception(request, PermissionDenied()) is None
    assert instance.process_exception(request, SuspiciousOperation()).status_code == 400


# ---------------------------------------------------------------------------
# HTTPS の強制・本番設定（NFR-SC-02、NFR-SC-10、ADDR-014）
# ---------------------------------------------------------------------------


# trace: NFR-SC-02, ADDR-014
def test_https_only_middleware_rejects_plain_http_in_production(settings):
    instance = middleware.HttpsOnlyMiddleware(lambda r: "passed")
    factory = RequestFactory()
    settings.IS_PRODUCTION = True
    response = instance(factory.get("/"))
    assert response.status_code == 403  # 転送せずに業務処理の前に拒否する
    assert instance(factory.get("/", secure=True)) == "passed"
    settings.IS_PRODUCTION = False
    assert instance(factory.get("/")) == "passed"


# trace: NFR-SC-10, NFR-SC-02, NFR-SC-19, ADDR-014
def _load_settings(monkeypatch, **environment):
    for key in (
        "DJANGO_DEBUG",
        "MINICOMMERCE_DEV_FEATURES",
        "DJANGO_ALLOWED_HOSTS",
        "MINICOMMERCE_TRUSTED_PROXY_SSL_HEADER",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("DJANGO_SECRET_KEY", "test-only-not-a-secret")
    for key, value in environment.items():
        monkeypatch.setenv(key, value)
    path = Path(settings.BASE_DIR) / "config" / "settings.py"
    spec = importlib.util.spec_from_file_location("mc_settings_probe", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sys.modules.pop("mc_settings_probe", None)
    return module


# trace: NFR-SC-10, NFR-SC-02, NFR-SC-19, ADDR-014
def test_production_profile_enforces_safe_settings(monkeypatch):
    prod = _load_settings(monkeypatch, MINICOMMERCE_ENV="production")
    assert prod.DEBUG is False and prod.MINICOMMERCE_DEV_FEATURES is False
    assert "test_support" not in prod.INSTALLED_APPS
    assert prod.SESSION_COOKIE_SECURE and prod.CSRF_COOKIE_SECURE and prod.SECURE_HSTS_SECONDS > 0
    assert prod.SESSION_COOKIE_HTTPONLY and prod.ALLOWED_HOSTS == []
    assert (
        "rest_framework.authentication.SessionAuthentication"
        not in prod.REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"]
    )
    with pytest.raises(ImproperlyConfigured):
        _load_settings(monkeypatch, MINICOMMERCE_ENV="production", DJANGO_DEBUG="true")
    monkeypatch.delenv("DJANGO_DEBUG")
    with pytest.raises(ImproperlyConfigured):
        _load_settings(monkeypatch, MINICOMMERCE_ENV="production", MINICOMMERCE_DEV_FEATURES="true")
    dev = _load_settings(
        monkeypatch, MINICOMMERCE_ENV="development", DJANGO_DEBUG="true", MINICOMMERCE_DEV_FEATURES="false"
    )
    assert dev.SESSION_COOKIE_SECURE is False and "test_support" not in dev.INSTALLED_APPS


# ---------------------------------------------------------------------------
# 要求の識別子・アクセスログ・無操作判定・共通表示（ADDR-013、ADDR-002）
# ---------------------------------------------------------------------------


# trace: NFR-SC-10, ADDR-013
@pytest.mark.django_db
def test_request_id_is_generated_by_server_not_taken_from_header(app_logs):
    response = Client().get("/api/categories/", HTTP_X_REQUEST_ID="attacker-chosen")
    assert response["X-Request-ID"] != "attacker-chosen" and len(response["X-Request-ID"]) == 36
    access = [r for r in app_logs.records() if r["log_type"] == "LOG-03"][-1]
    assert access["request_id"] == response["X-Request-ID"] and access["status"] == 200


# trace: NFR-SC-10, ADDR-013
def test_access_log_user_id_resolution_failures_do_not_break_response():
    class Broken:
        @property
        def is_authenticated(self):
            raise RuntimeError("x")

    request = RequestFactory().get("/x/")
    request.user = Broken()
    assert middleware._user_id(request) is None
    request = RequestFactory().get("/api/x/")
    request.api_user_id = 5
    assert middleware._user_id(request) == 5


# trace: NFR-SC-10, ADDR-002
@pytest.mark.django_db
def test_site_header_context_for_visitor_buyer_and_admin(buyer, admin):
    request = RequestFactory().get("/")
    from django.contrib.auth.models import AnonymousUser

    request.user = AnonymousUser()
    assert site_header(request)["header_user"] is None
    request.user = admin
    context = site_header(request)
    assert context["header_is_admin"] is True and context["header_cart_count"] is None
    request.user = buyer
    assert site_header(request)["header_is_admin"] is False


# trace: NFR-SC-10, ADDR-001
@pytest.mark.django_db
def test_header_cart_count_failure_on_error_page_hides_count(buyer):
    from carts.context_processors import header_cart_count
    from common.errors import SystemFailureError, system_failure
    from common.web import ERROR_PAGE_ATTR

    request = RequestFactory().get("/")
    request.user = buyer
    with mock.patch("carts.services.get_cart", side_effect=system_failure("E-020-03")):
        with pytest.raises(SystemFailureError):
            header_cart_count(request)
        setattr(request, ERROR_PAGE_ATTR, True)
        assert header_cart_count(request) == {}


# ---------------------------------------------------------------------------
# 試験支援（ADDR-011：開発用機能フラグ有効時のみ）
# ---------------------------------------------------------------------------


# trace: FR-060, ADDR-011
@pytest.mark.django_db
def test_test_support_features_are_inert_when_flag_disabled(settings, test_state):
    test_state(order_fault_point="after_stock_decrement")
    with pytest.raises(faults.InjectedFaultError):
        faults.order_fault_point("after_stock_decrement")
    faults.order_fault_point("after_order_insert")  # 別の障害点では何もしない
    settings.MINICOMMERCE_DEV_FEATURES = False
    faults.order_fault_point("after_stock_decrement")
    assert clock._fixed_now() is None


# trace: FR-060, ADDR-011
@pytest.mark.django_db
def test_test_state_command_and_validation():
    from test_support import state

    out = io.StringIO()
    call_command("test_state", "set", "--now", "2027-04-30T23:59:59+09:00", "--payment-mode", "normal", stdout=out)
    from datetime import datetime

    from tests.unit.conftest import jst

    assert datetime.fromisoformat(json.loads(out.getvalue())["fixed_now"]) == jst(2027, 4, 30, 23, 59, 59)
    for bad in (["--now", "not-a-date"], ["--now", "2027-04-30T23:59:59"], ["--payment-delay", "-1"]):
        with pytest.raises(CommandError):
            call_command("test_state", "set", *bad, stdout=io.StringIO())
    call_command("test_state", "clear", stdout=io.StringIO())
    out = io.StringIO()
    call_command("test_state", "show", stdout=out)
    assert json.loads(out.getvalue())["payment_mode"] == "normal"
    with pytest.raises(ValueError):
        state.set_state(payment_mode="nope")
    with pytest.raises(ValueError):
        state.set_state(order_fault_point="nope")
    assert state.read_payment_settings() == (0.0, "normal") and state.read_order_fault_point() == "none"
