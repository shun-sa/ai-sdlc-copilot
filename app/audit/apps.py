# trace: ADDR-012
from django.apps import AppConfig


# trace: ADDR-012
class AuditConfig(AppConfig):
    name = "audit"
    verbose_name = "監査ログ"
