# trace: ADDR-011
"""試験用状態（1行。業務データではない：ADDR-011 DD-002）。開発用機能フラグ有効時だけ組み込まれる。"""

from django.db import models

PAYMENT_MODES = (
    ("normal", "通常"),
    ("connection_error", "接続不可"),
    ("invalid_result", "結果が承認・否認以外"),
    ("missing_result", "結果の欠落"),
    ("missing_processed_at", "処理日時の欠落"),
    ("missing_transaction_ref", "承認で取引参照番号の欠落"),
    ("invalid_transaction_ref", "承認で取引参照番号の形式誤り"),
    ("missing_decline_reason", "否認で否認理由の欠落"),
)
ORDER_FAULT_POINTS = (
    ("none", "なし"),
    ("after_stock_decrement", "在庫数量の減算後"),
    ("after_order_insert", "注文の登録後"),
)


# trace: ADDR-011
class TestState(models.Model):
    __test__ = False  # pytest の収集対象にしない

    fixed_now = models.DateTimeField(null=True, blank=True)
    payment_delay_seconds = models.FloatField(default=0)
    payment_mode = models.CharField(max_length=32, choices=PAYMENT_MODES, default="normal")
    order_fault_point = models.CharField(max_length=32, choices=ORDER_FAULT_POINTS, default="none")
