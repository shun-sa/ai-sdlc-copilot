from __future__ import annotations

import importlib.util
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from validate_requirements_structure import (
    ARTIFACTS, INDEX, STEERING_OUTPUT, STEERING_TEMPLATE, TEMPLATE_DIR,
    non_functional_rows, parse_document, row_records, validate, validate_document, visible_text,
)


REPOSITORY = SCRIPT_DIR.parents[3]


def filled(template: str, name: str) -> str:
    counter = 0

    def replace(match: re.Match) -> str:
        nonlocal counter
        label = match.group(1)
        if label == "ID" and name == "non_functional_requirements.md":
            counter += 1
            headers = re.findall(r"(?m)^\| [^\n]+\n\|[-|]+\|", match.string[:match.start()])
            prefix = "NFR" if headers and (("要件項目" in headers[-1] and "目標値（単位付き）" in headers[-1]) or "法令・規約名" in headers[-1]) else "AUX"
            return f"{prefix}-{counter:03d}"
        if label == "ID" and name == "functional_requirements.md":
            return "FR-001"
        for token, value in (
            ("機能ID", "FR-001"), ("Requirement ID", "FR-001"),
            ("Use Case ID", "UC-001"), ("UC ID", "UC-001"),
            ("User Story ID", "US-001"), ("US ID", "US-001"),
            ("Actor ID", "ACT-001"), ("AC ID", "AC-001"),
        ):
            if token in label:
                return value
        if label == "相対パス":
            return "use-cases/UC-001.md"
        return "記入済み"

    text = re.sub(r"\{\{([^{}]+)\}\}", replace, visible_text(template))
    if name == "steering":
        for path in (str(INDEX), ARTIFACTS["use_case_user_story_list.md"], "docs/requirements/use-cases/", ARTIFACTS["glossary.md"]):
            reference = path.replace("\\", "/")
            text = text.replace(f"<{reference}>", reference)
    return re.sub(r"<[^<>\n]+>", "記入済み", text) if name == "steering" else text


def create_repository(root: Path) -> None:
    shutil.copytree(REPOSITORY / TEMPLATE_DIR, root / TEMPLATE_DIR)
    (root / STEERING_TEMPLATE).parent.mkdir(parents=True)
    shutil.copyfile(REPOSITORY / STEERING_TEMPLATE, root / STEERING_TEMPLATE)
    for name, output in ARTIFACTS.items():
        path = root / output
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(filled((root / TEMPLATE_DIR / name).read_text(encoding="utf-8"), name), encoding="utf-8")
    (root / STEERING_OUTPUT).write_text(filled((root / STEERING_TEMPLATE).read_text(encoding="utf-8"), "steering"), encoding="utf-8")
    detail = root / "docs/requirements/use-cases/UC-001.md"
    detail.parent.mkdir()
    detail.write_text(filled((root / TEMPLATE_DIR / "use_case_detail.md").read_text(encoding="utf-8"), "uc"), encoding="utf-8")
    write_index(root)


def write_index(root: Path) -> None:
    paths = list(ARTIFACTS.values()) + ["../../.github/project-context/project-ai-steering.md", "docs/requirements/use-cases/UC-001.md"]
    lines = ["# Requirements Index", "", "## 成果物"]
    for path in paths:
        relative = path.removeprefix("docs/requirements/")
        lines.append(f"- [文書]({relative})")
    lines.extend(["", "## 機能要件", "- FR-001: [機能](functional_requirements.md)", "", "## 非機能要件"])
    document = parse_document((root / ARTIFACTS["non_functional_requirements.md"]).read_text(encoding="utf-8"))
    for row in non_functional_rows(document):
        lines.append(f"- {row['ID']}: [要件](non_functional_requirements.md)")
    (root / INDEX).write_text("\n".join(lines) + "\n", encoding="utf-8")


