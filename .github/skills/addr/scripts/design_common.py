from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

import yaml


SKILLS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SKILLS / "requirements/scripts"))
from validate_requirements_structure import (
    LINK, compare_structure, parse_document, resolve_link, row_records,
    validate_document, visible_text, walk,
)


INPUT = "reports/architecture/design-input.json"
FINAL = "reports/architecture/design-manifest.json"
REQUEST = "reports/architecture/addr-request.json"
RESULT = "reports/architecture/addr-result.json"
GATE = "reports/architecture/architecture-gate.json"
REQ_INDEX = "docs/requirements/requirements.md"
STEERING = ".github/project-context/project-ai-steering.md"
TEMPLATES = ".github/skills/architecture/templates"
KINDS = {"画面": "A.", "帳票": "B.", "外部インターフェース": "C.", "バッチ": "D.", "権限・認証": "E.", "非機能": "F."}
ID_PATTERN = re.compile(r"\b[A-Z][A-Z0-9_]*-\d+\b")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def local_path(root: Path, value, errors: list[str]) -> Path | None:
    if not isinstance(value, str) or not value or Path(value).is_absolute() or re.match(r"[A-Za-z]:", value):
        errors.append(f"Invalid repository path: {value}")
        return None
    path = (root / value).resolve()
    if not path.is_relative_to(root.resolve()):
        errors.append(f"Path escapes repository: {value}")
        return None
    return path


def load_json(path: Path, errors: list[str]) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(value, dict):
            raise ValueError("Expected JSON object")
        return value
    except (OSError, ValueError) as error:
        errors.append(f"{path}: {error}")
        return {}


def objects(value, label: str, errors: list[str]) -> list[dict]:
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        errors.append(f"{label}: expected object array")
        return []
    return value


def strings(value, label: str, errors: list[str]) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        errors.append(f"{label}: expected string array")
        return []
    return value


def duplicates(values, label: str, errors: list[str]) -> None:
    for value, count in Counter(values).items():
        if count > 1:
            errors.append(f"{label}: duplicate {value}")


def requirement_ids(root: Path) -> set[str]:
    path = root / REQ_INDEX
    if not path.is_file():
        return set()
    text = path.read_text(encoding="utf-8-sig")
    sections = re.findall(r"^## (?:機能要件|非機能要件)\s*\n(.*?)(?=^## |\Z)", text, re.MULTILINE | re.DOTALL)
    if sections:
        return {identifier for section in sections for identifier in re.findall(r"^-\s+([^\s:]+):", section, re.MULTILINE)}
    return {identifier for identifier in ID_PATTERN.findall(text) if not identifier.startswith(("ADR-", "ADDR-"))}


def baseline_paths(root: Path) -> set[str]:
    required = {REQ_INDEX, STEERING}
    path = root / REQ_INDEX
    if path.is_file():
        for link in LINK.findall(visible_text(path.read_text(encoding="utf-8-sig"))):
            target = resolve_link(path, link, root)
            if target is not None and target.is_file():
                required.add(target.relative_to(root).as_posix())
    return required


def snapshots(root: Path, records, label: str, errors: list[str]) -> set[str]:
    paths = []
    for record in objects(records, label, errors):
        path = local_path(root, record.get("path"), errors)
        if path is None:
            continue
        paths.append(path.relative_to(root).as_posix())
        if not path.is_file():
            errors.append(f"{label}: missing {path}")
        elif record.get("sha256") != digest(path):
            errors.append(f"{label}: stale hash {path}")
    duplicates(paths, label, errors)
    return set(paths)


