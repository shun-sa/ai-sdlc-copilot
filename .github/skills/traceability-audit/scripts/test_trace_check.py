#!/usr/bin/env python3

"""
Unit tests for trace_check.py

Run:
    python .github/skills/traceability-audit/scripts/test_trace_check.py

No third-party test framework is required.
PyYAML is required because trace_check.py imports yaml.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import copy
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
CHECKER_PATH = SCRIPT_DIR / "trace_check.py"
POLICY_PATH = SCRIPT_DIR.parent / "policy" / "traceability-policy.yaml"

SPEC = importlib.util.spec_from_file_location("trace_check", CHECKER_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Unable to import checker: {CHECKER_PATH}")
checker = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = checker  # dataclassの型解決に必要
SPEC.loader.exec_module(checker)


BASE_FILES: dict[str, str] = {
    "docs/requirements/functional_requirements.md": """---
document_type: "機能要件定義書"
---

# 機能要件定義書

<!-- 記入例: FR-999 はコメントなので定義として読まない -->

| ID | 大分類 | 機能名 | 概要 |
|---|---|---|---|
| FR-001 | 販売 | クーポン適用 | クーポンを適用する |
| FR-002 | 販売 | 期限切れの拒否 | 期限切れは適用しない |

### 6.1 FR-001：クーポン適用

- 入力検証は要件NFR-SEC-001に従う。
""",
    "docs/requirements/non_functional_requirements.md": """# 非機能要件定義書

| ID | 区分 | 要件項目 | 要件内容 |
|---|---|---|---|
| NFR-SEC-001 | セキュリティ | 入力検証 | サーバー側で検証する |
""",
    "docs/requirements/acceptance.md": """# 受入条件

- AC-001: 期限切れを入力するとエラーが出る（FR-002）
""",
    "docs/addr/ADDR-001-voucher.md": """---
addr_id: "ADDR-001"
title: "クーポンの検証をサービス層で行う"
design_type: "画面"
status: "ACTIVE"
---

# ADDR：クーポンの検証をサービス層で行う

## 2. 関連要件・参照成果物

| 区分 | 参照先 | 関係 |
|---|---|---|
| 要件 | FR-001, FR-002, NFR-SEC-001 | 検証の場所 |
| データモデル | DBD-001 | 期限を参照 |
""",
    "docs/addr/ADDR-002-old.md": """---
addr_id: "ADDR-002"
title: "旧方式"
status: "SUPERSEDED"
---

# ADDR：旧方式

## 2. 関連要件・参照成果物

| 区分 | 参照先 | 関係 |
|---|---|---|
| 要件 | FR-002 | ADDR-001 に置き換えた |
""",
    "docs/architecture/db-logical-design.md": """# DB論理設計書

### DBD-001 Voucher

- 関連要件: FR-001, FR-002
""",
    "docs/architecture/implementation-task-list.md": """# 実装タスク一覧

| Task ID | Title | Related Requirement | Related ADR | Depends On |
| --- | --- | --- | --- | --- |
| TASK-001 | モデル | FR-001 | DBD-001 | None |
| TASK-002 | 適用 | FR-001, FR-002 | ADDR-001 | TASK-001 |
""",
    "app/vouchers/models.py": """# trace: DBD-001
\"\"\"クーポン。\"\"\"


class Voucher:
    pass
""",
    "app/vouchers/services.py": """# trace: ADDR-001
\"\"\"クーポンの適用。\"\"\"


def apply_voucher(total, voucher):
    return total


def _helper():
    return None
