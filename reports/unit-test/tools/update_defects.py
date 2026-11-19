"""defects.json（単体テスト工程で分類した不具合の記録）を更新する（RUN-AOBA-EC-1118 Scope Assurance 修正 cycle=1/3〜3/3）。

日本語を含むため、PowerShell のパイプ・リダイレクト・文字列直渡しを使わず、本スクリプトから
encoding='utf-8'・ensure_ascii=False で書き出す。書き出し後に U+FFFD と「?」の連続がないことを検証する。
実行：python reports/unit-test/tools/update_defects.py （リポジトリ直下。何度実行しても同じ結果）
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DEFECTS = ROOT / "reports/unit-test/tools/defects.json"
EXEC = "unit-exec-7"
KNOWN = "UNRESOLVED-6de5eec64599b907"
FULL_SUITE_NOTE = f"full_suite は本不具合と無関係の UT-DEF-001・002（既知 {KNOWN}）8件の失敗が残るため FAIL"

KNOWN_NOTE = (
    f"{EXEC}（Scope Assurance 修正 cycle=3/3 後の正式実行。固定版 Django 5.2.19・DRF 3.18.3 の .venv）でも同じ8件が失敗。"
    f"失敗のまま記録し skip しない。既知の未解決 {KNOWN} のため新しい3回ループにしない。"
)

NEW_DEFECTS = [
    {
        "id": "UT-DEF-009",
        "classification": "TEST_ERROR",
        "repair_cycle": "1/3",
        "related_requirement": None,
        "related_adr": "ADDR-011, ADDR-002",
        "failing_test": "python .github/skills/traceability-audit/scripts/trace_check.py --scope UNIT_TEST --no-write"
        "（app/tests/unit/conftest.py：C05 1件・C06 19件）",
        "expected": "テスト工程の対象外（**/conftest.py）のファイルは code として監査され、trace 注釈は code に書ける種類の ID"
        "（ADDR/ENT/DBD/FILE）だけとする。先頭の ID が2件以上かつトップレベル定義が2件以上なら、各定義の直前に先頭の部分集合の"
        " trace 注釈を付ける。",
        "actual": "先頭注釈に要件 ID FR-001 を記載していた（C05）。各定義の直前に trace 注釈がなかった（C06）。",
        "cause": "conftest.py が code として監査されることを考慮せずに注釈を付けていた（テストコードの誤り）。",
        "action": "先頭を `# trace: ADDR-011, ADDR-002` に変更し、19件の定義の直前（decorator より前）に `# trace: ADDR-011`"
        "（bearer は `ADDR-011, ADDR-002`）を付与。テストの期待値・Assertion は変更していない。"
        "app/tests/conftest.py・__init__.py（3件）・settings_test.py にも ADDR の先頭注釈を付与。",
        "regression_test": "trace_check.py --scope UNIT_TEST --no-write（C05/C06/C07 0件）、python -m ruff check .（All checks passed）、"
        "Unit Test Suite 全体",
        "resolved": True,
        "rerun": {"target_test": "PASS", "related_tests": "PASS", "full_suite": "FAIL"},
        "note": FULL_SUITE_NOTE,
    },
    {
        "id": "UT-DEF-010",
        "classification": "TEST_ERROR",
        "repair_cycle": "1/3",
        "source_findings": ["QR-UT-1118-001", "QR-UT-1118-003", "QR-UT-1118-004", "QR-UT-1118-005", "SR-UT-R1-001"],
        "related_requirement": "FR-001, FR-002, FR-021, FR-022, FR-024, FR-026, FR-030, FR-031, FR-034, FR-043, FR-044, FR-045, "
        "NFR-SC-05, NFR-SC-19",
        "related_adr": "ADDR-002, ADDR-003, ADDR-012",
        "failing_test": "UNIT_TEST Scope Assurance（Quality Review・Security Review）の指摘：要件・ADDR 由来のテスト観点の欠落と"
        " Assertion のないテスト2件",
        "expected": "(1) 複数条件が同時に成立する場合の判定順序（AC-UC-001-013、AC-UC-004-027、AC-UC-005-030、AC-UC-006-032、"
        "FR-030 6.15.4 手順3〜9、ADDR-012 DD-003・9章）を業務処理層の単体テストで確認する。"
        "(2) ADDR-003 6章 F(2)：p＋NUL・NUL＋p・途中に NUL を挟んだ文字列の encode 結果が p と異なり p 自身では verify が成立することを、"
        "64バイト以下・ちょうど64バイト・65バイト以上・多バイト文字を含むパスワードで確認する。"
        "(3) 在庫単位ごとの数量上限（TERM-032）と購入者間のクーポン利用回数無制限（FR-024）のテストに要件由来の Assertion を持つ。"
        "(4) CSRF トークンのない管理者の出荷登録・配達完了・キャンセル、購入者の支払・キャンセルは拒否され何も変化しない（NFR-SC-05、VUL-06）。"
        "(5) NFR-SC-19：ログイン前に送信していたセッションの値での要求はログイン後も未ログインとして扱う。",
        "actual": "(1) 判定順序は非公開→在庫の1組だけを確認し、AC の組合せ（数量上限と在庫不足、適用中とコード不存在、有効期間と最低購入金額、"
        "入力不備と登録済みメールアドレス、確定時の全順序）が未確認。(2) 末尾 NUL・64文字＋NUL だけで先頭 NUL・65バイト以上・"
        "多バイト文字が未確認。(3) 2件のテストが業務処理を呼ぶだけで Assertion がなかった。(4) CSRF 拒否はカート・注文確定・"
        "ログイン系だけ。(5) セッション識別子が変わることだけを確認し、旧値での要求の扱いを確認していなかった。",
        "cause": "要件・ADDR からのテストケース導出の漏れ（テストコードの不足）。Production Code の挙動起因の失敗は検出されていない。",
        "action": "追加：test_carts_services.py::test_quantity_limit_is_judged_before_insufficient_stock・"
        "test_coupon_judgement_order_when_several_conditions_hold、test_orders_place_pay.py::"
        "test_place_order_judgement_order_when_several_conditions_hold・test_place_order_full_judgement_order、"
        "test_accounts_services.py::test_register_input_error_is_judged_before_registered_email、test_api_views.py::"
        "test_register_api_input_error_precedes_registered_email、test_password_hasher.py::"
        "test_nul_appended_prepended_or_inserted_encodes_differently（7ケース）、test_web_views.py::"
        "test_order_operations_without_csrf_token_are_rejected（5ケース）・"
        "test_pre_login_session_value_is_treated_as_not_logged_in_after_login。"
        "Assertion 追加：test_add_item_limit_counts_each_stock_unit_separately・"
        "test_apply_coupon_usage_is_not_limited_across_buyers。既存の期待値・Assertion は弱めていない。",
        "regression_test": "上記の追加・強化した単体テスト（19件）",
        "resolved": True,
        "rerun": {"target_test": "PASS", "related_tests": "PASS", "full_suite": "FAIL"},
        "note": FULL_SUITE_NOTE,
    },
    {
        "id": "UT-DEF-011",
        "classification": "TEST_ERROR",
        "repair_cycle": "1/3",
        "source_findings": ["QR-UT-1118-002", "QR-UT-1118-006"],
        "related_requirement": None,
        "related_adr": "ADDR-011",
        "failing_test": "reports/unit-test/unit-test-evidence.json（defects の日本語・criteria_coverage・database_tests）",
        "expected": "evidence の日本語が UTF-8 で正しく保存される（U+FFFD・「?」の連続なし）。database Criterion は DB を実際に使った"
        "テストだけに付け、検証していないロック挙動を検証済みと記載しない。",
        "actual": "UT-DEF-001・002 の note と UT-DEF-009 の全項目が「?」に化けていた。database タグがファイル単位で付き DB を使わない"
        "テストにも付いていた。行ロックによる排他を検証済みと記載していたが該当テストはなかった。",
        "cause": "生成後の evidence を PowerShell の文字列経由で書き換えた（文字コード変換で欠落）。分類がファイル名とテスト名だけで決まっていた。",
        "action": "defects は本スクリプトから ensure_ascii=False・UTF-8 で再出力し、evidence は build_unit_artifacts.py だけで生成する。"
        "app/tests/unit/conftest.py の autouse フィクスチャで各テストの SQL 文の数を JUnit property database_statements に記録し、"
        "1以上のテストだけを database に分類。並行実行（行ロック・アドバイザリロックの排他）は単体テストの対象外と明記し、"
        "テストモジュールの docstring の記載も是正（結合テスト工程：ADDR-011 DD-010）。",
        "regression_test": "update_defects.py・build_unit_artifacts.py の書き出し後検証（U+FFFD・「?」の連続が0件）、"
        "build_unit_artifacts.py の JUnit property 欠落時の停止",
        "resolved": True,
        "rerun": {"target_test": "PASS", "related_tests": "PASS", "full_suite": "FAIL"},
        "note": FULL_SUITE_NOTE,
    },
    {
        "id": "UT-DEF-012",
        "classification": "TEST_ERROR",
        "repair_cycle": "1/3",
        "source_findings": ["Traceability 監査（requirements-traceability-check：単体テスト全件が未実行扱い）"],
        "related_requirement": None,
        "related_adr": "ADDR-011",
        "failing_test": "reports/experiments/RUN-AOBA-EC-1118/unit-command.json の pytest 実行（JUnit classname）",
        "expected": "JUnit の classname がテストファイルのパスと一致する（app/tests/unit/test_xxx.py → app.tests.unit.test_xxx）。"
        "trace_check.py が各テストの実行結果を照合できる。",
        "actual": "rootdir が app/（pytest.ini の場所）となり classname が tests.unit.test_xxx で、全件が未実行扱いとなった。",
        "cause": "pytest の rootdir をリポジトリ直下に揃えていなかった（実行設定の誤り）。",
        "action": "unit-command.json に --rootdir=. を追加（-c app/pytest.ini はそのまま。pythonpath は pytest.ini の場所 app/ を基準に"
        "解決され、DJANGO_SETTINGS_MODULE=tests.settings_test の読込みを確認）。README・app/pytest.ini の実行方法の記述を、"
        "単体・結合とも同じ基準（-c app/pytest.ini --rootdir=.）に整合。build_unit_artifacts.py は classname がテストファイルの"
        "パスと一致しない場合に停止する。",
        "regression_test": "build_unit_artifacts.py の classname 検査、trace_check.py による実行結果の照合（未実行0件）",
        "resolved": True,
        "rerun": {"target_test": "PASS", "related_tests": "PASS", "full_suite": "FAIL"},
        "note": FULL_SUITE_NOTE,
    },
    {
        "id": "UT-DEF-013",
        "classification": "TEST_ERROR",
        "repair_cycle": "2/3",
        "source_findings": ["QR-UT-1118-R1-001"],
        "related_requirement": "FR-031, FR-034, FR-043, FR-044, FR-045",
        "related_adr": "ADDR-004, ADDR-012, ADDR-011",
        "failing_test": "UNIT_TEST Scope Assurance（Quality Review）の指摘：管理者キャンセル（FR-045）・配達完了（FR-044）の"
        "業務処理層テストで異常終了・二重実行防止の事後条件が未検証",
        "expected": "FR-045 6.25.6 異常終了・E-045-04・E-045-05・二重実行防止、AC-UC-012-001（注文受付のキャンセルで在庫8→10）、"
        "AC-UC-012-005（出荷済・配達完了・キャンセル済の3件とも拒否、在庫8・5のまま、キャンセル日時・履歴件数不変）、"
        "FR-044 E-044-04・E-044-05（状態・各日時・配送伝票番号・在庫・決済記録・履歴が処理前のまま）を業務処理層で確認する。"
        "自己点検で同種の不足があった FR-043（E-043-05・E-043-06・二重実行防止）、FR-034（E-034-04・E-034-05）、"
        "FR-031（E-031-05・E-031-08・承認後の再送信）も同様に確認する。",
        "actual": "E-045-04 は出荷済1状態の通知内容だけ、E-045-05・E-044-05 は例外コードだけを確認し、在庫・状態・キャンセル日時・"
        "履歴の不変を Assert していなかった。管理者経路の再送信で在庫を2回戻さないこと、注文受付の管理者キャンセルの在庫数量が"
        "未確認。FR-043・FR-034・FR-031 の状態不正・障害のテストも状態以外の事後条件（各日時・履歴・決済記録・在庫）が未確認。",
        "cause": "要件の事後条件（異常終了・二重実行防止）と AC からのテストケース導出の漏れ（テストコードの不足）。"
        "Production Code の挙動起因の失敗は検出されていない。",
        "action": "app/tests/unit/conftest.py に snapshot_order（注文・明細・配送先・履歴・決済記録・在庫数量/更新日時の比較用）と"
        " fail_sql（指定テーブルへの UPDATE/INSERT の n 回目で DatabaseError を差し込み、差し込み前に実行された更新を記録）を追加。"
        "追加：test_orders_lifecycle.py::test_admin_cancel_accepted_order_returns_stock_and_keeps_amounts・"
        "test_admin_cancel_invalid_status_keeps_order_stock_and_history・"
        "test_admin_cancel_resend_is_invalid_status_and_returns_stock_once（2ケース）・"
        "test_admin_cancel_database_failure_at_each_step_rolls_back_everything（4障害点：状態更新・1件目/2件目の在庫戻し・"
        "在庫戻し後の履歴記録）・test_cancel_my_order_database_failure_at_each_step_rolls_back_everything（同4障害点）・"
        "test_ship_order_resend_keeps_first_shipment・test_ship_order_database_failure_at_each_step_rolls_back_everything（2障害点）・"
        "test_deliver_order_invalid_status_keeps_order（4状態）・"
        "test_deliver_order_database_failure_at_each_step_rolls_back_everything（2障害点）、"
        "test_orders_place_pay.py::test_pay_order_resend_after_approval_keeps_single_approved_record。"
        "Assertion 追加（不変の確認）：test_admin_cancel_errors・test_deliver_order_errors・test_deliver_order_from_shipped_only_once・"
        "test_ship_order_requires_paid_status・test_cancel_my_order_invalid_status_keeps_stock・"
        "test_pay_order_wrong_status_does_not_send_request・test_pay_order_database_failure_changes_nothing、"
        "test_api_views.py::test_admin_order_apis・test_web_views.py の管理画面テスト（在庫数量8→10と再送信で10のまま）。"
        "既存の期待値・Assertion は弱めていない。",
        "regression_test": "上記の追加・強化した単体テスト（在庫戻しの後の障害で在庫が戻らないこと、再送信で在庫が2回戻らないことを"
        "業務処理層・Web API・画面で検出する）",
        "resolved": True,
        "rerun": {"target_test": "PASS", "related_tests": "PASS", "full_suite": "FAIL"},
        "note": FULL_SUITE_NOTE,
    },
    {
        "id": "UT-DEF-014",
        "classification": "ENVIRONMENT_ERROR",
        "repair_cycle": "2/3",
        "source_findings": ["SR-UT-R2-002"],
        "related_requirement": "NFR-SC-11",
        "related_adr": "ADDR-014, ADDR-011",
        "failing_test": "reports/experiments/RUN-AOBA-EC-1118/unit-command.json（unit-exec-5 はホストの Python で実行）",
        "expected": "単体テストを固定版（app/requirements.txt・app/requirements-dev.txt のハッシュ付き版）の依存で実行し、"
        "実行時の主要依存の版を証跡に残す。",
        "actual": "ホストの依存（Django 5.2.7・DRF 3.16.1・psycopg 3.2.10・pytest 9.1.1 等）で実行され、固定版と不一致。"
        "実行時の版の記録がなかった。",
        "cause": "unit-command.json の argv がホストの python を指していた（実行環境の設定の誤り）。",
        "action": "リポジトリ直下の .venv（.gitignore 対象）へ pip install --require-hashes --no-deps --force-reinstall で"
        "固定版を導入し、計測用の coverage==7.15.4・pytest-cov==7.1.0 を版指定で追加（固定ファイルに含まれないためハッシュ照合なし）。"
        "unit-command.json の argv を .venv\\Scripts\\python.exe に変更。app/tests/unit/conftest.py のセッションフィクスチャで"
        "python・django・djangorestframework・psycopg・psycopg-binary・pytest・pytest-django・pytest-cov・coverage の版を"
        "JUnit の testsuite property（runtime.*）に記録し、build_unit_artifacts.py が evidence の runtime_environment に"
        "固定版との照合結果とともに出力する。",
        "regression_test": "build_unit_artifacts.py（runtime.* の欠落時に停止、固定版との照合 all_pinned_packages_match）",
        "resolved": True,
        "rerun": {"target_test": "PASS", "related_tests": "PASS", "full_suite": "FAIL"},
        "note": FULL_SUITE_NOTE
        + "。coverage・pytest-cov は app/requirements-dev.txt に固定されていない（計測ツールのハッシュ固定は"
        "依存ファイルの所管工程での追加を推奨）。",
    },
    {
        "id": "UT-DEF-015",
        "classification": "TEST_ERROR",
        "repair_cycle": "3/3",
        "source_findings": ["QR-UT-1118-R2-001", "QR-UT-1118-R2-002"],
        "related_requirement": "FR-031, FR-034, FR-043, FR-044, FR-045",
        "related_adr": "ADDR-004, ADDR-008, ADDR-011",
        "failing_test": "UNIT_TEST Scope Assurance（Quality Review）の指摘：支払済注文のキャンセル（ST-PO-04、AC-UC-012-002 必須）で"
        "「支払日時・決済記録は変化しない」を検出できる Assertion がない（R2-001）。FR-031 手順10・11 の否認・連携エラーの"
        "決済記録の登録で障害が発生した場合の E-031-08 が未検証（R2-002）",
        "expected": "FR-045 6.25.4 手順5・手順8・6.25.6 正常終了、FR-034 6.19.4 手順8・6.19.6 正常終了、AC-UC-012-002"
        "（支払日時 2027-04-01 11:05:00 のまま、決済記録1件・承認・6,105円・MOCK-Q1W2E3R4T5Y6U7I8・処理日時が不変、"
        "状態履歴3件、在庫数量5→8）：決済記録の件数・全項目と注文日時・支払日時、注文の金額・明細・配送先は処理前と同じ。"
        "自己点検で同種の不足があった成功系（FR-043 6.23.6、FR-044 6.24.6、FR-031 6.16.6 正常終了・否認・外部連携エラー）も"
        "要件が「処理前と同じ」と定める項目を処理前後で比較する。FR-031 6.16.4 手順10・手順11：否認・連携エラーの決済記録の"
        "登録で障害が発生した場合は E-031-08（E-031-06・E-031-07 にしない）、6.16.6 異常終了（その他）のとおり何も変化しない。",
        "actual": "FR-045 の支払済キャンセルは paid_at is not None だけで、処理時刻等で上書きされても PASS した。決済記録の不変は"
        "FR-045 では未確認、FR-034 では件数のみ。出荷登録・配達完了登録・支払の成功系も決済記録・各日時・明細・配送先の不変が"
        "未確認。否認・連携エラーの決済記録の登録失敗の分岐はテストがなかった。",
        "cause": "要件の正常終了の事後条件（処理前と同じ項目）と AC-UC-012-002 の Pass/Fail Rule、FR-031 手順10・11 の分岐からの"
        "テストケース導出の漏れ（テストコードの不足）。Production Code の挙動起因の失敗は検出されていない。",
        "action": "追加：test_orders_lifecycle.py::test_admin_cancel_paid_order_keeps_paid_at_and_payment_record（AC-UC-012-002 の値で"
        "処理前後の snapshot_order を比較し、決済記録の全項目・支払日時・状態履歴3件・在庫8・注文詳細（管理者）の決済記録を確認）、"
        "test_orders_place_pay.py::test_pay_order_failure_while_recording_declined_or_integration_error_is_system_failure"
        "（fail_sql で否認・連携エラーの決済記録の INSERT に障害を差し込み E-031-08、決済要求1回・当該結果、snapshot 不変）。"
        "比較用の _assert_unchanged_except（データ更新の対象以外の注文の項目・明細・配送先・決済記録の全項目が処理前と同じ）を"
        "各テストモジュールに追加し、Assertion 追加：test_cancel_my_order_returns_stock_once_and_records_history（paid は"
        "支払日時 2027-04-01 11:05:00 と承認の決済記録の全項目）・test_admin_cancel_any_buyers_order_returns_stock_regardless_of_"
        "visibility・test_admin_cancel_resend_is_invalid_status_and_returns_stock_once・test_admin_cancel_database_failure_at_each_"
        "step_rolls_back_everything（取消し後の再実行）・test_ship_order_records_tracking_number_as_entered・"
        "test_deliver_order_from_shipped_only_once・test_pay_order_approved_marks_paid_and_records_payment・"
        "test_pay_order_declined_keeps_order_and_persists_record・test_pay_order_integration_error_records_and_logs。"
        "既存の期待値・Assertion は弱めていない。",
        "regression_test": "上記の追加・強化した単体テスト（支払日時・決済記録の上書き・追加・削除、否認・連携エラー時の決済記録登録"
        "失敗を E-031-06・E-031-07 で返す退行を検出する）",
        "resolved": True,
        "rerun": {"target_test": "PASS", "related_tests": "PASS", "full_suite": "FAIL"},
        "note": FULL_SUITE_NOTE
        + "。SR-UT-R3-001（LOW）：coverage・pytest-cov が app/requirements-dev.txt に固定されていない件は、依存ファイルの所管が"
        "Implementation 工程のため本工程では記録のみ（未対応）。",
    },
]


def verify_text(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if "\ufffd" in text or re.search(r"\?\?", text):
        raise SystemExit(f"{path}: U+FFFD または「?」の連続が含まれる")


def main() -> int:
    defects = json.loads(DEFECTS.read_text(encoding="utf-8"))
    by_id = {d["id"]: d for d in defects}
    for defect_id in ("UT-DEF-001", "UT-DEF-002"):
        by_id[defect_id]["note"] = KNOWN_NOTE
    for defect in NEW_DEFECTS:
        if defect["id"] in by_id:
            defects[[d["id"] for d in defects].index(defect["id"])] = defect
        else:
            defects.append(defect)
    DEFECTS.write_text(json.dumps(defects, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    verify_text(DEFECTS)
    print(json.dumps([d["id"] for d in defects]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
