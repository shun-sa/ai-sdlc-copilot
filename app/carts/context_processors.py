# trace: ADDR-001, ADDR-012
"""共通表示（UI-05）の合計点数を供給する部品（ADDR-001 4.3 の14・DD-015・DD-016、r4 の Task の割当て）。

購入者の画面の表示ごとに FR-020 の業務処理（carts.services.get_cart。利用中カートがなければ作成する）を実行し、
その結果の合計点数を共通レイアウトへ渡す。来訪者・管理者では実行しない（作成しない）。
共通レイアウト（common）はカートを参照・作成せず、供給された値を表示する枠だけを持つ。
FR-020 がシステムエラー（E-020-03）となった場合は作成を取り消して SCR-901 を表示する。
SCR-901 の表示中に失敗した場合に限り、合計点数を表示せずに SCR-901 を表示する（ADDR-001 ASM-002）。
"""

from typing import Any

from django.http import HttpRequest

from carts import services
from common.codes import UserType
from common.errors import ServiceError
from common.logging import operation_log
from common.web import ERROR_PAGE_ATTR


# trace: ADDR-001, ADDR-012
def header_cart_count(request: HttpRequest) -> dict[str, Any]:
    user = getattr(request, "user", None)
    if user is None or not getattr(user, "is_authenticated", False) or user.user_type != UserType.BUYER:
        return {}
    try:
        with operation_log("FR-020 cart-count", user.pk):
            content = services.get_cart(user)
    except ServiceError:
        if getattr(request, ERROR_PAGE_ATTR, False):
            return {}
        raise
    return {"header_cart_count": content["total_quantity"]}
