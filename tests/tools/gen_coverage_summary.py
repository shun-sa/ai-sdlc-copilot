"""coverage.py の JSON を Unit Test Validator 期待形式へ変換する。

Validator (`.github/skills/unit-test/script/validate_unit_test.py`) は
`reports/unit-test/coverage-summary.json` の `total` に
statements / branches / functions / lines (pct) を要求する。

coverage.py は statements / branches / lines を計測するが functions は計測しない。
そのため functions coverage は AST で関数定義を抽出し、
coverage の executed_lines と突き合わせて算出する
(関数本体のいずれかの行が実行されていれば covered とみなす)。
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path


def _function_coverage(files: dict) -> tuple[int, int]:
    total = 0
    covered = 0
    for rel_path, info in files.items():
        source_path = Path(rel_path)
        if not source_path.exists():
            continue
        try:
            tree = ast.parse(source_path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        executed = set(info.get("executed_lines", []))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            body_lines = {
                child.lineno
                for stmt in node.body
                for child in ast.walk(stmt)
                if hasattr(child, "lineno")
            }
            if not body_lines:
                continue
            total += 1
            if body_lines & executed:
                covered += 1
    return covered, total


def _pct(covered: int, total: int) -> float:
    if total == 0:
        return 100.0
    return round(covered / total * 100, 2)


def main() -> int:
    coverage_json = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
        "reports/unit-test/coverage.json"
    )
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(
        "reports/unit-test/coverage-summary.json"
    )

    data = json.loads(coverage_json.read_text(encoding="utf-8"))
    files = data.get("files", {})
    totals = data.get("totals", {})

    statements_pct = float(totals.get("percent_covered", 0.0))

    num_branches = int(totals.get("num_branches", 0))
    covered_branches = int(totals.get("covered_branches", 0))
    branches_pct = _pct(covered_branches, num_branches)

    func_covered, func_total = _function_coverage(files)
    functions_pct = _pct(func_covered, func_total)

    # coverage.py では statement == line 単位。lines は statements と同義で扱う。
    lines_pct = statements_pct

    summary = {
        "total": {
            "statements": round(statements_pct, 2),
            "branches": branches_pct,
            "functions": functions_pct,
            "lines": round(lines_pct, 2),
        },
        "_detail": {
            "functions_covered": func_covered,
            "functions_total": func_total,
            "branches_covered": covered_branches,
            "branches_total": num_branches,
        },
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary["total"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
