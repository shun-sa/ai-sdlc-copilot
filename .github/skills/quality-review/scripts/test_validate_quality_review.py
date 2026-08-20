#!/usr/bin/env python3

"""
Unit tests for validate_quality_review.py

Run:
    python .github/skills/quality-review/scripts/test_validate_quality_review.py

No third-party test framework is required.
PyYAML is required because validate_quality_review.py imports yaml.
"""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
VALIDATOR_PATH = SCRIPT_DIR / "validate_quality_review.py"

SPEC = importlib.util.spec_from_file_location(
    "validate_quality_review",
    VALIDATOR_PATH,
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Unable to import validator: {VALIDATOR_PATH}")

validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)

CRITERIA = {
    "requirements-quality",
    "architecture-quality",
    "implementation-quality",
    "unit-test-quality",
    "integration-test-quality",
    "cross-phase-consistency",
}


def base_policy() -> dict[str, Any]:
    classifications = [
        "REQUIREMENT_QUALITY_ISSUE",
        "ARCHITECTURE_QUALITY_ISSUE",
        "IMPLEMENTATION_QUALITY_ISSUE",
        "UNIT_TEST_QUALITY_ISSUE",
        "INTEGRATION_TEST_QUALITY_ISSUE",
        "CROSS_PHASE_CONSISTENCY_ISSUE",
        "UNNECESSARY_COMPLEXITY",
        "SCOPE_EXPANSION",
        "EXPECTED_BEHAVIOR_MISMATCH",
        "INSUFFICIENT_TEST_ASSERTION",
        "MISSING_BEHAVIOR_COVERAGE",
    ]

    return {
        "audit": {
            "allowed_scopes": [
                "REQUIREMENTS",
                "ARCHITECTURE",
                "IMPLEMENTATION",
                "UNIT_TEST",
                "INTEGRATION_TEST",
                "FULL",
            ],
            "allow_unresolved_blocking_issue": False,
        },
        "criteria": {
            "directory": ".github/skills/quality-review/criteria",
            "pattern": "*.criterion.md",
            "load_all": True,
            "allowed_results": ["PASS", "NOT_APPLICABLE", "FAIL"],
            "require_all_applicable_pass": True,
            "require_reason_when_not_applicable": True,
        },
        "quality": {
            "requirements": {
                "require_internal_consistency": True,
                "require_testable_behavior": True,
                "allow_unresolved_material_ambiguity": False,
                "allow_scope_conflict": False,
            },
            "architecture": {
                "require_requirement_alignment": True,
                "require_accepted_adr_alignment": True,
                "allow_unjustified_complexity": False,
                "allow_implicit_important_decision": False,
            },
            "implementation": {
                "require_requirement_alignment": True,
                "require_accepted_adr_alignment": True,
                "allow_scope_expansion": False,
                "allow_unjustified_complexity": False,
                "require_testability": True,
            },
            "unit_test": {
                "require_requirement_based_expected_result": True,
                "allow_code_derived_expected_result": False,
                "require_meaningful_assertion": True,
                "allow_material_behavior_gap": False,
            },
            "integration_test": {
                "require_requirement_based_expected_result": True,
                "allow_code_derived_expected_result": False,
                "allow_material_behavior_gap": False,
            },
        },
        "cross_phase": {
            "require_semantic_consistency": True,
            "allow_behavior_contradiction": False,
        },
        "scope": {"allow_scope_expansion": False},
        "complexity": {
            "allow_unjustified_complexity": False,
            "prefer_simplest_sufficient_solution": True,
        },
        "severity": {
            "allowed": ["CRITICAL", "HIGH", "MEDIUM", "LOW"],
            "blocking": ["CRITICAL", "HIGH", "MEDIUM"],
            "advisory": ["LOW"],
        },
        "issues": {
            "allow_unresolved_blocking_issue": False,
            "classifications": classifications,
        },
        "routing": {
            "REQUIREMENT_QUALITY_ISSUE": "REQUIREMENTS",
            "ARCHITECTURE_QUALITY_ISSUE": "ARCHITECTURE",
            "IMPLEMENTATION_QUALITY_ISSUE": "IMPLEMENTATION",
            "UNIT_TEST_QUALITY_ISSUE": "UNIT_TEST",
            "INTEGRATION_TEST_QUALITY_ISSUE": "INTEGRATION_TEST",
            "CROSS_PHASE_CONSISTENCY_ISSUE": "ROOT_CAUSE",
            "UNNECESSARY_COMPLEXITY": "ROOT_CAUSE",
            "SCOPE_EXPANSION": "ROOT_CAUSE",
            "EXPECTED_BEHAVIOR_MISMATCH": "ROOT_CAUSE",
            "INSUFFICIENT_TEST_ASSERTION": "UNIT_TEST",
            "MISSING_BEHAVIOR_COVERAGE": "ROOT_CAUSE",
        },
        "reports": {
            "directory": "reports/quality-review",
            "required": [
                "quality-review-report.json",
                "quality-review-report.md",
            ],
        },
    }


