"""AI GAP_FILL 結合試験ケース（RUN-AOBA-EC-1118）。

Coverage Gap Analysis（AI INITIAL と Required Coverage の比較。External Case は未提供でユーザーが明示的に
外部取り込みなしを選択）で MISSING となった Required Coverage を補う。origin=AI_GENERATED、generation_stage=GAP_FILL。
INITIAL を置き換えず、INITIAL の固定ファイル（ai-initial-cases.json）は変更しない。

- GF-001〜GF-009：Required Coverage Revision 1 の MISSING を補う。
- GF-010・GF-011：INITIAL が宣言した Coverage の確認漏れの補完（supplemental。Initial 時点の MISSING ではない）。
- GF-012〜GF-038（TEST_ERROR 修正 cycle=1/3、INTEGRATION_TEST Scope Assurance の指摘対応）：
  Required Coverage Revision 2 の MISSING を補う GAP_FILL と、INITIAL の確認漏れの補完（GF-018 の RC-091、GF-019〜021）。
- GF-002 は Security Review SR-IT-R1-001 により確認項目（再送したブラウザのログイン状態）を追加した。
- GF-039〜GF-043（TEST_ERROR 修正 cycle=2/3、Quality QR-IT-1118-R1-001）：Required Coverage Revision 3（RC-129〜RC-133）の
  MISSING を補う GAP_FILL。処理中（送信トークンのアドバイザリロック保持中）の同一トークンの後着を別接続から送る。
  GF-034 は前提の記述を実際の手順（先着の応答後の逐次再送）に修正した（期待結果・テストコードは変更なし）。
- TEST_ERROR 修正 cycle=3/3（Quality QR-IT-1118-R2-001）：GF-034 の title・試験関数の docstring と GF-002 の試験コード内の
  注記を実際の手順（先着の応答後の逐次再送）に合わせた（判定・期待値・Coverage は変更なし）。
- GF-044〜GF-058（FULL Traceability C10 の差し戻し、UNRESOLVED-e1d9dfe900863622 修正 cycle=1/3）：Required Coverage
  Revision 4（RC-134〜RC-148）の MISSING を補う GAP_FILL。NFR の「該当なし」の前提と、リポジトリ内で確かめられる部分だけ。
- GF-059〜GF-073（FULL Traceability C10 の差し戻し、UNRESOLVED-e1d9dfe900863622 修正 cycle=2/3）：Required Coverage
  Revision 5（RC-149〜RC-163）の MISSING を補う GAP_FILL。開発環境の PC・ブラウザ・使い捨て DB で行う参考計測・操作確認と機械確認。
"""

T = "app/tests/integration"

_RAW = [
    ("GF-001", "画面の会員登録の入力エラー表示・ログイン失敗表示と入力値の保持", "FR-001, FR-002", "ADDR-012, ADDR-004",
     "WEB", "api", "Web>accounts.services",
     "CSRF 検証を有効にした画面クライアント。購入者1名が登録済み。",
     "SCR-003 に不正な値（メール形式不正・パスワード短い・氏名空）、SCR-004 に誤パスワード",
     "1) SCR-003 に不正な値で登録 2) SCR-004 に誤パスワードでログイン 3) DB・監査ログを確認",
     "1) 400 で SCR-003 を再表示、項目ごとの理由、メール・氏名の入力値を保持しパスワード欄は空 2) 401 で SCR-004 に「メールアドレスまたはパスワード」が誤っている旨、メールを保持しパスワード欄は空 3) 利用者は増えない、login_failure が1件",
     ["RC-014", "RC-018"], f"{T}/test_it_gap_fill.py::test_gf_001_web_register_and_login_error_display"),
    ("GF-002", "画面ログインの同じ送信トークンでの再送（照合・監査ログを重ねない）", "FR-002", "ADDR-004",
     "DATABASE", "database", "Web>SubmitToken>accounts.services>AuditLog",
     "CSRF 検証を有効にした画面クライアント。購入者1名。",
     "SCR-004 の同じ submit_token で2回送信（2回目は誤パスワード）",
     "1) 正しいパスワードで送信 2) 同じトークンで誤パスワードを送信 3) 監査ログを確認 4) 再送したブラウザで保護画面（/cart/）を要求",
     "1) 302 で / 2) 先着の結果（成功）と同じ遷移先へ 302（入力値に依存しない） 3) login_success が1件のみ、login_failure は記録されない "
     "4) 再送したブラウザにはログイン状態が付与されず SCR-004（required）へ遷移、先着のブラウザはログイン中",
     ["RC-023"], f"{T}/test_it_gap_fill.py::test_gf_002_web_login_double_submit_same_token"),
    ("GF-003", "画面「カートに入れる」の同じ送信トークンでの再送", "FR-021", "ADDR-004",
     "DATABASE", "database", "Web>SubmitToken>carts.services>DB",
     "CSRF 検証を有効にした購入者の画面クライアント。在庫単位（在庫20）。",
     "SCR-002 の同じ submit_token で数量3を2回送信",
     "1) 1回目 2) 同じトークンで2回目 3) カート明細を確認",
     "1)2) いずれも 302 で商品詳細へ戻る 3) 明細の数量は3（加算されない）",
     ["RC-044"], f"{T}/test_it_gap_fill.py::test_gf_003_web_cart_add_double_submit"),
    ("GF-004", "画面の注文手続きの配送先入力エラー表示と入力値の保持", "FR-030", "ADDR-012",
     "WEB", "api", "Web>orders.services",
     "CSRF 検証を有効にした購入者の画面クライアント。カートに1明細。",
     "郵便番号 '〒1234567'、電話 '03-1234'、氏名 '山田 花子'、住所1 '千代田区1-1'",
     "1) SCR-006 から不正な配送先で確定 2) DB を確認",
     "1) 400 で SCR-006 を再表示、郵便番号・電話番号の理由を表示し入力値（氏名・住所1・郵便番号）を保持 2) 注文0件、在庫・カート不変",
     ["RC-054"], f"{T}/test_it_gap_fill.py::test_gf_004_web_checkout_input_error_retains_values"),
    ("GF-005", "画面（SCR-010）での購入者キャンセル", "FR-034", "ADDR-012, ADDR-004",
     "WEB", "end-to-end-flow", "Web>SubmitToken>orders.services>DB",
     "CSRF 検証を有効にした購入者の画面クライアント。注文受付の注文（在庫引当済み）。",
     "SCR-010 のキャンセルフォーム",
     "1) SCR-010 を表示しキャンセルを送信 2) 遷移先を表示 3) DB を確認",
     "1) 302 で SCR-010 2) 「注文をキャンセルしました。」と状態「キャンセル済」 3) 在庫が戻る、履歴（実行者=購入者）",
     ["RC-072"], f"{T}/test_it_gap_fill.py::test_gf_005_web_buyer_cancel"),
    ("GF-006", "在庫単位一覧（管理）の入力エラー全項目", "FR-040", "ADDR-001",
     "API", "api", "API>catalog.services",
     "管理者。仕入先1件。",
     "supplier_code=未登録、low_stock_only=yes、page=abc、sku=33文字",
     "1) 不正な条件を同時に指定して GET /api/admin/stock-units/",
     "1) 400 input_error、fields に supplier_code・low_stock_only・page・sku の全項目",
     ["RC-074"], f"{T}/test_it_gap_fill.py::test_gf_006_stock_unit_list_input_errors"),
    ("GF-007", "注文一覧検索（管理者）の入力エラー", "FR-041", "ADDR-001",
     "API", "api", "API>orders.services",
     "管理者。",
     "order_date_from=2027-04-10・order_date_to=2027-04-09、order_date_from=2027-02-30、order_number=PO-123、status=unknown",
     "1) 開始＞終了 2) 実在しない日付・注文番号形式不正・状態不正を同時に",
     "1) 400 input_error（invalid_range） 2) 400 input_error、fields に order_date_from・order_number・status",
     ["RC-077"], f"{T}/test_it_gap_fill.py::test_gf_007_admin_order_search_input_errors"),
    ("GF-008", "出荷登録の配送伝票番号の検証（30文字可・31文字・不正文字）", "FR-043", "ADDR-001",
     "API", "api", "API>orders.services",
     "支払済の注文2件。管理者。",
     "31文字、'TRK 001'（空白）、'伝票1'、30文字",
     "1) 31文字・不正文字で出荷登録 2) DB を確認 3) 30文字で出荷登録",
     "1) 400 input_error（tracking_number） 2) 支払済のまま、履歴不変 3) 200 shipped、伝票番号を大小文字そのまま記録",
     ["RC-080"], f"{T}/test_it_gap_fill.py::test_gf_008_ship_tracking_number_validation"),
    ("GF-009", "提供済み定義ファイル（app/seed/initial_data.json）の投入", "FR-060", "ADDR-009, ADDR-010",
     "BATCH", "database", "ManagementCommand>initial_data.loader>DB",
     "空の試験用 DB。",
     "python manage.py load_initial_data app/seed/initial_data.json",
     "1) コマンドを実行 2) DB 件数を確認",
     "1) 成功 2) 利用者・仕入先・商品分類・商品・在庫単位・クーポンの件数が定義ファイルの件数と一致",
     ["RC-096"], f"{T}/test_it_gap_fill.py::test_gf_009_seed_file_loadable"),
    # --- 以下は実装時の照合（テストコードと Required Coverage の突合せ）で、AI INITIAL が Coverage を宣言しているが
    #     一部の条件を検証していないと判明した項目の補完（Initial Coverage Metrics は変更しない） ---
    ("GF-010", "クーポン適用のコード不存在・形式不正と有効終了日時ちょうど／1秒後の適用", "FR-024", "ADDR-001, ADDR-011",
     "STATE", "state-transition", "API>carts.services>Clock(TestState)>DB",
     "現在日時を固定。有効終了日時 2027-04-30T23:59:59 のクーポン。購入者のカートに1明細。",
     "コード 'NOPE-1'、'BAD CODE'・21文字・空・全角、処理時刻=有効終了日時ちょうど／1秒後",
     "1) 未登録コードを適用 2) 形式不正の各コードを適用 3) 有効終了日時ちょうどに適用→解除 4) 1秒後に適用",
     "1) 422 coupon_not_found 2) 400 input_error（coupon_code） 3) 200 4) 422 coupon_expired（valid_to を通知）、クーポンは適用されない",
     ["RC-038", "RC-039"], f"{T}/test_it_gap_fill.py::test_gf_010_coupon_not_found_format_and_end_boundary"),
    ("GF-011", "注文済カートの明細を指定した数量変更・削除は対象なし", "FR-022, FR-023", "ADDR-001",
     "API", "api", "API>carts.services>DB",
     "購入者のカートに1明細。",
     "注文確定後に、確定前のカート明細 ID で PATCH・DELETE",
     "1) 明細を追加し注文確定 2) その明細 ID に PATCH・DELETE 3) DB を確認",
     "2) いずれも 404 not_found 3) 注文済カートの明細は変化しない",
     ["RC-036"], f"{T}/test_it_gap_fill.py::test_gf_011_ordered_cart_item_not_found"),
]


