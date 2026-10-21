# trace: ADDR-011
"""エラー画面（SCR-901）とDjangoの例外ハンドラ。"""

from __future__ import annotations

import logging
from typing import Any

from django.http import HttpRequest, HttpResponse

from web.support import ERROR_INTERNAL, ERROR_NOT_FOUND, ERROR_PERMISSION, render_error

logger = logging.getLogger("minicommerce.error")


def bad_request(request: HttpRequest, exception: Any = None) -> HttpResponse:
    """不正な要求（内部情報は表示しない）。"""
    return render_error(request, ERROR_NOT_FOUND, 400)


def permission_denied(request: HttpRequest, exception: Any = None) -> HttpResponse:
    """権限なし（SCR-901）。"""
    return render_error(request, ERROR_PERMISSION, 403)


def not_found(request: HttpRequest, exception: Any = None) -> HttpResponse:
    """対象なし（SCR-901）。"""
    return render_error(request, ERROR_NOT_FOUND, 404)


def server_error(request: HttpRequest) -> HttpResponse:
    """システムエラー（SCR-901）。スタックトレース・SQLは表示しない。"""
    logger.error("unhandled screen error", extra={"path": request.path})
    return render_error(request, ERROR_INTERNAL, 500)
