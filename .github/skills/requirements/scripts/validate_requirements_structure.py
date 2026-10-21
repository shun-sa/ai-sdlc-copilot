#!/usr/bin/env python3
"""Validate split requirements against repository templates. Exit: 0 PASS, 1 FAIL."""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote


ARTIFACTS = {
    "business_requirements.md": "docs/requirements/business_requirements.md",
    "functional_requirements.md": "docs/requirements/functional_requirements.md",
    "non_functional_requirements.md": "docs/requirements/non_functional_requirements.md",
    "data_requirements.md": "docs/requirements/data_requirements.md",
    "external_interface_requirements.md": "docs/requirements/external_interface_requirements.md",
    "ui_report_requirements.md": "docs/requirements/ui_report_requirements.md",
    "use_case_user_story_list.md": "docs/requirements/use-case-user-story-index.md",
    "glossary.md": "docs/requirements/glossary.md",
    "requirements_quality_checklist.md": "docs/requirements/requirements_quality_checklist.md",
}
TEMPLATE_DIR = Path(".github/skills/requirements/templates")
STEERING_TEMPLATE = Path(".github/project-context/templates/project-ai-steering.md")
STEERING_OUTPUT = Path(".github/project-context/project-ai-steering.md")
INDEX = Path("docs/requirements/requirements.md")
PLACEHOLDER = re.compile(r"\{\{[^{}]+\}\}|<\w[^<>\n]*>")
HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
IDENTIFIER = re.compile(r"(?<![A-Za-z0-9_-])[A-Z][A-Z0-9_]*(?:-[A-Z0-9_]+)*-\d+(?![A-Za-z0-9_-])")
LINK = re.compile(r"\[[^\]]+\]\(([^\s)]+)\)")
NOT_APPLICABLE = {"該当なし", "N/A", "None", "なし", "－", "-"}


@dataclass
class Section:
    level: int
    title: str
    body: list[str] = field(default_factory=list)
    children: list[Section] = field(default_factory=list)


def visible_text(text: str) -> str:
    return re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)


def markdown_lines(text: str) -> list[str]:
    lines = []
    fence = None
    for line in visible_text(text).splitlines():
        marker = re.match(r"^\s*(`{3,}|~{3,})", line)
        if marker:
            token = marker.group(1)
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
            continue
        if fence is None:
            lines.append(line)
    return lines


def parse_document(text: str) -> Section:
    root = Section(0, "")
    stack = [root]
    for line in markdown_lines(text):
        match = HEADING.match(line)
        if not match:
            stack[-1].body.append(line)
            continue
        section = Section(len(match.group(1)), match.group(2))
        while stack[-1].level >= section.level:
            stack.pop()
        stack[-1].children.append(section)
        stack.append(section)
    return root


def walk(section: Section):
    yield section
    for child in section.children:
        yield from walk(child)


def cells(line: str) -> list[str]:
    return [cell.strip().strip("`") for cell in re.split(r"(?<!\\)\|", line.strip().strip("|"))]


def tables(section: Section) -> list[tuple[list[str], list[list[str]]]]:
    result = []
    lines = section.body
    position = 0
    while position + 1 < len(lines):
        if not lines[position].lstrip().startswith("|"):
            position += 1
            continue
        header = cells(lines[position])
        separator = cells(lines[position + 1])
        if not separator or not all(re.fullmatch(r":?-{3,}:?", value) for value in separator):
            position += 1
            continue
        position += 2
        rows = []
        while position < len(lines) and lines[position].lstrip().startswith("|"):
            rows.append(cells(lines[position]))
            position += 1
        result.append((header, rows))
    return result


def all_tables(document: Section):
    for section in walk(document):
        for header, rows in tables(section):
            yield section, header, rows


def pattern(value: str) -> str:
    parts = []
    cursor = 0
    for match in PLACEHOLDER.finditer(value):
        parts.extend((re.escape(value[cursor:match.start()]), r".+?"))
        cursor = match.end()
    parts.append(re.escape(value[cursor:]))
    return "".join(parts)


def same_value(expected: str, actual: str) -> bool:
    return re.fullmatch(pattern(expected), actual) is not None


def renamed_number(title: str, old: str, new: str) -> str:
    if old and (title.startswith(old + ".") or title.startswith(old + " ")):
        return new + title[len(old):]
    return title


