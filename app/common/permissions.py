# trace: ADDR-002
"""ロールによる認可（サーバー側で判定する。NFR-SC-03）。"""

from __future__ import annotations

from typing import Any

from rest_framework.permissions import BasePermission

from common.exceptions import AuthenticationRequired, PermissionDeniedError

ROLE_BUYER = "buyer"
ROLE_ADMIN = "admin"


class IsAuthenticated(BasePermission):
    """ログイン済み（購入者・管理者）であることを要求する。"""

    def has_permission(self, request: Any, view: Any) -> bool:
        if getattr(request, "user", None) is None:
            raise AuthenticationRequired()
        return True


class IsBuyer(BasePermission):
    """購入者だけが利用できる機能に適用する。"""

    def has_permission(self, request: Any, view: Any) -> bool:
        user = getattr(request, "user", None)
        if user is None:
            raise AuthenticationRequired()
        if user.role != ROLE_BUYER:
            raise PermissionDeniedError()
        return True


class IsAdmin(BasePermission):
    """管理者だけが利用できる機能に適用する。"""

    def has_permission(self, request: Any, view: Any) -> bool:
        user = getattr(request, "user", None)
        if user is None:
            raise AuthenticationRequired()
        if user.role != ROLE_ADMIN:
            raise PermissionDeniedError()
        return True
