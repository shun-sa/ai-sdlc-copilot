from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
import uuid
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path


PHASES = ("REQUIREMENTS", "ARCHITECTURE", "IMPLEMENTATION", "UNIT_TEST", "INTEGRATION_TEST", "FULL")
RESULTS = {"PASS", "FAIL", "BLOCKED", "CONTINUE_WITH_UNRESOLVED"}
EXCLUDE = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", ".ruff_cache", "reports", "htmlcov", "evaluation-input", "dist", "build"}


def canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def local(root: Path, value: str) -> Path:
    if not isinstance(value, str) or not value or Path(value).is_absolute() or ":" in value or ".." in Path(value).parts:
        raise ValueError(f"Expected repository-relative path: {value}")
    path = (root / value).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Path escapes repository")
    return path


def directory(root: Path, run_id: str) -> Path:
    if not isinstance(run_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", run_id):
        raise ValueError("run_id must be a safe, unique experiment identifier")
    return local(root, f"reports/experiments/{run_id}")


def timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("A timezone-aware timestamp is required")
    return parsed


def clock() -> tuple[str, int]:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds"), time.monotonic_ns()


def source_fingerprint(root: Path) -> str:
    paths = []
    for current, subdirectories, names in os.walk(root):
        subdirectories[:] = sorted(name for name in subdirectories if name not in EXCLUDE and not (Path(current) / name).is_symlink())
        for name in sorted(names):
            path = Path(current) / name
            if path.is_symlink() or name.startswith(".coverage") or path.suffix.lower() in (".pyc", ".db", ".sqlite", ".sqlite3"):
                continue
            paths.append({"path": path.relative_to(root).as_posix(), "sha256": digest(path)})
    return hashlib.sha256(canonical(sorted(paths, key=lambda item: item["path"])).encode()).hexdigest()


def load_events(root: Path, run_id: str) -> list[dict]:
    path = directory(root, run_id) / "events.sqlite3"
    if not path.is_file():
        raise ValueError("No recorded run; historical timing cannot be reconstructed")
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as connection:
        rows = connection.execute("SELECT sequence, body FROM events ORDER BY sequence").fetchall()
    events = verify_rows(rows)
    if events[0]["payload"].get("run_id") != run_id:
        raise ValueError("Journal belongs to a different experiment run")
    return events


def verify_rows(rows) -> list[dict]:
    events = []
    previous = ""
    for expected, (sequence, body) in enumerate(rows, 1):
        event = json.loads(body)
        unsigned = {key: value for key, value in event.items() if key != "sha256"}
        if sequence != expected or event["sequence"] != sequence or event["previous_sha256"] != previous or hashlib.sha256(canonical(unsigned).encode()).hexdigest() != event["sha256"]:
            raise ValueError("Event journal is incomplete or was altered")
        if events and timestamp(event["at"]) < timestamp(events[-1]["at"]):
            raise ValueError("Wall clock moved backwards")
        previous = event["sha256"]
        events.append(event)
    if not events or events[0]["kind"] != "RUN_STARTED":
        raise ValueError("Run start is missing")
    return events


def replay(events: list[dict]) -> dict:
    state = {"current": None, "spans": [], "activities": {}, "closed_activities": [], "routes": [], "ended": None, "snapshots": [], "last_phase": None, "interruptions": []}
    for event in events:
        kind, payload, at = event["kind"], event["payload"], event["at"]
        if kind in ("RUN_STARTED", "PHASE_ENTERED"):
            phase = payload.get("phase", "ARCHITECTURE") if kind == "RUN_STARTED" else payload["phase"]
            previous = state["current"]
            origin = previous["phase"] if previous else state["last_phase"]
            if previous:
                previous.update(end=at, result=payload["previous_result"], end_sequence=event["sequence"])
            if origin and PHASES.index(phase) < PHASES.index(origin):
                state["routes"].append({"event_id": event["event_id"], "timestamp": at, "event_type": "PHASE_ROUTE", "from_phase": origin, "to_phase": phase, "classification": payload["classification"], "reason": payload["reason"], "trigger_agent": payload.get("trigger_agent", ""), "minor_refactoring": False})
            span = {"visit_id": event["event_id"], "phase": phase, "start": at, "start_sequence": event["sequence"], "end": None, "result": None}
            state["spans"].append(span)
            state["current"] = span
            state["last_phase"] = phase
        elif kind == "PHASE_ENDED":
            state["current"].update(end=at, result=payload["result"], end_sequence=event["sequence"])
            state["current"] = None
        elif kind == "ACTIVITY_STARTED":
            state["activities"][payload["activity_id"]] = {**payload, "phase": state["current"]["phase"], "visit_id": state["current"]["visit_id"], "start": at, "end": None}
        elif kind == "ACTIVITY_ENDED":
            activity = state["activities"].pop(payload["activity_id"])
            activity.update(end=at, result=payload["result"])
            state["closed_activities"].append(activity)
        elif kind == "INTERRUPTED":
            if state["current"]:
                state["current"]["result"] = "INTERRUPTED"
            state["closed_activities"].extend({**activity, "result": "INTERRUPTED"} for activity in state["activities"].values())
            state["activities"] = {}
            state["current"] = None
            state["interruptions"].append({"at": at, "reason": payload["reason"]})
        elif kind == "RUN_ENDED":
            state["ended"] = event
        elif kind == "SNAPSHOT":
            state["snapshots"].append(event)
    return state


def validate_next(events: list[dict], kind: str, payload: dict) -> None:
    if not events:
        if kind != "RUN_STARTED":
            raise ValueError("Start measurement before Architecture PREPARE")
        if payload.get("phase", "ARCHITECTURE") not in ("REQUIREMENTS", "ARCHITECTURE"):
            raise ValueError("Measurement starts at Requirements or Architecture PREPARE")
        return
    state = replay(events)
    if kind == "RUN_STARTED":
        raise ValueError("Run IDs cannot be reused")
    if state["ended"] and not (kind == "SNAPSHOT" and payload.get("type") == "ACCEPTANCE"):
        raise ValueError("Development measurement already ended")
    if kind in ("PHASE_ENTERED", "PHASE_ENDED", "RUN_ENDED") and state["activities"]:
        raise ValueError("End open activities before leaving the parent phase")
    if kind == "PHASE_ENTERED":
        phase = payload.get("phase")
        if phase not in PHASES or (state["current"] and phase == state["current"]["phase"]):
            raise ValueError("Unknown/same phase; use a checkpoint for same-phase retries")
        if state["current"] and payload.get("previous_result") not in RESULTS:
            raise ValueError("Record the actual previous phase result")
        origin = state["current"]["phase"] if state["current"] else state["last_phase"]
        if origin and PHASES.index(phase) < PHASES.index(origin) and not (payload.get("classification") and payload.get("reason")):
            raise ValueError("Actual backwards dispatch requires classification and reason")
    elif kind == "PHASE_ENDED":
        if not state["current"] or payload.get("phase") != state["current"]["phase"] or payload.get("result") not in RESULTS:
            raise ValueError("Phase end does not match the current phase")
    elif kind == "ACTIVITY_STARTED":
        used = set(state["activities"]) | {activity["activity_id"] for activity in state["closed_activities"]}
        if not state["current"] or not payload.get("name") or not payload.get("activity_id") or payload["activity_id"] in used:
            raise ValueError("Activity needs a current phase and a unique ID")
    elif kind == "ACTIVITY_ENDED":
        if payload.get("activity_id") not in state["activities"] or payload.get("result") not in RESULTS:
            raise ValueError("Activity end has no matching start/result")
    elif kind == "RUN_ENDED":
        if state["current"] or payload.get("status") not in ("COMPLETE", "COMPLETE_WITH_UNRESOLVED", "ABORTED"):
            raise ValueError("Close the current phase and record the actual terminal status")
    elif kind == "INTERRUPTED":
        if not payload.get("reason"):
            raise ValueError("Interruption requires a reason; unknown end times are not fabricated")
    elif kind == "SNAPSHOT":
        if payload["type"] == "ACCEPTANCE" and not state["ended"]:
            raise ValueError("Hidden acceptance data must not be exposed during development")
        if payload["type"] == "AI_INITIAL":
            existing = [event for event in state["snapshots"] if event["payload"]["type"] == "AI_INITIAL"]
            if existing and existing[0]["payload"]["artifact"]["sha256"] != payload["artifact"]["sha256"]:
                raise ValueError("Frozen AI INITIAL cases cannot be replaced")
    elif kind != "CHECKPOINT":
        raise ValueError("Unknown measurement event")


def append(root: Path, run_id: str, event_id: str, kind: str, payload: dict, now=None) -> dict:
    if not isinstance(event_id, str) or not event_id.strip():
        raise ValueError("A stable execution/event ID is required")
    if kind == "RUN_STARTED":
        payload = {**payload, "run_id": run_id}
    folder = directory(root, run_id)
    folder.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(folder / "events.sqlite3", timeout=30)) as connection:
        connection.execute("CREATE TABLE IF NOT EXISTS events (sequence INTEGER PRIMARY KEY, event_id TEXT NOT NULL UNIQUE, body TEXT NOT NULL)")
        connection.execute("BEGIN IMMEDIATE")
        rows = connection.execute("SELECT sequence, body FROM events ORDER BY sequence").fetchall()
        events = verify_rows(rows) if rows else []
        if events and events[0]["payload"].get("run_id") != run_id:
            raise ValueError("Journal belongs to a different experiment run")
        prior = next((event for event in events if event["event_id"] == event_id), None)
        if prior:
            if prior["kind"] != kind or prior["payload"] != payload:
                raise ValueError("Event ID reused for different facts")
            return prior
        validate_next(events, kind, payload)
        at, monotonic = (now or clock)()
        if events and timestamp(at) < timestamp(events[-1]["at"]):
            raise ValueError("Wall clock moved backwards; measurement needs review")
        event = {"sequence": len(events) + 1, "event_id": event_id, "kind": kind, "at": at, "monotonic_ns": monotonic, "payload": payload, "previous_sha256": events[-1]["sha256"] if events else ""}
        event["sha256"] = hashlib.sha256(canonical(event).encode()).hexdigest()
        connection.execute("INSERT INTO events(sequence,event_id,body) VALUES (?,?,?)", (event["sequence"], event_id, canonical(event)))
        connection.commit()
    return event


