# trace: ADDR-004
"""shop アプリの設定。"""
from django.apps import AppConfig


class ShopConfig(AppConfig):
    """単一 Django アプリ shop の構成。"""

    default_auto_field = "django.db.models.AutoField"
    name = "shop"
