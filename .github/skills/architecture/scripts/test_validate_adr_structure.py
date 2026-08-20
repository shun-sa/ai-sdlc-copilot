from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


# 同じscriptsディレクトリにあるValidatorをimportする
SCRIPT_DIR = Path(__file__).resolve().parent

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


from validate_adr_structure import (  # noqa: E402
    EXPECTED_SECTIONS,
    extract_adr_id,
    extract_related_requirements,
    extract_sections,
    validate,
    validate_adr,
    validate_ai_guardrails,
    validate_alternatives,
    validate_length,
    validate_related_requirements,
    validate_required_content,
    validate_sections,
    validate_status,
    validate_title,
)


# ============================================================
# Test Data Builders
# ============================================================


def build_adr(
    *,
    adr_id: str = "ADR-001",
    title: str = "認証方式を決定する",
    status: str = "Proposed",
    related_requirements: list[str] | None = None,
    sections: list[str] | None = None,
    alternatives: list[str] | None = None,
    consequences: list[str] | None = None,
    guardrails: list[str] | None = None,
    context: str = "認証方式について設計判断が必要である。",
    decision: str = "OpenID Connectを採用する。",
) -> str:
    """
    正常なADRを基本として、
    テストケースごとに一部だけ変更できるBuilder。
    """

    related_requirements = (
        ["FR-001", "NFR-001"]
        if related_requirements is None
        else related_requirements
    )

    sections = (
        EXPECTED_SECTIONS.copy()
        if sections is None
        else sections
    )

    alternatives = (
        [
            "OpenID Connect: 採用",
            "SAML: SPAとの親和性を考慮して不採用",
        ]
        if alternatives is None
        else alternatives
    )

    consequences = (
        [
            "自前でパスワードを管理する必要がない。",
            "IdPとの連携設定が必要になる。",
            "後続実装ではトークン検証が必要になる。",
        ]
        if consequences is None
        else consequences
    )

    guardrails = (
        [
            "独自パスワード認証を実装しない。",
            "API側でトークン検証を省略しない。",
        ]
        if guardrails is None
        else guardrails
    )

    content: dict[str, list[str]] = {
        "Status": [
            status,
        ],
        "Related Requirements": [
            f"- {requirement}"
            for requirement in related_requirements
        ],
        "Context": [
            context,
        ],
        "Decision": [
            decision,
        ],
        "Alternatives": [
            f"- {alternative}"
            for alternative in alternatives
        ],
        "Consequences": [
            f"- {consequence}"
            for consequence in consequences
        ],
        "AI Guardrails": [
            f"- {guardrail}"
            for guardrail in guardrails
        ],
    }

    lines: list[str] = [
        f"# {adr_id} {title}",
        "",
    ]

    for section in sections:
        lines.append(f"## {section}")
        lines.append("")

        # 不明な追加Sectionのテストにも対応
        section_content = content.get(
            section,
            ["追加された内容"],
        )

        lines.extend(section_content)
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def write_file(
    path: Path,
    content: str,
) -> Path:
    """
    テスト用ファイルを書き込む。
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


def create_requirements(
    root: Path,
    ids: list[str] | None = None,
) -> Path:
    """
    Related Requirements存在チェック用の
    Requirements成果物を作成する。
    """

    ids = (
        [
            "FR-001",
            "FR-002",
            "NFR-001",
            "NFR-002",
        ]
        if ids is None
        else ids
    )

    content = (
        "# 要件定義構造\n\n"
        + "\n".join(
            f"- {requirement_id}: テスト用要件"
            for requirement_id in ids
        )
        + "\n"
    )

    return write_file(
        root / "docs" / "requirements" / "requirements.md",
        content,
    )


# ============================================================
# Basic Extraction Tests
# ============================================================


class ExtractionTests(unittest.TestCase):

    def test_extract_sections(self) -> None:
        adr = build_adr()

        self.assertEqual(
            EXPECTED_SECTIONS,
            extract_sections(adr),
        )

    def test_extract_adr_id(self) -> None:
        adr = build_adr(
            adr_id="ADR-123"
        )

        self.assertEqual(
            "ADR-123",
            extract_adr_id(adr),
        )

    def test_extract_related_requirements(self) -> None:
        adr = build_adr(
            related_requirements=[
                "FR-001",
                "NFR-002",
            ]
        )

        self.assertEqual(
            [
                "FR-001",
                "NFR-002",
            ],
            extract_related_requirements(adr),
        )


# ============================================================
# Title Tests
# ============================================================


class TitleValidationTests(unittest.TestCase):

    def test_valid_title_passes(self) -> None:
        path = Path(
            "ADR-001-authentication.md"
        )

        errors = validate_title(
            build_adr(),
            path,
        )

        self.assertEqual(
            [],
            errors,
        )

    def test_invalid_title_format_fails(self) -> None:
        path = Path(
            "ADR-001-authentication.md"
        )

        adr = build_adr().replace(
            "# ADR-001 認証方式を決定する",
            "# 認証方式を決定する",
        )

        errors = validate_title(
            adr,
            path,
        )

        self.assertTrue(errors)

    def test_filename_and_title_id_mismatch_fails(
        self,
    ) -> None:
        path = Path(
            "ADR-002-authentication.md"
        )

        errors = validate_title(
            build_adr(
                adr_id="ADR-001"
            ),
            path,
        )

        self.assertTrue(errors)

        self.assertTrue(
            any(
                "ADR ID mismatch" in error
                for error in errors
            )
        )

    def test_invalid_filename_fails(self) -> None:
        path = Path(
            "authentication.md"
        )

        errors = validate_title(
            build_adr(),
            path,
        )

        self.assertTrue(errors)


# ============================================================
# Section Tests
# ============================================================


class SectionValidationTests(unittest.TestCase):

    def test_valid_sections_pass(self) -> None:
        errors = validate_sections(
            build_adr(),
            Path("ADR-001-test.md"),
        )

        self.assertEqual(
            [],
            errors,
        )

    def test_missing_section_fails(self) -> None:
        sections = EXPECTED_SECTIONS.copy()

        sections.remove(
            "AI Guardrails"
        )

        adr = build_adr(
            sections=sections
        )

        errors = validate_sections(
            adr,
            Path("ADR-001-test.md"),
        )

        self.assertTrue(errors)

        self.assertTrue(
            any(
                "Missing section" in error
                and "AI Guardrails" in error
                for error in errors
            )
        )

    def test_extra_section_fails(self) -> None:
        sections = EXPECTED_SECTIONS.copy()

        sections.append(
            "Implementation Notes"
        )

        adr = build_adr(
            sections=sections
        )

        errors = validate_sections(
            adr,
            Path("ADR-001-test.md"),
        )

        self.assertTrue(errors)

        self.assertTrue(
            any(
                "Unexpected section" in error
                for error in errors
            )
        )

    def test_section_order_change_fails(self) -> None:
        sections = EXPECTED_SECTIONS.copy()

        sections[0], sections[1] = (
            sections[1],
            sections[0],
        )

        adr = build_adr(
            sections=sections
        )

        errors = validate_sections(
            adr,
            Path("ADR-001-test.md"),
        )

        self.assertTrue(errors)

        self.assertTrue(
            any(
                "ADR section order has been changed"
                in error
                for error in errors
            )
        )


# ============================================================
# Status Tests
# ============================================================


class StatusValidationTests(unittest.TestCase):

    def test_proposed_status_passes(self) -> None:
        errors = validate_status(
            build_adr(
                status="Proposed"
            ),
            Path("ADR-001-test.md"),
        )

        self.assertEqual(
            [],
            errors,
        )

    def test_accepted_status_passes(self) -> None:
        errors = validate_status(
            build_adr(
                status="Accepted"
            ),
            Path("ADR-001-test.md"),
        )

        self.assertEqual(
            [],
            errors,
        )

    def test_superseded_status_passes(self) -> None:
        errors = validate_status(
            build_adr(
                status="Superseded"
            ),
            Path("ADR-001-test.md"),
        )

        self.assertEqual(
            [],
            errors,
        )

    def test_rejected_status_passes(self) -> None:
        errors = validate_status(
            build_adr(
                status="Rejected"
            ),
            Path("ADR-001-test.md"),
        )

        self.assertEqual(
            [],
            errors,
        )

    def test_invalid_status_fails(self) -> None:
        errors = validate_status(
            build_adr(
                status="Done"
            ),
            Path("ADR-001-test.md"),
        )

        self.assertTrue(errors)

        self.assertTrue(
            any(
                "Invalid Status" in error
                for error in errors
            )
        )


# ============================================================
# Related Requirements Tests
# ============================================================


class RelatedRequirementsTests(unittest.TestCase):

    def test_valid_related_requirements_pass(
        self,
    ) -> None:
        adr = build_adr(
            related_requirements=[
                "FR-001",
                "NFR-001",
            ]
        )

        errors = validate_related_requirements(
            adr,
            Path("ADR-001-test.md"),
            {
                "FR-001",
                "NFR-001",
            },
            True,
        )

        self.assertEqual(
            [],
            errors,
        )

    def test_missing_related_requirements_fails(
        self,
    ) -> None:
        adr = build_adr(
            related_requirements=[]
        )

        errors = validate_related_requirements(
            adr,
            Path("ADR-001-test.md"),
            set(),
            True,
        )

        self.assertTrue(errors)

        self.assertTrue(
            any(
                "at least one Requirement ID"
                in error
                for error in errors
            )
        )

    def test_nonexistent_requirement_fails(
        self,
    ) -> None:
        adr = build_adr(
            related_requirements=[
                "FR-999"
            ]
        )

        errors = validate_related_requirements(
            adr,
            Path("ADR-001-test.md"),
            {
                "FR-001"
            },
            True,
        )

        self.assertTrue(errors)

        self.assertTrue(
            any(
                "does not exist" in error
                for error in errors
            )
        )

    def test_duplicate_requirement_fails(
        self,
    ) -> None:
        adr = build_adr(
            related_requirements=[
                "FR-001",
                "FR-001",
            ]
        )

        errors = validate_related_requirements(
            adr,
            Path("ADR-001-test.md"),
            {
                "FR-001"
            },
            True,
        )

        self.assertTrue(errors)

        self.assertTrue(
            any(
                "Duplicate Related Requirement"
                in error
                for error in errors
            )
        )

    def test_requirement_existence_check_can_be_skipped(
        self,
    ) -> None:
        adr = build_adr(
            related_requirements=[
                "FR-999"
            ]
        )

        errors = validate_related_requirements(
            adr,
            Path("ADR-001-test.md"),
            set(),
            False,
        )

        self.assertEqual(
            [],
            errors,
        )


# ============================================================
# Required Content Tests
# ============================================================


class RequiredContentTests(unittest.TestCase):

    def test_required_content_passes(self) -> None:
        errors = validate_required_content(
            build_adr(),
            Path("ADR-001-test.md"),
        )

        self.assertEqual(
            [],
            errors,
        )

    def test_empty_decision_fails(self) -> None:
        adr = build_adr(
            decision=""
        )

        errors = validate_required_content(
            adr,
            Path("ADR-001-test.md"),
        )

        self.assertTrue(errors)

        self.assertTrue(
            any(
                "'Decision' must not be empty"
                in error
                for error in errors
            )
        )

    def test_empty_context_fails(self) -> None:
        adr = build_adr(
            context=""
        )

        errors = validate_required_content(
            adr,
            Path("ADR-001-test.md"),
        )

        self.assertTrue(errors)


# ============================================================
# Alternatives Tests
# ============================================================


class AlternativesValidationTests(unittest.TestCase):

    def test_three_alternatives_pass(self) -> None:
        adr = build_adr(
            alternatives=[
                "案A",
                "案B",
                "案C",
            ]
        )

        errors = validate_alternatives(
            adr,
            Path("ADR-001-test.md"),
        )

        self.assertEqual(
            [],
            errors,
        )

    def test_four_alternatives_fail(self) -> None:
        adr = build_adr(
            alternatives=[
                "案A",
                "案B",
                "案C",
                "案D",
            ]
        )

        errors = validate_alternatives(
            adr,
            Path("ADR-001-test.md"),
        )

        self.assertTrue(errors)

        self.assertTrue(
            any(
                "Maximum is 3" in error
                for error in errors
            )
        )

    def test_no_alternative_fails(self) -> None:
        adr = build_adr(
            alternatives=[]
        )

        errors = validate_alternatives(
            adr,
            Path("ADR-001-test.md"),
        )

        self.assertTrue(errors)


# ============================================================
# AI Guardrails Tests
# ============================================================


class GuardrailsValidationTests(unittest.TestCase):

    def test_three_guardrails_pass(self) -> None:
        adr = build_adr(
            guardrails=[
                "制約1",
                "制約2",
                "制約3",
            ]
        )

        errors = validate_ai_guardrails(
            adr,
            Path("ADR-001-test.md"),
        )

        self.assertEqual(
            [],
            errors,
        )

    def test_four_guardrails_fail(self) -> None:
        adr = build_adr(
            guardrails=[
                "制約1",
                "制約2",
                "制約3",
                "制約4",
            ]
        )

        errors = validate_ai_guardrails(
            adr,
            Path("ADR-001-test.md"),
        )

        self.assertTrue(errors)

        self.assertTrue(
            any(
                "Maximum is 3" in error
                for error in errors
            )
        )

    def test_no_guardrail_fails(self) -> None:
        adr = build_adr(
            guardrails=[]
        )

        errors = validate_ai_guardrails(
            adr,
            Path("ADR-001-test.md"),
        )

        self.assertTrue(errors)


# ============================================================
# Length Tests
# ============================================================


class LengthValidationTests(unittest.TestCase):

    def test_normal_adr_length_passes(self) -> None:
        adr = build_adr()

        errors = validate_length(
            adr,
            Path("ADR-001-test.md"),
        )

        self.assertEqual(
            [],
            errors,
        )

    def test_over_50_lines_fails(self) -> None:
        adr = build_adr()

        adr += "\n".join(
            f"追加行 {index}"
            for index in range(1, 60)
        )

        errors = validate_length(
            adr,
            Path("ADR-001-test.md"),
        )

        self.assertTrue(errors)

        self.assertTrue(
            any(
                "Recommended maximum is 50"
                in error
                for error in errors
            )
        )


# ============================================================
# ADR Integration Tests
# ============================================================


class ADRValidationTests(unittest.TestCase):

    def test_valid_adr_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)

            adr_path = write_file(
                root
                / "ADR-001-authentication.md",
                build_adr(),
            )

            errors = validate_adr(
                adr_path,
                {
                    "FR-001",
                    "NFR-001",
                },
                True,
            )

            self.assertEqual(
                [],
                errors,
            )

    def test_invalid_adr_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)

            adr_path = write_file(
                root
                / "ADR-001-authentication.md",
                build_adr(
                    status="Done",
                    decision="",
                ),
            )

            errors = validate_adr(
                adr_path,
                {
                    "FR-001",
                    "NFR-001",
                },
                True,
            )

            self.assertTrue(errors)


# ============================================================
# Full Repository Validation Tests
# ============================================================


class FullValidationTests(unittest.TestCase):

    def test_valid_repository_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)

            requirements = create_requirements(
                root
            )

            adr_dir = (
                root
                / "docs"
                / "adr"
            )

            write_file(
                adr_dir
                / "ADR-001-authentication.md",
                build_adr(
                    adr_id="ADR-001",
                    related_requirements=[
                        "FR-001",
                        "NFR-001",
                    ],
                ),
            )

            write_file(
                adr_dir
                / "ADR-002-api.md",
                build_adr(
                    adr_id="ADR-002",
                    title="API方式を決定する",
                    related_requirements=[
                        "FR-002",
                        "NFR-002",
                    ],
                ),
            )

            errors = validate(
                adr_path=adr_dir,
                requirements_root=requirements.parent,
            )

            self.assertEqual(
                [],
                errors,
            )

    def test_unknown_requirement_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)

            requirements = create_requirements(
                root,
                ids=[
                    "FR-001",
                    "NFR-001",
                ],
            )

            adr_dir = (
                root
                / "docs"
                / "adr"
            )

            write_file(
                adr_dir
                / "ADR-001-authentication.md",
                build_adr(
                    related_requirements=[
                        "FR-999"
                    ]
                ),
            )

            errors = validate(
                adr_path=adr_dir,
                requirements_root=requirements.parent,
            )

            self.assertTrue(errors)

            self.assertTrue(
                any(
                    "FR-999" in error
                    and "does not exist" in error
                    for error in errors
                )
            )

    def test_duplicate_adr_id_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)

            requirements = create_requirements(
                root
            )

            adr_dir = (
                root
                / "docs"
                / "adr"
            )

            write_file(
                adr_dir
                / "ADR-001-authentication.md",
                build_adr(
                    adr_id="ADR-001"
                ),
            )

            write_file(
                adr_dir
                / "ADR-001-authentication-v2.md",
                build_adr(
                    adr_id="ADR-001"
                ),
            )

            errors = validate(
                adr_path=adr_dir,
                requirements_root=requirements.parent,
            )

            self.assertTrue(errors)

            self.assertTrue(
                any(
                    "Duplicate ADR ID: ADR-001"
                    in error
                    for error in errors
                )
            )

    def test_no_adr_files_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)

            requirements = create_requirements(
                root
            )

            empty_adr_dir = (
                root
                / "docs"
                / "adr"
            )

            empty_adr_dir.mkdir(
                parents=True
            )

            errors = validate(
                adr_path=empty_adr_dir,
                requirements_root=requirements.parent,
            )

            self.assertTrue(errors)

            self.assertTrue(
                any(
                    "No ADR files found"
                    in error
                    for error in errors
                )
            )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )