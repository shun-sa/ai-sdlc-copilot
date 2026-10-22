# 結合試験レポート

- run_id: RUN-20261022-MC
- 工程: INTEGRATION_TEST
- Integration Test Agent としての結果: SUCCESS
- 判定の正本: `.github/skills/integration-test/policy/integration-test-policy.yaml`

## 1. 試験対象と環境

- 連携範囲: ローカル検証環境。Web API は Django のテストクライアントで URLルーティング・ミドルウェア・認証・権限判定・例外ハンドラ・Service・ORM を通して実行し、DB は Docker（postgres:16）上の使い捨てテストDBへ接続する。
- 構成要素:
  - Web API（Django 5.2 / DRF）
  - Service 層（shop.services）
  - ORM / PostgreSQL 16（Docker コンテナ、使い捨てテストDB）
  - 決済サービス（模擬実装 MockPaymentGateway。外部ネットワークへ接続しない）
  - 管理コマンド（load_initial_data）
- Database: PostgreSQL 16（Docker コンテナ） / test_<DB_NAME>（pytest-django が作成・破棄する使い捨てテストDB）
- 本番環境・本番DB・本番データ・本番資格情報: いずれも未使用
- 外部サービス: MOCK（shop.payments.mock.MockPaymentGateway。異常系は応答不正・締切超過を模擬）

## 2. External Test Case の入力状態

- provided: False
- user_confirmed_without_external_cases: True
- 経緯: AI INITIAL Case を固定（snapshot initial-1）した後に標準配置先を確認し、未配置であったため EXTERNAL_TEST_INPUT_REQUIRED を返却した。ユーザーが External Case なしで続行することを明示的に選択したため、--allow-none 相当として External Case 0件で継続した。

## 3. 実行結果（AI INITIAL / GAP_FILL / EXTERNAL 分離）

| 区分 | 件数 | PASS | FAIL | ERROR | BLOCKED |
| --- | --- | --- | --- | --- | --- |
| AI_GENERATED / INITIAL | 54 | 54 | 0 | 0 | 0 |
| AI_GENERATED / GAP_FILL | 84 | 84 | 0 | 0 | 0 |
| EXTERNAL | 0 | 0 | 0 | 0 | 0 |
| TOTAL | 138 | 138 | 0 | 0 | 0 |

- JUnit（実測）: total=138 / passed=138 / failed=0 / errors=0 / skipped=0
- 実行コマンド: `docker compose exec -T app pytest`（単体791件と結合138件を1コマンドで収集し 929 passed。ADDR-012 DD-002）／JUnit 取得は `docker compose exec -T app pytest tests/integration --junitxml=reports/integration-test/junit.xml`

## 4. Coverage 比較（Gap Fill 前の測定値）

| 区分 | 件数 |
| --- | --- |
| Required Coverage | 143 |
| COMMON | 0 |
| AI_ONLY | 59 |
| EXTERNAL_ONLY | 0 |
| MISSING | 84 |

- AI INITIAL Coverage 率: 41.26%
- External Coverage 率: 測定対象外（External Case 0 件）
- Combined Initial Coverage 率: 41.26%
- 最終 Coverage 率（GAP_FILL 後）: 100.0%

### 4.1 初回測定時に凍結した初期Coverage測定値（書き換えていない）

- Required Coverage（初版）: 70 件 / COMMON 0 / AI_ONLY 59 / EXTERNAL_ONLY 0 / MISSING 11
- AI INITIAL Coverage 率: 84.29% / Combined Initial Coverage 率: 84.29%
- 正本: `reports/integration-test/initial-coverage-metrics.json`
- repair cycle 3（最終精査）までに Required Coverage は 143 件となった（C10 是正で追加した分を含む）。repair cycle 1 で Required Coverage の導出元（NFR-SC の検証方法・UC の同時実行受入基準）を是正し 17 件を追加したため、上表の母数は 87 件となっている。AI INITIAL Case が実際にCoverageしたCoverage Key の件数（59 件）と AI INITIAL Case の内容（54 件、sha256 94f1d86…）は変更していない。

## 5. ケースの抜け漏れ（MISSING）と Gap Fill