def criterion_result(
    name: str,
    *,
    applicable: bool = True,
    result: str = "PASS",
    reason: str | None = None,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "criterion": name,
        "applicable": applicable,
        "result": result,
    }
    if reason is not None:
        item["reason"] = reason
    return item


def criteria_for_scope(scope: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    minimum = {
        "requirements-quality": "REQUIREMENTS",
        "architecture-quality": "ARCHITECTURE",
        "implementation-quality": "IMPLEMENTATION",
        "unit-test-quality": "UNIT_TEST",
        "integration-test-quality": "INTEGRATION_TEST",
        "cross-phase-consistency": "ARCHITECTURE",
    }

    for name in sorted(CRITERIA):
        applicable = validator.scope_includes(scope, minimum[name])
        if applicable:
            rows.append(criterion_result(name))
        else:
            rows.append(
                criterion_result(
                    name,
                    applicable=False,
                    result="NOT_APPLICABLE",
                    reason=f"Outside {scope} audit scope.",
                )
            )
    return rows


def base_report(scope: str = "FULL") -> dict[str, Any]:
    rows = criteria_for_scope(scope)
    pass_count = sum(1 for item in rows if item["result"] == "PASS")
    na_count = sum(1 for item in rows if item["result"] == "NOT_APPLICABLE")

    return {
        "status": "PASS",
        "audit_scope": scope,
        "criteria_results": rows,
        "issues": [],
        "summary": {
            "criteria_total": len(CRITERIA),
            "criteria_pass": pass_count,
            "criteria_not_applicable": na_count,
            "criteria_fail": 0,
            "issues_total": 0,
            "blocking_issues": 0,
        },
        "reports": {
            "json": "reports/quality-review/quality-review-report.json",
            "markdown": "reports/quality-review/quality-review-report.md",
        },
    }


class PolicyTest(unittest.TestCase):
    def test_valid_policy_has_no_errors(self) -> None:
        self.assertEqual([], validator.validate_policy(base_policy()))

    def test_missing_routing_fails(self) -> None:
        policy = base_policy()
        del policy["routing"]["SCOPE_EXPANSION"]
        errors = validator.validate_policy(policy)
        self.assertTrue(any("routing missing" in e and "SCOPE_EXPANSION" in e for e in errors))

    def test_blocking_severity_must_be_allowed(self) -> None:
        policy = base_policy()
        policy["severity"]["blocking"].append("UNKNOWN")
        errors = validator.validate_policy(policy)
        self.assertTrue(any("severity.blocking" in e for e in errors))


class CriteriaDiscoveryTest(unittest.TestCase):
    def test_discovers_criteria(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in CRITERIA:
                (root / f"{name}.criterion.md").write_text(f"# {name}\n", encoding="utf-8")
            discovered = validator.discover_criteria(root, "*.criterion.md")
        self.assertEqual(CRITERIA, discovered)


class CriteriaResultTest(unittest.TestCase):
    def test_full_scope_all_passes(self) -> None:
        errors, counts = validator.validate_criteria_results(
            base_report("FULL"), CRITERIA, base_policy(), "FULL"
        )
        self.assertEqual([], errors)
        self.assertEqual(len(CRITERIA), counts["pass"])

    def test_missing_criterion_fails(self) -> None:
        report = base_report("FULL")
        report["criteria_results"] = report["criteria_results"][:-1]
        errors, _ = validator.validate_criteria_results(
            report, CRITERIA, base_policy(), "FULL"
        )
        self.assertTrue(any("Criterion not evaluated" in e for e in errors))

    def test_not_applicable_requires_reason(self) -> None:
        report = base_report("REQUIREMENTS")
        target = next(i for i in report["criteria_results"] if i["criterion"] == "architecture-quality")
        target.pop("reason")
        errors, _ = validator.validate_criteria_results(
            report, CRITERIA, base_policy(), "REQUIREMENTS"
        )
        self.assertTrue(any("NOT_APPLICABLE requires reason" in e for e in errors))

    def test_applicable_criterion_must_pass(self) -> None:
        report = base_report("FULL")
        target = next(i for i in report["criteria_results"] if i["criterion"] == "implementation-quality")
        target["result"] = "FAIL"
        errors, counts = validator.validate_criteria_results(
            report, CRITERIA, base_policy(), "FULL"
        )
        self.assertTrue(any("Applicable criterion is not PASS" in e for e in errors))
        self.assertEqual(1, counts["fail"])

    def test_scope_outside_criterion_cannot_be_applicable(self) -> None:
        report = base_report("REQUIREMENTS")
        target = next(i for i in report["criteria_results"] if i["criterion"] == "integration-test-quality")
        target["applicable"] = True
        target["result"] = "PASS"
        target.pop("reason", None)
        errors, _ = validator.validate_criteria_results(
            report, CRITERIA, base_policy(), "REQUIREMENTS"
        )
        self.assertTrue(any("outside audit_scope=REQUIREMENTS" in e for e in errors))

    def test_unknown_criterion_fails(self) -> None:
        report = base_report("FULL")
        report["criteria_results"].append(criterion_result("unknown-quality"))
        errors, _ = validator.validate_criteria_results(
            report, CRITERIA, base_policy(), "FULL"
        )
        self.assertTrue(any("unknown criterion" in e for e in errors))


class IssueTest(unittest.TestCase):
    def test_valid_nonblocking_issue_passes(self) -> None:
        report = base_report("FULL")
        report["issues"] = [{
            "issue_id": "QUALITY-001",
            "classification": "IMPLEMENTATION_QUALITY_ISSUE",
            "severity": "LOW",
            "description": "Minor maintainability concern.",
            "evidence": "src/service.py",
            "recommended_route": "IMPLEMENTATION",
            "resolved": False,
        }]
        errors, counts = validator.validate_issues(report, base_policy())
        self.assertEqual([], errors)
        self.assertEqual(0, counts["blocking"])
        self.assertEqual(1, counts["unresolved"])

    def test_blocking_issue_fails(self) -> None:
        report = base_report("FULL")
        report["issues"] = [{
            "issue_id": "QUALITY-001",
            "classification": "IMPLEMENTATION_QUALITY_ISSUE",
            "severity": "HIGH",
            "description": "Required behavior is missing.",
            "evidence": "FR-001 / src/service.py",
            "recommended_route": "IMPLEMENTATION",
            "resolved": False,
        }]
        errors, counts = validator.validate_issues(report, base_policy())
        self.assertEqual(1, counts["blocking"])
        self.assertTrue(any("Unresolved blocking" in e for e in errors))

    def test_wrong_fixed_routing_fails(self) -> None:
        report = base_report("FULL")
        report["issues"] = [{
            "issue_id": "QUALITY-001",
            "classification": "UNIT_TEST_QUALITY_ISSUE",
            "severity": "LOW",
            "description": "Weak assertion.",
            "evidence": "test_service.py",
            "recommended_route": "IMPLEMENTATION",
            "resolved": False,
        }]
        errors, _ = validator.validate_issues(report, base_policy())
        self.assertTrue(any("recommended_route" in e and "UNIT_TEST" in e for e in errors))

    def test_root_cause_requires_concrete_route(self) -> None:
        report = base_report("FULL")
        report["issues"] = [{
            "issue_id": "QUALITY-001",
            "classification": "CROSS_PHASE_CONSISTENCY_ISSUE",
            "severity": "LOW",
            "description": "Behavior differs between phases.",
            "evidence": "FR-001 / ADR-001 / src/service.py",
            "recommended_route": "ROOT_CAUSE",
            "resolved": False,
        }]
        errors, _ = validator.validate_issues(report, base_policy())
        self.assertTrue(any("concrete root-cause phase" in e for e in errors))

    def test_invalid_classification_fails(self) -> None:
        report = base_report("FULL")
        report["issues"] = [{
            "issue_id": "QUALITY-001",
            "classification": "UNKNOWN_QUALITY",
            "severity": "LOW",
            "description": "Unknown issue.",
            "evidence": "artifact",
            "recommended_route": "IMPLEMENTATION",
            "resolved": False,
        }]
        errors, _ = validator.validate_issues(report, base_policy())
        self.assertTrue(any("invalid classification" in e for e in errors))

    def test_invalid_severity_fails(self) -> None:
        report = base_report("FULL")
        report["issues"] = [{
            "issue_id": "QUALITY-001",
            "classification": "IMPLEMENTATION_QUALITY_ISSUE",
            "severity": "UNKNOWN",
            "description": "Issue.",
            "evidence": "artifact",
            "recommended_route": "IMPLEMENTATION",
            "resolved": False,
        }]
        errors, _ = validator.validate_issues(report, base_policy())
        self.assertTrue(any("invalid severity" in e for e in errors))

    def test_issue_requires_evidence(self) -> None:
        report = base_report("FULL")
        report["issues"] = [{
            "issue_id": "QUALITY-001",
            "classification": "IMPLEMENTATION_QUALITY_ISSUE",
            "severity": "LOW",
            "description": "Issue.",
            "recommended_route": "IMPLEMENTATION",
            "resolved": False,
        }]
        errors, _ = validator.validate_issues(report, base_policy())
        self.assertTrue(any("evidence is required" in e for e in errors))


class ReportHeaderTest(unittest.TestCase):
    def test_valid_header_passes(self) -> None:
        errors, scope = validator.validate_report_header(base_report("FULL"), base_policy())
        self.assertEqual([], errors)
        self.assertEqual("FULL", scope)

    def test_invalid_scope_fails(self) -> None:
        report = base_report("FULL")
        report["audit_scope"] = "UNKNOWN"
        errors, _ = validator.validate_report_header(report, base_policy())
        self.assertTrue(any("audit_scope" in e for e in errors))

    def test_invalid_status_fails(self) -> None:
        report = base_report("FULL")
        report["status"] = "SUCCESS"
        errors, _ = validator.validate_report_header(report, base_policy())
        self.assertTrue(any("report status" in e for e in errors))


class RequiredReportTest(unittest.TestCase):
    def test_missing_required_report_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            reports = Path(temp)
            (reports / "quality-review-report.json").write_text("{}", encoding="utf-8")
            errors = validator.validate_required_reports(reports, base_policy())
        self.assertTrue(any("quality-review-report.md" in e for e in errors))


class UpstreamValidatorTest(unittest.TestCase):
    def test_requirements_scope_does_not_require_test_validators(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            errors = validator.validate_upstream_validators(
                "REQUIREMENTS",
                root / "unit.json",
                root / "integration.json",
            )
        self.assertEqual([], errors)

    def test_unit_scope_requires_unit_validator_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            unit = root / "unit.json"
            unit.write_text(json.dumps({"status": "FAIL"}), encoding="utf-8")
            errors = validator.validate_upstream_validators(
                "UNIT_TEST",
                unit,
                root / "integration.json",
            )
        self.assertTrue(any("Unit Test validation-result status is not PASS" in e for e in errors))

    def test_integration_scope_requires_both_test_validators_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            unit = root / "unit.json"
            integration = root / "integration.json"
            unit.write_text(json.dumps({"status": "PASS"}), encoding="utf-8")
            integration.write_text(json.dumps({"status": "PASS"}), encoding="utf-8")
            errors = validator.validate_upstream_validators(
                "INTEGRATION_TEST",
                unit,
                integration,
            )
        self.assertEqual([], errors)

    def test_missing_integration_validation_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            unit = root / "unit.json"
            unit.write_text(json.dumps({"status": "PASS"}), encoding="utf-8")
            errors = validator.validate_upstream_validators(
                "INTEGRATION_TEST",
                unit,
                root / "missing.json",
            )
        self.assertTrue(any("Integration Test validation result missing" in e for e in errors))


class SummaryTest(unittest.TestCase):
    def test_correct_summary_passes(self) -> None:
        report = base_report("FULL")
        errors = validator.validate_summary(
            report,
            {"total": 6, "pass": 6, "not_applicable": 0, "fail": 0},
            {"total": 0, "blocking": 0, "unresolved": 0},
        )
        self.assertEqual([], errors)

    def test_summary_mismatch_fails(self) -> None:
        report = base_report("FULL")
        report["summary"]["criteria_pass"] = 999
        errors = validator.validate_summary(
            report,
            {"total": 6, "pass": 6, "not_applicable": 0, "fail": 0},
            {"total": 0, "blocking": 0, "unresolved": 0},
        )
        self.assertTrue(any("summary.criteria_pass" in e for e in errors))


class ReportStatusTest(unittest.TestCase):
    def test_pass_with_no_errors_is_valid(self) -> None:
        errors = validator.validate_report_status(
            base_report("FULL"),
            {"total": 6, "pass": 6, "not_applicable": 0, "fail": 0},
            {"total": 0, "blocking": 0, "unresolved": 0},
            [],
        )
        self.assertEqual([], errors)

    def test_pass_with_failed_criterion_fails(self) -> None:
        errors = validator.validate_report_status(
            base_report("FULL"),
            {"total": 6, "pass": 5, "not_applicable": 0, "fail": 1},
            {"total": 0, "blocking": 0, "unresolved": 0},
            [],
        )
        self.assertTrue(any("criteria FAIL exists" in e for e in errors))

    def test_pass_with_blocking_issue_fails(self) -> None:
        errors = validator.validate_report_status(
            base_report("FULL"),
            {"total": 6, "pass": 6, "not_applicable": 0, "fail": 0},
            {"total": 1, "blocking": 1, "unresolved": 1},
            [],
        )
        self.assertTrue(any("blocking Issue exists" in e for e in errors))

    def test_pass_with_deterministic_error_fails(self) -> None:
        errors = validator.validate_report_status(
            base_report("FULL"),
            {"total": 6, "pass": 6, "not_applicable": 0, "fail": 0},
            {"total": 0, "blocking": 0, "unresolved": 0},
            ["some validator error"],
        )
        self.assertTrue(any("deterministic validation found errors" in e for e in errors))


if __name__ == "__main__":
    unittest.main(verbosity=2)
