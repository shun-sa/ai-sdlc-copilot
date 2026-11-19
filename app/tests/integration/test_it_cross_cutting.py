# trace: FR-001, FR-002, FR-011, FR-012, FR-022, FR-030, FR-033, FR-042, NFR-OM-01, NFR-OM-06, NFR-OM-18
# trace: NFR-SC-04, NFR-SC-05, NFR-SC-06, NFR-SC-10, ADDR-001, ADDR-006, ADDR-011, ADDR-012, ADDR-013
# trace: ADDR-014
"""結合試験：横断的な連携（ミドルウェア→ログ、WSGI 入口、共通エラー、画面出力、試験用状態の管理コマンド）。

IT-056〜IT-061（AI INITIAL）。期待結果は NFR-OM-01/06/18、NFR-SC-04/05/06/10、CMN-18、
ADDR-001（エラー封筒・HTTP ステータス）・ADDR-011（試験用状態）・ADDR-012・
ADDR-013（ログ形式・要求の識別子・機密除外）・
ADDR-014（WSGI 起動点）から導出する。charset 指定とクエリを伴う要求は config.wsgi.application を直接呼ぶ。
"""

import io
import json
import re
import sys
from contextlib import contextmanager
from datetime import datetime

import pytest
from django.core.management import call_command

from tests.integration._helpers import ADDRESS, PASSWORD, add_item, api, body, error_of, place, text

pytestmark = pytest.mark.django_db

UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
INTERNALS = ("Traceback", "SELECT ", "INSERT ", '.py"', ".py,", "psycopg", 'File "', "line ")


# trace: NFR-OM-18, NFR-OM-01, NFR-SC-06, FR-001, FR-002, FR-030, ADDR-013
def test_it_056_request_id_correlation_and_no_sensitive_logs(api_client, catalog, app_logs):
    """IT-056 要求の識別子によるログの関連付けと機密項目の非出力。"""
    unit = catalog.stock_unit(stock=5)
    email, name = "log.check@example.test", "記録 確認者"
    responses = [
        api(
            api_client,
            "post",
            "/api/auth/register/",
            data={"email": email, "password": PASSWORD, "password_confirmation": PASSWORD, "name": name},
        )
    ]
    login = api(api_client, "post", "/api/auth/login/", data={"email": email, "password": PASSWORD})
    responses.append(login)
    token_value = body(login)["token"]
    token = f"Bearer {token_value}"
    responses.append(add_item(api_client, token, unit.pk, 1))
    address = {
        **ADDRESS,
        "recipient_name": "配送 秘匿",
        "address_line1": "秘匿市1-2-3",
        "address_line2": "秘匿ビル",
        "phone_number": "09087654321",
        "postal_code": "9876543",
    }
    responses.append(place(api_client, token, address))
    responses.append(api(api_client, "get", "/api/products/?keyword=secretword&page=1", token))
    assert [r.status_code for r in responses] == [201, 200, 200, 201, 200]

    records = app_logs.records()
    request_ids = [r["X-Request-ID"] for r in responses]
    assert all(UUID.match(rid) for rid in request_ids) and len(set(request_ids)) == len(request_ids)
    for response, rid in zip(responses, request_ids, strict=True):
        own = [r for r in records if r["request_id"] == rid]
        types = {r["log_type"] for r in own}
        assert {"LOG-01", "LOG-03"} <= types, (rid, types)
        access = [r for r in own if r["log_type"] == "LOG-03"]
        assert len(access) == 1 and access[0]["status"] == response.status_code
        assert "?" not in access[0]["path"]
        for record in own:
            assert {"timestamp", "level", "log_type", "request_id"} <= set(record)
    search = next(r for r in records if r["request_id"] == request_ids[-1] and r["log_type"] == "LOG-03")
    assert search["path"] == "/api/products/"

    dump = "\n".join(app_logs.lines)
    for secret in (
        email,
        PASSWORD,
        token_value,
        name,
        "配送 秘匿",
        "秘匿市1-2-3",
        "秘匿ビル",
        "09087654321",
        "9876543",
        "secretword",
    ):
        assert secret not in dump, secret