| Gap ID | Coverage Key | 要件ID | Criterion | 不足していた確認内容 | 補完した Case |
| --- | --- | --- | --- | --- | --- |
| GAP-001 | CK-CMN-ERR-01 | FR-004 | error-handling | 認証エラー・権限エラー・対象なしエラー・業務エラーの各応答本文を確認する | IT-AI-GF-009 |
| GAP-002 | CK-CMN-ERR-02 | FR-030 | error-handling | 複数のエラー要因が同時に成立する要求（未認証かつ入力不正、権限なしかつ対象なし等）を送る | IT-AI-GF-010 |
| GAP-003 | CK-E2E-03 | FR-031 | end-to-end-flow | 支払が否認された後、同じ注文に再度支払（承認）を行い、管理者が決済記録を確認する | IT-AI-GF-007 |
| GAP-004 | CK-FR001-05 | FR-001 | database | 正規化（前後空白除去・英小文字化）後が同一となる5種類のメールアドレスで会員登録要求を同時に送信する（AC-UC-001-017、10試行） | IT-AI-GF-020 |
| GAP-005 | CK-FR011-05 | FR-011 | api | 総ページ数を超えるページ番号、および該当0件となる条件を指定する | IT-AI-GF-001 |
| GAP-006 | CK-FR021-04 | FR-021 | error-handling | 存在しない在庫単位ID・解釈できない値を指定してカート明細追加を要求する | IT-AI-GF-002 |
| GAP-007 | CK-FR021-05 | FR-021 | database | 同一在庫単位・数量6のカート明細追加を2本の接続から同時に送信する（AC-UC-004-025、10試行） | IT-AI-GF-021 |
| GAP-008 | CK-FR026-03 | FR-026 | api | 適用中クーポンが条件を満たさない状態（有効期間外・最低購入金額未満・明細0件）でカートを照会する | IT-AI-GF-003 |
| GAP-009 | CK-FR030-07 | FR-030 | error-handling | カート明細の数量が10を超える状態で注文確定する | IT-AI-GF-004 |
| GAP-010 | CK-FR030-08 | FR-030 | database | 複数の注文を連続して確定する | IT-AI-GF-005 |
| GAP-011 | CK-FR030-09 | FR-030 | database | 在庫数量1の在庫単位を1個ずつ含む2つのカートを同時に注文確定する | IT-AI-GF-011 |
| GAP-012 | CK-FR031-06 | FR-031 | error-handling | mock_result に approve/decline 以外の値を指定する | IT-AI-GF-006 |
| GAP-013 | CK-FR031-07 | FR-031 | state-transition | 注文受付の同一注文へ mock_result=approve の支払要求を2件同時に送信する（AC-UC-007-013、10試行） | IT-AI-GF-022 |
| GAP-014 | CK-FR031-08 | FR-031 | state-transition | 注文受付の同一注文へ支払要求（approve）とキャンセル要求を同時に送信する（AC-UC-007-019、10試行） | IT-AI-GF-023 |
| GAP-015 | CK-FR034-03 | FR-034 | state-transition | 複数明細を持つ同一注文へキャンセル要求を2件同時に送信する（AC-UC-009-007、10試行） | IT-AI-GF-024 |
| GAP-016 | CK-FR043-03 | FR-043 | state-transition | 支払済の同一注文へ、2人の管理者が別々の配送伝票番号で出荷登録を同時に送信する（AC-UC-011-020、10試行） | IT-AI-GF-025 |
| GAP-017 | CK-FR045-02 | FR-045 | state-transition | 注文受付の同一注文へ、管理者の注文キャンセルと購入者の注文キャンセルを同時に送信する（AC-UC-012-009、10試行） | IT-AI-GF-026 |
| GAP-018 | CK-FR045-03 | FR-045 | state-transition | 支払済の同一注文へ、管理者の注文キャンセルと別の管理者の出荷登録を同時に送信する（AC-UC-012-010、10試行） | IT-AI-GF-027 |
| GAP-019 | CK-FR045-04 | FR-045 | state-transition | 注文受付の同一注文（合計5,500円）へ、管理者の注文キャンセルと購入者の支払（approve）を同時に送信する（AC-UC-012-011、10試行） | IT-AI-GF-028 |
| GAP-020 | CK-FR060-02 | FR-060 | database | 違反を1件含む定義ファイルで初期データ一括投入コマンドを実行する | IT-AI-GF-008 |
| GAP-021 | CK-FR060-03 | FR-060 | authentication | 認証トークンと画面のログインセッションを保持した状態で、全削除指定つきの初期データ一括投入を実行する | IT-AI-GF-019 |
| GAP-022 | CK-FROUT01-01 | FR-OUT-01 | end-to-end-flow | 注文確定済の注文に対して支払を実行し、使用される決済ゲートウェイ実装・決済要求の項目・外部ネットワークへの接続有無を確認する | IT-AI-GF-029 |
| GAP-023 | CK-FROUT02-01 | FR-OUT-02 | api | 商品・商品分類・仕入先・在庫単位・クーポンの登録・更新・削除を意図した要求（POST/PATCH/DELETE）を管理者の認証付きで送信し、管理者画面の更新フォームを確認する | IT-AI-GF-030 |
| GAP-024 | CK-FROUT03-01 | FR-OUT-03 | api | 在庫補充・入荷登録を意図した要求を送信し、あわせて注文確定→支払→出荷→配達完了まで実行して在庫数量の推移を確認する | IT-AI-GF-031 |
| GAP-025 | CK-FROUT04-01 | FR-OUT-04 | state-transition | 注文状態の定義を確認し、明細単位の出荷指定を含む出荷登録、返品・返金・部分出荷を意図した要求、配達完了後のキャンセルを実行する | IT-AI-GF-032 |
| GAP-026 | CK-FROUT05-01 | FR-OUT-05 | api | クーポンを1枚適用した状態で別のクーポンを適用し、カート内容・注文確定後の割引額を確認する | IT-AI-GF-033 |
| GAP-027 | CK-FROUT06-01 | FR-OUT-06 | api | 通貨・言語を指定するクエリと Accept-Language ヘッダーを付けて商品照会・画面表示を行い、国外を想定した都道府県コードで注文確定を試みる | IT-AI-GF-034 |
| GAP-028 | CK-FROUT07-01 | FR-OUT-07 | api | 同一内容のカートに対し、都道府県が異なる配送先（01・47）と、実在しない郵便番号・配送日時指定・配送業者の項目を含む要求で注文確定する | IT-AI-GF-035 |
| GAP-029 | CK-FROUT08-01 | FR-OUT-08 | end-to-end-flow | 会員登録・注文確定・支払・出荷登録・注文キャンセルを連続して実行する | IT-AI-GF-036 |
| GAP-030 | CK-FROUT09-01 | FR-OUT-09, NFR-SC-17 | api | 会員情報の変更・パスワード変更・パスワード再設定・退会を意図した要求と画面を確認する | IT-AI-GF-037 |
| GAP-031 | CK-FROUT10-01 | FR-OUT-10 | authentication | 未ログインでカート照会・カート明細追加・注文確定・注文履歴照会（API）とカート画面・注文手続き画面（画面）を要求する | IT-AI-GF-038 |
| GAP-032 | CK-FROUT11-01 | FR-OUT-11, NFR-SC-14 | authentication | 同一利用者で認証失敗を10回連続させた直後に、正しい資格情報でログインする | IT-AI-GF-039 |
| GAP-033 | CK-FROUT12-01 | FR-OUT-12 | state-transition | 注文日時を30日前に遡らせた未払いの注文を照会し、支払を実行する | IT-AI-GF-040 |
| GAP-034 | CK-FROUT13-01 | FR-OUT-13, NFR-SC-28 | api | 商品詳細の応答項目、レビュー・画像・お気に入り・おすすめを意図した経路、商品詳細画面の表示内容、ファイルを保持する項目の有無を確認する | IT-AI-GF-041 |
| GAP-035 | CK-FROUT14-01 | FR-OUT-14 | api | PC とスマートフォンの User-Agent で同じ画面を要求し、スマートフォン専用パスを要求する | IT-AI-GF-042 |
| GAP-036 | CK-FROUT15-01 | FR-OUT-15 | api | 一覧APIへ出力形式を指定するクエリ（format=csv/pdf、export、download）を付けて要求し、出力用の経路と画面のリンクを確認する | IT-AI-GF-043 |
| GAP-037 | CK-FROUT16-01 | FR-OUT-16, NFR-LG-04 | api | 特定商取引法に基づく表記・利用規約等の静的ページを要求し、主要画面に当該ページへの導線が無いことを確認する | IT-AI-GF-044 |
| GAP-038 | CK-NFRAV10-01 | NFR-AV-10 | error-handling | DB が応答しない状態を作り、認証不要の照会API・認証が必要なAPI・画面を要求する。その後 DB を復旧させて同じ経路を再度要求する | IT-AI-GF-077 |
| GAP-039 | CK-NFREN01-01 | NFR-EN-01, NFR-EN-02 | database | 結合試験の実行環境で、app の言語・フレームワークの版と、接続先 DB の製品・版を確認する | IT-AI-GF-056 |
| GAP-040 | CK-NFREN04-01 | NFR-EN-04 | database | app・db のタイムゾーン設定と DB の文字コードを確認し、注文・ログイン・画面の日時表記と日本語の表示を確認する | IT-AI-GF-057 |
| GAP-041 | CK-NFREN05-01 | NFR-EN-05, NFR-LG-10 | end-to-end-flow | 外部ネットワークへの接続を遮断した状態で、会員登録→ログイン→検索→カート→注文確定→支払→出荷→配達完了まで操作し、主要画面の参照先 URL を確認する | IT-AI-GF-058 |
| GAP-042 | CK-NFREN08-01 | NFR-EN-08 | api | app サービスのコンテナで実行中の起動コマンドと WSGI エントリポイントを確認する（要件が定める実行方法 `docker compose exec app pytest` での実行を前提とする） | IT-AI-GF-076 |
| GAP-043 | CK-NFREN09-01 | NFR-EN-09 | end-to-end-flow | フロントエンドのビルド設定の有無、画面が読み込む JavaScript の内容と本数、商品詳細画面の HTML、カート画面と カート照会API の金額を確認する | IT-AI-GF-075 |
| GAP-044 | CK-NFREN11-01 | NFR-EN-11 | api | URLconf に登録された全経路のパス、購入者・管理者の主要 API を一巡した応答の全 JSON 項目名（入力エラー応答の項目名を含む）、自動テストのファイル名を収集して規約と照合する | IT-AI-GF-071 |
| GAP-045 | CK-NFREN12-01 | NFR-EN-12 | api | app のイメージへ導入済みの全依存ライブラリについて、ライセンス（License-Expression・License・分類子）を解決して照合する | IT-AI-GF-072 |
| GAP-046 | CK-NFRLG02-01 | NFR-LG-02 | api | 税抜1,000円の商品を含む画面（商品一覧・商品詳細・カート）を表示し、金額内訳を確認する | IT-AI-GF-065 |
| GAP-047 | CK-NFRLG03-01 | NFR-LG-03 | database | 注文確定→支払→キャンセルまで実行し、キャンセル前後の注文・注文明細・配送先・決済記録・注文状態履歴の内容を比較する。あわせて注文を削除する要求（DELETE）を送信する | IT-AI-GF-079 |
| GAP-048 | CK-NFRLG05-01 | NFR-LG-05 | api | カード番号・有効期限・セキュリティコードを含む支払要求を送信し、決済要求の項目・保存内容・支払画面の入力項目を確認する | IT-AI-GF-055 |
| GAP-049 | CK-NFRLG09-01 | NFR-LG-09 | error-handling | 都道府県コードに範囲外・桁違い・英字・未入力の値を指定して注文確定を試み、その後 01 と 47 で注文確定する | IT-AI-GF-066 |
| GAP-050 | CK-NFRMG01-01 | NFR-MG-01 | database | 稼働開始時に用いる初期データ定義ファイル（app/seed/initial_data.json）の内容を確認し、実際に投入する | IT-AI-GF-067 |
| GAP-051 | CK-NFROM07-01 | NFR-OM-07 | api | ENV-01 で app のソースツリーに対し ruff を実行し、解析対象のファイル一覧と指摘件数を確認する | IT-AI-GF-070 |
| GAP-052 | CK-NFROM11-01 | NFR-OM-11 | error-handling | 検索・未認証要求・支払・未捕捉例外を発生させ、出力されたログ行と DB の監査ログ・注文状態履歴を確認する | IT-AI-GF-059 |
| GAP-053 | CK-NFROM13-01 | NFR-OM-13, NFR-MG-07 | database | 違反を含む定義ファイルで初期データ一括投入を実行し、違反内容を確認した後、修正した定義ファイルを全削除指定で再実行し、さらにもう一度実行する | IT-AI-GF-068 |
| GAP-054 | CK-NFROM18-01 | NFR-OM-18 | api | X-Request-ID を指定した支払要求、指定しない要求、形式が不正な値を指定した要求を送信する | IT-AI-GF-060 |
| GAP-055 | CK-NFRPF07-01 | NFR-PF-07, NFR-LG-06 | database | 在庫数量5の在庫単位に対して、各1個のカート明細を持つ10名の購入者が同時に注文確定を要求する（VDC-05 の条件）。10試行行う | IT-AI-GF-069 |
| GAP-056 | CK-NFRPF08-01 | NFR-PF-08 | api | 上限を超える件数の商品・注文・在庫単位・商品分類を用意し、各一覧APIの先頭ページ・最終ページを取得する | IT-AI-GF-061 |
| GAP-057 | CK-NFRPF11-01 | NFR-PF-11 | state-transition | 在庫3の在庫単位4件（合計12個）に対し、クーポン適用の有無を混在させた24件の注文確定を同時に送信し、続けて成立した注文へ支払・キャンセルを同時に要求する | IT-AI-GF-080 |
| GAP-058 | CK-NFRPF12-01 | NFR-PF-12 | database | 定期実行のライブラリの導入状況・コンテナの cron 定義・shop の管理コマンドを確認し、引数なしでの管理コマンド実行を試みる。あわせて注文日を8年前にした注文を残したまま業務操作を続ける | IT-AI-GF-078 |
| GAP-059 | CK-NFRPF16-01 | NFR-PF-16 | database | 認証トークン・ログインセッション・カートを作成し、別のクライアントから同じ状態を参照し、DB の該当行を削除した後に再度要求する | IT-AI-GF-062 |
| GAP-060 | CK-NFRPF17-01 | NFR-PF-17 | api | 決済連携部分の各モジュールの import、shop 配下で決済連携部分を利用しているモジュール、決済要求・決済応答の項目定義を解析し、あわせて実際の支払で境界へ渡される決済要求を記録する | IT-AI-GF-073 |
| GAP-061 | CK-NFRSC04-01 | NFR-SC-04 | error-handling | 会員登録・ログイン・商品検索・商品詳細・カート明細追加・クーポン適用・管理者検索・支払の各入力項目へ、SQL インジェクションと OS コマンドインジェクションの攻撃文字列を送信する | IT-AI-GF-016 |
| GAP-062 | CK-NFRSC04-02 | NFR-SC-04 | error-handling | 会員登録画面・ログイン画面・商品一覧の検索条件・管理者の在庫単位一覧／注文一覧の検索条件へ、SQL・OSコマンドの攻撃文字列を送信する | IT-AI-GF-017 |
| GAP-063 | CK-NFRSC04-03 | NFR-SC-04 | database | 定義ファイルのコード項目（仕入先コード・分類コード）と名称項目（氏名・仕入先名・商品名・商品説明）へ攻撃文字列を記載して初期データ一括投入を実行する | IT-AI-GF-018 |
| GAP-064 | CK-NFRSC05-01 | NFR-SC-05 | authentication | Cookie のログインセッションで認証した購入者の更新要求（カート明細追加）を、CSRF対策用トークンなしで送信する。あわせてトークンありの同一要求も送信する | IT-AI-GF-012 |
| GAP-065 | CK-NFRSC05-02 | NFR-SC-05 | authentication | Cookie のログインセッションで認証した管理者の更新要求（出荷登録）を、CSRF対策用トークンなしで送信する。あわせてトークンありの同一要求も送信する | IT-AI-GF-013 |
| GAP-066 | CK-NFRSC05-03 | NFR-SC-05 | api | 氏名・配送先（受取人氏名・市区町村番地）・商品名に HTML の script タグ等を含む値を登録し、管理者の注文一覧・注文詳細・在庫単位一覧を表示する | IT-AI-GF-014 |
| GAP-067 | CK-NFRSC05-04 | NFR-SC-05 | api | 氏名・商品名・配送先に HTML の script タグ等を含む値を登録し、商品一覧・商品詳細・注文履歴・注文詳細を表示する | IT-AI-GF-015 |
| GAP-068 | CK-NFRSC07-01 | NFR-SC-07 | authentication | 実行中の秘密鍵・DB パスワードが環境変数から与えられていることを確認し、app に同梱される全ソース・設定・テンプレートを当該の値で走査する。あわせて環境変数を与えずに設定を2回読み込み、既定値を確認する | IT-AI-GF-074 |
| GAP-069 | CK-NFRSC08-01 | NFR-SC-08 | authentication | ログインを2回行い、トークンの値・保存形式・有効期限を確認し、有効期限日時の直前・有効期限日時ちょうど・ログアウト後の要求を行う | IT-AI-GF-047 |
| GAP-070 | CK-NFRSC10-01 | NFR-SC-10 | error-handling | 内部情報（SQL・ファイルパス・ライブラリ名）を含むメッセージの未捕捉例外を Web API・画面で発生させ、あわせて対象なし・入力エラーの応答を確認する | IT-AI-GF-048 |
| GAP-071 | CK-NFRSC12-01 | NFR-SC-12 | authentication | 購入者・管理者がメールアドレスとパスワードで認証し、トークンをクエリ・Cookie で渡した場合と、誤ったパスワード・未登録のメールアドレスで認証した場合を確認する | IT-AI-GF-049 |
| GAP-072 | CK-NFRSC13-01 | NFR-SC-13 | authentication | メールアドレスとパスワードだけでログインし、発行された認証トークン・ログインセッションをそのまま利用する | IT-AI-GF-045 |
| GAP-073 | CK-NFRSC15-01 | NFR-SC-15 | authentication | ロールを指定した会員登録（API・画面）と、ロール変更を意図した要求を行い、初期データ一括投入で管理者を登録する | IT-AI-GF-050 |
| GAP-074 | CK-NFRSC19-01 | NFR-SC-19 | authentication | ログイン前後のセッション識別子を比較し、ログイン前の識別子でログイン後の画面を要求し、ログアウト後に識別子を再利用する | IT-AI-GF-051 |
| GAP-075 | CK-NFRSC22-01 | NFR-SC-22 | database | 初期データ一括投入・ログイン成功・ログイン失敗・ログアウトを実行し、注文確定から配達完了までの状態変更を行う | IT-AI-GF-052 |
| GAP-076 | CK-NFRSC23-01 | NFR-SC-23 | database | 監査ログ・注文状態履歴の参照・更新・削除を意図した要求（API・画面）を送信し、その後に正常な状態変更を行う | IT-AI-GF-053 |
| GAP-077 | CK-NFRSC24-01 | NFR-SC-24, NFR-LG-01 | api | 来訪者・他の購入者・本人・管理者として注文・商品を照会し、支払時の決済要求とアプリケーションログを確認する | IT-AI-GF-054 |
| GAP-078 | CK-NFRSC27-01 | NFR-SC-27 | api | 同一クライアントから公開API60回・認証付きAPI30回・認証失敗20回を連続で送信する | IT-AI-GF-046 |
| GAP-079 | CK-NFRUS03-01 | NFR-US-03 | database | JIS 第3・第4水準の漢字を含む氏名・受取人氏名・住所で会員登録と注文確定を行い、API 応答・DB・画面表示を確認する | IT-AI-GF-063 |
| GAP-080 | CK-NFRUS04-01 | NFR-US-04 | error-handling | 会員登録画面で4項目を同時に誤って送信する | IT-AI-GF-064 |
| GAP-081 | CK-NFRSC25-01 | NFR-SC-25 | database | 初期データ定義ファイルの値が架空であること、結合試験の接続先が使い捨てテストDBであることを確認する | IT-AI-GF-081 |
| GAP-082 | CK-NFROM17-01 | NFR-OM-17 | api | 環境別設定（DB接続・秘密鍵・許可ホスト・デバッグ表示・Cookie の Secure 属性）が環境変数だけで切り替わることを確認する | IT-AI-GF-082 |
| GAP-083 | CK-NFREN07-01 | NFR-EN-07 | api | app のソース・設定がホスト OS 固有のパス・分岐・文字コード既定値に依存しないことを確認する | IT-AI-GF-083 |
| GAP-084 | CK-NFREN03-01 | NFR-EN-03 | database | 実行基盤が app・db の2サービスだけで成立し、本番基盤固有の製品に依存しないことを確認する | IT-AI-GF-084 |

