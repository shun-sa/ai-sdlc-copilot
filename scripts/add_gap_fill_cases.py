"""Coverage Gap Analysis（repair cycle 1）で追加した AI GAP_FILL Case を登録する。

SR-IT-001（NFR-SC-04 / NFR-SC-05 / FR-060 手順9 の検証方法）と
QR-IT-001（UC の同時実行受入基準）の是正で Required Coverage へ追加した
ICOV-071〜ICOV-087 を補うケースを、既存の IT-AI-GF-001〜011 に続けて追加する。
AI INITIAL Case（ai-initial-cases.json）は変更しない。
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "reports" / "integration-test" / "ai-gap-fill-cases.json"

NEW_CASES = [
    {
        "case_id": "IT-AI-GF-012",
        "title": "CSRF対策用トークンの無い購入者画面の更新要求が拒否される",
        "requirement_id": "NFR-SC-05",
        "related_adr": "ADDR-002",
        "test_category": "セキュリティ（CSRF）",
        "criterion": "authentication",
        "coverage_keys": ["CK-NFRSC05-01"],
        "precondition": "購入者が画面（SCR-004）からログインし、Cookie のログインセッションを保持している。公開商品の在庫単位が1件存在する",
        "input": "①CSRF対策用トークンを含まない POST /cart/lines ②正しいトークンを含む同一要求",
        "steps": (
            "1. CSRF 検証を有効にしたクライアントでログイン画面を表示し、トークンを取得してログインする\n"
            "2. トークンを付けずに POST /cart/lines を送信する\n"
            "3. 応答とカート明細件数を確認する\n"
            "4. 商品詳細画面からトークンを取得し、同じ内容を再送する\n"
            "5. 応答とカート明細件数を確認する"
        ),
        "expected_result": (
            "②はトークンが無いため 403 で拒否され、カート明細は作成されない（データ変更0件）。"
            "④はカート明細が1件作成され、カート画面へ遷移する（NFR-SC-05、VUL-06）"
        ),
    },
    {
        "case_id": "IT-AI-GF-013",
        "title": "CSRF対策用トークンの無い管理者画面の更新要求が拒否される",
        "requirement_id": "NFR-SC-05",
        "related_adr": "ADDR-002",
        "test_category": "セキュリティ（CSRF）",
        "criterion": "authentication",
        "coverage_keys": ["CK-NFRSC05-02"],
        "precondition": "支払済の注文が1件存在し、管理者が画面からログインしている",
        "input": "①CSRF対策用トークンを含まない出荷登録要求 ②正しいトークンを含む同一要求",
        "steps": (
            "1. 管理者が CSRF 検証を有効にしたクライアントでログインする\n"
            "2. トークンを付けずに POST /admin/purchase-orders/{id}/ship を送信する\n"
            "3. 応答と注文の状態・配送伝票番号・状態履歴件数を確認する\n"
            "4. 注文詳細画面からトークンを取得して同じ内容を再送し、注文の状態を確認する"
        ),
        "expected_result": (
            "②は 403 で拒否され、注文状態は支払済のまま、配送伝票番号・出荷日時は未設定、状態履歴は2件のまま。"
            "④は出荷済へ遷移し配送伝票番号が記録される（NFR-SC-05、VUL-06）"
        ),
    },
    {
        "case_id": "IT-AI-GF-014",
        "title": "管理者画面に表示する氏名・配送先・商品名がHTMLエスケープされる",
        "requirement_id": "NFR-SC-05",
        "related_adr": "ADDR-006",
        "test_category": "セキュリティ（XSS）",
        "criterion": "api",
        "coverage_keys": ["CK-NFRSC05-03"],
        "precondition": "氏名・商品名・配送先に script タグ等を含む値で会員登録・商品登録・注文確定を行っている",
        "input": "氏名・受取人氏名・市区町村番地・商品名に script タグおよび img タグ（onerror属性）を含む値",
        "steps": (
            "1. script タグを含む氏名で会員登録し、script タグを含む商品名の在庫単位を注文する\n"
            "2. 管理者でログインし、注文一覧（管理）・注文詳細（管理）・在庫単位一覧（管理）を表示する\n"
            "3. 各応答本文を確認する"
        ),
        "expected_result": (
            "いずれの画面でも生の script タグ・img タグが応答本文に現れず、"
            "エスケープ済みの文字列（&lt;script&gt; など）として出力される（NFR-SC-05、VUL-05）"
        ),
    },
    {
        "case_id": "IT-AI-GF-015",
        "title": "購入者画面に表示する氏名・商品名・配送先がHTMLエスケープされる",
        "requirement_id": "NFR-SC-05",
        "related_adr": "ADDR-006",
        "test_category": "セキュリティ（XSS）",
        "criterion": "api",
        "coverage_keys": ["CK-NFRSC05-04"],
        "precondition": "氏名・商品名・配送先に script タグ等を含む値で会員登録・商品登録・注文確定を行っている",
        "input": "氏名・受取人氏名・市区町村番地・商品名に script タグおよび img タグ（onerror属性）を含む値",
        "steps": (
            "1. script タグを含む氏名で会員登録し、script タグを含む商品名の在庫単位を注文する\n"
            "2. 購入者でログインし、商品一覧・商品詳細・注文履歴・注文詳細を表示する\n"
            "3. 各応答本文を確認する"
        ),
        "expected_result": (
            "いずれの画面でも生の script タグ・img タグが応答本文に現れず、"
            "エスケープ済みの文字列として出力される（NFR-SC-05、VUL-05）"
        ),
    },
    {
        "case_id": "IT-AI-GF-016",
        "title": "Web APIの入力項目へのSQL・OSコマンド攻撃文字列が成立しない",
        "requirement_id": "NFR-SC-04",
        "related_adr": "ADDR-007",
        "test_category": "セキュリティ（インジェクション）",
        "criterion": "error-handling",
        "coverage_keys": ["CK-NFRSC04-01"],
        "precondition": "購入者・管理者・公開商品の在庫単位が登録済みで、業務データの件数を記録している",
        "input": "SQL インジェクション（'OR'1'='1、DROP TABLE item、UNION SELECT 等）と OS コマンドインジェクション（$(id)、`id`、| cat /etc/passwd 等）の攻撃文字列",
        "steps": (
            "1. 会員登録・ログイン・商品一覧検索・商品詳細・カート明細追加・クーポン適用・"
            "管理者の在庫単位検索／注文検索・支払の各入力項目（要求本文・クエリ・パス）へ攻撃文字列を送信する\n"
            "2. 各応答のHTTPステータスを確認する\n"
            "3. 業務データの件数と、通常の商品一覧照会が成功することを確認する"
        ),
        "expected_result": (
            "すべて入力エラー（400）・認証失敗（401）・対象なし（404）・業務エラー（409）または通常処理（200）となり、"
            "システムエラー（5xx）とSQLの実行エラーは0件。業務データの件数は変化せず、表は削除されていない（NFR-SC-04、VUL-04）"
        ),
    },
    {
        "case_id": "IT-AI-GF-017",
        "title": "画面フォーム・検索条件へのSQL・OSコマンド攻撃文字列が成立しない",
        "requirement_id": "NFR-SC-04",
        "related_adr": "ADDR-006",
        "test_category": "セキュリティ（インジェクション）",
        "criterion": "error-handling",
        "coverage_keys": ["CK-NFRSC04-02"],
        "precondition": "管理者と公開商品の在庫単位が登録済みで、業務データの件数を記録している",
        "input": "SQL・OSコマンドの攻撃文字列（IT-AI-GF-016 と同一の文字列集合）",
        "steps": (
            "1. 会員登録画面・ログイン画面のフォームへ攻撃文字列を送信する\n"
            "2. 商品一覧の検索条件（キーワード・分類ID）へ攻撃文字列を送信する\n"
            "3. 管理者の在庫単位一覧（SKU・商品名）・注文一覧（注文番号・購入者メールアドレス）へ攻撃文字列を送信する\n"
            "4. 各応答と業務データの件数を確認する"
        ),
        "expected_result": (
            "すべて入力エラーまたは通常の処理となり、システムエラーは0件。"
            "業務データの件数は変化しない（NFR-SC-04、VUL-04）"
        ),
    },
    {
        "case_id": "IT-AI-GF-018",
        "title": "初期データ定義ファイルの攻撃文字列が値域違反または文字列として扱われる",
        "requirement_id": "NFR-SC-04",
        "related_adr": "ADDR-010",
        "test_category": "セキュリティ（インジェクション）",
        "criterion": "database",
        "coverage_keys": ["CK-NFRSC04-03"],
        "precondition": "データが未投入の状態である",
        "input": "①仕入先コード・分類コードに攻撃文字列を含む定義ファイル ②氏名・仕入先名・商品名・商品説明に攻撃文字列を含む定義ファイル",
        "steps": (
            "1. コード項目に攻撃文字列を含む定義ファイルで初期データ一括投入を実行する\n"
            "2. 終了コードと各データの件数を確認する\n"
            "3. 名称項目に攻撃文字列を含む定義ファイルで実行する\n"
            "4. 終了コードと保存された値を確認する"
        ),
        "expected_result": (
            "①は文字種の値域違反（E-060-04）として異常終了し、1件も投入されない。"
            "②は正常終了し、攻撃文字列が文字列としてそのまま保存される（表の削除・意図しないデータ変更は発生しない。NFR-SC-04、VUL-04）"
        ),
    },
    {
        "case_id": "IT-AI-GF-019",
        "title": "全削除指定の実行後は旧認証トークン・旧ログインセッションが拒否される",
        "requirement_id": "FR-060",
        "related_adr": "ADDR-002",
        "test_category": "認証状態の無効化",
        "criterion": "authentication",
        "coverage_keys": ["CK-FR060-03"],
        "precondition": "初期データ投入済みの購入者が、認証トークンと画面のログインセッションの両方を保持している",
        "input": "全削除指定（--reset）つきの初期データ一括投入（投入する利用者は別のメールアドレス）",
        "steps": (
            "1. 定義ファイルを投入し、購入者がAPIと画面の双方でログインする\n"
            "2. 認証トークン・セッション・監査ログの件数を記録する\n"
            "3. 全削除指定つきで別の定義ファイルを投入する\n"
            "4. 認証トークン・セッションの件数、監査ログの件数を確認する\n"
            "5. 旧トークンで GET /api/auth/me、旧セッションで GET /cart を要求する"
        ),
        "expected_result": (
            "全削除指定の実行で認証トークンは連動削除され、セッション表の全行も削除される（0件）。"
            "旧トークンでの認証付きAPIは 401 AUTHENTICATION_REQUIRED、旧セッションでの画面要求はログイン画面へ遷移する。"
            "監査ログは削除されず1件増える（FR-060 手順9、ADDR-002 DD-009〜DD-011）"
        ),
    },
    {
        "case_id": "IT-AI-GF-020",
        "title": "正規化後が同一のメールアドレスの同時会員登録は1件だけ成功する",
        "requirement_id": "FR-001",
        "related_adr": "ADDR-001",
        "test_category": "同時実行",
        "criterion": "database",
        "coverage_keys": ["CK-FR001-05"],
        "precondition": "対象のメールアドレスの利用者が存在しない（トランザクションを確定する使い捨てテストDBを使用）",
        "input": "正規化後が同一となる5種類のメールアドレス（大文字小文字違い・先頭空白）での会員登録要求",
        "steps": (
            "1. 5本の接続から同時に POST /api/auth/register を送信する\n"
            "2. 5件の応答のHTTPステータスとエラーコードを確認する\n"
            "3. 当該メールアドレスの利用者件数を確認する\n"
            "4. メールアドレスを変えて計10試行行う"
        ),
        "expected_result": (
            "各試行で 201 が1件、409 EMAIL_ALREADY_REGISTERED が4件となり、500 は0件。"
            "当該メールアドレスの利用者は1件のみ（AC-UC-001-017）"
        ),
    },
    {
        "case_id": "IT-AI-GF-021",
        "title": "同一在庫単位への同時カート明細追加でも合算数量が10個を超えない",
        "requirement_id": "FR-021",
        "related_adr": "ADDR-001",
        "test_category": "同時実行",
        "criterion": "database",
        "coverage_keys": ["CK-FR021-05"],
        "precondition": "在庫数量20の在庫単位が1件あり、購入者の利用中カートは明細0件である",
        "input": "同一在庫単位・数量6のカート明細追加要求を2件",
        "steps": (
            "1. 試行ごとにカート明細を0件に戻す\n"
            "2. 2本の接続から同時に POST /api/cart/lines（数量6）を送信する\n"
            "3. 応答・カート明細・在庫数量を確認する\n"
            "4. 10試行行う"
        ),
        "expected_result": (
            "各試行で 200 が1件、409 QUANTITY_LIMIT_EXCEEDED が1件。"
            "カート明細は1件・数量6で、在庫数量は20のまま（AC-UC-004-025）"
        ),
    },
    {
        "case_id": "IT-AI-GF-022",
        "title": "同一注文への同時支払では承認済み決済記録が1件だけ登録される",
        "requirement_id": "FR-031",
        "related_adr": "ADDR-009",
        "test_category": "同時実行",
        "criterion": "state-transition",
        "coverage_keys": ["CK-FR031-07"],
        "precondition": "試行ごとに注文受付の注文を1件新たに用意する",
        "input": "mock_result=approve の支払要求を2件",
        "steps": (
            "1. 注文を作成し、在庫数量を記録する\n"
            "2. 2本の接続から同時に支払要求を送信する\n"
            "3. 応答・決済記録・注文状態履歴・在庫数量を確認する\n"
            "4. 10試行行う"
        ),
        "expected_result": (
            "各試行で 200（paid）が1件、409 INVALID_STATUS_TRANSITION（current_status=paid）が1件。"
            "承認済み決済記録は1件のみ、注文受付→支払済の状態履歴は1件のみ、在庫数量は変化しない（AC-UC-007-013）"
        ),
    },
    {
        "case_id": "IT-AI-GF-023",
        "title": "同一注文への支払とキャンセルの同時実行が逐次実行と一致する",
        "requirement_id": "FR-031",
        "related_adr": "ADDR-009",
        "test_category": "同時実行",
        "criterion": "state-transition",
        "coverage_keys": ["CK-FR031-08"],
        "precondition": "試行ごとに注文受付の注文を1件新たに用意し、決済サービス（模擬）の受信記録を初期化する",
        "input": "mock_result=approve の支払要求とキャンセル要求を同時に1件ずつ",
        "steps": (
            "1. 注文を作成し、在庫数量と決済サービス（模擬）の受信記録を初期化する\n"
            "2. 2本の接続から同時に支払要求とキャンセル要求を送信する\n"
            "3. 応答・決済記録・注文状態履歴・在庫数量・決済サービス（模擬）の受信記録を確認する\n"
            "4. 10試行行う"
        ),
        "expected_result": (
            "各試行でキャンセルは 200（cancelled）。支払は (a) 409 INVALID_STATUS_TRANSITION（current_status=cancelled）"
            "で決済記録0件・状態履歴2件・決済サービス（模擬）が当該注文の決済要求を受けていない（FR-031 手順5 は"
            "E-031-05 で決済要求を送信しないと定める）か、(b) 200（paid）で承認済み決済記録1件・状態履歴3件のいずれか。"
            "いずれも最終状態は cancelled で在庫戻しは1回だけ（AC-UC-007-019）"
        ),
    },
    {
        "case_id": "IT-AI-GF-024",
        "title": "同一注文への同時キャンセルでは在庫が1回だけ戻る",
        "requirement_id": "FR-034",
        "related_adr": "ADDR-001",
        "test_category": "同時実行",
        "criterion": "state-transition",
        "coverage_keys": ["CK-FR034-03"],
        "precondition": "試行ごとに2明細（数量2・数量3）を持つ注文受付の注文を1件新たに用意する",
        "input": "注文キャンセル要求を2件",
        "steps": (
            "1. 注文を作成し、2つの在庫単位の在庫数量を記録する\n"
            "2. 2本の接続から同時にキャンセル要求を送信する\n"
            "3. 応答・在庫数量・注文状態履歴を確認する\n"
            "4. 10試行行う"
        ),
        "expected_result": (
            "各試行で 200（cancelled）が1件、409 INVALID_STATUS_TRANSITION（current_status=cancelled）が1件。"
            "在庫数量は＋2・＋3 だけ増え、キャンセルの状態履歴は1件のみ（AC-UC-009-007）"
        ),
    },
    {
        "case_id": "IT-AI-GF-025",
        "title": "同一注文への同時の出荷登録は1件だけ成功する",
        "requirement_id": "FR-043",
        "related_adr": "ADDR-001",
        "test_category": "同時実行",
        "criterion": "state-transition",
        "coverage_keys": ["CK-FR043-03"],
        "precondition": "試行ごとに支払済の注文を1件新たに用意し、管理者2名がログイン済みである",
        "input": "配送伝票番号 TRK-X と TRK-Y の出荷登録要求",
        "steps": (
            "1. 注文を作成して支払済にし、在庫数量を記録する\n"
            "2. 2名の管理者が同時に出荷登録を送信する\n"
            "3. 応答・注文の配送伝票番号・状態履歴の実行者・在庫数量を確認する\n"
            "4. 10試行行う"
        ),
        "expected_result": (
            "各試行で 200 が1件、409 INVALID_STATUS_TRANSITION（current_status=shipped）が1件。"
            "支払済→出荷済の状態履歴は1件のみで、実行者と配送伝票番号は 200 を受けた管理者と一致し、在庫数量は変化しない（AC-UC-011-020）"
        ),
    },
    {
        "case_id": "IT-AI-GF-026",
        "title": "管理者キャンセルと購入者キャンセルの同時実行では在庫が1回だけ戻る",
        "requirement_id": "FR-045",
        "related_adr": "ADDR-001",
        "test_category": "同時実行",
        "criterion": "state-transition",
        "coverage_keys": ["CK-FR045-02"],
        "precondition": "試行ごとに注文受付の注文を1件新たに用意し、管理者と購入者がログイン済みである",
        "input": "注文キャンセル（管理者）要求と注文キャンセル（購入者）要求",
        "steps": (
            "1. 注文を作成し、在庫数量を記録する\n"
            "2. 管理者と購入者が同時にキャンセルを送信する\n"
            "3. 応答・在庫数量・キャンセルの状態履歴の実行者区分を確認する\n"
            "4. 10試行行う"
        ),
        "expected_result": (
            "各試行で一方が 200（cancelled）、もう一方が 409 INVALID_STATUS_TRANSITION（current_status=cancelled）。"
            "在庫数量は＋2 だけ増え、キャンセルの状態履歴は1件で実行者区分は 200 を受けた側と一致する（AC-UC-012-009）"
        ),
    },
    {
        "case_id": "IT-AI-GF-027",
        "title": "管理者キャンセルと出荷登録の同時実行はどちらか一方だけが成功する",
        "requirement_id": "FR-045",
        "related_adr": "ADDR-001",
        "test_category": "同時実行",
        "criterion": "state-transition",
        "coverage_keys": ["CK-FR045-03"],
        "precondition": "試行ごとに支払済（承認済み決済記録1件）の注文を1件新たに用意し、管理者2名がログイン済みである",
        "input": "注文キャンセル（管理者）要求と配送伝票番号 TRK-Y の出荷登録要求",
        "steps": (
            "1. 注文を作成して支払済にし、在庫数量と状態履歴件数を記録する\n"
            "2. 2名の管理者が同時にキャンセルと出荷登録を送信する\n"
            "3. 応答・注文の状態・在庫数量・出荷日時・キャンセル日時・状態履歴・決済記録を確認する\n"
            "4. 10試行行う"
        ),
        "expected_result": (
            "各試行で一方だけが 200 となり、もう一方は 409 INVALID_STATUS_TRANSITION（current_status は成功側に応じて"
            " cancelled または shipped）。キャンセル成功時は在庫が＋3 で出荷日時・配送伝票番号は未設定、"
            "出荷成功時は在庫が変化せずキャンセル日時は未設定。状態履歴の追加は1件のみ、承認済み決済記録は1件のまま（AC-UC-012-010）"
        ),
    },
    {
        "case_id": "IT-AI-GF-028",
        "title": "管理者キャンセルと購入者の支払の同時実行が逐次実行と同じ結果になる",
        "requirement_id": "FR-045",
        "related_adr": "ADDR-009",
        "test_category": "同時実行",
        "criterion": "state-transition",
        "coverage_keys": ["CK-FR045-04"],
        "precondition": "試行ごとに注文受付（合計5,500円）の注文を1件新たに用意し、管理者と購入者がログイン済みである",
        "input": "注文キャンセル（管理者）要求と mock_result=approve の支払要求",
        "steps": (
            "1. 注文を作成し、合計金額と在庫数量を確認する\n"
            "2. 管理者のキャンセルと購入者の支払を同時に送信する\n"
            "3. 応答・決済記録・注文状態履歴・支払日時・在庫数量を確認する\n"
            "4. 10試行行う"
        ),
        "expected_result": (
            "各試行でキャンセルは 200（cancelled、can_ship/can_deliver/can_cancel はいずれも false）。"
            "支払は (a) 409（current_status=cancelled）でキャンセル応答の決済記録は空・支払日時は未設定・状態履歴2件、"
            "または (b) 200（paid）でキャンセル応答の決済記録が承認・金額5,500円の1件・状態履歴3件のいずれか。"
            "最終状態は cancelled で在庫は＋2 だけ戻る（AC-UC-012-011）"
        ),
    },
]


def main() -> int:
    """AI GAP_FILL Case を追加する（既存ケースは変更しない）。"""
    doc = json.loads(PATH.read_text(encoding="utf-8"))
    existing = {case["case_id"] for case in doc["cases"]}
    for case in NEW_CASES:
        if case["case_id"] in existing:
            raise SystemExit(f"case_id が重複しています: {case['case_id']}")
        doc["cases"].append(
            {
                "case_id": case["case_id"],
                "origin": "AI_GENERATED",
                "generation_stage": "GAP_FILL",
                "gap_id": "",
                "title": case["title"],
                "requirement_id": case["requirement_id"],
                "related_adr": case["related_adr"],
                "test_category": case["test_category"],
                "criterion": case["criterion"],
                "coverage_keys": case["coverage_keys"],
                "precondition": case["precondition"],
                "input": case["input"],
                "steps": case["steps"],
                "expected_result": case["expected_result"],
                "execution_type": "AUTOMATABLE",
            }
        )

    doc["derived_from"] = [
        "docs/requirements/functional_requirements.md",
        "docs/requirements/non_functional_requirements.md",
        "docs/requirements/use-cases/UC-001.md..UC-013.md（受入基準）",
        "docs/specifications/api-contract.md",
        "docs/addr/ADDR-001.md..ADDR-012.md",
    ]
    doc["note"] = (
        "Coverage Gap Analysis（case-comparison.json / coverage-gap-report.json）で MISSING と判定された "
        "Required Coverage を補うために追加したTest Case。"
        "IT-AI-GF-001〜011 は初回の Gap Fill、IT-AI-GF-012〜028 は repair cycle 1 で "
        "Required Coverage の導出元を是正（NFR-SC の検証方法・UC の同時実行受入基準を追加）した結果の Gap Fill。"
        "AI INITIAL Case（ai-initial-cases.json、snapshot initial-1）は変更していない。"
    )
    PATH.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"gap fill cases: {len(doc['cases'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
