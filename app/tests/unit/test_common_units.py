# trace: NFR-SC-04, NFR-SC-06, NFR-SC-07, NFR-SC-10, NFR-EN-04, FR-011, FR-030, ADDR-001, ADDR-012, ADDR-013, ADDR-014
"""共通部品（入力の正規化・型判定、一覧の分割表示、エラー封筒、ログ、設定の読取り、表示フィルタ）の単体テスト。

期待値の根拠：NFR-SC-04（全外部入力の型・桁数・値域・形式の検証）、NFR-SC-06（ログへの機密情報出力禁止）、
NFR-SC-10（内部情報の非表示）、CMN-15/18/35（FR-011 等の共通方針）、ADDR-001 4.3 の6〜8・DD-005、ADDR-013、ADDR-014。
DB を使わない（DB Test Strategy：NOT_APPLICABLE）。
"""

import json
import logging
from datetime import UTC, date, datetime, timedelta

import pytest
from django.core.exceptions import ImproperlyConfigured, SuspiciousOperation
from rest_framework import exceptions as drf_exceptions

from common import api, codes, errors, normalize, paging
from common import logging as mc_logging
from common.templatetags import mc_format
from config import env
from tests.unit.conftest import jst

# ---------------------------------------------------------------------------
# 入力の正規化・型判定（NFR-SC-04、CMN-15、CMN-18）
# ---------------------------------------------------------------------------


# trace: NFR-SC-04
@pytest.mark.parametrize(
    ("raw", "expected"),
    [(" a ", "a"), ("\u3000全角\u3000", "全角"), ("\t改行\r\n", "改行"), ("内 部", "内 部"), (5, 5), (None, None)],
)
def test_strip_text_removes_only_leading_and_trailing_whitespace(raw, expected):
    """CMN-15：半角・全角スペース・タブ・改行を前後から除去し、内部は残す。文字列以外はそのまま。"""
    assert normalize.strip_text(raw) == expected


# trace: NFR-SC-04
@pytest.mark.parametrize(("raw", "blank"), [(None, True), ("", True), (" \u3000\t", True), ("a", False), (0, False)])
def test_is_blank(raw, blank):
    assert normalize.is_blank(raw) is blank


# trace: NFR-SC-04
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (1, 1),
        ("10", 10),
        (" 7 ", 7),
        ("-3", -3),
        ("007", 7),
        ("1.5", None),
        (1.0, None),
        (True, None),
        ("abc", None),
        ("１", None),
        ("1\n", 1),
        ("", None),
        (None, None),
        ([1], None),
    ],
)
def test_parse_int_accepts_only_integers(raw, expected):
    assert normalize.parse_int(raw) == expected


# trace: NFR-SC-04
def test_parse_int_maps_out_of_64bit_range_to_sentinels_without_exception():
    """桁数を判定してから変換し、範囲外は範囲外の値として返す（値域判定で必ず範囲外になる）。"""
    huge = "9" * 400
    assert normalize.parse_int(huge) == normalize.INT_ABOVE_RANGE
    assert normalize.parse_int("-" + huge) == normalize.INT_BELOW_RANGE
    assert normalize.parse_int(2**70) == normalize.INT_ABOVE_RANGE
    assert normalize.parse_int(-(2**70)) == normalize.INT_BELOW_RANGE
    assert normalize.parse_int("9223372036854775807") == 9223372036854775807
    assert normalize.parse_int("9223372036854775808") == normalize.INT_ABOVE_RANGE


# trace: NFR-SC-04
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1", 1),
        (5, 5),
        ("0", None),
        (0, None),
        ("-1", None),
        ("abc", None),
        ("1.0", None),
        (" 1", None),
        ("１２", None),
        (True, None),
        (None, None),
        ("9223372036854775807", 9223372036854775807),
        ("9223372036854775808", None),
        ("9" * 100, None),
    ],
)
def test_parse_identifier_returns_none_for_uninterpretable_values(raw, expected):
    """CMN-18：識別子として解釈できない値は対象なし（None）として扱う。"""
    assert normalize.parse_identifier(raw) == expected


