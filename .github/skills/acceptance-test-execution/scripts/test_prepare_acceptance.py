from __future__ import annotations

import csv
import json
import sys
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

import yaml

from acceptance_common import read_json, read_yaml, write_json
import prepare_acceptance as preparation
import run_acceptance_tests as runner
import validate_acceptance_results as validator


SCRIPT_DIR = Path(__file__).resolve().parent
POLICY = SCRIPT_DIR.parent / "policy/acceptance-test-policy.yaml"


def definition(identifier="AT-001"):
    return {"case_id": identifier, "title": "会員登録", "requirement_id": "FR-001", "requirement_type": "FUNCTIONAL", "precondition": "利用者が未登録\nDB照会可能", "steps": "登録する", "expected_result": "201\n利用者は1件増加", "pass_rule": "全条件成立", "fail_rule": "1件でも不一致", "blocked_rule": "DB観測不能", "measurement": {"許容差": "0"}, "evidence_hint": "APIとDB証跡"}


def save_xlsx(path, sheets):
    namespace = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    relationship = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    workbook = f'<workbook xmlns="{namespace}" xmlns:r="{relationship}"><sheets>'
    relations = '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    with zipfile.ZipFile(path, "w") as archive:
        for ordinal, (name, rows) in enumerate(sheets.items(), 1):
            workbook += f'<sheet name="{escape(name)}" sheetId="{ordinal}" r:id="rId{ordinal}"/>'
            relations += f'<Relationship Id="rId{ordinal}" Target="worksheets/sheet{ordinal}.xml"/>'
            content = f'<worksheet xmlns="{namespace}"><sheetData>'
            for row_number, row in enumerate(rows, 1):
                content += f'<row r="{row_number}">'
                for column_number, value in enumerate(row, 1):
                    column = ""
                    remaining = column_number
                    while remaining:
                        remaining, remainder = divmod(remaining - 1, 26)
                        column = chr(65 + remainder) + column
                    reference = f"{column}{row_number}"
                    if isinstance(value, dict):
                        content += f'<c r="{reference}"><f>1+1</f><v>2</v></c>'
                    else:
                        content += f'<c r="{reference}" t="inlineStr"><is><t xml:space="preserve">{escape(str(value))}</t></is></c>'
                content += '</row>'
            content += '</sheetData></worksheet>'
            archive.writestr(f"xl/worksheets/sheet{ordinal}.xml", content)
        archive.writestr("xl/workbook.xml", workbook + '</sheets></workbook>')
        archive.writestr("xl/_rels/workbook.xml.rels", relations + '</Relationships>')


class AcceptancePreparationTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        (self.repo / "app.py").write_text("application source", encoding="utf-8")
        self.context = self.repo / "reports/experiments/RUN-001/run-context.json"
        write_json(self.context, {"run_id": "RUN-001", "status": "COMPLETE", "sdlc_completed_at": "2026-01-01T12:00:00+09:00"})
        self.source = self.root / "cases.json"
        write_json(self.source, {"document_kind": "ACCEPTANCE_CASE_DEFINITIONS_NOT_EXECUTION_MANIFEST", "cases": [definition()]})
        self.workspace = self.root / "external-evaluation"
        self.exposed = "2026-01-01T12:01:00+09:00"

    def import_source(self):
        return preparation.import_sheet(self.repo, self.source, self.workspace, self.context, self.exposed)

    def bind(self, mode="COMMAND", code="raise SystemExit(0)\n"):
        if not self.workspace.exists():
            self.import_source()
        (self.workspace / "tests/probe.py").write_text(code, encoding="utf-8")
        binding = {"case_id": "AT-001", "execution_type": mode, "command": [sys.executable, str(self.workspace / "tests/probe.py")], "test_files": ["tests/probe.py"], "assertion_map": {"precondition": "probe前提処理", "steps": "probe操作", "expected_result": "probe検証", "evidence": "probe証跡"}, "blocked_reason": "検証用環境なし"}
        write_json(self.workspace / "bindings.json", {"cases": [binding]})

    def freeze(self, mode="COMMAND", code="raise SystemExit(0)\n"):
        self.bind(mode, code)
        plan = preparation.reviewed_plan(self.workspace)
        preparation.seal(self.workspace, "fixture-human-reviewer", plan["review_sha256"])
        return self.workspace / "acceptance-test-manifest.json"

    def execute(self, path):
        return runner.execute(self.repo, self.workspace, path, POLICY)

    def full_workbook(self, overrides=None):
        fields = [["case_id", "項目", "分割番号", "内容", "出典"], ["AT-001", "前提条件", 1, "未登録", "source:1"], ["AT-001", "操作・手順", 1, "登録", ""], ["AT-001", "期待結果", 1, "201\n", ""], ["AT-001", "期待結果", 2, "件数増加", ""]]
        sheets = {"受入項目": [["case_id", "試験項目", "区分", "関連要件ID", "根拠AC"], ["AT-001", "登録", "機能", "FR-001, NFR-01", "AC-001"]], "受入詳細": fields}
        if overrides:
            overrides(sheets)
        path = self.root / "cases.xlsx"
        save_xlsx(path, sheets)
        return path

    def test_json_preserves_all_fields(self):
        self.assertEqual([definition()], preparation.load_cases(self.source))

    def test_csv_preserves_multiline_conditions(self):
        path = self.root / "cases.csv"
        case = definition()
        case["measurement"] = "許容差0"
        with path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(case))
            writer.writeheader()
            writer.writerow(case)
        self.assertEqual([case], preparation.load_cases(path))

    def test_xlsx_flat_table(self):
        path = self.root / "flat.xlsx"
        case = definition()
        case["measurement"] = "許容差0"
        save_xlsx(path, {"Cases": [list(case), list(case.values())]})
        self.assertEqual([case], preparation.load_cases(path))

    def test_xlsx_reassembles_full_details(self):
        case = preparation.load_cases(self.full_workbook())[0]
        self.assertEqual("201\n件数増加", case["expected_result"])
        self.assertEqual("FR-001", case["requirement_id"])

    def test_xlsx_nfr_primary(self):
        path = self.full_workbook(lambda sheets: sheets["受入項目"][1].__setitem__(2, "非機能"))
        case = preparation.load_cases(path)[0]
        self.assertEqual(("NFR-01", "NON_FUNCTIONAL"), (case["requirement_id"], case["requirement_type"]))

    def test_xlsx_summary_alone_rejected(self):
        path = self.full_workbook(lambda sheets: sheets.pop("受入詳細"))
        with self.assertRaisesRegex(ValueError, "受入詳細"):
            preparation.load_cases(path)

    def test_xlsx_missing_detail_fragment_rejected(self):
        path = self.full_workbook(lambda sheets: sheets["受入詳細"][-1].__setitem__(2, 3))
        with self.assertRaisesRegex(ValueError, "fragment"):
            preparation.load_cases(path)

    def test_xlsx_duplicate_detail_fragment_rejected(self):
        path = self.full_workbook(lambda sheets: sheets["受入詳細"][-1].__setitem__(2, 1))
        with self.assertRaisesRegex(ValueError, "fragment"):
            preparation.load_cases(path)

    def test_xlsx_formula_expected_rejected(self):
        path = self.full_workbook(lambda sheets: sheets["受入詳細"][-1].__setitem__(3, {"formula": True}))
        with self.assertRaisesRegex(ValueError, "formulas"):
            preparation.load_cases(path)

    def test_xlsx_supplementary_not_added_to_denominator(self):
        def supplement(sheets):
            sheets["受入詳細"].append(["NFR-CHK-001", "期待結果", 1, "月間稼働", ""])
            sheets["補足NFR"] = [["case_id"], ["NFR-CHK-001"]]
        self.assertEqual(1, len(preparation.load_cases(self.full_workbook(supplement))))

    def test_xlsx_orphan_acceptance_rejected(self):
        path = self.full_workbook(lambda sheets: sheets["受入詳細"].append(["AT-999", "期待結果", 1, "隠れた条件", ""]))
        with self.assertRaisesRegex(ValueError, "Unmatched"):
            preparation.load_cases(path)

    def test_xlsx_rich_shared_strings_exclude_phonetic_and_xml_indentation(self):
        path = self.root / "rich.xlsx"
        save_xlsx(path, {"Cases": [["placeholder"]]})
        with zipfile.ZipFile(path) as archive:
            content = {name: archive.read(name) for name in archive.namelist()}
        namespace = preparation.NAMESPACE["sheet"]
        content["xl/sharedStrings.xml"] = f'<sst xmlns="{namespace}">\n<si>\n<r><t>期待</t></r>\n<r><t>結果</t></r>\n<rPh sb="0" eb="2"><t>キタイ</t></rPh>\n</si></sst>'.encode()
        content["xl/worksheets/sheet1.xml"] = f'<worksheet xmlns="{namespace}"><sheetData><row r="1"><c r="A1" t="s"><v>0</v></c></row></sheetData></worksheet>'.encode()
        with zipfile.ZipFile(path, "w") as archive:
            for name, value in content.items():
                archive.writestr(name, value)
        self.assertEqual([["期待結果"]], preparation.read_xlsx(path)["Cases"])

    def test_duplicate_case_rejected(self):
        write_json(self.source, [definition(), definition()])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            preparation.load_cases(self.source)

    def test_missing_expectation_rejected(self):
        case = definition()
        case["expected_result"] = ""
        write_json(self.source, [case])
        with self.assertRaises(ValueError):
            preparation.load_cases(self.source)

    def test_execution_manifest_not_used_as_definitions(self):
        write_json(self.source, {"cases": [definition()]})
        with self.assertRaisesRegex(ValueError, "definitions"):
            preparation.load_cases(self.source)

    def test_import_does_not_execute_or_approve(self):
        self.assertEqual(1, self.import_source()["total_cases"])
        self.assertEqual([definition()], read_json(self.workspace / "case-bundle.json")["cases"])
        self.assertFalse((self.workspace / "acceptance-test-manifest.json").exists())
        self.assertFalse((self.workspace / "execution-started.json").exists())

    def test_early_exposure_rejected_before_source_read(self):
        self.exposed = "2026-01-01T11:59:00+09:00"
        self.source.unlink()
        with self.assertRaisesRegex(ValueError, "after SDLC"):
            self.import_source()

    def test_aborted_or_incomplete_context_rejected(self):
        for status in ("ABORTED", "IN_PROGRESS", None):
            context = read_json(self.context)
            context["status"] = status
            write_json(self.context, context)
            with self.assertRaisesRegex(ValueError, "completion"):
                self.import_source()

    def test_unresolved_complete_allowed(self):
        context = read_json(self.context)
        context["status"] = "COMPLETE_WITH_UNRESOLVED"
        write_json(self.context, context)
        self.import_source()

    def test_workspace_in_repo_rejected(self):
        self.workspace = self.repo / "evaluation-input"
        with self.assertRaisesRegex(ValueError, "outside"):
            self.import_source()

    def test_source_in_repo_rejected(self):
        self.source = self.repo / "hidden.json"
        write_json(self.source, [definition()])
        with self.assertRaisesRegex(ValueError, "outside"):
            self.import_source()

    def test_nonempty_workspace_rejected(self):
        self.import_source()
        with self.assertRaisesRegex(ValueError, "empty"):
            self.import_source()

    def test_other_run_context_rejected(self):
        self.context = self.root / "fake-context.json"
        write_json(self.context, {"run_id": "RUN-001"})
        with self.assertRaisesRegex(ValueError, "recorded"):
            self.import_source()

    def test_unbound_cannot_be_sealed(self):
        self.import_source()
        plan = preparation.reviewed_plan(self.workspace)
        with self.assertRaisesRegex(ValueError, "UNBOUND"):
            preparation.seal(self.workspace, "reviewer", plan["review_sha256"])

    def test_blank_reviewer_rejected(self):
        self.bind()
        with self.assertRaisesRegex(ValueError, "human reviewer"):
            preparation.seal(self.workspace, " ", preparation.reviewed_plan(self.workspace)["review_sha256"])

    def test_stale_review_hash_rejected(self):
        self.bind()
        plan = preparation.reviewed_plan(self.workspace)
        (self.workspace / "tests/probe.py").write_text("raise SystemExit(1)\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "revision"):
            preparation.seal(self.workspace, "reviewer", plan["review_sha256"])

    def test_missing_binding_case_rejected(self):
        self.import_source()
        write_json(self.workspace / "bindings.json", {"cases": []})
        with self.assertRaisesRegex(ValueError, "exact case set"):
            preparation.reviewed_plan(self.workspace)

    def test_missing_assertion_mapping_rejected(self):
        self.bind()
        binding = read_json(self.workspace / "bindings.json")
        binding["cases"][0]["assertion_map"] = {}
        write_json(self.workspace / "bindings.json", binding)
        with self.assertRaisesRegex(ValueError, "assertion mapping"):
            preparation.reviewed_plan(self.workspace)

    def test_source_snapshot_tamper_rejected(self):
        self.bind()
        (self.workspace / "source.json").write_text("[]", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "source/conditions"):
            preparation.reviewed_plan(self.workspace)

    def test_bundle_expected_tamper_rejected(self):
        self.bind()
        bundle = read_json(self.workspace / "case-bundle.json")
        bundle["cases"][0]["expected_result"] = "都合のよい値"
        write_json(self.workspace / "case-bundle.json", bundle)
        with self.assertRaisesRegex(ValueError, "conditions"):
            preparation.reviewed_plan(self.workspace)

    def test_source_target_tamper_rejected(self):
        self.bind()
        (self.repo / "app.py").write_text("changed", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Target source changed"):
            preparation.reviewed_plan(self.workspace)

    def test_frozen_test_tamper_blocks_execution(self):
        path = self.freeze()
        (self.workspace / "tests/probe.py").write_text("raise SystemExit(1)", encoding="utf-8")
        rows, _, errors = self.execute(path)
        self.assertEqual([], rows)
        self.assertTrue(errors)
        self.assertFalse((self.workspace / "execution-started.json").exists())

    def test_approved_manifest_expected_tamper_blocks_execution(self):
        path = self.freeze()
        manifest = read_json(path)
        manifest["cases"][0]["expected"]["exit_code"] = 1
        write_json(path, manifest)
        self.assertTrue(self.execute(path)[2])

    def test_all_pass_pipeline_validates(self):
        path = self.freeze()
        rows, evidence, errors = self.execute(path)
        self.assertEqual([], errors)
        self.assertEqual("PASS", rows[0]["result"])
        self.assertEqual([], validator.validate(read_json(path), rows, evidence))

    def test_assertion_failure_is_fail(self):
        path = self.freeze(code="raise SystemExit(1)\n")
        rows, evidence, errors = self.execute(path)
        self.assertEqual([], errors)
        self.assertEqual("FAIL", rows[0]["result"])
        self.assertEqual([], validator.validate(read_json(path), rows, evidence))

    def test_runtime_prerequisite_failure_is_blocked(self):
        path = self.freeze(code="raise SystemExit(125)\n")
        rows, _, errors = self.execute(path)
        self.assertEqual([], errors)
        self.assertEqual("BLOCKED", rows[0]["result"])

    def test_unavailable_case_kept_as_blocked(self):
        path = self.freeze(mode="BLOCKED")
        rows, evidence, errors = self.execute(path)
        self.assertEqual([], errors)
        self.assertEqual(1, evidence["summary"]["total"])
        self.assertEqual("BLOCKED", rows[0]["result"])
        self.assertFalse(evidence["cases"][0]["command_executed"])
        self.assertEqual([], validator.validate(read_json(path), rows, evidence))

    def test_second_execution_rejected(self):
        path = self.freeze()
        self.execute(path)
        self.assertTrue(self.execute(path)[2])

    def test_reseal_rejected(self):
        self.freeze()
        with self.assertRaisesRegex(ValueError, "already exists"):
            preparation.seal(self.workspace, "reviewer", preparation.reviewed_plan(self.workspace)["review_sha256"])

    def test_target_changed_during_execution_invalidates_measurement(self):
        code = f"from pathlib import Path\nPath({str(self.repo / 'app.py')!r}).write_text('modified')\n"
        path = self.freeze(code=code)
        rows, evidence, errors = self.execute(path)
        self.assertTrue(errors)
        self.assertFalse(evidence["target_source_unchanged"])
        self.assertTrue(validator.validate(read_json(path), rows, evidence))

    def test_prepared_evidence_requires_binding_and_source_integrity(self):
        path = self.freeze()
        rows, evidence, _ = self.execute(path)
        evidence.pop("sheet_preparation_sha256")
        self.assertTrue(validator.validate(read_json(path), rows, evidence))

    def test_legacy_manifest_cannot_claim_blocked_without_preparation(self):
        self.freeze(mode="BLOCKED")
        manifest = read_json(self.workspace / "acceptance-test-manifest.json")
        manifest.pop("sheet_preparation")
        self.assertTrue(runner.validate_manifest(manifest, read_yaml(POLICY), self.workspace / "manifest.json"))

    def test_path_traversal_rejected(self):
        with self.assertRaises(ValueError):
            preparation.local(self.workspace, "../escape.py")

    def test_cli_preserves_first_result_on_repeat(self):
        path = self.freeze()
        command = [sys.executable, str(SCRIPT_DIR / "run_acceptance_tests.py"), "--repo-root", str(self.repo), "--input-dir", str(self.workspace), "--policy", str(POLICY)]
        completed = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
        evidence_path = self.repo / "reports/evaluation/RUN-001/acceptance-test/execution-evidence.json"
        original_evidence = evidence_path.read_bytes()
        original_results = (self.workspace / "acceptance-test-results.csv").read_bytes()
        repeated = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(1, repeated.returncode)
        self.assertEqual(original_evidence, evidence_path.read_bytes())
        self.assertEqual(original_results, (self.workspace / "acceptance-test-results.csv").read_bytes())

    def test_measurement_journal_import_and_acceptance_aggregation(self):
        preparation.fingerprint(self.repo)
        import experiment_recorder as recorder
        instant = "2026-01-01T11:00:00+09:00"
        monotonic = 0

        def event(identifier, kind, payload):
            nonlocal monotonic
            monotonic += 1
            recorder.append(self.repo, "RUN-001", identifier, kind, payload, lambda: (instant, monotonic))

        event("start", "RUN_STARTED", {"condition_id": "fixture"})
        event("enter-integration", "PHASE_ENTERED", {"phase": "INTEGRATION_TEST", "previous_result": "PASS"})
        event("end-integration", "PHASE_ENDED", {"phase": "INTEGRATION_TEST", "result": "PASS"})
        event("end", "RUN_ENDED", {"status": "COMPLETE", "source_fingerprint": preparation.fingerprint(self.repo)})
        recorder.export(self.repo, "RUN-001")
        path = self.freeze(mode="BLOCKED")
        rows, evidence, errors = self.execute(path)
        self.assertEqual([], errors)
        results_path = self.workspace / "acceptance-test-results.csv"
        from acceptance_common import write_results_csv
        write_results_csv(results_path, rows)
        evidence_path = self.repo / "reports/evaluation/RUN-001/acceptance-test/execution-evidence.json"
        write_json(evidence_path, evidence)
        runner.record_experiment_measurement(self.repo, "RUN-001", path, results_path, evidence_path)
        measured = recorder.summary(self.repo, "RUN-001")["acceptance"]
        self.assertEqual("MEASURED", measured["status"], measured)
        self.assertEqual((1, 1, 0.0), (measured["total"], measured["blocked"], measured["rate"]))

    def test_agent_delegation_is_postprocess_only(self):
        agent_root = SCRIPT_DIR.parents[2] / "agents"
        executor = yaml.safe_load((agent_root / "acceptance-test-executor.agent.md").read_text(encoding="utf-8").split("---", 2)[1])
        child = yaml.safe_load((agent_root / "acceptance-test-prepare.agent.md").read_text(encoding="utf-8").split("---", 2)[1])
        orchestrator = yaml.safe_load((agent_root / "sdlc-orchestrator.agent.md").read_text(encoding="utf-8").split("---", 2)[1])
        self.assertEqual(["AcceptanceTestPrepare"], executor["agents"])
        self.assertIn("agent", executor["tools"])
        self.assertFalse(child["user-invocable"])
        self.assertNotIn("AcceptanceTestPrepare", orchestrator["agents"])
        self.assertNotIn("AcceptanceTestExecutor", orchestrator["agents"])


if __name__ == "__main__":
    unittest.main()