_NOTE_R1 = "Required Coverage Revision 1 の Coverage Gap（MISSING）を補う GAP_FILL"
_NOTE_SUPPLEMENT_R1 = (
    "INITIAL の確認漏れの補完（supplemental）。対象 RC は INITIAL（{by}）が Coverage を宣言済みで Initial 時点の MISSING ではない。"
    "実装時のテストコードと Required Coverage の照合で一部条件が未検証と判明したため補完する。Initial Coverage Metrics・分類は変更せず、"
    "Revision 1 の AI INITIAL Coverage Rate（90.38%）にはこの過大宣言分が含まれる"
)
_NOTE_R2 = "Required Coverage Revision 2（{src}）で追加した Coverage の MISSING を補う GAP_FILL"
_NOTE_R2_PARTIAL = _NOTE_R2 + "。部分検証：{part}（未検証部分は nfr-verification-scope.json）"
_NOTE_SUPPLEMENT_R2 = (
    "INITIAL の確認漏れの補完（supplemental、QR-IT-1118-005）。対象 RC は INITIAL（{by}）が宣言済み。AC の Then の残り項目と"
    "測定条件（注文を作り直して10試行）を確認し、行ロック待ちの解放順を固定して両方の逐次順序の Then も確認する"
)

NOTES = {
    "GF-002": _NOTE_R1 + "。先着の応答後の逐次の再送（使用済みトークンの判定）。処理中の同一トークンの到着は GF-043（QR-IT-1118-R1-001）",
    "GF-003": _NOTE_R1 + "。先着の応答後の逐次の再送（使用済みトークンの判定）。処理中の同一トークンの到着は GF-042（QR-IT-1118-R1-001）",
    "GF-010": _NOTE_SUPPLEMENT_R1.format(by="IT-020"),
    "GF-011": _NOTE_SUPPLEMENT_R1.format(by="IT-018"),
}

