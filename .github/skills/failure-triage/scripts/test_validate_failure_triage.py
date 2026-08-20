#!/usr/bin/env python3
"""
Unit tests for validate_failure_triage.py

Run:
    python .github/skills/failure-triage/scripts/test_validate_failure_triage.py

No third-party test framework is required.
PyYAML is required because validate_failure_triage.py imports yaml.
"""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
VALIDATOR_PATH = SCRIPT_DIR / "validate_failure_triage.py"

SPEC = importlib.util.spec_from_file_location(
    "validate_failure_triage",
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
        "version": 1,
        "invocation": {
            "retry_threshold": 3,
            "require_same_failure": True,
            "direct_user_gate_failures": [
                "EXTERNAL_TEST_INPUT_REQUIRED",
                "TEST_SPEC_CONFLICT",
                "AUTOMATION_BLOCKED",
            ],
            "allow_triage_below_threshold": False,
        },
        "failure_signature": {
            "fields": [
                "source_phase",
                "classification",
                "requirement_reference",
                "artifact",
                "error_location",
                "test_case",
                "stable_error_type",
            ],
            "ignore_dynamic_values": [
                "timestamp",
                "request_id",
                "trace_id",
                "random_id",
                "temporary_file_name",
            ],
        },
        "history": {
            "require_failure_history": True,
            "require_previous_routes": True,
            "require_previous_changes": True,
            "require_retry_results": True,
        },
        "analysis": {
            "require_expected_behavior": True,
            "require_actual_behavior": True,
            "require_previous_attempt_analysis": True,
            "require_root_cause_evidence": True,
            "root_cause_priority": [
                "REQUIREMENTS",
                "ARCHITECTURE",
                "IMPLEMENTATION",
                "UNIT_TEST",
                "INTEGRATION_TEST",
                "ENVIRONMENT",
            ],
        },
        "classification": {
            "allowed": [
                "REQUIREMENT_ERROR",
                "ADR_REQUIRED",
                "IMPLEMENTATION_ERROR",
                "TEST_ERROR",
                "ENVIRONMENT_ERROR",
                "CROSS_PHASE_CONFLICT",
                "UNKNOWN_ROOT_CAUSE",
            ],
        },
        "routing": {
            "REQUIREMENT_ERROR": "REQUIREMENTS",
            "ADR_REQUIRED": "ARCHITECTURE",
            "IMPLEMENTATION_ERROR": "IMPLEMENTATION",
            "TEST_ERROR": "ROOT_CAUSE",
            "ENVIRONMENT_ERROR": "SDLC_ORCHESTRATOR",
            "CROSS_PHASE_CONFLICT": "ROOT_CAUSE",
            "UNKNOWN_ROOT_CAUSE": "BLOCKED",
        },
        "routes": {
            "allowed": [
                "REQUIREMENTS",
                "ARCHITECTURE",
                "IMPLEMENTATION",
                "UNIT_TEST",
                "INTEGRATION_TEST",
                "SDLC_ORCHESTRATOR",
                "BLOCKED",
            ],
        },
        "invalidation": {
            "REQUIREMENTS": [
                "ARCHITECTURE",
                "IMPLEMENTATION",
                "UNIT_TEST",
                "INTEGRATION_TEST",
            ],
            "ARCHITECTURE": [
                "IMPLEMENTATION",
                "UNIT_TEST",
                "INTEGRATION_TEST",
            ],
            "IMPLEMENTATION": [
                "UNIT_TEST",
                "INTEGRATION_TEST",
            ],
            "UNIT_TEST": [
                "UNIT_TEST",
            ],
            "INTEGRATION_TEST": [
                "INTEGRATION_TEST",
            ],
            "SDLC_ORCHESTRATOR": [],
            "BLOCKED": [],
        },
        "modification": {
            "allow_requirement_change": False,
            "allow_adr_change": False,
            "allow_production_code_change": False,
            "allow_test_code_change": False,
            "allow_environment_change": False,
            "allow_external_test_case_change": False,
        },
        "agent_invocation": {
            "allow_direct_subagent_invocation": False,
        },
        "evidence": {
            "require_failure_history": True,
            "require_source_artifact": True,
            "require_expected_behavior": True,
            "require_actual_behavior": True,
            "require_previous_attempts": True,
            "require_root_cause_reason": True,
        },
        "result": {
            "allowed_status": [
                "TRIAGED",
                "BLOCKED",
                "INVALID_INVOCATION",
            ],
        },
        "reports": {
            "directory": "reports/failure-triage",
            "required": [
                "failure-triage-report.json",
                "failure-triage-report.md",
            ],
        },
    }


