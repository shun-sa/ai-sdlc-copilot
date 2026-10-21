# trace: ADDR-001
"""catalog アプリケーションの定義。"""

from django.apps import AppConfig


class CatalogConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "catalog"
    verbose_name = "商品カタログ"