## 6. 不具合（Defect）

| 区分 | 件数 |
| --- | --- |
| Case Failure | 0 |
| Unique Defect | 1 |
| COMMON_DEFECT | 0 |
| AI_ONLY_DEFECT | 1 |
| EXTERNAL_ONLY_DEFECT | 0 |

| Defect ID | 分類 | 状態 | 検出Case | 根拠要件 | Error 箇所 | 対応・差し戻し先 |
| --- | --- | --- | --- | --- | --- | --- |
| DEF-IT-001 | ADR_REQUIRED | 解消済み | IT-AI-GF-023 | FR-031 | app/shop/services/orders.py pay_order（状態判定→決済要求→行ロック再判定の順序）／docs/addr/ADDR-009.md DD-005・INV-006 | ADDR（ADDR-013 採択）→ IMPLEMENTATION（app/shop/services/orders.py 是正） |

- 詳細は `error-report.md` を参照。

## 7. Test Criteria の判定

| Criterion | 適用 | 結果 | 根拠 |
| --- | --- | --- | --- |
| api | 適用 | PASS | FR-001〜FR-004・FR-010〜FR-012・FR-020〜FR-025・FR-032・FR-033・FR-040〜FR-042 の Web API について、HTTP要求からルーティング・認証・権限判定・Service・ORM・PostgreSQL までを 通した応答（ステータス・項目・ページング・金額内訳）を api-contract と各FRの出力仕様で確認した。あわせて画面出力の HTML エスケープ（NFR-SC-05、VUL-05）を購入者画面・管理者画面で確認した。さらに C10 是正として、対象外機能（FR-OUT-02・03・05〜07・09・13〜16）の経路が存在しないこと、一覧の応答件数上限（NFR-PF-08）、X-Request-ID の相関（NFR-OM-18）、個人情報の返却範囲（NFR-SC-24、NFR-LG-01）、カード情報を扱わないこと（NFR-LG-05）、総額表示（NFR-LG-02）を確認した。 |
| authentication | 適用 | PASS | 認証トークンの発行・多重ログイン・ログアウトによる無効化・期限切れ・未認証・ロール別権限（CMN-02、CMN-03、CMN-09、CMN-11、CMN-12）を、実際のAuthorizationヘッダーと認証クラス経由で確認した。あわせて Cookie のログインセッションで認証する画面更新要求の CSRF 対策用トークン検証（NFR-SC-05、VUL-06）と、全削除指定の実行後に旧トークン・旧ログインセッションが拒否されること（FR-060 手順9、ADDR-002 DD-009〜011）を確認した。さらに C10 是正として、認証トークンの保護（NFR-SC-08）、認証方式（NFR-SC-12）、特権の管理（NFR-SC-15）、セッション識別子の再発行・破棄（NFR-SC-19）、1段階認証（NFR-SC-13）、ゲスト購入の不可（FR-OUT-10）、アカウントロックを設けないこと（FR-OUT-11、NFR-SC-14）を確認した。 |
| database | 適用 | PASS | 使い捨てテストDB（pytest-django が作成・破棄する test_<DB_NAME>）に対し、永続化内容・一意制約・在庫引当のトランザクション・行ロックによる同時実行制御・初期データ投入の全件ロールバックを確認した。あわせて同時会員登録（AC-UC-001-017）・同時カート明細追加（AC-UC-004-025）の直列化と、定義ファイル経由の攻撃文字列が SQL として実行されないこと（NFR-SC-04、VUL-04）を確認した。さらに C10 是正として、実行基盤の版（NFR-EN-01・NFR-EN-02）、タイムゾーン・文字コード（NFR-EN-04）、JIS 第3・第4水準の漢字の保存・表示（NFR-US-03）、利用者状態のDB保持（NFR-PF-16）、監査ログと注文状態履歴の記録・追記のみ（NFR-SC-22・NFR-SC-23）、初期データの移行対象（NFR-MG-01）、投入失敗時の全件取消しと再実行（NFR-OM-13・NFR-MG-07）、在庫5への10並列注文確定（NFR-PF-07、NFR-LG-06）を確認した。 |
| end-to-end-flow | 適用 | PASS | 会員登録→ログイン→検索→カート→クーポン→注文確定→支払→出荷→配達完了の業務フロー、キャンセル後の在庫復元と再購入、否認後の再支払までを複数FR跨ぎで確認した。さらに C10 是正として、外部ネットワークを遮断した状態での全機能の操作（NFR-EN-05、NFR-LG-10）、模擬決済だけで支払が完結すること（FR-OUT-01）、一連の操作で通知を送信しないこと（FR-OUT-08）を確認した。 |
| error-handling | 適用 | PASS | 入力エラー・業務エラー・対象なし・認証/権限エラー・決済サービスの応答不正と締切超過・共通エラー構造と判定順序（CMN-14、CMN-16、MSG-04）を連携経路全体で確認した。あわせて Web API・画面フォームの全入力項目へ SQL・OSコマンドの攻撃文字列を送り、入力エラーまたは通常処理となりデータ変更が0件であること（NFR-SC-04、VUL-04）を確認した。さらに C10 是正として、内部情報の非表示（NFR-SC-10）、ログ出力形式（NFR-OM-11）、入力エラーの表示（NFR-US-04）、都道府県コードの値域（NFR-LG-09）を確認した。 |
| state-transition | 適用 | PASS | 注文の状態遷移（ST-PO-01〜ST-PO-06）とカートの状態遷移（ST-CART-01、ST-CART-02）について、許可された遷移と不正遷移（INVALID_STATUS_TRANSITION）、履歴記録・在庫戻しを確認した。あわせて同時支払・支払とキャンセル・同時キャンセル・同時出荷登録・管理者キャンセルとの競合（AC-UC-007-013、AC-UC-007-019、AC-UC-009-007、AC-UC-011-020、AC-UC-012-009〜011）を確認した。さらに C10 是正として、返品・返金・部分出荷の状態と操作を持たないこと（FR-OUT-04）、未払い注文が自動キャンセルされないこと（FR-OUT-12）を確認した。 |

