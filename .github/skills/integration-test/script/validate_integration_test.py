#!/usr/bin/env python3

"""
Integration Test Validator

Integration Test Policyに基づき、
結合試験工程の機械的なQuality Gateを実施する。

検証対象:

- Integration Test Policy
- Integration Test Plan
- AI GENERATED / EXTERNAL Case分類
- AI INITIAL / GAP_FILL分類
- Required Coverage
- COMMON / AI_ONLY / EXTERNAL_ONLY / MISSING
- Final Coverage
- Test Criteria
- External Case Integrity
- Test Result
- Defect
- Regression / Re-execution
- Error Report
- Database / Test Environment
- Traceability
- Required Reports
- JUnit XML

Exit Code:
    0: PASS
    1: FAIL

Dependency:
    PyYAML
"""

from __future__ import annotations

import argparse
import glob
import json
import math
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import Any

import yaml


AI_ORIGIN = "AI_GENERATED"
EXTERNAL_ORIGIN = "EXTERNAL"

INITIAL_STAGE = "INITIAL"
GAP_FILL_STAGE = "GAP_FILL"


# ============================================================
# Utility
# ============================================================


def read_json(
    path: Path,
) -> dict[str, Any]:

    if not path.exists():
        raise FileNotFoundError(
            f"File not found: {path}"
        )

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise ValueError(
            f"JSON root must be an object: {path}"
        )

    return data


def read_yaml(
    path: Path,
) -> dict[str, Any]:

    if not path.exists():
        raise FileNotFoundError(
            f"File not found: {path}"
        )

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        data = yaml.safe_load(file)

    if not isinstance(data, dict):
        raise ValueError(
            f"YAML root must be a mapping: {path}"
        )

    return data


def nested_get(
    source: dict[str, Any],
    path: list[str],
    default: Any = None,
) -> Any:

    current: Any = source

    for key in path:

        if (
            not isinstance(current, dict)
            or key not in current
        ):
            return default

        current = current[key]

    return current


def non_empty(
    value: Any,
) -> bool:

    if value is None:
        return False

    if isinstance(value, str):
        return bool(value.strip())

    if isinstance(
        value,
        (list, dict, tuple, set),
    ):
        return len(value) > 0

    return True


def pct(
    part: int,
    whole: int,
) -> float:

    if whole == 0:
        return 100.0

    return round(
        (part / whole) * 100.0,
        2,
    )


def nearly_equal(
    a: Any,
    b: Any,
    tolerance: float = 0.01,
) -> bool:

    if a is None and b is None:
        return True

    if a is None or b is None:
        return False

    try:
        return math.isclose(
            float(a),
            float(b),
            abs_tol=tolerance,
        )

    except (
        TypeError,
        ValueError,
    ):
        return False


def as_string_list(
    value: Any,
) -> list[str]:

    if value is None:
        return []

    if isinstance(value, str):
        return (
            [value]
            if value.strip()
            else []
        )

    if isinstance(value, list):
        return [
            str(item)
            for item in value
            if str(item).strip()
        ]

    return []


def case_coverage_keys(
    case: dict[str, Any],
) -> set[str]:

    keys = set(
        as_string_list(
            case.get("coverage_keys")
        )
    )

    one = case.get(
        "coverage_key"
    )

    if (
        isinstance(one, str)
        and one.strip()
    ):
        keys.add(
            one.strip()
        )

    return keys


def case_criteria(
    case: dict[str, Any],
) -> set[str]:

    values = set(
        as_string_list(
            case.get("criteria")
        )
    )

    one = case.get(
        "criterion"
    )

    if (
        isinstance(one, str)
        and one.strip()
    ):
        values.add(
            one.strip()
        )

    return values


# ============================================================
# Policy
# ============================================================


def validate_policy(
    policy: dict[str, Any],
) -> list[str]:

    errors: list[str] = []

    required_paths = [
        [
            "test_result",
            "required_pass_rate",
        ],
        [
            "test_result",
            "allowed_failures",
        ],
        [
            "test_result",
            "allowed_errors",
        ],
        [
            "case_origin",
            "allowed",
        ],
        [
            "ai_generated_cases",
            "initial_generation_required",
        ],
        [
            "external_cases",
            "optional",
        ],
        [
            "external_cases",
            "missing_input",
            "require_user_decision",
        ],
        [
            "external_cases",
            "missing_input",
            "allow_continue_without_external_cases_after_confirmation",
        ],
        [
            "external_cases",
            "missing_input",
            "allow_implicit_no_external_cases",
        ],
        [
            "external_cases",
            "immutable",
        ],
        [
            "coverage",
            "enabled",
        ],
        [
            "coverage",
            "final",
            "required_coverage_rate",
        ],
        [
            "coverage",
            "final",
            "allow_missing",
        ],
        [
            "coverage",
            "gap_fill",
            "required_when_missing",
        ],
        [
            "criteria",
            "directory",
        ],
        [
            "criteria",
            "pattern",
        ],
        [
            "criteria",
            "load_all",
        ],
        [
            "automation",
            "execute_all_automatable_cases",
        ],
        [
            "automation",
            "allowed_automation_blocked",
        ],
        [
            "test_spec_conflict",
            "allowed_unresolved",
        ],
        [
            "error_classification",
            "allowed",
        ],
        [
            "error_classification",
            "require_classification_for_all_failures",
        ],
        [
            "defects",
            "unresolved_allowed",
        ],
        [
            "defects",
            "require_root_cause",
        ],
        [
            "regression",
            "required_after_defect",
        ],
        [
            "regression",
            "rerun_failed_case",
        ],
        [
            "regression",
            "rerun_related_cases",
        ],
        [
            "regression",
            "rerun_full_suite",
        ],
        [
            "failure_handling",
            "allow_next_phase_with_failure",
        ],
        [
            "reports",
            "directory",
        ],
        [
            "reports",
            "required",
        ],
    ]

    for path in required_paths:

        if nested_get(
            policy,
            path,
            None,
        ) is None:

            errors.append(
                "Policy missing required setting: "
                + ".".join(path)
            )

    allowed_origins = set(
        as_string_list(
            nested_get(
                policy,
                [
                    "case_origin",
                    "allowed",
                ],
                [],
            )
        )
    )

    if {
        AI_ORIGIN,
        EXTERNAL_ORIGIN,
    } - allowed_origins:

        errors.append(
            "case_origin.allowed must include "
            "AI_GENERATED and EXTERNAL."
        )

    allowed_stages = set(
        as_string_list(
            nested_get(
                policy,
                [
                    "case_origin",
                    "ai_generation_stage",
                    "allowed",
                ],
                [],
            )
        )
    )

    if {
        INITIAL_STAGE,
        GAP_FILL_STAGE,
    } - allowed_stages:

        errors.append(
            "case_origin.ai_generation_stage.allowed "
            "must include INITIAL and GAP_FILL."
        )

    required_rate = nested_get(
        policy,
        [
            "coverage",
            "final",
            "required_coverage_rate",
        ],
        None,
    )

    if required_rate is not None:

        try:
            value = float(
                required_rate
            )

            if (
                value < 0
                or value > 100
            ):
                errors.append(
                    "coverage.final."
                    "required_coverage_rate must be "
                    "between 0 and 100."
                )

        except (
            TypeError,
            ValueError,
        ):
            errors.append(
                "coverage.final."
                "required_coverage_rate "
                "must be numeric."
            )

    return errors


# ============================================================
# Criteria
# ============================================================


def discover_criteria(
    criteria_dir: Path,
    pattern: str,
) -> set[str]:

    if not criteria_dir.exists():
        return set()

    result: set[str] = set()

    for path in criteria_dir.glob(
        pattern
    ):

        if not path.is_file():
            continue

        name = path.name

        if name.endswith(
            ".criterion.md"
        ):
            name = name[
                :-len(".criterion.md")
            ]

        result.add(
            name
        )

    return result