def archive(root: Path, run_id: str, path: Path) -> dict:
    path = path.resolve()
    checksum = digest(path)
    target = directory(root, run_id) / "artifacts" / (checksum + path.suffix.lower())
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_bytes(path.read_bytes())
    if digest(target) != checksum:
        raise ValueError("Archived artifact was altered")
    return {"source": path.relative_to(root).as_posix() if path.is_relative_to(root) else str(path), "path": target.relative_to(root).as_posix(), "sha256": checksum}


def artifact(root: Path, reference: dict) -> Path:
    path = local(root, reference["path"])
    if digest(path) != reference["sha256"]:
        raise ValueError("Measurement artifact checksum differs")
    return path


def branch_coverage(data: dict) -> dict:
    if data.get("meta", {}).get("branch_coverage") is True:
        total = data.get("totals", {}).get("num_branches")
        covered = data.get("totals", {}).get("covered_branches")
        format_name = "coverage.py"
    elif isinstance(data.get("total", {}).get("branches"), dict):
        total = data["total"]["branches"].get("total")
        covered = data["total"]["branches"].get("covered")
        format_name = "Istanbul"
    else:
        return {"status": "NOT_MEASURED", "rate": None, "reason": "Raw branch counts/branch-enabled report are required; line/combined percentages are not branch coverage"}
    if type(total) is not int or type(covered) is not int or not 0 <= covered <= total:
        raise ValueError("Invalid branch counts")
    measured_files = sorted(data.get("files", {})) if format_name == "coverage.py" else sorted(key for key in data if key != "total")
    return {"status": "MEASURED" if total else "NO_BRANCHES", "format": format_name, "covered": covered, "total": total, "rate": round(100 * covered / total, 2) if total else None, "measured_files": measured_files}


