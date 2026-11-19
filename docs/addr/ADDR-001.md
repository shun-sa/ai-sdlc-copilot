---
document_type: "ADDR（Architecture Decision & Design Record）"
system_name: "MiniCommerce"
addr_id: "ADDR-001"
title: "Web API 契約の方式（パス・電文形式・認証ヘッダー・エラー応答・ページング・HTTP ステータス）"
design_type: "外部インターフェース"
target_id: "application"
status: "ACTIVE"
generated_by: "ADDR Agent（RUN-AOBA-EC-1118）"
generated_at: "2026-11-19T07:40:00Z"
source_revision: "958677fe4a672dc82902289cfd4b0da5cfac39e5+worktree(RUN-AOBA-EC-1118 requirements 2026-11-19)"
generation_id: "RUN-AOBA-EC-1118"
primary_decision: "提供済み API 契約が未格納のため、Steering の事前指定を制約として Web API の電文・エラー・ページング・ステータス・パスの規約と、要求・応答の項目キー・検索条件・並び順・エラー理由の外部値（r2 追加）を確定する。あわせて GET（参照用要求）で業務データを変えない原則の唯一の例外として、FR-020 の利用中カートの作成の範囲・冪等性・一意性・CSRF 上の位置づけと、共通表示の合計点数での FR-020 の実行を担う Task（TASK-012）を確定する（r3 追加、r4 改訂）"
---

# ADDR：Web API 契約の方式（パス・電文形式・認証ヘッダー・エラー応答・ページング・HTTP ステータス）

## 1. 対象範囲

| 項目 | 内容 |
|---|---|
| 対象ID・名称 | application：MiniCommerce アプリケーションの Web API（manifest 候補 api-contract） |
| 対象機能・業務 | FR-001〜FR-004、FR-010〜FR-012、FR-020〜FR-026、FR-030〜FR-034、FR-040〜FR-045 の Web API（FR-060 は Web API を持たない：CMN-37） |
| 対象環境・リリース | 第1期（2027-04-01 稼働）。ENV-01・本番環境（ENV-02）共通 |
| 対象外 | 画面の URL・レイアウト（ui_report_requirements.md が正本）、ログイン状態の保持方式（ADDR-002）、コード値の割当て（ADDR-007）、決済サービス（模擬）との内部連携（ADDR-008）、同時実行制御（ADDR-004）。業務ルール・判定順序・例外条件そのもの（functional_requirements.md が正本） |

## 2. 関連要件・参照成果物

本ADDRの判断または設計差分に直接関係する成果物だけを記載する。
論理DB設計はArchitectureの正本をパス・版・Entity IDで参照し、Entity/属性/識別子/関連/制約の定義表やER図を本書へ複製しない。

| 区分 | 参照先 | 関係 |
|---|---|---|
| 要件 | FR-001、FR-002、FR-003、FR-004、FR-010、FR-011、FR-012、FR-020、FR-021、FR-022、FR-023、FR-024、FR-025、FR-026、FR-030、FR-031、FR-032、FR-033、FR-034、FR-040、FR-041、FR-042、FR-043、FR-044、FR-045、NFR-SC-03、NFR-SC-04、NFR-SC-05、NFR-SC-08、NFR-SC-10、NFR-SC-15、NFR-SC-21、NFR-SC-24、NFR-PF-08、NFR-US-04、NFR-EN-04、NFR-LG-06（docs/requirements/functional_requirements.md 1.4、non_functional_requirements.md 1.4） | 機能要件 1.2 は Web API の呼出し方式（パス・電文形式）を定義しない。CMN-14・CMN-34・CMN-35・CMN-18、ERR-01〜ERR-08、MSG-04・MSG-05 と非機能要件が電文規約を縛る。VUL-01・VUL-04〜VUL-06・VUL-13 は NFR-SC-21 の対策方針。項目キーは各 FR の 6.x.3 入力・処理内容の返却項目・6.x.5 出力（6.8.5、6.18.5、6.20.5、6.21.5、6.22.5）と、docs/requirements/data_requirements.md（1.1）3章の項目・4章 CD-06 に対応させる（r2 追加）。GET と FR-020 の利用中カートの作成の関係は FR-020 6.8.1・6.8.4 手順4・6.8.5・6.8.6・6.8.9、8.2.2 ST-CART-01、CMN-19・CMN-21・CMN-22、NFR-SC-05、VUL-06、data_requirements.md DQ-09・UPD-11 を根拠とする（r3 追加） |
| 受入条件 | docs/requirements/use-cases/UC-001.md〜UC-012.md 9章 AC（例：AC-UC-001-001、AC-UC-002-001、AC-UC-002-011、AC-UC-002-012、AC-UC-011-008）、AC-UC-004-020（r3 追加） | Web API で要求・応答内容を確認する AC の電文表現。AC-UC-004-020 は照会で利用中カートを1件だけ作成することを求める（r3 追加） |
| AIステアリング文書 | .github/project-context/project-ai-steering.md 1.3（5章 External Interface Standards・Naming、6.2 Authentication、8.1 OQ-PJ-001） | REST/JSON（UTF-8）、ベースパス /api・/api/admin、項目名 snake_case、URL パス小文字・ハイフン区切り、Web API は Bearer トークン。正本とされる docs/specifications/api-contract.md は未格納 |
| システム構成図 | N/A（受領なし） | 該当なし |
| データモデル | docs/architecture/db-logical-design.md（LDB-001、1.1）。参照のみ（属性値の表現は ADDR-006・ADDR-007） | 応答項目の値は Entity の属性に対応する |
| 関連ADDR | ADDR-002（Bearer の発行・検証。DD-008 の画面の更新操作と FR-020 の作成の関係：r3）、ADDR-004（再送・同時実行。4.3 の4 の利用中カートの条件付き一意と一意違反時の読み直し：r3）、ADDR-006（識別子の表現）、ADDR-007（コード値）、ADDR-008（支払の連携・mock_instruction）、ADDR-009（定義ファイルの項目キー。同じ項目は同じキー名）、ADDR-012（画面と API の共通業務処理）、ADDR-013（アクセスログ） | 依存／補足 |
| 設計資料 | PLAN-001 docs/architecture/implementation-task-list.md：TASK-002、TASK-006、TASK-007、TASK-010、TASK-012、TASK-014、TASK-015、TASK-016、TASK-018、TASK-020 | 各 Task の Web API 実装・試験が本契約に従う。ANALYSIS-001（reports/architecture/cross-artifact-consistency.md）ARCH-CI-004 の委譲先、ARCH-CI-009 のうち API 設計資料の要否を本 ADDR が判断する（r2 追加）。FR-020 の利用中カートの作成の例外（DD-015・DD-016）には、TASK-012（FR-020 の業務処理を持ち、カート照会の Web API・SCR-005 と、共通表示の合計点数の値の供給を担う）・TASK-014（SCR-006 の表示で TASK-012 の業務処理を呼ぶ）・TASK-002（共通レイアウトに合計点数の表示枠だけを持ち、カートを参照・作成しない）・TASK-020 が従う（r3 追加、r4 改訂：TASK-002 は TASK-012 より前の Wave で TASK-012 に依存できないため、FR-020 の実行を TASK-002 に割り当てない。TASK-012 の In Scope「FR-020〜FR-025 の処理・例外」は 6.8.1 の起動契機（共通表示の合計点数）を含み、TASK-012 は TASK-006 等を経て TASK-002 に依存済みのため、Task 本文・依存の変更は不要） |

## 3. 背景

### 3.1 判断が必要な理由

Steering は Web API の詳細（項目・認証ヘッダー・エラー応答・ページング・ステータス対応）の正本を docs/specifications/api-contract.md としているが、同資料は未格納（OQ-PJ-001、ARCH-CI-004）であり、機能要件も呼出し方式を定義しない（functional_requirements.md 1.2）。要件は「エラー種別を識別できる情報」「全項目分の入力エラー」「ページ番号・総件数・総ページ数」「ログイン応答にログイン状態を示す情報・有効期限日時・利用者情報」を求めるのみで、表現は一意に決まらない。要件は項目を日本語の項目名でだけ定め（物理名を持たない：TERM-RULE-001）、要求・応答の項目キー、検索条件の名前、並び順・業務エラーの種類の外部値も定まっていないため、Task ごとに別の名前で実装されないよう項目単位の対応規則を決める必要がある（r2 追加）。

r2 の DD-009（GET では業務データを変更しない）は例外を定めていなかったが、FR-020（カート照会）は要件上、利用中カートがない場合に明細0件・クーポンなしの利用中カートを1件作成し（6.8.4 手順4、6.8.5 データ更新、ST-CART-01）、正常終了後に利用中カートがちょうど1件あることを事後条件とする（6.8.6、AC-UC-004-020）。本 ADDR は FR-020 を GET /api/cart/ に割り当てており、画面でも SCR-005・SCR-006 の表示と購入者向け各画面の合計点数の表示（6.8.1 起動契機、UI-05）で実行するため、DD-009 と要件が矛盾していた（Implementation 後の Quality Review 指摘 QR-IMPL-001）。NFR-SC-21（VUL-06）の「更新操作は参照用の要求では実行できない」との関係を含めて判断する必要がある（r3 追加）。

### 3.2 判断時の制約

Steering 5章・6.2 の事前指定（REST/JSON・UTF-8、/api・/api/admin、snake_case、小文字・ハイフン区切りのパス、Bearer トークン）を変更しない。外部契約資料の内容を推測して捏造しない（本書の契約は本システム自身の設計判断であり、提供資料が格納された場合はそちらを正とする：ASM-001）。画面と API は同一の業務ルール・判定順序・通知内容（CMN-34）。内部情報を応答に含めない（NFR-SC-10、MSG-04）。

## 4. 設計判断

### 4.1 判断基準

| ID | 判断基準 | 優先度 | 根拠ID |
|---|---|---|---|
| DC-001 | Steering 5章・6.2 の事前指定（REST/JSON、/api・/api/admin、snake_case、Bearer）に適合すること | 必須 | Steering 5章・6.2 |
| DC-002 | エラー種別（ERR-01〜ERR-08）と業務エラーの種類・判定に用いた値を API 利用者が機械的に識別できること | 必須 | MSG-05、NFR-US-04、CMN-14 |
| DC-003 | 一覧の応答件数上限とページングの規則（CMN-35）を一意に表現できること | 必須 | NFR-PF-08、CMN-35 |
| DC-004 | 内部情報・他者の情報・データの存在有無を応答で漏らさないこと | 必須 | NFR-SC-10、NFR-SC-03、NFR-SC-24、MSG-04 |
| DC-005 | Django REST Framework の標準機能で実装でき、画面と同じ業務処理を呼べること | 重視 | NFR-EN-09、CMN-34 |
| DC-006 | 要求・応答・検索条件の各項目のキーと外部値が要件の項目から一意に導け、全 Task で同じ名前になること（r2 追加） | 必須 | CMN-34、NFR-US-04、FR-011 |
| DC-007 | FR-020 の振る舞い（利用中カートがない場合の作成・事後条件・同時実行時の1件）を変えずに、参照用の要求で利用者の更新操作を実行させないこと（VUL-06）と両立すること（r3 追加） | 必須 | FR-020、AC-UC-004-020、NFR-SC-05、NFR-SC-21（VUL-06）、DQ-09 |

