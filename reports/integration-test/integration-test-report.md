# 結合試験 Report（RUN-AOBA-EC-1118）

- 状態: **IMPLEMENTATION_FIX_REQUIRED**（品質 PASS ではない。FAIL 1件を FAIL のまま記録：IT-058（IMPLEMENTATION_ERROR、既知 UNRESOLVED-6de5eec64599b907））
- 正式実行: it-exec-7（2026-11-19T19:01:54.818822+00:00、812.806 秒）、JUnit reports/integration-test/junit.xml、trace 実行記録 WORKTREE:0df85adc06740c92644e74920eefaa59caf67b586c379665c2ab6e87f58fb58b
- External Case: 未提供（external-tests/ なし）。ユーザーの明示選択（external_cases_confirmed_absent: true）により外部取り込みなしで実施

## 1. Test Summary

| 区分 | 件数 | PASS | FAIL | BLOCKED |
|---|---|---|---|---|
| AI_GENERATED / INITIAL | 61 | 60 | 1 | 0 |
| AI_GENERATED / GAP_FILL | 73 | 73 | 0 | 0 |
| EXTERNAL | 0 | 0 | 0 | 0 |
| TOTAL | 134 | 133 | 1 | 0 |

## 2. Coverage 比較（Required Coverage 163件＝Revision 1 の 104件＋Revision 2〜4 の 59件、Gap Fill 前の値）

- COMMON 0 / AI_ONLY 94 / EXTERNAL_ONLY 0 / MISSING 69
- AI INITIAL Coverage Rate 57.67%、External Coverage Rate なし（未提供）、Combined Initial 57.67%、Gap Fill 後 Final 100.0%
- Revision 1（104件）の固定値（initial-coverage-metrics.json、変更なし）: AI INITIAL 90.38%、MISSING 10。この値には INITIAL の過大宣言分（RC-036・038・039・063・084・085・091）が含まれる

## 3. Coverage Gap（MISSING → AI GAP_FILL）

