#!/usr/bin/env python3

"""
Unit tests for validate_unit_test.py

Run:
    python .github/skills/unit-test/scripts/test_validate_unit_test.py

No third-party test framework is required.
PyYAML is required because validate_unit_test.py imports yaml.
"""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

import yaml


SCRIPT_DIR = Path(__file__).resolve().parent
VALIDATOR_PATH = SCRIPT_DIR / "validate_unit_test.py"

SPEC = importlib.util.spec_from_file_location(
    "validate_unit_test",
    VALIDATOR_PATH,
)

if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Unable to import validator: {VALIDATOR_PATH}")

validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


def base_policy() -> dict[str, Any]:
    return {
        "test_result": {
            "required_pass_rate": 100,
            "allowed_failures": 0,
            "allowed_errors": 0,
        },
        "skipped_tests": {
            "allowed": 0,
            "allowlist": [],
        },
        "coverage": {
            "enabled": True,
            "thresholds": {
                "statements": 80,
                "branches": 80,
                "functions": 80,
                "lines": 80,
            },
            "fail_when_below_threshold": True,
        },
        "requirement_coverage": {
            "enabled": True,
            "require_all_unit_testable_requirements": True,
        },
        "database": {
            "production_database_allowed": False,
            "shared_test_database_allowed": False,
            "service_and_domain": {
                "strategy": "mock",
            },
            "repository_and_dao": {
                "strategy": "container",
            },
            "container": {
                "disposable": True,
                "isolated_state": True,
            },
        },
        "regression": {
            "required_after_defect": True,
            "rerun_failed_test": True,
            "rerun_related_tests": True,
            "rerun_full_suite": True,
        },
        "flaky_test": {
            "allowed": False,
            "repeat_count_when_suspected": 3,
        },
        "failure_handling": {
            "unresolved_error_allowed": False,
            "allow_next_phase_with_failure": False,
        },
        "criteria": {
            "directory": ".github/skills/unit-test/criteria",
            "pattern": "*.criterion.md",
            "load_all": True,
        },
    }


def base_summary() -> dict[str, Any]:
    return {
        "total": 2,
        "passed": 2,
        "failed": 0,
        "errors": 0,
        "skipped": 0,
        "skipped_tests": [],
    }


def base_evidence() -> dict[str, Any]:
    return {
        "criteria_coverage": [
            {
                "criterion": "normal-case",
                "applicable": True,
                "result": "PASS",
                "reason": "Normal behavior verified.",
            },
            {
                "criterion": "exception",
                "applicable": True,
                "result": "PASS",
                "reason": "Exception behavior verified.",
            },
        ],
        "requirement_coverage": [
            {
                "requirement": "FR-001",
                "requirement_id": "FR-001",
                "unit_testable": True,
                "tests": [
                    {
                        "id": "tests/unit/test_user.py::test_register",
                        "result": "PASS",
                    }
                ],
            }
        ],
        "defects": [],
        "database_tests": [
            {
                "target": "UserService",
                "production_database_used": False,
                "shared_database_used": False,
                "strategy": "MOCK",
            }
        ],
        "flaky_tests": [],
    }


def write_junit(
    path: Path,
    *,
    passed: int = 1,
    failed: int = 0,
    errors: int = 0,
    skipped: int = 0,
) -> None:
    cases: list[str] = []

    for index in range(passed):
        cases.append(
            f'<testcase classname="tests.unit.TestUser" name="test_pass_{index}" />'
        )

    for index in range(failed):
        cases.append(
            f'<testcase classname="tests.unit.TestUser" name="test_fail_{index}">'
            "<failure>failed</failure>"
            "</testcase>"
        )

    for index in range(errors):
        cases.append(
            f'<testcase classname="tests.unit.TestUser" name="test_error_{index}">'
            "<error>error</error>"
            "</testcase>"
        )

    for index in range(skipped):
        cases.append(
            f'<testcase classname="tests.unit.TestUser" name="test_skip_{index}">'
            "<skipped />"
            "</testcase>"
        )

    path.write_text(
        "<testsuites><testsuite>"
        + "".join(cases)
        + "</testsuite></testsuites>",
        encoding="utf-8",
    )


