"""coverage.py の JSON レポートから単体テスト用の Coverage Summary を生成する。

Unit Test Skill の Validator（validate_unit_test.py）が読み込む
reports/unit-test/coverage-summary.json を、同一実行で出力した生の
coverage.json（branch 有効）だけから機械的に導出する。値の推定・補完は行わない。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def _ratio(covered: int, total: int) -> float:
    """被覆率（%）を求める（対象0件は100%とする）。"""
    return 100.0 if total == 0 else round(covered * 100 / total, 2)


def _metric(covered: int, total: int) -> dict[str, float | int]:
    """Istanbul 形式の指標（total・covered・pct）を組み立てる。"""
    return {"total": total, "covered": covered, "pct": _ratio(covered, total)}


def _function_counts(files: dict) -> tuple[int, int]:
    """関数の総数と、1文以上実行された関数の数を数える。"""
    total = 0
    covered = 0
    for file_data in files.values():
        for function in file_data.get("functions", {}).values():
            summary = function.get("summary", {})
            if summary.get("num_statements", 0) == 0:
                continue
            total += 1
            if summary.get("covered_lines", 0) > 0:
                covered += 1
    return covered, total


def build_summary(coverage: dict) -> dict:
    """coverage.py の JSON から Coverage Summary を組み立てる。"""
    if not coverage.get("meta", {}).get("branch_coverage"):
        raise ValueError("branch coverage is not enabled in the coverage report")
    totals = coverage["totals"]
    functions_covered, functions_total = _function_counts(coverage.get("files", {}))
    statements = _metric(totals["covered_lines"], totals["num_statements"])
    return {
        "total": {
            "statements": statements,
            "branches": _metric(totals["covered_branches"], totals["num_branches"]),
            "functions": _metric(functions_covered, functions_total),
            "lines": dict(statements),
        },
        "source": {
            "format": "coverage.py",
            "version": coverage["meta"]["version"],
            "generated_at": coverage["meta"]["timestamp"],
        },
    }


def main(argv: list[str]) -> int:
    """coverage.json を読み込み coverage-summary.json を書き出す。"""
    source = Path(argv[1] if len(argv) > 1 else "reports/unit-test/coverage.json")
    target = Path(argv[2] if len(argv) > 2 else "reports/unit-test/coverage-summary.json")
    coverage = json.loads(source.read_text(encoding="utf-8"))
    summary = build_summary(coverage)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary["total"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