def capture_integration(root: Path, run_id: str, event_id: str, kind: str, source: str, now=None) -> dict:
    if kind not in ("AI_INITIAL", "INTEGRATION_PLAN", "INTEGRATION_RESULT"):
        raise ValueError("Unknown integration artifact type")
    state = replay(load_events(root, run_id))
    payload = {"type": kind, "artifact": archive(root, run_id, local(root, source)), "source_fingerprint": source_fingerprint(root)}
    if kind == "INTEGRATION_RESULT":
        plans = [event for event in state["snapshots"] if event["payload"]["type"] == "INTEGRATION_PLAN"]
        if plans:
            reference = plans[-1]["payload"]["artifact"]
            current = local(root, reference["source"])
            payload["plan_sha256"] = reference["sha256"] if current.is_file() and digest(current) == reference["sha256"] else None
    return append(root, run_id, event_id, "SNAPSHOT", payload, now)


def run_unit(root: Path, run_id: str, event_id: str, specification: dict) -> int:
    events = load_events(root, run_id)
    spec_hash = hashlib.sha256(canonical(specification).encode()).hexdigest()
    prior = next((event for event in events if event["event_id"] == event_id + ":coverage"), None)
    if prior:
        if prior["payload"].get("spec_sha256") != spec_hash:
            raise ValueError("Execution ID reused for a different command")
        return prior["payload"]["exit_code"]
    if any(event["event_id"] == event_id + ":start" for event in events):
        raise ValueError("Interrupted command: record interruption, then use a new execution ID")
    state = replay(events)
    if not state["current"] or state["current"]["phase"] != "UNIT_TEST":
        raise ValueError("Unit execution belongs to the UNIT_TEST phase")
    commands = specification.get("commands")
    if not isinstance(commands, list) or not commands or any(not isinstance(command, list) or not command or not all(isinstance(value, str) and value for value in command) for command in commands):
        raise ValueError("Explicit test/export command argument arrays are required")
    paths = {key: local(root, specification[key]) for key in ("coverage", "junit")}
    spec_path = directory(root, run_id) / "command-specs" / (spec_hash + ".json")
    save(spec_path, specification)
    spec_reference = archive(root, run_id, spec_path)
    before = {key: (path.stat().st_mtime_ns, digest(path)) if path.is_file() else None for key, path in paths.items()}
    fingerprint = source_fingerprint(root)
    append(root, run_id, event_id + ":start", "ACTIVITY_STARTED", {"activity_id": event_id, "name": "UNIT_TEST_EXECUTION", "spec_sha256": spec_hash})
    codes = []
    for command in commands:
        try:
            result = subprocess.run(command, cwd=root, capture_output=True, timeout=specification.get("timeout_seconds", 600))
            codes.append(result.returncode)
        except (OSError, subprocess.TimeoutExpired):
            codes.append(-1)
    code = next((code for code in codes if code), 0)
    append(root, run_id, event_id + ":end", "ACTIVITY_ENDED", {"activity_id": event_id, "result": "PASS" if code == 0 else "FAIL"})
    references = {key: archive(root, run_id, path) if path.is_file() else None for key, path in paths.items()}
    fresh = all(path.is_file() and before[key] != (path.stat().st_mtime_ns, digest(path)) for key, path in paths.items())
    payload = {"type": "UNIT_COVERAGE", "coverage": references["coverage"], "junit": references["junit"], "command_spec": spec_reference, "fresh": fresh, "source_fingerprint": fingerprint, "source_unchanged_during_execution": fingerprint == source_fingerprint(root), "spec_sha256": spec_hash, "exit_code": code}
    append(root, run_id, event_id + ":coverage", "SNAPSHOT", payload)
    return code


