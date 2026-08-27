#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from evaluation_common import nested_get, pct, read_json, write_json


RATE_PATHS = [
    "metrics.quality.requirement_satisfaction.overall.rate",
    "metrics.quality.requirement_satisfaction.functional.rate",
    "metrics.quality.requirement_satisfaction.non_functional.rate",
    "metrics.quality.unit_test_coverage.rate",
    "metrics.quality.integration_generated_test_coverage.requirement_rate",
    "metrics.quality.integration_generated_test_coverage.trace_item_rate",
]

NONNEGATIVE_PATHS = [
    "metrics.cost_efficiency.human_effort.input_count",
    "metrics.cost_efficiency.human_effort.input_characters",
    "metrics.cost_efficiency.human_effort.review_count",
    "metrics.cost_efficiency.human_effort.correction_count",
    "metrics.cost_efficiency.human_effort.active_work_seconds",
    "metrics.cost_efficiency.human_effort.elapsed_seconds",
    "metrics.cost_efficiency.rework.count",
    "metrics.cost_efficiency.ai_usage.input_tokens",
    "metrics.cost_efficiency.ai_usage.output_tokens",
    "metrics.cost_efficiency.ai_usage.total_tokens",
]


def validate(report: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    if report.get("status") not in {"PASS", "FAIL"}:
        errors.append("evaluation-report.json status must be PASS or FAIL.")

    if not str(report.get("run_id", "")).strip():
        errors.append("evaluation-report.json run_id is required.")

    if not isinstance(report.get("metrics"), dict):
        errors.append("evaluation-report.json metrics must be an object.")
        return errors

    for path in RATE_PATHS:
        value = nested_get(report, path, None)
        if value is None:
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            errors.append(f"{path} must be numeric or null.")
            continue
        if number < 0 or number > 100:
            errors.append(f"{path} must be between 0 and 100.")

    for path in NONNEGATIVE_PATHS:
        value = nested_get(report, path, None)
        if value is None:
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            errors.append(f"{path} must be numeric or null.")
            continue
        if number < 0:
            errors.append(f"{path} must not be negative.")

    req = nested_get(report, "metrics.quality.requirement_satisfaction", {})
    if isinstance(req, dict):
        for key in ("overall", "functional", "non_functional"):
            group = req.get(key, {})
            if not isinstance(group, dict):
                continue
            total = group.get("total")
            passed = group.get("passed")
            rate = group.get("rate")
            if isinstance(total, int) and isinstance(passed, int):
                expected = pct(passed, total)
                if rate != expected:
                    errors.append(
                        f"requirement_satisfaction.{key}.rate={rate!r}, expected {expected!r}."
                    )

    usage = nested_get(report, "metrics.cost_efficiency.ai_usage", {})
    if isinstance(usage, dict):
        inp = usage.get("input_tokens")
        out = usage.get("output_tokens")
        total = usage.get("total_tokens")
        if all(isinstance(v, int) for v in (inp, out, total)):
            if total < inp + out:
                errors.append(
                    "ai_usage.total_tokens must not be smaller than input_tokens + output_tokens."
                )

    report_errors = report.get("errors", [])
    if report.get("status") == "PASS" and report_errors:
        errors.append("Evaluation reports PASS but contains errors.")

    if report.get("status") == "PASS" and report.get("missing_inputs"):
        errors.append("Evaluation reports PASS but contains missing_inputs.")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate evaluation report.")
    parser.add_argument("--report", required=True)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    report_path = Path(args.report).resolve()
    output_path = (
        Path(args.output).resolve()
        if args.output
        else report_path.parent / "validation-result.json"
    )

    try:
        report = read_json(report_path)
        if not isinstance(report, dict):
            raise ValueError("evaluation-report.json root must be an object.")
        errors = validate(report)
    except (FileNotFoundError, ValueError) as exc:
        errors = [str(exc)]

    result = {
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
    }
    write_json(output_path, result)

    print("========================================")
    print(" Evaluation Validation")
    print("========================================")
    print(f"Status: {result['status']}")
    if errors:
        for idx, error in enumerate(errors, start=1):
            print(f"{idx}. {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
