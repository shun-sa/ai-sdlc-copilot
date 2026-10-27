from __future__ import annotations

import unittest

import test_independent_addr as workflow
from design_common import (
    FINAL,
    GATE,
    RESULT,
    TEMPLATES,
    digest,
    validate_design,
    validate_gate,
)
from test_design_split import fill, read, save
from validate_addr import validate_addr, write_handoff


class LogicalDatabaseDesignTests(unittest.TestCase):
    def setUp(self):
        self.flow = workflow.IndependentAddrTests()
        self.flow.setUp()
        self.addCleanup(self.flow.doCleanups)
        self.root = self.flow.root

    def add_model(self, path="docs/architecture/db-logical-design.md", entity_id="ENT-001", multiple=False):
        template = (self.root / TEMPLATES / "logical-database-design.template.md").read_text(encoding="utf-8")
        text = fill(template.replace("<ENT-001>", "ENT-001"))
        if multiple:
            start = text.index("### 7.1 ")
            end = text.index("## 8. ")
            detail = text[start:end].replace("7.1", "7.2").replace("ENT-001", "ENT-002").replace("STATE-001", "STATE-002")
            text = text[:end] + detail + text[end:]
            row = next(line for line in text.splitlines() if line.startswith("| ENT-001 |"))
            text = text.replace(row, row + "\n" + row.replace("ENT-001", "ENT-002"), 1)
        text = text.replace("ENT-001", entity_id)
        save(self.root, path, text)
        manifest = read(self.root, FINAL)
        manifest["artifacts"].append({"artifact_id": "LDB-001", "path": path, "template": "logical-database-design", "sha256": digest(self.root / path), "target_id": "FR-001", "related_requirement_ids": ["FR-001"], "related_addr_ids": []})
        save(self.root, FINAL, manifest)
        return path

    def replace_model(self, path, before, after):
        save(self.root, path, (self.root / path).read_text(encoding="utf-8").replace(before, after))
        manifest = read(self.root, FINAL)
        next(item for item in manifest["artifacts"] if item["path"] == path)["sha256"] = digest(self.root / path)
        save(self.root, FINAL, manifest)

    def link_model(self):
        path = self.add_model()
        self.flow.addr()
        addr_path = "docs/addr/ADDR-001.md"
        text = (self.root / addr_path).read_text(encoding="utf-8")
        save(self.root, addr_path, text.replace("PLAN-001 TASK-001 docs/architecture/implementation-task-list.md", f"LDB-001 ENT-001 {path}"))
        result = read(self.root, RESULT)
        result["output_artifacts"][0]["sha256"] = digest(self.root / addr_path)
        result["artifact_link_updates"] = [{"artifact_id": "LDB-001", "target_id": "FR-001", "related_addr_id": "ADDR-001", "requested_action": "LINK_ADDR", "element_ids": ["ENT-001"]}]
        save(self.root, RESULT, result)
        return path

    def test_logical_model_is_accepted_without_addr_or_draft(self):
        self.add_model()
        self.assertEqual([], validate_design(self.root, "final"))
        self.flow.design_gate()

    def test_split_domain_path_and_repeated_entity_details_are_accepted(self):
        self.add_model("docs/architecture/db-logical-design/customer.md", multiple=True)
        self.assertEqual([], validate_design(self.root, "final"))

    def test_existing_dbd_entity_ids_remain_valid(self):
        self.add_model(entity_id="DBD-001")
        self.assertEqual([], validate_design(self.root, "final"))

    def test_logical_model_cannot_use_an_untracked_output_path(self):
        self.add_model("docs/architecture/database.md")
        self.assertTrue(any("canonical document path" in error for error in validate_design(self.root, "final")))

    def test_missing_entity_detail_is_rejected(self):
        path = self.add_model()
        self.replace_model(path, "| Entity ID | `ENT-001` |", "| Entity ID | `ENT-999` |")
        self.assertTrue(any("Entity Summary and Details differ" in error for error in validate_design(self.root, "final")))

    def test_split_design_requires_a_markdown_extension(self):
        self.add_model("docs/architecture/db-logical-design/customer.txt")
        self.assertTrue(any("canonical document path" in error for error in validate_design(self.root, "final")))

    def test_duplicate_entities_are_rejected(self):
        path = self.add_model()
        row = next(line for line in (self.root / path).read_text(encoding="utf-8").splitlines() if line.startswith("| ENT-001 |"))
        self.replace_model(path, row, row + "\n" + row)
        self.assertTrue(any("duplicate ENT-001" in error for error in validate_design(self.root, "final")))

    def test_missing_logical_design_chapter_is_rejected(self):
        path = self.add_model()
        self.replace_model(path, "## 8. Relationship定義", "## 8. Removed")
        self.assertTrue(validate_design(self.root, "final"))

    def test_addr_can_bind_to_a_real_entity_without_editing_the_model(self):
        path = self.link_model()
        before = (self.root / path).read_bytes()
        self.assertEqual([], validate_addr(self.root, True))
        self.assertEqual([], write_handoff(self.root))
        self.flow.assurance("ADDR", "reports/addr/implementation-handoff.json")
        self.assertEqual([], workflow.write_gate(self.root))
        self.assertEqual([], validate_gate(self.root))
        self.assertEqual(before, (self.root / path).read_bytes())
        self.assertEqual(read(self.root, GATE)["phase"], "ADDR")

    def test_addr_cannot_bind_to_an_undefined_entity(self):
        self.link_model()
        result = read(self.root, RESULT)
        result["artifact_link_updates"][0]["element_ids"] = ["ENT-999"]
        save(self.root, RESULT, result)
        self.assertTrue(validate_addr(self.root, True))

    def test_modified_logical_model_invalidates_frozen_handoff(self):
        path = self.link_model()
        save(self.root, path, (self.root / path).read_text(encoding="utf-8") + "\n変更\n")
        self.assertTrue(validate_addr(self.root, True))
        self.assertTrue(write_handoff(self.root))

    def test_traceability_reads_ent_entities_and_their_addr_bindings(self):
        self.link_model()
        self.assertEqual([], write_handoff(self.root))
        audit = self.flow.trace("ADDR")
        self.assertFalse(audit.issues, audit.issues)
        self.assertEqual(audit.elements["ENT-001"].kind, "entity")
        self.assertIn("ADDR-001", audit.elements["ENT-001"].refs)

    def test_projects_without_database_design_still_release(self):
        self.flow.release(False)
        self.assertEqual([], validate_gate(self.root))

    def test_traceability_reads_split_models_and_all_entity_definitions(self):
        self.add_model("docs/architecture/db-logical-design/customer.md", multiple=True)
        self.flow.release(False)
        audit = self.flow.trace("ADDR")
        self.assertFalse(audit.issues, audit.issues)
        for identifier in ("ENT-001", "ENT-002"):
            self.assertEqual(audit.elements[identifier].kind, "entity")


if __name__ == "__main__":
    unittest.main(verbosity=2)
