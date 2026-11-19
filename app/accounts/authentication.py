# trace: ADDR-002, ADDR-001
"""Web API の Bearer 認証（ADDR-002 4.3 の2、ADDR-001 4.3 の3）。

Authorization ヘッダーの Bearer 値の照合値で行を検索し、判定時刻（秒）＜有効期限日時の場合だけ有効とする。
無効な値は例外にせず来訪者として扱い、認証を要する API で 401 authentication_required とする。
Cookie によるセッション認証は /api/ で受け付けない（ADDR-001 INV-003）。
"""

from typing import Any

from rest_framework.authentication import BaseAuthentication

from accounts import services


# trace: ADDR-002, ADDR-001
class BearerAuthentication(BaseAuthentication):
    keyword = "Bearer"

    def authenticate(self, request: Any) -> tuple[Any, Any] | None:
        header = request.META.get("HTTP_AUTHORIZATION")
        if not isinstance(header, str):
            return None
        parts = header.split(" ")
        if len(parts) != 2 or parts[0] != self.keyword or not parts[1]:
            return None
        resolved = services.resolve_api_token(parts[1])
        if resolved is None:
            return None
        user, state = resolved
        request._request.api_user_id = user.pk
        return user, state

    def authenticate_header(self, request: Any) -> str:
        return 'Bearer realm="api"'