def compare_structure(expected: Section, actual: Section, source: Path, errors: list[str]) -> None:
    expected_tables = tables(expected)
    actual_tables = tables(actual)
    if len(expected_tables) != len(actual_tables):
        errors.append(f"{source}: table count mismatch in '{actual.title}'")
    for (expected_header, _), (actual_header, _) in zip(expected_tables, actual_tables):
        actor_columns = expected_header[:2] == ["機能ID", "機能名"] and any(
            "{{利用者区分" in value for value in expected_header[2:]
        )
        valid = (
            len(actual_header) >= 3 and actual_header[:2] == expected_header[:2]
            if actor_columns
            else len(expected_header) == len(actual_header)
            and all(same_value(left, right) for left, right in zip(expected_header, actual_header))
        )
        if not valid:
            errors.append(f"{source}: table columns mismatch in '{actual.title}'")
    for header, rows in actual_tables:
        for row in rows:
            if len(row) != len(header) or any(not value for value in row):
                errors.append(f"{source}: empty cell or invalid row width in '{actual.title}'")

    position = 0
    for template_child in expected.children:
        repeat = PLACEHOLDER.search(template_child.title) is not None and template_child.level > 1
        count = 0
        while position < len(actual.children):
            child = actual.children[position]
            title = template_child.title
            number = re.match(r"^(\d+(?:\.\d+)+)\s", title)
            old_number = number.group(1) if number else ""
            new_number = old_number
            if repeat and old_number:
                prefix, ordinal = old_number.rsplit(".", 1)
                new_number = f"{prefix}.{int(ordinal) + count}"
                title = renamed_number(title, old_number, new_number)
            if child.level != template_child.level or not same_value(title, child.title):
                break
            adjusted = template_child
            if new_number != old_number:
                adjusted = renumber_section(template_child, old_number, new_number)
            compare_structure(adjusted, child, source, errors)
            position += 1
            count += 1
            if not repeat:
                break
        if count == 0:
            non_applicable = "該当なし" in "\n".join(actual.body)
            if not (repeat and non_applicable):
                errors.append(f"{source}: missing or reordered heading '{template_child.title}'")
    for extra in actual.children[position:]:
        errors.append(f"{source}: unexpected or reordered heading '{extra.title}'")


def renumber_section(section: Section, old: str, new: str) -> Section:
    return Section(
        section.level,
        renamed_number(section.title, old, new),
        section.body,
        [renumber_section(child, old, new) for child in section.children],
    )


def validate_document(template: str, text: str, source: Path) -> list[str]:
    errors = []
    visible = visible_text(text)
    if re.search(r"\{\{[^{}]+\}\}", visible):
        errors.append(f"{source}: unresolved placeholder")
    for token in set(re.findall(r"<\w[^<>\n]*>", visible_text(template))):
        if token in visible:
            errors.append(f"{source}: unresolved placeholder {token}")
    expected_keys = re.findall(r"^([a-z_]+):", template.split("---", 2)[1], re.MULTILINE) if template.startswith("---") else []
    actual_keys = re.findall(r"^([a-z_]+):", text.split("---", 2)[1], re.MULTILINE) if text.startswith("---") and text.count("---") >= 2 else []
    if expected_keys != actual_keys:
        errors.append(f"{source}: front matter keys mismatch")
    compare_structure(parse_document(template), parse_document(text), source, errors)
    return errors


def row_records(document: Section, required: set[str], chapter: str = ""):
    for section, header, rows in all_tables(document):
        if required.issubset(header) and section.title.startswith(chapter):
            for row in rows:
                if len(row) == len(header):
                    yield dict(zip(header, row))


def definitions(records, column: str, source: Path, errors: list[str]) -> list[str]:
    values = [record[column] for record in records if record[column] not in NOT_APPLICABLE]
    for value, count in Counter(values).items():
        if count > 1:
            errors.append(f"{source}: duplicate definition {value}")
    return values


def non_functional_rows(document: Section) -> list[dict[str, str]]:
    performance = list(row_records(document, {"ID", "要件項目", "目標値（単位付き）", "検証方法"}))
    compliance = list(row_records(document, {"ID", "法令・規約名", "求められる事項", "確認方法"}, "11."))
    return performance + [{**row, "要件項目": row["法令・規約名"]} for row in compliance]


def resolve_link(source: Path, link: str, root: Path) -> Path | None:
    target = unquote(link.split("#", 1)[0])
    if not target or re.match(r"[a-zA-Z][a-zA-Z0-9+.-]*:", target):
        return None
    resolved = (source.parent / target).resolve()
    if not resolved.is_relative_to(root.resolve()):
        return None
    return resolved