# trace: NFR-SC-04
@pytest.mark.parametrize(
    ("raw", "expected"),
    [("123", True), ("12a", False), ("１２", False), ("", False), (12, False)],
)
def test_is_ascii_digits(raw, expected):
    assert normalize.is_ascii_digits(raw) is expected


# trace: NFR-SC-04
@pytest.mark.parametrize(
    ("raw", "unstorable", "surrogate"),
    [
        ("abc", False, False),
        ("a\x00b", True, False),
        ("a\ud800", True, True),
        (5, False, False),
        ("日本語", False, False),
    ],
)
def test_unstorable_and_surrogate_detection(raw, unstorable, surrogate):
    """データベースが受理しない文字（NUL・対になっていないサロゲート）を検出する。"""
    assert normalize.has_unstorable_chars(raw) is unstorable
    assert normalize.has_surrogates(raw) is surrogate


# trace: NFR-SC-04
def test_unstorable_message_names_the_field():
    assert "氏名" in normalize.unstorable_message("氏名")
    assert normalize.text_length("日本語") == 3


# ---------------------------------------------------------------------------
# 一覧の分割表示（CMN-35、NFR-PF-08、ADDR-001 4.3 の8）
# ---------------------------------------------------------------------------


# trace: FR-011, ADDR-001
@pytest.mark.parametrize(
    ("raw", "page", "reason"),
    [
        (None, 1, None),
        ("", 1, None),
        ("1", 1, None),
        ("3", 3, None),
        ("0", 1, "out_of_range"),
        ("-1", 1, "out_of_range"),
        ("abc", 1, "invalid_type"),
        ("1.5", 1, "invalid_type"),
    ],
)
def test_parse_page_validates_positive_integer(raw, page, reason):
    collected = errors.FieldErrors()
    assert paging.parse_page(raw, collected) == page
    if reason is None:
        assert not collected
    else:
        assert [(f.field, f.reason) for f in collected.items] == [("page", reason)]


# trace: FR-011, ADDR-001
@pytest.mark.parametrize(
    ("total", "size", "pages"), [(0, 20, 0), (1, 20, 1), (20, 20, 1), (21, 20, 2), (40, 20, 2), (41, 20, 3)]
)
def test_build_page_total_pages_is_ceiling_and_zero_for_empty(total, size, pages):
    info = paging.build_page(1, size, total)
    assert info.total_pages == pages
    assert info.as_dict() == {"page": 1, "page_size": size, "total_count": total, "total_pages": pages}


# trace: FR-011, ADDR-001
def test_build_page_caps_page_size_at_50():
    """NFR-PF-08：1回の応答の件数は50件以下。"""
    assert paging.build_page(1, 500, 10).page_size == 50


# trace: FR-011, ADDR-001
def test_slice_queryset_returns_requested_page_and_empty_beyond_total():
    items = list(range(45))
    info = paging.build_page(2, 20, len(items))
    assert paging.slice_queryset(items, info) == list(range(20, 40))
    assert info.offset == 20 and info.first_index == 21 and info.last_index(20) == 40
    beyond = paging.build_page(4, 20, len(items))
    assert beyond.is_beyond
    assert paging.slice_queryset(items, beyond) == []


# ---------------------------------------------------------------------------
# 業務例外と共通エラー封筒（ADDR-001 4.3 の6・7、DD-002、DD-010）
# ---------------------------------------------------------------------------


