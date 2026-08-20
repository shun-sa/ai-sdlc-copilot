#!/usr/bin/env python3
"""
Failure Triage Validator

Failure Triage Agentが生成したReportを、
failure-triage-policy.yaml と照合し、
診断結果の構造・Invocation条件・Routing・Invalidation整合を
決定論的に検証する。

Checks:
- Policy structure
- Allowed result status
- Retry threshold
- Same Failure confirmation
- Direct user gate failure exclusion
- Failure history presence
- Previous routes / changes / retry results
- Failure signature
- Root cause classification
- Recommended route
- Invalidated phases
- Required evidence
- Required reports
- Report summary consistency
- INVALID_INVOCATION / BLOCKED / TRIAGED consistency

Exit Code:
    0: PASS
    1: FAIL

Dependency:
    PyYAML

Notes:
- Root Causeの意味的妥当性はFailure Triage Agentが診断する。
- 本Validatorは、その診断結果がPolicy・Routing・Retry Rule・
  Invalidation Ruleと整合しているかを機械検証する。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml


VALID_PHASES = {
    "REQUIREMENTS",
    "ARCHITECTURE",
    "IMPLEMENTATION",
    "UNIT_TEST",
    "INTEGRATION_TEST",
    "SDLC_ORCHESTRATOR",
    "BLOCKED",
}

VALID_RESULT_STATUS = {
    "TRIAGED",
    "BLOCKED",
    "INVALID_INVOCATION",
}


# ============================================================
# Utility
# ============================================================


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be an object: {path}")

    return data


def read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    with path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file)

    if not isinstance(data, dict):
        raise ValueError(f"YAML root must be a mapping: {path}")

    return data


def nested_get(
    source: dict[str, Any],
    keys: list[str],
    default: Any = None,
) -> Any:
    current: Any = source

    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return default

        current = current[key]

    return current


def non_empty(value: Any) -> bool:
    if value is None:
        return False

    if isinstance(value, str):
        return bool(value.strip())

    if isinstance(value, (list, dict, tuple, set)):
        return len(value) > 0

    return True


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []

    if isinstance(value, list):
        return value

    return [value]


def as_string_list(value: Any) -> list[str]:
    return [
        str(item).strip()
        for item in as_list(value)
        if str(item).strip()
    ]


def write_result(path: Path, result: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


# ============================================================
# Policy
# ============================================================


def validate_policy(policy: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    required_paths = [
        ["invocation", "retry_threshold"],
        ["invocation", "require_same_failure"],
        ["invocation", "direct_user_gate_failures"],
        ["invocation", "allow_triage_below_threshold"],
        ["failure_signature", "fields"],
        ["failure_signature", "ignore_dynamic_values"],
        ["history", "require_failure_history"],
        ["history", "require_previous_routes"],
        ["history", "require_previous_changes"],
        ["history", "require_retry_results"],
        ["analysis", "require_expected_behavior"],
        ["analysis", "require_actual_behavior"],
        ["analysis", "require_previous_attempt_analysis"],
        ["analysis", "require_root_cause_evidence"],
        ["analysis", "root_cause_priority"],
        ["classification", "allowed"],
        ["routing"],
        ["routes", "allowed"],
        ["invalidation"],
        ["modification", "allow_requirement_change"],
        ["modification", "allow_adr_change"],
        ["modification", "allow_production_code_change"],
        ["modification", "allow_test_code_change"],
        ["modification", "allow_environment_change"],
        ["modification", "allow_external_test_case_change"],
        ["agent_invocation", "allow_direct_subagent_invocation"],
        ["evidence", "require_failure_history"],
        ["evidence", "require_source_artifact"],
        ["evidence", "require_expected_behavior"],
        ["evidence", "require_actual_behavior"],
        ["evidence", "require_previous_attempts"],
        ["evidence", "require_root_cause_reason"],
        ["result", "allowed_status"],
        ["reports", "directory"],
        ["reports", "required"],
    ]

    for keys in required_paths:
        if nested_get(policy, keys, None) is None:
            errors.append(
                "Policy missing required setting: "
                + ".".join(keys)
            )

    threshold = nested_get(
        policy,
        ["invocation", "retry_threshold"],
        None,
    )

    if threshold is not None:
        if not isinstance(threshold, int) or threshold < 1:
            errors.append(
                "invocation.retry_threshold must be an integer >= 1."
            )

    allowed_classifications = set(
        as_string_list(
            nested_get(
                policy,
                ["classification", "allowed"],
                [],
            )
        )
    )

    routing = nested_get(
        policy,
        ["routing"],
        {},
    )

    if not isinstance(routing, dict):
        errors.append(
            "Policy routing must be a mapping."
        )
    else:
        for classification in sorted(
            allowed_classifications
        ):
            if classification not in routing:
                errors.append(
                    "Policy routing missing for classification: "
                    f"{classification}"
                )

    allowed_routes = set(
        as_string_list(
            nested_get(
                policy,
                ["routes", "allowed"],
                [],
            )
        )
    )

    unknown_routes = (
        allowed_routes
        - VALID_PHASES
    )

    if unknown_routes:
        errors.append(
            "Policy contains unknown allowed route(s): "
            + ", ".join(
                sorted(unknown_routes)
            )
        )

    allowed_status = set(
        as_string_list(
            nested_get(
                policy,
                ["result", "allowed_status"],
                [],
            )
        )
    )

    unknown_status = (
        allowed_status
        - VALID_RESULT_STATUS
    )

    if unknown_status:
        errors.append(
            "Policy contains unknown result status(es): "
            + ", ".join(
                sorted(unknown_status)
            )
        )

    return errors


# ============================================================
# Required Reports
# ============================================================


def validate_required_reports(
    reports_dir: Path,
    policy: dict[str, Any],
) -> list[str]:
    errors: list[str] = []

    for name in as_string_list(
        nested_get(
            policy,
            ["reports", "required"],
            [],
        )
    ):
        path = (
            reports_dir
            / name
        )

        if not path.exists():
            errors.append(
                f"Required report missing: "
                f"{path}"
            )

        elif (
            path.is_file()
            and path.stat().st_size == 0
        ):
            errors.append(
                f"Required report is empty: "
                f"{path}"
            )

    return errors


# ============================================================
# Header / Invocation
# ============================================================


def validate_header(
    report: dict[str, Any],
    policy: dict[str, Any],
) -> tuple[
    list[str],
    str,
    int,
]:
    errors: list[str] = []

    status = str(
        report.get(
            "status",
            "",
        )
    ).upper()

    allowed_status = {
        value.upper()
        for value in as_string_list(
            nested_get(
                policy,
                ["result", "allowed_status"],
                [],
            )
        )
    }

    if status not in allowed_status:
        errors.append(
            f"Invalid or missing status: "
            f"{status!r}"
        )

    source_phase = str(
        report.get(
            "source_phase",
            "",
        )
    ).upper()

    if source_phase not in {
        "REQUIREMENTS",
        "ARCHITECTURE",
        "IMPLEMENTATION",
        "UNIT_TEST",
        "INTEGRATION_TEST",
    }:
        errors.append(
            f"Invalid or missing source_phase: "
            f"{source_phase!r}"
        )

    retry_count = report.get(
        "retry_count"
    )

    if not isinstance(
        retry_count,
        int,
    ) or retry_count < 0:
        errors.append(
            "retry_count must be an integer >= 0."
        )
        retry_count = 0

    return (
        errors,
        status,
        retry_count,
    )


def validate_invocation(
    report: dict[str, Any],
    policy: dict[str, Any],
    status: str,
    retry_count: int,
) -> list[str]:
    errors: list[str] = []

    threshold = int(
        nested_get(
            policy,
            ["invocation", "retry_threshold"],
            3,
        )
    )

    allow_below_threshold = bool(
        nested_get(
            policy,
            [
                "invocation",
                "allow_triage_below_threshold",
            ],
            False,
        )
    )

    latest_failure = report.get(
        "latest_failure",
        {},
    )

    latest_classification = ""

    if isinstance(
        latest_failure,
        dict,
    ):
        latest_classification = str(
            latest_failure.get(
                "classification",
                "",
            )
        ).upper()

    if not latest_classification:
        latest_classification = str(
            report.get(
                "latest_failure_classification",
                "",
            )
        ).upper()

    if not latest_classification:
        latest_classification = str(
            report.get(
                "classification",
                "",
            )
        ).upper()

    direct_user_gate_failures = {
        value.upper()
        for value in as_string_list(
            nested_get(
                policy,
                [
                    "invocation",
                    "direct_user_gate_failures",
                ],
                [],
            )
        )
    }

    excluded_failure = (
        latest_classification
        in direct_user_gate_failures
    )

    below_threshold = (
        retry_count
        < threshold
    )

    invalid_invocation = (
        excluded_failure
        or (
            below_threshold
            and not allow_below_threshold
        )
    )

    if invalid_invocation:
        if status != "INVALID_INVOCATION":
            if excluded_failure:
                errors.append(
                    "Direct user gate failure must result in "
                    "INVALID_INVOCATION."
                )

            if (
                below_threshold
                and not allow_below_threshold
            ):
                errors.append(
                    f"retry_count={retry_count} is below "
                    f"retry_threshold={threshold}; "
                    "status must be INVALID_INVOCATION."
                )

    else:
        if status == "INVALID_INVOCATION":
            errors.append(
                "status is INVALID_INVOCATION but "
                "invocation conditions are satisfied."
            )

    return errors


# ============================================================
# Same Failure
# ============================================================


def validate_same_failure(
    report: dict[str, Any],
    policy: dict[str, Any],
    status: str,
) -> list[str]:
    errors: list[str] = []

    same_failure = report.get(
        "same_failure"
    )

    if not isinstance(
        same_failure,
        dict,
    ):
        return [
            "same_failure must be an object."
        ]

    confirmed = bool(
        same_failure.get(
            "confirmed",
            False,
        )
    )

    require_same = bool(
        nested_get(
            policy,
            [
                "invocation",
                "require_same_failure",
            ],
            True,
        )
    )

    failure_signature = str(
        same_failure.get(
            "failure_signature",
            "",
        )
    ).strip()

    reason = str(
        same_failure.get(
            "reason",
            "",
        )
    ).strip()

    if status == "TRIAGED":
        if require_same and not confirmed:
            errors.append(
                "TRIAGED requires same_failure.confirmed=true."
            )

        if not failure_signature:
            errors.append(
                "TRIAGED requires a failure_signature."
            )

        if not reason:
            errors.append(
                "same_failure.reason is required."
            )

    if status == "INVALID_INVOCATION":
        # Same failure=falseは有効。
        # threshold不足等の場合はtrueでもINVALID_INVOCATIONになりうる。
        pass

    return errors


# ============================================================
# History / Previous Attempts
# ============================================================


def validate_history(
    report: dict[str, Any],
    policy: dict[str, Any],
    status: str,
) -> tuple[
    list[str],
    int,
]:
    errors: list[str] = []

    failure_history = report.get(
        "failure_history"
    )

    if failure_history is None:
        failure_history = report.get(
            "previous_attempts"
        )

    if not isinstance(
        failure_history,
        list,
    ):
        failure_history = []

    if (
        status != "INVALID_INVOCATION"
        and bool(
            nested_get(
                policy,
                [
                    "history",
                    "require_failure_history",
                ],
                True,
            )
        )
        and not failure_history
    ):
        errors.append(
            "failure_history is required."
        )

    previous_attempts = report.get(
        "previous_attempts",
        [],
    )

    if not isinstance(
        previous_attempts,
        list,
    ):
        errors.append(
            "previous_attempts must be an array."
        )
        previous_attempts = []

    if (
        status != "INVALID_INVOCATION"
        and bool(
            nested_get(
                policy,
                [
                    "evidence",
                    "require_previous_attempts",
                ],
                True,
            )
        )
        and not previous_attempts
    ):
        errors.append(
            "previous_attempts is required."
        )

    for index, attempt in enumerate(
        previous_attempts,
        start=1,
    ):
        if not isinstance(
            attempt,
            dict,
        ):
            errors.append(
                f"previous_attempts #{index} "
                "must be an object."
            )
            continue

        if not non_empty(
            attempt.get(
                "attempt"
            )
        ):
            errors.append(
                f"previous_attempts #{index}: "
                "attempt is required."
            )

        if bool(
            nested_get(
                policy,
                [
                    "history",
                    "require_previous_routes",
                ],
                True,
            )
        ):
            route = str(
                attempt.get(
                    "route",
                    "",
                )
            ).upper()

            if route not in VALID_PHASES:
                errors.append(
                    f"previous_attempts #{index}: "
                    f"invalid or missing route "
                    f"'{route}'."
                )

        if bool(
            nested_get(
                policy,
                [
                    "history",
                    "require_previous_changes",
                ],
                True,
            )
        ):
            if not non_empty(
                attempt.get(
                    "changed_artifacts"
                )
            ):
                errors.append(
                    f"previous_attempts #{index}: "
                    "changed_artifacts is required."
                )

        if bool(
            nested_get(
                policy,
                [
                    "history",
                    "require_retry_results",
                ],
                True,
            )
        ):
            if not non_empty(
                attempt.get(
                    "result"
                )
            ):
                errors.append(
                    f"previous_attempts #{index}: "
                    "result is required."
                )

    return (
        errors,
        len(previous_attempts),
    )


# ============================================================
# Classification / Routing
# ============================================================


def validate_classification_and_route(
    report: dict[str, Any],
    policy: dict[str, Any],
    status: str,
) -> list[str]:
    errors: list[str] = []

    classification = str(
        report.get(
            "classification",
            "",
        )
    ).upper()

    allowed_classifications = {
        value.upper()
        for value in as_string_list(
            nested_get(
                policy,
                [
                    "classification",
                    "allowed",
                ],
                [],
            )
        )
    }

    if status == "TRIAGED":
        if classification not in allowed_classifications:
            errors.append(
                f"Invalid or missing classification: "
                f"{classification!r}"
            )

    elif status == "BLOCKED":
        if (
            classification
            and classification not in allowed_classifications
        ):
            errors.append(
                f"Invalid classification: "
                f"{classification!r}"
            )

    recommended_route = str(
        report.get(
            "recommended_route",
            "",
        )
    ).upper()

    allowed_routes = {
        value.upper()
        for value in as_string_list(
            nested_get(
                policy,
                ["routes", "allowed"],
                [],
            )
        )
    }

    if status == "TRIAGED":
        if recommended_route not in allowed_routes:
            errors.append(
                f"Invalid or missing recommended_route: "
                f"{recommended_route!r}"
            )

        routing = nested_get(
            policy,
            ["routing"],
            {},
        )

        expected_route = (
            str(
                routing.get(
                    classification,
                    "",
                )
            ).upper()
            if isinstance(
                routing,
                dict,
            )
            else ""
        )

        if expected_route == "ROOT_CAUSE":
            if recommended_route not in {
                "REQUIREMENTS",
                "ARCHITECTURE",
                "IMPLEMENTATION",
                "UNIT_TEST",
                "INTEGRATION_TEST",
            }:
                errors.append(
                    "ROOT_CAUSE classification requires "
                    "a concrete SDLC phase as "
                    "recommended_route."
                )

        elif expected_route:
            if recommended_route != expected_route:
                errors.append(
                    f"recommended_route "
                    f"'{recommended_route}' "
                    f"!= policy route "
                    f"'{expected_route}'."
                )

        else:
            errors.append(
                f"No routing policy found for "
                f"{classification}."
            )

    if status == "BLOCKED":
        if recommended_route != "BLOCKED":
            errors.append(
                "BLOCKED status requires "
                "recommended_route=BLOCKED."
            )

    if status == "INVALID_INVOCATION":
        # INVALID_INVOCATIONではrouteは不要。
        if recommended_route and recommended_route not in allowed_routes:
            errors.append(
                f"Invalid recommended_route: "
                f"{recommended_route!r}"
            )

    return errors


# ============================================================
# Evidence / Root Cause
# ============================================================


def validate_evidence(
    report: dict[str, Any],
    policy: dict[str, Any],
    status: str,
) -> list[str]:
    """
    Failure Triage AgentのResult Contractにある
    evidence: [{source, detail}] を使って必須Evidenceを検証する。

    Agentに定義されていない追加Top-level Fieldを要求しない。
    """
    errors: list[str] = []

    if status == "INVALID_INVOCATION":
        return errors

    root_cause = report.get(
        "root_cause"
    )

    if bool(
        nested_get(
            policy,
            [
                "evidence",
                "require_root_cause_reason",
            ],
            True,
        )
    ):
        if not non_empty(root_cause):
            errors.append(
                "root_cause is required."
            )

    evidence = report.get(
        "evidence"
    )

    if not isinstance(
        evidence,
        list,
    ) or not evidence:
        errors.append(
            "evidence must be a non-empty array."
        )
        return errors

    evidence_sources: set[str] = set()

    for index, item in enumerate(
        evidence,
        start=1,
    ):
        if not isinstance(
            item,
            dict,
        ):
            errors.append(
                f"evidence #{index} must be an object."
            )
            continue

        source = str(
            item.get(
                "source",
                "",
            )
        ).strip()

        detail = item.get(
            "detail"
        )

        if not source:
            errors.append(
                f"evidence #{index}: source is required."
            )
        else:
            normalized = (
                source.lower()
                .replace("_", " ")
                .replace("-", " ")
            )
            evidence_sources.add(
                " ".join(
                    normalized.split()
                )
            )

        if not non_empty(detail):
            errors.append(
                f"evidence #{index}: detail is required."
            )

    def has_source(*keywords: str) -> bool:
        for source in evidence_sources:
            if all(
                keyword.lower() in source
                for keyword in keywords
            ):
                return True
        return False

    if bool(
        nested_get(
            policy,
            [
                "evidence",
                "require_failure_history",
            ],
            True,
        )
    ):
        # previous_attempts自体がFailure Historyの構造化Evidenceなので、
        # どちらかが存在すればよい。
        if (
            not non_empty(
                report.get(
                    "previous_attempts"
                )
            )
            and not has_source(
                "failure",
                "history",
            )
        ):
            errors.append(
                "Failure History evidence is required."
            )

    if bool(
        nested_get(
            policy,
            [
                "evidence",
                "require_source_artifact",
            ],
            True,
        )
    ):
        if not (
            has_source("source", "artifact")
            or has_source("artifact")
            or has_source("error", "location")
            or has_source("test", "case")
        ):
            errors.append(
                "Source Artifact / Error Location / "
                "Test Case evidence is required."
            )

    if bool(
        nested_get(
            policy,
            [
                "evidence",
                "require_expected_behavior",
            ],
            True,
        )
    ):
        if not has_source(
            "expected",
            "behavior",
        ):
            errors.append(
                "Expected Behavior evidence is required."
            )

    if bool(
        nested_get(
            policy,
            [
                "evidence",
                "require_actual_behavior",
            ],
            True,
        )
    ):
        if not has_source(
            "actual",
            "behavior",
        ):
            errors.append(
                "Actual Behavior evidence is required."
            )

    if bool(
        nested_get(
            policy,
            [
                "evidence",
                "require_previous_attempts",
            ],
            True,
        )
    ):
        if not non_empty(
            report.get(
                "previous_attempts"
            )
        ):
            errors.append(
                "previous_attempts is required."
            )

    # analysis.require_previous_attempt_analysisは、
    # Result Contractに専用Fieldがないため、
    # Root Cause EvidenceまたはPrevious Attemptsのdetailで担保する。
    if bool(
        nested_get(
            policy,
            [
                "analysis",
                "require_previous_attempt_analysis",
            ],
            True,
        )
    ):
        if not (
            has_source("previous", "attempt")
            or has_source("retry", "analysis")
            or has_source("root", "cause")
        ):
            errors.append(
                "Previous attempt analysis evidence is required."
            )

    return errors


# ============================================================
# Invalidation
# ============================================================


def validate_invalidated_phases(
    report: dict[str, Any],
    policy: dict[str, Any],
    status: str,
) -> list[str]:
    errors: list[str] = []

    invalidated = report.get(
        "invalidated_phases",
        [],
    )

    if not isinstance(
        invalidated,
        list,
    ):
        return [
            "invalidated_phases must be an array."
        ]

    invalidated_normalized = [
        str(value).upper()
        for value in invalidated
    ]

    unknown = (
        set(invalidated_normalized)
        - {
            "ARCHITECTURE",
            "IMPLEMENTATION",
            "UNIT_TEST",
            "INTEGRATION_TEST",
        }
    )

    if unknown:
        errors.append(
            "invalidated_phases contains unknown phase(s): "
            + ", ".join(
                sorted(unknown)
            )
        )

    if status != "TRIAGED":
        return errors

    route = str(
        report.get(
            "recommended_route",
            "",
        )
    ).upper()

    invalidation_policy = nested_get(
        policy,
        ["invalidation"],
        {},
    )

    expected = []

    if isinstance(
        invalidation_policy,
        dict,
    ):
        expected = [
            str(value).upper()
            for value in as_list(
                invalidation_policy.get(
                    route,
                    [],
                )
            )
        ]

    if invalidated_normalized != expected:
        errors.append(
            "invalidated_phases does not match "
            f"policy for route {route}. "
            f"actual={invalidated_normalized}, "
            f"expected={expected}"
        )

    return errors


# ============================================================
# Modification / Agent Invocation Evidence
# ============================================================


def validate_no_prohibited_actions(
    report: dict[str, Any],
    policy: dict[str, Any],
) -> list[str]:
    errors: list[str] = []

    modifications = report.get(
        "modifications_performed",
        [],
    )

    if modifications is None:
        modifications = []

    if not isinstance(
        modifications,
        list,
    ):
        errors.append(
            "modifications_performed must be an array."
        )
        modifications = []

    if modifications:
        errors.append(
            "Failure Triage must not modify artifacts."
        )

    direct_agents = report.get(
        "direct_agent_invocations",
        [],
    )

    if direct_agents is None:
        direct_agents = []

    if not isinstance(
        direct_agents,
        list,
    ):
        errors.append(
            "direct_agent_invocations must be an array."
        )
        direct_agents = []

    allow_direct = bool(
        nested_get(
            policy,
            [
                "agent_invocation",
                "allow_direct_subagent_invocation",
            ],
            False,
        )
    )

    if direct_agents and not allow_direct:
        errors.append(
            "Failure Triage must not invoke "
            "subagents directly."
        )

    return errors


# ============================================================
# Status Consistency
# ============================================================


def validate_status_consistency(
    report: dict[str, Any],
    status: str,
    current_errors: list[str],
) -> list[str]:
    errors: list[str] = []

    if status == "TRIAGED":
        if str(
            report.get(
                "recommended_route",
                "",
            )
        ).upper() == "BLOCKED":
            errors.append(
                "TRIAGED cannot use "
                "recommended_route=BLOCKED."
            )

        if not non_empty(
            report.get(
                "recommended_action"
            )
        ):
            errors.append(
                "TRIAGED requires recommended_action."
            )

    elif status == "BLOCKED":
        if not non_empty(
            report.get(
                "recommended_action"
            )
        ):
            errors.append(
                "BLOCKED requires recommended_action "
                "or explanation of required information."
            )

    if status in {
        "TRIAGED",
        "BLOCKED",
    } and current_errors:
        errors.append(
            "Failure Triage report contains "
            "deterministic validation errors."
        )

    return errors


# ============================================================
# Full Validation
# ============================================================


def validate(
    repo_root: Path,
    policy_path: Path,
    report_path: Path,
    reports_dir: Path,
) -> tuple[
    list[str],
    dict[str, Any],
]:
    errors: list[str] = []

    policy = read_yaml(
        policy_path
    )

    policy_errors = validate_policy(
        policy
    )

    errors.extend(
        policy_errors
    )

    if policy_errors:
        return (
            errors,
            {
                "status": "FAIL",
                "errors": errors,
            },
        )

    errors.extend(
        validate_required_reports(
            reports_dir,
            policy,
        )
    )

    report = read_json(
        report_path
    )

    header_errors, status, retry_count = (
        validate_header(
            report,
            policy,
        )
    )

    errors.extend(
        header_errors
    )

    errors.extend(
        validate_invocation(
            report=report,
            policy=policy,
            status=status,
            retry_count=retry_count,
        )
    )

    errors.extend(
        validate_same_failure(
            report=report,
            policy=policy,
            status=status,
        )
    )

    history_errors, attempt_count = (
        validate_history(
            report=report,
            policy=policy,
            status=status,
        )
    )

    errors.extend(
        history_errors
    )

    errors.extend(
        validate_classification_and_route(
            report=report,
            policy=policy,
            status=status,
        )
    )

    errors.extend(
        validate_evidence(
            report=report,
            policy=policy,
            status=status,
        )
    )

    errors.extend(
        validate_invalidated_phases(
            report=report,
            policy=policy,
            status=status,
        )
    )

    errors.extend(
        validate_no_prohibited_actions(
            report=report,
            policy=policy,
        )
    )

    status_errors = (
        validate_status_consistency(
            report=report,
            status=status,
            current_errors=list(
                errors
            ),
        )
    )

    errors.extend(
        status_errors
    )

    result = {
        "status": (
            "PASS"
            if not errors
            else "FAIL"
        ),

        "triage_status":
            status,

        "source_phase":
            str(
                report.get(
                    "source_phase",
                    "",
                )
            ).upper(),

        "retry_count":
            retry_count,

        "attempt_count":
            attempt_count,

        "classification":
            str(
                report.get(
                    "classification",
                    "",
                )
            ).upper(),

        "recommended_route":
            str(
                report.get(
                    "recommended_route",
                    "",
                )
            ).upper(),

        "invalidated_phases":
            report.get(
                "invalidated_phases",
                [],
            ),

        "errors":
            errors,
    }

    return (
        errors,
        result,
    )


# ============================================================
# CLI
# ============================================================


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate Failure Triage report "
            "against policy, retry conditions, "
            "routing and invalidation rules."
        )
    )

    parser.add_argument(
        "--repo-root",
        default=".",
    )

    parser.add_argument(
        "--policy",
        default=(
            ".github/skills/"
            "failure-triage/"
            "policy/"
            "failure-triage-policy.yaml"
        ),
    )

    parser.add_argument(
        "--report",
        default=(
            "reports/"
            "failure-triage/"
            "failure-triage-report.json"
        ),
    )

    parser.add_argument(
        "--reports-dir",
        default=(
            "reports/"
            "failure-triage"
        ),
    )

    parser.add_argument(
        "--output",
        default=(
            "reports/"
            "failure-triage/"
            "validation-result.json"
        ),
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    repo_root = Path(
        args.repo_root
    ).resolve()

    def resolve(
        value: str,
    ) -> Path:
        path = Path(
            value
        )

        if path.is_absolute():
            return path

        return (
            repo_root
            / path
        )

    output_path = resolve(
        args.output
    )

    try:
        errors, result = validate(
            repo_root=repo_root,

            policy_path=resolve(
                args.policy
            ),

            report_path=resolve(
                args.report
            ),

            reports_dir=resolve(
                args.reports_dir
            ),
        )

    except (
        FileNotFoundError,
        ValueError,
        json.JSONDecodeError,
        yaml.YAMLError,
    ) as error:
        result = {
            "status": "FAIL",
            "errors": [
                str(error)
            ],
        }

        write_result(
            output_path,
            result,
        )

        print(
            "========================================"
        )

        print(
            " Failure Triage Validation"
        )

        print(
            "========================================"
        )

        print()

        print(
            f"[FAIL] {error}"
        )

        print(
            f"Result: {output_path}"
        )

        return 1

    write_result(
        output_path,
        result,
    )

    print(
        "========================================"
    )

    print(
        " Failure Triage Validation"
    )

    print(
        "========================================"
    )

    print()

    if errors:
        print(
            "[FAIL] Failure Triage "
            "validation failed."
        )

        print()

        for index, error in enumerate(
            errors,
            start=1,
        ):
            print(
                f"{index}. {error}"
            )

        print()

        print(
            f"Total errors: "
            f"{len(errors)}"
        )

        print(
            f"Result: "
            f"{output_path}"
        )

        return 1

    print(
        "[PASS] Failure Triage "
        "diagnostic gate passed."
    )

    print(
        f"Result: "
        f"{output_path}"
    )

    return 0


if __name__ == "__main__":
    sys.exit(
        main()
    )
