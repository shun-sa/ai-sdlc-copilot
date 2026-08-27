#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import time
from pathlib import Path
from typing import Any

from acceptance_common import (
    canonical_json_sha256,
    parse_datetime,
    read_json,
    read_yaml,
    text_sha256,
    write_json,
    write_results_csv,
)


def validate_manifest(
    manifest: dict[str, Any],
    policy: dict[str, Any],
    manifest_path: Path,
) -> list[str]:
    errors: list[str] = []

    expected_version = policy.get("manifest", {}).get("schema_version", 1)
    if manifest.get("schema_version") != expected_version:
        errors.append(
            f"Manifest schema_version must be {expected_version}."
        )

    run_id = str(manifest.get("run_id", "")).strip()
    if not run_id:
        errors.append("Manifest run_id is required.")

    isolation = policy.get("isolation", {})
    completed = manifest.get("sdlc_completed_at")
    exposed = manifest.get("evaluation_data_exposed_at")

    if isolation.get("require_sdlc_complete_before_execution", True):
        if not completed:
            errors.append("Manifest sdlc_completed_at is required.")

    if isolation.get("require_evaluation_data_exposed_after_complete", True):
        if not exposed:
            errors.append("Manifest evaluation_data_exposed_at is required.")
        if completed and exposed:
            try:
                if parse_datetime(exposed) < parse_datetime(completed):
                    errors.append(
                        "Hidden Acceptance Test was exposed before SDLC COMPLETE."
                    )
            except ValueError as exc:
                errors.append(str(exc))

    if isolation.get("forbid_development_external_test_path", True):
        normalized = str(manifest_path).replace("\\", "/").lower()
        for fragment in isolation.get("forbidden_path_fragments", []):
            if str(fragment).replace("\\", "/").lower() in normalized:
                errors.append(
                    "Hidden Acceptance Test manifest must not be placed under "
                    f"development External Test path: {fragment}"
                )

    cases = manifest.get("cases")
    if not isinstance(cases, list) or not cases:
        errors.append("Manifest must contain non-empty cases array.")
        return errors

    required = policy.get("manifest", {}).get("required_case_fields", [])
    supported = {
        str(v).upper()
        for v in policy.get("manifest", {}).get(
            "supported_execution_types", ["COMMAND"]
        )
    }

    seen: set[str] = set()

    for index, case in enumerate(cases, start=1):
        if not isinstance(case, dict):
            errors.append(f"Case #{index} must be an object.")
            continue

        for field in required:
            if field not in case or case.get(field) in (None, "", []):
                errors.append(
                    f"Case #{index} missing required field: {field}"
                )

        case_id = str(case.get("case_id", "")).strip()
        if case_id:
            if case_id in seen:
                errors.append(f"Duplicate case_id: {case_id}")
            seen.add(case_id)

        execution_type = str(
            case.get("execution_type", "")
        ).upper()
        if execution_type and execution_type not in supported:
            errors.append(
                f"{case_id or f'Case #{index}'}: unsupported execution_type "
                f"{execution_type!r}."
            )

        command = case.get("command")
        if execution_type == "COMMAND":
            if (
                not isinstance(command, list)
                or not command
                or not all(isinstance(v, str) and v for v in command)
            ):
                errors.append(
                    f"{case_id or f'Case #{index}'}: command must be "
                    "a non-empty string array."
                )

        expected = case.get("expected")
        if not isinstance(expected, dict):
            errors.append(
                f"{case_id or f'Case #{index}'}: expected must be an object."
            )
        elif policy.get("manifest", {}).get(
            "require_expected_exit_code", True
        ) and "exit_code" not in expected:
            errors.append(
                f"{case_id or f'Case #{index}'}: expected.exit_code is required."
            )

    return errors


def expected_matches(
    expected: dict[str, Any],
    exit_code: int,
    stdout: str,
    stderr: str,
) -> tuple[bool, list[str]]:
    mismatches: list[str] = []

    if exit_code != int(expected.get("exit_code", 0)):
        mismatches.append(
            f"exit_code={exit_code}, expected={expected.get('exit_code')}"
        )

    checks = [
        ("stdout_contains", stdout, True),
        ("stderr_contains", stderr, True),
        ("stdout_not_contains", stdout, False),
        ("stderr_not_contains", stderr, False),
    ]

    for key, actual, should_contain in checks:
        values = expected.get(key, [])
        if values is None:
            continue
        if not isinstance(values, list):
            mismatches.append(f"{key} must be an array.")
            continue
        for value in values:
            text = str(value)
            present = text in actual
            if should_contain and not present:
                mismatches.append(f"{key} missing: {text!r}")
            if not should_contain and present:
                mismatches.append(f"{key} unexpectedly found: {text!r}")

    return not mismatches, mismatches


