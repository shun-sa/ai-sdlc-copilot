#!/usr/bin/env python3
"""Unit tests for traceability_ast.py."""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import traceability_ast as astmod


def policy() -> dict[str, Any]:
    return {
        "source_analysis": {
            "enabled": True,
            "production_roots": ["src", "app"],
            "test_roots": ["tests", "test", "src/test"],
            "test_file_patterns": [
                "**/test_*.py",
                "**/*_test.py",
                "**/*.test.ts",
                "**/*.test.tsx",
                "**/*.spec.ts",
                "**/*.spec.tsx",
                "**/*.test.js",
                "**/*.test.jsx",
                "**/*.spec.js",
                "**/*.spec.jsx",
                "**/__tests__/**",
            ],
            "include_extensions": [".py", ".java", ".ts", ".tsx", ".js", ".jsx"],
            "exclude_globs": ["**/__pycache__/**", "**/node_modules/**"],
        },
        "implementation_analysis": {
            "detect_orphan_symbols": True,
            "candidate_kinds": ["class", "function", "method"],
            "ignore_private_symbols": True,
            "ignore_file_patterns": [],
            "ignore_symbol_patterns": [],
        },
    }


class PythonAstTest(unittest.TestCase):
    def test_python_symbols_calls_and_assertions(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "src/pkg").mkdir(parents=True)
            (root / "tests").mkdir()
            (root / "src/pkg/service.py").write_text(
                "def helper(x):\n"
                "    return x + 1\n\n"
                "class UserService:\n"
                "    def register(self, x):\n"
                "        return helper(x)\n",
                encoding="utf-8",
            )
            (root / "tests/test_service.py").write_text(
                "from src.pkg.service import UserService\n\n"
                "def test_register():\n"
                "    service = UserService()\n"
                "    result = service.register(1)\n"
                "    assert result == 2\n",
                encoding="utf-8",
            )

            index = astmod.analyze_repository(root, policy(), SCRIPT_DIR)

        prod = {item["qualified_name"]: item for item in index["production_symbols"]}
        tests = {item["qualified_name"]: item for item in index["test_symbols"]}
        self.assertIn("src.pkg.service.UserService", prod)
        self.assertIn("src.pkg.service.UserService.register", prod)
        self.assertIn("tests.test_service.test_register", tests)
        test = tests["tests.test_service.test_register"]
        self.assertEqual(1, test["assertion_count"])
        self.assertIn(
            "src.pkg.service.UserService.register",
            astmod.resolved_call_targets(test),
        )

    def test_colocated_test_pattern_is_not_counted_as_production(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "src").mkdir()
            (root / "src/service.py").write_text(
                "def run():\n    return True\n",
                encoding="utf-8",
            )
            (root / "src/service_test.py").write_text(
                "def test_run():\n    assert True\n",
                encoding="utf-8",
            )
            local_policy = policy()
            local_policy["source_analysis"]["test_roots"] = []
            local_policy["source_analysis"]["test_file_patterns"] = ["**/*_test.py"]
            index = astmod.analyze_repository(root, local_policy, SCRIPT_DIR)

        production_files = {item["file"] for item in index["production_symbols"]}
        test_files = {item["file"] for item in index["test_symbols"]}
        self.assertIn("src/service.py", production_files)
        self.assertNotIn("src/service_test.py", production_files)
        self.assertIn("src/service_test.py", test_files)

    def test_test_root_is_not_counted_as_production(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "src/test").mkdir(parents=True)
            (root / "src/test/test_only.py").write_text(
                "def test_only():\n    assert True\n",
                encoding="utf-8",
            )
            index = astmod.analyze_repository(root, policy(), SCRIPT_DIR)

        self.assertEqual([], index["production_symbols"])
        self.assertEqual(1, len(index["test_symbols"]))


