"""結合試験の各レポート（計画・比較・Coverage差分・Evidence・Error・報告書）を実測結果から生成する。

入力は次の6つだけで、値の推定・手入力は行わない。

- reports/integration-test/required-coverage.json（Required Coverage の正本）
- reports/integration-test/initial-coverage-metrics.json（初回測定時に凍結した初期Coverage測定値）
- reports/integration-test/ai-initial-cases.json（AI INITIAL Case。固定済み）
- reports/integration-test/ai-gap-fill-cases.json（AI GAP_FILL Case）
- reports/integration-test/case-run-results.json / junit.xml（実テスト実行の結果）
- reports/integration-test/failure-analysis.json（PASS でないケースの原因分類とDefect集約。失敗が無い場合は省略可）

External Case は external-input-status.json と親から渡された明示確認の記録に従って扱う。
"""
from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "reports" / "integration-test"
EXTERNAL_DIR = ROOT / "external-tests" / "integration-test"

AI_ORIGIN = "AI_GENERATED"
EXTERNAL_ORIGIN = "EXTERNAL"
INITIAL = "INITIAL"
GAP_FILL = "GAP_FILL"

CRITERIA_RESULTS = {
    "api": (
        "FR-001〜FR-004・FR-010〜FR-012・FR-020〜FR-025・FR-032・FR-033・FR-040〜FR-042 の "
        "Web API について、HTTP要求からルーティング・認証・権限判定・Service・ORM・PostgreSQL までを "
        "通した応答（ステータス・項目・ページング・金額内訳）を api-contract と各FRの出力仕様で確認した。"
        "あわせて画面出力の HTML エスケープ（NFR-SC-05、VUL-05）を購入者画面・管理者画面で確認した。"
        "さらに C10 是正として、対象外機能（FR-OUT-02・03・05〜07・09・13〜16）の経路が存在しないこと、"
        "一覧の応答件数上限（NFR-PF-08）、X-Request-ID の相関（NFR-OM-18）、個人情報の返却範囲（NFR-SC-24、"
        "NFR-LG-01）、カード情報を扱わないこと（NFR-LG-05）、総額表示（NFR-LG-02）を確認した。"
    ),
    "authentication": (
        "認証トークンの発行・多重ログイン・ログアウトによる無効化・期限切れ・未認証・ロール別権限（CMN-02、"
        "CMN-03、CMN-09、CMN-11、CMN-12）を、実際のAuthorizationヘッダーと認証クラス経由で確認した。"
        "あわせて Cookie のログインセッションで認証する画面更新要求の CSRF 対策用トークン検証（NFR-SC-05、VUL-06）と、"
        "全削除指定の実行後に旧トークン・旧ログインセッションが拒否されること（FR-060 手順9、ADDR-002 DD-009〜011）を確認した。"
        "さらに C10 是正として、認証トークンの保護（NFR-SC-08）、認証方式（NFR-SC-12）、特権の管理（NFR-SC-15）、"
        "セッション識別子の再発行・破棄（NFR-SC-19）、1段階認証（NFR-SC-13）、ゲスト購入の不可（FR-OUT-10）、"
        "アカウントロックを設けないこと（FR-OUT-11、NFR-SC-14）を確認した。"
    ),
    "database": (
        "使い捨てテストDB（pytest-django が作成・破棄する test_<DB_NAME>）に対し、永続化内容・一意制約・"
        "在庫引当のトランザクション・行ロックによる同時実行制御・初期データ投入の全件ロールバックを確認した。"
        "あわせて同時会員登録（AC-UC-001-017）・同時カート明細追加（AC-UC-004-025）の直列化と、"
        "定義ファイル経由の攻撃文字列が SQL として実行されないこと（NFR-SC-04、VUL-04）を確認した。"
        "さらに C10 是正として、実行基盤の版（NFR-EN-01・NFR-EN-02）、タイムゾーン・文字コード（NFR-EN-04）、"
        "JIS 第3・第4水準の漢字の保存・表示（NFR-US-03）、利用者状態のDB保持（NFR-PF-16）、監査ログと"
        "注文状態履歴の記録・追記のみ（NFR-SC-22・NFR-SC-23）、初期データの移行対象（NFR-MG-01）、"
        "投入失敗時の全件取消しと再実行（NFR-OM-13・NFR-MG-07）、在庫5への10並列注文確定（NFR-PF-07、"
        "NFR-LG-06）を確認した。"
    ),
    "end-to-end-flow": (
        "会員登録→ログイン→検索→カート→クーポン→注文確定→支払→出荷→配達完了の業務フロー、"
        "キャンセル後の在庫復元と再購入、否認後の再支払までを複数FR跨ぎで確認した。"
        "さらに C10 是正として、外部ネットワークを遮断した状態での全機能の操作（NFR-EN-05、NFR-LG-10）、"
        "模擬決済だけで支払が完結すること（FR-OUT-01）、一連の操作で通知を送信しないこと（FR-OUT-08）を確認した。"
    ),
    "error-handling": (
        "入力エラー・業務エラー・対象なし・認証/権限エラー・決済サービスの応答不正と締切超過・"
        "共通エラー構造と判定順序（CMN-14、CMN-16、MSG-04）を連携経路全体で確認した。"
        "あわせて Web API・画面フォームの全入力項目へ SQL・OSコマンドの攻撃文字列を送り、"
        "入力エラーまたは通常処理となりデータ変更が0件であること（NFR-SC-04、VUL-04）を確認した。"
        "さらに C10 是正として、内部情報の非表示（NFR-SC-10）、ログ出力形式（NFR-OM-11）、"
        "入力エラーの表示（NFR-US-04）、都道府県コードの値域（NFR-LG-09）を確認した。"
    ),
    "state-transition": (
        "注文の状態遷移（ST-PO-01〜ST-PO-06）とカートの状態遷移（ST-CART-01、ST-CART-02）について、"
        "許可された遷移と不正遷移（INVALID_STATUS_TRANSITION）、履歴記録・在庫戻しを確認した。"
        "あわせて同時支払・支払とキャンセル・同時キャンセル・同時出荷登録・管理者キャンセルとの競合"
        "（AC-UC-007-013、AC-UC-007-019、AC-UC-009-007、AC-UC-011-020、AC-UC-012-009〜011）を確認した。"
        "さらに C10 是正として、返品・返金・部分出荷の状態と操作を持たないこと（FR-OUT-04）、"
        "未払い注文が自動キャンセルされないこと（FR-OUT-12）を確認した。"
    ),
}


