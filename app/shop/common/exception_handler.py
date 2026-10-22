# trace: ADDR-005, ADDR-007
"""Web API の単一例外ハンドラ。すべての例外を共通のエラー応答へ変換する。"""
import logging
from typing import Any

from django.http import Http404
from rest_framework.response import Response

from shop.common.errors import AppError, InternalError, NotFoundError, ValidationError
from shop.common.logging import build_extra

logger = logging.getLogger("shop.api")


# trace: ADDR-007
def _details_from_drf(detail: Any, prefix: str = "") -> list[dict[str, str]]:
    """DRF の検証エラー内容を details（項目名と理由）の配列へ変換する。"""
    details: list[dict[str, str]] = []
    if isinstance(detail, dict):
        for field, value in detail.items():
            field_name = f"{prefix}{field}"
            details.extend(_details_from_drf(value, prefix=f"{field_name}."))
            if not isinstance(value, dict | list):
                details.append({"field": field_name, "reason": str(value)})
    elif isinstance(detail, list):
        for value in detail:
            if isinstance(value, dict | list):
                details.extend(_details_from_drf(value, prefix=prefix))
            else:
                details.append({"field": prefix.rstrip("."), "reason": str(value)})
    else:
        details.append({"field": prefix.rstrip("."), "reason": str(detail)})
    return details


# trace: ADDR-005, ADDR-007
def api_exception_handler(exc: Exception, context: dict[str, Any]) -> Response:
    """業務例外・検証例外・未捕捉例外を共通形式のエラー応答へ変換する。"""
    from rest_framework.exceptions import ValidationError as DrfValidationError

    if isinstance(exc, AppError):
        error = exc
    elif isinstance(exc, DrfValidationError):
        details: list[dict[str, str]] = []
        for item in _details_from_drf(exc.detail):
            if item not in details:
                details.append(item)
        error = ValidationError(details=details)
    elif isinstance(exc, Http404):
        error = NotFoundError()
    else:
        error = InternalError()

    if error.code == "INTERNAL_ERROR":
        logger.exception(
            "unhandled_error",
            extra=build_extra(event="unhandled_error", error_code=error.code, exception_class=type(exc).__name__),
        )
    else:
        logger.info("business_error", extra=build_extra(event="business_error", error_code=error.code))
    return Response(error.to_payload(), status=error.http_status)