def previous_attempts() -> list[dict[str, Any]]:
    return [
        {
            "attempt": 1,
            "route": "IMPLEMENTATION",
            "changed_artifacts": [
                "src/user_service.py",
            ],
            "result": "FAILED_SAME_ROOT_CAUSE",
        },
        {
            "attempt": 2,
            "route": "IMPLEMENTATION",
            "changed_artifacts": [
                "src/user_service.py",
            ],
            "result": "FAILED_SAME_ROOT_CAUSE",
        },
        {
            "attempt": 3,
            "route": "IMPLEMENTATION",
            "changed_artifacts": [
                "src/user_service.py",
            ],
            "result": "FAILED_SAME_ROOT_CAUSE",
        },
    ]


def valid_evidence() -> list[dict[str, str]]:
    return [
        {
            "source": "Source Artifact",
            "detail": "src/user_service.py / register_user",
        },
        {
            "source": "Expected Behavior",
            "detail": "FR-001 requires ACTIVE users only.",
        },
        {
            "source": "Actual Behavior",
            "detail": "Inactive users are accepted.",
        },
        {
            "source": "Previous Attempt Analysis",
            "detail": "Three implementation fixes changed validation branches but not the root condition.",
        },
        {
            "source": "Root Cause",
            "detail": "The production condition does not implement the required state check.",
        },
    ]


def base_triaged_report() -> dict[str, Any]:
    attempts = previous_attempts()

    return {
        "status": "TRIAGED",
        "source_phase": "UNIT_TEST",
        "retry_count": 3,
        "latest_failure": {
            "classification": "IMPLEMENTATION_ERROR",
        },
        "failure_history": attempts,
        "same_failure": {
            "confirmed": True,
            "failure_signature": (
                "UNIT_TEST|IMPLEMENTATION_ERROR|FR-001|"
                "UserService|registerUser|UserServiceTest|AssertionError"
            ),
            "reason": "The same requirement, code path and failing behavior persisted across all retries.",
        },
        "classification": "IMPLEMENTATION_ERROR",
        "root_cause": "Production code does not enforce the required ACTIVE state condition.",
        "evidence": valid_evidence(),
        "previous_attempts": attempts,
        "recommended_route": "IMPLEMENTATION",
        "recommended_action": (
            "Re-check the implementation against FR-001 and the Accepted ADR, "
            "then rerun Unit Test and Integration Test."
        ),
        "invalidated_phases": [
            "UNIT_TEST",
            "INTEGRATION_TEST",
        ],
        "modifications_performed": [],
        "direct_agent_invocations": [],
        "reports": {
            "json": "reports/failure-triage/failure-triage-report.json",
            "markdown": "reports/failure-triage/failure-triage-report.md",
        },
        "summary_message": "Root cause triaged to Implementation.",
    }


def base_blocked_report() -> dict[str, Any]:
    report = base_triaged_report()
    report.update(
        {
            "status": "BLOCKED",
            "classification": "UNKNOWN_ROOT_CAUSE",
            "root_cause": "Available evidence is insufficient to distinguish requirement, environment, and implementation causes.",
            "recommended_route": "BLOCKED",
            "recommended_action": "Collect additional failure evidence before any further modification.",
            "invalidated_phases": [],
        }
    )
    return report