def write_coverage(
    path: Path,
    *,
    statements: float = 100,
    branches: float = 100,
    functions: float = 100,
    lines: float = 100,
) -> None:
    path.write_text(
        json.dumps(
            {
                "total": {
                    "statements": {"pct": statements},
                    "branches": {"pct": branches},
                    "functions": {"pct": functions},
                    "lines": {"pct": lines},
                }
            }
        ),
        encoding="utf-8",
    )


class PolicyTest(unittest.TestCase):

    def test_valid_policy_passes(self) -> None:
        self.assertEqual([], validator.validate_policy(base_policy()))

    def test_missing_required_setting_fails(self) -> None:
        policy = base_policy()
        del policy["test_result"]["allowed_errors"]

        errors = validator.validate_policy(policy)

        self.assertTrue(
            any("test_result.allowed_errors" in error for error in errors)
        )

    def test_enabled_coverage_requires_all_thresholds(self) -> None:
        policy = base_policy()
        del policy["coverage"]["thresholds"]["branches"]

        errors = validator.validate_policy(policy)

        self.assertTrue(
            any("Coverage threshold missing: branches" in error for error in errors)
        )

    def test_disabled_coverage_does_not_require_thresholds(self) -> None:
        policy = base_policy()
        policy["coverage"]["enabled"] = False
        policy["coverage"].pop("thresholds")

        errors = validator.validate_policy(policy)

        self.assertEqual([], errors)