class RequirementsTests(unittest.TestCase):
    def test_compliance_requirements_are_part_of_the_requirement_catalog(self) -> None:
        document = parse_document((self.root / ARTIFACTS["non_functional_requirements.md"]).read_text(encoding="utf-8"))
        legal = next(row for row in non_functional_rows(document) if "法令・規約名" in row)
        self.change("docs/requirements/use-cases/UC-001.md", "| 関連Requirement ID | FR-001 |", f"| 関連Requirement ID | {legal['ID']} |")
        self.assertEqual([], validate(self.root))
        self.change(INDEX, f"- {legal['ID']}: [要件](non_functional_requirements.md)", "")
        self.assert_error("IDs differ")

    def test_existing_compound_requirement_ids_are_preserved(self) -> None:
        for path in self.root.rglob("*.md"):
            if ".github/skills" in path.as_posix() or "templates" in path.parts:
                continue
            text = path.read_text(encoding="utf-8")
            path.write_text(text.replace("NFR-002", "NFR-SC-02").replace("NFR-001", "NFR-PF-01"), encoding="utf-8")
        self.assertEqual([], validate(self.root))

    def test_compound_identifiers_are_not_truncated(self) -> None:
        from validate_requirements_structure import IDENTIFIER
        self.assertEqual(["NFR-SC-01", "AC-UC-001-001", "FR-001"], IDENTIFIER.findall("NFR-SC-01, AC-UC-001-001, FR-001"))

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        create_repository(self.root)

    def change(self, path: str | Path, old: str, new: str) -> None:
        target = self.root / path
        text = target.read_text(encoding="utf-8")
        self.assertIn(old, text)
        target.write_text(text.replace(old, new, 1), encoding="utf-8")

    def assert_error(self, fragment: str) -> None:
        self.assertTrue(any(fragment in error for error in validate(self.root)), validate(self.root))

    def test_actual_templates_pass(self) -> None:
        self.assertEqual([], validate(self.root))

    def test_missing_template_fails(self) -> None:
        (self.root / TEMPLATE_DIR / "glossary.md").unlink()
        self.assert_error("glossary.md")

    def test_missing_output_fails(self) -> None:
        (self.root / ARTIFACTS["data_requirements.md"]).unlink()
        self.assert_error("data_requirements.md")

    def test_missing_steering_fails(self) -> None:
        (self.root / STEERING_OUTPUT).unlink()
        self.assert_error("steering")

    def test_renamed_heading_fails(self) -> None:
        self.change(ARTIFACTS["business_requirements.md"], "## 2. 背景", "## 2. 新背景")
        self.assert_error("heading")

    def test_reordered_headings_fail(self) -> None:
        self.change(ARTIFACTS["glossary.md"], "## 2. 用語カテゴリ", "## 9. 用語カテゴリ")
        self.assert_error("heading")

    def test_extra_heading_fails(self) -> None:
        with (self.root / ARTIFACTS["glossary.md"]).open("a", encoding="utf-8") as output:
            output.write("\n## 99. 追加章\n")
        self.assert_error("unexpected")

    def test_missing_nested_heading_fails(self) -> None:
        self.change(ARTIFACTS["functional_requirements.md"], "#### 6.1.7 例外・エラー", "例外・エラー")
        self.assert_error("6.1.7")

    def test_changed_table_columns_fail(self) -> None:
        self.change(ARTIFACTS["glossary.md"], "| Term ID | 用語 |", "| Term ID | 別名 |")
        self.assert_error("columns")

    def test_blank_cell_fails(self) -> None:
        self.change(ARTIFACTS["functional_requirements.md"], "| 機能ID | FR-001 |", "| 機能ID |  |")
        self.assert_error("empty cell")

    def test_unfilled_placeholder_fails(self) -> None:
        self.change(ARTIFACTS["data_requirements.md"], "system_name: \"記入済み\"", "system_name: \"{{システム名}}\"")
        self.assert_error("placeholder")

    def test_comment_and_fenced_headings_are_ignored(self) -> None:
        with (self.root / ARTIFACTS["glossary.md"]).open("a", encoding="utf-8") as output:
            output.write("\n<!-- ## 追加章 {{説明}} -->\n```text\n## 見本\n```\n")
        self.assertEqual([], validate(self.root))

    def test_duplicate_fr_fails(self) -> None:
        target = self.root / ARTIFACTS["functional_requirements.md"]
        lines = target.read_text(encoding="utf-8").splitlines()
        row = next(line for line in lines if line.startswith("| FR-001 |") and len(line.split("|")) == 11)
        self.change(ARTIFACTS["functional_requirements.md"], row, row + "\n" + row)
        self.assert_error("duplicate definition FR-001")

    def test_duplicate_nfr_fails(self) -> None:
        self.change(ARTIFACTS["non_functional_requirements.md"], "NFR-002", "NFR-001")
        self.assert_error("duplicate definition NFR-001")

    def test_removed_nfr_representative_item_fails(self) -> None:
        target = self.root / ARTIFACTS["non_functional_requirements.md"]
        lines = target.read_text(encoding="utf-8").splitlines()
        target.write_text("\n".join(line for line in lines if not line.startswith("| NFR-001 |")), encoding="utf-8")
        self.assert_error("representative item removed")

    def test_detail_id_mismatch_fails(self) -> None:
        self.change(ARTIFACTS["functional_requirements.md"], "### 6.1 FR-001", "### 6.1 FR-999")
        self.assert_error("list and detail")

    def test_detail_metadata_id_mismatch_fails(self) -> None:
        self.change(ARTIFACTS["functional_requirements.md"], "| 機能ID | FR-001 |", "| 機能ID | FR-999 |")
        self.assert_error("basic information ID differs")

    def test_steering_reference_mismatch_fails(self) -> None:
        self.change(STEERING_OUTPUT, "docs/requirements/glossary.md", "docs/requirements/absent.md")
        self.assert_error("AI Steering reference")

    def test_unknown_requirement_reference_fails(self) -> None:
        self.change(ARTIFACTS["use_case_user_story_list.md"], "FR-001", "FR-999")
        self.assert_error("undefined reference FR-999")

    def test_uc_detail_unknown_requirement_reference_fails(self) -> None:
        self.change("docs/requirements/use-cases/UC-001.md", "| 関連Requirement ID | FR-001 |", "| 関連Requirement ID | FR-999 |")
        self.assert_error("undefined reference FR-999")

    def test_missing_uc_file_fails(self) -> None:
        (self.root / "docs/requirements/use-cases/UC-001.md").unlink()
        self.assert_error("UC-001.md")

    def test_uc_identity_mismatch_fails(self) -> None:
        self.change("docs/requirements/use-cases/UC-001.md", "| Use Case ID | UC-001 |", "| Use Case ID | UC-999 |")
        self.change("docs/requirements/use-cases/UC-001.md", "| Use Case ID | UC-001 |", "| Use Case ID | UC-999 |")
        self.assert_error("Use Case ID differs")

    def test_uc_path_escape_fails(self) -> None:
        self.change(ARTIFACTS["use_case_user_story_list.md"], "use-cases/UC-001.md", "../../../outside.md")
        self.assert_error("path invalid")

    def test_orphan_uc_file_fails(self) -> None:
        shutil.copyfile(self.root / "docs/requirements/use-cases/UC-001.md", self.root / "docs/requirements/use-cases/UC-002.md")
        self.assert_error("Unlisted")

    def test_index_missing_definition_fails(self) -> None:
        self.change(INDEX, "- FR-001: [機能](functional_requirements.md)", "")
        self.assert_error("IDs differ")

    def test_index_title_contract_fails(self) -> None:
        self.change(INDEX, "# Requirements Index", "# 要件一覧")
        self.assert_error("downstream discovery")

    def test_duplicate_acceptance_criteria_fail(self) -> None:
        path = "docs/requirements/use-cases/UC-001.md"
        text = (self.root / path).read_text(encoding="utf-8")
        block = text.split("### 9.1 ", 1)[1].split("## 10.", 1)[0]
        self.change(path, "## 10.", "### 9.2 " + block + "## 10.")
        self.assert_error("Duplicate AC definition")

    def test_index_wrong_requirement_source_fails(self) -> None:
        self.change(INDEX, "- FR-001: [機能](functional_requirements.md)", "- FR-001: [機能](glossary.md)")
        self.assert_error("wrong source link")

    def test_index_missing_artifact_fails(self) -> None:
        self.change(INDEX, "- [文書](glossary.md)", "")
        self.assert_error("missing artifact link")

    def test_repeated_blocks_and_actor_columns_pass(self) -> None:
        name = "functional_requirements.md"
        template = (self.root / TEMPLATE_DIR / name).read_text(encoding="utf-8")
        text = (self.root / ARTIFACTS[name]).read_text(encoding="utf-8")
        block = text.split("### 6.1 ", 1)[1].split("## 7.", 1)[0]
        text = text.replace("## 7.", "### 6.2 " + block.replace("6.1.", "6.2.") + "## 7.", 1)
        text = text.replace("| 機能ID | 機能名 | 記入済み | 記入済み | 記入済み |", "| 機能ID | 機能名 | 利用者 |")
        lines = text.splitlines()
        inside = False
        for position, line in enumerate(lines):
            if line.startswith("### 5.1"):
                inside = True
            if line.startswith("### 5.2"):
                inside = False
            if inside and line.startswith("|---"):
                lines[position] = "|---|---|---|"
            elif inside and line.startswith("| FR-001 |"):
                lines[position] = "| FR-001 | 記入済み | ○ |"
        self.assertEqual([], validate_document(template, "\n".join(lines), Path(name)))

    def test_no_external_interface_repeat_block_passes(self) -> None:
        name = "external_interface_requirements.md"
        text = (self.root / ARTIFACTS[name]).read_text(encoding="utf-8")
        start = text.index("### 5.1 ")
        end = text.index("## 6. 責任分界", start)
        text = text[:start] + "該当なし\n\n" + text[end:]
        self.assertEqual([], validate_document((self.root / TEMPLATE_DIR / name).read_text(encoding="utf-8"), text, Path(name)))

    def test_alternate_existing_requirement_ids_pass(self) -> None:
        for path in (self.root / "docs/requirements").rglob("*.md"):
            path.write_text(path.read_text(encoding="utf-8").replace("FR-001", "REQ-101"), encoding="utf-8")
        self.assertEqual([], validate(self.root))

    def test_front_matter_missing_field_fails(self) -> None:
        self.change(ARTIFACTS["glossary.md"], 'author: "記入済み"', "")
        self.assert_error("front matter")

    def test_cli_success_and_failure(self) -> None:
        command = [sys.executable, str(SCRIPT_DIR / "validate_requirements_structure.py"), "--root", str(self.root)]
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        result = subprocess.run(command[:2], cwd=self.root, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        (self.root / STEERING_OUTPUT).unlink()
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(1, result.returncode)
        self.assertNotIn("Traceback", result.stderr)

    def test_inline_traceability_reads_primary_requirements_not_derived_index(self) -> None:
        directory = REPOSITORY / ".github/skills/traceability-audit/scripts"
        sys.path.insert(0, str(directory))
        self.addCleanup(sys.path.remove, str(directory))
        spec = importlib.util.spec_from_file_location("requirements_traceability_contract", directory / "trace_check.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        self.addCleanup(sys.modules.pop, spec.name, None)
        spec.loader.exec_module(module)
        policy = module.load_policy(directory.parent / "policy/traceability-policy.yaml")
        audit = module.Auditor(self.root, policy, "REQUIREMENTS")
        audit.load()
        audit.check_all(None)
        identifiers = {identifier for identifier, element in audit.elements.items() if element.kind == "requirement"}
        document = parse_document((self.root / ARTIFACTS["non_functional_requirements.md"]).read_text(encoding="utf-8"))
        expected = {"FR-001", "UC-001"} | {row["ID"] for row in non_functional_rows(document)}
        self.assertEqual(expected, identifiers)
        self.assertFalse(audit.duplicates)
        self.assertFalse(audit.issues, audit.issues)
        legacy_features = self.root / "docs/requirements/features"
        legacy_features.mkdir()
        (legacy_features / "FR-999.md").write_text("# FR-999: 廃止済み資料", encoding="utf-8")
        audit = module.Auditor(self.root, policy, "REQUIREMENTS")
        audit.load()
        identifiers = {identifier for identifier, element in audit.elements.items() if element.kind == "requirement"}
        self.assertEqual(expected, identifiers)


if __name__ == "__main__":
    unittest.main(verbosity=2)