def capture_acceptance(root: Path, run_id: str, event_id: str, manifest_path: Path, results_path: Path, evidence_path: Path, now=None) -> dict:
    state = replay(load_events(root, run_id))
    if not state["ended"] or state["ended"]["payload"]["status"] == "ABORTED":
        raise ValueError("Acceptance data is post-process only")
    manifest = read(manifest_path)
    if manifest.get("run_id") != run_id:
        raise ValueError("Acceptance manifest belongs to a different run")
    if timestamp(manifest["evaluation_data_exposed_at"]) < timestamp(state["ended"]["at"]):
        raise ValueError("Hidden acceptance data was exposed before recorded SDLC completion")
    references = {key: archive(root, run_id, path) for key, path in (("manifest", manifest_path), ("results", results_path), ("evidence", evidence_path))}
    payload = {"type": "ACCEPTANCE", **references, "source_fingerprint": source_fingerprint(root)}
    return append(root, run_id, event_id, "SNAPSHOT", payload, now)


def cases(data: dict, key="cases") -> dict:
    values = data.get(key)
    if not isinstance(values, list) or not all(isinstance(value, dict) and isinstance(value.get("case_id"), str) and value["case_id"] for value in values):
        raise ValueError(f"Invalid {key} array")
    indexed = {value["case_id"]: value for value in values}
    if len(indexed) != len(values):
        raise ValueError("Duplicate test case IDs")
    return indexed


