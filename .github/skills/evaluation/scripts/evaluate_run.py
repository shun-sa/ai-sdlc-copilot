#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from evaluation_common import (
    as_number,
    as_upper,
    load_rows,
    nested_get,
    parse_datetime,
    pct,
    read_json,
    read_yaml,
    write_json,
)


def resolve_input(input_dir: Path, manifest: dict[str, Any], key: str, default: str) -> Path:
    value = nested_get(manifest, f"inputs.{key}", default)
    path = Path(str(value))
    return path if path.is_absolute() else input_dir / path


def validate_isolation(
    manifest: dict[str, Any],
    acceptance_path: Path,
    policy: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    isolation = policy.get("isolation", {})

    if isolation.get("require_sdlc_complete_before_evaluation", True):
        if not manifest.get("sdlc_completed_at"):
            errors.append("experiment-manifest.json missing sdlc_completed_at.")

    if isolation.get("require_evaluation_data_exposed_after_complete", True):
        if not manifest.get("evaluation_data_exposed_at"):
            errors.append("experiment-manifest.json missing evaluation_data_exposed_at.")
        if manifest.get("sdlc_completed_at") and manifest.get("evaluation_data_exposed_at"):
            try:
                completed = parse_datetime(manifest["sdlc_completed_at"])
                exposed = parse_datetime(manifest["evaluation_data_exposed_at"])
                if exposed < completed:
                    errors.append(
                        "Hidden evaluation data was exposed before SDLC COMPLETE."
                    )
            except ValueError as exc:
                errors.append(str(exc))

    if isolation.get("forbid_development_external_cases_as_hidden_acceptance", True):
        normalized = str(acceptance_path).replace("\\", "/").lower()
        for fragment in isolation.get("forbidden_acceptance_path_fragments", []):
            if str(fragment).replace("\\", "/").lower() in normalized:
                errors.append(
                    "Hidden Acceptance Test must not use development External Integration Test path: "
                    + str(fragment)
                )

    return errors


def evaluate_requirement_satisfaction(
    rows: list[dict[str, Any]],
    policy: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    config = policy.get("requirement_satisfaction", {})
    pass_results = {as_upper(v) for v in config.get("pass_results", ["PASS"])}
    functional_types = {as_upper(v) for v in config.get("functional_types", ["FUNCTIONAL", "FR"])}
    non_functional_types = {
        as_upper(v) for v in config.get("non_functional_types", ["NON_FUNCTIONAL", "NFR"])
    }

    cases: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(rows, start=1):
        case_id = str(row.get("case_id", "")).strip()
        result = as_upper(row.get("result"))
        req_type = as_upper(row.get("requirement_type"))
        if not case_id:
            errors.append(f"Acceptance row #{index} missing case_id.")
            continue
        if not result:
            errors.append(f"Acceptance case {case_id} missing result.")
            continue
        current = cases.get(case_id)
        if current and current["result"] != result:
            errors.append(f"Acceptance case {case_id} has conflicting results.")
            continue
        cases[case_id] = {
            "result": result,
            "requirement_type": req_type,
        }

    def summarize(items: list[dict[str, Any]]) -> dict[str, Any]:
        total = len(items)
        passed = sum(1 for item in items if item["result"] in pass_results)
        return {
            "total": total,
            "passed": passed,
            "rate": pct(passed, total),
        }

    all_items = list(cases.values())
    functional = [v for v in all_items if v["requirement_type"] in functional_types]
    non_functional = [v for v in all_items if v["requirement_type"] in non_functional_types]

    return {
        "overall": summarize(all_items),
        "functional": summarize(functional),
        "non_functional": summarize(non_functional),
    }, errors


def evaluate_unit_coverage(
    repo_root: Path,
    policy: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    config = policy.get("unit_test_coverage", {})
    if not config.get("enabled", True):
        return {"enabled": False, "rate": None}, []

    path = repo_root / str(config.get("source", "reports/unit-test/coverage-summary.json"))
    if not path.exists():
        return {"enabled": True, "rate": None}, [f"Unit Test coverage source missing: {path}"]

    data = read_json(path)
    metric = str(config.get("metric", "branches"))
    total = data.get("total", {}) if isinstance(data, dict) else {}
    raw = total.get(metric) if isinstance(total, dict) else None

    if isinstance(raw, dict):
        value = raw.get("pct")
    else:
        value = raw

    number = as_number(value)
    if number is None:
        return {
            "enabled": True,
            "metric": metric,
            "rate": None,
            "source": str(path),
        }, [f"Unit Test coverage metric missing: {metric}"]

    return {
        "enabled": True,
        "metric": metric,
        "rate": round(number, 2),
        "source": str(path),
    }, []


def evaluate_generated_integration_coverage(
    matrix_rows: list[dict[str, Any]],
    repo_root: Path,
    policy: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    config = policy.get("integration_generated_test_coverage", {})
    source = repo_root / str(
        config.get("ai_case_source", "reports/integration-test/ai-initial-cases.json")
    )
    if not source.exists():
        return {
            "requirement_rate": None,
            "trace_item_rate": None,
            "source": str(source),
        }, [f"AI INITIAL case source missing: {source}"]

    data = read_json(source)
    cases = data.get("cases", []) if isinstance(data, dict) else []
    if not isinstance(cases, list):
        return {}, [f"AI INITIAL case source must contain cases array: {source}"]

    required_origin = as_upper(config.get("required_origin", "AI_GENERATED"))
    required_stage = as_upper(config.get("required_generation_stage", "INITIAL"))
    key_field = str(config.get("trace_key_field", "coverage_key"))

    ai_requirements: set[str] = set()
    ai_trace_keys: set[str] = set()

    for case in cases:
        if not isinstance(case, dict):
            continue
        origin = as_upper(case.get("origin", data.get("origin")))
        stage = as_upper(case.get("generation_stage", data.get("generation_stage")))
        if origin != required_origin or stage != required_stage:
            continue

        requirement = str(
            case.get("requirement_id")
            or case.get("requirement_reference")
            or ""
        ).strip()
        if requirement:
            ai_requirements.add(requirement)

        trace_key = str(case.get(key_field, "")).strip()
        if trace_key:
            ai_trace_keys.add(trace_key)

    matrix_requirements: set[str] = set()
    matrix_trace_keys: set[str] = set()
    covered_trace_keys: set[str] = set()

    for index, row in enumerate(matrix_rows, start=1):
        requirement = str(row.get("requirement_id", "")).strip()
        trace_key = str(row.get(key_field, "")).strip()

        if not requirement:
            errors.append(f"Human Traceability Matrix row #{index} missing requirement_id.")
            continue

        matrix_requirements.add(requirement)
        effective_key = trace_key or requirement
        matrix_trace_keys.add(effective_key)

        if trace_key:
            if trace_key in ai_trace_keys:
                covered_trace_keys.add(effective_key)
        elif requirement in ai_requirements:
            covered_trace_keys.add(effective_key)

    covered_requirements = matrix_requirements & ai_requirements

    return {
        "ai_initial_case_count": sum(
            1
            for case in cases
            if isinstance(case, dict)
            and as_upper(case.get("origin", data.get("origin"))) == required_origin
            and as_upper(case.get("generation_stage", data.get("generation_stage"))) == required_stage
        ),
        "human_requirement_total": len(matrix_requirements),
        "human_requirement_covered": len(covered_requirements),
        "requirement_rate": pct(len(covered_requirements), len(matrix_requirements)),
        "human_trace_item_total": len(matrix_trace_keys),
        "human_trace_item_covered": len(covered_trace_keys),
        "trace_item_rate": pct(len(covered_trace_keys), len(matrix_trace_keys)),
        "source": str(source),
    }, errors


def evaluate_human_effort(
    data: dict[str, Any],
    policy: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    config = policy.get("human_effort", {})
    input_types = {as_upper(v) for v in config.get(
        "input_event_types", ["PROMPT", "CORRECTION", "OTHER_INPUT"]
    )}
    review_type = as_upper(config.get("review_event_type", "REVIEW"))
    correction_type = as_upper(config.get("correction_event_type", "CORRECTION"))

    events = data.get("events", [])
    if not isinstance(events, list):
        return {}, ["human-interaction-log.json events must be an array."]

    input_count = 0
    input_characters = 0
    review_count = 0
    correction_count = 0

    for event in events:
        if not isinstance(event, dict):
            continue
        event_type = as_upper(event.get("type"))
        chars = as_number(event.get("characters"), default=0) or 0
        if event_type in input_types:
            input_count += 1
            input_characters += int(chars)
        if event_type == review_type:
            review_count += 1
        if event_type == correction_type:
            correction_count += 1

    active = as_number(data.get("human_active_seconds"))
    if active is None and config.get("require_active_work_seconds", True):
        errors.append("human-interaction-log.json missing human_active_seconds.")

    elapsed_seconds: float | None = None
    if data.get("started_at") and data.get("completed_at"):
        try:
            start = parse_datetime(data["started_at"])
            end = parse_datetime(data["completed_at"])
            if end < start:
                errors.append("human-interaction-log completed_at is before started_at.")
            else:
                elapsed_seconds = (end - start).total_seconds()
        except ValueError as exc:
            errors.append(str(exc))
    else:
        errors.append("human-interaction-log.json requires started_at and completed_at.")

    return {
        "input_count": input_count,
        "input_characters": input_characters,
        "review_count": review_count,
        "correction_count": correction_count,
        "active_work_seconds": active,
        "active_work_minutes": round(active / 60.0, 2) if active is not None else None,
        "elapsed_seconds": elapsed_seconds,
        "elapsed_minutes": round(elapsed_seconds / 60.0, 2)
        if elapsed_seconds is not None
        else None,
    }, errors


def evaluate_rework(
    data: dict[str, Any],
    policy: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    config = policy.get("rework", {})
    target = as_upper(config.get("target_phase", "IMPLEMENTATION"))
    from_phases = {as_upper(v) for v in config.get("count_from_phases", [])}
    excluded = {as_upper(v) for v in config.get("excluded_classifications", [])}
    exclude_minor = bool(config.get("exclude_minor_refactoring", True))

    events = data.get("events", [])
    if not isinstance(events, list):
        return {}, ["rework-events.json events must be an array."]

    counted: list[dict[str, Any]] = []
    for event in events:
        if not isinstance(event, dict):
            continue
        if as_upper(event.get("event_type", "PHASE_ROUTE")) != "PHASE_ROUTE":
            continue
        if as_upper(event.get("to_phase")) != target:
            continue
        if from_phases and as_upper(event.get("from_phase")) not in from_phases:
            continue
        if as_upper(event.get("classification")) in excluded:
            continue
        if exclude_minor and bool(event.get("minor_refactoring", False)):
            continue
        counted.append(event)

    return {
        "count": len(counted),
        "counted_events": [
            {
                "timestamp": event.get("timestamp"),
                "from_phase": event.get("from_phase"),
                "to_phase": event.get("to_phase"),
                "classification": event.get("classification"),
            }
            for event in counted
        ],
    }, []


def evaluate_ai_usage(
    data: dict[str, Any],
    policy: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    config = policy.get("ai_usage", {})
    records = data.get("records", [])
    if not isinstance(records, list):
        return {}, ["ai-usage-log.json records must be an array."]

    totals = {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "cache_read_tokens": 0,
        "cache_write_tokens": 0,
        "design_context_tokens": 0,
    }
    design_context_available = True

    for index, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            continue
        if config.get("exclude_evaluation_agent_usage", True) and bool(
            record.get("evaluation_agent", False)
        ):
            continue

        input_tokens = as_number(record.get("input_tokens"))
        output_tokens = as_number(record.get("output_tokens"))

        if input_tokens is None and config.get("require_input_tokens", True):
            errors.append(f"AI usage record #{index} missing input_tokens.")
            input_tokens = 0
        if output_tokens is None and config.get("require_output_tokens", True):
            errors.append(f"AI usage record #{index} missing output_tokens.")
            output_tokens = 0

        input_tokens = input_tokens or 0
        output_tokens = output_tokens or 0

        total_tokens = as_number(record.get("total_tokens"))
        if total_tokens is None:
            if config.get("allow_total_from_input_plus_output", True):
                total_tokens = input_tokens + output_tokens
            else:
                errors.append(f"AI usage record #{index} missing total_tokens.")
                total_tokens = 0

        design = as_number(record.get("design_context_tokens"))
        if design is None:
            design_context_available = False
            if config.get("require_design_context_tokens", False):
                errors.append(f"AI usage record #{index} missing design_context_tokens.")
            design = 0

        totals["input_tokens"] += int(input_tokens)
        totals["output_tokens"] += int(output_tokens)
        totals["total_tokens"] += int(total_tokens)
        totals["cache_read_tokens"] += int(as_number(record.get("cache_read_tokens"), default=0) or 0)
        totals["cache_write_tokens"] += int(as_number(record.get("cache_write_tokens"), default=0) or 0)
        totals["design_context_tokens"] += int(design)

    totals["design_context_tokens_available"] = design_context_available
    totals["record_count"] = len([
        r for r in records
        if isinstance(r, dict)
        and not (
            config.get("exclude_evaluation_agent_usage", True)
            and bool(r.get("evaluation_agent", False))
        )
    ])
    return totals, errors


def render_markdown(report: dict[str, Any]) -> str:
    m = report["metrics"]
    req = m["quality"]["requirement_satisfaction"]
    unit = m["quality"]["unit_test_coverage"]
    integ = m["quality"]["integration_generated_test_coverage"]
    human = m["cost_efficiency"]["human_effort"]
    rework = m["cost_efficiency"]["rework"]
    usage = m["cost_efficiency"]["ai_usage"]

    lines = [
        f"# Evaluation Report: {report['run_id']}",
        "",
        f"- Status: **{report['status']}**",
        f"- Condition: `{report.get('condition_id', '')}`",
        f"- Task: `{report.get('task_id', '')}`",
        f"- Task Category: `{report.get('task_category', '')}`",
        f"- Model: `{report.get('model', '')}`",
        "",
        "## Quality",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Requirement Satisfaction | {req['overall']['rate']}% |",
        f"| Functional Satisfaction | {req['functional']['rate']}% |",
        f"| Non-functional Satisfaction | {req['non_functional']['rate']}% |",
        f"| Unit Test {unit.get('metric', '')} Coverage | {unit.get('rate')}% |",
        f"| AI INITIAL Requirement Coverage | {integ.get('requirement_rate')}% |",
        f"| AI INITIAL Trace Item Coverage | {integ.get('trace_item_rate')}% |",
        "",
        "## Cost / Efficiency",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Human Input Count | {human.get('input_count')} |",
        f"| Human Input Characters | {human.get('input_characters')} |",
        f"| Review Count | {human.get('review_count')} |",
        f"| Correction Count | {human.get('correction_count')} |",
        f"| Human Active Work | {human.get('active_work_minutes')} min |",
        f"| Experiment Elapsed | {human.get('elapsed_minutes')} min |",
        f"| Rework Count | {rework.get('count')} |",
        f"| AI Input Tokens | {usage.get('input_tokens')} |",
        f"| AI Output Tokens | {usage.get('output_tokens')} |",
        f"| AI Total Tokens | {usage.get('total_tokens')} |",
        f"| AI Design Context Tokens | {usage.get('design_context_tokens') if usage.get('design_context_tokens_available') else 'NOT_AVAILABLE'} |",
        "",
    ]

    if report.get("errors"):
        lines.extend(["## Errors", ""])
        lines.extend(f"- {e}" for e in report["errors"])
        lines.append("")

    if report.get("warnings"):
        lines.extend(["## Warnings", ""])
        lines.extend(f"- {w}" for w in report["warnings"])
        lines.append("")

    return "\n".join(lines)


def evaluate(
    repo_root: Path,
    input_dir: Path,
    policy_path: Path,
    manifest_path: Path,
) -> dict[str, Any]:
    policy = read_yaml(policy_path)
    manifest = read_json(manifest_path)
    if not isinstance(manifest, dict):
        raise ValueError("experiment-manifest.json root must be an object.")

    run_id = str(manifest.get("run_id", "")).strip()
    if not run_id:
        raise ValueError("experiment-manifest.json missing run_id.")

    required_defaults = {
        "acceptance_results": "acceptance-test-results.csv",
        "human_traceability_matrix": "human-traceability-matrix.csv",
        "human_interaction_log": "human-interaction-log.json",
        "ai_usage_log": "ai-usage-log.json",
        "rework_events": "rework-events.json",
    }
    paths = {
        key: resolve_input(input_dir, manifest, key, default)
        for key, default in required_defaults.items()
    }

    errors: list[str] = []
    warnings: list[str] = []
    missing_inputs: list[str] = []

    if not manifest_path.exists():
        missing_inputs.append(str(manifest_path))

    required_keys = set(policy.get("inputs", {}).get("required_keys", required_defaults.keys()))
    for key, path in paths.items():
        if key in required_keys and not path.exists() and str(path) not in missing_inputs:
            missing_inputs.append(str(path))

    if missing_inputs:
        errors.extend(f"Required evaluation input missing: {p}" for p in missing_inputs)

    errors.extend(validate_isolation(manifest, paths["acceptance_results"], policy))

    req_metrics: dict[str, Any] = {
        "overall": {"total": 0, "passed": 0, "rate": None},
        "functional": {"total": 0, "passed": 0, "rate": None},
        "non_functional": {"total": 0, "passed": 0, "rate": None},
    }
    integration_metrics: dict[str, Any] = {
        "requirement_rate": None,
        "trace_item_rate": None,
    }
    human_metrics: dict[str, Any] = {}
    rework_metrics: dict[str, Any] = {}
    ai_metrics: dict[str, Any] = {}

    if paths["acceptance_results"].exists():
        req_metrics, es = evaluate_requirement_satisfaction(
            load_rows(paths["acceptance_results"]), policy
        )
        errors.extend(es)

    unit_metrics, es = evaluate_unit_coverage(repo_root, policy)
    errors.extend(es)

    if paths["human_traceability_matrix"].exists():
        integration_metrics, es = evaluate_generated_integration_coverage(
            load_rows(paths["human_traceability_matrix"]), repo_root, policy
        )
        errors.extend(es)

    if paths["human_interaction_log"].exists():
        data = read_json(paths["human_interaction_log"])
        if isinstance(data, dict):
            human_metrics, es = evaluate_human_effort(data, policy)
            errors.extend(es)
        else:
            errors.append("human-interaction-log.json root must be an object.")

    if paths["rework_events"].exists():
        data = read_json(paths["rework_events"])
        if isinstance(data, dict):
            rework_metrics, es = evaluate_rework(data, policy)
            errors.extend(es)
        else:
            errors.append("rework-events.json root must be an object.")

    if paths["ai_usage_log"].exists():
        data = read_json(paths["ai_usage_log"])
        if isinstance(data, dict):
            ai_metrics, es = evaluate_ai_usage(data, policy)
            errors.extend(es)
        else:
            errors.append("ai-usage-log.json root must be an object.")

    metrics = {
        "quality": {
            "requirement_satisfaction": req_metrics,
            "unit_test_coverage": unit_metrics,
            "integration_generated_test_coverage": integration_metrics,
        },
        "cost_efficiency": {
            "human_effort": human_metrics,
            "rework": rework_metrics,
            "ai_usage": ai_metrics,
        },
        "process": {
            "reproducibility": "AGGREGATE_REQUIRED",
            "generality": "AGGREGATE_REQUIRED",
        },
    }

    report = {
        "schema_version": 1,
        "status": "PASS" if not errors else "FAIL",
        "run_id": run_id,
        "condition_id": manifest.get("condition_id"),
        "task_id": manifest.get("task_id"),
        "task_category": manifest.get("task_category"),
        "model": manifest.get("model"),
        "model_version": manifest.get("model_version"),
        "prompt_profile_id": manifest.get("prompt_profile_id"),
        "requirements_snapshot": manifest.get("requirements_snapshot"),
        "framework_revision": manifest.get("framework_revision"),
        "sdlc_completed_at": manifest.get("sdlc_completed_at"),
        "evaluation_data_exposed_at": manifest.get("evaluation_data_exposed_at"),
        "metrics": metrics,
        "missing_inputs": missing_inputs,
        "errors": errors,
        "warnings": warnings,
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate one completed AI SDLC experiment run.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--input-dir", required=True)
    parser.add_argument(
        "--policy",
        default=".github/skills/evaluation/policy/evaluation-policy.yaml",
    )
    parser.add_argument("--manifest", default="experiment-manifest.json")
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    input_dir = Path(args.input_dir).resolve()
    policy_path = Path(args.policy)
    if not policy_path.is_absolute():
        policy_path = repo_root / policy_path
    manifest_path = Path(args.manifest)
    if not manifest_path.is_absolute():
        manifest_path = input_dir / manifest_path

    try:
        report = evaluate(repo_root, input_dir, policy_path, manifest_path)
        run_id = report["run_id"]
        output_dir = (
            Path(args.output_dir).resolve()
            if args.output_dir
            else repo_root / "reports" / "evaluation" / run_id
        )

        write_json(output_dir / "metrics.json", report["metrics"])
        write_json(output_dir / "evaluation-report.json", report)
        (output_dir / "evaluation-report.md").write_text(
            render_markdown(report),
            encoding="utf-8",
        )

        print("========================================")
        print(" Evaluation")
        print("========================================")
        print(f"Run: {run_id}")
        print(f"Status: {report['status']}")
        print(f"Report: {output_dir / 'evaluation-report.json'}")
        if report["errors"]:
            for idx, error in enumerate(report["errors"], start=1):
                print(f"{idx}. {error}")
            return 1
        return 0
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"[FAIL] {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