## 8. 再実行（Regression）

- 対象 Case の再実行: NOT_REQUIRED（今回のサイクルで Failed / Error Case は0件）
- 関連 Case の再実行: PASS（既存134ケースを含む結合試験全ケースを再実行）
- Integration Test Suite 全体の再実行: PASS（単体791件＋結合138件＝929 passed / 0 failed）

## 9. 未解決事項

- 未解決 Error: 0 件
- 未解決 Defect: 0 件
- 解消済み Defect: 1 件（DEF-IT-001: ADDR（ADDR-013 採択）→ IMPLEMENTATION（app/shop/services/orders.py 是正））
- TEST_SPEC_CONFLICT: 0 件
- AUTOMATION_BLOCKED: 0 件

## 10. 修正・再検査サイクル 5 の対応

| 指摘 | 分類 | 追加・是正した内容 | 結果 |
| --- | --- | --- | --- |
| SR-IT-001 | SECURITY_TEST_GAP | Required Coverage の導出元へ非機能要件（NFR-SC-04・NFR-SC-05 の検証方法、8.2 VUL-04〜06、12.2 VDC-06）を追加し、ICOV-071〜ICOV-078 を定義。tests/integration/test_security.py（6ケース）と tests/integration/test_seeding_command.py（2ケース）で (a) CSRF対策用トークン欠落時の拒否、(b) 画面出力のHTMLエスケープ、(c) SQL・OSコマンド攻撃文字列の投入、(d) 全削除後の旧トークン・旧セッションの拒否を検証。 | 全8ケース PASS |
| QR-IT-001 | MISSING_BEHAVIOR_COVERAGE | Required Coverage の導出元へ UC の同時実行受入基準を追加し、ICOV-079〜ICOV-087 を定義。tests/integration/test_concurrency.py に AC-UC-001-017 / AC-UC-004-025 / AC-UC-007-013 / AC-UC-007-019 / AC-UC-009-007 / AC-UC-011-020 / AC-UC-012-009 / AC-UC-012-010 / AC-UC-012-011 の9ケース（各10試行）を追加。 | 9ケース中8ケースが初回 PASS。IT-AI-GF-023（AC-UC-007-019）で DEF-IT-001 を検出し ADR_REQUIRED として返却。ADDR-013 採択と実装是正の後に再実行し、9ケース全件 PASS。 |
| QR-IT-003 | INTEGRATION_TEST_QUALITY_ISSUE | 指摘本文を参照できなかったため（reports/quality-review/quality-review-report.json は ADDR Scope 再Review（QR-ADDR-20261022-003）で上書きされ、QR-IT-20261022-001 の本文が現存しない。reports/loop-control・reports/experiments 内にも保存されていない）、自己点検として結合試験コードの静的解析（ruff E,F,W,I,UP,B,C4）と Traceability 注釈（C05・C06）を実施して検出した指摘を是正した。 | PARTIAL（指摘本文が入手不能。解消の確認は INTEGRATION_TEST Scope の Quality Review 再実行が必要） |
| DEF-IT-001 | ADR_REQUIRED | ADDR-013（ACTIVE）を採択し、支払では注文行のロックを手順5の状態判定の前に取得して、状態判定→決済要求送信→結果反映を同一トランザクション・同一ロック区間で確定する方式へ決定した（ADDR-009 DD-005・INV-006、ADDR-001 DD-007・INV-004 を更新し、ロック保持中の禁止対象を外部ネットワーク通信・スリープ・他プロセス待ちに限定）。Implementation 工程が ADDR-013 に従って app/shop/services/orders.py の pay_order を是正し、ロック取得後に CREATED 以外であれば決済ゲートウェイを呼び出さずに InvalidStatusTransitionError を送出する実装とした（_authorize_locked_order を新設、否認・連携エラーは決済記録を同一トランザクションで登録しコミット後に例外送出、_record_payment の独立トランザクションを廃止）。Integration Test Agent は Production Code・ADDR・要件を変更していない。 | 解消。Production Code 変更後に全ケースを再実行して確認した。IT-AI-GF-023（AC-UC-007-019、各10試行）を単独で3回再実行し3回とも PASS。関連ケース（tests/integration/test_concurrency.py 10件、test_orders_api.py・test_e2e_flow.py・test_admin_api.py 計29件）PASS。結合試験 82ケース全件 PASS（junit.xml 再生成）。全体（単体742件＋結合82件）は docker compose exec -T app pytest で 824 passed / 0 failed。 |
| TA-C10-001 | TEST_TRACEABILITY_MISSING | Traceability Audit（FULL Scope）の C10 で不合格となった 124 件の要件について、要件本文を正本として 「自動テストで正当に検証できるもの」と「検証方法が自動テストではないもの」を分類した。検証できる 41 観点（対象外機能 FR-OUT-01〜16 が実装されていないことの確認、および設定値・形式・件数・記録・同時実行整合に関する非機能要件）を Required Coverage へ追加（ICOV-088〜ICOV-128）し、AI GAP_FILL Case IT-AI-GF-029〜069 として tests/integration/test_out_of_scope.py・test_security_contract.py・test_platform_contract.py・test_concurrency.py に実装した。自動テストで検証できない要件は reports/integration-test/non-automatable-requirements.json / .md へ 要件IDごとの検証方法・対象外理由とともに記録した。AI INITIAL Case 54件と初回測定値は変更していない。 | 41ケースすべて初回 PASS。結合試験 123ケース全件 PASS（単体747件と合わせて 870 passed / 0 failed） |
| TA-C10-001 | TEST_TRACEABILITY_MISSING | 修正1回目で「自動テスト対象外」と分類した 74 件を、要件本文の「検証方法」欄を正本として1件ずつ再精査した。区分名ではなく「結合試験環境（app サービスのコンテナ）の中に解析・判定の対象が存在するか」「形骸的（常に真・実質無検証・ファイル存在確認のみ）でない検証ができるか」で判定し、11 件を自動検証へ移した。内訳は静的解析6件（NFR-OM-07・NFR-EN-11・NFR-EN-12・NFR-PF-17・NFR-SC-07・NFR-EN-09）、構成・設定レビュー2件（NFR-EN-08・NFR-LG-03）、該当なし2件（NFR-AV-10・NFR-PF-12）、性能テスト1件（NFR-PF-11 の不変条件のみ）。Required Coverage へ ICOV-129〜ICOV-139 を追加し、AI GAP_FILL Case IT-AI-GF-070〜080 として tests/integration/test_quality_contract.py・test_resilience_contract.py に実装した。負荷の測定値そのもの、本番環境でのみ測定できる指標、ブラウザ操作・移行リハーサル・脆弱性診断を要する要件は追加していない。AI INITIAL Case 54件と初回測定値（initial-coverage-metrics.json）は変更していない。 | 11ケースすべて初回 PASS（1件は WhiteNoise のハッシュ付き静的ファイル名に対する照合誤り、1件は管理コマンドの終了方法の想定誤りを TEST_ERROR として Test Code 側で是正。いずれも期待結果を Production Code に合わせて変更していない）。結合試験 134ケース全件 PASS（単体747件と合わせて 881 passed / 0 failed） |
| TA-C10-001 | TEST_TRACEABILITY_MISSING | 修正2回目の後に残った C10 不合格 63 件を、要件本文の「検証方法」欄を正本として1件ずつ最終精査した。結合試験環境の中に判定対象が存在し、形骸的でない判定ができる 4 件（NFR-SC-25 検証データが架空の値のみ・NFR-OM-17 環境変数だけでの設定切替・NFR-EN-07 ホスト OS 非依存・NFR-EN-03 app/db 2サービスと本番基盤非依存）を Required Coverage（ICOV-140〜ICOV-143）へ追加し、AI GAP_FILL Case IT-AI-GF-081〜084 として tests/integration/test_operations_contract.py に実装した。運用時に測定・性能/負荷テスト・移行リハーサル・脆弱性診断・互換性/操作性テスト・本番環境の構成レビュー・該当なしに属する 59 件は、件数削減のための形骸的なテストを作らない方針に従い追加していない（reports/integration-test/non-automatable-requirements.md 最終版へ理由と人が実施すべき検証を記録）。AI INITIAL Case 54件（sha256 94f1d86…）と初回測定値は変更していない。 | 4ケースすべて PASS（開発中に 2 件の TEST_ERROR（テストDB名の照合誤り、設定ソース内の真偽値表記との照合誤り）をTest Code 側で是正。期待結果を Production Code に合わせて変更していない）。結合試験 138ケース全件 PASS（単体791件と合わせて 929 passed / 0 failed） |