def validate_index(root: Path, paths: list[Path], fr_ids: list[str], nfr_ids: list[str]) -> list[str]:
    errors = []
    source = root / INDEX
    try:
        text = source.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as error:
        return [f"{source}: {error}"]
    if not text.splitlines() or text.splitlines()[0] != "# Requirements Index":
        errors.append(f"{source}: expected '# Requirements Index' for downstream discovery")
    targets = set()
    for link in LINK.findall(visible_text(text)):
        target = resolve_link(source, link, root)
        if target is None or not target.is_file():
            errors.append(f"{source}: invalid artifact link {link}")
        else:
            targets.add(target)
    for path in paths:
        if path.resolve() not in targets:
            errors.append(f"{source}: missing artifact link {path.relative_to(root)}")
    document = parse_document(text)
    for heading, identifiers, output in (
        ("機能要件", fr_ids, "functional_requirements.md"),
        ("非機能要件", nfr_ids, "non_functional_requirements.md"),
    ):
        sections = [section for section in walk(document) if section.level == 2 and section.title == heading]
        actual = []
        for section in sections:
            for line in section.body:
                match = re.match(r"^-\s+([^\s:]+):\s+(.+)$", line)
                if match:
                    actual.append(match.group(1))
                    links = LINK.findall(match.group(2))
                    expected_path = root / "docs/requirements" / output
                    if len(links) != 1 or resolve_link(source, links[0], root) != expected_path.resolve():
                        errors.append(f"{source}: wrong source link for {match.group(1)}")
        if len(sections) != 1 or Counter(actual) != Counter(identifiers):
            errors.append(f"{source}: {heading} IDs differ from source definitions")
    return errors


