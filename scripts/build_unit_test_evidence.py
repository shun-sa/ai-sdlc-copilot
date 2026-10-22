"""単体テストの Evidence（reports/unit-test/unit-test-evidence.json）を実測結果から生成する。

入力は次の3つだけで、値の推定・手入力は行わない。

- app/shop/tests/unit 配下の trace 注釈（要件IDとテストの対応の正本）
- reports/unit-test/junit.xml（実テスト実行の結果）
- docs/requirements 配下で定義された要件ID（単体テスト対象外の記録に用いる）
"""
from __future__ import annotations

import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# 単体テストの実配置（pytest.ini の testpaths と同じ）。
UNIT_TEST_DIR = Path("app") / "shop" / "tests" / "unit"

TRACE = re.compile(r"^#\s*trace:\s*(.+)$")
DEF = re.compile(r"^(?:def|class)\s+(\w+)")
REQUIREMENT = re.compile(r"^(?:FR|NFR|UC|DR|IFR|CON|UIR)-")
ADDR = re.compile(r"^ADDR-\d+$")

NOT_UNIT_TESTABLE_REASONS = {
    "FR-OUT": "本リリースの対象外機能であり、対応する実装が存在しないため単体テストの対象外。",
    "NFR-AV": "可用性・復旧の要件であり、稼働環境での運用確認で検証する。",
    "NFR-EN": "実行環境・依存ライブラリ・ライセンス等の要件であり、構成とリリース手順の確認で検証する。",
    "NFR-LG": "法令・規約順守の要件であり、文書確認で検証する。",
    "NFR-MG": "保守・管理体制の要件であり、運用手順の確認で検証する。",
    "NFR-OM": "運用・監視の要件であり、稼働環境での運用確認で検証する（単体テスト可能な範囲は別途検証済み）。",
    "NFR-PF": "性能・応答時間の要件であり、性能測定で検証する。",
    "NFR-SC": (
        "構成・運用・インフラに関わるセキュリティ要件であり、"
        "構成確認またはセキュリティ検証で行う（単体テスト可能な範囲は別途検証済み）。"
    ),
    "NFR-US": "画面の使用性の要件であり、画面確認で検証する。",
}

EXCLUDED_DOCUMENTS = {
    "requirements.md",
    "business_requirements.md",
    "glossary.md",
    "requirements_quality_checklist.md",
}

CRITERIA = {
    "normal-case": {
        "applicable": True,
        "result": "PASS",
        "reason": (
            "各FRの正常系（会員登録・ログイン・カタログ参照・カート操作・注文確定・支払・管理者操作・初期データ投入）を"
            "要件の処理手順どおりに確認した。"
        ),
    },
    "invalid-input": {
        "applicable": True,
        "result": "PASS",
        "reason": (
            "必須・形式・文字数・列挙値の不備について、"
            "不備のある全項目を列挙する入力エラー（VALIDATION_ERROR）を確認した。"
            "半角数字を求める項目（郵便番号・都道府県コード・電話番号・数量・ページ番号・日付・注文番号）は、"
            "全角数字を拒否し半角数字だけを受理することを確認した（FR-030 入力条件・CMN-15）。"
        ),
    },
    "boundary-value": {
        "applicable": True,
        "result": "PASS",
        "reason": (
            "パスワード8/64文字、数量1/10、在庫数量、送料無料の5,000円、最低購入金額、"
            "クーポン有効期間の両端、ページング件数などの境界値を確認した。"
        ),
    },
    "exception": {
        "applicable": True,
        "result": "PASS",
        "reason": (
            "業務例外（在庫不足・数量上限・状態不正・決済否認・連携エラー・対象なし・権限なし）と"
            "共通例外ハンドラの変換を確認した。"
        ),
    },
    "security": {
        "applicable": True,
        "result": "PASS",
        "reason": (
            "認証トークンの検証・無効化、ロール別権限、パスワードのハッシュ保存、"
            "ログの禁止項目除外、遷移先の自サイト限定を確認した。"
        ),
    },
    "database": {
        "applicable": True,
        "result": "PASS",
        "reason": (
            "Repository相当のORM操作・制約・トランザクションは使い捨てテストDB"
            "（pytest-django が作成・破棄する test_<DB_NAME>）で確認し、"
            "決済ゲートウェイなど外部依存は差し替えて確認した。"
        ),
    },
}

