# trace: NFR-OM-01, NFR-SC-06, ADDR-005
"""アプリケーションログ・要求コンテキスト・共通ミドルウェアの単体テスト。

期待値は CMN-23（リクエストログ）、LOG-02（例外情報）、NFR-SC-06（ログの禁止項目）、
NFR-OM-01（日時形式）、ADDR-005 の決定内容から導出する。
"""
import json
import logging

import pytest
from django.test import RequestFactory

from shop.common import request_context
from shop.common.logging import ALLOWED_EXTRA_FIELDS, JsonLinesFormatter, RequestContextFilter, build_extra
from shop.common.middleware import RequestLogMiddleware


# trace: NFR-SC-06
def _record(message="event", **extra):
    """ログレコードを1件組み立てる。"""
    record = logging.LogRecord("shop.test", logging.INFO, "module.py", 10, message, None, None)
    for key, value in extra.items():
        setattr(record, key, value)
    return record


# trace: NFR-OM-01
def test_json_lines_formatter_outputs_single_line_json():
    """ログは1イベント1行の JSON として出力する。"""
    record = _record(event="request", status=200)
    RequestContextFilter().filter(record)

    output = JsonLinesFormatter().format(record)

    assert "\n" not in output
    payload = json.loads(output)
    assert payload["level"] == "INFO"
    assert payload["logger"] == "shop.test"
    assert payload["message"] == "event"
    assert payload["event"] == "request"
    assert payload["status"] == 200


# trace: NFR-OM-01
def test_json_lines_formatter_outputs_iso8601_with_offset():
    """発生時刻は ISO 8601（+09:00 付き）で出力する。"""
    record = _record()
    RequestContextFilter().filter(record)

    payload = json.loads(JsonLinesFormatter().format(record))

    assert payload["timestamp"].endswith("+09:00")
    assert "T" in payload["timestamp"]


# trace: NFR-SC-06
def test_build_extra_drops_disallowed_fields():
    """ログの追加項目は許可項目だけに限定する（禁止項目を渡せない）。"""
    extra = build_extra(
        event="login",
        email="user@example.com",
        password="Passw0rd",
        full_name="山田 太郎",
        token="secret-token",
        order_number="PO-00000001",
    )

    assert extra == {"event": "login", "order_number": "PO-00000001"}
    assert "email" not in ALLOWED_EXTRA_FIELDS
    assert "password" not in ALLOWED_EXTRA_FIELDS


# trace: NFR-SC-06
def test_json_lines_formatter_omits_disallowed_attributes():
    """許可項目以外の属性はログ本文へ出力しない。"""
    record = _record(event="login", email="user@example.com")
    RequestContextFilter().filter(record)

    payload = json.loads(JsonLinesFormatter().format(record))

    assert "email" not in payload
    assert "user@example.com" not in json.dumps(payload, ensure_ascii=False)


# trace: NFR-SC-06
def test_json_lines_formatter_excludes_exception_message():
    """例外情報は種類と発生箇所だけを出力し、例外メッセージを出力しない（LOG-02）。"""
    try:
        raise ValueError("secret-value-123")
    except ValueError:
        import sys

        record = logging.LogRecord(
            "shop.test", logging.ERROR, "module.py", 10, "unhandled_error", None, sys.exc_info()
        )
    RequestContextFilter().filter(record)

    output = JsonLinesFormatter().format(record)
    payload = json.loads(output)

    assert payload["exception_class"] == "ValueError"
    assert "secret-value-123" not in output
    assert payload["stack_trace"]
    assert all(" in " in frame for frame in payload["stack_trace"])


# trace: NFR-OM-01
def test_request_context_filter_injects_request_id_and_user_id():
    """要求ID・利用者IDをログレコードへ注入する。"""
    request_context.set_request_id("req-1")
    request_context.set_user_id(7)
    record = _record()

    assert RequestContextFilter().filter(record) is True
    payload = json.loads(JsonLinesFormatter().format(record))

    assert payload["request_id"] == "req-1"
    assert payload["user_id"] == 7


# trace: NFR-OM-01
def test_request_context_reset_clears_values():
    """要求の終了時に要求コンテキストを初期化する。"""
    request_context.set_request_id("req-1")
    request_context.set_user_id(7)

    request_context.reset()

    assert request_context.get_request_id() is None
    assert request_context.get_user_id() is None


# trace: NFR-OM-01
def test_middleware_generates_request_id_when_not_provided():
    """X-Request-ID が無い場合は新しい要求IDを生成して応答へ返す。"""
    from django.http import HttpResponse

    middleware = RequestLogMiddleware(lambda request: HttpResponse("ok"))
    response = middleware(RequestFactory().get("/items"))

    assert response["X-Request-ID"]
    assert len(response["X-Request-ID"]) == 32


# trace: NFR-OM-01
@pytest.mark.parametrize(
    ("received", "is_accepted"),
    [("abc-123", True), ("A" * 64, True), ("A" * 65, False), ("invalid id", False), ("", False)],
)
def test_middleware_accepts_valid_request_id_only(received, is_accepted):
    """受理する X-Request-ID は英数字とハイフンで64文字以下とする（境界値）。"""
    from django.http import HttpResponse

    middleware = RequestLogMiddleware(lambda request: HttpResponse("ok"))
    request = RequestFactory().get("/items", headers={"x-request-id": received})

    response = middleware(request)

    if is_accepted:
        assert response["X-Request-ID"] == received
    else:
        assert response["X-Request-ID"] != received


# trace: NFR-OM-01
def test_middleware_logs_one_request_log(caplog):
    """要求1件につきリクエストログを1件出力する（方式・パス・状態・処理時間）。"""
    from django.http import HttpResponse

    middleware = RequestLogMiddleware(lambda request: HttpResponse("ok", status=201))

    with caplog.at_level(logging.INFO, logger="shop.access"):
        middleware(RequestFactory().post("/api/items"))

    records = [record for record in caplog.records if record.message == "request"]
    assert len(records) == 1
    assert records[0].method == "POST"
    assert records[0].path == "/api/items"
    assert records[0].status == 201
    assert records[0].duration_ms >= 0


# trace: NFR-OM-01
def test_middleware_resets_context_after_response():
    """応答後に要求コンテキストを初期化する。"""
    from django.http import HttpResponse

    middleware = RequestLogMiddleware(lambda request: HttpResponse("ok"))

    middleware(RequestFactory().get("/"))

    assert request_context.get_request_id() is None