### 4.2 検討した選択肢

| 選択肢ID | 選択肢 | 利点 | 欠点・リスク | 選定結果 | 根拠 |
|---|---|---|---|---|---|
| OPT-001 | 資源指向の REST（名詞の資源パス＋状態遷移操作は POST のサブパス）、HTTP ステータスをエラー種別に1対1で対応させ、本文は共通のエラー封筒（error.type・reason・fields・values）とする。項目キーは要件の項目名から固定の対応表で決める。GET では業務データを変えず、唯一の例外として FR-020 の利用中カートの作成を明示し、作成の条件・冪等性・一意性・取消しと VUL-06 の更新操作に当たらない理由を拘束にする（r3 追加） | エラー種別を HTTP ステータスと type の両方で識別でき、DRF の例外ハンドラ1か所で実装できる。Steering の事前指定と整合。項目名が Task 間で一致する。FR-020 の作成・事後条件・AC-UC-004-020 を満たしたまま照会を GET に保てる（r3） | 業務エラーの細分（在庫不足・状態不正等）は reason で区別する必要がある。FR-020 の画面の GET が他サイトから送られた場合も空の利用中カートが作られ得る（明細・クーポン・金額・注文は変わらない：r3） | SELECTED | DC-001、DC-002、DC-003、DC-005、DC-006、DC-007 |
| OPT-002 | 全応答を HTTP 200 とし、本文の結果コードで成否を表す（RPC 風） | ステータス対応の判断が不要 | REST の事前指定に反し、認証エラー等を HTTP レベルで識別できない。中継装置で誤扱いされる | NOT_SELECTED | DC-001、DC-002 |
| OPT-003 | RFC 9457（application/problem+json）の形式のみで返す | 標準形式 | 全項目分の入力エラーと業務エラーの判定値の配置を拡張項目で別途決める必要があり、Steering の snake_case 規約と項目名が混在する | NOT_SELECTED | DC-001、DC-002 |
| OPT-005 | （r3 追加。OPT-001 のうち FR-020 の扱いの代替）GET では作成せず、利用中カートがない場合は保存しない空のカート内容（明細0件・0円）を返し、作成は FR-021・FR-025 の時点に限る | GET で業務データを一切変えない | FR-020 6.8.4 手順4・6.8.5 データ更新・6.8.6 事後条件（利用中カートがちょうど1件）・ST-CART-01・UPD-11 と AC-UC-004-020 の Then「利用中カートは1件」を満たさず、要件の振る舞いを変える | NOT_SELECTED | DC-007 |
| OPT-006 | （r3 追加。OPT-001 のうち FR-020 の扱いの代替）FR-020 を POST（画面は CSRF トークン付きのフォーム送信）で受け付け、GET で照会させない | 参照用の要求で作成が起きない | 照会を状態変更操作として扱うことになり Steering 5章の REST 規約・DD-001 と合わず、SCR-005・SCR-006 への遷移や各画面の合計点数の表示（UI-05）を GET の画面表示で行えない。表示の度に送信操作が必要になり画面要件の遷移を変える | NOT_SELECTED | DC-001、DC-007 |

### 4.3 決定内容

OPT-001 を採用する。

1. 共通：電文は JSON（UTF-8、Content-Type: application/json）。項目名は snake_case。パスは小文字・ハイフン区切り、末尾スラッシュあり。版番号をパスに含めない（単一版）。購入者・来訪者向けは /api/、管理者向けは /api/admin/ に置く。
2. 値の表現：日時は日本時間の ISO 8601 秒単位・オフセット付き（例 2027-04-01T10:00:00+09:00）、日付は YYYY-MM-DD、金額・数量は整数（円・個）、識別子は JSON の整数（ADDR-006）、コード値は ADDR-007 の値とし、同じ項目名に _label を付けた日本語表示名を併記する（例 user_type と user_type_label、status と status_label）。値なしは null。
3. 認証：Authorization ヘッダーに Bearer 方式でログイン状態を示す情報を付ける（ADDR-002）。認証を要する API で未指定・無効・期限切れの場合は 401。認証を要しない API（FR-001、FR-002、FR-010〜FR-012）は、無効な値が付いていても来訪者として処理する。Cookie によるセッション認証は /api/ で受け付けない。
4. 機能と操作の対応（FR-026 は単独の API を持たず、カート・注文の応答に金額内訳として含める。パス中の「商品ID」等は識別子の値）：
   - FR-001 POST /api/auth/register/、FR-002 POST /api/auth/login/、FR-003 POST /api/auth/logout/、FR-004 GET /api/auth/me/
   - FR-010 GET /api/categories/、FR-011 GET /api/products/、FR-012 GET /api/products/商品ID/
   - FR-020 GET /api/cart/、FR-021 POST /api/cart/items/、FR-022 PATCH /api/cart/items/カート明細ID/、FR-023 DELETE /api/cart/items/カート明細ID/、FR-024 POST /api/cart/coupon/、FR-025 DELETE /api/cart/coupon/
   - FR-030 POST /api/orders/、FR-031 POST /api/orders/注文ID/payment/、FR-032 GET /api/orders/、FR-033 GET /api/orders/注文ID/、FR-034 POST /api/orders/注文ID/cancel/
   - FR-040 GET /api/admin/stock-units/、FR-041 GET /api/admin/orders/、FR-042 GET /api/admin/orders/注文ID/、FR-043 POST /api/admin/orders/注文ID/ship/、FR-044 POST /api/admin/orders/注文ID/deliver/、FR-045 POST /api/admin/orders/注文ID/cancel/
