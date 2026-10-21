# trace: ADDR-001
"""accounts アプリケーションの定義。"""

from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"
    verbose_name = "利用者・認証"
