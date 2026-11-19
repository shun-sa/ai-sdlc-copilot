# trace: ADDR-011
from django.apps import AppConfig


# trace: ADDR-011
class TestSupportConfig(AppConfig):
    __test__ = False  # pytest の収集対象にしない

    name = "test_support"
    verbose_name = "試験支援（開発・検証環境専用）"
