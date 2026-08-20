from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


# このテストファイルと同じディレクトリにある
# validate_requirements_structure.py を確実にimportする。
SCRIPT_DIR = Path(__file__).resolve().parent

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


from validate_requirements_structure import (  # noqa: E402
    EXPECTED_FR_FIELDS,
    EXPECTED_SECTIONS,
    EXPECTED_TITLE,
    extract_feature_fields,
    extract_h2_sections,
    extract_main_fr_ids,
    find_duplicates,
    validate,
    validate_canonical_template,
    validate_feature_structure,
    validate_main_requirements,
    validate_sections,
    validate_title,
)


# ============================================================
# Test Data Builders
# ============================================================


def build_canonical_template(
    *,
    title: str = EXPECTED_TITLE,
    sections: list[str] | None = None,
    fr_fields: list[str] | None = None,
) -> str:
    """
    Validatorが期待するCanonical Templateを生成する。

    テストケースごとに章名やFR構造を変更できるようにしている。
    """

    sections = (
        EXPECTED_SECTIONS.copy()
        if sections is None
        else sections
    )

    fr_fields = (
        EXPECTED_FR_FIELDS.copy()
        if fr_fields is None
        else fr_fields
    )

    lines: list[str] = [
        f"# {title}",
        "",
    ]

    for section in sections:
        lines.extend(
            [
                f"## {section}",
                "",
            ]
        )

        if section == "13. 機能要件（FR）":
            lines.extend(
                [
                    "※必要に応じて機能ごとにファイルを分ける。",
                    "",
                    "- FR-001: サンプル機能",
                    "  - 例:",
                ]
            )

            for field in fr_fields:
                lines.extend(
                    [
                        f"    - {field}",
                        "      - サンプル",
                    ]
                )

            lines.append("")
        else:
            lines.extend(
                [
                    "- サンプル",
                    "",
                ]
            )

    return "\n".join(lines)


def build_requirements_document(
    *,
    title: str = EXPECTED_TITLE,
    sections: list[str] | None = None,
    fr_ids: list[str] | None = None,
) -> str:
    """
    docs/requirements/requirements.md 相当の
    テスト用Markdownを生成する。
    """

    sections = (
        EXPECTED_SECTIONS.copy()
        if sections is None
        else sections
    )

    fr_ids = ["FR-001"] if fr_ids is None else fr_ids

    lines: list[str] = [
        f"# {title}",
        "",
    ]

    for section in sections:
        lines.extend(
            [
                f"## {section}",
                "",
            ]
        )

        if section == "13. 機能要件（FR）":
            for fr_id in fr_ids:
                lines.append(
                    f"- {fr_id}: サンプル機能"
                )

            lines.append("")
        else:
            lines.extend(
                [
                    "- サンプル",
                    "",
                ]
            )

    return "\n".join(lines)


def build_feature_document(
    *,
    fr_id: str = "FR-001",
    feature_name: str = "サンプル機能",
    fields: list[str] | None = None,
) -> str:
    """
    分割されたFRファイルを生成する。
    """

    fields = (
        EXPECTED_FR_FIELDS.copy()
        if fields is None
        else fields
    )

    lines: list[str] = [
        f"# {fr_id}: {feature_name}",
        "",
    ]

    for field in fields:
        lines.extend(
            [
                f"- {field}",
                "  - サンプル",
                "",
            ]
        )

    return "\n".join(lines)


def write_file(
    path: Path,
    content: str,
) -> Path:
    """
    親ディレクトリを含めてテストファイルを作成する。
    """

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        content,
        encoding="utf-8",
    )

    return path


# ============================================================
# Utility Function Tests
# ============================================================


