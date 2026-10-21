from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree

from acceptance_common import canonical_json_sha256, parse_datetime, read_json, write_json


REQUIRED = ("case_id", "title", "requirement_id", "requirement_type", "precondition", "steps", "expected_result")
DETAIL_FIELDS = {"前提条件": "precondition", "操作・手順": "steps", "期待結果": "expected_result", "PASS条件": "pass_rule", "FAIL条件": "fail_rule", "BLOCKED条件": "blocked_rule", "測定・許容条件": "measurement", "証跡": "evidence_hint", "備考": "notes"}
NAMESPACE = {"sheet": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clock() -> str:
    return datetime.now(timezone.utc).isoformat()


def fingerprint(repo_root: Path) -> str:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "evaluation/scripts"))
    from experiment_recorder import source_fingerprint
    return source_fingerprint(repo_root)


def external(path: Path, repo_root: Path) -> Path:
    resolved = path.resolve()
    if resolved.is_relative_to(repo_root.resolve()):
        raise ValueError("Sheet preparation input/workspace must be outside the development repository.")
    return resolved


def local(workspace: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or "\\" in relative or ":" in relative:
        raise ValueError("Expected a workspace-relative POSIX path.")
    parts = PurePosixPath(relative)
    if parts.is_absolute() or ".." in parts.parts:
        raise ValueError("Path escapes evaluation workspace.")
    path = workspace / relative
    if not path.resolve().is_relative_to(workspace.resolve()) or any((workspace / Path(*parts.parts[:index])).is_symlink() for index in range(1, len(parts.parts) + 1)):
        raise ValueError("Symlink/path escapes evaluation workspace.")
    return path


def read_xlsx(path: Path) -> dict[str, list[list[str]]]:
    with zipfile.ZipFile(path) as archive:
        if len(archive.infolist()) > 10000 or sum(item.file_size for item in archive.infolist()) > 100_000_000:
            raise ValueError("Workbook exceeds import size limits.")

        def xml(name):
            payload = archive.read(name)
            if b"<!DOCTYPE" in payload.upper() or b"<!ENTITY" in payload.upper():
                raise ValueError("Workbook XML declarations are not supported.")
            return ElementTree.fromstring(payload)

        def string_value(element):
            values = []
            for child in element:
                if child.tag == "{" + NAMESPACE["sheet"] + "}t":
                    values.append(child.text or "")
                elif child.tag == "{" + NAMESPACE["sheet"] + "}r":
                    values.extend(part.text or "" for part in child.findall("sheet:t", NAMESPACE))
            return "".join(values)

        shared = []
        if "xl/sharedStrings.xml" in archive.namelist():
            shared = [string_value(part) for part in xml("xl/sharedStrings.xml").findall("sheet:si", NAMESPACE)]
        relations = {item.get("Id"): item.get("Target") for item in xml("xl/_rels/workbook.xml.rels") if item.get("TargetMode") != "External"}
        sheets = {}
        for sheet in xml("xl/workbook.xml").findall("sheet:sheets/sheet:sheet", NAMESPACE):
            target = relations[sheet.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")]
            name = target.lstrip("/") if target.startswith("/") else "xl/" + target
            rows = []
            for row in xml(name).findall("sheet:sheetData/sheet:row", NAMESPACE):
                cells = []
                for cell in row:
                    reference = cell.get("r", "")
                    letters = re.match(r"[A-Z]+", reference)
                    if not letters:
                        raise ValueError("Workbook cell must have a column reference.")
                    column = 0
                    for letter in letters.group():
                        column = column * 26 + ord(letter) - ord("A") + 1
                    if column > 500:
                        continue
                    while len(cells) < column:
                        cells.append("")
                    value = cell.find("sheet:v", NAMESPACE)
                    text = value.text or "" if value is not None else ""
                    if cell.find("sheet:f", NAMESPACE) is not None:
                        text = {"formula": True}
                    elif cell.get("t") == "s":
                        text = shared[int(text)]
                    elif cell.get("t") == "inlineStr":
                        text = string_value(cell.find("sheet:is", NAMESPACE))
                    cells[column - 1] = text
                rows.append(cells)
            sheets[sheet.get("name")] = rows
        return sheets


def table(rows: list[list], key: str) -> list[dict]:
    for index, row in enumerate(rows):
        if key in row:
            headers = row
            if len(set(headers)) != len(headers):
                raise ValueError("Duplicate table headers.")
            return [dict(zip(headers, values + [""] * (len(headers) - len(values)))) for values in rows[index + 1:] if any(value != "" for value in values)]
    raise ValueError(f"Table header not found: {key}")


def workbook_cases(path: Path) -> list[dict]:
    sheets = read_xlsx(path)
    if "受入項目" not in sheets:
        if len(sheets) != 1:
            raise ValueError("Use the full reference workbook or a single flat acceptance table.")
        return table(next(iter(sheets.values())), "case_id")
    if "受入詳細" not in sheets:
        raise ValueError("受入詳細 is required; the summary sheet alone loses expected conditions.")
    definitions = {}
    detail_records = {}
    for row in table(sheets["受入詳細"], "case_id"):
        identifier, label = row["case_id"], row["項目"]
        if not isinstance(identifier, str) or not isinstance(label, str) or not isinstance(row["内容"], str):
            raise ValueError("Definition cells must contain literal text, not formulas.")
        ordinal = int(row["分割番号"])
        parts = definitions.setdefault(identifier, {}).setdefault(label, {})
        if ordinal in parts or ordinal < 1:
            raise ValueError("Duplicate/invalid detail fragment number.")
        parts[ordinal] = row["内容"]
        detail_records.setdefault(identifier, []).append(row)
    cases = []
    for row in table(sheets["受入項目"], "case_id"):
        identifier = row["case_id"]
        if not isinstance(identifier, str) or identifier not in definitions:
            raise ValueError("Acceptance row has no matching full definition.")
        if not isinstance(row["関連要件ID"], str):
            raise ValueError("Requirement IDs must be literal text.")
        identifiers = [value.strip() for value in row["関連要件ID"].split(",") if value.strip()]
        primary = next((value for value in identifiers if value.startswith("NFR-")), "") if row.get("区分") == "非機能" else next(iter(identifiers), "")
        case = {"case_id": identifier, "title": row["試験項目"], "requirement_id": primary, "requirement_ids": identifiers, "requirement_type": "NON_FUNCTIONAL" if primary.startswith("NFR-") else "FUNCTIONAL", "source_ac_id": row.get("根拠AC", ""), "source_details": {}}
        case.update(source_row=row, source_detail_rows=detail_records[identifier])
        for label, parts in definitions[identifier].items():
            if sorted(parts) != list(range(1, len(parts) + 1)):
                raise ValueError("Missing definition fragment.")
            text = "".join(parts[index] for index in sorted(parts))
            case["source_details"][label] = text
            if label in DETAIL_FIELDS:
                case[DETAIL_FIELDS[label]] = text
        cases.append(case)
    extra = set(definitions) - {case["case_id"] for case in cases}
    supplementary = {row["case_id"] for row in table(sheets["補足NFR"], "case_id")} if "補足NFR" in sheets else set()
    if extra - supplementary:
        raise ValueError("Unmatched acceptance definitions; do not silently drop cases.")
    return cases


def load_cases(source: Path) -> list[dict]:
    suffix = source.suffix.lower()
    if suffix == ".json":
        document = json.loads(source.read_text(encoding="utf-8-sig"))
        if isinstance(document, dict) and document.get("document_kind") != "ACCEPTANCE_CASE_DEFINITIONS_NOT_EXECUTION_MANIFEST":
            raise ValueError("JSON must be acceptance case definitions, not an executable manifest.")
        cases = document.get("cases") if isinstance(document, dict) else document
    elif suffix == ".csv":
        with source.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            if len(reader.fieldnames or []) != len(set(reader.fieldnames or [])):
                raise ValueError("Duplicate CSV headers.")
            cases = list(reader)
    elif suffix == ".xlsx":
        cases = workbook_cases(source)
    else:
        raise ValueError("Supported sheet formats: .xlsx, .csv, .json.")
    if not isinstance(cases, list) or not cases or len(cases) > 10000:
        raise ValueError("A non-empty acceptance case table is required (maximum 10000).")
    seen = set()
    for case in cases:
        if not isinstance(case, dict) or any(not isinstance(case.get(key), str) or not case[key].strip() for key in REQUIRED):
            raise ValueError("Each case needs literal non-empty fields: " + ", ".join(REQUIRED))
        identifier = case["case_id"]
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,99}", identifier) or identifier in seen:
            raise ValueError("Invalid/duplicate case_id: " + identifier)
        seen.add(identifier)
        if case["requirement_type"] not in ("FUNCTIONAL", "NON_FUNCTIONAL"):
            raise ValueError("Invalid requirement_type: " + identifier)
        for value in case.values():
            if isinstance(value, dict) and value.get("formula"):
                raise ValueError("Source formula cells are not allowed.")
    return cases


def validate_context(context: dict, exposed: str) -> None:
    if not isinstance(context, dict):
        raise ValueError("Run context must be an object.")
    if context.get("status") not in ("COMPLETE", "COMPLETE_WITH_UNRESOLVED"):
        raise ValueError("Sheet preparation requires recorded SDLC completion.")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", str(context.get("run_id", ""))):
        raise ValueError("Invalid run_id.")
    completed_at = parse_datetime(context.get("sdlc_completed_at"))
    exposed_at = parse_datetime(exposed)
    if not completed_at <= exposed_at <= parse_datetime(clock()):
        raise ValueError("Actual exposure must be after SDLC completion and not in the future.")


def import_sheet(repo_root: Path, source: Path, workspace: Path, run_context: Path, exposed: str) -> dict:
    source = external(source, repo_root)
    workspace = external(workspace, repo_root)
    if workspace.exists() and any(workspace.iterdir()):
        raise ValueError("Use a new empty evaluation workspace; never overwrite an earlier attempt.")
    context = read_json(run_context)
    if not isinstance(context, dict):
        raise ValueError("Run context must be an object.")
    expected_context = repo_root / "reports/experiments" / str(context.get("run_id")) / "run-context.json"
    if expected_context.resolve() != run_context.resolve():
        raise ValueError("Use the target repository's recorded run-context.json.")
    validate_context(context, exposed)
    target_fingerprint = fingerprint(repo_root)
    journal = expected_context.parent / "events.sqlite3"
    if journal.is_file():
        from experiment_recorder import load_events, replay
        ended = replay(load_events(repo_root, context["run_id"]))["ended"]
        if not ended or ended["at"] != context["sdlc_completed_at"] or ended["payload"]["status"] != context["status"] or ended["payload"]["source_fingerprint"] != target_fingerprint:
            raise ValueError("Run context/target source does not match the recorded development end.")
    cases = load_cases(source)
    payload = source.read_bytes()
    bundle = {"schema_version": 1, "run_id": context["run_id"], "sdlc_completed_at": context["sdlc_completed_at"], "evaluation_data_exposed_at": exposed, "target_repo": str(repo_root.resolve()), "target_fingerprint": target_fingerprint, "run_context": str(run_context.resolve()), "run_context_sha256": digest(run_context), "source_name": "source" + source.suffix.lower(), "source_sha256": hashlib.sha256(payload).hexdigest(), "cases": cases}
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / bundle["source_name"]).write_bytes(payload)
    write_json(workspace / "case-bundle.json", bundle)
    write_json(workspace / "bindings.json", {"cases": [{"case_id": case["case_id"], "execution_type": "UNBOUND", "command": [], "test_files": [], "assertion_map": {}, "blocked_reason": ""} for case in cases]})
    (workspace / "tests").mkdir()
    return {"status": "PREPARATION_REQUIRED", "total_cases": len(cases), "workspace": str(workspace), "source_sha256": bundle["source_sha256"]}


