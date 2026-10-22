# trace: ADDR-002
"""画面共通レイアウト（UI-05、UI-06、UI-08）に渡す情報。"""
from typing import Any

from django.http import HttpRequest

from shop.services import accounts, carts
from shop.web import session


# trace: ADDR-002
def layout(request: HttpRequest) -> dict[str, Any]:
    """共通ヘッダーとメッセージ領域の表示情報を返す。"""
    user = session.current_user(request)
    is_admin = accounts.is_admin(user)
    return {
        "current_user": user,
        "is_admin": is_admin,
        "cart_total_quantity": carts.open_cart_total_quantity(user) if user and not is_admin else 0,
        "flash_message": session.pop_flash(request),
    }
