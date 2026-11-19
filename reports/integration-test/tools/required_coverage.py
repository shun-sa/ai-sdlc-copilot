"""Required Integration Test Coverage（RUN-AOBA-EC-1118）。

要件（docs/requirements の FR・CMN・UC の AC・NFR）と ACTIVE の ADDR（ADDR-001〜014）から導出した、
結合試験で確認すべき連携の一覧。AI INITIAL Case・External Case から逆算していない（Integration Test Skill Step 5）。
各項目の coverage_key は requirement_id・integration_point・test_category・criterion・condition から生成する（Step 13）。
"""

# (coverage_id, requirement_id, related_adr, integration_point, test_category, criterion, condition, expected_behavior)
_RAW = [
    # --- 会員・認証（Web API） ---
    ("RC-001", "FR-001, FR-002", "ADDR-001, ADDR-003", "API>accounts.services>DB", "API", "end-to-end-flow", "register-then-login",
     "会員登録（201、利用者区分=購入者、メールアドレスは前後空白除去・英小文字化）した利用者が同じパスワードでログインでき、パスワードは平文で保持されない（FR-001、CMN-06、AC-UC-001-001/003/015）"),
    ("RC-002", "FR-001", "ADDR-004", "API>accounts.services>DB(unique)", "DATABASE", "database", "duplicate-normalized-email",
     "正規化後に同一となるメールアドレスの登録は 422 business_error/email_already_registered とし利用者は増えない（E-001-02、AC-UC-001-004）"),
    ("RC-003", "FR-001", "ADDR-004", "MultiConnection>DB(unique)", "CONCURRENCY", "database", "concurrent-same-email",
     "同一メールアドレスの同時登録は1件だけ成功し、他方は email_already_registered（CMN-19、AC-UC-001-017、ADDR-004 DD-009）"),
    ("RC-004", "FR-001", "ADDR-001", "API>accounts.services", "API", "api", "input-errors-all-fields",
     "複数項目の入力不備は 400 input_error で fields に全項目を1回で通知し、利用者を作成しない（CMN-16、AC-UC-001-011）"),
    ("RC-005", "FR-002, FR-004", "ADDR-001, ADDR-002", "API>BearerAuthentication>accounts.services", "AUTH", "authentication", "login-token-me",
     "ログイン成功で token・expires_at（ログイン時刻+24時間）・user を返し、その Bearer で利用者情報照会が本人の情報を返す（FR-002、FR-004、AC-UC-002-001/013）"),
    ("RC-006", "FR-002", "ADDR-002, ADDR-004, ADDR-007", "API>accounts.services>AuditLog", "DATABASE", "database", "audit-login-success-failure",
     "ログイン成功・失敗を監査ログ（login_success/login_failure、結果、対象利用者。未登録メールは null）に記録し、入力値・トークンを記録しない（CMN-24/25、AC-UC-002-007）"),
    ("RC-007", "FR-002", "ADDR-001", "API>accounts.services", "AUTH", "authentication", "failure-indistinguishable",
     "誤パスワードと未登録メールアドレスは同一の 401 authentication_failed・同一文言で区別しない（CMN-05、AC-UC-002-005）"),
    ("RC-008", "FR-003", "ADDR-002", "API>BearerAuthentication>accounts.services", "AUTH", "authentication", "logout-invalidates-only-own",
     "ログアウト（204）した状態の要求は 401、同じ利用者の別のログイン状態は有効のまま、監査ログに logout（CMN-11/12、AC-UC-002-009/010）"),
    ("RC-009", "FR-002, FR-004", "ADDR-002, ADDR-011", "API>BearerAuthentication>Clock(TestState)", "AUTH", "authentication", "token-expiry-24h-boundary",
     "ログイン時刻+24時間未満は有効、ちょうど24時間で 401 authentication_required（CMN-09/29、AC-UC-002-011）"),
    ("RC-010", "FR-004, FR-020, FR-030, FR-040, FR-041", "ADDR-001, ADDR-002", "API>BearerAuthentication>Permission", "AUTH", "authentication", "permission-matrix",
     "未ログインは 401、購入者の /api/admin/ は 403、管理者のカート・注文（購入者）API は 403（5.1 権限表、CMN-02/03、AC-UC-002-014）"),
    ("RC-011", "FR-021", "ADDR-001", "API>BearerAuthentication>Validation", "AUTH", "authentication", "auth-before-input",
     "未ログインの入力不正の要求は入力エラーより先に認証エラー（401）とする（CMN-14、AC-UC-004-021）"),
    ("RC-012", "FR-020", "ADDR-001, ADDR-002", "API>CookieSession(rejected)", "AUTH", "authentication", "api-rejects-cookie-session",
     "/api/ は画面のセッション Cookie を認証に使わず、Bearer なしの要求は 401（ADDR-001 4.3 の3、ADDR-002 4.3 の5）"),
    # --- 会員・認証（画面） ---
    ("RC-013", "FR-001", "ADDR-004, ADDR-012", "Web>CSRF>accounts.services>DB", "WEB", "end-to-end-flow", "web-register-redirect-login",
     "画面（SCR-003）の会員登録完了で SCR-004 へ遷移し完了メッセージを表示する（MSG-02、AC-UC-001-002）"),
    ("RC-014", "FR-001", "ADDR-012", "Web>accounts.services", "WEB", "api", "web-register-input-error-retains",
     "画面の会員登録の入力エラーは項目ごとに理由を表示し、入力値を保持（パスワードは保持しない）（CMN-17、UI-19、AC-UC-001-018）"),
    ("RC-015", "FR-002", "ADDR-002, ADDR-012", "Web>Session>accounts.services", "AUTH", "authentication", "web-login-home-by-type",
     "画面ログイン成功で購入者は SCR-001（/）、管理者は SCR-102（/manage/orders/）へ遷移する（AC-UC-002-003）"),
    ("RC-016", "FR-002", "ADDR-002", "Web>Session>Redirect(next)", "AUTH", "authentication", "web-return-to-original",
     "未ログインで保護画面を要求すると SCR-004（ログインが必要な旨）へ遷移し、ログイン後に元の画面へ戻る（CMN-02、UI-17、AC-UC-002-016）"),
    ("RC-017", "FR-002", "ADDR-002", "Web>Session>Cookie", "AUTH", "authentication", "session-cookie-httponly",
     "画面のログイン状態の Cookie は HttpOnly（スクリプトから参照不可）・SameSite=Lax（NFR-SC-19、AC-UC-002-021）"),
    ("RC-018", "FR-002", "ADDR-012", "Web>accounts.services", "AUTH", "authentication", "web-login-failure-message",
     "画面ログイン失敗は SCR-004 に区別しないメッセージ、メールアドレスを保持しパスワードは保持しない（AC-UC-002-017）"),
    ("RC-019", "FR-003", "ADDR-002, ADDR-012", "Web>Session>AuditLog", "AUTH", "end-to-end-flow", "web-logout",
     "画面ログアウトで SCR-001 へ遷移し「ログアウトしました。」、監査ログに logout、以後の保護画面は SCR-004（UI-20、AC-UC-002-018）"),
    ("RC-020", "FR-002, FR-020", "ADDR-002, ADDR-011", "Web>IdleTimeoutMiddleware>Clock(TestState)", "AUTH", "authentication", "idle-timeout-30min",
     "画面のログイン状態は無操作30分未満なら継続し、30分経過で切断して SCR-004 へ遷移する（CMN-10、NFR-SC-09、AC-UC-002-015）"),
    ("RC-021", "FR-040, FR-020", "ADDR-012", "Web>Permission", "AUTH", "authentication", "web-permission-scr901",
     "購入者の管理画面、管理者の購入者向け画面は SCR-901（権限なし、HTTP 403）（UI-18、CMN-03）"),
    ("RC-022", "FR-021", "ADDR-002", "Web>CSRF", "AUTH", "error-handling", "csrf-reject",
     "CSRF トークンを伴わない画面の更新要求は拒否され、業務データは変化しない（NFR-SC-05、ADDR-002 4.3 の5）"),
    ("RC-023", "FR-002", "ADDR-004", "Web>SubmitToken>accounts.services>AuditLog", "DATABASE", "database", "login-double-submit",
     "同じ送信トークンのログイン再送は照合・監査ログ記録・新たなログイン状態の開始を行わず、先着の結果を通知する（ADDR-004 DD-013/016、CMN-22）"),
    # --- 商品カタログ ---
    ("RC-024", "FR-010", "ADDR-001", "API>catalog.services>DB", "API", "api", "category-tree-order",
     "全商品分類を親子の木構造の順（表示順・同値は登録順）で depth・parent_category_id 付きで返す（FR-010、AC-UC-003-001）"),
    ("RC-025", "FR-011", "ADDR-001", "API>catalog.services>DB", "API", "api", "product-search-target-filter",
     "公開かつ在庫単位を持つ商品だけを返し、分類指定は配下分類を含み重複せず、キーワードは商品名・説明の部分一致（英字大小区別なし）（AC-UC-003-003/004/005）"),
    ("RC-026", "FR-011", "ADDR-001", "API>catalog.services>DB", "API", "api", "product-search-sort-paging",
     "並び順4種（同値は登録順）、1ページ20件、総ページ数を超えるページは空の一覧（AC-UC-003-007/008、CMN-35）"),
    ("RC-027", "FR-011", "ADDR-001", "API>catalog.services", "API", "api", "product-search-input-errors",
     "不正な並び順・ページ番号・未登録の分類ID・51文字のキーワードは 400 input_error で全項目を通知（AC-UC-003-009〜012）"),
    ("RC-028", "FR-012", "ADDR-001, ADDR-006", "API>catalog.services>DB", "API", "api", "product-detail-contract",
     "商品詳細は在庫単位を SKU 昇順で、税込価格（1円未満切捨て）・在庫数量付きで返し、仕入先を含まない（AC-UC-003-013/015、MSG-04）"),
    ("RC-029", "FR-012", "ADDR-001, ADDR-006", "API>catalog.services", "API", "error-handling", "product-detail-not-found",
     "非公開・在庫単位なし・存在しない・識別子として解釈できない商品は 404 not_found で区別しない（AC-UC-003-016、CMN-18）"),
    ("RC-030", "FR-011, FR-012", "ADDR-012", "Web/API>catalog.services", "E2E", "end-to-end-flow", "same-result-all-actors-and-screen",
     "来訪者・購入者・管理者で同じ結果を返し、画面は税込価格を主表示し税抜価格を併記する（AC-UC-003-017/019、UI-25）"),
    # --- カート ---
    ("RC-031", "FR-020", "ADDR-001, ADDR-004", "API>carts.services>DB", "DATABASE", "database", "get-cart-creates-single",
     "利用中カートがない購入者のカート照会は空のカートを1件だけ作成し、再照会しても1件（AC-UC-004-020、ADDR-001 DD-015/016）"),
    ("RC-032", "FR-020", "ADDR-004", "MultiConnection>DB(partial unique)", "CONCURRENCY", "database", "concurrent-get-cart",
     "同じ購入者のカート照会を同時に行っても利用中カートは1件（6.8.9、ADDR-004 4.3 の4）"),
    ("RC-033", "FR-021", "ADDR-001, ADDR-004", "API>carts.services>DB", "API", "database", "add-merge-limit-stock",
     "明細追加で明細を作成し在庫数量は減らない、同一在庫単位は合算、合算10は可・11は quantity_limit_exceeded、在庫超過は insufficient_stock（AC-UC-004-001〜010）"),
    ("RC-034", "FR-021", "ADDR-001", "API>carts.services>DB", "API", "api", "add-not-found-unpublished",
     "存在しない在庫単位・非公開商品の在庫単位の追加は 404 not_found（AC-UC-004-013）"),
    ("RC-035", "FR-021", "ADDR-004", "MultiConnection>DB(lock)", "CONCURRENCY", "database", "concurrent-add-limit",
     "同一在庫単位の同時追加でも合算数量は10個を超えない（AC-UC-004-025）"),
    ("RC-036", "FR-022, FR-023", "ADDR-001, ADDR-006", "API>carts.services>DB", "API", "api", "change-delete-ownership",
     "数量変更・削除が反映され金額を再計算、他の購入者・存在しない・注文済カートの明細は 404（AC-UC-004-005/014/015）"),
    ("RC-037", "FR-026, FR-020", "ADDR-001", "API>carts.services>carts.pricing", "API", "api", "amounts-shipping-tax",
     "小計4,999円は送料500円・消費税額549円・合計6,048円、小計5,000円は送料0円・消費税額500円・合計5,500円（AC-UC-004-017/018）"),
    ("RC-038", "FR-024", "ADDR-001, ADDR-011", "API>carts.services>Clock(TestState)>DB", "STATE", "state-transition", "coupon-validity-boundaries",
     "有効開始日時ちょうど・有効終了日時ちょうどは適用でき、開始1秒前は coupon_not_yet_valid、終了1秒後は coupon_expired（AC-UC-005-012〜015）"),
    ("RC-039", "FR-024", "ADDR-001", "API>carts.services>DB", "API", "api", "coupon-errors",
     "空カート（cart_empty）・適用済み（coupon_already_applied）・コードなし（coupon_not_found）・最低購入金額未満（最低購入金額と小計を通知）・形式不正（400）（AC-UC-005-007〜011/017）"),
    ("RC-040", "FR-024, FR-025, FR-026", "ADDR-001", "API>carts.services>carts.pricing", "STATE", "state-transition", "coupon-applicability-recalc",
     "適用後に数量を減らし最低購入金額を下回ると割引額0・is_applicable=false（クーポンは残る）、再び満たすと割引を算出（AC-UC-005-020/021）"),
    ("RC-041", "FR-025", "ADDR-001", "API>carts.services>DB", "API", "api", "coupon-remove",
     "クーポン解除で割引額0円に再計算、未適用での解除はエラーにせず変化なし（AC-UC-005-018/019）"),
    ("RC-042", "FR-020, FR-021, FR-022, FR-023, FR-024, FR-025", "ADDR-012, ADDR-004", "Web>carts.services>DB", "WEB", "end-to-end-flow", "web-cart-operations",
     "画面でカートに入れる（完了メッセージ・カート（n点））→数量変更→クーポン適用・解除→削除が反映される（AC-UC-004-023、AC-UC-005-026）"),
    ("RC-043", "FR-021", "ADDR-012", "Web/API>carts.services", "API", "api", "same-rule-web-api",
     "画面と Web API で同じ数量上限・在庫の判定結果となる（CMN-34、FCN-09）"),
    ("RC-044", "FR-021", "ADDR-004", "Web>SubmitToken>carts.services", "DATABASE", "database", "cart-add-double-submit",
     "同じ送信トークンの「カートに入れる」再送は数量を加算しない（ADDR-004 DD-013、UI-15）"),
    # --- 注文確定 ---
    ("RC-045", "FR-030, FR-026", "ADDR-001, ADDR-004, ADDR-005", "API>orders.services>DB", "DATABASE", "database", "place-order-persistence",
     "注文確定は 201、注文受付、全明細の在庫減算、注文明細・配送先（正規化）・状態履歴（なし→注文受付）、カート注文済、注文番号 PO-8桁で確定順に増加（AC-UC-006-001/006）"),
    ("RC-046", "FR-030", "ADDR-001", "API>orders.services", "API", "api", "place-order-input-errors",
     "配送先の不備は全項目を 400 で通知し何も変更しない（AC-UC-006-008〜012）"),
    ("RC-047", "FR-030", "ADDR-004", "API>orders.services>DB", "STATE", "state-transition", "place-order-empty-and-resend",
     "空カートは cart_empty（配送先の入力判定が先）、同一カートの再送信は2件目 cart_empty で注文1件（AC-UC-006-013/021）"),
    ("RC-048", "FR-030", "ADDR-004, ADDR-011", "API>orders.services>DB", "DATABASE", "database", "place-order-business-errors-no-change",
     "非公開→クーポン条件→在庫の順に判定し、在庫不足は不足する全在庫単位を通知、いずれも何も変更しない（AC-UC-006-014〜018/032）"),
    ("RC-049", "FR-030", "ADDR-004", "MultiConnection>DB(lock)", "CONCURRENCY", "database", "concurrent-place-stock1",
     "在庫数量1を2名が同時確定すると1件だけ成功し在庫0、他方は insufficient_stock（AC-UC-006-019）"),
    ("RC-050", "FR-030", "ADDR-004", "MultiConnection>DB(lock)", "CONCURRENCY", "database", "concurrent-place-10",
     "同一在庫単位への10並列確定で引当合計は在庫数量を超えず在庫は0未満にならない（AC-UC-006-020、NFR-PF-07）"),
    ("RC-051", "FR-030", "ADDR-004", "MultiConnection>DB(lock)", "CONCURRENCY", "database", "concurrent-same-cart",
     "同一カートの同時確定で注文は1件、他方は cart_empty（CMN-23、6.15.9）"),
    ("RC-052", "FR-030", "ADDR-004, ADDR-011, ADDR-013", "API>orders.services>FaultPoint(TestState)>DB", "ERROR", "error-handling", "place-order-fault-rollback",
     "確定途中の障害は 500 system_error（内部情報なし）、在庫・注文・カートは処理前のまま、LOG-02 に記録（E-030-11、AC-UC-006-022）"),
    ("RC-053", "FR-030, FR-033", "ADDR-012", "Web>orders.services", "WEB", "end-to-end-flow", "web-checkout-complete",
     "画面で確定すると SCR-007 に注文番号と合計を表示し、カートの合計点数は0点（MSG-02、6.15.5）"),
    ("RC-054", "FR-030", "ADDR-012", "Web>orders.services", "WEB", "api", "web-checkout-input-error-retains",
     "画面の配送先不備は項目ごとの理由を表示し入力値を保持して再表示する（AC-UC-006-028）"),
    ("RC-055", "FR-030", "ADDR-004", "Web>SubmitToken>orders.services", "DATABASE", "database", "web-place-double-submit",
     "同じ送信トークンで確定を繰り返しても注文は1件（CMN-22、AC-UC-006-026、ADDR-004 DD-010）"),
    # --- 支払 ---
    ("RC-056", "FR-031", "ADDR-008, ADDR-004, ADDR-007", "API>orders.services>payments.gateway(mock)>DB", "STATE", "state-transition", "pay-approved",
     "承認で支払済・支払日時、決済記録 approved（取引参照番号 MOCK-+16文字）、履歴（注文受付→支払済）、在庫不変（AC-UC-007-001/003）"),
    ("RC-057", "FR-031", "ADDR-008", "API>orders.services>payments.gateway(mock)>DB", "STATE", "state-transition", "pay-declined-then-retry",
     "否認は 422 payment_declined、注文受付のまま否認の決済記録が残り、再支払（承認）で支払済（AC-UC-007-004/005）"),
    ("RC-058", "FR-031", "ADDR-008, ADDR-011", "API>orders.services>payments.client(timeout 10s)", "ERROR", "error-handling", "pay-timeout",
     "10秒以内に応答しない場合は 502 integration_error、連携エラーの決済記録、注文受付のまま（AC-UC-007-014）"),
    ("RC-059", "FR-031", "ADDR-008, ADDR-011", "API>orders.services>payments.client(response check)", "ERROR", "error-handling", "pay-invalid-response",
     "応答不正（結果不正・欠落・取引参照番号不正等）は 502 integration_error と連携エラーの決済記録（AC-UC-007-015、IF-01-EXC-04）"),
    ("RC-060", "FR-031", "ADDR-001, ADDR-004", "API>orders.services", "STATE", "state-transition", "pay-invalid-status",
     "支払済・出荷済・配達完了・キャンセル済への支払は 422 invalid_status（現在の状態を通知）、決済記録は増えない（AC-UC-007-006/007）"),
    ("RC-061", "FR-031", "ADDR-001", "API>orders.services", "AUTH", "authentication", "pay-ownership-permission",
     "他人・存在しない注文は 404、管理者は 403、模擬決済指示の不正は所有判定より先に 400（AC-UC-007-008〜011）"),
    ("RC-062", "FR-031", "ADDR-004, ADDR-008", "MultiConnection>DB(lock)", "CONCURRENCY", "database", "concurrent-pay",
     "同一注文への同時支払で承認の決済記録は1件、後着は invalid_status（AC-UC-007-013）"),
    ("RC-063", "FR-031, FR-034", "ADDR-004", "MultiConnection>DB(lock)", "CONCURRENCY", "database", "concurrent-pay-cancel",
     "同一注文への支払とキャンセルの同時実行は逐次実行のいずれかの順序の結果と一致（AC-UC-007-019）"),
    ("RC-064", "FR-031", "ADDR-012, ADDR-008", "Web>orders.services>payments.gateway(mock)", "WEB", "end-to-end-flow", "web-payment",
     "画面で否認は SCR-008 に理由、続けて承認で SCR-010 へ遷移し支払完了の旨（AC-UC-007-002/005）"),
    ("RC-065", "FR-031", "ADDR-004", "Web>SubmitToken>payments.gateway(mock)", "DATABASE", "database", "web-pay-double-submit",
     "同じ送信トークンで「支払う」を繰り返しても決済要求・決済記録は1回分（UI-15、ADDR-004 DD-013）"),
    # --- 注文照会・キャンセル ---
    ("RC-066", "FR-032", "ADDR-001", "API>orders.services>DB", "API", "api", "history-own-desc-paging",
     "本人の注文だけを注文日時降順（同値は注文番号降順）、1ページ20件、総ページ数超過は空、不正ページは 400（AC-UC-008-001〜005）"),
    ("RC-067", "FR-033", "ADDR-001", "API>orders.services>DB", "API", "api", "detail-contents",
     "注文詳細は明細（追加順）・金額・クーポン・配送先・状態履歴（昇順）・can_pay/can_cancel、未発生日時は null、決済記録を含まない（AC-UC-008-006〜009/015、MSG-04）"),
    ("RC-068", "FR-033, FR-030", "ADDR-001", "API>orders.services>DB", "DATABASE", "database", "price-fixed-at-confirm",
     "確定後に在庫単位の税抜価格が変わっても注文の単価・金額は確定時点のまま（AC-UC-006-005）"),
    ("RC-069", "FR-034", "ADDR-004", "API>orders.services>DB", "STATE", "state-transition", "buyer-cancel",
     "注文受付・支払済のキャンセルでキャンセル済、全明細の数量を在庫へ戻し履歴を記録、支払済でも決済記録は不変（AC-UC-009-001/002）"),
    ("RC-070", "FR-034", "ADDR-004", "API>orders.services", "STATE", "state-transition", "buyer-cancel-invalid",
     "出荷済・配達完了・キャンセル済は 422 invalid_status、在庫は2回戻らない（AC-UC-009-005/006）"),
    ("RC-071", "FR-034", "ADDR-004", "MultiConnection>DB(lock)", "CONCURRENCY", "database", "concurrent-cancel",
     "同一注文への同時キャンセルで在庫は1回だけ戻る（AC-UC-009-007）"),
    ("RC-072", "FR-034", "ADDR-012", "Web>orders.services", "WEB", "end-to-end-flow", "web-buyer-cancel",
     "画面（SCR-010）のキャンセルで完了メッセージを表示し、在庫が戻る（AC-UC-009-003）"),
    # --- 管理 ---
    ("RC-073", "FR-040", "ADDR-001", "API>catalog.services>DB", "API", "api", "stock-list-filter-paging",
     "非公開を含む全在庫単位を SKU 昇順、SKU 前方一致・商品名部分一致（大小区別なし）・仕入先完全一致・低在庫のみ（5含む6含まない）、1ページ50件（AC-UC-010-001〜007）"),
    ("RC-074", "FR-040", "ADDR-001", "API>catalog.services", "API", "api", "stock-list-input-errors",
     "未登録の仕入先・低在庫のみの値不正・ページ不正は 400 input_error で全項目（AC-UC-010-009）"),
    ("RC-075", "FR-040, FR-030, FR-034", "ADDR-004", "API>orders.services>catalog.services>DB", "E2E", "end-to-end-flow", "stock-reflects-orders",
     "注文確定・キャンセル後の在庫数量が在庫単位一覧に反映される（AC-UC-010-008）"),
    ("RC-076", "FR-041", "ADDR-001", "API>orders.services>DB", "API", "api", "admin-order-search",
     "全購入者の注文を降順、注文番号完全一致、注文状態複数、注文日 JST 両端含む、メール部分一致（大小区別なし）、条件は「かつ」（AC-UC-011-001〜008）"),
    ("RC-077", "FR-041", "ADDR-001", "API>orders.services", "API", "api", "admin-order-search-errors",
     "注文日（開始）＞注文日（終了）、日付形式不正、注文番号形式不正は 400 input_error（AC-UC-011-005）"),
    ("RC-078", "FR-042", "ADDR-001, ADDR-007", "API>orders.services>DB", "API", "api", "admin-detail-contents",
     "注文詳細（管理）は購入者情報・決済記録・状態履歴（actor_user_id）・can_ship/can_deliver を含む（AC-UC-011-009）"),
    ("RC-079", "FR-043", "ADDR-004", "API>orders.services>DB", "STATE", "state-transition", "ship",
     "支払済→出荷済、出荷日時・配送伝票番号（省略可）を記録、在庫・決済記録は不変、履歴の実行者は管理者（AC-UC-011-010/012）"),
    ("RC-080", "FR-043", "ADDR-001", "API>orders.services", "API", "api", "ship-tracking-validation",
     "配送伝票番号は30文字まで受け付け、31文字・不正な文字は 400 input_error（AC-UC-011-013）"),
    ("RC-081", "FR-044", "ADDR-004", "API>orders.services>DB", "STATE", "state-transition", "deliver",
     "出荷済→配達完了、配達完了日時と履歴を記録（AC-UC-011-015）"),
    ("RC-082", "FR-045, FR-033", "ADDR-004", "API>orders.services>DB", "E2E", "end-to-end-flow", "admin-cancel-visible-to-buyer",
     "管理者キャンセルで在庫が戻り、購入者が注文詳細でキャンセル済と履歴（実行者=管理者）を確認できる（AC-UC-012-001/002/004）"),
    ("RC-083", "FR-031, FR-034, FR-043, FR-044, FR-045", "ADDR-004", "API>orders.services", "STATE", "state-transition", "invalid-transitions-matrix",
     "遷移表にない遷移は 422 invalid_status（現在の状態）とし、状態・在庫・履歴・決済記録を変更しない（8.1.2）"),
    ("RC-084", "FR-043, FR-045", "ADDR-004", "MultiConnection>DB(lock)", "CONCURRENCY", "database", "concurrent-ship-and-cancel-ship",
     "同一注文への同時出荷登録は1件だけ成功、管理者キャンセルと出荷登録の同時実行はどちらか一方だけ成功（AC-UC-011-020、AC-UC-012-010）"),
    ("RC-085", "FR-045, FR-034", "ADDR-004", "MultiConnection>DB(lock)", "CONCURRENCY", "database", "concurrent-admin-buyer-cancel",
     "管理者キャンセルと購入者キャンセルの同時実行で在庫は1回だけ戻る（AC-UC-012-009）"),
    ("RC-086", "FR-041, FR-042, FR-043, FR-044, FR-045", "ADDR-012, ADDR-004", "Web>orders.services(admin)", "WEB", "end-to-end-flow", "web-admin-operations",
     "画面で注文一覧（管理）→注文詳細（管理）→出荷登録→配達完了登録、別注文のキャンセルが反映され完了メッセージを表示（AC-UC-011-011、AC-UC-012-003）"),
    # --- 一連の業務フロー ---
    ("RC-087", "FR-001, FR-002, FR-011, FR-012, FR-021, FR-024, FR-030, FR-031, FR-032, FR-033, FR-041, FR-042, FR-043, FR-044", "ADDR-001, ADDR-002, ADDR-004, ADDR-008", "API(all)>Services>DB", "E2E", "end-to-end-flow", "api-full-flow",
     "会員登録→ログイン→商品検索→カート→クーポン→注文確定→支払→管理者の出荷・配達完了→購入者の照会まで Web API でデータが引き継がれる"),
    ("RC-088", "FR-002, FR-012, FR-021, FR-030, FR-031, FR-033, FR-043, FR-044", "ADDR-012, ADDR-004, ADDR-008", "Web(all)>Services>DB", "E2E", "end-to-end-flow", "web-full-flow",
     "画面で購入者の購入〜支払、管理者の出荷・配達完了、購入者の状態確認までが連携する"),
    # --- 初期データ一括投入 ---
    ("RC-089", "FR-060, FR-002", "ADDR-009, ADDR-010, ADDR-003", "ManagementCommand>initial_data.loader>DB>AuditLog", "BATCH", "end-to-end-flow", "load-success-login",
     "投入件数の表示が定義ファイルと一致し、投入した利用者が記載パスワードでログインでき、監査ログに成功（件数、値なし）を記録（AC-UC-013-001/002/008）"),
    ("RC-090", "FR-060, FR-011, FR-040", "ADDR-009", "ManagementCommand>initial_data.loader>DB>API", "BATCH", "end-to-end-flow", "load-defaults-visibility",
     "省略項目は既定値で登録し、非公開の商品は商品一覧に出ず在庫単位一覧には出る（AC-UC-013-003）"),
    ("RC-091", "FR-060", "ADDR-010, ADDR-002, ADDR-004", "ManagementCommand>initial_data.loader>DB", "BATCH", "database", "reset-deletes-all",
     "--reset 指定で監査ログ以外（注文・カートを含む）を削除して投入し、削除前のログイン状態は無効（AC-UC-013-004、ADDR-002 4.3 の6）"),
    ("RC-092", "FR-060", "ADDR-009, ADDR-010", "ManagementCommand>initial_data.loader>DB", "BATCH", "error-handling", "violations-all-no-insert",
     "値域・参照・定義内重複の違反を全件（データ名・行番号・項目名・理由、値なし）示し何も投入しない、--reset でも削除しない、監査ログに失敗（AC-UC-013-006/007）"),
    ("RC-093", "FR-060", "ADDR-010", "ManagementCommand>initial_data.loader>DB", "BATCH", "error-handling", "duplicate-existing-key",
     "削除指定なしで業務キーが既存データと重複するとエラーとなり何も投入しない（AC-UC-013-005）"),
    ("RC-094", "FR-060", "ADDR-010", "ManagementCommand>initial_data.loader>AuditLog", "BATCH", "error-handling", "args-read-format-errors",
     "実行時の指定誤り（E-060-01）・読込不可（E-060-02）・記載形式誤り（E-060-03）は失敗とし既存データ不変、監査ログに失敗1件（AC-UC-013-009）"),
    ("RC-095", "FR-060", "ADDR-010", "Web/API>URLRouting", "AUTH", "authentication", "no-web-api-entry",
     "初期データ一括投入は Web 画面・Web API から実行できない（AC-UC-013-011、NFR-SC-15）"),
    ("RC-096", "FR-060", "ADDR-009, ADDR-010", "ManagementCommand>initial_data.loader>DB", "BATCH", "database", "seed-file-loadable",
     "提供済みの定義ファイル（app/seed/initial_data.json）を投入でき、データ別件数が定義ファイルと一致する（Steering 4章、FR-060）"),
    # --- 横断（NFR） ---
    ("RC-097", "NFR-OM-18, NFR-OM-01", "ADDR-013", "Middleware>AppLog", "LOGGING", "api", "request-id-correlation",
     "応答に X-Request-ID、同一要求の全ログ行が同一 request_id、LOG-03 の path は検索条件を含まない（ADDR-013 4.3 の1・2）"),
    ("RC-098", "NFR-SC-06", "ADDR-013", "Service>AppLog", "LOGGING", "error-handling", "no-sensitive-in-logs",
     "会員登録・ログイン・注文確定のログにメールアドレス・パスワード・ログイン状態を示す情報・氏名・住所・電話番号を出力しない（AC-UC-001-016、AC-UC-002-008、AC-UC-006-023）"),
    ("RC-099", "NFR-SC-10", "ADDR-001, ADDR-013", "API/Web>ExceptionHandler", "ERROR", "error-handling", "error-envelope-no-internals",
     "存在しないパス 404・許可しないメソッド 405・JSON 不正 400 は共通封筒（type/reason/message/fields/values）、システムエラーは内部情報を含まない（ADDR-001 4.3 の6・7）"),
    ("RC-100", "NFR-SC-04", "ADDR-012, ADDR-014", "WSGI(config.wsgi.application)>RequestCharsetMiddleware", "ERROR", "error-handling", "wsgi-unusable-charset",
     "Content-Type の charset が文字列の符号化方式でない・復号に使えない指定にクエリ等を伴う要求は 400 入力エラーとし 500 にしない（NFR-SC-04、ADDR-001 4.3 の7）"),
    ("RC-101", "NFR-SC-04", "ADDR-001", "API>Validation>DB", "ERROR", "error-handling", "nul-char-input",
     "NUL 文字を含む入力は 400 input_error とし DB エラー（500）にしない（NFR-SC-04）"),
    ("RC-102", "NFR-SC-05", "ADDR-012", "Web>Template(rendering)", "WEB", "api", "xss-escape",
     "画面に出力する値に含まれるスクリプトはエスケープされ実行されない（NFR-SC-05）"),
    ("RC-103", "NFR-OM-06", "ADDR-011", "ManagementCommand(test_state)>TestState>Clock", "DATABASE", "database", "test-state-command",
     "管理コマンド test_state の set・show・clear で試験用状態を設定・確認・解除でき、時刻提供点に反映される（ADDR-011 4.3 の4）"),
    ("RC-104", "FR-012, FR-022, FR-033, FR-042", "ADDR-001, ADDR-006", "API>URLRouting>Services", "API", "error-handling", "uninterpretable-id-404",
     "識別子として解釈できない値は各 API で 404 not_found（CMN-18）"),
]

