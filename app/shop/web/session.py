# trace: ADDR-002
"""画面のログインセッション管理（ADDR-002 DD-005、DD-006）。

利用者の照会は services 層（accounts）へ委譲し、web 層からモデルを直接参照しない（ADDR-004 DD-003）。
"""
from typing import Any

from django.http import HttpRequest

from shop.common import request_context
from shop.services import accounts

SESSION_USER_KEY = "user_id"
FLASH_KEY = "flash_message"


# trace: ADDR-002
def login(request: HttpRequest, user: Any) -> None:
    """ログイン成功時にセッション識別子を再発行し、利用者を記録する。"""
    request.session.cycle_key()
    request.session[SESSION_USER_KEY] = user.user_id
    request_context.set_user_id(user.user_id)


# trace: ADDR-002
def logout(request: HttpRequest) -> None:
    """ログインセッションを破棄する。"""
    request.session.flush()
    request_context.set_user_id(None)


# trace: ADDR-002
def current_user(request: HttpRequest) -> Any:
    """ログイン中の利用者を返す（未ログインは None）。"""
    cached = getattr(request, "_shop_user", None)
    if cached is not None:
        return cached
    user_id = request.session.get(SESSION_USER_KEY)
    if not user_id:
        return None
    user = accounts.find_user(user_id)
    if user is None:
        request.session.flush()
        return None
    request._shop_user = user
    request_context.set_user_id(user.user_id)
    return user


# trace: ADDR-002
def set_flash(request: HttpRequest, message: str) -> None:
    """次の画面で表示する完了メッセージを保持する。"""
    request.session[FLASH_KEY] = message


# trace: ADDR-002
def pop_flash(request: HttpRequest) -> Any:
    """保持した完了メッセージを取り出す（1回だけ表示する）。"""
    return request.session.pop(FLASH_KEY, None)
