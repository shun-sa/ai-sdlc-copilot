# trace: ADDR-002, ADDR-012
"""画面のログイン状態（Django セッション）から利用者を復元する認証バックエンド。

パスワードの照合は業務処理層で check_password により行うため、本バックエンドは照合を行わない。
"""

from typing import Any

from accounts.models import User


# trace: ADDR-002, ADDR-012
class SessionUserBackend:
    def authenticate(self, request: Any, **credentials: Any) -> None:
        return None

    def get_user(self, user_id: Any) -> User | None:
        try:
            return User.objects.get(pk=user_id)
        except (User.DoesNotExist, ValueError, TypeError):
            return None