### 10.1 残課題

- QR-IT-003（LOW / INTEGRATION_TEST_QUALITY_ISSUE）の指摘本文が入手できない：reports/quality-review/quality-review-report.json は ADDR Scope（QR-ADDR-20261022-003）で上書きされており、QR-IT-003 は observations の列挙でのみ言及されている。今回の再実行時点でも本文は復元できていない。自己点検として (1) プロジェクト標準の静的解析 `ruff check .`（pyproject.toml: line-length=120、select=E,F,W,I,UP,B,C4、exclude に ./tests を含む＝ADDR-004・ADDR-012 の決定により結合試験コードは解析対象外）を実行し All checks passed、(2) 参考として tests/integration を明示指定して同一ルールで解析し、tests/integration/test_admin_api.py の2行に E501（122>120、121>120）を検出（行長のみ。設計上の解析対象外であり、意味・アサーションには影響しない）、(3) Traceability 注釈（C05・C06）の充足、を確認した。SDLC Orchestrator が INTEGRATION_TEST Scope の Quality Review を再実行し、QR-IT-003 の残存可否と E501 2件の扱い（ADDR-004 の解析対象外方針を維持するか是正するか）を判定する必要がある。（推奨対応先: QUALITY_REVIEW）
- OBS-IT-001（全角数字の都道府県コード・郵便番号が受理される）の扱いが未決：FR-030 の入力条件は半角数字を定めるが、実機では全角数字が受理され保存される。Integration Test Agent はProduction Code を変更できず、また本サイクルの差し戻し範囲外であるため、Test Case の期待結果には含めていない（したがって Failure としては計上していない）。SDLC Orchestrator が是正の要否を判定し、是正する場合は Implementation 工程での修正後に結合試験ケースを追加して再実行する必要がある。（推奨対応先: IMPLEMENTATION）

## 11. Traceability C10 の最終精査結果と未解決事項の持越し

| 項目 | 内容 |
| --- | --- |
| 精査対象 | 修正2回目の後に残った C10 不合格 63 件すべて |
| 追加したケース | 4 件（IT-AI-GF-081〜084。NFR-SC-25・NFR-OM-17・NFR-EN-07・NFR-EN-03） |
| 追加しなかった要件 | 59 件（運用時に測定22／互換性・操作性9／性能・負荷8／移行リハーサル5／脆弱性診断4／構成・設定レビュー4／運用テスト3／該当なし4）。検証方法が本質的に自動テストの対象外であり、件数削減のための形骸的なテストは作らない方針に従った |
| C10 残存見込み | 59 件（本工程の修正では解消できない） |
| 未解決の扱い | 共通3回ループの規定により UNRESOLVED として記録し、4回目の修正ループは行わない。工程継続の判定は SDLC Orchestrator が行う |
| 申し送り | `reports/integration-test/non-automatable-requirements.md` 5章（本番稼働前に人が実施すべき検証）を受入試験・運用準備へ引き継ぐ |

結合試験そのものは全 138 ケース PASS・未解決 Defect 0 件であり、C10 の残存は試験の失敗・未実行ではない。
