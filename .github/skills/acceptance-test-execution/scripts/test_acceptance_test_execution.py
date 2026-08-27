#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

import yaml


SCRIPT_DIR = Path(__file__).resolve().parent


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(
        name,
        SCRIPT_DIR / filename,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = load_module(
    "run_acceptance_tests",
    "run_acceptance_tests.py",
)
result_validator = load_module(
    "validate_acceptance_results",
    "validate_acceptance_results.py",
)


def base_policy() -> dict[str, Any]:
    return {
        "isolation": {
            "require_sdlc_complete_before_execution": True,
            "require_evaluation_data_exposed_after_complete": True,
            "forbid_development_external_test_path": True,
            "forbidden_path_fragments": [
                "external-tests/integration-test"
            ],
        },
        "manifest": {
            "schema_version": 1,
            "require_unique_case_id": True,
            "supported_execution_types": ["COMMAND"],
            "required_case_fields": [
                "case_id",
                "requirement_id",
                "requirement_type",
                "execution_type",
                "command",
                "expected",
            ],
            "require_expected_exit_code": True,
        },
        "execution": {
            "default_timeout_seconds": 5,
            "maximum_timeout_seconds": 10,
            "shell": False,
            "continue_after_fail": True,
            "continue_after_blocked": True,
        },
        "evidence": {
            "save_stdout_text": False,
            "save_stderr_text": False,
        },
    }


def manifest(command: list[str]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "run_id": "RUN-001",
        "sdlc_completed_at": "2026-01-01T12:00:00+09:00",
        "evaluation_data_exposed_at": "2026-01-01T12:01:00+09:00",
        "cases": [
            {
                "case_id": "AC-001",
                "requirement_id": "FR-001",
                "requirement_type": "FUNCTIONAL",
                "execution_type": "COMMAND",
                "command": command,
                "expected": {"exit_code": 0},
            }
        ],
    }


class ManifestValidationTest(unittest.TestCase):

    def test_valid_manifest(self):
        data = manifest([sys.executable, "-c", "print('ok')"])
        errors = runner.validate_manifest(
            data,
            base_policy(),
            Path("/tmp/evaluation-input/acceptance-test-manifest.json"),
        )
        self.assertEqual([], errors)

    def test_hidden_data_before_complete_fails(self):
        data = manifest([sys.executable, "-c", "print('ok')"])
        data["evaluation_data_exposed_at"] = (
            "2026-01-01T11:59:00+09:00"
        )
        errors = runner.validate_manifest(
            data,
            base_policy(),
            Path("/tmp/evaluation-input/acceptance-test-manifest.json"),
        )
        self.assertTrue(
            any("before SDLC COMPLETE" in error for error in errors)
        )

    def test_external_test_path_fails(self):
        data = manifest([sys.executable, "-c", "print('ok')"])
        errors = runner.validate_manifest(
            data,
            base_policy(),
            Path(
                "/repo/external-tests/integration-test/"
                "acceptance-test-manifest.json"
            ),
        )
        self.assertTrue(
            any("development External Test path" in error for error in errors)
        )

    def test_duplicate_case_fails(self):
        data = manifest([sys.executable, "-c", "print('ok')"])
        data["cases"].append(dict(data["cases"][0]))
        errors = runner.validate_manifest(
            data,
            base_policy(),
            Path("/tmp/input/acceptance-test-manifest.json"),
        )
        self.assertTrue(
            any("Duplicate case_id" in error for error in errors)
        )

    def test_string_command_fails(self):
        data = manifest([sys.executable, "-c", "print('ok')"])
        data["cases"][0]["command"] = "python test.py"
        errors = runner.validate_manifest(
            data,
            base_policy(),
            Path("/tmp/input/acceptance-test-manifest.json"),
        )
        self.assertTrue(
            any("string array" in error for error in errors)
        )


class ExpectedComparisonTest(unittest.TestCase):

    def test_matching_exit_and_stdout_passes(self):
        matched, errors = runner.expected_matches(
            {
                "exit_code": 0,
                "stdout_contains": ["hello"],
                "stderr_not_contains": ["fatal"],
            },
            0,
            "hello world",
            "",
        )
        self.assertTrue(matched)
        self.assertEqual([], errors)

    def test_wrong_exit_fails(self):
        matched, errors = runner.expected_matches(
            {"exit_code": 0},
            1,
            "",
            "",
        )
        self.assertFalse(matched)
        self.assertTrue(any("exit_code" in error for error in errors))

    def test_not_contains_fails_when_present(self):
        matched, errors = runner.expected_matches(
            {
                "exit_code": 0,
                "stdout_not_contains": ["secret"],
            },
            0,
            "secret",
            "",
        )
        self.assertFalse(matched)


class ExecutionTest(unittest.TestCase):

    def test_pass_case(self):
        case = manifest(
            [sys.executable, "-c", "print('hello')"]
        )["cases"][0]
        case["expected"] = {
            "exit_code": 0,
            "stdout_contains": ["hello"],
        }

        row, evidence = runner.run_case(
            case,
            Path(".").resolve(),
            base_policy(),
        )

        self.assertEqual("PASS", row["result"])
        self.assertEqual("PASS", evidence["result"])
        self.assertNotIn("stdout", evidence)

    def test_fail_case_is_measurement_not_blocked(self):
        case = manifest(
            [sys.executable, "-c", "raise SystemExit(1)"]
        )["cases"][0]

        row, _ = runner.run_case(
            case,
            Path(".").resolve(),
            base_policy(),
        )

        self.assertEqual("FAIL", row["result"])
        self.assertEqual(1, row["exit_code"])

    def test_missing_command_is_blocked(self):
        case = manifest(
            ["definitely-not-an-existing-command-xyz"]
        )["cases"][0]

        row, _ = runner.run_case(
            case,
            Path(".").resolve(),
            base_policy(),
        )

        self.assertEqual("BLOCKED", row["result"])
        self.assertIn(
            "COMMAND_START_FAILED",
            row["blocked_reason"],
        )

    def test_timeout_is_blocked(self):
        policy = base_policy()
        policy["execution"]["default_timeout_seconds"] = 1
        case = manifest(
            [
                sys.executable,
                "-c",
                "import time; time.sleep(2)",
            ]
        )["cases"][0]
        case["timeout_seconds"] = 1

        row, _ = runner.run_case(
            case,
            Path(".").resolve(),
            policy,
        )

        self.assertEqual("BLOCKED", row["result"])
        self.assertEqual("TIMEOUT", row["blocked_reason"])


class ResultValidationTest(unittest.TestCase):

    def base_inputs(self):
        m = manifest([sys.executable, "-c", "print('ok')"])
        rows = [
            {
                "case_id": "AC-001",
                "requirement_id": "FR-001",
                "requirement_type": "FUNCTIONAL",
                "result": "PASS",
            }
        ]
        from acceptance_common import canonical_json_sha256
        evidence = {
            "manifest_sha256": canonical_json_sha256(m),
            "summary": {
                "total": 1,
                "passed": 1,
                "failed": 0,
                "blocked": 0,
            },
            "cases": [
                {
                    "case_id": "AC-001",
                    "result": "PASS",
                }
            ],
        }
        return m, rows, evidence

    def test_valid_results(self):
        m, rows, evidence = self.base_inputs()
        errors = result_validator.validate(
            m,
            rows,
            evidence,
        )
        self.assertEqual([], errors)

    def test_fail_result_is_valid_measurement(self):
        m, rows, evidence = self.base_inputs()
        rows[0]["result"] = "FAIL"
        evidence["cases"][0]["result"] = "FAIL"
        evidence["summary"] = {
            "total": 1,
            "passed": 0,
            "failed": 1,
            "blocked": 0,
        }

        errors = result_validator.validate(
            m,
            rows,
            evidence,
        )
        self.assertEqual([], errors)

    def test_missing_result_case_fails(self):
        m, _, evidence = self.base_inputs()
        errors = result_validator.validate(
            m,
            [],
            evidence,
        )
        self.assertTrue(
            any("missing Manifest cases" in error for error in errors)
        )

    def test_requirement_mismatch_fails(self):
        m, rows, evidence = self.base_inputs()
        rows[0]["requirement_id"] = "FR-999"

        errors = result_validator.validate(
            m,
            rows,
            evidence,
        )

        self.assertTrue(
            any("requirement_id" in error for error in errors)
        )

    def test_manifest_hash_mismatch_fails(self):
        m, rows, evidence = self.base_inputs()
        evidence["manifest_sha256"] = "bad"

        errors = result_validator.validate(
            m,
            rows,
            evidence,
        )

        self.assertTrue(
            any("manifest_sha256" in error for error in errors)
        )


class EndToEndTest(unittest.TestCase):

    def test_execute_mixed_pass_fail(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            input_dir = root / "evaluation-input"
            input_dir.mkdir()

            p = base_policy()
            policy_path = root / "policy.yaml"
            policy_path.write_text(
                yaml.safe_dump(p, sort_keys=False),
                encoding="utf-8",
            )

            data = manifest(
                [sys.executable, "-c", "print('pass')"]
            )
            fail_case = {
                "case_id": "AC-002",
                "requirement_id": "NFR-001",
                "requirement_type": "NON_FUNCTIONAL",
                "execution_type": "COMMAND",
                "command": [
                    sys.executable,
                    "-c",
                    "raise SystemExit(1)",
                ],
                "expected": {"exit_code": 0},
            }
            data["cases"].append(fail_case)

            manifest_path = (
                input_dir / "acceptance-test-manifest.json"
            )
            manifest_path.write_text(
                json.dumps(data),
                encoding="utf-8",
            )

            rows, evidence, errors = runner.execute(
                root,
                input_dir,
                manifest_path,
                policy_path,
            )

        self.assertEqual([], errors)
        self.assertEqual(
            ["PASS", "FAIL"],
            [row["result"] for row in rows],
        )
        self.assertEqual(2, evidence["summary"]["total"])
        self.assertEqual(1, evidence["summary"]["passed"])
        self.assertEqual(1, evidence["summary"]["failed"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
