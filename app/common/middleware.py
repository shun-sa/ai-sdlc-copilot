# trace: ADDR-007
"""要求ごとの相関ID採番とアクセスログ出力を行うミドルウェア。"""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

from common.logging import reset_request_id, set_request_id

logger = logging.getLogger("minicommerce.request")

REQUEST_ID_HEADER = "X-Request-ID"


class RequestLogMiddleware:
    """X-Request-ID の採番・引継ぎと、1要求1行のアクセスログを担当する。"""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    # trace: ADDR-007
    def __call__(self, request: HttpRequest) -> HttpResponse:
        request_id = (request.headers.get(REQUEST_ID_HEADER) or "").strip() or uuid.uuid4().hex
        request.request_id = request_id
        # 以降の全ログ行（例外ログ・外部連携ログを含む）へ同じ相関IDを出力する（INV-003）。
        token = set_request_id(request_id)
        started = time.monotonic()
        try:
            try:
                response = self.get_response(request)
            except Exception:
                duration_ms = int((time.monotonic() - started) * 1000)
                logger.exception(
                    "request failed",
                    extra=self.log_fields(request, request_id, status=500, duration_ms=duration_ms),
                )
                raise
            duration_ms = int((time.monotonic() - started) * 1000)
            response[REQUEST_ID_HEADER] = request_id
            logger.info(
                "request",
                extra=self.log_fields(request, request_id, status=response.status_code, duration_ms=duration_ms),
            )
            return response
        finally:
            reset_request_id(token)

    @staticmethod
    def log_fields(request: HttpRequest, request_id: str, *, status: int, duration_ms: int) -> dict[str, object]:
        """ログの必須項目を組み立てる（path はクエリ文字列を除いたパス部のみ）。"""
        user = getattr(request, "login_user", None)
        return {
            "request_id": request_id,
            "method": request.method,
            "path": request.path,
            "status": status,
            "user_id": getattr(user, "id", None),
            "duration_ms": duration_ms,
        }
