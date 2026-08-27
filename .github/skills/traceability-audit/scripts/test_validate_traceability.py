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
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

import yaml


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
        "ORPHAN_IMPLEMENTATION",
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
        "ORPHAN_IMPLEMENTATION": "IMPLEMENTATION",
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
            "architecture_scope_status": ["Proposed", "Accepted"],
            "downstream_status": ["Accepted"],
            "require_related_requirements": True,
            "allow_invalid_requirement_reference": False,
            "allow_superseded_as_current_decision": False,
        },
        "trace_map": {
            "required": True,
            "path": "reports/traceability/trace-map.json",
            "version": 2,
            "derived": True,
            "allow_as_source_of_truth": False,
            "require_regeneration_on_source_change": True,
        },
        "ast_index": {
            "required": True,
            "path": "reports/traceability/ast-index.json",
            "version": 1,
            "derived": True,
            "allow_as_source_of_truth": False,
        },
        "source_analysis": {
            "enabled": True,
            "production_roots": ["src", "app"],
            "test_roots": ["tests", "test", "src/test"],
            "test_file_patterns": [
                "**/test_*.py",
                "**/*_test.py",
                "**/*.test.ts",
                "**/*.test.tsx",
                "**/*.spec.ts",
                "**/*.spec.tsx",
                "**/*.test.js",
                "**/*.test.jsx",
                "**/*.spec.js",
                "**/*.spec.jsx",
                "**/__tests__/**",
            ],
            "include_extensions": [".py", ".java", ".ts", ".tsx", ".js", ".jsx"],
            "exclude_globs": ["**/__pycache__/**", "**/node_modules/**"],
        },
        "symbol_validation": {
            "validate_symbol_when_present": True,
            "validate_qualified_name_when_present": True,
            "require_symbol_for_supported_source": True,
            "require_qualified_name_for_supported_source": True,
            "fail_when_resolver_unavailable": False,
        },
        "implementation": {
            "require_mapping_for_implementation_responsible_requirement": True,
            "allow_missing_mapping": False,
        },
        "implementation_analysis": {
            "detect_orphan_symbols": True,
            "candidate_kinds": ["class", "function", "method"],
            "ignore_private_symbols": True,
            "ignore_file_patterns": [],
            "ignore_symbol_patterns": [],
        },
        "unit_test": {
            "require_mapping_for_unit_testable_requirement": True,
            "allow_missing_mapping": False,
            "allow_not_applicable": True,
            "require_reason_when_not_applicable": True,
        },
        "code_test_traceability": {
            "enabled": True,
            "require_test_file_mapping": True,
            "require_test_symbol_mapping": True,
            "require_call_to_mapped_implementation": True,
            "allow_transitive_calls": True,
            "max_call_depth": 5,
            "require_assertion": True,
            "require_trace_map_targets": True,
            "require_trace_map_assertion_count": True,
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
            "allow_orphan_implementation": False,
        },
        "stale_evidence": {"allowed": False},
        "conflicts": {"allowed": False},
        "severity": {"blocking": ["CRITICAL", "HIGH"]},
        "issue_classification": {"allowed": allowed},
        "routing": routing,
        "reports": {
            "directory": "reports/traceability",
            "required": [
                "ast-index.json",
                "trace-map.json",
                "traceability-report.json",
                "traceability-report.md",
            ],
        },
    }


def adrs_with_status(
    status: str,
    requirement_id: str = "FR-001",
) -> dict[str, dict[str, Any]]:
    return {
        "ADR-001": {
            "id": "ADR-001",
            "path": "docs/adr/ADR-001-test.md",
            "status": status,
            "related_requirements": [requirement_id],
        }
    }


def accepted_adrs(requirement_id: str = "FR-001") -> dict[str, dict[str, Any]]:
    return adrs_with_status("Accepted", requirement_id)


