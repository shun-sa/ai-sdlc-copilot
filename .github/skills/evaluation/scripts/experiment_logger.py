#!/usr/bin/env python3
"""
Optional external measurement helper.

This logger is NOT part of the SDLC flow.
Run it from a separate terminal/process when you need to capture
human interaction, routing, or AI usage metadata.

It stores counts/metadata only; it does not need prompt text.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def read(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return data


def write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="External experiment metadata logger.")
    sub = parser.add_subparsers(dest="command", required=True)

    start = sub.add_parser("start")
    start.add_argument("--input-dir", required=True)

    human = sub.add_parser("human")
    human.add_argument("--input-dir", required=True)
    human.add_argument(
        "--type",
        required=True,
        choices=["PROMPT", "REVIEW", "CORRECTION", "OTHER_INPUT"],
    )
    human.add_argument("--characters", type=int, default=0)

    finish = sub.add_parser("finish")
    finish.add_argument("--input-dir", required=True)
    finish.add_argument("--active-seconds", type=float, required=True)

    route = sub.add_parser("route")
    route.add_argument("--input-dir", required=True)
    route.add_argument("--from-phase", required=True)
    route.add_argument("--to-phase", required=True)
    route.add_argument("--classification", required=True)
    route.add_argument("--minor-refactoring", action="store_true")

    usage = sub.add_parser("usage")
    usage.add_argument("--input-dir", required=True)
    usage.add_argument("--agent", required=True)
    usage.add_argument("--input-tokens", type=int, required=True)
    usage.add_argument("--output-tokens", type=int, required=True)
    usage.add_argument("--total-tokens", type=int)
    usage.add_argument("--cache-read-tokens", type=int, default=0)
    usage.add_argument("--cache-write-tokens", type=int, default=0)
    usage.add_argument("--design-context-tokens", type=int)
    usage.add_argument("--evaluation-agent", action="store_true")

    args = parser.parse_args()
    directory = Path(args.input_dir).resolve()
    human_path = directory / "human-interaction-log.json"
    route_path = directory / "rework-events.json"
    usage_path = directory / "ai-usage-log.json"

    if args.command == "start":
        write(human_path, {
            "schema_version": 1,
            "started_at": now(),
            "completed_at": None,
            "human_active_seconds": None,
            "events": [],
        })
        write(route_path, {"schema_version": 1, "events": []})
        write(usage_path, {"schema_version": 1, "records": []})
        print(f"Started experiment logging: {directory}")
        return 0

    if args.command == "human":
        data = read(human_path, {"schema_version": 1, "events": []})
        data.setdefault("events", []).append({
            "timestamp": now(),
            "type": args.type,
            "characters": args.characters,
        })
        write(human_path, data)
        return 0

    if args.command == "finish":
        data = read(human_path, {"schema_version": 1, "events": []})
        data["completed_at"] = now()
        data["human_active_seconds"] = args.active_seconds
        write(human_path, data)
        return 0

    if args.command == "route":
        data = read(route_path, {"schema_version": 1, "events": []})
        data.setdefault("events", []).append({
            "timestamp": now(),
            "event_type": "PHASE_ROUTE",
            "from_phase": args.from_phase,
            "to_phase": args.to_phase,
            "classification": args.classification,
            "minor_refactoring": bool(args.minor_refactoring),
        })
        write(route_path, data)
        return 0

    if args.command == "usage":
        data = read(usage_path, {"schema_version": 1, "records": []})
        record = {
            "timestamp": now(),
            "agent": args.agent,
            "input_tokens": args.input_tokens,
            "output_tokens": args.output_tokens,
            "cache_read_tokens": args.cache_read_tokens,
            "cache_write_tokens": args.cache_write_tokens,
            "evaluation_agent": bool(args.evaluation_agent),
        }
        if args.total_tokens is not None:
            record["total_tokens"] = args.total_tokens
        if args.design_context_tokens is not None:
            record["design_context_tokens"] = args.design_context_tokens
        data.setdefault("records", []).append(record)
        write(usage_path, data)
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
