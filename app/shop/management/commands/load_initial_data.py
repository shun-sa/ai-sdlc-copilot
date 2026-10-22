# trace: ADDR-010, FILE-001
"""初期データ一括投入コマンド（FR-060）。運用者がサーバー上で実行する。"""
from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from shop.services import seeding
from shop.services.seeding import DATA_LABELS, SeedFileError, SeedLoader, read_definition_file

EXIT_SUCCESS = 0
EXIT_FAILURE = 1


# trace: ADDR-010
class Command(BaseCommand):
    """定義ファイルから初期データを一括投入する。"""

    help = "定義ファイル（JSON、UTF-8）から初期データを一括投入する（FR-060）。"

    def add_arguments(self, parser: CommandParser) -> None:
        """引数（定義ファイルのパス）とオプション（全削除指定）を定義する。"""
        parser.add_argument("path", nargs="?", default=None, help="定義ファイルのパス")
        parser.add_argument(
            "--reset",
            action="store_true",
            help="監査ログ以外の全データを削除してから投入する（検証環境の初期化専用）",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        """読込・検証・登録を行い、終了コードを制御する。"""
        path = options["path"]
        reset = bool(options["reset"])

        if not path:
            self._fail(
                "コマンドの指定が誤っています。定義ファイルのパスを指定してください"
                "（オプションは --reset のみ指定できます）。",
                "コマンドの指定が誤っています",
            )
            return

        try:
            data = read_definition_file(path)
        except FileNotFoundError:
            self._fail(f"定義ファイルが見つからない、または読み取れません：{path}", "定義ファイルを読み取れません")
            return
        except SeedFileError as exc:
            self._fail(f"定義ファイルを解釈できません：{exc}", "定義ファイルを解釈できません")
            return

        loader = SeedLoader(data, reset=reset)
        loader.validate()
        if loader.violations:
            self.stderr.write("定義ファイルに違反があるため、削除も投入も行いませんでした。")
            for violation in loader.violations:
                self.stderr.write(violation.format())
            self._fail(f"違反 {len(loader.violations)} 件", "定義ファイルに違反があります", write_stderr=False)
            return

        try:
            result = loader.load()
        except Exception:
            self._fail(
                "データベースの処理に失敗したため、削除も投入も行いませんでした。",
                "データベースの処理に失敗しました",
            )
            return
        for key, label in DATA_LABELS.items():
            self.stdout.write(f"{label}: {result.counts.get(key, 0)} 件")
        raise SystemExit(EXIT_SUCCESS)

    def _fail(self, stderr_message: str, audit_detail: str, write_stderr: bool = True) -> None:
        """失敗を記録し、終了コード0以外で終了する。"""
        if write_stderr:
            self.stderr.write(stderr_message)
            self.stderr.write("何も投入しませんでした。")
        seeding.record_failure(audit_detail)
        raise SystemExit(EXIT_FAILURE)