5. 成功時の HTTP ステータス：FR-001・FR-030 は 201、FR-003 は 204（本文なし）、それ以外は 200。応答本文の内容は各 FR の出力（例：FR-002 は token・expires_at・user、FR-030・FR-031 は注文詳細内容）とする。
6. エラー応答：次の封筒で返す。type は ERR 種別、reason は業務エラーの種類（snake_case の英字。ERR-02 の列挙に1対1）、fields は入力エラーの全項目（field と reason）、values は各例外表で定めた判定に用いた値、message は利用者向けの日本語文言。

```json
{"error": {"type": "business_error", "reason": "insufficient_stock", "message": "在庫が不足しています。", "fields": [], "values": {"stock_units": [{"stock_unit_id": 12, "sku": "MUG-001-BL", "requested_quantity": 3, "stock_quantity": 1}]}}}
```

7. エラー種別と HTTP ステータス：ERR-01 入力エラー＝400 input_error、ERR-02 業務エラー＝422 business_error、ERR-03 権限エラー＝403 permission_denied、ERR-04 認証エラー＝401 authentication_required、ERR-05 認証失敗＝401 authentication_failed、ERR-06 対象なし＝404 not_found、ERR-07 外部連携エラー＝502 integration_error、ERR-08 システムエラー＝500 system_error。存在しないパス・識別子として解釈できない値（CMN-18）も 404 not_found、許可しないメソッドは 405、JSON として解釈できない本文は 400 input_error とし、いずれも同じ封筒で返す。
8. ページング：一覧は query の page（1以上の整数、省略時1）で指定し、応答は items・page・page_size・total_count・total_pages を持つ。page_size は各 FR が定める件数で固定（利用者は指定できない。上限 50：NFR-PF-08）。page が整数でない・1未満は 400、総ページ数超過は 200 で items が空。検索条件はすべて query に置く。
9. 項目キーの命名規則（r2 追加）：
   - R-1：要件の入力項目・返却項目1つに1キーを対応させ、キーは 10 の対応表の英小文字 snake_case とする。同じ意味の項目は全 API・定義ファイル（ADDR-009）で同じキーにする。表にない項目を要求・応答に加えない（第1期内の追加は新 ADDR）。
   - R-2：識別子は 対象名＋_id（user_id、category_id、product_id、stock_unit_id、cart_item_id、order_id、parent_category_id）。
   - R-3：日時は _at、日付は _date、範囲の指定は _from／_to。金額は円の整数。
   - R-4：コード値は値のキーと _label のキーを併記する（ADDR-007。都道府県は CD-06 の2桁の文字列 01〜47 を prefecture とし、prefecture_label に名称）。公開状態は visibility（public／private、ADDR-009 と同じ）と visibility_label。
   - R-5：二値の項目は JSON の真偽値とし is_ または can_ を前置する。「なし」は null、0件の一覧は []、未適用のクーポン等の関連のまとまりは null。
   - R-6：関連のまとまりはオブジェクト（user、coupon、amounts、shipping_address、buyer）、繰返しは配列（items、categories、stock_units、status_history、payments）とする。入力エラーの fields[].field は要求のキーで、入れ子はドット区切り（例 shipping_address.postal_code）。
10. 項目キーの対応表（要件の項目名 → キー。r2 追加）：
   - 利用者（FR-001 の入力・登録結果、FR-002 の入力・応答の user、FR-004）：利用者ID user_id、メールアドレス email、パスワード password、パスワード（確認） password_confirmation、氏名 name、利用者区分 user_type、登録日時 registered_at。FR-002 の応答はログイン状態を示す情報 token、有効期限日時 expires_at、利用者情報 user（user_id・email・name・user_type）。
   - 商品分類（FR-010。全件を items で返しページング項目を持たない）：分類ID category_id、分類コード category_code、分類名 name、親分類ID parent_category_id、階層 depth、表示順 display_order。
   - 商品（FR-011 の items、FR-012）：商品ID product_id、商品コード product_code、商品名 name、商品説明 description、最低税抜価格 min_price_excluding_tax、最低税込価格 min_price_including_tax、在庫有無 is_in_stock、所属分類 categories（category_id・name）、在庫単位の一覧 stock_units（stock_unit_id・sku・variant_name（規格名）・price_excluding_tax（税抜価格）・price_including_tax（税込価格）・stock_quantity（在庫数量）・is_in_stock）。
   - カート内容（FR-020〜FR-025 の応答）：明細 items（cart_item_id、stock_unit_id、sku、product_id、product_name、variant_name、unit_price_excluding_tax（現在の税抜単価）、quantity、line_amount（明細金額）、stock_quantity（現在の在庫数量））、合計点数 total_quantity、クーポン coupon（coupon_code、name（クーポン名）、discount_type、discount_value、minimum_purchase_amount、valid_from、valid_to、is_applicable（適用可否）、not_applicable_reason（適用不可理由：empty_cart＝カート明細0件、not_yet_valid＝有効期間前、expired＝有効期間終了、below_minimum_purchase_amount＝最低購入金額未満。適用可は null））、金額 amounts（subtotal（小計）、discount_amount（割引額）、discounted_subtotal（割引後小計）、shipping_fee（送料）、tax_amount（消費税額）、total_amount（合計））。要求は在庫単位ID stock_unit_id、数量 quantity、クーポンコード coupon_code。
   - 注文詳細内容（FR-030・FR-031・FR-033・FR-034 の応答）：order_id、order_number、status（注文状態）、ordered_at、paid_at、shipped_at、delivered_at、cancelled_at、tracking_number（配送伝票番号）、items（stock_unit_id、sku、product_name、variant_name、unit_price_excluding_tax（税抜単価）、quantity、line_amount）、coupon（coupon_code、discount_type、discount_value）、amounts（カート内容と同じ6キー）、shipping_address（recipient_name（受取人氏名）、postal_code、prefecture、address_line1（住所1）、address_line2（住所2）、phone_number）、status_history（from_status（変更前の状態）、to_status（変更後の状態）、changed_at、actor_user_type（実行者の利用者区分））、can_pay（支払可否）、can_cancel（キャンセル可否）。注文詳細（管理者：FR-042〜FR-045 の応答）は加えて status_history の actor_user_id、buyer（user_id、email、name）、payments（result（決済結果）、amount（決済金額）、transaction_ref（取引参照番号）、processed_at）、can_ship（出荷登録可否）、can_deliver（配達完了登録可否）。要求は FR-030 が shipping_address（同じ6キー）、FR-031 が mock_instruction（ADDR-008）、FR-043 が tracking_number。
   - 注文の一覧（FR-032・FR-041 の items）：order_id、order_number、ordered_at、status、total_amount（合計・合計金額）、total_quantity（合計点数）。FR-041 は加えて buyer_email（購入者のメールアドレス）、buyer_name（購入者の氏名）。
   - 在庫単位の一覧（FR-040 の items）：stock_unit_id、sku、product_id、product_code、product_name、variant_name、visibility（商品の公開状態）、supplier_name（仕入先名）、price_excluding_tax、stock_quantity、is_low_stock（低在庫）。
