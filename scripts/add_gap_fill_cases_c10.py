"""C10（テストされていない要件）の是正として追加した AI GAP_FILL Case を登録する。

Traceability Audit（FULL Scope）の C10 で不合格となった 124 件の要件のうち、
結合試験で正当に検証できる 41 観点（ICOV-088〜ICOV-128）を補う Test Case を、
既存の IT-AI-GF-001〜028 に続けて IT-AI-GF-029〜069 として追加する。

AI INITIAL Case（ai-initial-cases.json）は変更しない。
既存 GAP_FILL Case の内容（期待結果・手順・入力）も変更しない。
gap_id は Required Coverage の MISSING 一覧から毎回導出する参照値のため、
全 GAP_FILL Case について現在の Required Coverage に合わせて付け直す。
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "reports" / "integration-test"
PATH = REPORT_DIR / "ai-gap-fill-cases.json"

AUTOMATABLE = "AUTOMATABLE"

NEW_CASES = [
    {
        "case_id": "IT-AI-GF-029",
        "title": "支払が本システム内の模擬決済だけで完結し実決済サービスへ接続しない",
        "requirement_id": "FR-OUT-01",
        "related_adr": "ADDR-009",
        "test_category": "対象外機能（実決済連携）",
        "criterion": "end-to-end-flow",
        "coverage_keys": ["CK-FROUT01-01"],
        "precondition": "購入者が注文確定済の注文を1件持っている",
        "input": "①mock_result=approve の支払要求 ②外部ネットワークを遮断した状態",
        "steps": (
            "1. 購入者がカート明細追加→注文確定を行う\n"
            "2. 決済ゲートウェイの呼び出しを記録し、外部ネットワークへの接続を遮断する\n"
            "3. 支払（mock_result=approve）を要求する\n"
            "4. 使用された決済ゲートウェイ実装・決済要求の項目・決済記録を確認する"
        ),
        "expected_result": (
            "支払は200で成功し、使用された実装は MockPaymentGateway である。決済要求は注文番号・決済金額・"
            "通貨・模擬決済指示の4項目のみで、外部ネットワークへの接続は発生しない。取引参照番号は MOCK- で"
            "始まる内部生成値で、注文は支払済となる（FR-OUT-01）"
        ),
    },
    {
        "case_id": "IT-AI-GF-030",
        "title": "マスタ保守のWeb API・画面が存在しない",
        "requirement_id": "FR-OUT-02",
        "related_adr": "ADDR-007",
        "test_category": "対象外機能（マスタ保守）",
        "criterion": "api",
        "coverage_keys": ["CK-FROUT02-01"],
        "precondition": "管理者がログインしており、商品・分類・仕入先・在庫単位・クーポンが登録済み",
        "input": "商品・分類・仕入先・在庫単位・クーポンの登録・更新・削除を意図した14通りの要求",
        "steps": (
            "1. 各マスタへの POST / PATCH / DELETE を管理者の認証付きで送信する\n"
            "2. 各応答のHTTPステータスを確認する\n"
            "3. マスタの件数と、商品名・在庫単位の価格が変わっていないことを確認する\n"
            "4. 管理者の在庫単位一覧画面に含まれる更新フォームの送信先を確認する"
        ),
        "expected_result": (
            "いずれの要求も成功応答（2xx）とならず、マスタの件数・内容が変化しない。"
            "管理者画面の POST フォームはログアウトのみである（FR-OUT-02）"
        ),
    },
    {
        "case_id": "IT-AI-GF-031",
        "title": "入荷・在庫補充を登録する手段が存在しない",
        "requirement_id": "FR-OUT-03",
        "related_adr": "ADDR-001",
        "test_category": "対象外機能（入荷・在庫補充）",
        "criterion": "api",
        "coverage_keys": ["CK-FROUT03-01"],
        "precondition": "在庫数量10の在庫単位があり、数量2の注文が確定している",
        "input": "在庫補充・入荷登録を意図した4通りの要求と、支払・出荷登録・配達完了登録",
        "steps": (
            "1. 在庫補充・入荷登録を意図した要求を管理者の認証付きで送信する\n"
            "2. 各要求の後に在庫数量を確認する\n"
            "3. 支払→出荷登録→配達完了登録まで実行する\n"
            "4. 在庫数量を確認する"
        ),
        "expected_result": (
            "補充を意図した要求はいずれも成功せず在庫数量が8のまま変化しない。"
            "配達完了まで進めても在庫数量は8のままで補充されない（FR-OUT-03）"
        ),
    },
    {
        "case_id": "IT-AI-GF-032",
        "title": "返品・返金・部分出荷・分割配送の状態と操作が存在しない",
        "requirement_id": "FR-OUT-04",
        "related_adr": "ADDR-001",
        "test_category": "対象外機能（返品・返金・部分出荷）",
        "criterion": "state-transition",
        "coverage_keys": ["CK-FROUT04-01"],
        "precondition": "2明細を含む支払済の注文が1件ある",
        "input": "①明細指定を含む出荷登録 ②返品・返金・部分出荷を意図した要求 ③配達完了後のキャンセル",
        "steps": (
            "1. 注文状態の定義（CD-02）を確認する\n"
            "2. 明細ID・出荷数量を含む出荷登録を要求し、注文状態・明細・配送伝票番号を確認する\n"
            "3. 配達完了登録を行う\n"
            "4. 返品・返金・部分出荷を意図した要求を送信する\n"
            "5. 配達完了後にキャンセルを要求し、決済記録を確認する"
        ),
        "expected_result": (
            "注文状態は注文受付・支払済・出荷済・配達完了・キャンセル済の5つのみ。出荷は注文単位で一括され"
            "2明細とも出荷済となる。返品・返金・部分出荷の経路は成功せず、配達完了後のキャンセルは"
            "INVALID_STATUS_TRANSITION（409）で、決済記録は承認1件のままである（FR-OUT-04）"
        ),
    },
    {
        "case_id": "IT-AI-GF-033",
        "title": "クーポンの併用ができない",
        "requirement_id": "FR-OUT-05",
        "related_adr": "ADDR-007",
        "test_category": "対象外機能（複数クーポン併用）",
        "criterion": "api",
        "coverage_keys": ["CK-FROUT05-01"],
        "precondition": "カートに税抜3,000円の明細が1件あり、1,000円割引と500円割引のクーポンが登録済み",
        "input": "①SAVE1000 の適用 ②SAVE500 の適用 ③注文確定",
        "steps": (
            "1. SAVE1000 を適用する\n"
            "2. 続けて SAVE500 を適用する\n"
            "3. カート内容（適用中クーポン・割引額）を確認する\n"
            "4. 注文確定し、注文のクーポンコードと割引額を確認する"
        ),
        "expected_result": (
            "2枚目の適用は COUPON_ALREADY_APPLIED（409）となり、カート・注文の割引は SAVE1000 の1,000円"
            "だけが反映される（FR-OUT-05、NFR-LG-06）"
        ),
    },
    {
        "case_id": "IT-AI-GF-034",
        "title": "多通貨・多言語・海外配送に対応しない",
        "requirement_id": "FR-OUT-06",
        "related_adr": "ADDR-006",
        "test_category": "対象外機能（多通貨・多言語）",
        "criterion": "api",
        "coverage_keys": ["CK-FROUT06-01"],
        "precondition": "税抜1,000円の在庫単位を持つ公開商品が1件ある",
        "input": "①currency=USD・lang=en を付けた商品詳細照会 ②Accept-Language: en-US の画面要求 ③範囲外の都道府県コード",
        "steps": (
            "1. 通貨・言語の指定なしと指定ありで商品詳細を照会し、応答を比較する\n"
            "2. Accept-Language: en-US で商品一覧画面を表示する\n"
            "3. 都道府県コード99の配送先で注文確定を要求する"
        ),
        "expected_result": (
            "通貨・言語の指定は応答に影響せず、価格は税抜1,000円・税込1,100円のまま。画面は lang=\"ja\" の"
            "日本語で表示される。国内の都道府県コード以外は入力エラー（400）となり注文は作成されない（FR-OUT-06）"
        ),
    },
    {
        "case_id": "IT-AI-GF-035",
        "title": "配送業者連携・住所検証・配送日時指定・送料の地域別設定が無い",
        "requirement_id": "FR-OUT-07",
        "related_adr": "ADDR-001",
        "test_category": "対象外機能（配送）",
        "criterion": "api",
        "coverage_keys": ["CK-FROUT07-01"],
        "precondition": "同一内容のカートを持つ購入者が2名いる",
        "input": "①都道府県コード01の配送先 ②都道府県コード47の配送先 ③配送日時・配送業者の項目と実在しない郵便番号",
        "steps": (
            "1. 配送先の保持項目（D-12）を確認する\n"
            "2. 購入者1が都道府県01、購入者2が都道府県47で、配送日時・配送業者の項目を含めて注文確定する\n"
            "3. 送料・合計を比較する\n"
            "4. 保存された配送先を確認する"
        ),
        "expected_result": (
            "送料は地域によらず500円で合計も一致する。配送先は D-12 の6項目のみで、配送日時・配送業者の指定は"
            "保存されない。実在しない郵便番号でも住所検証は行われず受理される（FR-OUT-07）"
        ),
    },
    {
        "case_id": "IT-AI-GF-036",
        "title": "利用者への通知を送信しない",
        "requirement_id": "FR-OUT-08",
        "related_adr": "ADDR-004",
        "test_category": "対象外機能（通知）",
        "criterion": "end-to-end-flow",
        "coverage_keys": ["CK-FROUT08-01"],
        "precondition": "公開商品の在庫単位が1件ある",
        "input": "会員登録・注文確定・支払・出荷登録・注文キャンセルの一連の操作",
        "steps": (
            "1. 会員登録→ログインを行う\n"
            "2. 注文確定→支払→出荷登録を行う\n"
            "3. 別の注文を確定してキャンセルする\n"
            "4. 送信された通知の件数を確認する"
        ),
        "expected_result": "一連の操作で通知（メール等）が1件も送信されない（FR-OUT-08）",
    },
    {
        "case_id": "IT-AI-GF-037",
        "title": "会員情報変更・パスワード再設定・退会の手段が存在しない",
        "requirement_id": "FR-OUT-09, NFR-SC-17",
        "related_adr": "ADDR-008",
        "test_category": "対象外機能（会員情報の変更）",
        "criterion": "api",
        "coverage_keys": ["CK-FROUT09-01"],
        "precondition": "購入者が1名ログインしている",
        "input": "会員情報変更・パスワード変更・パスワード再設定・退会を意図した7通りの要求と3つの画面パス",
        "steps": (
            "1. 各要求を認証付きで送信する\n"
            "2. パスワード再設定・会員情報・退会の画面を要求する\n"
            "3. ログイン画面・会員登録画面の導線を確認する\n"
            "4. 利用者の登録内容を確認する"
        ),
        "expected_result": (
            "いずれも成功せず、画面は対象なし（404）となる。ログイン・会員登録画面にパスワード再設定・退会の"
            "導線が無く、メールアドレス・氏名・パスワードハッシュが変化しない（FR-OUT-09、NFR-SC-17）"
        ),
    },
    {
        "case_id": "IT-AI-GF-038",
        "title": "未ログインではカート・注文を利用できない",
        "requirement_id": "FR-OUT-10",
        "related_adr": "ADDR-002",
        "test_category": "対象外機能（ゲスト購入）",
        "criterion": "authentication",
        "coverage_keys": ["CK-FROUT10-01"],
        "precondition": "公開商品の在庫単位が1件ある（未ログイン状態）",
        "input": "①未認証のカート照会・明細追加・注文確定・注文履歴照会 ②未ログインのカート画面・注文手続き画面",
        "steps": (
            "1. 認証トークンなしで各APIを要求する\n"
            "2. 未ログインでカート画面・注文手続き画面・カート明細追加を要求する\n"
            "3. カート・注文の件数を確認する"
        ),
        "expected_result": (
            "APIはすべて AUTHENTICATION_REQUIRED（401）、画面はログイン画面へ遷移し、"
            "カート・注文が1件も作成されない（FR-OUT-10）"
        ),
    },
    {
        "case_id": "IT-AI-GF-039",
        "title": "認証失敗が続いてもアカウントロックされない",
        "requirement_id": "FR-OUT-11, NFR-SC-14",
        "related_adr": "ADDR-002",
        "test_category": "対象外機能（アカウントロック）",
        "criterion": "authentication",
        "coverage_keys": ["CK-FROUT11-01"],
        "precondition": "購入者が1名登録されている",
        "input": "①誤ったパスワードでのログイン10回 ②正しいパスワードでのログイン",
        "steps": (
            "1. 誤ったパスワードで10回ログインを要求する\n"
            "2. 正しいパスワードでログインを要求する\n"
            "3. 発行されたトークンで利用者情報を照会する\n"
            "4. 監査ログの件数を確認し、画面からもログインする"
        ),
        "expected_result": (
            "10回の失敗後も正しい資格情報でログインでき（200）、トークンで照会できる。"
            "監査ログにはログイン失敗10件・成功1件が記録され、ロック状態は作られない（FR-OUT-11、NFR-SC-14）"
        ),
    },
    {
        "case_id": "IT-AI-GF-040",
        "title": "未払い注文が自動キャンセルされない",
        "requirement_id": "FR-OUT-12",
        "related_adr": "ADDR-001",
        "test_category": "対象外機能（未払い注文の自動キャンセル）",
        "criterion": "state-transition",
        "coverage_keys": ["CK-FROUT12-01"],
        "precondition": "注文受付の注文が1件あり、注文日時を30日前に遡らせている",
        "input": "①注文詳細照会 ②支払（approve）",
        "steps": (
            "1. 注文確定後、注文日時を30日前に更新する\n"
            "2. 注文詳細を照会し、状態と支払可否を確認する\n"
            "3. キャンセル済の注文が無いことを確認する\n"
            "4. 支払を要求し、状態を確認する"
        ),
        "expected_result": (
            "注文状態は注文受付のまま支払可否が可で、キャンセル済の注文は0件。"
            "支払は200で成功し支払済へ遷移する（FR-OUT-12）"
        ),
    },
    {
        "case_id": "IT-AI-GF-041",
        "title": "商品画像・レビュー・お気に入り・おすすめとファイル投稿が存在しない",
        "requirement_id": "FR-OUT-13, NFR-SC-28",
        "related_adr": "ADDR-006",
        "test_category": "対象外機能（商品画像・レビュー）",
        "criterion": "api",
        "coverage_keys": ["CK-FROUT13-01"],
        "precondition": "公開商品が1件ある",
        "input": "①商品詳細照会 ②レビュー・画像・お気に入り・おすすめを意図した5通りの要求 ③商品詳細画面",
        "steps": (
            "1. 商品詳細を照会し、応答項目を確認する\n"
            "2. レビュー・画像・お気に入り・おすすめの経路を要求する\n"
            "3. 商品詳細画面の表示内容を確認する\n"
            "4. ファイルを保持する項目の有無を確認する"
        ),
        "expected_result": (
            "商品詳細の応答は FR-012 の6項目のみで、画像・レビュー・評価・お気に入り・おすすめの項目を含まない。"
            "各経路は成功せず、画面に商品画像・レビュー・お気に入り・おすすめの表示が無い。"
            "ファイルを保存する項目を持たない（FR-OUT-13、NFR-SC-28）"
        ),
    },
    {
        "case_id": "IT-AI-GF-042",
        "title": "スマートフォン専用画面が存在しない",
        "requirement_id": "FR-OUT-14",
        "related_adr": "ADDR-004",
        "test_category": "対象外機能（スマートフォン専用画面）",
        "criterion": "api",
        "coverage_keys": ["CK-FROUT14-01"],
        "precondition": "公開商品が1件ある",
        "input": "①PC の User-Agent ②スマートフォンの User-Agent ③スマートフォン向けパス（/m・/sp・/mobile）",
        "steps": (
            "1. PC の User-Agent で商品一覧画面を要求する\n"
            "2. スマートフォンの User-Agent で同じ画面を要求する\n"
            "3. 応答本文と使用テンプレートを比較する\n"
            "4. スマートフォン向けパスを要求する"
        ),
        "expected_result": (
            "どちらの User-Agent でも同一のテンプレート・同一の応答本文を返し、"
            "スマートフォン向けパスは対象なし（404）となる（FR-OUT-14）"
        ),
    },
    {
        "case_id": "IT-AI-GF-043",
        "title": "一覧の帳票（CSV・PDF）出力が存在しない",
        "requirement_id": "FR-OUT-15",
        "related_adr": "ADDR-006",
        "test_category": "対象外機能（帳票出力）",
        "criterion": "api",
        "coverage_keys": ["CK-FROUT15-01"],
        "precondition": "購入者の注文が1件あり、管理者がログインしている",
        "input": "①format=csv／export=csv／format=pdf／download=1 を付けた一覧API ②出力用の経路 ③管理者画面",
        "steps": (
            "1. 商品一覧・注文履歴・注文一覧（管理）・在庫単位一覧へ出力指定のクエリを付けて要求する\n"
            "2. 応答の Content-Type・Content-Disposition を確認する\n"
            "3. 出力専用の経路を要求する\n"
            "4. 管理者画面のリンク・文言を確認する"
        ),
        "expected_result": (
            "応答は JSON または HTML のみで、CSV・PDF の Content-Type と添付ファイルの指定が返らない。"
            "出力専用の経路は成功せず、画面にファイル出力の導線が無い（FR-OUT-15）"
        ),
    },
    {
        "case_id": "IT-AI-GF-044",
        "title": "特定商取引法に基づく表記等の静的ページを持たない",
        "requirement_id": "FR-OUT-16, NFR-LG-04",
        "related_adr": "ADDR-004",
        "test_category": "対象外機能（静的ページ）",
        "criterion": "api",
        "coverage_keys": ["CK-FROUT16-01"],
        "precondition": "公開商品が1件ある",
        "input": "①/legal・/tokushoho・/terms・/privacy・/company・/about・/law ②商品一覧・ログイン・会員登録画面",
        "steps": (
            "1. 静的ページを想定したパスを要求する\n"
            "2. 各応答のステータスと本文を確認する\n"
            "3. 主要画面に「特定商取引」の表記・リンクが無いことを確認する"
        ),
        "expected_result": (
            "いずれのパスも対象なし（404）で、本文・主要画面に「特定商取引」の表記とリンクが現れない"
            "（FR-OUT-16、NFR-LG-04）"
        ),
    },
    {
        "case_id": "IT-AI-GF-045",
        "title": "認証が1段階で完了する（多要素認証を設けない）",
        "requirement_id": "NFR-SC-13",
        "related_adr": "ADDR-002",
        "test_category": "セキュリティ（認証方式）",
        "criterion": "authentication",
        "coverage_keys": ["CK-NFRSC13-01"],
        "precondition": "購入者が1名登録されている",
        "input": "メールアドレスとパスワードによるログイン（API・画面）",
        "steps": (
            "1. API でログインし、応答項目を確認する\n"
            "2. 発行されたトークンで利用者情報を照会する\n"
            "3. 画面からログインし、カート画面を表示する"
        ),
        "expected_result": (
            "ログイン応答は token・expires_at・user の3項目のみで、追加の確認手順を経ずに照会できる。"
            "画面も1回のログインで利用可能となる（NFR-SC-13 は該当なし）"
        ),
    },
    {
        "case_id": "IT-AI-GF-046",
        "title": "送信元単位のリクエスト数制限を行わない",
        "requirement_id": "NFR-SC-27",
        "related_adr": "ADDR-007",
        "test_category": "セキュリティ（大量アクセス対策）",
        "criterion": "api",
        "coverage_keys": ["CK-NFRSC27-01"],
        "precondition": "購入者がログインしており、公開商品が1件ある",
        "input": "①公開APIへの60回の要求 ②認証付きAPIへの30回の要求 ③認証失敗20回",
        "steps": (
            "1. 商品一覧APIを60回連続で要求する\n"
            "2. カート照会APIを30回連続で要求する\n"
            "3. 誤ったパスワードで20回ログインを要求する\n"
            "4. 応答のHTTPステータスを集計する"
        ),
        "expected_result": (
            "公開API・認証付きAPIはすべて200、認証失敗はすべて401で、"
            "要求数の制限による拒否（429等）が発生しない（NFR-SC-27 は該当なし）"
        ),
    },
    {
        "case_id": "IT-AI-GF-047",
        "title": "認証トークンが推測困難で24時間で失効しログアウトで無効化される",
        "requirement_id": "NFR-SC-08",
        "related_adr": "ADDR-002",
        "test_category": "セキュリティ（認証トークンの保護）",
        "criterion": "authentication",
        "coverage_keys": ["CK-NFRSC08-01"],
        "precondition": "購入者が1名登録されている",
        "input": "①2回のログイン ②有効期限日時の1秒前・有効期限日時ちょうどの照会 ③ログアウト後の照会",
        "steps": (
            "1. 2回ログインし、トークンの値・長さ・文字種・保存形式を確認する\n"
            "2. 保存された有効期限が発行時刻＋24時間であることを確認する\n"
            "3. 現在時刻を有効期限日時の1秒前として利用者情報を照会する\n"
            "4. 現在時刻を有効期限日時ちょうどとして照会する\n"
            "5. ログアウト後に同じトークンで照会する"
        ),
        "expected_result": (
            "2つのトークンは異なり、43文字以上の URL-safe な乱数で、DB にはハッシュのみを保持する。"
            "有効期限は発行から24時間で、1秒前は200、有効期限日時ちょうどとログアウト後は"
            "AUTHENTICATION_REQUIRED（401）となり、無効化日時が記録される（NFR-SC-08）"
        ),
    },
    {
        "case_id": "IT-AI-GF-048",
        "title": "エラー応答・エラー画面に内部情報を含めない",
        "requirement_id": "NFR-SC-10",
        "related_adr": "ADDR-007",
        "test_category": "セキュリティ（内部情報の非表示）",
        "criterion": "error-handling",
        "coverage_keys": ["CK-NFRSC10-01"],
        "precondition": "デバッグ表示が無効（DEBUG=False）であり、公開商品が1件ある",
        "input": "①SQL文・ファイルパス・ライブラリ名を含むメッセージの未捕捉例外 ②存在しない商品ID ③不正なページ番号",
        "steps": (
            "1. 商品分類一覧の処理で未捕捉例外を発生させ、Web API を要求する\n"
            "2. 同じ状態で商品一覧画面を要求する\n"
            "3. 存在しない商品IDの照会と不正なページ番号の検索を要求する\n"
            "4. 各応答本文を確認する"
        ),
        "expected_result": (
            "APIは500で INTERNAL_ERROR と利用者向け文言のみを返し、details・context は空。"
            "画面も500のエラー画面を表示する。いずれの応答にもスタックトレース・SQL文・ファイルパス・"
            "ライブラリ名・例外クラス名が現れない。対象なし・入力エラーの応答も同様（NFR-SC-10）"
        ),
    },
    {
        "case_id": "IT-AI-GF-049",
        "title": "認証はメールアドレスとパスワードで行いトークン・セッションでのみ識別する",
        "requirement_id": "NFR-SC-12",
        "related_adr": "ADDR-002",
        "test_category": "セキュリティ（認証方式）",
        "criterion": "authentication",
        "coverage_keys": ["CK-NFRSC12-01"],
        "precondition": "購入者・管理者が1名ずつ登録されている",
        "input": "①正しい資格情報 ②クエリ・Cookie に置いたトークン ③誤ったパスワード ④未登録のメールアドレス",
        "steps": (
            "1. 購入者・管理者がログインし、トークンでロールを確認する\n"
            "2. トークンをクエリ・Cookie で渡して照会する\n"
            "3. 誤ったパスワード・未登録のメールアドレスでログインを要求する（API・画面）\n"
            "4. 画面から正しい資格情報でログインする"
        ),
        "expected_result": (
            "Authorization ヘッダーのトークンでのみ API を利用でき、クエリ・Cookie のトークンは401。"
            "認証失敗はメールアドレスとパスワードのどちらが誤りかを区別しない同一の応答・同一の画面文言となる。"
            "画面は正しい資格情報でログインセッションを開始する（NFR-SC-12）"
        ),
    },
    {
        "case_id": "IT-AI-GF-050",
        "title": "管理者ロールは初期データ一括投入でのみ付与される",
        "requirement_id": "NFR-SC-15",
        "related_adr": "ADDR-010",
        "test_category": "セキュリティ（特権の管理）",
        "criterion": "authentication",
        "coverage_keys": ["CK-NFRSC15-01"],
        "precondition": "利用者が未登録で、初期データ定義ファイルに管理者1名を含む",
        "input": "①role=admin を含む会員登録（API・画面） ②ロール変更を意図した3通りの要求 ③初期データ一括投入",
        "steps": (
            "1. role・is_admin を含めて会員登録する（API）\n"
            "2. 画面からも role を含めて会員登録する\n"
            "3. ロール変更を意図した要求を送信する\n"
            "4. 初期データ一括投入で管理者を登録する"
        ),
        "expected_result": (
            "会員登録で作成される利用者は全件が購入者で、ロール変更の経路は成功しない。"
            "初期データ一括投入で登録した利用者だけが管理者となる（NFR-SC-15）"
        ),
    },
    {
        "case_id": "IT-AI-GF-051",
        "title": "ログインでセッション識別子を再発行しログアウトで破棄する",
        "requirement_id": "NFR-SC-19",
        "related_adr": "ADDR-002",
        "test_category": "セキュリティ（セッション識別子の保護）",
        "criterion": "authentication",
        "coverage_keys": ["CK-NFRSC19-01"],
        "precondition": "購入者が1名登録されている",
        "input": "①ログイン前のセッション識別子 ②ログイン後のセッション識別子 ③ログアウト後の再利用",
        "steps": (
            "1. 未ログインでカート画面を要求し、セッション識別子を取得する\n"
            "2. 画面からログインし、識別子を比較する\n"
            "3. ログイン前の識別子を設定した別クライアントでカート画面を要求する\n"
            "4. ログアウト後、ログイン時の識別子を設定した別クライアントでカート画面を要求する"
        ),
        "expected_result": (
            "ログイン前後で識別子が異なり（32文字以上）、ログイン前の識別子は DB から削除されている。"
            "ログイン前の識別子・ログアウト後の識別子を設定した要求はいずれも未ログインとして"
            "ログイン画面へ遷移する（NFR-SC-19）"
        ),
    },
    {
        "case_id": "IT-AI-GF-052",
        "title": "記録対象操作と注文状態の変更が記録される",
        "requirement_id": "NFR-SC-22",
        "related_adr": "ADDR-005",
        "test_category": "セキュリティ（監査ログ）",
        "criterion": "database",
        "coverage_keys": ["CK-NFRSC22-01"],
        "precondition": "監査ログが0件の状態",
        "input": "初期データ一括投入・ログイン成功2回・ログイン失敗1回・ログアウト1回・注文確定→支払→出荷→配達完了",
        "steps": (
            "1. 初期データ一括投入を実行する\n"
            "2. 購入者・管理者でログインし、誤ったパスワードでログインを要求し、ログアウトする\n"
            "3. 監査ログの種別別件数と記録項目を確認する\n"
            "4. 注文確定→支払→出荷登録→配達完了登録を行い、注文状態履歴を確認する"
        ),
        "expected_result": (
            "監査ログは初期データ投入1件・ログイン成功2件・ログイン失敗1件・ログアウト1件で、"
            "発生日時・結果が記録されメールアドレス・パスワードを含まない。注文状態履歴は4件で、"
            "遷移と実行者のロール（購入者・購入者・管理者・管理者）が記録される（NFR-SC-22）"
        ),
    },
    {
        "case_id": "IT-AI-GF-053",
        "title": "監査ログ・注文状態履歴が追記のみで更新・削除できない",
        "requirement_id": "NFR-SC-23",
        "related_adr": "ADDR-005",
        "test_category": "セキュリティ（改ざん防止）",
        "criterion": "database",
        "coverage_keys": ["CK-NFRSC23-01"],
        "precondition": "支払済の注文が1件あり、監査ログ・注文状態履歴が記録されている",
        "input": "監査ログ・注文状態履歴・注文の更新/削除を意図した7通りの要求と2つの画面パス",
        "steps": (
            "1. 監査ログ・注文状態履歴・注文への参照／更新／削除要求を管理者の認証付きで送信する\n"
            "2. 管理者画面から監査ログ・状態履歴の画面を要求する\n"
            "3. 既存の監査ログ・注文状態履歴の行を比較する\n"
            "4. 出荷登録を行い、記録の増え方を確認する"
        ),
        "expected_result": (
            "いずれの要求も成功せず、画面は対象なし（404）。既存の監査ログ・注文状態履歴の行は変化せず、"
            "出荷登録により注文状態履歴が1件追記されるだけである（NFR-SC-23）"
        ),
    },
    {
        "case_id": "IT-AI-GF-054",
        "title": "個人情報を本人と管理者だけに返し決済要求・ログへ出力しない",
        "requirement_id": "NFR-SC-24, NFR-LG-01",
        "related_adr": "ADDR-009",
        "test_category": "セキュリティ（個人情報の取扱い）",
        "criterion": "api",
        "coverage_keys": ["CK-NFRSC24-01"],
        "precondition": "購入者2名・管理者1名が登録され、購入者Aの支払済の注文が1件ある",
        "input": "①来訪者としての商品照会 ②他の購入者としての注文詳細照会 ③本人・管理者としての注文詳細照会 ④支払時の決済要求とログ",
        "steps": (
            "1. 購入者Aが個人情報（氏名・受取人氏名・郵便番号・電話番号・住所）を含む注文を確定し支払う\n"
            "2. 来訪者として商品一覧・商品詳細を照会する\n"
            "3. 他の購入者として注文詳細を照会する\n"
            "4. 本人・管理者として注文詳細を照会する\n"
            "5. 決済要求の項目と出力されたログを確認する"
        ),
        "expected_result": (
            "来訪者の応答に個人情報・仕入先が含まれない。他の購入者の照会は対象なし（404）。"
            "本人の注文詳細には配送先が含まれ決済記録・購入者情報を含まない。管理者の注文詳細には"
            "購入者情報と決済記録が含まれる。決済要求とログには個人情報が1件も現れない（NFR-SC-24、NFR-LG-01）"
        ),
    },
    {
        "case_id": "IT-AI-GF-055",
        "title": "クレジットカード情報を受け付けず保存も送信もしない",
        "requirement_id": "NFR-LG-05",
        "related_adr": "ADDR-009",
        "test_category": "法令順守（割賦販売法）",
        "criterion": "api",
        "coverage_keys": ["CK-NFRLG05-01"],
        "precondition": "注文受付の注文が1件ある",
        "input": "カード番号・有効期限・セキュリティコードを含む支払要求",
        "steps": (
            "1. カード情報を含む支払要求を送信する\n"
            "2. 決済要求の項目を確認する\n"
            "3. モデルの項目名にカード情報が無いことを確認する\n"
            "4. 保存された注文・決済記録にカード番号が含まれないことを確認する\n"
            "5. 支払画面の入力項目を確認する"
        ),
        "expected_result": (
            "支払は200で成功するが、決済要求は4項目のみでカード番号を含まない。カード情報を保持する項目が"
            "存在せず、保存データにもカード番号が現れない。支払画面にカード情報の入力欄が無い（NFR-LG-05）"
        ),
    },
    {
        "case_id": "IT-AI-GF-056",
        "title": "実行基盤が目標値の言語・フレームワーク・DB製品の版である",
        "requirement_id": "NFR-EN-01, NFR-EN-02",
        "related_adr": "ADDR-011",
        "test_category": "システム環境（実行基盤の版）",
        "criterion": "database",
        "coverage_keys": ["CK-NFREN01-01"],
        "precondition": "結合試験が ENV-01（Docker Compose の app・db）で実行されている",
        "input": "app の実行環境と db への接続",
        "steps": (
            "1. Python・Django・Django REST Framework の版を確認する\n"
            "2. 接続先 DB の種別と版を確認する"
        ),
        "expected_result": (
            "Python 3.12・Django 5.2・Django REST Framework 3.15 以上で動作し、"
            "接続先は PostgreSQL 16 である（NFR-EN-01、NFR-EN-02）"
        ),
    },
    {
        "case_id": "IT-AI-GF-057",
        "title": "タイムゾーンが Asia/Tokyo で文字コードが UTF-8 である",
        "requirement_id": "NFR-EN-04",
        "related_adr": "ADDR-004",
        "test_category": "システム環境（タイムゾーン・文字コード）",
        "criterion": "database",
        "coverage_keys": ["CK-NFREN04-01"],
        "precondition": "支払済の注文が1件ある",
        "input": "①app・db の設定 ②注文詳細・ログイン応答の日時 ③画面の文字コード",
        "steps": (
            "1. app のタイムゾーン設定と db の既定タイムゾーン・文字コードを確認する\n"
            "2. 注文詳細の注文日時・支払日時・状態履歴の変更日時を確認する\n"
            "3. ログイン応答の有効期限を確認する\n"
            "4. 画面の Content-Type と日本語表示を確認する"
        ),
        "expected_result": (
            "app のタイムゾーンは Asia/Tokyo（USE_TZ 有効）、db の既定タイムゾーンは Asia/Tokyo、"
            "文字コードは UTF8。API の日時はすべて +09:00 付きで返り、画面は UTF-8 の日本語で表示される"
            "（NFR-EN-04）"
        ),
    },
    {
        "case_id": "IT-AI-GF-058",
        "title": "外部ネットワークへ接続せずに全機能を操作できる",
        "requirement_id": "NFR-EN-05, NFR-LG-10",
        "related_adr": "ADDR-009",
        "test_category": "システム環境（外部サービスの利用制約）",
        "criterion": "end-to-end-flow",
        "coverage_keys": ["CK-NFREN05-01"],
        "precondition": "管理者がログインしており、公開商品の在庫単位が1件ある",
        "input": "外部ネットワークを遮断した状態での会員登録→ログイン→検索→注文確定→支払→出荷→配達完了",
        "steps": (
            "1. 外部ネットワークへの接続を遮断する\n"
            "2. 会員登録・ログイン・商品検索・注文確定・支払・出荷登録・配達完了登録を実行する\n"
            "3. 商品一覧・商品詳細・ログイン・会員登録の各画面の参照先 URL を確認する"
        ),
        "expected_result": (
            "すべての操作が外部への接続なしで成功し、画面が外部 URL（外部 CDN を含む）を参照しない"
            "（NFR-EN-05、NFR-LG-10）"
        ),
    },
    {
        "case_id": "IT-AI-GF-059",
        "title": "アプリケーションログが JSON Lines で必須項目とともに出力される",
        "requirement_id": "NFR-OM-11",
        "related_adr": "ADDR-005",
        "test_category": "運用・保守性（ログの出力）",
        "criterion": "error-handling",
        "coverage_keys": ["CK-NFROM11-01"],
        "precondition": "注文受付の注文が1件ある",
        "input": "①keyword 付きの商品一覧照会 ②未認証のカート照会 ③支払 ④未捕捉例外",
        "steps": (
            "1. 検索・未認証要求・支払を実行し、出力されたログを収集する\n"
            "2. アクセスログ・業務エラー・外部連携ログの項目を確認する\n"
            "3. 未捕捉例外を発生させ、エラーログの項目を確認する\n"
            "4. 監査ログ・注文状態履歴が DB に記録されていることを確認する"
        ),
        "expected_result": (
            "各ログは1行1件の JSON で、アクセスログは timestamp（+09:00）・level・request_id・method・path・"
            "status・duration_ms を持ち path にクエリ文字列を含まない。業務エラーはエラーコード、外部連携ログは"
            "注文番号・結果・所要時間を持つ。エラーログは level=ERROR で例外の種類と発生箇所のみを出力し"
            "例外メッセージを含まない。監査ログ・注文状態履歴は DB に記録される（NFR-OM-11）"
        ),
    },
    {
        "case_id": "IT-AI-GF-060",
        "title": "X-Request-ID を引き継ぎ全ログ行と応答ヘッダーで相関できる",
        "requirement_id": "NFR-OM-18",
        "related_adr": "ADDR-005",
        "test_category": "運用・保守性（障害調査の容易さ）",
        "criterion": "api",
        "coverage_keys": ["CK-NFROM18-01"],
        "precondition": "注文受付の注文が1件ある",
        "input": "①X-Request-ID を指定した支払要求 ②指定しない要求 ③形式が不正な値を指定した要求",
        "steps": (
            "1. X-Request-ID を指定して支払を要求し、応答ヘッダーとログを確認する\n"
            "2. 指定せずに商品一覧を要求し、応答ヘッダーとログを確認する\n"
            "3. 形式が不正な値を指定して要求し、応答ヘッダーを確認する"
        ),
        "expected_result": (
            "指定した値はそのまま応答ヘッダー X-Request-ID に付与され、その要求の全ログ行が同じ request_id を持つ。"
            "未指定時は32桁の16進数が生成されて応答ヘッダーとログで一致する。形式が不正な値は引き継がず"
            "新しい値を生成する（NFR-OM-18）"
        ),
    },
    {
        "case_id": "IT-AI-GF-061",
        "title": "一覧APIの応答件数が上限以下で分類一覧は全件を返す",
        "requirement_id": "NFR-PF-08",
        "related_adr": "ADDR-006",
        "test_category": "性能・拡張性（一覧の応答件数上限）",
        "criterion": "api",
        "coverage_keys": ["CK-NFRPF08-01"],
        "precondition": "商品25件・商品分類45件・注文21件・在庫単位76件を登録した状態",
        "input": "各一覧APIの先頭ページと最終ページ",
        "steps": (
            "1. 商品一覧の1ページ目・2ページ目を取得する\n"
            "2. 商品分類一覧を取得する\n"
            "3. 注文履歴一覧・注文一覧（管理）の1ページ目・2ページ目を取得する\n"
            "4. 在庫単位一覧の1ページ目・2ページ目を取得する"
        ),
        "expected_result": (
            "商品一覧・注文履歴一覧・注文一覧（管理）は1ページ20件で2ページ目に残件を返し、"
            "在庫単位一覧は1ページ50件で2ページ目に26件を返す。商品分類一覧はページングを持たず45件を"
            "配列で返す（NFR-PF-08）"
        ),
    },
    {
        "case_id": "IT-AI-GF-062",
        "title": "利用者の状態を DB に保持しプロセス内に持たない",
        "requirement_id": "NFR-PF-16",
        "related_adr": "ADDR-002",
        "test_category": "性能・拡張性（業務量増加への対応）",
        "criterion": "database",
        "coverage_keys": ["CK-NFRPF16-01"],
        "precondition": "購入者がログインし、カートに明細が1件ある",
        "input": "①別クライアントからの照会 ②認証トークンの行削除 ③セッション行の削除",
        "steps": (
            "1. 認証トークン・カートが DB の行として存在することを確認する\n"
            "2. 別のクライアントから同じトークンで利用者情報・カートを照会する\n"
            "3. 認証トークンの行を削除し、再度照会する\n"
            "4. 画面からログインし、セッション行を削除してカート画面を要求する"
        ),
        "expected_result": (
            "別クライアントからも同じ状態を参照できる。認証トークンの行を削除すると401、"
            "セッション行を削除するとログイン画面へ遷移し、カート明細は DB に残る（NFR-PF-16）"
        ),
    },
    {
        "case_id": "IT-AI-GF-063",
        "title": "JIS 第3・第4水準の漢字を保存・表示できる",
        "requirement_id": "NFR-US-03",
        "related_adr": "ADDR-006",
        "test_category": "ユーザビリティ（使用可能文字）",
        "criterion": "database",
        "coverage_keys": ["CK-NFRUS03-01"],
        "precondition": "公開商品の在庫単位が1件ある",
        "input": "JIS 第3水準（﨑）・第4水準（𠮟）の漢字を含む氏名・受取人氏名・住所",
        "steps": (
            "1. 当該の漢字を含む氏名で会員登録する\n"
            "2. 応答・DB の値を確認する\n"
            "3. 当該の漢字を含む受取人氏名・住所で注文確定する\n"
            "4. 注文詳細（API）と注文詳細画面の表示を確認する"
        ),
        "expected_result": (
            "入力した文字がそのまま保存され、API 応答・画面表示でも同じ文字が表示される（NFR-US-03）"
        ),
    },
    {
        "case_id": "IT-AI-GF-064",
        "title": "入力エラーを項目の近傍へ全件表示し入力値を保持する",
        "requirement_id": "NFR-US-04",
        "related_adr": "ADDR-007",
        "test_category": "ユーザビリティ（入力エラーの表示）",
        "criterion": "error-handling",
        "coverage_keys": ["CK-NFRUS04-01"],
        "precondition": "会員登録画面を表示できる状態",
        "input": "形式誤りのメールアドレス・短いパスワード・不一致の確認用パスワード・51文字以上の氏名",
        "steps": (
            "1. 4項目を同時に誤って会員登録画面から送信する\n"
            "2. 表示された理由の件数と位置を確認する\n"
            "3. 入力値の保持状況を確認する\n"
            "4. 利用者が作成されていないことを確認する"
        ),
        "expected_result": (
            "400で再表示され、4項目分の理由がそれぞれ該当する入力項目の直後（次の項目より前）に表示される。"
            "メールアドレス・氏名の入力値は保持され、パスワードは保持されない。利用者は作成されない（NFR-US-04）"
        ),
    },
    {
        "case_id": "IT-AI-GF-065",
        "title": "価格を税込主表示・税抜併記で表示し内訳に消費税額と合計を表示する",
        "requirement_id": "NFR-LG-02",
        "related_adr": "ADDR-004",
        "test_category": "法令順守（総額表示義務）",
        "criterion": "api",
        "coverage_keys": ["CK-NFRLG02-01"],
        "precondition": "税抜1,000円の在庫単位を2個カートに入れた購入者がログインしている",
        "input": "商品一覧画面・商品詳細画面・カート画面",
        "steps": (
            "1. カート照会APIで金額内訳を取得する\n"
            "2. 商品一覧画面・商品詳細画面の価格表示を確認する\n"
            "3. カート画面の金額内訳を確認する"
        ),
        "expected_result": (
            "一覧・詳細の価格は「1,100円（税込）／1,000円（税抜）」と表示される。カート画面に消費税額と"
            "合計（税込）が表示され、APIの金額内訳と一致する。消費税額は（割引後小計＋送料）×10÷100 の"
            "切り捨てである（NFR-LG-02、CMN-32）"
        ),
    },
    {
        "case_id": "IT-AI-GF-066",
        "title": "都道府県は JIS X 0401 のコードだけを受け付ける",
        "requirement_id": "NFR-LG-09",
        "related_adr": "ADDR-007",
        "test_category": "法令順守（JIS X 0401）",
        "criterion": "error-handling",
        "coverage_keys": ["CK-NFRLG09-01"],
        "precondition": "カートに明細が1件ある購入者が2名いる",
        "input": "①00・48・1・047・ab・未入力 ②47 ③01",
        "steps": (
            "1. 範囲外・桁違い・英字・未入力の都道府県コードで注文確定を要求する\n"
            "2. 注文が作成されていないことを確認する\n"
            "3. 47 で注文確定する\n"
            "4. 別の購入者が 01 で注文確定する"
        ),
        "expected_result": (
            "01〜47 以外はすべて入力エラー（400、項目 prefecture_code）となり注文が作成されない。"
            "47・01 は受理され、指定したコードがそのまま保存される（NFR-LG-09）"
        ),
    },
    {
        "case_id": "IT-AI-GF-067",
        "title": "稼働開始時の初期データに注文関連データを含まない",
        "requirement_id": "NFR-MG-01",
        "related_adr": "ADDR-010",
        "test_category": "移行性（移行対象データ）",
        "criterion": "database",
        "coverage_keys": ["CK-NFRMG01-01"],
        "precondition": "DB が空の状態",
        "input": "稼働開始時に用いる初期データ定義ファイル（app/seed/initial_data.json）",
        "steps": (
            "1. 定義ファイルのトップレベルの項目を確認する\n"
            "2. 定義ファイルで初期データ一括投入を実行する\n"
            "3. 利用者・商品・在庫単位の件数を確認する\n"
            "4. 注文・配送先・決済記録・注文状態履歴・カートの件数を確認する"
        ),
        "expected_result": (
            "定義ファイルは利用者・マスタのみを持ち、注文・カート・決済記録・注文状態履歴の項目を含まない。"
            "投入は成功し、注文関連データ・カートは0件である（NFR-MG-01）"
        ),
    },
    {
        "case_id": "IT-AI-GF-068",
        "title": "投入失敗時は何も投入せず修正後の再実行で重複なくやり直せる",
        "requirement_id": "NFR-OM-13, NFR-MG-07",
        "related_adr": "ADDR-010",
        "test_category": "運用・保守性（異常終了時の再実行）",
        "criterion": "database",
        "coverage_keys": ["CK-NFROM13-01"],
        "precondition": "DB が空の状態",
        "input": "①価格が負の在庫単位を含む定義ファイル ②修正した定義ファイル（全削除指定）",
        "steps": (
            "1. 違反を含む定義ファイルで投入を実行する\n"
            "2. 終了コード・違反内容・各データの件数・監査ログを確認する\n"
            "3. 修正した定義ファイルを全削除指定で実行する\n"
            "4. 同じ定義ファイルで全削除指定の実行をもう一度行い、件数と監査ログを確認する"
        ),
        "expected_result": (
            "違反時は終了コードが0以外で違反項目（price）が出力され、全データが0件のまま、"
            "監査ログに失敗が1件記録される。修正後の実行では定義ファイルどおりに投入され、"
            "再実行してもデータが重複せず、監査ログは削除されず3件に増える（NFR-OM-13、NFR-MG-07）"
        ),
    },
    {
        "case_id": "IT-AI-GF-069",
        "title": "在庫5への10並列の注文確定で在庫整合が保たれる",
        "requirement_id": "NFR-PF-07, NFR-LG-06",
        "related_adr": "ADDR-001",
        "test_category": "性能・拡張性（整合性を伴う同時実行）",
        "criterion": "database",
        "coverage_keys": ["CK-NFRPF07-01"],
        "precondition": "在庫数量5の在庫単位1件と、各1個のカート明細を持つ購入者10名（VDC-05 の条件）",
        "input": "10名の購入者による同時の注文確定（10試行）",
        "steps": (
            "1. 在庫数量5の在庫単位と購入者10名・カート明細を用意する\n"
            "2. 10件の注文確定を同時に送信する\n"
            "3. 応答のHTTPステータスとエラーコードを集計する\n"
            "4. 在庫数量・注文件数・注文明細の数量合計を確認する\n"
            "5. 1〜4を10試行繰り返す"
        ),
        "expected_result": (
            "10試行のすべてで成功5件・在庫不足（INSUFFICIENT_STOCK）5件となり、在庫数量は0（0未満にならない）、"
            "引き当てた数量の合計は初期の在庫数量5と一致し、注文は5件作成される（NFR-PF-07、NFR-LG-06）"
        ),
    },
]


def gap_ids(cases: list[dict]) -> dict[str, str]:
    """Required Coverage の MISSING 一覧から coverage_key ごとの Gap ID を導出する。"""
    required = json.loads((REPORT_DIR / "required-coverage.json").read_text(encoding="utf-8"))
    initial = json.loads((REPORT_DIR / "ai-initial-cases.json").read_text(encoding="utf-8"))["cases"]
    covered: set[str] = set()
    for case in initial:
        covered.update(case.get("coverage_keys") or [case["coverage_key"]])
    missing = sorted({item["coverage_key"] for item in required["required_coverage"]} - covered)
    return {key: f"GAP-{index:03d}" for index, key in enumerate(missing, start=1)}


def main() -> int:
    """GAP_FILL Case を追記し、gap_id を現在の Required Coverage に合わせる。"""
    document = json.loads(PATH.read_text(encoding="utf-8"))
    existing = {case["case_id"] for case in document["cases"]}
    added = [case for case in NEW_CASES if case["case_id"] not in existing]
    for case in added:
        case.update({"origin": "AI_GENERATED", "generation_stage": "GAP_FILL", "execution_type": AUTOMATABLE})
        document["cases"].append(
            {
                "case_id": case["case_id"],
                "origin": case["origin"],
                "generation_stage": case["generation_stage"],
                "gap_id": None,
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
                "execution_type": case["execution_type"],
            }
        )

    mapping = gap_ids(document["cases"])
    for case in document["cases"]:
        case["gap_id"] = mapping.get(case["coverage_keys"][0], case.get("gap_id"))

    document["note"] = (
        "Coverage Gap Analysis（case-comparison.json / coverage-gap-report.json）で MISSING と判定された "
        "Required Coverage を補うために追加した Test Case。IT-AI-GF-001〜011 は初回の Gap Fill、"
        "IT-AI-GF-012〜028 は repair cycle 1 で Required Coverage の導出元を是正（NFR-SC の検証方法・"
        "UC の同時実行観点を追加）した結果の Gap Fill、IT-AI-GF-029〜069 は Traceability Audit の C10"
        "（テストされていない要件）是正として、対象外機能（FR-OUT-01〜16）と結合試験で検証できる非機能要件を"
        "補う Gap Fill。AI INITIAL Case（ai-initial-cases.json、snapshot initial-1）は変更していない。"
        "gap_id は Required Coverage の MISSING 一覧から毎回導出する参照値であり、追加に伴い付け直している"
        "（各ケースの内容・期待結果は変更していない）。"
    )
    document["derived_from"] = sorted(
        set(document.get("derived_from", []))
        | {
            "docs/requirements/functional_requirements.md 2.3 対象外機能",
            "docs/requirements/non_functional_requirements.md 4〜12章",
        }
    )
    PATH.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"追加: {len(added)} 件 / 合計: {len(document['cases'])} 件")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
