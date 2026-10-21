from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

from test_design_split import REPOSITORY, create, fill, read, save
from design_common import DESIGN_GATE, FINAL, GATE, HANDOFF, INPUT, REQUEST, RESULT, TEMPLATES, digest, validate_design, validate_design_gate, validate_gate, write_design_gate
from validate_addr import prepare_request, validate_addr, write_gate, write_handoff


class IndependentAddrTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        create(self.root)
        manifest = read(self.root, FINAL)
        manifest.update(version=2, unresolved_design_decisions=[])
        manifest.pop("design_input_sha256")
        analysis = "reports/architecture/cross-artifact-consistency.md"
        save(self.root, analysis, fill((self.root / TEMPLATES / "cross-artifact-consistency-analysis.template.md").read_text(encoding="utf-8")))
        manifest["artifacts"].append({"artifact_id": "ANALYSIS-001", "path": analysis, "sha256": digest(self.root / analysis), "template": "cross-artifact-consistency-analysis", "target_id": "FR-001", "related_requirement_ids": ["FR-001"], "related_addr_ids": []})
        save(self.root, FINAL, manifest)
        for name in (INPUT, REQUEST, RESULT):
            (self.root / name).unlink()

    def assurance(self, scope, baseline):
        for kind in ("quality-review", "security-review", "traceability"):
            save(self.root, f"reports/{kind}/validation-result.json", {"status": "PASS", "audit_scope": scope, "source_baseline_sha256": digest(self.root / baseline), "errors": []})

    def design_gate(self):
        self.assurance("ARCHITECTURE", FINAL)
        self.assertEqual([], write_design_gate(self.root))

    def addr(self, needed=True):
        self.design_gate()
        self.assertEqual([], prepare_request(self.root))
        request = read(self.root, REQUEST)
        result = {"status": "SUCCESS", "result": "SUCCESS", "source_revision": "rev1", "design_input_sha256": digest(self.root / FINAL), "output_artifacts": [], "addr_creation_results": [{"candidate_key": "decision-1", "target_id": "FR-001", "needed": needed, "reason": "根拠あり", "addr_id": "ADDR-001" if needed else None}], "unused_addr_ids": request["addr_id_pool"][1:] if needed else request["addr_id_pool"], "artifact_link_updates": [], "design_change_requests": [], "assumptions": [], "blocking_issues": [], "human_intervention_requested": False, "autonomous_recovery": {"action": "NONE", "attempt": 0, "max_attempts": 3}}
        if needed:
            path = "docs/addr/ADDR-001.md"
            text = fill((self.root / ".github/skills/addr/templates/addr.md").read_text(encoding="utf-8"), True)
            text = text.replace("## 3.", "| 設計資料 | PLAN-001 TASK-001 docs/architecture/implementation-task-list.md | 判断の対象 |\n\n## 3.", 1)
            save(self.root, path, text)
            result["output_artifacts"] = [{"addr_id": "ADDR-001", "path": path, "sha256": digest(self.root / path)}]
            result["artifact_link_updates"] = [{"artifact_id": "PLAN-001", "target_id": "FR-001", "related_addr_id": "ADDR-001", "requested_action": "LINK_ADDR", "element_ids": ["TASK-001"]}]
        save(self.root, RESULT, result)
        self.assertEqual([], validate_addr(self.root, True))

    def release(self, needed=True):
        self.addr(needed)
        self.assertEqual([], write_handoff(self.root))
        self.assurance("ADDR", HANDOFF)
        self.assertEqual([], write_gate(self.root))

    def update_result(self, **changes):
        save(self.root, RESULT, {**read(self.root, RESULT), **changes})

    def test_architecture_is_complete_without_draft_or_addr(self):
        self.assertFalse((self.root / INPUT).exists())
        self.assertFalse((self.root / RESULT).exists())
        self.assertEqual([], validate_design(self.root, "final"))
        self.design_gate()
        self.assertEqual([], validate_design_gate(self.root))

    def test_architecture_requires_its_own_consistency_analysis(self):
        manifest = read(self.root, FINAL)
        manifest["artifacts"] = manifest["artifacts"][:1]
        save(self.root, FINAL, manifest)
        self.assertTrue(validate_design(self.root, "final"))

    def test_decision_candidates_are_valid_handoff_not_finalized_by_architecture(self):
        manifest = read(self.root, FINAL)
        manifest["unresolved_design_decisions"] = [{"candidate_key": "decision-1", "target_id": "FR-001", "related_requirement_ids": ["FR-001"], "reason_unresolved": "ADDRへ委譲"}]
        save(self.root, FINAL, manifest)
        self.release()
        self.assertEqual([], validate_gate(self.root))

    def test_request_uses_frozen_final_manifest(self):
        self.addr()
        request = read(self.root, REQUEST)
        self.assertEqual(request["design_input_path"], FINAL)
        self.assertEqual(request["design_input_sha256"], digest(self.root / FINAL))
        self.assertEqual(request["workflow_version"], 2)

    def test_addr_without_design_gate_is_rejected(self):
        self.assertTrue(prepare_request(self.root))

    def test_no_addr_needed_does_not_create_empty_document_or_finalize(self):
        self.release(False)
        self.assertFalse((self.root / "docs/addr").exists())
        self.assertFalse((self.root / INPUT).exists())
        self.assertEqual([], validate_gate(self.root))

    def test_addr_and_release_do_not_edit_architecture_documents(self):
        before = {item["path"]: (self.root / item["path"]).read_bytes() for item in read(self.root, FINAL)["artifacts"]}
        before[FINAL] = (self.root / FINAL).read_bytes()
        self.release()
        self.assertEqual(before, {path: (self.root / path).read_bytes() for path in before})

    def test_addr_cannot_silently_modify_design(self):
        self.addr()
        path = self.root / "docs/architecture/implementation-task-list.md"
        path.write_text(path.read_text(encoding="utf-8") + "変更", encoding="utf-8")
        self.assertTrue(validate_addr(self.root, True))
        self.assertTrue(write_handoff(self.root))

    def test_design_change_requires_actual_return_not_automatic_finalize(self):
        self.addr()
        self.update_result(design_change_requests=[{"artifact_id": "PLAN-001", "reason": "設計本文変更", "change": "処理を分離"}])
        self.assertTrue(write_handoff(self.root))

    def test_binding_must_use_real_artifact_and_target(self):
        self.addr()
        links = read(self.root, RESULT)["artifact_link_updates"]
        links[0]["target_id"] = "FR-999"
        self.update_result(artifact_link_updates=links)
        self.assertTrue(validate_addr(self.root, True))

    def test_binding_must_use_real_task_ids_in_canonical_addr(self):
        self.addr()
        links = read(self.root, RESULT)["artifact_link_updates"]
        links[0]["element_ids"] = ["TASK-999"]
        self.update_result(artifact_link_updates=links)
        self.assertTrue(validate_addr(self.root, True))

    def test_created_addr_cannot_omit_binding(self):
        self.addr()
        self.update_result(artifact_link_updates=[])
        self.assertTrue(validate_addr(self.root, True))

    def test_binding_does_not_accept_a_longer_id_as_an_explicit_reference(self):
        self.addr()
        path = self.root / "docs/addr/ADDR-001.md"
        path.write_text(path.read_text(encoding="utf-8").replace("TASK-001", "TASK-0010"), encoding="utf-8")
        result = read(self.root, RESULT)
        result["output_artifacts"][0]["sha256"] = digest(path)
        save(self.root, RESULT, result)
        self.assertTrue(validate_addr(self.root, True))

    def test_missing_frozen_artifact_returns_errors_instead_of_crashing(self):
        self.addr()
        (self.root / "docs/architecture/implementation-task-list.md").unlink()
        self.assertTrue(validate_addr(self.root, True))

    def test_handoff_must_precede_addr_assurance_and_release(self):
        self.addr()
        self.assertTrue(write_gate(self.root))

    def test_architecture_assurance_cannot_replace_addr_assurance(self):
        self.addr()
        self.assertEqual([], write_handoff(self.root))
        self.assurance("ARCHITECTURE", HANDOFF)
        self.assertTrue(write_gate(self.root))

    def test_release_is_bound_to_both_independent_stages(self):
        self.release()
        self.assertEqual(read(self.root, GATE)["phase"], "ADDR")
        self.assertEqual([], validate_gate(self.root))
        save(self.root, RESULT, {**read(self.root, RESULT), "note": "different input"})
        self.assertTrue(validate_gate(self.root))

    def test_architecture_gate_survives_new_addr_and_later_assurance_files(self):
        self.release()
        self.assertEqual([], validate_design_gate(self.root))
        self.assurance("FULL", HANDOFF)
        self.assertEqual([], validate_gate(self.root))

    def trace(self, scope):
        directory = REPOSITORY / ".github/skills/traceability-audit/scripts"
        sys.path.insert(0, str(directory))
        self.addCleanup(sys.path.remove, str(directory))
        spec = importlib.util.spec_from_file_location("independent_trace", directory / "trace_check.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        self.addCleanup(sys.modules.pop, spec.name, None)
        spec.loader.exec_module(module)
        audit = module.Auditor(self.root, module.load_policy(directory.parent / "policy/traceability-policy.yaml"), scope)
        audit.load()
        audit.check_all(None)
        return audit

    def test_addr_scope_checks_links_without_demanding_future_code_or_tests(self):
        self.addr()
        self.assertEqual([], write_handoff(self.root))
        audit = self.trace("ADDR")
        self.assertFalse(audit.issues, audit.issues)
        self.assertEqual(audit.addr_rows()[0]["TASK"], ["TASK-001"])
        self.assertIn("ADDR-001", audit.elements["TASK-001"].refs)

    def test_addr_trace_cli_generation_and_independent_check(self):
        self.addr()
        self.assertEqual([], write_handoff(self.root))
        path = ".github/skills/traceability-audit/policy/traceability-policy.yaml"
        (self.root / path).parent.mkdir(parents=True)
        shutil.copyfile(REPOSITORY / path, self.root / path)
        command = [sys.executable, str(REPOSITORY / ".github/skills/traceability-audit/scripts/trace_check.py"), "--repo-root", str(self.root), "--scope", "ADDR"]
        for extra in ([], ["--no-write"]):
            result = subprocess.run(command + extra, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        validation = read(self.root, "reports/traceability/validation-result.json")
        self.assertEqual(validation["source_baseline_sha256"], digest(self.root / HANDOFF))

    def module(self, skill, filename):
        path = REPOSITORY / ".github/skills" / skill / "scripts" / filename
        spec = importlib.util.spec_from_file_location("independent_" + skill.replace("-", "_"), path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_quality_and_security_accept_addr_scope_but_not_future_code_criteria(self):
        for kind in ("quality-review", "security-review"):
            module = self.module(kind, "validate_" + kind.replace("-", "_") + ".py")
            policy = yaml.safe_load((REPOSITORY / f".github/skills/{kind}/policy/{kind}-policy.yaml").read_text(encoding="utf-8"))
            errors, scope = module.validate_report_header({"audit_scope": "ADDR", "status": "PASS"}, policy)
            self.assertFalse(errors)
            self.assertEqual(scope, "ADDR")
            self.assertFalse(module.scope_includes("ADDR", "IMPLEMENTATION"))
            self.assertTrue(module.scope_includes("ADDR", "ARCHITECTURE"))

    def test_failure_triage_accepts_addr_as_source_and_return_destination(self):
        module = self.module("failure-triage", "validate_failure_triage.py")
        policy = yaml.safe_load((REPOSITORY / ".github/skills/failure-triage/policy/failure-triage-policy.yaml").read_text(encoding="utf-8"))
        errors, _, _ = module.validate_header({"status": "TRIAGED", "source_phase": "ADDR", "retry_count": 3}, policy)
        self.assertFalse(errors)
        self.assertEqual(policy["routing"]["ADR_REQUIRED"], "ADDR")
        self.assertIn("ADDR", policy["invalidation"]["ARCHITECTURE"])

    def test_default_orchestrator_has_independent_stages_and_no_finalize_call(self):
        text = (REPOSITORY / ".github/agents/sdlc-orchestrator.agent.md").read_text(encoding="utf-8")
        stages = [text.index("# Phase 2: Architecture"), text.index("# Phase 3: ADDR"), text.index("# Phase 4: Implementation")]
        self.assertEqual(stages, sorted(stages))
        self.assertNotIn("operation=FINALIZE", text)
        self.assertNotIn("operation=PREPARE", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
