#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from acceptance_common import (
    canonical_json_sha256,
    read_json,
    read_results_csv,
    write_json,
)


ALLOWED = {"PASS", "FAIL", "BLOCKED"}


def validate(
    manifest: dict[str, Any],
    rows: list[dict[str, str]],
    evidence: dict[str, Any],
) -> list[str]:
    errors: list[str] = []

    cases = manifest.get("cases")
    if not isinstance(cases, list):
        return ["Manifest cases must be an array."]

    manifest_by_id: dict[str, dict[str, Any]] = {}
    for case in cases:
        if not isinstance(case, dict):
            continue
        case_id = str(case.get("case_id", "")).strip()
        if case_id:
            if case_id in manifest_by_id:
                errors.append(f"Duplicate Manifest case_id: {case_id}")
            manifest_by_id[case_id] = case

    result_by_id: dict[str, dict[str, str]] = {}
    for row in rows:
        case_id = str(row.get("case_id", "")).strip()
        if not case_id:
            errors.append("Result row missing case_id.")
            continue
        if case_id in result_by_id:
            errors.append(f"Duplicate Result case_id: {case_id}")
        result_by_id[case_id] = row

        status = str(row.get("result", "")).upper()
        if status not in ALLOWED:
            errors.append(
                f"{case_id}: invalid result status {status!r}."
            )

    if set(manifest_by_id) != set(result_by_id):
        missing = sorted(set(manifest_by_id) - set(result_by_id))
        extra = sorted(set(result_by_id) - set(manifest_by_id))
        if missing:
            errors.append(
                "Results missing Manifest cases: " + ", ".join(missing)
            )
        if extra:
            errors.append(
                "Results contain unknown cases: " + ", ".join(extra)
            )

    for case_id in sorted(set(manifest_by_id) & set(result_by_id)):
        case = manifest_by_id[case_id]
        row = result_by_id[case_id]

        if str(row.get("requirement_id", "")).strip() != str(
            case.get("requirement_id", "")
        ).strip():
            errors.append(
                f"{case_id}: requirement_id does not match Manifest."
            )

        if str(row.get("requirement_type", "")).strip().upper() != str(
            case.get("requirement_type", "")
        ).strip().upper():
            errors.append(
                f"{case_id}: requirement_type does not match Manifest."
            )

    if evidence.get("manifest_sha256") != canonical_json_sha256(manifest):
        errors.append(
            "execution-evidence.json manifest_sha256 does not match Manifest."
        )

    evidence_cases = evidence.get("cases")
    if not isinstance(evidence_cases, list):
        errors.append("execution-evidence.json cases must be an array.")
        evidence_cases = []

    evidence_by_id: dict[str, dict[str, Any]] = {}
    for item in evidence_cases:
        if not isinstance(item, dict):
            continue
        case_id = str(item.get("case_id", "")).strip()
        if case_id:
            evidence_by_id[case_id] = item

    if set(evidence_by_id) != set(manifest_by_id):
        errors.append(
            "execution-evidence.json case set does not match Manifest."
        )

    for case_id in sorted(
        set(evidence_by_id) & set(result_by_id)
    ):
        evidence_status = str(
            evidence_by_id[case_id].get("result", "")
        ).upper()
        result_status = str(
            result_by_id[case_id].get("result", "")
        ).upper()
        if evidence_status != result_status:
            errors.append(
                f"{case_id}: Result CSV status does not match Evidence."
            )

    summary = evidence.get("summary", {})
    if isinstance(summary, dict):
        expected_total = len(rows)
        expected_passed = sum(
            1 for row in rows
            if str(row.get("result", "")).upper() == "PASS"
        )
        expected_failed = sum(
            1 for row in rows
            if str(row.get("result", "")).upper() == "FAIL"
        )
        expected_blocked = sum(
            1 for row in rows
            if str(row.get("result", "")).upper() == "BLOCKED"
        )
        expected = {
            "total": expected_total,
            "passed": expected_passed,
            "failed": expected_failed,
            "blocked": expected_blocked,
        }
        for key, value in expected.items():
            if summary.get(key) != value:
                errors.append(
                    f"execution-evidence summary.{key}="
                    f"{summary.get(key)!r}, expected {value}."
                )
    else:
        errors.append(
            "execution-evidence.json summary must be an object."
        )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate Acceptance Test execution results."
    )
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--results", required=True)
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    manifest_path = Path(args.manifest).resolve()
    results_path = Path(args.results).resolve()
    evidence_path = Path(args.evidence).resolve()
    output_path = (
        Path(args.output).resolve()
        if args.output
        else evidence_path.parent / "validation-result.json"
    )

    try:
        manifest = read_json(manifest_path)
        evidence = read_json(evidence_path)
        rows = read_results_csv(results_path)

        if not isinstance(manifest, dict):
            raise ValueError("Manifest root must be an object.")
        if not isinstance(evidence, dict):
            raise ValueError("Evidence root must be an object.")

        errors = validate(
            manifest,
            rows,
            evidence,
        )

    except (FileNotFoundError, ValueError) as exc:
        errors = [str(exc)]

    result = {
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
    }
    write_json(output_path, result)

    print("========================================")
    print(" Acceptance Result Validation")
    print("========================================")
    print(f"Status: {result['status']}")

    if errors:
        for index, error in enumerate(errors, start=1):
            print(f"{index}. {error}")
        return 1

    print(f"Result: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
