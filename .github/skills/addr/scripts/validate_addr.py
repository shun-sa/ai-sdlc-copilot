#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

import yaml

from design_common import (
    FINAL, GATE, INPUT, KINDS, REQUEST, RESULT, addr_records, digest, duplicates,
    gate_paths, load_json, local_path, objects, parse_document, requirement_ids,
    row_records, snapshots, strings, validate_design, validate_document, validate_gate, walk,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "failure-triage/scripts"))
from loop_control import REPAIR_CYCLES


def prepare_request(root: Path, reserve_count: int = 0, renew: bool = False) -> list[str]:
    errors = validate_design(root, "draft")
    if errors:
        return errors
    draft = load_json(root / INPUT, errors)
    records, discovery_errors = addr_records(root / "docs/addr")
    errors.extend(discovery_errors)
    if errors:
        return errors
    path = root / REQUEST
    if path.exists():
        previous = load_json(path, errors)
        if previous.get("design_input_sha256") == digest(root / INPUT) and not renew:
            return errors
        if not renew:
            return ["ADDR request baseline changed; invalidate prior result and use --renew-request"]
        old_result = load_json(root / RESULT, []) if (root / RESULT).is_file() else {}
        old_gate = load_json(root / GATE, []) if (root / GATE).is_file() else {}
        released = {item.get("path"): item.get("sha256") for item in objects(old_gate.get("snapshots", []), "prior Gate", []) if isinstance(item.get("path"), str)}
        for item in objects(old_result.get("output_artifacts", []), "prior outputs", []):
            candidate = local_path(root, item.get("path"), errors)
            if candidate is not None and candidate.is_file() and released.get(item.get("path")) != digest(candidate):
                errors.append("Archive prior unreleased ADDR candidates before renewing request")
        if errors:
            return errors
        archive = path.with_name(f"addr-request-{digest(path)[:12]}.json")
        if not archive.exists():
            archive.write_bytes(path.read_bytes())
    count = reserve_count or max(1, len(draft["targets"]) + len(draft["unresolved_design_decisions"]))
    if count < 1:
        return ["reserve-count must be positive"]
    reserved = set(records)
    for history in path.parent.glob("addr-request*.json"):
        previous = load_json(history, errors)
        reserved.update(strings(previous.get("addr_id_pool"), "previous pool", errors))
    if errors:
        return errors
    if any(not re.fullmatch(r"ADDR-\d{3,}", identifier) for identifier in reserved):
        return ["Historical ADDR pool contains invalid IDs"]
    highest = max([int(identifier.split("-")[1]) for identifier in reserved] + [0])
    request = {
        "source_revision": draft["source_revision"], "design_input_sha256": digest(root / INPUT),
        "addr_id_pool": [f"ADDR-{highest + offset:03d}" for offset in range(1, count + 1)],
        "existing_addr_ids": sorted(records), "target_criticality": draft["targets"],
        "recovery_policy": {"max_attempts": REPAIR_CYCLES}, "attempt": 0,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(request, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return []


def validate_addr(root: Path, final: bool = False) -> list[str]:
    root = root.resolve()
    errors = []
    draft = load_json(root / INPUT, errors)
    request = load_json(root / REQUEST, errors)
    result = load_json(root / RESULT, errors)
    if errors:
        return errors
    targets = objects(draft.get("targets"), "input targets", errors)
    strings([item.get("target_id") for item in targets], "input target IDs", errors)
    objects(draft.get("unresolved_design_decisions"), "input decisions", errors)
    if errors:
        return errors
    snapshots(root, draft.get("sources"), "ADDR input sources", errors)
    for record in (request, result):
        if record.get("design_input_sha256") != digest(root / INPUT) or record.get("source_revision") != draft.get("source_revision"):
            errors.append("ADDR input revision/hash differs from design input")
    if request.get("target_criticality") != draft.get("targets"):
        errors.append("ADDR target criticality changed")
    pool = strings(request.get("addr_id_pool"), "ADDR pool", errors)
    prior = strings(request.get("existing_addr_ids"), "existing ADDRs", errors)
    duplicates(pool, "ADDR pool", errors)
    if any(not re.fullmatch(r"ADDR-\d{3,}", identifier) for identifier in pool) or set(pool) & set(prior):
        errors.append("ADDR pool contains invalid or previously allocated IDs")
    recovery = request.get("recovery_policy", {})
    maximum = recovery.get("max_attempts") if isinstance(recovery, dict) else None
    attempt = request.get("attempt")
    if type(maximum) is not int or maximum < 0 or type(attempt) is not int or not 0 <= attempt <= maximum:
        errors.append("Invalid recovery attempt or max_attempts")
    result_recovery = result.get("autonomous_recovery", {})
    if not isinstance(result_recovery, dict) or result_recovery.get("attempt") != attempt or result_recovery.get("max_attempts") != maximum:
        errors.append("ADDR recovery bounds differ from request")
    if result.get("human_intervention_requested") is not False:
        errors.append("ADDR must return recovery to Orchestrator, not request human intervention")
    if result.get("status") != "SUCCESS" or result.get("result") not in ("SUCCESS", "SUCCESS_WITH_ASSUMPTIONS"):
        errors.append("ADDR result is not complete SUCCESS; partial/blocked/failed cannot pass Gate")
    if result.get("blocking_issues") != []:
        errors.append("ADDR has blocking issues")
    known = requirement_ids(root)
    assumptions = objects(result.get("assumptions"), "assumptions", errors)
    if result.get("result") == "SUCCESS_WITH_ASSUMPTIONS" and not assumptions:
        errors.append("SUCCESS_WITH_ASSUMPTIONS requires assumptions")
    for assumption in assumptions:
        basis = strings(assumption.get("basis_ids"), "assumption basis", errors)
        targets = strings(assumption.get("affected_target_ids"), "assumption targets", errors)
        allowed_targets = [item.get("target_id") for item in draft.get("targets", []) if isinstance(item, dict)]
        if not basis or not set(basis).issubset(known) or not targets or not set(targets).issubset(allowed_targets):
            errors.append("Assumption basis or targets are invalid")
        if not assumption.get("assumption_id") or not assumption.get("statement") or type(assumption.get("reversible")) is not bool or not assumption.get("verification_method"):
            errors.append("Assumption lacks ID, statement, reversibility or verification method")
    records, discovery_errors = addr_records(root / "docs/addr")
    errors.extend(discovery_errors)
    outputs = objects(result.get("output_artifacts"), "ADDR outputs", errors)
    snapshots(root, outputs, "ADDR outputs", errors)
    output_ids = strings([item.get("addr_id") for item in outputs], "output ADDR IDs", errors)
    duplicates(output_ids, "output ADDR IDs", errors)
    if not set(output_ids).issubset(pool):
        errors.append("Output ADDR ID is outside reserved pool")
    for item in outputs:
        path = local_path(root, item.get("path"), errors)
        record = records.get(item.get("addr_id"), {}) if isinstance(item.get("addr_id"), str) else {}
        if path is None or not path.is_relative_to(root / "docs/addr") or str(path) != record.get("path"):
            errors.append("ADDR output path/ID mismatch")
        if record.get("native_status") != "ACTIVE":
            errors.append("New ADDR output must be ACTIVE")
        if record.get("metadata", {}).get("source_revision") != draft.get("source_revision"):
            errors.append("ADDR metadata source_revision differs")
    if set(records) - set(prior) != set(output_ids):
        errors.append("Unregistered or missing new ADDR document")
    choices = objects(result.get("addr_creation_results"), "ADDR creation results", errors)
    keys = strings([item.get("candidate_key") for item in choices], "result candidate keys", errors)
    duplicates(keys, "result candidate keys", errors)
    candidate_keys = {item.get("candidate_key") for item in draft.get("unresolved_design_decisions", []) if isinstance(item, dict) and isinstance(item.get("candidate_key"), str)}
    if not candidate_keys.issubset(keys):
        errors.append("Input decision candidate has no result")
    target_ids = {item.get("target_id") for item in draft.get("targets", []) if isinstance(item, dict) and isinstance(item.get("target_id"), str)}
    covered = set()
    assigned = []
    for choice in choices:
        target = choice.get("target_id")
        if not isinstance(target, str) or target not in target_ids or not choice.get("reason") or type(choice.get("needed")) is not bool:
            errors.append("Decision result lacks known target, reason or boolean needed")
            continue
        covered.add(target)
        if choice["needed"]:
            assigned.append(choice.get("addr_id"))
            record = records.get(choice.get("addr_id"), {}) if isinstance(choice.get("addr_id"), str) else {}
            if record.get("metadata", {}).get("target_id") != target:
                errors.append("ADDR metadata target differs from decision result")
        elif choice.get("addr_id") is not None:
            errors.append("Unnecessary ADDR consumed an ID")
    if covered != target_ids:
        errors.append("ADDR necessity review does not cover every target")
    assigned = strings(assigned, "assigned IDs", errors)
    if Counter(assigned) != Counter(output_ids):
        errors.append("Created ADDRs and decision assignments differ")
    if assigned != [identifier for identifier in pool if identifier in assigned]:
        errors.append("ADDR IDs not allocated in pool order")
    unused = strings(result.get("unused_addr_ids"), "unused IDs", errors)
    if unused != [identifier for identifier in pool if identifier not in assigned]:
        errors.append("Unused ADDR pool accounting differs")
    template_path = root / ".github/skills/addr/templates/addr.md"
    if not template_path.is_file():
        errors.append("Canonical ADDR template missing")
        return errors
    template = template_path.read_text(encoding="utf-8-sig")
    template_metadata = yaml.safe_load(template.split("---", 2)[1])
    for identifier, record in records.items():
        if record["native_status"] != "ACTIVE":
            continue
        metadata = record["metadata"]
        if set(metadata) != set(template_metadata) or any(not isinstance(value, str) or not value for value in metadata.values()):
            errors.append(f"ADDR metadata differs from canonical fields: {identifier}")
        design_type = metadata.get("design_type")
        if not isinstance(design_type, str) or design_type not in KINDS:
            errors.append(f"Invalid ADDR design_type: {identifier}")
            continue
        expected = parse_document(template)
        for section in walk(expected):
            if section.title.startswith("6. "):
                section.children = [child for child in section.children if child.title.startswith(KINDS[design_type])]
        from design_common import compare_structure
        text = Path(record["path"]).read_text(encoding="utf-8-sig")
        compare_structure(expected, parse_document(text), Path(record["path"]), errors)
        if re.search(r"\{\{[^{}]+\}\}", text):
            errors.append(f"Unresolved ADDR placeholder: {identifier}")
        if Path(record["path"]).stem != identifier:
            errors.append(f"ADDR filename differs from ID: {identifier}")
        if not record["related_requirements"] or not set(record["related_requirements"]).issubset(known):
            errors.append(f"ADDR has missing/unknown requirement: {identifier}")
        document = parse_document(text)
        options = list(row_records(document, {"選択肢ID", "選定結果"}))
        if sum(row["選定結果"] == "SELECTED" for row in options) != 1 or any(row["選定結果"] not in ("SELECTED", "NOT_SELECTED") for row in options):
            errors.append(f"ADDR must select exactly one real option: {identifier}")
        for row in row_records(document, {"ID", "実装拘束"}):
            if row["実装拘束"] not in ("MUST", "MUST_NOT", "SHOULD"):
                errors.append(f"Invalid ADDR implementation constraint: {identifier}")
        local_ids = [row["ID"] for row in row_records(document, {"ID"}) if re.fullmatch(r"(?:DC|DD|INV|ASM)-\d+", row["ID"])]
        duplicates(local_ids, f"{identifier} local IDs", errors)
    links = objects(result.get("artifact_link_updates"), "ADDR link updates", errors)
    if final:
        manifest = load_json(root / FINAL, errors)
        artifacts = {item.get("artifact_id"): item for item in objects(manifest.get("artifacts"), "FINAL artifacts", errors) if isinstance(item.get("artifact_id"), str)}
        for link in links:
            artifact = artifacts.get(link.get("artifact_id"), {}) if isinstance(link.get("artifact_id"), str) else {}
            if link.get("requested_action") != "LINK_ADDR" or link.get("related_addr_id") not in artifact.get("related_addr_ids", []):
                errors.append("LINK_ADDR request not reflected in FINAL design")
        referenced = {identifier for artifact in artifacts.values() for identifier in strings(artifact.get("related_addr_ids"), "FINAL ADDR refs", errors)}
        if not set(assigned).issubset(referenced):
            errors.append("Created ADDR missing from final design/task references")
        if not referenced.issubset({identifier for identifier, record in records.items() if record["native_status"] == "ACTIVE"}):
            errors.append("FINAL design references missing or superseded ADDR")
    return errors


def write_gate(root: Path) -> list[str]:
    errors = validate_design(root, "final") + validate_addr(root, final=True)
    if errors:
        return errors
    paths = gate_paths(root)
    for path in paths:
        if not (root / path).is_file():
            errors.append(f"Architecture Gate source missing: {path}")
    if errors:
        return errors
    consistency_template = root / ".github/skills/architecture/templates/cross-artifact-consistency-analysis.template.md"
    consistency_path = root / "reports/architecture/cross-artifact-consistency.md"
    errors.extend(validate_document(consistency_template.read_text(encoding="utf-8-sig"), consistency_path.read_text(encoding="utf-8-sig"), consistency_path))
    if errors:
        return errors
    gate = {"status": "PASS", "snapshots": [{"path": path, "sha256": digest(root / path)} for path in sorted(paths)], "assurance": []}
    for kind, directory in (("quality-review", "quality-review"), ("security-review", "security-review"), ("traceability", "traceability")):
        path = f"reports/{directory}/validation-result.json"
        report = load_json(root / path, errors)
        if report.get("source_baseline_sha256") != digest(root / FINAL):
            errors.append(f"Assurance result is not bound to current FINAL manifest: {kind}")
        archived = f"reports/architecture/assurance/{kind}-validation-result.json"
        if (root / path).is_file():
            (root / archived).parent.mkdir(parents=True, exist_ok=True)
            (root / archived).write_bytes((root / path).read_bytes())
        gate["assurance"].append({"kind": kind, "path": archived, "sha256": digest(root / archived) if (root / archived).is_file() else ""})
    errors.extend(validate_gate(root, gate))
    if not errors:
        (root / GATE).write_text(json.dumps(gate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate ADDR contracts, templates and architecture release Gate")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--prepare-request", action="store_true")
    parser.add_argument("--renew-request", action="store_true")
    parser.add_argument("--reserve-count", type=int, default=0)
    parser.add_argument("--final", action="store_true")
    parser.add_argument("--write-gate", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    errors = prepare_request(root, args.reserve_count, args.renew_request) if args.prepare_request else write_gate(root) if args.write_gate else validate_addr(root, args.final)
    for error in errors:
        print(f"- {error}")
    print("[FAIL] ADDR validation" if errors else "[PASS] ADDR validation")
    return int(bool(errors))


if __name__ == "__main__":
    sys.exit(main())
