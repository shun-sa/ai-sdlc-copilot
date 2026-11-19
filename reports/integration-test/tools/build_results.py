"""Step 24〜41：結合試験の実行結果（JUnit）から Evidence・Error Report・Integration Test Report を作る。

python reports/integration-test/tools/build_results.py

- 入力：integration-test-plan.json（実行直前に固定した計画）、junit.xml（実行直後の結果）、trace-execution.json、
  unit-test-evidence.json（Requirement→Implementation→Unit Test の連鎖）、coverage-gap-report.json、case-comparison.json。
- 結果未取得を PASS にしない。FAIL は原因分類（Integration Test Policy の error_classification）とともに記録する。
- 既知の未解決（UNRESOLVED-*）は新しい3回ループにせず、要件どおりの期待値で FAIL のまま記録する。
"""

import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import nfr_scope  # noqa: E402
OUT = HERE.parent
ROOT = HERE.parents[2]
RUN_ID = "RUN-AOBA-EC-1118"
EXECUTION_EVENT = "it-exec-7"
PLAN_EVENT = "it-plan-8"
RESULT_EVENT = "it-result-7"

# 本対応：FULL Traceability C10 の差し戻し（UNRESOLVED-e1d9dfe900863622、修正 cycle=2/3）
TRACE_C2_CASES = tuple(f"GF-{n:03d}" for n in range(59, 74))
TRACE_C2_FIXES = [
    ("TRACE-FULL-C10", "FAIL(FULL)",
     "cycle=1/3 の後も要件→テスト未到達の NFR 38件の要件本文・測定条件・検証方法・代替確認を読み直し、Required Coverage Revision 5"
     "（RC-149〜RC-163）と AI GAP_FILL GF-059〜GF-073 を追加。開発環境の PC（Windows 11）にインストール済みの Edge・Chrome での全画面の"
     "表示・代表操作・表示完了時間、3年後データ量・同時155/310仮想利用者の参考計測、使い捨て PostgreSQL 16 での pg_dump/pg_restore による"
     "取得・復元・業務再開と更新・切戻し、開発時の公開脆弱性情報（OSV）との照合、保存データ・ログの出力先・監査ログの削除経路・個人情報の"
     "出力・全画面/全 API の簡易な動的診断・HTTPS 以外の拒否・在庫数量の反映の機械確認で、25件を PARTIAL_IT として確認（合格扱いにしない）。"
     "検証したケースの要件 ID だけを trace に付与し、確かめられる観点が無い 13件（NOT_VERIFIED 10・NOT_APPLICABLE 3）は cycle=2/3 の"
     "再評価の記録とともに維持"),
]
TRACE_C2_TRIAL_TEST_ERRORS = [
    ("GF-059", "購入者のログインフォームをエラー画面（SCR-901）の表示中に送信し、カートに入れるフォームを商品詳細を表示せずに送信していた"
     "（試験手順の誤り）",
     "app/tests/integration/test_it_gap_fill_nfr_browser.py::test_gf_059_browser_compatibility",
     "ログイン画面・商品詳細を表示してからフォームを送信するよう修正（全画面の表示・代表操作・横スクロールなしの期待値は変更なし）"),
    ("GF-068", "LOG-05 を manage.py の起動経路（execute_from_command_line）で発生させたため、ログ設定の読み直しで捕捉用のハンドラーが外れ、"
     "LOG-05 を捕捉できなかった（試験コードの誤り）",
     "app/tests/integration/test_it_gap_fill_nfr_ops.py::test_gf_068_application_log_output",
     "初期データ一括投入を call_command で実行するよう修正（LOG-01〜03・05・06 の出力の期待値は変更なし）"),
]

# 前サイクル：FULL Traceability C10 の差し戻し（UNRESOLVED-e1d9dfe900863622、修正 cycle=1/3。it-exec-5）
# 正式実行で検出した TEST_ERROR（本サイクル内で試験コードを修正し、次の正式実行で対象・関連・全体を再実行する）
FORMAL_TEST_ERRORS = {
    "GF-062": {
        "detected_in": "it-exec-6",
        "cause": "仮想利用者（_Buyer）がカートのクーポンの適用状態を応答から同期せず、カートの明細を全て削除した時点で「クーポンなし」と"
        "みなしていた。カートの明細の削除ではクーポンは外れない（carts.services.delete_item）ため、適用中のカートへ再びクーポン適用を"
        "要求し、業務エラー（E-024-05 クーポンは1注文につき1枚まで、422）を2件発生させた。測定条件の「業務エラーとならない条件で要求する」"
        "を試験側が満たしていなかった（試験コードの誤り。Production Code の不具合ではない）",
        "location": "app/tests/integration/test_it_gap_fill_nfr_perf.py::_Buyer（_update の cart_delete・coupon_apply）",
        "fix": "カートの応答（明細追加・数量変更・削除・クーポン適用/解除・カート照会）の coupon からクーポンの適用状態を同期するよう修正"
        "（業務エラー0件・システムエラー0件・95パーセンタイルの期待値は変更なし）",
    },
}

TRACE_ISSUE = "UNRESOLVED-e1d9dfe900863622"
TRACE_FIX_CASES = tuple(f"GF-{n:03d}" for n in range(44, 59))
TRACE_FIXES = [
    ("TRACE-FULL-C10", "FAIL(FULL)",
     "Policy require_test_for の NFR のうち要件→テスト未到達の 60件（NOT_VERIFIED 48・NOT_APPLICABLE 12）の要件本文・測定条件・検証方法・"
     "根拠を読み直し、Required Coverage Revision 4（RC-134〜RC-148）と AI GAP_FILL GF-044〜GF-058 を追加。「該当なし」の 9件は根拠の"
     "前提（バッチ・ファイルアップロード・多要素認証・アカウントロック・パスワード変更・送信元単位の制限・外部決済・特定商取引法の表記が"
     "無いこと）だけを NOT_APPLICABLE_PREMISE_IT として確認、構成・設定レビュー／静的解析の 13件はリポジトリ内で確かめられる部分だけを"
     "PARTIAL_IT として確認（合格扱いにしない）。検証したケースの要件 ID だけを trace に付与し、残りは再評価の記録とともに"
     "NOT_VERIFIED・NOT_APPLICABLE を維持"),
    ("QR-FULL-1118-001", "LOW",
     "nfr-verification-scope の件数表記を、一覧の件数（92）・差し戻し時点の FULL 監査の C10 の NFR 件数・本対応後の未到達件数に分けて"
     "記録し、basis・md・Report の「C10 の NFR 92件」の表記を修正"),
]
TRACE_TRIAL_TEST_ERRORS = [
    ("GF-050", "Dockerfile に開発用サーバーが無いことを、コメント行（「runserver を起動構成に含めない」）を含む全文で判定していた"
     "（試験コードの判定対象の誤り）",
     "app/tests/integration/test_it_gap_fill_nfr_config.py::test_gf_050_compose_single_start_gunicorn",
     "コメントを除く Dockerfile の命令行で判定するよう修正（起動定義に runserver を含まないという期待値は変更なし）"),
]

# 本サイクル（TEST_ERROR 修正 cycle=3/3）で対応した Quality 再レビューの指摘
CYCLE3_FIXES = [
    ("QR-IT-1118-R2-001", "LOW",
     "GF-034 の title（integration-test-plan.json）と試験関数 test_gf_034_double_submit_place_pay の docstring を「処理完了前の繰り返し操作」から"
     "実際の手順「先着の応答後の同じ送信トークンでの逐次の再送」（処理中の同時再送は GF-039〜GF-043）に修正。"
     "自己点検（全104件の title と試験関数の docstring・試験手順の突合）で、GF-002 の試験コード内の注記（「処理完了前の繰り返し操作は"
     "先着の応答を受け取る前と同じ Cookie・フォーム値で送られる」）も逐次再送の実態に合わせて修正。他の食い違いはなし"
     "（AI INITIAL の IT-050・IT-026 は「二重送信」「再送信」で実装と一致、変更なし）。判定・期待値・Coverage は変更なし"),
]

# 前サイクル（TEST_ERROR 修正 cycle=2/3）で対応した Quality 再レビューの指摘
CYCLE2_FIXES = [
    ("QR-IT-1118-R1-001", "MEDIUM",
     "Required Coverage Revision 3（RC-129〜RC-133、NFR-US-10・ADDR-004 4.4 の検証方法・テスト行から導出）を追加し、GAP_FILL GF-039〜GF-043 で"
     "先着が送信トークンのアドバイザリロックを保持して業務処理中に同じトークンの後着を別接続から送り、後着のロック待ち（pg_locks）を確認したうえで、"
     "支払（承認・否認）・先着 E-031-08／結果の記録前の中断・注文確定・カートに入れる・ログイン（先着 E-002-02）の反映・決済要求・監査ログが1回分、"
     "後着の通知が ADDR-004 DD-013 どおりであることを確認。GF-034 の前提を実際の手順（先着の応答後の逐次再送）に修正し、"
     "nfr-verification-scope の NFR-US-10 を GF-039〜GF-043 の実行結果で更新（PASS の場合だけ counts_as_quality_pass=true）"),
]

# TEST_ERROR 修正 cycle=2/3 の試行実行（一時 JUnit。正式結果ではない）で検出し本工程内で修正した TEST_ERROR
CYCLE2_CASES = ("GF-039", "GF-040", "GF-041", "GF-042", "GF-043")
NFR_US10_CASES = (*CYCLE2_CASES, "GF-034", "IT-050", "GF-002", "GF-003")
CYCLE2_TRIAL_TEST_ERRORS = [
    ("GF-039", "送信トークンの記録の確認で、同じ操作種別（order_pay）の記録が試験全体で1件と仮定していた（承認・否認の2注文で2件。試験コードの誤り）",
     "app/tests/integration/test_it_gap_fill_inflight.py::test_gf_039_inflight_repeat_pay_approved_declined",
     "対象トークン（操作種別＋照合値）の記録が1件であることだけを確認するよう修正（期待値は変更なし）"),
    ("GF-040", "システムエラー画面の文言を「システムエラーが発生しました。」（句点付き）で照合したが、画面は見出し（句点なし）と本文に分けて表示する"
     "（試験コードの照合文字列の誤り）",
     "app/tests/integration/test_it_gap_fill_inflight.py::test_gf_040_inflight_repeat_pay_system_error_and_interrupted",
     "ERR-08 の本文「時間をおいて再度操作してください。解消しない場合は当社までお問い合わせください。」と 500 で照合（期待値は変更なし）"),
]

# 前サイクル（TEST_ERROR 修正 cycle=1/3）で対応した INTEGRATION_TEST Scope Assurance の指摘
SCOPE_ASSURANCE_FIXES = [
    ("QR-IT-1118-001", "MEDIUM", "RC-105 を追加し GF-012（管理者キャンセル×支払、10試行＋両順序の固定、(a)(b) の Then 全項目）"),
    ("QR-IT-1118-002", "MEDIUM", "RC-106 を追加し GF-013（来訪者の「カートに入れる」→SCR-004→ログイン後 SCR-002、カート・在庫不変）"),
    ("QR-IT-1118-003", "MEDIUM", "RC-107・RC-108 を追加し GF-014（支払要求の識別子で LOG-01〜03・06 を抽出、連携エラー時の LOG-02）・"
     "GF-015（模擬決済が受けた要求4項目・外部通信0件・1秒以内）"),
    ("QR-IT-1118-004", "MEDIUM", "RC-109〜RC-111 を追加し GF-016（10並列×10回・注文番号の一意とコミット順の増加）・GF-017（障害後の欠番）・"
     "GF-018（--reset 後の採番・識別子の非巻き戻し）"),
    ("QR-IT-1118-005", "LOW", "GF-019〜GF-021（IT-042〜044 の Then の残り：履歴件数・順序・実行者区分・後着の通知文言・出荷日時/伝票番号・決済記録、"
     "AC の10試行）を supplemental として追加"),
    ("QR-IT-1118-006", "LOW", "GF-010・GF-011 の notes を INITIAL の確認漏れの補完（supplemental）に修正し、Revision 1 の Initial Coverage Rate に"
     "過大宣言分が含まれる旨を coverage-gap-report に注記（値は変更しない）"),
    ("SR-IT-R1-001", "LOW", "GF-002 に再送ブラウザのログイン状態なしの確認を追加、GF-018 で --reset 後の画面セッションの無効化を確認"),
    ("TRACE-C10", "FAIL(FULL)", "Required Coverage Revision 2 に結合試験で自動検証できる NFR（RC-112〜RC-128）を追加し GF-022〜GF-038 で検証。"
     "検証できない NFR は nfr-verification-scope.json に未検証・理由・検証すべき工程として記録"),
]

KNOWN_UNRESOLVED = {
    "UNRESOLVED-6de5eec64599b907": "SEC-IMPL-001 NUL文字入力でDB DataError→500(NFR-SC-04)、charset=undefined/idna で500、002 compose公開範囲（原因工程 IMPLEMENTATION）",
    "UNRESOLVED-32af0f4a0ca9c80f": "SEC-REQ-001..004（原因工程 REQUIREMENTS。本工程の期待値はこの未決のまま現行要件どおり）",
    "UNRESOLVED-0b5694db22a0bead": "SR-ARCH-001 本番デバッグ無効化/環境別設定の設計・ADDR引渡し漏れ（原因工程 ARCHITECTURE）",
    "UNRESOLVED-60a549ca11f16034": "QR-ARCH-001 Task依存矛盾、002 FR-060削除後のログイン状態無効化の引渡し漏れ（原因工程 ARCHITECTURE）",
    "UNRESOLVED-34471205dd0539bc": "expected-fr.txt の FR-OUT-01〜16 の EXCLUDE 書式が trace_check C12 と不整合（原因工程 IMPLEMENTATION→REQUIREMENTS）",
}

# 最終実行で FAIL したケースの原因分類と箇所（JUnit の失敗内容・Production Code の読取りで特定。推測で断定しない）
FAILURE_ANALYSIS = {
    "IT-058": {
        "defect_id": "IT-DEF-001",
        "classification": "IMPLEMENTATION_ERROR",
        "known_issue": "UNRESOLVED-6de5eec64599b907",
        "expected": "Content-Type の charset が復号に使えない指定（undefined・idna）で非 ASCII のクエリを伴う要求も、"
        "rot13 と同じく 400 入力エラーとし、500 にしない（NFR-SC-04、ADDR-001 4.3 の7、RC-100）",
        "cause": "config.wsgi.application が呼ぶ common.middleware.is_unusable_charset は codecs の _is_text_encoding が偽の"
        "符号化方式（rot13 等）だけを除外し、テキスト用として登録されているが入力を復号できない 'undefined'・'idna' を通過させる。"
        "このため Django の WSGIRequest 生成時（クエリ文字列の復号）に UnicodeError となり、RequestCharsetMiddleware・"
        "WebExceptionMiddleware を経ずにアプリケーション外へ例外が送出される（AP サーバーでは 500、LOG-03 も出力されない）",
        "error_location": {
            "layer": "WSGI 入口・共通ミドルウェア",
            "files": ["app/config/wsgi.py", "app/common/middleware.py"],
            "symbols": ["config.wsgi.application", "common.middleware.is_unusable_charset"],
            "api": "全要求（/api/products/、/ ほか。Content-Type に charset=undefined／idna とクエリを伴う GET）",
            "database": "該当なし",
        },
        "recommended_route": "IMPLEMENTATION",
        "fix": "Production Code は変更していない（Integration Test Agent の責務外）。既知の未解決 UNRESOLVED-6de5eec64599b907 "
        "のため新しい3回ループにせず、IMPLEMENTATION_FIX_REQUIRED として親へ返す。修正候補：is_unusable_charset で空文字列・"
        "非 ASCII を実際に復号して失敗する指定も入力エラーとする",
    }
}

# 実装中の試行実行（junit を一時ファイルへ出力。正式な結果ではない）で検出し本工程内で修正した TEST_ERROR
TRIAL_TEST_ERRORS = [
    ("IT-020", "固定した現在日時（2027年）より前の実時刻で発行した Bearer が有効期限切れとなり 401（試験データの不備）",
     "app/tests/integration/test_it_cart.py::test_it_020_coupon_apply_validity_recalc_remove",
     "固定日時ごとにログイン状態を発行し直すよう試験手順を修正（期待値は変更なし）"),
    ("IT-031", "注文詳細の coupon に ADDR-001 R-4 の discount_type_label があるのに完全一致で比較していた（期待値の記述誤り）",
     "app/tests/integration/test_it_orders.py::test_it_031_history_and_detail_contents",
     "R-4 どおり値と _label の両方を確認する比較に修正（要件の期待値に合わせた。弱体化なし）"),
    ("IT-051", "manage.py 実行（run_from_argv）が終了時に DB 接続を閉じ、ロールバック方式の試験トランザクションが失われた（試験環境の不備）",
     "app/tests/integration/test_it_initial_data.py::test_it_051_load_then_login_and_listings",
     "コマンドを実行するケースを transaction=True（コミット方式、ADDR-011 DD-010 と同じ）に変更"),
    ("IT-052", "同上（コマンド終了時の DB 接続の切断）", "app/tests/integration/test_it_initial_data.py::test_it_052_reset_deletes_all_and_invalidates_tokens",
     "transaction=True に変更"),
    ("IT-053", "同上（コマンド終了時の DB 接続の切断）", "app/tests/integration/test_it_initial_data.py::test_it_053_violations_reported_nothing_loaded",
     "transaction=True に変更"),
    ("IT-054", "同上（コマンド終了時の DB 接続の切断）", "app/tests/integration/test_it_initial_data.py::test_it_054_argument_read_and_format_errors",
     "transaction=True に変更"),
    ("GF-009", "同上（コマンド終了時の DB 接続の切断）", "app/tests/integration/test_it_gap_fill.py::test_gf_009_seed_file_loadable",
     "transaction=True に変更"),
    ("GF-002", "二重送信の再現で、先着の応答で更新された CSRF Cookie を後着に使い 403（二重送信は先着の応答前の Cookie で送られる）",
     "app/tests/integration/test_it_gap_fill.py::test_gf_002_web_login_double_submit_same_token",
     "先着の応答前の Cookie を複製したクライアントから後着を送るよう再現手順を修正（期待値は変更なし）"),
    ("IT-058", "ASCII だけのクエリでは idna で復号でき『復号に使えない指定』の条件を満たさず、試験データが条件を再現していなかった",
     "app/tests/integration/test_it_cross_cutting.py::test_it_058_wsgi_unusable_charset_with_query",
     "非 ASCII（UTF-8 のあ）を含むクエリに変更（期待値 400 は変更なし）。修正後は IT-DEF-001（既知の未解決）として FAIL"),
]

# TEST_ERROR 修正 cycle=1/3 の試行実行（一時 JUnit。正式結果ではない）で検出し本工程内で修正した TEST_ERROR
CYCLE1_TRIAL_TEST_ERRORS = [
    ("GF-034", "使用済みトークンの注文確定の後着に先着と同じ遷移先を期待していたが、ADDR-004 DD-010・DD-013 では注文確定は省略対象外で"
     "再判定の結果（カートが空、AC-UC-006-021）を通知する（期待値の導出誤り）",
     "app/tests/integration/test_it_gap_fill_flows.py::test_gf_034_double_submit_place_pay",
     "後着はカートへ遷移（cart_empty）と ADDR-004 どおりに修正。注文1件の確認は変更なし（弱体化なし）"),
    ("GF-028", "ログイン失敗の種類を error.reason で比較していた（ADDR-001 の封筒では type=authentication_failed、reason は null）",
     "app/tests/integration/test_it_gap_fill_nfr_web.py::test_gf_028_auth_means",
     "error.type で比較するよう修正（2つの失敗の本文が同一であることの確認は変更なし）"),
    ("GF-024", "注文を含む定義ファイルの拒否（監査ログに失敗1件）より前に監査ログを記録し、移行リハーサルの実行で1件増加の判定に失敗を含めていた",
     "app/tests/integration/test_it_gap_fill_nfr_batch.py::test_gf_024_vdc04_rehearsal",
     "拒否の失敗1件を別に確認し、--reset の実行直前の監査ログに対して1件増加を判定するよう修正"),
]


def read(name: str) -> dict:
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def write(name: str, data: dict) -> None:
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_junit(path: Path) -> tuple[dict, dict]:
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    meta = {k: suites[0].get(k) for k in ("name", "tests", "failures", "errors", "skipped", "time", "timestamp", "hostname")}
    results = {}
    for case in root.iter("testcase"):
        status, message = "PASS", None
        for tag, label in (("failure", "FAIL"), ("error", "ERROR"), ("skipped", "SKIPPED")):
            node = case.find(tag)
            if node is not None:
                status = label
                message = (node.get("message") or "") + "\n" + (node.text or "")
                break
        results[case.get("name")] = {
            "classname": case.get("classname"),
            "name": case.get("name"),
            "time": float(case.get("time") or 0),
            "status": status,
            "message": message,
        }
    return meta, results


def runtime_versions() -> dict:
    code = (
        "import json,platform,importlib.metadata as m;"
        "print(json.dumps({'python':platform.python_version(),**{d:m.version(d) for d in "
        "['django','djangorestframework','psycopg','psycopg-binary','pytest','pytest-django','ruff']}}))"
    )
    out = subprocess.run([str(ROOT / ".venv" / "Scripts" / "python.exe"), "-c", code], capture_output=True, text=True)
    return json.loads(out.stdout) if out.returncode == 0 else {"error": "version lookup failed"}


def summarize(cases: list[dict]) -> dict:
    total = len(cases)
    passed = sum(1 for c in cases if c["result"] == "PASS")
    failed = sum(1 for c in cases if c["result"] in ("FAIL", "ERROR"))
    blocked = sum(1 for c in cases if c["result"] in ("BLOCKED", "NOT_RUN", "SKIPPED"))
    return {"total": total, "passed": passed, "failed": failed, "blocked": blocked}


def main() -> None:
    now = datetime.now(UTC).isoformat(timespec="seconds")
    plan = read("integration-test-plan.json")
    gap = read("coverage-gap-report.json")
    comparison = read("case-comparison.json")
    trace_exec = read("trace-execution.json")
    junit_meta, junit = parse_junit(OUT / "junit.xml")
    unit = json.loads((ROOT / "reports/unit-test/unit-test-evidence.json").read_text(encoding="utf-8"))
    unit_by_req = {item["requirement"]: item for item in unit.get("requirement_coverage", [])}

    case_results, traceability = [], []
    for case in plan["cases"]:
        test_name = case["automated_test"].split("::")[1]
        run = junit.get(test_name)
        if run is None:
            result, message, elapsed, classification = "NOT_RUN", "JUnit に結果がない", None, "ENVIRONMENT_ERROR"
        else:
            result, message, elapsed = run["status"], run["message"], run["time"]
            classification = FAILURE_ANALYSIS.get(case["case_id"], {}).get("classification") if result != "PASS" else None
            if result != "PASS" and case["case_id"] in FORMAL_TEST_ERRORS:
                classification = "TEST_ERROR"
        analysis = FAILURE_ANALYSIS.get(case["case_id"]) if result != "PASS" else None
        actual = "期待結果どおり（全アサーション成功）" if result == "PASS" else (message or "").strip().splitlines()[0][:600]
        case_results.append(
            {
                "case_id": case["case_id"],
                "origin": case["origin"],
                "generation_stage": case.get("generation_stage"),
                "title": case["title"],
                "requirement_id": case["requirement_id"],
                "related_adr": case["related_adr"],
                "integration_point": case["integration_point"],
                "criterion": case["criterion"],
                "expected_result": case["expected_result"],
                "actual_result": actual,
                "result": result,
                "classification": classification,
                "known_issue": analysis.get("known_issue") if analysis else None,
                "defect_id": analysis.get("defect_id") if analysis else None,
                "execution_time_seconds": elapsed,
                "error_message": None if result == "PASS" else (message or "").strip()[:2000],
                "automated_test": case["automated_test"],
                "junit": {"classname": run["classname"], "name": run["name"]} if run else None,
            }
        )
        reqs = [r.strip() for r in re.split(r"[,\s]+", case["requirement_id"]) if r.strip()]
        implementation, unit_tests = [], []
        for req in reqs:
            entry = unit_by_req.get(req)
            if entry:
                implementation += [f"{i['path']}::{i['symbol']}" for i in entry.get("implementation", [])]
                unit_tests.append(
                    {
                        "requirement": req,
                        "unit_tests": len(entry.get("tests", [])),
                        "unit_failed": sum(1 for t in entry.get("tests", []) if t.get("result") != "PASS"),
                    }
                )
        traceability.append(
            {
                "case_id": case["case_id"],
                "origin": case["origin"],
                "generation_stage": case.get("generation_stage"),
                "requirement_id": case["requirement_id"],
                "related_adr": case["related_adr"],
                "implementation": sorted(set(implementation)),
                "unit_test": unit_tests or "単体テストの要件対応なし（NFR 等は reports/unit-test/unit-test-evidence.json の criteria を参照）",
                "integration_test": case["automated_test"],
                "integration_point": case["integration_point"],
                "result": result,
            }
        )

    def stage_cases(origin: str, stage: str | None) -> list[dict]:
        return [c for c in case_results if c["origin"] == origin and (stage is None or c["generation_stage"] == stage)]

    summary = {
        "ai_initial": summarize(stage_cases("AI_GENERATED", "INITIAL")),
        "ai_gap_fill": summarize(stage_cases("AI_GENERATED", "GAP_FILL")),
        "external": {"provided": False, **summarize(stage_cases("EXTERNAL", None))},
        "total": summarize(case_results),
    }

    defects = []
    for case_id, info in FAILURE_ANALYSIS.items():
        detected = [c for c in case_results if c["case_id"] == case_id and c["result"] != "PASS"]
        if not detected:
            continue
        origins = {c["origin"] for c in detected}
        source = "COMMON_DEFECT" if origins == {"AI_GENERATED", "EXTERNAL"} else (
            "AI_ONLY_DEFECT" if "AI_GENERATED" in origins else "EXTERNAL_ONLY_DEFECT")
        defects.append(
            {
                "defect_id": info["defect_id"],
                "classification": info["classification"],
                "known_issue": info["known_issue"],
                "detected_by_cases": [c["case_id"] for c in detected],
                "detected_by_stage": {c["case_id"]: c["generation_stage"] for c in detected},
                "detection_source": source,
                "requirement_id": detected[0]["requirement_id"],
                "related_adr": detected[0]["related_adr"],
                "expected": info["expected"],
                "actual": detected[0]["actual_result"],
                "root_cause": info["cause"],
                "error_location_identifiable": True,
                "error_location": info["error_location"],
                "recommended_route": info["recommended_route"],
                "fix": info["fix"],
                "resolved": False,
                "loop": {"new_loop_started": False, "reason": "既知の未解決（3回修正済み）。後続工程の再検出として OBSERVE"},
                "rerun": {
                    "target_cases": "NOT_EXECUTED",
                    "related_cases": "NOT_EXECUTED",
                    "full_suite": "NOT_EXECUTED",
                    "reason": "Production Code の修正が行われていないため修正後の再試験は未実行（結果を PASS にしない）",
                },
            }
        )

    criteria = sorted(p.name.replace(".criterion.md", "") for p in (ROOT / ".github/skills/integration-test/criteria").glob("*.criterion.md"))
    criteria_coverage = []
    for criterion in criteria:
        rows = [c for c in case_results if c["criterion"] == criterion]
        failing = [c["case_id"] for c in rows if c["result"] != "PASS"]
        criteria_coverage.append(
            {
                "criterion": criterion,
                "applicable": bool(rows),
                "result": ("FAIL" if failing else "PASS") if rows else "NOT_APPLICABLE",
                "cases": len(rows),
                "failing_cases": failing,
                "reason": ("適用ケース " + ", ".join(c["case_id"] for c in rows)) if rows else "対象ケースなし",
            }
        )

    initial_metrics = gap["initial_metrics"]
    final_metrics = gap["final_metrics"]
    rev1 = gap["initial_metrics_revision1_frozen"]["metrics"]
    scope_counts = Counter(row[1] for row in nfr_scope.SCOPE)
    nfr_scope_summary = {k: scope_counts.get(k, 0) for k in nfr_scope.STATUSES}
    by_stage = Counter(stage for d in defects for stage in d["detected_by_stage"].values())
    experimental = {
        "ai_initial_case_count": summary["ai_initial"]["total"],
        "ai_gap_fill_case_count": summary["ai_gap_fill"]["total"],
        "external_case_count": summary["external"]["total"],
        "common_coverage_count": initial_metrics["common"],
        "ai_only_coverage_count": initial_metrics["ai_only"],
        "external_only_coverage_count": initial_metrics["external_only"],
        "missing_coverage_count": initial_metrics["missing"],
        "ai_initial_coverage_rate": initial_metrics["ai_initial_coverage_rate"],
        "external_coverage_rate": initial_metrics["external_coverage_rate"],
        "combined_initial_coverage_rate": initial_metrics["combined_initial_coverage_rate"],
        "final_coverage_rate": final_metrics["final_coverage_rate"],
        "ai_initial_defect_detection_count": by_stage.get("INITIAL", 0),
        "ai_gap_fill_defect_detection_count": by_stage.get("GAP_FILL", 0),
        "external_defect_detection_count": 0,
        "common_defect_count": sum(1 for d in defects if d["detection_source"] == "COMMON_DEFECT"),
        "ai_only_defect_count": sum(1 for d in defects if d["detection_source"] == "AI_ONLY_DEFECT"),
        "external_only_defect_count": sum(1 for d in defects if d["detection_source"] == "EXTERNAL_ONLY_DEFECT"),
    }

    failed_total = summary["total"]["failed"] + summary["total"]["blocked"]
    status = "SUCCESS" if failed_total == 0 and not defects else "IMPLEMENTATION_FIX_REQUIRED"
    versions = runtime_versions()
    evidence = {
        "run_id": RUN_ID,
        "execution_event_id": EXECUTION_EVENT,
        "generated_at": now,
        "status": status,
        "external_input": {
            "provided": False,
            "user_confirmed_without_external_cases": True,
            "standard_location_checked": "external-tests/integration-test/（存在しない。AI INITIAL 固定後に確認）",
            "confirmation_source": "SDLC Orchestrator からの external_cases_confirmed_absent: true（ユーザーが 2026-11-19 に"
            "「結合テストは外部取り込みなしで実施」と明示指示）。Integration Test Agent 自身は true にしていない",
            "normalizer": "normalize_external_test_cases.py --allow-none → reports/integration-test/external-test-cases.normalized.json",
        },
        "external_case_integrity": [],
        "precondition_unit_test": {
            "evidence": "reports/unit-test/unit-test-evidence.json",
            "status": unit.get("status"),
            "summary": unit.get("test_summary"),
            "note": "単体テストは既知の未解決（UNRESOLVED-6de5eec64599b907 ほか）を残したまま親が CONTINUE_WITH_UNRESOLVED で"
            "結合試験へ進めた。依存する結合ケースは要件どおりの期待値で実行し、失敗を FAIL のまま記録する",
        },
        "environment": {
            "production_environment_used": False,
            "identification": "ENV-IT（開発者 PC 上の使い捨て環境。外部インターネット・実決済サービスへ接続しない）",
            "runner": "reports/integration-test/tools/run_integration.py（PostgreSQL 16 コンテナ起動→pytest 1回→停止・削除）",
            "command": ".venv/Scripts/python.exe -m pytest -c app/pytest.ini --rootdir=. app/tests/integration -p no:cacheprovider "
            "-o junit_family=xunit2 --junitxml=reports/integration-test/junit.xml -W ignore::UserWarning -p no:logging --tb=short -q",
            "process_timeout_seconds": 3600,
            "settings": "tests.settings_test（MINICOMMERCE_ENV=development、MINICOMMERCE_DEV_FEATURES=true、秘密鍵は実行ごとの乱数）",
            "runtime": versions,
            "external_services": "決済サービス（模擬）はプロセス内（ADDR-008）。外部通信なし",
            "browsers": "GF-059・GF-060・GF-062：PC（Windows 11）にインストール済みの Microsoft Edge・Google Chrome をヘッドレスで起動し"
            "（一時プロファイル・背景通信停止）、live_server（127.0.0.1）の画面だけを表示。版は browser-reference.json",
            "pre_execution_fetch": "GF-064：実行前に tools/fetch_dependency_vulns.py で OSV・PyPI・ブラウザの最新安定版を取得"
            "（dependency-vulnerability-osv.json。パッケージ名と版だけを送信）。pytest・アプリケーションは外部へ接続しない",
            "reference_outputs": ["browser-reference.json", "performance-reference.json", "security-reference.json",
                                  "operations-reference.json", "recovery-reference.json", "dependency-vulnerability-osv.json"],
        },
        "database": {
            "used": True,
            "type": "PostgreSQL 16.16（docker image postgres:16 sha256:3950ad7c3148ca2175ef1b6c36c9efbf78957ae8fbe8b3a5d7c35af50500382f）",
            "strategy": "CONTAINER（docker run --rm、127.0.0.1 のランダムポートのみ公開、データ領域 tmpfs、実行終了時に停止・削除）",
            "test_database": "pytest-django が作成・破棄する test_minicommerce_it",
            "timeouts": {"connect": "PGCONNECT_TIMEOUT=10s", "statement_timeout": "60s", "lock_timeout": "30s",
                         "idle_in_transaction_session_timeout": "120s", "process": "3600s"},
            "credentials": "実行ごとの乱数（保存しない）",
            "production_database_used": False,
            "shared_database_used": False,
            "production_credentials_used": False,
            "production_data_used": False,
            "schema_reproducible": True,
            "schema_source": "Django migrations（pytest-django が試験用 DB に適用）",
            "isolation": "ロールバック方式（既定）。複数接続の同時実行試験と manage.py 実行ケースは transaction=True（ADDR-011 DD-010）で終了時に flush",
        },
        "junit": {"path": "reports/integration-test/junit.xml", "suite": junit_meta},
        "trace_execution": trace_exec,
        "test_summary": summary,
        "case_results": case_results,
        "defects": defects,
        "flaky_tests": [],
        "flaky_check": "it-exec-1 後：同時実行9ケースと時間依存ケース（IT-029・IT-050・IT-058・GF-002）を一時 JUnit へ3回再実行し同じ結果。"
        "cycle=1（it-exec-2 前）：追加した同時実行・時間依存の GAP_FILL（GF-002・GF-012・GF-014〜GF-017・GF-019〜GF-021・GF-034）を"
        "一時 JUnit へ3回再実行し、毎回全 PASS（非決定的な失敗なし）。"
        "cycle=2（it-exec-3 前）：追加した GF-039〜GF-043 と関連（GF-002・GF-003・GF-034・IT-050）の9件を一時 JUnit へ3回再実行し、毎回全 PASS。"
        "cycle=3（it-exec-4 前）：判定・期待値の変更なし（title・docstring・注記のみ）のため試行実行は行わず正式実行のみ。"
        f"{TRACE_ISSUE} cycle=1/3（it-exec-5 前）：追加した GF-044〜GF-058 を一時 JUnit へ2回実行し、修正後は全 PASS"
        "（同時実行・時間依存の判定を含まない）。"
        f"{TRACE_ISSUE} cycle=2/3（it-exec-6 前）：追加した GF-059〜GF-073 を一時 JUnit へ分けて実行（性能の GF-062・GF-063 は"
        "短縮した時間で1回、他は1〜2回）し、TEST_ERROR 2件の修正後は全 PASS。正式実行 it-exec-6（短縮なし）で GF-062 の TEST_ERROR"
        f"（業務エラー 422 が2件）を検出し、試験コードを修正して GF-061〜GF-063 を一時 JUnit へ1回（短縮）実行し全 PASS、{EXECUTION_EVENT} で"
        "全体を再実行（短縮なし：GF-062 300秒・GF-063 120秒）",
        "repair_cycle": {
            "issue_id": TRACE_ISSUE,
            "classification": "TEST_ERROR",
            "cycle": "2/3",
            "trigger": "FULL Traceability C10（cycle=1/3 後の FULL 監査）：Policy require_test_for の NFR のうち要件→テスト未到達 38件"
            "（AV-02/03/04/05/07/08/09/11/12、EN-06/13、LG-01/07、MG-05/06、OM-02/03/08/09/10/14/15/16、PF-03/04/05/06/11/13/14/15、"
            "SC-11/20/26/29、US-01/02/06）。親（SDLC Orchestrator）が INTEGRATION_TEST へ差し戻し",
            "fixes": [{"finding": f, "severity": s, "fix": x} for f, s, x in TRACE_C2_FIXES],
            "rerun": {
                "target_cases": "追加した GF-059〜GF-073 を正式実行で実行（it-exec-6 で TEST_ERROR となった GF-062 は試験コードの修正後に"
                f" {EXECUTION_EVENT} で再試験）",
                "related_cases": "GF-062 と同じ試験ファイル・負荷の部品を使う GF-061・GF-063 と、同じ連携点（画面・API・設定・ログ・監査ログ・"
                "初期データ一括投入・注文の状態遷移）の既存ケース（GF-022・GF-024・GF-026・GF-027・GF-031・GF-044〜GF-058・IT-056 ほか）",
                "full_suite": f"{EXECUTION_EVENT} で全 {len(case_results)} 件を実行",
            },
            "production_code_changed": False,
            "ai_initial_changed": False,
            "existing_assertions_changed": False,
            "nfr_verification_scope": nfr_scope_summary,
            "previous_cycles_of_this_issue": [
                {
                    "cycle": "1/3",
                    "trigger": "FULL Traceability C10：要件→テスト未到達 60件（NOT_VERIFIED 48・NOT_APPLICABLE 12）",
                    "fixes": [{"finding": f, "severity": s, "fix": x} for f, s, x in TRACE_FIXES],
                    "execution_event": "it-exec-5",
                    "added_cases": "GF-044〜GF-058",
                },
            ],
            "previous_loop": {
                "issue": "INTEGRATION_TEST の TEST_ERROR 修正ループ（Scope Assurance・Quality 再レビューの指摘。3回で終了）",
                "cycles": [
                    {
                        "cycle": "1/3",
                        "trigger": "INTEGRATION_TEST Scope Assurance（Quality QR-IT-1118-001〜006、Security SR-IT-R1-001、Traceability C10）",
                        "fixes": [{"finding": f, "severity": s, "fix": x} for f, s, x in SCOPE_ASSURANCE_FIXES],
                        "execution_event": "it-exec-2",
                    },
                    {
                        "cycle": "2/3",
                        "trigger": "Quality 再レビュー QR-IT-1118-R1-001（NFR-US-10 の処理中の繰り返し操作が未再現のまま VERIFIED_IT）",
                        "fixes": [{"finding": f, "severity": s, "fix": x} for f, s, x in CYCLE2_FIXES],
                        "execution_event": "it-exec-3",
                    },
                    {
                        "cycle": "3/3",
                        "trigger": "Quality 再レビュー QR-IT-1118-R2-001（LOW、GF-034 の title・docstring が逐次再送の実態と食い違い）",
                        "fixes": [{"finding": f, "severity": s, "fix": x} for f, s, x in CYCLE3_FIXES],
                        "execution_event": "it-exec-4",
                    },
                ],
            },
        },
        "criteria_coverage": criteria_coverage,
        "traceability": traceability,
        "coverage": {"initial_metrics": initial_metrics, "final_metrics": final_metrics, "comparison_summary": comparison["summary"]},
        "experimental_metrics": experimental,
        "known_unresolved_carried": KNOWN_UNRESOLVED,
        "implementation_trial_test_errors": [
            {"case_id": c, "classification": "TEST_ERROR", "cause": cause, "location": loc, "fix": fix, "resolved": True,
             "phase": "implementation_trial_run（it-exec-1 前）"}
            for c, cause, loc, fix in TRIAL_TEST_ERRORS
        ] + [
            {"case_id": c, "classification": "TEST_ERROR", "cause": cause, "location": loc, "fix": fix, "resolved": True,
             "phase": "cycle1_trial_run（it-exec-2 前）"}
            for c, cause, loc, fix in CYCLE1_TRIAL_TEST_ERRORS
        ] + [
            {"case_id": c, "classification": "TEST_ERROR", "cause": cause, "location": loc, "fix": fix, "resolved": True,
             "phase": "cycle2_trial_run（it-exec-3 前）"}
            for c, cause, loc, fix in CYCLE2_TRIAL_TEST_ERRORS
        ] + [
            {"case_id": c, "classification": "TEST_ERROR", "cause": cause, "location": loc, "fix": fix, "resolved": True,
             "phase": f"trace_c10_cycle1_trial_run（{TRACE_ISSUE}、it-exec-5 前）"}
            for c, cause, loc, fix in TRACE_TRIAL_TEST_ERRORS
        ] + [
            {"case_id": c, "classification": "TEST_ERROR", "cause": cause, "location": loc, "fix": fix, "resolved": True,
             "phase": f"trace_c10_cycle2_trial_run（{TRACE_ISSUE}、it-exec-6 前）"}
            for c, cause, loc, fix in TRACE_C2_TRIAL_TEST_ERRORS
        ] + [
            {"case_id": c, "classification": "TEST_ERROR", "cause": info["cause"], "location": info["location"],
             "fix": info["fix"], "resolved": next(r["result"] for r in case_results if r["case_id"] == c) == "PASS"
             and info["detected_in"] != EXECUTION_EVENT,
             "phase": f"formal_execution（{info['detected_in']}）"}
            for c, info in FORMAL_TEST_ERRORS.items()
        ],
        "snapshots": {
            "ai_initial": "experiment_recorder snapshot it-initial-1（AI_INITIAL）",
            "plan": ["it-plan-1（計画確定時）", "it-plan-2（テスト実装後・it-exec-1 直前）", "it-plan-3（cycle=1 の計画更新後・it-exec-2 直前）",
                     "it-plan-4（cycle=2 の計画更新後・it-exec-3 直前）", "it-plan-5（cycle=3 の計画更新後・it-exec-4 直前）",
                     f"it-plan-6（{TRACE_ISSUE} cycle=1/3 の計画更新後・it-exec-5 直前）",
                     f"it-plan-7（{TRACE_ISSUE} cycle=2/3 の計画更新後・it-exec-6 直前）",
                     f"{PLAN_EVENT}（{TRACE_ISSUE} cycle=2/3 の GF-062 の TEST_ERROR 修正後・{EXECUTION_EVENT} 直前）"],
            "result": ["it-result-1（it-exec-1 の結果）", "it-result-2（it-exec-2 の結果）", "it-result-3（it-exec-3 の結果）",
                       "it-result-4（it-exec-4 の結果）", "it-result-5（it-exec-5 の結果）",
                       "it-result-6（it-exec-6 の結果。IT-058・GF-062 が FAIL）",
                       f"{RESULT_EVENT}（本 Evidence、{EXECUTION_EVENT} の結果）"],
        },
    }
    write("integration-test-evidence.json", evidence)

    # --- Error Report ---
    errors = []
    for d in defects:
        for cid in d["detected_by_cases"]:
            case = next(c for c in case_results if c["case_id"] == cid)
            errors.append(
                {
                    "case_id": cid,
                    "origin": case["origin"],
                    "generation_stage": case["generation_stage"],
                    "phase": f"final_execution（{EXECUTION_EVENT}）",
                    "classification": d["classification"],
                    "defect_id": d["defect_id"],
                    "known_issue": d["known_issue"],
                    "requirement_id": case["requirement_id"],
                    "related_adr": case["related_adr"],
                    "expected": d["expected"],
                    "actual": case["actual_result"],
                    "cause": d["root_cause"],
                    "error_location_identifiable": True,
                    "error_location": d["error_location"],
                    "fix": d["fix"],
                    "retest": d["rerun"],
                    "resolved": False,
                }
            )
    plan_by_id = {c["case_id"]: c for c in plan["cases"]}
    trial_rows = [(row, "implementation_trial_run（一時 JUnit。正式結果ではない、it-exec-1 前）") for row in TRIAL_TEST_ERRORS]
    trial_rows += [(row, "cycle1_trial_run（一時 JUnit。正式結果ではない、it-exec-2 前）") for row in CYCLE1_TRIAL_TEST_ERRORS]
    trial_rows += [(row, "cycle2_trial_run（一時 JUnit。正式結果ではない、it-exec-3 前）") for row in CYCLE2_TRIAL_TEST_ERRORS]
    trial_rows += [(row, f"trace_c10_cycle1_trial_run（一時 JUnit。正式結果ではない、{TRACE_ISSUE}、it-exec-5 前）")
                   for row in TRACE_TRIAL_TEST_ERRORS]
    trial_rows += [(row, f"trace_c10_cycle2_trial_run（一時 JUnit。正式結果ではない、{TRACE_ISSUE}、it-exec-6 前）")
                   for row in TRACE_C2_TRIAL_TEST_ERRORS]
    for (cid, cause, loc, fix), phase in trial_rows:
        case = plan_by_id[cid]
        final = next(c for c in case_results if c["case_id"] == cid)["result"]
        errors.append(
            {
                "case_id": cid,
                "origin": case["origin"],
                "generation_stage": case.get("generation_stage"),
                "phase": phase,
                "classification": "TEST_ERROR",
                "requirement_id": case["requirement_id"],
                "related_adr": case["related_adr"],
                "expected": case["expected_result"],
                "actual": cause,
                "cause": cause,
                "error_location_identifiable": True,
                "error_location": {"layer": "Test Code", "files": [loc.split("::")[0]], "symbols": [loc.split("::")[1]]},
                "fix": fix,
                "retest": {"target_case": final, "full_suite": f"{EXECUTION_EVENT} で全{len(case_results)}件を実行"},
                "resolved": True,
            }
        )
    for cid, info in FORMAL_TEST_ERRORS.items():
        case = plan_by_id[cid]
        final = next(c for c in case_results if c["case_id"] == cid)
        current = info["detected_in"] == EXECUTION_EVENT
        errors.append(
            {
                "case_id": cid,
                "origin": case["origin"],
                "generation_stage": case.get("generation_stage"),
                "phase": f"final_execution（{EXECUTION_EVENT}）" if current else f"formal_execution（{info['detected_in']}）",
                "classification": "TEST_ERROR",
                "requirement_id": case["requirement_id"],
                "related_adr": case["related_adr"],
                "expected": case["expected_result"],
                "actual": final["actual_result"] if current else info["cause"],
                "cause": info["cause"],
                "error_location_identifiable": True,
                "error_location": {"layer": "Test Code", "files": [info["location"].split("::")[0]],
                                   "symbols": [info["location"].split("::")[1]]},
                "fix": info["fix"],
                "retest": {
                    "target_case": final["result"] if not current else "NOT_EXECUTED（修正後の正式実行で再試験）",
                    "related_cases": "同じ試験ファイルの GF-061・GF-063 を含む" if not current else "NOT_EXECUTED",
                    "full_suite": f"{EXECUTION_EVENT} で全{len(case_results)}件を実行" if not current else "NOT_EXECUTED",
                },
                "resolved": (not current) and final["result"] == "PASS",
            }
        )
    by_origin = Counter(e["origin"] for e in errors)
    by_cause = Counter(e["classification"] for e in errors)
    by_stage = Counter(f"{e['origin']}/{e.get('generation_stage') or '-'}" for e in errors)
    final_errors = [e for e in errors if e["phase"].startswith("final")]
    error_report = {
        "run_id": RUN_ID,
        "generated_at": now,
        "summary": {
            "total_errors": len(errors),
            "errors_by_origin": {"AI_GENERATED": by_origin.get("AI_GENERATED", 0), "EXTERNAL": by_origin.get("EXTERNAL", 0)},
            "errors_by_stage": dict(by_stage),
            "errors_by_cause": dict(by_cause),
            "final_execution": {
                "failed_cases": len(final_errors),
                "failed_cases_by_stage": {
                    "AI_GENERATED/INITIAL": sum(1 for e in final_errors if e["generation_stage"] == "INITIAL"),
                    "AI_GENERATED/GAP_FILL": sum(1 for e in final_errors if e["generation_stage"] == "GAP_FILL"),
                    "EXTERNAL": 0,
                },
                "unique_defects": len(defects),
                "unresolved_defects": sum(1 for d in defects if not d["resolved"]),
            },
            "test_errors_fixed_during_implementation": sum(1 for e in errors if e["classification"] == "TEST_ERROR"),
            "defect_detection": {
                "COMMON_DEFECT": experimental["common_defect_count"],
                "AI_ONLY_DEFECT": experimental["ai_only_defect_count"],
                "EXTERNAL_ONLY_DEFECT": experimental["external_only_defect_count"],
            },
        },
        "defects": defects,
        "errors": errors,
    }
    write("error-report.json", error_report)

    lines = [
        "# 結合試験 Error Report（RUN-AOBA-EC-1118）",
        "",
        f"- 生成: {now}（正式実行 {EXECUTION_EVENT}、JUnit: reports/integration-test/junit.xml）",
        f"- 正式実行の Failed Case: {len(final_errors)} 件（AI INITIAL {error_report['summary']['final_execution']['failed_cases_by_stage']['AI_GENERATED/INITIAL']}"
        f"・AI GAP_FILL {error_report['summary']['final_execution']['failed_cases_by_stage']['AI_GENERATED/GAP_FILL']}・EXTERNAL 0）",
        f"- Unique Defect: {len(defects)} 件（未解決 {error_report['summary']['final_execution']['unresolved_defects']} 件）",
        "- 検出元: COMMON_DEFECT 0 / AI_ONLY_DEFECT {0} / EXTERNAL_ONLY_DEFECT 0（External Case は未提供）".format(experimental["ai_only_defect_count"]),
        f"- 原因別（全 Error {len(errors)} 件）: " + "、".join(f"{k} {v}" for k, v in by_cause.items()),
        "",
        "## 正式実行で残った不具合",
        "",
    ]
    for d in defects:
        loc = d["error_location"]
        lines += [
            f"### {d['defect_id']}（{d['classification']}、既知 {d['known_issue']}）",
            "",
            f"- 検出ケース: {', '.join(d['detected_by_cases'])}（{d['detection_source']}）",
            f"- Requirement / ADR: {d['requirement_id']} / {d['related_adr']}",
            f"- 期待: {d['expected']}",
            f"- 実際: {d['actual']}",
            f"- 原因: {d['root_cause']}",
            f"- 箇所: {loc['layer']} — {', '.join(loc['files'])}（{', '.join(loc['symbols'])}）、API: {loc['api']}",
            f"- 対応: {d['fix']}",
            f"- 再試験: 対象 {d['rerun']['target_cases']}・関連 {d['rerun']['related_cases']}・全体 {d['rerun']['full_suite']}（{d['rerun']['reason']}）",
            f"- 推奨対応先: {d['recommended_route']}（新しい3回ループは開始しない）",
            "",
        ]
    lines += ["## 試行実行で検出し修正した TEST_ERROR（一時 JUnit。正式結果ではない）", "",
              "| Case | 時点 | 原因 | 箇所 | 修正 | 正式実行の結果 |", "|---|---|---|---|---|---|"]
    for e in errors:
        if e["classification"] == "TEST_ERROR":
            lines.append(f"| {e['case_id']} | {e['phase']} | {e['cause']} | {e['error_location']['files'][0]}::{e['error_location']['symbols'][0]} | {e['fix']} | {e['retest']['target_case']} |")
    (OUT / "error-report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # --- Integration Test Report ---
    report = {
        "run_id": RUN_ID,
        "generated_at": now,
        "status": status,
        "test_summary": summary,
        "case_counts": {"ai_initial": summary["ai_initial"]["total"], "ai_gap_fill": summary["ai_gap_fill"]["total"],
                        "external": 0, "total": summary["total"]["total"]},
        "coverage": {**initial_metrics, "final_coverage_rate": final_metrics["final_coverage_rate"],
                     "final_covered": final_metrics["covered"], "final_missing": final_metrics["missing"]},
        "coverage_gaps": gap["gaps"],
        "supplemental_gap_fill": gap.get("supplemental_gap_fill", []),
        "errors": error_report["summary"],
        "defects": defects,
        "criteria": criteria_coverage,
        "experimental_metrics": experimental,
        "external_input": evidence["external_input"],
        "known_unresolved_carried": KNOWN_UNRESOLVED,
        "repair_cycle": evidence["repair_cycle"],
        "initial_metrics_revision1_frozen": gap.get("initial_metrics_revision1_frozen"),
        "reports": sorted(p.name for p in OUT.glob("*.json")) + ["error-report.md", "integration-test-report.md",
                                                                 "nfr-verification-scope.md", "junit.xml"],
    }
    write("integration-test-report.json", report)

    s = summary
    md = [
        "# 結合試験 Report（RUN-AOBA-EC-1118）",
        "",
        f"- 状態: **{status}**（品質 PASS ではない。FAIL {summary['total']['failed']}件を FAIL のまま記録："
        + "、".join(
            f"{c['case_id']}（{c['classification']}"
            + (f"、既知 {c['known_issue']}" if c.get("known_issue") else "")
            + "）"
            for c in case_results
            if c["result"] != "PASS"
        )
        + "）",
        f"- 正式実行: {EXECUTION_EVENT}（{junit_meta.get('timestamp')}、{junit_meta.get('time')} 秒）、JUnit reports/integration-test/junit.xml、"
        f"trace 実行記録 {trace_exec.get('revision')}",
        "- External Case: 未提供（external-tests/ なし）。ユーザーの明示選択（external_cases_confirmed_absent: true）により外部取り込みなしで実施",
        "",
        "## 1. Test Summary",
        "",
        "| 区分 | 件数 | PASS | FAIL | BLOCKED |",
        "|---|---|---|---|---|",
        f"| AI_GENERATED / INITIAL | {s['ai_initial']['total']} | {s['ai_initial']['passed']} | {s['ai_initial']['failed']} | {s['ai_initial']['blocked']} |",
        f"| AI_GENERATED / GAP_FILL | {s['ai_gap_fill']['total']} | {s['ai_gap_fill']['passed']} | {s['ai_gap_fill']['failed']} | {s['ai_gap_fill']['blocked']} |",
        f"| EXTERNAL | {s['external']['total']} | {s['external']['passed']} | {s['external']['failed']} | {s['external']['blocked']} |",
        f"| TOTAL | {s['total']['total']} | {s['total']['passed']} | {s['total']['failed']} | {s['total']['blocked']} |",
        "",
        "## 2. Coverage 比較（Required Coverage {0}件＝Revision 1 の {1}件＋Revision 2〜4 の {2}件、Gap Fill 前の値）".format(
            initial_metrics["required"], rev1["required"], initial_metrics["required"] - rev1["required"]),
        "",
        f"- COMMON {initial_metrics['common']} / AI_ONLY {initial_metrics['ai_only']} / EXTERNAL_ONLY {initial_metrics['external_only']} / MISSING {initial_metrics['missing']}",
        f"- AI INITIAL Coverage Rate {initial_metrics['ai_initial_coverage_rate']}%、External Coverage Rate なし（未提供）、"
        f"Combined Initial {initial_metrics['combined_initial_coverage_rate']}%、Gap Fill 後 Final {final_metrics['final_coverage_rate']}%",
        f"- Revision 1（{rev1['required']}件）の固定値（initial-coverage-metrics.json、変更なし）: AI INITIAL {rev1['ai_initial_coverage_rate']}%、"
        f"MISSING {rev1['missing']}。この値には INITIAL の過大宣言分（RC-036・038・039・063・084・085・091）が含まれる",
        "",
        "## 3. Coverage Gap（MISSING → AI GAP_FILL）",
        "",
        "| Gap | Coverage | Requirement | 不足内容 | GAP_FILL |",
        "|---|---|---|---|---|",
    ]
    for g in gap["gaps"]:
        md.append(f"| {g['gap_id']} | {g['coverage_id']} | {g['requirement_id']} | {g['missing']} | {', '.join(g['filled_by_gap_fill_cases'])} |")
    md += ["", "INITIAL が宣言していたが一部条件を検証していなかった Coverage の補完（supplemental。Initial 値・分類は変更しない）:", ""]
    for sgf in gap.get("supplemental_gap_fill", []):
        md.append(f"- {sgf['case_id']}: {', '.join(sgf['coverage_ids'])}（INITIAL 宣言: {', '.join(sgf['initially_declared_by'])}）")
    md += [
        "",
        "## 4〜8. Error・Defect",
        "",
        f"- 正式実行の Error（Failed Case）: {len(final_errors)} 件、Unique Defect: {len(defects)} 件",
        f"- 原因別（実装中の TEST_ERROR を含む全 {len(errors)} 件）: " + "、".join(f"{k} {v}" for k, v in by_cause.items()),
        f"- AI / External 別: AI_GENERATED {by_origin.get('AI_GENERATED', 0)}、EXTERNAL {by_origin.get('EXTERNAL', 0)}",
        f"- COMMON_DEFECT {experimental['common_defect_count']} / AI_ONLY_DEFECT {experimental['ai_only_defect_count']} / EXTERNAL_ONLY_DEFECT {experimental['external_only_defect_count']}",
        "",
        "## 9〜12. 不具合の箇所",
        "",
    ]
    for d in defects:
        md.append(f"- {d['defect_id']}（{', '.join(d['detected_by_cases'])}、{d['classification']}、{d['known_issue']}）: "
                  f"{', '.join(d['error_location']['symbols'])} — {d['root_cause']}")
    md += [
        "",
        "## 13〜14. 修正結果・再試験結果",
        "",
        "- Production Code は変更していない（Integration Test Agent の責務外）。IT-DEF-001 は既知の未解決のため新しい3回ループを開始せず、"
        "IMPLEMENTATION_FIX_REQUIRED として親へ返す。修正後の対象・関連・全体の再試験は未実行（PASS としない）",
        f"- 試行実行で TEST_ERROR {sum(1 for e in errors if e['classification'] == 'TEST_ERROR')} 件を修正（it-exec-1 前 "
        f"{len(TRIAL_TEST_ERRORS)} 件、cycle=1 の it-exec-2 前 {len(CYCLE1_TRIAL_TEST_ERRORS)} 件、cycle=2 の it-exec-3 前 "
        f"{len(CYCLE2_TRIAL_TEST_ERRORS)} 件、{TRACE_ISSUE} cycle=1/3 の it-exec-5 前 {len(TRACE_TRIAL_TEST_ERRORS)} 件、"
        f"cycle=2/3 の it-exec-6 前 {len(TRACE_C2_TRIAL_TEST_ERRORS)} 件、正式実行 it-exec-6 で検出 {len(FORMAL_TEST_ERRORS)} 件。"
        "期待値の弱体化・ケース削除なし）。修正後の全体実行が正式実行 {0}".format(EXECUTION_EVENT),
        "",
        f"## FULL Traceability C10 の差し戻し（{TRACE_ISSUE}、修正 cycle=2/3。{EXECUTION_EVENT}）",
        "",
        "| 指摘 | 重大度 | 対応 |",
        "|---|---|---|",
        *[f"| {f} | {sev} | {x} |" for f, sev, x in TRACE_C2_FIXES],
        "",
        "- 追加 GAP_FILL: GF-059〜GF-073（Required Coverage Revision 5 の RC-149〜RC-163）。結果: "
        + "、".join(f"{c['case_id']} {c['result']}" for c in case_results if c["case_id"] in TRACE_C2_CASES),
        "- 参考計測・機械確認の記録: browser-reference.json・performance-reference.json・security-reference.json・"
        "operations-reference.json・recovery-reference.json・dependency-vulnerability-osv.json（いずれも合格扱いにしない PARTIAL_IT の根拠）",
        "- NFR の検証可否（nfr-verification-scope.json／.md）: 一覧 {0} 件の区分 ".format(len(nfr_scope.SCOPE))
        + " / ".join(f"{k} {v}" for k, v in nfr_scope_summary.items())
        + "。差し戻し時点の C10 の NFR 件数・本対応後の未到達件数は nfr-verification-scope.json の counts（PARTIAL_IT・"
        "NOT_APPLICABLE_PREMISE_IT・NOT_VERIFIED・NOT_APPLICABLE は合格扱いにしない）",
        "",
        f"## FULL Traceability C10 の差し戻し（{TRACE_ISSUE}、修正 cycle=1/3。it-exec-5）",
        "",
        "| 指摘 | 重大度 | 対応 |",
        "|---|---|---|",
        *[f"| {f} | {sev} | {x} |" for f, sev, x in TRACE_FIXES],
        "",
        "- 追加 GAP_FILL: GF-044〜GF-058（Required Coverage Revision 4 の RC-134〜RC-148）。結果（本実行）: "
        + "、".join(f"{c['case_id']} {c['result']}" for c in case_results if c["case_id"] in TRACE_FIX_CASES),
        "",
        "## TEST_ERROR 修正 cycle=3/3（Quality 再レビュー QR-IT-1118-R2-001 への対応。it-exec-4）",
        "",
        "| 指摘 | 重大度 | 対応 |",
        "|---|---|---|",
        *[f"| {f} | {sev} | {x} |" for f, sev, x in CYCLE3_FIXES],
        "",
        "- 結果: " + "、".join(f"{c['case_id']} {c['result']}" for c in case_results if c["case_id"] in ("GF-034", "GF-002")),
        "",
        "## TEST_ERROR 修正 cycle=2/3（Quality 再レビュー QR-IT-1118-R1-001 への対応。it-exec-3）",
        "",
        "| 指摘 | 重大度 | 対応 |",
        "|---|---|---|",
        *[f"| {f} | {sev} | {x} |" for f, sev, x in CYCLE2_FIXES],
        "",
        "- 追加 GAP_FILL: GF-039〜GF-043（Required Coverage Revision 3 の RC-129〜RC-133）。結果: "
        + "、".join(f"{c['case_id']} {c['result']}" for c in case_results if c["case_id"] in CYCLE2_CASES),
        "- NFR-US-10: VERIFIED_IT（counts_as_quality_pass={0}。GF-039〜GF-043・GF-034・IT-050・GF-002・GF-003 がすべて PASS の場合だけ true）".format(
            all(c["result"] == "PASS" for c in case_results if c["case_id"] in NFR_US10_CASES)),
        "",
        "## TEST_ERROR 修正 cycle=1/3（INTEGRATION_TEST Scope Assurance への対応。it-exec-2）",
        "",
        "| 指摘 | 重大度 | 対応 |",
        "|---|---|---|",
        *[f"| {f} | {sev} | {x} |" for f, sev, x in SCOPE_ASSURANCE_FIXES],
        "",
        "- Production Code・AI INITIAL（ai-initial-cases.json）・External 入力の状態（external_cases_confirmed_absent=true）は変更していない",
        "- cycle=1/3 時点の NFR の検証可否は Scope Assurance 時点の C10 の NFR 92件の一覧で記録（現在の区分は上の"
        "「FULL Traceability C10 の差し戻し」を参照）",
        "- 応答時間（GF-022）は単一利用者・小データ量の参考計測（response-time-reference.json）で、性能要件の合否判定ではない",
        "",
        "## Criteria",
        "",
        "| Criterion | 適用 | 結果 | ケース数 | FAIL |",
        "|---|---|---|---|---|",
    ]
    for c in criteria_coverage:
        md.append(f"| {c['criterion']} | {c['applicable']} | {c['result']} | {c['cases']} | {', '.join(c['failing_cases']) or '-'} |")
    md += ["", "## 引き継ぐ既知の未解決", ""] + [f"- {k}: {v}" for k, v in KNOWN_UNRESOLVED.items()]
    (OUT / "integration-test-report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    nfr_scope.main()
    print(json.dumps({"status": status, "summary": summary, "defects": len(defects), "errors": len(errors)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