class UtilityFunctionTests(unittest.TestCase):

    def test_extract_h2_sections(self) -> None:
        text = build_requirements_document()

        actual = extract_h2_sections(text)

        self.assertEqual(
            EXPECTED_SECTIONS,
            actual,
        )

    def test_extract_main_fr_ids(self) -> None:
        text = build_requirements_document(
            fr_ids=[
                "FR-001",
                "FR-002",
                "FR-003",
            ]
        )

        actual = extract_main_fr_ids(text)

        self.assertEqual(
            [
                "FR-001",
                "FR-002",
                "FR-003",
            ],
            actual,
        )

    def test_find_duplicates(self) -> None:
        actual = find_duplicates(
            [
                "FR-001",
                "FR-002",
                "FR-001",
                "FR-003",
                "FR-002",
            ]
        )

        self.assertEqual(
            [
                "FR-001",
                "FR-002",
            ],
            actual,
        )

    def test_extract_feature_fields(self) -> None:
        text = build_feature_document()

        actual = extract_feature_fields(text)

        self.assertEqual(
            EXPECTED_FR_FIELDS,
            actual,
        )


# ============================================================
# Title Validation Tests
# ============================================================


class TitleValidationTests(unittest.TestCase):

    def test_valid_title_passes(self) -> None:
        text = build_requirements_document()

        errors = validate_title(
            text,
            "test",
        )

        self.assertEqual(
            [],
            errors,
        )

    def test_invalid_title_fails(self) -> None:
        text = build_requirements_document(
            title="要件定義書"
        )

        errors = validate_title(
            text,
            "test",
        )

        self.assertTrue(errors)

        self.assertTrue(
            any(
                "H1 title mismatch" in error
                for error in errors
            )
        )


# ============================================================
# Section Validation Tests
# ============================================================


class SectionValidationTests(unittest.TestCase):

    def test_valid_sections_pass(self) -> None:
        text = build_requirements_document()

        errors = validate_sections(
            text,
            "test",
        )

        self.assertEqual(
            [],
            errors,
        )

    def test_missing_section_fails(self) -> None:
        sections = EXPECTED_SECTIONS.copy()

        sections.remove(
            "9. 認証・認可"
        )

        text = build_requirements_document(
            sections=sections
        )

        errors = validate_sections(
            text,
            "test",
        )

        self.assertTrue(errors)

        self.assertTrue(
            any(
                "Missing section" in error
                and "9. 認証・認可" in error
                for error in errors
            )
        )

    def test_extra_section_fails(self) -> None:
        sections = EXPECTED_SECTIONS.copy()

        sections.append(
            "15. その他"
        )

        text = build_requirements_document(
            sections=sections
        )

        errors = validate_sections(
            text,
            "test",
        )

        self.assertTrue(errors)

        self.assertTrue(
            any(
                "Unexpected section" in error
                and "15. その他" in error
                for error in errors
            )
        )

    def test_section_order_change_fails(self) -> None:
        sections = EXPECTED_SECTIONS.copy()

        sections[1], sections[2] = (
            sections[2],
            sections[1],
        )

        text = build_requirements_document(
            sections=sections
        )

        errors = validate_sections(
            text,
            "test",
        )

        self.assertTrue(errors)

        self.assertTrue(
            any(
                "Section order has been changed"
                in error
                for error in errors
            )
        )

    def test_section_name_change_fails(self) -> None:
        sections = EXPECTED_SECTIONS.copy()

        sections[0] = "1. 用語"

        text = build_requirements_document(
            sections=sections
        )

        errors = validate_sections(
            text,
            "test",
        )

        self.assertTrue(errors)


# ============================================================
# Canonical Template Tests
# ============================================================


class CanonicalTemplateTests(unittest.TestCase):

    def test_valid_template_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)

            template = write_file(
                root / "requirements-template.md",
                build_canonical_template(),
            )

            errors = validate_canonical_template(
                template
            )

            self.assertEqual(
                [],
                errors,
            )

    def test_template_missing_section_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)

            sections = EXPECTED_SECTIONS.copy()
            sections.pop()

            template = write_file(
                root / "requirements-template.md",
                build_canonical_template(
                    sections=sections
                ),
            )

            errors = validate_canonical_template(
                template
            )

            self.assertTrue(errors)

    def test_template_section_order_change_fails(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)

            sections = EXPECTED_SECTIONS.copy()

            sections[0], sections[1] = (
                sections[1],
                sections[0],
            )

            template = write_file(
                root / "requirements-template.md",
                build_canonical_template(
                    sections=sections
                ),
            )

            errors = validate_canonical_template(
                template
            )

            self.assertTrue(errors)

    def test_template_missing_fr_field_fails(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)

            fields = EXPECTED_FR_FIELDS.copy()

            fields.remove(
                "エラー条件"
            )

            template = write_file(
                root / "requirements-template.md",
                build_canonical_template(
                    fr_fields=fields
                ),
            )

            errors = validate_canonical_template(
                template
            )

            self.assertTrue(errors)

            self.assertTrue(
                any(
                    "Missing FR field" in error
                    and "エラー条件" in error
                    for error in errors
                )
            )

    def test_template_fr_order_change_fails(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)

            fields = EXPECTED_FR_FIELDS.copy()

            fields[0], fields[1] = (
                fields[1],
                fields[0],
            )

            template = write_file(
                root / "requirements-template.md",
                build_canonical_template(
                    fr_fields=fields
                ),
            )

            errors = validate_canonical_template(
                template
            )

            self.assertTrue(errors)

    def test_template_not_found_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)

            errors = validate_canonical_template(
                root / "not-found.md"
            )

            self.assertTrue(errors)