# trace: NFR-SC-10, ADDR-001
@pytest.mark.parametrize(
    ("cls", "error_type", "status"),
    [
        (errors.InputError, "input_error", 400),
        (errors.BusinessError, "business_error", 422),
        (errors.PermissionDeniedError, "permission_denied", 403),
        (errors.AuthenticationRequiredError, "authentication_required", 401),
        (errors.AuthenticationFailedError, "authentication_failed", 401),
        (errors.NotFoundError, "not_found", 404),
        (errors.IntegrationError, "integration_error", 502),
        (errors.SystemFailureError, "system_error", 500),
    ],
)
def test_error_types_map_to_http_status(cls, error_type, status):
    """ERR-01〜ERR-08 と HTTP ステータスの対応（ADDR-001 4.3 の7）。"""
    exc = cls("E-000-00", "msg")
    assert exc.error_type == error_type
    assert exc.http_status == status
    response = api.service_error_response(exc)
    assert response.status_code == status
    body = response.data["error"]
    assert set(body) == {"type", "reason", "message", "fields", "values"}
    assert body["type"] == error_type
    if status == 401:
        assert response["WWW-Authenticate"] == 'Bearer realm="api"'


# trace: NFR-SC-10, ADDR-001
def test_business_error_envelope_has_reason_and_values_but_other_types_do_not():
    business = errors.BusinessError("E-1", "m", reason="cart_empty", values={"subtotal": 1})
    body = api.service_error_response(business).data["error"]
    assert body["reason"] == "cart_empty" and body["values"] == {"subtotal": 1}
    other = errors.NotFoundError("E-2", "m", reason="x", values={"secret": 1})
    body = api.service_error_response(other).data["error"]
    assert body["reason"] is None and body["values"] == {}


# trace: NFR-SC-10, ADDR-001
def test_field_errors_are_collected_and_raised_once():
    """CMN-16：入力エラーは全項目分をまとめて1回で通知する。"""
    collected = errors.FieldErrors()
    collected.raise_if_any("E-1")  # 誤りなしは何もしない
    collected.add("a", "required", "A")
    collected.add("b", "invalid_type", "B")
    assert collected.has("a") and not collected.has("c")
    with pytest.raises(errors.InputError) as info:
        collected.raise_if_any("E-1")
    assert [(f.field, f.reason) for f in info.value.fields] == [("a", "required"), ("b", "invalid_type")]


# trace: NFR-SC-10, ADDR-001
def test_to_record_and_from_record_round_trip_without_input_values():
    exc = errors.BusinessError(
        "E-021-05", "msg", reason="quantity_limit_exceeded", fields=[errors.FieldError("q", "r", "m")], values={"x": 1}
    )
    record = exc.to_record()
    assert record["status"] == "error" and record["type"] == "business_error"
    restored = errors.from_record(record)
    assert isinstance(restored, errors.BusinessError)
    assert (restored.code, restored.reason, restored.values) == ("E-021-05", "quantity_limit_exceeded", {"x": 1})
    assert restored.fields[0].field == "q"


# trace: NFR-SC-10, ADDR-001
def test_from_record_with_unknown_type_becomes_system_error():
    restored = errors.from_record({"status": "error", "type": "nope"})
    assert isinstance(restored, errors.SystemFailureError)
    assert restored.message == errors.MSG_SYSTEM_ERROR


# trace: NFR-SC-10, ADDR-001
def test_is_request_parse_error_recognizes_request_level_errors():
    assert errors.is_request_parse_error(SuspiciousOperation("x"))
    marked = ValueError("x")
    setattr(marked, errors.REQUEST_PARSE_ERROR_ATTR, True)
    assert errors.is_request_parse_error(marked)
    assert not errors.is_request_parse_error(ValueError("x"))