11. 検索条件（query）と並び順の外部値（r2 追加）：
   - FR-011：category_id（分類ID）、keyword（キーワード）、sort（並び順：newest＝新着順、price_asc＝価格の安い順、price_desc＝価格の高い順、name＝商品名順。省略時 newest）、page。
   - FR-032：page。FR-040：sku、product_name（商品名）、supplier_code（仕入先。登録済みの仕入先コードと完全一致）、low_stock_only（低在庫のみ：true＝指定する、false＝指定しない。省略時 false）、page。FR-041：order_number、status（注文状態。複数指定はキーの繰返し：status=paid&status=shipped。値は ADDR-007 の CD-02）、order_date_from（注文日（開始））、order_date_to（注文日（終了））、buyer_email（購入者のメールアドレス）、page。
   - 共通：空の値は要件が「0文字は条件なし」「値のない指定は指定なし」とする項目では指定なしとする。真偽値は true・false の小文字だけを受け付け、sort の4値・コード値・真偽値以外の値は 400 input_error（fields に当該キー）。定義していない query のキーは無視する。
12. エラーの reason・values のキー（r2 追加）：
   - business_error の reason（ERR-02 の12種に1対1）：email_already_registered（メールアドレス登録済み）、quantity_limit_exceeded（数量上限超過）、insufficient_stock（在庫不足）、unavailable_product（販売していない商品を含む）、cart_empty（カートが空）、coupon_already_applied（クーポン適用済み）、coupon_not_found（クーポンなし）、coupon_not_yet_valid（クーポンの有効期間前）、coupon_expired（クーポンの有効期間終了）、below_minimum_purchase_amount（最低購入金額未満）、invalid_status（状態不正）、payment_declined（決済否認）。business_error 以外の reason は null。
   - values のキー（各例外表で定めた値だけを入れる）：stock_unit_id、max_quantity（上限数量）、current_quantity（カート内の現在の数量）、requested_quantity（要求数量）、resulting_quantity（要求後の数量）、minimum_purchase_amount、subtotal、valid_from、valid_to、current_status・current_status_label（現在の注文状態）、stock_units（在庫が不足する在庫単位ごとの stock_unit_id・sku・requested_quantity・stock_quantity）、unavailable_stock_unit_ids（販売していない商品の在庫単位IDの一覧）。
   - input_error の fields[] は field・reason・message とし、reason は required、invalid_type、invalid_length、invalid_format、invalid_choice、out_of_range、mismatch（パスワード（確認）の不一致）、invalid_range（注文日（開始）＞注文日（終了））、unknown_reference（登録済みでない分類ID・仕入先）のいずれか。
