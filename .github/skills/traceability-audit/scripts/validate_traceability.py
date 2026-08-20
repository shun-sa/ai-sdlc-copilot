#!/usr/bin/env python3
"""
Traceability Validator

Traceability Auditor が生成した監査Reportを、Repository内の実Artifactと
Test Evidenceに照合して決定論的にQuality Gate判定する。

Exit Code:
    0: PASS
    1: FAIL

Dependency:
    PyYAML

Notes:
- 「対応内容が意味的に正しいか」は Traceability Auditor が監査する。
- 本Validatorは参照実在性、構造、Coverage、Policy整合を機械的に検証する。
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
    "ARCHITECTURE",
    "IMPLEMENTATION",
    "UNIT_TEST",
    "INTEGRATION_TEST",
    "FULL",
}

SCOPE_LEVEL = {
    "ARCHITECTURE": 1,
    "IMPLEMENTATION": 2,
    "UNIT_TEST": 3,
    "INTEGRATION_TEST": 4,
    "FULL": 4,
}

SEVERITIES = {"CRITICAL", "HIGH", "MEDIUM", "LOW"}
GENERIC_ID_PATTERN = re.compile(r"\b([A-Z][A-Z0-9_]*-\d+)\b")
ADR_ID_PATTERN = re.compile(r"\b(ADR-\d+)\b", re.IGNORECASE)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return data


def read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
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
    return value if isinstance(value, list) else [value]


def as_string_list(value: Any) -> list[str]:
    return [str(v).strip() for v in as_list(value) if str(v).strip()]


def pct(part: int, whole: int) -> float:
    if whole == 0:
        return 100.0
    return round((part / whole) * 100.0, 2)


def nearly_equal(a: Any, b: Any, tolerance: float = 0.01) -> bool:
    try:
        return abs(float(a) - float(b)) <= tolerance
    except (TypeError, ValueError):
        return False


def scope_includes(scope: str, target: str) -> bool:
    return SCOPE_LEVEL[scope] >= SCOPE_LEVEL[target]


def write_result(path: Path, result: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ============================================================
# Policy
# ============================================================


def validate_policy(policy: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    required_paths = [
        ["audit", "require_forward_traceability"],
        ["audit", "require_reverse_traceability"],
        ["audit", "allow_unresolved_blocking_issue"],
        ["requirements", "allow_invented_requirement_id"],
        ["requirements", "require_existing_reference"],
        ["global_requirements", "allow_source_reference_without_id"],
        ["global_requirements", "allow_generated_id"],
        ["adr", "downstream_status"],
        ["adr", "require_related_requirements"],
        ["adr", "allow_invalid_requirement_reference"],
        ["adr", "allow_superseded_as_current_decision"],
        ["implementation", "require_mapping_for_implementation_responsible_requirement"],
        ["implementation", "allow_missing_mapping"],
        ["unit_test", "require_mapping_for_unit_testable_requirement"],
        ["unit_test", "allow_missing_mapping"],
        ["integration_test", "require_mapping_for_integration_testable_requirement"],
        ["integration_test", "allow_missing_mapping"],
        ["coverage", "requirement_to_implementation", "required_rate"],
        ["coverage", "requirement_to_unit_test", "required_rate"],
        ["coverage", "requirement_to_integration_test", "required_rate"],
        ["orphan_artifacts", "allow_orphan_test"],
        ["orphan_artifacts", "allow_orphan_accepted_adr"],
        ["stale_evidence", "allowed"],
        ["conflicts", "allowed"],
        ["severity", "blocking"],
        ["issue_classification", "allowed"],
        ["routing"],
        ["reports", "directory"],
        ["reports", "required"],
    ]

    for keys in required_paths:
        if nested_get(policy, keys, None) is None:
            errors.append("Policy missing required setting: " + ".".join(keys))

    for keys in [
        ["coverage", "requirement_to_implementation", "required_rate"],
        ["coverage", "requirement_to_unit_test", "required_rate"],
        ["coverage", "requirement_to_integration_test", "required_rate"],
    ]:
        value = nested_get(policy, keys)
        if value is None:
            continue
        try:
            rate = float(value)
            if rate < 0 or rate > 100:
                errors.append(".".join(keys) + " must be between 0 and 100.")
        except (TypeError, ValueError):
            errors.append(".".join(keys) + " must be numeric.")

    allowed = set(
        as_string_list(nested_get(policy, ["issue_classification", "allowed"], []))
    )
    routing = nested_get(policy, ["routing"], {})

    if isinstance(routing, dict):
        for classification in allowed:
            if classification not in routing:
                errors.append(
                    f"Policy routing missing for classification: {classification}"
                )
    else:
        errors.append("Policy routing must be a mapping.")

    return errors


# ============================================================
# Repository Artifact Discovery
# ============================================================


def markdown_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    if not path.exists():
        return []
    return sorted(p for p in path.rglob("*.md") if p.is_file())


def discover_requirement_ids(
    requirements_file: Path,
    features_dir: Path,
) -> tuple[set[str], dict[str, list[str]]]:
    ids: set[str] = set()
    locations: dict[str, list[str]] = {}

    for path in markdown_files(requirements_file) + markdown_files(features_dir):
        text = path.read_text(encoding="utf-8")
        for match in GENERIC_ID_PATTERN.finditer(text):
            value = match.group(1).upper()
            if value.startswith("ADR-"):
                continue
            ids.add(value)
            locations.setdefault(value, []).append(str(path))

    return ids, locations


def section_text(markdown: str, heading: str) -> str | None:
    pattern = re.compile(
        rf"^##\s+{re.escape(heading)}\s*$",
        re.MULTILINE | re.IGNORECASE,
    )
    match = pattern.search(markdown)
    if not match:
        return None

    start = match.end()
    next_heading = re.search(r"^##\s+", markdown[start:], re.MULTILINE)
    end = start + next_heading.start() if next_heading else len(markdown)
    return markdown[start:end].strip()


def discover_adrs(
    adr_dir: Path,
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    adrs: dict[str, dict[str, Any]] = {}
    errors: list[str] = []

    if not adr_dir.exists():
        return adrs, errors

    for path in sorted(adr_dir.rglob("*.md")):
        text = path.read_text(encoding="utf-8")

        id_match = ADR_ID_PATTERN.search(path.name) or ADR_ID_PATTERN.search(text)
        if not id_match:
            errors.append(f"ADR file has no ADR ID: {path}")
            continue

        adr_id = id_match.group(1).upper()
        if adr_id in adrs:
            errors.append(f"Duplicate ADR ID: {adr_id}")
            continue

        status_section = section_text(text, "Status") or ""
        status = ""
        for line in status_section.splitlines():
            candidate = line.strip().lstrip("-").strip()
            if candidate:
                status = candidate.split()[0]
                break

        related_section = section_text(text, "Related Requirements") or ""
        related_ids: set[str] = set()
        for match in GENERIC_ID_PATTERN.finditer(related_section):
            value = match.group(1).upper()
            if not value.startswith("ADR-"):
                related_ids.add(value)

        adrs[adr_id] = {
            "id": adr_id,
            "path": str(path),
            "status": status,
            "related_requirements": sorted(related_ids),
        }

    return adrs, errors


# ============================================================
# Reports / Evidence
# ============================================================


def validate_required_reports(
    reports_dir: Path,
    policy: dict[str, Any],
) -> list[str]:
    errors: list[str] = []

    for name in as_string_list(nested_get(policy, ["reports", "required"], [])):
        path = reports_dir / name
        if not path.exists():
            errors.append(f"Required report missing: {path}")
        elif path.is_file() and path.stat().st_size == 0:
            errors.append(f"Required report is empty: {path}")

    return errors


def collect_strings_for_keys(node: Any, target_keys: set[str]) -> set[str]:
    result: set[str] = set()

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key in target_keys:
                    if isinstance(child, str) and child.strip():
                        result.add(child.strip())
                    elif isinstance(child, list):
                        for item in child:
                            if isinstance(item, str) and item.strip():
                                result.add(item.strip())
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(node)
    return result


def collect_requirement_refs(node: Any) -> set[str]:
    raw = collect_strings_for_keys(
        node,
        {
            "requirement_id",
            "requirement_ids",
            "requirement_reference",
            "related_requirements",
        },
    )

    result: set[str] = set()
    for value in raw:
        for match in GENERIC_ID_PATTERN.finditer(value):
            item = match.group(1).upper()
            if not item.startswith("ADR-"):
                result.add(item)
    return result


def collect_case_ids(node: Any) -> set[str]:
    return collect_strings_for_keys(
        node,
        {"case_id", "test_id", "test_name", "test"},
    )


# ============================================================
# ADR Validation
# ============================================================


def validate_adrs(
    adrs: dict[str, dict[str, Any]],
    requirement_ids: set[str],
    policy: dict[str, Any],
    scope: str,
) -> list[str]:
    errors: list[str] = []

    if not scope_includes(scope, "ARCHITECTURE"):
        return errors

    current_statuses = {
        value.lower()
        for value in as_string_list(
            nested_get(policy, ["adr", "downstream_status"], ["Accepted"])
        )
    }

    require_related = bool(
        nested_get(policy, ["adr", "require_related_requirements"], True)
    )
    allow_invalid = bool(
        nested_get(policy, ["adr", "allow_invalid_requirement_reference"], False)
    )

    for adr_id, adr in adrs.items():
        status = str(adr.get("status", "")).strip().lower()
        if status not in current_statuses:
            continue

        related = set(adr.get("related_requirements", []))
        if require_related and not related:
            errors.append(f"{adr_id}: Accepted ADR has no Related Requirements.")

        if not allow_invalid:
            for requirement_id in sorted(related):
                if requirement_id not in requirement_ids:
                    errors.append(
                        f"{adr_id}: Related Requirement does not exist: {requirement_id}"
                    )

    return errors


# ============================================================
# Traceability Report
# ============================================================


def validate_report_header(report: dict[str, Any]) -> tuple[list[str], str]:
    errors: list[str] = []

    scope = str(report.get("audit_scope", "")).upper()
    if scope not in AUDIT_SCOPES:
        errors.append(f"Invalid or missing audit_scope: {scope!r}")

    status = str(report.get("status", "")).upper()
    if status not in {"PASS", "FAIL", "BLOCKED"}:
        errors.append(f"Invalid or missing report status: {status!r}")

    return errors, scope


def validate_traceability_entries(
    report: dict[str, Any],
    requirement_ids: set[str],
    adrs: dict[str, dict[str, Any]],
    repo_root: Path,
    unit_evidence: dict[str, Any] | None,
    integration_plan: dict[str, Any] | None,
    integration_evidence: dict[str, Any] | None,
    policy: dict[str, Any],
    scope: str,
) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []

    entries = report.get("traceability")
    if not isinstance(entries, list):
        return ["traceability-report.json must contain traceability array."], {}

    current_statuses = {
        value.lower()
        for value in as_string_list(
            nested_get(policy, ["adr", "downstream_status"], ["Accepted"])
        )
    }
    accepted_adrs = {
        adr_id
        for adr_id, adr in adrs.items()
        if str(adr.get("status", "")).lower() in current_statuses
    }

    unit_requirement_refs = (
        collect_requirement_refs(unit_evidence) if unit_evidence else set()
    )

    integration_requirement_refs: set[str] = set()
    integration_case_ids: set[str] = set()

    if integration_plan:
        integration_requirement_refs |= collect_requirement_refs(integration_plan)
        integration_case_ids |= collect_case_ids(integration_plan)
    if integration_evidence:
        integration_requirement_refs |= collect_requirement_refs(integration_evidence)
        integration_case_ids |= collect_case_ids(integration_evidence)

    seen_refs: set[str] = set()

    implementation_total = implementation_covered = 0
    unit_total = unit_covered = 0
    integration_total = integration_covered = 0
    adr_total = adr_covered = 0

    for index, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            errors.append(f"traceability entry #{index} must be an object.")
            continue

        requirement_ref = str(entry.get("requirement_reference", "")).strip()
        if not requirement_ref:
            errors.append(
                f"traceability entry #{index}: requirement_reference is required."
            )
            continue

        requirement_ref_upper = requirement_ref.upper()
        looks_like_id = GENERIC_ID_PATTERN.fullmatch(requirement_ref_upper) is not None
        is_existing_id = requirement_ref_upper in requirement_ids

        if looks_like_id:
            if not is_existing_id:
                errors.append(
                    f"{requirement_ref}: Requirement reference does not exist."
                )
        else:
            allow_source_ref = bool(
                nested_get(
                    policy,
                    ["global_requirements", "allow_source_reference_without_id"],
                    True,
                )
            )
            if not allow_source_ref:
                errors.append(
                    f"{requirement_ref}: Source reference without ID is not allowed."
                )
            elif "#" not in requirement_ref:
                errors.append(
                    f"{requirement_ref}: Global requirement reference should identify File#Heading."
                )

        if requirement_ref in seen_refs:
            errors.append(
                f"Duplicate traceability entry for requirement: {requirement_ref}"
            )
        seen_refs.add(requirement_ref)

        # ADR mapping
        adr_ids = {v.upper() for v in as_string_list(entry.get("adrs"))}
        for adr_id in sorted(adr_ids):
            if adr_id not in adrs:
                errors.append(
                    f"{requirement_ref}: Referenced ADR does not exist: {adr_id}"
                )
                continue
            if adr_id not in accepted_adrs:
                errors.append(
                    f"{requirement_ref}: ADR is not an Accepted/current ADR: {adr_id}"
                )
            if (
                is_existing_id
                and requirement_ref_upper
                not in set(adrs[adr_id].get("related_requirements", []))
            ):
                errors.append(
                    f"{requirement_ref}: ADR {adr_id} does not list this Requirement in Related Requirements."
                )

        adr_required = bool(entry.get("adr_required", False))
        if adr_required:
            adr_total += 1
            if adr_ids:
                adr_covered += 1
            else:
                errors.append(
                    f"{requirement_ref}: adr_required=true but no ADR mapping."
                )

        # Implementation mapping
        implementation_applicable = bool(
            entry.get("implementation_applicable", True)
        )
        implementations = entry.get("implementation", [])
        if not isinstance(implementations, list):
            errors.append(
                f"{requirement_ref}: implementation must be an array."
            )
            implementations = []

        if scope_includes(scope, "IMPLEMENTATION") and implementation_applicable:
            implementation_total += 1
            if implementations:
                implementation_covered += 1
            elif not bool(
                nested_get(policy, ["implementation", "allow_missing_mapping"], False)
            ):
                errors.append(
                    f"{requirement_ref}: Implementation mapping is missing."
                )

        for mapping in implementations:
            if isinstance(mapping, str):
                file_value = mapping.strip()
            elif isinstance(mapping, dict):
                file_value = str(mapping.get("file", "")).strip()
            else:
                errors.append(
                    f"{requirement_ref}: Invalid implementation mapping."
                )
                continue

            if not file_value:
                errors.append(
                    f"{requirement_ref}: Implementation mapping has no file."
                )
                continue

            file_path = Path(file_value)
            if not file_path.is_absolute():
                file_path = repo_root / file_path
            if not file_path.exists():
                errors.append(
                    f"{requirement_ref}: Implementation file does not exist: {file_value}"
                )

        # Unit Test mapping
        unit_applicable = bool(entry.get("unit_test_applicable", True))
        unit_tests = as_string_list(entry.get("unit_tests"))

        if scope_includes(scope, "UNIT_TEST") and unit_applicable:
            unit_total += 1
            if unit_tests:
                unit_covered += 1
            elif not bool(
                nested_get(policy, ["unit_test", "allow_missing_mapping"], False)
            ):
                errors.append(f"{requirement_ref}: Unit Test mapping is missing.")

            if (
                is_existing_id
                and unit_evidence is not None
                and requirement_ref_upper not in unit_requirement_refs
            ):
                errors.append(
                    f"{requirement_ref}: Unit Test evidence does not reference this Requirement."
                )

        if not unit_applicable and bool(
            nested_get(
                policy,
                ["unit_test", "require_reason_when_not_applicable"],
                True,
            )
        ):
            reason = nested_get(entry, ["not_applicable_reason", "unit_test"], None)
            if not non_empty(reason):
                errors.append(
                    f"{requirement_ref}: Unit Test NOT_APPLICABLE requires reason."
                )

        # Integration Test mapping
        integration_applicable = bool(
            entry.get("integration_test_applicable", True)
        )
        integration_tests = as_string_list(entry.get("integration_tests"))

        if scope_includes(scope, "INTEGRATION_TEST") and integration_applicable:
            integration_total += 1
            if integration_tests:
                integration_covered += 1
            elif not bool(
                nested_get(
                    policy,
                    ["integration_test", "allow_missing_mapping"],
                    False,
                )
            ):
                errors.append(
                    f"{requirement_ref}: Integration Test mapping is missing."
                )

            if (
                is_existing_id
                and (integration_plan is not None or integration_evidence is not None)
                and requirement_ref_upper not in integration_requirement_refs
            ):
                errors.append(
                    f"{requirement_ref}: Integration Test evidence/plan does not reference this Requirement."
                )

            for case_id in integration_tests:
                if integration_case_ids and case_id not in integration_case_ids:
                    errors.append(
                        f"{requirement_ref}: Integration Test Case does not exist in plan/evidence: {case_id}"
                    )

        if not integration_applicable and bool(
            nested_get(
                policy,
                ["integration_test", "require_reason_when_not_applicable"],
                True,
            )
        ):
            reason = nested_get(
                entry,
                ["not_applicable_reason", "integration_test"],
                None,
            )
            if not non_empty(reason):
                errors.append(
                    f"{requirement_ref}: Integration Test NOT_APPLICABLE requires reason."
                )

    metrics = {
        "requirement_to_adr": {
            "total": adr_total,
            "covered": adr_covered,
            "rate": pct(adr_covered, adr_total),
        },
        "requirement_to_implementation": {
            "total": implementation_total,
            "covered": implementation_covered,
            "rate": pct(implementation_covered, implementation_total),
        },
        "requirement_to_unit_test": {
            "total": unit_total,
            "covered": unit_covered,
            "rate": pct(unit_covered, unit_total),
        },
        "requirement_to_integration_test": {
            "total": integration_total,
            "covered": integration_covered,
            "rate": pct(integration_covered, integration_total),
        },
    }

    return errors, metrics


# ============================================================
# Coverage
# ============================================================


def validate_coverage(
    report: dict[str, Any],
    metrics: dict[str, Any],
    policy: dict[str, Any],
    scope: str,
) -> list[str]:
    errors: list[str] = []
    reported = report.get("coverage", {})

    if not isinstance(reported, dict):
        return ["traceability-report.json coverage must be an object."]

    targets: list[tuple[str, str | None]] = [("requirement_to_adr", None)]

    if scope_includes(scope, "IMPLEMENTATION"):
        targets.append(
            ("requirement_to_implementation", "requirement_to_implementation")
        )
    if scope_includes(scope, "UNIT_TEST"):
        targets.append(("requirement_to_unit_test", "requirement_to_unit_test"))
    if scope_includes(scope, "INTEGRATION_TEST"):
        targets.append(
            ("requirement_to_integration_test", "requirement_to_integration_test")
        )

    for key, policy_key in targets:
        calculated_rate = metrics.get(key, {}).get("rate", 100.0)
        reported_value = reported.get(key)
        reported_rate = (
            reported_value.get("rate")
            if isinstance(reported_value, dict)
            else reported_value
        )

        if reported_rate is None:
            errors.append(f"coverage.{key} is missing.")
        elif not nearly_equal(reported_rate, calculated_rate):
            errors.append(
                f"coverage.{key}={reported_rate!r}, but recalculated rate is {calculated_rate:.2f}."
            )

        if policy_key:
            required_rate = float(
                nested_get(
                    policy,
                    ["coverage", policy_key, "required_rate"],
                    100,
                )
            )
            if calculated_rate < required_rate:
                errors.append(
                    f"{key} coverage {calculated_rate:.2f}% < required {required_rate:.2f}%."
                )

    return errors


# ============================================================
# Issues
# ============================================================


def issue_is_policy_failure(issue: dict[str, Any], policy: dict[str, Any]) -> bool:
    classification = str(issue.get("classification", "")).upper()
    severity = str(issue.get("severity", "")).upper()
    resolved = bool(issue.get("resolved", False))

    if resolved:
        return False

    blocking_severities = {
        item.upper()
        for item in as_string_list(
            nested_get(policy, ["severity", "blocking"], [])
        )
    }

    if (
        severity in blocking_severities
        and not bool(
            nested_get(
                policy,
                ["audit", "allow_unresolved_blocking_issue"],
                False,
            )
        )
    ):
        return True

    if classification == "INVALID_REQUIREMENT_REFERENCE":
        return bool(
            nested_get(policy, ["requirements", "require_existing_reference"], True)
        )
    if classification == "INVALID_ADR_REFERENCE":
        return True
    if classification == "IMPLEMENTATION_TRACEABILITY_MISSING":
        return not bool(
            nested_get(policy, ["implementation", "allow_missing_mapping"], False)
        )
    if classification == "UNIT_TEST_TRACEABILITY_MISSING":
        return not bool(
            nested_get(policy, ["unit_test", "allow_missing_mapping"], False)
        )
    if classification == "INTEGRATION_TEST_TRACEABILITY_MISSING":
        return not bool(
            nested_get(policy, ["integration_test", "allow_missing_mapping"], False)
        )
    if classification == "ORPHAN_ADR":
        return not bool(
            nested_get(
                policy,
                ["orphan_artifacts", "allow_orphan_accepted_adr"],
                False,
            )
        )
    if classification == "ORPHAN_TEST":
        return not bool(
            nested_get(policy, ["orphan_artifacts", "allow_orphan_test"], False)
        )
    if classification == "STALE_EVIDENCE":
        return not bool(nested_get(policy, ["stale_evidence", "allowed"], False))
    if classification == "TRACEABILITY_CONFLICT":
        return not bool(nested_get(policy, ["conflicts", "allowed"], False))

    return severity in blocking_severities


def validate_issues(
    report: dict[str, Any],
    requirement_ids: set[str],
    adrs: dict[str, dict[str, Any]],
    policy: dict[str, Any],
) -> tuple[list[str], int]:
    errors: list[str] = []
    issues = report.get("issues", [])

    if not isinstance(issues, list):
        return ["traceability-report.json issues must be an array."], 0

    allowed_classifications = {
        item.upper()
        for item in as_string_list(
            nested_get(policy, ["issue_classification", "allowed"], [])
        )
    }
    routing = nested_get(policy, ["routing"], {})
    blocking_count = 0
    ids: set[str] = set()

    for index, issue in enumerate(issues, start=1):
        if not isinstance(issue, dict):
            errors.append(f"Issue #{index} must be an object.")
            continue

        issue_id = str(issue.get("issue_id", "")).strip()
        if not issue_id:
            errors.append(f"Issue #{index}: issue_id is required.")
        elif issue_id in ids:
            errors.append(f"Duplicate issue_id: {issue_id}")
        else:
            ids.add(issue_id)

        classification = str(issue.get("classification", "")).upper()
        if classification not in allowed_classifications:
            errors.append(
                f"{issue_id or index}: invalid classification '{classification}'."
            )

        severity = str(issue.get("severity", "")).upper()
        if severity not in SEVERITIES:
            errors.append(
                f"{issue_id or index}: invalid severity '{severity}'."
            )

        if not non_empty(issue.get("description")):
            errors.append(f"{issue_id or index}: description is required.")

        recommended_route = str(issue.get("recommended_route", "")).upper()
        expected_route = (
            str(routing.get(classification, "")).upper()
            if isinstance(routing, dict)
            else ""
        )
        if expected_route and recommended_route != expected_route:
            errors.append(
                f"{issue_id or index}: recommended_route '{recommended_route}' != policy route '{expected_route}'."
            )

        requirement_ref = str(issue.get("requirement_reference", "")).strip()
        if requirement_ref and GENERIC_ID_PATTERN.fullmatch(requirement_ref.upper()):
            if requirement_ref.upper() not in requirement_ids:
                if classification != "INVALID_REQUIREMENT_REFERENCE":
                    errors.append(
                        f"{issue_id or index}: issue references unknown Requirement: {requirement_ref}"
                    )

        related_adr = str(issue.get("related_adr", "")).strip().upper()
        if (
            related_adr
            and related_adr not in adrs
            and classification != "INVALID_ADR_REFERENCE"
        ):
            errors.append(
                f"{issue_id or index}: issue references unknown ADR: {related_adr}"
            )

        if issue_is_policy_failure(issue, policy):
            blocking_count += 1

    return errors, blocking_count


# ============================================================
# Summary
# ============================================================


def validate_summary(
    report: dict[str, Any],
    metrics: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    summary = report.get("summary", {})

    if not isinstance(summary, dict):
        return ["traceability-report.json summary must be an object."]

    expected = {
        "implementation_mappings": metrics.get(
            "requirement_to_implementation", {}
        ).get("covered", 0),
        "unit_test_mappings": metrics.get("requirement_to_unit_test", {}).get(
            "covered", 0
        ),
        "integration_test_mappings": metrics.get(
            "requirement_to_integration_test", {}
        ).get("covered", 0),
        "issues": len(report.get("issues", []))
        if isinstance(report.get("issues", []), list)
        else 0,
    }

    for key, expected_value in expected.items():
        if key in summary and summary.get(key) != expected_value:
            errors.append(
                f"summary.{key}={summary.get(key)!r}, expected {expected_value}."
            )

    return errors


# ============================================================
# Main Validation
# ============================================================


def validate(
    repo_root: Path,
    policy_path: Path,
    requirements_file: Path,
    features_dir: Path,
    adr_dir: Path,
    report_path: Path,
    reports_dir: Path,
    unit_evidence_path: Path,
    unit_validation_path: Path,
    integration_plan_path: Path,
    integration_evidence_path: Path,
    integration_validation_path: Path,
) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []

    policy = read_yaml(policy_path)
    policy_errors = validate_policy(policy)
    errors.extend(policy_errors)

    if policy_errors:
        return errors, {"status": "FAIL", "errors": errors}

    errors.extend(validate_required_reports(reports_dir, policy))

    report = read_json(report_path)
    header_errors, scope = validate_report_header(report)
    errors.extend(header_errors)

    if scope not in AUDIT_SCOPES:
        return errors, {"status": "FAIL", "errors": errors}

    requirement_ids, _ = discover_requirement_ids(
        requirements_file,
        features_dir,
    )
    if not requirement_ids:
        errors.append(
            "No Requirement IDs were discovered from Requirements artifacts."
        )

    adrs, adr_discovery_errors = discover_adrs(adr_dir)
    errors.extend(adr_discovery_errors)
    errors.extend(validate_adrs(adrs, requirement_ids, policy, scope))

    def optional_json(path: Path, required: bool, label: str) -> dict[str, Any] | None:
        if path.exists():
            return read_json(path)
        if required:
            errors.append(f"{label} missing: {path}")
        return None

    unit_evidence = optional_json(
        unit_evidence_path,
        scope_includes(scope, "UNIT_TEST"),
        "Unit Test evidence",
    )
    unit_validation = optional_json(
        unit_validation_path,
        scope_includes(scope, "UNIT_TEST"),
        "Unit Test validation result",
    )
    integration_plan = optional_json(
        integration_plan_path,
        scope_includes(scope, "INTEGRATION_TEST"),
        "Integration Test plan",
    )
    integration_evidence = optional_json(
        integration_evidence_path,
        scope_includes(scope, "INTEGRATION_TEST"),
        "Integration Test evidence",
    )
    integration_validation = optional_json(
        integration_validation_path,
        scope_includes(scope, "INTEGRATION_TEST"),
        "Integration Test validation result",
    )

    if unit_validation is not None:
        unit_status = str(unit_validation.get("status", "")).upper()
        if unit_status != "PASS":
            errors.append(
                f"Unit Test validation-result status is not PASS: {unit_status!r}"
            )

    if integration_validation is not None:
        integration_status = str(
            integration_validation.get("status", "")
        ).upper()
        if integration_status != "PASS":
            errors.append(
                "Integration Test validation-result status is not PASS: "
                f"{integration_status!r}"
            )

    entry_errors, metrics = validate_traceability_entries(
        report=report,
        requirement_ids=requirement_ids,
        adrs=adrs,
        repo_root=repo_root,
        unit_evidence=unit_evidence,
        integration_plan=integration_plan,
        integration_evidence=integration_evidence,
        policy=policy,
        scope=scope,
    )
    errors.extend(entry_errors)
    errors.extend(validate_coverage(report, metrics, policy, scope))

    issue_errors, blocking_issue_count = validate_issues(
        report,
        requirement_ids,
        adrs,
        policy,
    )
    errors.extend(issue_errors)
    errors.extend(validate_summary(report, metrics))

    reported_status = str(report.get("status", "")).upper()
    if reported_status == "PASS" and blocking_issue_count > 0:
        errors.append(
            "traceability-report.json status is PASS, but "
            f"{blocking_issue_count} unresolved policy-blocking issue(s) exist."
        )

    if reported_status == "PASS" and errors:
        errors.append(
            "traceability-report.json reports PASS, but deterministic validation found errors."
        )

    result = {
        "status": "PASS" if not errors else "FAIL",
        "audit_scope": scope,
        "discovered": {
            "requirements": len(requirement_ids),
            "accepted_or_current_adrs": sum(
                1
                for adr in adrs.values()
                if str(adr.get("status", "")).lower()
                in {
                    item.lower()
                    for item in as_string_list(
                        nested_get(
                            policy,
                            ["adr", "downstream_status"],
                            ["Accepted"],
                        )
                    )
                }
            ),
        },
        "coverage": metrics,
        "blocking_issues": blocking_issue_count,
        "errors": errors,
    }

    return errors, result


# ============================================================
# CLI
# ============================================================


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate Traceability Auditor reports against repository artifacts "
            "and traceability policy."
        )
    )

    parser.add_argument("--repo-root", default=".")
    parser.add_argument(
        "--policy",
        default=(
            ".github/skills/traceability-audit/"
            "policy/traceability-policy.yaml"
        ),
    )
    parser.add_argument(
        "--requirements",
        default="docs/requirements/requirements.md",
    )
    parser.add_argument(
        "--features-dir",
        default="docs/requirements/features",
    )
    parser.add_argument("--adr-dir", default="docs/adr")
    parser.add_argument(
        "--report",
        default="reports/traceability/traceability-report.json",
    )
    parser.add_argument(
        "--reports-dir",
        default="reports/traceability",
    )
    parser.add_argument(
        "--unit-evidence",
        default="reports/unit-test/unit-test-evidence.json",
    )
    parser.add_argument(
        "--unit-validation",
        default="reports/unit-test/validation-result.json",
    )
    parser.add_argument(
        "--integration-plan",
        default="reports/integration-test/integration-test-plan.json",
    )
    parser.add_argument(
        "--integration-evidence",
        default="reports/integration-test/integration-test-evidence.json",
    )
    parser.add_argument(
        "--integration-validation",
        default="reports/integration-test/validation-result.json",
    )
    parser.add_argument(
        "--output",
        default="reports/traceability/validation-result.json",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()

    def resolve(value: str) -> Path:
        path = Path(value)
        return path if path.is_absolute() else repo_root / path

    output_path = resolve(args.output)

    try:
        errors, result = validate(
            repo_root=repo_root,
            policy_path=resolve(args.policy),
            requirements_file=resolve(args.requirements),
            features_dir=resolve(args.features_dir),
            adr_dir=resolve(args.adr_dir),
            report_path=resolve(args.report),
            reports_dir=resolve(args.reports_dir),
            unit_evidence_path=resolve(args.unit_evidence),
            unit_validation_path=resolve(args.unit_validation),
            integration_plan_path=resolve(args.integration_plan),
            integration_evidence_path=resolve(args.integration_evidence),
            integration_validation_path=resolve(args.integration_validation),
        )
    except (
        FileNotFoundError,
        ValueError,
        json.JSONDecodeError,
        yaml.YAMLError,
    ) as error:
        result = {"status": "FAIL", "errors": [str(error)]}
        write_result(output_path, result)

        print("========================================")
        print(" Traceability Validation")
        print("========================================")
        print()
        print(f"[FAIL] {error}")
        print(f"Result: {output_path}")
        return 1

    write_result(output_path, result)

    print("========================================")
    print(" Traceability Validation")
    print("========================================")
    print()

    if errors:
        print("[FAIL] Traceability validation failed.")
        print()
        for index, error in enumerate(errors, start=1):
            print(f"{index}. {error}")
        print()
        print(f"Total errors: {len(errors)}")
        print(f"Result: {output_path}")
        return 1

    print("[PASS] Traceability quality gate passed.")
    print(f"Result: {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
