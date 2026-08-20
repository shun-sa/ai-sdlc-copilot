#!/usr/bin/env python3

"""
Unit tests for validate_security_review.py

Run:
    python .github/skills/security-review/scripts/test_validate_security_review.py

No third-party test framework is required.
PyYAML is required because validate_security_review.py imports yaml.
"""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
VALIDATOR_PATH = SCRIPT_DIR / "validate_security_review.py"

SPEC = importlib.util.spec_from_file_location(
    "validate_security_review",
    VALIDATOR_PATH,
)

if SPEC is None or SPEC.loader is None:
    raise RuntimeError(
        f"Unable to import validator: {VALIDATOR_PATH}"
    )

validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


CRITERIA = {
    "authentication-authorization",
    "secrets-credentials",
    "input-validation-injection",
    "data-protection",
    "error-logging",
    "dependency-configuration",
    "security-test-coverage",
    "cross-phase-security-consistency",
}


def base_policy() -> dict[str, Any]:
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
            "directory": ".github/skills/security-review/criteria",
            "pattern": "*.criterion.md",
            "load_all": True,
            "allowed_results": [
                "PASS",
                "NOT_APPLICABLE",
                "FAIL",
            ],
            "require_all_applicable_pass": True,
            "require_reason_when_not_applicable": True,
        },
        "security": {
            "authentication": {
                "require_when_applicable": True,
                "allow_authentication_bypass": False,
            },
            "authorization": {
                "require_when_applicable": True,
                "require_deny_behavior": True,
                "allow_client_only_authorization": False,
            },
            "secrets": {
                "allow_hardcoded_secret": False,
                "allow_repository_credential": False,
                "allow_production_credential_in_test": False,
                "allow_secret_in_log": False,
                "allow_secret_in_error_response": False,
            },
            "input_validation": {
                "require_at_trust_boundary": True,
                "allow_client_only_security_validation": False,
            },
            "injection": {
                "allow_material_injection_risk": False,
            },
            "data_protection": {
                "allow_unnecessary_sensitive_data_exposure": False,
                "allow_sensitive_data_in_log": False,
                "allow_production_sensitive_data_in_test": False,
            },
            "error_logging": {
                "allow_internal_detail_external_exposure": False,
                "allow_secret_logging": False,
            },
            "dependency_configuration": {
                "allow_production_security_bypass": False,
                "allow_debug_security_bypass": False,
            },
            "test": {
                "require_applicable_security_behavior_test": True,
                "allow_material_security_test_gap": False,
                "require_requirement_based_expected_result": True,
                "allow_code_derived_expected_result": False,
            },
        },
        "cross_phase": {
            "require_security_consistency": True,
            "allow_security_behavior_contradiction": False,
        },
        "severity": {
            "allowed": [
                "CRITICAL",
                "HIGH",
                "MEDIUM",
                "LOW",
            ],
            "blocking": [
                "CRITICAL",
                "HIGH",
                "MEDIUM",
            ],
            "advisory": [
                "LOW",
            ],
        },
        "issues": {
            "allow_unresolved_blocking_issue": False,
            "classifications": [
                "SECURITY_REQUIREMENT_ISSUE",
                "AUTHENTICATION_ISSUE",
                "AUTHORIZATION_ISSUE",
                "SECRET_MANAGEMENT_ISSUE",
                "INPUT_VALIDATION_ISSUE",
                "INJECTION_RISK",
                "DATA_PROTECTION_ISSUE",
                "SENSITIVE_DATA_EXPOSURE",
                "ERROR_LOGGING_SECURITY_ISSUE",
                "DEPENDENCY_CONFIGURATION_ISSUE",
                "SECURITY_TEST_GAP",
                "CROSS_PHASE_SECURITY_CONSISTENCY_ISSUE",
            ],
        },
        "routing": {
            "SECURITY_REQUIREMENT_ISSUE": "REQUIREMENTS",
            "AUTHENTICATION_ISSUE": "ROOT_CAUSE",
            "AUTHORIZATION_ISSUE": "ROOT_CAUSE",
            "SECRET_MANAGEMENT_ISSUE": "ROOT_CAUSE",
            "INPUT_VALIDATION_ISSUE": "ROOT_CAUSE",
            "INJECTION_RISK": "ROOT_CAUSE",
            "DATA_PROTECTION_ISSUE": "ROOT_CAUSE",
            "SENSITIVE_DATA_EXPOSURE": "ROOT_CAUSE",
            "ERROR_LOGGING_SECURITY_ISSUE": "ROOT_CAUSE",
            "DEPENDENCY_CONFIGURATION_ISSUE": "ROOT_CAUSE",
            "SECURITY_TEST_GAP": "ROOT_CAUSE",
            "CROSS_PHASE_SECURITY_CONSISTENCY_ISSUE": "ROOT_CAUSE",
        },
        "reports": {
            "directory": "reports/security-review",
            "required": [
                "security-review-report.json",
                "security-review-report.md",
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


def full_scope_criteria() -> list[dict[str, Any]]:
    return [
        criterion_result(name)
        for name in sorted(CRITERIA)
    ]


def requirements_scope_criteria() -> list[dict[str, Any]]:
    applicable = {
        "authentication-authorization",
        "input-validation-injection",
        "data-protection",
        "error-logging",
    }

    results: list[dict[str, Any]] = []

    for name in sorted(CRITERIA):
        if name in applicable:
            results.append(
                criterion_result(name)
            )
        else:
            results.append(
                criterion_result(
                    name,
                    applicable=False,
                    result="NOT_APPLICABLE",
                    reason="Outside REQUIREMENTS audit scope.",
                )
            )

    return results


def base_report(scope: str = "FULL") -> dict[str, Any]:
    if scope == "REQUIREMENTS":
        criteria_results = requirements_scope_criteria()
        pass_count = 4
        na_count = len(CRITERIA) - 4
    else:
        criteria_results = full_scope_criteria()
        pass_count = len(CRITERIA)
        na_count = 0

    return {
        "status": "PASS",
        "audit_scope": scope,
        "criteria_results": criteria_results,
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
            "json": "reports/security-review/security-review-report.json",
            "markdown": "reports/security-review/security-review-report.md",
        },
        "summary_message": "Security review passed.",
    }


def validation_pass() -> dict[str, Any]:
    return {"status": "PASS"}


class PolicyTest(unittest.TestCase):

    def test_valid_policy_passes(self) -> None:
        self.assertEqual(
            [],
            validator.validate_policy(base_policy()),
        )

    def test_missing_routing_fails(self) -> None:
        policy = base_policy()
        del policy["routing"]["AUTHORIZATION_ISSUE"]

        errors = validator.validate_policy(policy)

        self.assertTrue(
            any(
                "routing missing" in error
                and "AUTHORIZATION_ISSUE" in error
                for error in errors
            )
        )

    def test_blocking_severity_must_be_allowed(self) -> None:
        policy = base_policy()
        policy["severity"]["blocking"].append("UNKNOWN")

        errors = validator.validate_policy(policy)

        self.assertTrue(
            any(
                "severity.blocking" in error
                for error in errors
            )
        )

    def test_required_security_setting_missing_fails(self) -> None:
        policy = base_policy()
        del policy["security"]["secrets"]["allow_hardcoded_secret"]

        errors = validator.validate_policy(policy)

        self.assertTrue(
            any(
                "security.secrets.allow_hardcoded_secret" in error
                for error in errors
            )
        )


class CriteriaDiscoveryTest(unittest.TestCase):

    def test_discovers_all_criteria(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)

            for name in CRITERIA:
                (
                    root / f"{name}.criterion.md"
                ).write_text(
                    f"# {name}\n",
                    encoding="utf-8",
                )

            discovered = validator.discover_criteria(
                root,
                "*.criterion.md",
            )

        self.assertEqual(
            CRITERIA,
            discovered,
        )


class CriteriaResultTest(unittest.TestCase):

    def test_full_scope_all_passes(self) -> None:
        errors, counts = validator.validate_criteria_results(
            report=base_report("FULL"),
            criteria=CRITERIA,
            policy=base_policy(),
            scope="FULL",
        )

        self.assertEqual([], errors)
        self.assertEqual(len(CRITERIA), counts["pass"])
        self.assertEqual(0, counts["fail"])

    def test_missing_criterion_fails(self) -> None:
        report = base_report("FULL")
        report["criteria_results"] = report["criteria_results"][:-1]

        errors, _ = validator.validate_criteria_results(
            report=report,
            criteria=CRITERIA,
            policy=base_policy(),
            scope="FULL",
        )

        self.assertTrue(
            any(
                "Criterion not evaluated" in error
                for error in errors
            )
        )

    def test_not_applicable_requires_reason(self) -> None:
        report = base_report("REQUIREMENTS")

        target = next(
            item
            for item in report["criteria_results"]
            if item["criterion"] == "secrets-credentials"
        )
        target.pop("reason")

        errors, _ = validator.validate_criteria_results(
            report=report,
            criteria=CRITERIA,
            policy=base_policy(),
            scope="REQUIREMENTS",
        )

        self.assertTrue(
            any(
                "NOT_APPLICABLE requires reason" in error
                for error in errors
            )
        )

    def test_applicable_criterion_must_pass(self) -> None:
        report = base_report("FULL")

        target = next(
            item
            for item in report["criteria_results"]
            if item["criterion"] == "authentication-authorization"
        )
        target["result"] = "FAIL"

        errors, counts = validator.validate_criteria_results(
            report=report,
            criteria=CRITERIA,
            policy=base_policy(),
            scope="FULL",
        )

        self.assertTrue(
            any(
                "Applicable criterion is not PASS" in error
                for error in errors
            )
        )
        self.assertEqual(1, counts["fail"])

    def test_scope_outside_criterion_cannot_be_applicable(self) -> None:
        report = base_report("REQUIREMENTS")

        target = next(
            item
            for item in report["criteria_results"]
            if item["criterion"] == "security-test-coverage"
        )
        target["applicable"] = True
        target["result"] = "PASS"
        target.pop("reason", None)

        errors, _ = validator.validate_criteria_results(
            report=report,
            criteria=CRITERIA,
            policy=base_policy(),
            scope="REQUIREMENTS",
        )

        self.assertTrue(
            any(
                "outside audit_scope=REQUIREMENTS" in error
                for error in errors
            )
        )

    def test_unknown_criterion_fails(self) -> None:
        report = base_report("FULL")
        report["criteria_results"].append(
            criterion_result("unknown-security")
        )

        errors, _ = validator.validate_criteria_results(
            report=report,
            criteria=CRITERIA,
            policy=base_policy(),
            scope="FULL",
        )

        self.assertTrue(
            any(
                "unknown criterion" in error
                for error in errors
            )
        )


class SecretReportTest(unittest.TestCase):

    def test_normal_security_report_has_no_secret_error(self) -> None:
        report = base_report("FULL")
        report["issues"] = [
            {
                "issue_id": "SEC-001",
                "classification": "SECRET_MANAGEMENT_ISSUE",
                "severity": "LOW",
                "description": "Hard-coded credential reference found.",
                "evidence": "src/config.py:12 contains a hard-coded credential.",
                "recommended_route": "IMPLEMENTATION",
                "resolved": True,
            }
        ]

        errors = validator.validate_no_secret_values(report)

        self.assertEqual([], errors)

    def test_forbidden_secret_field_fails(self) -> None:
        report = base_report("FULL")
        report["secret_value"] = "abc12345"

        errors = validator.validate_no_secret_values(report)

        self.assertTrue(
            any(
                "must not contain secret values" in error
                for error in errors
            )
        )

    def test_raw_password_text_fails(self) -> None:
        report = base_report("FULL")
        report["summary_message"] = "password=supersecret"

        errors = validator.validate_no_secret_values(report)

        self.assertTrue(
            any(
                "raw secret value" in error
                for error in errors
            )
        )

    def test_api_key_text_fails(self) -> None:
        report = base_report("FULL")
        report["summary_message"] = "api_key: abcdef123456"

        errors = validator.validate_no_secret_values(report)

        self.assertTrue(
            any(
                "raw secret value" in error
                for error in errors
            )
        )


class IssueTest(unittest.TestCase):

    def test_valid_low_issue_passes(self) -> None:
        report = base_report("FULL")
        report["issues"] = [
            {
                "issue_id": "SEC-001",
                "classification": "AUTHORIZATION_ISSUE",
                "severity": "LOW",
                "description": "Minor authorization concern.",
                "evidence": "src/auth.py:44",
                "recommended_route": "IMPLEMENTATION",
                "resolved": False,
            }
        ]

        errors, counts = validator.validate_issues(
            report,
            base_policy(),
        )

        self.assertEqual([], errors)
        self.assertEqual(0, counts["blocking"])
        self.assertEqual(1, counts["unresolved"])

    def test_blocking_issue_fails(self) -> None:
        report = base_report("FULL")
        report["issues"] = [
            {
                "issue_id": "SEC-001",
                "classification": "AUTHORIZATION_ISSUE",
                "severity": "HIGH",
                "description": "Unauthorized access is possible.",
                "evidence": "src/auth.py:44",
                "recommended_route": "IMPLEMENTATION",
                "resolved": False,
            }
        ]

        errors, counts = validator.validate_issues(
            report,
            base_policy(),
        )

        self.assertEqual(1, counts["blocking"])
        self.assertTrue(
            any(
                "Unresolved blocking Security Review" in error
                for error in errors
            )
        )

    def test_fixed_route_mismatch_fails(self) -> None:
        report = base_report("FULL")
        report["issues"] = [
            {
                "issue_id": "SEC-001",
                "classification": "SECURITY_REQUIREMENT_ISSUE",
                "severity": "LOW",
                "description": "Security requirement is ambiguous.",
                "evidence": "docs/requirements/requirements.md",
                "recommended_route": "IMPLEMENTATION",
                "resolved": False,
            }
        ]

        errors, _ = validator.validate_issues(
            report,
            base_policy(),
        )

        self.assertTrue(
            any(
                "recommended_route" in error
                and "REQUIREMENTS" in error
                for error in errors
            )
        )

    def test_root_cause_requires_concrete_route(self) -> None:
        report = base_report("FULL")
        report["issues"] = [
            {
                "issue_id": "SEC-001",
                "classification": "INJECTION_RISK",
                "severity": "LOW",
                "description": "Potential unsafe query construction.",
                "evidence": "src/repository.py:88",
                "recommended_route": "ROOT_CAUSE",
                "resolved": False,
            }
        ]

        errors, _ = validator.validate_issues(
            report,
            base_policy(),
        )

        self.assertTrue(
            any(
                "concrete root-cause phase" in error
                for error in errors
            )
        )

    def test_invalid_classification_fails(self) -> None:
        report = base_report("FULL")
        report["issues"] = [
            {
                "issue_id": "SEC-001",
                "classification": "UNKNOWN_SECURITY_ISSUE",
                "severity": "LOW",
                "description": "Unknown issue.",
                "evidence": "artifact",
                "recommended_route": "IMPLEMENTATION",
                "resolved": False,
            }
        ]

        errors, _ = validator.validate_issues(
            report,
            base_policy(),
        )

        self.assertTrue(
            any(
                "invalid classification" in error
                for error in errors
            )
        )

    def test_invalid_severity_fails(self) -> None:
        report = base_report("FULL")
        report["issues"] = [
            {
                "issue_id": "SEC-001",
                "classification": "AUTHENTICATION_ISSUE",
                "severity": "UNKNOWN",
                "description": "Authentication issue.",
                "evidence": "artifact",
                "recommended_route": "IMPLEMENTATION",
                "resolved": False,
            }
        ]

        errors, _ = validator.validate_issues(
            report,
            base_policy(),
        )

        self.assertTrue(
            any(
                "invalid severity" in error
                for error in errors
            )
        )

    def test_issue_requires_evidence(self) -> None:
        report = base_report("FULL")
        report["issues"] = [
            {
                "issue_id": "SEC-001",
                "classification": "AUTHENTICATION_ISSUE",
                "severity": "LOW",
                "description": "Authentication issue.",
                "recommended_route": "IMPLEMENTATION",
                "resolved": False,
            }
        ]

        errors, _ = validator.validate_issues(
            report,
            base_policy(),
        )

        self.assertTrue(
            any(
                "evidence is required" in error
                for error in errors
            )
        )


class ReportHeaderTest(unittest.TestCase):

    def test_valid_header_passes(self) -> None:
        errors, scope = validator.validate_report_header(
            base_report("FULL"),
            base_policy(),
        )

        self.assertEqual([], errors)
        self.assertEqual("FULL", scope)

    def test_invalid_scope_fails(self) -> None:
        report = base_report("FULL")
        report["audit_scope"] = "UNKNOWN"

        errors, _ = validator.validate_report_header(
            report,
            base_policy(),
        )

        self.assertTrue(
            any(
                "audit_scope" in error
                for error in errors
            )
        )

    def test_invalid_status_fails(self) -> None:
        report = base_report("FULL")
        report["status"] = "SUCCESS"

        errors, _ = validator.validate_report_header(
            report,
            base_policy(),
        )

        self.assertTrue(
            any(
                "report status" in error
                for error in errors
            )
        )


class RequiredReportTest(unittest.TestCase):

    def test_missing_required_report_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            reports = Path(temp)

            (
                reports / "security-review-report.json"
            ).write_text(
                "{}",
                encoding="utf-8",
            )

            errors = validator.validate_required_reports(
                reports,
                base_policy(),
            )

        self.assertTrue(
            any(
                "security-review-report.md" in error
                for error in errors
            )
        )


class UpstreamValidatorTest(unittest.TestCase):

    def test_requirements_scope_does_not_require_test_validators(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)

            errors = validator.validate_upstream_validators(
                scope="REQUIREMENTS",
                unit_validation_path=root / "unit.json",
                integration_validation_path=root / "integration.json",
            )

        self.assertEqual([], errors)

    def test_unit_scope_requires_unit_validator_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            unit_path = root / "unit.json"

            unit_path.write_text(
                json.dumps({"status": "FAIL"}),
                encoding="utf-8",
            )

            errors = validator.validate_upstream_validators(
                scope="UNIT_TEST",
                unit_validation_path=unit_path,
                integration_validation_path=root / "integration.json",
            )

        self.assertTrue(
            any(
                "Unit Test validation-result status is not PASS" in error
                for error in errors
            )
        )

    def test_integration_scope_requires_both_validators_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            unit_path = root / "unit.json"
            integration_path = root / "integration.json"

            unit_path.write_text(
                json.dumps(validation_pass()),
                encoding="utf-8",
            )
            integration_path.write_text(
                json.dumps(validation_pass()),
                encoding="utf-8",
            )

            errors = validator.validate_upstream_validators(
                scope="INTEGRATION_TEST",
                unit_validation_path=unit_path,
                integration_validation_path=integration_path,
            )

        self.assertEqual([], errors)

    def test_missing_integration_validator_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            unit_path = root / "unit.json"

            unit_path.write_text(
                json.dumps(validation_pass()),
                encoding="utf-8",
            )

            errors = validator.validate_upstream_validators(
                scope="INTEGRATION_TEST",
                unit_validation_path=unit_path,
                integration_validation_path=root / "missing.json",
            )

        self.assertTrue(
            any(
                "Integration Test validation result missing" in error
                for error in errors
            )
        )


class SummaryTest(unittest.TestCase):

    def test_correct_summary_passes(self) -> None:
        report = base_report("FULL")

        errors = validator.validate_summary(
            report,
            {
                "total": len(CRITERIA),
                "pass": len(CRITERIA),
                "not_applicable": 0,
                "fail": 0,
            },
            {
                "total": 0,
                "blocking": 0,
                "unresolved": 0,
            },
        )

        self.assertEqual([], errors)

    def test_summary_mismatch_fails(self) -> None:
        report = base_report("FULL")
        report["summary"]["criteria_pass"] = 999

        errors = validator.validate_summary(
            report,
            {
                "total": len(CRITERIA),
                "pass": len(CRITERIA),
                "not_applicable": 0,
                "fail": 0,
            },
            {
                "total": 0,
                "blocking": 0,
                "unresolved": 0,
            },
        )

        self.assertTrue(
            any(
                "summary.criteria_pass" in error
                for error in errors
            )
        )


class ReportStatusTest(unittest.TestCase):

    def test_pass_without_errors_is_valid(self) -> None:
        errors = validator.validate_report_status(
            report=base_report("FULL"),
            criteria_counts={
                "total": len(CRITERIA),
                "pass": len(CRITERIA),
                "not_applicable": 0,
                "fail": 0,
            },
            issue_counts={
                "total": 0,
                "blocking": 0,
                "unresolved": 0,
            },
            current_errors=[],
        )

        self.assertEqual([], errors)

    def test_pass_with_failed_criterion_fails(self) -> None:
        errors = validator.validate_report_status(
            report=base_report("FULL"),
            criteria_counts={
                "total": len(CRITERIA),
                "pass": len(CRITERIA) - 1,
                "not_applicable": 0,
                "fail": 1,
            },
            issue_counts={
                "total": 0,
                "blocking": 0,
                "unresolved": 0,
            },
            current_errors=[],
        )

        self.assertTrue(
            any(
                "criteria FAIL exists" in error
                for error in errors
            )
        )

    def test_pass_with_blocking_issue_fails(self) -> None:
        errors = validator.validate_report_status(
            report=base_report("FULL"),
            criteria_counts={
                "total": len(CRITERIA),
                "pass": len(CRITERIA),
                "not_applicable": 0,
                "fail": 0,
            },
            issue_counts={
                "total": 1,
                "blocking": 1,
                "unresolved": 1,
            },
            current_errors=[],
        )

        self.assertTrue(
            any(
                "blocking Security Issue exists" in error
                for error in errors
            )
        )

    def test_pass_with_deterministic_error_fails(self) -> None:
        errors = validator.validate_report_status(
            report=base_report("FULL"),
            criteria_counts={
                "total": len(CRITERIA),
                "pass": len(CRITERIA),
                "not_applicable": 0,
                "fail": 0,
            },
            issue_counts={
                "total": 0,
                "blocking": 0,
                "unresolved": 0,
            },
            current_errors=[
                "secret leakage detected"
            ],
        )

        self.assertTrue(
            any(
                "deterministic validation found errors" in error
                for error in errors
            )
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