# ============================================================
# Main Requirements Tests
# ============================================================


class MainRequirementsTests(unittest.TestCase):

    def test_valid_main_document_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)

            requirements = write_file(
                root / "requirements.md",
                build_requirements_document(
                    fr_ids=[
                        "FR-001",
                        "FR-002",
                    ]
                ),
            )

            errors, fr_ids = (
                validate_main_requirements(
                    requirements
                )
            )

            self.assertEqual(
                [],
                errors,
            )

            self.assertEqual(
                [
                    "FR-001",
                    "FR-002",
                ],
                fr_ids,
            )

    def test_duplicate_fr_id_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)

            requirements = write_file(
                root / "requirements.md",
                build_requirements_document(
                    fr_ids=[
                        "FR-001",
                        "FR-002",
                        "FR-001",
                    ]
                ),
            )

            errors, _ = (
                validate_main_requirements(
                    requirements
                )
            )

            self.assertTrue(errors)

            self.assertTrue(
                any(
                    "Duplicate FR ID: FR-001"
                    in error
                    for error in errors
                )
            )


# ============================================================
# Split Feature File Tests
# ============================================================


class FeatureFileTests(unittest.TestCase):

    def test_valid_feature_file_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)

            feature = write_file(
                root / "FR-001-sample.md",
                build_feature_document(),
            )

            errors, fr_id = (
                validate_feature_structure(
                    feature,
                    ["FR-001"],
                )
            )

            self.assertEqual(
                [],
                errors,
            )

            self.assertEqual(
                "FR-001",
                fr_id,
            )

    def test_feature_not_defined_in_main_fails(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)

            feature = write_file(
                root / "FR-002-sample.md",
                build_feature_document(
                    fr_id="FR-002"
                ),
            )

            errors, _ = (
                validate_feature_structure(
                    feature,
                    ["FR-001"],
                )
            )

            self.assertTrue(errors)

            self.assertTrue(
                any(
                    "FR-002 is not defined"
                    in error
                    for error in errors
                )
            )

    def test_feature_missing_field_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)

            fields = EXPECTED_FR_FIELDS.copy()

            fields.remove(
                "エラー条件"
            )

            feature = write_file(
                root / "FR-001-sample.md",
                build_feature_document(
                    fields=fields
                ),
            )

            errors, _ = (
                validate_feature_structure(
                    feature,
                    ["FR-001"],
                )
            )

            self.assertTrue(errors)

            self.assertTrue(
                any(
                    "Missing FR field" in error
                    and "エラー条件" in error
                    for error in errors
                )
            )

    def test_feature_field_order_change_fails(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)

            fields = EXPECTED_FR_FIELDS.copy()

            fields[0], fields[1] = (
                fields[1],
                fields[0],
            )

            feature = write_file(
                root / "FR-001-sample.md",
                build_feature_document(
                    fields=fields
                ),
            )

            errors, _ = (
                validate_feature_structure(
                    feature,
                    ["FR-001"],
                )
            )

            self.assertTrue(errors)

            self.assertTrue(
                any(
                    "FR field order has been changed"
                    in error
                    for error in errors
                )
            )

    def test_feature_extra_field_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)

            fields = EXPECTED_FR_FIELDS.copy()

            fields.append(
                "Agentが追加した項目"
            )

            feature = write_file(
                root / "FR-001-sample.md",
                build_feature_document(
                    fields=fields
                ),
            )

            errors, _ = (
                validate_feature_structure(
                    feature,
                    ["FR-001"],
                )
            )

            self.assertTrue(errors)

            self.assertTrue(
                any(
                    "Unexpected top-level FR field"
                    in error
                    for error in errors
                )
            )

    def test_feature_invalid_title_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)

            feature = write_file(
                root / "FR-001-sample.md",
                (
                    "# サンプル機能\n\n"
                    + "\n".join(
                        f"- {field}\n  - サンプル"
                        for field
                        in EXPECTED_FR_FIELDS
                    )
                ),
            )

            errors, fr_id = (
                validate_feature_structure(
                    feature,
                    ["FR-001"],
                )
            )

            self.assertTrue(errors)

            self.assertIsNone(fr_id)


