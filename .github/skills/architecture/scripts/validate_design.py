#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "addr/scripts"))
from design_common import validate_design, validate_gate, validate_design_gate, write_design_gate


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate design artifacts and implementation task dependencies")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--stage", choices=["draft", "final"], default="final")
    parser.add_argument("--check-gate", action="store_true")
    parser.add_argument("--write-design-gate", action="store_true")
    parser.add_argument("--check-design-gate", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    errors = write_design_gate(root) if args.write_design_gate else validate_design_gate(root) if args.check_design_gate else validate_gate(root) if args.check_gate else validate_design(root, args.stage)
    for error in errors:
        print(f"- {error}")
    print("[FAIL] Design validation" if errors else "[PASS] Design validation")
    return int(bool(errors))


if __name__ == "__main__":
    sys.exit(main())
