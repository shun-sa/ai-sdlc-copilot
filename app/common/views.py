# trace: ADDR-001, ADDR-012
"""存在しない要求先・CSRF 検証の失敗・想定外のエラーの応答（ADDR-001 4.3 の7、NFR-SC-10）。

/api/ 配下は ADDR-001 の封筒（JSON）、それ以外は SCR-901 を返す。内部情報は含めない。
"""

from django.http import HttpRequest, HttpResponse

from common.api import api_error_response
from common.errors import MSG_SYSTEM_ERROR
from common.middleware import is_api_request
from common.web import error_page


# trace: ADDR-001, ADDR-012
def not_found(request: HttpRequest, exception: Exception | None = None) -> HttpResponse:
    if is_api_request(request):
        return api_error_response("not_found", "指定された対象が見つかりません。", 404)
    return error_page(request, "not_found")


# trace: ADDR-001, ADDR-012
def bad_request(request: HttpRequest, exception: Exception | None = None) -> HttpResponse:
    if is_api_request(request):
        return api_error_response("input_error", "要求を処理できません。", 400)
    return error_page(request, "not_found", status=400)


# trace: ADDR-001, ADDR-012
def permission_denied_view(request: HttpRequest, exception: Exception | None = None) -> HttpResponse:
    if is_api_request(request):
        return api_error_response("permission_denied", "この操作を行う権限がありません。", 403)
    return error_page(request, "permission_denied")


# trace: ADDR-001, ADDR-012
def system_error_response(request: HttpRequest) -> HttpResponse:
    if is_api_request(request):
        return api_error_response("system_error", MSG_SYSTEM_ERROR, 500)
    try:
        return error_page(request, "system_error")
    except Exception:  # noqa: BLE001 - テンプレートの表示にも失敗した場合は最小限の応答を返す
        return HttpResponse(MSG_SYSTEM_ERROR, status=500, content_type="text/plain; charset=utf-8")


# trace: ADDR-001, ADDR-012
def server_error(request: HttpRequest) -> HttpResponse:
    return system_error_response(request)


# trace: ADDR-012
def csrf_failure(request: HttpRequest, reason: str = "") -> HttpResponse:
    """他のサイトから送信させた更新要求を受け付けない（NFR-SC-05、ADDR-002 DD-008）。"""
    return error_page(request, "permission_denied")