def test_inventory(workspace: Path) -> dict[str, str]:
    inventory = {}
    if (workspace / "tests").is_symlink():
        raise ValueError("Symlinks are not permitted in prepared tests.")
    for path in sorted((workspace / "tests").rglob("*")):
        if path.is_symlink():
            raise ValueError("Symlinks are not permitted in prepared tests.")
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
            relative = path.relative_to(workspace).as_posix()
            inventory[relative] = digest(local(workspace, relative))
    return inventory


def reviewed_plan(workspace: Path) -> dict:
    bundle = read_json(workspace / "case-bundle.json")
    repo_root = Path(bundle["target_repo"])
    external(workspace, repo_root)
    source = local(workspace, bundle["source_name"])
    if digest(source) != bundle["source_sha256"] or load_cases(source) != bundle["cases"]:
        raise ValueError("Imported source/conditions changed; create a new preparation instead.")
    context_path = Path(bundle["run_context"])
    if digest(context_path) != bundle["run_context_sha256"]:
        raise ValueError("Recorded run context changed.")
    context = read_json(context_path)
    validate_context(context, bundle["evaluation_data_exposed_at"])
    if context["run_id"] != bundle["run_id"] or context["sdlc_completed_at"] != bundle["sdlc_completed_at"]:
        raise ValueError("Run identity/completion mismatch.")
    if fingerprint(repo_root) != bundle["target_fingerprint"]:
        raise ValueError("Target source changed since preparation; do not repair the evaluated app.")
    inventory = test_inventory(workspace)
    bindings = read_json(workspace / "bindings.json").get("cases")
    if not isinstance(bindings, list) or any(not isinstance(item, dict) for item in bindings):
        raise ValueError("Bindings must contain a cases array.")
    indexed = {item.get("case_id"): item for item in bindings}
    if len(indexed) != len(bindings) or set(indexed) != {item["case_id"] for item in bundle["cases"]}:
        raise ValueError("Bindings must preserve the exact case set, without missing/extra/duplicate cases.")
    counts = {"COMMAND": 0, "BLOCKED": 0, "UNBOUND": 0}
    for binding in bindings:
        mode = binding.get("execution_type")
        if mode not in counts:
            raise ValueError("Unknown binding execution_type.")
        counts[mode] += 1
        if mode == "BLOCKED" and not str(binding.get("blocked_reason", "")).strip():
            raise ValueError("BLOCKED requires a concrete reason.")
        if mode != "COMMAND":
            continue
        command = binding.get("command")
        if not isinstance(command, list) or not command or any(not isinstance(value, str) or not value for value in command):
            raise ValueError("Prepared command must be an argv array.")
        files = binding.get("test_files")
        if not isinstance(files, list) or not files or any(value not in inventory for value in files):
            raise ValueError("Every executable case must reference existing frozen tests/ files.")
        mapping = binding.get("assertion_map")
        if not isinstance(mapping, dict) or any(not isinstance(mapping.get(key), str) or not mapping[key].strip() for key in ("precondition", "steps", "expected_result", "evidence")):
            raise ValueError("Record the source-to-test assertion mapping, including prerequisites/evidence.")
        timeout = binding.get("timeout_seconds", 300)
        if type(timeout) is not int or not 1 <= timeout <= 1800:
            raise ValueError("timeout_seconds must be an integer from 1 to 1800.")
    plan = {"schema_version": 1, "run_id": bundle["run_id"], "bundle_sha256": digest(workspace / "case-bundle.json"), "bindings_sha256": digest(workspace / "bindings.json"), "target_fingerprint": bundle["target_fingerprint"], "test_files": inventory, "counts": counts, "total_cases": len(bindings)}
    return {**plan, "review_sha256": canonical_json_sha256(plan)}


