# trace: ADDR-002
"""API の Bearer トークン認証（DRF の認証クラス）。

common は機能アプリを import しないため、トークンの解決は設定値
（``AUTH_TOKEN_RESOLVER``）で与えられた関数へ委ねる（ADDR-001 INV-001、ADDR-002）。
"""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.utils.module_loading import import_string
from rest_framework.authentication import BaseAuthentication

from common.exceptions import AuthenticationRequired

KEYWORD = "Bearer"


class BearerTokenAuthentication(BaseAuthentication):
    """Authorization ヘッダーの Bearer トークンで利用者を識別する。"""

    def authenticate(self, request: Any) -> tuple[Any, Any] | None:
        header = request.headers.get("Authorization")
        if not header:
            return None
        parts = header.split()
        if len(parts) != 2 or parts[0] != KEYWORD or not parts[1]:
            raise AuthenticationRequired()
        resolver = import_string(settings.AUTH_TOKEN_RESOLVER)
        resolved = resolver(parts[1])
        if resolved is None:
            raise AuthenticationRequired()
        user, token = resolved
        underlying = getattr(request, "_request", request)
        underlying.login_user = user
        return user, token

    def authenticate_header(self, request: Any) -> str:
        return KEYWORD