13. 追加の API 設計資料の要否（ANALYSIS-001 ARCH-CI-009 のうち API。r2 追加）：別の API 設計資料は作らない。要求・応答の項目の集合と意味は要件（各 FR の入力・返却項目）を正本とし、キー・外部値は本書 9〜12 で一意に定まるため、別資料は FR の表の複製になる。画面・物理DB の資料の要否は本 ADDR の対象外とする。
14. FR-020 の利用中カートの作成と参照用要求（r3 追加。QR-IMPL-001）：
   - 例外の範囲：FR-020 を実行する GET（GET /api/cart/、SCR-005・SCR-006 の表示、購入者向け各画面の共通表示（UI-05）の合計点数）では、認証（E-020-01）と権限（E-020-02）の判定を通過し、かつ本人の利用中カートがない場合に限り、明細0件・クーポンなしの利用中カートを1件作成する（6.8.4 手順4）。これが DD-009 の唯一の例外であり、GET でその他の業務データを登録・更新・削除しない。来訪者・管理者の要求と E-020-03 では作成しない（作成途中は取り消す：CMN-21）。
   - VUL-06 上の位置づけ：VUL-06・NFR-SC-05 の「更新操作」は、利用者の操作で業務データを変える機能（CMN-22 の画面の更新機能：FR-001〜FR-003、FR-021〜FR-025、FR-030、FR-031、FR-034、FR-043〜FR-045）を指し、これらは POST・PATCH・DELETE（画面は CSRF 検証付きの POST：ADDR-002 DD-008）でだけ受け付ける。FR-020 は機能種別「照会・検索」で、作成は照会の結果として要件が定める初期状態（ST-CART-01）の登録であり、明細・クーポンの適用・在庫数量・注文を変えない（6.8.6）。このため FR-020 の GET は更新操作に当たらず、CSRF トークンを要求しない。
   - 冪等性・一意性：同じ購入者の GET を何回・同時に受けても利用中カートは1件で、2回目以降・後着は既存の利用中カートの内容を返す（6.8.9、DQ-09）。同時作成は ADDR-004 4.3 の4（購入者ごとの利用中カートの条件付き一意制約、一意違反の側は作成済みを読み直す）で守る。作成は FR-020 の1業務処理（1トランザクション）の中で行い、冪等キー・送信トークンを用いない。
   - 他サイトからの要求：/api/ は Bearer 認証だけで Cookie を認証に使わない（INV-003）ため、他サイトから認証付きの GET /api/cart/ を送らせることはできない。画面の GET は SameSite=Lax の Cookie によりトップレベルの遷移で送られ得るが、結果は購入者本人がいずれかの購入者向け画面を表示した場合と同じ空の利用中カートの作成に限られ、明細・クーポン・金額・注文・在庫は変化しない。
   - 共通表示の合計点数：UI-05 の合計点数も FR-020 の起動契機（6.8.1）であるため、FR-020 の業務処理（作成を含む）の結果の合計点数を表示し、参照のみの集計で0点を表示して作成を省略しない。E-020-03 の扱いは FR-020 6.8.7 に従う（SCR-901 の表示中の扱いは ASM-002）。
   - Task の割当て（r4 追加。QR-ADDR-R4-001）：共通表示の合計点数のための FR-020 の実行（作成を含む）は FR-020 の業務処理を持つ TASK-012 が担い、その結果の合計点数を共通表示へ供給する部品も TASK-012 が用意する。TASK-002 の共通レイアウトは供給された合計点数を表示する枠だけを持ち、カートの参照・作成を行わない（TASK-012 の完成前で値の供給がない間だけ点数を表示しない。TASK-012 の完成後は購入者向けの全画面で供給する）。これにより依存は TASK-012→（TASK-006 等）→TASK-002 の既存の方向だけで成立し、TASK-002 から TASK-012 への依存（循環）を生じない。

### 4.4 決定理由

OPT-001 は Steering の事前指定（DC-001）を満たし、エラー種別を HTTP ステータスと type の2段で識別でき（DC-002）、DRF の例外ハンドラとページネーションクラス各1つで全 API に一律適用できる（DC-003、DC-005）。OPT-002 は REST の事前指定に反し、OPT-003 は全項目分の入力エラーと判定値の配置を別途決める必要があり項目名規約と混在する。業務エラーは HTTP 422 に統一し、種類を reason で区別することで、画面の通知（MSG-03）と同じ分類を保つ。対象なし・他者データを同じ 404 にすることで存在有無を明かさない（DC-004）。項目キーを要件の項目名からの固定の対応表と命名規則で決め、検索条件・並び順・業務エラーの種類の外部値を列挙することで、並行して実装される Task 間で名前が一致し、API 利用者が値を機械的に解釈できる（DC-006。r2 追加）。項目の集合と意味は要件の入出力表が正本であり、別の API 設計資料はその複製になるため作らない。
FR-020 の作成は OPT-001 の中で GET の唯一の例外として明示する（r3 追加）。OPT-005 は GET で業務データを変えないが、要件の作成・事後条件と AC-UC-004-020 を満たさず要件の振る舞いを変えるため採れない（DC-007）。OPT-006 は照会を送信操作に変え、REST 規約と画面の遷移・共通表示の要件に合わない（DC-001）。この例外は、作成を購入者本人の初期状態1件に限り、冪等で同時でも1件、明細・クーポン・金額・注文・在庫を変えないことを拘束にするため、VUL-06 が防ぐ「参照用の要求による利用者の更新操作の実行」は起こらない。また Web API は Cookie を使わないため他サイトから実行させられない（DC-004、DC-007）。

## 5. 設計差分

要件定義、AIステアリング文書、システム構成図およびデータモデルから一意に導出できない事項だけを記載する。
データに関する重要判断は、判断で追加・確定した差分と拘束だけを記録する。モデル本文の更新はArchitectureへの変更要求として返す。

