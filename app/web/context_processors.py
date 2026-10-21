# trace: ADDR-010
"""共通レイアウトへ渡す値（ヘッダー表示・メッセージ領域）。"""

from __future__ import annotations

from typing import Any

from django.http import HttpRequest

from accounts.models import ROLE_ADMIN
from carts import services as cart_services
from web.support import current_user, pop_flash


def layout(request: HttpRequest) -> dict[str, Any]:
    """共通ヘッダー・メッセージ領域の表示に必要な値を返す。"""
    user = current_user(request)
    total_quantity = None
    if user is not None and user.role != ROLE_ADMIN:
        cart = cart_services.get_open_cart(user)
        if cart is None:
            total_quantity = 0
        else:
            total_quantity = sum(line.quantity for line in cart.lines.all())
    return {
        "login_user": user,
        "is_admin": bool(user and user.role == ROLE_ADMIN),
        "cart_total_quantity": total_quantity,
        "flash_message": pop_flash(request),
    }
