#!/usr/bin/env python3

"""
ADR Structure Validator

Architecture Decision Record が、
プロジェクトで定義されたCanonical ADR Structureに
従っていることを決定論的に検証する。

このValidatorは設計判断そのものの妥当性は評価しない。
ADRの構造、ID、Status、Requirementとの参照整合性を検証する。

Exit Code:
    0: PASS
    1: FAIL
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


# ============================================================
# Canonical ADR Structure
# ============================================================

EXPECTED_SECTIONS = [
    "Status",
    "Related Requirements",
    "Context",
    "Decision",
    "Alternatives",
    "Consequences",
    "AI Guardrails",
]

ALLOWED_STATUSES = {
    "Proposed",
    "Accepted",
    "Superseded",
    "Rejected",
}

MAX_ADR_LINES = 50
MAX_ALTERNATIVES = 3
MAX_AI_GUARDRAILS = 3


# ============================================================
# Patterns
# ============================================================

ADR_TITLE_PATTERN = re.compile(
    r"^#\s+(ADR-\d{3,})\s+(.+?)\s*$"
)

ADR_FILENAME_PATTERN = re.compile(
    r"^(ADR-\d{3,})(?:-.+)?\.md$"
)

H2_PATTERN = re.compile(
    r"^##\s+(.+?)\s*$"
)

REQUIREMENT_PATTERN = re.compile(
    r"^(FR|NFR|SEC|CON)-\d{3,}$"
)

REQUIREMENT_ANYWHERE_PATTERN = re.compile(
    r"\b(?:FR|NFR|SEC|CON)-\d{3,}\b"
)

BULLET_PATTERN = re.compile(
    r"^\s*-\s+(.+?)\s*$"
)

TOP_LEVEL_BULLET_PATTERN = re.compile(
    r"^-\s+(.+?)\s*$"
)


# ============================================================
# Utilities
# ============================================================

def read_file(path: Path) -> str:
    """UTF-8でファイルを読み込む。"""

    if not path.exists():
        raise FileNotFoundError(
            f"File not found: {path}"
        )

    if not path.is_file():
        raise ValueError(
            f"Not a file: {path}"
        )

    return path.read_text(
        encoding="utf-8"
    )


def normalize(value: str) -> str:
    """前後空白とNBSPのみを正規化する。"""

    return value.strip().replace(
        "\u00a0",
        " ",
    )


def extract_sections(text: str) -> list[str]:
    """H2セクションを順番どおり取得する。"""

    result: list[str] = []

    for line in text.splitlines():

        match = H2_PATTERN.match(line)

        if match:
            result.append(
                normalize(match.group(1))
            )

    return result


def extract_section_body(
    text: str,
    section_name: str,
) -> str:
    """
    指定したH2セクションの本文を取得する。
    """

    lines = text.splitlines()

    start_index: int | None = None

    for index, line in enumerate(lines):

        match = H2_PATTERN.match(line)

        if not match:
            continue

        if normalize(
            match.group(1)
        ) == section_name:
            start_index = index + 1
            break

    if start_index is None:
        return ""

    end_index = len(lines)

    for index in range(
        start_index,
        len(lines),
    ):
        if H2_PATTERN.match(lines[index]):
            end_index = index
            break

    return "\n".join(
        lines[start_index:end_index]
    ).strip()


def meaningful_lines(
    text: str,
) -> list[str]:
    """
    空行を除外した行を返す。
    """

    return [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]


# ============================================================
# Title / ID Validation
# ============================================================

def extract_adr_id(
    text: str,
) -> str | None:
    """ADRタイトルからADR IDを取得する。"""

    for line in text.splitlines():

        match = ADR_TITLE_PATTERN.match(line)

        if match:
            return match.group(1)

    return None


def validate_title(
    text: str,
    path: Path,
) -> list[str]:

    errors: list[str] = []

    first_non_empty = next(
        (
            line
            for line in text.splitlines()
            if line.strip()
        ),
        None,
    )

    if first_non_empty is None:
        return [
            f"{path}: ADR is empty."
        ]

    match = ADR_TITLE_PATTERN.match(
        first_non_empty
    )

    if not match:
        errors.append(
            f"{path}: "
            "ADR title must use "
            "'# ADR-001 タイトル' format."
        )

        return errors

    adr_id = match.group(1)

    filename_match = (
        ADR_FILENAME_PATTERN.match(
            path.name
        )
    )

    if not filename_match:
        errors.append(
            f"{path}: "
            "Filename must start with ADR ID. "
            "Example: ADR-001-authentication.md"
        )

        return errors

    filename_adr_id = (
        filename_match.group(1)
    )

    if adr_id != filename_adr_id:
        errors.append(
            f"{path}: "
            f"ADR ID mismatch. "
            f"Title='{adr_id}', "
            f"Filename='{filename_adr_id}'"
        )

    return errors


# ============================================================
# Section Validation
# ============================================================

def validate_sections(
    text: str,
    path: Path,
) -> list[str]:

    errors: list[str] = []

    actual = extract_sections(text)

    if actual == EXPECTED_SECTIONS:
        return errors

    missing = [
        section
        for section in EXPECTED_SECTIONS
        if section not in actual
    ]

    extra = [
        section
        for section in actual
        if section not in EXPECTED_SECTIONS
    ]

    for section in missing:
        errors.append(
            f"{path}: "
            f"Missing section: "
            f"'## {section}'"
        )

    for section in extra:
        errors.append(
            f"{path}: "
            f"Unexpected section: "
            f"'## {section}'"
        )

    if (
        not missing
        and not extra
        and actual != EXPECTED_SECTIONS
    ):
        errors.append(
            f"{path}: "
            "ADR section order has been changed."
        )

        for index, expected in enumerate(
            EXPECTED_SECTIONS
        ):
            actual_section = actual[index]

            if expected != actual_section:
                errors.append(
                    f"{path}: "
                    f"Position {index + 1}: "
                    f"Expected='{expected}', "
                    f"Actual='{actual_section}'"
                )

    return errors


# ============================================================
# Status Validation
# ============================================================

def validate_status(
    text: str,
    path: Path,
) -> list[str]:

    errors: list[str] = []

    body = extract_section_body(
        text,
        "Status",
    )

    lines = meaningful_lines(body)

    if not lines:
        return [
            f"{path}: "
            "Status must not be empty."
        ]

    if len(lines) != 1:
        errors.append(
            f"{path}: "
            "Status must contain exactly one value."
        )

        return errors

    status = lines[0]

    if status not in ALLOWED_STATUSES:
        errors.append(
            f"{path}: "
            f"Invalid Status '{status}'. "
            f"Allowed={sorted(ALLOWED_STATUSES)}"
        )

    return errors


# ============================================================
# Requirement Traceability
# ============================================================

def extract_related_requirements(
    text: str,
) -> list[str]:

    body = extract_section_body(
        text,
        "Related Requirements",
    )

    result: list[str] = []

    for line in body.splitlines():

        match = BULLET_PATTERN.match(line)

        if not match:
            continue

        content = normalize(
            match.group(1)
        )

        requirement_match = (
            REQUIREMENT_ANYWHERE_PATTERN.search(
                content
            )
        )

        if requirement_match:
            result.append(
                requirement_match.group(0)
            )

    return result


def collect_requirement_ids(
    requirements_root: Path,
) -> set[str]:
    """
    Requirements成果物からRequirement IDを収集する。

    FR / NFR / SEC / CON を対象とする。
    """

    result: set[str] = set()

    if not requirements_root.exists():
        return result

    files: list[Path]

    if requirements_root.is_file():
        files = [requirements_root]

    else:
        files = list(
            requirements_root.rglob("*.md")
        )

    for path in files:

        try:
            text = read_file(path)

        except (
            FileNotFoundError,
            ValueError,
        ):
            continue

        for match in (
            REQUIREMENT_ANYWHERE_PATTERN.finditer(
                text
            )
        ):
            result.add(
                match.group(0)
            )

    return result


def validate_related_requirements(
    text: str,
    path: Path,
    known_requirement_ids: set[str],
    check_existence: bool,
) -> list[str]:

    errors: list[str] = []

    requirements = (
        extract_related_requirements(text)
    )

    if not requirements:
        errors.append(
            f"{path}: "
            "Related Requirements must contain "
            "at least one Requirement ID."
        )

        return errors

    duplicates = {
        requirement
        for requirement in requirements
        if requirements.count(
            requirement
        ) > 1
    }

    for requirement in sorted(
        duplicates
    ):
        errors.append(
            f"{path}: "
            "Duplicate Related Requirement: "
            f"{requirement}"
        )

    for requirement in requirements:

        if not REQUIREMENT_PATTERN.match(
            requirement
        ):
            errors.append(
                f"{path}: "
                "Invalid Requirement ID: "
                f"{requirement}"
            )

        if (
            check_existence
            and requirement
            not in known_requirement_ids
        ):
            errors.append(
                f"{path}: "
                f"Related Requirement "
                f"'{requirement}' "
                "does not exist in "
                "Requirements artifacts."
            )

    return errors


# ============================================================
# Required Content
# ============================================================

def validate_required_content(
    text: str,
    path: Path,
) -> list[str]:

    errors: list[str] = []

    required_sections = [
        "Context",
        "Decision",
        "Alternatives",
        "Consequences",
        "AI Guardrails",
    ]

    for section in required_sections:

        body = extract_section_body(
            text,
            section,
        )

        if not body.strip():
            errors.append(
                f"{path}: "
                f"'{section}' must not be empty."
            )

    return errors


# ============================================================
# Alternatives
# ============================================================

def validate_alternatives(
    text: str,
    path: Path,
) -> list[str]:

    errors: list[str] = []

    body = extract_section_body(
        text,
        "Alternatives",
    )

    alternatives = [
        normalize(match.group(1))
        for line in body.splitlines()
        if (
            match :=
            TOP_LEVEL_BULLET_PATTERN.match(
                line
            )
        )
    ]

    if not alternatives:
        errors.append(
            f"{path}: "
            "Alternatives must contain "
            "at least one option."
        )

        return errors

    if len(alternatives) > MAX_ALTERNATIVES:
        errors.append(
            f"{path}: "
            f"Alternatives has "
            f"{len(alternatives)} options. "
            f"Maximum is {MAX_ALTERNATIVES}."
        )

    return errors


# ============================================================
# AI Guardrails
# ============================================================

def validate_ai_guardrails(
    text: str,
    path: Path,
) -> list[str]:

    errors: list[str] = []

    body = extract_section_body(
        text,
        "AI Guardrails",
    )

    guardrails = [
        normalize(match.group(1))
        for line in body.splitlines()
        if (
            match :=
            TOP_LEVEL_BULLET_PATTERN.match(
                line
            )
        )
    ]

    if not guardrails:
        errors.append(
            f"{path}: "
            "AI Guardrails must contain "
            "at least one item."
        )

        return errors

    if len(guardrails) > MAX_AI_GUARDRAILS:
        errors.append(
            f"{path}: "
            f"AI Guardrails has "
            f"{len(guardrails)} items. "
            f"Maximum is "
            f"{MAX_AI_GUARDRAILS}."
        )

    return errors


# ============================================================
# Length Validation
# ============================================================

def validate_length(
    text: str,
    path: Path,
) -> list[str]:

    line_count = len(
        text.splitlines()
    )

    if line_count <= MAX_ADR_LINES:
        return []

    return [
        f"{path}: "
        f"ADR has {line_count} lines. "
        f"Recommended maximum is "
        f"{MAX_ADR_LINES}."
    ]


# ============================================================
# ADR Validation
# ============================================================

def validate_adr(
    path: Path,
    known_requirement_ids: set[str],
    check_requirement_existence: bool,
) -> list[str]:

    try:
        text = read_file(path)

    except (
        FileNotFoundError,
        ValueError,
    ) as error:
        return [
            f"{path}: {error}"
        ]

    errors: list[str] = []

    errors.extend(
        validate_title(
            text,
            path,
        )
    )

    errors.extend(
        validate_sections(
            text,
            path,
        )
    )

    # セクション構造が壊れている場合でも
    # 可能な範囲で残りの検証を継続する。

    errors.extend(
        validate_status(
            text,
            path,
        )
    )

    errors.extend(
        validate_related_requirements(
            text,
            path,
            known_requirement_ids,
            check_requirement_existence,
        )
    )

    errors.extend(
        validate_required_content(
            text,
            path,
        )
    )

    errors.extend(
        validate_alternatives(
            text,
            path,
        )
    )

    errors.extend(
        validate_ai_guardrails(
            text,
            path,
        )
    )

    errors.extend(
        validate_length(
            text,
            path,
        )
    )

    return errors


# ============================================================
# Repository Validation
# ============================================================

def find_adr_files(
    adr_path: Path,
) -> list[Path]:

    if not adr_path.exists():
        return []

    if adr_path.is_file():
        return [adr_path]

    return sorted(
        path
        for path in adr_path.glob("ADR-*.md")
        if path.is_file()
    )


def validate(
    adr_path: Path,
    requirements_root: Path | None,
) -> list[str]:

    errors: list[str] = []

    files = find_adr_files(
        adr_path
    )

    if not files:
        return [
            f"No ADR files found: {adr_path}"
        ]

    check_requirement_existence = (
        requirements_root is not None
    )

    known_requirement_ids: set[str] = set()

    if requirements_root is not None:

        known_requirement_ids = (
            collect_requirement_ids(
                requirements_root
            )
        )

        if not known_requirement_ids:
            errors.append(
                "No Requirement IDs were found "
                f"under: {requirements_root}"
            )

            return errors

    adr_ids: list[str] = []

    for path in files:

        try:
            text = read_file(path)
            adr_id = extract_adr_id(text)

            if adr_id:
                adr_ids.append(adr_id)

        except (
            FileNotFoundError,
            ValueError,
        ):
            pass

        errors.extend(
            validate_adr(
                path,
                known_requirement_ids,
                check_requirement_existence,
            )
        )

    # ADR ID重複
    duplicate_ids = {
        adr_id
        for adr_id in adr_ids
        if adr_ids.count(adr_id) > 1
    }

    for adr_id in sorted(
        duplicate_ids
    ):
        errors.append(
            f"Duplicate ADR ID: {adr_id}"
        )

    return errors


# ============================================================
# CLI
# ============================================================

def parse_args() -> argparse.Namespace:

    parser = argparse.ArgumentParser(
        description=(
            "Validate ADR artifacts against "
            "the project's Canonical ADR Structure."
        )
    )

    parser.add_argument(
        "--adr",
        default="docs/adr",
        help=(
            "ADR file or ADR directory. "
            "Default: docs/adr"
        ),
    )

    parser.add_argument(
        "--requirements",
        default="docs/requirements",
        help=(
            "Requirements file or directory "
            "used for traceability validation. "
            "Default: docs/requirements"
        ),
    )

    parser.add_argument(
        "--skip-requirement-existence-check",
        action="store_true",
        help=(
            "Validate Requirement ID syntax only "
            "without checking whether referenced "
            "Requirement IDs exist."
        ),
    )

    return parser.parse_args()


def main() -> int:

    args = parse_args()

    adr_path = Path(
        args.adr
    )

    requirements_root: Path | None

    if args.skip_requirement_existence_check:
        requirements_root = None
    else:
        requirements_root = Path(
            args.requirements
        )

    errors = validate(
        adr_path=adr_path,
        requirements_root=requirements_root,
    )

    print(
        "========================================"
    )
    print(
        " ADR Structure Validation"
    )
    print(
        "========================================"
    )

    if errors:

        print()
        print(
            "[FAIL] ADR validation failed."
        )
        print()

        for index, error in enumerate(
            errors,
            start=1,
        ):
            print(
                f"{index}. {error}"
            )

        print()
        print(
            f"Total errors: {len(errors)}"
        )

        return 1

    print()
    print(
        "[PASS] ADR structure and "
        "traceability are valid."
    )
    print()

    return 0


if __name__ == "__main__":
    sys.exit(
        main()
    )