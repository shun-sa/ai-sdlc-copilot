# trace: ADDR-001, ADDR-002, ADDR-012
"""会員・認証の Web API（FR-001〜FR-004。ADDR-001 4.3 の4）。"""

from rest_framework.request import Request
from rest_framework.response import Response

from accounts import services
from common.api import BaseApiView, request_body, require_user, run


# trace: ADDR-001, ADDR-012
class RegisterApi(BaseApiView):
    """FR-001 POST /api/auth/register/（認証不要。成功時 201）。"""

    def post(self, request: Request) -> Response:
        body = request_body(request)
        return run(
            request,
            "FR-001 register",
            lambda: services.register(
                body.get("email"), body.get("password"), body.get("password_confirmation"), body.get("name")
            ),
            status=201,
        )


# trace: ADDR-001, ADDR-002
class LoginApi(BaseApiView):
    """FR-002 POST /api/auth/login/（token・expires_at・user を返す：ADDR-001 DD-006）。"""

    def post(self, request: Request) -> Response:
        body = request_body(request)
        return run(request, "FR-002 login", lambda: services.login_api(body.get("email"), body.get("password")))


# trace: ADDR-001, ADDR-002
class LogoutApi(BaseApiView):
    """FR-003 POST /api/auth/logout/（成功時 204・本文なし）。"""

    def post(self, request: Request) -> Response:
        def action() -> None:
            user = require_user(request, "E-003", None)
            services.logout_api(user, request.auth)

        return run(request, "FR-003 logout", action, status=204)


# trace: ADDR-001, ADDR-002
class MeApi(BaseApiView):
    """FR-004 GET /api/auth/me/。"""

    def get(self, request: Request) -> Response:
        return run(request, "FR-004 me", lambda: services.me(require_user(request, "E-004", None)))