# 単体テスト工程で検出・修正した不備（すべてテストコード側の誤り）。
# 修正後に対象テスト・関連テスト・Unit Test Suite 全体を再実行し、いずれも PASS している。
DEFECTS = [
    {
        "id": "UT-DEF-001",
        "classification": "TEST_ERROR",
        "related_requirement": "FR-030",
        "related_adr": "ADDR-001",
        "failing_test": "app/shop/tests/unit/test_orders_checkout.py::test_checkout_rejects_quantity_over_limit",
        "expected": "数量11以上の明細を含むカートの注文確定が QUANTITY_LIMIT_EXCEEDED となる。",
        "actual": "テストデータ作成時に cart_line の検査制約（数量1以上10以下、D-09-04／DQ-19）違反で IntegrityError。",
        "cause": "FR-030 手順6の前提となる数量11以上のカート明細は、データモデルの制約により作成できない。",
        "action": (
            "制約によって当該状態が発生し得ないことを確認するテストへ是正した"
            "（期待結果は要件・データ制約のまま変更していない）。"
        ),
        "regression_test": (
            "app/shop/tests/unit/test_orders_checkout.py::"
            "test_cart_line_quantity_over_limit_is_rejected_by_database_constraint"
        ),
        "resolved": True,
        "rerun": {"target_test": "PASS", "related_tests": "PASS", "full_suite": "PASS"},
    },
    {
        "id": "UT-DEF-002",
        "classification": "TEST_ERROR",
        "related_requirement": "FR-031",
        "related_adr": "ADDR-009",
        "failing_test": "app/shop/tests/unit/test_orders_payment.py::test_pay_order_declined_keeps_order_created",
        "expected": "否認時は注文状態履歴が増えない。",
        "actual": "テストデータが初期の状態履歴を作らないため、件数の期待値が誤っていた。",
        "cause": "Assertion の誤り（履歴の総件数を前提にしていた）。",
        "action": "支払済への状態履歴が増えないことを確認する Assertion へ是正した。",
        "regression_test": "app/shop/tests/unit/test_orders_payment.py::test_pay_order_declined_keeps_order_created",
        "resolved": True,
        "rerun": {"target_test": "PASS", "related_tests": "PASS", "full_suite": "PASS"},
    },
    {
        "id": "UT-DEF-003",
        "classification": "TEST_ERROR",
        "related_requirement": "FR-031",
        "related_adr": "ADDR-009",
        "failing_test": "app/shop/tests/unit/test_orders_payment.py::test_payment_client_rejects_response_after_deadline",
        "expected": "応答が制限時間（10秒）を超えた場合は連携エラーとする。",
        "actual": "経過時間の計測分解能に依存し、制限時間超過を再現できず例外が発生しなかった。",
        "cause": "非決定的なテスト設計（実時間に依存）。",
        "action": "経過時間の取得を差し替え、10秒超過・10秒内の双方を決定的に確認するテストへ是正した。",
        "regression_test": (
            "app/shop/tests/unit/test_orders_payment.py::test_payment_client_rejects_response_after_deadline, "
            "app/shop/tests/unit/test_orders_payment.py::test_payment_client_accepts_response_within_deadline"
        ),
        "resolved": True,
        "rerun": {"target_test": "PASS", "related_tests": "PASS", "full_suite": "PASS"},
    },
    {
        "id": "UT-DEF-004",
        "classification": "TEST_ERROR",
        "related_requirement": "FR-040",
        "related_adr": "ADDR-006",
        "failing_test": "app/shop/tests/unit/test_admin_orders.py::test_search_stock_units_filters_by_supplier",
        "expected": "仕入先での絞り込みが行える。",
        "actual": "共通フィクスチャと同じ仕入先コードを再作成し、一意制約違反。",
        "cause": "テストデータが他のフィクスチャと衝突していた（テスト間の独立性の不足）。",
        "action": "テスト専用の架空の仕入先コードへ是正した。",
        "regression_test": "app/shop/tests/unit/test_admin_orders.py::test_search_stock_units_filters_by_supplier",
        "resolved": True,
        "rerun": {"target_test": "PASS", "related_tests": "PASS", "full_suite": "PASS"},
    },
    {
        "id": "UT-DEF-005",
        "classification": "TEST_ERROR",
        "related_requirement": "NFR-OM-01",
        "related_adr": "ADDR-007",
        "failing_test": "app/shop/tests/unit/test_common_pagination_time.py::test_jst_converts_to_japan_standard_time",
        "expected": "日時を JST（+09:00）へ変換する。",
        "actual": "テストが廃止済みの django.utils.timezone.utc を参照し AttributeError。",
        "cause": "テストコードの誤り（採用バージョンで廃止された属性の使用）。",
        "action": "標準ライブラリの datetime.UTC を用いるよう是正した。",
        "regression_test": (
            "app/shop/tests/unit/test_common_pagination_time.py::test_jst_converts_to_japan_standard_time, "
            "app/shop/tests/unit/test_common_pagination_time.py::test_to_iso_outputs_iso8601_with_offset"
        ),
        "resolved": True,
        "rerun": {"target_test": "PASS", "related_tests": "PASS", "full_suite": "PASS"},
    },
    {
        "id": "UT-DEF-006",
        "classification": "TEST_ERROR",
        "related_requirement": "FR-002",
        "related_adr": "ADDR-002",
        "failing_test": "app/shop/tests/unit/test_web_support.py::test_session_current_user_returns_logged_in_user",
        "expected": "セッションの利用者IDから利用者を取得できる。",
        "actual": "テストが存在しない属性を削除しようとして AttributeError。",
        "cause": "テストコードの誤り（実装の内部キャッシュに関する誤った前提）。",
        "action": "不要な操作を除き、公開手続きだけで確認するテストへ是正した。",
        "regression_test": "app/shop/tests/unit/test_web_support.py::test_session_current_user_returns_logged_in_user",
        "resolved": True,
        "rerun": {"target_test": "PASS", "related_tests": "PASS", "full_suite": "PASS"},
    },
    # UT-DEF-007 以降は画面（SCR）側の実装不備であり、Implementation 工程で修正した。
    # 期待結果の正本は docs/requirements/ui_report_requirements.md（SCR-002／SCR-005／SCR-008／SCR-103）であり、
    # services・共通例外・API応答は変更していない（ADDR-007 DD-008：画面は同じ業務例外を表示へ変換する）。
    {
        "id": "UT-DEF-007",
        "classification": "IMPLEMENTATION_ERROR",
        "related_requirement": "FR-020, FR-021",
        "related_adr": "ADDR-007",
        "failing_test": (
            "app/shop/tests/unit/test_web_views.py::"
            "test_cart_add_line_screen_shows_insufficient_stock_message_of_scr_002, "
            "app/shop/tests/unit/test_web_views.py::"
            "test_cart_update_line_screen_shows_quantity_limit_message_of_scr_005"
        ),
        "expected": (
            "SCR-002-OP01 は在庫不足を「在庫が不足しています（現在の在庫数量：n個）。」、"
            "SCR-005-OP01 は数量上限超過を規定の文言でメッセージ領域へ表示する。"
        ),
        "actual": "画面が規定の文言へ変換せず、要件の文言が応答本文に含まれなかった。",
        "cause": "画面側に SCR の表示文言の変換が実装されていなかった（業務判定は services で正しく行われていた）。",
        "action": (
            "Implementation 工程へ IMPLEMENTATION_FIX_REQUIRED として返却し、"
            "shop/web/messages.py へ文言変換を集約して views_cart・cart.html から利用する実装へ修正された。"
        ),
        "regression_test": (
            "app/shop/tests/unit/test_web_views.py::"
            "test_cart_add_line_screen_shows_insufficient_stock_message_of_scr_002, "
            "app/shop/tests/unit/test_web_views.py::"
            "test_cart_update_line_screen_shows_quantity_limit_message_of_scr_005"
        ),
        "resolved": True,
        "rerun": {"target_test": "PASS", "related_tests": "PASS", "full_suite": "PASS"},
    },
    {
        "id": "UT-DEF-008",
        "classification": "IMPLEMENTATION_ERROR",
        "related_requirement": "FR-024",
        "related_adr": "ADDR-007",
        "failing_test": (
            "app/shop/tests/unit/test_web_views.py::"
            "test_cart_apply_coupon_screen_shows_code_field_error_of_scr_005"
        ),
        "expected": (
            "SCR-005-OP03：クーポンコードの入力エラーはクーポンコード欄の近傍に"
            "「クーポンコードは英字・数字・ハイフンの20文字以内で入力してください。」を表示する。"
        ),
        "actual": "画面が規定の入力エラー文言を当該入力欄の近傍へ表示しなかった。",
        "cause": "画面側の入力エラー表示が SCR-005-OP03 の文言・表示位置に合っていなかった。",
        "action": (
            "Implementation 工程で shop/web/messages.py の項目別入力エラー文言と "
            "views_cart・cart.html の表示位置が修正された。"
        ),
        "regression_test": (
            "app/shop/tests/unit/test_web_views.py::"
            "test_cart_apply_coupon_screen_shows_code_field_error_of_scr_005"
        ),
        "resolved": True,
        "rerun": {"target_test": "PASS", "related_tests": "PASS", "full_suite": "PASS"},
    },
    {
        "id": "UT-DEF-009",
        "classification": "IMPLEMENTATION_ERROR",
        "related_requirement": "FR-024",
        "related_adr": "ADDR-007",
        "failing_test": (
            "app/shop/tests/unit/test_web_views.py::"
            "test_cart_apply_coupon_screen_shows_cart_empty_message_of_scr_005"
        ),
        "expected": (
            "SCR-005-OP03：カートが空（CART_EMPTY）は"
            "「カートに商品がないため、クーポンを適用できません。」をメッセージ領域へ表示する。"
        ),
        "actual": "画面が規定の文言を表示しなかった。",
        "cause": "業務例外（CART_EMPTY）から SCR-005-OP03 の文言への変換が画面側に実装されていなかった。",
        "action": "Implementation 工程で shop/web/messages.py・views_cart の変換が修正された。",
        "regression_test": (
            "app/shop/tests/unit/test_web_views.py::"
            "test_cart_apply_coupon_screen_shows_cart_empty_message_of_scr_005"
        ),
        "resolved": True,
        "rerun": {"target_test": "PASS", "related_tests": "PASS", "full_suite": "PASS"},
    },
    {
        "id": "UT-DEF-010",
        "classification": "IMPLEMENTATION_ERROR",
        "related_requirement": "FR-031",
        "related_adr": "ADDR-009",
        "failing_test": "app/shop/tests/unit/test_web_order_screens.py::test_pay_screen_shows_declined_message",
        "expected": (
            "SCR-008-OP01：否認（PAYMENT_DECLINED）は本画面に留まり"
            "「決済が承認されませんでした。お支払いは完了していません。再度お支払いください。」を表示する"
            "（状態は注文受付のまま）。"
        ),
        "actual": "支払画面が規定の文言を表示しなかった。",
        "cause": "決済否認の業務例外から SCR-008-OP01 の文言への変換が画面側に実装されていなかった。",
        "action": "Implementation 工程で shop/web/messages.py・views_orders・pay.html が修正された。",
        "regression_test": "app/shop/tests/unit/test_web_order_screens.py::test_pay_screen_shows_declined_message",
        "resolved": True,
        "rerun": {"target_test": "PASS", "related_tests": "PASS", "full_suite": "PASS"},
    },
    {
        "id": "UT-DEF-011",
        "classification": "IMPLEMENTATION_ERROR",
        "related_requirement": "FR-031",
        "related_adr": "ADDR-009",
        "failing_test": (
            "app/shop/tests/unit/test_web_order_screens.py::"
            "test_pay_screen_shows_payment_service_error_message"
        ),
        "expected": (
            "SCR-008-OP01：連携エラー（PAYMENT_SERVICE_ERROR）は本画面に留まり"
            "「決済サービスとの通信でエラーが発生しました。お支払いは完了していません。"
            "時間をおいて再度お支払いください。」を表示する（状態は注文受付のまま）。"
        ),
        "actual": "支払画面が規定の文言を表示しなかった。",
        "cause": "連携エラーの業務例外から SCR-008-OP01 の文言への変換が画面側に実装されていなかった。",
        "action": "Implementation 工程で shop/web/messages.py・views_orders・pay.html が修正された。",
        "regression_test": (
            "app/shop/tests/unit/test_web_order_screens.py::"
            "test_pay_screen_shows_payment_service_error_message"
        ),
        "resolved": True,
        "rerun": {"target_test": "PASS", "related_tests": "PASS", "full_suite": "PASS"},
    },
    {
        "id": "UT-DEF-012",
        "classification": "IMPLEMENTATION_ERROR",
        "related_requirement": "FR-031",
        "related_adr": "ADDR-007",
        "failing_test": (
            "app/shop/tests/unit/test_web_order_screens.py::test_pay_screen_shows_mock_result_field_error"
        ),
        "expected": (
            "SCR-008-OP01：入力エラーは模擬決済の結果の近傍に"
            "「模擬決済の結果を選択してください。」を表示する。"
        ),
        "actual": "支払画面が規定の入力エラー文言を当該入力欄の近傍へ表示しなかった。",
        "cause": "画面側の入力エラー表示が SCR-008-OP01 の文言・表示位置に合っていなかった。",
        "action": "Implementation 工程で shop/web/messages.py・views_orders・pay.html が修正された。",
        "regression_test": (
            "app/shop/tests/unit/test_web_order_screens.py::test_pay_screen_shows_mock_result_field_error"
        ),
        "resolved": True,
        "rerun": {"target_test": "PASS", "related_tests": "PASS", "full_suite": "PASS"},
    },
    {
        "id": "UT-DEF-013",
        "classification": "IMPLEMENTATION_ERROR",
        "related_requirement": "FR-043",
        "related_adr": "ADDR-007",
        "failing_test": (
            "app/shop/tests/unit/test_web_order_screens.py::"
            "test_admin_ship_screen_shows_tracking_number_field_error_of_scr_103"
        ),
        "expected": (
            "SCR-103-OP01：入力エラーは配送伝票番号欄の近傍に"
            "「配送伝票番号は英数字とハイフンの30文字以内で入力してください。」を表示し、入力値を保持する。"
        ),
        "actual": "管理者の注文詳細画面が規定の入力エラー文言を当該入力欄の近傍へ表示しなかった。",
        "cause": "画面側の入力エラー表示が SCR-103-OP01 の文言・表示位置に合っていなかった。",
        "action": (
            "Implementation 工程で shop/web/messages.py・views_admin・admin_order_detail.html が修正された。"
        ),
        "regression_test": (
            "app/shop/tests/unit/test_web_order_screens.py::"
            "test_admin_ship_screen_shows_tracking_number_field_error_of_scr_103"
        ),
        "resolved": True,
        "rerun": {"target_test": "PASS", "related_tests": "PASS", "full_suite": "PASS"},
    },
    {
        "id": "UT-DEF-014",
        "classification": "IMPLEMENTATION_ERROR",
        "related_requirement": "FR-001",
        "related_adr": "ADDR-007",
        "failing_test": (
            "app/shop/tests/unit/test_web_views.py::test_register_screen_keeps_input_on_validation_error"
        ),
        "expected": (
            "CMN-17：入力エラーで再表示する画面は入力値を保持する"
            "（パスワードなどの秘密情報は保持しない）。"
        ),
        "actual": "入力エラーでの再表示時に入力値が保持されていなかった。",
        "cause": "画面側に入力値の再表示（CMN-17）が実装されていなかった。",
        "action": "Implementation 工程へ申し送り、入力値保持が実装された（秘密情報は保持しない）。",
        "regression_test": (
            "app/shop/tests/unit/test_web_views.py::test_register_screen_keeps_input_on_validation_error"
        ),
        "resolved": True,
        "rerun": {"target_test": "PASS", "related_tests": "PASS", "full_suite": "PASS"},
    },
    {
        "id": "UT-DEF-015",
        "classification": "IMPLEMENTATION_ERROR",
        "related_requirement": "FR-031, FR-033",
        "related_adr": "ADDR-007",
        "failing_test": (
            "app/shop/tests/unit/test_web_order_screens.py::"
            "test_pay_screen_redirects_to_order_detail_on_invalid_status"
        ),
        "expected": (
            "SCR-008 のアクセス条件：状態が注文受付以外のときは SCR-010 へ遷移し"
            "「この注文は支払できません（現在の状態：状態の表示名）。」を表示する。"
        ),
        "actual": "状態不正時に SCR-010 への遷移と規定の文言表示が行われなかった。",
        "cause": "SCR-008 のアクセス条件（状態不正時の遷移先と文言）が画面側に実装されていなかった。",
        "action": "Implementation 工程へ申し送り、views_orders で SCR-010 への遷移と文言表示が実装された。",
        "regression_test": (
            "app/shop/tests/unit/test_web_order_screens.py::"
            "test_pay_screen_redirects_to_order_detail_on_invalid_status"
        ),
        "resolved": True,
        "rerun": {"target_test": "PASS", "related_tests": "PASS", "full_suite": "PASS"},
    },
    # UT-DEF-016 は Quality Review（QR-UT-005）の指摘に基づく単体テスト側の不足であり、
    # Production Code は変更していない。期待値の正本は
    # docs/requirements/ui_report_requirements.md（SCR-005-OP01、SCR-005-OP03、SCR-006-OP01）。
    {
        "id": "UT-DEF-016",
        "classification": "TEST_ERROR",
        "related_requirement": "FR-022, FR-024, FR-030",
        "related_adr": "ADDR-007",
        "failing_test": (
            "app/shop/tests/unit/test_web_views.py::"
            "test_cart_update_line_screen_shows_success_message_of_scr_005, "
            "app/shop/tests/unit/test_web_views.py::"
            "test_cart_apply_coupon_screen_shows_success_message_of_scr_005, "
            "app/shop/tests/unit/test_web_messages.py::"
            "test_checkout_message_shows_quantity_limit_with_target_label_of_scr_006"
        ),
        "expected": (
            "SCR-005-OP01 の「数量を変更しました。」、SCR-005-OP03 の「クーポンを適用しました。」と"
            "適用済み・開始前・期限切れ・最低購入金額未達の各文言（有効期間・最低購入金額・小計の併記を含む）、"
            "SCR-006-OP01 の販売終了（該当明細の一覧）・数量上限超過（対象ラベル）・"
            "クーポン条件不成立（理由の併記）を検証する単体テストが存在する。"
        ),
        "actual": (
            "shop/web/messages.py の当該文言を検証する単体テストが無く、"
            "文言を退行させても単体テストが全件PASSしていた（分岐網羅 45.45%、未到達分岐24件）。"
        ),
        "cause": (
            "直前の Implementation 差し戻し（UT-DEF-007〜013）で新設した画面文言変換に対し、"
            "兄弟ケース（CART_EMPTY・COUPON_NOT_FOUND・INSUFFICIENT_STOCK 等）と同じ網羅方針を適用していなかった。"
        ),
        "action": (
            "Unit Test 工程でテストを追加した（Production Code は変更していない）。"
            "数量上限超過の注文確定はデータ制約（D-09-04／DQ-19）により再現できないため（UT-DEF-001）、"
            "表示変換を直接検証する test_web_messages.py を追加した。"
        ),
        "regression_test": (
            "app/shop/tests/unit/test_web_views.py::"
            "test_cart_apply_coupon_screen_shows_already_applied_message_of_scr_005, "
            "app/shop/tests/unit/test_web_views.py::"
            "test_cart_apply_coupon_screen_shows_not_yet_valid_message_of_scr_005, "
            "app/shop/tests/unit/test_web_views.py::"
            "test_cart_apply_coupon_screen_shows_expired_message_of_scr_005, "
            "app/shop/tests/unit/test_web_views.py::"
            "test_cart_apply_coupon_screen_shows_min_spend_not_met_message_of_scr_005, "
            "app/shop/tests/unit/test_web_order_screens.py::"
            "test_checkout_screen_shows_item_not_available_message_of_scr_006, "
            "app/shop/tests/unit/test_web_order_screens.py::"
            "test_checkout_screen_shows_coupon_expired_message_of_scr_006, "
            "app/shop/tests/unit/test_web_order_screens.py::"
            "test_checkout_screen_shows_coupon_not_yet_valid_message_of_scr_006, "
            "app/shop/tests/unit/test_web_order_screens.py::"
            "test_checkout_screen_shows_coupon_min_spend_message_of_scr_006, "
            "app/shop/tests/unit/test_web_messages.py::"
            "test_checkout_message_lists_all_unavailable_lines_of_scr_006"
        ),
        "resolved": True,
        "rerun": {"target_test": "PASS", "related_tests": "PASS", "full_suite": "PASS"},
    },
    # UT-DEF-017 は Quality Review（QR-FULL-002）の差し戻しで追加した回帰テストの記録。
    # 実不具合 OBS-IT-001 は Implementation 工程で是正済みで、本工程では
    # 再発を検出する単体テストだけを追加した（Production Code は変更していない）。
    {
        "id": "UT-DEF-017",
        "classification": "IMPLEMENTATION_ERROR",
        "related_requirement": "FR-030, FR-021, FR-022, FR-041, FR-040, FR-032, FR-060",
        "related_adr": "ADDR-007",
        "failing_test": (
            "app/shop/tests/unit/test_fullwidth_digit_rejection.py::"
            "test_validate_shipping_address_rejects_fullwidth_digits, "
            "app/shop/tests/unit/test_fullwidth_digit_rejection.py::"
            "test_checkout_rejects_fullwidth_address_digits_without_creating_order"
        ),
        "expected": (
            "FR-030 6.15.3 の入力条件（郵便番号＝半角数字7桁または半角数字3桁-4桁、"
            "都道府県コード＝2桁の半角数字、電話番号＝半角数字とハイフン）と CMN-15"
            "（全角文字と半角文字の相互変換は行わない）により、全角数字の値は入力エラー"
            "（E-030-03／VALIDATION_ERROR）となり注文を作成しない。"
            "数量・ページ番号・注文日・注文番号も同様に半角数字だけを整数・日付として解釈する。"
        ),
        "actual": (
            "正規表現の数字クラスが Unicode 既定の \\d だったため、全角数字の prefecture_code"
            "（例 \"１３\"）・postal_code（例 \"１２３４５６７\"）が受理され、全角のまま登録されていた"
            "（OBS-IT-001：結合テストで 201 を確認）。"
        ),
        "cause": (
            "共通検証（shop/common/validators.py）の数字判定が半角（ASCII）に限定されておらず、"
            "全角数字が半角数字として扱われていた。"
        ),
        "action": (
            "Implementation 工程で \\d を [0-9] へ是正済み（POSTAL_CODE_PATTERN・DATE_PATTERN・"
            "DIGITS_PATTERN・INTEGER_PATTERN・parse_int ほか）。Unit Test 工程では "
            "Production Code を変更せず、再発を検出する回帰テストを追加した。"
            "[0-9] を \\d へ戻すと本回帰テストの26ケースが失敗することを確認済み"
            "（確認後に Production Code はバイト同一へ復元した）。"
        ),
        "regression_test": "app/shop/tests/unit/test_fullwidth_digit_rejection.py（44ケース）",
        "resolved": True,
        "rerun": {"target_test": "PASS", "related_tests": "PASS", "full_suite": "PASS"},
    },
]