def integration_metrics(root: Path, snapshots: list[dict], fingerprint: str) -> dict:
    selected = {event["payload"]["type"]: event["payload"] for event in snapshots if event["payload"]["type"] in ("AI_INITIAL", "INTEGRATION_PLAN", "INTEGRATION_RESULT")}
    if "INTEGRATION_PLAN" not in selected:
        return {"status": "MISSING", "cases": [], "reason": "Final plan not captured"}
    plan = selected["INTEGRATION_PLAN"]
    values = cases(read(artifact(root, plan["artifact"])))
    initial_payload = selected.get("AI_INITIAL")
    initial = cases(read(artifact(root, initial_payload["artifact"]))) if initial_payload else {}
    errors = []
    for identifier, initial_case in initial.items():
        if identifier not in values or any(values[identifier].get(key) != value for key, value in initial_case.items() if key not in ("result", "actual_result")):
            errors.append(f"Frozen INITIAL case changed or missing: {identifier}")
    results = {}
    evidence = selected.get("INTEGRATION_RESULT")
    valid_results = bool(evidence and evidence.get("plan_sha256") == plan["artifact"]["sha256"] and evidence["source_fingerprint"] == fingerprint)
    if valid_results:
        results = cases(read(artifact(root, evidence["artifact"])), "case_results")
        if set(results) - set(values):
            errors.append("Result contains cases outside the captured plan")
    inventory = [{**value, "result": results.get(identifier, {}).get("result", "NOT_RUN") if valid_results else "UNCONFIRMED"} for identifier, value in values.items()]
    groups = Counter(f"{value.get('origin', 'UNKNOWN')}:{value.get('generation_stage', 'UNKNOWN')}" for value in values.values())
    return {"status": "INVALID" if errors else "MEASURED" if plan["source_fingerprint"] == fingerprint else "STALE", "total": len(values), "by_origin_stage": dict(groups), "initial_total": len(initial) if initial_payload else None, "cases": inventory, "result_binding": "BOUND" if valid_results else "UNCONFIRMED", "errors": errors, "sources": selected}


def acceptance_metrics(root: Path, run_id: str, state: dict, fingerprint: str) -> dict:
    snapshots = [event for event in state["snapshots"] if event["payload"]["type"] == "ACCEPTANCE"]
    if not snapshots:
        return {"status": "NOT_YET_IMPORTED", "rate": None}
    selected = snapshots[-1]["payload"]
    manifest = read(artifact(root, selected["manifest"]))
    evidence = read(artifact(root, selected["evidence"]))
    with artifact(root, selected["results"]).open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "acceptance-test-execution/scripts"))
    from validate_acceptance_results import validate
    errors = validate(manifest, rows, evidence)
    if manifest.get("run_id") != run_id or evidence.get("run_id") != run_id:
        errors.append("Acceptance run identity differs")
    valid_baseline = bool(state["ended"] and selected["source_fingerprint"] == state["ended"]["payload"]["source_fingerprint"] == fingerprint)
    if not valid_baseline:
        errors.append("Application/configuration changed after SDLC completion")
    total = len(cases(manifest))
    counts = Counter(str(row.get("result", "")).upper() for row in rows)
    return {"status": "INVALID" if errors else "MEASURED", "total": total, "passed": counts["PASS"], "failed": counts["FAIL"], "blocked": counts["BLOCKED"], "rate": round(100 * counts["PASS"] / total, 2) if total and not errors else None, "errors": errors, "sources": selected}