| Gap | Coverage | Requirement | 不足内容 | GAP_FILL |
|---|---|---|---|---|
| GAP-001 | RC-014 | FR-001 | 画面の会員登録の入力エラーは項目ごとに理由を表示し、入力値を保持（パスワードは保持しない）（CMN-17、UI-19、AC-UC-001-018） | GF-001 |
| GAP-002 | RC-018 | FR-002 | 画面ログイン失敗は SCR-004 に区別しないメッセージ、メールアドレスを保持しパスワードは保持しない（AC-UC-002-017） | GF-001 |
| GAP-003 | RC-023 | FR-002 | 同じ送信トークンのログイン再送は照合・監査ログ記録・新たなログイン状態の開始を行わず、先着の結果を通知する（ADDR-004 DD-013/016、CMN-22） | GF-002 |
| GAP-004 | RC-044 | FR-021 | 同じ送信トークンの「カートに入れる」再送は数量を加算しない（ADDR-004 DD-013、UI-15） | GF-003 |
| GAP-005 | RC-054 | FR-030 | 画面の配送先不備は項目ごとの理由を表示し入力値を保持して再表示する（AC-UC-006-028） | GF-004 |
| GAP-006 | RC-072 | FR-034 | 画面（SCR-010）のキャンセルで完了メッセージを表示し、在庫が戻る（AC-UC-009-003） | GF-005 |
| GAP-007 | RC-074 | FR-040 | 未登録の仕入先・低在庫のみの値不正・ページ不正は 400 input_error で全項目（AC-UC-010-009） | GF-006 |
| GAP-008 | RC-077 | FR-041 | 注文日（開始）＞注文日（終了）、日付形式不正、注文番号形式不正は 400 input_error（AC-UC-011-005） | GF-007 |
| GAP-009 | RC-080 | FR-043 | 配送伝票番号は30文字まで受け付け、31文字・不正な文字は 400 input_error（AC-UC-011-013） | GF-008 |
| GAP-010 | RC-096 | FR-060 | 提供済みの定義ファイル（app/seed/initial_data.json）を投入でき、データ別件数が定義ファイルと一致する（Steering 4章、FR-060） | GF-009 |
| GAP-011 | RC-105 | FR-045, FR-031 | 管理者キャンセルと購入者の支払（承認）の同時実行で、(a) キャンセル先着：支払は invalid_status（キャンセル済）、決済記録0件・支払日時なし・履歴2件（2件目 注文受付→キャンセル済、実行者 管理者）、(b) 支払先着：承認1件不変・支払日時あり・履歴3件（注文受付→支払済 購入者、支払済→キャンセル済 管理者）、いずれも最終キャンセル済・在庫+2。10試行（AC-UC-012-011、ADDR-004 DD-006） | GF-012 |
| GAP-012 | RC-106 | FR-012, FR-021, FR-002 | 来訪者が SCR-002 で「カートに入れる」を操作すると SCR-004（ログインが必要）へ遷移し、ログイン後に SCR-002（商品詳細）へ戻る。未ログイン時の追加は自動実行されず、カート・カート明細の件数・在庫は不変、カート（0点）（AC-UC-003-018、AC-UC-004-024） | GF-013 |
| GAP-013 | RC-107 | NFR-OM-18, NFR-OM-11, FR-031 | 支払要求1件の X-Request-ID で LOG-01・LOG-03・LOG-06（request/response：order_number・amount・currency=JPY・result・transaction_ref・duration_ms）を、連携エラー時は LOG-02 も漏れなく抽出でき、機密項目を含まない（NFR-OM-18 測定条件、ADDR-013 DC-002・検証方法、ADDR-008 DD-008） | GF-014 |
| GAP-014 | RC-108 | FR-031, NFR-SC-24, NFR-EN-05 | 決済サービス（模擬）が受けた決済要求は1件で、注文番号・決済金額（注文合計）・通貨 JPY・模擬決済指示の4項目だけ（個人情報なし）、支払処理中の外部ネットワーク宛て通信0件、送信から応答受信まで1秒以内（AC-UC-007-016、ADDR-008 DD-004/005） | GF-015 |
| GAP-015 | RC-109 | FR-030, NFR-PF-07, NFR-LG-06 | 在庫数量5の同一在庫単位を1個ずつカートに入れた10名の同時確定を10回繰り返し、各回 成功5・在庫不足5・在庫0以上・引当合計5以下、成功した注文番号は重複せずコミットの順に増加する（NFR-PF-07 測定条件、ADDR-005 4.3・検証方法） | GF-016 |
| GAP-016 | RC-110 | FR-030 | 注文番号の払い出し後の障害で取り消された番号は再使用されず欠番となり、次の注文番号はそれより大きい（ADDR-005 DD-003、AC-UC-006-022） | GF-017 |
| GAP-017 | RC-111 | FR-060 | --reset 指定の投入後も注文番号・各識別子（利用者・カート・注文・在庫単位等）を巻き戻さず再利用しない。削除前の画面のログイン状態も無効（ADDR-005 DD-003、ADDR-006 DD-002、ADDR-002 4.3 の6、AC-UC-013-004） | GF-018 |
| GAP-018 | RC-112 | NFR-PF-01, NFR-PF-02, NFR-PF-09 | 照会系・更新系・認証系 API の種別ごとの応答時間の95パーセンタイルが 1.0秒／2.0秒／2.0秒以内で、システムエラー・業務エラー0件（結合試験の条件：単一利用者・小データ量での参考計測。ピーク負荷・3年後データ量の判定は性能試験） | GF-022 |
| GAP-019 | RC-113 | NFR-PF-08 | 分割表示の一覧（商品一覧・注文履歴・在庫単位一覧・注文一覧（管理））は先頭ページ・最終ページとも1回の応答が50件以下、商品分類一覧は分割しない | GF-023 |
| GAP-020 | RC-114 | NFR-PF-10, NFR-MG-01, NFR-MG-02, NFR-MG-03, NFR-MG-04, NFR-MG-08, NFR-OM-04 | VDC-04 相当（管理者7・仕入先20・商品分類30・商品300・在庫単位800、計1,157件）の定義ファイルを注文作成後の環境へ --reset で1回の実行で投入し、60秒以内、件数照合・業務キーの内容照合で不一致0、管理者7名がログイン可、注文・カート・決済記録・注文状態履歴0件、実行前の監査ログが残り1件増加。定義ファイルに注文等のデータを含める指定は受け付けない | GF-024 |
| GAP-021 | RC-115 | NFR-OM-13, NFR-MG-07 | 違反1件を含む定義ファイルは投入件数0（--reset でも既存データを削除しない）・監査ログに失敗1件、修正版を同じ指定で再実行すると件数が定義と一致し重複しない、再々実行しても重複しない、切戻し（失敗後の再実行）が1時間以内 | GF-025 |
| GAP-022 | RC-116 | NFR-OM-11 | 全機能の実行で LOG-01〜LOG-07 が定めた内容で出力・記録される（LOG-01〜03・05・06 は JSON 行、LOG-04 は監査ログ、LOG-07 は注文状態履歴）。保管期間は対象外 | GF-026 |
| GAP-023 | RC-117 | NFR-OM-17 | 環境ごとに異なる設定値（接続先・許可ホスト・環境プロファイル・開発用機能）を環境変数だけで変更でき、本番プロファイルでは開発用機能・デバッグを有効にできない。設定の記入例（.env.example）に秘密情報の値を含まない | GF-027 |
| GAP-024 | RC-118 | NFR-SC-12 | 購入者・管理者はメールアドレス＋パスワードで認証でき、誤ったメールアドレス・誤ったパスワードは区別しない同一応答、来訪者は認証なしで商品を閲覧できる | GF-028 |
| GAP-025 | RC-119 | NFR-US-03 | 氏名・配送先に JIS 第3・第4水準の漢字を入力して登録し、画面・API で同じ文字が表示される。画面は日本語（lang=ja）・UTF-8 | GF-029 |
| GAP-026 | RC-120 | NFR-US-04 | 会員登録・注文手続きの画面で複数項目を誤って送信すると、誤りのある全項目分の理由を項目を識別できる形で1回で表示し、入力値を保持（パスワード除く） | GF-030 |
| GAP-027 | RC-121 | NFR-US-05, NFR-US-07, NFR-LG-08 | 全画面の HTML が適合レベル A の機械判定可能な達成基準（言語・ページタイトル・フォーム部品のラベル・表見出し・キーボード操作可能なネイティブ部品・正の tabindex なし）を満たす（チェックリストによる目視・ブラウザ操作の確認は対象外） | GF-031 |
| GAP-028 | RC-122 | NFR-US-08 | ログイン済みの購入者が商品一覧から支払完了までを画面のリンク・フォームだけで操作し、経由する画面は7画面以内 | GF-032 |
| GAP-029 | RC-123 | NFR-US-09 | 取消できない5操作（注文確定・注文キャンセル・出荷登録・配達完了登録・カート明細の削除）のフォームに確認文言があり、確認を求める画面の補助が読み込まれる（ブラウザの確認ダイアログの操作は対象外） | GF-033 |
| GAP-030 | RC-124 | NFR-US-10 | 注文確定・支払（承認）を処理完了前に繰り返しても注文・決済記録は1件、否認の後の支払は新たな支払として扱う | GF-034, GF-039, GF-041 |
| GAP-031 | RC-125 | NFR-EN-01, NFR-EN-02, NFR-EN-09 | 実行環境が Python 3.12・Django 5.2・Django REST Framework 3.15 以上で、接続先が PostgreSQL 16。画面は Django テンプレートで、SPA・フロントエンドのビルド工程を持たない | GF-035 |
| GAP-032 | RC-126 | NFR-LG-02 | 商品価格は税込価格を主に表示し税抜価格を併記、カート・注文手続き・注文完了・注文詳細に消費税額と税込の合計を表示する | GF-036 |
| GAP-033 | RC-127 | NFR-LG-09 | 配送先の都道府県は JIS X 0401 の47コード（01〜47）だけを受け付け、それ以外は入力エラー。画面の選択肢は47件で、名称で表示する | GF-037 |
| GAP-034 | RC-128 | NFR-PF-17 | 決済連携部分（ゲートウェイの実装）だけを別実装に差し替えても、注文・在庫・金額・状態遷移の処理が変更なしで支払が完了する | GF-038 |
| GAP-035 | RC-129 | NFR-US-10, FR-031 | 支払（承認・否認）の処理中（決済応答待ち）に同じ送信トークンの「支払う」を別接続から繰り返すと、後着は送信トークンのロックで先着の終了まで待ち、決済要求は1回分だけ送信される。承認では後着は再判定どおり E-031-05、否認では後着は先着の結果（E-031-06）を通知し、決済記録は1件（NFR-US-10、BR-UC-007-014、ADDR-004 DD-002・DD-010・DD-013、4.4 検証方法） | GF-039 |
| GAP-036 | RC-130 | NFR-US-10, FR-031 | 先着が承認の反映途中の障害（E-031-08）で終わる間、および先着が結果の記録前に中断した場合の繰り返し「支払う」でも決済要求は1回だけ送信し、後着は E-031-08 を通知する。決済記録・注文状態は変化せず、その後に新たに表示した支払画面からの操作は新たな支払（ADDR-004 DD-013・DD-015、4.3 の11、4.4 検証方法） | GF-040 |
| GAP-037 | RC-131 | NFR-US-10, FR-030 | 注文確定の処理中に同じ送信トークンの「注文を確定する」を別接続から繰り返すと、注文は1件・在庫の減算は1回分で、後着はカートが空（E-030-04）としてカート画面へ遷移する（AC-UC-006-021・AC-UC-006-026、BR-UC-006-012、ADDR-004 DD-010・DD-013） | GF-041 |
| GAP-038 | RC-132 | NFR-US-10, FR-021 | 「カートに入れる」の処理中に同じ送信トークンで別接続から繰り返しても数量は1回分だけ加算され、後着は先着の結果（成功）を通知する（NFR-US-10、ADDR-004 DD-013、4.4 検証方法） | GF-042 |
| GAP-039 | RC-133 | NFR-US-10, FR-002 | 先着が E-002-02 で終わる間の繰り返し「ログイン」で、ログイン失敗の監査ログは1件、後着は照合せず先着の結果（E-002-02）を通知しログイン状態を作らない。送信トークンの記録に入力値を残さない（ADDR-004 DD-013・DD-016、4.4 検証方法） | GF-043 |
| GAP-040 | RC-134 | NFR-PF-12, NFR-AV-01 | 定期的に実行するバッチ処理・定期ジョブの定義を持たない（NFR-PF-12「該当なし」の根拠の前提）。起動定義（compose のサービスは app・db のみ、app の起動は移行適用・静的ファイル収集・Gunicorn だけ、Dockerfile に定期実行の仕組みなし）、依存に定期実行のライブラリなし、管理コマンドは手動実行の初期データ一括投入・試験用状態と無効化した Django 付属の2件だけ。NFR-AV-01 の代替確認（計画停止以外にサービス停止を要する定期処理が無い）のうちリポジトリ内の起動定義の範囲 | GF-044 |
| GAP-041 | RC-135 | NFR-SC-28 | 画面・API にファイルをアップロードする機能が無い（NFR-SC-28「該当なし」の根拠の前提）。ファイルを保存する項目を持つデータが無く、画面にファイル選択部品・multipart のフォームが無く、業務処理がアップロードされたファイルを参照せず、Web API は JSON の本文だけを解釈し、ファイルを伴う multipart の要求は 400 input_error でデータを変更しない（ADDR-001 4.3 の7） | GF-045 |
| GAP-042 | RC-136 | NFR-SC-13, NFR-SC-14 | 購入者はメールアドレス＋パスワードだけで1回の要求でログインが完了し追加の認証要素を求めない（NFR-SC-13「該当なし」の前提）。誤ったパスワードでの失敗を API・画面で各10回続けた後も正しいパスワードでログインでき（アカウントロック・試行回数制限なし：NFR-SC-14「該当なし」の前提）、失敗は監査ログに1回につき1件、対象利用者付きで記録される（NFR-SC-14 の根拠） | GF-046 |
| GAP-043 | RC-137 | NFR-SC-13, NFR-SC-17, NFR-LG-04 | 画面・API に多要素認証・パスワードの変更／再設定・特定商取引法に基づく表記の要求先が無く（該当しそうな要求は 404）、Django 付属の changepassword は何も変更せずにエラー終了し、画面に特定商取引法の表記が無い（NFR-SC-13・NFR-SC-17（FR-OUT-09）・NFR-LG-04（FR-OUT-16）の「該当なし」・対象外の前提） | GF-047 |
| GAP-044 | RC-138 | NFR-SC-27 | 同一の送信元からの短時間の連続要求（商品一覧 API・商品一覧画面・ログイン API）を送信元単位で制限しない（429 を返さない。NFR-SC-27「該当なし」の根拠の前提） | GF-048 |
| GAP-045 | RC-139 | NFR-AV-10, NFR-LG-10 | 決済サービスは本システム内の模擬機能だけで（使用する実装はプログラム内の既定で模擬機能）、決済の部品に外部通信のモジュールを使わず、実在の決済サービスの接続先・認証情報の設定項目・連携ライブラリを持たない（NFR-AV-10・NFR-LG-10 の「該当なし」の根拠の前提。外部通信0件は RC-108） | GF-049 |
| GAP-046 | RC-140 | NFR-EN-03, NFR-OM-05, NFR-EN-08 | Docker Compose の定義で全構成要素（アプリケーション・データベース）を1回の起動操作で起動する（app は db の正常性確認後に、移行適用→静的ファイル収集→Gunicorn を1つの起動コマンドで行う）。起動定義は本番運用向けの AP サーバー（Gunicorn）で Django 付属の開発用サーバーを含まず、Gunicorn の設定が指す WSGI アプリケーションが商品一覧画面を返す。依存に特定のクラウド基盤の SDK を含まない（compose での実際の起動・本番環境の構成は対象外） | GF-050 |
| GAP-047 | RC-141 | NFR-EN-07 | Production Code が特定の OS に固有のモジュールを読み込まず、OS 固有の絶対パスを書かない。OS はコンテナのベースイメージ（python:3.12-slim、ダイジェスト固定）だけで決まる | GF-051 |
| GAP-048 | RC-142 | NFR-SC-21, NFR-EN-10 | 依存ライブラリ・実行環境の取得元と版が特定でき同じ構成を再現できる（VUL-10、NFR-SC-21 の対策方針の一部）：依存は全件が版固定とハッシュ付き、イメージ構築は --require-hashes、ベースイメージ・DB イメージはダイジェスト固定、試験環境の版が固定した版と一致し、依存の一覧の版と一致する。採用製品の版が NFR-EN-10 のサポート期限の前提の版（Django 5.2 LTS 2028-04、Python 3.12 2028-10、PostgreSQL 16 2028-11）である（更新計画は対象外） | GF-052 |
| GAP-049 | RC-143 | NFR-EN-12 | 固定した全依存ライブラリのライセンスがパッケージのメタデータから特定でき（ライセンス不明 0件）、AGPL のものが無い（利用条件の充足の判断は対象外） | GF-053 |
| GAP-050 | RC-144 | NFR-EN-11 | リポジトリの規約設定（ruff.toml。pycodestyle の E・W を含む）で全ソースコードを静的解析し違反0件（規則の選択が PEP 8 に一致するかは対象外） | GF-054 |
| GAP-051 | RC-145 | NFR-PF-16 | 処理能力の増強（実行単位内のプロセス数）を環境変数だけで変更でき、画面のログイン状態・Web API のログイン状態・カートの内容がデータベースに保持され、別のプロセスから同じ Cookie・Bearer でログイン中のカートを参照できる（増強手順のレビュー・2倍の負荷は対象外） | GF-055 |
| GAP-052 | RC-146 | NFR-SC-25 | リポジトリの初期データ（検証用の定義ファイル）の利用者のメールアドレスは全件 example.com（VDC-01 の作成方法）で、それ以外のドメインを含まず、試験用の利用者は予約済みドメイン（example.test）で作る | GF-056 |
| GAP-053 | RC-147 | NFR-OM-19 | 開発・検証環境向けの手順書に、環境ごとの設定（秘密情報を含む）の作成・構築・起動・停止・データベースの初期化・初期データ一括投入・自動テスト・静的解析の手順があり、手順が参照するファイル・サービス・コマンドが存在し、初期データ一括投入の手順（seed/initial_data.json、--reset）が成功する（本番運用手順書・compose での構築・起動の実施は対象外） | GF-057 |
| GAP-054 | RC-148 | NFR-LG-03 | 注文明細・配送先・決済記録・注文状態履歴は登録後に変更・削除されず（決済記録・履歴は追記のみ）、注文の登録後の更新は注文状態の遷移（支払・出荷登録・配達完了登録・キャンセル）に伴う注文状態・日時・配送伝票番号だけ（NFR-LG-03 の対応方針の一部。7年保存・削除手順は対象外） | GF-058 |
| GAP-055 | RC-149 | NFR-US-01, NFR-US-02, NFR-US-06 | Windows 11 の PC にインストールした Microsoft Edge・Google Chrome で、表示領域 1280×720・表示倍率 100% のとき、全画面（SCR-001〜SCR-010、SCR-101〜SCR-103、SCR-901）が想定の状態コードで表示され、資源の読込失敗・スクリプトの例外・外部への要求が無く、横スクロール（表示領域の幅を超える内容・要素）が無い。来訪者・購入者・管理者の代表操作（会員登録・ログイン・カートに入れる・クーポン適用・注文確定・支払・キャンセル・出荷登録・配達完了登録・ログアウト）をブラウザのフォーム送信と確認ダイアログで行える（ヘッドレス表示。目視の表示崩れ・全操作の網羅・最新版であることは対象外） | GF-059 |
| GAP-056 | RC-150 | NFR-PF-03 | 全画面（14画面）を各ブラウザで30回以上表示し、画面要求の送信から構成に必要な全資源の読込完了（load イベント終了）までの時間の95パーセンタイルを画面ごとに記録し、単一利用者・小データ量でも 2.0秒以内（ピーク負荷・3年後データ量・ENV-01 の判定は対象外） | GF-060 |
| GAP-057 | RC-151 | NFR-PF-06 | 3年後相当のデータ量（VDC-01〜VDC-03 の件数：注文 110,000・注文明細 330,000・会員 10,000・商品 600・在庫単位 1,600 等）の DB で、照会系・更新系 API と画面の応答時間の95パーセンタイルを記録し、単一利用者でも目標値（照会 1.0秒・更新 2.0秒・画面 2.0秒）以内（ピーク負荷・ENV-01 の判定は対象外） | GF-061 |
| GAP-058 | RC-152 | NFR-PF-05, NFR-PF-04, NFR-PF-14, NFR-PF-15, NFR-PF-03 | 同時155の仮想利用者（購入者・来訪者 150、管理者 5、思考時間 5〜15秒、照会：更新＝8：2＋認証系、業務エラーにならない条件）の負荷で、システムエラー0件・要求の全件成功・照会/更新/認証の95パーセンタイルが目標値以内、注文確定の到着 4件/分（異なる購入者、3明細・5点）の全件成功、負荷中のブラウザ表示の95パーセンタイル 2.0秒以内を確認し、アプリケーション・DB の CPU・メモリ使用量と応答時間の推移を記録する（60分・2時間の連続負荷・3年後データ量・ENV-01 の判定は対象外） | GF-062 |
| GAP-059 | RC-153 | NFR-PF-11 | 想定の2倍（310）の仮想利用者で在庫不足が起きる負荷をかけた後、システムエラーとなる応答の割合が 1%以下、在庫数量が0未満の在庫単位 0件、金額整合を満たさない注文 0件、在庫の増減と注文明細（キャンセル以外）が一致（10分間・3年後データ量は対象外） | GF-063 |
| GAP-060 | RC-154 | NFR-SC-11 | 固定した全依存ライブラリ（app/requirements.txt・requirements-dev.txt）を開発時に公開脆弱性情報（OSV）と照合し、照合対象が固定した版と一致し、CVSS 7.0以上（または重大度 HIGH/CRITICAL）・重大度不明の既知の脆弱性が0件（リリース前の再照合・コンテナイメージの OS パッケージは対象外） | GF-064 |
| GAP-061 | RC-155 | NFR-LG-01 | 利用者の個人情報（メールアドレス・氏名・配送先）を扱う一連の操作（会員登録・ログイン・注文確定・支払・照会・管理者の検索）で、ログに個人情報・パスワードを出力せず、ファイルとして出力する要求先・応答が無く、外部へ送信しない。注文の参照は本人と管理者に限られる（利用目的の表示・通信の暗号化・法令適合の判断は対象外） | GF-065 |
| GAP-062 | RC-156 | NFR-SC-29, NFR-LG-07 | 全画面・全 API に対し、利用者区分ごとのアクセス制御（VUL-01）、CSRF トークンなしの更新要求と参照用の要求での更新（VUL-06）、検索条件・パス・本文への攻撃文字列（VUL-04・VUL-05・VUL-13）を送り、システムエラー・無害化されない反映・内部情報の露出・セキュリティヘッダーの欠落が無く、外部へ要求を送る部品が無い（VUL-12）（診断ツールによる診断・指摘の対処は対象外） | GF-066 |
| GAP-063 | RC-157 | NFR-SC-20 | 保存データの所在がデータベースだけで（ファイル項目・ファイル型のセッション/キャッシュ・ファイルへの書込み・ログファイルが無い）、データベースとバックアップの暗号化で全保存データが対象になる前提（本番の暗号化の設定は対象外） | GF-067 |
| GAP-064 | RC-158 | NFR-OM-02 | LOG-01〜LOG-03・LOG-05・LOG-06 が標準出力へ1行1件の JSON（日本時間の日時・ログの種類・要求の識別子）で出力され、ファイル・ローテーションのハンドラーが無く、アプリケーションがログを削除しない（ENV-02 での90日保管・検索は対象外） | GF-068 |
| GAP-065 | RC-159 | NFR-OM-03 | 監査ログは DB に発生日時付きで追記のみで記録され、更新・削除の操作は拒否され、利用者への外部キーを持たず、初期データ一括投入（--reset）を含む本システムのどの処理も削除しない（1年保管・運用手順書の削除手順は対象外） | GF-069 |
| GAP-066 | RC-160 | NFR-SC-26 | 利用者向けサービス（画面・API・管理者の画面/API）は1つの待受け（Gunicorn の bind 1件、EXPOSE 8000）だけで提供し、本番プロファイルでは全要求先で HTTPS 以外を拒否し、管理サイト・デバッグ用の要求先・遠隔ログインのソフトウェアが無い（本番のネットワーク設定は対象外。compose.yaml の公開範囲は既知の未解決 SEC-IMPL-002 の対象で根拠に用いない） | GF-070 |
| GAP-067 | RC-161 | NFR-MG-05 | 初期データ一括投入は投入時点の在庫管理表の値（定義ファイルの在庫数量）をそのまま反映し、更新後の在庫管理表の値で再投入（--reset）すると後の値に置き換わる（移行計画の実施日・実施者・確定時刻のレビューは対象外） | GF-071 |
| GAP-068 | RC-162 | NFR-AV-04, NFR-AV-07, NFR-AV-08, NFR-AV-12, NFR-PF-13 | 3年後相当のデータで、利用者の要求を処理しながら（全要求が成功）全データ（監査ログを含む）のバックアップを取得でき、全データの喪失後にバックアップから復元すると取得時点のデータ（取得前の注文あり・取得後の注文なし）に戻り、障害前の全業務（来訪者・購入者・管理者の操作、初期データ一括投入）を再開できる。リストア時間を記録する（本番のバックアップ方式・3:00・7世代・保管場所は対象外） | GF-072 |
| GAP-069 | RC-163 | NFR-OM-15 | 3年後相当のデータで、データ構造の変更を含む更新（マイグレーションの適用）と起動確認を行い、更新直前のバックアップから切戻すとデータ構造・データが更新前の状態に戻り、所要時間（取得・更新・切戻し）が 120分以内（プログラムの入替え・ENV-01 での実施は対象外） | GF-073 |

