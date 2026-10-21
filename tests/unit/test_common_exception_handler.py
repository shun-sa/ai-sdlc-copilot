# trace: FR-001, FR-002, FR-012, FR-021, FR-031, NFR-SC-06, ADDR-011
"""API 共通例外ハンドラ（ADDR-011 4.3 の分岐順）の単体テスト。

期待結果は提供済みAPI契約 6.2、共通エラー仕様（ERR-01〜ERR-08）、
ADDR-011（応答本文の組み立てを1箇所に限定し、内部情報を応答へ含めない）から導出する。
"""

from __future__ import annotations

import pytest
from common.exception_handler import api_exception_handler, error_payload, to_minicommerce_error
from common.exceptions import (
    AuthenticationRequired,
    CartEmpty,
    InvalidCredentials,
    NotFoundError,
    PaymentServiceError,
    PermissionDeniedError,
    ValidationFailed,
)
from django.db import IntegrityError
from django.http import Http404
from rest_framework import exceptions as drf_exceptions


# trace: FR-001
def test_error_payload_contains_only_contract_fields():
    """応答本文は error 封筒だけで構成し、封筒内は code・message・details・context とする。

    提供済みAPI契約 6.2：{"error": {"code", "message", "details": [{"field", "reason"}], "context"}}。
    """
    payload = error_payload(ValidationFailed(details=[{"field": "email", "reason": "必須です。"}]))

    assert set(payload) == {"error"}
    assert set(payload["error"]) == {"code", "message", "details", "context"}
    assert payload["error"]["code"] == "VALIDATION_ERROR"
    assert payload["error"]["details"] == [{"field": "email", "reason": "必須です。"}]
    assert set(payload["error"]["details"][0]) == {"field", "reason"}


# trace: FR-001
def test_error_payload_omits_detail_keys_outside_the_contract():
    """DEF-IT-001 再発防止：details の要素は field・reason だけで構成する。"""
    payload = error_payload(
        ValidationFailed(details=[{"field": "email", "reason": "必須です。", "internal_hint": "users.email"}])
    )

    assert payload["error"]["details"] == [{"field": "email", "reason": "必須です。"}]
    assert "internal_hint" not in payload["error"]["details"][0]


# trace: FR-002
@pytest.mark.parametrize(
    ("exception", "expected_code", "expected_status"),
    [
        (AuthenticationRequired(), "AUTHENTICATION_REQUIRED", 401),
        (InvalidCredentials(), "INVALID_CREDENTIALS", 401),
        (PermissionDeniedError(), "PERMISSION_DENIED", 403),
        (ValidationFailed(), "VALIDATION_ERROR", 400),
        (NotFoundError(), "NOT_FOUND", 404),
        (CartEmpty(), "CART_EMPTY", 409),
        (PaymentServiceError(), "PAYMENT_SERVICE_ERROR", 502),
    ],
)
def test_business_exceptions_keep_their_contract_code(exception, expected_code, expected_status):
    """ADDR-011 4.3：分岐順1-a〜5は例外が持つエラーコードとHTTPステータスで応答する。"""
    response = api_exception_handler(exception)

    assert response.status_code == expected_status
    assert response.data["error"]["code"] == expected_code


# trace: FR-012
def test_http404_is_mapped_to_not_found():
    """フレームワークの Http404 は NOT_FOUND（404）とする。"""
    response = api_exception_handler(Http404())

    assert response.status_code == 404
    assert response.data["error"]["code"] == "NOT_FOUND"


# trace: FR-002
@pytest.mark.parametrize(
    ("exception", "expected_code", "expected_status"),
    [
        (drf_exceptions.NotAuthenticated(), "AUTHENTICATION_REQUIRED", 401),
        (drf_exceptions.AuthenticationFailed(), "AUTHENTICATION_REQUIRED", 401),
        (drf_exceptions.PermissionDenied(), "PERMISSION_DENIED", 403),
        (drf_exceptions.ParseError(), "VALIDATION_ERROR", 400),
        (drf_exceptions.UnsupportedMediaType("text/plain"), "VALIDATION_ERROR", 400),
        (drf_exceptions.NotFound(), "NOT_FOUND", 404),
        (drf_exceptions.MethodNotAllowed("PUT"), "NOT_FOUND", 404),
        (drf_exceptions.NotAcceptable(), "NOT_FOUND", 404),
    ],
)
def test_framework_exceptions_are_mapped_to_contract_codes(exception, expected_code, expected_status):
    """フレームワークの例外も提供済みAPI契約のエラーコードへ写像する。"""
    response = api_exception_handler(exception)

    assert response.status_code == expected_status
    assert response.data["error"]["code"] == expected_code


# trace: FR-021
def test_framework_validation_error_is_reported_as_validation_error():
    """DRF の検証例外は VALIDATION_ERROR（400）として通知する。"""
    converted = to_minicommerce_error(drf_exceptions.ValidationError("不正な入力"))

    assert converted.code == "VALIDATION_ERROR"
    assert converted.details


# trace: FR-001
def test_known_integrity_error_is_converted_to_business_error():
    """DB整合性例外は制約名の対応表で業務エラーへ変換する（分岐順6）。"""
    response = api_exception_handler(IntegrityError("unique constraint uq_user_email"))

    assert response.status_code == 409
    assert response.data["error"]["code"] == "EMAIL_ALREADY_REGISTERED"


# trace: FR-031
def test_unhandled_exception_is_internal_error_without_internal_details():
    """分岐順7：未捕捉例外は INTERNAL_ERROR（500）とし、内部情報を応答へ含めない。"""
    response = api_exception_handler(RuntimeError("内部のスタックトレースや SQL"))

    assert response.status_code == 500
    assert response.data["error"]["code"] == "INTERNAL_ERROR"
    assert "内部のスタックトレースや SQL" not in response.data["error"]["message"]
    assert response.data["error"]["details"] == []
    assert response.data["error"]["context"] == {}


# trace: NFR-SC-06
def test_unknown_integrity_error_is_internal_error_without_constraint_name():
    """対応表にないDB整合性例外はシステムエラーとし、制約名を応答へ含めない。"""
    response = api_exception_handler(IntegrityError("violates unique constraint uq_secret_internal"))

    assert response.status_code == 500
    assert response.data["error"]["code"] == "INTERNAL_ERROR"
    assert "uq_secret_internal" not in response.data["error"]["message"]
