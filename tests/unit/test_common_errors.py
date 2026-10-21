# trace: FR-001, FR-002, FR-012, FR-021, FR-024, FR-030, FR-031, FR-034, ADDR-011
"""共通エラー仕様（ERR-01〜ERR-08）とエラーコード対応の単体テスト。

期待結果は提供済みAPI契約 6.2（エラーコードとHTTPステータスの対応）および
ADDR-011（エラー応答の単一化、DB整合性例外の業務例外への変換）から導出する。
"""

from __future__ import annotations

import pytest
from common import errors
from common.exceptions import (
    AuthenticationRequired,
    BusinessError,
    CartEmpty,
    CouponAlreadyApplied,
    CouponExpired,
    CouponMinSpendNotMet,
    CouponNotFound,
    CouponNotYetValid,
    EmailAlreadyRegistered,
    InsufficientStock,
    InternalError,
    InvalidCredentials,
    InvalidStatusTransition,
    ItemNotAvailable,
    MiniCommerceError,
    NotFoundError,
    PaymentDeclined,
    PaymentServiceError,
    PermissionDeniedError,
    QuantityLimitExceeded,
    ValidationFailed,
    business_error_for_integrity,
    constraint_name_of,
)
from django.db import IntegrityError

# 提供済みAPI契約 6.2 のエラーコードとHTTPステータスの対応（正本）。
CONTRACT = {
    "VALIDATION_ERROR": 400,
    "EMAIL_ALREADY_REGISTERED": 409,
    "QUANTITY_LIMIT_EXCEEDED": 409,
    "INSUFFICIENT_STOCK": 409,
    "ITEM_NOT_AVAILABLE": 409,
    "CART_EMPTY": 409,
    "COUPON_ALREADY_APPLIED": 409,
    "COUPON_NOT_FOUND": 409,
    "COUPON_NOT_YET_VALID": 409,
    "COUPON_EXPIRED": 409,
    "COUPON_MIN_SPEND_NOT_MET": 409,
    "INVALID_STATUS_TRANSITION": 409,
    "PAYMENT_DECLINED": 409,
    "PERMISSION_DENIED": 403,
    "AUTHENTICATION_REQUIRED": 401,
    "INVALID_CREDENTIALS": 401,
    "NOT_FOUND": 404,
    "PAYMENT_SERVICE_ERROR": 502,
    "INTERNAL_ERROR": 500,
}

EXCEPTION_CODES = [
    (ValidationFailed, "VALIDATION_ERROR"),
    (EmailAlreadyRegistered, "EMAIL_ALREADY_REGISTERED"),
    (QuantityLimitExceeded, "QUANTITY_LIMIT_EXCEEDED"),
    (InsufficientStock, "INSUFFICIENT_STOCK"),
    (ItemNotAvailable, "ITEM_NOT_AVAILABLE"),
    (CartEmpty, "CART_EMPTY"),
    (CouponAlreadyApplied, "COUPON_ALREADY_APPLIED"),
    (CouponNotFound, "COUPON_NOT_FOUND"),
    (CouponNotYetValid, "COUPON_NOT_YET_VALID"),
    (CouponExpired, "COUPON_EXPIRED"),
    (CouponMinSpendNotMet, "COUPON_MIN_SPEND_NOT_MET"),
    (InvalidStatusTransition, "INVALID_STATUS_TRANSITION"),
    (PaymentDeclined, "PAYMENT_DECLINED"),
    (PermissionDeniedError, "PERMISSION_DENIED"),
    (AuthenticationRequired, "AUTHENTICATION_REQUIRED"),
    (InvalidCredentials, "INVALID_CREDENTIALS"),
    (NotFoundError, "NOT_FOUND"),
    (PaymentServiceError, "PAYMENT_SERVICE_ERROR"),
    (InternalError, "INTERNAL_ERROR"),
]


# trace: FR-001
def test_error_status_matches_api_contract_exactly():
    """API契約 6.2 のエラーコードとHTTPステータスが過不足なく一致する。"""
    assert errors.ERROR_STATUS == CONTRACT


