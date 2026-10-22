# trace: ADDR-002
"""Web API の認証クラス。Authorization ヘッダーの Bearer トークンだけを認証に用いる。"""
from typing import Any

from rest_framework.authentication import BaseAuthentication
from rest_framework.request import Request

from shop.common import request_context
from shop.common.errors import AuthenticationRequiredError
from shop.services import accounts

AUTH_SCHEME = "Bearer"


# trace: ADDR-002
class ApiTokenAuthentication(BaseAuthentication):
    """DB に保持した認証トークンで利用者を特定する（ADDR-002 DD-001）。"""

    def authenticate(self, request: Request) -> tuple[Any, Any] | None:
        """Authorization ヘッダーがある場合にトークンを検証する。"""
        header = request.headers.get("Authorization", "")
        if not header:
            return None
        scheme, _, value = header.partition(" ")
        if scheme != AUTH_SCHEME or not value.strip():
            raise AuthenticationRequiredError()
        user, token = accounts.resolve_token(value.strip())
        request_context.set_user_id(user.user_id)
        return user, token

    def authenticate_header(self, request: Request) -> str:
        """認証方式を返す。"""
        return AUTH_SCHEME


# trace: ADDR-002
def current_user(request: Any) -> Any:
    """認証済みの利用者を返す（未認証は認証エラー）。"""
    user = getattr(request, "user", None)
    if user is None:
        raise AuthenticationRequiredError()
    return user


# trace: ADDR-002
def current_token(request: Any) -> Any:
    """要求に使われた認証トークンを返す。"""
    token = getattr(request, "auth", None)
    if token is None:
        raise AuthenticationRequiredError()
    return token