_RAW_R2 = [
    ("GF-012", "管理者キャンセルと購入者の支払の同時実行（10試行・両順序）", "FR-045, FR-031", "ADDR-004, ADDR-008, ADDR-011",
     "CONCURRENCY", "database", "MultiConnection>DB(lock)>payments.gateway(mock)",
     "transaction=True、現在日時を固定。在庫単位（税抜2,500円）。購入者・管理者のログイン状態。試行ごとに注文（×2、合計5,500円）を新たに用意",
     "管理者キャンセル（POST /api/admin/orders/{id}/cancel/）と支払（承認）",
     "1) 2要求を Barrier で同時に送る試行を10回 2) 注文行を別接続でロックし、キャンセル→支払の順に行ロック待ちへ入れて解放 3) 支払→キャンセルの順で同様 "
     "4) 各回の注文詳細（管理）・在庫を確認",
     "各回：キャンセル 200・状態キャンセル済・出荷/配達完了/キャンセル不可・在庫+2。(a) キャンセル先着：支払 422 invalid_status（cancelled）、"
     "決済記録0件・支払日時なし・履歴2件（2件目 注文受付→キャンセル済 管理者）。(b) 支払先着：支払 200、決済記録 承認5,500円の1件・支払日時あり・"
     "履歴3件（注文受付→支払済 購入者、支払済→キャンセル済 管理者）。2) は (a)、3) は (b)",
     ["RC-105"], f"{T}/test_it_gap_fill_concurrency.py::test_gf_012_concurrent_admin_cancel_and_pay",
     _NOTE_R2.format(src="QR-IT-1118-001、AC-UC-012-011")),
    ("GF-013", "来訪者の「カートに入れる」→ログイン画面→ログイン後に商品詳細へ戻る", "FR-012, FR-021, FR-002", "ADDR-002, ADDR-012",
     "AUTH", "authentication", "Web>Session>Redirect(next)>carts.services",
     "CSRF 検証を有効にした未ログインの画面クライアント。商品「ステンレスマグ」の在庫単位（ブルー、税抜1,500円、在庫20）。購入者A（カート明細0件）",
     "SCR-002 の「カートに入れる」（規格ブルー、数量1）",
     "1) SCR-002 を表示し「カートに入れる」を送信 2) カート・在庫を確認 3) 遷移先の SCR-004 で購入者Aとしてログイン 4) 遷移先を表示",
     "1) 302 で /login/?required=1&next=/products/{id}/ 2) カート・カート明細の件数と在庫数量（20）は不変 3) SCR-004 に「ログインが必要」、"
     "next=商品詳細、ログイン後 302 で /products/{id}/ 4) SCR-002 を表示、カート（0点）、購入者Aのカート明細0件、在庫20",
     ["RC-106"], f"{T}/test_it_gap_fill_flows.py::test_gf_013_visitor_cart_add_login_return",
     _NOTE_R2.format(src="QR-IT-1118-002、AC-UC-003-018、AC-UC-004-024")),
    ("GF-014", "支払要求の要求の識別子による LOG-01〜LOG-03・LOG-06 の横断追跡", "NFR-OM-18, NFR-OM-11, FR-031", "ADDR-013, ADDR-008, ADDR-011",
     "LOGGING", "api", "API>orders.services>payments.client>AppLog",
     "アプリケーションログを JSON 行で捕捉。注文受付の注文（×2、合計5,500円）",
     "POST /api/orders/{id}/payment/（承認）、別注文で試験用状態 payment_mode=connection_error",
     "1) 支払要求 2) 応答の X-Request-ID で全ログ行を抽出 3) 連携エラーの支払要求で同様",
     "2) 要求中の全行が同じ識別子で、LOG-01（start/end success・利用者）、LOG-03（POST・パス・200・利用者・処理時間）、LOG-06（request/response、"
     "order_number・amount=5,500・currency=JPY、response は approved と決済記録の取引参照番号・duration_ms）。日時は日本時間。"
     "メールアドレス・氏名・ログイン状態・配送先を含まない 3) 502、同じ識別子で LOG-01・LOG-02（integration_error・例外の種類・発生箇所）・LOG-03・LOG-06（integration_error）",
     ["RC-107"], f"{T}/test_it_gap_fill_flows.py::test_gf_014_payment_request_id_trace",
     _NOTE_R2.format(src="QR-IT-1118-003、NFR-OM-18 測定条件、ADDR-013 DC-002")),
    ("GF-015", "決済サービス（模擬）が受けた決済要求の内容と外部通信0件", "FR-031, NFR-SC-24, NFR-EN-05", "ADDR-008",
     "API", "api", "API>orders.services>payments.client>gateway(mock)",
     "模擬機能を包んで受けた要求を記録する境界（実装は差し替えない）。socket の接続操作を記録。注文受付の注文（合計5,500円）",
     "POST /api/orders/{id}/payment/（承認）",
     "1) 支払要求 2) 模擬機能が受けた要求・送信から応答受信までの時間・外部への接続操作を確認",
     "1) 200 2) 要求は1件で {order_number, amount=5500, currency=JPY, mock_instruction=approved} の4項目だけ（個人情報なし）、"
     "応答まで1秒以内、外部ネットワーク宛ての接続0件、決済記録 承認5,500円",
     ["RC-108"], f"{T}/test_it_gap_fill_flows.py::test_gf_015_payment_request_contents_no_external",
     _NOTE_R2.format(src="QR-IT-1118-003、AC-UC-007-016")),
    ("GF-016", "在庫数量5への10並列の注文確定×10回と注文番号の一意・確定順", "FR-030, NFR-PF-07, NFR-LG-06", "ADDR-005, ADDR-004",
     "CONCURRENCY", "database", "MultiConnection>DB(lock, advisory lock, sequence)",
     "transaction=True。試験用 DB は track_commit_timestamp=on。試行ごとに在庫数量5の在庫単位と、1個ずつカートに入れた購入者10名",
     "POST /api/orders/ を10並列（Barrier）",
     "1) 10並列の注文確定を10回 2) 各回の応答・在庫・注文明細の数量合計を確認 3) 成功した50件の注文番号とコミット時刻（pg_xact_commit_timestamp）を確認",
     "2) 各回 成功5・insufficient_stock 5、在庫0、引当合計5 3) 注文番号は重複せず PO-＋8桁、コミットの順に増加",
     ["RC-109"], f"{T}/test_it_gap_fill_concurrency.py::test_gf_016_ten_parallel_ten_trials_order_numbers",
     _NOTE_R2.format(src="QR-IT-1118-004、NFR-PF-07 測定条件、ADDR-005 検証方法")
     + "。注文日時は秒単位でロック取得前の時刻のため順序判定に用いず、コミットの順で判定する"),
    ("GF-017", "払い出し後の障害で取り消された注文番号の欠番", "FR-030", "ADDR-005, ADDR-011",
     "ERROR", "error-handling", "API>orders.services>FaultPoint(TestState)>DB(sequence)",
     "購入者の注文1件（PO-n）。カートに1明細",
     "試験用状態 order_fault_point=after_order_insert で注文確定、解除して再確定",
     "1) 障害点を設定して確定 2) 解除して確定 3) 注文番号を確認",
     "1) 500 system_error、注文は1件のまま、在庫不変 2) 201 3) 新しい注文番号は PO-(n+2)（PO-(n+1) は欠番で再使用されない）",
     ["RC-110"], f"{T}/test_it_gap_fill_flows.py::test_gf_017_fault_order_number_gap",
     _NOTE_R2.format(src="QR-IT-1118-004、ADDR-005 DD-003")),
    ("GF-018", "--reset 後の採番・識別子の非巻き戻しと削除前の画面のログイン状態の無効化", "FR-060", "ADDR-002, ADDR-005, ADDR-006, ADDR-010",
     "BATCH", "database", "ManagementCommand>initial_data.loader>DB(sequence, identity)>Session",
     "transaction=True。画面でログインしたブラウザ、Web API のログイン状態、支払済の注文・カート明細・クーポン等がある状態",
     "python manage.py load_initial_data <定義ファイル> --reset",
     "1) 各データの識別子の最大値を記録 2) --reset で投入 3) 画面・API のログイン状態を確認 4) 投入した利用者で注文確定・支払 5) 識別子・注文番号を比較",
     "2) 成功 3) 画面のセッションは削除され保護画面は SCR-004 へ、旧 Bearer は 401 4) 成功 5) 投入・新規作成した全データの識別子は削除前の最大値より大きく、"
     "注文番号も削除前より大きい（巻き戻し・再利用なし）",
     ["RC-111", "RC-091"], f"{T}/test_it_gap_fill_flows.py::test_gf_018_reset_no_rewind_and_web_session",
     _NOTE_R2.format(src="QR-IT-1118-004、ADDR-005 DD-003、ADDR-006 DD-002")
     + "。RC-091 は INITIAL（IT-052）の確認漏れ（画面のログイン状態の無効化、SR-IT-R1-001）の補完"),
    ("GF-019", "支払とキャンセル（購入者）の同時実行の Then 全項目（10試行・両順序）", "FR-031, FR-034", "ADDR-004, ADDR-008, ADDR-011",
     "CONCURRENCY", "database", "MultiConnection>DB(lock)",
     "transaction=True、現在日時を固定。模擬機能が受けた要求を記録。試行ごとに注文（×2、合計5,500円）を新たに用意",
     "支払（承認）と POST /api/orders/{id}/cancel/",
     "1) 同時に送る試行を10回 2) キャンセル→支払、支払→キャンセルの順を行ロック待ちで固定 3) 各回の決済記録・状態履歴・在庫・模擬機能への要求を確認",
     "各回：キャンセル 200・最終キャンセル済・在庫+2。(a) 支払 422 invalid_status（cancelled）、決済記録0件、履歴2件（注文受付→キャンセル済）、"
     "模擬機能は当該注文の要求を受けない。(b) 支払 200、決済記録 承認1件のみ、履歴3件（注文受付→支払済、支払済→キャンセル済）",
     ["RC-063"], f"{T}/test_it_gap_fill_concurrency.py::test_gf_019_pay_and_buyer_cancel_ten_trials",
     _NOTE_SUPPLEMENT_R2.format(by="IT-042") + "（AC-UC-007-019）"),
    ("GF-020", "管理者キャンセルと購入者キャンセルの同時実行の Then 全項目（10試行・両順序）", "FR-034, FR-045", "ADDR-004, ADDR-011",
     "CONCURRENCY", "database", "MultiConnection>DB(lock)",
     "transaction=True、現在日時を固定。試行ごとに注文（×2）を新たに用意",
     "POST /api/admin/orders/{id}/cancel/ と POST /api/orders/{id}/cancel/",
     "1) 同時に送る試行を10回 2) 管理者→購入者、購入者→管理者の順を行ロック待ちで固定 3) 後着の通知・状態履歴・在庫を確認",
     "各回：一方 200・他方 422 invalid_status（cancelled、「この注文はキャンセルできません（現在の状態：キャンセル済）。」）、在庫+2、"
     "キャンセル済の履歴は1件で実行者の利用者区分は完了した側と一致。2) は管理者、逆順は購入者が完了",
     ["RC-085"], f"{T}/test_it_gap_fill_concurrency.py::test_gf_020_admin_and_buyer_cancel_ten_trials",
     _NOTE_SUPPLEMENT_R2.format(by="IT-043") + "（AC-UC-012-009）"),
    ("GF-021", "管理者キャンセルと出荷登録の同時実行の Then 全項目（10試行・両順序）", "FR-043, FR-045", "ADDR-004, ADDR-011",
     "CONCURRENCY", "database", "MultiConnection>DB(lock)",
     "transaction=True、現在日時を固定。管理者X・Y。試行ごとに支払済の注文（×3、決済記録 承認1件、履歴2件）を新たに用意",
     "管理者Xのキャンセルと管理者Yの出荷登録（配送伝票番号 TRK-Y）",
     "1) 同時に送る試行を10回 2) キャンセル→出荷、出荷→キャンセルの順を行ロック待ちで固定 3) 状態・在庫・出荷日時・伝票番号・履歴・決済記録を確認",
     "各回：一方だけ 200、履歴の追加1件、決済記録は承認1件のまま。キャンセル完了：出荷登録は「この注文は出荷登録できません（現在の状態：キャンセル済）。」、"
     "在庫+3、出荷日時・配送伝票番号なし。出荷完了：キャンセルは「この注文はキャンセルできません（現在の状態：出荷済）。」、伝票番号 TRK-Y、在庫不変、キャンセル日時なし",
     ["RC-084"], f"{T}/test_it_gap_fill_concurrency.py::test_gf_021_admin_cancel_and_ship_ten_trials",
     _NOTE_SUPPLEMENT_R2.format(by="IT-044") + "（AC-UC-012-010）"),
    ("GF-022", "照会系・更新系・認証系 API の応答時間の95パーセンタイル（参考計測）", "NFR-PF-01, NFR-PF-02, NFR-PF-09", "ADDR-001",
     "API", "api", "API(all)>Services>DB",
     "商品40件・在庫単位80件・クーポン（定率10%）。購入者・管理者。各 API を1回以上要求して起動直後の影響を除く",
     "照会系9種・更新系11種・認証系4種を各100要求以上（注文確定は3明細・5点、半数はクーポン適用）",
     "1) 種別ごとに逐次要求し、要求の送信から応答の受信完了までを計測 2) 95パーセンタイルと応答の種類を集計（response-time-reference.json）",
     "全種別でシステムエラー・業務エラー0件、95パーセンタイルが照会系1.0秒・更新系2.0秒・認証系2.0秒以内",
     ["RC-112"], f"{T}/test_it_gap_fill_nfr_web.py::test_gf_022_response_time_p95_reference",
     _NOTE_R2_PARTIAL.format(src="Traceability C10 の NFR 見直し", part="単一利用者・逐次・小データ量の参考計測。ピーク負荷（同時155利用者）・3年後データ量での判定は性能試験")),
    ("GF-023", "一覧の1回の応答の件数上限", "NFR-PF-08", "ADDR-001",
     "API", "api", "API>catalog/orders.services>DB(paging)",
     "公開商品45件（在庫単位55件）、購入者の注文21件、商品分類2件",
     "GET /api/products/・/api/orders/・/api/admin/stock-units/・/api/admin/orders/ の先頭ページと最終ページ、GET /api/categories/",
     "1) 各一覧の先頭・最終ページを照会 2) 件数とページ項目を確認",
     "先頭・最終ページとも50件以下（商品・注文履歴20件、在庫単位50件ずつ）、総件数どおりの端数、商品分類一覧は全件をページ項目なしで返す",
     ["RC-113"], f"{T}/test_it_gap_fill_nfr_web.py::test_gf_023_list_response_cap",
     _NOTE_R2_PARTIAL.format(src="Traceability C10 の NFR 見直し", part="3年後データ量での確認と商品分類45件以下（データ量に依存）は性能試験・運用")),
    ("GF-024", "VDC-04 相当の初期データの移行リハーサル（--reset、1回の実行）", "NFR-PF-10, NFR-MG-01, NFR-MG-02, NFR-MG-03, NFR-MG-04, NFR-MG-08, NFR-OM-04, FR-060", "ADDR-009, ADDR-010",
     "BATCH", "end-to-end-flow", "ManagementCommand>initial_data.loader>DB>API",
     "transaction=True。注文（支払済）・カート明細・監査ログがある状態。VDC-04 と同じ件数構成の架空の定義ファイル（計1,157件）",
     "1) 注文データを含む定義ファイル 2) VDC-04 相当の定義ファイルを --reset で投入",
     "1) 注文を含む定義ファイルを投入 2) VDC-04 相当を投入し所要時間を計測 3) 件数・業務キーを照合 4) 管理者7名でログイン",
     "1) 失敗し何も変わらない（監査ログに失敗1件） 2) 成功、60秒以内、通知の件数が定義と一致、LOG-05 成功 3) 利用者7・仕入先20・商品分類30・商品300・在庫単位800、"
     "業務キー（メールアドレス・仕入先コード・分類コード・商品コード・SKU）全件一致、注文・カート・決済記録・状態履歴0件、2) の実行前の監査ログが残り1件増加 4) 7名とも成功",
     ["RC-114"], f"{T}/test_it_gap_fill_nfr_batch.py::test_gf_024_vdc04_rehearsal",
     _NOTE_R2_PARTIAL.format(src="Traceability C10 の NFR 見直し", part="架空の値による同じ件数構成での ENV-01 相当のリハーサル。本番の定義ファイル・本番環境での実施は移行工程")),
    ("GF-025", "違反を含む定義ファイルの失敗と修正版の再実行（切戻し）", "NFR-OM-13, NFR-MG-07, FR-060", "ADDR-010",
     "BATCH", "error-handling", "ManagementCommand>initial_data.loader>DB>AuditLog",
     "transaction=True。既存の利用者・仕入先。VDC-04 相当の定義ファイルの在庫単位400行目に違反（税抜価格 -1）",
     "--reset で違反版→修正版→修正版、指定なしで修正版",
     "1) 違反版を --reset で投入 2) 修正版を同じ指定で再実行 3) もう一度 4) 指定なしで再実行",
     "1) 失敗、違反（在庫単位 400行目・price_excluding_tax）を通知し何も投入・削除しない、監査ログ失敗1件、LOG-05 failure 2) 成功、件数が定義と一致、"
     "失敗から1時間以内 3) 成功、件数不変（重複なし） 4) 業務キーの重複で失敗し件数不変",
     ["RC-115"], f"{T}/test_it_gap_fill_nfr_batch.py::test_gf_025_failed_load_corrected_rerun",
     _NOTE_R2_PARTIAL.format(src="Traceability C10 の NFR 見直し", part="初期データ一括投入の再実行。バックアップの異常終了時の再実行（MON-07）は運用")),
    ("GF-026", "全機能の実行による LOG-01〜LOG-07 の出力・記録", "NFR-OM-11, FR-002, FR-030, FR-031, FR-060", "ADDR-007, ADDR-011, ADDR-013",
     "LOGGING", "api", "Services>AppLog/AuditLog/OrderStatusHistory",
     "transaction=True。アプリケーションログを捕捉。購入者・管理者",
     "ログイン成功・失敗、注文確定・支払・出荷・配達完了・キャンセル、入力エラー、注文確定中の障害、ログアウト、初期データ一括投入",
     "1) 各機能を実行 2) LOG-01〜03・06 の JSON 行、LOG-04（監査ログ）、LOG-07（注文状態履歴）を確認 3) 初期データ一括投入の LOG-05 を確認",
     "2) 全行に日時・重要度・種類・要求の識別子、LOG-01（処理名・開始/終了・結果、入力エラーの種類）、LOG-02（system_error・例外の種類・発生箇所）、"
     "LOG-03（メソッド・パス・状態・処理時間）、LOG-06（request/response）、監査ログ（ログイン成功・失敗・ログアウト）、"
     "状態履歴（注文受付→支払済→出荷済→配達完了、キャンセル済）3) LOG-05（initial_data_load・success・件数）と監査ログ（初期データ一括投入）",
     ["RC-116"], f"{T}/test_it_gap_fill_nfr_batch.py::test_gf_026_log_types_output",
     _NOTE_R2_PARTIAL.format(src="Traceability C10 の NFR 見直し", part="出力内容（ENV-01 相当）。保管期間（90日・1年・7年）は ENV-02 の運用")),
    ("GF-027", "環境ごとに異なる設定値の環境変数による変更", "NFR-OM-17", "ADDR-014",
     "CONFIG", "end-to-end-flow", "Environment>config.settings>Middleware/INSTALLED_APPS",
     "別プロセスで設定モジュールを読み込む（プログラムは変更しない）。秘密情報は実行ごとの乱数",
     "MINICOMMERCE_ENV・DJANGO_DEBUG・MINICOMMERCE_DEV_FEATURES・DJANGO_ALLOWED_HOSTS・DB_HOST/PORT/NAME の組合せ",
     "1) 本番プロファイルの値で読み込む 2) 開発プロファイル＋開発用機能 3) 本番で開発用機能・デバッグを有効 4) .env.example を確認",
     "1) 接続先・許可ホストが反映、デバッグ・開発用機能・試験支援モジュール無効、Secure Cookie・HSTS 有効 2) 試験支援モジュールが組み込まれる "
     "3) 設定エラーで起動しない 4) 秘密情報（DJANGO_SECRET_KEY・DB_USER・DB_PASSWORD）の値が空",
     ["RC-117"], f"{T}/test_it_gap_fill_nfr_batch.py::test_gf_027_env_specific_settings",
     _NOTE_R2_PARTIAL.format(src="Traceability C10 の NFR 見直し", part="設定値の反映。全設定項目の一覧の網羅性は構成・設定レビュー")),
    ("GF-028", "認証の手段（メールアドレス＋パスワード、失敗の区別なし、来訪者は認証不要）", "NFR-SC-12, FR-002, FR-011, FR-012", "ADDR-002, ADDR-003",
     "AUTH", "authentication", "API/Web>accounts.services",
     "購入者・管理者。公開商品",
     "正しい認証情報、誤ったパスワード、未登録のメールアドレス（API・画面）、来訪者の照会",
     "1) 購入者・管理者でログイン 2) 誤ったパスワード・未登録メールで API と画面からログイン 3) 来訪者で商品照会",
     "1) 200、利用者区分どおり 2) API は同じ 401 本文（type=authentication_failed）、画面は同じ文言（メールアドレスまたはパスワード） 3) 200",
     ["RC-118"], f"{T}/test_it_gap_fill_nfr_web.py::test_gf_028_auth_means",
     _NOTE_R2_PARTIAL.format(src="Traceability C10 の NFR 見直し", part="購入者・管理者・来訪者。運用者のサーバーへのログイン権限は運用（初期データ一括投入の Web/API 非公開は IT-055）")),
    ("GF-029", "JIS 第3・第4水準の漢字の登録・表示（画面・API）", "NFR-US-03, FR-001, FR-002, FR-030, FR-033", "ADDR-012",
     "WEB", "end-to-end-flow", "Web>accounts/orders.services>DB>Template",
     "CSRF 検証を有効にした画面クライアント",
     "氏名「𠮟𩸽 太郎」、受取人氏名「受取 𩸽𠮟」、住所1「𠮟町1-1」、住所2「𩸽荘101」",
     "1) 画面で会員登録・ログイン 2) 画面でカートに入れ注文確定 3) 画面と API で表示",
     "1) 登録・ログイン成功、ヘッダーに「𠮟𩸽 太郎さん」、lang=ja・charset=utf-8 2) 注文確定、DB に同じ文字 3) 注文詳細画面・API に同じ文字",
     ["RC-119"], f"{T}/test_it_gap_fill_nfr_web.py::test_gf_029_jis_level3_4_roundtrip",
     _NOTE_R2_PARTIAL.format(src="Traceability C10 の NFR 見直し", part="サーバー側の保存・出力。対応ブラウザでの字形表示は互換性・操作性テスト")),
    ("GF-030", "入力エラーの項目識別・全項目表示・入力値の保持", "NFR-US-04, FR-001, FR-030", "ADDR-012",
     "WEB", "api", "Web>accounts/orders.services",
     "CSRF 検証を有効にした画面クライアント。購入者のカートに1明細",
     "会員登録：メール形式不正・パスワード短い・確認不一致・氏名空。注文手続き：受取人氏名空・郵便番号不正・都道府県不正・電話番号不正",
     "1) 会員登録画面で送信 2) 注文手続き画面で送信 3) 項目の行ごとの理由・入力値を確認",
     "1)2) 400、誤りのある全項目の行に「項目名：理由」を1回で表示、誤りのない項目には表示しない、入力値を保持しパスワード欄は空",
     ["RC-120"], f"{T}/test_it_gap_fill_nfr_web.py::test_gf_030_input_error_identifiable_all",
     _NOTE_R2.format(src="Traceability C10 の NFR 見直し")),
    ("GF-031", "全画面の HTML の適合レベル A（機械判定可能な範囲）とキーボード操作可能な部品構成", "NFR-US-05, NFR-US-07, NFR-LG-08", "ADDR-012",
     "WEB", "api", "Web>Template(HTML structure)",
     "来訪者・購入者・管理者の画面クライアント。注文・カートのある状態",
     "SCR-001〜SCR-010・SCR-101〜SCR-103・SCR-901",
     "1) 各画面を表示 2) HTML を検査",
     "全画面で lang=ja、ページタイトル、フォーム部品のラベル関連付け、ボタン・リンクの文言、表見出し、画像の代替テキスト、正の tabindex なし、"
     "インラインのイベント処理なし（操作はネイティブのリンク・フォーム部品）",
     ["RC-121"], f"{T}/test_it_gap_fill_nfr_web.py::test_gf_031_accessible_html_structure",
     _NOTE_R2_PARTIAL.format(src="Traceability C10 の NFR 見直し", part="HTML の機械判定。チェックリストによる全達成基準の確認・キーボードだけでの実操作は互換性・操作性テスト")),
    ("GF-032", "商品一覧から支払完了までの画面数", "NFR-US-08, FR-011, FR-012, FR-021, FR-030, FR-031, FR-033", "ADDR-012",
     "WEB", "end-to-end-flow", "Web(SCR-001→002→005→006→007→008→010)",
     "ログイン済みの購入者の画面クライアント。在庫単位1件",
     "画面のリンク・フォームだけで操作（URL を直接入力しない）",
     "1) 商品一覧→商品詳細→カートに入れる→カート→注文手続き→注文確定→注文完了→支払→注文詳細 2) 経由した画面を数える",
     "経由した画面は7画面（商品一覧・商品詳細・カート・注文手続き・注文完了・支払・注文詳細）で、最後は支払済",
     ["RC-122"], f"{T}/test_it_gap_fill_nfr_web.py::test_gf_032_purchase_screen_count",
     _NOTE_R2.format(src="Traceability C10 の NFR 見直し")),
    ("GF-033", "取消できない5操作の確認の表示", "NFR-US-09, FR-023, FR-030, FR-034, FR-043, FR-044", "ADDR-012",
     "WEB", "api", "Web>Template(data-confirm)>site.js",
     "購入者・管理者の画面クライアント。注文受付・支払済・出荷済の注文、カート明細",
     "注文手続き・注文詳細・カート・注文詳細（管理）の画面",
     "1) 各画面を表示 2) 対象操作のフォームと確認の補助を確認",
     "注文確定・注文キャンセル・カート明細の削除・出荷登録・配達完了登録のフォームに確認文言（よろしいですか？）、全画面で site.js を読み込み、"
     "site.js は data-confirm の確認で承諾しない場合に送信を取り消す",
     ["RC-123"], f"{T}/test_it_gap_fill_nfr_web.py::test_gf_033_confirm_before_irreversible",
     _NOTE_R2_PARTIAL.format(src="Traceability C10 の NFR 見直し", part="確認の表示の構成。ブラウザでの確認ダイアログの操作と承諾しない場合のデータ変更0件は互換性・操作性テスト")),
    ("GF-034", "注文確定・支払の先着の応答後の同じ送信トークンでの逐次の再送（二重送信）", "NFR-US-10, FR-030, FR-031", "ADDR-004, ADDR-008, ADDR-012",
     "WEB", "database", "Web>SubmitToken>orders.services>payments.gateway(mock)",
     "CSRF 検証を有効にした購入者の画面クライアント。2回目は1回目の送信前に複製した Cookie・フォーム値（同じ送信トークン）を持つ別の"
     "クライアントから、1回目の応答を受け取った後に逐次に送る（使用済みトークンの判定経路。処理中の同時到着は再現しない：GF-039〜GF-043）",
     "注文確定・支払（承認）を同じ送信トークンで2回、別注文で否認後に承認",
     "1) 注文確定を2回（逐次） 2) 支払を2回（逐次） 3) 別注文で否認→新しい画面で承認",
     "1) 注文1件、先着は注文完了へ、後着（使用済みトークン）は再判定どおりカートが空としてカートへ遷移（ADDR-004 DD-010・DD-013、"
     "AC-UC-006-021） 2) 決済記録 承認1件、模擬機能への要求1回 3) 決済記録は否認・承認の2件、要求2回、支払済",
     ["RC-124"], f"{T}/test_it_gap_fill_flows.py::test_gf_034_double_submit_place_pay",
     _NOTE_R2.format(src="Traceability C10 の NFR 見直し") + "。cycle=2（QR-IT-1118-R1-001）で前提の記述を実際の手順（先着の応答後の"
     "逐次再送）に修正。RC-124 の「処理完了前（処理中）の繰り返し」は GF-039・GF-041 が確認する。cycle=3（QR-IT-1118-R2-001）で"
     "title と試験関数の docstring を実際の手順（先着の応答後の逐次再送。処理中の同時再送は GF-039〜GF-043）に修正"
     "（判定・期待値・Coverage は変更なし）"),
    ("GF-035", "実行環境の言語・フレームワーク・データベースの版", "NFR-EN-01, NFR-EN-02, NFR-EN-09", "ADDR-014",
     "CONFIG", "database", "Runtime>Django>PostgreSQL",
     "結合試験の実行環境（.venv の固定版、使い捨て PostgreSQL 16）",
     "なし",
     "1) 実行環境・Dockerfile・接続先 DB の版を確認 2) リポジトリのフロントエンドのビルド構成・静的ファイルを確認",
     "1) Python 3.12（Dockerfile も 3.12）、Django 5.2、DRF 3.15 以上、PostgreSQL 16 2) package.json 等のビルド構成なし、静的ファイルは site.css・site.js だけでモジュール読込なし",
     ["RC-125"], f"{T}/test_it_gap_fill_nfr_batch.py::test_gf_035_tech_stack_versions",
     _NOTE_R2_PARTIAL.format(src="Traceability C10 の NFR 見直し", part="結合試験の実行環境と構成ファイル。本番環境の版は構成・設定レビュー")),
    ("GF-036", "総額表示（税込価格の主表示・税抜の併記、消費税額と税込合計）", "NFR-LG-02, FR-011, FR-012, FR-020, FR-030, FR-033", "ADDR-012",
     "WEB", "end-to-end-flow", "Web>Template(price display)",
     "ログイン済みの購入者の画面クライアント。在庫単位（税抜1,000円）",
     "商品一覧・商品詳細・カート（×2）・注文手続き・注文完了・注文詳細",
     "1) 各画面を表示 2) 価格・消費税額・合計の表示を確認",
     "商品価格は「1,100円（税込）／1,000円（税抜）」、カート・注文手続き・注文詳細に消費税額250円・合計（税込）2,750円、注文完了に合計（税込）2,750円",
     ["RC-126"], f"{T}/test_it_gap_fill_nfr_web.py::test_gf_036_tax_inclusive_display",
     _NOTE_R2.format(src="Traceability C10 の NFR 見直し")),
    ("GF-037", "配送先の都道府県（JIS X 0401 の47コード）", "NFR-LG-09, FR-030, FR-033", "ADDR-001, ADDR-012",
     "API", "api", "API/Web>orders.services(prefecture)",
     "購入者。在庫単位",
     "prefecture=01・13・47、00・48・1・東京都・13（数値）・JP-13",
     "1) 各値で注文確定 2) 注文手続き画面の選択肢を確認",
     "1) 01・13・47 は 201 で名称（北海道・東京都・沖縄県）を返す、それ以外は 400（shipping_address.prefecture） 2) 選択肢は空＋01〜47 の47件",
     ["RC-127"], f"{T}/test_it_gap_fill_nfr_web.py::test_gf_037_jis_x0401_prefectures",
     _NOTE_R2.format(src="Traceability C10 の NFR 見直し")),
    ("GF-038", "決済連携部分（ゲートウェイの実装）の差し替え", "NFR-PF-17, FR-031, FR-043, FR-044", "ADDR-008",
     "API", "end-to-end-flow", "orders.services>payments.client>PaymentGateway(substitute)",
     "PaymentGateway の別実装（承認を返す）に get_gateway だけを差し替える。クーポン（定率10%）、在庫単位2件",
     "カート（1,800円×2、700円×1）＋クーポン、注文確定・支払・出荷・配達完了",
     "1) 注文確定 2) 支払 3) 出荷・配達完了 4) 注文の業務処理のソースが模擬機能を参照しないことを確認",
     "1) 小計4,300・割引430・送料500・消費税437・合計4,807円 2) 支払済、別実装が受けた要求は4項目（金額4,807円）、決済記録に別実装の取引参照番号、在庫は確定時の減算のまま "
     "3) 状態履歴 注文受付→支払済→出荷済→配達完了 4) orders.services は payments.mock を参照しない",
     ["RC-128"], f"{T}/test_it_gap_fill_flows.py::test_gf_038_gateway_substitution",
     _NOTE_R2_PARTIAL.format(src="Traceability C10 の NFR 見直し", part="境界の差し替えで業務処理が変わらないこと。実決済サービスとの連携は後続フェーズ・静的解析")),
]

