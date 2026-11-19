# trace: ADDR-012, ADDR-002
"""全画面共通の表示内容（UI-05・UI-06：システム名、ログイン中の氏名、カートの合計点数の表示枠）。

共通レイアウトはカートを参照・作成しない。合計点数は FR-020 の業務処理を持つ carts の部品
（carts.context_processors.header_cart_count）が供給し、供給がない間（来訪者・管理者等）は表示しない
（ADDR-001 4.3 の14 r4）。
"""

from typing import Any

from django.http import HttpRequest

from common.codes import UserType


# trace: ADDR-012, ADDR-002
def site_header(request: HttpRequest) -> dict[str, Any]:
    user = getattr(request, "user", None)
    context: dict[str, Any] = {
        "header_user": None,
        "header_is_admin": False,
        "header_cart_count": None,  # 表示枠の既定値（値は carts の部品が供給する）
        "session_expired": bool(getattr(request, "mc_session_expired", False)),
    }
    if user is None or not getattr(user, "is_authenticated", False):
        return context
    context["header_user"] = user
    context["header_is_admin"] = user.user_type == UserType.ADMIN
    return context
