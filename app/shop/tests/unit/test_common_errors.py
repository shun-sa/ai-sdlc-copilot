# trace: FR-001, FR-024, NFR-SC-04, NFR-SC-06, ADDR-007
"""共通エラー仕様（ERR-01〜ERR-08、api-contract 6.2・6.3）の単体テスト。

期待値は共通機能要件のエラー種別・エラーコードとHTTPステータスの対応表から導出する。
"""
import pytest
from django.http import Http404
from rest_framework.exceptions import ValidationError as DrfValidationError

from shop.common import errors
from shop.common.exception_handler import api_exception_handler
from shop.common.validators import ErrorCollector, normalize_coupon_code, normalize_email, parse_int, strip_value


# trace: NFR-SC-06
@pytest.mark.parametrize(
    ("error_class", "code", "status"),
    [
        (errors.ValidationError, "VALIDATION_ERROR", 400),
        (errors.EmailAlreadyRegisteredError, "EMAIL_ALREADY_REGISTERED", 409),
        (errors.QuantityLimitExceededError, "QUANTITY_LIMIT_EXCEEDED", 409),
        (errors.InsufficientStockError, "INSUFFICIENT_STOCK", 409),
        (errors.ItemNotAvailableError, "ITEM_NOT_AVAILABLE", 409),
        (errors.CartEmptyError, "CART_EMPTY", 409),
        (errors.CouponAlreadyAppliedError, "COUPON_ALREADY_APPLIED", 409),
        (errors.CouponNotFoundError, "COUPON_NOT_FOUND", 409),
        (errors.CouponNotYetValidError, "COUPON_NOT_YET_VALID", 409),
        (errors.CouponExpiredError, "COUPON_EXPIRED", 409),
        (errors.CouponMinSpendNotMetError, "COUPON_MIN_SPEND_NOT_MET", 409),
        (errors.InvalidStatusTransitionError, "INVALID_STATUS_TRANSITION", 409),
        (errors.PaymentDeclinedError, "PAYMENT_DECLINED", 409),
        (errors.PermissionDeniedError, "PERMISSION_DENIED", 403),
        (errors.AuthenticationRequiredError, "AUTHENTICATION_REQUIRED", 401),
        (errors.InvalidCredentialsError, "INVALID_CREDENTIALS", 401),
        (errors.NotFoundError, "NOT_FOUND", 404),
        (errors.PaymentServiceError, "PAYMENT_SERVICE_ERROR", 502),
        (errors.InternalError, "INTERNAL_ERROR", 500),
    ],
)
def test_error_code_and_http_status(error_class, code, status):
    """各業務エラーのエラーコードとHTTPステータスが対応表と一致する。"""
    error = error_class()

    assert error.code == code
    assert error.http_status == status
    assert error.message != ""


# trace: NFR-SC-06
def test_error_payload_structure():
    """エラー応答本文は code・message・details・context を持つ。"""
    error = errors.ValidationError(details=[{"field": "email", "reason": "必須です。"}], context={"key": "value"})

    payload = error.to_payload()

    assert payload == {
        "error": {
            "code": "VALIDATION_ERROR",
            "message": error.message,
            "details": [{"field": "email", "reason": "必須です。"}],
            "context": {"key": "value"},
        }
    }


# trace: NFR-SC-06
def test_error_message_can_be_overridden():
    """業務エラーのメッセージは個別に差し替えできる（既定値を持つ）。"""
    assert errors.NotFoundError(message="指定した注文が見つかりません。").message == "指定した注文が見つかりません。"
    assert errors.NotFoundError().message == "指定した対象が見つかりません。"


# trace: NFR-SC-06
def test_exception_handler_converts_app_error():
    """業務例外は対応するHTTPステータスと共通形式の応答へ変換する。"""
    response = api_exception_handler(errors.CartEmptyError(), {})

    assert response.status_code == 409
    assert response.data["error"]["code"] == "CART_EMPTY"


# trace: NFR-SC-06
def test_exception_handler_converts_drf_validation_error():
    """DRF の検証エラーは入力エラー（details つき）へ変換する。"""
    response = api_exception_handler(DrfValidationError({"email": ["必須です。"]}), {})

    assert response.status_code == 400
    assert response.data["error"]["code"] == "VALIDATION_ERROR"
    assert {"field": "email", "reason": "必須です。"} in response.data["error"]["details"]


# trace: NFR-SC-06
def test_exception_handler_converts_http404():
    """Http404 は対象なし（404）へ変換する。"""
    response = api_exception_handler(Http404(), {})

    assert response.status_code == 404
    assert response.data["error"]["code"] == "NOT_FOUND"


# trace: NFR-SC-06
def test_exception_handler_hides_internal_details():
    """未捕捉の例外はシステムエラーへ変換し、内部情報を応答に含めない（UI-34）。"""
    response = api_exception_handler(RuntimeError("DB connection failed at 10.0.0.1"), {})

    assert response.status_code == 500
    assert response.data["error"]["code"] == "INTERNAL_ERROR"
    assert "10.0.0.1" not in response.data["error"]["message"]
    assert response.data["error"]["details"] == []


# trace: NFR-SC-06
def test_exception_handler_deduplicates_details():
    """同一の項目・理由の組は details に重複して出力しない。"""
    response = api_exception_handler(DrfValidationError(["不正です。", "不正です。"]), {})

    assert len(response.data["error"]["details"]) == 1


# trace: NFR-SC-04
@pytest.mark.parametrize(
    ("value", "expected"),
    [("  abc  ", "abc"), ("\t\r\nabc\n", "abc"), ("　全角　", "全角"), (None, ""), (123, "123"), ("", "")],
)
def test_strip_value(value, expected):
    """前後の空白（半角・全角・タブ・改行）を除去する（CMN-15）。"""
    assert strip_value(value) == expected


# trace: NFR-SC-04
@pytest.mark.parametrize(
    ("value", "expected"),
    [("10", 10), (" 10 ", 10), (10, 10), ("abc", None), ("", None), (None, None), (True, None), ("1.5", None)],
)
def test_parse_int(value, expected):
    """整数として解釈できる場合のみ整数を返す（真偽値は整数として扱わない）。"""
    assert parse_int(value) == expected


# trace: FR-001
def test_normalize_email():
    """メールアドレスは前後空白除去・英小文字化で正規化する。"""
    assert normalize_email("  USER@Example.COM ") == "user@example.com"
    assert normalize_email(None) == ""


# trace: FR-024
def test_normalize_coupon_code():
    """クーポンコードは前後空白除去・英大文字化で正規化する。"""
    assert normalize_coupon_code("  save500 ") == "SAVE500"
    assert normalize_coupon_code(None) == ""


# trace: NFR-SC-04
def test_error_collector_collects_all_details():
    """入力エラーは不備のある全項目を1回で通知する（CMN-16）。"""
    collector = ErrorCollector()

    assert collector.has_error is False
    collector.raise_if_error()

    collector.add("email", "必須です。")
    collector.add("password", "8文字以上です。")

    assert collector.has_error is True
    with pytest.raises(errors.ValidationError) as exc:
        collector.raise_if_error()
    assert [detail["field"] for detail in exc.value.details] == ["email", "password"]