_NOTE_R3 = (
    "Required Coverage Revision 3（QR-IT-1118-R1-001、NFR-US-10・ADDR-004 4.4 の検証方法・テスト行）で追加した Coverage の MISSING を補う"
    " GAP_FILL。先着が送信トークンのアドバイザリロックを保持して業務処理中であることと、後着が同じトークンのロック待ちに入った時点で"
    "先着・後着とも未完了であることを pg_locks で確認してから先着を進める"
)
_PRE_R3 = (
    "transaction=True（ADDR-011 DD-010）。CSRF 検証を有効にした画面クライアント。後着は先着の送信前に複製した Cookie・フォーム値"
    "（同じ送信トークン）を持つ別のクライアントから、別スレッド・別の DB 接続で送る。"
)
_IN_FLIGHT_STEPS = (
    "先着を送信し、送信トークンのロックを保持して{hold}ことを確認 2) 同じトークンの後着を送信し、後着が送信トークンのロック待ちに入り"
    "先着・後着とも未完了であることを確認 3) {release}"
)

_RAW_R3 = [
    ("GF-039", "支払（承認・否認）の処理中に同じ送信トークンの「支払う」を繰り返す", "NFR-US-10, FR-031", "ADDR-004, ADDR-008, ADDR-011",
     "CONCURRENCY", "database", "Web(同一トークン×別接続)>SubmitToken(advisory lock)>orders.services>payments.gateway(mock)",
     _PRE_R3 + "模擬決済の応答遅延3秒（試験用状態 payment_delay_seconds）。購入者のログイン状態。注文受付の注文を承認用・否認用に各1件",
     "SCR-008 の「支払う」（模擬決済の結果＝承認、否認）",
     "1) " + _IN_FLIGHT_STEPS.format(hold="模擬決済の応答待ち（決済要求の送信済み）である", release="応答遅延の経過で先着が終了し、後着が続く")
     + " 4) 承認・否認それぞれで応答・決済要求・決済記録・注文・状態履歴・送信トークンの記録を確認",
     "決済要求は各注文1回だけ。承認：先着 302 で注文詳細・「支払が完了しました。」、後着 302 で注文詳細・「この注文は支払できません"
     "（現在の状態：支払済）。」（E-031-05）、決済記録 承認1件（合計金額）、支払済・支払日時あり、履歴 注文受付→支払済。否認：先着・後着とも"
     " 422 で「決済が承認されませんでした。…再度お支払いください。」（後着は先着の結果 E-031-06）、決済記録 否認1件、注文受付のまま・履歴1件。"
     "送信トークンの記録は1件で先着の結果を保持",
     ["RC-129", "RC-124"], f"{T}/test_it_gap_fill_inflight.py::test_gf_039_inflight_repeat_pay_approved_declined", _NOTE_R3),
    ("GF-040", "支払の先着が E-031-08・結果の記録前の中断で終わる間の「支払う」の繰り返し", "NFR-US-10, FR-031", "ADDR-004, ADDR-008, ADDR-011",
     "CONCURRENCY", "error-handling",
     "Web(同一トークン×別接続)>SubmitToken(advisory lock・outcome)>orders.services>payments.gateway(mock)",
     _PRE_R3 + "模擬決済の応答遅延3秒。先着の要求の接続だけで注文状態履歴の INSERT を DB 障害にする（承認の反映途中の障害）。"
     "(b) ではさらに送信トークンの結果の記録（④）を中断させる",
     "SCR-008 の「支払う」（承認）",
     "(a) 1) " + _IN_FLIGHT_STEPS.format(hold="模擬決済の応答待ちである", release="先着は承認の反映で障害、後着が続く")
     + " 4) 応答・決済要求・決済記録・状態を確認 5) 支払画面を新たに表示して「支払う」（承認） "
     "(b) 先着の結果の記録前の中断で 1)〜4) と同様",
     "(a) 決済要求1回、先着・後着とも 500 システムエラー（後着は先着の結果 E-031-08）、決済記録0件・注文受付のまま・履歴1件、"
     "送信トークンの結果は E-031-08。5) 新しい送信トークンで新たな支払となり 302・支払済、決済要求は計2回・決済記録 承認1件 "
     "(b) 決済要求1回、先着・後着とも 500 システムエラー（後着は先着の結果の記録がないため E-031-08 とし再送信しない）、"
     "決済記録0件・注文受付のまま、送信トークンの結果は記録なし",
     ["RC-130"], f"{T}/test_it_gap_fill_inflight.py::test_gf_040_inflight_repeat_pay_system_error_and_interrupted", _NOTE_R3),
    ("GF-041", "注文確定の処理中に同じ送信トークンの「注文を確定する」を繰り返す", "NFR-US-10, FR-030", "ADDR-004, ADDR-011",
     "CONCURRENCY", "database", "Web(同一トークン×別接続)>SubmitToken(advisory lock)>orders.services(place_order)>DB",
     _PRE_R3 + "購入者の利用中カートに在庫単位（税抜1,000円、在庫10）×2。先着を業務処理中に留めるため利用中カートの行を別接続でロック",
     "SCR-006 の「注文を確定する」（配送先は有効な値）",
     "1) " + _IN_FLIGHT_STEPS.format(hold="利用中カートの行ロック待ち（注文確定の業務処理中）である", release="カートの行ロックを解放")
     + " 4) 応答・注文・在庫・カート・送信トークンの記録を確認",
     "注文1件（明細の数量2）、在庫 10→8（減算1回分）、カートは注文済。先着 302 で注文完了、後着 302 でカート画面・「カートに商品がありません。」"
     "（E-030-04、AC-UC-006-021）。送信トークンの記録は1件で先着の結果（成功・注文完了への遷移）",
     ["RC-131", "RC-124"], f"{T}/test_it_gap_fill_inflight.py::test_gf_041_inflight_repeat_place_order", _NOTE_R3),
    ("GF-042", "「カートに入れる」の処理中に同じ送信トークンで繰り返す", "NFR-US-10, FR-021", "ADDR-004, ADDR-011",
     "CONCURRENCY", "database", "Web(同一トークン×別接続)>SubmitToken(advisory lock)>carts.services(add_item)>DB",
     _PRE_R3 + "購入者の利用中カートに別の在庫単位×1。対象の在庫単位（在庫20）。先着を業務処理中に留めるため利用中カートの行を別接続でロック",
     "SCR-002 の「カートに入れる」（数量3）",
     "1) " + _IN_FLIGHT_STEPS.format(hold="利用中カートの行ロック待ちである", release="カートの行ロックを解放")
     + " 4) 応答・カート明細・送信トークンの記録を確認",
     "先着・後着とも 302 で商品詳細・「カートに追加しました（規格名、3個）。」（後着は加算せず先着の結果）。対象の明細の数量は3（1回分）、"
     "別の明細は1のまま、カートは1件。送信トークンの記録は1件で先着の結果（成功）",
     ["RC-132"], f"{T}/test_it_gap_fill_inflight.py::test_gf_042_inflight_repeat_cart_add", _NOTE_R3),
    ("GF-043", "先着が E-002-02 で終わる間の「ログイン」の繰り返し", "NFR-US-10, FR-002", "ADDR-004, ADDR-011",
     "AUTH", "authentication", "Web(同一トークン×別接続)>SubmitToken(advisory lock)>accounts.services(login_web)>AuditLog",
     _PRE_R3 + "未ログインのブラウザ。購入者1名。先着を業務処理中に留めるため監査ログの表を別接続でロック（SHARE）",
     "SCR-004 に購入者のメールアドレスと誤ったパスワード",
     "1) " + _IN_FLIGHT_STEPS.format(hold="ログイン失敗の監査ログの記録待ちである", release="監査ログの表のロックを解放")
     + " 4) 応答・監査ログ・両ブラウザのログイン状態・送信トークンの記録を確認",
     "先着・後着とも 401 で「メールアドレスまたはパスワードが正しくありません。」（後着は照合せず先着の結果 E-002-02）。login_failure は1件"
     "（対象利用者＝購入者）、login_success 0件、どちらのブラウザもログイン状態なし（保護画面は SCR-004 へ）。送信トークンの記録は1件で"
     "E-002-02、メールアドレス・パスワードを含まない",
     ["RC-133"], f"{T}/test_it_gap_fill_inflight.py::test_gf_043_inflight_repeat_login_failure", _NOTE_R3),
]


