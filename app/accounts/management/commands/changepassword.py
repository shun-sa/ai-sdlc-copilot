# trace: ADDR-012
"""Django 付属の changepassword を置き換え、何も変更せずにエラー終了する（ADDR-012 DD-012）。"""

from typing import Any

from django.core.management.base import BaseCommand, CommandError


# trace: ADDR-012
class Command(BaseCommand):
    help = "利用できません。パスワードの変更・再設定は提供しません（FR-OUT-09）。"

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("args", nargs="*")
        parser.add_argument("--database")

    def handle(self, *args: Any, **options: Any) -> None:
        raise CommandError("このコマンドは利用できません。パスワードの変更・再設定は提供しません。")
