from __future__ import annotations

import concurrent.futures
import csv
import hashlib
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

import experiment_recorder as recorder


class RecorderTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.run_id = "RUN-001"
        self.tick = 0
        self.base = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def clock(self):
        return (self.base + timedelta(seconds=self.tick)).isoformat(), self.tick * 1_000_000_000

    def event(self, kind, payload=None, seconds=10, identifier=None):
        self.tick += seconds
        return recorder.append(self.root, self.run_id, identifier or f"event-{self.tick}", kind, payload or {}, self.clock)

    def start(self):
        return self.event("RUN_STARTED", {"condition_id": "COND-001"}, seconds=0, identifier="start")

    def enter(self, phase, result="PASS", **extra):
        return self.event("PHASE_ENTERED", {"phase": phase, "previous_result": result, **extra})

    def finish(self, result="PASS"):
        self.event("PHASE_ENDED", {"phase": "INTEGRATION_TEST", "result": result})
        return self.event("RUN_ENDED", {"status": "COMPLETE" if result == "PASS" else "COMPLETE_WITH_UNRESOLVED", "source_fingerprint": recorder.source_fingerprint(self.root)})

    def forward(self):
        self.start()
        self.enter("IMPLEMENTATION")
        self.enter("UNIT_TEST")
        self.enter("INTEGRATION_TEST")

    def write(self, relative, value):
        path = self.root / relative
        recorder.save(path, value)
        return path

    def test_elapsed_and_each_phase_do_not_use_test_suite_duration(self):
        self.forward()
        self.finish()
        result = recorder.summary(self.root, self.run_id)
        self.assertEqual(result["time_window"]["elapsed_seconds"], 40)
        for phase in ("ARCHITECTURE", "IMPLEMENTATION", "UNIT_TEST", "INTEGRATION_TEST"):
            self.assertEqual(result["phase_times"][phase]["seconds"], 10)
        self.assertEqual(result["time_window"]["quality_pass_elapsed_seconds"], 40)
        self.assertEqual(result["time_window"]["unallocated_seconds"], 0)

    def test_rework_matrix_counts_actual_back_dispatches_to_every_earlier_phase(self):
        self.forward()
        self.enter("IMPLEMENTATION", result="FAIL", classification="IMPLEMENTATION_ERROR", reason="実装修正", trigger_agent="IntegrationTest")
        self.enter("REQUIREMENTS", result="BLOCKED", classification="REQUIREMENT_ERROR", reason="要件不足")
        self.enter("ARCHITECTURE")
        self.enter("IMPLEMENTATION")
        self.enter("UNIT_TEST")
        self.enter("INTEGRATION_TEST")
        self.finish()
        result = recorder.summary(self.root, self.run_id)
        self.assertEqual(result["rework"]["total"], 2)
        self.assertEqual(result["rework"]["by_to_phase"], {"IMPLEMENTATION": 1, "REQUIREMENTS": 1})
        self.assertEqual(result["phase_times"]["IMPLEMENTATION"]["visits"], 3)
        self.assertEqual(result["phase_times"]["IMPLEMENTATION"]["seconds"], 30)

    def test_same_phase_retry_checkpoint_is_not_rework(self):
        self.start()
        self.event("CHECKPOINT", {"reason": "同一工程の修正1"})
        self.assertEqual(recorder.summary(self.root, self.run_id)["rework"]["total"], 0)
        with self.assertRaises(ValueError):
            self.enter("ARCHITECTURE")

    def test_initial_requirements_and_final_assurance_are_timed_outside_main_window(self):
        self.event("RUN_STARTED", {"phase": "REQUIREMENTS"}, seconds=0)
        self.enter("ARCHITECTURE")
        self.enter("IMPLEMENTATION")
        self.enter("UNIT_TEST")
        self.enter("INTEGRATION_TEST")
        self.event("PHASE_ENDED", {"phase": "INTEGRATION_TEST", "result": "PASS"})
        self.enter("FULL")
        self.event("PHASE_ENDED", {"phase": "FULL", "result": "PASS"})
        self.event("RUN_ENDED", {"status": "COMPLETE", "source_fingerprint": recorder.source_fingerprint(self.root)})
        measured = recorder.summary(self.root, self.run_id)
        self.assertEqual(measured["time_window"]["elapsed_seconds"], 40)
        self.assertEqual(measured["phase_times"]["REQUIREMENTS"]["seconds"], 10)
        self.assertEqual(measured["phase_times"]["FULL"]["seconds"], 10)
        self.assertEqual(measured["measurement_window_phase_times"]["FULL"]["visits"], 0)
        self.assertEqual(measured["measurement_window_phase_times"]["REQUIREMENTS"]["visits"], 0)
        self.assertEqual(measured["time_window"]["unallocated_seconds"], 0)

    def test_completed_phase_can_be_summarized_before_integration_end(self):
        self.start()
        self.enter("IMPLEMENTATION")
        measured = recorder.summary(self.root, self.run_id)
        self.assertEqual(measured["phase_times"]["ARCHITECTURE"]["seconds"], 10)
        self.assertIsNone(measured["time_window"]["elapsed_seconds"])

    def test_missing_design_start_is_not_reconstructed_from_requirements(self):
        self.event("RUN_STARTED", {"phase": "REQUIREMENTS"}, seconds=0)
        self.assertIsNone(recorder.summary(self.root, self.run_id)["time_window"]["start"])

    def test_duplicate_dispatch_id_is_idempotent(self):
        self.start()
        payload = {"phase": "IMPLEMENTATION", "previous_result": "PASS"}
        self.event("PHASE_ENTERED", payload, identifier="dispatch-1")
        self.tick += 10
        recorder.append(self.root, self.run_id, "dispatch-1", "PHASE_ENTERED", payload, self.clock)
        self.assertEqual(len(recorder.load_events(self.root, self.run_id)), 2)

    def test_id_cannot_be_reused_for_different_facts(self):
        self.start()
        with self.assertRaises(ValueError):
            recorder.append(self.root, self.run_id, "start", "CHECKPOINT", {}, self.clock)

    def test_addr_activity_time_is_not_added_again_to_architecture(self):
        self.start()
        self.event("ACTIVITY_STARTED", {"activity_id": "addr-1", "name": "ADDR"})
        self.event("ACTIVITY_ENDED", {"activity_id": "addr-1", "result": "PASS"})
        self.enter("IMPLEMENTATION")
        self.enter("UNIT_TEST")
        self.enter("INTEGRATION_TEST")
        self.finish()
        result = recorder.summary(self.root, self.run_id)
        self.assertEqual(result["phase_times"]["ARCHITECTURE"]["seconds"], 30)
        self.assertEqual(result["activity_times"]["ADDR"]["summed_seconds"], 10)
        self.assertEqual(result["time_window"]["elapsed_seconds"], 60)

    def test_open_activity_prevents_unnoticed_phase_exit(self):
        self.start()
        self.event("ACTIVITY_STARTED", {"activity_id": "addr-1", "name": "ADDR"})
        with self.assertRaises(ValueError):
            self.enter("IMPLEMENTATION")

    def test_missing_end_is_not_invented(self):
        self.start()
        result = recorder.summary(self.root, self.run_id)
        self.assertIsNone(result["time_window"]["elapsed_seconds"])
        self.assertIsNone(result["phase_times"]["ARCHITECTURE"]["seconds"])

    def test_interruption_retains_unknown_time_instead_of_fabricating_end(self):
        self.start()
        self.event("INTERRUPTED", {"reason": "アプリ中断。実際の停止時刻は不明"})
        self.enter("ARCHITECTURE")
        self.enter("IMPLEMENTATION")
        self.enter("UNIT_TEST")
        self.enter("INTEGRATION_TEST")
        self.finish()
        result = recorder.summary(self.root, self.run_id)
        self.assertIsNone(result["phase_times"]["ARCHITECTURE"]["seconds"])
        self.assertGreater(result["time_window"]["unallocated_seconds"], 0)

    def test_unresolved_completion_is_not_quality_pass_completion(self):
        self.forward()
        self.finish("CONTINUE_WITH_UNRESOLVED")
        result = recorder.summary(self.root, self.run_id)
        self.assertEqual(result["time_window"]["elapsed_seconds"], 40)
        self.assertIsNone(result["time_window"]["quality_pass_elapsed_seconds"])
        self.assertEqual(result["run_status"], "COMPLETE_WITH_UNRESOLVED")

    def test_rework_after_integration_invalidates_old_completion_time(self):
        self.forward()
        self.event("PHASE_ENDED", {"phase": "INTEGRATION_TEST", "result": "PASS"})
        self.enter("FULL")
        self.enter("IMPLEMENTATION", result="FAIL", classification="IMPLEMENTATION_ERROR", reason="最終監査で修正")
        self.assertIsNone(recorder.summary(self.root, self.run_id)["time_window"]["elapsed_seconds"])
        self.enter("UNIT_TEST")
        self.enter("INTEGRATION_TEST")
        self.finish()
        self.assertEqual(recorder.summary(self.root, self.run_id)["time_window"]["elapsed_seconds"], 90)

    def test_backward_wall_clock_is_rejected(self):
        self.start()
        self.tick = -10
        with self.assertRaises(ValueError):
            recorder.append(self.root, self.run_id, "bad-clock", "CHECKPOINT", {}, self.clock)

    def test_clock_adjustment_marks_timing_for_review(self):
        self.forward()
        self.tick += 10
        recorder.append(self.root, self.run_id, "bad-clock", "CHECKPOINT", {}, lambda: ((self.base + timedelta(seconds=100)).isoformat(), 40 * 1_000_000_000))
        self.tick = 110
        self.event("PHASE_ENDED", {"phase": "INTEGRATION_TEST", "result": "PASS"})
        self.assertIsNone(recorder.summary(self.root, self.run_id)["time_window"]["elapsed_seconds"])

    def test_sqlite_transaction_preserves_concurrent_checkpoints(self):
        recorder.append(self.root, self.run_id, "start", "RUN_STARTED", {})
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            list(executor.map(lambda number: recorder.append(self.root, self.run_id, f"checkpoint-{number}", "CHECKPOINT", {}), range(12)))
        self.assertEqual(len(recorder.load_events(self.root, self.run_id)), 13)

    def test_journal_tampering_is_detected(self):
        self.start()
        path = recorder.directory(self.root, self.run_id) / "events.sqlite3"
        with closing(sqlite3.connect(path)) as connection:
            connection.execute("UPDATE events SET body = replace(body, 'COND-001', 'TAMPERED')")
            connection.commit()
        with self.assertRaises(ValueError):
            recorder.load_events(self.root, self.run_id)

    def test_journal_cannot_be_relabelled_as_another_experiment(self):
        self.start()
        source = recorder.directory(self.root, self.run_id)
        target = recorder.directory(self.root, "RUN-002")
        target.mkdir()
        (target / "events.sqlite3").write_bytes((source / "events.sqlite3").read_bytes())
        with self.assertRaises(ValueError):
            recorder.load_events(self.root, "RUN-002")
        with self.assertRaises(ValueError):
            recorder.append(self.root, "RUN-002", "checkpoint", "CHECKPOINT", {}, self.clock)

    def test_safe_paths_and_run_ids(self):
        for identifier in ("../escape", "C:/escape", "RUN/001"):
            with self.assertRaises(ValueError):
                recorder.directory(self.root, identifier)

    def test_raw_branch_percentage_is_computed_from_counts(self):
        coverage = {"meta": {"branch_coverage": True}, "totals": {"num_branches": 8, "covered_branches": 6, "percent_covered": 99}}
        self.assertEqual(recorder.branch_coverage(coverage)["rate"], 75)
        self.assertEqual(recorder.branch_coverage({"total": {"branches": {"total": 10, "covered": 8, "pct": 80}}})["rate"], 80)

    def test_line_coverage_and_rate_only_are_not_treated_as_branch_coverage(self):
        for data in ({"totals": {"percent_covered": 100}}, {"total": {"branches": 83}}, {"meta": {"branch_coverage": False}, "totals": {"num_branches": 0, "covered_branches": 0}}):
            self.assertIsNone(recorder.branch_coverage(data)["rate"])

    def test_zero_branches_is_not_automatically_100_percent(self):
        result = recorder.branch_coverage({"meta": {"branch_coverage": True}, "totals": {"num_branches": 0, "covered_branches": 0}})
        self.assertEqual(result["status"], "NO_BRANCHES")
        self.assertIsNone(result["rate"])

    def test_invalid_branch_counts_are_rejected(self):
        for total, covered in ((3, 4), (-1, 0), (True, 1)):
            with self.assertRaises(ValueError):
                recorder.branch_coverage({"meta": {"branch_coverage": True}, "totals": {"num_branches": total, "covered_branches": covered}})

    def unit_run(self, failed=False, produce=True):
        recorder.append(self.root, self.run_id, "start", "RUN_STARTED", {})
        recorder.append(self.root, self.run_id, "unit", "PHASE_ENTERED", {"phase": "UNIT_TEST", "previous_result": "PASS"})
        code = "from pathlib import Path; import json; Path('reports/unit-test').mkdir(parents=True,exist_ok=True); Path('reports/unit-test/coverage.json').write_text(json.dumps({'meta':{'branch_coverage':True},'totals':{'num_branches':4,'covered_branches':3}})); Path('reports/unit-test/junit.xml').write_text('<testsuite/>'); print('never-store-this-secret')"
        if not produce:
            code = "pass"
        if failed:
            code += "; raise SystemExit(1)"
        spec = {"commands": [[sys.executable, "-c", code]], "coverage": "reports/unit-test/coverage.json", "junit": "reports/unit-test/junit.xml"}
        result = recorder.run_unit(self.root, self.run_id, "unit-exec-1", spec)
        return spec, result

    def test_actual_unit_command_records_branch_counts_even_when_tests_fail(self):
        _, result = self.unit_run(failed=True)
        self.assertEqual(result, 1)
        measurement = recorder.summary(self.root, self.run_id)["unit_branch_coverage"]
        self.assertEqual(measurement["rate"], 75)
        self.assertEqual(measurement["execution"]["exit_code"], 1)
        self.assertNotIn("never-store-this-secret", recorder.canonical(recorder.load_events(self.root, self.run_id)))

    def test_duplicate_unit_command_id_does_not_execute_twice(self):
        spec, _ = self.unit_run()
        count = len(recorder.load_events(self.root, self.run_id))
        self.assertEqual(recorder.run_unit(self.root, self.run_id, "unit-exec-1", spec), 0)
        self.assertEqual(len(recorder.load_events(self.root, self.run_id)), count)

    def test_actual_command_specification_is_preserved_as_fixed_evidence(self):
        specification, _ = self.unit_run()
        execution = recorder.summary(self.root, self.run_id)["unit_branch_coverage"]["execution"]
        stored = recorder.read(recorder.artifact(self.root, execution["command_spec"]))
        self.assertEqual(stored, specification)

    def test_missing_or_unchanged_test_artifacts_are_unconfirmed(self):
        self.write("reports/unit-test/coverage.json", {"meta": {"branch_coverage": True}, "totals": {"num_branches": 4, "covered_branches": 4}})
        (self.root / "reports/unit-test/junit.xml").write_text("<testsuite/>", encoding="utf-8")
        self.unit_run(produce=False)
        self.assertIsNone(recorder.summary(self.root, self.run_id)["unit_branch_coverage"]["rate"])

    def test_source_change_invalidates_earlier_coverage(self):
        self.unit_run()
        self.write("app/changed.json", {"new_code": True})
        self.assertEqual(recorder.summary(self.root, self.run_id)["unit_branch_coverage"]["status"], "STALE")

    def test_original_report_overwrite_does_not_destroy_coverage_evidence(self):
        self.unit_run()
        self.write("reports/unit-test/coverage.json", {"overwritten": True})
        self.assertEqual(recorder.summary(self.root, self.run_id)["unit_branch_coverage"]["rate"], 75)

    def test_captured_artifact_tampering_is_detected(self):
        self.unit_run()
        events = recorder.load_events(self.root, self.run_id)
        reference = events[-1]["payload"]["coverage"]
        self.write(reference["path"], {"tampered": True})
        with self.assertRaises(ValueError):
            recorder.summary(self.root, self.run_id)

    def test_frozen_initial_cases_and_final_inventory_are_distinct(self):
        self.forward()
        initial = {"cases": [{"case_id": "IT-001", "title": "初期項目", "origin": "AI_GENERATED", "generation_stage": "INITIAL", "expected_result": "正常"}]}
        plan = {"cases": initial["cases"] + [{"case_id": "EXT-001", "title": "人の結合項目", "origin": "EXTERNAL", "generation_stage": "EXTERNAL", "expected_result": "拒否"}]}
        self.write("reports/integration-test/ai-initial-cases.json", initial)
        self.write("reports/integration-test/integration-test-plan.json", plan)
        recorder.capture_integration(self.root, self.run_id, "initial", "AI_INITIAL", "reports/integration-test/ai-initial-cases.json", self.clock)
        recorder.capture_integration(self.root, self.run_id, "plan", "INTEGRATION_PLAN", "reports/integration-test/integration-test-plan.json", self.clock)
        measured = recorder.summary(self.root, self.run_id)["integration"]
        self.assertEqual(measured["total"], 2)
        self.assertEqual(measured["initial_total"], 1)
        self.assertEqual(measured["cases"][0]["expected_result"], "正常")
        self.write("reports/integration-test/ai-initial-cases.json", {"cases": []})
        with self.assertRaises(ValueError):
            recorder.capture_integration(self.root, self.run_id, "altered", "AI_INITIAL", "reports/integration-test/ai-initial-cases.json", self.clock)

    def acceptance_files(self):
        completed = recorder.replay(recorder.load_events(self.root, self.run_id))["ended"]["at"]
        manifest = {"run_id": self.run_id, "sdlc_completed_at": completed, "evaluation_data_exposed_at": completed, "cases": [{"case_id": f"AC-{number}", "requirement_id": "FR-001", "requirement_type": "FUNCTIONAL"} for number in range(3)]}
        statuses = ("PASS", "FAIL", "BLOCKED")
        rows = [{**case, "result": statuses[index]} for index, case in enumerate(manifest["cases"])]
        evidence = {"run_id": self.run_id, "manifest_sha256": hashlib.sha256(recorder.canonical(manifest).encode()).hexdigest(), "cases": rows, "summary": {"total": 3, "passed": 1, "failed": 1, "blocked": 1}}
        manifest_path = self.write("reports/hidden-input/acceptance-test-manifest.json", manifest)
        evidence_path = self.write("reports/hidden-input/evidence.json", evidence)
        results_path = self.root / "reports/hidden-input/results.csv"
        with results_path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        return manifest_path, results_path, evidence_path

    def test_final_plan_cannot_modify_frozen_initial_expected_result(self):
        self.forward()
        initial = {"cases": [{"case_id": "IT-001", "expected_result": "拒否"}]}
        self.write("reports/integration-test/initial.json", initial)
        recorder.capture_integration(self.root, self.run_id, "initial", "AI_INITIAL", "reports/integration-test/initial.json", self.clock)
        self.write("reports/integration-test/plan.json", {"cases": [{"case_id": "IT-001", "expected_result": "成功"}]})
        recorder.capture_integration(self.root, self.run_id, "plan", "INTEGRATION_PLAN", "reports/integration-test/plan.json", self.clock)
        self.assertEqual(recorder.summary(self.root, self.run_id)["integration"]["status"], "INVALID")

    def test_integration_results_are_bound_to_captured_plan_not_later_plan(self):
        self.forward()
        source = "reports/integration-test/plan.json"
        evidence = "reports/integration-test/evidence.json"
        self.write(source, {"cases": [{"case_id": "IT-001"}]})
        self.write(evidence, {"case_results": [{"case_id": "IT-001", "result": "PASS"}]})
        recorder.capture_integration(self.root, self.run_id, "plan-1", "INTEGRATION_PLAN", source, self.clock)
        recorder.capture_integration(self.root, self.run_id, "results-1", "INTEGRATION_RESULT", evidence, self.clock)
        self.assertEqual(recorder.summary(self.root, self.run_id)["integration"]["result_binding"], "BOUND")
        self.write(source, {"cases": [{"case_id": "IT-001"}, {"case_id": "IT-002"}]})
        recorder.capture_integration(self.root, self.run_id, "plan-2", "INTEGRATION_PLAN", source, self.clock)
        measured = recorder.summary(self.root, self.run_id)["integration"]
        self.assertEqual(measured["result_binding"], "UNCONFIRMED")
        self.assertEqual({case["result"] for case in measured["cases"]}, {"UNCONFIRMED"})

    def test_changed_live_plan_does_not_bind_old_result_to_captured_plan(self):
        self.forward()
        source = "reports/integration-test/plan.json"
        self.write(source, {"cases": [{"case_id": "IT-001"}]})
        recorder.capture_integration(self.root, self.run_id, "plan", "INTEGRATION_PLAN", source, self.clock)
        self.write(source, {"cases": [{"case_id": "IT-002"}]})
        self.write("reports/integration-test/evidence.json", {"case_results": [{"case_id": "IT-002", "result": "PASS"}]})
        recorder.capture_integration(self.root, self.run_id, "results", "INTEGRATION_RESULT", "reports/integration-test/evidence.json", self.clock)
        self.assertEqual(recorder.summary(self.root, self.run_id)["integration"]["result_binding"], "UNCONFIRMED")

    def test_acceptance_rate_uses_all_human_cases_including_blocked(self):
        self.forward()
        self.finish()
        before = recorder.summary(self.root, self.run_id)["time_window"]
        paths = self.acceptance_files()
        recorder.capture_acceptance(self.root, self.run_id, "acceptance", *paths, now=self.clock)
        result = recorder.summary(self.root, self.run_id)
        self.assertEqual(result["acceptance"]["rate"], 33.33)
        self.assertEqual(result["acceptance"]["blocked"], 1)
        self.assertEqual(result["time_window"], before)

    def test_acceptance_cannot_be_imported_during_development(self):
        self.forward()
        with self.assertRaises(ValueError):
            recorder.capture_acceptance(self.root, self.run_id, "acceptance", Path("missing"), Path("missing"), Path("missing"), now=self.clock)

    def test_existing_acceptance_executor_cli_automatically_adds_measurement(self):
        self.forward()
        self.finish()
        paths = self.acceptance_files()
        manifest = recorder.read(paths[0])
        manifest["schema_version"] = 1
        for case in manifest["cases"]:
            case.update(execution_type="COMMAND", command=[sys.executable, "-c", "pass"], expected={"exit_code": 0})
        recorder.save(paths[0], manifest)
        directory = Path(recorder.__file__).resolve().parents[2] / "acceptance-test-execution"
        result = subprocess.run([sys.executable, str(directory / "scripts/run_acceptance_tests.py"), "--repo-root", str(self.root), "--input-dir", str(paths[0].parent), "--policy", str(directory / "policy/acceptance-test-policy.yaml")], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertNotIn("MEASUREMENT WARNING", result.stdout)
        measured = recorder.summary(self.root, self.run_id)["acceptance"]
        self.assertEqual(measured["rate"], 100)
        self.assertEqual(measured["total"], 3)

    def test_acceptance_missing_rows_cannot_inflate_rate(self):
        self.forward()
        self.finish()
        paths = self.acceptance_files()
        content = paths[1].read_text(encoding="utf-8").splitlines()
        paths[1].write_text("\n".join(content[:2]) + "\n", encoding="utf-8")
        recorder.capture_acceptance(self.root, self.run_id, "acceptance", *paths, now=self.clock)
        self.assertIsNone(recorder.summary(self.root, self.run_id)["acceptance"]["rate"])

    def test_acceptance_different_baseline_is_not_reported_as_verified(self):
        self.forward()
        self.finish()
        paths = self.acceptance_files()
        self.write("app/source-changed.json", {"changed": True})
        recorder.capture_acceptance(self.root, self.run_id, "acceptance", *paths, now=self.clock)
        self.assertIsNone(recorder.summary(self.root, self.run_id)["acceptance"]["rate"])

    def test_acceptance_manifest_must_use_same_run_identity(self):
        self.forward()
        self.finish()
        paths = self.acceptance_files()
        manifest = recorder.read(paths[0])
        manifest["run_id"] = "RUN-OTHER"
        recorder.save(paths[0], manifest)
        with self.assertRaises(ValueError):
            recorder.capture_acceptance(self.root, self.run_id, "acceptance", *paths, now=self.clock)

    def test_acceptance_exposure_is_checked_against_actual_recorded_completion(self):
        self.forward()
        self.finish()
        paths = self.acceptance_files()
        manifest = recorder.read(paths[0])
        manifest["sdlc_completed_at"] = self.base.isoformat()
        manifest["evaluation_data_exposed_at"] = self.base.isoformat()
        recorder.save(paths[0], manifest)
        with self.assertRaises(ValueError):
            recorder.capture_acceptance(self.root, self.run_id, "acceptance", *paths, now=self.clock)

    def test_export_keeps_events_and_vs_code_tokens_unknown(self):
        self.forward()
        self.finish()
        result = recorder.export(self.root, self.run_id)
        self.assertIsNone(result["tokens"]["value"])
        folder = recorder.directory(self.root, self.run_id)
        self.assertTrue((folder / "events.jsonl").is_file())
        self.assertTrue((folder / "measurement-report.md").is_file())
        self.assertTrue((folder / "rework-events.json").is_file())

    def test_cli_records_and_summarizes_without_user_supplied_timestamps(self):
        command = [sys.executable, str(Path(recorder.__file__))]
        for arguments in (["start"], ["summarize"]):
            result = subprocess.run([*command, *arguments, "--root", str(self.root), "--run-id", self.run_id], capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((recorder.directory(self.root, self.run_id) / "metrics.json").is_file())


if __name__ == "__main__":
    unittest.main(verbosity=2)