def base_invalid_invocation_report() -> dict[str, Any]:
    return {
        "status": "INVALID_INVOCATION",
        "source_phase": "UNIT_TEST",
        "retry_count": 2,
        "latest_failure": {
            "classification": "IMPLEMENTATION_ERROR",
        },
        "same_failure": {
            "confirmed": True,
            "failure_signature": "UNIT_TEST|IMPLEMENTATION_ERROR|FR-001",
            "reason": "Same failure, but retry threshold has not been reached.",
        },
        "classification": "",
        "root_cause": "",
        "evidence": [],
        "previous_attempts": [],
        "recommended_route": "",
        "recommended_action": "",
        "invalidated_phases": [],
        "modifications_performed": [],
        "direct_agent_invocations": [],
    }


class PolicyTest(unittest.TestCase):

    def test_valid_policy_passes(self) -> None:
        self.assertEqual(
            [],
            validator.validate_policy(
                base_policy()
            ),
        )

    def test_invalid_retry_threshold_fails(self) -> None:
        policy = base_policy()
        policy["invocation"]["retry_threshold"] = 0

        errors = validator.validate_policy(policy)

        self.assertTrue(
            any(
                "retry_threshold" in error
                for error in errors
            )
        )

    def test_missing_classification_route_fails(self) -> None:
        policy = base_policy()
        del policy["routing"]["IMPLEMENTATION_ERROR"]

        errors = validator.validate_policy(policy)

        self.assertTrue(
            any(
                "routing missing" in error
                and "IMPLEMENTATION_ERROR" in error
                for error in errors
            )
        )

    def test_unknown_allowed_route_fails(self) -> None:
        policy = base_policy()
        policy["routes"]["allowed"].append("UNKNOWN_PHASE")

        errors = validator.validate_policy(policy)

        self.assertTrue(
            any(
                "unknown allowed route" in error
                for error in errors
            )
        )

    def test_unknown_result_status_fails(self) -> None:
        policy = base_policy()
        policy["result"]["allowed_status"].append("SUCCESS")

        errors = validator.validate_policy(policy)

        self.assertTrue(
            any(
                "unknown result status" in error
                for error in errors
            )
        )


class HeaderTest(unittest.TestCase):

    def test_valid_header_passes(self) -> None:
        errors, status, retry_count = validator.validate_header(
            base_triaged_report(),
            base_policy(),
        )

        self.assertEqual([], errors)
        self.assertEqual("TRIAGED", status)
        self.assertEqual(3, retry_count)

    def test_invalid_source_phase_fails(self) -> None:
        report = base_triaged_report()
        report["source_phase"] = "UNKNOWN"

        errors, _, _ = validator.validate_header(
            report,
            base_policy(),
        )

        self.assertTrue(
            any(
                "source_phase" in error
                for error in errors
            )
        )

    def test_negative_retry_count_fails(self) -> None:
        report = base_triaged_report()
        report["retry_count"] = -1

        errors, _, _ = validator.validate_header(
            report,
            base_policy(),
        )

        self.assertTrue(
            any(
                "retry_count" in error
                for error in errors
            )
        )