INITIAL が宣言していたが一部条件を検証していなかった Coverage の補完（supplemental。Initial 値・分類は変更しない）:

- GF-010: RC-038, RC-039（INITIAL 宣言: IT-020）
- GF-011: RC-036（INITIAL 宣言: IT-018）
- GF-018: RC-091（INITIAL 宣言: IT-052）
- GF-019: RC-063（INITIAL 宣言: IT-042）
- GF-020: RC-085（INITIAL 宣言: IT-043）
- GF-021: RC-084（INITIAL 宣言: IT-044）

## 4〜8. Error・Defect

- 正式実行の Error（Failed Case）: 1 件、Unique Defect: 1 件
- 原因別（実装中の TEST_ERROR を含む全 19 件）: IMPLEMENTATION_ERROR 1、TEST_ERROR 18
- AI / External 別: AI_GENERATED 19、EXTERNAL 0
- COMMON_DEFECT 0 / AI_ONLY_DEFECT 1 / EXTERNAL_ONLY_DEFECT 0

## 9〜12. 不具合の箇所

- IT-DEF-001（IT-058、IMPLEMENTATION_ERROR、UNRESOLVED-6de5eec64599b907）: config.wsgi.application, common.middleware.is_unusable_charset — config.wsgi.application が呼ぶ common.middleware.is_unusable_charset は codecs の _is_text_encoding が偽の符号化方式（rot13 等）だけを除外し、テキスト用として登録されているが入力を復号できない 'undefined'・'idna' を通過させる。このため Django の WSGIRequest 生成時（クエリ文字列の復号）に UnicodeError となり、RequestCharsetMiddleware・WebExceptionMiddleware を経ずにアプリケーション外へ例外が送出される（AP サーバーでは 500、LOG-03 も出力されない）