def manifest_cases(bundle: dict, bindings: dict, workspace: Path) -> list[dict]:
    indexed = {item["case_id"]: item for item in bindings["cases"]}
    cases = []
    for definition in bundle["cases"]:
        binding = indexed[definition["case_id"]]
        case = {"case_id": definition["case_id"], "requirement_id": definition["requirement_id"], "requirement_type": definition["requirement_type"], "source_definition": definition, "execution_type": binding["execution_type"]}
        if case["execution_type"] == "COMMAND":
            case.update(command=binding["command"], cwd=str(workspace.resolve()), timeout_seconds=binding.get("timeout_seconds", 300), expected={"exit_code": 0}, blocked_exit_codes=[125])
        else:
            case["blocked_reason"] = binding["blocked_reason"]
        cases.append(case)
    return cases


def seal(workspace: Path, reviewer: str, review_hash: str) -> dict:
    if not reviewer.strip():
        raise ValueError("An actual human reviewer is required; the Agent must not approve itself.")
    plan = reviewed_plan(workspace)
    if plan["review_sha256"] != review_hash or plan["counts"]["UNBOUND"]:
        raise ValueError("Review revision changed or UNBOUND cases remain; review again before approval.")
    manifest_path = workspace / "acceptance-test-manifest.json"
    if manifest_path.exists():
        raise ValueError("An approved manifest already exists; do not reseal or rewrite it.")
    bundle = read_json(workspace / "case-bundle.json")
    preparation = {"workspace": str(workspace.resolve()), "plan": plan, "reviewer": reviewer, "approved_at": clock()}
    manifest = {"schema_version": 1, "run_id": bundle["run_id"], "sdlc_completed_at": bundle["sdlc_completed_at"], "evaluation_data_exposed_at": bundle["evaluation_data_exposed_at"], "sheet_preparation": preparation, "cases": manifest_cases(bundle, read_json(workspace / "bindings.json"), workspace)}
    write_json(manifest_path, manifest)
    return {"status": "APPROVED_FOR_EXECUTION", "manifest": str(manifest_path), "total_cases": len(manifest["cases"]), "blocked_cases": plan["counts"]["BLOCKED"]}