def summary(root: Path, run_id: str) -> dict:
    events = load_events(root, run_id)
    state = replay(events)
    fingerprint = source_fingerprint(root)
    integrations = [span for span in state["spans"] if span["phase"] == "INTEGRATION_TEST" and span["end"]]
    last = integrations[-1] if integrations else None
    invalidated = bool(last and any(span["start_sequence"] > last["end_sequence"] and PHASES.index(span["phase"]) <= PHASES.index("INTEGRATION_TEST") for span in state["spans"]))
    if invalidated:
        last = None
    design = next((span for span in state["spans"] if span["phase"] == "ARCHITECTURE"), None)
    start, end = timestamp(design["start"]) if design else None, timestamp(last["end"]) if last and design else None
    warnings = []
    clock_errors = []
    all_clock_errors = []
    for previous, current in zip(events, events[1:]):
        wall = (timestamp(current["at"]) - timestamp(previous["at"])).total_seconds()
        monotonic = (current["monotonic_ns"] - previous["monotonic_ns"]) / 1_000_000_000
        if monotonic < 0 or abs(wall - monotonic) > 5:
            if not state["ended"] or current["sequence"] <= state["ended"]["sequence"]:
                all_clock_errors.append(current["event_id"])
            if last and design and design["start_sequence"] < current["sequence"] <= last["end_sequence"]:
                clock_errors.append(current["event_id"])
    phase_times = {}
    window_phase_times = {}
    known = 0.0
    for phase in PHASES:
        all_spans = [span for span in state["spans"] if span["phase"] == phase]
        all_complete = bool(all_spans and not all_clock_errors and all(span["end"] for span in all_spans))
        phase_times[phase] = {"visits": len(all_spans), "seconds": round(sum((timestamp(span["end"]) - timestamp(span["start"])).total_seconds() for span in all_spans), 6) if all_complete else None, "status": "MEASURED" if all_complete else "NOT_ENTERED" if not all_spans else "INCOMPLETE"}
        spans = [span for span in all_spans if start and end and timestamp(span["start"]) < end and (not span["end"] or timestamp(span["end"]) > start)]
        complete = bool(spans and not clock_errors and all(span["end"] for span in spans))
        seconds = sum(max(0, (min(timestamp(span["end"]), end) - max(timestamp(span["start"]), start)).total_seconds()) for span in spans if span["end"]) if start and end and not clock_errors else None
        if seconds is not None:
            known += seconds
        window_phase_times[phase] = {"visits": len(spans), "seconds": round(seconds, 6) if complete else None, "status": "MEASURED" if complete else "NOT_ENTERED" if not spans else "INCOMPLETE"}
    elapsed = (end - start).total_seconds() if start and end and not clock_errors else None
    if state["current"] or state["activities"] or state["interruptions"]:
        warnings.append("Unclosed/interrupted spans exist; missing phase/activity ends are not inferred")
    if all_clock_errors:
        warnings.append("Clock adjustment/reboot detected; timing requires human review")
    if invalidated:
        warnings.append("Previous integration completion was invalidated by a later revisit; do not use its elapsed time as final")
    units = [event["payload"] for event in state["snapshots"] if event["payload"]["type"] == "UNIT_COVERAGE"]
    unit = {"status": "MISSING", "rate": None}
    if units:
        selected = units[-1]
        for key in ("coverage", "junit", "command_spec"):
            if selected.get(key):
                artifact(root, selected[key])
        if not selected["fresh"] or not selected["coverage"] or not selected["junit"]:
            unit = {"status": "UNCONFIRMED", "rate": None, "reason": "Test command did not freshly produce coverage and JUnit"}
        elif not selected["source_unchanged_during_execution"] or selected["source_fingerprint"] != fingerprint:
            unit = {"status": "STALE", "rate": None}
        else:
            try:
                unit = branch_coverage(read(artifact(root, selected["coverage"])))
            except (ValueError, TypeError, AttributeError) as error:
                unit = {"status": "INVALID", "rate": None, "reason": str(error)}
        unit["execution"] = selected
    try:
        integration = integration_metrics(root, state["snapshots"], fingerprint)
    except (ValueError, KeyError, TypeError, AttributeError) as error:
        integration = {"status": "INVALID", "cases": [], "reason": str(error)}
    try:
        acceptance = acceptance_metrics(root, run_id, state, fingerprint)
    except (ValueError, KeyError, TypeError, AttributeError) as error:
        acceptance = {"status": "INVALID", "rate": None, "reason": str(error)}
    edges = Counter((route["from_phase"], route["to_phase"]) for route in state["routes"])
    activities = [{**activity, "seconds": round((timestamp(activity["end"]) - timestamp(activity["start"])).total_seconds(), 6) if activity["end"] and not all_clock_errors else None} for activity in state["closed_activities"] + list(state["activities"].values())]
    activity_times = {}
    for name in sorted({activity["name"] for activity in activities}):
        selected = [activity for activity in activities if activity["name"] == name]
        complete = bool(selected and not all_clock_errors and all(activity["end"] for activity in selected))
        activity_times[name] = {"visits": len(selected), "summed_seconds": round(sum(activity["seconds"] for activity in selected), 6) if complete else None, "non_additive_to_parent_phase": True}
    return {"schema_version": 1, "run_id": run_id, "metadata": events[0]["payload"], "run_status": state["ended"]["payload"]["status"] if state["ended"] else "RUNNING", "time_window": {"start": design["start"] if design else None, "end": last["end"] if last else None, "elapsed_seconds": round(elapsed, 6) if elapsed is not None else None, "integration_result": last["result"] if last else None, "quality_pass_elapsed_seconds": round(elapsed, 6) if elapsed is not None and last["result"] == "PASS" else None, "finalized": state["ended"] is not None, "unallocated_seconds": round(max(0, elapsed - known), 6) if elapsed is not None else None, "clock_anomalies": clock_errors}, "phase_times": phase_times, "measurement_window_phase_times": window_phase_times, "phase_visits": state["spans"], "activities": activities, "activity_times": activity_times, "clock_anomalies": all_clock_errors, "rework": {"total": len(state["routes"]), "by_from_phase": dict(Counter(route["from_phase"] for route in state["routes"])), "by_to_phase": dict(Counter(route["to_phase"] for route in state["routes"])), "edges": [{"from_phase": source, "to_phase": target, "count": count} for (source, target), count in sorted(edges.items())], "events": state["routes"]}, "unit_branch_coverage": unit, "integration": integration, "acceptance": acceptance, "tokens": {"status": "MANUAL_EXTERNAL", "source": "VSCode", "value": None}, "warnings": warnings, "journal_head_sha256": events[-1]["sha256"]}


