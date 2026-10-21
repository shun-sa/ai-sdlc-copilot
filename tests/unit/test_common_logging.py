# trace: FR-002, FR-030, NFR-SC-06, NFR-OM-11, ADDR-007
"""アクセスログ・エラーログの出力（JSON Lines・機密情報の出力禁止）の単体テスト。

期待結果は NFR-SC-06（パスワード・認証トークン・メールアドレス・氏名・住所・電話番号を
ログへ出力しない、path にクエリ文字列を含めない）、LOG-02（例外は種類と発生箇所のみ）、
ADDR-007（1行1JSON・相関ID）から導出する。
"""

from __future__ import annotations

import json
import logging

import pytest
from common.logging import (
    REQUEST_ID_FIELD,
    JsonLinesFormatter,
    RequestIdFilter,
    current_request_id,
    exception_fields,
    is_json_safe,
    reset_request_id,
    set_request_id,
)


# trace: NFR-SC-06
def build_record(message: str = "request", **extra) -> logging.LogRecord:
    """ログレコードを組み立てる（テスト補助）。"""
    record = logging.LogRecord(
        name="minicommerce.request",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=message,
        args=(),
        exc_info=None,
    )
    for key, value in extra.items():
        setattr(record, key, value)
    return record


# trace: NFR-OM-11
def test_formatter_writes_single_json_line():
    """ADDR-007：1行1JSON（timestamp・level・logger・message）で出力する。"""
    output = JsonLinesFormatter().format(build_record())

    assert "\n" not in output
    payload = json.loads(output)
    assert payload["level"] == "INFO"
    assert payload["logger"] == "minicommerce.request"
    assert payload["message"] == "request"
    assert payload["timestamp"].endswith("+09:00")


# trace: NFR-OM-11
def test_formatter_outputs_access_log_fields():
    """アクセスログの必須項目（method・path・status・user_id・duration_ms）を出力する。"""
    record = build_record(
        request_id="abc", method="GET", path="/api/items", status=200, user_id=7, duration_ms=12
    )

    payload = json.loads(JsonLinesFormatter().format(record))

    assert payload["method"] == "GET"
    assert payload["path"] == "/api/items"
    assert payload["status"] == 200
    assert payload["user_id"] == 7
    assert payload["duration_ms"] == 12
    assert payload["request_id"] == "abc"


# trace: NFR-SC-06
def test_formatter_drops_request_response_sql_and_params():
    """要求・応答オブジェクトと SQL・パラメータ値はログへ出力しない。"""
    record = build_record(
        request="<HttpRequest body with password>",
        response="<HttpResponse>",
        sql="SELECT * FROM users WHERE email = %s",
        params=("user@example.test",),
    )

    payload = json.loads(JsonLinesFormatter().format(record))

    assert "request" not in payload
    assert "response" not in payload
    assert "sql" not in payload
    assert "params" not in payload


# trace: NFR-SC-06
def test_formatter_drops_non_json_values():
    """JSONの基本型以外（オブジェクト）はログへ出力しない。"""

    class Secret:
        def __str__(self) -> str:
            return "user@example.test"

    payload = json.loads(JsonLinesFormatter().format(build_record(user=Secret())))

    assert "user" not in payload


# trace: NFR-SC-06
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, True),
        ("文字列", True),
        (1, True),
        (1.5, True),
        (True, True),
        ([1, "a"], True),
        ({"key": [1, 2]}, True),
        ({1: "a"}, False),
        (object(), False),
        ([object()], False),
    ],
)
def test_is_json_safe_accepts_only_json_primitives(value, expected):
    """JSONの基本型だけで構成された値かを判定する。"""
    assert is_json_safe(value) is expected


# trace: NFR-SC-06
def test_exception_fields_exclude_exception_message():
    """LOG-02：例外は種類と発生箇所だけを出力し、例外メッセージ本文は出力しない。"""
    try:
        raise ValueError("user@example.test のパスワードが不正です")
    except ValueError:
        import sys

        fields = exception_fields(sys.exc_info())

    assert fields["exception_type"] == "builtins.ValueError"
    assert fields["exception_location"]
    serialized = json.dumps(fields, ensure_ascii=False)
    assert "user@example.test" not in serialized


