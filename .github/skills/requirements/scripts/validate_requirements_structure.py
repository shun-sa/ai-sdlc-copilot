#!/usr/bin/env python3

"""
Requirements Structure Validator

研究で定義されたCanonical Requirements Templateと、
生成された要件定義成果物の構造一致を検証する。

このValidatorは要件内容の意味的な妥当性は評価しない。
構造・ID・ファイル間整合性のみを決定論的に検証する。

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
# Canonical Requirements Structure
# ============================================================

EXPECTED_TITLE = "要件定義構造"


EXPECTED_SECTIONS = [
    "1. 用語集",
    "2. 背景",
    "3. 目的",
    "4. 誰のために",
    "5. 開発のスコープ外（Out of Scope）",
    "6. 成功条件（Acceptance Criteria）",
    "7. 業務フロー/ユーザーストーリー",
    "8. 共通機能要件",
    "9. 認証・認可",
    "10. エラー仕様（共通）",
    "11. 非機能要件（NFR）",
    "12. データモデル",
    "13. 機能要件（FR）",
    "14. 制約条件",
]


EXPECTED_FR_FIELDS = [
    "機能目的",
    "機能概要",
    "ユーザーストーリー",
    "入力項目",
    "バリデーション",
    "データ構造（必要に応じて）",
    "画面要件 ※詳細画面イメージは機能設計フェーズ（PLAN）でAIが作成",
    "エラー条件",
    "制約条件",
    "非機能要件（任意, PJ全体非機能要件のカスタマイズ）",
    "出力/挙動・完了条件",
]


# ============================================================
# Regular Expressions
# ============================================================

H1_PATTERN = re.compile(
    r"^#\s+(.+?)\s*$"
)

H2_PATTERN = re.compile(
    r"^##\s+(.+?)\s*$"
)

MAIN_FR_PATTERN = re.compile(
    r"^-\s+(FR-\d{3,})\s*:\s*(.+?)\s*$"
)

FEATURE_TITLE_PATTERN = re.compile(
    r"^#\s+(FR-\d{3,})\s*:\s*(.+?)\s*$"
)

BULLET_PATTERN = re.compile(
    r"^\s*-\s+(.+?)\s*$"
)

TOP_LEVEL_BULLET_PATTERN = re.compile(
    r"^-\s+(.+?)\s*$"
)


# ============================================================
# Utility
# ============================================================

def read_file(path: Path) -> str:
    """UTF-8でMarkdownファイルを読み込む。"""

    if not path.exists():
        raise FileNotFoundError(
            f"File not found: {path}"
        )

    if not path.is_file():
        raise ValueError(
            f"Not a file: {path}"
        )

    return path.read_text(encoding="utf-8")


def normalize(value: str) -> str:
    """
    比較に影響する不要な空白のみを正規化する。

    構造上の名称自体は変更しない。
    """

    return value.strip().replace("\u00a0", " ")


def find_first_h1(text: str) -> str | None:
    """最初のH1を取得する。"""

    for line in text.splitlines():
        match = H1_PATTERN.match(line)

        if match:
            # ## をH1として誤認しない
            if line.startswith("##"):
                continue

            return normalize(match.group(1))

    return None


def extract_h2_sections(text: str) -> list[str]:
    """H2を出現順に取得する。"""

    sections: list[str] = []

    for line in text.splitlines():
        match = H2_PATTERN.match(line)

        if match:
            sections.append(
                normalize(match.group(1))
            )

    return sections


def extract_section_body(
    text: str,
    section_name: str,
) -> str:
    """
    指定されたH2セクションの本文だけを取得する。
    """

    lines = text.splitlines()

    start_index: int | None = None

    for index, line in enumerate(lines):
        match = H2_PATTERN.match(line)

        if not match:
            continue

        if normalize(match.group(1)) == section_name:
            start_index = index + 1
            break

    if start_index is None:
        return ""

    end_index = len(lines)

    for index in range(start_index, len(lines)):
        if H2_PATTERN.match(lines[index]):
            end_index = index
            break

    return "\n".join(
        lines[start_index:end_index]
    )


# ============================================================
# Main Structure Validation
# ============================================================

def validate_title(
    text: str,
    source_name: str,
) -> list[str]:

    errors: list[str] = []

    actual_title = find_first_h1(text)

    if actual_title != EXPECTED_TITLE:
        errors.append(
            f"{source_name}: "
            f"H1 title mismatch. "
            f"Expected='{EXPECTED_TITLE}', "
            f"Actual='{actual_title}'"
        )

    return errors


def validate_sections(
    text: str,
    source_name: str,
) -> list[str]:

    errors: list[str] = []

    actual_sections = extract_h2_sections(text)

    if actual_sections == EXPECTED_SECTIONS:
        return errors

    errors.append(
        f"{source_name}: "
        "Requirements section structure does not "
        "match the Canonical Requirements Structure."
    )

    # 不足
    missing = [
        section
        for section in EXPECTED_SECTIONS
        if section not in actual_sections
    ]

    for section in missing:
        errors.append(
            f"{source_name}: "
            f"Missing section: '{section}'"
        )

    # 余分
    extra = [
        section
        for section in actual_sections
        if section not in EXPECTED_SECTIONS
    ]

    for section in extra:
        errors.append(
            f"{source_name}: "
            f"Unexpected section: '{section}'"
        )

    # 同じ要素でも順番違い
    if (
        not missing
        and not extra
        and actual_sections != EXPECTED_SECTIONS
    ):
        errors.append(
            f"{source_name}: "
            "Section order has been changed."
        )

        for index, expected in enumerate(
            EXPECTED_SECTIONS
        ):
            actual = actual_sections[index]

            if expected != actual:
                errors.append(
                    f"{source_name}: "
                    f"Position {index + 1}: "
                    f"Expected='{expected}', "
                    f"Actual='{actual}'"
                )

    return errors


# ============================================================
# Canonical Template Validation
# ============================================================

def extract_template_fr_fields(
    text: str,
) -> list[str]:

    """
    Canonical Templateの13章から、
    FR内部構成要素を抽出する。

    サンプル値は無視し、
    EXPECTED_FR_FIELDSに該当するラベルのみを取得する。
    """

    fr_body = extract_section_body(
        text,
        "13. 機能要件（FR）",
    )

    expected_set = set(EXPECTED_FR_FIELDS)

    result: list[str] = []

    for line in fr_body.splitlines():

        match = BULLET_PATTERN.match(line)

        if not match:
            continue

        value = normalize(
            match.group(1)
        )

        if value in expected_set:
            result.append(value)

    return result


def validate_template_fr_structure(
    text: str,
    source_name: str,
) -> list[str]:

    errors: list[str] = []

    actual = extract_template_fr_fields(text)

    if actual == EXPECTED_FR_FIELDS:
        return errors

    errors.append(
        f"{source_name}: "
        "FR internal structure has been modified."
    )

    missing = [
        value
        for value in EXPECTED_FR_FIELDS
        if value not in actual
    ]

    extra = [
        value
        for value in actual
        if value not in EXPECTED_FR_FIELDS
    ]

    for value in missing:
        errors.append(
            f"{source_name}: "
            f"Missing FR field: '{value}'"
        )

    for value in extra:
        errors.append(
            f"{source_name}: "
            f"Unexpected FR field: '{value}'"
        )

    if (
        not missing
        and not extra
        and actual != EXPECTED_FR_FIELDS
    ):
        errors.append(
            f"{source_name}: "
            "FR field order has been changed."
        )

    return errors


def validate_canonical_template(
    path: Path,
) -> list[str]:

    errors: list[str] = []

    try:
        text = read_file(path)

    except (FileNotFoundError, ValueError) as error:
        return [
            f"Canonical Template: {error}"
        ]

    errors.extend(
        validate_title(
            text,
            "Canonical Template",
        )
    )

    errors.extend(
        validate_sections(
            text,
            "Canonical Template",
        )
    )

    errors.extend(
        validate_template_fr_structure(
            text,
            "Canonical Template",
        )
    )

    return errors


# ============================================================
# requirements.md Validation
# ============================================================

def extract_main_fr_ids(
    text: str,
) -> list[str]:

    """
    requirements.md の
    「13. 機能要件（FR）」に記載されたFR IDを取得する。
    """

    fr_body = extract_section_body(
        text,
        "13. 機能要件（FR）",
    )

    ids: list[str] = []

    for line in fr_body.splitlines():

        match = MAIN_FR_PATTERN.match(line)

        if match:
            ids.append(
                match.group(1)
            )

    return ids


def find_duplicates(
    values: list[str],
) -> list[str]:

    seen: set[str] = set()
    duplicates: set[str] = set()

    for value in values:

        if value in seen:
            duplicates.add(value)

        seen.add(value)

    return sorted(duplicates)


def validate_main_requirements(
    path: Path,
) -> tuple[list[str], list[str]]:

    errors: list[str] = []

    try:
        text = read_file(path)

    except (FileNotFoundError, ValueError) as error:
        return (
            [f"Requirements document: {error}"],
            [],
        )

    errors.extend(
        validate_title(
            text,
            str(path),
        )
    )

    errors.extend(
        validate_sections(
            text,
            str(path),
        )
    )

    fr_ids = extract_main_fr_ids(text)

    duplicates = find_duplicates(fr_ids)

    for fr_id in duplicates:
        errors.append(
            f"{path}: "
            f"Duplicate FR ID: {fr_id}"
        )

    return errors, fr_ids


# ============================================================
# Split Feature File Validation
# ============================================================

def extract_feature_title(
    text: str,
) -> tuple[str, str] | None:

    for line in text.splitlines():

        match = FEATURE_TITLE_PATTERN.match(line)

        if match:
            return (
                match.group(1),
                normalize(match.group(2)),
            )

    return None


def extract_feature_fields(
    text: str,
) -> list[str]:

    """
    FR別ファイルのトップレベル構成要素を取得する。

    以下の形式を前提とする。

    - 機能目的
      - ...
    - 機能概要
      - ...
    """

    result: list[str] = []

    for line in text.splitlines():

        match = TOP_LEVEL_BULLET_PATTERN.match(line)

        if not match:
            continue

        result.append(
            normalize(match.group(1))
        )

    return result


def validate_feature_structure(
    path: Path,
    main_fr_ids: list[str],
) -> tuple[list[str], str | None]:

    errors: list[str] = []

    try:
        text = read_file(path)

    except (FileNotFoundError, ValueError) as error:
        return (
            [f"{path}: {error}"],
            None,
        )

    title = extract_feature_title(text)

    if title is None:
        errors.append(
            f"{path}: "
            "FR title is missing. "
            "Expected format: "
            "'# FR-001: 機能名'"
        )

        return errors, None

    fr_id, _ = title

    # requirements.md側にFRがあること
    if fr_id not in main_fr_ids:
        errors.append(
            f"{path}: "
            f"{fr_id} is not defined in "
            "requirements.md section "
            "'13. 機能要件（FR）'."
        )

    actual_fields = extract_feature_fields(text)

    if actual_fields != EXPECTED_FR_FIELDS:

        errors.append(
            f"{path}: "
            "FR structure does not match "
            "the Canonical Requirements Structure."
        )

        missing = [
            field
            for field in EXPECTED_FR_FIELDS
            if field not in actual_fields
        ]

        extra = [
            field
            for field in actual_fields
            if field not in EXPECTED_FR_FIELDS
        ]

        for field in missing:
            errors.append(
                f"{path}: "
                f"Missing FR field: '{field}'"
            )

        for field in extra:
            errors.append(
                f"{path}: "
                f"Unexpected top-level FR field: "
                f"'{field}'"
            )

        if (
            not missing
            and not extra
            and actual_fields != EXPECTED_FR_FIELDS
        ):
            errors.append(
                f"{path}: "
                "FR field order has been changed."
            )

    return errors, fr_id


def validate_feature_directory(
    feature_dir: Path,
    main_fr_ids: list[str],
) -> list[str]:

    errors: list[str] = []

    # FRファイル分割は任意のため、
    # ディレクトリ不存在はエラーにしない。
    if not feature_dir.exists():
        return errors

    files = sorted(
        path
        for path in feature_dir.glob("*.md")
        if path.is_file()
    )

    feature_ids: list[str] = []

    for path in files:

        file_errors, fr_id = (
            validate_feature_structure(
                path,
                main_fr_ids,
            )
        )

        errors.extend(file_errors)

        if fr_id is not None:
            feature_ids.append(fr_id)

    duplicates = find_duplicates(feature_ids)

    for fr_id in duplicates:
        errors.append(
            f"{feature_dir}: "
            f"Multiple feature files found "
            f"for {fr_id}."
        )

    return errors


# ============================================================
# Full Validation
# ============================================================

def validate(
    template_path: Path,
    requirements_path: Path,
    feature_dir: Path,
) -> list[str]:

    errors: list[str] = []

    # 1. Canonical Template自体を検証
    errors.extend(
        validate_canonical_template(
            template_path
        )
    )

    # Templateが壊れている場合、
    # その後のValidation結果を信用しない。
    if errors:
        return errors

    # 2. requirements.md
    main_errors, main_fr_ids = (
        validate_main_requirements(
            requirements_path
        )
    )

    errors.extend(main_errors)

    # 3. 分割されたFR
    errors.extend(
        validate_feature_directory(
            feature_dir,
            main_fr_ids,
        )
    )

    return errors


# ============================================================
# CLI
# ============================================================

def parse_args() -> argparse.Namespace:

    parser = argparse.ArgumentParser(
        description=(
            "Validate Requirements artifacts "
            "against the Canonical "
            "Requirements Structure."
        )
    )

    parser.add_argument(
        "--template",
        default=(
            ".github/skills/requirements/"
            "templates/requirements-template.md"
        ),
        help=(
            "Path to Canonical Requirements Template."
        ),
    )

    parser.add_argument(
        "--requirements",
        default=(
            "docs/requirements/requirements.md"
        ),
        help=(
            "Path to requirements.md."
        ),
    )

    parser.add_argument(
        "--feature-dir",
        default=(
            "docs/requirements/features"
        ),
        help=(
            "Directory containing split FR files."
        ),
    )

    return parser.parse_args()


def main() -> int:

    args = parse_args()

    template_path = Path(args.template)
    requirements_path = Path(args.requirements)
    feature_dir = Path(args.feature_dir)

    errors = validate(
        template_path=template_path,
        requirements_path=requirements_path,
        feature_dir=feature_dir,
    )

    print(
        "========================================"
    )
    print(
        " Requirements Structure Validation"
    )
    print(
        "========================================"
    )

    if errors:

        print()
        print("[FAIL] Validation failed.")
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
        "[PASS] Requirements structure is valid."
    )
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())