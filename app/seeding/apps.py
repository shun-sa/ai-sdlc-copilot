# trace: ADDR-001
"""seeding アプリケーションの定義。"""

from django.apps import AppConfig


class SeedingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "seeding"
    verbose_name = "初期データ投入"
