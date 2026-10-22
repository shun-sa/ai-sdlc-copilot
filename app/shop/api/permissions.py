# trace: ADDR-002, ADDR-007
"""Web API のロール判定。権限判定はサーバー側で行う（NFR-SC-03）。

判定そのものは services 層（accounts）の単一実装へ委譲する（ADDR-004 DD-002、DD-003、INV-001）。
"""
from typing import Any

from rest_framework.permissions import BasePermission

from shop.services import accounts


# trace: ADDR-002
class IsAuthenticated(BasePermission):
    """認証済みであることを要求する（DRF の既定の権限判定）。"""

    def has_permission(self, request: Any, view: Any) -> bool:
        """未認証の場合は認証エラーを送出する。"""
        accounts.require_authenticated(getattr(request, "user", None))
        return True


# trace: ADDR-002
class IsBuyer(BasePermission):
    """購入者だけが利用できる機能の権限判定。"""

    def has_permission(self, request: Any, view: Any) -> bool:
        """購入者以外は権限エラーを送出する。"""
        accounts.require_buyer(getattr(request, "user", None))
        return True


# trace: ADDR-002
class IsAdmin(BasePermission):
    """管理者だけが利用できる機能の権限判定。"""

    def has_permission(self, request: Any, view: Any) -> bool:
        """管理者以外は権限エラーを送出する。"""
        accounts.require_admin(getattr(request, "user", None))
        return True