class InvocationTest(unittest.TestCase):

    def test_threshold_reached_triaged_is_valid(self) -> None:
        report = base_triaged_report()

        errors = validator.validate_invocation(
            report,
            base_policy(),
            "TRIAGED",
            3,
        )

        self.assertEqual([], errors)

    def test_below_threshold_must_be_invalid_invocation(self) -> None:
        report = base_triaged_report()
        report["retry_count"] = 2

        errors = validator.validate_invocation(
            report,
            base_policy(),
            "TRIAGED",
            2,
        )

        self.assertTrue(
            any(
                "below retry_threshold" in error
                for error in errors
            )
        )

    def test_below_threshold_invalid_invocation_passes(self) -> None:
        report = base_invalid_invocation_report()

        errors = validator.validate_invocation(
            report,
            base_policy(),
            "INVALID_INVOCATION",
            2,
        )

        self.assertEqual([], errors)

    def test_external_input_required_must_be_invalid_invocation(self) -> None:
        report = base_triaged_report()
        report["latest_failure"] = {
            "classification": "EXTERNAL_TEST_INPUT_REQUIRED",
        }

        errors = validator.validate_invocation(
            report,
            base_policy(),
            "TRIAGED",
            3,
        )

        self.assertTrue(
            any(
                "Direct user gate failure" in error
                for error in errors
            )
        )

    def test_test_spec_conflict_invalid_invocation_passes(self) -> None:
        report = base_invalid_invocation_report()
        report["retry_count"] = 3
        report["latest_failure"] = {
            "classification": "TEST_SPEC_CONFLICT",
        }

        errors = validator.validate_invocation(
            report,
            base_policy(),
            "INVALID_INVOCATION",
            3,
        )

        self.assertEqual([], errors)

    def test_invalid_invocation_rejected_when_conditions_are_satisfied(self) -> None:
        report = base_invalid_invocation_report()
        report["retry_count"] = 3
        report["latest_failure"] = {
            "classification": "IMPLEMENTATION_ERROR",
        }

        errors = validator.validate_invocation(
            report,
            base_policy(),
            "INVALID_INVOCATION",
            3,
        )

        self.assertTrue(
            any(
                "conditions are satisfied" in error
                for error in errors
            )
        )


class SameFailureTest(unittest.TestCase):

    def test_confirmed_same_failure_passes(self) -> None:
        self.assertEqual(
            [],
            validator.validate_same_failure(
                base_triaged_report(),
                base_policy(),
                "TRIAGED",
            ),
        )

    def test_triaged_requires_same_failure_confirmation(self) -> None:
        report = base_triaged_report()
        report["same_failure"]["confirmed"] = False

        errors = validator.validate_same_failure(
            report,
            base_policy(),
            "TRIAGED",
        )

        self.assertTrue(
            any(
                "confirmed=true" in error
                for error in errors
            )
        )

    def test_triaged_requires_failure_signature(self) -> None:
        report = base_triaged_report()
        report["same_failure"]["failure_signature"] = ""

        errors = validator.validate_same_failure(
            report,
            base_policy(),
            "TRIAGED",
        )

        self.assertTrue(
            any(
                "failure_signature" in error
                for error in errors
            )
        )


class HistoryTest(unittest.TestCase):

    def test_valid_history_passes(self) -> None:
        errors, count = validator.validate_history(
            base_triaged_report(),
            base_policy(),
            "TRIAGED",
        )

        self.assertEqual([], errors)
        self.assertEqual(3, count)

    def test_missing_previous_attempts_fails(self) -> None:
        report = base_triaged_report()
        report["previous_attempts"] = []
        report["failure_history"] = []

        errors, _ = validator.validate_history(
            report,
            base_policy(),
            "TRIAGED",
        )

        self.assertTrue(
            any(
                "failure_history is required" in error
                for error in errors
            )
        )
        self.assertTrue(
            any(
                "previous_attempts is required" in error
                for error in errors
            )
        )

    def test_attempt_requires_changed_artifacts(self) -> None:
        report = base_triaged_report()
        report["previous_attempts"][0]["changed_artifacts"] = []

        errors, _ = validator.validate_history(
            report,
            base_policy(),
            "TRIAGED",
        )

        self.assertTrue(
            any(
                "changed_artifacts is required" in error
                for error in errors
            )
        )

    def test_attempt_requires_retry_result(self) -> None:
        report = base_triaged_report()
        report["previous_attempts"][0]["result"] = ""

        errors, _ = validator.validate_history(
            report,
            base_policy(),
            "TRIAGED",
        )

        self.assertTrue(
            any(
                "result is required" in error
                for error in errors
            )
        )


