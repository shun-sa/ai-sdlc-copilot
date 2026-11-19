# trace: ADDR-012
"""Django 付属の createsuperuser を置き換え、何も変更せずにエラー終了する（ADDR-012 DD-012）。"""

from typing import Any

from django.core.management.base import BaseCommand, CommandError


# trace: ADDR-012
class Command(BaseCommand):
    help = "利用できません。管理者は初期データ一括投入（load_initial_data）でのみ作成します。"

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("args", nargs="*")
        parser.add_argument("--noinput", "--no-input", action="store_true")
        parser.add_argument("--username")
        parser.add_argument("--email")
        parser.add_argument("--database")

    def handle(self, *args: Any, **options: Any) -> None:
        raise CommandError("このコマンドは利用できません。管理者は初期データ一括投入でのみ作成します。")
