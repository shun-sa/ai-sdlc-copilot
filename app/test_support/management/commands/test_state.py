# trace: ADDR-011
"""試験用状態を設定する管理コマンド（ENV-01 の手動の結合テスト用。ADDR-011 4.3 の4）。

  python manage.py test_state set --now 2027-04-30T23:59:59+09:00 --payment-delay 11 --payment-mode normal
  python manage.py test_state set --order-fault after_stock_decrement
  python manage.py test_state show
  python manage.py test_state clear

開発用機能フラグ（MINICOMMERCE_DEV_FEATURES=true）が有効なときだけ存在する（本番では利用できない）。
"""

import json
from datetime import datetime
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from test_support import state
from test_support.models import ORDER_FAULT_POINTS, PAYMENT_MODES


# trace: ADDR-011
class Command(BaseCommand):
    help = "試験用状態（現在日時・模擬決済の応答・注文確定途中の障害）を設定・表示・解除する（開発・検証環境専用）。"

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("action", choices=["set", "clear", "show"])
        parser.add_argument("--now", dest="now", help="判定に用いる現在日時（ISO 8601、オフセット付き。秒未満可）")
        parser.add_argument("--payment-delay", dest="delay", type=float, help="模擬決済の応答の遅延秒数")
        parser.add_argument("--payment-mode", dest="mode", choices=[v for v, _ in PAYMENT_MODES])
        parser.add_argument("--order-fault", dest="fault", choices=[v for v, _ in ORDER_FAULT_POINTS])

    def handle(self, *args: Any, **options: Any) -> None:
        action = options["action"]
        if action == "clear":
            state.clear_state()
        elif action == "set":
            fixed_now = None
            if options.get("now"):
                try:
                    fixed_now = datetime.fromisoformat(options["now"])
                except ValueError as exc:
                    raise CommandError("--now must be ISO 8601 with offset") from exc
                if fixed_now.tzinfo is None:
                    raise CommandError("--now must include a UTC offset (e.g. +09:00)")
            try:
                state.set_state(
                    fixed_now=fixed_now,
                    payment_delay_seconds=options.get("delay"),
                    payment_mode=options.get("mode"),
                    order_fault_point=options.get("fault"),
                )
            except ValueError as exc:
                raise CommandError(str(exc)) from exc
        self.stdout.write(json.dumps(state.show_state(), ensure_ascii=False))
