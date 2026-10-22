# trace: ADDR-002, ADDR-007
"""認証・利用者機能の Web API（FR-001〜FR-004）。"""
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from shop.api.authentication import current_token, current_user
from shop.api.permissions import IsAuthenticated
from shop.common import timeutils
from shop.services import accounts


# trace: ADDR-002
class RegisterView(APIView):
    """会員登録（FR-001）。認証不要。自動ログインは行わない。"""

    authentication_classes: list = []
    permission_classes: list = []

    def post(self, request: Request) -> Response:
        """購入者を1件登録する。"""
        data = request.data if isinstance(request.data, dict) else {}
        user = accounts.register_user(
            email=data.get("email", ""),
            password=data.get("password", ""),
            password_confirmation=data.get("password_confirmation", ""),
            full_name=data.get("full_name", ""),
        )
        payload = accounts.user_payload(user)
        payload["registered_at"] = timeutils.jst(user.registered_at)
        return Response(payload, status=201)


# trace: ADDR-002
class LoginView(APIView):
    """ログイン（FR-002）。認証トークンを発行する。"""

    authentication_classes: list = []
    permission_classes: list = []

    def post(self, request: Request) -> Response:
        """認証トークン・有効期限・利用者情報を返す。"""
        data = request.data if isinstance(request.data, dict) else {}
        issued = accounts.login_with_token(data.get("email", ""), data.get("password", ""))
        return Response(
            {
                "token": issued.value,
                "expires_at": timeutils.jst(issued.expires_at),
                "user": accounts.user_payload(issued.user),
            }
        )


# trace: ADDR-002
class LogoutView(APIView):
    """ログアウト（FR-003）。要求に使われたトークンのみ無効化する。"""

    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        """トークンを無効化し、応答本文なしで正常終了を返す。"""
        accounts.logout_token(current_token(request))
        return Response(status=204)


# trace: ADDR-002
class MeView(APIView):
    """ログイン利用者情報照会（FR-004）。"""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        """ログイン中の利用者情報を返す。"""
        return Response(accounts.user_payload(current_user(request)))
