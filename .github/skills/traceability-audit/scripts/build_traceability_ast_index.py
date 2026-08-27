#!/usr/bin/env python3
"""Build deterministic AST evidence for Traceability Auditor."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from traceability_ast import analyze_repository, write_index


def read_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as stream:
        data = yaml.safe_load(stream)
    if not isinstance(data, dict):
        raise ValueError(f"YAML root must be a mapping: {path}")
    return data


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Traceability AST index.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument(
        "--policy",
        default=".github/skills/traceability-audit/policy/traceability-policy.yaml",
    )
    parser.add_argument(
        "--output",
        default="reports/traceability/ast-index.json",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()

    def resolve(value: str) -> Path:
        path = Path(value)
        return path if path.is_absolute() else repo_root / path

    try:
        policy = read_yaml(resolve(args.policy))
        index = analyze_repository(repo_root, policy, Path(__file__).resolve().parent)
        output = resolve(args.output)
        write_index(output, index)
    except (OSError, ValueError, yaml.YAMLError) as error:
        print(f"[FAIL] {error}")
        return 1

    print("========================================")
    print(" Traceability AST Index")
    print("========================================")
    print(f"Fingerprint: {index['source_fingerprint']}")
    print(f"Production symbols: {len(index['production_symbols'])}")
    print(f"Test symbols: {len(index['test_symbols'])}")
    for language, status in index["analyzers"].items():
        print(f"{language}: {status.get('status')} ({status.get('files', 0)} files)")
    print(f"Output: {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
