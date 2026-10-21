# trace: ADDR-009
"""payments アプリケーションの定義。"""

from django.apps import AppConfig


class PaymentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "payments"
    verbose_name = "決済（模擬）"