class JUnitTest(unittest.TestCase):

    def test_parse_junit_counts_all_result_types(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            junit = Path(temp) / "junit.xml"
            write_junit(
                junit,
                passed=2,
                failed=1,
                errors=1,
                skipped=1,
            )

            summary = validator.parse_junit([junit])

        self.assertEqual(5, summary["total"])
        self.assertEqual(2, summary["passed"])
        self.assertEqual(1, summary["failed"])
        self.assertEqual(1, summary["errors"])
        self.assertEqual(1, summary["skipped"])
        self.assertEqual(
            ["tests.unit.TestUser::test_skip_0"],
            summary["skipped_tests"],
        )

    def test_zero_executed_tests_fails(self) -> None:
        summary = {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "errors": 0,
            "skipped": 0,
            "skipped_tests": [],
        }

        errors = validator.validate_test_result(
            summary,
            base_policy(),
        )

        self.assertEqual(
            ["No Unit Tests were executed."],
            errors,
        )

    def test_failed_test_violates_pass_rate_and_failure_limit(self) -> None:
        summary = base_summary()
        summary.update(
            {
                "total": 2,
                "passed": 1,
                "failed": 1,
            }
        )

        errors = validator.validate_test_result(
            summary,
            base_policy(),
        )

        self.assertTrue(any("Test pass rate" in error for error in errors))
        self.assertTrue(any("Failed tests" in error for error in errors))

    def test_error_test_violates_error_limit(self) -> None:
        summary = base_summary()
        summary.update(
            {
                "total": 2,
                "passed": 1,
                "errors": 1,
            }
        )

        errors = validator.validate_test_result(
            summary,
            base_policy(),
        )

        self.assertTrue(any("Error tests" in error for error in errors))

    def test_failure_can_be_allowed_by_policy(self) -> None:
        policy = base_policy()
        policy["test_result"]["required_pass_rate"] = 50
        policy["test_result"]["allowed_failures"] = 1

        summary = base_summary()
        summary.update(
            {
                "total": 2,
                "passed": 1,
                "failed": 1,
            }
        )

        errors = validator.validate_test_result(
            summary,
            policy,
        )

        self.assertEqual([], errors)


class SkippedTest(unittest.TestCase):

    def test_unauthorized_skipped_test_fails(self) -> None:
        summary = base_summary()
        summary["skipped_tests"] = [
            "tests.unit.TestUser::test_skip"
        ]

        errors = validator.validate_skipped_tests(
            summary,
            base_policy(),
        )

        self.assertTrue(
            any("Unauthorized skipped tests" in error for error in errors)
        )

    def test_allowlisted_skipped_test_passes(self) -> None:
        policy = base_policy()
        policy["skipped_tests"]["allowlist"] = [
            "tests.unit.TestUser::test_skip"
        ]

        summary = base_summary()
        summary["skipped_tests"] = [
            "tests.unit.TestUser::test_skip"
        ]

        errors = validator.validate_skipped_tests(
            summary,
            policy,
        )

        self.assertEqual([], errors)


class CoverageTest(unittest.TestCase):

    def test_parse_istanbul_coverage_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "coverage-summary.json"
            write_coverage(
                path,
                statements=91,
                branches=92,
                functions=93,
                lines=94,
            )

            coverage = validator.parse_coverage_summary(path)

        self.assertEqual(
            {
                "statements": 91.0,
                "branches": 92.0,
                "functions": 93.0,
                "lines": 94.0,
            },
            coverage,
        )

    def test_parse_flat_coverage_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "coverage-summary.json"
            path.write_text(
                json.dumps(
                    {
                        "statements": 90,
                        "branches": 91,
                        "functions": 92,
                        "lines": 93,
                    }
                ),
                encoding="utf-8",
            )

            coverage = validator.parse_coverage_summary(path)

        self.assertEqual(90.0, coverage["statements"])
        self.assertEqual(93.0, coverage["lines"])

    def test_missing_coverage_metric_raises(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "coverage-summary.json"
            path.write_text(
                json.dumps(
                    {
                        "total": {
                            "statements": {"pct": 100},
                            "branches": {"pct": 100},
                            "functions": {"pct": 100},
                        }
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                ValueError,
                "Coverage metric missing: lines",
            ):
                validator.parse_coverage_summary(path)

    def test_coverage_below_threshold_fails(self) -> None:
        coverage = {
            "statements": 79.0,
            "branches": 100.0,
            "functions": 100.0,
            "lines": 100.0,
        }

        errors = validator.validate_coverage(
            coverage,
            base_policy(),
        )

        self.assertTrue(
            any("Coverage statements" in error for error in errors)
        )

    def test_disabled_coverage_passes(self) -> None:
        policy = base_policy()
        policy["coverage"]["enabled"] = False

        errors = validator.validate_coverage(
            {
                "statements": 0,
                "branches": 0,
                "functions": 0,
                "lines": 0,
            },
            policy,
        )

        self.assertEqual([], errors)


class CriteriaTest(unittest.TestCase):

    def test_discovers_criterion_names(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            (directory / "normal-case.criterion.md").write_text(
                "# normal",
                encoding="utf-8",
            )
            (directory / "exception.criterion.md").write_text(
                "# exception",
                encoding="utf-8",
            )
            (directory / "ignore.txt").write_text(
                "ignore",
                encoding="utf-8",
            )

            criteria = validator.discover_criteria(
                directory,
                "*.criterion.md",
            )

        self.assertEqual(
            {"normal-case", "exception"},
            criteria,
        )

    def test_missing_criterion_evidence_fails(self) -> None:
        evidence = base_evidence()
        evidence["criteria_coverage"] = [
            evidence["criteria_coverage"][0]
        ]

        errors = validator.validate_criteria_coverage(
            evidence,
            {"normal-case", "exception"},
            base_policy(),
        )

        self.assertTrue(
            any("Criterion not evaluated: exception" in error for error in errors)
        )

    def test_applicable_criterion_must_pass(self) -> None:
        evidence = base_evidence()
        evidence["criteria_coverage"][0]["result"] = "FAIL"

        errors = validator.validate_criteria_coverage(
            evidence,
            {"normal-case", "exception"},
            base_policy(),
        )

        self.assertTrue(
            any("Criterion failed: normal-case" in error for error in errors)
        )

    def test_not_applicable_requires_matching_result_and_reason(self) -> None:
        evidence = base_evidence()
        evidence["criteria_coverage"][0] = {
            "criterion": "normal-case",
            "applicable": False,
            "result": "PASS",
            "reason": "",
        }

        errors = validator.validate_criteria_coverage(
            evidence,
            {"normal-case", "exception"},
            base_policy(),
        )

        self.assertTrue(
            any("result=NOT_APPLICABLE" in error for error in errors)
        )
        self.assertTrue(
            any("NOT_APPLICABLE requires reason" in error for error in errors)
        )

    def test_not_applicable_with_reason_passes(self) -> None:
        evidence = base_evidence()
        evidence["criteria_coverage"][0] = {
            "criterion": "normal-case",
            "applicable": False,
            "result": "NOT_APPLICABLE",
            "reason": "No applicable logic in this scope.",
        }

        errors = validator.validate_criteria_coverage(
            evidence,
            {"normal-case", "exception"},
            base_policy(),
        )

        self.assertEqual([], errors)

    def test_criteria_check_can_be_disabled(self) -> None:
        policy = base_policy()
        policy["criteria"]["load_all"] = False

        errors = validator.validate_criteria_coverage(
            {},
            {"normal-case"},
            policy,
        )

        self.assertEqual([], errors)


class RequirementCoverageTest(unittest.TestCase):

    def test_empty_requirement_coverage_fails(self) -> None:
        evidence = base_evidence()
        evidence["requirement_coverage"] = []

        errors = validator.validate_requirement_coverage(
            evidence,
            base_policy(),
        )

        self.assertEqual(
            ["Requirement Coverage evidence is empty."],
            errors,
        )

    def test_requirement_entry_requires_id(self) -> None:
        evidence = base_evidence()
        evidence["requirement_coverage"][0].pop("requirement")

        errors = validator.validate_requirement_coverage(
            evidence,
            base_policy(),
        )

        self.assertTrue(
            any("has no Requirement ID" in error for error in errors)
        )

    def test_non_unit_testable_requirement_requires_reason(self) -> None:
        evidence = base_evidence()
        entry = evidence["requirement_coverage"][0]
        entry["unit_testable"] = False
        entry["tests"] = []

        errors = validator.validate_requirement_coverage(
            evidence,
            base_policy(),
        )

        self.assertTrue(
            any("unit_testable=false requires reason" in error for error in errors)
        )

    def test_non_unit_testable_requirement_with_reason_passes(self) -> None:
        evidence = base_evidence()
        entry = evidence["requirement_coverage"][0]
        entry["unit_testable"] = False
        entry["tests"] = []
        entry["reason"] = "Validated only by integration testing."

        errors = validator.validate_requirement_coverage(
            evidence,
            base_policy(),
        )

        self.assertEqual([], errors)

    def test_unit_testable_requirement_requires_mapping(self) -> None:
        evidence = base_evidence()
        evidence["requirement_coverage"][0]["tests"] = []

        errors = validator.validate_requirement_coverage(
            evidence,
            base_policy(),
        )

        self.assertTrue(
            any("no Unit Test mapped" in error for error in errors)
        )

    def test_unit_testable_requirement_requires_passing_mapping(self) -> None:
        evidence = base_evidence()
        evidence["requirement_coverage"][0]["tests"] = [
            {
                "id": "tests/unit/test_user.py::test_register",
                "result": "FAIL",
            }
        ]

        errors = validator.validate_requirement_coverage(
            evidence,
            base_policy(),
        )

        self.assertTrue(
            any("no mapped Unit Test passed" in error for error in errors)
        )

    def test_valid_requirement_mapping_passes(self) -> None:
        errors = validator.validate_requirement_coverage(
            base_evidence(),
            base_policy(),
        )

        self.assertEqual([], errors)


class DefectRegressionTest(unittest.TestCase):

    def test_unresolved_defect_fails(self) -> None:
        evidence = base_evidence()
        evidence["defects"] = [
            {
                "id": "DEF-001",
                "resolved": False,
                "regression_test": "test_regression",
                "rerun": {
                    "target_test": "PASS",
                    "related_tests": "PASS",
                    "full_suite": "PASS",
                },
            }
        ]

        errors = validator.validate_defects(
            evidence,
            base_policy(),
        )

        self.assertTrue(
            any("DEF-001: defect is unresolved" in error for error in errors)
        )

    def test_regression_test_is_required_after_defect(self) -> None:
        evidence = base_evidence()
        evidence["defects"] = [
            {
                "id": "DEF-001",
                "resolved": True,
                "rerun": {
                    "target_test": "PASS",
                    "related_tests": "PASS",
                    "full_suite": "PASS",
                },
            }
        ]

        errors = validator.validate_defects(
            evidence,
            base_policy(),
        )

        self.assertTrue(
            any("Regression Test is missing" in error for error in errors)
        )

    def test_required_reruns_must_pass(self) -> None:
        evidence = base_evidence()
        evidence["defects"] = [
            {
                "id": "DEF-001",
                "resolved": True,
                "regression_test": "test_regression",
                "rerun": {
                    "target_test": "PASS",
                    "related_tests": "FAIL",
                    "full_suite": "PASS",
                },
            }
        ]

        errors = validator.validate_defects(
            evidence,
            base_policy(),
        )

        self.assertTrue(
            any(
                "Regression rerun 'related_tests' is not PASS"
                in error
                for error in errors
            )
        )

    def test_resolved_defect_with_regression_and_reruns_passes(self) -> None:
        evidence = base_evidence()
        evidence["defects"] = [
            {
                "id": "DEF-001",
                "resolved": True,
                "regression_test": "test_regression",
                "rerun": {
                    "target_test": "PASS",
                    "related_tests": "PASS",
                    "full_suite": "PASS",
                },
            }
        ]

        errors = validator.validate_defects(
            evidence,
            base_policy(),
        )

        self.assertEqual([], errors)


class DatabasePolicyTest(unittest.TestCase):

    def test_production_database_use_fails(self) -> None:
        evidence = base_evidence()
        evidence["database_tests"][0]["production_database_used"] = True

        errors = validator.validate_database_tests(
            evidence,
            base_policy(),
        )

        self.assertTrue(
            any("Production Database was used" in error for error in errors)
        )

    def test_shared_database_use_fails(self) -> None:
        evidence = base_evidence()
        evidence["database_tests"][0]["shared_database_used"] = True

        errors = validator.validate_database_tests(
            evidence,
            base_policy(),
        )

        self.assertTrue(
            any("Shared Test Database was used" in error for error in errors)
        )

    def test_invalid_database_strategy_fails(self) -> None:
        evidence = base_evidence()
        evidence["database_tests"][0]["strategy"] = "PRODUCTION"

        errors = validator.validate_database_tests(
            evidence,
            base_policy(),
        )

        self.assertTrue(
            any("invalid database strategy" in error for error in errors)
        )

    def test_mock_container_and_not_applicable_are_valid(self) -> None:
        evidence = base_evidence()
        evidence["database_tests"] = [
            {
                "target": "Service",
                "production_database_used": False,
                "shared_database_used": False,
                "strategy": "MOCK",
            },
            {
                "target": "Repository",
                "production_database_used": False,
                "shared_database_used": False,
                "strategy": "CONTAINER",
            },
            {
                "target": "PureFunction",
                "production_database_used": False,
                "shared_database_used": False,
                "strategy": "NOT_APPLICABLE",
            },
        ]

        errors = validator.validate_database_tests(
            evidence,
            base_policy(),
        )

        self.assertEqual([], errors)


class FlakyTest(unittest.TestCase):

    def test_unresolved_flaky_test_fails(self) -> None:
        evidence = base_evidence()
        evidence["flaky_tests"] = [
            {
                "test": "tests/unit/test_user.py::test_flaky",
                "resolved": False,
            }
        ]

        errors = validator.validate_flaky_tests(
            evidence,
            base_policy(),
        )

        self.assertTrue(
            any("Unresolved flaky test" in error for error in errors)
        )

    def test_resolved_flaky_test_passes(self) -> None:
        evidence = base_evidence()
        evidence["flaky_tests"] = [
            {
                "test": "tests/unit/test_user.py::test_flaky",
                "resolved": True,
            }
        ]

        errors = validator.validate_flaky_tests(
            evidence,
            base_policy(),
        )

        self.assertEqual([], errors)

    def test_flaky_tests_can_be_allowed_by_policy(self) -> None:
        policy = base_policy()
        policy["flaky_test"]["allowed"] = True

        evidence = base_evidence()
        evidence["flaky_tests"] = [
            {
                "test": "tests/unit/test_user.py::test_flaky",
                "resolved": False,
            }
        ]

        errors = validator.validate_flaky_tests(
            evidence,
            policy,
        )

        self.assertEqual([], errors)


class EndToEndValidationTest(unittest.TestCase):

    def _create_valid_repository(
        self,
        root: Path,
    ) -> dict[str, Path]:
        policy_path = root / "unit-test-policy.yaml"
        criteria_dir = root / "criteria"
        junit_path = root / "junit.xml"
        coverage_path = root / "coverage-summary.json"
        evidence_path = root / "unit-test-evidence.json"

        criteria_dir.mkdir(parents=True, exist_ok=True)

        policy_path.write_text(
            yaml.safe_dump(
                base_policy(),
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )

        (criteria_dir / "normal-case.criterion.md").write_text(
            "# Normal Case",
            encoding="utf-8",
        )
        (criteria_dir / "exception.criterion.md").write_text(
            "# Exception",
            encoding="utf-8",
        )

        write_junit(
            junit_path,
            passed=2,
        )

        write_coverage(
            coverage_path,
        )

        evidence_path.write_text(
            json.dumps(
                base_evidence(),
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        return {
            "policy": policy_path,
            "criteria": criteria_dir,
            "junit": junit_path,
            "coverage": coverage_path,
            "evidence": evidence_path,
        }

    def test_valid_repository_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = self._create_valid_repository(root)

            errors, result = validator.validate(
                policy_path=paths["policy"],
                criteria_dir=paths["criteria"],
                junit_patterns=[str(paths["junit"])],
                coverage_path=paths["coverage"],
                evidence_path=paths["evidence"],
            )

        self.assertEqual([], errors)
        self.assertEqual("PASS", result["status"])
        self.assertEqual(2, result["test_summary"]["passed"])
        self.assertEqual(
            ["exception", "normal-case"],
            result["criteria"],
        )

    def test_no_junit_report_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = self._create_valid_repository(root)

            errors, result = validator.validate(
                policy_path=paths["policy"],
                criteria_dir=paths["criteria"],
                junit_patterns=[str(root / "missing-*.xml")],
                coverage_path=paths["coverage"],
                evidence_path=paths["evidence"],
            )

        self.assertTrue(
            any("No JUnit XML reports found" in error for error in errors)
        )
        self.assertEqual("FAIL", result["status"])

    def test_missing_criteria_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = self._create_valid_repository(root)

            for criterion in paths["criteria"].glob("*.criterion.md"):
                criterion.unlink()

            errors, result = validator.validate(
                policy_path=paths["policy"],
                criteria_dir=paths["criteria"],
                junit_patterns=[str(paths["junit"])],
                coverage_path=paths["coverage"],
                evidence_path=paths["evidence"],
            )

        self.assertTrue(
            any("No Unit Test Criteria found" in error for error in errors)
        )
        self.assertEqual("FAIL", result["status"])

    def test_coverage_failure_makes_full_validation_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = self._create_valid_repository(root)

            write_coverage(
                paths["coverage"],
                statements=79,
            )

            errors, result = validator.validate(
                policy_path=paths["policy"],
                criteria_dir=paths["criteria"],
                junit_patterns=[str(paths["junit"])],
                coverage_path=paths["coverage"],
                evidence_path=paths["evidence"],
            )

        self.assertTrue(
            any("Coverage statements" in error for error in errors)
        )
        self.assertEqual("FAIL", result["status"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