def validate(root: Path) -> list[str]:
    root = root.resolve()
    errors: list[str] = []
    texts: dict[str, str] = {}
    documents: dict[str, Section] = {}
    templates: dict[str, str] = {}
    pairs = [(name, TEMPLATE_DIR / name, Path(output)) for name, output in ARTIFACTS.items()]
    pairs.append(("steering", STEERING_TEMPLATE, STEERING_OUTPUT))
    for name, template_path, output in pairs:
        try:
            templates[name] = (root / template_path).read_text(encoding="utf-8-sig")
            texts[name] = (root / output).read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError) as error:
            errors.append(f"{name}: {error}")
            continue
        errors.extend(validate_document(templates[name], texts[name], root / output))
        documents[name] = parse_document(texts[name])
    try:
        uc_template = (root / TEMPLATE_DIR / "use_case_detail.md").read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as error:
        errors.append(f"Use Case template: {error}")
        return errors
    if len(documents) != len(pairs):
        return errors

    functional = documents["functional_requirements.md"]
    non_functional = documents["non_functional_requirements.md"]
    fr_ids = definitions(row_records(functional, {"ID", "機能名"}, "4."), "ID", root / ARTIFACTS["functional_requirements.md"], errors)
    nfr_rows = non_functional_rows(non_functional)
    nfr_ids = definitions(nfr_rows, "ID", root / ARTIFACTS["non_functional_requirements.md"], errors)
    for identifier in set(fr_ids) & set(nfr_ids):
        errors.append(f"Requirement ID defined as both functional and non-functional: {identifier}")
    details = [section for section in walk(functional) if section.level == 3 and re.match(r"^6\.\d+ ", section.title)]
    detail_ids = [re.sub(r"^6\.\d+\s+", "", section.title).split("：", 1)[0].split(":", 1)[0].strip() for section in details]
    if Counter(detail_ids) != Counter(fr_ids):
        errors.append("Functional list and detail IDs differ")
    for section, identifier in zip(details, detail_ids):
        values = [row["内容"] for row in row_records(section, {"項目", "内容"}) if row["項目"] == "機能ID"]
        if values != [identifier]:
            errors.append(f"Functional detail basic information ID differs: {identifier}")
    permission_ids = [row["機能ID"] for row in row_records(functional, {"機能ID", "機能名"}, "5.1") if row["機能ID"] not in NOT_APPLICABLE]
    if Counter(permission_ids) != Counter(fr_ids):
        errors.append("Functional list and permission IDs differ")
    template_nfr = parse_document(templates["non_functional_requirements.md"])
    required_items = [(row["区分"], row["要件項目"]) for row in row_records(template_nfr, {"ID", "区分", "要件項目", "目標値（単位付き）"})]
    actual_items = {(row["区分"], row["要件項目"]) for row in nfr_rows if "区分" in row}
    for item in required_items:
        if item not in actual_items:
            errors.append(f"Non-functional representative item removed: {item}")

    steering_references = {
        row["種別"]: row["Path / Reference"]
        for row in row_records(documents["steering"], {"種別", "Path / Reference"})
    }
    for kind, expected in (
        ("Requirements", INDEX),
        ("Use Case Index", Path(ARTIFACTS["use_case_user_story_list.md"])),
        ("Use Case Details", Path("docs/requirements/use-cases")),
        ("Glossary", Path(ARTIFACTS["glossary.md"])),
    ):
        value = steering_references.get(kind, "")
        links = LINK.findall(value)
        target = resolve_link(root / STEERING_OUTPUT, links[0], root) if links else (root / value).resolve()
        if target != (root / expected).resolve():
            errors.append(f"AI Steering reference differs from artifact contract: {kind}")

    index_doc = documents["use_case_user_story_list.md"]
    actors = definitions(row_records(index_doc, {"Actor ID", "種別"}, "2."), "Actor ID", root / ARTIFACTS["use_case_user_story_list.md"], errors)
    stories = list(row_records(index_doc, {"User Story ID", "Actor ID"}, "3."))
    story_ids = definitions(stories, "User Story ID", root / ARTIFACTS["use_case_user_story_list.md"], errors)
    use_cases = list(row_records(index_doc, {"Use Case ID", "詳細ファイル"}, "4."))
    uc_ids = definitions(use_cases, "Use Case ID", root / ARTIFACTS["use_case_user_story_list.md"], errors)
    uc_paths = []
    ac_ids = []
    for record in use_cases:
        if record["Use Case ID"] in NOT_APPLICABLE:
            continue
        source = root / ARTIFACTS["use_case_user_story_list.md"]
        link = record["詳細ファイル"]
        matches = LINK.findall(link)
        target = resolve_link(source, matches[0] if matches else link, root)
        if target is None or not target.is_relative_to(root / "docs/requirements/use-cases"):
            errors.append(f"Use Case detail path invalid: {link}")
            continue
        uc_paths.append(target)
        try:
            text = target.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError) as error:
            errors.append(f"{target}: {error}")
            continue
        errors.extend(validate_document(uc_template, text, target))
        document = parse_document(text)
        documents[str(target)] = document
        info = {row["項目"]: row["内容"] for row in row_records(document, {"項目", "内容"}, "2.")}
        if info.get("Use Case ID") != record["Use Case ID"]:
            errors.append(f"{target}: Use Case ID differs from index")
        criteria = [section for section in walk(document) if section.level == 3 and re.match(r"^9\.\d+ ", section.title)]
        ac_ids.extend(re.sub(r"^9\.\d+\s+", "", section.title).split("：", 1)[0].strip() for section in criteria)
    for identifier, count in Counter(ac_ids).items():
        if count > 1:
            errors.append(f"Duplicate AC definition: {identifier}")
    for path in (root / "docs/requirements/use-cases").rglob("*.md"):
        if path.resolve() not in uc_paths:
            errors.append(f"Unlisted Use Case detail: {path}")

    known = {
        "関連Requirement ID": set(fr_ids + nfr_ids),
        "Actor ID": set(actors),
        "Primary Actor": set(actors),
        "関連Use Case ID": set(uc_ids),
        "関連User Story ID": set(story_ids),
    }
    for name, document in documents.items():
        for _, header, rows in all_tables(document):
            for row in rows:
                references = list(zip(header, row))
                if header == ["項目", "内容"] and len(row) == 2:
                    references.append((row[0], row[1]))
                for column, value in references:
                    if column in known:
                        for identifier in IDENTIFIER.findall(value):
                            if identifier not in known[column]:
                                errors.append(f"{name}: undefined reference {identifier} in {column}")
    paths = [root / output for output in ARTIFACTS.values()] + [root / STEERING_OUTPUT] + uc_paths
    errors.extend(validate_index(root, paths, fr_ids, nfr_ids))
    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repository root (default: current directory)")
    return parser.parse_args()


def main() -> int:
    errors = validate(parse_args().root)
    if errors:
        print("[FAIL] Requirements structure validation")
        for error in errors:
            print(f"- {error}")
        return 1
    print("[PASS] Requirements structure is valid (semantic review is separate).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
