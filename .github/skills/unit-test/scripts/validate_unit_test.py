#!/usr/bin/env python3

"""
Unit Test Validator

以下を決定論的に検証する。

- Unit Test Policy
- Test実行結果
- Coverage
- Requirement Coverage
- Test Criteria Coverage
- Regression確認
- DB Test Policy
- 未解決Defect

このValidatorは、
テスト内容そのものの意味的妥当性は判定しない。

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
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import yaml


# ============================================================
# Utility
# ============================================================


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(
            f"File not found: {path}"
        )

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(
            f"File not found: {path}"
        )

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        result = yaml.safe_load(file)

    if not isinstance(result, dict):
        raise ValueError(
            f"Invalid YAML structure: {path}"
        )

    return result


def nested_get(
    source: dict[str, Any],
    path: list[str],
    default: Any = None,
) -> Any:
    current: Any = source

    for key in path:
        if not isinstance(current, dict):
            return default

        if key not in current:
            return default

        current = current[key]

    return current


def is_pass(value: Any) -> bool:
    return str(value).upper() == "PASS"


# ============================================================
# Policy Validation
# ============================================================


def validate_policy(
    policy: dict[str, Any],
) -> list[str]:

    errors: list[str] = []

    required_paths = [
        ["test_result", "required_pass_rate"],
        ["test_result", "allowed_failures"],
        ["test_result", "allowed_errors"],
        ["coverage", "enabled"],
        ["requirement_coverage", "enabled"],
        ["database", "production_database_allowed"],
        ["database", "shared_test_database_allowed"],
        ["regression", "required_after_defect"],
        ["flaky_test", "allowed"],
        ["failure_handling", "unresolved_error_allowed"],
        ["failure_handling", "allow_next_phase_with_failure"],
        ["criteria", "directory"],
        ["criteria", "pattern"],
        ["criteria", "load_all"],
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

    if nested_get(
        policy,
        ["coverage", "enabled"],
        False,
    ):
        thresholds = nested_get(
            policy,
            ["coverage", "thresholds"],
            {},
        )

        for metric in [
            "statements",
            "branches",
            "functions",
            "lines",
        ]:
            if metric not in thresholds:
                errors.append(
                    "Coverage threshold missing: "
                    f"{metric}"
                )

    return errors


# ============================================================
# JUnit XML
# ============================================================


def find_junit_files(
    patterns: list[str],
) -> list[Path]:

    files: set[Path] = set()

    for pattern in patterns:
        for path in glob.glob(
            pattern,
            recursive=True,
        ):
            candidate = Path(path)

            if candidate.is_file():
                files.add(candidate)

    return sorted(files)


def parse_junit(
    files: list[Path],
) -> dict[str, Any]:

    summary = {
        "total": 0,
        "passed": 0,
        "failed": 0,
        "errors": 0,
        "skipped": 0,
        "skipped_tests": [],
    }

    for path in files:
        root = ET.parse(path).getroot()

        for testcase in root.iter(
            "testcase"
        ):
            summary["total"] += 1

            classname = testcase.attrib.get(
                "classname",
                "",
            )

            name = testcase.attrib.get(
                "name",
                "",
            )

            test_id = (
                f"{classname}::{name}"
                if classname
                else name
            )

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

                summary[
                    "skipped_tests"
                ].append(test_id)

            else:
                summary["passed"] += 1

    return summary


def validate_test_result(
    summary: dict[str, Any],
    policy: dict[str, Any],
) -> list[str]:

    errors: list[str] = []

    total = summary["total"]
    passed = summary["passed"]

    if total == 0:
        return [
            "No Unit Tests were executed."
        ]

    pass_rate = (
        passed / total
    ) * 100

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

    if pass_rate < required_pass_rate:
        errors.append(
            f"Test pass rate is {pass_rate:.2f}%, "
            f"required >= {required_pass_rate:.2f}%."
        )

    if summary["failed"] > allowed_failures:
        errors.append(
            f"Failed tests: {summary['failed']}, "
            f"allowed: {allowed_failures}."
        )

    if summary["errors"] > allowed_errors:
        errors.append(
            f"Error tests: {summary['errors']}, "
            f"allowed: {allowed_errors}."
        )

    return errors


# ============================================================
# Skipped Tests
# ============================================================


def validate_skipped_tests(
    summary: dict[str, Any],
    policy: dict[str, Any],
) -> list[str]:

    errors: list[str] = []

    skipped_policy = policy.get(
        "skipped_tests",
        {},
    )

    allowed_count = int(
        skipped_policy.get(
            "allowed",
            0,
        )
    )

    allowlist = set(
        skipped_policy.get(
            "allowlist",
            [],
        )
    )

    unauthorized = [
        test
        for test in summary["skipped_tests"]
        if test not in allowlist
    ]

    if len(unauthorized) > allowed_count:
        errors.append(
            "Unauthorized skipped tests: "
            + ", ".join(unauthorized)
        )

    return errors


# ============================================================
# Coverage
# ============================================================


def parse_coverage_summary(
    path: Path,
) -> dict[str, float]:

    data = read_json(path)

    source = data.get(
        "total",
        data,
    )

    result: dict[str, float] = {}

    for metric in [
        "statements",
        "branches",
        "functions",
        "lines",
    ]:
        value = source.get(metric)

        if isinstance(value, dict):
            value = value.get("pct")

        if value is None:
            raise ValueError(
                f"Coverage metric missing: {metric}"
            )

        result[metric] = float(value)

    return result


def validate_coverage(
    coverage: dict[str, float],
    policy: dict[str, Any],
) -> list[str]:

    if not nested_get(
        policy,
        ["coverage", "enabled"],
        False,
    ):
        return []

    errors: list[str] = []

    thresholds = nested_get(
        policy,
        ["coverage", "thresholds"],
        {},
    )

    for metric in [
        "statements",
        "branches",
        "functions",
        "lines",
    ]:
        actual = coverage[metric]
        required = float(
            thresholds[metric]
        )

        if actual < required:
            errors.append(
                f"Coverage {metric}: "
                f"{actual:.2f}% "
                f"< required {required:.2f}%."
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

        result.add(name)

    return result


def validate_criteria_coverage(
    evidence: dict[str, Any],
    criteria: set[str],
    policy: dict[str, Any],
) -> list[str]:

    if not nested_get(
        policy,
        ["criteria", "load_all"],
        True,
    ):
        return []

    errors: list[str] = []

    reported = {
        item.get("criterion"): item
        for item in evidence.get(
            "criteria_coverage",
            []
        )
        if item.get("criterion")
    }

    for criterion in sorted(criteria):
        item = reported.get(criterion)

        if item is None:
            errors.append(
                f"Criterion not evaluated: "
                f"{criterion}"
            )
            continue

        applicable = item.get(
            "applicable",
            True,
        )

        result = str(
            item.get(
                "result",
                "",
            )
        ).upper()

        if applicable:
            if result != "PASS":
                errors.append(
                    f"Criterion failed: "
                    f"{criterion}"
                )

        else:
            if result != "NOT_APPLICABLE":
                errors.append(
                    f"Criterion {criterion}: "
                    "applicable=false requires "
                    "result=NOT_APPLICABLE."
                )

            if not str(
                item.get(
                    "reason",
                    "",
                )
            ).strip():
                errors.append(
                    f"Criterion {criterion}: "
                    "NOT_APPLICABLE requires reason."
                )

    return errors


# ============================================================
# Requirement Coverage
# ============================================================


def validate_requirement_coverage(
    evidence: dict[str, Any],
    policy: dict[str, Any],
) -> list[str]:

    if not nested_get(
        policy,
        ["requirement_coverage", "enabled"],
        False,
    ):
        return []

    errors: list[str] = []

    require_all = bool(
        nested_get(
            policy,
            [
                "requirement_coverage",
                "require_all_unit_testable_requirements",
            ],
            True,
        )
    )

    requirements = evidence.get(
        "requirement_coverage",
        []
    )

    if require_all and not requirements:
        return [
            "Requirement Coverage evidence "
            "is empty."
        ]

    for item in requirements:
        requirement = item.get(
            "requirement"
        )

        unit_testable = item.get(
            "unit_testable",
            True,
        )

        if not requirement:
            errors.append(
                "Requirement Coverage entry "
                "has no Requirement ID."
            )
            continue

        if not unit_testable:
            reason = str(
                item.get(
                    "reason",
                    "",
                )
            ).strip()

            if not reason:
                errors.append(
                    f"{requirement}: "
                    "unit_testable=false "
                    "requires reason."
                )

            continue

        tests = item.get(
            "tests",
            []
        )

        if not tests:
            errors.append(
                f"{requirement}: "
                "no Unit Test mapped."
            )
            continue

        if not any(
            is_pass(
                test.get("result")
            )
            for test in tests
        ):
            errors.append(
                f"{requirement}: "
                "no mapped Unit Test passed."
            )

    return errors


# ============================================================
# Regression / Defects
# ============================================================


def validate_defects(
    evidence: dict[str, Any],
    policy: dict[str, Any],
) -> list[str]:

    defects = evidence.get(
        "defects",
        []
    )

    errors: list[str] = []

    regression_required = bool(
        nested_get(
            policy,
            ["regression", "required_after_defect"],
            True,
        )
    )

    unresolved_allowed = bool(
        nested_get(
            policy,
            [
                "failure_handling",
                "unresolved_error_allowed",
            ],
            False,
        )
    )

    for index, defect in enumerate(
        defects,
        start=1,
    ):
        defect_id = defect.get(
            "id",
            f"defect-{index}",
        )

        resolved = defect.get(
            "resolved",
            False,
        )

        if (
            not resolved
            and not unresolved_allowed
        ):
            errors.append(
                f"{defect_id}: "
                "defect is unresolved."
            )

        if not regression_required:
            continue

        if not defect.get(
            "regression_test"
        ):
            errors.append(
                f"{defect_id}: "
                "Regression Test is missing."
            )

        rerun = defect.get(
            "rerun",
            {},
        )

        required_reruns = {
            "target_test":
                nested_get(
                    policy,
                    [
                        "regression",
                        "rerun_failed_test",
                    ],
                    True,
                ),
            "related_tests":
                nested_get(
                    policy,
                    [
                        "regression",
                        "rerun_related_tests",
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

        for key, required in (
            required_reruns.items()
        ):
            if (
                required
                and not is_pass(
                    rerun.get(key)
                )
            ):
                errors.append(
                    f"{defect_id}: "
                    f"Regression rerun "
                    f"'{key}' is not PASS."
                )

    return errors


# ============================================================
# Database Policy
# ============================================================


def validate_database_tests(
    evidence: dict[str, Any],
    policy: dict[str, Any],
) -> list[str]:

    errors: list[str] = []

    production_allowed = bool(
        nested_get(
            policy,
            [
                "database",
                "production_database_allowed",
            ],
            False,
        )
    )

    shared_allowed = bool(
        nested_get(
            policy,
            [
                "database",
                "shared_test_database_allowed",
            ],
            False,
        )
    )

    for item in evidence.get(
        "database_tests",
        []
    ):
        target = item.get(
            "target",
            "unknown",
        )

        if (
            item.get(
                "production_database_used",
                False,
            )
            and not production_allowed
        ):
            errors.append(
                f"{target}: "
                "Production Database was used."
            )

        if (
            item.get(
                "shared_database_used",
                False,
            )
            and not shared_allowed
        ):
            errors.append(
                f"{target}: "
                "Shared Test Database was used."
            )

        strategy = str(
            item.get(
                "strategy",
                "",
            )
        ).upper()

        if strategy not in {
            "MOCK",
            "CONTAINER",
            "NOT_APPLICABLE",
        }:
            errors.append(
                f"{target}: "
                f"invalid database strategy "
                f"'{strategy}'."
            )

    return errors


# ============================================================
# Flaky Test Evidence
# ============================================================


def validate_flaky_tests(
    evidence: dict[str, Any],
    policy: dict[str, Any],
) -> list[str]:

    if nested_get(
        policy,
        ["flaky_test", "allowed"],
        False,
    ):
        return []

    errors: list[str] = []

    for test in evidence.get(
        "flaky_tests",
        []
    ):
        if not test.get(
            "resolved",
            False,
        ):
            errors.append(
                "Unresolved flaky test: "
                f"{test.get('test', 'unknown')}"
            )

    return errors


# ============================================================
# Full Validation
# ============================================================


def validate(
    policy_path: Path,
    criteria_dir: Path,
    junit_patterns: list[str],
    coverage_path: Path,
    evidence_path: Path,
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

    errors.extend(policy_errors)

    if policy_errors:
        return errors, {}

    # --------------------------
    # Tests
    # --------------------------

    junit_files = find_junit_files(
        junit_patterns
    )

    if not junit_files:
        errors.append(
            "No JUnit XML reports found."
        )

        test_summary = {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "errors": 0,
            "skipped": 0,
            "skipped_tests": [],
        }

    else:
        test_summary = parse_junit(
            junit_files
        )

        errors.extend(
            validate_test_result(
                test_summary,
                policy,
            )
        )

        errors.extend(
            validate_skipped_tests(
                test_summary,
                policy,
            )
        )

    # --------------------------
    # Coverage
    # --------------------------

    coverage: dict[str, float] = {}

    if nested_get(
        policy,
        ["coverage", "enabled"],
        False,
    ):
        coverage = parse_coverage_summary(
            coverage_path
        )

        errors.extend(
            validate_coverage(
                coverage,
                policy,
            )
        )

    # --------------------------
    # Evidence
    # --------------------------

    evidence = read_json(
        evidence_path
    )

    criteria_pattern = str(
        nested_get(
            policy,
            ["criteria", "pattern"],
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
            ["criteria", "load_all"],
            True,
        )
        and not criteria
    ):
        errors.append(
            "No Unit Test Criteria found."
        )

    errors.extend(
        validate_criteria_coverage(
            evidence,
            criteria,
            policy,
        )
    )

    errors.extend(
        validate_requirement_coverage(
            evidence,
            policy,
        )
    )

    errors.extend(
        validate_defects(
            evidence,
            policy,
        )
    )

    errors.extend(
        validate_database_tests(
            evidence,
            policy,
        )
    )

    errors.extend(
        validate_flaky_tests(
            evidence,
            policy,
        )
    )

    result = {
        "status": (
            "PASS"
            if not errors
            else "FAIL"
        ),
        "test_summary": test_summary,
        "coverage": coverage,
        "criteria": sorted(criteria),
        "errors": errors,
    }

    return errors, result


# ============================================================
# CLI
# ============================================================


def parse_args() -> argparse.Namespace:

    parser = argparse.ArgumentParser(
        description=(
            "Validate Unit Test results "
            "against Unit Test Policy."
        )
    )

    parser.add_argument(
        "--policy",
        default=(
            ".github/skills/unit-test/"
            "policy/unit-test-policy.yaml"
        ),
    )

    parser.add_argument(
        "--criteria-dir",
        default=(
            ".github/skills/unit-test/"
            "criteria"
        ),
    )

    parser.add_argument(
        "--junit",
        action="append",
        default=[
            "reports/unit-test/junit.xml"
        ],
        help=(
            "JUnit XML path or glob. "
            "Can be specified multiple times."
        ),
    )

    parser.add_argument(
        "--coverage",
        default=(
            "reports/unit-test/"
            "coverage-summary.json"
        ),
    )

    parser.add_argument(
        "--evidence",
        default=(
            "reports/unit-test/"
            "unit-test-evidence.json"
        ),
    )

    parser.add_argument(
        "--output",
        default=(
            "reports/unit-test/"
            "validation-result.json"
        ),
    )

    return parser.parse_args()


def main() -> int:

    args = parse_args()

    try:
        errors, result = validate(
            policy_path=Path(
                args.policy
            ),
            criteria_dir=Path(
                args.criteria_dir
            ),
            junit_patterns=args.junit,
            coverage_path=Path(
                args.coverage
            ),
            evidence_path=Path(
                args.evidence
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
            " Unit Test Validation"
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
        " Unit Test Validation"
    )
    print(
        "========================================"
    )
    print()

    if errors:
        print(
            "[FAIL] Unit Test validation failed."
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
            f"Total errors: {len(errors)}"
        )
        print(
            f"Result: {output_path}"
        )

        return 1

    print(
        "[PASS] Unit Test quality gate passed."
    )
    print(
        f"Result: {output_path}"
    )

    return 0


if __name__ == "__main__":
    sys.exit(
        main()
    )