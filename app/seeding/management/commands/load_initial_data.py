# trace: ADDR-005, FILE-001
"""初期データ一括投入コマンド（FR-060）。

実行例: ``python manage.py load_initial_data seed/initial_data.json --reset``
"""

from __future__ import annotations

import sys
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import DatabaseError

from seeding import services

EXIT_FAILURE = 1


class Command(BaseCommand):
    """定義ファイルから初期データを一括投入する。"""

    help = "定義ファイル（JSON）から利用者・仕入先・商品分類・商品・在庫単位・クーポンを一括投入する。"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("path", nargs="?", default=None, help="定義ファイルのパス")
        parser.add_argument(
            "--reset",
            action="store_true",
            help="監査ログ以外の全データを削除してから投入する（検証環境の初期化専用）",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        path = options.get("path")
        if not path:
            services.record_failure()
            self.stderr.write(
                "コマンドの指定が誤っています。定義ファイルのパスを指定してください"
                "（全削除して投入する場合は --reset を指定します）。"
            )
            sys.exit(EXIT_FAILURE)

        try:
            result = services.load_initial_data(path, reset=bool(options.get("reset")))
        except services.SeedError as error:
            self.report_failure(error)
            sys.exit(EXIT_FAILURE)
        except DatabaseError as error:
            raise CommandError("システム障害のため何も投入しませんでした。") from error

        self.stdout.write(result.summary())

    def report_failure(self, error: services.SeedError) -> None:
        """失敗の理由と違反の全件を標準エラー出力へ表示する（項目の値は出力しない）。"""
        try:
            services.record_failure()
        except DatabaseError:
            pass
        self.stderr.write(f"{error.code}: {error.message}")
        for violation in error.violations:
            self.stderr.write(violation.format())
        self.stderr.write("何も投入しませんでした。")
