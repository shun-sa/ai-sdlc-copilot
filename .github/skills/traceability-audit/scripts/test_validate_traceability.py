#!/usr/bin/env python3

"""
Unit tests for validate_traceability.py

Run:
    python .github/skills/traceability-audit/scripts/test_validate_traceability.py

No third-party test framework is required.
PyYAML is required because validate_traceability.py imports yaml.
"""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
VALIDATOR_PATH = SCRIPT_DIR / "validate_traceability.py"

SPEC = importlib.util.spec_from_file_location(
    "validate_traceability",
    VALIDATOR_PATH,
)

if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Unable to import validator: {VALIDATOR_PATH}")

validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


def base_policy() -> dict[str, Any]:
    allowed = [
        "INVALID_REQUIREMENT_REFERENCE",
        "INVALID_ADR_REFERENCE",
        "REQUIREMENT_ADR_TRACEABILITY_MISSING",
        "IMPLEMENTATION_TRACEABILITY_MISSING",
        "UNIT_TEST_TRACEABILITY_MISSING",
        "INTEGRATION_TEST_TRACEABILITY_MISSING",
        "ADR_IMPLEMENTATION_MISMATCH",
        "TEST_REQUIREMENT_MISMATCH",
        "ORPHAN_ADR",
        "ORPHAN_TEST",
        "STALE_EVIDENCE",
        "TRACEABILITY_CONFLICT",
    ]

    routing = {
        "INVALID_REQUIREMENT_REFERENCE": "REQUIREMENTS",
        "INVALID_ADR_REFERENCE": "ARCHITECTURE",
        "REQUIREMENT_ADR_TRACEABILITY_MISSING": "ARCHITECTURE",
        "IMPLEMENTATION_TRACEABILITY_MISSING": "IMPLEMENTATION",
        "UNIT_TEST_TRACEABILITY_MISSING": "UNIT_TEST",
        "INTEGRATION_TEST_TRACEABILITY_MISSING": "INTEGRATION_TEST",
        "ADR_IMPLEMENTATION_MISMATCH": "IMPLEMENTATION",
        "TEST_REQUIREMENT_MISMATCH": "UNIT_TEST",
        "ORPHAN_ADR": "ARCHITECTURE",
        "ORPHAN_TEST": "UNIT_TEST",
        "STALE_EVIDENCE": "IMPLEMENTATION",
        "TRACEABILITY_CONFLICT": "REQUIREMENTS",
    }

    return {
        "audit": {
            "require_forward_traceability": True,
            "require_reverse_traceability": True,
            "allow_unresolved_blocking_issue": False,
        },
        "requirements": {
            "allow_invented_requirement_id": False,
            "require_existing_reference": True,
        },
        "global_requirements": {
            "allow_source_reference_without_id": True,
            "allow_generated_id": False,
        },
        "adr": {
            "downstream_status": ["Accepted"],
            "require_related_requirements": True,
            "allow_invalid_requirement_reference": False,
            "allow_superseded_as_current_decision": False,
        },
        "implementation": {
            "require_mapping_for_implementation_responsible_requirement": True,
            "allow_missing_mapping": False,
        },
        "unit_test": {
            "require_mapping_for_unit_testable_requirement": True,
            "allow_missing_mapping": False,
            "allow_not_applicable": True,
            "require_reason_when_not_applicable": True,
        },
        "integration_test": {
            "require_mapping_for_integration_testable_requirement": True,
            "allow_missing_mapping": False,
            "allow_not_applicable": True,
            "require_reason_when_not_applicable": True,
        },
        "coverage": {
            "requirement_to_implementation": {"required_rate": 100},
            "requirement_to_unit_test": {"required_rate": 100},
            "requirement_to_integration_test": {"required_rate": 100},
            "requirement_to_adr": {"enforce_rate": False},
        },
        "orphan_artifacts": {
            "allow_orphan_test": False,
            "allow_orphan_accepted_adr": False,
        },
        "stale_evidence": {"allowed": False},
        "conflicts": {"allowed": False},
        "severity": {"blocking": ["CRITICAL", "HIGH"]},
        "issue_classification": {"allowed": allowed},
        "routing": routing,
        "reports": {
            "directory": "reports/traceability",
            "required": [
                "traceability-report.json",
                "traceability-report.md",
            ],
        },
    }


def accepted_adrs(requirement_id: str = "FR-001") -> dict[str, dict[str, Any]]:
    return {
        "ADR-001": {
            "id": "ADR-001",
            "path": "docs/adr/ADR-001-test.md",
            "status": "Accepted",
            "related_requirements": [requirement_id],
        }
    }