# ============================================================
# Full Integration Tests
# ============================================================


class FullValidationTests(unittest.TestCase):

    def create_valid_repository(
        self,
        root: Path,
    ) -> tuple[Path, Path, Path]:

        template = write_file(
            (
                root
                / ".github"
                / "skills"
                / "requirements"
                / "templates"
                / "requirements-template.md"
            ),
            build_canonical_template(),
        )

        requirements = write_file(
            (
                root
                / "docs"
                / "requirements"
                / "requirements.md"
            ),
            build_requirements_document(
                fr_ids=[
                    "FR-001",
                    "FR-002",
                ]
            ),
        )

        feature_dir = (
            root
            / "docs"
            / "requirements"
            / "features"
        )

        write_file(
            (
                feature_dir
                / "FR-001-user-registration.md"
            ),
            build_feature_document(
                fr_id="FR-001",
                feature_name="ユーザー登録",
            ),
        )

        write_file(
            (
                feature_dir
                / "FR-002-login.md"
            ),
            build_feature_document(
                fr_id="FR-002",
                feature_name="ログイン",
            ),
        )

        return (
            template,
            requirements,
            feature_dir,
        )

    def test_valid_repository_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)

            (
                template,
                requirements,
                feature_dir,
            ) = self.create_valid_repository(
                root
            )

            errors = validate(
                template_path=template,
                requirements_path=requirements,
                feature_dir=feature_dir,
            )

            self.assertEqual(
                [],
                errors,
            )

    def test_template_error_stops_validation(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)

            (
                template,
                requirements,
                feature_dir,
            ) = self.create_valid_repository(
                root
            )

            broken_sections = (
                EXPECTED_SECTIONS.copy()
            )

            broken_sections.remove(
                "3. 目的"
            )

            template.write_text(
                build_canonical_template(
                    sections=broken_sections
                ),
                encoding="utf-8",
            )

            errors = validate(
                template_path=template,
                requirements_path=requirements,
                feature_dir=feature_dir,
            )

            self.assertTrue(errors)

    def test_main_document_error_fails(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)

            (
                template,
                requirements,
                feature_dir,
            ) = self.create_valid_repository(
                root
            )

            broken_sections = (
                EXPECTED_SECTIONS.copy()
            )

            broken_sections.remove(
                "10. エラー仕様（共通）"
            )

            requirements.write_text(
                build_requirements_document(
                    sections=broken_sections,
                    fr_ids=[
                        "FR-001",
                        "FR-002",
                    ],
                ),
                encoding="utf-8",
            )

            errors = validate(
                template_path=template,
                requirements_path=requirements,
                feature_dir=feature_dir,
            )

            self.assertTrue(errors)

    def test_feature_document_error_fails(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)

            (
                template,
                requirements,
                feature_dir,
            ) = self.create_valid_repository(
                root
            )

            fields = EXPECTED_FR_FIELDS.copy()

            fields.remove(
                "バリデーション"
            )

            (
                feature_dir
                / "FR-001-user-registration.md"
            ).write_text(
                build_feature_document(
                    fr_id="FR-001",
                    feature_name="ユーザー登録",
                    fields=fields,
                ),
                encoding="utf-8",
            )

            errors = validate(
                template_path=template,
                requirements_path=requirements,
                feature_dir=feature_dir,
            )

            self.assertTrue(errors)


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )