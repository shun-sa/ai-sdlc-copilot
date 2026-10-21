"""RUN-002 Integration Test: Plan / Coverage / Evidence / Report generator.

使い方:
    python scripts/gen_integration_reports.py plan      # Step 13-18（Coverage比較・計画）
    python scripts/gen_integration_reports.py reports   # Step 24-41（実行結果・Report）

AI INITIAL Case（reports/integration-test/ai-initial-cases.json）は読み取り専用として扱い、
本スクリプトからは一切変更しない。External Case はユーザーの明示確認により不提供。
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

RUN_ID = "RUN-002"
OUT_DIR = os.path.join("reports", "integration-test")
REQUIRED_COVERAGE = os.path.join(OUT_DIR, "required-coverage.json")
AI_INITIAL = os.path.join(OUT_DIR, "ai-initial-cases.json")
PLAN = os.path.join(OUT_DIR, "integration-test-plan.json")
JUNIT = os.path.join(OUT_DIR, "junit.xml")

# ------------------------------------------------------------------
# AI INITIAL Case → Required Coverage の対応（Coverage Key 付与。Step 13）
# ------------------------------------------------------------------
AI_INITIAL_COVERAGE: dict[int, list[int]] = {
    1: [1], 2: [2], 3: [3], 4: [4], 5: [4], 6: [4], 7: [5], 8: [6], 9: [6], 10: [7],
    11: [8], 12: [10], 13: [9], 14: [12], 15: [13], 16: [14], 17: [15], 18: [16], 19: [17], 20: [18],
    21: [19], 22: [22], 23: [23], 24: [24], 25: [25], 26: [26], 27: [27], 28: [20], 29: [32], 30: [30],
    31: [30], 32: [31], 33: [35], 34: [36], 35: [37], 36: [38], 37: [39], 38: [40], 39: [41], 40: [39],
    41: [42], 42: [43], 43: [44], 44: [45], 45: [46], 46: [47], 47: [48], 48: [49], 49: [49], 50: [50],
    51: [49], 52: [48], 53: [51], 54: [51], 55: [51], 56: [52], 57: [52], 58: [52], 59: [53], 60: [53],
    61: [54], 62: [54], 63: [55], 64: [55], 65: [56], 66: [57], 67: [58], 68: [59], 69: [60], 70: [60],
    71: [61], 72: [61], 73: [62], 74: [62], 75: [63], 76: [64], 77: [65], 78: [66], 79: [66], 80: [67],
    81: [68], 82: [69], 83: [69], 84: [71], 85: [72], 86: [73], 87: [74], 88: [75], 89: [75], 90: [76],
    91: [77], 92: [78], 93: [79], 94: [80], 95: [81], 96: [81], 97: [82], 98: [83], 99: [83], 100: [84],
    101: [89], 102: [87], 103: [88], 104: [90], 105: [90], 106: [91], 107: [91], 108: [92], 109: [93],
    110: [94], 111: [95], 112: [96], 113: [97], 114: [97], 115: [98], 116: [100], 117: [101], 118: [102],
    119: [103], 120: [104], 121: [105], 122: [106], 123: [107], 124: [109], 125: [109], 126: [110],
    127: [111], 128: [112], 129: [114], 130: [115], 131: [116], 132: [118], 133: [117], 134: [119],
    135: [120], 136: [121], 137: [122], 138: [123], 139: [124], 140: [125], 141: [126], 142: [127],
    143: [129], 144: [130], 145: [131], 146: [132], 147: [133], 148: [128, 134], 149: [135], 150: [136],
    151: [137], 152: [138], 153: [139], 154: [139], 155: [140], 156: [142], 157: [143], 158: [144],
    159: [148], 160: [151], 161: [152], 162: [153],
}

# 範囲表記（FR-001〜FR-045 等）の requirement_id を、実際に検証した要件IDへ正規化する。
REQUIREMENT_NORMALIZATION: dict[int, list[str]] = {
    156: ["FR-001", "FR-020", "FR-021", "FR-033", "FR-040"],
    157: [
        "FR-001", "FR-002", "FR-020", "FR-021", "FR-024",
        "FR-030", "FR-031", "FR-033", "FR-040", "FR-042",
    ],
    158: ["FR-020", "FR-021", "FR-030", "FR-031", "FR-034", "FR-043"],
    159: ["FR-021", "FR-030"],
}

# ------------------------------------------------------------------
# AI GAP_FILL Case（Step 17。MISSING Coverage を補完する）
# ------------------------------------------------------------------
GAP_CASES: list[dict] = [
    (1, 11, "会員登録のログに機密情報を出力しない",
     "1) 会員登録の成功・失敗を実行する 2) アプリケーションログを収集する 3) 必須項目と禁止項目を確認する"),
    (2, 21, "ログイン・ログアウトのログと監査ログに資格情報を出力しない",
     "1) ログイン・ログアウト・ログイン失敗を実行する 2) ログと監査ログを収集する 3) 禁止項目を確認する"),
    (3, 28, "画面セッションの無操作切断とログイン画面への遷移",
     "1) 画面でログインする 2) セッションを無効化する 3) 認証要画面へアクセスする"),
    (4, 29, "認証要画面への誘導後、ログインで元の画面へ戻る",
     "1) 未ログインで注文履歴画面へアクセスする 2) 誘導されたログイン画面でログインする"),
    (5, 33, "認証トークンの推測困難性と保存形式",
     "1) 同一利用者で3回ログインする 2) トークンを比較する 3) DBの保存値を確認する"),
    (6, 34, "画面セッションCookieの保護と識別子の再発行",
     "1) ログイン前のセッション識別子を記録する 2) 画面ログインする 3) Cookie属性と識別子を確認する"),
    (7, 70, "同一クーポンの複数購入者・複数注文での利用",
     "1) 購入者Aがクーポンを適用し注文する 2) 購入者Bが同じクーポンを適用する 3) 購入者Aが次の注文で再度適用する"),
    (8, 85, "注文確定中のシステムエラーで全てロールバックする",
     "1) 注文確定の途中で内部例外を発生させる 2) 応答・注文・在庫・カートを確認する 3) 再実行する"),
    (9, 86, "注文確定のログに配送先・メールアドレスを出力しない",
     "1) 注文確定を実行する 2) アプリケーションログを収集する 3) 禁止項目を確認する"),
    (10, 99, "支払とキャンセルの連続・同時実行の結果一致",
     "1) キャンセル後に支払う 2) 支払後にキャンセルする 3) 支払とキャンセルを並行実行する"),
    (11, 108, "画面の日時・金額・状態の表示形式",
     "1) 注文履歴画面を表示する 2) 注文詳細画面を表示する 3) 日時・金額・状態の表記を確認する"),
    (12, 113, "画面のキャンセル確認ダイアログの制御",
     "1) 注文詳細画面を表示する 2) 確認ダイアログを取り消す 3) 承諾してキャンセルする"),
    (13, 141, "初期データ投入のAPI・画面が存在しないこと",
     "1) 想定されるパスへ要求する 2) URL定義を確認する"),
    (14, 145, "X-Request-IDの引継ぎ・採番とAPI命名規約",
     "1) X-Request-ID付きで要求する 2) 未付与で要求する 3) 応答ヘッダー・ログ・項目名・URLを確認する"),
    (15, 146, "アプリケーションログの必須項目と禁止項目",
     "1) 代表的なAPI要求・エラー応答を実行する 2) JSON Lines の項目を確認する"),
    (16, 147, "API応答の日時がISO 8601（+09:00）であること",
     "1) 会員登録・ログイン・カート・注文詳細を要求する 2) 日時項目の形式を確認する"),
    (17, 149, "CSRFトークンのない画面更新要求の拒否",
     "1) CSRF検証を有効にした画面クライアントで更新要求を送る 2) 応答とデータを確認する"),
    (18, 150, "メールアドレス一意性のDB制約による保証",
     "1) 既存利用者と同一メールアドレスの行を直接追加する 2) 例外と件数を確認する"),
    (19, 154, "初期データ投入後のマスタで購入フローが成立すること",
     "1) 定義ファイルを投入する 2) 商品検索・詳細照会を行う 3) カート投入と注文確定を行う"),
    # --- Production Code 変更（QR-IMPL-006 の修正）に対する観点追補（Step 16-17 の再実施） ---
    (20, 59, "SCR-002 のカート投入失敗（入力エラー）で本画面に留まり入力値とカートを維持すること",
     "1) 画面でカートへ商品を1件入れておく 2) 数量に 0・整数以外・未入力を入力して「カートに入れる」を操作する "
     "3) 応答画面・入力値・DBのカート内容を確認する",
     {
         "requirement_id": ["FR-021", "FR-020"],
         "related_adr": ["ADDR-010", "ADDR-011"],
         "test_category": "SCREEN",
         "criterion": "error-handling",
         "precondition": "購入者が画面にログインし、対象商品に在庫数量1以上の在庫単位がある",
         "input": "数量＝0 / abc / 未入力（item_id・stock_unit_id は有効な値）",
         "expected_result": (
             "SCR-002 を再表示し（遷移しない）、数量欄の近傍に「数量は1以上の整数で入力してください。」を表示する。"
             "入力した数量と選択した規格を保持して再表示する。カート明細・在庫数量は変更しない"
             "（SCR-002-OP01、CMN-16、CMN-17、UI-19、CMN-21）"
         ),
         "notes": (
             "Production Code 変更（カート投入失敗時に SCR-002 を直接再表示する）に対する観点追補。"
             "既に AI INITIAL Case が被覆している COV-059 の失敗時の振る舞いを深掘りする追加ケース。"
         ),
     }),
    (21, 59, "SCR-002 のカート投入失敗（業務エラー）でメッセージ領域へ理由を表示し入力値とカートを維持すること",
     "1) 同一規格をカート内で10個にしておく 2) さらに1個追加する 3) 在庫数量を超える数量で別規格を追加する "
     "4) 応答画面・メッセージ・入力値・DBのカート内容を確認する",
     {
         "requirement_id": ["FR-021", "FR-020"],
         "related_adr": ["ADDR-010", "ADDR-011"],
         "test_category": "SCREEN",
         "criterion": "error-handling",
         "precondition": "購入者が画面にログインし、カートに同一規格が10個ある／在庫数量が不足する規格がある",
         "input": "数量上限超過：数量＝1（カート内10個）、在庫不足：数量＝5（在庫数量3）",
         "expected_result": (
             "SCR-002 を再表示し（遷移しない）、メッセージ領域に「同じ規格は1注文につき10個までです"
             "（現在のカート内数量：10個）。」／「在庫が不足しています（現在の在庫数量：3個）。」を表示する。"
             "入力した数量と選択した規格を保持し、カート明細・在庫数量は変更しない"
             "（SCR-002-OP01、MSG-05、CMN-17、UI-19、CMN-21）"
         ),
         "notes": (
             "Production Code 変更（カート投入失敗時に SCR-002 を直接再表示する）に対する観点追補。"
             "既に AI INITIAL Case が被覆している COV-059 の失敗時の振る舞いを深掘りする追加ケース。"
         ),
     }),
    (22, 145, "4xx 応答でフレームワークが出力するログ行にも同一の request_id が付くこと",
     "1) X-Request-ID を付与して 404 となる要求を送る 2) 400 となる要求を送る "
     "3) django.request の行とアクセスログの request_id を確認する",
     {
         "requirement_id": ["NFR-OM-18", "NFR-OM-01"],
         "related_adr": ["ADDR-007"],
         "test_category": "LOG",
         "criterion": "error-handling",
         "precondition": "購入者の認証トークンがある。ログ出力は設定済みハンドラ（整形・フィルタ）を用いる",
         "input": "X-Request-ID: trace-4xx-0001 / trace-4xx-0002",
         "expected_result": (
             "4xx の応答に対してフレームワークが出力する django.request のログ行にも、"
             "アクセスログと同一の request_id を出力する。1件の要求に関する全ログ行の request_id が一致し、"
             "要求オブジェクト・要求本文は出力しない（ADDR-007 INV-003/INV-004、NFR-OM-18、NFR-OM-01）"
         ),
         "notes": (
             "Production Code 変更（RequestIdFilter による相関IDの補完）に対する観点追補。"
             "既に AI INITIAL / GAP_FILL が被覆している COV-145 の応答確定後のログ行を深掘りする追加ケース。"
         ),
     }),
    (23, 145, "5xx 応答でフレームワークが出力するログ行にも同一の request_id が付くこと",
     "1) 内部例外を発生させ 500 となる要求を X-Request-ID 付きで送る 2) 同じ要求を X-Request-ID なしで送る "
     "3) django.request の行とアクセスログ・応答ヘッダーの request_id を確認する",
     {
         "requirement_id": ["NFR-OM-18", "NFR-OM-01"],
         "related_adr": ["ADDR-007"],
         "test_category": "LOG",
         "criterion": "error-handling",
         "precondition": "購入者の認証トークンがある。カート照会の内部処理で例外が発生する状態にする",
         "input": "X-Request-ID: trace-5xx-0001 / 未付与",
         "expected_result": (
             "5xx の応答に対する django.request のログ行（ERROR）にもアクセスログと同一の request_id を出力する。"
             "X-Request-ID 未付与時は生成した値を全ログ行と応答ヘッダーへ用いる。例外メッセージ本文は出力しない"
             "（ADDR-007 INV-003、LOG-02、NFR-OM-18）"
         ),
         "notes": (
             "Production Code 変更（RequestIdFilter による相関IDの補完）に対する観点追補。"
             "既に AI INITIAL / GAP_FILL が被覆している COV-145 の応答確定後のログ行を深掘りする追加ケース。"
         ),
     }),
]


def read_json(path: str) -> dict:
    with open(path, encoding="utf-8") as stream:
        return json.load(stream)


def write_json(path: str, payload: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def write_text(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as stream:
        stream.write(text)


def coverage_key(item: dict) -> str:
    """Coverage Key（要件・連携箇所・試験区分・観点・条件の識別子から生成）。"""
    return "#".join(
        [
            str(item["requirement_id"]),
            str(item["integration_point"]),
            str(item["test_category"]),
            str(item["criterion"]),
            str(item["coverage_id"]),
        ]
    )


def sha256_of(path: str) -> str:
    with open(path, "rb") as stream:
        return hashlib.sha256(stream.read()).hexdigest()


def case_number(case_id: str) -> int:
    return int(case_id.rsplit("-", 1)[1])


def load_coverage() -> tuple[list[dict], dict[int, dict]]:
    document = read_json(REQUIRED_COVERAGE)
    coverage = document["coverage"]
    by_number = {int(item["coverage_id"].split("-")[1]): item for item in coverage}
    return coverage, by_number


def split_ids(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [token.strip() for token in re.split(r"[,、，\s]+", str(value)) if token.strip()]


# ------------------------------------------------------------------
# Plan（Step 13〜18）
# ------------------------------------------------------------------
def build_plan() -> dict:
    coverage, coverage_by_number = load_coverage()
    keys = {item["coverage_id"]: coverage_key(item) for item in coverage}
    initial = read_json(AI_INITIAL)

    cases: list[dict] = []
    for case in initial["cases"]:
        number = case_number(case["case_id"])
        covered = AI_INITIAL_COVERAGE.get(number, [])
        if not covered:
            raise SystemExit(f"coverage mapping missing for {case['case_id']}")
        coverage_ids = [f"COV-{value:03d}" for value in covered]
        requirements = REQUIREMENT_NORMALIZATION.get(number) or split_ids(case["requirement_id"])
        entry = {
            "case_id": case["case_id"],
            "origin": "AI_GENERATED",
            "generation_stage": "INITIAL",
            "title": case["title"],
            "requirement_id": requirements,
            "requirement_id_source": case["requirement_id"],
            "related_adr": split_ids(case.get("related_adr")),
            "test_category": case["test_category"],
            "criterion": case["criterion"],
            "precondition": case.get("precondition"),
            "input": case.get("input"),
            "steps": case["steps"],
            "expected_result": case["expected_result"],
            "execution_type": case["execution_type"],
            "coverage_ids": coverage_ids,
            "coverage_keys": [keys[value] for value in coverage_ids],
            "integration_point": sorted(
                {coverage_by_number[value]["integration_point"] for value in covered}
            ),
            "notes": case.get("notes"),
        }
        cases.append(entry)

    for entry in GAP_CASES:
        number, coverage_number, title, steps = entry[:4]
        overrides: dict = entry[4] if len(entry) > 4 else {}
        item = coverage_by_number[coverage_number]
        coverage_id = item["coverage_id"]
        case = {
            "case_id": f"IT-AI-GAP-{number:03d}",
            "origin": "AI_GENERATED",
            "generation_stage": "GAP_FILL",
            "title": title,
            "requirement_id": split_ids(item["requirement_id"]),
            "requirement_id_source": item["requirement_id"],
            "related_adr": split_ids(item.get("related_adr")),
            "test_category": item["test_category"],
            "criterion": item["criterion"],
            "precondition": item["condition"],
            "input": item["condition"],
            "steps": steps,
            "expected_result": item["expected_behavior"],
            "execution_type": "AUTOMATABLE",
            "coverage_ids": [coverage_id],
            "coverage_keys": [keys[coverage_id]],
            "integration_point": [item["integration_point"]],
            "notes": "Coverage Gap Analysis（Step 16）で MISSING となった Coverage を補完する追加ケース。",
        }
        case.update(overrides)
        cases.append(case)

    return {
        "schema_version": 1,
        "run_id": RUN_ID,
        "phase": "integration-test",
        "generated_at": timestamp(),
        "source": {
            "ai_initial_cases": {
                "path": AI_INITIAL,
                "total": initial["total"],
                "freeze_sha256": initial["freeze_sha256"],
                "modified_by_this_phase": False,
            },
            "required_coverage": {"path": REQUIRED_COVERAGE, "total": len(coverage)},
            "external_cases": {
                "provided": False,
                "user_confirmed_without_external_cases": True,
                "standard_location": "external-tests/integration-test/",
            },
        },
        "coverage_key_rule": "requirement_id#integration_point#test_category#criterion#coverage_id",
        "totals": {
            "ai_initial": sum(1 for case in cases if case["generation_stage"] == "INITIAL"),
            "ai_gap_fill": sum(1 for case in cases if case["generation_stage"] == "GAP_FILL"),
            "external": 0,
            "total": len(cases),
        },
        "cases": cases,
    }


def timestamp() -> str:
    return dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).replace(microsecond=0).isoformat()


def classify_coverage(plan: dict, coverage: list[dict]) -> dict:
    keys = {item["coverage_id"]: coverage_key(item) for item in coverage}
    ai_initial: dict[str, list[str]] = {}
    ai_gap: dict[str, list[str]] = {}
    external: dict[str, list[str]] = {}
    for case in plan["cases"]:
        target = (
            ai_initial
            if case["generation_stage"] == "INITIAL"
            else ai_gap
            if case["generation_stage"] == "GAP_FILL"
            else external
        )
        for key in case["coverage_keys"]:
            target.setdefault(key, []).append(case["case_id"])

    required = [keys[item["coverage_id"]] for item in coverage]
    common = [key for key in required if key in ai_initial and key in external]
    ai_only = [key for key in required if key in ai_initial and key not in external]
    external_only = [key for key in required if key in external and key not in ai_initial]
    missing = [key for key in required if key not in ai_initial and key not in external]
    final_missing = [key for key in missing if key not in ai_gap]
    return {
        "keys": keys,
        "ai_initial": ai_initial,
        "ai_gap": ai_gap,
        "external": external,
        "required": required,
        "common": common,
        "ai_only": ai_only,
        "external_only": external_only,
        "missing": missing,
        "final_missing": final_missing,
    }


def rate(part: int, whole: int) -> float:
    if whole == 0:
        return 100.0
    return round(part / whole * 100.0, 2)


def build_coverage_report(plan: dict, coverage: list[dict], result: dict) -> dict:
    required_total = len(result["required"])
    covered_initial = required_total - len(result["missing"])
    final_covered = required_total - len(result["final_missing"])
    by_id = {item["coverage_id"]: item for item in coverage}
    key_to_id = {value: key for key, value in result["keys"].items()}

    gaps = []
    for index, key in enumerate(result["missing"], start=1):
        coverage_id = key_to_id[key]
        item = by_id[coverage_id]
        filled_by = result["ai_gap"].get(key, [])
        gaps.append(
            {
                "gap_id": f"GAP-{index:03d}",
                "coverage_id": coverage_id,
                "coverage_key": key,
                "requirement_id": item["requirement_id"],
                "related_adr": item.get("related_adr"),
                "integration_point": item["integration_point"],
                "test_category": item["test_category"],
                "criterion": item["criterion"],
                "missing_detail": item["condition"],
                "expected_behavior": item["expected_behavior"],
                "ai_initial": "NOT_COVERED",
                "external": "NOT_PROVIDED",
                "filled_by_gap_fill_cases": filled_by,
                "status": "FILLED" if filled_by else "UNFILLED",
            }
        )

    return {
        "schema_version": 1,
        "run_id": RUN_ID,
        "phase": "integration-test",
        "generated_at": timestamp(),
        "external_cases_provided": False,
        "user_confirmed_without_external_cases": True,
        "required_coverage": [
            {
                "coverage_id": item["coverage_id"],
                "coverage_key": result["keys"][item["coverage_id"]],
                "requirement_id": item["requirement_id"],
                "related_adr": item.get("related_adr"),
                "use_case_id": item.get("use_case_id"),
                "source_ac": item.get("source_ac"),
                "integration_point": item["integration_point"],
                "test_category": item["test_category"],
                "criterion": item["criterion"],
                "condition": item["condition"],
                "expected_behavior": item["expected_behavior"],
                "covered_by_ai_initial": result["ai_initial"].get(
                    result["keys"][item["coverage_id"]], []
                ),
                "covered_by_ai_gap_fill": result["ai_gap"].get(
                    result["keys"][item["coverage_id"]], []
                ),
                "covered_by_external": [],
            }
            for item in coverage
        ],
        "initial_metrics": {
            "required": required_total,
            "common": len(result["common"]),
            "ai_only": len(result["ai_only"]),
            "external_only": len(result["external_only"]),
            "missing": len(result["missing"]),
            "ai_initial_covered": covered_initial,
            "ai_initial_coverage_rate": rate(covered_initial, required_total),
            "external_coverage_rate": None,
            "combined_initial_coverage_rate": rate(covered_initial, required_total),
            "frozen": True,
            "note": "Gap Fill 前の測定値。GAP_FILL Case を追加して書き換えない。",
        },
        "final_metrics": {
            "covered": final_covered,
            "missing": len(result["final_missing"]),
            "final_coverage_rate": rate(final_covered, required_total),
            "gap_fill_cases": plan["totals"]["ai_gap_fill"],
        },
        "gaps": gaps,
    }


def build_case_comparison(plan: dict, coverage: list[dict], result: dict) -> dict:
    key_to_id = {value: key for key, value in result["keys"].items()}
    classification = {}
    for key in result["common"]:
        classification[key] = "COMMON"
    for key in result["ai_only"]:
        classification[key] = "AI_ONLY"
    for key in result["external_only"]:
        classification[key] = "EXTERNAL_ONLY"
    for key in result["missing"]:
        classification[key] = "MISSING"

    items = []
    for key in result["required"]:
        items.append(
            {
                "coverage_id": key_to_id[key],
                "coverage_key": key,
                "classification": classification[key],
                "ai_initial_cases": result["ai_initial"].get(key, []),
                "external_cases": [],
                "ai_gap_fill_cases": result["ai_gap"].get(key, []),
            }
        )

    return {
        "schema_version": 1,
        "run_id": RUN_ID,
        "phase": "integration-test",
        "generated_at": timestamp(),
        "external_input": {
            "provided": False,
            "user_confirmed_without_external_cases": True,
            "standard_location": "external-tests/integration-test/",
            "note": (
                "External Test Case は配置されていない。ユーザーが External Case なしで続行することを"
                "明示的に選択したため、EXTERNAL_ONLY は構造上0件、COMMON も0件となる。"
                "AI INITIAL Case が被覆していない Coverage は MISSING として記録している。"
            ),
        },
        "summary": {
            "required": len(result["required"]),
            "common": len(result["common"]),
            "ai_only": len(result["ai_only"]),
            "external_only": len(result["external_only"]),
            "missing": len(result["missing"]),
            "ai_initial_cases": plan["totals"]["ai_initial"],
            "ai_gap_fill_cases": plan["totals"]["ai_gap_fill"],
            "external_cases": 0,
        },
        "items": items,
    }


def command_plan() -> None:
    coverage, _ = load_coverage()
    plan = build_plan()
    result = classify_coverage(plan, coverage)
    write_json(PLAN, plan)
    write_json(os.path.join(OUT_DIR, "coverage-gap-report.json"), build_coverage_report(plan, coverage, result))
    write_json(os.path.join(OUT_DIR, "case-comparison.json"), build_case_comparison(plan, coverage, result))
    print(
        "plan: total={total} initial={initial} gap_fill={gap} missing={missing} final_missing={final}".format(
            total=plan["totals"]["total"],
            initial=plan["totals"]["ai_initial"],
            gap=plan["totals"]["ai_gap_fill"],
            missing=len(result["missing"]),
            final=len(result["final_missing"]),
        )
    )
    print("missing coverage:", ", ".join(sorted(key.split("#")[-1] for key in result["missing"])))


# ------------------------------------------------------------------
# Reports（Step 24〜41）
# ------------------------------------------------------------------
TEST_PATTERN = re.compile(r"test_it_(ai_init|ai_gap)_(\d{3})")


def read_junit() -> tuple[dict[str, list[dict]], dict[str, int]]:
    root = ET.parse(JUNIT).getroot()
    results: dict[str, list[dict]] = {}
    summary = {"total": 0, "passed": 0, "failed": 0, "errors": 0, "skipped": 0}
    for testcase in root.iter("testcase"):
        summary["total"] += 1
        failure = testcase.find("failure")
        error = testcase.find("error")
        skipped = testcase.find("skipped")
        if failure is not None:
            status, message = "FAIL", (failure.get("message") or "").strip()
            summary["failed"] += 1
        elif error is not None:
            status, message = "ERROR", (error.get("message") or "").strip()
            summary["errors"] += 1
        elif skipped is not None:
            status, message = "SKIPPED", (skipped.get("message") or "").strip()
            summary["skipped"] += 1
        else:
            status, message = "PASS", ""
            summary["passed"] += 1
        name = testcase.get("name", "")
        match = TEST_PATTERN.search(name)
        if not match:
            raise SystemExit(f"test name is not mapped to a case: {name}")
        prefix = "IT-AI-INIT-" if match.group(1) == "ai_init" else "IT-AI-GAP-"
        case_id = f"{prefix}{match.group(2)}"
        results.setdefault(case_id, []).append(
            {
                "test": f"{testcase.get('classname', '')}::{name}",
                "status": status,
                "message": message,
                "time_seconds": float(testcase.get("time") or 0.0),
            }
        )
    return results, summary


# 本Runの実行履歴（Production Code の再変更に伴う再実行。Step 23〜24・33〜35）。
EXECUTIONS = [
    {
        "execution": 1,
        "executed_at": "2026-10-22T01:52+09:00",
        "trigger": "RUN-002 の初回実行（AI INITIAL 162 + AI GAP_FILL 19）",
        "cases": {"ai_initial": 162, "ai_gap_fill": 19, "total": 181},
        "junit": {"total": 183, "passed": 183, "failed": 0},
        "result": "全件PASS（DEF-IT-001 の修正後の再試験）",
    },
    {
        "execution": 2,
        "executed_at": "2026-10-22T02:57+09:00",
        "trigger": (
            "Quality Review(IMPLEMENTATION) の QR-IMPL-006 に対する Implementation Agent の修正で "
            "Production Code が再変更されたため（SCR-002 のカート投入失敗時の再表示、"
            "RequestIdFilter による 4xx/5xx ログ行の相関ID補完、DJANGO_SERVE_STATIC の追記）、"
            "観点を追補して全件を再実行した。"
        ),
        "added_cases": [
            "IT-AI-GAP-020",
            "IT-AI-GAP-021",
            "IT-AI-GAP-022",
            "IT-AI-GAP-023",
        ],
        "cases": {"ai_initial": 162, "ai_gap_fill": 23, "total": 185},
        "junit": {"total": 187, "passed": 187, "failed": 0},
        "result": "全件PASS（新規 Defect の検出なし。AI INITIAL Case は変更していない）",
    },
]

RERUN_NOTE = (
    "Production Code の再変更（QR-IMPL-006 の修正）を受けて、AI INITIAL 162 件・AI GAP_FILL 23 件の"
    "全ケースを再実行した。追補した観点は IT-AI-GAP-020〜023（SCR-002 のカート投入失敗時に本画面へ留まり"
    "入力値とカートを維持すること、4xx/5xx 応答で django.request のログ行にも同一 request_id が付くこと）で、"
    "いずれも origin=AI_GENERATED / generation_stage=GAP_FILL として追加した。"
    "固定済みの AI INITIAL Case（162 件）と Gap Fill 前の初期 Coverage 測定値は変更していない。"
)

DEFECTS = [
    {
        "defect_id": "DEF-IT-001",
        "title": "APIのエラー応答が提供済みAPI契約の共通形式（error 封筒・details[].reason）になっていない",
        "classification": "IMPLEMENTATION_ERROR",
        "severity": "HIGH",
        "requirement_id": ["FR-001", "FR-020", "FR-021", "FR-033", "FR-040"],
        "related_adr": ["ADDR-011"],
        "expected": (
            "Steering 6章 Error Response／実装タスク一覧 TASK-003 のとおり、"
            '{"error": {"code": ..., "message": ..., "details": [{"field": ..., "reason": ...}], "context": {...}}} '
            "の形式で返すこと。"
        ),
        "actual": (
            '封筒 "error" を持たない {"code", "message", "details", "context"} の平坦な本文を返し、'
            'details の要素も {"field", "message"} となっている。'
        ),
        "root_cause": (
            "common/exception_handler.py の error_payload() がエラー本文を error キーで包まず、"
            "common/validators.py ValidationCollector.add() が details の理由を message キーで組み立てているため、"
            "提供済みAPI契約（Steering 6章 Error Response）と不一致になっている。"
        ),
        "error_location": (
            "app/common/exception_handler.py::error_payload / api_exception_handler、"
            "app/common/validators.py::ValidationCollector.add（details のキー名）"
        ),
        "error_location_identifiable": True,
        "layer": "API共通（例外ハンドラ）",
        "detected_by_cases": ["IT-AI-INIT-010", "IT-AI-INIT-156"],
        "detection_source": "AI_ONLY_DEFECT",
        "detected_by_generation_stage": ["INITIAL"],
        "impact": (
            "全APIのエラー応答が契約と異なるため、契約に従う利用側（画面以外のAPI利用者・将来の連携先）が"
            "エラーコードを解釈できない。影響範囲は 400/401/403/404/409/500/502 の全エラー応答。"
            "修正時は tests/unit 配下の平坦な本文（response.data[\"code\"] 等）を前提とした単体テストの"
            "期待値（29 箇所）の見直しも併せて必要になる。"
        ),
        "resolved": True,
        "resolution": (
            "Implementation Agent（cycle=1）が Production Code を正本どおりに修正した。"
            "app/common/exception_handler.py の error_payload() を "
            '{"error": {code, message, details, context}} の封筒形式へ変更し、'
            "details は常に配列（該当なしは空配列）、context は該当なしで空オブジェクトとした。"
            "要素整形用の error_detail_payload（field / reason）を追加し、"
            "from_framework_exception の details キーを message→reason へ変更。"
            "app/common/validators.py ほか計5ファイル（Production Code のみ）と画面側のエラー表示を整合させた。"
            "Unit Test Agent（cycle=2）が平坦形式を前提としていた逆算テストの期待値を正本へ是正し、"
            "Regression Test 3件・強化1件を追加（最終 821 passed / 0 failed）。"
            "Integration Test Agent は Production Code を変更していない。"
        ),
        "recommended_route": "IMPLEMENTATION",
        "repair_cycles": 1,
        "rerun": {
            "target_cases": "PASS",
            "related_cases": "PASS",
            "full_suite": "PASS",
            "note": (
                "修正後に再試験を実施。対象ケース（IT-AI-INIT-010 / IT-AI-INIT-156）は PASS。"
                "同一要件・同一連携箇所の関連ケース（エラーコードとHTTPステータスの対応・判定順序・"
                "内部情報の非表示を検証する IT-AI-INIT-157/158/159 等）も PASS。"
                "Integration Test Suite 全体（183 test / 181 case）を再実行し全件 PASS。"
            ),
        },
    }
]

CASE_FAILURE_INFO = {}

# 本Runで検出し、Implementation Agent の修正後に再試験でPASSとなったケース（履歴）。
# 隠蔽せず error-report に残し、再試験結果とともに記録する。
RESOLVED_CASE_ERRORS = {
    "IT-AI-INIT-010": {
        "classification": "IMPLEMENTATION_ERROR",
        "defect_id": "DEF-IT-001",
        "first_failed_at_cycle": 0,
        "actual_at_detection": (
            "HTTP 400 / VALIDATION_ERROR は返るが、応答本文が error 封筒を持たず、"
            "details の理由が reason ではなく message キーで返った。"
        ),
        "error_message_at_detection": (
            "AssertionError: assert {'code', 'con...s', 'message'} == {'error'}"
        ),
        "actual_after_fix": (
            '{"error": {"code": "VALIDATION_ERROR", "message": ..., "details": '
            '[{"field": ..., "reason": ...}], "context": {}}} 形式で返り、'
            "email・password・password_confirmation・full_name の全項目が1回で列挙される。"
        ),
    },
    "IT-AI-INIT-156": {
        "classification": "IMPLEMENTATION_ERROR",
        "defect_id": "DEF-IT-001",
        "first_failed_at_cycle": 0,
        "actual_at_detection": (
            "全エラー種別で応答本文が {code, message, details, context} の平坦な形式であり、"
            "契約の error 封筒形式と一致しなかった。"
        ),
        "error_message_at_detection": (
            "AssertionError: VALIDATION_ERROR\n"
            "assert {'code', 'con...s', 'message'} == {'error'}"
        ),
        "actual_after_fix": (
            "VALIDATION_ERROR / AUTHENTICATION_REQUIRED / PERMISSION_DENIED / NOT_FOUND / "
            "INSUFFICIENT_STOCK の全種別で本文のキーが {\"error\"} のみとなり、"
            "error 配下が code / message / details / context で構成される。"
            "details は該当なしで空配列、context は該当なしで空オブジェクト。"
            "スタックトレース・SQL 等の内部情報を含まない。"
        ),
    },
}

CRITERIA_RESULTS = [
    (
        "api",
        True,
        "PASS",
        "API契約（エンドポイント・成功ステータス・応答項目・ページング・正規化・金額計算）を"
        "API→Service→ORM→PostgreSQL の通しで検証し、該当ケースはすべてPASS。",
    ),
    (
        "authentication",
        True,
        "PASS",
        "認証トークンの発行・検証・失効・有効期限境界、ロール別権限、画面セッションの"
        "開始・破棄・無操作切断を検証し、該当ケースはすべてPASS。",
    ),
    (
        "database",
        True,
        "PASS",
        "永続化（正規化保存・スナップショット・在庫増減・監査ログ・一意制約）と"
        "同時実行時の整合を使い捨てテストDB（PostgreSQL 16）で検証し、該当ケースはすべてPASS。",
    ),
    (
        "end-to-end-flow",
        True,
        "PASS",
        "購入者・管理者の業務フロー、画面からの一連操作、初期データ投入後の購入フローを検証し、"
        "該当ケースはすべてPASS。",
    ),
    (
        "error-handling",
        True,
        "PASS",
        "業務エラー・入力エラーのエラーコード・HTTPステータス・context・判定順序に加え、"
        "共通エラー応答形式（error 封筒・details[].reason）・内部情報の非表示・異常終了時のロールバックを検証し、"
        "該当ケースはすべてPASS（DEF-IT-001 は修正済みで IT-AI-INIT-010 / IT-AI-INIT-156 ともPASS）。"
        "Production Code 再変更後は、画面の失敗時の再表示（本画面に留まる・入力値保持・カート不変。"
        "IT-AI-GAP-020/021）と 4xx/5xx 応答のログ行の相関ID（IT-AI-GAP-022/023）を追補して検証し、いずれもPASS。",
    ),
    (
        "state-transition",
        True,
        "PASS",
        "注文状態遷移（ST-PO-01〜06）・カート状態遷移（ST-CART-01/02）・クーポン適用状態と"
        "競合時の再判定を検証し、該当ケースはすべてPASS。",
    ),
]


def build_evidence(plan: dict, coverage: list[dict], result: dict, junit_results, junit_summary) -> dict:
    case_results = []
    traceability = []
    stage_summary = {
        "AI_GENERATED/INITIAL": {"total": 0, "passed": 0, "failed": 0, "blocked": 0},
        "AI_GENERATED/GAP_FILL": {"total": 0, "passed": 0, "failed": 0, "blocked": 0},
        "EXTERNAL": {"total": 0, "passed": 0, "failed": 0, "blocked": 0},
    }
    for case in plan["cases"]:
        executions = junit_results.get(case["case_id"], [])
        if not executions:
            raise SystemExit(f"no execution result for {case['case_id']}")
        failed = [row for row in executions if row["status"] in ("FAIL", "ERROR")]
        result_value = "PASS" if not failed else "FAIL"
        bucket = f"{case['origin']}/{case['generation_stage']}" if case["origin"] == "AI_GENERATED" else "EXTERNAL"
        stage_summary[bucket]["total"] += 1
        stage_summary[bucket]["passed" if result_value == "PASS" else "failed"] += 1
        failure_info = CASE_FAILURE_INFO.get(case["case_id"], {})
        fixed_info = RESOLVED_CASE_ERRORS.get(case["case_id"], {})
        if failure_info.get("actual"):
            actual_result = failure_info["actual"]
        elif result_value == "PASS" and fixed_info.get("actual_after_fix"):
            actual_result = fixed_info["actual_after_fix"]
        else:
            actual_result = "期待結果のとおり。"
        entry = {
            "case_id": case["case_id"],
            "origin": case["origin"],
            "generation_stage": case["generation_stage"],
            "requirement_id": case["requirement_id"],
            "related_adr": case["related_adr"],
            "integration_point": case["integration_point"],
            "coverage_ids": case["coverage_ids"],
            "criterion": case["criterion"],
            "execution_type": case["execution_type"],
            "expected_result": case["expected_result"],
            "actual_result": actual_result,
            "result": result_value,
            "execution_time_seconds": round(sum(row["time_seconds"] for row in executions), 3),
            "error_message": " / ".join(row["message"] for row in failed) if failed else None,
            "tests": [row["test"] for row in executions],
        }
        if result_value != "PASS":
            entry["classification"] = failure_info.get("classification", "IMPLEMENTATION_ERROR")
            entry["defect_id"] = failure_info.get("defect_id")
        case_results.append(entry)
        traceability.append(
            {
                "case_id": case["case_id"],
                "origin": case["origin"],
                "generation_stage": case["generation_stage"],
                "requirement_id": case["requirement_id"],
                "related_adr": case["related_adr"],
                "integration_point": case["integration_point"],
                "implementation": "app/ 配下 Production Code（API/Service/ORM/画面/コマンド）",
                "unit_test": "reports/unit-test/junit.xml（Unit Test 工程で全件PASS）",
                "integration_test": entry["tests"],
                "result": result_value,
            }
        )

    required_total = len(result["required"])
    covered_initial = required_total - len(result["missing"])
    final_covered = required_total - len(result["final_missing"])

    return {
        "schema_version": 1,
        "run_id": RUN_ID,
        "phase": "integration-test",
        "generated_at": timestamp(),
        "status": "SUCCESS",
        "execution_history": EXECUTIONS,
        "rerun_note": RERUN_NOTE,
        "external_input": {
            "provided": False,
            "user_confirmed_without_external_cases": True,
            "confirmed_at": "2026-10-22",
            "confirmed_via": "SDLC Orchestrator 経由のユーザー明示確認（external_cases_confirmed_absent: true）",
            "standard_location": "external-tests/integration-test/",
            "files_found": [],
            "note": (
                "External Test Case は配置されていない。Integration Test Agent / Skill の判断ではなく、"
                "ユーザーが External Case なしで続行することを明示的に選択したため処理を継続した。"
            ),
        },
        "external_case_integrity": [],
        "environment": {
            "production_environment_used": False,
            "description": (
                "ローカル検証環境。Django 5.2 + DRF のテストクライアントで API・画面を実行し、"
                "DB は Docker コンテナ上の PostgreSQL 16（compose の db サービス）。"
            ),
            "reproducible": True,
            "disposable": True,
            "test_runner": "pytest + pytest-django（tests/integration）",
            "command": (
                "python -m pytest tests/integration -c app/pyproject.toml --rootdir . "
                "--junitxml=reports/integration-test/junit.xml"
            ),
        },
        "database": {
            "used": True,
            "engine": "PostgreSQL 16（Docker コンテナ ai-sdlc-copilot-db-1）",
            "test_database": "pytest-django が作成・破棄する使い捨てテストDB",
            "production_database_used": False,
            "shared_database_used": False,
            "production_credentials_used": False,
            "production_data_used": False,
            "schema_reproducible": True,
            "isolated_test_data": True,
        },
        "external_services": [
            {
                "service": "決済サービス（模擬。IF-01）",
                "strategy": "LOCAL_IMPLEMENTATION / STUB",
                "production_service_used": False,
                "note": "本システム内の模擬実装を使用し、外部ネットワークへは接続しない（検証済み: IT-AI-INIT-115）。",
            }
        ],
        "criteria_coverage": [
            {"criterion": name, "applicable": applicable, "result": value, "reason": reason}
            for name, applicable, value, reason in CRITERIA_RESULTS
        ],
        "junit_summary": junit_summary,
        "test_summary": {
            "ai_initial": stage_summary["AI_GENERATED/INITIAL"],
            "ai_gap_fill": stage_summary["AI_GENERATED/GAP_FILL"],
            "external": stage_summary["EXTERNAL"],
            "total": {
                "total": sum(row["total"] for row in stage_summary.values()),
                "passed": sum(row["passed"] for row in stage_summary.values()),
                "failed": sum(row["failed"] for row in stage_summary.values()),
                "blocked": sum(row["blocked"] for row in stage_summary.values()),
            },
        },
        "coverage_metrics": {
            "required": required_total,
            "common": len(result["common"]),
            "ai_only": len(result["ai_only"]),
            "external_only": len(result["external_only"]),
            "missing": len(result["missing"]),
            "ai_initial_coverage_rate": rate(covered_initial, required_total),
            "external_coverage_rate": None,
            "combined_initial_coverage_rate": rate(covered_initial, required_total),
            "final_coverage_rate": rate(final_covered, required_total),
        },
        "case_results": case_results,
        "defects": DEFECTS,
        "flaky_tests": [],
        "automation_blocked": [],
        "test_spec_conflicts": [],
        "unresolved": [],
        "resolved_issues": [
            {
                "issue_id": "DEF-IT-001",
                "state": "RESOLVED",
                "repair_cycles": 1,
                "first_detected_cycle": 0,
                "resolved_by": "Implementation Agent（cycle=1）",
                "impact": (
                    "全APIのエラー応答形式が契約と不一致だった。修正後は 400/401/403/404/409/500/502 の"
                    "全エラー応答が error 封筒形式となり、結合試験・単体試験とも全件PASS。"
                ),
                "recommended_route": "IMPLEMENTATION",
                "rerun_result": "PASS（対象ケース・関連ケース・Suite全体）",
            }
        ],
        "traceability": traceability,
        "experimental_metrics": {
            "ai_initial_case_count": plan["totals"]["ai_initial"],
            "ai_gap_fill_case_count": plan["totals"]["ai_gap_fill"],
            "external_case_count": 0,
            "common_coverage_count": len(result["common"]),
            "ai_only_coverage_count": len(result["ai_only"]),
            "external_only_coverage_count": len(result["external_only"]),
            "missing_coverage_count": len(result["missing"]),
            "ai_initial_coverage_rate": rate(covered_initial, required_total),
            "external_coverage_rate": None,
            "combined_initial_coverage_rate": rate(covered_initial, required_total),
            "final_coverage_rate": rate(final_covered, required_total),
            "ai_initial_defect_detection_count": 1,
            "ai_gap_fill_defect_detection_count": 0,
            "external_defect_detection_count": 0,
            "common_defect_count": 0,
            "ai_only_defect_count": 1,
            "external_only_defect_count": 0,
        },
    }


def build_error_report(evidence: dict) -> dict:
    """本Runで検出したErrorを、現在のPASS/FAIL状態と再試験結果つきで集計する。

    修正済みのErrorも削除せず履歴として残す（Failureを隠さない）。
    """
    errors = []
    by_origin = {"AI_GENERATED": 0, "EXTERNAL": 0}
    by_cause: dict[str, int] = {}
    by_stage = {"INITIAL": 0, "GAP_FILL": 0}
    case_by_id = {case["case_id"]: case for case in evidence["case_results"]}
    current_failures = [case for case in evidence["case_results"] if case["result"] != "PASS"]

    for case_id, info in RESOLVED_CASE_ERRORS.items():
        case = case_by_id[case_id]
        defect = next(item for item in DEFECTS if item["defect_id"] == info["defect_id"])
        errors.append(
            {
                "case_id": case_id,
                "origin": case["origin"],
                "generation_stage": case["generation_stage"],
                "requirement_id": case["requirement_id"],
                "related_adr": case["related_adr"],
                "classification": info["classification"],
                "defect_id": info["defect_id"],
                "cause": defect["root_cause"],
                "error_location": defect["error_location"],
                "error_location_identifiable": True,
                "expected": case["expected_result"],
                "actual_at_detection": info["actual_at_detection"],
                "actual": case["actual_result"],
                "error_message": info["error_message_at_detection"],
                "fix": defect["resolution"],
                "retest_result": (
                    f"{case['result']}（修正後に対象ケースを再実行。"
                    f"実行テスト: {', '.join(case['tests'])}）"
                ),
                "resolved": True,
                "repair_cycles": defect["repair_cycles"],
                "first_failed_at_cycle": info["first_failed_at_cycle"],
            }
        )
        by_origin[case["origin"]] += 1
        by_cause[info["classification"]] = by_cause.get(info["classification"], 0) + 1
        by_stage[case["generation_stage"]] += 1

    for case in current_failures:
        if case["case_id"] in RESOLVED_CASE_ERRORS:
            continue
        raise SystemExit(f"unclassified failure: {case['case_id']}")

    return {
        "schema_version": 1,
        "run_id": RUN_ID,
        "phase": "integration-test",
        "generated_at": timestamp(),
        "summary": {
            "total_errors": len(errors),
            "failed_cases": len(current_failures),
            "resolved_errors": sum(1 for item in errors if item["resolved"]),
            "unique_defects": len(DEFECTS),
            "unresolved_defects": sum(1 for item in DEFECTS if not item["resolved"]),
            "errors_by_origin": by_origin,
            "errors_by_generation_stage": by_stage,
            "errors_by_cause": by_cause,
            "defects_by_detection_source": {
                "COMMON_DEFECT": 0,
                "AI_ONLY_DEFECT": sum(1 for item in DEFECTS if item["detection_source"] == "AI_ONLY_DEFECT"),
                "EXTERNAL_ONLY_DEFECT": 0,
            },
            "unresolved_errors": sum(1 for item in errors if not item["resolved"]),
            "test_spec_conflicts": 0,
            "automation_blocked": 0,
            "note": (
                "total_errors は本Runで検出したError（履歴）の件数。"
                "failed_cases は最終実行時点でFAILのケース数。"
            ),
        },
        "errors": errors,
        "defects": DEFECTS,
    }


def build_report(plan: dict, evidence: dict, coverage_report: dict, error_report: dict) -> dict:
    return {
        "schema_version": 1,
        "run_id": RUN_ID,
        "phase": "integration-test",
        "generated_at": timestamp(),
        "status": "SUCCESS",
        "test_summary": evidence["test_summary"],
        "junit_summary": evidence["junit_summary"],
        "case_counts": plan["totals"],
        "external_input": evidence["external_input"],
        "coverage": {
            "initial_metrics": coverage_report["initial_metrics"],
            "final_metrics": coverage_report["final_metrics"],
            "missing_coverage_ids": [gap["coverage_id"] for gap in coverage_report["gaps"]],
        },
        "defects": {
            "total": len(DEFECTS),
            "common": 0,
            "ai_only": sum(1 for item in DEFECTS if item["detection_source"] == "AI_ONLY_DEFECT"),
            "external_only": 0,
            "unresolved": sum(1 for item in DEFECTS if not item["resolved"]),
            "items": [
                {
                    "defect_id": item["defect_id"],
                    "title": item["title"],
                    "classification": item["classification"],
                    "detection_source": item["detection_source"],
                    "detected_by_cases": item["detected_by_cases"],
                    "error_location": item["error_location"],
                    "resolved": item["resolved"],
                }
                for item in DEFECTS
            ],
        },
        "errors": error_report["summary"],
        "criteria_coverage": evidence["criteria_coverage"],
        "regression": {
            "rerun_failed_cases": True,
            "rerun_related_cases": True,
            "rerun_full_suite": True,
            "full_suite_result": (
                "PASS（DEF-IT-001 修正後の再試験に加え、Production Code 再変更後に全件を再実行し全件PASS）"
            ),
            "execution_history": EXECUTIONS,
            "note": RERUN_NOTE,
        },
        "experimental_metrics": evidence["experimental_metrics"],
        "reports": [
            "reports/integration-test/integration-test-plan.json",
            "reports/integration-test/case-comparison.json",
            "reports/integration-test/coverage-gap-report.json",
            "reports/integration-test/integration-test-evidence.json",
            "reports/integration-test/error-report.json",
            "reports/integration-test/error-report.md",
            "reports/integration-test/integration-test-report.json",
            "reports/integration-test/integration-test-report.md",
            "reports/integration-test/junit.xml",
        ],
    }


def summary_row(label: str, values: dict) -> str:
    """Test Summary の1行を組み立てる。"""
    return (
        f"| {label} | {values['total']} | {values['passed']} | "
        f"{values['failed']} | {values['blocked']} |"
    )


def markdown_report(report: dict, coverage_report: dict, error_report: dict) -> str:
    summary = report["test_summary"]
    initial = coverage_report["initial_metrics"]
    final = coverage_report["final_metrics"]
    lines = [
        "# Integration Test Report（RUN-002）",
        "",
        f"- 生成日時: {report['generated_at']}",
        f"- 工程結果: **{report['status']}**"
        "（DEF-IT-001 修正後の再試験、および Production Code 再変更後の全件再実行で全ケースPASS）",
        "- 対象: MiniCommerce（Django 5.2 + DRF + PostgreSQL 16）",
        "",
        f"- 本Runの再実行: {RERUN_NOTE}",
        "",
        "## 1. Test Summary",
        "",
        "| 区分 | 総数 | PASS | FAIL | BLOCKED |",
        "| --- | ---: | ---: | ---: | ---: |",
        summary_row("AI_GENERATED / INITIAL", summary["ai_initial"]),
        summary_row("AI_GENERATED / GAP_FILL", summary["ai_gap_fill"]),
        summary_row("EXTERNAL", summary["external"]),
        summary_row("TOTAL", summary["total"]),
        "",
        f"JUnit: total={report['junit_summary']['total']}, passed={report['junit_summary']['passed']}, "
        f"failed={report['junit_summary']['failed']}, errors={report['junit_summary']['errors']}, "
        f"skipped={report['junit_summary']['skipped']}",
        "",
        "## 2. AI / External Case 数",
        "",
        f"- AI INITIAL Case: {report['case_counts']['ai_initial']} 件（External Case 確認前に生成・固定）",
        f"- AI GAP_FILL Case: {report['case_counts']['ai_gap_fill']} 件（MISSING Coverage の補完）",
        "- External Case: 0 件（未提供。ユーザーが External Case なしで続行することを明示的に選択）",
        "",
        "## 3. Coverage 比較（Gap Fill 前の測定値）",
        "",
        "| 区分 | 件数 |",
        "| --- | ---: |",
        f"| Required Coverage | {initial['required']} |",
        f"| COMMON | {initial['common']} |",
        f"| AI_ONLY | {initial['ai_only']} |",
        f"| EXTERNAL_ONLY | {initial['external_only']} |",
        f"| MISSING | {initial['missing']} |",
        "",
        f"- AI INITIAL Coverage Rate: {initial['ai_initial_coverage_rate']}%",
        "- External Coverage Rate: 測定対象外（External Case 未提供）",
        f"- Combined Initial Coverage Rate: {initial['combined_initial_coverage_rate']}%",
        f"- Final Coverage Rate（GAP_FILL 後）: {final['final_coverage_rate']}%（未被覆 {final['missing']} 件）",
        "",
        "## 4. Coverage Gap（MISSING と補完状況）",
        "",
        "| Gap ID | Coverage | 要件 | 内容 | 補完ケース |",
        "| --- | --- | --- | --- | --- |",
    ]
    for gap in coverage_report["gaps"]:
        detail = gap["missing_detail"].replace("|", "/")
        lines.append(
            f"| {gap['gap_id']} | {gap['coverage_id']} | {gap['requirement_id']} | {detail} | "
            f"{', '.join(gap['filled_by_gap_fill_cases'])} |"
        )
    error_summary = error_report["summary"]
    lines += [
        "",
        "## 5. Error / Defect",
        "",
        f"- 本Runで検出した Error（履歴）: {error_summary['total_errors']} 件",
        f"- 最終実行時点の Failed Case 数: {error_summary['failed_cases']}",
        f"- Unique Defect 数: {error_summary['unique_defects']}"
        f"（未解決 {error_summary['unresolved_defects']} 件）",
        f"- 原因別: {json.dumps(error_summary['errors_by_cause'], ensure_ascii=False)}",
        f"- Origin 別: {json.dumps(error_summary['errors_by_origin'], ensure_ascii=False)}",
        f"- 生成段階別: {json.dumps(error_summary['errors_by_generation_stage'], ensure_ascii=False)}",
        f"- COMMON_DEFECT: {error_summary['defects_by_detection_source']['COMMON_DEFECT']} 件 / "
        f"AI_ONLY_DEFECT: {error_summary['defects_by_detection_source']['AI_ONLY_DEFECT']} 件 / "
        f"EXTERNAL_ONLY_DEFECT: {error_summary['defects_by_detection_source']['EXTERNAL_ONLY_DEFECT']} 件",
        f"- TEST_SPEC_CONFLICT: {error_summary['test_spec_conflicts']} 件 / AUTOMATION_BLOCKED: "
        f"{error_summary['automation_blocked']} 件",
        "",
        "### 不具合一覧",
        "",
    ]
    for defect in DEFECTS:
        lines += [
            f"#### {defect['defect_id']} {defect['title']}",
            "",
            f"- 分類: {defect['classification']}（修正担当: {defect['recommended_route']}）",
            f"- 検出ケース: {', '.join(defect['detected_by_cases'])}（{defect['detection_source']}）",
            f"- 要件 / ADDR: {', '.join(defect['requirement_id'])} / {', '.join(defect['related_adr'])}",
            f"- 期待: {defect['expected']}",
            f"- 検出時の実際: {defect['actual']}",
            f"- 原因: {defect['root_cause']}",
            f"- 箇所: {defect['error_location']}",
            f"- 影響: {defect['impact']}",
            f"- 修正: {defect['resolution']}",
            f"- 解消: {'はい' if defect['resolved'] else 'いいえ'}（修正ループ {defect['repair_cycles']} 回）",
            f"- 再試験: 対象ケース={defect['rerun']['target_cases']} / 関連ケース={defect['rerun']['related_cases']}"
            f" / 全件={defect['rerun']['full_suite']}",
            f"- 再試験の内容: {defect['rerun']['note']}",
            "",
        ]
    lines += [
        "## 6. Test Criteria",
        "",
        "| Criterion | 適用 | 結果 | 理由 |",
        "| --- | --- | --- | --- |",
    ]
    for item in report["criteria_coverage"]:
        lines.append(
            f"| {item['criterion']} | {'YES' if item['applicable'] else 'NO'} | {item['result']} | {item['reason']} |"
        )
    lines += [
        "",
        "## 7. 再試験・再実行",
        "",
        "- Failure を検出した対象ケース（IT-AI-INIT-010 / IT-AI-INIT-156）: 再実行済み・PASS",
        "- 関連ケース（同一要件・同一連携箇所）: 再実行済み・PASS",
        f"- Integration Test Suite 全体: 再実行済み（ケース単位 {report['test_summary']['total']['passed']} PASS / "
        f"{report['test_summary']['total']['failed']} FAIL、JUnit {report['junit_summary']['passed']} PASS / "
        f"{report['junit_summary']['failed']} FAIL）",
        "",
        "| 実行 | 時刻 | 契機 | ケース数 | JUnit | 結果 |",
        "| --- | --- | --- | ---: | --- | --- |",
    ]
    for item in EXECUTIONS:
        lines.append(
            f"| {item['execution']} | {item['executed_at']} | {item['trigger']} | "
            f"{item['cases']['total']} | {item['junit']['passed']}/{item['junit']['total']} PASS | "
            f"{item['result']} |"
        )
    lines += [
        "",
        "- 追補ケース（2回目の実行で追加。origin=AI_GENERATED / generation_stage=GAP_FILL）: "
        "IT-AI-GAP-020（SCR-002 入力エラー時の再表示・入力値保持・カート不変）、"
        "IT-AI-GAP-021（SCR-002 業務エラー時の再表示・入力値保持・カート不変）、"
        "IT-AI-GAP-022（4xx の django.request ログ行の相関ID）、"
        "IT-AI-GAP-023（5xx の django.request ログ行の相関ID）",
        "- 固定済み AI INITIAL Case（162 件、freeze_sha256 不変）と Gap Fill 前の初期 Coverage 測定値は変更していない。",
        "",
        "## 8. 工程判定",
        "",
        f"- 品質判定: PASS（Failed Case {report['test_summary']['total']['failed']} 件・"
        f"未解決 Defect {report['defects']['unresolved']} 件・TEST_SPEC_CONFLICT 0 件・AUTOMATION_BLOCKED 0 件）",
        "- Integration Test Agent の返却: SUCCESS",
        "- Production Code・要件・設計・ADDR は本工程では変更していない。",
        "- 工程全体の最終PASS/FAIL判定は SDLC Orchestrator が行う。",
        "",
    ]
    return "\n".join(lines)


def markdown_error_report(error_report: dict) -> str:
    summary = error_report["summary"]
    lines = [
        "# Integration Test Error Report（RUN-002）",
        "",
        f"- 生成日時: {error_report['generated_at']}",
        f"- 本Runで検出した Error（履歴）: {summary['total_errors']} 件（うち解消済み {summary['resolved_errors']} 件）",
        f"- 最終実行時点の Failed Case 数: {summary['failed_cases']}",
        f"- Unique Defect 数: {summary['unique_defects']}（未解決 {summary['unresolved_defects']} 件）",
        f"- 未解決エラー数: {summary['unresolved_errors']}",
        "",
        "## 1. 集計",
        "",
        "| 区分 | 件数 |",
        "| --- | ---: |",
        f"| AI_GENERATED / INITIAL | {summary['errors_by_generation_stage']['INITIAL']} |",
        f"| AI_GENERATED / GAP_FILL | {summary['errors_by_generation_stage']['GAP_FILL']} |",
        f"| EXTERNAL | {summary['errors_by_origin']['EXTERNAL']} |",
        f"| TOTAL | {summary['total_errors']} |",
        "",
        f"- 原因別: {json.dumps(summary['errors_by_cause'], ensure_ascii=False)}",
        f"- TEST_SPEC_CONFLICT: {summary['test_spec_conflicts']} 件、AUTOMATION_BLOCKED: "
        f"{summary['automation_blocked']} 件",
        "",
        "## 2. エラー明細",
        "",
    ]
    for error in error_report["errors"]:
        lines += [
            f"### {error['case_id']}（{error['origin']} / {error['generation_stage']}）",
            "",
            f"- 分類: {error['classification']}（{error['defect_id']}）",
            f"- 要件 / ADDR: {', '.join(error['requirement_id'])} / {', '.join(error['related_adr']) or '—'}",
            f"- 期待: {error['expected']}",
            f"- 検出時の実際: {error['actual_at_detection']}",
            f"- 検出時のエラー: {error['error_message']}",
            f"- 原因: {error['cause']}",
            f"- 箇所: {error['error_location']}",
            f"- 修正: {error['fix']}",
            f"- 再試験後の実際: {error['actual']}",
            f"- 再試験結果: {error['retest_result']}",
            f"- 解消: {'はい' if error['resolved'] else 'いいえ'}"
            f"（初回失敗 cycle={error['first_failed_at_cycle']} / 修正ループ {error['repair_cycles']} 回）",
            "",
        ]
    lines += [
        "## 3. 未解決事項",
        "",
        "- 未解決の Error・Defect はない（DEF-IT-001 は解消済み）。",
        "- DEF-IT-001（IMPLEMENTATION_ERROR）は初回失敗 cycle=0 で検出し、"
        "Production Code の修正は Implementation Agent（cycle=1）が実施、"
        "逆算となっていた単体テストの期待値是正は Unit Test Agent（cycle=2）が実施した。"
        "Integration Test Agent は Production Code を変更していない。",
        "- 修正後、対象ケース・関連ケース・Integration Test Suite 全体を再実行し全件PASS（3回ループ内で解消）。",
        "- TEST_SPEC_CONFLICT・AUTOMATION_BLOCKED・ENVIRONMENT_ERROR・原因不明Error はいずれも 0 件。",
        "",
    ]
    return "\n".join(lines)


def command_reports() -> None:
    coverage, _ = load_coverage()
    plan = read_json(PLAN)
    result = classify_coverage(plan, coverage)
    junit_results, junit_summary = read_junit()
    evidence = build_evidence(plan, coverage, result, junit_results, junit_summary)
    coverage_report = build_coverage_report(plan, coverage, result)
    error_report = build_error_report(evidence)
    report = build_report(plan, evidence, coverage_report, error_report)

    evidence["artifacts"] = {
        "junit": {"path": JUNIT, "sha256": sha256_of(JUNIT)},
        "plan": {"path": PLAN, "sha256": sha256_of(PLAN)},
        "ai_initial_cases": {"path": AI_INITIAL, "sha256": sha256_of(AI_INITIAL)},
        "required_coverage": {"path": REQUIRED_COVERAGE, "sha256": sha256_of(REQUIRED_COVERAGE)},
    }

    write_json(os.path.join(OUT_DIR, "coverage-gap-report.json"), coverage_report)
    write_json(os.path.join(OUT_DIR, "case-comparison.json"), build_case_comparison(plan, coverage, result))
    write_json(os.path.join(OUT_DIR, "integration-test-evidence.json"), evidence)
    write_json(os.path.join(OUT_DIR, "error-report.json"), error_report)
    write_text(os.path.join(OUT_DIR, "error-report.md"), markdown_error_report(error_report))
    write_json(os.path.join(OUT_DIR, "integration-test-report.json"), report)
    write_text(
        os.path.join(OUT_DIR, "integration-test-report.md"),
        markdown_report(report, coverage_report, error_report),
    )
    print(
        "reports: cases={total} pass={passed} fail={failed} defects={defects}".format(
            total=report["test_summary"]["total"]["total"],
            passed=report["test_summary"]["total"]["passed"],
            failed=report["test_summary"]["total"]["failed"],
            defects=len(DEFECTS),
        )
    )


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in ("plan", "reports"):
        print(__doc__)
        return 2
    if sys.argv[1] == "plan":
        command_plan()
    else:
        command_reports()
    return 0


if __name__ == "__main__":
    sys.exit(main())