def verify_prepared_manifest(manifest: dict, repo_root: Path | None = None) -> dict:
    preparation = manifest["sheet_preparation"]
    workspace = Path(preparation["workspace"])
    plan = reviewed_plan(workspace)
    if plan != preparation["plan"] or not str(preparation.get("reviewer", "")).strip():
        raise ValueError("Prepared tests/bindings changed after human approval.")
    bundle = read_json(workspace / "case-bundle.json")
    approved = parse_datetime(preparation.get("approved_at"))
    if not parse_datetime(bundle["evaluation_data_exposed_at"]) <= approved <= parse_datetime(clock()):
        raise ValueError("Invalid approval timestamp.")
    if repo_root is not None and Path(bundle["target_repo"]).resolve() != repo_root.resolve():
        raise ValueError("Prepared tests belong to a different repository.")
    for key in ("run_id", "sdlc_completed_at", "evaluation_data_exposed_at"):
        if manifest.get(key) != bundle[key]:
            raise ValueError("Prepared manifest run/timestamp mismatch.")
    expected = manifest_cases(bundle, read_json(workspace / "bindings.json"), workspace)
    if manifest["cases"] != expected:
        raise ValueError("Approved case set, commands or expectations changed.")
    if plan["counts"]["UNBOUND"]:
        raise ValueError("UNBOUND cases cannot be executed.")
    return preparation


def main() -> int:
    parser = argparse.ArgumentParser(description="Import, review and freeze acceptance tables without changing expectations.")
    commands = parser.add_subparsers(dest="action", required=True)
    importer = commands.add_parser("import")
    importer.add_argument("--repo-root", required=True)
    importer.add_argument("--source", required=True)
    importer.add_argument("--workspace", required=True)
    importer.add_argument("--run-context", required=True)
    importer.add_argument("--exposed-at", required=True)
    reviewer = commands.add_parser("review")
    reviewer.add_argument("--workspace", required=True)
    freezer = commands.add_parser("seal")
    freezer.add_argument("--workspace", required=True)
    freezer.add_argument("--reviewer", required=True)
    freezer.add_argument("--review-sha256", required=True)
    args = parser.parse_args()
    try:
        workspace = Path(args.workspace).resolve()
        if args.action == "import":
            result = import_sheet(Path(args.repo_root).resolve(), Path(args.source), workspace, Path(args.run_context), args.exposed_at)
        elif args.action == "review":
            result = reviewed_plan(workspace)
            write_json(workspace / "plan-review.json", result)
        else:
            result = seal(workspace, args.reviewer, args.review_sha256)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile, ElementTree.ParseError) as error:
        print(f"[FAIL] {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