# --- Revision 2（INTEGRATION_TEST Scope Assurance：QR-IT-1118-001〜004、Traceability C10 の NFR 見直し）---
# 要件（UC の AC・NFR の測定条件）と ADDR の検証方法から導出した、Revision 1 で欠落していた結合試験の観点。
# AI INITIAL・GAP_FILL のケースから逆算していない。Revision 1 の Initial Coverage Metrics（initial-coverage-metrics.json）は
# 変更せず、Revision 2 を含む Required Coverage に対する AI INITIAL の分類は coverage-gap-report.json に別途記録する。
# 結合試験で検証できない NFR（本番基盤・運用・移行計画・法令・負荷条件等）は Required Coverage に含めず、
# nfr-verification-scope.json に「未検証・理由・検証すべき工程」として一覧化する。
_RAW_R2 = [
    ("RC-105", "FR-045, FR-031", "ADDR-004", "MultiConnection>DB(lock)>payments.gateway(mock)", "CONCURRENCY", "database", "concurrent-admin-cancel-and-pay",
     "管理者キャンセルと購入者の支払（承認）の同時実行で、(a) キャンセル先着：支払は invalid_status（キャンセル済）、決済記録0件・支払日時なし・"
     "履歴2件（2件目 注文受付→キャンセル済、実行者 管理者）、(b) 支払先着：承認1件不変・支払日時あり・履歴3件（注文受付→支払済 購入者、"
     "支払済→キャンセル済 管理者）、いずれも最終キャンセル済・在庫+2。10試行（AC-UC-012-011、ADDR-004 DD-006）"),
    ("RC-106", "FR-012, FR-021, FR-002", "ADDR-002, ADDR-012", "Web>Session>Redirect(next)>carts.services", "AUTH", "authentication", "visitor-cart-add-login-return",
     "来訪者が SCR-002 で「カートに入れる」を操作すると SCR-004（ログインが必要）へ遷移し、ログイン後に SCR-002（商品詳細）へ戻る。"
     "未ログイン時の追加は自動実行されず、カート・カート明細の件数・在庫は不変、カート（0点）（AC-UC-003-018、AC-UC-004-024）"),
    ("RC-107", "NFR-OM-18, NFR-OM-11, FR-031", "ADDR-013, ADDR-008", "API>orders.services>payments.client>AppLog", "LOGGING", "api", "payment-request-id-trace",
     "支払要求1件の X-Request-ID で LOG-01・LOG-03・LOG-06（request/response：order_number・amount・currency=JPY・result・"
     "transaction_ref・duration_ms）を、連携エラー時は LOG-02 も漏れなく抽出でき、機密項目を含まない（NFR-OM-18 測定条件、ADDR-013 DC-002・検証方法、ADDR-008 DD-008）"),
    ("RC-108", "FR-031, NFR-SC-24, NFR-EN-05", "ADDR-008", "API>orders.services>payments.client>gateway(mock)", "API", "api", "payment-request-contents-no-external",
     "決済サービス（模擬）が受けた決済要求は1件で、注文番号・決済金額（注文合計）・通貨 JPY・模擬決済指示の4項目だけ（個人情報なし）、"
     "支払処理中の外部ネットワーク宛て通信0件、送信から応答受信まで1秒以内（AC-UC-007-016、ADDR-008 DD-004/005）"),
    ("RC-109", "FR-030, NFR-PF-07, NFR-LG-06", "ADDR-005, ADDR-004", "MultiConnection>DB(lock, advisory lock, sequence)", "CONCURRENCY", "database", "ten-parallel-ten-trials-order-number",
     "在庫数量5の同一在庫単位を1個ずつカートに入れた10名の同時確定を10回繰り返し、各回 成功5・在庫不足5・在庫0以上・引当合計5以下、"
     "成功した注文番号は重複せずコミットの順に増加する（NFR-PF-07 測定条件、ADDR-005 4.3・検証方法）"),
    ("RC-110", "FR-030", "ADDR-005, ADDR-011", "API>orders.services>FaultPoint(TestState)>DB(sequence)", "ERROR", "error-handling", "fault-order-number-gap",
     "注文番号の払い出し後の障害で取り消された番号は再使用されず欠番となり、次の注文番号はそれより大きい（ADDR-005 DD-003、AC-UC-006-022）"),
    ("RC-111", "FR-060", "ADDR-005, ADDR-006, ADDR-002", "ManagementCommand>initial_data.loader>DB(sequence, identity)>Session", "BATCH", "database", "reset-no-rewind-web-session",
     "--reset 指定の投入後も注文番号・各識別子（利用者・カート・注文・在庫単位等）を巻き戻さず再利用しない。削除前の画面のログイン状態も無効"
     "（ADDR-005 DD-003、ADDR-006 DD-002、ADDR-002 4.3 の6、AC-UC-013-004）"),
    ("RC-112", "NFR-PF-01, NFR-PF-02, NFR-PF-09", "ADDR-001", "API(all)>Services>DB", "API", "api", "response-time-p95-reference",
     "照会系・更新系・認証系 API の種別ごとの応答時間の95パーセンタイルが 1.0秒／2.0秒／2.0秒以内で、システムエラー・業務エラー0件"
     "（結合試験の条件：単一利用者・小データ量での参考計測。ピーク負荷・3年後データ量の判定は性能試験）"),
    ("RC-113", "NFR-PF-08", "ADDR-001", "API>catalog/orders.services>DB(paging)", "API", "api", "list-response-cap",
     "分割表示の一覧（商品一覧・注文履歴・在庫単位一覧・注文一覧（管理））は先頭ページ・最終ページとも1回の応答が50件以下、商品分類一覧は分割しない"),
    ("RC-114", "NFR-PF-10, NFR-MG-01, NFR-MG-02, NFR-MG-03, NFR-MG-04, NFR-MG-08, NFR-OM-04", "ADDR-009, ADDR-010", "ManagementCommand>initial_data.loader>DB>API", "BATCH", "end-to-end-flow", "vdc04-rehearsal",
     "VDC-04 相当（管理者7・仕入先20・商品分類30・商品300・在庫単位800、計1,157件）の定義ファイルを注文作成後の環境へ --reset で1回の実行で投入し、"
     "60秒以内、件数照合・業務キーの内容照合で不一致0、管理者7名がログイン可、注文・カート・決済記録・注文状態履歴0件、実行前の監査ログが残り1件増加。"
     "定義ファイルに注文等のデータを含める指定は受け付けない"),
    ("RC-115", "NFR-OM-13, NFR-MG-07", "ADDR-010", "ManagementCommand>initial_data.loader>DB>AuditLog", "BATCH", "error-handling", "failed-load-corrected-rerun",
     "違反1件を含む定義ファイルは投入件数0（--reset でも既存データを削除しない）・監査ログに失敗1件、修正版を同じ指定で再実行すると件数が定義と一致し"
     "重複しない、再々実行しても重複しない、切戻し（失敗後の再実行）が1時間以内"),
    ("RC-116", "NFR-OM-11", "ADDR-013, ADDR-007", "Services>AppLog/AuditLog/OrderStatusHistory", "LOGGING", "api", "log-types-output",
     "全機能の実行で LOG-01〜LOG-07 が定めた内容で出力・記録される（LOG-01〜03・05・06 は JSON 行、LOG-04 は監査ログ、LOG-07 は注文状態履歴）。保管期間は対象外"),
    ("RC-117", "NFR-OM-17", "ADDR-014", "Environment>config.settings>Middleware/INSTALLED_APPS", "CONFIG", "end-to-end-flow", "env-specific-settings",
     "環境ごとに異なる設定値（接続先・許可ホスト・環境プロファイル・開発用機能）を環境変数だけで変更でき、本番プロファイルでは開発用機能・デバッグを"
     "有効にできない。設定の記入例（.env.example）に秘密情報の値を含まない"),
    ("RC-118", "NFR-SC-12", "ADDR-002, ADDR-003", "API/Web>accounts.services", "AUTH", "authentication", "auth-means",
     "購入者・管理者はメールアドレス＋パスワードで認証でき、誤ったメールアドレス・誤ったパスワードは区別しない同一応答、来訪者は認証なしで商品を閲覧できる"),
    ("RC-119", "NFR-US-03", "ADDR-012", "Web>accounts/orders.services>DB>Template", "WEB", "end-to-end-flow", "jis-level3-4-roundtrip",
     "氏名・配送先に JIS 第3・第4水準の漢字を入力して登録し、画面・API で同じ文字が表示される。画面は日本語（lang=ja）・UTF-8"),
    ("RC-120", "NFR-US-04", "ADDR-012", "Web>accounts/orders.services", "WEB", "api", "input-error-identifiable-all",
     "会員登録・注文手続きの画面で複数項目を誤って送信すると、誤りのある全項目分の理由を項目を識別できる形で1回で表示し、入力値を保持（パスワード除く）"),
    ("RC-121", "NFR-US-05, NFR-US-07, NFR-LG-08", "ADDR-012", "Web>Template(HTML structure)", "WEB", "api", "accessible-html-structure",
     "全画面の HTML が適合レベル A の機械判定可能な達成基準（言語・ページタイトル・フォーム部品のラベル・表見出し・キーボード操作可能なネイティブ部品・"
     "正の tabindex なし）を満たす（チェックリストによる目視・ブラウザ操作の確認は対象外）"),
    ("RC-122", "NFR-US-08", "ADDR-012", "Web(SCR-001→002→005→006→007→008→010)", "WEB", "end-to-end-flow", "purchase-screen-count",
     "ログイン済みの購入者が商品一覧から支払完了までを画面のリンク・フォームだけで操作し、経由する画面は7画面以内"),
    ("RC-123", "NFR-US-09", "ADDR-012", "Web>Template(data-confirm)>site.js", "WEB", "api", "confirm-before-irreversible",
     "取消できない5操作（注文確定・注文キャンセル・出荷登録・配達完了登録・カート明細の削除）のフォームに確認文言があり、確認を求める画面の補助が読み込まれる"
     "（ブラウザの確認ダイアログの操作は対象外）"),
    ("RC-124", "NFR-US-10", "ADDR-004", "Web>SubmitToken>orders.services>payments.gateway(mock)", "WEB", "database", "double-submit-place-pay",
     "注文確定・支払（承認）を処理完了前に繰り返しても注文・決済記録は1件、否認の後の支払は新たな支払として扱う"),
    ("RC-125", "NFR-EN-01, NFR-EN-02, NFR-EN-09", "ADDR-014", "Runtime>Django>PostgreSQL", "CONFIG", "database", "tech-stack-versions",
     "実行環境が Python 3.12・Django 5.2・Django REST Framework 3.15 以上で、接続先が PostgreSQL 16。画面は Django テンプレートで、SPA・フロントエンドのビルド工程を持たない"),
    ("RC-126", "NFR-LG-02", "ADDR-012", "Web>Template(price display)", "WEB", "end-to-end-flow", "tax-inclusive-display",
     "商品価格は税込価格を主に表示し税抜価格を併記、カート・注文手続き・注文完了・注文詳細に消費税額と税込の合計を表示する"),
    ("RC-127", "NFR-LG-09", "ADDR-001, ADDR-012", "API/Web>orders.services(prefecture)", "API", "api", "jis-x0401-prefectures",
     "配送先の都道府県は JIS X 0401 の47コード（01〜47）だけを受け付け、それ以外は入力エラー。画面の選択肢は47件で、名称で表示する"),
    ("RC-128", "NFR-PF-17", "ADDR-008", "orders.services>payments.client>PaymentGateway(substitute)", "API", "end-to-end-flow", "gateway-substitution",
     "決済連携部分（ゲートウェイの実装）だけを別実装に差し替えても、注文・在庫・金額・状態遷移の処理が変更なしで支払が完了する"),
]