def validate_criteria_coverage(
    evidence: dict[str, Any],
    criteria: set[str],
    policy: dict[str, Any],
) -> list[str]:

    if not nested_get(
        policy,
        [
            "criteria",
            "load_all",
        ],
        True,
    ):
        return []

    errors: list[str] = []

    allowed_results = set(
        as_string_list(
            nested_get(
                policy,
                [
                    "criteria",
                    "allowed_results",
                ],
                [],
            )
        )
    )

    reported = {
        str(
            item.get(
                "criterion",
                "",
            )
        ).strip(): item
        for item in evidence.get(
            "criteria_coverage",
            [],
        )
        if (
            isinstance(item, dict)
            and str(
                item.get(
                    "criterion",
                    "",
                )
            ).strip()
        )
    }

    for criterion in sorted(
        criteria
    ):

        item = reported.get(
            criterion
        )

        if item is None:

            errors.append(
                f"Criterion not evaluated: "
                f"{criterion}"
            )

            continue

        result = str(
            item.get(
                "result",
                "",
            )
        ).upper()

        if result not in allowed_results:

            errors.append(
                f"Criterion {criterion}: "
                f"invalid result '{result}'."
            )

            continue

        applicable = bool(
            item.get(
                "applicable",
                True,
            )
        )

        if (
            applicable
            and result != "PASS"
        ):
            errors.append(
                f"Applicable criterion "
                f"is not PASS: {criterion}"
            )

        if not applicable:

            if (
                result
                != "NOT_APPLICABLE"
            ):
                errors.append(
                    f"Criterion {criterion}: "
                    "applicable=false requires "
                    "NOT_APPLICABLE."
                )

            if nested_get(
                policy,
                [
                    "criteria",
                    "require_reason_when_not_applicable",
                ],
                True,
            ):

                if not non_empty(
                    item.get(
                        "reason"
                    )
                ):
                    errors.append(
                        f"Criterion {criterion}: "
                        "NOT_APPLICABLE requires reason."
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

    required = as_string_list(
        nested_get(
            policy,
            [
                "reports",
                "required",
            ],
            [],
        )
    )

    for name in required:

        path = (
            reports_dir
            / name
        )

        if not path.exists():

            errors.append(
                f"Required report missing: {path}"
            )

        elif (
            path.is_file()
            and path.stat().st_size == 0
        ):
            errors.append(
                f"Required report is empty: {path}"
            )

    return errors


# ============================================================
# JUnit
# ============================================================


def find_junit_files(
    patterns: list[str],
) -> list[Path]:

    files: set[Path] = set()

    for pattern in patterns:

        for item in glob.glob(
            pattern,
            recursive=True,
        ):

            path = Path(
                item
            )

            if path.is_file():
                files.add(
                    path
                )

    return sorted(
        files
    )


def parse_junit(
    files: list[Path],
) -> dict[str, Any]:

    summary = {
        "total": 0,
        "passed": 0,
        "failed": 0,
        "errors": 0,
        "skipped": 0,
    }

    for path in files:

        root = ET.parse(
            path
        ).getroot()

        for testcase in root.iter(
            "testcase"
        ):

            summary["total"] += 1

            if testcase.find(
                "failure"
            ) is not None:

                summary["failed"] += 1

            elif testcase.find(
                "error"
            ) is not None:

                summary["errors"] += 1

            elif testcase.find(
                "skipped"
            ) is not None:

                summary["skipped"] += 1

            else:

                summary["passed"] += 1

    return summary


def validate_junit(
    summary: dict[str, Any],
    policy: dict[str, Any],
) -> list[str]:

    errors: list[str] = []

    if summary["total"] == 0:
        return [
            "No Integration Tests were "
            "executed in JUnit XML."
        ]

    required_pass_rate = float(
        nested_get(
            policy,
            [
                "test_result",
                "required_pass_rate",
            ],
            100,
        )
    )

    allowed_failures = int(
        nested_get(
            policy,
            [
                "test_result",
                "allowed_failures",
            ],
            0,
        )
    )

    allowed_errors = int(
        nested_get(
            policy,
            [
                "test_result",
                "allowed_errors",
            ],
            0,
        )
    )

    actual_pass_rate = (
        summary["passed"]
        / summary["total"]
    ) * 100.0

    if (
        actual_pass_rate
        < required_pass_rate
    ):

        errors.append(
            f"JUnit pass rate "
            f"{actual_pass_rate:.2f}% "
            f"< required "
            f"{required_pass_rate:.2f}%."
        )

    if (
        summary["failed"]
        > allowed_failures
    ):

        errors.append(
            f"JUnit failed tests "
            f"{summary['failed']} "
            f"> allowed "
            f"{allowed_failures}."
        )

    if (
        summary["errors"]
        > allowed_errors
    ):

        errors.append(
            f"JUnit error tests "
            f"{summary['errors']} "
            f"> allowed "
            f"{allowed_errors}."
        )

    return errors


# ============================================================
# Integration Test Plan
# ============================================================


def validate_plan(
    plan: dict[str, Any],
    criteria: set[str],
    policy: dict[str, Any],
) -> tuple[
    list[str],
    dict[str, dict[str, Any]],
]:

    errors: list[str] = []

    cases = plan.get(
        "cases"
    )

    if (
        not isinstance(
            cases,
            list,
        )
        or not cases
    ):
        return (
            [
                "integration-test-plan.json "
                "must contain a non-empty "
                "cases array."
            ],
            {},
        )

    allowed_origins = set(
        as_string_list(
            nested_get(
                policy,
                [
                    "case_origin",
                    "allowed",
                ],
                [],
            )
        )
    )

    allowed_stages = set(
        as_string_list(
            nested_get(
                policy,
                [
                    "case_origin",
                    "ai_generation_stage",
                    "allowed",
                ],
                [],
            )
        )
    )

    case_map: dict[
        str,
        dict[str, Any],
    ] = {}

    ai_initial_count = 0

    required_fields = [
        "case_id",
        "title",
        "requirement_id",
        "test_category",
        "steps",
        "expected_result",
        "execution_type",
    ]

    for index, case in enumerate(
        cases,
        start=1,
    ):

        if not isinstance(
            case,
            dict,
        ):

            errors.append(
                f"Plan case #{index} "
                "must be an object."
            )

            continue

        case_id = str(
            case.get(
                "case_id",
                "",
            )
        ).strip()

        if not case_id:

            errors.append(
                f"Plan case #{index} "
                "has no case_id."
            )

            continue

        if case_id in case_map:

            errors.append(
                f"Duplicate case_id: "
                f"{case_id}"
            )

            continue

        case_map[
            case_id
        ] = case

        for field in required_fields:

            if not non_empty(
                case.get(
                    field
                )
            ):
                errors.append(
                    f"{case_id}: "
                    f"required field "
                    f"'{field}' "
                    "is missing/empty."
                )

        origin = str(
            case.get(
                "origin",
                "",
            )
        ).upper()

        if (
            origin
            not in allowed_origins
        ):
            errors.append(
                f"{case_id}: "
                f"invalid origin "
                f"'{origin}'."
            )

        stage = str(
            case.get(
                "generation_stage",
                "",
            )
        ).upper()

        if origin == AI_ORIGIN:

            if (
                stage
                not in allowed_stages
            ):
                errors.append(
                    f"{case_id}: "
                    "AI case has invalid "
                    "generation_stage "
                    f"'{stage}'."
                )

            if (
                stage
                == INITIAL_STAGE
            ):
                ai_initial_count += 1

        elif (
            origin
            == EXTERNAL_ORIGIN
        ):

            if stage:

                errors.append(
                    f"{case_id}: "
                    "EXTERNAL case must not "
                    "have generation_stage."
                )

            if not non_empty(
                case.get(
                    "source_case_id"
                )
            ):
                errors.append(
                    f"{case_id}: "
                    "EXTERNAL case requires "
                    "source_case_id."
                )

            if not non_empty(
                case.get(
                    "source_file"
                )
            ):
                errors.append(
                    f"{case_id}: "
                    "EXTERNAL case requires "
                    "source_file."
                )

        execution_type = str(
            case.get(
                "execution_type",
                "",
            )
        ).upper()

        if execution_type not in {
            "AUTOMATABLE",
            "NOT_AUTOMATABLE",
        }:

            errors.append(
                f"{case_id}: "
                "invalid execution_type "
                f"'{execution_type}'."
            )

        keys = case_coverage_keys(
            case
        )

        if not keys:

            errors.append(
                f"{case_id}: "
                "coverage_key or "
                "coverage_keys is required."
            )

        refs = case_criteria(
            case
        )

        if not refs:

            errors.append(
                f"{case_id}: "
                "criterion or criteria "
                "is required."
            )

        for criterion in sorted(
            refs
        ):

            if (
                criterion
                not in criteria
            ):
                errors.append(
                    f"{case_id}: "
                    "unknown criterion "
                    f"'{criterion}'."
                )

    if nested_get(
        policy,
        [
            "ai_generated_cases",
            "initial_generation_required",
        ],
        True,
    ):

        if ai_initial_count == 0:

            errors.append(
                "No AI_GENERATED / INITIAL "
                "case exists."
            )

    return (
        errors,
        case_map,
    )


# ============================================================
# Required Coverage
# ============================================================


def validate_required_coverage(
    coverage_report: dict[str, Any],
    criteria: set[str],
) -> tuple[
    list[str],
    dict[str, dict[str, Any]],
]:

    errors: list[str] = []

    items = coverage_report.get(
        "required_coverage"
    )

    if (
        not isinstance(
            items,
            list,
        )
        or not items
    ):
        return (
            [
                "coverage-gap-report.json "
                "requires non-empty "
                "required_coverage."
            ],
            {},
        )

    by_key: dict[
        str,
        dict[str, Any],
    ] = {}

    ids: set[str] = set()

    for index, item in enumerate(
        items,
        start=1,
    ):

        if not isinstance(
            item,
            dict,
        ):
            errors.append(
                f"required_coverage "
                f"#{index} "
                "must be an object."
            )

            continue

        coverage_id = str(
            item.get(
                "coverage_id",
                "",
            )
        ).strip()

        key = str(
            item.get(
                "coverage_key",
                "",
            )
        ).strip()

        if not coverage_id:

            errors.append(
                f"required_coverage "
                f"#{index}: "
                "coverage_id is required."
            )

        elif coverage_id in ids:

            errors.append(
                f"Duplicate coverage_id: "
                f"{coverage_id}"
            )

        else:
            ids.add(
                coverage_id
            )

        if not key:

            errors.append(
                f"required_coverage "
                f"#{index}: "
                "coverage_key is required."
            )

            continue

        if key in by_key:

            errors.append(
                "Duplicate required "
                f"coverage_key: {key}"
            )

        else:
            by_key[
                key
            ] = item

        required_fields = [
            "requirement_id",
            "integration_point",
            "test_category",
            "criterion",
            "expected_behavior",
        ]

        for field in required_fields:

            if not non_empty(
                item.get(
                    field
                )
            ):
                errors.append(
                    f"{coverage_id or key}: "
                    f"required field "
                    f"'{field}' "
                    "is missing/empty."
                )

        criterion = str(
            item.get(
                "criterion",
                "",
            )
        ).strip()

        if (
            criterion
            and criterion
            not in criteria
        ):
            errors.append(
                f"{coverage_id or key}: "
                f"unknown criterion "
                f"'{criterion}'."
            )

    return (
        errors,
        by_key,
    )


def derive_coverage(
    case_map: dict[
        str,
        dict[str, Any],
    ],
    required_keys: set[str],
) -> tuple[
    dict[str, Any],
    list[str],
]:

    errors: list[str] = []

    ai_initial: set[str] = set()
    ai_gap_fill: set[str] = set()
    external: set[str] = set()

    for case_id, case in (
        case_map.items()
    ):

        keys = case_coverage_keys(
            case
        )

        unknown = (
            keys
            - required_keys
        )

        if unknown:

            errors.append(
                f"{case_id}: "
                "references unknown "
                "coverage_key(s): "
                + ", ".join(
                    sorted(
                        unknown
                    )
                )
            )

        keys &= required_keys

        origin = str(
            case.get(
                "origin",
                "",
            )
        ).upper()

        stage = str(
            case.get(
                "generation_stage",
                "",
            )
        ).upper()

        if (
            origin
            == AI_ORIGIN
            and stage
            == INITIAL_STAGE
        ):
            ai_initial |= keys

        elif (
            origin
            == AI_ORIGIN
            and stage
            == GAP_FILL_STAGE
        ):
            ai_gap_fill |= keys

        elif (
            origin
            == EXTERNAL_ORIGIN
        ):
            external |= keys

    common = (
        ai_initial
        & external
    )

    ai_only = (
        ai_initial
        - external
    )

    external_only = (
        external
        - ai_initial
    )

    initial_union = (
        ai_initial
        | external
    )

    missing = (
        required_keys
        - initial_union
    )

    final_covered = (
        initial_union
        | ai_gap_fill
    )

    final_missing = (
        required_keys
        - final_covered
    )

    metrics = {
        "required": len(
            required_keys
        ),
        "common": len(
            common
        ),
        "ai_only": len(
            ai_only
        ),
        "external_only": len(
            external_only
        ),
        "missing": len(
            missing
        ),
        "ai_initial_coverage_rate": pct(
            len(ai_initial),
            len(required_keys),
        ),
        "external_coverage_rate": (
            pct(
                len(external),
                len(required_keys),
            )
            if external
            else None
        ),
        "combined_initial_coverage_rate": pct(
            len(initial_union),
            len(required_keys),
        ),
        "final_covered": len(
            final_covered
        ),
        "final_missing": len(
            final_missing
        ),
        "final_coverage_rate": pct(
            len(final_covered),
            len(required_keys),
        ),
        "sets": {
            "common": common,
            "ai_only": ai_only,
            "external_only": external_only,
            "missing": missing,
            "final_missing": final_missing,
        },
    }

    return (
        metrics,
        errors,
    )


# ============================================================
# Coverage Report
# ============================================================


def validate_coverage_report(
    report: dict[str, Any],
    derived: dict[str, Any],
    case_map: dict[
        str,
        dict[str, Any],
    ],
    policy: dict[str, Any],
) -> list[str]:

    errors: list[str] = []

    initial = report.get(
        "initial_metrics",
        {},
    )

    final = report.get(
        "final_metrics",
        {},
    )

    expected_initial = {
        "required":
            derived["required"],
        "common":
            derived["common"],
        "ai_only":
            derived["ai_only"],
        "external_only":
            derived["external_only"],
        "missing":
            derived["missing"],
    }

    for (
        key,
        expected,
    ) in expected_initial.items():

        if (
            initial.get(key)
            != expected
        ):

            errors.append(
                "coverage-gap-report "
                f"initial_metrics.{key}="
                f"{initial.get(key)!r}, "
                f"expected {expected}."
            )

    for key in [
        "ai_initial_coverage_rate",
        "combined_initial_coverage_rate",
    ]:

        if not nearly_equal(
            initial.get(key),
            derived[key],
        ):

            errors.append(
                "coverage-gap-report "
                f"initial_metrics.{key}="
                f"{initial.get(key)!r}, "
                f"expected "
                f"{derived[key]:.2f}."
            )

    has_external = any(
        str(
            case.get(
                "origin",
                "",
            )
        ).upper()
        == EXTERNAL_ORIGIN
        for case
        in case_map.values()
    )

    reported_external_rate = (
        initial.get(
            "external_coverage_rate"
        )
    )

    if has_external:

        if not nearly_equal(
            reported_external_rate,
            derived[
                "external_coverage_rate"
            ],
        ):
            errors.append(
                "coverage-gap-report "
                "initial_metrics."
                "external_coverage_rate "
                "does not match "
                "derived value."
            )

    elif (
        reported_external_rate
        not in (
            None,
            "",
            0,
            0.0,
        )
    ):
        errors.append(
            "external_coverage_rate must "
            "be null/empty/0 when no "
            "EXTERNAL cases are provided."
        )

    expected_final = {
        "covered":
            derived[
                "final_covered"
            ],
        "missing":
            derived[
                "final_missing"
            ],
    }

    for (
        key,
        expected,
    ) in expected_final.items():

        if (
            final.get(key)
            != expected
        ):
            errors.append(
                "coverage-gap-report "
                f"final_metrics.{key}="
                f"{final.get(key)!r}, "
                f"expected {expected}."
            )

    if not nearly_equal(
        final.get(
            "final_coverage_rate"
        ),
        derived[
            "final_coverage_rate"
        ],
    ):
        errors.append(
            "coverage-gap-report "
            "final_metrics."
            "final_coverage_rate "
            "does not match "
            "derived value."
        )

    required_rate = float(
        nested_get(
            policy,
            [
                "coverage",
                "final",
                "required_coverage_rate",
            ],
            100,
        )
    )

    if (
        derived[
            "final_coverage_rate"
        ]
        < required_rate
    ):
        errors.append(
            f"Final integration coverage "
            f"{derived['final_coverage_rate']:.2f}% "
            f"< required "
            f"{required_rate:.2f}%."
        )

    if not nested_get(
        policy,
        [
            "coverage",
            "final",
            "allow_missing",
        ],
        False,
    ):

        if (
            derived[
                "final_missing"
            ]
            > 0
        ):
            errors.append(
                "Final coverage has "
                f"{derived['final_missing']} "
                "missing coverage item(s)."
            )

    gaps = report.get(
        "gaps",
        [],
    )

    if not isinstance(
        gaps,
        list,
    ):
        errors.append(
            "coverage-gap-report "
            "gaps must be an array."
        )

        gaps = []

    gap_by_key = {
        str(
            item.get(
                "coverage_key",
                "",
            )
        ).strip(): item
        for item in gaps
        if (
            isinstance(item, dict)
            and str(
                item.get(
                    "coverage_key",
                    "",
                )
            ).strip()
        )
    }

    initial_missing: set[str] = (
        derived[
            "sets"
        ][
            "missing"
        ]
    )

    if nested_get(
        policy,
        [
            "coverage",
            "gap_analysis",
            "require_all_missing_items_reported",
        ],
        True,
    ):

        for key in sorted(
            initial_missing
        ):

            if (
                key
                not in gap_by_key
            ):
                errors.append(
                    "Initial MISSING "
                    "coverage not reported "
                    f"in gaps: {key}"
                )

    if (
        initial_missing
        and nested_get(
            policy,
            [
                "coverage",
                "gap_fill",
                "required_when_missing",
            ],
            True,
        )
    ):

        for key in sorted(
            initial_missing
        ):

            filling_cases = [
                case_id
                for (
                    case_id,
                    case,
                ) in case_map.items()
                if (
                    str(
                        case.get(
                            "origin",
                            "",
                        )
                    ).upper()
                    == AI_ORIGIN
                    and str(
                        case.get(
                            "generation_stage",
                            "",
                        )
                    ).upper()
                    == GAP_FILL_STAGE
                    and key
                    in case_coverage_keys(
                        case
                    )
                )
            ]

            if not filling_cases:

                errors.append(
                    "MISSING coverage was "
                    "not filled by "
                    "AI GAP_FILL case: "
                    f"{key}"
                )

    return errors


# ============================================================
# Case Comparison
# ============================================================


def validate_case_comparison(
    report: dict[str, Any],
    derived: dict[str, Any],
) -> list[str]:

    errors: list[str] = []

    items = report.get(
        "items"
    )

    if not isinstance(
        items,
        list,
    ):
        return [
            "case-comparison.json "
            "must contain an items array."
        ]

    expected: dict[
        str,
        str,
    ] = {}

    mapping = {
        "common":
            "COMMON",
        "ai_only":
            "AI_ONLY",
        "external_only":
            "EXTERNAL_ONLY",
        "missing":
            "MISSING",
    }

    for (
        classification,
        label,
    ) in mapping.items():

        for key in (
            derived[
                "sets"
            ][
                classification
            ]
        ):
            expected[
                key
            ] = label

    actual: dict[
        str,
        str,
    ] = {}

    for item in items:

        if not isinstance(
            item,
            dict,
        ):
            continue

        key = str(
            item.get(
                "coverage_key",
                "",
            )
        ).strip()

        classification = str(
            item.get(
                "classification",
                "",
            )
        ).upper()

        if key:
            actual[
                key
            ] = classification

    for (
        key,
        classification,
    ) in expected.items():

        if (
            actual.get(key)
            != classification
        ):
            errors.append(
                f"case-comparison {key}: "
                "classification="
                f"{actual.get(key)!r}, "
                f"expected "
                f"{classification}."
            )

    extra = (
        set(actual)
        - set(expected)
    )

    if extra:

        errors.append(
            "case-comparison contains "
            "unknown coverage_key(s): "
            + ", ".join(
                sorted(extra)
            )
        )

    summary = report.get(
        "summary",
        {},
    )

    expected_counts = {
        "common":
            derived["common"],
        "ai_only":
            derived["ai_only"],
        "external_only":
            derived["external_only"],
        "missing":
            derived["missing"],
    }

    for (
        key,
        expected_count,
    ) in expected_counts.items():

        if (
            summary.get(key)
            != expected_count
        ):
            errors.append(
                "case-comparison "
                f"summary.{key}="
                f"{summary.get(key)!r}, "
                f"expected "
                f"{expected_count}."
            )

    return errors

# ============================================================
# External Input
# ============================================================


def validate_external_input(
    evidence: dict[str, Any],
    case_map: dict[str, dict[str, Any]],
    policy: dict[str, Any],
) -> list[str]:

    errors: list[str] = []

    external_input = evidence.get(
        "external_input"
    )

    if not isinstance(
        external_input,
        dict,
    ):
        return [
            "integration-test-evidence.json "
            "must contain external_input."
        ]

    if "provided" not in external_input:
        errors.append(
            "external_input.provided is required."
        )

    if (
        "user_confirmed_without_external_cases"
        not in external_input
    ):
        errors.append(
            "external_input."
            "user_confirmed_without_external_cases "
            "is required."
        )

    if errors:
        return errors

    provided = bool(
        external_input[
            "provided"
        ]
    )

    confirmed_without_external = bool(
        external_input[
            "user_confirmed_without_external_cases"
        ]
    )

    has_external_cases = any(
        str(
            case.get(
                "origin",
                "",
            )
        ).upper()
        == EXTERNAL_ORIGIN
        for case in case_map.values()
    )

    require_user_decision = bool(
        nested_get(
            policy,
            [
                "external_cases",
                "missing_input",
                "require_user_decision",
            ],
            True,
        )
    )

    allow_after_confirmation = bool(
        nested_get(
            policy,
            [
                "external_cases",
                "missing_input",
                "allow_continue_without_external_cases_after_confirmation",
            ],
            True,
        )
    )

    allow_implicit = bool(
        nested_get(
            policy,
            [
                "external_cases",
                "missing_input",
                "allow_implicit_no_external_cases",
            ],
            False,
        )
    )

    if provided != has_external_cases:
        errors.append(
            "external_input.provided does not match "
            "the actual EXTERNAL cases in "
            "integration-test-plan.json."
        )

    if (
        provided
        and confirmed_without_external
    ):
        errors.append(
            "external_input is inconsistent: "
            "provided=true and "
            "user_confirmed_without_external_cases=true."
        )

    if (
        not provided
        and require_user_decision
        and not confirmed_without_external
        and not allow_implicit
    ):
        errors.append(
            "External test cases were not provided "
            "and the user did not explicitly confirm "
            "continuation without external cases."
        )

    if (
        not provided
        and confirmed_without_external
        and not allow_after_confirmation
    ):
        errors.append(
            "Policy does not allow continuation "
            "without external cases."
        )

    return errors

# ============================================================
# External Case Integrity
# ============================================================


def validate_external_integrity(
    evidence: dict[str, Any],
    case_map: dict[
        str,
        dict[str, Any],
    ],
    policy: dict[str, Any],
) -> list[str]:

    errors: list[str] = []

    external_cases = {
        case_id: case
        for (
            case_id,
            case,
        ) in case_map.items()
        if (
            str(
                case.get(
                    "origin",
                    "",
                )
            ).upper()
            == EXTERNAL_ORIGIN
        )
    }

    if not external_cases:
        return errors

    integrity_items = {
        str(
            item.get(
                "case_id",
                "",
            )
        ).strip(): item
        for item
        in evidence.get(
            "external_case_integrity",
            [],
        )
        if (
            isinstance(item, dict)
            and str(
                item.get(
                    "case_id",
                    "",
                )
            ).strip()
        )
    }

    for (
        case_id,
        case,
    ) in external_cases.items():

        item = integrity_items.get(
            case_id
        )

        if item is None:

            errors.append(
                f"{case_id}: "
                "external_case_integrity "
                "evidence is missing."
            )

            continue

        if (
            str(
                item.get(
                    "integrity_status",
                    "",
                )
            ).upper()
            != "PASS"
        ):

            errors.append(
                f"{case_id}: "
                "external case integrity "
                "is not PASS."
            )

        source_hash = str(
            item.get(
                "source_semantic_hash",
                "",
            )
        ).strip()

        normalized_hash = str(
            item.get(
                "normalized_semantic_hash",
                "",
            )
        ).strip()

        if (
            not source_hash
            or not normalized_hash
        ):

            errors.append(
                f"{case_id}: "
                "semantic hashes are "
                "required for external "
                "integrity."
            )

        elif (
            source_hash
            != normalized_hash
        ):

            errors.append(
                f"{case_id}: "
                "external case semantic "
                "hash changed during "
                "normalization."
            )

        if (
            str(
                item.get(
                    "source_case_id",
                    "",
                )
            ).strip()
            != str(
                case.get(
                    "source_case_id",
                    "",
                )
            ).strip()
        ):

            errors.append(
                f"{case_id}: "
                "source_case_id mismatch "
                "between plan and "
                "integrity evidence."
            )

        if (
            str(
                item.get(
                    "source_file",
                    "",
                )
            ).strip()
            != str(
                case.get(
                    "source_file",
                    "",
                )
            ).strip()
        ):

            errors.append(
                f"{case_id}: "
                "source_file mismatch "
                "between plan and "
                "integrity evidence."
            )

    return errors


# ============================================================
# Case Results
# ============================================================


def validate_case_results(
    evidence: dict[str, Any],
    case_map: dict[
        str,
        dict[str, Any],
    ],
    policy: dict[str, Any],
) -> list[str]:

    errors: list[str] = []

    results_list = evidence.get(
        "case_results"
    )

    if not isinstance(
        results_list,
        list,
    ):
        return [
            "integration-test-evidence.json "
            "must contain case_results array."
        ]

    result_map: dict[
        str,
        dict[str, Any],
    ] = {}

    for item in results_list:

        if not isinstance(
            item,
            dict,
        ):
            continue

        case_id = str(
            item.get(
                "case_id",
                "",
            )
        ).strip()

        if not case_id:

            errors.append(
                "case_results entry "
                "missing case_id."
            )

            continue

        if case_id in result_map:

            errors.append(
                "Duplicate case_results "
                f"entry: {case_id}"
            )

            continue

        result_map[
            case_id
        ] = item

    allowed_errors = set(
        as_string_list(
            nested_get(
                policy,
                [
                    "error_classification",
                    "allowed",
                ],
                [],
            )
        )
    )

    blocked_count = 0
    spec_conflict_count = 0

    for (
        case_id,
        case,
    ) in case_map.items():

        item = result_map.get(
            case_id
        )

        if item is None:

            errors.append(
                f"{case_id}: "
                "no final case result "
                "evidence."
            )

            continue

        origin = str(
            case.get(
                "origin",
                "",
            )
        ).upper()

        if (
            str(
                item.get(
                    "origin",
                    "",
                )
            ).upper()
            != origin
        ):

            errors.append(
                f"{case_id}: "
                "evidence origin does "
                "not match plan origin."
            )

        if origin == AI_ORIGIN:

            expected_stage = str(
                case.get(
                    "generation_stage",
                    "",
                )
            ).upper()

            if (
                str(
                    item.get(
                        "generation_stage",
                        "",
                    )
                ).upper()
                != expected_stage
            ):

                errors.append(
                    f"{case_id}: "
                    "evidence generation_stage "
                    "does not match plan."
                )

        result = str(
            item.get(
                "result",
                "",
            )
        ).upper()

        execution_type = str(
            case.get(
                "execution_type",
                "",
            )
        ).upper()

        classification = str(
            item.get(
                "classification",
                "",
            )
        ).upper()

        if (
            execution_type
            == "AUTOMATABLE"
        ):

            if result != "PASS":

                errors.append(
                    f"{case_id}: "
                    "final AUTOMATABLE "
                    f"case result is '{result}', "
                    "expected PASS."
                )

        else:

            if (
                classification
                != "AUTOMATION_BLOCKED"
            ):
                errors.append(
                    f"{case_id}: "
                    "NOT_AUTOMATABLE case "
                    "must be classified "
                    "AUTOMATION_BLOCKED."
                )

        if result in {
            "FAIL",
            "ERROR",
            "BLOCKED",
        }:

            if not classification:

                errors.append(
                    f"{case_id}: "
                    "non-PASS result "
                    "requires classification."
                )

            elif (
                classification
                not in allowed_errors
            ):

                errors.append(
                    f"{case_id}: "
                    "invalid error "
                    "classification "
                    f"'{classification}'."
                )

        if (
            classification
            == "AUTOMATION_BLOCKED"
        ):
            blocked_count += 1

        if (
            classification
            == "TEST_SPEC_CONFLICT"
        ):
            spec_conflict_count += 1

    extra = (
        set(result_map)
        - set(case_map)
    )

    if extra:

        errors.append(
            "Evidence contains unknown "
            "case_id(s): "
            + ", ".join(
                sorted(extra)
            )
        )

    allowed_blocked = int(
        nested_get(
            policy,
            [
                "automation",
                "allowed_automation_blocked",
            ],
            0,
        )
    )

    if (
        blocked_count
        > allowed_blocked
    ):

        errors.append(
            "AUTOMATION_BLOCKED count "
            f"{blocked_count} "
            f"> allowed "
            f"{allowed_blocked}."
        )

    allowed_conflicts = int(
        nested_get(
            policy,
            [
                "test_spec_conflict",
                "allowed_unresolved",
            ],
            0,
        )
    )

    if (
        spec_conflict_count
        > allowed_conflicts
    ):

        errors.append(
            "TEST_SPEC_CONFLICT count "
            f"{spec_conflict_count} "
            f"> allowed "
            f"{allowed_conflicts}."
        )

    return errors


# ============================================================
# Defects
# ============================================================


def defect_detection_source(
    defect: dict[str, Any],
    case_map: dict[
        str,
        dict[str, Any],
    ],
) -> str | None:

    origins: set[str] = set()

    for case_id in as_string_list(
        defect.get(
            "detected_by_cases"
        )
    ):

        case = case_map.get(
            case_id
        )

        if case:

            origins.add(
                str(
                    case.get(
                        "origin",
                        "",
                    )
                ).upper()
            )

    if (
        AI_ORIGIN in origins
        and EXTERNAL_ORIGIN
        in origins
    ):
        return "COMMON_DEFECT"

    if AI_ORIGIN in origins:
        return "AI_ONLY_DEFECT"

    if EXTERNAL_ORIGIN in origins:
        return "EXTERNAL_ONLY_DEFECT"

    return None


def validate_defects(
    evidence: dict[str, Any],
    case_map: dict[
        str,
        dict[str, Any],
    ],
    policy: dict[str, Any],
) -> list[str]:

    errors: list[str] = []

    defects = evidence.get(
        "defects",
        [],
    )

    if not isinstance(
        defects,
        list,
    ):
        return [
            "integration-test-evidence.json "
            "defects must be an array."
        ]

    allowed_errors = set(
        as_string_list(
            nested_get(
                policy,
                [
                    "error_classification",
                    "allowed",
                ],
                [],
            )
        )
    )

    allowed_sources = set(
        as_string_list(
            nested_get(
                policy,
                [
                    "defects",
                    "detection_source_classification",
                    "allowed",
                ],
                [],
            )
        )
    )

    unresolved_allowed = bool(
        nested_get(
            policy,
            [
                "defects",
                "unresolved_allowed",
            ],
            False,
        )
    )

    regression_required = bool(
        nested_get(
            policy,
            [
                "regression",
                "required_after_defect",
            ],
            True,
        )
    )

    ids: set[str] = set()

    for index, defect in enumerate(
        defects,
        start=1,
    ):

        if not isinstance(
            defect,
            dict,
        ):

            errors.append(
                f"defects #{index} "
                "must be an object."
            )

            continue

        defect_id = str(
            defect.get(
                "defect_id",
                "",
            )
        ).strip()

        if not defect_id:
            defect_id = (
                f"defect-{index}"
            )

        if defect_id in ids:

            errors.append(
                f"Duplicate defect_id: "
                f"{defect_id}"
            )

        ids.add(
            defect_id
        )

        classification = str(
            defect.get(
                "classification",
                "",
            )
        ).upper()

        if (
            classification
            not in allowed_errors
        ):

            errors.append(
                f"{defect_id}: "
                "invalid classification "
                f"'{classification}'."
            )

        detected = as_string_list(
            defect.get(
                "detected_by_cases"
            )
        )

        if not detected:

            errors.append(
                f"{defect_id}: "
                "detected_by_cases "
                "is required."
            )

        for case_id in detected:

            if (
                case_id
                not in case_map
            ):

                errors.append(
                    f"{defect_id}: "
                    "unknown detected_by case "
                    f"'{case_id}'."
                )

        if nested_get(
            policy,
            [
                "defects",
                "require_root_cause",
            ],
            True,
        ):

            if not non_empty(
                defect.get(
                    "root_cause"
                )
            ):
                errors.append(
                    f"{defect_id}: "
                    "root_cause is required."
                )

        if nested_get(
            policy,
            [
                "defects",
                "require_error_location_when_identifiable",
            ],
            True,
        ):

            identifiable = bool(
                defect.get(
                    "error_location_identifiable",
                    True,
                )
            )

            if (
                identifiable
                and not non_empty(
                    defect.get(
                        "error_location"
                    )
                )
            ):
                errors.append(
                    f"{defect_id}: "
                    "error_location is required "
                    "when identifiable."
                )

        resolved = bool(
            defect.get(
                "resolved",
                False,
            )
        )

        if (
            not resolved
            and not unresolved_allowed
        ):

            errors.append(
                f"{defect_id}: "
                "defect is unresolved."
            )

        expected_source = (
            defect_detection_source(
                defect,
                case_map,
            )
        )

        actual_source = str(
            defect.get(
                "detection_source",
                "",
            )
        ).upper()

        if expected_source is None:

            errors.append(
                f"{defect_id}: "
                "cannot derive detection "
                "source from "
                "detected_by_cases."
            )

        else:

            if (
                actual_source
                != expected_source
            ):

                errors.append(
                    f"{defect_id}: "
                    "detection_source "
                    f"'{actual_source}' "
                    "!= expected "
                    f"'{expected_source}'."
                )

            if (
                allowed_sources
                and actual_source
                not in allowed_sources
            ):

                errors.append(
                    f"{defect_id}: "
                    "invalid detection_source "
                    f"'{actual_source}'."
                )

        if regression_required:

            rerun = defect.get(
                "rerun",
                {},
            )

            required = {
                "target_cases":
                    nested_get(
                        policy,
                        [
                            "regression",
                            "rerun_failed_case",
                        ],
                        True,
                    ),
                "related_cases":
                    nested_get(
                        policy,
                        [
                            "regression",
                            "rerun_related_cases",
                        ],
                        True,
                    ),
                "full_suite":
                    nested_get(
                        policy,
                        [
                            "regression",
                            "rerun_full_suite",
                        ],
                        True,
                    ),
            }

            for (
                key,
                needed,
            ) in required.items():

                if (
                    needed
                    and str(
                        rerun.get(
                            key,
                            "",
                        )
                    ).upper()
                    != "PASS"
                ):

                    errors.append(
                        f"{defect_id}: "
                        f"rerun.{key} "
                        "must be PASS."
                    )

    return errors


# ============================================================
# Flaky Test
# ============================================================


def validate_flaky_tests(
    evidence: dict[str, Any],
    policy: dict[str, Any],
) -> list[str]:

    if nested_get(
        policy,
        [
            "flaky_test",
            "allowed",
        ],
        False,
    ):
        return []

    errors: list[str] = []

    for item in evidence.get(
        "flaky_tests",
        [],
    ):

        if (
            isinstance(item, dict)
            and not bool(
                item.get(
                    "resolved",
                    False,
                )
            )
        ):

            test = (
                item.get(
                    "case_id"
                )
                or item.get(
                    "test"
                )
                or "unknown"
            )

            errors.append(
                f"Unresolved flaky test: "
                f"{test}"
            )

    return errors


# ============================================================
# Error Report
# ============================================================


def validate_error_report(
    report: dict[str, Any],
    case_map: dict[
        str,
        dict[str, Any],
    ],
    policy: dict[str, Any],
) -> list[str]:

    errors: list[str] = []

    items = report.get(
        "errors",
        [],
    )

    if not isinstance(
        items,
        list,
    ):
        return [
            "error-report.json errors "
            "must be an array."
        ]

    allowed = set(
        as_string_list(
            nested_get(
                policy,
                [
                    "error_classification",
                    "allowed",
                ],
                [],
            )
        )
    )

    by_origin = Counter()
    by_cause = Counter()

    for index, item in enumerate(
        items,
        start=1,
    ):

        if not isinstance(
            item,
            dict,
        ):

            errors.append(
                f"error-report error "
                f"#{index} "
                "must be an object."
            )

            continue

        case_id = str(
            item.get(
                "case_id",
                "",
            )
        ).strip()

        case = case_map.get(
            case_id
        )

        if case is None:

            errors.append(
                "error-report: "
                "unknown case_id "
                f"'{case_id}'."
            )

            continue

        origin = str(
            item.get(
                "origin",
                "",
            )
        ).upper()

        expected_origin = str(
            case.get(
                "origin",
                "",
            )
        ).upper()

        if (
            origin
            != expected_origin
        ):

            errors.append(
                f"{case_id}: "
                "error-report origin "
                "mismatch."
            )

        classification = str(
            item.get(
                "classification",
                "",
            )
        ).upper()

        if (
            classification
            not in allowed
        ):

            errors.append(
                f"{case_id}: "
                "invalid error-report "
                "classification "
                f"'{classification}'."
            )

        if not non_empty(
            item.get(
                "cause"
            )
        ):

            errors.append(
                f"{case_id}: "
                "error-report cause "
                "is required."
            )

        if nested_get(
            policy,
            [
                "reports",
                "require_error_location",
            ],
            True,
        ):

            identifiable = bool(
                item.get(
                    "error_location_identifiable",
                    True,
                )
            )

            if (
                identifiable
                and not non_empty(
                    item.get(
                        "error_location"
                    )
                )
            ):

                errors.append(
                    f"{case_id}: "
                    "error-report "
                    "error_location "
                    "is required when "
                    "identifiable."
                )

        if not bool(
            item.get(
                "resolved",
                False,
            )
        ):

            errors.append(
                f"{case_id}: "
                "error-report contains "
                "unresolved error."
            )

        by_origin[
            origin
        ] += 1

        by_cause[
            classification
        ] += 1

    summary = report.get(
        "summary",
        {},
    )

    if nested_get(
        policy,
        [
            "reports",
            "require_error_count",
        ],
        True,
    ):

        if (
            summary.get(
                "total_errors"
            )
            != len(items)
        ):

            errors.append(
                "error-report "
                "summary.total_errors="
                f"{summary.get('total_errors')!r}, "
                f"expected {len(items)}."
            )

    reported_by_origin = (
        summary.get(
            "errors_by_origin",
            {},
        )
    )

    if isinstance(
        reported_by_origin,
        dict,
    ):

        for origin in [
            AI_ORIGIN,
            EXTERNAL_ORIGIN,
        ]:

            expected = by_origin.get(
                origin,
                0,
            )

            if (
                reported_by_origin.get(
                    origin,
                    0,
                )
                != expected
            ):

                errors.append(
                    "error-report "
                    "errors_by_origin."
                    f"{origin}="
                    f"{reported_by_origin.get(origin, 0)!r}, "
                    f"expected {expected}."
                )

    reported_by_cause = (
        summary.get(
            "errors_by_cause",
            {},
        )
    )

    if isinstance(
        reported_by_cause,
        dict,
    ):

        for (
            classification,
            expected,
        ) in by_cause.items():

            if (
                reported_by_cause.get(
                    classification,
                    0,
                )
                != expected
            ):

                errors.append(
                    "error-report "
                    "errors_by_cause."
                    f"{classification}="
                    f"{reported_by_cause.get(classification, 0)!r}, "
                    f"expected {expected}."
                )

    return errors

def validate_external_input(
    evidence: dict[str, Any],
    policy: dict[str, Any],
) -> list[str]:

    errors: list[str] = []

    external_input = evidence.get(
        "external_input",
        {},
    )

    provided = bool(
        external_input.get(
            "provided",
            False,
        )
    )

    confirmed_without_external = bool(
        external_input.get(
            "user_confirmed_without_external_cases",
            False,
        )
    )

    require_user_decision = bool(
        nested_get(
            policy,
            [
                "external_cases",
                "missing_input",
                "require_user_decision",
            ],
            True,
        )
    )

    allow_implicit = bool(
        nested_get(
            policy,
            [
                "external_cases",
                "missing_input",
                "allow_implicit_no_external_cases",
            ],
            False,
        )
    )

    if (
        not provided
        and require_user_decision
        and not confirmed_without_external
        and not allow_implicit
    ):
        errors.append(
            "External test cases were not provided "
            "and the user did not explicitly confirm "
            "continuation without external cases."
        )

    if (
        provided
        and confirmed_without_external
    ):
        errors.append(
            "external_input is inconsistent: "
            "provided=true and "
            "user_confirmed_without_external_cases=true."
        )

    return errors

# ============================================================
# Environment / Database
# ============================================================


def validate_database_environment(
    evidence: dict[str, Any],
    policy: dict[str, Any],
) -> list[str]:

    errors: list[str] = []

    environment = evidence.get(
        "environment",
        {},
    )

    if (
        nested_get(
            policy,
            [
                "environment",
                "production_environment_allowed",
            ],
            False,
        )
        is False
    ):

        if bool(
            environment.get(
                "production_environment_used",
                False,
            )
        ):
            errors.append(
                "Production environment "
                "was used for "
                "integration testing."
            )

    database = evidence.get(
        "database",
        {},
    )

    if (
        nested_get(
            policy,
            [
                "database",
                "production_database_allowed",
            ],
            False,
        )
        is False
    ):

        if bool(
            database.get(
                "production_database_used",
                False,
            )
        ):
            errors.append(
                "Production database "
                "was used for "
                "integration testing."
            )

    if (
        nested_get(
            policy,
            [
                "database",
                "shared_database_allowed",
            ],
            False,
        )
        is False
    ):

        if bool(
            database.get(
                "shared_database_used",
                False,
            )
        ):
            errors.append(
                "Shared database was used "
                "for integration testing."
            )

    if (
        nested_get(
            policy,
            [
                "database",
                "production_credentials_allowed",
            ],
            False,
        )
        is False
    ):

        if bool(
            database.get(
                "production_credentials_used",
                False,
            )
        ):
            errors.append(
                "Production database "
                "credentials were used."
            )

    if (
        nested_get(
            policy,
            [
                "database",
                "production_data_allowed",
            ],
            False,
        )
        is False
    ):

        if bool(
            database.get(
                "production_data_used",
                False,
            )
        ):
            errors.append(
                "Production data was used."
            )

    if nested_get(
        policy,
        [
            "database",
            "schema_reproducible",
        ],
        True,
    ):

        if (
            database.get(
                "used",
                False,
            )
            and not bool(
                database.get(
                    "schema_reproducible",
                    False,
                )
            )
        ):

            errors.append(
                "Database schema is not "
                "reproducible in "
                "test environment."
            )

    return errors


# ============================================================
# Traceability
# ============================================================


def validate_traceability(
    evidence: dict[str, Any],
    case_map: dict[
        str,
        dict[str, Any],
    ],
    policy: dict[str, Any],
) -> list[str]:

    if not nested_get(
        policy,
        [
            "traceability",
            "enabled",
        ],
        True,
    ):
        return []

    errors: list[str] = []

    trace_items = evidence.get(
        "traceability",
        [],
    )

    if not isinstance(
        trace_items,
        list,
    ):

        return [
            "integration-test-evidence.json "
            "traceability must be an array."
        ]

    trace_map = {
        str(
            item.get(
                "case_id",
                "",
            )
        ).strip(): item
        for item in trace_items
        if (
            isinstance(item, dict)
            and str(
                item.get(
                    "case_id",
                    "",
                )
            ).strip()
        )
    }

    for (
        case_id,
        case,
    ) in case_map.items():

        item = trace_map.get(
            case_id
        )

        if item is None:

            errors.append(
                f"{case_id}: "
                "traceability entry missing."
            )

            continue

        checks = [
            (
                "requirement_id",
                "require_requirement_id",
            ),
            (
                "case_id",
                "require_case_id",
            ),
            (
                "origin",
                "require_case_origin",
            ),
            (
                "integration_point",
                "require_integration_point",
            ),
            (
                "result",
                "require_result",
            ),
        ]

        for (
            field,
            policy_key,
        ) in checks:

            if (
                nested_get(
                    policy,
                    [
                        "traceability",
                        policy_key,
                    ],
                    True,
                )
                and not non_empty(
                    item.get(
                        field
                    )
                )
            ):

                errors.append(
                    f"{case_id}: "
                    f"traceability.{field} "
                    "is required."
                )

        if (
            str(
                item.get(
                    "origin",
                    "",
                )
            ).upper()
            != str(
                case.get(
                    "origin",
                    "",
                )
            ).upper()
        ):

            errors.append(
                f"{case_id}: "
                "traceability origin "
                "does not match plan."
            )

    return errors


# ============================================================
# Full Validation
# ============================================================


def validate(
    policy_path: Path,
    criteria_dir: Path,
    reports_dir: Path,
    plan_path: Path,
    case_comparison_path: Path,
    coverage_gap_path: Path,
    evidence_path: Path,
    error_report_path: Path,
    junit_patterns: list[str],
) -> tuple[
    list[str],
    dict[str, Any],
]:

    errors: list[str] = []

    policy = read_yaml(
        policy_path
    )

    policy_errors = (
        validate_policy(
            policy
        )
    )

    errors.extend(
        policy_errors
    )

    if policy_errors:

        return (
            errors,
            {
                "status":
                    "FAIL",
                "errors":
                    errors,
            },
        )

    criteria_pattern = str(
        nested_get(
            policy,
            [
                "criteria",
                "pattern",
            ],
            "*.criterion.md",
        )
    )

    criteria = discover_criteria(
        criteria_dir,
        criteria_pattern,
    )

    if (
        nested_get(
            policy,
            [
                "criteria",
                "load_all",
            ],
            True,
        )
        and not criteria
    ):

        errors.append(
            "No Integration Test "
            "Criteria found."
        )

    # --------------------------------------------------------
    # Required Reports
    # --------------------------------------------------------

    errors.extend(
        validate_required_reports(
            reports_dir,
            policy,
        )
    )

    # --------------------------------------------------------
    # Test Plan
    # --------------------------------------------------------

    plan = read_json(
        plan_path
    )

    (
        plan_errors,
        case_map,
    ) = validate_plan(
        plan,
        criteria,
        policy,
    )

    errors.extend(
        plan_errors
    )

    # --------------------------------------------------------
    # Required Coverage
    # --------------------------------------------------------

    coverage_report = read_json(
        coverage_gap_path
    )

    (
        coverage_errors,
        required_map,
    ) = validate_required_coverage(
        coverage_report,
        criteria,
    )

    errors.extend(
        coverage_errors
    )

    derived: dict[
        str,
        Any,
    ] = {}

    if (
        case_map
        and required_map
    ):

        (
            derived,
            derive_errors,
        ) = derive_coverage(
            case_map,
            set(
                required_map
            ),
        )

        errors.extend(
            derive_errors
        )

        errors.extend(
            validate_coverage_report(
                coverage_report,
                derived,
                case_map,
                policy,
            )
        )

        # ----------------------------------------------------
        # Case Comparison
        # ----------------------------------------------------

        case_comparison = read_json(
            case_comparison_path
        )

        errors.extend(
            validate_case_comparison(
                case_comparison,
                derived,
            )
        )

    # --------------------------------------------------------
    # Evidence
    # --------------------------------------------------------

    evidence = read_json(
        evidence_path
    )

    errors.extend(
    validate_external_input(
        evidence,
        policy,
    )
)

    errors.extend(
        validate_criteria_coverage(
            evidence,
            criteria,
            policy,
        )
    )

    errors.extend(
        validate_external_integrity(
            evidence,
            case_map,
            policy,
        )
    )

    errors.extend(
        validate_case_results(
            evidence,
            case_map,
            policy,
        )
    )

    errors.extend(
        validate_defects(
            evidence,
            case_map,
            policy,
        )
    )

    errors.extend(
        validate_flaky_tests(
            evidence,
            policy,
        )
    )

    errors.extend(
        validate_database_environment(
            evidence,
            policy,
        )
    )

    errors.extend(
        validate_traceability(
            evidence,
            case_map,
            policy,
        )
    )

    # --------------------------------------------------------
    # Error Report
    # --------------------------------------------------------

    error_report = read_json(
        error_report_path
    )

    errors.extend(
        validate_error_report(
            error_report,
            case_map,
            policy,
        )
    )

    # --------------------------------------------------------
    # JUnit
    # --------------------------------------------------------

    junit_files = find_junit_files(
        junit_patterns
    )

    if not junit_files:

        junit_summary = {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "errors": 0,
            "skipped": 0,
        }

        errors.append(
            "No JUnit XML reports found."
        )

    else:

        junit_summary = parse_junit(
            junit_files
        )

        errors.extend(
            validate_junit(
                junit_summary,
                policy,
            )
        )

    # --------------------------------------------------------
    # Result
    # --------------------------------------------------------

    result = {
        "status": (
            "PASS"
            if not errors
            else "FAIL"
        ),
        "junit":
            junit_summary,
        "criteria":
            sorted(criteria),
        "coverage": (
            {
                key: value
                for (
                    key,
                    value,
                ) in derived.items()
                if key != "sets"
            }
            if derived
            else {}
        ),
        "case_counts": {
            "total":
                len(case_map),

            "ai_initial":
                sum(
                    1
                    for case
                    in case_map.values()
                    if (
                        str(
                            case.get(
                                "origin",
                                "",
                            )
                        ).upper()
                        == AI_ORIGIN
                        and str(
                            case.get(
                                "generation_stage",
                                "",
                            )
                        ).upper()
                        == INITIAL_STAGE
                    )
                ),

            "ai_gap_fill":
                sum(
                    1
                    for case
                    in case_map.values()
                    if (
                        str(
                            case.get(
                                "origin",
                                "",
                            )
                        ).upper()
                        == AI_ORIGIN
                        and str(
                            case.get(
                                "generation_stage",
                                "",
                            )
                        ).upper()
                        == GAP_FILL_STAGE
                    )
                ),

            "external":
                sum(
                    1
                    for case
                    in case_map.values()
                    if (
                        str(
                            case.get(
                                "origin",
                                "",
                            )
                        ).upper()
                        == EXTERNAL_ORIGIN
                    )
                ),
        },
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
            "Validate Integration Test "
            "artifacts against "
            "Integration Test Policy."
        )
    )

    parser.add_argument(
        "--policy",
        default=(
            ".github/skills/"
            "integration-test/"
            "policy/"
            "integration-test-policy.yaml"
        ),
    )

    parser.add_argument(
        "--criteria-dir",
        default=(
            ".github/skills/"
            "integration-test/"
            "criteria"
        ),
    )

    parser.add_argument(
        "--reports-dir",
        default=(
            "reports/"
            "integration-test"
        ),
    )

    parser.add_argument(
        "--plan",
        default=(
            "reports/"
            "integration-test/"
            "integration-test-plan.json"
        ),
    )

    parser.add_argument(
        "--case-comparison",
        default=(
            "reports/"
            "integration-test/"
            "case-comparison.json"
        ),
    )

    parser.add_argument(
        "--coverage-gap",
        default=(
            "reports/"
            "integration-test/"
            "coverage-gap-report.json"
        ),
    )

    parser.add_argument(
        "--evidence",
        default=(
            "reports/"
            "integration-test/"
            "integration-test-evidence.json"
        ),
    )

    parser.add_argument(
        "--error-report",
        default=(
            "reports/"
            "integration-test/"
            "error-report.json"
        ),
    )

    parser.add_argument(
        "--junit",
        action="append",
        default=[
            "reports/"
            "integration-test/"
            "junit.xml"
        ],
        help=(
            "JUnit XML path or glob. "
            "Can be specified "
            "multiple times."
        ),
    )

    parser.add_argument(
        "--output",
        default=(
            "reports/"
            "integration-test/"
            "validation-result.json"
        ),
    )

    return parser.parse_args()