""",
    "app/templates/vouchers/apply.html": """{# trace: ADDR-001 #}
<p>{{ message }}</p>
""",
    "tests/unit/test_voucher.py": """# trace: FR-001, FR-002, NFR-SEC-001, ADDR-001
\"\"\"単体テスト。\"\"\"


# trace: FR-001, ADDR-001
def test_apply():
    assert True


# trace: FR-002, NFR-SEC-001, ADDR-001
@decorator(
    "multi-line",
)
def test_expired():
    assert True
""",
}


def run_checker(root: Path, *args: str) -> tuple[int, dict[str, Any]]:
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        policy = root / "test-policy.json"
        code = checker.main(["--repo-root", str(root), "--policy", str(policy if policy.is_file() else POLICY_PATH), *args])
    result_path = root / "reports" / "traceability" / "validation-result.json"
    result = json.loads(result_path.read_text(encoding="utf-8")) if result_path.is_file() else {}
    report_path = root / "reports" / "traceability" / "traceability-report.json"
    if report_path.is_file():
        try:
            result["report"] = json.loads(report_path.read_text(encoding="utf-8"))
        except ValueError:
            result["report"] = {}
    return code, result


class TraceCheckTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.write_files(BASE_FILES)
        policy = checker.load_policy(POLICY_PATH)
        policy["integration"]["preserve_architecture_gate"] = False
        self.write_files({"test-policy.json": json.dumps(policy)})

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write_files(self, files: dict[str, str]) -> None:
        for rel, text in files.items():
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")

    def issues(self, result: dict[str, Any], check: str, level: str | None = None) -> list[dict[str, Any]]:
        return [
            issue
            for issue in result["report"]["issues"]
            if issue["check"] == check and (level is None or issue["level"] == level)
        ]

    # ---------- 正常系 ----------

    def test_base_repository_passes_every_scope(self) -> None:
        for scope in checker.SCOPES:
            if scope == "FULL":
                continue
            with self.subTest(scope=scope):
                code, result = run_checker(self.root, "--scope", scope)
                fails = [i for i in result["report"]["issues"] if i["level"] == "FAIL"]
                self.assertEqual(code, 0, fails)

    def test_full_passes_and_writes_derived_artifacts(self) -> None:
        code, result = run_checker(self.root, "--scope", "FULL")
        self.assertEqual(code, 0, result.get("errors"))
        out = self.root / "reports" / "traceability"
        for name in (
            "trace-map.json",
            "traceability-report.json",
            "traceability-report.md",
            "requirements-traceability-matrix.md",
            "requirements-traceability-matrix.csv",
            "requirements-traceability-check.md",
            "addr-index.md",
        ):
            self.assertTrue((out / name).is_file(), name)
        trace_map = json.loads((out / "trace-map.json").read_text(encoding="utf-8"))
        self.assertEqual(trace_map["audit_scope"], "FULL")
        self.assertNotIn("FR-999", trace_map["elements"])

    def test_title_comes_from_name_column_and_ids_next_to_japanese(self) -> None:
        run_checker(self.root, "--scope", "IMPLEMENTATION")
        trace_map = json.loads(
            (self.root / "reports" / "traceability" / "trace-map.json").read_text(encoding="utf-8")
        )
        self.assertEqual(trace_map["elements"]["FR-001"]["title"], "クーポン適用")
        self.assertIn("NFR-SEC-001", trace_map["elements"]["FR-001"]["references"])
        self.assertEqual(trace_map["elements"]["ADDR-001"]["related_requirements"], ["FR-001", "FR-002", "NFR-SEC-001"])

    def test_matrix_links_requirement_to_code_through_addr(self) -> None:
        run_checker(self.root, "--scope", "UNIT_TEST")
        matrix = (self.root / "reports" / "traceability" / "requirements-traceability-matrix.md").read_text(
            encoding="utf-8"
        )
        row = next(line for line in matrix.splitlines() if line.startswith("| FR-002 "))
        self.assertIn("app/vouchers/services.py", row)
        self.assertIn("tests/unit/test_voucher.py::test_expired", row)
        self.assertNotIn("ADDR-002", row)

    # ---------- C01〜C11 ----------

    def test_c01_undefined_id_in_code_routes_to_implementation(self) -> None:
        self.write_files({"app/vouchers/services.py": "# trace: ADDR-099\ndef f():\n    pass\n"})
        code, result = run_checker(self.root, "--scope", "IMPLEMENTATION")
        self.assertEqual(code, 1)
        issue = self.issues(result, "C01")[0]
        self.assertEqual(issue["classification"], "INVALID_ADR_REFERENCE")
        self.assertEqual(issue["route"], "IMPLEMENTATION")

    def test_c01_duplicate_definition_across_files(self) -> None:
        self.write_files({"docs/requirements/other.md": "| ID | 機能名 |\n|---|---|\n| FR-001 | 重複 |\n"})
        code, result = run_checker(self.root, "--scope", "ARCHITECTURE")
        self.assertEqual(code, 1)
        self.assertEqual(self.issues(result, "C01")[0]["classification"], "DUPLICATE_ID")

    def test_c02_superseded_addr_in_code(self) -> None:
        self.write_files({"app/vouchers/services.py": "# trace: ADDR-002\ndef f():\n    pass\n"})
        code, result = run_checker(self.root, "--scope", "IMPLEMENTATION")
        self.assertEqual(code, 1)
        self.assertTrue(self.issues(result, "C02", "FAIL"))

    def test_c03_addr_without_requirements(self) -> None:
        self.write_files(
            {
                "docs/addr/ADDR-003-x.md": '---\naddr_id: "ADDR-003"\nstatus: "ACTIVE"\n---\n\n# ADDR：x\n\n## 2. 関連要件・参照成果物\n\n| 区分 | 参照先 |\n|---|---|\n| 要件 | なし |\n'
            }
        )
        code, result = run_checker(self.root, "--scope", "ARCHITECTURE")
        self.assertEqual(code, 1)
        self.assertEqual(self.issues(result, "C03")[0]["classification"], "ADR_REQUIREMENT_MISSING")

    def test_c04_task_without_source(self) -> None:
        self.write_files(
            {
                "docs/architecture/implementation-task-list.md": "| Task ID | Title | Related Requirement |\n| --- | --- | --- |\n| TASK-001 | x | None |\n"
            }
        )
        code, result = run_checker(self.root, "--scope", "ARCHITECTURE")
        self.assertEqual(code, 1)
        self.assertTrue(self.issues(result, "C04"))

    def test_c05_missing_header_and_disallowed_kind(self) -> None:
        self.write_files(
            {
                "app/vouchers/models.py": '"""docstringの後の注釈は先頭注釈ではない"""\n# trace: DBD-001\nclass Voucher:\n    pass\n',
                "app/vouchers/services.py": "# trace: FR-001, TASK-001, ADDR-1\ndef f():\n    pass\n",
            }
        )
        code, result = run_checker(self.root, "--scope", "IMPLEMENTATION")
        self.assertEqual(code, 1)
        classes = {issue["classification"] for issue in self.issues(result, "C05")}
        self.assertEqual(classes, {"TRACE_ANNOTATION_MISSING", "TRACE_ANNOTATION_INVALID"})
        messages = " ".join(issue["message"] for issue in self.issues(result, "C05"))
        self.assertIn("FR-001", messages)
        self.assertIn("TASK-001", messages)
        self.assertIn("ADDR-1", messages)

    def test_c06_symbol_annotation_rules(self) -> None:
        self.write_files(
            {
                "app/vouchers/services.py": "# trace: ADDR-001, DBD-001\n\n# trace: ADDR-001\ndef a():\n    pass\n\n\ndef b():\n    pass\n\n\n# trace: ADDR-002\ndef c():\n    pass\n"
            }
        )
        code, result = run_checker(self.root, "--scope", "IMPLEMENTATION")
        self.assertEqual(code, 1)
        classes = sorted(issue["classification"] for issue in self.issues(result, "C06"))
        self.assertEqual(classes, ["SYMBOL_ANNOTATION_INCONSISTENT", "SYMBOL_ANNOTATION_MISSING"])

    def test_c06_not_required_for_single_id_file_and_private_symbols(self) -> None:
        code, result = run_checker(self.root, "--scope", "IMPLEMENTATION")
        self.assertEqual(code, 0)
        self.assertFalse(self.issues(result, "C06"))

    def test_c07_test_without_requirement(self) -> None:
        self.write_files({"tests/unit/test_voucher.py": "# trace: ADDR-001\ndef test_x():\n    assert True\n"})
        code, result = run_checker(self.root, "--scope", "UNIT_TEST")
        self.assertEqual(code, 1)
        self.assertEqual(self.issues(result, "C07")[0]["route"], "UNIT_TEST")

    def test_c09_c10_warn_during_development_and_fail_at_full(self) -> None:
        self.write_files(
            {
                "docs/addr/ADDR-003-y.md": '---\naddr_id: "ADDR-003"\nstatus: "ACTIVE"\n---\n\n# ADDR：y\n\n## 2. 関連要件・参照成果物\n\n| 区分 | 参照先 |\n|---|---|\n| 要件 | FR-001 |\n',
                "tests/unit/test_voucher.py": "# trace: FR-001, ADDR-001\ndef test_apply():\n    assert True\n",
            }
        )
        code, result = run_checker(self.root, "--scope", "UNIT_TEST")
        self.assertEqual(code, 0)
        self.assertTrue(self.issues(result, "C09", "WARN"))
        self.assertTrue(self.issues(result, "C10", "WARN"))
        code, result = run_checker(self.root, "--scope", "FULL")
        self.assertEqual(code, 1)
        self.assertTrue(self.issues(result, "C09", "FAIL"))
        self.assertTrue(self.issues(result, "C10", "FAIL"))

    def test_c11_detects_hand_edited_matrix(self) -> None:
        run_checker(self.root, "--scope", "FULL")
        matrix = self.root / "reports" / "traceability" / "requirements-traceability-matrix.md"
        matrix.write_text(matrix.read_text(encoding="utf-8") + "| FR-100 | 手で追加 |\n", encoding="utf-8")
        code, result = run_checker(self.root, "--scope", "FULL", "--no-write")
        self.assertEqual(code, 1)
        self.assertTrue(any("[C11]" in error for error in result["errors"]))

    def test_junit_results_feed_check_table(self) -> None:
        self.write_files(
            {
                "reports/unit-test/junit.xml": """<testsuites><testsuite>
<testcase classname="tests.unit.test_voucher" name="test_apply"/>
<testcase classname="tests.unit.test_voucher" name="test_expired"><failure message="x"/></testcase>
</testsuite></testsuites>"""
            }
        )
        checker.main(["--repo-root", str(self.root), "--policy", str(self.root / "test-policy.json"), "--record-test-run", "unit_test"])
        run_checker(self.root, "--scope", "UNIT_TEST")
        table = (self.root / "reports" / "traceability" / "requirements-traceability-check.md").read_text(
            encoding="utf-8"
        )
        fr001 = next(line for line in table.splitlines() if line.startswith("| FR-001 "))
        fr002 = next(line for line in table.splitlines() if line.startswith("| FR-002 "))
        self.assertIn("充足", fr001)
        self.assertIn("不合格", fr002)

    def test_bad_policy_returns_2(self) -> None:
        run_checker(self.root, "--scope", "FULL")
        bad = self.root / "policy.yaml"
        bad.write_text("version: 2\n", encoding="utf-8")
        buffer = io.StringIO()
        with contextlib.redirect_stderr(buffer):
            code = checker.main(["--repo-root", str(self.root), "--policy", str(bad), "--scope", "FULL"])
        self.assertEqual(code, 2)
        result = json.loads((self.root / "reports/traceability/validation-result.json").read_text(encoding="utf-8"))
        self.assertEqual(result["status"], "FAIL")

    def audit(self, scope="FULL"):
        policy = checker.load_policy(self.root / "test-policy.json")
        audit = checker.Auditor(self.root, policy, scope)
        audit.load()
        audit.check_all(None)
        return audit

    def record(self, role="unit_test"):
        checker.record_test_run(self.root, checker.load_policy(self.root / "test-policy.json"), role)

    def check_row(self, identifier="FR-001"):
        audit = self.audit("UNIT_TEST")
        return next(row for row in audit.check_rows(audit.requirement_rows()) if row["要件ID"] == identifier)

    def test_index_and_background_and_old_features_are_not_definitions(self):
        self.write_files({
            "docs/requirements/requirements.md": "- FR-001: 派生索引\n- FR-999: 旧索引\n",
            "docs/requirements/features/FR-001.md": "# FR-001 古い内容\n",
            "docs/requirements/business_requirements.md": "- FR-001: 背景\n",
            "docs/requirements/glossary.md": "- FR-001: 用語\n",
            "docs/requirements/requirements_quality_checklist.md": "- FR-001: 検査\n",
        })
        audit = self.audit("REQUIREMENTS")
        self.assertFalse(audit.duplicates)
        self.assertNotIn("FR-999", audit.elements)
        self.assertFalse(audit.issues)

    def test_real_file_metadata_links_code_and_addr_and_task(self):
        self.write_files({
            "docs/architecture/files/FILE-001.md": "# ファイル定義書\n| 項目 | 内容 |\n| --- | --- |\n| File Interface ID | FILE-001 |\n\n## 関連\nADDR-001\n",
            "app/vouchers/services.py": "# trace: FILE-001\ndef apply_voucher():\n    return True\n",
            "docs/architecture/implementation-task-list.md": "| Task ID | Title | Related Requirement | Related ADR |\n| --- | --- | --- | --- |\n| TASK-001 | 出力 | FR-001 | FILE-001 |\n",
        })
        audit = self.audit()
        self.assertIn("FILE-001", audit.elements)
        row = next(row for row in audit.requirement_rows() if row["要件ID"] == "FR-001")
        self.assertIn("app/vouchers/services.py", row["コード"])
        self.assertIn("TASK-001", row["TASK"])
        addr = next(row for row in audit.addr_rows() if row["ADDR"] == "ADDR-001")
        self.assertIn("app/vouchers/services.py", addr["コード"])
        self.assertFalse([issue for issue in audit.issues if issue.check == "C09"])

    def test_db_entity_can_link_to_addr_without_repeating_requirement(self):
        self.write_files({"docs/architecture/db-logical-design.md": "### DBD-001 Voucher\nADDR-001\n", "app/vouchers/services.py": "# trace: DBD-001\ndef run():\n    pass\n", "app/templates/vouchers/apply.html": "{# trace: DBD-001 #}\n<p>ok</p>\n"})
        audit = self.audit()
        row = next(row for row in audit.requirement_rows() if row["要件ID"] == "FR-001")
        self.assertIn("app/vouchers/services.py", row["コード"])
        self.assertFalse([issue for issue in audit.issues if issue.check == "C09"])

    def test_canonical_addr_non_requirement_rows_do_not_supply_requirement_link(self):
        original = BASE_FILES["docs/addr/ADDR-001-voucher.md"]
        self.write_files({"docs/addr/ADDR-001-voucher.md": original.replace("| 要件 | FR-001, FR-002, NFR-SEC-001 |", "| 要件 | AC-001 |").replace("| データモデル | DBD-001 |", "| データモデル | FR-001 |")})
        audit = self.audit("ARCHITECTURE")
        self.assertFalse(audit.elements["ADDR-001"].req_refs)
        self.assertTrue([issue for issue in audit.issues if issue.check == "C03"])

    def test_uc_is_requirement_and_ac_is_separate(self):
        self.write_files({"docs/requirements/use_case_user_story_list.md": "| UC ID | 名称 |\n| --- | --- |\n| UC-001 | 注文 |\n", "docs/requirements/acceptance.md": "- AC-001: 条件 UC-001\n"})
        audit = self.audit("REQUIREMENTS")
        self.assertEqual(audit.elements["UC-001"].kind, "requirement")
        self.assertEqual(audit.elements["AC-001"].kind, "acceptance")
        row = next(row for row in audit.requirement_rows() if row["要件ID"] == "UC-001")
        self.assertEqual(row["受入条件"], ["AC-001"])

    def test_private_definition_also_requires_own_annotation(self):
        self.write_files({"app/vouchers/services.py": "# trace: ADDR-001, DBD-001\n\n# trace: ADDR-001\ndef public():\n    pass\n\ndef _private():\n    pass\n"})
        audit = self.audit("IMPLEMENTATION")
        self.assertTrue(any(issue.check == "C06" and "_private" in issue.message for issue in audit.issues))

    def test_nonempty_init_is_checked_and_empty_init_is_exempt(self):
        self.write_files({"app/empty/__init__.py": "", "app/real/__init__.py": "VALUE = 1\n"})
        audit = self.audit("IMPLEMENTATION")
        self.assertTrue(any(issue.check == "C05" and issue.location == "app/real/__init__.py" for issue in audit.issues))
        self.assertNotIn("app/empty/__init__.py", [source.path for source in audit.sources])

    def test_ac_only_test_is_not_requirement_coverage(self):
        self.write_files({"tests/unit/test_voucher.py": "# trace: AC-001\ndef test_case():\n    assert True\n"})
        self.assertTrue(any(issue.check == "C07" for issue in self.audit("UNIT_TEST").issues))

    def test_plan_malformed_or_wrong_id_kind_or_duplicates_fail(self):
        for payload in ("not-json", {"cases": [{"case_id": "CASE-001", "requirement_id": "ADDR-001", "related_adr": "FR-001"}]}, {"cases": [{"case_id": "CASE-001"}, {"case_id": "CASE-001"}]}):
            with self.subTest(payload=payload):
                self.write_files({"reports/integration-test/integration-test-plan.json": json.dumps(payload) if isinstance(payload, dict) else payload})
                self.assertTrue(any(issue.check == "C01" and issue.route == "INTEGRATION_TEST" for issue in self.audit().issues))

    def test_retired_addr_in_plan_and_task_fails(self):
        self.write_files({"reports/integration-test/integration-test-plan.json": json.dumps({"cases": [{"case_id": "CASE-001", "requirement_id": "FR-001", "related_adr": ["ADDR-002"]}]}), "docs/architecture/implementation-task-list.md": "| Task ID | Title | Related Requirement |\n| --- | --- | --- |\n| TASK-001 | 古い判断 | ADDR-002 |\n"})
        issues = [issue for issue in self.audit().issues if issue.check == "C02"]
        self.assertTrue(any(issue.route == "INTEGRATION_TEST" for issue in issues))
        self.assertTrue(any(issue.route == "ARCHITECTURE" for issue in issues))

    def test_junit_module_names_do_not_match_by_basename(self):
        source = checker.SourceFile("tests/unit/test_voucher.py", "unit_test")
        symbol = checker.Symbol("test_apply", 1)
        self.assertEqual("NOT_RUN", checker.symbol_status(source, symbol, [("tests.integration.test_voucher", "test_apply", "PASS")]))
        self.assertEqual("PASS", checker.symbol_status(source, symbol, [("tests.unit.test_voucher", "test_apply", "PASS")]))

    def test_mixed_pass_and_skipped_parameters_are_not_pass(self):
        source = checker.SourceFile("tests/unit/test_voucher.py", "unit_test")
        symbol = checker.Symbol("test_apply", 1)
        results = [("tests.unit.test_voucher", "test_apply", "PASS"), ("tests.unit.test_voucher", "test_apply", "SKIP")]
        self.assertEqual("SKIP", checker.symbol_status(source, symbol, results))

    def test_unrecorded_and_stale_test_versions_are_not_fulfilled(self):
        self.write_files({"reports/unit-test/junit.xml": '<testsuite><testcase classname="tests.unit.test_voucher" name="test_apply"/></testsuite>'})
        self.assertEqual("未確認", self.check_row()["判定"])
        self.record()
        self.assertEqual("充足", self.check_row()["判定"])
        self.write_files({"app/vouchers/models.py": BASE_FILES["app/vouchers/models.py"] + "\nCHANGED = True\n"})
        self.assertEqual("未確認", self.check_row()["判定"])

    def test_changed_junit_invalidates_execution_binding(self):
        path = "reports/unit-test/junit.xml"
        self.write_files({path: '<testsuite><testcase classname="tests.unit.test_voucher" name="test_apply"/></testsuite>'})
        self.record()
        self.write_files({path: '<testsuite><testcase classname="tests.unit.test_voucher" name="test_apply" time="1"/></testsuite>'})
        self.assertEqual("未確認", self.check_row()["判定"])

    def test_design_link_alone_is_not_implementation_fulfillment(self):
        for path in ("app/vouchers/models.py", "app/vouchers/services.py", "app/templates/vouchers/apply.html"):
            (self.root / path).unlink()
        self.write_files({"reports/unit-test/junit.xml": '<testsuite><testcase classname="tests.unit.test_voucher" name="test_apply"/></testsuite>'})
        self.record()
        self.assertEqual("未確認", self.check_row()["判定"])
        self.assertIn("実装へのリンクなし", self.check_row()["未対応事項"])

    def test_root_and_nested_dependency_templates_are_excluded(self):
        self.write_files({".venv/lib/templates/widget.html": "<p>vendor</p>", "node_modules/lib/templates/widget.html": "<p>vendor</p>", "app/vendor/.venv/templates/widget.html": "<p>vendor</p>"})
        self.assertFalse(any("vendor" in source.path or "node_modules" in source.path or ".venv" in source.path for source in self.audit().sources))

    def test_template_trace_must_precede_content_not_merely_be_in_first_five_lines(self):
        self.write_files({"app/templates/vouchers/apply.html": "<h1>already content</h1>\n{# trace: ADDR-001 #}\n"})
        self.assertTrue(any(issue.check == "C05" and "apply.html" in issue.location for issue in self.audit("IMPLEMENTATION").issues))
        self.write_files({"app/templates/vouchers/apply.html": "<!--\nlicense\nline\nline\nline\n-->\n{# trace: ADDR-001 #}\n<p>ok</p>\n"})
        self.assertFalse(any(issue.check == "C05" and "apply.html" in issue.location for issue in self.audit("IMPLEMENTATION").issues))

    def test_native_addr_keeps_canonical_status_not_legacy_accepted(self):
        self.write_files({"docs/addr/ADDR-001-voucher.md": BASE_FILES["docs/addr/ADDR-001-voucher.md"].replace('status: "ACTIVE"', 'status: "Accepted"')})
        self.assertTrue(any(issue.check == "C03" for issue in self.audit("ARCHITECTURE").issues))

    def test_unresolved_loop_results_are_visible_without_perpetual_c11_invalidation(self):
        directory = SCRIPT_DIR.parents[3] / ".github/skills/failure-triage/scripts"
        sys.path.insert(0, str(directory))
        self.addCleanup(sys.path.remove, str(directory))
        import loop_control as control
        configuration = (SCRIPT_DIR.parents[3] / control.POLICY).read_text(encoding="utf-8")
        self.write_files({control.POLICY: configuration, "reports/loop-control/check.json": json.dumps({"status": "FAIL", "errors": ["design unresolved"]})})
        signature = {"origin_phase": "ARCHITECTURE", "classification": "ADR_REQUIRED", "artifact": "docs/addr/ADDR-001.md", "requirement_reference": "FR-001", "test_case": "", "stable_error_type": "decision_missing"}
        event = {"signature": signature, "impact": "未確定判断あり", "recommended_route": "ADDR", "validation_result": "reports/loop-control/check.json"}
        for cycle in range(4):
            control.record(self.root, {**event, "cycle": cycle, "run_id": f"actual-{cycle}", "repair": "実修正・再検査" if cycle else ""})
        status, result = run_checker(self.root, "--scope", "UNIT_TEST")
        self.assertEqual(status, 0)
        self.assertTrue(result["report"]["workflow_unresolved"])
        self.assertEqual(self.check_row()["判定"], "未解決あり")
        control.record(self.root, {**event, "action": "OBSERVE", "cycle": 3, "run_id": "observed-again"})
        self.assertEqual(run_checker(self.root, "--scope", "UNIT_TEST", "--no-write")[0], 0)

    def test_no_write_detects_tampering_in_every_output_without_repair(self):
        run_checker(self.root, "--scope", "FULL")
        directory = self.root / "reports/traceability"
        outputs = {path: path.read_bytes() for path in directory.iterdir() if path.name != "validation-result.json"}
        for path, original in outputs.items():
            with self.subTest(path=path.name):
                path.write_bytes(original + b"tampered\n")
                status, result = run_checker(self.root, "--scope", "FULL", "--no-write")
                self.assertEqual(status, 1)
                self.assertTrue(any(issue["check"] == "C11" for issue in result["issues"]))
                self.assertEqual(original + b"tampered\n", path.read_bytes())
                path.write_bytes(original)
        self.assertEqual(0, run_checker(self.root, "--scope", "FULL", "--no-write")[0])

    def test_source_change_invalidates_derived_map(self):
        run_checker(self.root, "--scope", "FULL")
        self.write_files({"app/vouchers/services.py": BASE_FILES["app/vouchers/services.py"] + "\nVALUE = 2\n"})
        status, result = run_checker(self.root, "--scope", "FULL", "--no-write")
        self.assertEqual(status, 1)
        self.assertTrue(any(issue["check"] == "C11" for issue in result["issues"]))

    def test_invalid_policy_paths_or_prefixes_return_2(self):
        policy = checker.load_policy(POLICY_PATH)
        for changes in ({"outputs": {"dir": "../escape"}}, {"outputs": []}, {"ids": {**policy["ids"], "requirement": "FR"}}):
            candidate = copy.deepcopy(policy)
            candidate.update(changes)
            self.write_files({"bad-policy.json": json.dumps(candidate)})
            with contextlib.redirect_stderr(io.StringIO()):
                status = checker.main(["--repo-root", str(self.root), "--policy", "bad-policy.json", "--scope", "FULL"])
            self.assertEqual(status, 2)

    def test_commit_ids_must_be_at_start_and_exist(self):
        original = checker.git
        self.addCleanup(setattr, checker, "git", original)
        checker.git = lambda *args: "a\x1fmessage [TASK-001]\nb\x1f[TASK-001] implement\nc\x1f[TASK-999] unknown\n"
        audit = self.audit("IMPLEMENTATION")
        audit.c08_commits("main..HEAD")
        commits = [issue.location for issue in audit.issues if issue.check == "C08"]
        self.assertEqual(commits, ["commit a", "commit c"])

    def split_fixture(self, needed=False):
        repository = SCRIPT_DIR.parents[3]
        directory = repository / ".github/skills/architecture/scripts"
        sys.path.insert(0, str(directory))
        self.addCleanup(sys.path.remove, str(directory))
        spec = importlib.util.spec_from_file_location("trace_design_fixture", directory / "test_design_split.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        root = self.root / "split"
        module.create(root, needed)
        module.save(root, "reports/architecture/cross-artifact-consistency.md", module.fill((root / module.TEMPLATES / "cross-artifact-consistency-analysis.template.md").read_text(encoding="utf-8")))
        for kind in ("quality-review", "security-review"):
            module.save(root, f"reports/{kind}/validation-result.json", {"status": "PASS", "audit_scope": "ARCHITECTURE", "source_baseline_sha256": module.digest(root / module.FINAL), "errors": []})
        self.assertEqual(0, run_checker(root, "--scope", "ARCHITECTURE")[0])
        self.assertEqual(0, run_checker(root, "--scope", "ARCHITECTURE", "--no-write")[0])
        self.assertEqual([], module.write_gate(root))
        return root, module

    def test_actual_split_architecture_trace_result_can_issue_gate(self):
        root, module = self.split_fixture(True)
        module.save(root, "app/feature.py", "# trace: ADDR-001\ndef feature():\n    return True\n")
        status, result = run_checker(root, "--scope", "IMPLEMENTATION")
        self.assertEqual(status, 0, result)
        self.assertEqual(result["source_baseline_sha256"], module.digest(root / module.FINAL))
        self.assertEqual([], module.validate_gate(root))

    def test_no_addr_needed_allows_only_gate_approved_requirement(self):
        root, module = self.split_fixture()
        module.save(root, "app/feature.py", "# trace: FR-001\ndef feature():\n    return True\n")
        status, result = run_checker(root, "--scope", "IMPLEMENTATION")
        self.assertEqual(status, 0, result)
        (root / module.GATE).unlink()
        status, result = run_checker(root, "--scope", "IMPLEMENTATION")
        self.assertEqual(status, 1)
        self.assertTrue(any(issue["classification"] == "ARCHITECTURE_GATE_INVALID" for issue in result["issues"]))
        self.assertTrue(any(issue["check"] == "C05" for issue in result["issues"]))

    def test_direct_requirement_is_not_allowed_when_addr_was_required(self):
        root, module = self.split_fixture(True)
        module.save(root, "app/feature.py", "# trace: FR-001\ndef feature():\n    return True\n")
        status, result = run_checker(root, "--scope", "IMPLEMENTATION")
        self.assertEqual(status, 1)
        self.assertTrue(any(issue["check"] == "C05" for issue in result["issues"]))

    def test_addr_project_without_manifest_does_not_bypass_gate(self):
        policy = checker.load_policy(POLICY_PATH)
        audit = checker.Auditor(self.root, policy, "IMPLEMENTATION")
        audit.load()
        audit.check_all(None)
        self.assertTrue(any(issue.classification == "ARCHITECTURE_GATE_INVALID" for issue in audit.issues))


if __name__ == "__main__":
    unittest.main()