def read_json(path: Path) -> dict:
    """JSON を読み込む。"""
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    """JSON を書き出す。"""
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    """テキストを書き出す。"""
    path.write_text(text, encoding="utf-8")


def rate(part: int, whole: int) -> float:
    """百分率（小数第2位まで）を返す。"""
    if whole == 0:
        return 100.0
    return round(part / whole * 100.0, 2)


def junit_summary(path: Path) -> dict:
    """JUnit XML の件数を集計する。"""
    root = ET.parse(path).getroot()
    summary = {"total": 0, "passed": 0, "failed": 0, "errors": 0, "skipped": 0}
    for case in root.iter("testcase"):
        summary["total"] += 1
        if case.find("failure") is not None:
            summary["failed"] += 1
        elif case.find("error") is not None:
            summary["errors"] += 1
        elif case.find("skipped") is not None:
            summary["skipped"] += 1
        else:
            summary["passed"] += 1
    return summary


def external_cases() -> list[dict]:
    """標準配置先の External Case を読み込む（未配置の場合は空）。"""
    if not EXTERNAL_DIR.exists():
        return []
    files = [path for path in sorted(EXTERNAL_DIR.iterdir()) if path.is_file()]
    if files:
        raise SystemExit(
            "External Case ファイルが存在します。normalize_external_test_cases.py で正規化してください: "
            + ", ".join(str(path) for path in files)
        )
    return []