# trace: NFR-SC-10, ADDR-001, ADDR-013
@pytest.mark.parametrize(
    ("exc", "status", "error_type"),
    [
        (drf_exceptions.NotAuthenticated(), 401, "authentication_required"),
        (drf_exceptions.AuthenticationFailed(), 401, "authentication_required"),
        (drf_exceptions.PermissionDenied(), 403, "permission_denied"),
        (drf_exceptions.NotFound(), 404, "not_found"),
        (drf_exceptions.MethodNotAllowed("OPTIONS"), 405, "not_found"),
        (drf_exceptions.ParseError(), 400, "input_error"),
        (drf_exceptions.UnsupportedMediaType("text/plain"), 400, "input_error"),
        (SuspiciousOperation("bad host"), 400, "input_error"),
        (drf_exceptions.Throttled(), 400, "input_error"),
    ],
)
def test_exception_handler_converts_framework_errors_to_envelope(exc, status, error_type):
    response = api.exception_handler(exc, {})
    assert response.status_code == status
    assert response.data["error"]["type"] == error_type


# trace: NFR-SC-10, ADDR-001, ADDR-013
def test_exception_handler_hides_internal_details_of_unexpected_errors(app_logs):
    """NFR-SC-10：想定外の例外は system_error の利用者向け文言だけを返し、例外の文言・SQL を含めない。"""
    secret = "SELECT * FROM accounts_user -- /srv/app/secret.py"
    response = api.exception_handler(RuntimeError(secret), {})
    assert response.status_code == 500
    rendered = json.dumps(response.data, ensure_ascii=False)
    assert secret not in rendered and "RuntimeError" not in rendered
    assert response.data["error"]["message"] == errors.MSG_SYSTEM_ERROR
    log = [r for r in app_logs.records() if r["log_type"] == "LOG-02"]
    assert log and log[-1]["error_type"] == "system_error"
    assert secret not in json.dumps(log, ensure_ascii=False)


# trace: NFR-SC-10, ADDR-001, ADDR-013
def test_exception_handler_logs_service_system_error_only(app_logs):
    api.exception_handler(errors.system_failure("E-1"), {})
    api.exception_handler(errors.BusinessError("E-2", "m"), {})
    assert [r["error_type"] for r in app_logs.records() if r["log_type"] == "LOG-02"] == ["system_error"]


# trace: NFR-EN-04, ADDR-001
def test_to_json_value_formats_datetime_with_jst_offset_seconds_and_dates():
    """ADDR-001 DD-005：日時は +09:00 付き ISO 8601 秒単位、日付は YYYY-MM-DD。"""
    moment = datetime(2027, 4, 1, 1, 0, 0, 123456, tzinfo=UTC)
    value = api.to_json_value({"a": [moment, date(2027, 4, 1)], "b": (1, None)})
    assert value == {"a": ["2027-04-01T10:00:00+09:00", "2027-04-01"], "b": [1, None]}


# trace: NFR-SC-10, ADDR-001
def test_api_error_response_and_not_found_response_use_envelope():
    response = api.api_not_found_response()
    assert response.status_code == 404
    assert json.loads(response.content)["error"]["type"] == "not_found"
    response = api.api_error_response("input_error", "m", 400)
    assert json.loads(response.content)["error"] == {
        "type": "input_error",
        "reason": None,
        "message": "m",
        "fields": [],
        "values": {},
    }


# ---------------------------------------------------------------------------
# ログ（ADDR-013：許可リストの項目だけ。NFR-SC-06：機密情報を出力しない）
# ---------------------------------------------------------------------------


# trace: NFR-SC-06, ADDR-013
def test_json_formatter_outputs_only_allowlisted_fields():
    formatter = mc_logging.JsonFormatter()
    record = logging.LogRecord("minicommerce", logging.INFO, __file__, 1, "msg", None, None)
    record.mc_log_type = "LOG-01"
    record.mc_fields = {"operation": "op", "result": "success", "event": "end", "user_id": 3, "email": "a@b.c"}
    payload = json.loads(formatter.format(record))
    assert set(payload) == {"timestamp", "level", "log_type", "request_id", "operation", "result", "event", "user_id"}
    assert "a@b.c" not in json.dumps(payload)
    assert payload["timestamp"].endswith("+09:00")