# trace: FR-001
def test_every_error_code_has_user_message():
    """全エラーコードに利用者向けの文言がある（内部情報は含めない）。"""
    assert set(errors.ERROR_MESSAGES) == set(CONTRACT)
    assert all(message.strip() for message in errors.ERROR_MESSAGES.values())


# trace: FR-030
@pytest.mark.parametrize(("exception_class", "expected_code"), EXCEPTION_CODES)
def test_exception_classes_carry_contract_code_and_status(exception_class, expected_code):
    """各業務例外はAPI契約のエラーコードとHTTPステータスを持つ。"""
    error = exception_class()

    assert error.code == expected_code
    assert error.status_code == CONTRACT[expected_code]
    assert error.message == errors.ERROR_MESSAGES[expected_code]


# trace: FR-021
def test_business_errors_inherit_business_error_base():
    """ERR-02 業務エラーは業務エラーの基底クラスを継承する。"""
    for exception_class in (
        QuantityLimitExceeded,
        InsufficientStock,
        ItemNotAvailable,
        CartEmpty,
        CouponAlreadyApplied,
        InvalidStatusTransition,
        PaymentDeclined,
    ):
        assert issubclass(exception_class, BusinessError)


# trace: FR-002
def test_authentication_and_credential_errors_are_distinct_types():
    """ERR-04（認証エラー）と ERR-05（認証失敗）は別の型として区別する。"""
    assert not issubclass(InvalidCredentials, AuthenticationRequired)
    assert not issubclass(AuthenticationRequired, InvalidCredentials)


# trace: FR-021
def test_error_keeps_details_and_context():
    """エラーは details（項目別理由）と context（判定に用いた値）を保持する。"""
    error = QuantityLimitExceeded(
        context={"stock_unit_id": 1, "limit": 10, "current_quantity": 8, "requested_quantity": 11}
    )

    assert error.context["limit"] == 10
    assert error.details == []


# trace: FR-012
def test_default_error_has_empty_details_and_context():
    """context を指定しない例外は空の context を返す（API契約 6.3 の「上記以外」）。"""
    error = NotFoundError()

    assert error.details == []
    assert error.context == {}


# trace: FR-001
def test_custom_message_overrides_default_message():
    """個別の文言を指定した場合はその文言を用いる。"""
    error = ValidationFailed("個別の文言", details=[{"field": "email", "reason": "必須です。"}])

    assert error.message == "個別の文言"
    assert error.details[0]["field"] == "email"
    assert error.details[0]["reason"] == "必須です。"


# trace: FR-001
def test_constraint_name_is_read_from_integrity_error_text():
    """制約名を含む整合性例外から制約名を取り出す。"""
    assert constraint_name_of(IntegrityError("duplicate key value violates unique constraint uq_user_email")) == (
        "uq_user_email"
    )


# trace: FR-001
def test_constraint_name_is_read_from_diagnostic_attribute():
    """ドライバの診断情報（diag.constraint_name）から制約名を取り出す。"""

    class Diagnostic:
        constraint_name = "uq_user_email"

    class DriverError(Exception):
        diag = Diagnostic()

    error = IntegrityError("wrapped")
    error.__cause__ = DriverError()

    assert constraint_name_of(error) == "uq_user_email"


# trace: FR-001
def test_unknown_constraint_has_no_business_error():
    """対応表にない制約は業務エラーへ変換しない（システムエラーとして扱う）。"""
    assert constraint_name_of(IntegrityError("violates unique constraint uq_unknown")) is None
    assert business_error_for_integrity(IntegrityError("violates unique constraint uq_unknown")) is None


# trace: FR-001
def test_user_email_constraint_maps_to_email_already_registered():
    """E-001-02：uq_user_email 違反は EMAIL_ALREADY_REGISTERED へ変換する。"""
    converted = business_error_for_integrity(IntegrityError("unique constraint uq_user_email"))

    assert isinstance(converted, EmailAlreadyRegistered)
    assert converted.status_code == 409


# trace: FR-031
def test_base_error_defaults_to_internal_error():
    """分類できない例外は INTERNAL_ERROR（500）とする。"""
    error = MiniCommerceError()

    assert error.code == errors.INTERNAL_ERROR
    assert error.status_code == 500