## 13〜14. 修正結果・再試験結果

- Production Code は変更していない（Integration Test Agent の責務外）。IT-DEF-001 は既知の未解決のため新しい3回ループを開始せず、IMPLEMENTATION_FIX_REQUIRED として親へ返す。修正後の対象・関連・全体の再試験は未実行（PASS としない）
- 試行実行で TEST_ERROR 18 件を修正（it-exec-1 前 9 件、cycle=1 の it-exec-2 前 3 件、cycle=2 の it-exec-3 前 2 件、UNRESOLVED-e1d9dfe900863622 cycle=1/3 の it-exec-5 前 1 件、cycle=2/3 の it-exec-6 前 2 件、正式実行 it-exec-6 で検出 1 件。期待値の弱体化・ケース削除なし）。修正後の全体実行が正式実行 it-exec-7

## FULL Traceability C10 の差し戻し（UNRESOLVED-e1d9dfe900863622、修正 cycle=2/3。it-exec-7）

| 指摘 | 重大度 | 対応 |
|---|---|---|
| TRACE-FULL-C10 | FAIL(FULL) | cycle=1/3 の後も要件→テスト未到達の NFR 38件の要件本文・測定条件・検証方法・代替確認を読み直し、Required Coverage Revision 5（RC-149〜RC-163）と AI GAP_FILL GF-059〜GF-073 を追加。開発環境の PC（Windows 11）にインストール済みの Edge・Chrome での全画面の表示・代表操作・表示完了時間、3年後データ量・同時155/310仮想利用者の参考計測、使い捨て PostgreSQL 16 での pg_dump/pg_restore による取得・復元・業務再開と更新・切戻し、開発時の公開脆弱性情報（OSV）との照合、保存データ・ログの出力先・監査ログの削除経路・個人情報の出力・全画面/全 API の簡易な動的診断・HTTPS 以外の拒否・在庫数量の反映の機械確認で、25件を PARTIAL_IT として確認（合格扱いにしない）。検証したケースの要件 ID だけを trace に付与し、確かめられる観点が無い 13件（NOT_VERIFIED 10・NOT_APPLICABLE 3）は cycle=2/3 の再評価の記録とともに維持 |

