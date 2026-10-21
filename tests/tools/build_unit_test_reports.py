"""単体テストの機械判定用成果物（coverage-summary / unit-test-evidence）を生成する。

入力は実際のテスト実行で生成した次の成果物だけとする。

- reports/unit-test/coverage.json（coverage.py の branch 有効なJSON）
- reports/unit-test/junit.xml（同一実行で出力したJUnit）
- tests/unit 配下のテストコードの trace 注釈（要件IDとテストの対応）
- reports/traceability/trace-map.json（要件IDの一覧。正本から生成した派生成果物）

値を推定・補完しない。coverage.py の行網羅は文網羅と同一指標のため lines と statements は同じ値を用いる。
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COVERAGE_JSON = ROOT / "reports" / "unit-test" / "coverage.json"
JUNIT_XML = ROOT / "reports" / "unit-test" / "junit.xml"
TRACE_MAP = ROOT / "reports" / "traceability" / "trace-map.json"
UNIT_TESTS = ROOT / "tests" / "unit"
COVERAGE_SUMMARY = ROOT / "reports" / "unit-test" / "coverage-summary.json"
EVIDENCE = ROOT / "reports" / "unit-test" / "unit-test-evidence.json"

TRACE_PATTERN = re.compile(r"^#\s*trace:\s*(.+)$")
DEF_PATTERN = re.compile(r"^def\s+([A-Za-z_][A-Za-z0-9_]*)")
ID_PATTERN = re.compile(
    r"\b(?:FR|NFR|SEC|CON|DR|IFR|UIR|UC|AC|ADDR|ADR|DBD|FILE|TASK|CR)-[A-Za-z0-9-]+\b"
)

UC_REASON = (
    "ユースケース（画面遷移を伴う利用者操作の流れ全体）であり、単体テストでは検証できない。"
    "結合試験・受入試験で検証する。"
)
OUT_OF_SCOPE_REASON = "機能要件定義書 2.3 の対象外機能であり、実装・テストの対象ではない。"
NFR_REASON = (
    "非機能要件定義書で定めた検証方法（性能試験・運用テスト・互換性／操作性テスト・"
    "脆弱性診断・構成／設定レビュー等）で検証する要件であり、単体テストでは検証できない。"
)


def coverage_metrics() -> dict[str, object]:
    """coverage.py の生JSONから statements / branches / functions / lines を求める。"""
    data = json.loads(COVERAGE_JSON.read_text(encoding="utf-8"))
    totals = data["totals"]
    statements = totals["covered_lines"] / totals["num_statements"] * 100
    branches = totals["covered_branches"] / totals["num_branches"] * 100
    functions_total = 0
    functions_covered = 0
    for file_data in data["files"].values():
        for region in file_data.get("functions", {}).values():
            summary = region["summary"]
            if summary["num_statements"] == 0:
                continue
            functions_total += 1
            if summary["covered_lines"] > 0:
                functions_covered += 1
    return {
        "statements": round(statements, 2),
        "branches": round(branches, 2),
        "functions": round(functions_covered / functions_total * 100, 2),
        "lines": round(statements, 2),
        "raw": {
            "covered_statements": totals["covered_lines"],
            "total_statements": totals["num_statements"],
            "covered_branches": totals["covered_branches"],
            "total_branches": totals["num_branches"],
            "covered_functions": functions_covered,
            "total_functions": functions_total,
        },
    }


def junit_results() -> tuple[dict[str, list[dict[str, str]]], dict[str, int]]:
    """JUnit XML からテスト関数ごとの実行結果を読み取る。"""
    root = ET.parse(JUNIT_XML).getroot()
    results: dict[str, list[dict[str, str]]] = defaultdict(list)
    summary = {"total": 0, "passed": 0, "failed": 0, "errors": 0, "skipped": 0}
    for testcase in root.iter("testcase"):
        summary["total"] += 1
        classname = testcase.attrib.get("classname", "")
        name = testcase.attrib.get("name", "")
        module = classname.split(".")[-1]
        base = name.split("[")[0]
        if testcase.find("failure") is not None:
            result = "FAIL"
            summary["failed"] += 1
        elif testcase.find("error") is not None:
            result = "FAIL"
            summary["errors"] += 1
        elif testcase.find("skipped") is not None:
            result = "SKIPPED"
            summary["skipped"] += 1
        else:
            result = "PASS"
            summary["passed"] += 1
        results[f"{module}::{base}"].append({"test": name, "result": result})
    return results, summary


def parse_trace_annotations() -> dict[str, list[tuple[str, str]]]:
    """テストコードの trace 注釈から、要件ID → （モジュール名, テスト関数名）を作る。"""
    mapping: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for path in sorted(UNIT_TESTS.glob("test_*.py")):
        module = path.stem
        header: list[str] = []
        pending: list[str] = []
        in_header = True
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            match = TRACE_PATTERN.match(stripped)
            if match:
                identifiers = ID_PATTERN.findall(match.group(1))
                if in_header:
                    header.extend(identifiers)
                else:
                    pending = list(identifiers)
                continue
            if in_header and stripped and not stripped.startswith("#"):
                in_header = False
            definition = DEF_PATTERN.match(line)
            if definition:
                name = definition.group(1)
                identifiers = pending or header
                if name.startswith("test_"):
                    for identifier in identifiers:
                        mapping[identifier].append((module, name))
                pending = []
    return mapping


def requirement_inventory() -> list[str]:
    """正本から生成済みのTrace Mapを用いて、要件IDの一覧を得る。"""
    data = json.loads(TRACE_MAP.read_text(encoding="utf-8"))
    return sorted(
        identifier
        for identifier, element in data["elements"].items()
        if element.get("kind") == "requirement"
    )


def not_unit_testable_reason(identifier: str) -> str:
    """単体テストで検証できない要件の理由を返す。"""
    if identifier.startswith("UC-"):
        return UC_REASON
    if identifier.startswith("FR-OUT"):
        return OUT_OF_SCOPE_REASON
    return NFR_REASON


def build_requirement_coverage(
    mapping: dict[str, list[tuple[str, str]]],
    results: dict[str, list[dict[str, str]]],
) -> list[dict[str, object]]:
    """要件IDごとに、対応する単体テストと実行結果を並べる。"""
    coverage: list[dict[str, object]] = []
    for identifier in requirement_inventory():
        entries = mapping.get(identifier, [])
        if not entries:
            coverage.append(
                {
                    "requirement": identifier,
                    "unit_testable": False,
                    "reason": not_unit_testable_reason(identifier),
                    "tests": [],
                }
            )
            continue
        tests: list[dict[str, str]] = []
        for module, name in sorted(set(entries)):
            for case in results.get(f"{module}::{name}", []):
                tests.append(
                    {
                        "path": f"tests/unit/{module}.py",
                        "test": case["test"],
                        "result": case["result"],
                    }
                )
        coverage.append({"requirement": identifier, "unit_testable": True, "tests": tests})
    return coverage


def main() -> int:
    """生成した成果物から coverage-summary.json と unit-test-evidence.json を書き出す。"""
    metrics = coverage_metrics()
    results, summary = junit_results()
    mapping = parse_trace_annotations()
    requirement_coverage = build_requirement_coverage(mapping, results)

    COVERAGE_SUMMARY.write_text(
        json.dumps(
            {
                "total": {
                    "statements": metrics["statements"],
                    "branches": metrics["branches"],
                    "functions": metrics["functions"],
                    "lines": metrics["lines"],
                },
                "source": "reports/unit-test/coverage.json",
                "tool": "coverage.py (branch=True)",
                "note": (
                    "coverage.py の行網羅は文網羅と同一指標のため lines と statements は同じ値。"
                    "functions は関数単位の実行有無（coverage.py の functions 領域）から算出。"
                ),
                "raw": metrics["raw"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8")) if EVIDENCE.exists() else {}
    evidence["test_summary"] = summary
    evidence["coverage"] = {
        "statements": metrics["statements"],
        "branches": metrics["branches"],
        "functions": metrics["functions"],
        "lines": metrics["lines"],
        "raw": metrics["raw"],
    }
    evidence["requirement_coverage"] = requirement_coverage
    EVIDENCE.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    report = {
        "summary": summary,
        "coverage": {key: metrics[key] for key in ("statements", "branches", "functions", "lines")},
    }
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
