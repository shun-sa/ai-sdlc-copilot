# trace: ADDR-005
"""共通ミドルウェア。X-Request-ID の受理・生成と、要求1件ごとのログ出力を行う。"""
import logging
import re
import time
import uuid
from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

from shop.common import request_context
from shop.common.logging import build_extra

logger = logging.getLogger("shop.access")

# 受理する X-Request-ID の形式（ADDR-005 ASM-001）。
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9-]{1,64}$")


# trace: ADDR-005
class RequestLogMiddleware:
    """要求IDの相関付けと、応答直前のリクエストログ1件の出力を行う。"""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        """後続のハンドラを保持する。"""
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """要求IDを設定し、処理時間とともにリクエストログを出力する。"""
        request_id = self._resolve_request_id(request)
        request_context.set_request_id(request_id)
        request_context.set_user_id(None)
        started_at = time.monotonic()
        try:
            response = self.get_response(request)
        finally:
            duration_ms = int((time.monotonic() - started_at) * 1000)
        response["X-Request-ID"] = request_id
        logger.info(
            "request",
            extra=build_extra(
                event="request",
                method=request.method,
                path=request.path,
                status=response.status_code,
                duration_ms=duration_ms,
            ),
        )
        request_context.reset()
        return response

    @staticmethod
    def _resolve_request_id(request: HttpRequest) -> str:
        """要求ヘッダーの X-Request-ID を検証し、無効なら新しい値を生成する。"""
        received = request.headers.get("X-Request-ID", "")
        if received and REQUEST_ID_PATTERN.match(received):
            return received
        return uuid.uuid4().hex
