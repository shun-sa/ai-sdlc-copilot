from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path


REPAIR_CYCLES = 3
POLICY = ".github/skills/failure-triage/policy/loop-policy.json"
DIRECTORY = "reports/loop-control"
LEDGER = DIRECTORY + "/retry-ledger.json"
SIGNATURE_FIELDS = ("origin_phase", "classification", "artifact", "requirement_reference", "test_case", "stable_error_type")
EXCLUDED = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", ".ruff_cache", "dist", "build"}
PHASE_ORDER = ("REQUIREMENTS", "ARCHITECTURE", "IMPLEMENTATION", "UNIT_TEST", "INTEGRATION_TEST", "FULL", "ACCEPTANCE_TEST", "EVALUATION")


def local(root: Path, value: str) -> Path:
    if not isinstance(value, str) or not value or Path(value).is_absolute() or ":" in value or ".." in Path(value).parts:
        raise ValueError(f"Invalid repository path: {value}")
    result = (root / value).resolve()
    if not result.is_relative_to(root.resolve()):
        raise ValueError(f"Path escapes repository: {value}")
    return result


def read(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected object: {path}")
    return value


def save(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def policy(root: Path) -> dict:
    value = read(local(root, POLICY))
    if value.get("version") != 1 or value.get("repair_cycles") != REPAIR_CYCLES or value.get("on_exhausted") != "CONTINUE_WITH_UNRESOLVED":
        raise ValueError("Expected the three-repair continuation policy")
    if not isinstance(value.get("required_checks"), dict):
        raise ValueError("required_checks is missing")
    for checks in value["required_checks"].values():
        if not isinstance(checks, list) or not checks or not all(isinstance(key, str) and key for key in checks) or len(set(checks)) != len(checks):
            raise ValueError("Required checks must be a nonempty unique string array")
    return value


def ledger(root: Path) -> dict:
    path = local(root, LEDGER)
    value = read(path) if path.is_file() else {"version": 1, "issues": {}}
    if value.get("version") != 1 or not isinstance(value.get("issues"), dict):
        raise ValueError("Invalid retry ledger")
    return value


def problems(report: dict) -> list[str]:
    errors = report.get("errors", [])
    if not isinstance(errors, list) or not all(isinstance(error, str) and error for error in errors):
        raise ValueError("Result errors must be a string array")
    if errors:
        return sorted(set(errors))
    if report.get("status") in ("PASS", "SUCCESS"):
        return []
    return ["status=" + str(report.get("status", "MISSING"))]


def identity(signature: dict) -> str:
    if not isinstance(signature, dict) or set(signature) != set(SIGNATURE_FIELDS) or not all(isinstance(value, str) for value in signature.values()):
        raise ValueError("A complete stable failure signature is required")
    if not all(signature[field].strip() for field in ("origin_phase", "classification", "artifact", "stable_error_type")):
        raise ValueError("Failure signature contains empty required fields")
    return "UNRESOLVED-" + hashlib.sha256(json.dumps(signature, sort_keys=True).encode()).hexdigest()[:16]


def archive(root: Path, source: str) -> dict:
    path = local(root, source)
    digest = sha(path)
    relative = f"{DIRECTORY}/evidence/{digest}.json"
    target = local(root, relative)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_bytes(path.read_bytes())
    if sha(target) != digest:
        raise ValueError("Archived evidence was altered")
    return {"source": source, "path": relative, "sha256": digest}


def check_evidence(root: Path, evidence: dict) -> dict:
    path = local(root, evidence["path"])
    if sha(path) != evidence["sha256"]:
        raise ValueError("Evidence digest differs")
    return read(path)


def verified_issue(root: Path, issue: dict) -> None:
    if identity(issue["signature"]) != issue["issue_id"]:
        raise ValueError("Issue identity differs")
    if issue.get("state") not in ("OPEN", "UNRESOLVED", "RESOLVED"):
        raise ValueError("Invalid issue state")
    for episode in issue.get("previous_episodes", []):
        verified_issue(root, {**issue, "previous_episodes": [], "history": episode["history"], "cycle": episode["cycle"], "state": "RESOLVED"})
    history = issue.get("history", [])
    repairs = [entry for entry in history if entry["action"] == "FAILURE"]
    cycles = [entry["cycle"] for entry in repairs]
    if not cycles or cycles != list(range(len(cycles))) or len(cycles) > REPAIR_CYCLES + 1 or issue.get("cycle") != cycles[-1]:
        raise ValueError("Repair sequence differs")
    if issue.get("state") == "RESOLVED" and history[-1]["action"] != "RESOLVED":
        raise ValueError("Resolution evidence is missing")
    if issue.get("state") == "UNRESOLVED" and cycles != [0, 1, 2, 3]:
        raise ValueError("Three completed repair cycles are required")
    if len({entry["run_id"] for entry in history}) != len(history):
        raise ValueError("Repeated run IDs cannot count as new repairs")
    for entry in history:
        report = check_evidence(root, entry["evidence"])
        actual = problems(report)
        if entry["action"] == "RESOLVED":
            if actual:
                raise ValueError("Resolution must have successful evidence")
        elif not entry["errors"] or not set(entry["errors"]).issubset(actual):
            raise ValueError("Failure evidence does not contain the recorded errors")
        if entry["action"] == "FAILURE" and entry["cycle"] > 0 and not entry.get("repair"):
            raise ValueError("Repair description is missing")


def publish(root: Path, value: dict) -> None:
    for issue in value["issues"].values():
        verified_issue(root, issue)
    save(local(root, LEDGER), value)
    unresolved = [issue for issue in value["issues"].values() if issue["state"] == "UNRESOLVED"]
    save(local(root, DIRECTORY + "/unresolved-results.json"), {"status": "UNRESOLVED" if unresolved else "CLEAR", "issues": unresolved})
    lines = ["# 未解決の検査結果", "", "検査FAILは変更しない。3回の修正後も残った事項を次工程へ引き継ぐ。", ""]
    for issue in unresolved:
        lines.extend([f"## {issue['issue_id']}", f"- 原因工程: {issue['signature']['origin_phase']}", "- 修正・再検査: 3回", f"- 影響: {issue['impact']}", f"- 推奨対応先: {issue['recommended_route']}", f"- 対象: {issue['signature']['artifact']}", "- 検査結果: FAIL（未解決）", ""])
    path = local(root, DIRECTORY + "/unresolved-results.md")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def record(root: Path, event: dict) -> str:
    config = policy(root)
    signature = event.get("signature")
    issue_id = identity(signature)
    if signature["origin_phase"] not in config["required_checks"]:
        raise ValueError("Unknown origin phase")
    value = ledger(root)
    issue = value["issues"].get(issue_id)
    if issue:
        verified_issue(root, issue)
    action = event.get("action", "FAILURE")
    if action not in ("FAILURE", "OBSERVE", "RESOLVED"):
        raise ValueError("Invalid observation action")
    run_id = event.get("run_id")
    if not isinstance(run_id, str) or not run_id.strip():
        raise ValueError("A unique actual execution run_id is required")
    result_path = event.get("validation_result")
    report = read(local(root, result_path))
    actual = problems(report)
    errors = event.get("errors", actual)
    if not isinstance(errors, list) or not all(isinstance(error, str) for error in errors):
        raise ValueError("Event errors must be an array")
    if action == "RESOLVED":
        if not issue or actual:
            raise ValueError("Resolution requires an existing issue and PASS evidence")
        cycle = issue["cycle"]
        errors = []
    else:
        if not errors or not set(errors).issubset(actual):
            raise ValueError("Only actual failed result errors may be recorded")
        cycle = event.get("cycle")
        if type(cycle) is not int:
            raise ValueError("Cycle must be an integer")
    entry = {"action": action, "cycle": cycle, "run_id": run_id, "repair": event.get("repair", ""), "errors": sorted(set(errors)), "evidence": {"source": result_path, "sha256": sha(local(root, result_path))}}
    if issue:
        prior = next((entry for entry in issue["history"] if entry["run_id"] == run_id), None)
        if prior:
            comparable = {**prior, "evidence": {key: prior["evidence"][key] for key in ("source", "sha256")}}
            if comparable != entry:
                raise ValueError("A run_id was reused for different evidence")
            return issue_id
    if action == "OBSERVE":
        if not issue or issue["state"] != "UNRESOLVED" or cycle != REPAIR_CYCLES:
            raise ValueError("OBSERVE only refreshes an already unresolved issue without another repair")
    elif action == "FAILURE":
        if issue and issue["state"] == "RESOLVED" and cycle == 0:
            issue.setdefault("previous_episodes", []).append({"history": issue["history"], "cycle": issue["cycle"]})
            issue["history"] = []
            issue["cycle"] = -1
            issue["state"] = "OPEN"
        expected = issue["cycle"] + 1 if issue else 0
        if issue and issue["state"] != "OPEN":
            raise ValueError("Do not restart or extend an exhausted/resolved loop")
        if cycle != expected or cycle > REPAIR_CYCLES or (cycle > 0 and not entry["repair"]):
            raise ValueError("Record initial failure 0, then three sequential actual repairs")
    if issue is None:
        if not event.get("impact") or not event.get("recommended_route"):
            raise ValueError("Impact and recommended route are required")
        issue = {"issue_id": issue_id, "signature": signature, "impact": event["impact"], "recommended_route": event["recommended_route"], "cycle": 0, "state": "OPEN", "history": []}
        value["issues"][issue_id] = issue
    entry["evidence"] = archive(root, result_path)
    issue["history"].append(entry)
    issue["cycle"] = cycle
    issue["state"] = "RESOLVED" if action == "RESOLVED" else "UNRESOLVED" if cycle == REPAIR_CYCLES else "OPEN"
    publish(root, value)
    return issue_id


def source_snapshot(root: Path, phase: str) -> list[dict]:
    architecture = phase in ("REQUIREMENTS", "ARCHITECTURE")
    prefixes = ["docs/requirements", ".github/project-context", ".github/skills/requirements/templates"]
    if phase == "ARCHITECTURE":
        prefixes += ["docs/architecture", "docs/addr", "docs/adr", ".github/skills/architecture/templates", ".github/skills/addr/templates"]
    if not architecture:
        prefixes = ["."]
    paths = {POLICY}
    for prefix in prefixes:
        directory = root if prefix == "." else local(root, prefix)
        for path in directory.rglob("*"):
            relative = path.relative_to(root)
            if path.is_file() and path.resolve().is_relative_to(root) and not (set(relative.parts) & EXCLUDED) and relative.parts[0] != "reports":
                paths.add(relative.as_posix())
    if phase != "REQUIREMENTS":
        paths.update("reports/architecture/" + name for name in ("design-input.json", "design-manifest.json", "addr-request.json", "addr-result.json", "cross-artifact-consistency.md"))
        manifest = root / "reports/architecture/design-manifest.json"
        if manifest.is_file():
            try:
                data = read(manifest)
                for key in ("sources", "artifacts"):
                    for item in data.get(key, []):
                        paths.add(item["path"])
            except (ValueError, KeyError, TypeError):
                pass
    return [{"path": path, "sha256": sha(local(root, path)) if local(root, path).is_file() else None} for path in sorted(paths)]


def phase_decision(root: Path, phase: str, checks: dict) -> dict:
    config = policy(root)
    if phase not in config["required_checks"] or set(checks) != set(config["required_checks"][phase]):
        raise ValueError("All configured phase checks must be supplied; none may be omitted")
    if len(set(checks.values())) != len(checks):
        raise ValueError("Different checks require separate results")
    value = ledger(root)
    for issue in value["issues"].values():
        verified_issue(root, issue)
        if issue["state"] == "OPEN":
            raise ValueError("An issue has not completed three repairs")
    unresolved = [issue for issue in value["issues"].values() if issue["state"] == "UNRESOLVED"]
    evidence = {}
    for key, relative in checks.items():
        report = read(local(root, relative))
        if report.get("audit_scope", phase) != phase:
            raise ValueError(f"Wrong audit scope: {key}")
        for error in problems(report):
            covered = any(entry["evidence"]["source"] == relative and entry["evidence"]["sha256"] == sha(local(root, relative)) and error in entry["errors"] for issue in unresolved for entry in issue["history"])
            if not covered:
                raise ValueError(f"Unrecorded current failure in {key}: {error}")
        evidence[key] = archive(root, relative)
    decision = {"status": "CONTINUE_WITH_UNRESOLVED" if unresolved else "PASS", "quality_pass": not unresolved, "phase": phase, "checks": evidence, "unresolved_ids": [issue["issue_id"] for issue in unresolved], "sources": source_snapshot(root, phase)}
    save(local(root, f"{DIRECTORY}/phase-{phase}.json"), decision)
    return decision


def verify_transition(root: Path, phase: str) -> dict:
    config = policy(root)
    decision = read(local(root, f"{DIRECTORY}/phase-{phase}.json"))
    if decision.get("phase") != phase or decision.get("status") not in ("PASS", "CONTINUE_WITH_UNRESOLVED"):
        raise ValueError("No valid phase transition decision")
    if set(decision["checks"]) != set(config["required_checks"][phase]) or decision["sources"] != source_snapshot(root, phase):
        raise ValueError("Phase checks or source baseline changed")
    value = ledger(root)
    unresolved = {identifier: issue for identifier, issue in value["issues"].items() if issue["state"] == "UNRESOLVED"}
    included = set(decision["unresolved_ids"])
    relevant = {identifier for identifier, issue in unresolved.items() if PHASE_ORDER.index(issue["signature"]["origin_phase"]) <= PHASE_ORDER.index(phase)}
    pending = any(issue["state"] == "OPEN" and PHASE_ORDER.index(issue["signature"]["origin_phase"]) <= PHASE_ORDER.index(phase) for issue in value["issues"].values())
    if not relevant.issubset(included) or not included.issubset(unresolved) or pending:
        raise ValueError("Unresolved issue set changed; regenerate the decision")
    recorded = {identifier: unresolved[identifier] for identifier in included}
    for issue in recorded.values():
        verified_issue(root, issue)
    if (decision["status"] == "PASS") != (not recorded) or decision.get("quality_pass") != (not recorded):
        raise ValueError("Unresolved failures must not be labelled PASS")
    for evidence in decision["checks"].values():
        report = check_evidence(root, evidence)
        for error in problems(report):
            if not any(entry["evidence"]["source"] == evidence["source"] and entry["evidence"]["sha256"] == evidence["sha256"] and error in entry["errors"] for issue in recorded.values() for entry in issue["history"]):
                raise ValueError("Current failure is not covered by an unresolved issue")
    return decision


def run_check(root: Path, specification: dict) -> dict:
    command = specification.get("command")
    if not isinstance(command, list) or not command or not all(isinstance(argument, str) for argument in command):
        raise ValueError("An explicit argument array is required")
    try:
        result = subprocess.run(command, cwd=root, capture_output=True, timeout=specification.get("timeout_seconds", 300))
        code = result.returncode
    except (OSError, subprocess.TimeoutExpired):
        code = -1
    report = {"status": "PASS" if code == 0 else "FAIL", "exit_code": code, "check_id": specification["check_id"], "errors": [] if code == 0 else [f"{specification['check_id']}: command exit code {code}"]}
    save(local(root, specification["result_path"]), report)
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Three repair cycles, then record unresolved results and continue")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--record", help="Repository-relative event JSON")
    group.add_argument("--decide-phase", help="Phase name")
    group.add_argument("--check-phase", help="Verify a saved transition decision")
    group.add_argument("--run-check", help="Repository-relative command specification JSON")
    parser.add_argument("--checks", help="Repository-relative check-id to result-path JSON")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        if args.record:
            print(record(root, read(local(root, args.record))))
        elif args.run_check:
            report = run_check(root, read(local(root, args.run_check)))
            print(report["status"])
            return int(report["status"] != "PASS")
        else:
            decision = phase_decision(root, args.decide_phase, read(local(root, args.checks))) if args.decide_phase else verify_transition(root, args.check_phase)
            print(decision["status"])
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"[BLOCKED] {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