_NOTE_R4 = (
    "Required Coverage Revision 4 の MISSING を補う GAP_FILL（FULL Traceability C10 の差し戻し、UNRESOLVED-e1d9dfe900863622 "
    "修正 cycle=1/3）。要件が「該当なし」と定める NFR は根拠の前提だけ、構成・設定レビュー／静的解析を検証方法とする NFR は"
    "リポジトリ内で確かめられる部分だけを確認する（要件の合否・本番環境は判定しない。nfr-verification-scope.json）"
)
T4 = f"{T}/test_it_gap_fill_nfr_config.py"

_RAW_R4 = [
    ("GF-044", "定期的に実行するバッチ処理・定期ジョブの定義が無い", "NFR-PF-12, NFR-AV-01", "ADDR-014",
     "CONFIG", "end-to-end-flow", "compose.yaml(app,db)>Dockerfile>requirements*.txt>manage.py commands",
     "リポジトリの compose.yaml・app/Dockerfile・app/requirements*.txt・設定（INSTALLED_APPS）。Docker Compose の CLI（変数は展開しない）",
     "なし（起動定義・依存・管理コマンドの一覧）",
     "1) docker compose config で compose.yaml を解釈 2) Dockerfile・依存の固定・INSTALLED_APPS を確認 3) 本システムの管理コマンドを列挙",
     "1) サービスは app・db だけ、app の起動は「migrate → collectstatic → exec gunicorn」だけ、db は既定の起動 2) 定期実行の仕組み"
     "（cron・スケジューラ）・定期実行ライブラリ・アプリケーションなし 3) 管理コマンドは changepassword・createsuperuser（無効化）・"
     "load_initial_data・test_state（手動実行）だけ",
     ["RC-134"], f"{T4}::test_gf_044_no_scheduled_batch"),
    ("GF-045", "画面・API にファイルをアップロードする機能が無い", "NFR-SC-28", "ADDR-001, ADDR-012",
     "API", "api", "API(JsonBodyParser)/Web(Template)>Models",
     "購入者1名（Bearer）、在庫単位1件（在庫5）。全モデル・全テンプレート・Production Code",
     "POST /api/auth/register/ と POST /api/cart/items/ に multipart（ファイル添付 evil.html・cart.csv）",
     "1) 全モデルのファイル項目、全テンプレートのファイル選択部品・multipart、Production Code の request.FILES 参照、API の本文の解釈を確認 "
     "2) 会員登録 API にファイル付き multipart 3) カート明細追加 API にファイル付き multipart 4) DB を確認",
     "1) ファイル項目0件、ファイル選択部品・multipart 0件、FILES 参照0件、API の本文は application/json だけ 2)3) 400 input_error "
     "4) 利用者は増えない、カート明細0件",
     ["RC-135"], f"{T4}::test_gf_045_no_file_upload"),
    ("GF-046", "メールアドレス＋パスワードだけでログインが完了し、失敗を続けてもロックしない", "NFR-SC-13, NFR-SC-14",
     "ADDR-002, ADDR-003",
     "AUTH", "authentication", "API/Web>accounts.services>AuditLog",
     "購入者1名。CSRF 検証を有効にした画面クライアント",
     "誤ったパスワード Wrong0Pass9（API・画面で各10回）、正しいパスワード",
     "1) API で誤ったパスワードのログインを10回 2) 正しいパスワードでログインし利用者情報照会 3) 画面のログインフォームの入力項目を確認 "
     "4) 画面で誤ったパスワードを10回 5) 正しいパスワードでログインしカートを表示 6) 監査ログを確認",
     "1) 各 401 authentication_failed 2) 200 で token・expires_at・user だけを返し（追加の認証要素を求める項目なし）、その Bearer で"
     "利用者情報照会 200 3) 入力項目はメールアドレス・パスワードだけ 4) 各 401 5) 302 で /、カート 200 6) login_failure が20件"
     "（対象利用者＝購入者）、login_success が2件",
     ["RC-136"], f"{T4}::test_gf_046_single_factor_login_without_lockout"),
    ("GF-047", "多要素認証・パスワードの変更／再設定・特定商取引法の表記の要求先が無い", "NFR-SC-13, NFR-SC-17, NFR-LG-04",
     "ADDR-001, ADDR-012",
     "WEB", "api", "URLconf(API/Web)>management commands>Template",
     "購入者1名。画面クライアント・API クライアント",
     "GET /password_change/・/password_reset/・/accounts/password/reset/・/mfa/・/tokushoho/、POST /api/auth/password/・"
     "/api/auth/password-reset/・/api/auth/mfa/・/api/auth/otp/、manage.py changepassword <購入者のメールアドレス>",
     "1) 全 URL パターンを列挙 2) 各要求先へ要求 3) changepassword を実行しパスワードの保持値を確認 4) 全テンプレートを確認",
     "1) password・reset・otp・mfa・2fa・totp・tokushoho 等を含むパターン0件 2) すべて 404 3) CommandError で終了し保持値は不変 "
     "4) 「特定商取引」の表記0件",
     ["RC-137"], f"{T4}::test_gf_047_out_of_scope_functions_absent"),
    ("GF-048", "同一の送信元からの連続要求を送信元単位で制限しない", "NFR-SC-27", "ADDR-001",
     "API", "api", "API/Web>Middleware>DRF settings",
     "公開中の商品1件。同一の試験クライアント（同一送信元）",
     "GET /api/products/ ×120、GET / ×60、POST /api/auth/login/（未登録メールアドレス）×30",
     "1) DRF の設定・ミドルウェアに送信元単位の制限が無いことを確認 2) 連続要求を送り応答を確認",
     "1) 制限の設定なし 2) 429 は0件。商品一覧 API・画面は全件 200、ログイン失敗は全件 401",
     ["RC-138"], f"{T4}::test_gf_048_no_per_source_rate_limit"),
    ("GF-049", "決済サービスは本システム内の模擬機能で、外部の決済サービスへの接続の設定・手段を持たない", "NFR-AV-10, NFR-LG-10",
     "ADDR-008",
     "API", "api", "orders.services>payments.client>payments.gateway>payments.mock",
     "購入者1名（Bearer）、在庫単位1件（税抜1,200円、在庫5）。.env.example・app/requirements.txt",
     "支払（模擬決済指示＝承認）",
     "1) 使用するゲートウェイの実装と所在を確認 2) payments の各モジュールの読込み、依存、設定項目を確認 3) 注文を確定して支払",
     "1) payments.mock の MockPaymentGateway（app/payments 内） 2) 外部通信のモジュール・決済の連携ライブラリ・接続先・認証情報の"
     "設定項目なし 3) 200 で支払済、決済記録 承認1件・取引参照番号は MOCK-（英数字16桁）",
     ["RC-139"], f"{T4}::test_gf_049_payment_is_in_process_mock"),
    ("GF-050", "1回の起動操作で app・db を起動する定義、起動は Gunicorn、WSGI が商品一覧画面を返す",
     "NFR-EN-03, NFR-OM-05, NFR-EN-08", "ADDR-014",
     "CONFIG", "end-to-end-flow", "compose.yaml(app,db)>Dockerfile>gunicorn.conf>config.wsgi",
     "Docker Compose の CLI（変数は展開しない）。公開中の商品1件（起動確認の商品）",
     "GET /（gunicorn.conf.py の wsgi_app を WSGI で直接呼ぶ）",
     "1) compose.yaml を解釈しサービス・依存・起動コマンドを確認 2) Dockerfile・gunicorn.conf.py・依存を確認 3) wsgi_app で / を要求",
     "1) app・db の2サービス、db はダイジェスト固定の postgres:16・pg_isready の正常性確認、app は db の正常性確認後に migrate→"
     "collectstatic→exec gunicorn、開発用サーバー（runserver）なし 2) CMD は gunicorn、wsgi_app=config.wsgi:application・bind 0.0.0.0:8000・"
     "sync、gunicorn を固定、クラウド基盤の SDK なし 3) 200 で商品一覧画面（起動確認の商品）",
     ["RC-140"], f"{T4}::test_gf_050_compose_single_start_gunicorn"),
    ("GF-051", "Production Code が特定の OS に固有のモジュール・パス表記に依存しない", "NFR-EN-07", "ADDR-014",
     "CONFIG", "end-to-end-flow", "app(production code)>Python stdlib>Dockerfile",
     "app/ の Production Code（試験・マイグレーションを除く）、app/Dockerfile",
     "なし（ソースコードの構文解析）",
     "1) 全モジュールの import を解析 2) 文字列定数の絶対パスを確認 3) ベースイメージを確認",
     "1) fcntl・pwd・grp・msvcrt・winreg 等の OS 固有モジュール0件 2) OS 固有の絶対パス0件 3) python:3.12-slim（ダイジェスト固定）",
     ["RC-141"], f"{T4}::test_gf_051_os_independent_code"),
    ("GF-052", "依存・実行環境の取得元と版が特定でき同じ構成を再現できる（VUL-10）、採用製品の版", "NFR-SC-21, NFR-EN-10",
     "ADDR-014",
     "CONFIG", "end-to-end-flow", "requirements*.txt>Dockerfile>compose.yaml>.venv>dependency-inventory",
     "app/requirements.txt・requirements-dev.txt、app/Dockerfile、compose.yaml、試験環境（.venv）、docs/operations/dependency-inventory.md",
     "なし",
     "1) 依存の各行が版固定・ハッシュ付きか確認 2) 試験環境の版と照合 3) Dockerfile・compose のイメージと取得方法を確認 4) 依存の一覧と照合",
     "1) 全件 ==・sha256 ハッシュ付き 2) 全件一致 3) python:3.12-slim・postgres:16 はダイジェスト固定、pip install --require-hashes "
     "4) 実行時依存の版が一覧と一致、Django 5.2.x（2028-04）・Python 3.12（2028-10）・PostgreSQL 16（2028-11）",
     ["RC-142"], f"{T4}::test_gf_052_pinned_reproducible_dependencies"),
    ("GF-053", "固定した全依存ライブラリのライセンスが特定でき、AGPL が無い", "NFR-EN-12", "ADDR-014",
     "CONFIG", "end-to-end-flow", "requirements*.txt>.venv(package metadata)",
     "試験環境（.venv）に固定版の依存が入っている",
     "なし",
     "1) 固定した全依存のパッケージのメタデータ（License-Expression・License・Classifier）を読む",
     "1) ライセンス不明0件、AGPL・Affero 0件",
     ["RC-143"], f"{T4}::test_gf_053_dependency_licenses"),
    ("GF-054", "リポジトリの規約設定で全ソースコードを静的解析し違反0件", "NFR-EN-11", "ADDR-014",
     "CONFIG", "end-to-end-flow", "ruff.toml>ruff>repository sources",
     "ruff.toml、試験環境の ruff（固定版）",
     "ruff check --no-cache .（リポジトリ直下）",
     "1) ruff.toml の規則選択を確認 2) 静的解析を実行",
     "1) E・W（pycodestyle）を含む 2) 終了コード 0・All checks passed",
     ["RC-144"], f"{T4}::test_gf_054_static_analysis_zero"),
    ("GF-055", "プロセス数を環境変数だけで増強でき、ログイン状態・カートを別のプロセスからも参照できる", "NFR-PF-16",
     "ADDR-002, ADDR-014",
     "CONFIG", "database", "gunicorn.conf(GUNICORN_WORKERS)>SessionStore(DB)>ApiLoginState(DB)>Cart(DB)",
     "購入者1名、在庫単位1件（在庫10）。コミット方式（transaction=True）",
     "GUNICORN_WORKERS 未設定・6、カートに数量2、別プロセス（python -c）から同じ Cookie・Bearer で要求",
     "1) gunicorn.conf.py のプロセス数を確認 2) セッションの保持先を確認 3) API・画面でログインしカートに追加 "
     "4) 別プロセスから画面のカート・カート照会 API を要求",
     "1) 未設定 2・6 を指定で 6 2) データベース保持 4) 画面 200 で商品を表示、API 200 で数量2の明細1件",
     ["RC-145"], f"{T4}::test_gf_055_scale_out_keeps_user_state"),
    ("GF-056", "リポジトリの初期データ・試験用利用者は架空の値（予約済みドメイン）だけで作る", "NFR-SC-25",
     "ADDR-009, ADDR-011",
     "CONFIG", "database", "seed/initial_data.json>tests fixtures",
     "app/seed/initial_data.json、試験フィクスチャ make_user",
     "なし",
     "1) 初期データの利用者のメールアドレスとファイル中の全メールアドレスのドメインを確認 2) 試験用の利用者を作成",
     "1) 全件 @example.com、他のドメインなし 2) @example.test",
     ["RC-146"], f"{T4}::test_gf_056_fictional_initial_data"),
    ("GF-057", "開発・検証環境向けの手順書に必要な手順があり、参照先が存在し、初期データ一括投入の手順が成功する",
     "NFR-OM-19", "ADDR-010, ADDR-014",
     "CONFIG", "end-to-end-flow", "README(ENV-01 手順)>.env.example>compose.yaml>manage.py>pytest/ruff",
     "README.md の MiniCommerce（開発・検証環境の手順）。コミット方式（transaction=True）",
     "load_initial_data <app/seed/initial_data.json> --reset",
     "1) 手順書の節に7種の手順があるか確認 2) 参照する設定項目・ファイル・サービス・コマンドの存在を確認 3) 初期データ一括投入の手順を実行",
     "1) 設定の作成・構築・起動・停止・DB の初期化・初期データ一括投入・自動テスト・静的解析の手順あり 2) すべて存在 "
     "3) 終了コード 0、「初期データ一括投入が成功しました。」",
     ["RC-147"], f"{T4}::test_gf_057_dev_procedure_document"),
    ("GF-058", "注文明細・配送先・決済記録・注文状態履歴は登録後に変わらず、注文の更新は状態・日時・伝票番号だけ", "NFR-LG-03",
     "ADDR-004, ADDR-012",
     "DATABASE", "state-transition",
     "API>orders.services>DB(OrderItem/ShippingAddress/PaymentRecord/OrderStatusHistory)",
     "購入者・管理者各1名（Bearer）、在庫単位1件（税抜1,800円、在庫10）",
     "注文A（数量2）：支払 否認→承認→出荷登録（LG03-1）→配達完了登録。注文B（数量1）：支払 承認→管理者キャンセル",
     "1) 注文確定後に注文・明細・配送先・決済記録・履歴を記録 2) 各操作の後に再取得し比較",
     "否認 422・決済記録+1・履歴+0。承認・出荷・配達完了・キャンセルは各 200・履歴+1（承認は決済記録+1）。明細・配送先は不変、"
     "決済記録・履歴は既存行が不変で追記のみ、注文の変更項目は状態・支払/出荷/配達完了/キャンセル日時・配送伝票番号だけ",
     ["RC-148"], f"{T4}::test_gf_058_order_records_immutable"),
]