class ClassificationRoutingTest(unittest.TestCase):

    def test_implementation_error_routes_to_implementation(self) -> None:
        errors = validator.validate_classification_and_route(
            base_triaged_report(),
            base_policy(),
            "TRIAGED",
        )

        self.assertEqual([], errors)

    def test_fixed_route_mismatch_fails(self) -> None:
        report = base_triaged_report()
        report["recommended_route"] = "UNIT_TEST"

        errors = validator.validate_classification_and_route(
            report,
            base_policy(),
            "TRIAGED",
        )

        self.assertTrue(
            any(
                "!= policy route" in error
                for error in errors
            )
        )

    def test_test_error_requires_concrete_test_phase(self) -> None:
        report = base_triaged_report()
        report["classification"] = "TEST_ERROR"
        report["recommended_route"] = "UNIT_TEST"

        errors = validator.validate_classification_and_route(
            report,
            base_policy(),
            "TRIAGED",
        )

        self.assertEqual([], errors)

    def test_root_cause_route_cannot_be_blocked_for_triaged(self) -> None:
        report = base_triaged_report()
        report["classification"] = "TEST_ERROR"
        report["recommended_route"] = "BLOCKED"

        errors = validator.validate_classification_and_route(
            report,
            base_policy(),
            "TRIAGED",
        )

        self.assertTrue(
            any(
                "concrete SDLC phase" in error
                for error in errors
            )
        )

    def test_blocked_requires_blocked_route(self) -> None:
        report = base_blocked_report()
        report["recommended_route"] = "IMPLEMENTATION"

        errors = validator.validate_classification_and_route(
            report,
            base_policy(),
            "BLOCKED",
        )

        self.assertTrue(
            any(
                "recommended_route=BLOCKED" in error
                for error in errors
            )
        )


class EvidenceTest(unittest.TestCase):

    def test_valid_evidence_passes(self) -> None:
        errors = validator.validate_evidence(
            base_triaged_report(),
            base_policy(),
            "TRIAGED",
        )

        self.assertEqual([], errors)

    def test_root_cause_is_required(self) -> None:
        report = base_triaged_report()
        report["root_cause"] = ""

        errors = validator.validate_evidence(
            report,
            base_policy(),
            "TRIAGED",
        )

        self.assertTrue(
            any(
                "root_cause is required" in error
                for error in errors
            )
        )

    def test_expected_behavior_evidence_is_required(self) -> None:
        report = base_triaged_report()
        report["evidence"] = [
            item
            for item in report["evidence"]
            if item["source"] != "Expected Behavior"
        ]

        errors = validator.validate_evidence(
            report,
            base_policy(),
            "TRIAGED",
        )

        self.assertTrue(
            any(
                "Expected Behavior evidence" in error
                for error in errors
            )
        )

    def test_actual_behavior_evidence_is_required(self) -> None:
        report = base_triaged_report()
        report["evidence"] = [
            item
            for item in report["evidence"]
            if item["source"] != "Actual Behavior"
        ]

        errors = validator.validate_evidence(
            report,
            base_policy(),
            "TRIAGED",
        )

        self.assertTrue(
            any(
                "Actual Behavior evidence" in error
                for error in errors
            )
        )

    def test_source_artifact_evidence_is_required(self) -> None:
        report = base_triaged_report()
        report["evidence"] = [
            item
            for item in report["evidence"]
            if item["source"] != "Source Artifact"
        ]

        errors = validator.validate_evidence(
            report,
            base_policy(),
            "TRIAGED",
        )

        self.assertTrue(
            any(
                "Source Artifact" in error
                for error in errors
            )
        )

    def test_previous_attempt_analysis_evidence_is_required(self) -> None:
        report = base_triaged_report()
        report["evidence"] = [
            item
            for item in report["evidence"]
            if item["source"] not in {
                "Previous Attempt Analysis",
                "Root Cause",
            }
        ]

        errors = validator.validate_evidence(
            report,
            base_policy(),
            "TRIAGED",
        )

        self.assertTrue(
            any(
                "Previous attempt analysis evidence" in error
                for error in errors
            )
        )


