#!/usr/bin/env python3
from __future__ import annotations

import argparse
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

from evaluation_common import nested_get, read_json, read_yaml, write_json


def summarize(values: list[float], sample: bool) -> dict[str, Any]:
    if not values:
        return {
            "n": 0,
            "mean": None,
            "stddev": None,
            "min": None,
            "max": None,
        }

    stddev: float | None = None
    if len(values) >= 2:
        stddev = statistics.stdev(values) if sample else statistics.pstdev(values)

    return {
        "n": len(values),
        "mean": round(statistics.mean(values), 4),
        "stddev": round(stddev, 4) if stddev is not None else None,
        "min": round(min(values), 4),
        "max": round(max(values), 4),
    }


def collect_reports(reports_root: Path) -> list[dict[str, Any]]:
    reports: list[dict[str, Any]] = []
    for path in sorted(reports_root.glob("*/evaluation-report.json")):
        if path.parent.name == "aggregate":
            continue
        data = read_json(path)
        if isinstance(data, dict) and data.get("status") == "PASS":
            data["_path"] = str(path)
            reports.append(data)
    return reports


def aggregate(
    reports: list[dict[str, Any]],
    policy: dict[str, Any],
) -> dict[str, Any]:
    config = policy.get("aggregation", {})
    metric_paths = list(config.get("numeric_metrics", []))
    sample = bool(config.get("use_sample_standard_deviation", True))
    recommended = int(config.get("recommended_repetitions", 5))

    by_condition: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_category: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for report in reports:
        condition = str(report.get("condition_id") or "UNSPECIFIED")
        category = str(report.get("task_category") or "UNSPECIFIED")
        by_condition[condition].append(report)
        by_category[category].append(report)

    def group_summary(groups: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for group, items in groups.items():
            metrics: dict[str, Any] = {}
            for path in metric_paths:
                values: list[float] = []
                for item in items:
                    value = nested_get(item, path, None)
                    if isinstance(value, (int, float)) and not isinstance(value, bool):
                        values.append(float(value))
                metrics[path] = summarize(values, sample)
            result[group] = {
                "run_count": len(items),
                "metrics": metrics,
            }
        return result

    reproducibility = group_summary(by_condition)
    generality = group_summary(by_category)

    warnings: list[str] = []
    integrity_errors: list[str] = []

    signature_fields = [
        "model",
        "model_version",
        "prompt_profile_id",
        "requirements_snapshot",
        "framework_revision",
    ]
    for condition, items in by_condition.items():
        if len(items) < recommended:
            warnings.append(
                f"Condition {condition} has {len(items)} run(s); "
                f"recommended repetitions are {recommended}."
            )
        for field in signature_fields:
            values = {str(item.get(field) or "") for item in items}
            if len(values) > 1:
                integrity_errors.append(
                    f"Condition {condition} mixes different {field} values: {sorted(values)}"
                )

    if len(by_category) < 2:
        warnings.append(
            "Generality evaluation requires at least two task_category groups."
        )

    return {
        "schema_version": 1,
        "status": "PASS" if not integrity_errors else "FAIL",
        "run_count": len(reports),
        "reproducibility": reproducibility,
        "generality": generality,
        "integrity_errors": integrity_errors,
        "warnings": warnings,
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Evaluation Aggregate Report",
        "",
        f"- Runs: **{result['run_count']}**",
        "",
        "## Reproducibility",
        "",
    ]

    for condition, group in result["reproducibility"].items():
        lines.append(f"### {condition}")
        lines.append("")
        lines.append(f"Run count: {group['run_count']}")
        lines.append("")
        lines.append("| Metric | Mean | Stddev | N |")
        lines.append("|---|---:|---:|---:|")
        for metric, summary in group["metrics"].items():
            lines.append(
                f"| `{metric}` | {summary['mean']} | {summary['stddev']} | {summary['n']} |"
            )
        lines.append("")

    lines.extend(["## Generality", ""])
    for category, group in result["generality"].items():
        lines.append(f"### {category}")
        lines.append("")
        lines.append(f"Run count: {group['run_count']}")
        lines.append("")
        lines.append("| Metric | Mean | Stddev | N |")
        lines.append("|---|---:|---:|---:|")
        for metric, summary in group["metrics"].items():
            lines.append(
                f"| `{metric}` | {summary['mean']} | {summary['stddev']} | {summary['n']} |"
            )
        lines.append("")

    if result.get("warnings"):
        lines.extend(["## Warnings", ""])
        lines.extend(f"- {w}" for w in result["warnings"])
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Aggregate completed evaluation runs.")
    parser.add_argument("--reports-root", default="reports/evaluation")
    parser.add_argument(
        "--policy",
        default=".github/skills/evaluation/policy/evaluation-policy.yaml",
    )
    parser.add_argument("--repo-root", default=".")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    reports_root = Path(args.reports_root)
    if not reports_root.is_absolute():
        reports_root = repo_root / reports_root
    policy_path = Path(args.policy)
    if not policy_path.is_absolute():
        policy_path = repo_root / policy_path

    policy = read_yaml(policy_path)
    reports = collect_reports(reports_root)
    result = aggregate(reports, policy)

    output_dir = reports_root / "aggregate"
    write_json(output_dir / "aggregate-metrics.json", result)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "aggregate-report.md").write_text(
        render_markdown(result),
        encoding="utf-8",
    )

    print("========================================")
    print(" Evaluation Aggregate")
    print("========================================")
    print(f"Runs: {result['run_count']}")
    print(f"Report: {output_dir / 'aggregate-report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