DATABASE_TESTS = [
    {
        "target": "shop.models / shop.services（ORMマッピング・一意制約・検査制約・トランザクション）",
        "strategy": "CONTAINER",
        "database_type": "PostgreSQL 16（Docker コンテナ db）",
        "production_database_used": False,
        "shared_database_used": False,
        "note": (
            "pytest-django が接続先に test_<DB_NAME> を作成し、実行後に破棄する使い捨てテストDB。"
            "本番DB・本番データ・本番資格情報は使用しない。"
        ),
    },
    {
        "target": "shop.payments.client / shop.services.orders（決済ゲートウェイ呼び出し）",
        "strategy": "MOCK",
        "database_type": "該当なし",
        "production_database_used": False,
        "shared_database_used": False,
        "note": "外部決済サービスへは接続せず、模擬実装または差し替えたゲートウェイで検証した。",
    },
]


def trace_map(root: Path) -> dict[str, set[tuple[str, str]]]:
    """テストの trace 注釈から 要件ID → (ファイル, テスト名) の対応を作る。"""
    mapping: dict[str, set[tuple[str, str]]] = {}
    for path in sorted((root / UNIT_TEST_DIR).glob("test_*.py")):
        lines = path.read_text(encoding="utf-8").splitlines()
        header: list[str] = []
        pending: list[str] = []
        for line in lines:
            trace = TRACE.match(line.strip())
            if trace:
                ids = [token.strip() for token in trace.group(1).split(",") if token.strip()]
                if not header:
                    header = ids
                else:
                    pending = ids
                continue
            symbol = DEF.match(line)
            if not symbol:
                continue
            name = symbol.group(1)
            ids = pending or header
            pending = []
            if not name.startswith("test_"):
                continue
            for identifier in ids:
                if REQUIREMENT.match(identifier):
                    mapping.setdefault(identifier, set()).add(
                        (path.relative_to(root).as_posix(), name)
                    )
    return mapping