# trace: NFR-SC-06, ADDR-013
def test_json_formatter_suppresses_foreign_logger_messages():
    formatter = mc_logging.JsonFormatter()
    record = logging.LogRecord("other", logging.ERROR, __file__, 1, "password=secret", None, None)
    payload = json.loads(formatter.format(record))
    assert payload["log_type"] == "LOG-02"
    assert payload["result"] == "suppressed"
    assert "secret" not in json.dumps(payload)


# trace: NFR-SC-06, ADDR-013
def test_log_error_outputs_exception_class_and_location_but_not_message(app_logs):
    try:
        raise ValueError("pii: taro@example.test")
    except ValueError as exc:
        wrapped = errors.system_failure("E-1")
        wrapped.__cause__ = exc
        mc_logging.log_error("system_error", wrapped, 9)
    record = app_logs.records()[-1]
    assert record["exception_class"] == "builtins.ValueError"
    assert record["location"].startswith("tests.unit.test_common_units:")
    assert "taro@example.test" not in json.dumps(record)


# trace: NFR-SC-06, ADDR-013
def test_operation_log_records_start_and_end_results(app_logs):
    with mc_logging.operation_log("FR-x op", 1):
        pass
    with pytest.raises(errors.BusinessError):
        with mc_logging.operation_log("FR-x op", 1):
            raise errors.BusinessError("E", "m", reason="cart_empty")
    with pytest.raises(RuntimeError):
        with mc_logging.operation_log("FR-x op", 1):
            raise RuntimeError("boom")
    with pytest.raises(SuspiciousOperation):
        with mc_logging.operation_log("FR-x op", 1):
            raise SuspiciousOperation("bad")
    ends = [r["result"] for r in app_logs.records() if r.get("event") == "end"]
    assert ends == ["success", "business_error:cart_empty", "system_error", "input_error"]


# trace: NFR-SC-06, ADDR-013
def test_request_scope_sets_request_id_for_log_lines(app_logs):
    with mc_logging.request_scope("rid-1"):
        mc_logging.log_access("GET", "/api/products/", 200, None, 5)
        mc_logging.log_job("success", {"users": 1}, [])
        mc_logging.log_integration("request", "PO-00000001", 100, "JPY")
    assert mc_logging.current_request_id() is None
    records = app_logs.records()
    assert {r["request_id"] for r in records} == {"rid-1"}
    assert [r["log_type"] for r in records] == ["LOG-03", "LOG-05", "LOG-06"]
    assert records[0]["path"] == "/api/products/"


# trace: NFR-SC-10, ADDR-013
def test_exception_location_without_traceback_is_unknown():
    assert mc_logging.exception_location(ValueError()) == "unknown"
    assert len(mc_logging.new_request_id()) == 36


# ---------------------------------------------------------------------------
# 設定値の読取り（ADDR-014 DD-002・DD-011：fail-closed）
# ---------------------------------------------------------------------------


# trace: NFR-SC-10, ADDR-014
@pytest.mark.parametrize(("value", "expected"), [(None, False), ("true", True), ("false", False)])
def test_read_bool_accepts_only_lowercase_true_false(monkeypatch, value, expected):
    if value is None:
        monkeypatch.delenv("MC_FLAG", raising=False)
    else:
        monkeypatch.setenv("MC_FLAG", value)
    assert env.read_bool("MC_FLAG") is expected


# trace: NFR-SC-10, ADDR-014
@pytest.mark.parametrize("value", ["True", "1", "yes", "", " true"])
def test_read_bool_rejects_other_notations(monkeypatch, value):
    monkeypatch.setenv("MC_FLAG", value)
    with pytest.raises(ImproperlyConfigured):
        env.read_bool("MC_FLAG")


# trace: NFR-SC-10, ADDR-014
def test_read_environment_name_is_fail_closed(monkeypatch):
    monkeypatch.setenv("MINICOMMERCE_ENV", "production")
    assert env.read_environment_name() == "production"
    monkeypatch.setenv("MINICOMMERCE_ENV", "staging")
    with pytest.raises(ImproperlyConfigured):
        env.read_environment_name()
    monkeypatch.delenv("MINICOMMERCE_ENV")
    with pytest.raises(ImproperlyConfigured):
        env.read_environment_name()


