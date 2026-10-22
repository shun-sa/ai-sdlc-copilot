# trace: ADDR-002, ADDR-007
"""エラー画面（SCR-901）とハンドラ。内部情報を表示しない（UI-34）。"""
from typing import Any

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from shop.web import messages

TEMPLATE = "web/error.html"


# trace: ADDR-007
def _render(request: HttpRequest, title: str, message: str, status: int) -> HttpResponse:
    """SCR-901 を指定の区分で表示する。"""
    return render(request, TEMPLATE, {"page_title": title, "error_message": message}, status=status)


# trace: ADDR-007
def bad_request(request: HttpRequest, exception: Any = None) -> HttpResponse:
    """不正な要求を受け取った場合の画面。"""
    return _render(request, "エラー", "要求の内容が正しくありません。入力内容を確認してください。", 400)


# trace: ADDR-007
def permission_denied(request: HttpRequest, exception: Any = None) -> HttpResponse:
    """権限なしの画面（SCR-901-V02）。"""
    return _render(request, messages.PERMISSION_DENIED_TITLE, messages.PERMISSION_DENIED_MESSAGE, 403)


# trace: ADDR-007
def page_not_found(request: HttpRequest, exception: Any = None) -> HttpResponse:
    """対象なしの画面（SCR-901-V01）。"""
    return _render(request, messages.NOT_FOUND_TITLE, messages.NOT_FOUND_MESSAGE, 404)


# trace: ADDR-007
def server_error(request: HttpRequest) -> HttpResponse:
    """システムエラーの画面（SCR-901-V03）。"""
    return _render(request, messages.INTERNAL_ERROR_TITLE, messages.INTERNAL_ERROR_MESSAGE, 500)