# trace: NFR-SC-10, FR-012, FR-022, FR-033, FR-042, ADDR-001, ADDR-006
def test_it_057_api_error_envelope(api_client, buyer, admin, bearer):
    """IT-057 Web API の共通エラー封筒（404・405・JSON 不正・識別子解釈不可）。"""
    buyer_token, admin_token = bearer(buyer), bearer(admin)
    checks = [
        (api(api_client, "get", "/api/no-such/"), 404, "not_found"),
        (api(api_client, "get", "/api/products/1.5/"), 404, "not_found"),
        (api(api_client, "patch", "/api/cart/items/x/", buyer_token, {"quantity": 1}), 404, "not_found"),
        (api(api_client, "get", "/api/orders/abc/", buyer_token), 404, "not_found"),
        (api(api_client, "get", "/api/admin/orders/-1/", admin_token), 404, "not_found"),
        (api_client.post("/api/auth/login/", data="{bad json", content_type="application/json"), 400, "input_error"),
    ]
    for response, status, error_type in checks:
        assert response.status_code == status, response.content
        err = error_of(response)
        assert err["type"] == error_type
        assert err["reason"] is None and err["values"] == {} and isinstance(err["message"], str) and err["message"]
        assert not any(word in response.content.decode("utf-8") for word in INTERNALS)
    put = api(api_client, "put", "/api/products/", data={})
    assert put.status_code == 405
    error_of(put)
    assert not any(word in put.content.decode("utf-8") for word in INTERNALS)


# trace: NFR-SC-04, ADDR-012
@contextmanager
def _without_connection_reset():
    """WSGI 処理の要求開始・終了の接続の整理を一時停止する。

    試験のトランザクションを保つため（Django の試験クライアントと同じ扱い）。
    """
    from django.core.signals import request_finished, request_started
    from django.db import close_old_connections

    request_started.disconnect(close_old_connections)
    request_finished.disconnect(close_old_connections)
    try:
        yield
    finally:
        request_started.connect(close_old_connections)
        request_finished.connect(close_old_connections)


# trace: NFR-SC-04, ADDR-012, ADDR-014
def _call_wsgi(path, query, content_type):
    from config.wsgi import application

    environ = {
        "REQUEST_METHOD": "GET",
        "PATH_INFO": path,
        "QUERY_STRING": query,
        "CONTENT_TYPE": content_type,
        "CONTENT_LENGTH": "0",
        "SERVER_NAME": "localhost",
        "SERVER_PORT": "80",
        "HTTP_HOST": "localhost",
        "SERVER_PROTOCOL": "HTTP/1.1",
        "wsgi.input": io.BytesIO(b""),
        "wsgi.errors": sys.stderr,
        "wsgi.url_scheme": "http",
        "wsgi.version": (1, 0),
        "wsgi.multithread": False,
        "wsgi.multiprocess": False,
        "wsgi.run_once": False,
    }
    status = {}

    def start_response(value, headers, exc_info=None):
        status["value"] = value
        return lambda data: None

    try:
        with _without_connection_reset():
            chunks = application(environ, start_response)
            content = b"".join(chunks)
            if hasattr(chunks, "close"):
                chunks.close()
        return int(status["value"].split()[0]), content
    except Exception as exc:  # noqa: BLE001 - アプリケーション外へ送出された例外は AP サーバーで 500 になる
        return 500, f"{type(exc).__name__} raised out of application".encode()