# trace: NFR-SC-07, ADDR-014
def test_read_required_optional_list_and_proxy_header(monkeypatch):
    monkeypatch.delenv("MC_X", raising=False)
    with pytest.raises(ImproperlyConfigured):
        env.read_required("MC_X")
    monkeypatch.setenv("MC_X", "")
    with pytest.raises(ImproperlyConfigured):
        env.read_required("MC_X")
    assert env.read_optional("MC_X", "dflt") == "dflt"
    assert env.read_list("MC_X", ["a"]) == ["a"]
    monkeypatch.setenv("MC_X", "v")
    assert env.read_required("MC_X") == "v" and env.read_optional("MC_X", "d") == "v"
    monkeypatch.setenv("MC_X", " a , ,b ")
    assert env.read_list("MC_X", []) == ["a", "b"]
    monkeypatch.setenv("MC_P", "X-Forwarded-Proto=https")
    assert env.read_proxy_ssl_header("MC_P") == ("HTTP_X_FORWARDED_PROTO", "https")
    for bad in ("noequal", "=https", "X-H="):
        monkeypatch.setenv("MC_P", bad)
        with pytest.raises(ImproperlyConfigured):
            env.read_proxy_ssl_header("MC_P")
    monkeypatch.delenv("MC_P")
    assert env.read_proxy_ssl_header("MC_P") is None


# ---------------------------------------------------------------------------
# 表示フィルタ（UI-23〜UI-33）とコード値
# ---------------------------------------------------------------------------


# trace: FR-011, ADDR-012
def test_display_filters_format_values():
    assert mc_format.yen(1234567) == "1,234,567円" and mc_format.yen(None) == "－"
    assert mc_format.number(1000) == "1,000" and mc_format.number(None) == "－"
    assert mc_format.jst(datetime(2027, 4, 1, 1, 2, 3, tzinfo=UTC)) == "2027/04/01 10:02"
    assert mc_format.jst("x") == "－"
    assert mc_format.dash("") == "－" and mc_format.dash(None) == "－" and mc_format.dash("a") == "a"
    assert mc_format.postal("1234567") == "123-4567" and mc_format.postal("") == "－" and mc_format.postal("12") == "12"
    assert mc_format.prefecture_name("13") == "東京都" and mc_format.prefecture_name("99") == "－"
    assert mc_format.price_pair(1000) == "1,100円（税込）／1,000円（税抜）" and mc_format.price_pair(None) == "－"
    assert mc_format.discount_text({"discount_type": "percentage", "discount_value": 10}) == "10%引き"
    assert mc_format.discount_text({"discount_type": "fixed_amount", "discount_value": 1000}) == "1,000円引き"
    assert mc_format.discount_text(None) == "－"
    assert mc_format.get_item({"a": 1}, "a") == 1 and mc_format.get_item([], "a") is None
    assert mc_format.reason_label("expired") == "有効期間が終了しています" and mc_format.reason_label("x") == "－"


# trace: FR-030, ADDR-012
def test_prefecture_codes_cover_47_prefectures():
    assert len(codes.PREFECTURES) == 47
    assert codes.PREFECTURES[0] == ("01", "北海道") and codes.PREFECTURES[-1] == ("47", "沖縄県")


# trace: NFR-EN-04, ADDR-012
def test_clock_helpers_format_and_truncate():
    from common import clock

    moment = jst(2027, 4, 30, 23, 59, 59) + timedelta(microseconds=900000)
    assert clock.truncate_seconds(moment) == jst(2027, 4, 30, 23, 59, 59)
    assert clock.format_display(moment) == "2027/04/30 23:59"
    assert clock.format_display(None) == "－"
    assert clock.to_jst(None) is None
