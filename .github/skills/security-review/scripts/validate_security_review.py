#!/usr/bin/env python3
"""
Security Review Validator

Security Review Agentが生成したReportを、
security-review-policy.yaml および Criteria定義と照合し、
決定論的にSecurity Gate判定する。

Checks:
- Policy structure
- Audit Scope
- Required Criteria discovery
- Criteria evaluation completeness
- PASS / NOT_APPLICABLE / FAIL consistency
- NOT_APPLICABLE reason
- Issue classification
- Severity
- Recommended route
- Blocking issue
- Required reports
- Scope-dependent upstream validator PASS
- Summary consistency
- Report status consistency
- Security report内への明示的なSecret値記録の禁止

Exit Code:
    0: PASS
    1: FAIL

Dependency:
    PyYAML
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml


AUDIT_SCOPES = {
    "REQUIREMENTS",
    "ARCHITECTURE",
    "IMPLEMENTATION",
    "UNIT_TEST",
    "INTEGRATION_TEST",
    "FULL",
}

SCOPE_LEVEL = {
    "REQUIREMENTS": 1,
    "ARCHITECTURE": 2,
    "IMPLEMENTATION": 3,
    "UNIT_TEST": 4,
    "INTEGRATION_TEST": 5,
    "FULL": 5,
}

VALID_ROUTES = {
    "REQUIREMENTS",
    "ARCHITECTURE",
    "IMPLEMENTATION",
    "UNIT_TEST",
    "INTEGRATION_TEST",
}

FORBIDDEN_SECRET_FIELD_NAMES = {
    "secret",
    "secret_value",
    "password",
    "passwd",
    "credential",
    "credential_value",
    "api_key",
    "apikey",
    "access_key",
    "secret_access_key",
    "token",
    "refresh_token",
    "client_secret",
    "private_key",
}

FORBIDDEN_SECRET_TEXT_PATTERNS = [
    re.compile(
        r"(?i)\b(?:api[_-]?key|client[_-]?secret|password|passwd|"
        r"secret[_-]?access[_-]?key|access[_-]?token|refresh[_-]?token)"
        r"\s*[:=]\s*[^\s,;]{4,}"
    ),
]


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


def nested_get(source: dict[str, Any], keys: list[str], default: Any = None) -> Any:
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
    return [str(item).strip() for item in as_list(value) if str(item).strip()]


def scope_includes(scope: str, target: str) -> bool:
    return SCOPE_LEVEL[scope] >= SCOPE_LEVEL[target]


def write_result(path: Path, result: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def validate_policy(policy: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    required_paths = [
        ["audit", "allowed_scopes"],
        ["audit", "allow_unresolved_blocking_issue"],
        ["criteria", "directory"],
        ["criteria", "pattern"],
        ["criteria", "load_all"],
        ["criteria", "allowed_results"],
        ["criteria", "require_all_applicable_pass"],
        ["criteria", "require_reason_when_not_applicable"],
        ["security", "authentication", "require_when_applicable"],
        ["security", "authorization", "require_when_applicable"],
        ["security", "secrets", "allow_hardcoded_secret"],
        ["security", "input_validation", "require_at_trust_boundary"],
        ["security", "injection", "allow_material_injection_risk"],
        ["security", "data_protection", "allow_unnecessary_sensitive_data_exposure"],
        ["security", "error_logging", "allow_internal_detail_external_exposure"],
        ["security", "dependency_configuration", "allow_production_security_bypass"],
        ["security", "test", "require_applicable_security_behavior_test"],
        ["cross_phase", "require_security_consistency"],
        ["severity", "allowed"],
        ["severity", "blocking"],
        ["severity", "advisory"],
        ["issues", "allow_unresolved_blocking_issue"],
        ["issues", "classifications"],
        ["routing"],
        ["reports", "directory"],
        ["reports", "required"],
    ]

    for keys in required_paths:
        if nested_get(policy, keys, None) is None:
            errors.append("Policy missing required setting: " + ".".join(keys))

    allowed_scopes = {
        value.upper()
        for value in as_string_list(nested_get(policy, ["audit", "allowed_scopes"], []))
    }
    unknown_scopes = allowed_scopes - AUDIT_SCOPES
    if unknown_scopes:
        errors.append(
            "Policy contains unknown audit scope(s): "
            + ", ".join(sorted(unknown_scopes))
        )

    allowed_results = {
        value.upper()
        for value in as_string_list(
            nested_get(policy, ["criteria", "allowed_results"], [])
        )
    }
    required_results = {"PASS", "NOT_APPLICABLE", "FAIL"}
    if not required_results.issubset(allowed_results):
        errors.append(
            "criteria.allowed_results must include PASS, NOT_APPLICABLE and FAIL."
        )

    allowed_severity = {
        value.upper()
        for value in as_string_list(nested_get(policy, ["severity", "allowed"], []))
    }
    blocking = {
        value.upper()
        for value in as_string_list(nested_get(policy, ["severity", "blocking"], []))
    }
    advisory = {
        value.upper()
        for value in as_string_list(nested_get(policy, ["severity", "advisory"], []))
    }

    if not blocking.issubset(allowed_severity):
        errors.append(
            "severity.blocking contains values not present in severity.allowed."
        )
    if not advisory.issubset(allowed_severity):
        errors.append(
            "severity.advisory contains values not present in severity.allowed."
        )

    classifications = {
        value.upper()
        for value in as_string_list(nested_get(policy, ["issues", "classifications"], []))
    }
    routing = nested_get(policy, ["routing"], {})

    if not isinstance(routing, dict):
        errors.append("Policy routing must be a mapping.")
    else:
        for classification in sorted(classifications):
            if classification not in routing:
                errors.append(
                    "Policy routing missing for classification: "
                    f"{classification}"
                )

    return errors


def discover_criteria(criteria_dir: Path, pattern: str) -> set[str]:
    if not criteria_dir.exists():
        return set()

    result: set[str] = set()

    for path in criteria_dir.glob(pattern):
        if not path.is_file():
            continue
        name = path.name
        if name.endswith(".criterion.md"):
            name = name[:-len(".criterion.md")]
        result.add(name)

    return result


def criterion_scope_applicable(criterion: str, scope: str) -> bool:
    minimum_scope = {
        "authentication-authorization": "REQUIREMENTS",
        "secrets-credentials": "ARCHITECTURE",
        "input-validation-injection": "REQUIREMENTS",
        "data-protection": "REQUIREMENTS",
        "error-logging": "REQUIREMENTS",
        "dependency-configuration": "ARCHITECTURE",
        "security-test-coverage": "UNIT_TEST",
        "cross-phase-security-consistency": "ARCHITECTURE",
    }

    minimum = minimum_scope.get(criterion)
    if minimum is None:
        return True
    return scope_includes(scope, minimum)


def validate_criteria_results(
    report: dict[str, Any],
    criteria: set[str],
    policy: dict[str, Any],
    scope: str,
) -> tuple[list[str], dict[str, int]]:
    errors: list[str] = []

    results = report.get("criteria_results")
    if not isinstance(results, list):
        return (
            ["security-review-report.json must contain criteria_results array."],
            {"total": 0, "pass": 0, "not_applicable": 0, "fail": 0},
        )

    allowed_results = {
        value.upper()
        for value in as_string_list(
            nested_get(policy, ["criteria", "allowed_results"], [])
        )
    }

    reported: dict[str, dict[str, Any]] = {}

    for index, item in enumerate(results, start=1):
        if not isinstance(item, dict):
            errors.append(f"criteria_results #{index} must be an object.")
            continue

        criterion = str(item.get("criterion", "")).strip()
        if not criterion:
            errors.append(f"criteria_results #{index}: criterion is required.")
            continue

        if criterion in reported:
            errors.append(f"Duplicate criterion result: {criterion}")
            continue

        reported[criterion] = item

    if bool(nested_get(policy, ["criteria", "load_all"], True)):
        for criterion in sorted(criteria):
            if criterion not in reported:
                errors.append(f"Criterion not evaluated: {criterion}")

    extra = set(reported) - criteria
    if extra:
        errors.append(
            "Report contains unknown criterion(s): "
            + ", ".join(sorted(extra))
        )

    counts = {
        "total": 0,
        "pass": 0,
        "not_applicable": 0,
        "fail": 0,
    }

    require_all_applicable_pass = bool(
        nested_get(policy, ["criteria", "require_all_applicable_pass"], True)
    )
    require_na_reason = bool(
        nested_get(policy, ["criteria", "require_reason_when_not_applicable"], True)
    )

    for criterion in sorted(criteria):
        item = reported.get(criterion)
        if item is None:
            continue

        counts["total"] += 1

        result = str(item.get("result", "")).upper()
        applicable = bool(item.get("applicable", True))
        reason = item.get("reason")

        if result not in allowed_results:
            errors.append(f"{criterion}: invalid result '{result}'.")
            continue

        if result == "PASS":
            counts["pass"] += 1
        elif result == "NOT_APPLICABLE":
            counts["not_applicable"] += 1
        elif result == "FAIL":
            counts["fail"] += 1

        if applicable:
            if result == "NOT_APPLICABLE":
                errors.append(
                    f"{criterion}: applicable=true cannot be NOT_APPLICABLE."
                )
            if require_all_applicable_pass and result != "PASS":
                errors.append(
                    f"Applicable criterion is not PASS: {criterion}"
                )
        else:
            if result != "NOT_APPLICABLE":
                errors.append(
                    f"{criterion}: applicable=false requires NOT_APPLICABLE."
                )
            if require_na_reason and not non_empty(reason):
                errors.append(
                    f"{criterion}: NOT_APPLICABLE requires reason."
                )

        deterministic_scope_applicable = criterion_scope_applicable(
            criterion,
            scope,
        )
        if not deterministic_scope_applicable and applicable:
            errors.append(
                f"{criterion}: criterion is outside "
                f"audit_scope={scope} but was marked applicable=true."
            )

    return errors, counts


def validate_no_secret_values(report: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    def walk(value: Any, path: str) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                key_name = str(key)
                normalized_key = key_name.strip().lower()
                current_path = f"{path}.{key_name}" if path else key_name

                if normalized_key in FORBIDDEN_SECRET_FIELD_NAMES and non_empty(child):
                    errors.append(
                        "Security report must not contain secret values in field: "
                        f"{current_path}"
                    )

                walk(child, current_path)

        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, f"{path}[{index}]")

        elif isinstance(value, str):
            for pattern in FORBIDDEN_SECRET_TEXT_PATTERNS:
                if pattern.search(value):
                    errors.append(
                        "Security report may contain a raw secret value at: "
                        f"{path}"
                    )
                    break

    walk(report, "")
    return errors


def validate_required_reports(
    reports_dir: Path,
    policy: dict[str, Any],
) -> list[str]:
    errors: list[str] = []

    for name in as_string_list(
        nested_get(policy, ["reports", "required"], [])
    ):
        path = reports_dir / name

        if not path.exists():
            errors.append(f"Required report missing: {path}")
        elif path.is_file() and path.stat().st_size == 0:
            errors.append(f"Required report is empty: {path}")

    return errors


def validate_report_header(
    report: dict[str, Any],
    policy: dict[str, Any],
) -> tuple[list[str], str]:
    errors: list[str] = []

    scope = str(report.get("audit_scope", "")).upper()
    allowed_scopes = {
        value.upper()
        for value in as_string_list(
            nested_get(policy, ["audit", "allowed_scopes"], [])
        )
    }

    if scope not in AUDIT_SCOPES:
        errors.append(f"Invalid or missing audit_scope: {scope!r}")
    elif allowed_scopes and scope not in allowed_scopes:
        errors.append(
            f"audit_scope '{scope}' is not allowed by policy."
        )

    status = str(report.get("status", "")).upper()
    if status not in {"PASS", "FAIL", "BLOCKED"}:
        errors.append(f"Invalid or missing report status: {status!r}")

    return errors, scope


def validate_issues(
    report: dict[str, Any],
    policy: dict[str, Any],
) -> tuple[list[str], dict[str, int]]:
    errors: list[str] = []

    issues = report.get("issues", [])
    if not isinstance(issues, list):
        return (
            ["security-review-report.json issues must be an array."],
            {"total": 0, "blocking": 0, "unresolved": 0},
        )

    allowed_classifications = {
        value.upper()
        for value in as_string_list(
            nested_get(policy, ["issues", "classifications"], [])
        )
    }
    allowed_severity = {
        value.upper()
        for value in as_string_list(
            nested_get(policy, ["severity", "allowed"], [])
        )
    }
    blocking_severity = {
        value.upper()
        for value in as_string_list(
            nested_get(policy, ["severity", "blocking"], [])
        )
    }
    routing = nested_get(policy, ["routing"], {})

    counts = {
        "total": 0,
        "blocking": 0,
        "unresolved": 0,
    }
    issue_ids: set[str] = set()

    for index, issue in enumerate(issues, start=1):
        if not isinstance(issue, dict):
            errors.append(f"Issue #{index} must be an object.")
            continue

        counts["total"] += 1

        issue_id = str(issue.get("issue_id", "")).strip()
        if not issue_id:
            errors.append(f"Issue #{index}: issue_id is required.")
        elif issue_id in issue_ids:
            errors.append(f"Duplicate issue_id: {issue_id}")
        else:
            issue_ids.add(issue_id)

        classification = str(issue.get("classification", "")).upper()
        if classification not in allowed_classifications:
            errors.append(
                f"{issue_id or index}: invalid classification '{classification}'."
            )

        severity = str(issue.get("severity", "")).upper()
        if severity not in allowed_severity:
            errors.append(
                f"{issue_id or index}: invalid severity '{severity}'."
            )

        if not non_empty(issue.get("description")):
            errors.append(
                f"{issue_id or index}: description is required."
            )

        if not non_empty(issue.get("evidence")):
            errors.append(
                f"{issue_id or index}: evidence is required."
            )

        recommended_route = str(
            issue.get("recommended_route", "")
        ).upper()

        expected_route = (
            str(routing.get(classification, "")).upper()
            if isinstance(routing, dict)
            else ""
        )

        if expected_route == "ROOT_CAUSE":
            if recommended_route not in VALID_ROUTES:
                errors.append(
                    f"{issue_id or index}: recommended_route must be "
                    "a concrete root-cause phase for classification "
                    f"{classification}."
                )
        elif expected_route:
            if recommended_route != expected_route:
                errors.append(
                    f"{issue_id or index}: recommended_route "
                    f"'{recommended_route}' != policy route "
                    f"'{expected_route}'."
                )
        else:
            errors.append(
                f"{issue_id or index}: no routing policy found for "
                f"{classification}."
            )

        resolved = bool(issue.get("resolved", False))
        if not resolved:
            counts["unresolved"] += 1
            if severity in blocking_severity:
                counts["blocking"] += 1

    allow_unresolved_blocking = bool(
        nested_get(
            policy,
            ["issues", "allow_unresolved_blocking_issue"],
            False,
        )
    )

    if counts["blocking"] > 0 and not allow_unresolved_blocking:
        errors.append(
            "Unresolved blocking Security Review "
            f"Issue(s): {counts['blocking']}"
        )

    return errors, counts


def read_optional_validation(
    path: Path,
    required: bool,
    label: str,
) -> tuple[list[str], dict[str, Any] | None]:
    if not path.exists():
        if required:
            return (
                [f"{label} validation result missing: {path}"],
                None,
            )
        return [], None

    try:
        data = read_json(path)
    except (
        ValueError,
        json.JSONDecodeError,
    ) as error:
        return (
            [f"{label} validation result could not be read: {error}"],
            None,
        )

    status = str(data.get("status", "")).upper()
    if status != "PASS":
        return (
            [
                f"{label} validation-result status is not PASS: "
                f"{status!r}"
            ],
            data,
        )

    return [], data


def validate_upstream_validators(
    scope: str,
    unit_validation_path: Path,
    integration_validation_path: Path,
) -> list[str]:
    errors: list[str] = []

    if scope not in AUDIT_SCOPES:
        return errors

    checks: list[tuple[Path, str]] = []

    if scope_includes(scope, "UNIT_TEST"):
        checks.append((unit_validation_path, "Unit Test"))

    if scope_includes(scope, "INTEGRATION_TEST"):
        checks.append((integration_validation_path, "Integration Test"))

    for path, label in checks:
        validation_errors, _ = read_optional_validation(
            path=path,
            required=True,
            label=label,
        )
        errors.extend(validation_errors)

    return errors


def validate_summary(
    report: dict[str, Any],
    criteria_counts: dict[str, int],
    issue_counts: dict[str, int],
) -> list[str]:
    errors: list[str] = []

    summary = report.get("summary")
    if not isinstance(summary, dict):
        return [
            "security-review-report.json summary must be an object."
        ]

    expected = {
        "criteria_total": criteria_counts["total"],
        "criteria_pass": criteria_counts["pass"],
        "criteria_not_applicable": criteria_counts["not_applicable"],
        "criteria_fail": criteria_counts["fail"],
        "issues_total": issue_counts["total"],
        "blocking_issues": issue_counts["blocking"],
    }

    for key, expected_value in expected.items():
        actual = summary.get(key)
        if actual != expected_value:
            errors.append(
                f"summary.{key}={actual!r}, expected {expected_value}."
            )

    return errors


def validate_report_status(
    report: dict[str, Any],
    criteria_counts: dict[str, int],
    issue_counts: dict[str, int],
    current_errors: list[str],
) -> list[str]:
    errors: list[str] = []

    status = str(report.get("status", "")).upper()

    if status == "PASS":
        if criteria_counts["fail"] > 0:
            errors.append(
                "security-review-report.json status is PASS but criteria FAIL exists."
            )

        if issue_counts["blocking"] > 0:
            errors.append(
                "security-review-report.json status is PASS but unresolved "
                "blocking Security Issue exists."
            )

        if current_errors:
            errors.append(
                "security-review-report.json reports PASS, but deterministic "
                "validation found errors."
            )

    return errors


def validate(
    repo_root: Path,
    policy_path: Path,
    criteria_dir: Path,
    report_path: Path,
    reports_dir: Path,
    unit_validation_path: Path,
    integration_validation_path: Path,
) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []

    policy = read_yaml(policy_path)

    policy_errors = validate_policy(policy)
    errors.extend(policy_errors)

    if policy_errors:
        return (
            errors,
            {
                "status": "FAIL",
                "errors": errors,
            },
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
        bool(
            nested_get(
                policy,
                ["criteria", "load_all"],
                True,
            )
        )
        and not criteria
    ):
        errors.append("No Security Review Criteria found.")

    errors.extend(
        validate_required_reports(
            reports_dir,
            policy,
        )
    )

    report = read_json(report_path)

    header_errors, scope = validate_report_header(
        report,
        policy,
    )
    errors.extend(header_errors)

    if scope not in AUDIT_SCOPES:
        return (
            errors,
            {
                "status": "FAIL",
                "errors": errors,
            },
        )

    errors.extend(
        validate_no_secret_values(report)
    )

    errors.extend(
        validate_upstream_validators(
            scope=scope,
            unit_validation_path=unit_validation_path,
            integration_validation_path=integration_validation_path,
        )
    )

    criteria_errors, criteria_counts = validate_criteria_results(
        report=report,
        criteria=criteria,
        policy=policy,
        scope=scope,
    )
    errors.extend(criteria_errors)

    issue_errors, issue_counts = validate_issues(
        report,
        policy,
    )
    errors.extend(issue_errors)

    errors.extend(
        validate_summary(
            report,
            criteria_counts,
            issue_counts,
        )
    )

    status_errors = validate_report_status(
        report=report,
        criteria_counts=criteria_counts,
        issue_counts=issue_counts,
        current_errors=list(errors),
    )
    errors.extend(status_errors)

    result = {
        "status": "PASS" if not errors else "FAIL",
        "audit_scope": scope,
        "criteria": {
            "discovered": sorted(criteria),
            "total": criteria_counts["total"],
            "pass": criteria_counts["pass"],
            "not_applicable": criteria_counts["not_applicable"],
            "fail": criteria_counts["fail"],
        },
        "issues": {
            "total": issue_counts["total"],
            "unresolved": issue_counts["unresolved"],
            "blocking": issue_counts["blocking"],
        },
        "errors": errors,
    }

    return errors, result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate Security Review report against policy, criteria "
            "and upstream validator results."
        )
    )

    parser.add_argument("--repo-root", default=".")

    parser.add_argument(
        "--policy",
        default=(
            ".github/skills/security-review/"
            "policy/security-review-policy.yaml"
        ),
    )

    parser.add_argument(
        "--criteria-dir",
        default=(
            ".github/skills/security-review/criteria"
        ),
    )

    parser.add_argument(
        "--report",
        default=(
            "reports/security-review/"
            "security-review-report.json"
        ),
    )

    parser.add_argument(
        "--reports-dir",
        default="reports/security-review",
    )

    parser.add_argument(
        "--unit-validation",
        default=(
            "reports/unit-test/"
            "validation-result.json"
        ),
    )

    parser.add_argument(
        "--integration-validation",
        default=(
            "reports/integration-test/"
            "validation-result.json"
        ),
    )

    parser.add_argument(
        "--output",
        default=(
            "reports/security-review/"
            "validation-result.json"
        ),
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    repo_root = Path(args.repo_root).resolve()

    def resolve(value: str) -> Path:
        path = Path(value)
        if path.is_absolute():
            return path
        return repo_root / path

    output_path = resolve(args.output)

    try:
        errors, result = validate(
            repo_root=repo_root,
            policy_path=resolve(args.policy),
            criteria_dir=resolve(args.criteria_dir),
            report_path=resolve(args.report),
            reports_dir=resolve(args.reports_dir),
            unit_validation_path=resolve(args.unit_validation),
            integration_validation_path=resolve(args.integration_validation),
        )

    except (
        FileNotFoundError,
        ValueError,
        json.JSONDecodeError,
        yaml.YAMLError,
    ) as error:
        result = {
            "status": "FAIL",
            "errors": [str(error)],
        }

        write_result(output_path, result)

        print("========================================")
        print(" Security Review Validation")
        print("========================================")
        print()
        print(f"[FAIL] {error}")
        print(f"Result: {output_path}")

        return 1

    write_result(output_path, result)

    print("========================================")
    print(" Security Review Validation")
    print("========================================")
    print()

    if errors:
        print("[FAIL] Security Review validation failed.")
        print()

        for index, error in enumerate(errors, start=1):
            print(f"{index}. {error}")

        print()
        print(f"Total errors: {len(errors)}")
        print(f"Result: {output_path}")

        return 1

    print("[PASS] Security Review security gate passed.")
    print(f"Result: {output_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