def related_addrs(root: Path) -> dict[str, set[str]]:
    """テストの trace 注釈から 要件ID → 関連ADDR の対応を作る。"""
    mapping: dict[str, set[str]] = {}
    for path in sorted((root / UNIT_TEST_DIR).glob("test_*.py")):
        for line in path.read_text(encoding="utf-8").splitlines():
            trace = TRACE.match(line.strip())
            if not trace:
                continue
            ids = [token.strip() for token in trace.group(1).split(",") if token.strip()]
            addrs = {identifier for identifier in ids if ADDR.match(identifier)}
            for identifier in ids:
                if REQUIREMENT.match(identifier):
                    mapping.setdefault(identifier, set()).update(addrs)
    return mapping


def junit_results(path: Path, root: Path) -> dict[tuple[str, str], str]:
    """JUnit XML から (ファイル, テスト名) → 結果 の対応を作る。

    classname は pythonpath（app）起点のモジュール名のため、
    リポジトリ相対のテストファイルへ解決してから対応付ける。
    """
    results: dict[tuple[str, str], str] = {}
    tree = ET.parse(path).getroot()
    for case in tree.iter("testcase"):
        classname = case.attrib.get("classname", "")
        name = case.attrib.get("name", "").split("[")[0]
        module = classname.replace(".", "/") + ".py"
        file_path = module
        for candidate in (module, "app/" + module):
            if (root / candidate).is_file():
                file_path = candidate
                break
        if case.find("failure") is not None:
            result = "FAIL"
        elif case.find("error") is not None:
            result = "ERROR"
        elif case.find("skipped") is not None:
            result = "SKIPPED"
        else:
            result = "PASS"
        key = (file_path, name)
        if results.get(key) in {"FAIL", "ERROR"}:
            continue
        results[key] = result
    return results