| ID | 要件・成果物参照先 | 条件・対象 | 追加・確定した内容 | 実装拘束 |
|---|---|---|---|---|
| DD-001 | Steering 5章、FR-001〜FR-045 | 全 Web API | 4.3 の 1・4 のパスとメソッドを用いる。/api/admin/ 配下は管理者のみ、それ以外の購入者機能は購入者のみ（CMN-03） | MUST |
| DD-002 | MSG-05、ERR-01〜ERR-08 | 全エラー応答 | 4.3 の 6・7 の封筒と HTTP ステータス対応で返す。type・reason・fields・values・message を常に含める（該当なしは null・空配列・空オブジェクト） | MUST |
| DD-003 | NFR-US-04、CMN-16 | 入力エラー | fields に誤りのある全項目を、項目名（要求の項目キー）と理由で1回の応答にまとめる | MUST |
| DD-004 | CMN-35、NFR-PF-08 | 一覧 API | 4.3 の 8 のページング表現を用いる。page_size を利用者に指定させない | MUST |
| DD-005 | NFR-EN-04、ADDR-006、ADDR-007 | 全応答 | 日時は +09:00 付き ISO 8601 秒単位、識別子は整数、コード値は値と _label を併記する | MUST |
| DD-006 | FR-002、NFR-SC-08 | ログイン応答 | token（ログイン状態を示す情報）・expires_at（有効期限日時）・user（user_id・email・name・user_type・user_type_label）を返す | MUST |
| DD-007 | CMN-18、CMN-04、NFR-SC-03 | 識別子の指定 | 整数として解釈できない識別子、存在しない識別子、他の購入者のデータは同じ 404 not_found とし、存在有無を区別しない | MUST |
| DD-008 | NFR-SC-15 | 要求本文の未定義項目 | 定義していない項目は無視する（会員登録の user_type 等を受け付けても登録内容に反映しない） | MUST |
| DD-009 | NFR-SC-21（VUL-06） | GET 要求 | GET では業務データを変更しない。状態を変える操作は POST・PATCH・DELETE に限る。唯一の例外は DD-015 の FR-020 の利用中カートの作成とする（r3 改訂） | MUST |
| DD-010 | NFR-SC-10 | 全エラー応答 | スタックトレース・SQL 文・ファイルパス・ライブラリ名と版、例外の文言を応答に含める | MUST_NOT |
| DD-011 | CMN-34、FR-001〜FR-045 | 要求・応答の項目キー（r2 追加） | 4.3 の9の命名規則と10の対応表のキーを用い、要件の入力・返却項目と1対1で対応させる。表にない項目を加えない | MUST |
| DD-012 | FR-011、FR-032、FR-040、FR-041、CMN-35 | 検索条件・並び順（r2 追加） | 4.3 の11の query キーと外部値（sort は newest・price_asc・price_desc・name）を用い、それ以外の値は入力エラーとする | MUST |
| DD-013 | ERR-01、ERR-02、MSG-05 | エラーの reason・values・fields（r2 追加） | 4.3 の12の reason・values のキー・fields[].reason の値を用いる | MUST |
| DD-014 | Steering 5章、OQ-PJ-001 | API 設計資料（r2 追加） | 項目単位の契約の正本は本 ADDR の 4.3 と要件の入出力表とし、別の API 設計資料を作らない（ARCH-CI-009 の API 部分の判断） | MUST |
| DD-015 | FR-020 6.8.1・6.8.4 手順4・6.8.5・6.8.6、ST-CART-01、AC-UC-004-020、UI-05、NFR-SC-05、NFR-SC-21（VUL-06）、CMN-22 | FR-020 の利用中カートの作成（r3 追加） | FR-020 を実行するすべての GET（GET /api/cart/、SCR-005・SCR-006 の表示、購入者向け各画面の共通表示の合計点数）で、E-020-01・E-020-02 の判定を通過し本人の利用中カートがない場合に限り、明細0件・クーポンなしの利用中カートを1件作成する。これは VUL-06 の更新操作に当たらないため CSRF トークンを要求しない（4.3 の14） | MUST |
| DD-016 | FR-020 6.8.7・6.8.9、CMN-19、CMN-21、DQ-09、ADDR-004 4.3 の4 | 作成の冪等性・一意性（r3 追加） | 同じ購入者の GET を何回・同時に受けても利用中カートは1件とし、2回目以降・後着は既存の利用中カートの内容を返す（条件付き一意制約と一意違反時の読み直し）。作成は FR-020 の1業務処理の中で行い、E-020-03 では作成を取り消す。冪等キー・送信トークンを用いない | MUST |

## 6. 種別固有差分

`design_type`に対応する節を1つだけ残し、その他の節は生成結果から削除する。要件等から一意に決まらない差分だけを記載し、該当する差分がない項目は `なし` とする。

### C. 外部インターフェースの場合

| 項目 | 設計差分 | 根拠・参照先 |
|---|---|---|
| 方式・プロトコル | REST/JSON over HTTP(S)。本番は HTTPS のみ（ADDR-014） | Steering 5章、DD-001 |
| 同期・非同期 | 全 API 同期。支払も同期で最大10秒の応答待ちを含む（ADDR-008） | FR-031、DD-001 |
| 契約の正本・版 | 本 ADDR-001（ACTIVE）4.3 の1〜13（項目キー・検索条件・エラー理由を含む）。docs/specifications/api-contract.md が格納された場合はそれを正とし、差異は新 ADDR で置換する | OQ-PJ-001、ASM-001、DD-011〜DD-014 |
| 互換性・バージョニング | 版番号をパスに含めない。第1期内の変更は項目の追加のみとし、既存項目の削除・意味変更をしない | DD-001 |
| タイムアウト | なし（API 側に独自の打切りを設けない。支払の10秒は ADDR-008） | なし |
| 冪等性・重複制御 | 冪等キーを設けない。再送は受付時点のデータで再判定する（CMN-23、ADDR-004）。GET は冪等とし、FR-020 の利用中カートの作成も何回・同時に受けても購入者ごとに1件とする（r3 追加） | CMN-23、DD-009、DD-015、DD-016 |
| 再送・補償 | 自動再送・補償処理なし | CMN-23 |
| トランザクション境界 | 1要求＝1業務処理の境界（ADDR-004） | ADDR-004 |
| 責任分界 | API 層は電文の変換・認証情報の取出し・例外の変換のみ。業務判定は共通業務処理（ADDR-012） | CMN-34、ADDR-012 |

## 7. AI実装制約

当該ADDR固有の不変条件・禁止事項だけを記載する。一般的な実装規約はAIステアリング文書を参照する。