# trace: NFR-SC-04, ADDR-012, ADDR-014
def test_it_058_wsgi_unusable_charset_with_query():
    """IT-058 WSGI 入口の文字コード指定（charset）とクエリを伴う要求。"""
    results = {}
    # 復号に使えない指定であることが判定に影響するよう、UTF-8 の非 ASCII を含むクエリ（keyword=あ）を伴わせる
    for charset in ("rot13", "undefined", "idna"):
        for path in ("/api/products/", "/"):
            code, content = _call_wsgi(path, "keyword=%E3%81%82&page=1", f"text/plain; charset={charset}")
            results[(charset, path)] = code
    failures = {k: v for k, v in results.items() if v != 400}
    assert not failures, f"charset 指定の要求が 400 にならない: {failures}（全結果 {results}）"


# trace: NFR-SC-04, FR-001, FR-011, FR-030, ADDR-001
def test_it_059_nul_character_input_is_input_error(api_client, buyer, bearer, catalog):
    """IT-059 NUL 文字を含む入力（保存できない文字）。"""
    from accounts.models import User
    from orders.models import Order

    unit = catalog.stock_unit(stock=5)
    users_before = User.objects.count()
    register = api(
        api_client,
        "post",
        "/api/auth/register/",
        data={
            "email": "nul@example.test",
            "password": PASSWORD,
            "password_confirmation": PASSWORD,
            "name": "名\u0000前",
        },
    )
    search = api(api_client, "get", "/api/products/?keyword=a%00b")
    token = bearer(buyer)
    add_item(api_client, token, unit.pk, 1)
    order = place(api_client, token, {**ADDRESS, "recipient_name": "受取\u0000太郎"})
    results = {"register": register.status_code, "search": search.status_code, "order": order.status_code}
    assert results == {"register": 400, "search": 400, "order": 400}, results
    for response in (register, search, order):
        assert error_of(response)["type"] == "input_error"
    assert User.objects.count() == users_before and Order.objects.count() == 0


# trace: NFR-SC-05, FR-012, ADDR-012
def test_it_060_xss_escaped_in_screens(web, catalog):
    """IT-060 画面出力のスクリプトのエスケープ。"""
    product = catalog.product("<script>alert('x1')</script>", description="<img src=x onerror=alert('x2')>")
    catalog.stock_unit(product, variant_name="<b>v</b>")
    client = web()
    detail = text(client.get(f"/products/{product.pk}/"))
    assert "<script>alert('x1')</script>" not in detail and "&lt;script&gt;" in detail
    assert "<img src=x onerror" not in detail and "&lt;img src=x" in detail
    assert "<b>v</b>" not in detail
    listing = text(client.get("/?keyword=%3Cscript%3Ealert(%27x3%27)%3C/script%3E"))
    assert "<script>alert('x3')</script>" not in listing


# trace: NFR-OM-06, ADDR-011
def test_it_061_test_state_command():
    """IT-061 試験用状態の管理コマンド（set・show・clear）と時刻提供点。"""
    from common import clock

    def run(*args):
        out = io.StringIO()
        call_command("test_state", *args, stdout=out)
        return json.loads(out.getvalue().strip().splitlines()[-1])

    shown = run(
        "set",
        "--now",
        "2027-04-30T23:59:59+09:00",
        "--payment-mode",
        "invalid_result",
        "--payment-delay",
        "2",
        "--order-fault",
        "after_order_insert",
    )
    assert datetime.fromisoformat(shown["fixed_now"]) == datetime.fromisoformat("2027-04-30T23:59:59+09:00")
    assert (shown["payment_mode"], shown["payment_delay_seconds"], shown["order_fault_point"]) == (
        "invalid_result",
        2.0,
        "after_order_insert",
    )
    assert run("show") == shown
    assert clock.now_seconds() == datetime.fromisoformat("2027-04-30T23:59:59+09:00")
    cleared = run("clear")
    assert cleared == {
        "fixed_now": None,
        "payment_delay_seconds": 0.0,
        "payment_mode": "normal",
        "order_fault_point": "none",
    }
    assert run("show") == cleared
    assert abs((clock.now_seconds() - datetime.now().astimezone()).total_seconds()) < 5