- 追加 GAP_FILL: GF-059〜GF-073（Required Coverage Revision 5 の RC-149〜RC-163）。結果: GF-059 PASS、GF-060 PASS、GF-061 PASS、GF-062 PASS、GF-063 PASS、GF-064 PASS、GF-065 PASS、GF-066 PASS、GF-067 PASS、GF-068 PASS、GF-069 PASS、GF-070 PASS、GF-071 PASS、GF-072 PASS、GF-073 PASS
- 参考計測・機械確認の記録: browser-reference.json・performance-reference.json・security-reference.json・operations-reference.json・recovery-reference.json・dependency-vulnerability-osv.json（いずれも合格扱いにしない PARTIAL_IT の根拠）
- NFR の検証可否（nfr-verification-scope.json／.md）: 一覧 92 件の区分 VERIFIED_IT 5 / PARTIAL_IT 65 / NOT_APPLICABLE_PREMISE_IT 9 / NOT_VERIFIED 10 / NOT_APPLICABLE 3。差し戻し時点の C10 の NFR 件数・本対応後の未到達件数は nfr-verification-scope.json の counts（PARTIAL_IT・NOT_APPLICABLE_PREMISE_IT・NOT_VERIFIED・NOT_APPLICABLE は合格扱いにしない）

## FULL Traceability C10 の差し戻し（UNRESOLVED-e1d9dfe900863622、修正 cycle=1/3。it-exec-5）