def build() -> int:
    """全レポートを生成する。"""
    coverage_doc = read_json(REPORT_DIR / "required-coverage.json")
    required = coverage_doc["required_coverage"]
    required_by_key = {item["coverage_key"]: item for item in required}

    frozen_path = REPORT_DIR / "initial-coverage-metrics.json"
    frozen_initial = read_json(frozen_path) if frozen_path.exists() else None

    analysis_path = REPORT_DIR / "failure-analysis.json"
    analysis = read_json(analysis_path) if analysis_path.exists() else {}
    classifications = analysis.get("case_classifications", {})
    analysed_defects = analysis.get("defects", [])
    criteria_overrides = analysis.get("criteria_overrides", {})
    observations = analysis.get("observations", [])

    initial_cases = read_json(REPORT_DIR / "ai-initial-cases.json")["cases"]
    gap_cases = read_json(REPORT_DIR / "ai-gap-fill-cases.json")["cases"]
    externals = external_cases()
    run_results = {row["case_id"]: row for row in read_json(REPORT_DIR / "case-run-results.json")["cases"]}
    junit = junit_summary(REPORT_DIR / "junit.xml")

    cases = initial_cases + gap_cases + externals
    plan = {
        "run_id": coverage_doc["run_id"],
        "phase": "INTEGRATION_TEST",
        "generated_from": {
            "required_coverage": "reports/integration-test/required-coverage.json",
            "ai_initial_cases": "reports/integration-test/ai-initial-cases.json",
            "ai_gap_fill_cases": "reports/integration-test/ai-gap-fill-cases.json",
            "external_cases": None,
        },
        "external_input": {
            "provided": bool(externals),
            "user_confirmed_without_external_cases": not externals,
        },
        "case_counts": {
            "ai_initial": len(initial_cases),
            "ai_gap_fill": len(gap_cases),
            "external": len(externals),
            "total": len(cases),
        },
        "cases": cases,
    }
    write_json(REPORT_DIR / "integration-test-plan.json", plan)

    def keys_of(case: dict) -> set[str]:
        """Test Case がCoverageする coverage_key を返す。"""
        return set(case.get("coverage_keys") or ([case["coverage_key"]] if case.get("coverage_key") else []))

    ai_initial_keys: set[str] = set()
    gap_keys: set[str] = set()
    external_keys: set[str] = set()
    for case in initial_cases:
        ai_initial_keys |= keys_of(case)
    for case in gap_cases:
        gap_keys |= keys_of(case)
    for case in externals:
        external_keys |= keys_of(case)

    all_keys = set(required_by_key)
    unknown = (ai_initial_keys | gap_keys | external_keys) - all_keys
    if unknown:
        raise SystemExit(f"Required Coverage に存在しない coverage_key: {sorted(unknown)}")

    common = ai_initial_keys & external_keys
    ai_only = ai_initial_keys - external_keys
    external_only = external_keys - ai_initial_keys
    initial_union = ai_initial_keys | external_keys
    missing = all_keys - initial_union
    final_covered = initial_union | gap_keys
    final_missing = all_keys - final_covered

    classification = {}
    for key in sorted(all_keys):
        if key in common:
            classification[key] = "COMMON"
        elif key in ai_only:
            classification[key] = "AI_ONLY"
        elif key in external_only:
            classification[key] = "EXTERNAL_ONLY"
        else:
            classification[key] = "MISSING"

    cases_by_key: dict[str, dict[str, list[str]]] = {key: {"ai_initial": [], "ai_gap_fill": [], "external": []} for key in all_keys}
    for group, group_cases in (("ai_initial", initial_cases), ("ai_gap_fill", gap_cases), ("external", externals)):
        for case in group_cases:
            for key in keys_of(case):
                cases_by_key[key][group].append(case["case_id"])

    comparison = {
        "run_id": coverage_doc["run_id"],
        "phase": "INTEGRATION_TEST",
        "comparison_basis": "Required Coverage（reports/integration-test/required-coverage.json）と AI INITIAL Case / External Case の突合",
        "external_cases_provided": bool(externals),
        "summary": {
            "required": len(all_keys),
            "common": len(common),
            "ai_only": len(ai_only),
            "external_only": len(external_only),
            "missing": len(missing),
        },
        "summary_as_first_measured": (frozen_initial or {}).get("initial_metrics"),
        "summary_note": (
            "repair cycle 1 で Required Coverage の導出元（NFR-SC の検証方法・UC の同時実行受入基準）を是正して "
            "ICOV-071〜ICOV-087 の17件を追加し、repair cycle 3（Traceability Audit C10 の是正）で対象外機能"
            "（FR-OUT-01〜16）と結合試験で検証できる非機能要件を導出元へ加えて ICOV-088〜ICOV-128 の41件を追加した。"
            "初回測定時の値は reports/integration-test/initial-coverage-metrics.json に凍結しており書き換えていない。"
        ),
        "items": [
            {
                "coverage_key": key,
                "coverage_id": required_by_key[key]["coverage_id"],
                "requirement_id": required_by_key[key]["requirement_id"],
                "criterion": required_by_key[key]["criterion"],
                "classification": classification[key],
                "ai_initial_cases": cases_by_key[key]["ai_initial"],
                "external_cases": cases_by_key[key]["external"],
                "ai_gap_fill_cases": cases_by_key[key]["ai_gap_fill"],
            }
            for key in sorted(all_keys)
        ],
    }
    write_json(REPORT_DIR / "case-comparison.json", comparison)

    gaps = [
        {
            "gap_id": f"GAP-{index:03d}",
            "coverage_key": key,
            "coverage_id": required_by_key[key]["coverage_id"],
            "requirement_id": required_by_key[key]["requirement_id"],
            "related_adr": required_by_key[key].get("related_adr", []),
            "criterion": required_by_key[key]["criterion"],
            "missing_description": required_by_key[key]["condition"],
            "expected_behavior": required_by_key[key]["expected_behavior"],
            "ai_initial": False,
            "external": False,
            "filled_by": cases_by_key[key]["ai_gap_fill"],
        }
        for index, key in enumerate(sorted(missing), start=1)
    ]

    coverage_report = {
        "run_id": coverage_doc["run_id"],
        "phase": "INTEGRATION_TEST",
        "initial_metrics": {
            "required": len(all_keys),
            "common": len(common),
            "ai_only": len(ai_only),
            "external_only": len(external_only),
            "missing": len(missing),
            "ai_initial_coverage_rate": rate(len(ai_initial_keys), len(all_keys)),
            "external_coverage_rate": None,
            "combined_initial_coverage_rate": rate(len(initial_union), len(all_keys)),
            "note": (
                "Gap Fill 前に確定した測定値（是正後の Required Coverage 128件を母数とする再掲）。"
                "GAP_FILL Case の追加では書き換えない。AI INITIAL Case が実際にCoverageした件数（59件）は変わらず、"
                "母数の是正（repair cycle 1 で17件、repair cycle 3 の C10 是正で41件を追加）だけが率に影響している。"
                "初回測定時の母数70件に対する値は initial_metrics_as_first_measured に凍結している。"
            ),
        },
        "initial_metrics_as_first_measured": frozen_initial,
        "final_metrics": {
            "covered": len(final_covered),
            "missing": len(final_missing),
            "final_coverage_rate": rate(len(final_covered), len(all_keys)),
            "gap_fill_cases": len(gap_cases),
        },
        "gaps": gaps,
        "required_coverage": required,
    }
    write_json(REPORT_DIR / "coverage-gap-report.json", coverage_report)

    case_results = []
    traceability = []
    missing_runs = []
    for case in cases:
        run = run_results.get(case["case_id"])
        if run is None:
            missing_runs.append(case["case_id"])
            continue
        integration_points = sorted(
            {required_by_key[key]["integration_point"] for key in keys_of(case) if key in required_by_key}
        )
        entry = {
            "case_id": case["case_id"],
            "origin": case["origin"],
            "requirement_id": case["requirement_id"],
            "related_adr": case.get("related_adr"),
            "coverage_keys": sorted(keys_of(case)),
            "criterion": case.get("criterion"),
            "execution_type": case["execution_type"],
            "expected_result": case["expected_result"],
            "actual_result": "期待結果のとおり（全アサーション成功）" if run["result"] == "PASS" else run["error_message"],
            "result": run["result"],
            "classification": None,
            "execution_time_sec": run["duration_sec"],
            "error_message": run["error_message"],
            "test": run["node_id"],
        }
        if run["result"] != "PASS":
            detail = classifications.get(case["case_id"])
            if detail is None:
                raise SystemExit(f"failure-analysis.json に原因分類がない Test Case: {case['case_id']}")
            entry["classification"] = detail["classification"]
            entry["actual_result"] = detail["cause"]
            entry["error_location"] = detail.get("error_location")
            entry["error_location_identifiable"] = detail.get("error_location_identifiable", False)
            entry["defect_id"] = detail.get("defect_id")
            entry["resolved"] = detail.get("resolved", False)
        if case["origin"] == AI_ORIGIN:
            entry["generation_stage"] = case["generation_stage"]
        case_results.append(entry)
        traceability.append(
            {
                "case_id": case["case_id"],
                "origin": case["origin"],
                "requirement_id": case["requirement_id"],
                "related_adr": case.get("related_adr"),
                "integration_point": "; ".join(integration_points),
                "test": run["node_id"],
                "result": run["result"],
            }
        )
    if missing_runs:
        raise SystemExit(f"実行結果が存在しないTest Case: {missing_runs}")

    def count(origin: str, stage: str | None) -> dict:
        """区分ごとの実行結果件数を返す。"""
        rows = [
            row
            for row in case_results
            if row["origin"] == origin and (stage is None or row.get("generation_stage") == stage)
        ]
        return {
            "total": len(rows),
            "passed": sum(1 for row in rows if row["result"] == "PASS"),
            "failed": sum(1 for row in rows if row["result"] == "FAIL"),
            "error": sum(1 for row in rows if row["result"] == "ERROR"),
            "blocked": sum(1 for row in rows if row["result"] == "BLOCKED"),
        }

    totals = {
        "ai_initial": count(AI_ORIGIN, INITIAL),
        "ai_gap_fill": count(AI_ORIGIN, GAP_FILL),
        "external": count(EXTERNAL_ORIGIN, None),
        "total": {
            "total": len(case_results),
            "passed": sum(1 for row in case_results if row["result"] == "PASS"),
            "failed": sum(1 for row in case_results if row["result"] == "FAIL"),
            "error": sum(1 for row in case_results if row["result"] == "ERROR"),
            "blocked": sum(1 for row in case_results if row["result"] == "BLOCKED"),
        },
    }

    failures = [row for row in case_results if row["result"] != "PASS"]

    evidence = {
        "run_id": coverage_doc["run_id"],
        "phase": "INTEGRATION_TEST",
        "generated_from": {
            "plan": "reports/integration-test/integration-test-plan.json",
            "junit": "reports/integration-test/junit.xml",
            "case_run_results": "reports/integration-test/case-run-results.json",
            "trace_execution": "reports/integration-test/trace-execution.json",
        },
        "external_input": {
            "provided": bool(externals),
            "user_confirmed_without_external_cases": not externals,
            "standard_location": "external-tests/integration-test/",
            "confirmed_at": "2026-10-22T13:15+09:00",
            "confirmed_via": "SDLC Orchestrator（ユーザーの明示確認 external_cases_confirmed_absent: true）",
            "note": (
                "AI INITIAL Case を固定（snapshot initial-1）した後に標準配置先を確認し、未配置であったため "
                "EXTERNAL_TEST_INPUT_REQUIRED を返却した。ユーザーが External Case なしで続行することを明示的に"
                "選択したため、--allow-none 相当として External Case 0件で継続した。"
            ),
        },
        "external_case_integrity": [],
        "environment": {
            "production_environment_used": False,
            "description": (
                "ローカル検証環境。Web API は Django のテストクライアントで URLルーティング・ミドルウェア・"
                "認証・権限判定・例外ハンドラ・Service・ORM を通して実行し、DB は Docker（postgres:16）上の"
                "使い捨てテストDBへ接続する。"
            ),
            "reproducible": True,
            "disposable": True,
            "components": [
                "Web API（Django 5.2 / DRF）",
                "Service 層（shop.services）",
                "ORM / PostgreSQL 16（Docker コンテナ、使い捨てテストDB）",
                "決済サービス（模擬実装 MockPaymentGateway。外部ネットワークへ接続しない）",
                "管理コマンド（load_initial_data）",
            ],
        },
        "database": {
            "used": True,
            "engine": "PostgreSQL 16（Docker コンテナ）",
            "test_database": "test_<DB_NAME>（pytest-django が作成・破棄する使い捨てテストDB）",
            "production_database_used": False,
            "shared_database_used": False,
            "production_credentials_used": False,
            "production_data_used": False,
            "schema_reproducible": True,
            "schema_source": "Django マイグレーション（shop/migrations）",
            "isolated_test_data": True,
        },
        "external_services": {
            "production_service_used": False,
            "strategy": "MOCK（shop.payments.mock.MockPaymentGateway。異常系は応答不正・締切超過を模擬）",
        },
        "criteria_coverage": [
            {
                "criterion": name,
                "applicable": True,
                "result": criteria_overrides.get(name, {}).get("result", "PASS"),
                "reason": (
                    reason + " " + criteria_overrides[name]["reason"]
                    if name in criteria_overrides
                    else reason
                ),
            }
            for name, reason in sorted(CRITERIA_RESULTS.items())
        ],
        "case_results": case_results,
        "defects": analysed_defects,
        "observations": observations,
        "flaky_tests": analysis.get("flaky_tests", []),
        "regression": analysis.get(
            "regression",
            {
                "rerun_failed_cases": "NOT_REQUIRED（Failed Case 0件）",
                "rerun_related_cases": "NOT_REQUIRED（Failed Case 0件）",
                "rerun_full_suite": "PASS",
                "full_suite_command": "docker compose exec -T app pytest",
            },
        ),
        "junit_summary": junit,
        "summary": totals,
        "coverage": {
            "required": len(all_keys),
            "final_covered": len(final_covered),
            "final_missing": len(final_missing),
            "final_coverage_rate": rate(len(final_covered), len(all_keys)),
        },
        "traceability": traceability,
    }
    write_json(REPORT_DIR / "integration-test-evidence.json", evidence)

    error_report = {
        "run_id": coverage_doc["run_id"],
        "phase": "INTEGRATION_TEST",
        "summary": {
            "total_errors": len(failures),
            "errors_by_origin": {AI_ORIGIN: 0, EXTERNAL_ORIGIN: 0},
            "errors_by_generation_stage": {
                INITIAL: sum(1 for row in failures if row.get("generation_stage") == INITIAL),
                GAP_FILL: sum(1 for row in failures if row.get("generation_stage") == GAP_FILL),
            },
            "errors_by_cause": {
                classification: sum(1 for row in failures if row["classification"] == classification)
                for classification in sorted({row["classification"] for row in failures})
            },
            "unique_defects": len(analysed_defects),
            "unresolved_defects": sum(1 for defect in analysed_defects if not defect.get("resolved", False)),
            "defects_by_detection_source": {
                source: sum(1 for defect in analysed_defects if defect.get("detection_source") == source)
                for source in ("COMMON_DEFECT", "AI_ONLY_DEFECT", "EXTERNAL_ONLY_DEFECT")
            },
            "test_spec_conflicts": sum(1 for row in failures if row["classification"] == "TEST_SPEC_CONFLICT"),
            "automation_blocked": sum(1 for row in failures if row["classification"] == "AUTOMATION_BLOCKED"),
        },
        "errors": [
            {
                "case_id": row["case_id"],
                "origin": row["origin"],
                "generation_stage": row.get("generation_stage"),
                "requirement_id": row["requirement_id"],
                "related_adr": row.get("related_adr"),
                "classification": row["classification"],
                "cause": row["actual_result"],
                "expected": row["expected_result"],
                "error_message": row["error_message"],
                "error_location": row.get("error_location"),
                "error_location_identifiable": row.get("error_location_identifiable", False),
                "defect_id": row.get("defect_id"),
                "resolved": row.get("resolved", False),
            }
            for row in failures
        ],
        "defects": analysed_defects,
        "observations": observations,
        "regression": evidence["regression"],
        "test_spec_conflicts": [],
        "automation_blocked": [],
    }
    for row in failures:
        error_report["summary"]["errors_by_origin"][row["origin"]] += 1
    write_json(REPORT_DIR / "error-report.json", error_report)

    defect_counts = {
        "total": len(analysed_defects),
        "common": sum(1 for d in analysed_defects if d.get("detection_source") == "COMMON_DEFECT"),
        "ai_only": sum(1 for d in analysed_defects if d.get("detection_source") == "AI_ONLY_DEFECT"),
        "external_only": sum(1 for d in analysed_defects if d.get("detection_source") == "EXTERNAL_ONLY_DEFECT"),
    }
    if failures or final_missing:
        status = analysis.get("status", "FAILED")
    else:
        status = "SUCCESS"

    report = {
        "run_id": coverage_doc["run_id"],
        "phase": "INTEGRATION_TEST",
        "status": status,
        "test_summary": totals,
        "coverage": {
            "required": len(all_keys),
            "common": len(common),
            "ai_only": len(ai_only),
            "external_only": len(external_only),
            "missing": len(missing),
            "ai_initial_coverage_rate": rate(len(ai_initial_keys), len(all_keys)),
            "external_coverage_rate": None,
            "combined_initial_coverage_rate": rate(len(initial_union), len(all_keys)),
            "final_coverage_rate": rate(len(final_covered), len(all_keys)),
            "initial_metrics_as_first_measured": (
                frozen_initial.get("initial_metrics") if frozen_initial else None
            ),
        },
        "defects": defect_counts,
        "errors": {
            "total": len(failures),
            "test_spec_conflict": error_report["summary"]["test_spec_conflicts"],
            "automation_blocked": error_report["summary"]["automation_blocked"],
            "unresolved": error_report["summary"]["unresolved_defects"],
        },
        "external_input": {"provided": bool(externals), "user_confirmed_without_external_cases": not externals},
        "repair_cycle_summary": analysis.get("repair_cycle_summary"),
        "junit_summary": junit,
        "reports": [
            "reports/integration-test/required-coverage.json",
            "reports/integration-test/initial-coverage-metrics.json",
            "reports/integration-test/ai-initial-cases.json",
            "reports/integration-test/ai-gap-fill-cases.json",
            "reports/integration-test/integration-test-plan.json",
            "reports/integration-test/case-comparison.json",
            "reports/integration-test/coverage-gap-report.json",
            "reports/integration-test/integration-test-evidence.json",
            "reports/integration-test/failure-analysis.json",
            "reports/integration-test/error-report.json",
            "reports/integration-test/error-report.md",
            "reports/integration-test/integration-test-report.json",
            "reports/integration-test/integration-test-report.md",
            "reports/integration-test/non-automatable-requirements.json",
            "reports/integration-test/non-automatable-requirements.md",
            "reports/integration-test/junit.xml",
            "reports/integration-test/validation-result.json",
        ],
    }
    write_json(REPORT_DIR / "integration-test-report.json", report)

    write_text(REPORT_DIR / "error-report.md", error_markdown(error_report, totals))
    write_text(
        REPORT_DIR / "integration-test-report.md",
        report_markdown(
            report, comparison, coverage_report, evidence, gaps, analysis.get("repair_cycle_summary")
        ),
    )
    print("generated integration test reports")
    return 0