class InvalidationTest(unittest.TestCase):

    def test_implementation_route_invalidation_passes(self) -> None:
        self.assertEqual(
            [],
            validator.validate_invalidated_phases(
                base_triaged_report(),
                base_policy(),
                "TRIAGED",
            ),
        )

    def test_invalidation_mismatch_fails(self) -> None:
        report = base_triaged_report()
        report["invalidated_phases"] = [
            "UNIT_TEST",
        ]

        errors = validator.validate_invalidated_phases(
            report,
            base_policy(),
            "TRIAGED",
        )

        self.assertTrue(
            any(
                "does not match policy" in error
                for error in errors
            )
        )

    def test_requirements_route_requires_all_downstream_invalidation(self) -> None:
        report = base_triaged_report()
        report["classification"] = "REQUIREMENT_ERROR"
        report["recommended_route"] = "REQUIREMENTS"
        report["invalidated_phases"] = [
            "ARCHITECTURE",
            "IMPLEMENTATION",
            "UNIT_TEST",
            "INTEGRATION_TEST",
        ]

        errors = validator.validate_invalidated_phases(
            report,
            base_policy(),
            "TRIAGED",
        )

        self.assertEqual([], errors)

    def test_unknown_invalidated_phase_fails(self) -> None:
        report = base_triaged_report()
        report["invalidated_phases"] = [
            "UNIT_TEST",
            "INTEGRATION_TEST",
            "UNKNOWN",
        ]

        errors = validator.validate_invalidated_phases(
            report,
            base_policy(),
            "TRIAGED",
        )

        self.assertTrue(
            any(
                "unknown phase" in error
                for error in errors
            )
        )


class ProhibitedActionTest(unittest.TestCase):

    def test_no_modification_and_no_direct_invocation_passes(self) -> None:
        self.assertEqual(
            [],
            validator.validate_no_prohibited_actions(
                base_triaged_report(),
                base_policy(),
            ),
        )

    def test_artifact_modification_fails(self) -> None:
        report = base_triaged_report()
        report["modifications_performed"] = [
            "src/user_service.py",
        ]

        errors = validator.validate_no_prohibited_actions(
            report,
            base_policy(),
        )

        self.assertTrue(
            any(
                "must not modify artifacts" in error
                for error in errors
            )
        )

    def test_direct_subagent_invocation_fails(self) -> None:
        report = base_triaged_report()
        report["direct_agent_invocations"] = [
            "Implementation",
        ]

        errors = validator.validate_no_prohibited_actions(
            report,
            base_policy(),
        )

        self.assertTrue(
            any(
                "must not invoke subagents directly" in error
                for error in errors
            )
        )


class StatusConsistencyTest(unittest.TestCase):

    def test_triaged_requires_recommended_action(self) -> None:
        report = base_triaged_report()
        report["recommended_action"] = ""

        errors = validator.validate_status_consistency(
            report,
            "TRIAGED",
            [],
        )

        self.assertTrue(
            any(
                "TRIAGED requires recommended_action" in error
                for error in errors
            )
        )

    def test_blocked_requires_explanation(self) -> None:
        report = base_blocked_report()
        report["recommended_action"] = ""

        errors = validator.validate_status_consistency(
            report,
            "BLOCKED",
            [],
        )

        self.assertTrue(
            any(
                "BLOCKED requires recommended_action" in error
                for error in errors
            )
        )

    def test_triaged_with_deterministic_errors_fails(self) -> None:
        errors = validator.validate_status_consistency(
            base_triaged_report(),
            "TRIAGED",
            [
                "routing mismatch",
            ],
        )

        self.assertTrue(
            any(
                "deterministic validation errors" in error
                for error in errors
            )
        )


class RequiredReportTest(unittest.TestCase):

    def test_missing_markdown_report_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            reports = Path(temp)

            (
                reports
                / "failure-triage-report.json"
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
                "failure-triage-report.md" in error
                for error in errors
            )
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