| 指摘 | 重大度 | 対応 |
|---|---|---|
| TRACE-FULL-C10 | FAIL(FULL) | Policy require_test_for の NFR のうち要件→テスト未到達の 60件（NOT_VERIFIED 48・NOT_APPLICABLE 12）の要件本文・測定条件・検証方法・根拠を読み直し、Required Coverage Revision 4（RC-134〜RC-148）と AI GAP_FILL GF-044〜GF-058 を追加。「該当なし」の 9件は根拠の前提（バッチ・ファイルアップロード・多要素認証・アカウントロック・パスワード変更・送信元単位の制限・外部決済・特定商取引法の表記が無いこと）だけを NOT_APPLICABLE_PREMISE_IT として確認、構成・設定レビュー／静的解析の 13件はリポジトリ内で確かめられる部分だけをPARTIAL_IT として確認（合格扱いにしない）。検証したケースの要件 ID だけを trace に付与し、残りは再評価の記録とともにNOT_VERIFIED・NOT_APPLICABLE を維持 |
| QR-FULL-1118-001 | LOW | nfr-verification-scope の件数表記を、一覧の件数（92）・差し戻し時点の FULL 監査の C10 の NFR 件数・本対応後の未到達件数に分けて記録し、basis・md・Report の「C10 の NFR 92件」の表記を修正 |