| ID | 種別 | 内容 | 根拠ID |
|---|---|---|---|
| INV-001 | 不変条件 | 画面と API の判定順序・エラー種別・業務エラーの種類は同じ業務処理の結果から生成し、API 層で判定を追加・省略しない | CMN-14、CMN-34、NFR-LG-06 |
| INV-002 | 不変条件 | すべての外部入力（path・query・本文）は業務処理で型・桁数・値域・形式を検証し、ORM のパラメータ化以外で SQL を組み立てない（SQL・OS コマンドインジェクションの成立 0件） | NFR-SC-04、NFR-SC-21（VUL-04） |
| INV-003 | 禁止事項 | /api/ で Cookie によるセッション認証（DRF SessionAuthentication）を有効にしない | NFR-SC-21（VUL-06）、ADDR-002 |
| INV-004 | 禁止事項 | 応答に、他の購入者の情報、来訪者・購入者への仕入先・決済記録、パスワード（照合用を含む）を含めない | NFR-SC-24、MSG-04 |
| INV-005 | 禁止事項 | GET の要求で、DD-015 の利用中カートの作成以外の業務データ（カート明細、適用中のクーポン、注文済のカート、注文、在庫数量、決済記録、監査ログ等）を登録・更新・削除しない。GET の要求での利用中カートの作成は FR-020 の業務処理（ADDR-012）からだけ行い、FR-004、FR-010〜FR-012、FR-032、FR-033、FR-040〜FR-042 の業務処理の中で作成しない。GET 以外の FR-021（POST）・FR-025（DELETE）が要件（各手順、ST-CART-01）どおり利用中カートを作成することは本項の対象外であり禁じない（r3 追加、r4 改訂） | NFR-SC-21（VUL-06）、FR-020 6.8.6、CMN-21 |

## 8. 仮定事項

設計を一意に確定できない場合に、AIが処理継続のために採用した仮定を記載する。外部契約、法令、認証情報、秘密情報など、推測してはならない事項は仮定しない。

| ID | 不足・曖昧な情報 | 採用した仮定 | 根拠 | リスク |
|---|---|---|---|---|
| ASM-001 | 提供済み API 契約（docs/specifications/api-contract.md）が未格納（OQ-PJ-001） | 未格納の間は本 ADDR を本システムの API 契約の正とする。格納された場合は同資料を正とし、差異を新 ADDR で置換し影響 Task を ADDR から再開する | Steering 5章・8.1、functional_requirements.md 1.2 | MEDIUM |
| ASM-002 | SCR-901（システムエラー）を表示する際の共通表示（UI-05）で FR-020 自体が E-020-03 となった場合の扱いが要件にない（E-020-03 は SCR-901 の表示を求めるため循環する） | SCR-901 の表示中に共通表示の FR-020 が失敗した場合に限り、作成を取り消し、合計点数を表示せずに SCR-901 を表示する。それ以外の画面での E-020-03 は FR-020 6.8.7 どおり SCR-901 とする（r3 追加） | FR-020 6.8.7、UI-05、CMN-21 | LOW |

## 9. 後続工程への引継ぎ事項

設計判断または設計差分によって、後続工程で追加考慮が必要となる事項だけを記載する。

| 区分 | 引継ぎ事項 | 参照先 |
|---|---|---|
| 実装 | DRF の共通例外ハンドラ・共通ページネーション・認証クラスを TASK-002 で1つずつ用意し、全 API Task が再利用する。認証を要しない API で無効な Bearer を 401 にしない。4.3 の10〜12のキー・外部値（reason・fields[].reason・sort 等）は TASK-002 の共通定数として1か所で定義し、各 API Task のシリアライザはそれを参照する。FR-020 は GET /api/cart/・SCR-005・SCR-006 の表示・共通表示（UI-05）の合計点数のいずれでも作成を含む同じ業務処理を用い、CSRF 検証の対象外とする。共通表示の合計点数は TASK-012 が FR-020 の業務処理（作成を含む）の結果を共通表示へ供給する部品として実装し、TASK-002 の共通レイアウトは供給された値を表示する枠だけを持ってカートを参照・作成しない。参照のみの集計で代替しない（r3 追加、r4 改訂：4.3 の14 の Task の割当て） | DD-002、DD-004、DD-006、DD-011〜DD-013、DD-015、DD-016、INV-003、INV-005 |
| テスト | 全 API について ERR-01〜ERR-08 の HTTP ステータス・type・reason・fields を検証する。識別子の非整数・他者データが同じ 404 であることを確認する。各 API の応答キーが 4.3 の10と一致し表にないキーがないこと、FR-011 の sort 4値と不正値、FR-040 の low_stock_only・FR-041 の status の繰返しを検証する。AC-UC-004-020 を Web API と画面（SCR-005・SCR-006・共通表示）で確認し、同時の GET /api/cart/ でも利用中カートが1件であること、来訪者・管理者の要求と E-020-03 で作成されないこと、FR-020 の GET で明細・クーポン・在庫・注文が変化しないこと、FR-020 以外の GET の Web API で業務データが変化しないことを確認する（r3 追加）。共通表示の合計点数での作成（利用中カートのない購入者が購入者向けの任意の画面を表示すると利用中カートが1件になり点数が0点で表示されること）は TASK-012 の試験で確認する（r4 追加） | DD-002、DD-003、DD-007、DD-011〜DD-013、DD-015、DD-016、INV-005、AC-UC-002-012、AC-UC-004-020 |
| 運用 | API 契約資料が格納された時点で本 ADDR との差異を確認する | ASM-001 |