def proposed_adrs(requirement_id: str = "FR-001") -> dict[str, dict[str, Any]]:
    return adrs_with_status("Proposed", requirement_id)


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
                "qualified_name": "src.user_service.register_user",
            }
        ],
        "unit_test_applicable": True,
        "unit_tests": [
            {
                "test_id": "test_register_user",
                "file": "tests/test_user_service.py",
                "symbol": "test_register_user",
                "qualified_name": "tests.test_user_service.test_register_user",
                "implementation_targets": ["src.user_service.register_user"],
                "assertion_count": 1,
            }
        ],
        "integration_test_applicable": True,
        "integration_tests": [
            {
                "case_id": "AI-IT-001",
            }
        ],
    }


def base_trace_map(scope: str = "FULL") -> dict[str, Any]:
    return {
        "version": 2,
        "audit_scope": scope,
        "ast_index": {
            "path": "reports/traceability/ast-index.json",
            "version": 1,
            "source_fingerprint": "TEST-FINGERPRINT",
        },
        "entries": [base_entry()],
    }


def base_report(scope: str = "FULL") -> dict[str, Any]:
    return {
        "status": "PASS",
        "audit_scope": scope,
        "trace_map": {
            "path": "reports/traceability/trace-map.json",
            "version": 2,
        },
        "summary": {
            "requirements": 1,
            "accepted_adrs": 1,
            "implementation_mappings": 1 if scope != "ARCHITECTURE" else 0,
            "unit_test_mappings": 1 if scope in {"UNIT_TEST", "INTEGRATION_TEST", "FULL"} else 0,
            "integration_test_mappings": 1 if scope in {"INTEGRATION_TEST", "FULL"} else 0,
            "issues": 0,
        },
        "coverage": {
            "requirement_to_adr": 100,
            "requirement_to_implementation": 100,
            "requirement_to_unit_test": 100,
            "requirement_to_integration_test": 100,
        },
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

    def test_missing_trace_map_policy_fails(self) -> None:
        policy = base_policy()
        del policy["trace_map"]["path"]

        errors = validator.validate_policy(policy)

        self.assertTrue(
            any("trace_map.path" in error for error in errors)
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

    def test_proposed_adr_is_valid_in_architecture_scope(self) -> None:
        errors = validator.validate_adrs(
            proposed_adrs(),
            {"FR-001"},
            base_policy(),
            "ARCHITECTURE",
        )
        self.assertEqual([], errors)

    def test_proposed_adr_is_not_current_in_full_scope_mapping(self) -> None:
        trace_map = base_trace_map("FULL")

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "src").mkdir()
            (root / "src/user_service.py").write_text("pass\n", encoding="utf-8")

            errors, _ = validator.validate_traceability_entries(
                trace_map=trace_map,
                requirement_ids={"FR-001"},
                adrs=proposed_adrs(),
                repo_root=root,
                unit_evidence=unit_evidence(),
                integration_plan=integration_plan(),
                integration_evidence=integration_evidence(),
                policy=base_policy(),
                scope="FULL",
            )

        self.assertTrue(
            any("not valid for the current audit scope" in error for error in errors)
        )

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


class TraceMapHeaderTest(unittest.TestCase):

    def test_valid_trace_map_header_passes(self) -> None:
        errors = validator.validate_trace_map_header(
            base_trace_map(),
            "FULL",
            base_policy(),
        )
        self.assertEqual([], errors)

    def test_invalid_trace_map_version_fails(self) -> None:
        trace_map = base_trace_map()
        trace_map["version"] = 999

        errors = validator.validate_trace_map_header(
            trace_map,
            "FULL",
            base_policy(),
        )

        self.assertTrue(any("version" in error for error in errors))

    def test_trace_map_scope_mismatch_fails(self) -> None:
        errors = validator.validate_trace_map_header(
            base_trace_map("ARCHITECTURE"),
            "FULL",
            base_policy(),
        )

        self.assertTrue(any("audit_scope" in error for error in errors))

    def test_trace_map_without_entries_fails(self) -> None:
        trace_map = base_trace_map()
        del trace_map["entries"]

        errors = validator.validate_trace_map_header(
            trace_map,
            "FULL",
            base_policy(),
        )

        self.assertTrue(any("entries array" in error for error in errors))


class TraceMapReferenceTest(unittest.TestCase):

    def test_valid_reference_passes(self) -> None:
        errors = validator.validate_trace_map_reference(
            base_report(),
            base_trace_map(),
            base_policy(),
        )
        self.assertEqual([], errors)

    def test_missing_reference_fails(self) -> None:
        report = base_report()
        del report["trace_map"]

        errors = validator.validate_trace_map_reference(
            report,
            base_trace_map(),
            base_policy(),
        )

        self.assertTrue(any("trace_map reference" in error for error in errors))

    def test_version_mismatch_fails(self) -> None:
        report = base_report()
        report["trace_map"]["version"] = 1

        errors = validator.validate_trace_map_reference(
            report,
            base_trace_map(),
            base_policy(),
        )

        self.assertTrue(any("version mismatch" in error.lower() for error in errors))

    def test_legacy_traceability_array_fails(self) -> None:
        report = base_report()
        report["traceability"] = [base_entry()]

        errors = validator.validate_trace_map_reference(
            report,
            base_trace_map(),
            base_policy(),
        )

        self.assertTrue(any("must not contain" in error for error in errors))


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
                trace_map=base_trace_map(),
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

    def test_string_test_mapping_is_still_supported(self) -> None:
        trace_map = base_trace_map()
        trace_map["entries"][0]["unit_tests"] = ["test_register_user"]
        trace_map["entries"][0]["integration_tests"] = ["AI-IT-001"]

        with self._repo_with_implementation() as temp:
            root = Path(temp)
            (root / "src").mkdir()
            (root / "src/user_service.py").write_text("pass\n", encoding="utf-8")

            errors, _ = validator.validate_traceability_entries(
                trace_map=trace_map,
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

    def test_unknown_requirement_reference_fails(self) -> None:
        trace_map = base_trace_map()
        trace_map["entries"][0]["requirement_reference"] = "FR-999"

        with self._repo_with_implementation() as temp:
            root = Path(temp)
            (root / "src").mkdir()
            (root / "src/user_service.py").write_text("pass\n", encoding="utf-8")

            errors, _ = validator.validate_traceability_entries(
                trace_map=trace_map,
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
        trace_map = base_trace_map()
        trace_map["entries"][0]["implementation"] = []

        with self._repo_with_implementation() as temp:
            root = Path(temp)

            errors, metrics = validator.validate_traceability_entries(
                trace_map=trace_map,
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
                trace_map=base_trace_map(),
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
                trace_map=base_trace_map(),
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
        trace_map = base_trace_map()
        trace_map["entries"][0]["integration_tests"] = [
            {"case_id": "AI-IT-999"}
        ]

        with self._repo_with_implementation() as temp:
            root = Path(temp)
            (root / "src").mkdir()
            (root / "src/user_service.py").write_text("pass\n", encoding="utf-8")

            errors, _ = validator.validate_traceability_entries(
                trace_map=trace_map,
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
        trace_map = base_trace_map()
        entry = trace_map["entries"][0]
        entry["unit_test_applicable"] = False
        entry["unit_tests"] = []

        with self._repo_with_implementation() as temp:
            root = Path(temp)
            (root / "src").mkdir()
            (root / "src/user_service.py").write_text("pass\n", encoding="utf-8")

            errors, _ = validator.validate_traceability_entries(
                trace_map=trace_map,
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
            any(
                "recommended_route" in error and "IMPLEMENTATION" in error
                for error in errors
            )
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

    def test_orphan_implementation_is_policy_failure(self) -> None:
        issue = {
            "classification": "ORPHAN_IMPLEMENTATION",
            "severity": "LOW",
            "resolved": False,
        }
        self.assertTrue(
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
            (reports / "traceability-report.md").write_text(
                "# report\n",
                encoding="utf-8",
            )

            errors = validator.validate_required_reports(
                reports,
                base_policy(),
            )

        self.assertTrue(
            any("trace-map.json" in error for error in errors)
        )

    def test_all_required_reports_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            reports = Path(temp)
            for name in (
                "ast-index.json",
                "trace-map.json",
                "traceability-report.json",
                "traceability-report.md",
            ):
                (reports / name).write_text(
                    "{}" if name.endswith(".json") else "# report\n",
                    encoding="utf-8",
                )

            errors = validator.validate_required_reports(
                reports,
                base_policy(),
            )

        self.assertEqual([], errors)


class EndToEndValidateTest(unittest.TestCase):

    def test_full_valid_repository_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)

            requirements_dir = root / "docs/requirements"
            features_dir = requirements_dir / "features"
            adr_dir = root / "docs/adr"
            src_dir = root / "src"
            tests_dir = root / "tests"
            unit_report_dir = root / "reports/unit-test"
            integration_report_dir = root / "reports/integration-test"
            trace_report_dir = root / "reports/traceability"
            policy_dir = root / ".github/skills/traceability-audit/policy"

            for directory in (
                requirements_dir,
                features_dir,
                adr_dir,
                src_dir,
                tests_dir,
                unit_report_dir,
                integration_report_dir,
                trace_report_dir,
                policy_dir,
            ):
                directory.mkdir(parents=True, exist_ok=True)

            (requirements_dir / "requirements.md").write_text(
                "# Requirements\n\nFR-001\n",
                encoding="utf-8",
            )

            (adr_dir / "ADR-001-test.md").write_text(
                "# ADR-001\n\n"
                "## Status\n\n"
                "Accepted\n\n"
                "## Related Requirements\n\n"
                "- FR-001\n",
                encoding="utf-8",
            )

            (src_dir / "user_service.py").write_text(
                "def register_user():\n    return True\n",
                encoding="utf-8",
            )
            (tests_dir / "test_user_service.py").write_text(
                "from src.user_service import register_user\n\n"
                "def test_register_user():\n"
                "    result = register_user()\n"
                "    assert result is True\n",
                encoding="utf-8",
            )

            (unit_report_dir / "unit-test-evidence.json").write_text(
                json.dumps(unit_evidence()),
                encoding="utf-8",
            )
            (unit_report_dir / "validation-result.json").write_text(
                json.dumps({"status": "PASS"}),
                encoding="utf-8",
            )

            (integration_report_dir / "integration-test-plan.json").write_text(
                json.dumps(integration_plan()),
                encoding="utf-8",
            )
            (integration_report_dir / "integration-test-evidence.json").write_text(
                json.dumps(integration_evidence()),
                encoding="utf-8",
            )
            (integration_report_dir / "validation-result.json").write_text(
                json.dumps({"status": "PASS"}),
                encoding="utf-8",
            )

            ast_index = validator.analyze_repository(
                root,
                base_policy(),
                SCRIPT_DIR,
            )
            (trace_report_dir / "ast-index.json").write_text(
                json.dumps(ast_index),
                encoding="utf-8",
            )

            trace_map = base_trace_map()
            trace_map["ast_index"]["source_fingerprint"] = ast_index["source_fingerprint"]
            report = base_report()

            (trace_report_dir / "trace-map.json").write_text(
                json.dumps(trace_map),
                encoding="utf-8",
            )
            (trace_report_dir / "traceability-report.json").write_text(
                json.dumps(report),
                encoding="utf-8",
            )
            (trace_report_dir / "traceability-report.md").write_text(
                "# Traceability Report\n",
                encoding="utf-8",
            )

            policy_path = policy_dir / "traceability-policy.yaml"
            policy_path.write_text(
                yaml.safe_dump(
                    base_policy(),
                    allow_unicode=True,
                    sort_keys=False,
                ),
                encoding="utf-8",
            )

            errors, result = validator.validate(
                repo_root=root,
                policy_path=policy_path,
                requirements_file=requirements_dir / "requirements.md",
                features_dir=features_dir,
                adr_dir=adr_dir,
                ast_index_path=trace_report_dir / "ast-index.json",
                trace_map_path=trace_report_dir / "trace-map.json",
                report_path=trace_report_dir / "traceability-report.json",
                reports_dir=trace_report_dir,
                unit_evidence_path=unit_report_dir / "unit-test-evidence.json",
                unit_validation_path=unit_report_dir / "validation-result.json",
                integration_plan_path=integration_report_dir / "integration-test-plan.json",
                integration_evidence_path=integration_report_dir / "integration-test-evidence.json",
                integration_validation_path=integration_report_dir / "validation-result.json",
            )

        self.assertEqual([], errors)
        self.assertEqual("PASS", result["status"])
        self.assertEqual(1, result["discovered"]["current_scope_adrs"])


class AstIndexValidationTest(unittest.TestCase):

    def test_ast_index_reference_passes(self) -> None:
        trace_map = base_trace_map()
        ast_index = {
            "version": 1,
            "source_fingerprint": "TEST-FINGERPRINT",
        }
        self.assertEqual(
            [],
            validator.validate_ast_index_reference(
                trace_map,
                ast_index,
                base_policy(),
            ),
        )

    def test_ast_index_fingerprint_mismatch_fails(self) -> None:
        trace_map = base_trace_map()
        ast_index = {
            "version": 1,
            "source_fingerprint": "DIFFERENT",
        }
        errors = validator.validate_ast_index_reference(
            trace_map,
            ast_index,
            base_policy(),
        )
        self.assertTrue(any("fingerprint" in error.lower() for error in errors))

    def test_stale_ast_index_fails(self) -> None:
        policy = base_policy()
        current = {
            "version": 1,
            "source_fingerprint": "CURRENT",
            "source_files": [],
            "production_roots": ["src", "app"],
            "test_roots": ["tests", "test", "src/test"],
            "test_file_patterns": [],
            "analyzers": {},
            "production_symbols": [],
            "test_symbols": [],
            "test_files": [],
        }
        stale = dict(current)
        stale["source_fingerprint"] = "OLD"
        errors = validator.validate_ast_index_freshness(
            stale,
            current,
            policy,
            "FULL",
        )
        self.assertTrue(any("stale" in error.lower() for error in errors))


class AstTraceabilityPhaseTest(unittest.TestCase):

    def _repo(self, *, call_impl: bool = True, assertion: bool = True) -> tuple[tempfile.TemporaryDirectory[str], Path, dict[str, Any]]:
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        (root / "src").mkdir()
        (root / "tests").mkdir()
        (root / "src/user_service.py").write_text(
            "def helper():\n"
            "    return True\n\n"
            "def register_user():\n"
            "    return helper()\n\n"
            "def orphan_public():\n"
            "    return False\n",
            encoding="utf-8",
        )
        body = "    result = register_user()\n" if call_impl else "    result = True\n"
        if assertion:
            body += "    assert result is True\n"
        (root / "tests/test_user_service.py").write_text(
            "from src.user_service import register_user\n\n"
            "def test_register_user():\n" + body,
            encoding="utf-8",
        )
        index = validator.analyze_repository(root, base_policy(), SCRIPT_DIR)
        return temp, root, index

    def _trace_map(self, index: dict[str, Any], *, include_orphan: bool = True) -> dict[str, Any]:
        trace_map = base_trace_map()
        trace_map["ast_index"]["source_fingerprint"] = index["source_fingerprint"]
        implementation = [
            {
                "file": "src/user_service.py",
                "symbol": "register_user",
                "qualified_name": "src.user_service.register_user",
            },
            {
                "file": "src/user_service.py",
                "symbol": "helper",
                "qualified_name": "src.user_service.helper",
            },
        ]
        if include_orphan:
            implementation.append(
                {
                    "file": "src/user_service.py",
                    "symbol": "orphan_public",
                    "qualified_name": "src.user_service.orphan_public",
                }
            )
        trace_map["entries"][0]["implementation"] = implementation
        trace_map["entries"][0]["unit_tests"] = [
            {
                "test_id": "test_register_user",
                "file": "tests/test_user_service.py",
                "symbol": "test_register_user",
                "qualified_name": "tests.test_user_service.test_register_user",
                "implementation_targets": [
                    "src.user_service.helper",
                    "src.user_service.register_user",
                ],
                "assertion_count": 1,
            }
        ]
        return trace_map

    def test_phase2_valid_symbol_and_qualified_name_pass(self) -> None:
        temp, root, index = self._repo()
        try:
            mapping = {
                "file": "src/user_service.py",
                "symbol": "register_user",
                "qualified_name": "src.user_service.register_user",
            }
            errors = validator.validate_symbol_mapping(
                mapping,
                index,
                base_policy(),
                "FR-001",
                tests=False,
            )
        finally:
            temp.cleanup()
        self.assertEqual([], errors)

    def test_phase2_missing_symbol_fails(self) -> None:
        temp, root, index = self._repo()
        try:
            mapping = {
                "file": "src/user_service.py",
                "qualified_name": "src.user_service.register_user",
            }
            errors = validator.validate_symbol_mapping(
                mapping,
                index,
                base_policy(),
                "FR-001",
                tests=False,
            )
        finally:
            temp.cleanup()
        self.assertTrue(any("requires symbol" in error for error in errors))

    def test_phase2_nonexistent_qualified_name_fails(self) -> None:
        temp, root, index = self._repo()
        try:
            mapping = {
                "file": "src/user_service.py",
                "symbol": "register_user",
                "qualified_name": "src.user_service.missing",
            }
            errors = validator.validate_symbol_mapping(
                mapping,
                index,
                base_policy(),
                "FR-001",
                tests=False,
            )
        finally:
            temp.cleanup()
        self.assertTrue(any("qualified_name does not exist" in error for error in errors))

    def test_phase3_orphan_implementation_fails(self) -> None:
        temp, root, index = self._repo()
        try:
            trace_map = self._trace_map(index, include_orphan=False)
            errors, orphans = validator.validate_orphan_implementations(
                trace_map,
                index,
                base_policy(),
                "FULL",
            )
        finally:
            temp.cleanup()
        self.assertEqual(["src.user_service.orphan_public"], [item["qualified_name"] for item in orphans])
        self.assertTrue(any("Orphan implementation symbol" in error for error in errors))

    def test_phase4_direct_code_test_edge_passes(self) -> None:
        temp, root, index = self._repo()
        try:
            trace_map = self._trace_map(index)
            errors, metrics = validator.validate_code_test_traceability(
                trace_map,
                index,
                base_policy(),
                "FULL",
            )
        finally:
            temp.cleanup()
        self.assertEqual([], errors)
        self.assertEqual(1, metrics["tests_with_implementation_call"])
        self.assertEqual(1, metrics["tests_with_assertion"])

    def test_phase4_missing_implementation_call_fails(self) -> None:
        temp, root, index = self._repo(call_impl=False)
        try:
            trace_map = self._trace_map(index)
            errors, _ = validator.validate_code_test_traceability(
                trace_map,
                index,
                base_policy(),
                "FULL",
            )
        finally:
            temp.cleanup()
        self.assertTrue(any("does not call mapped Implementation" in error for error in errors))

    def test_phase4_missing_assertion_fails(self) -> None:
        temp, root, index = self._repo(assertion=False)
        try:
            trace_map = self._trace_map(index)
            trace_map["entries"][0]["unit_tests"][0]["assertion_count"] = 0
            errors, _ = validator.validate_code_test_traceability(
                trace_map,
                index,
                base_policy(),
                "FULL",
            )
        finally:
            temp.cleanup()
        self.assertTrue(any("no AST-detected assertion" in error for error in errors))

    def test_phase4_trace_map_target_mismatch_fails(self) -> None:
        temp, root, index = self._repo()
        try:
            trace_map = self._trace_map(index)
            trace_map["entries"][0]["unit_tests"][0]["implementation_targets"] = [
                "src.user_service.helper"
            ]
            errors, _ = validator.validate_code_test_traceability(
                trace_map,
                index,
                base_policy(),
                "FULL",
            )
        finally:
            temp.cleanup()
        self.assertTrue(any("implementation_targets do not match AST" in error for error in errors))


if __name__ == "__main__":
    unittest.main(verbosity=2)