- 追加 GAP_FILL: GF-044〜GF-058（Required Coverage Revision 4 の RC-134〜RC-148）。結果（本実行）: GF-044 PASS、GF-045 PASS、GF-046 PASS、GF-047 PASS、GF-048 PASS、GF-049 PASS、GF-050 PASS、GF-051 PASS、GF-052 PASS、GF-053 PASS、GF-054 PASS、GF-055 PASS、GF-056 PASS、GF-057 PASS、GF-058 PASS

## TEST_ERROR 修正 cycle=3/3（Quality 再レビュー QR-IT-1118-R2-001 への対応。it-exec-4）

| 指摘 | 重大度 | 対応 |
|---|---|---|
| QR-IT-1118-R2-001 | LOW | GF-034 の title（integration-test-plan.json）と試験関数 test_gf_034_double_submit_place_pay の docstring を「処理完了前の繰り返し操作」から実際の手順「先着の応答後の同じ送信トークンでの逐次の再送」（処理中の同時再送は GF-039〜GF-043）に修正。自己点検（全104件の title と試験関数の docstring・試験手順の突合）で、GF-002 の試験コード内の注記（「処理完了前の繰り返し操作は先着の応答を受け取る前と同じ Cookie・フォーム値で送られる」）も逐次再送の実態に合わせて修正。他の食い違いはなし（AI INITIAL の IT-050・IT-026 は「二重送信」「再送信」で実装と一致、変更なし）。判定・期待値・Coverage は変更なし |

- 結果: GF-002 PASS、GF-034 PASS

## TEST_ERROR 修正 cycle=2/3（Quality 再レビュー QR-IT-1118-R1-001 への対応。it-exec-3）