# trace: NFR-SC-06
def test_exception_fields_record_cause_chain_types_only():
    """例外の連鎖は型名だけを記録する。"""
    try:
        try:
            raise KeyError("secret-token")
        except KeyError as cause:
            raise RuntimeError("内部エラー") from cause
    except RuntimeError:
        import sys

        fields = exception_fields(sys.exc_info())

    assert fields["exception_type"] == "builtins.RuntimeError"
    assert "builtins.KeyError" in fields["exception_chain"]
    assert "secret-token" not in json.dumps(fields, ensure_ascii=False)


# trace: NFR-OM-11
def test_exception_fields_is_empty_without_exception():
    """例外がない場合は例外の項目を出力しない。"""
    assert exception_fields((None, None, None)) == {}


# trace: NFR-OM-11
def test_formatter_adds_exception_fields_from_record():
    """例外付きのログレコードには例外の種類・発生箇所を補う。"""
    import sys

    try:
        raise RuntimeError("内部の詳細")
    except RuntimeError:
        record = build_record("request failed")
        record.exc_info = sys.exc_info()

    payload = json.loads(JsonLinesFormatter().format(record))

    assert payload["exception_type"] == "builtins.RuntimeError"
    assert "内部の詳細" not in json.dumps(payload, ensure_ascii=False)


# trace: NFR-OM-11
def test_request_id_is_taken_from_current_context():
    """相関IDは実行文脈から補い、1件の要求の全ログ行へ同じ値を出力する。"""
    token = set_request_id("correlation-1")
    try:
        assert current_request_id() == "correlation-1"
        payload = json.loads(JsonLinesFormatter().format(build_record()))
        assert payload[REQUEST_ID_FIELD] == "correlation-1"
    finally:
        reset_request_id(token)

    assert current_request_id() == ""


# trace: NFR-OM-11
class FakeRequest:
    """相関IDを保持する要求オブジェクトの代用（実通信は行わない。テスト補助）。"""

    def __init__(self, request_id: str | None = None) -> None:
        if request_id is not None:
            self.request_id = request_id


# trace: NFR-OM-11
def test_request_id_filter_keeps_request_id_already_on_the_record():
    """レコードが相関IDを持つ場合はそのまま使う（出力の可否は変えない）。"""
    record = build_record(request_id="from-record", request=FakeRequest("from-request"))

    assert RequestIdFilter().filter(record) is True
    assert getattr(record, REQUEST_ID_FIELD) == "from-record"


# trace: NFR-OM-11
def test_request_id_filter_fills_request_id_from_current_context():
    """実行文脈に相関IDがある場合はその値を補う（ADDR-007 DD-003）。"""
    record = build_record()
    token = set_request_id("correlation-2")
    try:
        assert RequestIdFilter().filter(record) is True
    finally:
        reset_request_id(token)

    assert getattr(record, REQUEST_ID_FIELD) == "correlation-2"


# trace: NFR-OM-11
def test_request_id_filter_fills_request_id_from_record_request_without_context():
    """実行文脈を抜けた後のログ行（4xx/5xx）は、要求オブジェクトの相関IDで補う（ADDR-007 INV-003）。

    要求オブジェクト自体はログへ出力しない（NFR-SC-06）。
    """
    record = build_record(request=FakeRequest("from-request"))

    assert RequestIdFilter().filter(record) is True
    assert getattr(record, REQUEST_ID_FIELD) == "from-request"
    payload = json.loads(JsonLinesFormatter().format(record))
    assert payload[REQUEST_ID_FIELD] == "from-request"
    assert "request" not in payload


# trace: NFR-OM-11
@pytest.mark.parametrize("request_object", [None, FakeRequest(), FakeRequest("")])
def test_request_id_filter_adds_no_request_id_without_any_source(request_object):
    """実行文脈にも要求オブジェクトにも相関IDがない場合は request_id を付けない。"""
    record = build_record() if request_object is None else build_record(request=request_object)

    assert RequestIdFilter().filter(record) is True
    assert not hasattr(record, REQUEST_ID_FIELD)
    assert REQUEST_ID_FIELD not in json.loads(JsonLinesFormatter().format(record))