def run_case(
    case: dict[str, Any],
    repo_root: Path,
    policy: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    execution = policy.get("execution", {})
    default_timeout = int(execution.get("default_timeout_seconds", 300))
    maximum_timeout = int(execution.get("maximum_timeout_seconds", 1800))

    requested_timeout = int(case.get("timeout_seconds", default_timeout))
    timeout = min(max(requested_timeout, 1), maximum_timeout)

    cwd_value = str(case.get("cwd", "."))
    cwd = Path(cwd_value)
    if not cwd.is_absolute():
        cwd = repo_root / cwd

    command = list(case["command"])
    expected = dict(case["expected"])

    started = time.monotonic()

    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
            check=False,
        )
        duration = round(time.monotonic() - started, 4)

        matched, mismatches = expected_matches(
            expected,
            completed.returncode,
            completed.stdout,
            completed.stderr,
        )
        status = "PASS" if matched else "FAIL"

        result = {
            "case_id": case["case_id"],
            "requirement_id": case["requirement_id"],
            "requirement_type": case["requirement_type"],
            "result": status,
            "exit_code": completed.returncode,
            "duration_seconds": duration,
            "blocked_reason": "",
        }

        evidence = {
            **result,
            "execution_type": case["execution_type"],
            "command": command,
            "cwd": str(cwd),
            "timeout_seconds": timeout,
            "expected": expected,
            "mismatches": mismatches,
            "stdout_sha256": text_sha256(completed.stdout),
            "stderr_sha256": text_sha256(completed.stderr),
        }

        if policy.get("evidence", {}).get("save_stdout_text", False):
            evidence["stdout"] = completed.stdout
        if policy.get("evidence", {}).get("save_stderr_text", False):
            evidence["stderr"] = completed.stderr

        return result, evidence

    except subprocess.TimeoutExpired as exc:
        duration = round(time.monotonic() - started, 4)
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode(errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode(errors="replace")

        result = {
            "case_id": case["case_id"],
            "requirement_id": case["requirement_id"],
            "requirement_type": case["requirement_type"],
            "result": "BLOCKED",
            "exit_code": "",
            "duration_seconds": duration,
            "blocked_reason": "TIMEOUT",
        }
        evidence = {
            **result,
            "execution_type": case["execution_type"],
            "command": command,
            "cwd": str(cwd),
            "timeout_seconds": timeout,
            "expected": expected,
            "mismatches": [],
            "stdout_sha256": text_sha256(stdout),
            "stderr_sha256": text_sha256(stderr),
        }
        return result, evidence

    except (FileNotFoundError, OSError) as exc:
        duration = round(time.monotonic() - started, 4)
        result = {
            "case_id": case["case_id"],
            "requirement_id": case["requirement_id"],
            "requirement_type": case["requirement_type"],
            "result": "BLOCKED",
            "exit_code": "",
            "duration_seconds": duration,
            "blocked_reason": f"COMMAND_START_FAILED: {exc}",
        }
        evidence = {
            **result,
            "execution_type": case["execution_type"],
            "command": command,
            "cwd": str(cwd),
            "timeout_seconds": timeout,
            "expected": expected,
            "mismatches": [],
            "stdout_sha256": text_sha256(""),
            "stderr_sha256": text_sha256(str(exc)),
        }
        return result, evidence


def execute(
    repo_root: Path,
    input_dir: Path,
    manifest_path: Path,
    policy_path: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any], list[str]]:
    policy = read_yaml(policy_path)
    manifest = read_json(manifest_path)
    if not isinstance(manifest, dict):
        raise ValueError("Acceptance Test Manifest root must be an object.")

    errors = validate_manifest(
        manifest,
        policy,
        manifest_path,
    )
    if errors:
        return [], {
            "status": "FAIL",
            "run_id": manifest.get("run_id"),
            "errors": errors,
        }, errors

    rows: list[dict[str, Any]] = []
    case_evidence: list[dict[str, Any]] = []

    for case in manifest["cases"]:
        row, evidence = run_case(case, repo_root, policy)
        rows.append(row)
        case_evidence.append(evidence)

    counts = {
        "total": len(rows),
        "passed": sum(1 for row in rows if row["result"] == "PASS"),
        "failed": sum(1 for row in rows if row["result"] == "FAIL"),
        "blocked": sum(1 for row in rows if row["result"] == "BLOCKED"),
    }

    evidence = {
        "schema_version": 1,
        "status": "COMPLETE",
        "run_id": manifest["run_id"],
        "manifest_sha256": canonical_json_sha256(manifest),
        "summary": counts,
        "cases": case_evidence,
        "errors": [],
    }

    return rows, evidence, []


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Execute human-authored hidden Acceptance Tests."
    )
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--input-dir", required=True)
    parser.add_argument(
        "--manifest",
        default="acceptance-test-manifest.json",
    )
    parser.add_argument(
        "--policy",
        default=(
            ".github/skills/acceptance-test-execution/"
            "policy/acceptance-test-policy.yaml"
        ),
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    input_dir = Path(args.input_dir).resolve()

    manifest_path = Path(args.manifest)
    if not manifest_path.is_absolute():
        manifest_path = input_dir / manifest_path

    policy_path = Path(args.policy)
    if not policy_path.is_absolute():
        policy_path = repo_root / policy_path

    try:
        rows, evidence, errors = execute(
            repo_root,
            input_dir,
            manifest_path,
            policy_path,
        )

        run_id = str(
            evidence.get("run_id")
            or "UNKNOWN"
        )

        results_path = input_dir / "acceptance-test-results.csv"
        evidence_path = (
            repo_root
            / "reports"
            / "evaluation"
            / run_id
            / "acceptance-test"
            / "execution-evidence.json"
        )

        if rows:
            write_results_csv(results_path, rows)
        write_json(evidence_path, evidence)

        print("========================================")
        print(" Acceptance Test Execution")
        print("========================================")
        print(f"Run: {run_id}")
        print(f"Status: {'FAIL' if errors else 'COMPLETE'}")
        if rows:
            print(
                f"Cases: {len(rows)} / "
                f"PASS={sum(1 for r in rows if r['result'] == 'PASS')} / "
                f"FAIL={sum(1 for r in rows if r['result'] == 'FAIL')} / "
                f"BLOCKED={sum(1 for r in rows if r['result'] == 'BLOCKED')}"
            )
            print(f"Results: {results_path}")
        print(f"Evidence: {evidence_path}")

        if errors:
            for index, error in enumerate(errors, start=1):
                print(f"{index}. {error}")
            return 1

        # Test FAIL/BLOCKED is measurement output, not executor failure.
        return 0

    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"[FAIL] {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
