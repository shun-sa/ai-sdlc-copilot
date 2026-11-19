# trace: ADDR-011, ADDR-004
"""注文確定の業務処理の障害注入点（ADDR-011 4.3 の3、DD-005。TASK-019）。

開発用機能フラグが有効で試験支援モジュールが組み込まれている場合だけ試験用状態を読み、
指定の障害点でデータ更新の例外を発生させる。フラグ無効時は何もしない（本番では無効）。
"""

from django.apps import apps
from django.conf import settings
from django.db import DatabaseError


# trace: ADDR-011
class InjectedFaultError(DatabaseError):
    """試験用状態で指定した障害点で発生させるデータ更新の例外。"""


# trace: ADDR-011, ADDR-004
def order_fault_point(point: str) -> None:
    if not getattr(settings, "MINICOMMERCE_DEV_FEATURES", False):
        return
    if not apps.is_installed("test_support"):
        return
    from test_support.state import read_order_fault_point

    if read_order_fault_point() == point:
        raise InjectedFaultError("injected fault")
