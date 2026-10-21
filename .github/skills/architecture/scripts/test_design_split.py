from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parent
REPOSITORY = SCRIPTS.parents[3]
sys.path.insert(0, str(REPOSITORY / ".github/skills/addr/scripts"))
from design_common import (
    FINAL, GATE, INPUT, REQUEST, RESULT, TEMPLATES, addr_records, baseline_paths,
    digest, load_json, validate_design, validate_gate, visible_text,
)
from validate_addr import prepare_request, validate_addr, write_gate


def save(root: Path, path: str, value) -> None:
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n" if isinstance(value, dict) else value, encoding="utf-8")


def read(root: Path, path: str) -> dict:
    return json.loads((root / path).read_text(encoding="utf-8"))


def fill(template: str, addr: bool = False) -> str:
    text = visible_text(template)
    if addr:
        text = re.sub(r"^### ([A-F])\..*?(?=^### [A-F]\.|^## 7\.)", lambda match: match.group(0) if match.group(1) == "C" else "", text, flags=re.MULTILINE | re.DOTALL)
        text = re.sub(r"^\| ASM-001 .*$", "", text, flags=re.MULTILINE)

    def replacement(match):
        label = match.group(1)
        if "連番" == label:
            return "001"
        if "ACTIVE／SUPERSEDED" == label:
            return "ACTIVE"
        if label.startswith("画面／帳票"):
            return "外部インターフェース"
        if label == "要件セット版／GitコミットID":
            return "rev1"
        if "SELECTED／NOT_SELECTED" == label:
            return "SELECTED"
        if "MUST／MUST_NOT／SHOULD" == label:
            return "MUST"
        if "対象ID" == label:
            return "FR-001"
        if "要件" in label:
            return "FR-001"
        return "記入済み"

    text = re.sub(r"\{\{([^{}]+)\}\}", replacement, text)

    def angle(match):
        label = match.group(1)
        if "TASK-001, TASK-002" in label:
            return "TASK-001"
        if "TASK-xxx" in label or "ADR-xxx" in label:
            return "None"
        if "FR-" in label:
            return "FR-001"
        return "記入済み"

    return re.sub(r"<([^<>\n]+)>", angle, text)


def create(root: Path, needed: bool = False) -> None:
    for directory in (TEMPLATES, ".github/skills/addr/templates"):
        shutil.copytree(REPOSITORY / directory, root / directory)
    save(root, "docs/requirements/requirements.md", "# Requirements Index\n\n## 成果物\n- [機能](functional_requirements.md)\n\n## 機能要件\n- FR-001: [機能](functional_requirements.md)\n\n## 非機能要件\n")
    save(root, "docs/requirements/functional_requirements.md", "# 機能\n- FR-001: 機能\n")
    save(root, ".github/project-context/project-ai-steering.md", "# Project AI Steering\n入力済み\n")
    sources = [{"path": path, "sha256": digest(root / path)} for path in sorted(baseline_paths(root))]
    draft = {"version": 1, "stage": "DRAFT", "source_revision": "rev1", "sources": sources, "artifacts": [], "targets": [{"target_id": "FR-001", "criticality": "MANDATORY", "basis_ids": ["FR-001"]}], "unresolved_design_decisions": []}
    if needed:
        draft["unresolved_design_decisions"] = [{"candidate_key": "decision-1", "target_id": "FR-001", "related_requirement_ids": ["FR-001"], "topic": "方式", "reason_unresolved": "複数の方式", "candidate_options": []}]
    save(root, INPUT, draft)
    errors = prepare_request(root)
    if errors:
        raise AssertionError(errors)
    request = read(root, REQUEST)
    result = {"status": "SUCCESS", "result": "SUCCESS", "source_revision": "rev1", "design_input_sha256": digest(root / INPUT), "output_artifacts": [], "addr_creation_results": [{"candidate_key": "decision-1", "target_id": "FR-001", "needed": needed, "reason": "根拠あり", "addr_id": "ADDR-001" if needed else None}], "unused_addr_ids": request["addr_id_pool"][1:] if needed else request["addr_id_pool"], "artifact_link_updates": [], "assumptions": [], "blocking_issues": [], "human_intervention_requested": False, "autonomous_recovery": {"action": "NONE", "attempt": 0, "max_attempts": request["recovery_policy"]["max_attempts"]}}
    if needed:
        path = "docs/addr/ADDR-001.md"
        save(root, path, fill((root / ".github/skills/addr/templates/addr.md").read_text(encoding="utf-8"), True))
        result["output_artifacts"] = [{"addr_id": "ADDR-001", "path": path, "sha256": digest(root / path)}]
    save(root, RESULT, result)
    plan_path = "docs/architecture/implementation-task-list.md"
    save(root, plan_path, fill((root / TEMPLATES / "implementation-task-list.template.md").read_text(encoding="utf-8")))
    final = {**draft, "stage": "FINAL", "design_input_sha256": digest(root / INPUT), "unresolved_design_decisions": [], "artifacts": [{"artifact_id": "PLAN-001", "path": plan_path, "sha256": digest(root / plan_path), "template": "implementation-task-list", "target_id": "FR-001", "related_requirement_ids": ["FR-001"], "related_addr_ids": ["ADDR-001"] if needed else []}]}
    save(root, FINAL, final)


class DesignSplitTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        create(self.root)

    def update(self, path, **changes):
        save(self.root, path, {**read(self.root, path), **changes})

    def needed(self):
        self.temporary.cleanup()
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        create(self.root, True)

    def evidence(self):
        save(self.root, "reports/architecture/cross-artifact-consistency.md", fill((self.root / TEMPLATES / "cross-artifact-consistency-analysis.template.md").read_text(encoding="utf-8")))
        for kind in ("quality-review", "security-review", "traceability"):
            save(self.root, f"reports/{kind}/validation-result.json", {"status": "PASS", "audit_scope": "ARCHITECTURE", "source_baseline_sha256": digest(self.root / FINAL), "errors": []})

    def test_no_addr_needed_is_success(self):
        self.assertEqual([], validate_design(self.root, "draft"))
        self.assertEqual([], validate_addr(self.root, True))
        self.assertEqual([], validate_design(self.root, "final"))

    def test_addr_needed_is_success(self):
        self.needed()
        self.assertEqual([], validate_addr(self.root, True))

    def test_changed_requirement_is_stale(self):
        save(self.root, "docs/requirements/functional_requirements.md", "変更後")
        self.assertTrue(validate_design(self.root, "draft"))
        self.assertTrue(validate_addr(self.root))

    def test_missing_baseline_snapshot_fails(self):
        self.update(INPUT, sources=[])
        self.assertTrue(validate_design(self.root, "draft"))

    def test_criticality_change_fails(self):
        self.update(REQUEST, target_criticality=[])
        self.assertTrue(validate_addr(self.root))

    def test_negative_retries_fail(self):
        self.update(REQUEST, recovery_policy={"max_attempts": -1})
        self.assertTrue(validate_addr(self.root))

    def test_retry_limit_exceeded_fails(self):
        self.update(REQUEST, attempt=4)
        self.assertTrue(validate_addr(self.root))

    def test_new_request_has_three_repair_cycles(self):
        self.assertEqual(read(self.root, REQUEST)["recovery_policy"]["max_attempts"], 3)

    def test_third_addr_repair_is_valid(self):
        self.update(REQUEST, attempt=3)
        result = read(self.root, RESULT)
        result["autonomous_recovery"]["attempt"] = 3
        save(self.root, RESULT, result)
        self.assertEqual([], validate_addr(self.root))

    def test_missing_result_fails(self):
        (self.root / RESULT).unlink()
        self.assertTrue(validate_addr(self.root))

    def test_missing_target_review_fails(self):
        self.update(RESULT, addr_creation_results=[])
        self.assertTrue(validate_addr(self.root))

    def test_unnecessary_id_consumption_fails(self):
        choices = read(self.root, RESULT)["addr_creation_results"]
        choices[0]["addr_id"] = "ADDR-001"
        self.update(RESULT, addr_creation_results=choices)
        self.assertTrue(validate_addr(self.root))

    def test_unused_pool_mismatch_fails(self):
        self.update(RESULT, unused_addr_ids=[])
        self.assertTrue(validate_addr(self.root))

    def test_partial_success_is_not_gate_success(self):
        self.update(RESULT, status="BLOCKED", result="PARTIAL_SUCCESS")
        self.assertTrue(validate_addr(self.root))

    def test_human_intervention_fails(self):
        self.update(RESULT, human_intervention_requested=True)
        self.assertTrue(validate_addr(self.root))

    def test_missing_task_plan_fails(self):
        self.update(FINAL, artifacts=[])
        self.assertTrue(validate_design(self.root, "final"))

    def test_final_unresolved_decision_fails(self):
        self.update(FINAL, unresolved_design_decisions=[{"candidate_key": "unresolved", "target_id": "FR-001", "related_requirement_ids": ["FR-001"]}])
        self.assertTrue(validate_design(self.root, "final"))

    def change_plan(self, old, new):
        final = read(self.root, FINAL)
        path = final["artifacts"][0]["path"]
        text = (self.root / path).read_text(encoding="utf-8")
        self.assertIn(old, text)
        save(self.root, path, text.replace(old, new, 1))
        final["artifacts"][0]["sha256"] = digest(self.root / path)
        save(self.root, FINAL, final)

    def test_task_cycle_fails(self):
        self.change_plan("| `None` | `HIGH / MEDIUM / LOW`", "| `TASK-001` | `HIGH / MEDIUM / LOW`")
        self.assertTrue(validate_design(self.root, "final"))

    def test_task_detail_missing_fails(self):
        self.change_plan("### TASK-001", "### TASK-999")
        self.assertTrue(validate_design(self.root, "final"))

    def test_multiple_task_blocks_pass(self):
        final = read(self.root, FINAL)
        path = final["artifacts"][0]["path"]
        text = (self.root / path).read_text(encoding="utf-8")
        block = text.split("### TASK-001", 1)[1].split("## 7.", 1)[0]
        text = text.replace("## 7.", "### TASK-002" + block + "## 7.", 1)
        row = next(line for line in text.splitlines() if line.startswith("| TASK-001 |"))
        text = text.replace(row, row + "\n" + row.replace("TASK-001", "TASK-002"), 1)
        text = text.replace("| 1 | `TASK-001` |", "| 1 | `TASK-001, TASK-002` |", 1)
        save(self.root, path, text)
        final["artifacts"][0]["sha256"] = digest(self.root / path)
        save(self.root, FINAL, final)
        self.assertEqual([], validate_design(self.root, "final"))

    def test_addr_type_section_mismatch_fails(self):
        self.needed()
        path = self.root / "docs/addr/ADDR-001.md"
        path.write_text(path.read_text(encoding="utf-8").replace("### C. 外部インターフェースの場合", "### A. 画面の場合"), encoding="utf-8")
        self.refresh_addr()
        self.assertTrue(any("heading" in error for error in validate_addr(self.root)))

    def test_addr_invalid_constraint_fails(self):
        self.needed()
        path = self.root / "docs/addr/ADDR-001.md"
        path.write_text(path.read_text(encoding="utf-8").replace("| MUST |", "| MAY |"), encoding="utf-8")
        self.refresh_addr()
        self.assertTrue(any("constraint" in error for error in validate_addr(self.root)))

    def test_addr_unknown_requirement_fails(self):
        self.needed()
        path = self.root / "docs/addr/ADDR-001.md"
        path.write_text(path.read_text(encoding="utf-8").replace("FR-001", "FR-999"), encoding="utf-8")
        self.refresh_addr()
        self.assertTrue(any("requirement" in error for error in validate_addr(self.root)))

    def refresh_addr(self):
        result = read(self.root, RESULT)
        result["output_artifacts"][0]["sha256"] = digest(self.root / result["output_artifacts"][0]["path"])
        save(self.root, RESULT, result)

    def test_addr_metadata_missing_fails(self):
        self.needed()
        path = self.root / "docs/addr/ADDR-001.md"
        text = path.read_text(encoding="utf-8")
        path.write_text(re.sub(r"^primary_decision:.*\n", "", text, flags=re.MULTILINE), encoding="utf-8")
        self.refresh_addr()
        self.assertTrue(any("metadata differs" in error for error in validate_addr(self.root)))

    def test_unknown_task_requirement_fails(self):
        self.change_plan("| `FR-001` | `None` |", "| `FR-999` | `None` |")
        self.assertTrue(any("unknown requirement" in error for error in validate_design(self.root, "final")))

    def test_failed_assurance_cannot_release_gate(self):
        self.evidence()
        save(self.root, "reports/quality-review/validation-result.json", {"status": "FAIL", "audit_scope": "ARCHITECTURE", "source_baseline_sha256": digest(self.root / FINAL)})
        self.assertTrue(write_gate(self.root))
        self.assertFalse((self.root / GATE).exists())

    def test_missing_final_link_fails(self):
        self.needed()
        self.update(RESULT, artifact_link_updates=[{"artifact_id": "FILE-999", "related_addr_id": "ADDR-001", "requested_action": "LINK_ADDR"}])
        self.assertTrue(validate_addr(self.root, True))

    def test_gate_requires_assurance(self):
        self.assertTrue(write_gate(self.root))
        self.assertFalse((self.root / GATE).exists())

    def test_gate_success_and_stale_output(self):
        self.evidence()
        self.assertEqual([], write_gate(self.root))
        self.assertEqual([], validate_gate(self.root))
        save(self.root, "docs/architecture/implementation-task-list.md", "変更")
        self.assertTrue(validate_gate(self.root))

    def test_gate_survives_later_phase_report_updates(self):
        self.evidence()
        self.assertEqual([], write_gate(self.root))
        save(self.root, "reports/quality-review/validation-result.json", {"status": "PASS", "audit_scope": "IMPLEMENTATION"})
        self.assertEqual([], validate_gate(self.root))

    def test_gate_rejects_stale_assurance_baseline(self):
        self.evidence()
        save(self.root, "reports/security-review/validation-result.json", {"status": "PASS", "audit_scope": "ARCHITECTURE", "source_baseline_sha256": "old"})
        self.assertTrue(write_gate(self.root))

    def test_gate_rejects_wrong_scope(self):
        self.evidence()
        save(self.root, "reports/traceability/validation-result.json", {"status": "PASS", "audit_scope": "FULL", "source_baseline_sha256": digest(self.root / FINAL)})
        self.assertTrue(write_gate(self.root))

    def test_request_is_idempotent(self):
        before = (self.root / REQUEST).read_bytes()
        self.assertEqual([], prepare_request(self.root))
        self.assertEqual(before, (self.root / REQUEST).read_bytes())

    def test_request_renewal_does_not_reuse_ids(self):
        original = read(self.root, REQUEST)["addr_id_pool"]
        self.assertEqual([], prepare_request(self.root, renew=True))
        self.assertFalse(set(original) & set(read(self.root, REQUEST)["addr_id_pool"]))

    def test_request_renewal_rejects_unreleased_candidates(self):
        self.needed()
        self.assertTrue(prepare_request(self.root, renew=True))

    def test_malformed_input_returns_errors(self):
        self.update(INPUT, targets="invalid")
        self.assertTrue(validate_addr(self.root))

    def test_gate_changed_canonical_template_is_stale(self):
        self.evidence()
        self.assertEqual([], write_gate(self.root))
        with (self.root / TEMPLATES / "file-definition.template.md").open("a", encoding="utf-8") as output:
            output.write("\n変更")
        self.assertTrue(validate_gate(self.root))

    def test_path_escape_fails(self):
        final = read(self.root, FINAL)
        final["artifacts"][0]["path"] = "../escape.md"
        save(self.root, FINAL, final)
        self.assertTrue(validate_design(self.root, "final"))

    def test_file_definition_uses_real_template(self):
        draft = read(self.root, INPUT)
        path = "docs/architecture/files/FILE-001.md"
        save(self.root, path, fill((self.root / TEMPLATES / "file-definition.template.md").read_text(encoding="utf-8")))
        draft["artifacts"] = [{"artifact_id": "FILE-001", "path": path, "template": "file-definition", "sha256": digest(self.root / path), "target_id": "FR-001", "related_requirement_ids": ["FR-001"], "related_addr_ids": []}]
        save(self.root, INPUT, draft)
        self.assertEqual([], validate_design(self.root, "draft"))

    def test_mixed_legacy_adr_and_addr_discovery(self):
        self.needed()
        save(self.root, "docs/adr/ADR-002.md", "# ADR-002 Legacy\n## Status\nAccepted\n## Related Requirements\n- FR-001\n")
        directory = REPOSITORY / ".github/skills/traceability-audit/scripts"
        sys.path.insert(0, str(directory))
        self.addCleanup(sys.path.remove, str(directory))
        spec = importlib.util.spec_from_file_location("design_trace_contract", directory / "trace_check.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        self.addCleanup(sys.modules.pop, spec.name, None)
        spec.loader.exec_module(module)
        audit = module.Auditor(self.root, module.load_policy(directory.parent / "policy/traceability-policy.yaml"), "ARCHITECTURE")
        audit.load()
        audit.check_all(None)
        records = {identifier: element for identifier, element in audit.elements.items() if element.kind == "addr"}
        self.assertEqual({"ADR-002", "ADDR-001"}, set(records))
        self.assertEqual("ACTIVE", records["ADDR-001"].status)
        self.assertEqual({"FR-001"}, records["ADDR-001"].req_refs)
        self.assertFalse(audit.issues, audit.issues)

    def test_cli_missing_inputs_returns_failure(self):
        result = subprocess.run([sys.executable, str(REPOSITORY / ".github/skills/addr/scripts/validate_addr.py"), "--root", str(self.root / "missing")], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(1, result.returncode)
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