def read_addr(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8-sig")
    if not text.startswith("---") or len(text.split("---", 2)) < 3:
        raise ValueError(f"ADDR front matter missing: {path}")
    metadata = yaml.safe_load(text.split("---", 2)[1])
    if not isinstance(metadata, dict):
        raise ValueError(f"ADDR front matter must be an object: {path}")
    return metadata, text


def addr_records(directory: Path) -> tuple[dict, list[str]]:
    result = {}
    errors = []
    for path in sorted(directory.glob("*.md")):
        try:
            metadata, text = read_addr(path)
            identifier = metadata.get("addr_id")
            if not isinstance(identifier, str) or not re.fullmatch(r"ADDR-\d{3,}", identifier):
                raise ValueError(f"Invalid ADDR ID: {path}")
            if identifier in result:
                raise ValueError(f"Duplicate ADDR ID: {identifier}")
            status = metadata.get("status")
            if status not in ("ACTIVE", "SUPERSEDED"):
                raise ValueError(f"Invalid ADDR status: {path}")
            related = set()
            document = parse_document(text)
            for row in row_records(document, {"区分", "参照先"}, "2."):
                if row["区分"] == "要件":
                    related.update(ID_PATTERN.findall(row["参照先"]))
            result[identifier] = {
                "id": identifier, "path": str(path),
                "status": "Accepted" if status == "ACTIVE" else "Superseded",
                "native_status": status, "related_requirements": sorted(related),
                "metadata": metadata,
            }
        except (OSError, ValueError, yaml.YAMLError) as error:
            errors.append(str(error))
    return result, errors


def validate_task_plan(template: str, text: str, path: Path, errors: list[str], known_requirements: set[str]) -> None:
    expected = parse_document(template)
    actual = parse_document(text)
    rows = list(row_records(actual, {"Task ID", "Depends On"}, "4."))
    identifiers = [row["Task ID"] for row in rows]
    duplicates(identifiers, "Task ID", errors)
    detail_sections = [section for section in walk(actual) if section.level == 3 and section.title.startswith("TASK-")]
    detail_ids = [section.title.split()[0] for section in detail_sections]
    if Counter(identifiers) != Counter(detail_ids):
        errors.append("Task Summary and Details differ")
    for section in walk(expected):
        if section.title.startswith("6. ") and section.children:
            prototype = section.children[0]
            section.children = [type(prototype)(prototype.level, prototype.title.replace("TASK-001", identifier), prototype.body, prototype.children) for identifier in identifiers]
    compare_structure(expected, actual, path, errors)
    if re.search(r"<\w[^<>\n]*>|\{\{", visible_text(text)):
        errors.append(f"{path}: unresolved placeholder")
    known = set(identifiers)
    graph = {}
    for row in rows:
        dependencies = set(re.findall(r"TASK-\d+", row["Depends On"]))
        if not dependencies.issubset(known):
            errors.append(f"Task dependency missing: {row['Task ID']}")
        graph[row["Task ID"]] = dependencies
        if not set(ID_PATTERN.findall(row.get("Related Requirement", ""))).issubset(known_requirements):
            errors.append(f"Task references unknown requirement: {row['Task ID']}")
    for section in detail_sections:
        identifier = section.title.split()[0]
        values = [row["内容"] for row in row_records(section, {"項目", "内容"}) if row["項目"] == "Depends On"]
        if len(values) != 1 or set(re.findall(r"TASK-\d+", values[0])) != graph.get(identifier, set()):
            errors.append(f"Task detail dependencies differ from summary: {identifier}")
    waves = {}
    for row in row_records(actual, {"Wave", "Task IDs"}, "5."):
        if not row["Wave"].isdigit():
            errors.append("Task Wave must be a positive integer")
            continue
        for identifier in re.findall(r"TASK-\d+", row["Task IDs"]):
            if identifier in waves or identifier not in known:
                errors.append(f"Duplicate or unknown task in Wave: {identifier}")
            waves[identifier] = int(row["Wave"])
    if set(waves) != known or not known:
        errors.append("Task Wave coverage differs from summary")
    for identifier, dependencies in graph.items():
        if any(waves.get(dependency, 0) >= waves.get(identifier, 0) for dependency in dependencies):
            errors.append(f"Task Wave violates dependency order: {identifier}")
    visiting, visited = set(), set()

    def visit(identifier: str) -> None:
        if identifier in visiting:
            errors.append(f"Task dependency cycle: {identifier}")
            return
        if identifier in visited:
            return
        visiting.add(identifier)
        for dependency in graph.get(identifier, set()):
            visit(dependency)
        visiting.remove(identifier)
        visited.add(identifier)

    for identifier in graph:
        visit(identifier)


def validate_design(root: Path, stage: str) -> list[str]:
    root = root.resolve()
    errors = []
    manifest = load_json(root / (INPUT if stage == "draft" else FINAL), errors)
    if not manifest:
        return errors
    if manifest.get("version") != 1 or manifest.get("stage") != stage.upper() or not manifest.get("source_revision"):
        errors.append("Invalid design manifest version, stage or source_revision")
    sources = snapshots(root, manifest.get("sources"), "design sources", errors)
    missing = baseline_paths(root) - sources
    if missing:
        errors.append(f"Missing baseline source snapshots: {sorted(missing)}")
    known = requirement_ids(root)
    targets = objects(manifest.get("targets"), "targets", errors)
    identifiers = strings([target.get("target_id") for target in targets], "target IDs", errors)
    duplicates(identifiers, "target IDs", errors)
    if not targets:
        errors.append("Design targets must not be empty")
    for target in targets:
        basis = strings(target.get("basis_ids"), "target basis", errors)
        if target.get("criticality") not in ("MANDATORY", "OPTIONAL") or not basis or not set(basis).issubset(known):
            errors.append(f"Invalid target criticality or basis: {target.get('target_id')}")
    candidates = objects(manifest.get("unresolved_design_decisions"), "unresolved decisions", errors)
    duplicates(strings([item.get("candidate_key") for item in candidates], "candidate keys", errors), "candidate keys", errors)
    for candidate in candidates:
        related = strings(candidate.get("related_requirement_ids"), "candidate requirements", errors)
        if candidate.get("target_id") not in identifiers or not related or not set(related).issubset(known):
            errors.append("Invalid unresolved decision target or requirement")
    if stage == "final" and candidates:
        errors.append("FINAL design contains unresolved decisions")
    artifacts = objects(manifest.get("artifacts"), "design artifacts", errors)
    snapshots(root, artifacts, "design artifacts", errors)
    artifact_ids = strings([item.get("artifact_id") for item in artifacts], "artifact IDs", errors)
    duplicates(artifact_ids, "artifact IDs", errors)
    task_count = 0
    for artifact in artifacts:
        path = local_path(root, artifact.get("path"), errors)
        if path is None or not path.is_file():
            continue
        related = strings(artifact.get("related_requirement_ids"), "design requirements", errors)
        strings(artifact.get("related_addr_ids"), "design ADDRs", errors)
        if not related or not set(related).issubset(known):
            errors.append(f"Unknown design requirement: {path}")
        kind = artifact.get("template")
        if kind == "provided":
            if path.relative_to(root).as_posix() not in sources:
                errors.append(f"Provided design is not a source: {path}")
            continue
        if kind not in ("file-definition", "implementation-task-list"):
            errors.append(f"Unknown design template: {kind}")
            continue
        if not path.is_relative_to(root / "docs/architecture"):
            errors.append(f"Design output outside docs/architecture: {path}")
        template_path = root / TEMPLATES / f"{kind}.template.md"
        if not template_path.is_file():
            errors.append(f"Missing design template: {template_path}")
            continue
        template = template_path.read_text(encoding="utf-8-sig")
        text = path.read_text(encoding="utf-8-sig")
        if kind == "implementation-task-list":
            task_count += 1
            validate_task_plan(template, text, path, errors, known)
        else:
            errors.extend(validate_document(template, text, path))
    if stage == "final":
        draft = load_json(root / INPUT, errors)
        if not (root / INPUT).is_file() or manifest.get("design_input_sha256") != digest(root / INPUT):
            errors.append("FINAL design has stale DRAFT baseline")
        if manifest.get("source_revision") != draft.get("source_revision"):
            errors.append("FINAL design source revision differs")
        if manifest.get("sources") != draft.get("sources") or manifest.get("targets") != draft.get("targets"):
            errors.append("FINAL design changed sources or target criticality")
        if task_count != 1:
            errors.append("FINAL design requires exactly one implementation task list")
    return errors


def gate_paths(root: Path) -> set[str]:
    errors = []
    manifest = load_json(root / FINAL, errors)
    paths = {INPUT, FINAL, REQUEST, RESULT, "reports/architecture/cross-artifact-consistency.md"} | baseline_paths(root)
    paths.update(path.relative_to(root).as_posix() for path in (root / TEMPLATES).glob("*.md"))
    paths.add(".github/skills/addr/templates/addr.md")
    for key in ("sources", "artifacts"):
        entries = manifest.get(key)
        if isinstance(entries, list):
            paths.update(item["path"] for item in entries if isinstance(item, dict) and isinstance(item.get("path"), str))
    paths.update(path.relative_to(root).as_posix() for directory in ("docs/addr", "docs/adr") for path in (root / directory).glob("*.md"))
    return paths


def validate_gate(root: Path, candidate: dict | None = None) -> list[str]:
    errors = []
    gate = load_json(root / GATE, errors) if candidate is None else candidate
    if gate.get("status") != "PASS":
        errors.append("Architecture Gate is not PASS")
    actual = snapshots(root, gate.get("snapshots"), "Architecture Gate", errors)
    if actual != gate_paths(root):
        errors.append("Architecture Gate snapshot coverage differs")
    evidence = objects(gate.get("assurance"), "Gate assurance", errors)
    expected = {"quality-review", "security-review", "traceability"}
    kinds = strings([item.get("kind") for item in evidence], "Gate Assurance kinds", errors)
    if set(kinds) != expected or len(evidence) != 3:
        errors.append("Architecture Gate requires three Assurance results")
    snapshots(root, evidence, "Gate assurance", errors)
    for item in evidence:
        path = local_path(root, item.get("path"), errors)
        report = load_json(path, errors) if path is not None else {}
        if report.get("status") != "PASS" or report.get("audit_scope") != "ARCHITECTURE":
            errors.append("Architecture Gate requires ARCHITECTURE PASS evidence")
        if (root / FINAL).is_file() and report.get("source_baseline_sha256") != digest(root / FINAL):
            errors.append("Architecture Gate Assurance baseline changed")
    return errors