class JavaAstTest(unittest.TestCase):
    @unittest.skipUnless(shutil.which("java"), "JDK is not available")
    def test_java_symbols_calls_and_assertions(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "src/main/java/com/example").mkdir(parents=True)
            (root / "src/test/java/com/example").mkdir(parents=True)
            (root / "src/main/java/com/example/UserService.java").write_text(
                "package com.example;\n"
                "public class UserService {\n"
                "  public int register(int x) { return helper(x); }\n"
                "  public int helper(int x) { return x + 1; }\n"
                "}\n",
                encoding="utf-8",
            )
            (root / "src/test/java/com/example/UserServiceTest.java").write_text(
                "package com.example;\n"
                "import static org.junit.jupiter.api.Assertions.assertEquals;\n"
                "public class UserServiceTest {\n"
                "  public void testRegister() {\n"
                "    UserService service = new UserService();\n"
                "    assertEquals(2, service.register(1));\n"
                "  }\n"
                "}\n",
                encoding="utf-8",
            )

            index = astmod.analyze_repository(root, policy(), SCRIPT_DIR)

        prod = {item["qualified_name"]: item for item in index["production_symbols"]}
        tests = {item["qualified_name"]: item for item in index["test_symbols"]}
        self.assertIn("com.example.UserService.register", prod)
        self.assertNotIn("com.example.UserServiceTest", prod)
        test = tests["com.example.UserServiceTest.testRegister"]
        self.assertEqual(1, test["assertion_count"])
        self.assertIn(
            "com.example.UserService.register",
            astmod.resolved_call_targets(test),
        )


class TypeScriptAstTest(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node.js is not available")
    def test_typescript_symbols_calls_and_assertions(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "src/ts").mkdir(parents=True)
            (root / "tests/ts").mkdir(parents=True)
            (root / "src/ts/user.ts").write_text(
                "export function helper(x: number): number { return x + 1; }\n"
                "export function registerUser(x: number): number { return helper(x); }\n",
                encoding="utf-8",
            )
            (root / "tests/ts/user.test.ts").write_text(
                "import { registerUser } from '../../src/ts/user';\n"
                "export function testRegisterUser() {\n"
                "  const result = registerUser(1);\n"
                "  expect(result).toBe(2);\n"
                "}\n",
                encoding="utf-8",
            )

            index = astmod.analyze_repository(root, policy(), SCRIPT_DIR)

        if index["analyzers"]["typescript"]["status"] != "AVAILABLE":
            self.skipTest(index["analyzers"]["typescript"].get("error", "TypeScript unavailable"))
        prod = {item["qualified_name"]: item for item in index["production_symbols"]}
        tests = {item["qualified_name"]: item for item in index["test_symbols"]}
        self.assertIn("src.ts.user.registerUser", prod)
        test = tests["tests.ts.user.test.testRegisterUser"]
        self.assertEqual(1, test["assertion_count"])
        self.assertIn("src.ts.user.registerUser", astmod.resolved_call_targets(test))


class MappingAnalysisTest(unittest.TestCase):
    def _python_index(self, root: Path) -> dict[str, Any]:
        (root / "src").mkdir(parents=True)
        (root / "tests").mkdir(parents=True)
        (root / "src/service.py").write_text(
            "def helper(x):\n    return x + 1\n\n"
            "def register(x):\n    return helper(x)\n\n"
            "def orphan():\n    return 99\n",
            encoding="utf-8",
        )
        (root / "tests/test_service.py").write_text(
            "from src.service import register\n\n"
            "def test_register():\n"
            "    result = register(1)\n"
            "    assert result == 2\n",
            encoding="utf-8",
        )
        return astmod.analyze_repository(root, policy(), SCRIPT_DIR)

    def test_orphan_symbol_detection(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            index = self._python_index(root)
            trace_map = {
                "entries": [
                    {
                        "requirement_reference": "FR-001",
                        "implementation": [
                            {
                                "file": "src/service.py",
                                "symbol": "register",
                                "qualified_name": "src.service.register",
                            },
                            {
                                "file": "src/service.py",
                                "symbol": "helper",
                                "qualified_name": "src.service.helper",
                            },
                        ],
                    }
                ]
            }
            orphans = astmod.orphan_production_symbols(trace_map, index, policy())

        self.assertEqual(["src.service.orphan"], [item["qualified_name"] for item in orphans])

    def test_file_only_mapping_covers_all_symbols_in_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            index = self._python_index(root)
            trace_map = {
                "entries": [
                    {
                        "requirement_reference": "FR-001",
                        "implementation": [{"file": "src/service.py"}],
                    }
                ]
            }
            orphans = astmod.orphan_production_symbols(trace_map, index, policy())

        self.assertEqual([], orphans)

    def test_production_call_graph_supports_transitive_reachability(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            index = self._python_index(root)
            graph = astmod.production_call_graph(index)
            reachable = astmod.reachable_targets({"src.service.register"}, graph, 5)

        self.assertIn("src.service.register", reachable)
        self.assertIn("src.service.helper", reachable)


if __name__ == "__main__":
    unittest.main(verbosity=2)