# --- Revision 3（TEST_ERROR 修正 cycle=2/3、Quality QR-IT-1118-R1-001）---
# NFR-US-10「処理が完了するまでの間」の繰り返し操作と、ADDR-004 4.4 の検証方法（画面の処理中の繰り返し操作：カートに入れる・
# 支払う（承認・否認）、先着が E-002-02・E-031-08 で終わる間、先着が結果の記録前に中断した場合）・テスト行（複数の接続・
# スレッドから実際に同時要求、画面の同一トークンの同時送信）から導出した観点。Revision 2 の RC-124 は「処理完了前」を
# 掲げていたが、宣言ケース（GF-034）は先着の応答後の逐次再送だけを確認しており、処理中の同一トークンの到着
# （送信トークンのアドバイザリロックの待機経路）を確認する観点が Required Coverage に独立して存在しなかった。ケースから逆算していない。
_RAW_R3 = [
    ("RC-129", "NFR-US-10, FR-031", "ADDR-004, ADDR-008, ADDR-011",
     "Web(同一トークン×別接続)>SubmitToken(advisory lock)>orders.services>payments.gateway(mock)", "CONCURRENCY", "database",
     "inflight-repeat-pay",
     "支払（承認・否認）の処理中（決済応答待ち）に同じ送信トークンの「支払う」を別接続から繰り返すと、後着は送信トークンのロックで"
     "先着の終了まで待ち、決済要求は1回分だけ送信される。承認では後着は再判定どおり E-031-05、否認では後着は先着の結果（E-031-06）を"
     "通知し、決済記録は1件（NFR-US-10、BR-UC-007-014、ADDR-004 DD-002・DD-010・DD-013、4.4 検証方法）"),
    ("RC-130", "NFR-US-10, FR-031", "ADDR-004, ADDR-008, ADDR-011",
     "Web(同一トークン×別接続)>SubmitToken(advisory lock・outcome)>orders.services>payments.gateway(mock)", "CONCURRENCY", "error-handling",
     "inflight-repeat-pay-system-error-interrupted",
     "先着が承認の反映途中の障害（E-031-08）で終わる間、および先着が結果の記録前に中断した場合の繰り返し「支払う」でも決済要求は"
     "1回だけ送信し、後着は E-031-08 を通知する。決済記録・注文状態は変化せず、その後に新たに表示した支払画面からの操作は新たな支払"
     "（ADDR-004 DD-013・DD-015、4.3 の11、4.4 検証方法）"),
    ("RC-131", "NFR-US-10, FR-030", "ADDR-004, ADDR-011",
     "Web(同一トークン×別接続)>SubmitToken(advisory lock)>orders.services(place_order)>DB", "CONCURRENCY", "database",
     "inflight-repeat-place-order",
     "注文確定の処理中に同じ送信トークンの「注文を確定する」を別接続から繰り返すと、注文は1件・在庫の減算は1回分で、後着はカートが空"
     "（E-030-04）としてカート画面へ遷移する（AC-UC-006-021・AC-UC-006-026、BR-UC-006-012、ADDR-004 DD-010・DD-013）"),
    ("RC-132", "NFR-US-10, FR-021", "ADDR-004, ADDR-011",
     "Web(同一トークン×別接続)>SubmitToken(advisory lock)>carts.services(add_item)>DB", "CONCURRENCY", "database",
     "inflight-repeat-cart-add",
     "「カートに入れる」の処理中に同じ送信トークンで別接続から繰り返しても数量は1回分だけ加算され、後着は先着の結果（成功）を通知する"
     "（NFR-US-10、ADDR-004 DD-013、4.4 検証方法）"),
    ("RC-133", "NFR-US-10, FR-002", "ADDR-004, ADDR-011",
     "Web(同一トークン×別接続)>SubmitToken(advisory lock)>accounts.services(login_web)>AuditLog", "AUTH", "authentication",
     "inflight-repeat-login-failure",
     "先着が E-002-02 で終わる間の繰り返し「ログイン」で、ログイン失敗の監査ログは1件、後着は照合せず先着の結果（E-002-02）を通知し"
     "ログイン状態を作らない。送信トークンの記録に入力値を残さない（ADDR-004 DD-013・DD-016、4.4 検証方法）"),
]


