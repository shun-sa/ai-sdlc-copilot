"""failure-analysis.json を C10 是正サイクルの実測結果で更新する。

既存の DEF-IT-001（解消済み）と case_classifications は変更しない。
今回のサイクルで追加した Test Case の実行結果・再実行の実測値と、
試験中に実機で確認した観測事項（Test Case の失敗ではないもの）を追記する。
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "reports" / "integration-test" / "failure-analysis.json"

REGRESSION = {
    "rerun_failed_cases": "NOT_REQUIRED（今回のサイクルで Failed / Error Case は0件）",
    "rerun_related_cases": "PASS（既存82ケースを含む結合試験全ケースを再実行）",
    "rerun_full_suite": "PASS（単体747件＋結合123件＝870 passed / 0 failed）",
    "full_suite_command": "docker compose exec -T app pytest",
    "integration_suite_command": "docker compose exec -T app pytest tests/integration --junitxml=reports/integration-test/junit.xml",
    "executed_at": "2026-10-22T17:50+09:00",
    "detail": {
        "previous_cases": "既存の82ケース（IT-AI-001〜054、IT-AI-GF-001〜028）を再実行し全件 PASS",
        "added_cases": "C10 是正で追加した41ケース（IT-AI-GF-029〜069）を実行し全件 PASS",
        "integration_only": "docker compose exec -T app pytest tests/integration：123 passed / 0 failed（84.50s）",
    },
}

C10_ENTRY = {
    "issue_id": "TA-C10-001",
    "classification": "TEST_TRACEABILITY_MISSING",
    "action": (
        "Traceability Audit（FULL Scope）の C10 で不合格となった 124 件の要件について、要件本文を正本として "
        "「自動テストで正当に検証できるもの」と「検証方法が自動テストではないもの」を分類した。"
        "検証できる 41 観点（対象外機能 FR-OUT-01〜16 が実装されていないことの確認、および設定値・形式・件数・"
        "記録・同時実行整合に関する非機能要件）を Required Coverage へ追加（ICOV-088〜ICOV-128）し、"
        "AI GAP_FILL Case IT-AI-GF-029〜069 として tests/integration/test_out_of_scope.py・"
        "test_security_contract.py・test_platform_contract.py・test_concurrency.py に実装した。"
        "自動テストで検証できない要件は reports/integration-test/non-automatable-requirements.json / .md へ "
        "要件IDごとの検証方法・対象外理由とともに記録した。AI INITIAL Case 54件と初回測定値は変更していない。"
    ),
    "cases": [f"IT-AI-GF-{number:03d}" for number in range(29, 70)],
    "result": "41ケースすべて初回 PASS。結合試験 123ケース全件 PASS（単体747件と合わせて 870 passed / 0 failed）",
}

OBSERVATIONS = [
    {
        "observation_id": "OBS-IT-001",
        "title": "全角数字の都道府県コード・郵便番号が入力エラーにならず保存される",
        "classification": "POSSIBLE_IMPLEMENTATION_ERROR（本サイクルの Test Case では判定していない）",
        "requirement_id": "FR-030, NFR-SC-04",
        "requirement_text": (
            "機能要件定義書 FR-030 の入力条件は、都道府県コードを「2桁の半角数字で \"01\" 以上 \"47\" 以下」、"
            "郵便番号を「半角数字7桁」または「半角数字3桁・ハイフン・半角数字4桁」と定める。"
        ),
        "observed": (
            "prefecture_code=\"１３\"、postal_code=\"１２３４５６７\"（いずれも全角数字）を含む注文確定が 201 で受理され、"
            "配送先に全角数字のまま保存された（ShippingAddress.prefecture_code='１３'、postal_code='１２３４５６７'）。"
            "原因は、都道府県コードの判定が str.isdigit()＋int() で全角数字を数字として扱うこと、"
            "郵便番号・電話番号・日付の正規表現が \\d（Unicode 数字）で半角に限定していないこと。"
        ),
        "how_observed": (
            "C10 是正の作業中に、NFR-LG-09（JIS X 0401）のケース設計のため一時的な確認用テストで実測した"
            "（確認後に削除済み。コミットした Test Case には含めていない）。"
        ),
        "impact": (
            "注文の配送先に半角・全角が混在して保存されうる。出荷は手作業で行うため直ちに業務が停止する種類の"
            "問題ではないが、検索・集計・外部帳票との突合で不一致が生じうる。NFR-SC-04（型・桁数・値域・形式の"
            "サーバー側検証）の観点でも不足である。"
        ),
        "handling": (
            "本サイクルの差し戻し範囲（C10 のテスト追加）の外であり、Integration Test Agent は Production Code を"
            "変更できないため、期待結果に含めず観測事項として記録した。Test Case 化すると現状の実装では FAIL と"
            "なるため、是正方針の決定後にケースを追加する。"
        ),
        "recommended_route": "IMPLEMENTATION（半角限定の検証へ是正）。要件の意図の確認が必要な場合は REQUIREMENTS",
    }
]

OPEN_ITEM = {
    "item": "OBS-IT-001（全角数字の都道府県コード・郵便番号が受理される）の扱いが未決",
    "detail": (
        "FR-030 の入力条件は半角数字を定めるが、実機では全角数字が受理され保存される。Integration Test Agent は"
        "Production Code を変更できず、また本サイクルの差し戻し範囲外であるため、Test Case の期待結果には"
        "含めていない（したがって Failure としては計上していない）。SDLC Orchestrator が是正の要否を判定し、"
        "是正する場合は Implementation 工程での修正後に結合試験ケースを追加して再実行する必要がある。"
    ),
    "recommended_route": "IMPLEMENTATION",
}


def main() -> int:
    """failure-analysis.json を更新する。"""
    document = json.loads(PATH.read_text(encoding="utf-8"))
    document["repair_cycle"] = 3
    document["analyzed_at"] = "2026-10-22T17:50:00+09:00"
    document["note"] = (
        "実行結果が PASS でなかった Test Case の原因分類と Defect 集約。期待結果は要件・UCの受入基準・"
        "Accepted ADR から導出しており、Production Code に合わせて期待結果を変更していない。"
        "repair cycle 3（Traceability Audit C10 の是正）では Failed / Error Case は発生していない。"
    )
    document["regression"] = REGRESSION
    document["observations"] = OBSERVATIONS

    summary = document.setdefault("repair_cycle_summary", {})
    summary["cycle"] = 3
    addressed = summary.setdefault("addressed", [])
    if all(entry.get("issue_id") != C10_ENTRY["issue_id"] for entry in addressed):
        addressed.append(C10_ENTRY)
    open_items = summary.setdefault("open_items", [])
    if all(item.get("item") != OPEN_ITEM["item"] for item in open_items):
        open_items.append(OPEN_ITEM)

    PATH.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("failure-analysis.json を更新した")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
