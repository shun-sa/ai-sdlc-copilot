#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

import yaml


SCRIPT_DIR = Path(__file__).resolve().parent


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPT_DIR / filename)
    if spec is None or spec.loader is None:
        raise RuntimeError(filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


evaluate_run = load_module("evaluate_run", "evaluate_run.py")
validate_evaluation = load_module("validate_evaluation", "validate_evaluation.py")
aggregate_experiments = load_module("aggregate_experiments", "aggregate_experiments.py")


def policy() -> dict[str, Any]:
    return {
        "isolation": {
            "require_sdlc_complete_before_evaluation": True,
            "require_evaluation_data_exposed_after_complete": True,
            "forbid_development_external_cases_as_hidden_acceptance": True,
            "forbidden_acceptance_path_fragments": ["external-tests/integration-test"],
        },
        "requirement_satisfaction": {
            "pass_results": ["PASS"],
            "functional_types": ["FUNCTIONAL", "FR"],
            "non_functional_types": ["NON_FUNCTIONAL", "NFR"],
        },
        "unit_test_coverage": {
            "enabled": True,
            "metric": "branches",
            "source": "reports/unit-test/coverage-summary.json",
        },
        "integration_generated_test_coverage": {
            "enabled": True,
            "ai_case_source": "reports/integration-test/ai-initial-cases.json",
            "required_origin": "AI_GENERATED",
            "required_generation_stage": "INITIAL",
            "trace_key_field": "coverage_key",
        },
        "human_effort": {
            "input_event_types": ["PROMPT", "CORRECTION", "OTHER_INPUT"],
            "review_event_type": "REVIEW",
            "correction_event_type": "CORRECTION",
            "require_active_work_seconds": True,
        },
        "rework": {
            "target_phase": "IMPLEMENTATION",
            "count_from_phases": [
                "UNIT_TEST",
                "INTEGRATION_TEST",
                "FINAL_ASSURANCE",
                "QUALITY_REVIEW",
                "SECURITY_REVIEW",
                "TRACEABILITY",
            ],
            "excluded_classifications": ["REFACTOR", "FORMAT_ONLY"],
            "exclude_minor_refactoring": True,
        },
        "ai_usage": {
            "require_input_tokens": True,
            "require_output_tokens": True,
            "require_design_context_tokens": False,
            "allow_total_from_input_plus_output": True,
            "exclude_evaluation_agent_usage": True,
        },
        "inputs": {"required_keys": []},
        "aggregation": {
            "recommended_repetitions": 5,
            "use_sample_standard_deviation": True,
            "numeric_metrics": [
                "metrics.quality.requirement_satisfaction.overall.rate",
            ],
        },
    }


class RequirementSatisfactionTest(unittest.TestCase):
    def test_rates(self):
        rows = [
            {"case_id": "A", "requirement_type": "FUNCTIONAL", "result": "PASS"},
            {"case_id": "B", "requirement_type": "FUNCTIONAL", "result": "FAIL"},
            {"case_id": "C", "requirement_type": "NON_FUNCTIONAL", "result": "PASS"},
        ]
        result, errors = evaluate_run.evaluate_requirement_satisfaction(rows, policy())
        self.assertEqual([], errors)
        self.assertEqual(66.67, result["overall"]["rate"])
        self.assertEqual(50.0, result["functional"]["rate"])
        self.assertEqual(100.0, result["non_functional"]["rate"])

    def test_duplicate_conflicting_result_fails(self):
        rows = [
            {"case_id": "A", "requirement_type": "FUNCTIONAL", "result": "PASS"},
            {"case_id": "A", "requirement_type": "FUNCTIONAL", "result": "FAIL"},
        ]
        _, errors = evaluate_run.evaluate_requirement_satisfaction(rows, policy())
        self.assertTrue(any("conflicting results" in e for e in errors))


class IsolationTest(unittest.TestCase):
    def test_exposure_after_complete_passes(self):
        manifest = {
            "sdlc_completed_at": "2026-01-01T12:00:00+09:00",
            "evaluation_data_exposed_at": "2026-01-01T12:01:00+09:00",
        }
        errors = evaluate_run.validate_isolation(
            manifest, Path("/tmp/acceptance.csv"), policy()
        )
        self.assertEqual([], errors)

    def test_exposure_before_complete_fails(self):
        manifest = {
            "sdlc_completed_at": "2026-01-01T12:00:00+09:00",
            "evaluation_data_exposed_at": "2026-01-01T11:59:00+09:00",
        }
        errors = evaluate_run.validate_isolation(
            manifest, Path("/tmp/acceptance.csv"), policy()
        )
        self.assertTrue(any("before SDLC COMPLETE" in e for e in errors))

    def test_development_external_path_fails(self):
        manifest = {
            "sdlc_completed_at": "2026-01-01T12:00:00+09:00",
            "evaluation_data_exposed_at": "2026-01-01T12:01:00+09:00",
        }
        errors = evaluate_run.validate_isolation(
            manifest,
            Path("/repo/external-tests/integration-test/results.csv"),
            policy(),
        )
        self.assertTrue(any("External Integration Test path" in e for e in errors))


class UnitCoverageTest(unittest.TestCase):
    def test_branch_coverage(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            p = root / "reports/unit-test"
            p.mkdir(parents=True)
            (p / "coverage-summary.json").write_text(
                json.dumps({"total": {"branches": 91.67}}),
                encoding="utf-8",
            )
            result, errors = evaluate_run.evaluate_unit_coverage(root, policy())
            self.assertEqual([], errors)
            self.assertEqual(91.67, result["rate"])


class IntegrationCoverageTest(unittest.TestCase):
    def test_ai_initial_only(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            p = root / "reports/integration-test"
            p.mkdir(parents=True)
            (p / "ai-initial-cases.json").write_text(
                json.dumps({
                    "origin": "AI_GENERATED",
                    "generation_stage": "INITIAL",
                    "cases": [
                        {
                            "case_id": "I1",
                            "requirement_id": "FR-001",
                            "coverage_key": "k1",
                        },
                        {
                            "case_id": "I2",
                            "requirement_id": "FR-002",
                            "coverage_key": "k2",
                            "generation_stage": "GAP_FILL",
                        },
                    ],
                }),
                encoding="utf-8",
            )
            rows = [
                {"requirement_id": "FR-001", "coverage_key": "k1"},
                {"requirement_id": "FR-002", "coverage_key": "k2"},
            ]
            result, errors = evaluate_run.evaluate_generated_integration_coverage(
                rows, root, policy()
            )
            self.assertEqual([], errors)
            self.assertEqual(50.0, result["requirement_rate"])
            self.assertEqual(50.0, result["trace_item_rate"])


class HumanEffortTest(unittest.TestCase):
    def test_counts_and_time(self):
        data = {
            "started_at": "2026-01-01T09:00:00+09:00",
            "completed_at": "2026-01-01T10:00:00+09:00",
            "human_active_seconds": 1800,
            "events": [
                {"type": "PROMPT", "characters": 100},
                {"type": "REVIEW", "characters": 0},
                {"type": "CORRECTION", "characters": 20},
                {"type": "OTHER_INPUT", "characters": 10},
            ],
        }
        result, errors = evaluate_run.evaluate_human_effort(data, policy())
        self.assertEqual([], errors)
        self.assertEqual(3, result["input_count"])
        self.assertEqual(130, result["input_characters"])
        self.assertEqual(1, result["review_count"])
        self.assertEqual(1, result["correction_count"])
        self.assertEqual(30.0, result["active_work_minutes"])
        self.assertEqual(60.0, result["elapsed_minutes"])

    def test_missing_active_time_fails(self):
        data = {
            "started_at": "2026-01-01T09:00:00+09:00",
            "completed_at": "2026-01-01T10:00:00+09:00",
            "events": [],
        }
        _, errors = evaluate_run.evaluate_human_effort(data, policy())
        self.assertTrue(any("human_active_seconds" in e for e in errors))


class ReworkTest(unittest.TestCase):
    def test_counts_downstream_route_only(self):
        data = {"events": [
            {
                "event_type": "PHASE_ROUTE",
                "from_phase": "UNIT_TEST",
                "to_phase": "IMPLEMENTATION",
                "classification": "IMPLEMENTATION_ERROR",
                "minor_refactoring": False,
            },
            {
                "event_type": "PHASE_ROUTE",
                "from_phase": "UNIT_TEST",
                "to_phase": "IMPLEMENTATION",
                "classification": "REFACTOR",
                "minor_refactoring": False,
            },
            {
                "event_type": "PHASE_ROUTE",
                "from_phase": "UNIT_TEST",
                "to_phase": "IMPLEMENTATION",
                "classification": "IMPLEMENTATION_ERROR",
                "minor_refactoring": True,
            },
        ]}
        result, errors = evaluate_run.evaluate_rework(data, policy())
        self.assertEqual([], errors)
        self.assertEqual(1, result["count"])


class AIUsageTest(unittest.TestCase):
    def test_sums_usage_and_excludes_evaluation(self):
        data = {"records": [
            {
                "input_tokens": 100,
                "output_tokens": 50,
                "design_context_tokens": 20,
                "evaluation_agent": False,
            },
            {
                "input_tokens": 1000,
                "output_tokens": 500,
                "design_context_tokens": 100,
                "evaluation_agent": True,
            },
        ]}
        result, errors = evaluate_run.evaluate_ai_usage(data, policy())
        self.assertEqual([], errors)
        self.assertEqual(100, result["input_tokens"])
        self.assertEqual(50, result["output_tokens"])
        self.assertEqual(150, result["total_tokens"])
        self.assertEqual(20, result["design_context_tokens"])
        self.assertEqual(1, result["record_count"])

    def test_missing_required_input_token_fails(self):
        data = {"records": [{"output_tokens": 5}]}
        _, errors = evaluate_run.evaluate_ai_usage(data, policy())
        self.assertTrue(any("input_tokens" in e for e in errors))


class ReportValidatorTest(unittest.TestCase):
    def base_report(self):
        return {
            "status": "PASS",
            "run_id": "RUN-001",
            "metrics": {
                "quality": {
                    "requirement_satisfaction": {
                        "overall": {"total": 2, "passed": 1, "rate": 50.0},
                        "functional": {"total": 1, "passed": 1, "rate": 100.0},
                        "non_functional": {"total": 1, "passed": 0, "rate": 0.0},
                    },
                    "unit_test_coverage": {"rate": 90.0},
                    "integration_generated_test_coverage": {
                        "requirement_rate": 80.0,
                        "trace_item_rate": 70.0,
                    },
                },
                "cost_efficiency": {
                    "human_effort": {
                        "input_count": 1,
                        "input_characters": 10,
                        "review_count": 1,
                        "correction_count": 0,
                        "active_work_seconds": 60,
                        "elapsed_seconds": 120,
                    },
                    "rework": {"count": 0},
                    "ai_usage": {
                        "input_tokens": 100,
                        "output_tokens": 50,
                        "total_tokens": 150,
                    },
                },
            },
            "errors": [],
            "missing_inputs": [],
        }

    def test_valid_report(self):
        self.assertEqual([], validate_evaluation.validate(self.base_report()))

    def test_invalid_rate(self):
        r = self.base_report()
        r["metrics"]["quality"]["unit_test_coverage"]["rate"] = 101
        errors = validate_evaluation.validate(r)
        self.assertTrue(any("between 0 and 100" in e for e in errors))

    def test_formula_mismatch(self):
        r = self.base_report()
        r["metrics"]["quality"]["requirement_satisfaction"]["overall"]["rate"] = 99
        errors = validate_evaluation.validate(r)
        self.assertTrue(any("expected 50.0" in e for e in errors))


class AggregateTest(unittest.TestCase):
    def report(self, condition: str, category: str, rate: float):
        return {
            "status": "PASS",
            "condition_id": condition,
            "task_category": category,
            "metrics": {
                "quality": {
                    "requirement_satisfaction": {
                        "overall": {"rate": rate}
                    }
                }
            },
        }

    def test_mean_and_sample_stddev(self):
        p = policy()
        result = aggregate_experiments.aggregate(
            [
                self.report("C1", "CRUD", 80.0),
                self.report("C1", "CRUD", 100.0),
            ],
            p,
        )
        summary = result["reproducibility"]["C1"]["metrics"][
            "metrics.quality.requirement_satisfaction.overall.rate"
        ]
        self.assertEqual(90.0, summary["mean"])
        self.assertAlmostEqual(14.1421, summary["stddev"], places=4)

    def test_generality_warning_for_one_category(self):
        result = aggregate_experiments.aggregate(
            [self.report("C1", "CRUD", 100.0)],
            policy(),
        )
        self.assertTrue(any("two task_category" in w for w in result["warnings"]))

    def test_condition_mixing_model_fails_integrity(self):
        a = self.report("C1", "CRUD", 100.0)
        b = self.report("C1", "CRUD", 90.0)
        a["model"] = "M1"
        b["model"] = "M2"
        result = aggregate_experiments.aggregate([a, b], policy())
        self.assertEqual("FAIL", result["status"])
        self.assertTrue(any("mixes different model" in e for e in result["integrity_errors"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
