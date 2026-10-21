# trace: ADDR-001
"""carts アプリケーションの定義。"""

from django.apps import AppConfig


class CartsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "carts"
    verbose_name = "カート・クーポン"
