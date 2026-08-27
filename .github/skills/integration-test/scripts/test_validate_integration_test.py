#!/usr/bin/env python3

"""
Unit tests for validate_integration_test.py

Run:
    python .github/skills/integration-test/scripts/test_validate_integration_test.py

No third-party test framework is required.
"""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
VALIDATOR_PATH = SCRIPT_DIR / "validate_integration_test.py"

SPEC = importlib.util.spec_from_file_location(
    "validate_integration_test",
    VALIDATOR_PATH,
)

if SPEC is None or SPEC.loader is None:
    raise RuntimeError(
        f"Unable to import validator: {VALIDATOR_PATH}"
    )

validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


def base_policy() -> dict[str, Any]:
    return {
        "test_result": {
            "required_pass_rate": 100,
            "allowed_failures": 0,
            "allowed_errors": 0,
        },
        "case_origin": {
            "allowed": [
                "AI_GENERATED",
                "EXTERNAL",
            ],
            "ai_generation_stage": {
                "allowed": [
                    "INITIAL",
                    "GAP_FILL",
                ]
            },
        },
        "ai_generated_cases": {
            "initial_generation_required": True,
        },
        "external_cases": {
            "optional": True,
            "missing_input": {
                "require_user_decision": True,
                "allow_continue_without_external_cases_after_confirmation": True,
                "allow_implicit_no_external_cases": False,
            },
            "immutable": True,
        },
        "coverage": {
            "enabled": True,
            "gap_analysis": {
                "require_all_missing_items_reported": True,
            },
            "gap_fill": {
                "required_when_missing": True,
            },
            "final": {
                "required_coverage_rate": 100,
                "allow_missing": False,
            },
        },
        "criteria": {
            "directory": "criteria",
            "pattern": "*.criterion.md",
            "load_all": True,
            "allowed_results": [
                "PASS",
                "NOT_APPLICABLE",
                "FAIL",
            ],
            "require_reason_when_not_applicable": True,
        },
        "automation": {
            "execute_all_automatable_cases": True,
            "allowed_automation_blocked": 0,
        },
        "test_spec_conflict": {
            "allowed_unresolved": 0,
        },
        "error_classification": {
            "allowed": [
                "TEST_ERROR",
                "IMPLEMENTATION_ERROR",
                "ADR_REQUIRED",
                "REQUIREMENT_ERROR",
                "ENVIRONMENT_ERROR",
                "TEST_SPEC_CONFLICT",
                "AUTOMATION_BLOCKED",
            ],
            "require_classification_for_all_failures": True,
        },
        "defects": {
            "unresolved_allowed": False,
            "require_root_cause": True,
            "require_error_location_when_identifiable": True,
            "detection_source_classification": {
                "allowed": [
                    "COMMON_DEFECT",
                    "AI_ONLY_DEFECT",
                    "EXTERNAL_ONLY_DEFECT",
                ]
            },
        },
        "regression": {
            "required_after_defect": True,
            "rerun_failed_case": True,
            "rerun_related_cases": True,
            "rerun_full_suite": True,
        },
        "flaky_test": {
            "allowed": False,
        },
        "failure_handling": {
            "allow_next_phase_with_failure": False,
        },
        "environment": {
            "production_environment_allowed": False,
        },
        "database": {
            "production_database_allowed": False,
            "shared_database_allowed": False,
            "production_credentials_allowed": False,
            "production_data_allowed": False,
            "schema_reproducible": True,
        },
        "traceability": {
            "enabled": True,
            "require_requirement_id": True,
            "require_case_id": True,
            "require_case_origin": True,
            "require_integration_point": True,
            "require_result": True,
        },
        "reports": {
            "directory": "reports/integration-test",
            "required": [
                "integration-test-plan.json",
                "case-comparison.json",
            ],
            "require_error_count": True,
            "require_error_location": True,
        },
    }


def ai_case(
    case_id: str,
    coverage_key: str,
    stage: str = "INITIAL",
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "origin": "AI_GENERATED",
        "generation_stage": stage,
        "title": case_id,
        "requirement_id": "FR-001",
        "test_category": "API",
        "criterion": "api",
        "steps": "execute",
        "expected_result": "success",
        "execution_type": "AUTOMATABLE",
        "coverage_key": coverage_key,
    }


def external_case(
    case_id: str,
    coverage_key: str,
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "origin": "EXTERNAL",
        "source_case_id": case_id,
        "source_file": "external.xlsx",
        "title": case_id,
        "requirement_id": "FR-001",
        "test_category": "API",
        "criterion": "api",
        "steps": "execute",
        "expected_result": "success",
        "execution_type": "AUTOMATABLE",
        "coverage_key": coverage_key,
    }


