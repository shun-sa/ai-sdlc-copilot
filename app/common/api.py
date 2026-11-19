# trace: ADDR-001, ADDR-002, ADDR-013, ADDR-012
"""Web API の共通変換部品（ADDR-001 9章：共通例外ハンドラ・認証の取出し・値の表現）。

API 層は電文の変換・認証情報の取出し・例外の変換のみを行い、業務判定は業務処理層で行う（ADDR-001 6章）。
"""

from collections.abc import Callable
from datetime import date, datetime
from typing import Any

from django.http import Http404, JsonResponse
from rest_framework import exceptions as drf_exceptions
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from common import clock
from common.codes import UserType
from common.errors import (
    MSG_SYSTEM_ERROR,
    REQUEST_PARSE_ERROR_ATTR,
    ServiceError,
    authentication_required,
    is_request_parse_error,
    permission_denied,
)
from common.logging import log_error, operation_log
from common.parsers import MSG_BODY_PARSE_ERROR

MSG_REQUEST_PARSE_ERROR = "要求を処理できません。"


# trace: ADDR-001
def to_json_value(value: Any) -> Any:
    """日時は +09:00 付き ISO 8601 秒単位、日付は YYYY-MM-DD とする（ADDR-001 DD-005）。"""
    if isinstance(value, datetime):
        return clock.to_jst(value).replace(microsecond=0).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: to_json_value(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [to_json_value(item) for item in value]
    return value


# trace: ADDR-001
def envelope(
    error_type: str,
    message: str,
    *,
    reason: str | None = None,
    fields: list[dict[str, Any]] | None = None,
    values: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """エラー応答の封筒（type・reason・message・fields・values を常に含める：DD-002）。"""
    return {
        "error": {
            "type": error_type,
            "reason": reason,
            "message": message,
            "fields": fields or [],
            "values": to_json_value(values or {}),
        }
    }


# trace: ADDR-001
def service_error_response(exc: ServiceError) -> Response:
    body = envelope(
        exc.error_type,
        exc.message,
        reason=exc.reason if exc.error_type == "business_error" else None,
        fields=[{"field": f.field, "reason": f.reason, "message": f.message} for f in exc.fields],
        values=exc.values if exc.error_type == "business_error" else {},
    )
    response = Response(body, status=exc.http_status)
    if exc.http_status == 401:
        response["WWW-Authenticate"] = 'Bearer realm="api"'
    return response


# trace: ADDR-001, ADDR-013
def exception_handler(exc: Exception, context: dict[str, Any]) -> Response:
    """DRF の共通例外ハンドラ。内部情報（スタックトレース・SQL 文等）を応答に含めない（DD-010）。"""
    request = context.get("request")
    user_id = api_user_id(request) if request is not None else None
    if isinstance(exc, ServiceError):
        if exc.error_type == "system_error":
            log_error(exc.error_type, exc, user_id)
        return service_error_response(exc)
    if isinstance(exc, drf_exceptions.NotAuthenticated | drf_exceptions.AuthenticationFailed):
        response = Response(envelope("authentication_required", authentication_required("").message), status=401)
        response["WWW-Authenticate"] = 'Bearer realm="api"'
        return response
    if isinstance(exc, drf_exceptions.PermissionDenied):
        return Response(envelope("permission_denied", permission_denied("").message), status=403)
    if isinstance(exc, Http404 | drf_exceptions.NotFound):
        return Response(envelope("not_found", "指定された対象が見つかりません。"), status=404)
    if isinstance(exc, drf_exceptions.MethodNotAllowed):
        return Response(envelope("not_found", "指定された操作は利用できません。"), status=405)
    if isinstance(exc, drf_exceptions.ParseError | drf_exceptions.UnsupportedMediaType):
        return Response(envelope("input_error", MSG_BODY_PARSE_ERROR), status=400)
    if is_request_parse_error(exc):
        # クエリ・フォームの項目数の上限超過、不正な Host 等の要求そのものの誤り（ERR-01。LOG-02 に記録しない）
        return Response(envelope("input_error", MSG_REQUEST_PARSE_ERROR), status=400)
    if isinstance(exc, drf_exceptions.APIException):
        return Response(envelope("input_error", MSG_REQUEST_PARSE_ERROR), status=400)
    log_error("system_error", exc, user_id)
    return Response(envelope("system_error", MSG_SYSTEM_ERROR), status=500)


# trace: ADDR-002, ADDR-013
def api_user_id(request: Any) -> int | None:
    raw = getattr(request, "_request", request)
    return getattr(raw, "api_user_id", None)


# trace: ADDR-001, ADDR-002, ADDR-012
def require_user(request: Request, code_prefix: str, role: str | None) -> Any:
    """認証（①）→ 利用者区分（②）の順に判定する（CMN-14、ADDR-012 DD-004）。"""
    user = getattr(request, "user", None)
    if user is None or not getattr(user, "is_authenticated", False):
        raise authentication_required(f"{code_prefix}-01")
    if role is not None and user.user_type != role:
        raise permission_denied(f"{code_prefix}-02")
    return user


# trace: ADDR-001, ADDR-012
def require_buyer(request: Request, code_prefix: str) -> Any:
    return require_user(request, code_prefix, UserType.BUYER)


# trace: ADDR-001, ADDR-012
def require_admin(request: Request, code_prefix: str) -> Any:
    return require_user(request, code_prefix, UserType.ADMIN)


# trace: ADDR-001
def request_body(request: Request) -> dict[str, Any]:
    """要求本文（JSON オブジェクト）を取り出す。オブジェクト以外は入力エラー（ADDR-001 4.3 の7）。"""
    try:
        data = request.data
    except (drf_exceptions.ParseError, drf_exceptions.UnsupportedMediaType) as exc:
        # 本文を解釈できない要求は LOG-01 にも入力エラーとして記録する（システムエラーとしない）
        setattr(exc, REQUEST_PARSE_ERROR_ATTR, True)
        raise
    if data is None or data == {}:
        return {}
    if not isinstance(data, dict):
        exc = drf_exceptions.ParseError(MSG_BODY_PARSE_ERROR)
        setattr(exc, REQUEST_PARSE_ERROR_ATTR, True)
        raise exc
    return data


# trace: ADDR-001, ADDR-013
def run(request: Request, operation: str, func: Callable[[], Any], status: int = 200) -> Response:
    """業務処理を1回実行し LOG-01 を出力して応答する。"""
    with operation_log(operation, api_user_id(request)):
        result = func()
    if status == 204:
        return Response(status=204)
    return Response(to_json_value(result), status=status)


# trace: ADDR-001
class BaseApiView(APIView):
    """全 API の基底。認証は Bearer のみ（ADDR-002 INV-003）、応答は JSON のみ。"""


# trace: ADDR-001
def api_not_found_response() -> JsonResponse:
    return JsonResponse(
        envelope("not_found", "指定された対象が見つかりません。"), status=404, json_dumps_params={"ensure_ascii": False}
    )


# trace: ADDR-001
def api_error_response(error_type: str, message: str, status: int) -> JsonResponse:
    return JsonResponse(envelope(error_type, message), status=status, json_dumps_params={"ensure_ascii": False})
