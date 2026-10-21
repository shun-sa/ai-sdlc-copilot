# trace: ADDR-011
"""DRF の例外ハンドラ差し替え。

分岐順（ADDR-011 4.3）：
1-a 認証情報の不在・無効・期限切れ → AUTHENTICATION_REQUIRED（401）
1-b 資格情報の照合失敗 → INVALID_CREDENTIALS（401）
2 権限 → PERMISSION_DENIED（403）
3 検証 → VALIDATION_ERROR（400）
4 対象なし → NOT_FOUND（404）
5 業務例外 → 例外が持つエラーコードとHTTPステータス
6 DB整合性例外 → 制約名の対応表で業務例外へ変換
7 未捕捉例外 → INTERNAL_ERROR（500、内部情報は応答へ含めない）
"""

from __future__ import annotations

import logging

from django.db import IntegrityError
from django.http import Http404
from rest_framework import exceptions as drf_exceptions
from rest_framework.response import Response

from common import errors
from common.exceptions import (
    AuthenticationRequired,
    BusinessError,
    InvalidCredentials,
    MiniCommerceError,
    NotFoundError,
    PermissionDeniedError,
    ValidationFailed,
    business_error_for_integrity,
    constraint_name_of,
)

logger = logging.getLogger("minicommerce.error")


def error_detail_payload(detail: dict[str, str]) -> dict[str, str]:
    """項目別の入力エラーを `field` / `reason` の形へ整える（提供済みAPI契約 6.2）。"""
    return {"field": detail.get("field", ""), "reason": detail.get("reason", "")}


def error_payload(error: MiniCommerceError) -> dict[str, object]:
    """利用者へ返すエラー本文を組み立てる（内部情報は含めない）。

    形式は提供済みAPI契約 6.2 の `error` 封筒に合わせる。
    `details` は該当なしの場合に空配列、`context` は該当なしの場合に空オブジェクト。
    """
    return {
        "error": {
            "code": error.code,
            "message": error.message,
            "details": [error_detail_payload(detail) for detail in error.details],
            "context": error.context or {},
        }
    }


def from_framework_exception(exc: Exception) -> MiniCommerceError | None:
    """フレームワークが送出する例外を、提供済みAPI契約のエラーコードへ写像する。"""
    if isinstance(exc, drf_exceptions.NotAuthenticated | drf_exceptions.AuthenticationFailed):
        return AuthenticationRequired()
    if isinstance(exc, drf_exceptions.PermissionDenied):
        return PermissionDeniedError()
    if isinstance(exc, drf_exceptions.ValidationError):
        return ValidationFailed(details=[{"field": "", "reason": str(exc.detail)}])
    if isinstance(exc, drf_exceptions.ParseError | drf_exceptions.UnsupportedMediaType):
        return ValidationFailed(details=[{"field": "", "reason": "要求本文を JSON として解釈できません。"}])
    if isinstance(exc, drf_exceptions.NotFound | drf_exceptions.MethodNotAllowed | drf_exceptions.NotAcceptable):
        return NotFoundError()
    return None


def to_minicommerce_error(exc: Exception) -> MiniCommerceError:
    """送出された例外を、分岐順に従って利用者向けの例外へ写像する。"""
    if isinstance(exc, AuthenticationRequired):
        return exc
    if isinstance(exc, InvalidCredentials):
        return exc
    if isinstance(exc, PermissionDeniedError):
        return exc
    if isinstance(exc, ValidationFailed):
        return exc
    if isinstance(exc, NotFoundError):
        return exc
    if isinstance(exc, Http404):
        return NotFoundError()
    if isinstance(exc, BusinessError):
        return exc
    if isinstance(exc, MiniCommerceError):
        return exc
    converted_framework_error = from_framework_exception(exc)
    if converted_framework_error is not None:
        return converted_framework_error
    if isinstance(exc, IntegrityError):
        converted = business_error_for_integrity(exc)
        if converted is not None:
            logger.warning(
                "integrity error converted to business error",
                extra={"constraint": constraint_name_of(exc), "error_code": converted.code},
            )
            return converted
    logger.exception("unhandled exception", extra={"error_code": errors.INTERNAL_ERROR})
    return MiniCommerceError()


def api_exception_handler(exc: Exception, context: dict | None = None) -> Response:
    """DRF の EXCEPTION_HANDLER として使う共通ハンドラ。"""
    error = to_minicommerce_error(exc)
    return Response(error_payload(error), status=error.status_code)