class PolicyTest(unittest.TestCase):

    def test_valid_policy_has_no_errors(self) -> None:
        errors = validator.validate_policy(
            base_policy()
        )
        self.assertEqual([], errors)

    def test_missing_required_policy_setting_fails(self) -> None:
        policy = base_policy()
        del policy["coverage"]["final"]["required_coverage_rate"]

        errors = validator.validate_policy(
            policy
        )

        self.assertTrue(
            any(
                "required_coverage_rate" in error
                for error in errors
            )
        )


class PlanTest(unittest.TestCase):

    def test_ai_initial_case_is_required(self) -> None:
        plan = {
            "cases": [
                ai_case(
                    "AI-IT-001",
                    "COV-001",
                    stage="GAP_FILL",
                )
            ]
        }

        errors, _ = validator.validate_plan(
            plan,
            {"api"},
            base_policy(),
        )

        self.assertTrue(
            any(
                "No AI_GENERATED / INITIAL" in error
                for error in errors
            )
        )

    def test_external_case_must_not_have_generation_stage(self) -> None:
        case = external_case(
            "EXT-IT-001",
            "COV-001",
        )
        case["generation_stage"] = "INITIAL"

        plan = {
            "cases": [
                ai_case(
                    "AI-IT-001",
                    "COV-001",
                ),
                case,
            ]
        }

        errors, _ = validator.validate_plan(
            plan,
            {"api"},
            base_policy(),
        )

        self.assertTrue(
            any(
                "EXTERNAL case must not have generation_stage" in error
                for error in errors
            )
        )


class CoverageTest(unittest.TestCase):

    def test_coverage_classification(self) -> None:
        cases = {
            "AI-1": ai_case(
                "AI-1",
                "COV-1",
            ),
            "AI-2": ai_case(
                "AI-2",
                "COV-2",
            ),
            "EXT-1": external_case(
                "EXT-1",
                "COV-1",
            ),
            "EXT-3": external_case(
                "EXT-3",
                "COV-3",
            ),
        }

        metrics, errors = validator.derive_coverage(
            cases,
            {
                "COV-1",
                "COV-2",
                "COV-3",
                "COV-4",
            },
        )

        self.assertEqual([], errors)
        self.assertEqual(1, metrics["common"])
        self.assertEqual(1, metrics["ai_only"])
        self.assertEqual(1, metrics["external_only"])
        self.assertEqual(1, metrics["missing"])
        self.assertEqual(75.0, metrics["combined_initial_coverage_rate"])
        self.assertEqual(75.0, metrics["final_coverage_rate"])

    def test_gap_fill_reaches_final_coverage(self) -> None:
        cases = {
            "AI-1": ai_case(
                "AI-1",
                "COV-1",
            ),
            "AI-GAP": ai_case(
                "AI-GAP",
                "COV-2",
                stage="GAP_FILL",
            ),
        }

        metrics, errors = validator.derive_coverage(
            cases,
            {
                "COV-1",
                "COV-2",
            },
        )

        self.assertEqual([], errors)
        self.assertEqual(1, metrics["missing"])
        self.assertEqual(0, metrics["final_missing"])
        self.assertEqual(100.0, metrics["final_coverage_rate"])

    def test_final_coverage_below_policy_fails(self) -> None:
        cases = {
            "AI-1": ai_case(
                "AI-1",
                "COV-1",
            ),
        }

        derived, _ = validator.derive_coverage(
            cases,
            {
                "COV-1",
                "COV-2",
            },
        )

        report = {
            "initial_metrics": {
                "required": 2,
                "common": 0,
                "ai_only": 1,
                "external_only": 0,
                "missing": 1,
                "ai_initial_coverage_rate": 50,
                "external_coverage_rate": None,
                "combined_initial_coverage_rate": 50,
            },
            "final_metrics": {
                "covered": 1,
                "missing": 1,
                "final_coverage_rate": 50,
            },
            "gaps": [
                {
                    "coverage_key": "COV-2",
                }
            ],
        }

        errors = validator.validate_coverage_report(
            report,
            derived,
            cases,
            base_policy(),
        )

        self.assertTrue(
            any(
                "Final integration coverage" in error
                for error in errors
            )
        )


class CaseResultTest(unittest.TestCase):

    def test_automation_blocked_is_not_allowed(self) -> None:
        cases = {
            "AI-1": ai_case(
                "AI-1",
                "COV-1",
            )
        }

        cases["AI-1"]["execution_type"] = "NOT_AUTOMATABLE"

        evidence = {
            "case_results": [
                {
                    "case_id": "AI-1",
                    "origin": "AI_GENERATED",
                    "generation_stage": "INITIAL",
                    "result": "BLOCKED",
                    "classification": "AUTOMATION_BLOCKED",
                }
            ]
        }

        errors = validator.validate_case_results(
            evidence,
            cases,
            base_policy(),
        )

        self.assertTrue(
            any(
                "AUTOMATION_BLOCKED count" in error
                for error in errors
            )
        )

    def test_test_spec_conflict_is_not_allowed(self) -> None:
        cases = {
            "EXT-1": external_case(
                "EXT-1",
                "COV-1",
            )
        }

        evidence = {
            "case_results": [
                {
                    "case_id": "EXT-1",
                    "origin": "EXTERNAL",
                    "result": "FAIL",
                    "classification": "TEST_SPEC_CONFLICT",
                }
            ]
        }

        errors = validator.validate_case_results(
            evidence,
            cases,
            base_policy(),
        )

        self.assertTrue(
            any(
                "TEST_SPEC_CONFLICT count" in error
                for error in errors
            )
        )


