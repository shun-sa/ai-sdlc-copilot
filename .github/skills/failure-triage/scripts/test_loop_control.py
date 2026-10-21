from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import loop_control as control


REPOSITORY = Path(__file__).resolve().parents[4]


class LoopControlTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        target = self.root / control.POLICY
        target.parent.mkdir(parents=True)
        shutil.copyfile(REPOSITORY / control.POLICY, target)
        self.checks = {}
        for key in control.policy(self.root)["required_checks"]["ARCHITECTURE"]:
            path = f"reports/checks/{key}.json"
            self.write(path, {"status": "PASS", "audit_scope": "ARCHITECTURE", "errors": []})
            self.checks[key] = path
        self.write(self.checks["architecture_gate"], {"status": "FAIL", "audit_scope": "ARCHITECTURE", "errors": ["Design unresolved"]})
        self.signature = {"origin_phase": "ARCHITECTURE", "classification": "ADR_REQUIRED", "artifact": "docs/addr/ADDR-001.md", "requirement_reference": "FR-001", "test_case": "", "stable_error_type": "decision_missing"}

    def write(self, path, data):
        control.save(self.root / path, data)

    def event(self, cycle=0, **changes):
        value = {"signature": self.signature, "cycle": cycle, "run_id": f"actual-run-{cycle}", "repair": f"修正と実再検査 {cycle}" if cycle else "", "validation_result": self.checks["architecture_gate"], "impact": "FR-001の実装・テストは判断未確定", "recommended_route": "ADDR"}
        value.update(changes)
        return value

    def exhaust(self):
        for cycle in range(4):
            identifier = control.record(self.root, self.event(cycle))
        return identifier

    def test_initial_failure_is_not_a_repair(self):
        identifier = control.record(self.root, self.event())
        issue = control.ledger(self.root)["issues"][identifier]
        self.assertEqual(issue["cycle"], 0)
        self.assertEqual(issue["state"], "OPEN")

    def test_one_or_two_repairs_cannot_advance(self):
        for cycle in range(3):
            control.record(self.root, self.event(cycle))
            with self.assertRaises(ValueError):
                control.phase_decision(self.root, "ARCHITECTURE", self.checks)

    def test_third_repair_records_unresolved_and_continues_not_pass(self):
        identifier = self.exhaust()
        decision = control.phase_decision(self.root, "ARCHITECTURE", self.checks)
        self.assertEqual(decision["status"], "CONTINUE_WITH_UNRESOLVED")
        self.assertFalse(decision["quality_pass"])
        self.assertIn(identifier, decision["unresolved_ids"])
        self.assertEqual(control.read(self.root / self.checks["architecture_gate"])["status"], "FAIL")
        self.assertEqual(control.verify_transition(self.root, "ARCHITECTURE"), decision)

    def test_fourth_repair_is_rejected(self):
        self.exhaust()
        with self.assertRaises(ValueError):
            control.record(self.root, self.event(4))

    def test_cannot_skip_repairs(self):
        with self.assertRaises(ValueError):
            control.record(self.root, self.event(3))

    def test_duplicate_run_is_idempotent_not_another_retry(self):
        identifier = control.record(self.root, self.event())
        control.record(self.root, self.event())
        self.assertEqual(len(control.ledger(self.root)["issues"][identifier]["history"]), 1)

    def test_reused_run_id_with_changed_evidence_is_rejected(self):
        control.record(self.root, self.event())
        with self.assertRaises(ValueError):
            control.record(self.root, self.event(1, run_id="actual-run-0"))

    def test_retry_requires_actual_repair_description(self):
        control.record(self.root, self.event())
        with self.assertRaises(ValueError):
            control.record(self.root, self.event(1, repair=""))

    def test_two_different_failures_do_not_share_budget(self):
        self.exhaust()
        other = copy.deepcopy(self.event())
        other["signature"] = {**self.signature, "stable_error_type": "different_root_cause"}
        control.record(self.root, other)
        with self.assertRaises(ValueError):
            control.phase_decision(self.root, "ARCHITECTURE", self.checks)

    def test_pass_cannot_be_registered_as_failure(self):
        with self.assertRaises(ValueError):
            control.record(self.root, self.event(validation_result=self.checks["design_draft"]))

    def test_only_errors_in_actual_result_can_be_registered(self):
        with self.assertRaises(ValueError):
            control.record(self.root, self.event(errors=["fabricated"]))

    def test_all_failed_checks_must_be_covered(self):
        self.exhaust()
        self.write(self.checks["traceability"], {"status": "FAIL", "errors": ["Another failure"]})
        with self.assertRaises(ValueError):
            control.phase_decision(self.root, "ARCHITECTURE", self.checks)

    def test_cannot_omit_or_duplicate_phase_checks(self):
        self.exhaust()
        missing = {key: path for key, path in self.checks.items() if key != "traceability"}
        duplicate = {**self.checks, "traceability": self.checks["quality"]}
        for checks in (missing, duplicate):
            with self.assertRaises(ValueError):
                control.phase_decision(self.root, "ARCHITECTURE", checks)

    def test_wrong_scope_report_cannot_satisfy_a_check(self):
        self.exhaust()
        self.write(self.checks["quality"], {"status": "PASS", "audit_scope": "FULL", "errors": []})
        with self.assertRaises(ValueError):
            control.phase_decision(self.root, "ARCHITECTURE", self.checks)

    def test_changed_baseline_invalidates_transition(self):
        self.exhaust()
        control.phase_decision(self.root, "ARCHITECTURE", self.checks)
        self.write("docs/architecture/new-design.json", {"changed": True})
        with self.assertRaises(ValueError):
            control.verify_transition(self.root, "ARCHITECTURE")

    def test_implementation_does_not_invalidate_architecture_transition(self):
        self.exhaust()
        control.phase_decision(self.root, "ARCHITECTURE", self.checks)
        self.write("app/new-source.json", {"new_implementation": True})
        self.assertEqual(control.verify_transition(self.root, "ARCHITECTURE")["status"], "CONTINUE_WITH_UNRESOLVED")

    def test_downstream_report_overwrite_does_not_erase_archived_evidence(self):
        self.exhaust()
        control.phase_decision(self.root, "ARCHITECTURE", self.checks)
        self.write(self.checks["quality"], {"status": "PASS", "audit_scope": "UNIT_TEST", "errors": []})
        control.verify_transition(self.root, "ARCHITECTURE")

    def test_tampered_history_evidence_invalidates_transition(self):
        identifier = self.exhaust()
        control.phase_decision(self.root, "ARCHITECTURE", self.checks)
        evidence = control.ledger(self.root)["issues"][identifier]["history"][0]["evidence"]
        self.write(evidence["path"], {"status": "PASS", "errors": []})
        with self.assertRaises(ValueError):
            control.verify_transition(self.root, "ARCHITECTURE")

    def test_current_observation_refresh_does_not_start_another_repair(self):
        identifier = self.exhaust()
        self.write(self.checks["architecture_gate"], {"status": "FAIL", "errors": ["Current form of same root cause"]})
        with self.assertRaises(ValueError):
            control.phase_decision(self.root, "ARCHITECTURE", self.checks)
        control.record(self.root, self.event(3, action="OBSERVE", run_id="downstream-observation", repair=""))
        self.assertEqual(control.ledger(self.root)["issues"][identifier]["cycle"], 3)
        control.phase_decision(self.root, "ARCHITECTURE", self.checks)

    def test_resolution_requires_pass_evidence(self):
        self.exhaust()
        with self.assertRaises(ValueError):
            control.record(self.root, self.event(action="RESOLVED", run_id="resolution"))

    def test_resolved_failure_is_removed_from_unresolved_results(self):
        identifier = self.exhaust()
        self.write(self.checks["architecture_gate"], {"status": "PASS", "errors": []})
        control.record(self.root, self.event(action="RESOLVED", run_id="resolution"))
        self.assertEqual(control.ledger(self.root)["issues"][identifier]["state"], "RESOLVED")
        self.assertEqual(control.phase_decision(self.root, "ARCHITECTURE", self.checks)["status"], "PASS")
        self.assertFalse(control.read(self.root / control.DIRECTORY / "unresolved-results.json")["issues"])

    def test_old_conditional_decision_is_invalidated_by_resolution(self):
        self.exhaust()
        control.phase_decision(self.root, "ARCHITECTURE", self.checks)
        self.write(self.checks["architecture_gate"], {"status": "PASS", "errors": []})
        control.record(self.root, self.event(action="RESOLVED", run_id="resolution"))
        with self.assertRaises(ValueError):
            control.verify_transition(self.root, "ARCHITECTURE")

    def test_real_resolution_then_recurrence_starts_new_episode_with_history(self):
        identifier = self.exhaust()
        self.write(self.checks["architecture_gate"], {"status": "PASS", "errors": []})
        control.record(self.root, self.event(action="RESOLVED", run_id="resolution"))
        self.write(self.checks["architecture_gate"], {"status": "FAIL", "errors": ["Design unresolved"]})
        control.record(self.root, self.event(run_id="new-episode"))
        issue = control.ledger(self.root)["issues"][identifier]
        self.assertEqual(issue["cycle"], 0)
        self.assertEqual(issue["state"], "OPEN")
        self.assertEqual(len(issue["previous_episodes"]), 1)

    def test_later_phase_inherits_unresolved_without_a_new_loop(self):
        self.exhaust()
        checks = {}
        for key in control.policy(self.root)["required_checks"]["UNIT_TEST"]:
            relative = f"reports/unit/{key}.json"
            self.write(relative, {"status": "PASS", "audit_scope": "UNIT_TEST", "errors": []})
            checks[key] = relative
        decision = control.phase_decision(self.root, "UNIT_TEST", checks)
        self.assertEqual(decision["status"], "CONTINUE_WITH_UNRESOLVED")
        self.assertEqual(len(control.ledger(self.root)["issues"]), 1)

    def test_new_downstream_failure_does_not_block_existing_architecture_handoff(self):
        self.exhaust()
        control.phase_decision(self.root, "ARCHITECTURE", self.checks)
        relative = "reports/unit/downstream.json"
        self.write(relative, {"status": "FAIL", "errors": ["unit failure"]})
        signature = {**self.signature, "origin_phase": "UNIT_TEST", "classification": "TEST_ERROR", "artifact": "tests/unit/test_case.py", "stable_error_type": "assertion_error"}
        for cycle in range(4):
            control.record(self.root, {**self.event(cycle), "signature": signature, "validation_result": relative, "run_id": f"unit-run-{cycle}"})
            self.assertEqual(control.verify_transition(self.root, "ARCHITECTURE")["status"], "CONTINUE_WITH_UNRESOLVED")

    def test_snapshot_detects_external_manifest_source_changes(self):
        self.write("reports/architecture/design-manifest.json", {"sources": [{"path": "inputs/spec.json"}], "artifacts": []})
        self.write("inputs/spec.json", {"version": 1})
        self.exhaust()
        control.phase_decision(self.root, "ARCHITECTURE", self.checks)
        self.write("inputs/spec.json", {"version": 2})
        with self.assertRaises(ValueError):
            control.verify_transition(self.root, "ARCHITECTURE")

    def test_run_check_captures_failure_without_storing_secret_stdout(self):
        specification = {"command": [sys.executable, "-c", "print('secret-value'); raise SystemExit(1)"], "check_id": "actual-check", "result_path": "reports/check.json"}
        report = control.run_check(self.root, specification)
        self.assertEqual(report["status"], "FAIL")
        self.assertNotIn("secret-value", (self.root / "reports/check.json").read_text(encoding="utf-8"))

    def test_run_check_failure_without_executable_is_recorded(self):
        report = control.run_check(self.root, {"command": ["nonexistent-command-test"], "check_id": "missing", "result_path": "reports/check.json"})
        self.assertEqual(report["exit_code"], -1)

    def test_paths_cannot_escape_repository(self):
        for path in ("../escape", "C:/escape", "/escape"):
            with self.assertRaises(ValueError):
                control.local(self.root, path)

    def test_no_failure_produces_ordinary_pass(self):
        self.write(self.checks["architecture_gate"], {"status": "PASS", "errors": []})
        self.assertTrue(control.phase_decision(self.root, "ARCHITECTURE", self.checks)["quality_pass"])

    def test_cli_records_and_verifies_conditional_continuation(self):
        command = [sys.executable, str(Path(control.__file__)), "--root", str(self.root)]
        for cycle in range(4):
            self.write("reports/event.json", self.event(cycle))
            result = subprocess.run([*command, "--record", "reports/event.json"], capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(result.returncode, 0, result.stderr)
        self.write("reports/checks.json", self.checks)
        result = subprocess.run([*command, "--decide-phase", "ARCHITECTURE", "--checks", "reports/checks.json"], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("CONTINUE_WITH_UNRESOLVED", result.stdout)
        result = subprocess.run([*command, "--check-phase", "ARCHITECTURE"], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_cli_without_transition_decision_cannot_advance(self):
        result = subprocess.run([sys.executable, str(Path(control.__file__)), "--root", str(self.root), "--check-phase", "ARCHITECTURE"], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("Traceback", result.stderr)

    def test_unresolved_result_contains_impact_and_route(self):
        self.exhaust()
        text = (self.root / control.DIRECTORY / "unresolved-results.md").read_text(encoding="utf-8")
        self.assertIn("修正・再検査: 3回", text)
        self.assertIn("FR-001の実装・テストは判断未確定", text)
        self.assertIn("ADDR", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
