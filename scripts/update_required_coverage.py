"""Required Coverage（結合試験で検証すべき観点）へ、NFR-SC の検証方法と同時実行ACの観点を追加する。

SR-IT-001（NFR-SC-04 / NFR-SC-05 / FR-060 手順9 の検証方法が導出元に無い）と
QR-IT-001（UC の同時実行受入基準が導出元に無い）の根本原因是正として、
derivation.sources・integration_points と required_coverage を追加する。
既存の 70 件は変更しない。
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "reports" / "integration-test" / "required-coverage.json"

NEW_SOURCES = [
    "docs/requirements/non_functional_requirements.md",
]

NEW_INTEGRATION_POINTS = [
    "画面（Cookieセッション）→ CsrfViewMiddleware → 画面ビュー → Service → PostgreSQL",
    "Service → Django テンプレート（自動エスケープ）→ 画面出力",
    "複数接続・実トランザクションによる同時要求 → 行ロック → PostgreSQL",
]

NEW_ITEMS = [
    {
        "coverage_id": "ICOV-071",
        "coverage_key": "CK-NFRSC05-01",
        "requirement_id": "NFR-SC-05",
        "related_adr": ["ADDR-002", "ADDR-006"],
        "integration_point": "画面（Cookieセッション）→ CsrfViewMiddleware → views_cart → carts → PostgreSQL",
        "test_category": "セキュリティ（CSRF）",
        "criterion": "authentication",
        "condition": "Cookie のログインセッションで認証した購入者の更新要求（カート明細追加）を、CSRF対策用トークンなしで送信する。あわせてトークンありの同一要求も送信する",
        "expected_behavior": "トークンなしの要求は拒否され（403）、カート明細は作成されない（データ変更0件）。トークンありの要求は通常どおり成功する（NFR-SC-05、VUL-06）",
    },
    {
        "coverage_id": "ICOV-072",
        "coverage_key": "CK-NFRSC05-02",
        "requirement_id": "NFR-SC-05",
        "related_adr": ["ADDR-001", "ADDR-002", "ADDR-006"],
        "integration_point": "管理者画面（Cookieセッション）→ CsrfViewMiddleware → views_admin → admin_orders → PostgreSQL",
        "test_category": "セキュリティ（CSRF）",
        "criterion": "authentication",
        "condition": "Cookie のログインセッションで認証した管理者の更新要求（出荷登録）を、CSRF対策用トークンなしで送信する。あわせてトークンありの同一要求も送信する",
        "expected_behavior": "トークンなしの要求は拒否され（403）、注文状態・配送伝票番号・注文状態履歴は変化しない。トークンありの要求は出荷済へ遷移する（NFR-SC-05、VUL-06）",
    },
    {
        "coverage_id": "ICOV-073",
        "coverage_key": "CK-NFRSC05-03",
        "requirement_id": "NFR-SC-05",
        "related_adr": ["ADDR-004", "ADDR-006"],
        "integration_point": "PostgreSQL → admin_orders → Django テンプレート（自動エスケープ）→ 管理者画面（SCR-101〜SCR-103）",
        "test_category": "セキュリティ（XSS）",
        "criterion": "api",
        "condition": "氏名・配送先（受取人氏名・市区町村番地）・商品名に HTML の script タグ等を含む値を登録し、管理者の注文一覧・注文詳細・在庫単位一覧を表示する",
        "expected_behavior": "すべての出力値が HTML エスケープされ、応答本文に生の script タグ・イベントハンドラ属性が現れない（エスケープ漏れ0件。NFR-SC-05、VUL-05）",
    },
    {
        "coverage_id": "ICOV-074",
        "coverage_key": "CK-NFRSC05-04",
        "requirement_id": "NFR-SC-05",
        "related_adr": ["ADDR-004", "ADDR-006"],
        "integration_point": "PostgreSQL → catalog/orders → Django テンプレート（自動エスケープ）→ 購入者画面（SCR-001・SCR-002・SCR-009・SCR-010）",
        "test_category": "セキュリティ（XSS）",
        "criterion": "api",
        "condition": "氏名・商品名・配送先に HTML の script タグ等を含む値を登録し、商品一覧・商品詳細・注文履歴・注文詳細を表示する",
        "expected_behavior": "すべての出力値が HTML エスケープされ、応答本文に生の script タグ・イベントハンドラ属性が現れない（NFR-SC-05、VUL-05）",
    },
    {
        "coverage_id": "ICOV-075",
        "coverage_key": "CK-NFRSC04-01",
        "requirement_id": "NFR-SC-04",
        "related_adr": ["ADDR-006", "ADDR-007"],
        "integration_point": "Web API（要求本文・クエリ・パス）→ validators → Service → ORM（プレースホルダ）→ PostgreSQL",
        "test_category": "セキュリティ（インジェクション）",
        "criterion": "error-handling",
        "condition": "会員登録・ログイン・商品検索・商品詳細・カート明細追加・クーポン適用・管理者検索・支払の各入力項目へ、SQL インジェクションと OS コマンドインジェクションの攻撃文字列を送信する",
        "expected_behavior": "いずれも入力エラーまたは通常の処理となり、システムエラー（5xx）とSQLの実行エラーが0件で、業務データの件数が変化しない。攻撃文字列の送信後も各表を通常どおり参照できる（NFR-SC-04、VUL-04）",
    },
    {
        "coverage_id": "ICOV-076",
        "coverage_key": "CK-NFRSC04-02",
        "requirement_id": "NFR-SC-04",
        "related_adr": ["ADDR-006", "ADDR-007"],
        "integration_point": "画面フォーム・検索条件 → 画面ビュー → validators → Service → ORM → PostgreSQL",
        "test_category": "セキュリティ（インジェクション）",
        "criterion": "error-handling",
        "condition": "会員登録画面・ログイン画面・商品一覧の検索条件・管理者の在庫単位一覧／注文一覧の検索条件へ、SQL・OSコマンドの攻撃文字列を送信する",
        "expected_behavior": "いずれも入力エラーまたは通常の処理となり、システムエラーが0件で、業務データの件数が変化しない（NFR-SC-04、VUL-04）",
    },
    {
        "coverage_id": "ICOV-077",
        "coverage_key": "CK-NFRSC04-03",
        "requirement_id": "NFR-SC-04",
        "related_adr": ["ADDR-010"],
        "integration_point": "初期データ一括投入の定義ファイル → SeedLoader（値域・文字種判定）→ ORM → PostgreSQL",
        "test_category": "セキュリティ（インジェクション）",
        "criterion": "database",
        "condition": "定義ファイルのコード項目（仕入先コード・分類コード）と名称項目（氏名・仕入先名・商品名・商品説明）へ攻撃文字列を記載して初期データ一括投入を実行する",
        "expected_behavior": "文字種が定められたコード項目は値域違反として1件も投入せず異常終了する（E-060-04）。文字種の制限がない名称項目は文字列としてそのまま保存され、表の削除・意図しないデータ変更は発生しない（NFR-SC-04、VUL-04）",
    },
    {
        "coverage_id": "ICOV-078",
        "coverage_key": "CK-FR060-03",
        "requirement_id": "FR-060",
        "related_adr": ["ADDR-002", "ADDR-010"],
        "integration_point": "管理コマンド（--reset）→ SeedLoader → User/AuthToken/Session → 認証付きAPI・画面セッション",
        "test_category": "認証状態の無効化",
        "criterion": "authentication",
        "condition": "認証トークンと画面のログインセッションを保持した状態で、全削除指定つきの初期データ一括投入を実行する",
        "expected_behavior": "削除した利用者の認証トークンは連動削除され、セッション表の全行も同一トランザクションで削除される。実行後、旧トークンでの認証付きAPIは 401 AUTHENTICATION_REQUIRED、旧セッションでの画面要求はログイン画面へ戻る。監査ログは削除されない（FR-060 手順9、ADDR-002 DD-009〜DD-011）",
    },
    {
        "coverage_id": "ICOV-079",
        "coverage_key": "CK-FR001-05",
        "requirement_id": "FR-001",
        "related_adr": ["ADDR-001", "ADDR-008"],
        "integration_point": "POST /api/auth/register（同時5要求）→ services.accounts → User 一意制約 → PostgreSQL",
        "test_category": "同時実行",
        "criterion": "database",
        "condition": "正規化（前後空白除去・英小文字化）後が同一となる5種類のメールアドレスで会員登録要求を同時に送信する（AC-UC-001-017、10試行）",
        "expected_behavior": "各試行で 201 が1件、409 EMAIL_ALREADY_REGISTERED が4件となり、システムエラーは0件。当該メールアドレスの利用者は1件のみ登録される",
    },
    {
        "coverage_id": "ICOV-080",
        "coverage_key": "CK-FR021-05",
        "requirement_id": "FR-021",
        "related_adr": ["ADDR-001"],
        "integration_point": "POST /api/cart/lines（同時2要求）→ services.carts（カート行ロック）→ PostgreSQL",
        "test_category": "同時実行",
        "criterion": "database",
        "condition": "同一在庫単位・数量6のカート明細追加を2本の接続から同時に送信する（AC-UC-004-025、10試行）",
        "expected_behavior": "各試行で 200 が1件、409 QUANTITY_LIMIT_EXCEEDED が1件となる。カート明細は1件・数量6（12にならない）で、在庫数量は変化しない",
    },
    {
        "coverage_id": "ICOV-081",
        "coverage_key": "CK-FR031-07",
        "requirement_id": "FR-031",
        "related_adr": ["ADDR-001", "ADDR-009"],
        "integration_point": "POST /api/purchase-orders/{id}/pay（同時2要求）→ 注文行ロック → PaymentRecord/状態履歴 → PostgreSQL",
        "test_category": "同時実行",
        "criterion": "state-transition",
        "condition": "注文受付の同一注文へ mock_result=approve の支払要求を2件同時に送信する（AC-UC-007-013、10試行）",
        "expected_behavior": "各試行で 200 が1件、409 INVALID_STATUS_TRANSITION（current_status=paid）が1件。承認済み決済記録は1件のみ、注文受付→支払済の状態履歴は1件のみで、在庫数量は変化しない",
    },
    {
        "coverage_id": "ICOV-082",
        "coverage_key": "CK-FR031-08",
        "requirement_id": "FR-031",
        "related_adr": ["ADDR-001", "ADDR-009"],
        "integration_point": "POST /api/purchase-orders/{id}/pay と /cancel（同時）→ 注文行ロック → 決済サービス（模擬）・在庫 → PostgreSQL",
        "test_category": "同時実行",
        "criterion": "state-transition",
        "condition": "注文受付の同一注文へ支払要求（approve）とキャンセル要求を同時に送信する（AC-UC-007-019、10試行）",
        "expected_behavior": "各試行でキャンセルは 200（cancelled）。支払は (a) 409 INVALID_STATUS_TRANSITION（current_status=cancelled）で決済記録0件・状態履歴2件・決済サービス（模擬）が当該注文の決済要求を受けていない（FR-031 手順5「決済要求を送信しない」）か、(b) 200（paid）で承認済み決済記録1件・状態履歴3件のいずれかとなる。いずれも最終状態は cancelled で在庫戻しは1回だけ",
    },
    {
        "coverage_id": "ICOV-083",
        "coverage_key": "CK-FR034-03",
        "requirement_id": "FR-034",
        "related_adr": ["ADDR-001"],
        "integration_point": "POST /api/purchase-orders/{id}/cancel（同時2要求）→ 注文行・在庫単位行ロック → PostgreSQL",
        "test_category": "同時実行",
        "criterion": "state-transition",
        "condition": "複数明細を持つ同一注文へキャンセル要求を2件同時に送信する（AC-UC-009-007、10試行）",
        "expected_behavior": "各試行で 200 が1件、409 INVALID_STATUS_TRANSITION（current_status=cancelled）が1件。各在庫単位の在庫数量は明細数量ぶんだけ1回戻り、キャンセルの状態履歴は1件のみ",
    },
    {
        "coverage_id": "ICOV-084",
        "coverage_key": "CK-FR043-03",
        "requirement_id": "FR-043",
        "related_adr": ["ADDR-001"],
        "integration_point": "POST /api/admin/purchase-orders/{id}/ship（異なる管理者からの同時2要求）→ 注文行ロック → PostgreSQL",
        "test_category": "同時実行",
        "criterion": "state-transition",
        "condition": "支払済の同一注文へ、2人の管理者が別々の配送伝票番号で出荷登録を同時に送信する（AC-UC-011-020、10試行）",
        "expected_behavior": "各試行で 200 が1件、409 INVALID_STATUS_TRANSITION（current_status=shipped）が1件。支払済→出荷済の状態履歴は1件のみで、実行者と配送伝票番号は 200 を受けた側と一致し、在庫数量は変化しない",
    },
    {
        "coverage_id": "ICOV-085",
        "coverage_key": "CK-FR045-02",
        "requirement_id": "FR-045",
        "related_adr": ["ADDR-001"],
        "integration_point": "管理者キャンセルAPIと購入者キャンセルAPI（同時）→ 注文行・在庫単位行ロック → PostgreSQL",
        "test_category": "同時実行",
        "criterion": "state-transition",
        "condition": "注文受付の同一注文へ、管理者の注文キャンセルと購入者の注文キャンセルを同時に送信する（AC-UC-012-009、10試行）",
        "expected_behavior": "各試行で一方が 200（cancelled）、もう一方が 409 INVALID_STATUS_TRANSITION（current_status=cancelled）。在庫は1回だけ戻り、キャンセルの状態履歴は1件のみで、その実行者区分は 200 を受けた側と一致する",
    },
    {
        "coverage_id": "ICOV-086",
        "coverage_key": "CK-FR045-03",
        "requirement_id": "FR-045",
        "related_adr": ["ADDR-001"],
        "integration_point": "管理者キャンセルAPIと出荷登録API（同時）→ 注文行ロック → PostgreSQL",
        "test_category": "同時実行",
        "criterion": "state-transition",
        "condition": "支払済の同一注文へ、管理者の注文キャンセルと別の管理者の出荷登録を同時に送信する（AC-UC-012-010、10試行）",
        "expected_behavior": "各試行で一方だけが 200 となり、もう一方は 409 INVALID_STATUS_TRANSITION（current_status は成功側に応じて cancelled または shipped）。キャンセル成功時のみ在庫が戻り出荷日時・配送伝票番号は未設定、出荷成功時は在庫が変化せずキャンセル日時は未設定。状態履歴の追加は1件のみで、承認済み決済記録は1件のまま",
    },
    {
        "coverage_id": "ICOV-087",
        "coverage_key": "CK-FR045-04",
        "requirement_id": "FR-045",
        "related_adr": ["ADDR-001", "ADDR-009"],
        "integration_point": "管理者キャンセルAPIと購入者の支払API（同時）→ 注文行ロック → PaymentRecord・在庫 → PostgreSQL",
        "test_category": "同時実行",
        "criterion": "state-transition",
        "condition": "注文受付の同一注文（合計5,500円）へ、管理者の注文キャンセルと購入者の支払（approve）を同時に送信する（AC-UC-012-011、10試行）",
        "expected_behavior": "各試行でキャンセルは 200（cancelled、can_ship/can_deliver/can_cancel はいずれも false）。支払は (a) 409（current_status=cancelled、決済記録0件、状態履歴2件）または (b) 200（paid、承認済み決済記録1件・金額5,500円、状態履歴3件）のいずれかとなる。最終状態は cancelled で、在庫は1回だけ戻る",
    },
]


def main() -> int:
    """Required Coverage を更新する。"""
    doc = json.loads(PATH.read_text(encoding="utf-8"))
    derivation = doc["derivation"]

    for source in NEW_SOURCES:
        if source not in derivation["sources"]:
            derivation["sources"].append(source)
    for point in NEW_INTEGRATION_POINTS:
        if point not in derivation["integration_points"]:
            derivation["integration_points"].append(point)

    derivation["acceptance_criteria_sources"] = [
        "docs/requirements/use-cases/UC-001.md 9.17 AC-UC-001-017（同時会員登録）",
        "docs/requirements/use-cases/UC-004.md 9.25 AC-UC-004-025（同時カート明細追加）",
        "docs/requirements/use-cases/UC-007.md 9.13 AC-UC-007-013（同時支払）",
        "docs/requirements/use-cases/UC-007.md 9.19 AC-UC-007-019（支払とキャンセルの同時実行）",
        "docs/requirements/use-cases/UC-009.md 9.7 AC-UC-009-007（同時キャンセル）",
        "docs/requirements/use-cases/UC-011.md 9.20 AC-UC-011-020（同時出荷登録）",
        "docs/requirements/use-cases/UC-012.md 9.9 AC-UC-012-009（管理者・購入者の同時キャンセル）",
        "docs/requirements/use-cases/UC-012.md 9.10 AC-UC-012-010（管理者キャンセルと出荷登録）",
        "docs/requirements/use-cases/UC-012.md 9.11 AC-UC-012-011（管理者キャンセルと支払）",
    ]
    derivation["non_functional_verification_sources"] = [
        "docs/requirements/non_functional_requirements.md 8.1 NFR-SC-04（入力値検証の検証方法）",
        "docs/requirements/non_functional_requirements.md 8.1 NFR-SC-05（XSS・CSRF 対策の検証方法）",
        "docs/requirements/non_functional_requirements.md 8.2 VUL-04・VUL-05・VUL-06",
        "docs/requirements/non_functional_requirements.md 12.2 VDC-06（セキュリティテスト用データ）",
    ]
    derivation["correction"] = {
        "corrected_at": "2026-10-22T15:20:00+09:00",
        "repair_cycle": 1,
        "issues": ["SR-IT-001", "QR-IT-001"],
        "reason": (
            "初版（70件）の導出元に非機能要件（NFR-SC の検証方法）とUCの同時実行受入基準が含まれて"
            "おらず、CSRF・XSS・インジェクション・全削除後の認証状態・同時実行の必須ACが"
            "Required Coverage に現れていなかった。導出元を是正し、ICOV-071〜ICOV-087 を追加した。"
        ),
        "added_coverage_ids": [item["coverage_id"] for item in NEW_ITEMS],
        "existing_items_unchanged": True,
    }

    existing_keys = {item["coverage_key"] for item in doc["required_coverage"]}
    for item in NEW_ITEMS:
        if item["coverage_key"] in existing_keys:
            raise SystemExit(f"coverage_key が重複しています: {item['coverage_key']}")
        doc["required_coverage"].append(item)

    PATH.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"required_coverage: {len(doc['required_coverage'])} items")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