# --- Revision 4（FULL Traceability C10 の差し戻し、UNRESOLVED-e1d9dfe900863622 修正 cycle=1/3）---
# Revision 2 で「結合試験で検証できない」として Required Coverage に含めなかった NFR 60件（NOT_VERIFIED 48・NOT_APPLICABLE 12）の
# 要件本文・測定条件・検証方法・根拠を読み直し、(a) 要件が「該当なし」と定める根拠の前提（機能・処理・接続が無いこと）を
# リポジトリのコード・URL・設定の不存在として確かめられるもの、(b) 構成・設定レビュー／静的解析を検証方法とし、リポジトリ内の
# 起動定義・依存の固定・設定値・手順書・ソースコードから一部を確かめられるもの、(c) 対応方針の一部を API・DB で確かめられるもの
# だけを追加した。本番環境・運用記録・負荷・ブラウザ・法令判断に依存する部分は含めない（nfr-verification-scope.json）。
# ケースから逆算していない。
_RAW_R4 = [
    ("RC-134", "NFR-PF-12, NFR-AV-01", "ADDR-014", "compose.yaml(app,db)>Dockerfile>requirements*.txt>manage.py commands",
     "CONFIG", "end-to-end-flow", "no-scheduled-batch",
     "定期的に実行するバッチ処理・定期ジョブの定義を持たない（NFR-PF-12「該当なし」の根拠の前提）。起動定義（compose のサービスは "
     "app・db のみ、app の起動は移行適用・静的ファイル収集・Gunicorn だけ、Dockerfile に定期実行の仕組みなし）、依存に定期実行の"
     "ライブラリなし、管理コマンドは手動実行の初期データ一括投入・試験用状態と無効化した Django 付属の2件だけ。NFR-AV-01 の代替確認"
     "（計画停止以外にサービス停止を要する定期処理が無い）のうちリポジトリ内の起動定義の範囲"),
    ("RC-135", "NFR-SC-28", "ADDR-001, ADDR-012", "API(JsonBodyParser)/Web(Template)>Models", "API", "api", "no-file-upload",
     "画面・API にファイルをアップロードする機能が無い（NFR-SC-28「該当なし」の根拠の前提）。ファイルを保存する項目を持つデータが無く、"
     "画面にファイル選択部品・multipart のフォームが無く、業務処理がアップロードされたファイルを参照せず、Web API は JSON の本文だけを"
     "解釈し、ファイルを伴う multipart の要求は 400 input_error でデータを変更しない（ADDR-001 4.3 の7）"),
    ("RC-136", "NFR-SC-13, NFR-SC-14", "ADDR-002, ADDR-003", "API/Web>accounts.services>AuditLog", "AUTH", "authentication",
     "single-factor-no-lockout",
     "購入者はメールアドレス＋パスワードだけで1回の要求でログインが完了し追加の認証要素を求めない（NFR-SC-13「該当なし」の前提）。"
     "誤ったパスワードでの失敗を API・画面で各10回続けた後も正しいパスワードでログインでき（アカウントロック・試行回数制限なし："
     "NFR-SC-14「該当なし」の前提）、失敗は監査ログに1回につき1件、対象利用者付きで記録される（NFR-SC-14 の根拠）"),
    ("RC-137", "NFR-SC-13, NFR-SC-17, NFR-LG-04", "ADDR-001, ADDR-012", "URLconf(API/Web)>management commands>Template",
     "WEB", "api", "out-of-scope-functions-absent",
     "画面・API に多要素認証・パスワードの変更／再設定・特定商取引法に基づく表記の要求先が無く（該当しそうな要求は 404）、"
     "Django 付属の changepassword は何も変更せずにエラー終了し、画面に特定商取引法の表記が無い（NFR-SC-13・NFR-SC-17（FR-OUT-09）・"
     "NFR-LG-04（FR-OUT-16）の「該当なし」・対象外の前提）"),
    ("RC-138", "NFR-SC-27", "ADDR-001", "API/Web>Middleware>DRF settings", "API", "api", "no-per-source-rate-limit",
     "同一の送信元からの短時間の連続要求（商品一覧 API・商品一覧画面・ログイン API）を送信元単位で制限しない（429 を返さない。"
     "NFR-SC-27「該当なし」の根拠の前提）"),
    ("RC-139", "NFR-AV-10, NFR-LG-10", "ADDR-008", "orders.services>payments.client>payments.gateway>payments.mock", "API", "api",
     "in-process-mock-payment-only",
     "決済サービスは本システム内の模擬機能だけで（使用する実装はプログラム内の既定で模擬機能）、決済の部品に外部通信のモジュールを"
     "使わず、実在の決済サービスの接続先・認証情報の設定項目・連携ライブラリを持たない（NFR-AV-10・NFR-LG-10 の「該当なし」の根拠の"
     "前提。外部通信0件は RC-108）"),
    ("RC-140", "NFR-EN-03, NFR-OM-05, NFR-EN-08", "ADDR-014", "compose.yaml(app,db)>Dockerfile>gunicorn.conf>config.wsgi",
     "CONFIG", "end-to-end-flow", "compose-single-start-gunicorn",
     "Docker Compose の定義で全構成要素（アプリケーション・データベース）を1回の起動操作で起動する（app は db の正常性確認後に、"
     "移行適用→静的ファイル収集→Gunicorn を1つの起動コマンドで行う）。起動定義は本番運用向けの AP サーバー（Gunicorn）で Django 付属"
     "の開発用サーバーを含まず、Gunicorn の設定が指す WSGI アプリケーションが商品一覧画面を返す。依存に特定のクラウド基盤の SDK を含まない"
     "（compose での実際の起動・本番環境の構成は対象外）"),
    ("RC-141", "NFR-EN-07", "ADDR-014", "app(production code)>Python stdlib>Dockerfile", "CONFIG", "end-to-end-flow",
     "os-independent-code",
     "Production Code が特定の OS に固有のモジュールを読み込まず、OS 固有の絶対パスを書かない。OS はコンテナのベースイメージ"
     "（python:3.12-slim、ダイジェスト固定）だけで決まる"),
    ("RC-142", "NFR-SC-21, NFR-EN-10", "ADDR-014", "requirements*.txt>Dockerfile>compose.yaml>.venv>dependency-inventory",
     "CONFIG", "end-to-end-flow", "pinned-reproducible-dependencies",
     "依存ライブラリ・実行環境の取得元と版が特定でき同じ構成を再現できる（VUL-10、NFR-SC-21 の対策方針の一部）：依存は全件が版固定と"
     "ハッシュ付き、イメージ構築は --require-hashes、ベースイメージ・DB イメージはダイジェスト固定、試験環境の版が固定した版と一致し、"
     "依存の一覧の版と一致する。採用製品の版が NFR-EN-10 のサポート期限の前提の版（Django 5.2 LTS 2028-04、Python 3.12 2028-10、"
     "PostgreSQL 16 2028-11）である（更新計画は対象外）"),
    ("RC-143", "NFR-EN-12", "ADDR-014", "requirements*.txt>.venv(package metadata)", "CONFIG", "end-to-end-flow",
     "dependency-licenses",
     "固定した全依存ライブラリのライセンスがパッケージのメタデータから特定でき（ライセンス不明 0件）、AGPL のものが無い"
     "（利用条件の充足の判断は対象外）"),
    ("RC-144", "NFR-EN-11", "ADDR-014", "ruff.toml>ruff>repository sources", "CONFIG", "end-to-end-flow", "static-analysis-zero",
     "リポジトリの規約設定（ruff.toml。pycodestyle の E・W を含む）で全ソースコードを静的解析し違反0件（規則の選択が PEP 8 に"
     "一致するかは対象外）"),
    ("RC-145", "NFR-PF-16", "ADDR-002, ADDR-014", "gunicorn.conf(GUNICORN_WORKERS)>SessionStore(DB)>ApiLoginState(DB)>Cart(DB)",
     "CONFIG", "database", "scale-out-state-preserved",
     "処理能力の増強（実行単位内のプロセス数）を環境変数だけで変更でき、画面のログイン状態・Web API のログイン状態・カートの内容が"
     "データベースに保持され、別のプロセスから同じ Cookie・Bearer でログイン中のカートを参照できる（増強手順のレビュー・2倍の負荷は対象外）"),
    ("RC-146", "NFR-SC-25", "ADDR-009, ADDR-011", "seed/initial_data.json>tests fixtures", "CONFIG", "database",
     "fictional-initial-data",
     "リポジトリの初期データ（検証用の定義ファイル）の利用者のメールアドレスは全件 example.com（VDC-01 の作成方法）で、"
     "それ以外のドメインを含まず、試験用の利用者は予約済みドメイン（example.test）で作る"),
    ("RC-147", "NFR-OM-19", "ADDR-010, ADDR-014", "README(ENV-01 手順)>.env.example>compose.yaml>manage.py>pytest/ruff",
     "CONFIG", "end-to-end-flow", "dev-procedure-document",
     "開発・検証環境向けの手順書に、環境ごとの設定（秘密情報を含む）の作成・構築・起動・停止・データベースの初期化・初期データ一括投入・"
     "自動テスト・静的解析の手順があり、手順が参照するファイル・サービス・コマンドが存在し、初期データ一括投入の手順"
     "（seed/initial_data.json、--reset）が成功する（本番運用手順書・compose での構築・起動の実施は対象外）"),
    ("RC-148", "NFR-LG-03", "ADDR-004, ADDR-012", "API>orders.services>DB(OrderItem/ShippingAddress/PaymentRecord/OrderStatusHistory)",
     "DATABASE", "state-transition", "order-records-immutable",
     "注文明細・配送先・決済記録・注文状態履歴は登録後に変更・削除されず（決済記録・履歴は追記のみ）、注文の登録後の更新は注文状態の"
     "遷移（支払・出荷登録・配達完了登録・キャンセル）に伴う注文状態・日時・配送伝票番号だけ（NFR-LG-03 の対応方針の一部。7年保存・"
     "削除手順は対象外）"),
]


