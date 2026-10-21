# trace: ADDR-002, ADDR-011
"""会員・認証の API ビュー（FR-001〜FR-004）。"""

from __future__ import annotations

from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts import serializers, services
from common.exceptions import AuthenticationRequired
from common.permissions import IsAuthenticated


# trace: ADDR-002, ADDR-011
class RegisterView(APIView):
    """FR-001 会員登録。認証不要。自動ログインしない。"""

    authentication_classes: list = []
    permission_classes: list = []

    def post(self, request: Request) -> Response:
        user = services.register_user(request.data if isinstance(request.data, dict) else {})
        return Response(serializers.registered_user_payload(user), status=201)


# trace: ADDR-002, ADDR-011
class LoginView(APIView):
    """FR-002 ログイン。認証トークンを発行する。"""

    authentication_classes: list = []
    permission_classes: list = []

    def post(self, request: Request) -> Response:
        data = request.data if isinstance(request.data, dict) else {}
        user, raw_token, token = services.login_api(data.get("email"), data.get("password"))
        return Response(serializers.login_payload(user, raw_token, token), status=200)


# trace: ADDR-002
class LogoutView(APIView):
    """FR-003 ログアウト。要求に使われたトークンのみを無効化する。"""

    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        token = request.auth
        if token is None:
            raise AuthenticationRequired()
        services.logout(token)
        return Response(status=204)


# trace: ADDR-002
class MeView(APIView):
    """FR-004 ログイン利用者情報照会。"""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        return Response(serializers.user_payload(request.user), status=200)