def main() -> int:

    args = parse_args()

    try:

        (
            errors,
            result,
        ) = validate(

            policy_path=Path(
                args.policy
            ),

            criteria_dir=Path(
                args.criteria_dir
            ),

            reports_dir=Path(
                args.reports_dir
            ),

            plan_path=Path(
                args.plan
            ),

            case_comparison_path=Path(
                args.case_comparison
            ),

            coverage_gap_path=Path(
                args.coverage_gap
            ),

            evidence_path=Path(
                args.evidence
            ),

            error_report_path=Path(
                args.error_report
            ),

            junit_patterns=(
                args.junit
            ),
        )

    except (
        FileNotFoundError,
        ValueError,
        json.JSONDecodeError,
        yaml.YAMLError,
        ET.ParseError,
    ) as error:

        print(
            "========================================"
        )

        print(
            " Integration Test Validation"
        )

        print(
            "========================================"
        )

        print()

        print(
            f"[FAIL] {error}"
        )

        return 1

    output_path = Path(
        args.output
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        "========================================"
    )

    print(
        " Integration Test Validation"
    )

    print(
        "========================================"
    )

    print()

    if errors:

        print(
            "[FAIL] Integration Test "
            "validation failed."
        )

        print()

        for (
            index,
            error,
        ) in enumerate(
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
        "[PASS] Integration Test "
        "quality gate passed."
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