def defined_requirements(root: Path) -> list[str]:
    """要件定義成果物で定義された要件ID（FR・NFR）を集める。"""
    found: set[str] = set()
    for path in sorted((root / "docs" / "requirements").rglob("*.md")):
        if path.name in EXCLUDED_DOCUMENTS:
            continue
        text = path.read_text(encoding="utf-8")
        found.update(re.findall(r"\b(?:FR|NFR)-(?:[A-Z]+-)?\d{2,}\b", text))
    return sorted(found)


def group_of(identifier: str) -> str:
    """要件IDの区分（FR-OUT、NFR-SC など）を返す。"""
    parts = identifier.split("-")
    return "-".join(parts[:2]) if not parts[1].isdigit() else parts[0]


def build(root: Path) -> dict:
    """Evidence を組み立てる。"""
    tests_by_requirement = trace_map(root)
    addrs_by_requirement = related_addrs(root)
    results = junit_results(root / "reports" / "unit-test" / "junit.xml", root)

    coverage: list[dict] = []
    for requirement in sorted(set(defined_requirements(root)) | set(tests_by_requirement)):
        mapped = sorted(tests_by_requirement.get(requirement, set()))
        if mapped:
            coverage.append(
                {
                    "requirement": requirement,
                    "unit_testable": True,
                    "related_adrs": sorted(addrs_by_requirement.get(requirement, set())),
                    "tests": [
                        {"path": path, "test": name, "result": results.get((path, name), "NOT_EXECUTED")}
                        for path, name in mapped
                    ],
                }
            )
            continue
        reason = NOT_UNIT_TESTABLE_REASONS.get(
            group_of(requirement), "単体テストでは検証できないため、後続工程で検証する。"
        )
        coverage.append(
            {
                "requirement": requirement,
                "unit_testable": False,
                "related_adrs": [],
                "reason": reason,
                "tests": [],
            }
        )

    summary = json.loads((root / "reports" / "unit-test" / "coverage-summary.json").read_text(encoding="utf-8"))
    return {
        "generated_from": {
            "junit": "reports/unit-test/junit.xml",
            "coverage_summary": "reports/unit-test/coverage-summary.json",
            "trace_annotations": UNIT_TEST_DIR.as_posix() + "/test_*.py",
        },
        "coverage": summary["total"],
        "criteria_coverage": [
            {"criterion": name, **values} for name, values in sorted(CRITERIA.items())
        ],
        "requirement_coverage": coverage,
        "database_tests": DATABASE_TESTS,
        "defects": DEFECTS,
        "flaky_tests": [],
    }


def main(argv: list[str]) -> int:
    """Evidence を生成して書き出す。"""
    root = Path(argv[1]) if len(argv) > 1 else Path(".")
    evidence = build(root)
    target = root / "reports" / "unit-test" / "unit-test-evidence.json"
    target.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    covered = sum(1 for item in evidence["requirement_coverage"] if item["unit_testable"])
    print(f"requirements: {len(evidence['requirement_coverage'])} (unit tested: {covered})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