# Revision 5（FULL Traceability C10 の差し戻し UNRESOLVED-e1d9dfe900863622 修正 cycle=2/3）：
# cycle=1/3 の後も要件→テスト未到達の NFR 38件の要件本文・測定条件・検証方法・代替確認を読み直し、cycle=1/3 で検討しなかった
# 観点として、(d) 開発環境の PC（Windows 11）とインストール済みのブラウザ・使い捨て PostgreSQL 16 で、要件の測定条件に沿って
# 実施できる参考計測・操作確認（ブラウザでの全画面の表示・代表操作・表示完了時間、3年後データ量、同時利用者・超過負荷、
# 標準の論理バックアップによる取得・復元・業務再開、データ構造の変更と切戻し）、(e) 開発時の公開脆弱性情報との照合、
# (f) Production Code・設定・起動定義から機械的に確かめられる前提（保存データ・ログの出力先、監査ログの削除経路の不存在、
# 個人情報のログ・ファイル・外部への出力の不存在、全画面・全 API の簡易な動的診断、HTTPS 以外の拒否・管理用の別口の不存在、
# 在庫数量の反映）を追加した。本番環境（ENV-02）の設定・運用記録・運用体制・法令判断・診断ツールによる診断は含めない
# （nfr-verification-scope.json）。ケースから逆算していない。
_RAW_R5 = [
    ("RC-149", "NFR-US-01, NFR-US-02, NFR-US-06", "ADDR-012, ADDR-014", "Browser(Edge/Chrome, Windows 11)>Web>Static",
     "WEB", "end-to-end-flow", "browser-display-and-operation",
     "Windows 11 の PC にインストールした Microsoft Edge・Google Chrome で、表示領域 1280×720・表示倍率 100% のとき、全画面"
     "（SCR-001〜SCR-010、SCR-101〜SCR-103、SCR-901）が想定の状態コードで表示され、資源の読込失敗・スクリプトの例外・外部への要求が無く、"
     "横スクロール（表示領域の幅を超える内容・要素）が無い。来訪者・購入者・管理者の代表操作（会員登録・ログイン・カートに入れる・"
     "クーポン適用・注文確定・支払・キャンセル・出荷登録・配達完了登録・ログアウト）をブラウザのフォーム送信と確認ダイアログで行える"
     "（ヘッドレス表示。目視の表示崩れ・全操作の網羅・最新版であることは対象外）"),
    ("RC-150", "NFR-PF-03", "ADDR-012", "Browser(Edge/Chrome)>Web>Static", "PERF", "end-to-end-flow",
     "screen-display-time-reference",
     "全画面（14画面）を各ブラウザで30回以上表示し、画面要求の送信から構成に必要な全資源の読込完了（load イベント終了）までの"
     "時間の95パーセンタイルを画面ごとに記録し、単一利用者・小データ量でも 2.0秒以内（ピーク負荷・3年後データ量・ENV-01 の判定は対象外）"),
    ("RC-151", "NFR-PF-06", "ADDR-001", "API/Web>services>DB(3年後データ量)", "PERF", "database",
     "three-year-data-volume-reference",
     "3年後相当のデータ量（VDC-01〜VDC-03 の件数：注文 110,000・注文明細 330,000・会員 10,000・商品 600・在庫単位 1,600 等）の DB で、"
     "照会系・更新系 API と画面の応答時間の95パーセンタイルを記録し、単一利用者でも目標値（照会 1.0秒・更新 2.0秒・画面 2.0秒）以内"
     "（ピーク負荷・ENV-01 の判定は対象外）"),
    ("RC-152", "NFR-PF-05, NFR-PF-04, NFR-PF-14, NFR-PF-15, NFR-PF-03", "ADDR-001, ADDR-011",
     "VirtualUsers(155)>HTTP>Web/API>DB", "PERF", "end-to-end-flow", "concurrent-users-reference",
     "同時155の仮想利用者（購入者・来訪者 150、管理者 5、思考時間 5〜15秒、照会：更新＝8：2＋認証系、業務エラーにならない条件）の"
     "負荷で、システムエラー0件・要求の全件成功・照会/更新/認証の95パーセンタイルが目標値以内、注文確定の到着 4件/分（異なる購入者、"
     "3明細・5点）の全件成功、負荷中のブラウザ表示の95パーセンタイル 2.0秒以内を確認し、アプリケーション・DB の CPU・メモリ使用量"
     "と応答時間の推移を記録する（60分・2時間の連続負荷・3年後データ量・ENV-01 の判定は対象外）"),
    ("RC-153", "NFR-PF-11", "ADDR-004, ADDR-011", "VirtualUsers(310)>HTTP>API>orders.services>DB", "PERF", "database",
     "overload-consistency-reference",
     "想定の2倍（310）の仮想利用者で在庫不足が起きる負荷をかけた後、システムエラーとなる応答の割合が 1%以下、在庫数量が0未満の"
     "在庫単位 0件、金額整合を満たさない注文 0件、在庫の増減と注文明細（キャンセル以外）が一致（10分間・3年後データ量は対象外）"),
    ("RC-154", "NFR-SC-11", "ADDR-014", "requirements*.txt>OSV(公開脆弱性情報)>PyPI", "CONFIG", "end-to-end-flow",
     "dependency-known-vulnerabilities",
     "固定した全依存ライブラリ（app/requirements.txt・requirements-dev.txt）を開発時に公開脆弱性情報（OSV）と照合し、照合対象が"
     "固定した版と一致し、CVSS 7.0以上（または重大度 HIGH/CRITICAL）・重大度不明の既知の脆弱性が0件（リリース前の再照合・"
     "コンテナイメージの OS パッケージは対象外）"),
    ("RC-155", "NFR-LG-01", "ADDR-001, ADDR-012, ADDR-013", "API/Web>services>Logging>URLconf>socket", "SECURITY",
     "authentication", "personal-information-handling",
     "利用者の個人情報（メールアドレス・氏名・配送先）を扱う一連の操作（会員登録・ログイン・注文確定・支払・照会・管理者の検索）で、"
     "ログに個人情報・パスワードを出力せず、ファイルとして出力する要求先・応答が無く、外部へ送信しない。注文の参照は本人と管理者に"
     "限られる（利用目的の表示・通信の暗号化・法令適合の判断は対象外）"),
    ("RC-156", "NFR-SC-29, NFR-LG-07", "ADDR-001, ADDR-002, ADDR-012", "Web/API(全要求先)>Middleware>services",
     "SECURITY", "api", "dynamic-probe-all-endpoints",
     "全画面・全 API に対し、利用者区分ごとのアクセス制御（VUL-01）、CSRF トークンなしの更新要求と参照用の要求での更新（VUL-06）、"
     "検索条件・パス・本文への攻撃文字列（VUL-04・VUL-05・VUL-13）を送り、システムエラー・無害化されない反映・内部情報の露出・"
     "セキュリティヘッダーの欠落が無く、外部へ要求を送る部品が無い（VUL-12）（診断ツールによる診断・指摘の対処は対象外）"),
    ("RC-157", "NFR-SC-20", "ADDR-002, ADDR-006, ADDR-013, ADDR-014", "settings>Models>Sessions>Logging>production code",
     "CONFIG", "database", "persistent-data-only-in-database",
     "保存データの所在がデータベースだけで（ファイル項目・ファイル型のセッション/キャッシュ・ファイルへの書込み・ログファイルが無い）、"
     "データベースとバックアップの暗号化で全保存データが対象になる前提（本番の暗号化の設定は対象外）"),
    ("RC-158", "NFR-OM-02", "ADDR-008, ADDR-010, ADDR-013", "Logging(stdout JSON)>gunicorn.conf>production code",
     "CONFIG", "end-to-end-flow", "application-log-output",
     "LOG-01〜LOG-03・LOG-05・LOG-06 が標準出力へ1行1件の JSON（日本時間の日時・ログの種類・要求の識別子）で出力され、ファイル・"
     "ローテーションのハンドラーが無く、アプリケーションがログを削除しない（ENV-02 での90日保管・検索は対象外）"),
    ("RC-159", "NFR-OM-03", "ADDR-006, ADDR-010, ADDR-012", "AuditLog(DB)>initial_data(--reset)>production code",
     "DATABASE", "database", "audit-log-retention-premise",
     "監査ログは DB に発生日時付きで追記のみで記録され、更新・削除の操作は拒否され、利用者への外部キーを持たず、初期データ一括投入"
     "（--reset）を含む本システムのどの処理も削除しない（1年保管・運用手順書の削除手順は対象外）"),
    ("RC-160", "NFR-SC-26", "ADDR-012, ADDR-014", "URLconf>HttpsOnlyMiddleware>gunicorn.conf>Dockerfile", "CONFIG",
     "end-to-end-flow", "single-https-user-service",
     "利用者向けサービス（画面・API・管理者の画面/API）は1つの待受け（Gunicorn の bind 1件、EXPOSE 8000）だけで提供し、本番プロファイル"
     "では全要求先で HTTPS 以外を拒否し、管理サイト・デバッグ用の要求先・遠隔ログインのソフトウェアが無い（本番のネットワーク設定は"
     "対象外。compose.yaml の公開範囲は既知の未解決 SEC-IMPL-002 の対象で根拠に用いない）"),
    ("RC-161", "NFR-MG-05", "ADDR-009, ADDR-010", "load_initial_data>loader>StockUnit", "DATABASE", "database",
     "initial-load-stock-sheet",
     "初期データ一括投入は投入時点の在庫管理表の値（定義ファイルの在庫数量）をそのまま反映し、更新後の在庫管理表の値で再投入"
     "（--reset）すると後の値に置き換わる（移行計画の実施日・実施者・確定時刻のレビューは対象外）"),
    ("RC-162", "NFR-AV-04, NFR-AV-07, NFR-AV-08, NFR-AV-12, NFR-PF-13", "ADDR-001, ADDR-011",
     "DB(PostgreSQL 16)>pg_dump/pg_restore>API/Web/initial_data", "DATABASE", "database", "backup-restore-resume",
     "3年後相当のデータで、利用者の要求を処理しながら（全要求が成功）全データ（監査ログを含む）のバックアップを取得でき、全データの"
     "喪失後にバックアップから復元すると取得時点のデータ（取得前の注文あり・取得後の注文なし）に戻り、障害前の全業務（来訪者・購入者・"
     "管理者の操作、初期データ一括投入）を再開できる。リストア時間を記録する（本番のバックアップ方式・3:00・7世代・保管場所は対象外）"),
    ("RC-163", "NFR-OM-15", "ADDR-014", "migrations(catalog 0002)>pg_dump/pg_restore>Web/API", "CONFIG", "database",
     "update-and-rollback",
     "3年後相当のデータで、データ構造の変更を含む更新（マイグレーションの適用）と起動確認を行い、更新直前のバックアップから切戻すと"
     "データ構造・データが更新前の状態に戻り、所要時間（取得・更新・切戻し）が 120分以内（プログラムの入替え・ENV-01 での実施は対象外）"),
]


def coverage_key(requirement_id: str, integration_point: str, test_category: str, criterion: str, condition: str) -> str:
    return f"{requirement_id}|{integration_point}|{test_category}|{criterion}|{condition}"


REQUIRED_COVERAGE = [
    {
        "coverage_id": cid,
        "requirement_id": req,
        "related_adr": adr,
        "integration_point": ip,
        "test_category": cat,
        "criterion": crit,
        "condition": cond,
        "expected_behavior": exp,
        "coverage_key": coverage_key(req, ip, cat, crit, cond),
        "revision": revision,
    }
    for revision, raw in ((1, _RAW), (2, _RAW_R2), (3, _RAW_R3), (4, _RAW_R4), (5, _RAW_R5))
    for (cid, req, adr, ip, cat, crit, cond, exp) in raw
]

REVISION1_IDS = [item[0] for item in _RAW]
REVISION2_IDS = [item[0] for item in _RAW_R2]
REVISION3_IDS = [item[0] for item in _RAW_R3]
REVISION4_IDS = [item[0] for item in _RAW_R4]
REVISION5_IDS = [item[0] for item in _RAW_R5]

KEY_BY_ID = {item["coverage_id"]: item["coverage_key"] for item in REQUIRED_COVERAGE}