class DefectTest(unittest.TestCase):

    def test_common_defect_is_derived_from_detection_cases(self) -> None:
        cases = {
            "AI-1": ai_case(
                "AI-1",
                "COV-1",
            ),
            "EXT-1": external_case(
                "EXT-1",
                "COV-1",
            ),
        }

        defect = {
            "detected_by_cases": [
                "AI-1",
                "EXT-1",
            ]
        }

        result = validator.defect_detection_source(
            defect,
            cases,
        )

        self.assertEqual(
            "COMMON_DEFECT",
            result,
        )

    def test_defect_requires_full_suite_rerun(self) -> None:
        cases = {
            "AI-1": ai_case(
                "AI-1",
                "COV-1",
            )
        }

        evidence = {
            "defects": [
                {
                    "defect_id": "DEF-001",
                    "classification": "IMPLEMENTATION_ERROR",
                    "detected_by_cases": [
                        "AI-1",
                    ],
                    "detection_source": "AI_ONLY_DEFECT",
                    "root_cause": "bug",
                    "error_location_identifiable": True,
                    "error_location": {
                        "file": "service.py",
                    },
                    "resolved": True,
                    "rerun": {
                        "target_cases": "PASS",
                        "related_cases": "PASS",
                        "full_suite": "FAIL",
                    },
                }
            ]
        }

        errors = validator.validate_defects(
            evidence,
            cases,
            base_policy(),
        )

        self.assertTrue(
            any(
                "rerun.full_suite" in error
                for error in errors
            )
        )

class ExternalInputTest(unittest.TestCase):

    def test_external_cases_provided_passes(self) -> None:
        cases = {
            "EXT-1": external_case(
                "EXT-1",
                "COV-1",
            )
        }

        evidence = {
            "external_input": {
                "provided": True,
                "user_confirmed_without_external_cases": False,
            }
        }

        errors = validator.validate_external_input(
            evidence,
            cases,
            base_policy(),
        )

        self.assertEqual(
            [],
            errors,
        )

    def test_confirmed_without_external_cases_passes(self) -> None:
        evidence = {
            "external_input": {
                "provided": False,
                "user_confirmed_without_external_cases": True,
            }
        }

        errors = validator.validate_external_input(
            evidence,
            {},
            base_policy(),
        )

        self.assertEqual(
            [],
            errors,
        )

    def test_missing_external_without_confirmation_fails(self) -> None:
        evidence = {
            "external_input": {
                "provided": False,
                "user_confirmed_without_external_cases": False,
            }
        }

        errors = validator.validate_external_input(
            evidence,
            {},
            base_policy(),
        )

        self.assertTrue(
            any(
                "did not explicitly confirm" in error
                for error in errors
            )
        )

    def test_external_input_must_match_plan(self) -> None:
        evidence = {
            "external_input": {
                "provided": True,
                "user_confirmed_without_external_cases": False,
            }
        }

        errors = validator.validate_external_input(
            evidence,
            {},
            base_policy(),
        )

        self.assertTrue(
            any(
                "does not match" in error
                for error in errors
            )
        )

class ExternalIntegrityTest(unittest.TestCase):

    def test_external_semantic_hash_mismatch_fails(self) -> None:
        cases = {
            "EXT-1": external_case(
                "EXT-1",
                "COV-1",
            )
        }

        evidence = {
            "external_case_integrity": [
                {
                    "case_id": "EXT-1",
                    "source_case_id": "EXT-1",
                    "source_file": "external.xlsx",
                    "source_semantic_hash": "sha256:a",
                    "normalized_semantic_hash": "sha256:b",
                    "integrity_status": "FAIL",
                }
            ]
        }

        errors = validator.validate_external_integrity(
            evidence,
            cases,
            base_policy(),
        )

        self.assertTrue(
            any(
                "integrity" in error.lower()
                or "semantic hash" in error.lower()
                for error in errors
            )
        )


class RequiredReportTest(unittest.TestCase):

    def test_missing_required_report_fails(self) -> None:
        policy = base_policy()

        with tempfile.TemporaryDirectory() as temp:
            reports = Path(temp)

            (
                reports
                / "integration-test-plan.json"
            ).write_text(
                "{}",
                encoding="utf-8",
            )

            errors = validator.validate_required_reports(
                reports,
                policy,
            )

        self.assertTrue(
            any(
                "case-comparison.json" in error
                for error in errors
            )
        )


if __name__ == "__main__":
    unittest.main()