def export(root: Path, run_id: str) -> dict:
    result = summary(root, run_id)
    folder = directory(root, run_id)
    save(folder / "metrics.json", result)
    save(folder / "rework-events.json", {"schema_version": 1, "events": [{**event, "from_phase": "FINAL_ASSURANCE" if event["from_phase"] == "FULL" else event["from_phase"]} for event in result["rework"]["events"]]})
    save(folder / "integration-cases.json", result["integration"])
    state = replay(load_events(root, run_id))
    save(folder / "run-context.json", {"run_id": run_id, "sdlc_completed_at": state["ended"]["at"] if state["ended"] else None, "status": result["run_status"], "measurement_window": result["time_window"]})
    (folder / "events.jsonl").write_text("".join(canonical(event) + "\n" for event in load_events(root, run_id)), encoding="utf-8")
    lines = [f"# 実験測定結果 {run_id}", "", f"- Run状態: {result['run_status']}", f"- 設計開始→最後の結合試験終了（秒）: {result['time_window']['elapsed_seconds']}", f"- 結合試験の終了状態: {result['time_window']['integration_result']}", f"- 手戻り総数: {result['rework']['total']}", f"- 分岐網羅率: {result['unit_branch_coverage'].get('rate')} / {result['unit_branch_coverage']['status']}", f"- 受入テスト合格率: {result['acceptance'].get('rate')} / {result['acceptance']['status']}", "- トークン数: VSCodeで取得（未入力を0とみなさない）", "", "## 工程別（待機・同一工程内の修正を含む。子活動は二重加算しない）", ""]
    lines.extend(f"- {phase}: {value['seconds']} 秒 / {value['visits']} visits / {value['status']}" for phase, value in result["phase_times"].items())
    lines += ["", "## 設計開始→最後の結合試験終了の区間内だけの工程時間", ""]
    lines.extend(f"- {phase}: {value['seconds']} 秒 / {value['status']}" for phase, value in result["measurement_window_phase_times"].items())
    lines += ["", "## 子活動（親工程へ加算しない）", ""]
    lines.extend(f"- {name}: {value['summed_seconds']} 秒 / {value['visits']} visits" for name, value in result["activity_times"].items())
    lines += ["", "## 手戻り：実際に戻した工程別", ""]
    lines.extend(f"- {edge['from_phase']} → {edge['to_phase']}: {edge['count']}" for edge in result["rework"]["edges"])
    lines += ["", "## 注意", "", "nullは未取得・未確認・非該当。0や100%に補完しない。", "計測は開発Gateや品質合格を代替しない。"] + result["warnings"]
    (folder / "measurement-report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Observation-only experiment journal and deterministic metrics")
    parser.add_argument("action", choices=("start", "enter", "phase-end", "activity-start", "activity-end", "checkpoint", "interrupt", "end", "run-unit", "snapshot", "acceptance", "summarize"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--run-id")
    parser.add_argument("--event-id")
    parser.add_argument("--phase", choices=PHASES)
    parser.add_argument("--result", choices=sorted(RESULTS))
    parser.add_argument("--status", choices=("COMPLETE", "COMPLETE_WITH_UNRESOLVED", "ABORTED"))
    parser.add_argument("--activity-id")
    parser.add_argument("--name")
    parser.add_argument("--reason", default="")
    parser.add_argument("--classification", default="")
    parser.add_argument("--trigger-agent", default="")
    parser.add_argument("--condition-id", default="")
    parser.add_argument("--spec")
    parser.add_argument("--kind", choices=("AI_INITIAL", "INTEGRATION_PLAN", "INTEGRATION_RESULT"))
    parser.add_argument("--source")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--results", type=Path)
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args(argv)
    if args.action == "start" and not args.run_id:
        args.run_id = "RUN-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8]
    if not args.run_id:
        parser.error("--run-id is required except when starting a new run")
    root = args.root.resolve()
    event_id = args.event_id or {"start": "run-start", "end": "run-end"}.get(args.action)
    try:
        if args.action == "summarize":
            export(root, args.run_id)
        elif args.action == "run-unit":
            return int(run_unit(root, args.run_id, event_id, read(local(root, args.spec))) != 0)
        elif args.action == "snapshot":
            capture_integration(root, args.run_id, event_id, args.kind, args.source)
        elif args.action == "acceptance":
            capture_acceptance(root, args.run_id, event_id, args.manifest, args.results, args.evidence)
        else:
            kinds = {"start": "RUN_STARTED", "enter": "PHASE_ENTERED", "phase-end": "PHASE_ENDED", "activity-start": "ACTIVITY_STARTED", "activity-end": "ACTIVITY_ENDED", "checkpoint": "CHECKPOINT", "interrupt": "INTERRUPTED", "end": "RUN_ENDED"}
            payload = {"start": {"condition_id": args.condition_id, "phase": args.phase or "ARCHITECTURE"}, "enter": {"phase": args.phase, "previous_result": args.result, "classification": args.classification, "reason": args.reason, "trigger_agent": args.trigger_agent}, "phase-end": {"phase": args.phase, "result": args.result}, "activity-start": {"activity_id": args.activity_id, "name": args.name}, "activity-end": {"activity_id": args.activity_id, "result": args.result}, "checkpoint": {"reason": args.reason}, "interrupt": {"reason": args.reason}, "end": {"status": args.status}}[args.action]
            if args.action == "end":
                payload["source_fingerprint"] = source_fingerprint(root)
            if args.action == "start":
                payload["source_fingerprint"] = source_fingerprint(root)
            append(root, args.run_id, event_id, kinds[args.action], payload)
        print(f"[RECORDED] {args.run_id}: {args.action}")
        return 0
    except (OSError, ValueError, KeyError, TypeError, AttributeError, sqlite3.Error) as error:
        print(f"[MEASUREMENT ERROR] {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