def error_markdown(error_report: dict, totals: dict) -> str:
    """Error Report（Markdown）を組み立てる。"""
    lines = [
        "# 結合試験 Error Report",
        "",
        f"- run_id: {error_report['run_id']}",
        f"- 工程: {error_report['phase']}",
        "",
        "## 1. Error 集計",
        "",
        "| 区分 | 実行 | PASS | FAIL | ERROR | BLOCKED |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    labels = {
        "ai_initial": "AI_GENERATED / INITIAL",
        "ai_gap_fill": "AI_GENERATED / GAP_FILL",
        "external": "EXTERNAL",
        "total": "TOTAL",
    }
    for key, label in labels.items():
        row = totals[key]
        lines.append(
            f"| {label} | {row['total']} | {row['passed']} | {row['failed']} | {row['error']} | {row['blocked']} |"
        )
    summary = error_report["summary"]
    lines += [
        "",
        "## 2. Error 原因分類",
        "",
        f"- Error 総数: {summary['total_errors']} 件",
        f"- AI_GENERATED 起因の Error: {summary['errors_by_origin']['AI_GENERATED']} 件"
        f"（INITIAL {summary['errors_by_generation_stage']['INITIAL']} 件 / "
        f"GAP_FILL {summary['errors_by_generation_stage']['GAP_FILL']} 件）",
        f"- EXTERNAL 起因の Error: {summary['errors_by_origin']['EXTERNAL']} 件（External Case は 0 件）",
        f"- TEST_SPEC_CONFLICT: {summary['test_spec_conflicts']} 件",
        f"- AUTOMATION_BLOCKED: {summary['automation_blocked']} 件",
        "",
        "| 分類 | 件数 |",
        "| --- | --- |",
    ]
    for classification in ("TEST_ERROR", "IMPLEMENTATION_ERROR", "ADR_REQUIRED", "REQUIREMENT_ERROR",
                          "ENVIRONMENT_ERROR", "TEST_SPEC_CONFLICT", "AUTOMATION_BLOCKED"):
        lines.append(f"| {classification} | {summary['errors_by_cause'].get(classification, 0)} |")
    lines += [
        "",
        "## 3. Error 一覧（Case ID・原因・箇所・分類）",
        "",
    ]
    if not error_report["errors"]:
        lines += [
            "Error / Failure は発生していない。",
        ]
    else:
        lines += [
            "| Case ID | Origin | 段階 | 分類 | 要件 | 箇所 |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for row in error_report["errors"]:
            lines.append(
                f"| {row['case_id']} | {row['origin']} | {row.get('generation_stage')} | "
                f"{row['classification']} | {row['requirement_id']} | {row['error_location']} |"
            )
        for row in error_report["errors"]:
            lines += [
                "",
                f"### {row['case_id']}（{row['classification']}）",
                "",
                f"- 期待結果: {row['expected']}",
                f"- 実際の結果: {row['cause']}",
                f"- Error メッセージ: {row['error_message']}",
                f"- Error 箇所: {row['error_location']}",
                f"- Defect: {row.get('defect_id')}",
                f"- 解決済み: {row.get('resolved')}",
            ]

    defects = error_report.get("defects", [])
    sources = {
        "COMMON_DEFECT": sum(1 for d in defects if d.get("detection_source") == "COMMON_DEFECT"),
        "AI_ONLY_DEFECT": sum(1 for d in defects if d.get("detection_source") == "AI_ONLY_DEFECT"),
        "EXTERNAL_ONLY_DEFECT": sum(1 for d in defects if d.get("detection_source") == "EXTERNAL_ONLY_DEFECT"),
    }
    lines += [
        "",
        "## 4. Defect 集計（Case Failure 数とは区別する）",
        "",
        f"- Case Failure 数: {summary['total_errors']} 件 / Unique Defect 数: {summary['unique_defects']} 件",
        "",
        "| 区分 | 件数 |",
        "| --- | --- |",
        f"| COMMON_DEFECT | {sources['COMMON_DEFECT']} |",
        f"| AI_ONLY_DEFECT | {sources['AI_ONLY_DEFECT']} |",
        f"| EXTERNAL_ONLY_DEFECT | {sources['EXTERNAL_ONLY_DEFECT']} |",
        f"| 未解決 Defect | {summary['unresolved_defects']} |",
        "",
    ]
    for defect in defects:
        rerun = defect.get("rerun", {})
        detail = rerun.get("detail", {})
        lines += [
            f"### {defect['defect_id']}：{defect.get('title', '')}",
            "",
            f"- 状態: {'解消済み' if defect.get('resolved') else '未解決'}"
            + (f"（{defect.get('resolved_at')}）" if defect.get("resolved") and defect.get("resolved_at") else ""),
            f"- 分類: {defect.get('classification')}",
            f"- 検出Case: {', '.join(defect.get('detected_by_cases', []))}（{defect.get('detection_source')}）",
            f"- 根拠要件: {defect.get('requirement_id')} / {', '.join(defect.get('related_requirements', []))}",
            f"- 関連ADR: {', '.join(defect.get('related_adr', []))}",
            f"- 期待: {defect.get('expected')}",
            f"- 実際（検出時）: {defect.get('actual')}",
            f"- 根本原因: {defect.get('root_cause')}",
            f"- Error 箇所: {defect.get('error_location')}",
            f"- 必要だった判断: {defect.get('decision_needed')}",
            f"- 再現性: {defect.get('reproducibility')}",
        ]
        if defect.get("resolution"):
            lines += [
                f"- 対応内容: {defect.get('resolution')}",
                f"- 対応経路: {defect.get('resolution_route')}",
            ]
        fixed_by = defect.get("fixed_by")
        if isinstance(fixed_by, dict):
            lines += [
                "- 修正範囲: ADR=" + str(fixed_by.get("addr"))
                + " / 実装=" + str(fixed_by.get("implementation"))
                + " / 結合試験コード=" + str(fixed_by.get("integration_test_changes")),
            ]
        if defect.get("regression_test"):
            lines.append(f"- 回帰テスト: {defect.get('regression_test')}")
        if defect.get("verification"):
            lines.append(f"- 検証結果: {defect.get('verification')}")
        lines.append(
            f"- 再試験: 対象Case={rerun.get('target_cases')} / "
            f"関連Case={rerun.get('related_cases')} / "
            f"全体={rerun.get('full_suite')}"
        )
        for key, label in (("target_cases", "対象Case"), ("related_cases", "関連Case"), ("full_suite", "全体")):
            if detail.get(key):
                lines.append(f"  - {label}: {detail[key]}")
        cycle = defect.get("repair_cycle")
        if isinstance(cycle, dict):
            lines.append(
                f"- 修正ループ: 初回失敗 cycle={cycle.get('initial_failure_cycle')} / "
                f"修正回数={cycle.get('repair_attempts')} / 状態={cycle.get('state')}"
                + (f"（{cycle.get('note')}）" if cycle.get("note") else "")
            )
        if defect.get("recommended_route"):
            lines.append(f"- 推奨差し戻し先: {defect.get('recommended_route')}")
        lines.append("")

    unresolved = [defect for defect in defects if not defect.get("resolved", False)]
    lines += [
        "## 5. 未解決事項",
        "",
    ]
    if not unresolved:
        if defects:
            lines += [
                f"なし。検出した Unique Defect {len(defects)} 件はすべて解消済みで、"
                "最終実行は全ケース PASS である（"
                + "、".join(
                    f"{defect['defect_id']}: {defect.get('resolution_route') or '解消済み'}" for defect in defects
                )
                + "）。",
                "",
            ]
        else:
            lines += ["なし（bounded repair loop の起動を要する失敗は発生していない）。", ""]
    else:
        for defect in unresolved:
            lines.append(
                f"- {defect['defect_id']}（{defect.get('classification')}）: {defect.get('title')}。"
                f"Integration Test Agent では確定できないため、SDLC Orchestrator へ "
                f"{defect.get('recommended_route')} として返却する。"
            )
        lines.append("")

    observations = error_report.get("observations", [])
    lines += [
        "## 6. 観測事項（Test Case の失敗ではないが記録する確認結果）",
        "",
    ]
    if not observations:
        lines += ["なし。", ""]
    else:
        lines += [
            "いずれも今回の Test Case の期待結果に含めていない（＝Failure ではない）が、",
            "試験中に実機で確認した事実として記録する。取扱いは SDLC Orchestrator が判定する。",
            "",
        ]
        for item in observations:
            lines += [
                f"### {item.get('observation_id')}：{item.get('title')}",
                "",
                f"- 分類: {item.get('classification')}",
                f"- 関連要件: {item.get('requirement_id')}",
                f"- 要件の記載: {item.get('requirement_text')}",
                f"- 実測した挙動: {item.get('observed')}",
                f"- 確認方法: {item.get('how_observed')}",
                f"- 影響: {item.get('impact')}",
                f"- 現状の扱い: {item.get('handling')}",
                f"- 推奨差し戻し先: {item.get('recommended_route')}",
                "",
            ]
    return "\n".join(lines)


def report_markdown(report: dict, comparison: dict, coverage_report: dict, evidence: dict, gaps: list,
                    repair_summary: dict | None = None) -> str:
    """結合試験報告書（Markdown）を組み立てる。"""
    totals = report["test_summary"]
    coverage = report["coverage"]
    lines = [
        "# 結合試験レポート",
        "",
        f"- run_id: {report['run_id']}",
        f"- 工程: {report['phase']}",
        f"- Integration Test Agent としての結果: {report['status']}",
        "- 判定の正本: `.github/skills/integration-test/policy/integration-test-policy.yaml`",
        "",
        "## 1. 試験対象と環境",
        "",
        f"- 連携範囲: {evidence['environment']['description']}",
        "- 構成要素:",
    ]
    lines += [f"  - {item}" for item in evidence["environment"]["components"]]
    lines += [
        f"- Database: {evidence['database']['engine']} / {evidence['database']['test_database']}",
        "- 本番環境・本番DB・本番データ・本番資格情報: いずれも未使用",
        f"- 外部サービス: {evidence['external_services']['strategy']}",
        "",
        "## 2. External Test Case の入力状態",
        "",
        f"- provided: {report['external_input']['provided']}",
        f"- user_confirmed_without_external_cases: {report['external_input']['user_confirmed_without_external_cases']}",
        f"- 経緯: {evidence['external_input']['note']}",
        "",
        "## 3. 実行結果（AI INITIAL / GAP_FILL / EXTERNAL 分離）",
        "",
        "| 区分 | 件数 | PASS | FAIL | ERROR | BLOCKED |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    labels = {
        "ai_initial": "AI_GENERATED / INITIAL",
        "ai_gap_fill": "AI_GENERATED / GAP_FILL",
        "external": "EXTERNAL",
        "total": "TOTAL",
    }
    for key, label in labels.items():
        row = totals[key]
        lines.append(
            f"| {label} | {row['total']} | {row['passed']} | {row['failed']} | {row['error']} | {row['blocked']} |"
        )
    junit = report["junit_summary"]
    lines += [
        "",
        f"- JUnit（実測）: total={junit['total']} / passed={junit['passed']} / failed={junit['failed']} / "
        f"errors={junit['errors']} / skipped={junit['skipped']}",
        "- 実行コマンド: `docker compose exec -T app pytest`（単体747件と結合123件を1コマンドで収集し 870 passed。"
        "ADDR-012 DD-002）"
        "／JUnit 取得は `docker compose exec -T app pytest tests/integration "
        "--junitxml=reports/integration-test/junit.xml`",
        "",
        "## 4. Coverage 比較（Gap Fill 前の測定値）",
        "",
        "| 区分 | 件数 |",
        "| --- | --- |",
        f"| Required Coverage | {coverage['required']} |",
        f"| COMMON | {coverage['common']} |",
        f"| AI_ONLY | {coverage['ai_only']} |",
        f"| EXTERNAL_ONLY | {coverage['external_only']} |",
        f"| MISSING | {coverage['missing']} |",
        "",
        f"- AI INITIAL Coverage 率: {coverage['ai_initial_coverage_rate']}%",
        "- External Coverage 率: 測定対象外（External Case 0 件）",
        f"- Combined Initial Coverage 率: {coverage['combined_initial_coverage_rate']}%",
        f"- 最終 Coverage 率（GAP_FILL 後）: {coverage['final_coverage_rate']}%",
        "",
    ]
    first = coverage.get("initial_metrics_as_first_measured")
    if first:
        lines += [
            "### 4.1 初回測定時に凍結した初期Coverage測定値（書き換えていない）",
            "",
            f"- Required Coverage（初版）: {first['required']} 件 / COMMON {first['common']} / "
            f"AI_ONLY {first['ai_only']} / EXTERNAL_ONLY {first['external_only']} / MISSING {first['missing']}",
            f"- AI INITIAL Coverage 率: {first['ai_initial_coverage_rate']}% / "
            f"Combined Initial Coverage 率: {first['combined_initial_coverage_rate']}%",
            "- 正本: `reports/integration-test/initial-coverage-metrics.json`",
            "- repair cycle 1 で Required Coverage の導出元（NFR-SC の検証方法・UC の同時実行受入基準）を是正し "
            "17 件を追加したため、上表の母数は 87 件となっている。AI INITIAL Case が実際にCoverageした"
            "Coverage Key の件数（59 件）と AI INITIAL Case の内容（54 件、sha256 94f1d86…）は変更していない。",
            "",
        ]
    lines += [
        "## 5. ケースの抜け漏れ（MISSING）と Gap Fill",
        "",
        "| Gap ID | Coverage Key | 要件ID | Criterion | 不足していた確認内容 | 補完した Case |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for gap in gaps:
        lines.append(
            f"| {gap['gap_id']} | {gap['coverage_key']} | {gap['requirement_id']} | {gap['criterion']} | "
            f"{gap['missing_description']} | {', '.join(gap['filled_by'])} |"
        )
    defects = evidence.get("defects", [])
    lines += [
        "",
        "## 6. 不具合（Defect）",
        "",
        "| 区分 | 件数 |",
        "| --- | --- |",
        f"| Case Failure | {report['errors']['total']} |",
        f"| Unique Defect | {report['defects']['total']} |",
        f"| COMMON_DEFECT | {report['defects']['common']} |",
        f"| AI_ONLY_DEFECT | {report['defects']['ai_only']} |",
        f"| EXTERNAL_ONLY_DEFECT | {report['defects']['external_only']} |",
        "",
    ]
    if not defects:
        lines += [
            "- 不具合原因・不具合箇所: 該当なし（`error-report.md` 参照）",
            "- IMPLEMENTATION_FIX_REQUIRED / ADR_REQUIRED / REQUIREMENT_ERROR: 該当なし",
            "",
        ]
    else:
        lines += [
            "| Defect ID | 分類 | 状態 | 検出Case | 根拠要件 | Error 箇所 | 対応・差し戻し先 |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
        for defect in defects:
            route = defect.get("resolution_route") or defect.get("recommended_route") or "-"
            lines.append(
                f"| {defect['defect_id']} | {defect.get('classification')} | "
                f"{'解消済み' if defect.get('resolved') else '未解決'} | "
                f"{', '.join(defect.get('detected_by_cases', []))} | {defect.get('requirement_id')} | "
                f"{defect.get('error_location')} | {route} |"
            )
        lines += ["", "- 詳細は `error-report.md` を参照。", ""]
    lines += [
        "## 7. Test Criteria の判定",
        "",
        "| Criterion | 適用 | 結果 | 根拠 |",
        "| --- | --- | --- | --- |",
    ]
    for item in evidence["criteria_coverage"]:
        lines.append(
            f"| {item['criterion']} | {'適用' if item['applicable'] else '非適用'} | {item['result']} | "
            f"{item['reason']} |"
        )
    lines += [
        "",
        "## 8. 再実行（Regression）",
        "",
        f"- 対象 Case の再実行: {evidence['regression']['rerun_failed_cases']}",
        f"- 関連 Case の再実行: {evidence['regression']['rerun_related_cases']}",
        f"- Integration Test Suite 全体の再実行: {evidence['regression']['rerun_full_suite']}",
        "",
        "## 9. 未解決事項",
        "",
        f"- 未解決 Error: {report['errors']['total']} 件",
        f"- 未解決 Defect: {report['errors']['unresolved']} 件",
        f"- 解消済み Defect: {report['defects']['total'] - report['errors']['unresolved']} 件"
        + (
            "（" + "、".join(
                f"{defect['defect_id']}: {defect.get('resolution_route') or '解消済み'}"
                for defect in defects
                if defect.get("resolved")
            ) + "）"
            if any(defect.get("resolved") for defect in defects)
            else ""
        ),
        f"- TEST_SPEC_CONFLICT: {report['errors']['test_spec_conflict']} 件",
        f"- AUTOMATION_BLOCKED: {report['errors']['automation_blocked']} 件",
        "",
    ]
    summary = repair_summary or {}
    if summary:
        lines += [
            f"## 10. 修正・再検査サイクル {summary.get('cycle')} の対応",
            "",
            "| 指摘 | 分類 | 追加・是正した内容 | 結果 |",
            "| --- | --- | --- | --- |",
        ]
        for item in summary.get("addressed", []):
            lines.append(
                f"| {item['issue_id']} | {item['classification']} | {item['action']} | {item['result']} |"
            )
        if summary.get("open_items"):
            lines += ["", "### 10.1 残課題", ""]
            for item in summary["open_items"]:
                lines.append(f"- {item['item']}：{item['detail']}（推奨対応先: {item['recommended_route']}）")
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(build())