_NOTE_R5 = (
    "Required Coverage Revision 5 の MISSING を補う GAP_FILL（FULL Traceability C10 の差し戻し、UNRESOLVED-e1d9dfe900863622 "
    "修正 cycle=2/3）。開発環境の PC（Windows 11・インストール済みの Edge/Chrome）と使い捨て PostgreSQL 16 で要件の測定条件に"
    "沿って行う参考計測・操作確認と、Production Code・設定・起動定義の機械確認。合格扱いにしない（PARTIAL_IT。本番環境・運用記録・"
    "運用体制・法令判断・診断ツールによる診断は nfr-verification-scope.json の verify_in の工程で確認する）"
)
T5B = f"{T}/test_it_gap_fill_nfr_browser.py"
T5P = f"{T}/test_it_gap_fill_nfr_perf.py"
T5O = f"{T}/test_it_gap_fill_nfr_ops.py"
T5R = f"{T}/test_it_gap_fill_nfr_recovery.py"

_RAW_R5 = [
    ("GF-059", "Windows 11 の PC の Edge・Chrome で、1280×720 の表示領域に全画面を横スクロールなく表示し、代表操作を行える",
     "NFR-US-01, NFR-US-02, NFR-US-06", "ADDR-012, ADDR-014",
     "WEB", "end-to-end-flow", "Browser(Edge/Chrome, Windows 11)>Web>Static",
     "開発環境の PC（Windows 11）にインストール済みの Microsoft Edge・Google Chrome（ヘッドレス、CDP で操作）。live_server。購入者・"
     "別の購入者・管理者・商品2件・在庫単位3件・クーポン（ブラウザごと）、注文受付の注文と支払済の注文（ブラウザごとに作成）",
     "表示領域 1280×720・表示倍率 100%。会員登録の入力（架空のメールアドレス・パスワード）、配送先、クーポンコード、配送伝票番号",
     "1) OS を確認 2) 各ブラウザで来訪者として SCR-001・SCR-002・SCR-003 を表示し会員登録、SCR-901（対象なし）・SCR-004 を表示 "
     "3) 購入者としてログイン→商品詳細→カートに入れる→カート→クーポン適用→注文手続き→注文確定（確認ダイアログ）→支払画面→支払→"
     "注文履歴→注文詳細→キャンセル（確認ダイアログ）→ログアウト 4) 管理者としてログイン→在庫単位一覧→注文詳細→出荷登録・配達完了登録"
     "（確認ダイアログ）→注文一覧→ログアウト 5) 各表示で主文書の状態・資源の読込・スクリプトの例外・外部への要求・横スクロールを確認",
     "1) Windows 11（ビルド 22000 以上） 2)〜4) 全画面（14画面）が想定の状態（SCR-901 は 404、他は 200）・遷移先で表示され、資源の"
     "読込失敗・スクリプトの例外・コンソールのエラー・外部への要求が0件、文書の幅が表示領域の幅以下で表示領域外の要素なし、lang=ja・"
     "UTF-8。確認ダイアログは各ブラウザで4回（注文確定・キャンセル・出荷登録・配達完了登録） 5) 配達完了2件・支払済2件",
     ["RC-149"], f"{T5B}::test_gf_059_browser_compatibility"),
    ("GF-060", "全画面（14画面）の表示完了時間の95パーセンタイル（Edge・Chrome で各30回。単一利用者の参考計測）", "NFR-PF-03",
     "ADDR-012",
     "PERF", "end-to-end-flow", "Browser(Edge/Chrome)>Web>Static",
     "GF-059 と同じ PC・ブラウザ（ヘッドレス、キャッシュ無効）。live_server。購入者・管理者・注文受付と支払済の注文、カートに明細1件",
     "各画面の URL（SCR-001〜SCR-010、SCR-101〜SCR-103、SCR-901）",
     "1) 来訪者で SCR-003・SCR-004 を各30回表示 2) 購入者でログインし SCR-001・002・005〜010・901 を各30回表示 3) 管理者でログインし "
     "SCR-101〜103 を各30回表示 4) Navigation Timing（画面要求の開始〜load イベント終了）を記録",
     "全画面・両ブラウザで各30回の表示が想定の状態で問題なし、画面ごとの95パーセンタイルが 2,000ミリ秒以内（参考計測。"
     "browser-reference.json に記録）",
     ["RC-150"], f"{T5B}::test_gf_060_screen_display_time_reference"),
    ("GF-061", "3年後データ量（VDC-01〜VDC-03）での API・画面の応答時間（単一利用者の参考計測）", "NFR-PF-06", "ADDR-001",
     "PERF", "database", "API/Web>services>DB(3年後データ量)",
     "使い捨て PostgreSQL 16 に COPY で 3年後相当のデータ（会員 10,000・管理者 7・商品 600・在庫単位 1,600・商品分類 45・仕入先 35・"
     "クーポン 150・注文 110,000・注文明細 330,000・配送先 110,000・決済記録 約120,000・注文状態履歴 約330,000〜360,000）を生成し ANALYZE",
     "照会系9種・更新系4種・画面7種（各50回以上。検索条件・ページを変える）",
     "1) データを生成し件数を確認 2) 照会系 API 9種を各50回 3) カート明細追加・注文確定・支払・出荷登録を各50回以上 4) 画面 7種を各50回 "
     "5) 種別ごとの95パーセンタイルを記録",
     "1) 件数が VDC-01〜VDC-03 どおり（注文関連は ±10%） 2)〜4) 全要求が 200/201 5) 照会 1.0秒・更新 2.0秒・画面 2.0秒以内"
     "（参考計測。performance-reference.json に記録）",
     ["RC-151"], f"{T5P}::test_gf_061_three_year_data_volume_reference"),
    ("GF-062", "同時155利用者（思考時間5〜15秒）の負荷での応答時間・注文確定の処理能力・資源使用量・応答時間の推移（参考計測）",
     "NFR-PF-05, NFR-PF-04, NFR-PF-14, NFR-PF-15, NFR-PF-03", "ADDR-001, ADDR-011",
     "PERF", "end-to-end-flow", "VirtualUsers(155)>HTTP>Web/API>DB",
     "live_server・使い捨て PostgreSQL 16（コミット方式）。在庫単位 200（在庫 99,999）・クーポン、購入者 150・管理者 5、到着用の購入者、"
     "管理者用の支払済 40・注文受付 20 の注文。DB のコンテナ名（IT_DB_CONTAINER）",
     "思考時間 5〜15秒、300秒間。注文確定の到着 15秒間隔（3明細・5点）。負荷中に Edge で購入者の画面を繰り返し表示",
     "1) 155の仮想利用者を開始（購入者は照会：更新＝8：2＋認証系、管理者は注文一覧検索・詳細・出荷・配達完了・キャンセル・在庫単位一覧） "
     "2) 注文確定を一定間隔で到着させる 3) ブラウザで SCR-001・002・005・009 を表示 4) 10秒ごとに資源使用量を記録 5) 集計",
     "システムエラー（5xx・接続失敗）0件、全要求が想定の成功応答、照会 1.0秒・更新 2.0秒・認証 2.0秒以内（95パーセンタイル）、"
     "到着した注文確定（20件）が全件 201、ブラウザ表示が全件 200 で95パーセンタイル 2.0秒以内、資源使用量の記録あり。最初と最後の"
     "60秒の95パーセンタイル・メモリ使用量を記録（参考計測）",
     ["RC-152"], f"{T5P}::test_gf_062_concurrent_users_reference"),
    ("GF-063", "想定の2倍（310仮想利用者）の負荷で、システムエラー率・在庫数量・金額整合を確認する（参考計測）", "NFR-PF-11",
     "ADDR-004, ADDR-011",
     "PERF", "database", "VirtualUsers(310)>HTTP>API>orders.services>DB",
     "live_server・使い捨て PostgreSQL 16（コミット方式）。在庫数量 5 の在庫単位 40、購入者 300・管理者 10、管理者用の注文",
     "思考時間 5〜15秒、120秒間（業務エラーを許容）",
     "1) 310の仮想利用者で負荷をかける 2) 負荷終了後に全在庫単位の在庫数量・全注文の金額整合・在庫の増減と注文明細を確認",
     "システムエラーとなる応答の割合 1%以下、在庫不足の業務エラーが発生、在庫数量が0未満の在庫単位 0件、金額整合を満たさない注文 0件、"
     "在庫の減少量＝キャンセル以外の注文明細の数量（参考計測）",
     ["RC-153"], f"{T5P}::test_gf_063_overload_consistency_reference"),
    ("GF-064", "固定した全依存ライブラリを公開脆弱性情報（OSV）と照合し、CVSS 7.0 以上の既知の脆弱性が0件", "NFR-SC-11",
     "ADDR-014",
     "CONFIG", "end-to-end-flow", "requirements*.txt>OSV(公開脆弱性情報)>PyPI",
     "実行前に tools/fetch_dependency_vulns.py で OSV・PyPI から取得し固定した照合結果（dependency-vulnerability-osv.json）",
     "app/requirements.txt・requirements-dev.txt",
     "1) 照合結果の取得状態と requirements の SHA-256 を確認 2) 照合した版と固定した版を照合 3) 版の実在（PyPI）を確認 4) 脆弱性の"
     "重大度（CVSS v3 の基本値・重大度）を判定",
     "1) FETCHED・SHA-256 一致 2) 全件一致（23件） 3) 全件 200 4) CVSS 7.0以上・HIGH/CRITICAL・重大度不明が0件",
     ["RC-154"], f"{T5O}::test_gf_064_dependency_known_vulnerabilities"),
    ("GF-065", "個人情報をログ・ファイル・外部へ出さず、参照は本人と管理者に限られる", "NFR-LG-01",
     "ADDR-001, ADDR-012, ADDR-013",
     "SECURITY", "authentication", "API/Web>services>Logging>URLconf>socket",
     "在庫単位1件。管理者1名。架空の個人情報（メールアドレス・氏名・パスワード・受取人・住所・電話番号）",
     "会員登録（誤り・成功）、ログイン（失敗・成功）、注文確定（配送先）、支払、照会、管理者の購入者メールアドレス検索・注文詳細",
     "1) 一連の操作を行い、アプリケーションログ・応答・URL 構成・送信先を記録 2) 別の購入者・来訪者で注文を参照",
     "1) ログに個人情報・パスワード0件、ファイルとして出力する応答・要求先0件、外部への接続0件 2) 別の購入者 API 404・画面 404、"
     "来訪者 API 401・画面 302、別の購入者の管理者 API 403。注文は支払済",
     ["RC-155"], f"{T5O}::test_gf_065_personal_information_handling"),
    ("GF-066", "全画面・全 API への簡易な動的診断（アクセス制御・CSRF・注入・XSS・内部情報・ヘッダー）と外部要求の部品の不存在",
     "NFR-SC-29, NFR-LG-07", "ADDR-001, ADDR-002, ADDR-012",
     "SECURITY", "api", "Web/API(全要求先)>Middleware>services",
     "購入者・別の購入者・管理者、在庫単位1件・クーポン、注文受付の注文（購入者）・支払済の注文（別の購入者）・カート明細",
     "全 URL パターン（44件）、攻撃文字列8種（スクリプト・属性・SQL・コマンド・パス・テンプレート・NUL・長大な全角数字）",
     "1) 来訪者・購入者・別の購入者・管理者で全要求先へ参照の要求 2) 更新 API を来訪者・購入者で要求 3) 画面の更新操作14件を CSRF "
     "トークンなしで送り、同じ要求先へ GET 4) 検索条件・パス・本文・フォームへ攻撃文字列 5) スクリプトを含む氏名の利用者で画面を表示 "
     "6) Production Code の外部通信の部品を確認",
     "システムエラー0件、無害化されない反映0件、内部情報の露出0件、全応答に nosniff・DENY・same-origin。管理者用は来訪者 401/302・"
     "購入者 403、他の購入者の注文は 404、更新 API は来訪者 401・購入者（管理者用）403、CSRF トークンなしは全件 403・データ変更なし、"
     "外部通信の部品0件",
     ["RC-156"], f"{T5O}::test_gf_066_dynamic_probe_all_screens_and_apis"),
    ("GF-067", "保存データの所在がデータベースだけ（ファイルへの保存・ファイル型のセッション/キャッシュ・ログファイルなし）",
     "NFR-SC-20", "ADDR-002, ADDR-006, ADDR-013, ADDR-014",
     "CONFIG", "database", "settings>Models>Sessions>Logging>production code",
     "Production Code・設定（tests.settings_test 経由の config.settings）・gunicorn.conf.py", "なし",
     "1) DB 接続・モデルのファイル項目・セッション・メッセージ・キャッシュ・ログのハンドラーを確認 2) Production Code のファイル書込みを確認",
     "1) DB は PostgreSQL の1件、ファイル項目0件、セッションは DB 保持、メッセージはセッション保持、キャッシュはファイル型・DB 型なし、"
     "ログは標準出力・Null だけ 2) ファイル書込み0件、Gunicorn の accesslog なし・errorlog は標準エラー",
     ["RC-157"], f"{T5O}::test_gf_067_persistent_data_only_in_database"),
    ("GF-068", "アプリケーションログ（LOG-01〜03・05・06）は標準出力への1行1件の JSON（日時・種類付き）で、アプリ内で削除しない",
     "NFR-OM-02", "ADDR-008, ADDR-010, ADDR-013",
     "CONFIG", "end-to-end-flow", "Logging(stdout JSON)>gunicorn.conf>production code",
     "購入者1名・在庫単位1件。試験用状態（注文確定の障害点）。コミット方式", "架空の定義ファイル（仕入先1件）",
     "1) 照会・対象なし・注文確定・支払・障害点ありの注文確定・初期データ一括投入を行う 2) ログの行・ハンドラー・Gunicorn の設定・"
     "Production Code のログ削除を確認",
     "1) LOG-01・02・03・05・06 が出力 2) 全行が1行の JSON・日時（+09:00、ミリ秒）・種類あり、要求のログに要求の識別子、ハンドラーは"
     "StreamHandler（標準出力）・NullHandler だけでファイル型なし、ログの削除・ローテーションの処理なし",
     ["RC-158"], f"{T5O}::test_gf_068_application_log_output"),
    ("GF-069", "監査ログは DB に追記のみで記録され、本システムのどの処理も削除・更新しない（1年保管の前提）", "NFR-OM-03",
     "ADDR-006, ADDR-010, ADDR-012",
     "DATABASE", "database", "AuditLog(DB)>initial_data(--reset)>production code",
     "購入者1名。コミット方式", "ログイン失敗・成功・ログアウト、架空の定義ファイルで --reset",
     "1) 監査ログを3件記録 2) 初期データ一括投入（--reset） 3) 更新・削除を試す 4) 外部キーと Production Code の削除経路を確認",
     "1) login_failure・login_success・logout 2) 既存の3件が変わらず1件（initial_data_load）増加、発生日時はタイムゾーン付き "
     "3) 一括削除・一括更新・1件削除・保存し直しはすべて拒否 4) 外部キー0件、削除・更新・TRUNCATE の経路0件",
     ["RC-159"], f"{T5O}::test_gf_069_audit_log_retention_premise"),
    ("GF-070", "利用者向けサービス（画面・API）は1つの待受けだけで提供し、本番プロファイルでは HTTPS 以外を拒否する。管理用の別口なし",
     "NFR-SC-26", "ADDR-012, ADDR-014",
     "CONFIG", "end-to-end-flow", "URLconf>HttpsOnlyMiddleware>gunicorn.conf>Dockerfile",
     "在庫単位1件。本番プロファイル（IS_PRODUCTION）・許可ホストを試験内で設定", "全 URL パターン（44件）を HTTP・HTTPS で要求",
     "1) 本番プロファイルで全要求先へ HTTP で要求 2) HTTPS で代表の要求先へ要求 3) Gunicorn の待受け・Dockerfile・URL 構成を確認",
     "1) 全件 403 2) 200 3) bind は 0.0.0.0:8000 の1件、EXPOSE 8000 だけ、遠隔ログインのソフトウェアなし、管理サイト・デバッグ用の"
     "要求先なし、非 root で実行",
     ["RC-160"], f"{T5O}::test_gf_070_single_https_user_service"),
    ("GF-071", "初期データ一括投入は投入時点の在庫数量（定義ファイルの値）をそのまま反映し、更新後の値で再投入すると置き換わる",
     "NFR-MG-05", "ADDR-009, ADDR-010",
     "DATABASE", "database", "load_initial_data>loader>StockUnit",
     "コミット方式。試験用状態の現在日時（2027-03-29 12:30、2027-03-31 17:30）",
     "架空の定義ファイル2件（在庫数量 12・0・7 と 9・30・0）",
     "1) 1件目を --reset で投入 2) 2件目を --reset で投入 3) 在庫数量を確認",
     "1)2) 終了コード 0 3) 各投入後の在庫数量が定義ファイルの値と一致、在庫単位は3件",
     ["RC-161"], f"{T5O}::test_gf_071_initial_load_reflects_stock_sheet"),
    ("GF-072", "3年後相当のデータで、サービスを止めずに全データを取得し、全データの喪失後に取得時点へ復元して全業務を再開する",
     "NFR-AV-04, NFR-AV-07, NFR-AV-08, NFR-AV-12, NFR-PF-13", "ADDR-001, ADDR-011",
     "DATABASE", "database", "DB(PostgreSQL 16)>pg_dump/pg_restore>API/Web/initial_data",
     "使い捨て PostgreSQL 16（コミット方式、コンテナ内で pg_dump・pg_restore）。3年後相当のデータを COPY で生成。購入者・監査ログ",
     "取得前の注文（目印）、取得中の要求（3並列、照会・カート・注文確定）、取得後の注文（目印）",
     "1) 取得前の目印の注文を作る 2) 要求を送りながら pg_dump で取得 3) 取得後の目印の注文を作る 4) スキーマを削除（全データの喪失）"
     "して pg_restore で復元 5) 件数・目印を確認 6) 全業務（来訪者・購入者・管理者・初期データ一括投入）を行う",
     "2) 取得中の要求（10件以上）が全件成功 4) 復元できる 5) 全テーブルあり、件数が取得の前後の間、監査ログあり、取得前の目印あり・"
     "取得後の目印なし 6) 全業務が成功。取得・復元の所要時間を記録（リストア 4時間以内）",
     ["RC-162"], f"{T5R}::test_gf_072_backup_restore_and_resume"),
    ("GF-073", "3年後相当のデータで、データ構造の変更を含む更新と、更新直前の状態への切戻しを行い所要時間を計測する", "NFR-OM-15",
     "ADDR-014",
     "CONFIG", "database", "migrations(catalog 0002)>pg_dump/pg_restore>Web/API",
     "使い捨て PostgreSQL 16（コミット方式）。3年後相当のデータを COPY で生成。catalog を 0001 に戻した状態を更新前とする",
     "migrate（catalog 0002 の適用）",
     "1) 更新前の状態で pg_dump 2) migrate で更新し画面・API を確認 3) 更新直前のバックアップから切戻し 4) データ構造・件数・画面/API を確認 "
     "5) 最新の状態へ戻す",
     "2) 制約・適用記録あり、200 3)4) 制約・適用記録なし、件数が更新前と一致、200 5) 制約あり。取得・更新・起動確認・切戻しの合計が"
     "120分以内（参考計測）",
     ["RC-163"], f"{T5R}::test_gf_073_update_and_rollback"),
]


def _case(cid, title, req, adr, cat, crit, ip, pre, inp, steps, exp, rcs, test, note, key_by_id):
    return {
        "case_id": cid,
        "origin": "AI_GENERATED",
        "generation_stage": "GAP_FILL",
        "title": title,
        "requirement_id": req,
        "related_adr": adr,
        "test_category": cat,
        "criterion": crit,
        "integration_point": ip,
        "precondition": pre,
        "input": inp,
        "steps": steps,
        "expected_result": exp,
        "execution_type": "AUTOMATABLE",
        "notes": note,
        "coverage_ids": list(rcs),
        "coverage_keys": [key_by_id[r] for r in rcs],
        "automated_test": test,
    }


def build_cases(key_by_id: dict[str, str]) -> list[dict]:
    cases = [
        _case(*row, NOTES.get(row[0], _NOTE_R1), key_by_id)
        for row in _RAW
    ]
    cases += [_case(*row, key_by_id) for row in _RAW_R2]
    cases += [_case(*row, key_by_id) for row in _RAW_R3]
    cases += [_case(*row, _NOTE_R4, key_by_id) for row in _RAW_R4]
    cases += [_case(*row, _NOTE_R5, key_by_id) for row in _RAW_R5]
    return cases