def unit_evidence() -> dict[str, Any]:
    return {
        "requirement_coverage": [
            {
                "requirement_id": "FR-001",
                "tests": ["test_register_user"],
                "result": "PASS",
            }
        ]
    }


def integration_plan() -> dict[str, Any]:
    return {
        "cases": [
            {
                "case_id": "AI-IT-001",
                "origin": "AI_GENERATED",
                "generation_stage": "INITIAL",
                "requirement_id": "FR-001",
            }
        ]
    }


def integration_evidence() -> dict[str, Any]:
    return {
        "case_results": [
            {
                "case_id": "AI-IT-001",
                "origin": "AI_GENERATED",
                "requirement_id": "FR-001",
                "result": "PASS",
            }
        ]
    }


def base_entry() -> dict[str, Any]:
    return {
        "requirement_reference": "FR-001",
        "adr_required": True,
        "adrs": ["ADR-001"],
        "implementation_applicable": True,
        "implementation": [
            {
                "file": "src/user_service.py",
                "symbol": "register_user",
            }
        ],
        "unit_test_applicable": True,
        "unit_tests": ["test_register_user"],
        "integration_test_applicable": True,
        "integration_tests": ["AI-IT-001"],
    }


def base_report() -> dict[str, Any]:
    return {
        "status": "PASS",
        "audit_scope": "FULL",
        "summary": {
            "requirements": 1,
            "accepted_adrs": 1,
            "implementation_mappings": 1,
            "unit_test_mappings": 1,
            "integration_test_mappings": 1,
            "issues": 0,
        },
        "coverage": {
            "requirement_to_adr": 100,
            "requirement_to_implementation": 100,
            "requirement_to_unit_test": 100,
            "requirement_to_integration_test": 100,
        },
        "traceability": [base_entry()],
        "issues": [],
    }


class PolicyTest(unittest.TestCase):

    def test_valid_policy_passes(self) -> None:
        self.assertEqual([], validator.validate_policy(base_policy()))

    def test_missing_routing_fails(self) -> None:
        policy = base_policy()
        del policy["routing"]["ORPHAN_TEST"]

        errors = validator.validate_policy(policy)

        self.assertTrue(
            any("routing missing" in error and "ORPHAN_TEST" in error for error in errors)
        )


