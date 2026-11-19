"""Step 5〜7：Required Coverage と AI INITIAL Case を JSON に書き出して固定する（外部ケースの確認前に実行）。

python reports/integration-test/tools/build_initial.py
"""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from definitions_initial import build_cases  # noqa: E402
from required_coverage import KEY_BY_ID, REQUIRED_COVERAGE  # noqa: E402

OUT = HERE.parent
RUN_ID = "RUN-AOBA-EC-1118"


def write(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    now = datetime.now(UTC).isoformat(timespec="seconds")
    if (OUT / "ai-initial-cases.json").exists():
        raise SystemExit("ai-initial-cases.json は固定済み。INITIAL は再生成しない（Skill Step 7）。")
    write(
        OUT / "required-coverage.json",
        {
            "run_id": RUN_ID,
            "generated_at": now,
            "source": "docs/requirements（FR・CMN・UC の AC・NFR）、docs/addr ADDR-001〜014（ACTIVE）、Steering",
            "derived_from_cases": False,
            "required_coverage": REQUIRED_COVERAGE,
        },
    )
    cases = build_cases(KEY_BY_ID)
    write(
        OUT / "ai-initial-cases.json",
        {
            "run_id": RUN_ID,
            "generated_at": now,
            "frozen": True,
            "external_cases_seen_before_generation": False,
            "origin": "AI_GENERATED",
            "generation_stage": "INITIAL",
            "case_count": len(cases),
            "cases": cases,
        },
    )
    print(f"required_coverage={len(REQUIRED_COVERAGE)} ai_initial={len(cases)}")


if __name__ == "__main__":
    main()