| 指摘 | 重大度 | 対応 |
|---|---|---|
| QR-IT-1118-R1-001 | MEDIUM | Required Coverage Revision 3（RC-129〜RC-133、NFR-US-10・ADDR-004 4.4 の検証方法・テスト行から導出）を追加し、GAP_FILL GF-039〜GF-043 で先着が送信トークンのアドバイザリロックを保持して業務処理中に同じトークンの後着を別接続から送り、後着のロック待ち（pg_locks）を確認したうえで、支払（承認・否認）・先着 E-031-08／結果の記録前の中断・注文確定・カートに入れる・ログイン（先着 E-002-02）の反映・決済要求・監査ログが1回分、後着の通知が ADDR-004 DD-013 どおりであることを確認。GF-034 の前提を実際の手順（先着の応答後の逐次再送）に修正し、nfr-verification-scope の NFR-US-10 を GF-039〜GF-043 の実行結果で更新（PASS の場合だけ counts_as_quality_pass=true） |

- 追加 GAP_FILL: GF-039〜GF-043（Required Coverage Revision 3 の RC-129〜RC-133）。結果: GF-039 PASS、GF-040 PASS、GF-041 PASS、GF-042 PASS、GF-043 PASS
- NFR-US-10: VERIFIED_IT（counts_as_quality_pass=True。GF-039〜GF-043・GF-034・IT-050・GF-002・GF-003 がすべて PASS の場合だけ true）

## TEST_ERROR 修正 cycle=1/3（INTEGRATION_TEST Scope Assurance への対応。it-exec-2）

| 指摘 | 重大度 | 対応 |
|---|---|---|
| QR-IT-1118-001 | MEDIUM | RC-105 を追加し GF-012（管理者キャンセル×支払、10試行＋両順序の固定、(a)(b) の Then 全項目） |
| QR-IT-1118-002 | MEDIUM | RC-106 を追加し GF-013（来訪者の「カートに入れる」→SCR-004→ログイン後 SCR-002、カート・在庫不変） |
| QR-IT-1118-003 | MEDIUM | RC-107・RC-108 を追加し GF-014（支払要求の識別子で LOG-01〜03・06 を抽出、連携エラー時の LOG-02）・GF-015（模擬決済が受けた要求4項目・外部通信0件・1秒以内） |
| QR-IT-1118-004 | MEDIUM | RC-109〜RC-111 を追加し GF-016（10並列×10回・注文番号の一意とコミット順の増加）・GF-017（障害後の欠番）・GF-018（--reset 後の採番・識別子の非巻き戻し） |
| QR-IT-1118-005 | LOW | GF-019〜GF-021（IT-042〜044 の Then の残り：履歴件数・順序・実行者区分・後着の通知文言・出荷日時/伝票番号・決済記録、AC の10試行）を supplemental として追加 |
| QR-IT-1118-006 | LOW | GF-010・GF-011 の notes を INITIAL の確認漏れの補完（supplemental）に修正し、Revision 1 の Initial Coverage Rate に過大宣言分が含まれる旨を coverage-gap-report に注記（値は変更しない） |
| SR-IT-R1-001 | LOW | GF-002 に再送ブラウザのログイン状態なしの確認を追加、GF-018 で --reset 後の画面セッションの無効化を確認 |
| TRACE-C10 | FAIL(FULL) | Required Coverage Revision 2 に結合試験で自動検証できる NFR（RC-112〜RC-128）を追加し GF-022〜GF-038 で検証。検証できない NFR は nfr-verification-scope.json に未検証・理由・検証すべき工程として記録 |

- Production Code・AI INITIAL（ai-initial-cases.json）・External 入力の状態（external_cases_confirmed_absent=true）は変更していない
- cycle=1/3 時点の NFR の検証可否は Scope Assurance 時点の C10 の NFR 92件の一覧で記録（現在の区分は上の「FULL Traceability C10 の差し戻し」を参照）
- 応答時間（GF-022）は単一利用者・小データ量の参考計測（response-time-reference.json）で、性能要件の合否判定ではない

## Criteria

| Criterion | 適用 | 結果 | ケース数 | FAIL |
|---|---|---|---|---|
| api | True | PASS | 34 | - |
| authentication | True | PASS | 12 | - |
| database | True | PASS | 39 | - |
| end-to-end-flow | True | PASS | 29 | - |
| error-handling | True | FAIL | 11 | IT-058 |
| state-transition | True | PASS | 9 | - |

## 引き継ぐ既知の未解決

- UNRESOLVED-6de5eec64599b907: SEC-IMPL-001 NUL文字入力でDB DataError→500(NFR-SC-04)、charset=undefined/idna で500、002 compose公開範囲（原因工程 IMPLEMENTATION）
- UNRESOLVED-32af0f4a0ca9c80f: SEC-REQ-001..004（原因工程 REQUIREMENTS。本工程の期待値はこの未決のまま現行要件どおり）
- UNRESOLVED-0b5694db22a0bead: SR-ARCH-001 本番デバッグ無効化/環境別設定の設計・ADDR引渡し漏れ（原因工程 ARCHITECTURE）
- UNRESOLVED-60a549ca11f16034: QR-ARCH-001 Task依存矛盾、002 FR-060削除後のログイン状態無効化の引渡し漏れ（原因工程 ARCHITECTURE）
- UNRESOLVED-34471205dd0539bc: expected-fr.txt の FR-OUT-01〜16 の EXCLUDE 書式が trace_check C12 と不整合（原因工程 IMPLEMENTATION→REQUIREMENTS）