class RequirementDiscoveryTest(unittest.TestCase):

    def test_discovers_requirement_ids_and_ignores_adr(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            requirements = root / "requirements.md"
            features = root / "features"
            features.mkdir()

            requirements.write_text(
                "FR-001\nNFR-001\nRelated ADR-001\n",
                encoding="utf-8",
            )
            (features / "feature.md").write_text(
                "FR-002",
                encoding="utf-8",
            )

            ids, _ = validator.discover_requirement_ids(
                requirements,
                features,
            )

        self.assertEqual(
            {"FR-001", "FR-002", "NFR-001"},
            ids,
        )


class AdrTest(unittest.TestCase):

    def test_accepted_adr_existing_requirement_passes(self) -> None:
        errors = validator.validate_adrs(
            accepted_adrs(),
            {"FR-001"},
            base_policy(),
            "FULL",
        )
        self.assertEqual([], errors)

    def test_accepted_adr_invalid_requirement_fails(self) -> None:
        errors = validator.validate_adrs(
            accepted_adrs("FR-999"),
            {"FR-001"},
            base_policy(),
            "FULL",
        )

        self.assertTrue(
            any("FR-999" in error and "does not exist" in error for error in errors)
        )

    def test_accepted_adr_without_related_requirement_fails(self) -> None:
        adrs = accepted_adrs()
        adrs["ADR-001"]["related_requirements"] = []

        errors = validator.validate_adrs(
            adrs,
            {"FR-001"},
            base_policy(),
            "FULL",
        )

        self.assertTrue(
            any("no Related Requirements" in error for error in errors)
        )


class TraceabilityEntryTest(unittest.TestCase):

    def _repo_with_implementation(self) -> tempfile.TemporaryDirectory[str]:
        return tempfile.TemporaryDirectory()

    def test_full_valid_mapping_passes(self) -> None:
        with self._repo_with_implementation() as temp:
            root = Path(temp)
            (root / "src").mkdir()
            (root / "src/user_service.py").write_text(
                "def register_user():\n    pass\n",
                encoding="utf-8",
            )

            errors, metrics = validator.validate_traceability_entries(
                report=base_report(),
                requirement_ids={"FR-001"},
                adrs=accepted_adrs(),
                repo_root=root,
                unit_evidence=unit_evidence(),
                integration_plan=integration_plan(),
                integration_evidence=integration_evidence(),
                policy=base_policy(),
                scope="FULL",
            )

        self.assertEqual([], errors)
        self.assertEqual(100.0, metrics["requirement_to_implementation"]["rate"])
        self.assertEqual(100.0, metrics["requirement_to_unit_test"]["rate"])
        self.assertEqual(100.0, metrics["requirement_to_integration_test"]["rate"])

    def test_unknown_requirement_reference_fails(self) -> None:
        report = base_report()
        report["traceability"][0]["requirement_reference"] = "FR-999"

        with self._repo_with_implementation() as temp:
            root = Path(temp)
            (root / "src").mkdir()
            (root / "src/user_service.py").write_text("pass\n", encoding="utf-8")

            errors, _ = validator.validate_traceability_entries(
                report=report,
                requirement_ids={"FR-001"},
                adrs=accepted_adrs(),
                repo_root=root,
                unit_evidence=unit_evidence(),
                integration_plan=integration_plan(),
                integration_evidence=integration_evidence(),
                policy=base_policy(),
                scope="FULL",
            )

        self.assertTrue(
            any("Requirement reference does not exist" in error for error in errors)
        )

    def test_missing_implementation_mapping_fails(self) -> None:
        report = base_report()
        report["traceability"][0]["implementation"] = []

        with self._repo_with_implementation() as temp:
            root = Path(temp)

            errors, metrics = validator.validate_traceability_entries(
                report=report,
                requirement_ids={"FR-001"},
                adrs=accepted_adrs(),
                repo_root=root,
                unit_evidence=unit_evidence(),
                integration_plan=integration_plan(),
                integration_evidence=integration_evidence(),
                policy=base_policy(),
                scope="FULL",
            )

        self.assertTrue(
            any("Implementation mapping is missing" in error for error in errors)
        )
        self.assertEqual(0.0, metrics["requirement_to_implementation"]["rate"])

    def test_missing_implementation_file_fails(self) -> None:
        with self._repo_with_implementation() as temp:
            root = Path(temp)

            errors, _ = validator.validate_traceability_entries(
                report=base_report(),
                requirement_ids={"FR-001"},
                adrs=accepted_adrs(),
                repo_root=root,
                unit_evidence=unit_evidence(),
                integration_plan=integration_plan(),
                integration_evidence=integration_evidence(),
                policy=base_policy(),
                scope="FULL",
            )

        self.assertTrue(
            any("Implementation file does not exist" in error for error in errors)
        )

    def test_unit_evidence_without_requirement_fails(self) -> None:
        with self._repo_with_implementation() as temp:
            root = Path(temp)
            (root / "src").mkdir()
            (root / "src/user_service.py").write_text("pass\n", encoding="utf-8")

            errors, _ = validator.validate_traceability_entries(
                report=base_report(),
                requirement_ids={"FR-001"},
                adrs=accepted_adrs(),
                repo_root=root,
                unit_evidence={"requirement_coverage": []},
                integration_plan=integration_plan(),
                integration_evidence=integration_evidence(),
                policy=base_policy(),
                scope="FULL",
            )

        self.assertTrue(
            any("Unit Test evidence does not reference" in error for error in errors)
        )

    def test_unknown_integration_case_fails(self) -> None:
        report = base_report()
        report["traceability"][0]["integration_tests"] = ["AI-IT-999"]

        with self._repo_with_implementation() as temp:
            root = Path(temp)
            (root / "src").mkdir()
            (root / "src/user_service.py").write_text("pass\n", encoding="utf-8")

            errors, _ = validator.validate_traceability_entries(
                report=report,
                requirement_ids={"FR-001"},
                adrs=accepted_adrs(),
                repo_root=root,
                unit_evidence=unit_evidence(),
                integration_plan=integration_plan(),
                integration_evidence=integration_evidence(),
                policy=base_policy(),
                scope="FULL",
            )

        self.assertTrue(
            any("Integration Test Case does not exist" in error for error in errors)
        )

    def test_not_applicable_requires_reason(self) -> None:
        report = base_report()
        entry = report["traceability"][0]
        entry["unit_test_applicable"] = False
        entry["unit_tests"] = []

        with self._repo_with_implementation() as temp:
            root = Path(temp)
            (root / "src").mkdir()
            (root / "src/user_service.py").write_text("pass\n", encoding="utf-8")

            errors, _ = validator.validate_traceability_entries(
                report=report,
                requirement_ids={"FR-001"},
                adrs=accepted_adrs(),
                repo_root=root,
                unit_evidence=unit_evidence(),
                integration_plan=integration_plan(),
                integration_evidence=integration_evidence(),
                policy=base_policy(),
                scope="FULL",
            )

        self.assertTrue(
            any("Unit Test NOT_APPLICABLE requires reason" in error for error in errors)
        )


class CoverageTest(unittest.TestCase):

    def test_reported_coverage_mismatch_fails(self) -> None:
        report = base_report()
        report["coverage"]["requirement_to_implementation"] = 50

        metrics = {
            "requirement_to_adr": {"total": 1, "covered": 1, "rate": 100.0},
            "requirement_to_implementation": {"total": 1, "covered": 1, "rate": 100.0},
            "requirement_to_unit_test": {"total": 1, "covered": 1, "rate": 100.0},
            "requirement_to_integration_test": {"total": 1, "covered": 1, "rate": 100.0},
        }

        errors = validator.validate_coverage(
            report,
            metrics,
            base_policy(),
            "FULL",
        )

        self.assertTrue(
            any("recalculated rate is 100.00" in error for error in errors)
        )

    def test_coverage_below_policy_fails(self) -> None:
        report = base_report()
        report["coverage"]["requirement_to_implementation"] = 50

        metrics = {
            "requirement_to_adr": {"total": 0, "covered": 0, "rate": 100.0},
            "requirement_to_implementation": {"total": 2, "covered": 1, "rate": 50.0},
            "requirement_to_unit_test": {"total": 1, "covered": 1, "rate": 100.0},
            "requirement_to_integration_test": {"total": 1, "covered": 1, "rate": 100.0},
        }

        errors = validator.validate_coverage(
            report,
            metrics,
            base_policy(),
            "FULL",
        )

        self.assertTrue(
            any("coverage 50.00% < required 100.00%" in error for error in errors)
        )


class IssueTest(unittest.TestCase):

    def test_correct_routing_and_blocking_issue(self) -> None:
        report = base_report()
        report["issues"] = [
            {
                "issue_id": "TRACE-001",
                "classification": "IMPLEMENTATION_TRACEABILITY_MISSING",
                "severity": "HIGH",
                "requirement_reference": "FR-001",
                "description": "Implementation mapping missing.",
                "recommended_route": "IMPLEMENTATION",
                "resolved": False,
            }
        ]

        errors, blocking = validator.validate_issues(
            report,
            {"FR-001"},
            accepted_adrs(),
            base_policy(),
        )

        self.assertEqual([], errors)
        self.assertEqual(1, blocking)

    def test_wrong_routing_fails(self) -> None:
        report = base_report()
        report["issues"] = [
            {
                "issue_id": "TRACE-001",
                "classification": "IMPLEMENTATION_TRACEABILITY_MISSING",
                "severity": "HIGH",
                "requirement_reference": "FR-001",
                "description": "Implementation mapping missing.",
                "recommended_route": "UNIT_TEST",
                "resolved": False,
            }
        ]

        errors, _ = validator.validate_issues(
            report,
            {"FR-001"},
            accepted_adrs(),
            base_policy(),
        )

        self.assertTrue(
            any("recommended_route" in error and "IMPLEMENTATION" in error for error in errors)
        )

    def test_invalid_classification_fails(self) -> None:
        report = base_report()
        report["issues"] = [
            {
                "issue_id": "TRACE-001",
                "classification": "UNKNOWN_ERROR",
                "severity": "HIGH",
                "description": "Unknown.",
                "recommended_route": "IMPLEMENTATION",
                "resolved": False,
            }
        ]

        errors, _ = validator.validate_issues(
            report,
            {"FR-001"},
            accepted_adrs(),
            base_policy(),
        )

        self.assertTrue(
            any("invalid classification" in error for error in errors)
        )

    def test_resolved_critical_issue_is_not_blocking(self) -> None:
        issue = {
            "classification": "TRACEABILITY_CONFLICT",
            "severity": "CRITICAL",
            "resolved": True,
        }

        self.assertFalse(
            validator.issue_is_policy_failure(
                issue,
                base_policy(),
            )
        )


class ReportHeaderTest(unittest.TestCase):

    def test_invalid_scope_fails(self) -> None:
        errors, _ = validator.validate_report_header(
            {
                "status": "PASS",
                "audit_scope": "UNKNOWN",
            }
        )

        self.assertTrue(any("audit_scope" in error for error in errors))

    def test_invalid_status_fails(self) -> None:
        errors, _ = validator.validate_report_header(
            {
                "status": "SUCCESS",
                "audit_scope": "FULL",
            }
        )

        self.assertTrue(any("report status" in error for error in errors))


class RequiredReportTest(unittest.TestCase):

    def test_missing_required_report_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            reports = Path(temp)
            (reports / "traceability-report.json").write_text(
                "{}",
                encoding="utf-8",
            )

            errors = validator.validate_required_reports(
                reports,
                base_policy(),
            )

        self.assertTrue(
            any("traceability-report.md" in error for error in errors)
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
