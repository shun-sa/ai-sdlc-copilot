# trace: FILE-001, ADDR-010, ADDR-013, ADDR-004
"""初期データ一括投入の管理コマンド（FR-060。ADDR-010）。

  python manage.py load_initial_data 定義ファイルのパス [--reset]

- 受け付けるのは定義ファイルのパス1件と任意の --reset（既存データ（監査ログを除く）を削除してから投入する指定）だけ。
  それ以外・指定なしは E-060-01 とし、引数解析の誤りでも監査ログに失敗を1件記録してから終了する。
- 成功時は標準出力に成功の旨とデータ別の投入件数、終了コード0。失敗時は標準エラーに理由・何も投入しなかった旨・
  違反の全件（データ名・行番号・項目名・理由）、終了コード1。項目の値は示さない。
- 実行ごとに識別子を付けて LOG-05（ジョブ実行ログ）を出力する。
- Web 画面・Web API・サブプロセスから起動する経路は作らない。実行環境による --reset の制限は設けない（運用手順で統制）。
"""

import sys
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from common import clock
from common.logging import new_request_id, request_scope
from initial_data import loader

USAGE_MESSAGE = (
    "実行時の指定が誤っています。指定できる内容：定義ファイルのパス（1件）と、"
    "既存データ（監査ログを除く）を削除してから投入する指定（--reset）。"
)


# trace: FILE-001, ADDR-010
class _ArgumentError(Exception):
    pass


# trace: FILE-001, ADDR-010, ADDR-013, ADDR-004
class Command(BaseCommand):
    help = (
        "定義ファイル（UTF-8/JSON）から初期データを一括投入する。"
        "--reset で監査ログ以外の既存データを削除してから投入する。"
    )

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("definition_files", nargs="*", help="定義ファイルのパス（1件）")
        parser.add_argument(
            "--reset",
            action="store_true",
            help="既存データ（監査ログを除く）を削除してから投入する（検証環境の初期化用）",
        )

    def create_parser(self, prog_name: str, subcommand: str, **kwargs: Any) -> Any:
        kwargs["allow_abbrev"] = False  # --res 等の省略形や Django 共通オプションの前方一致を受け付けない
        parser = super().create_parser(prog_name, subcommand, **kwargs)

        def error(message: str) -> None:
            raise _ArgumentError(message)

        parser.error = error  # 引数解析の誤りを E-060-01 として扱う（Django 既定の引数エラー終了を使わない）
        return parser

    def run_from_argv(self, argv: list[str]) -> None:
        try:
            super().run_from_argv(argv)
        except _ArgumentError:
            started_at = clock.now_seconds()
            with request_scope(new_request_id()):
                self._fail(started_at, loader.LoadError("E-060-01", USAGE_MESSAGE))
            sys.exit(1)

    def handle(self, *args: Any, **options: Any) -> None:
        started_at = clock.now_seconds()
        with request_scope(new_request_id()):
            files = list(options.get("definition_files") or []) + [str(a) for a in args]
            if len(files) != 1:
                self._fail(started_at, loader.LoadError("E-060-01", USAGE_MESSAGE))
                raise CommandError("初期データ一括投入は失敗しました。", returncode=1)
            try:
                result = loader.run_load(files[0], bool(options.get("reset")), started_at)
            except loader.LoadError as error:
                self._fail(started_at, error)
                raise CommandError("初期データ一括投入は失敗しました。", returncode=1) from None
            loader.log_result(True, result.counts, [])
            self.stdout.write("初期データ一括投入が成功しました。")
            self.stdout.write(f"投入件数：{loader.counts_text(result.counts)}")

    def _fail(self, started_at: Any, error: loader.LoadError) -> None:
        loader.record_failure(started_at)
        loader.log_result(False, loader.zero_counts(), error.violations)
        self.stderr.write("初期データ一括投入は失敗しました。何も投入していません。")
        self.stderr.write(f"理由：{error.message}")
        if error.violations:
            self.stderr.write(f"違反（{len(error.violations)}件）：")
            for violation in error.violations:
                self.stderr.write(f"  {violation.text()}")
