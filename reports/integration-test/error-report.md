# 結合試験 Error Report（RUN-AOBA-EC-1118）

- 生成: 2026-11-19T19:15:42+00:00（正式実行 it-exec-7、JUnit: reports/integration-test/junit.xml）
- 正式実行の Failed Case: 1 件（AI INITIAL 1・AI GAP_FILL 0・EXTERNAL 0）
- Unique Defect: 1 件（未解決 1 件）
- 検出元: COMMON_DEFECT 0 / AI_ONLY_DEFECT 1 / EXTERNAL_ONLY_DEFECT 0（External Case は未提供）
- 原因別（全 Error 19 件）: IMPLEMENTATION_ERROR 1、TEST_ERROR 18

## 正式実行で残った不具合

### IT-DEF-001（IMPLEMENTATION_ERROR、既知 UNRESOLVED-6de5eec64599b907）

- 検出ケース: IT-058（AI_ONLY_DEFECT）
- Requirement / ADR: NFR-SC-04 / ADDR-012, ADDR-014
- 期待: Content-Type の charset が復号に使えない指定（undefined・idna）で非 ASCII のクエリを伴う要求も、rot13 と同じく 400 入力エラーとし、500 にしない（NFR-SC-04、ADDR-001 4.3 の7、RC-100）
- 実際: AssertionError: charset 指定の要求が 400 にならない: {('undefined', '/api/products/'): 500, ('undefined', '/'): 500, ('idna', '/api/products/'): 500, ('idna', '/'): 500}（全結果 {('rot13', '/api/products/'): 400, ('rot13', '/'): 400, ('undefined', '/api/products/'): 500, ('undefined', '/'): 500, ('idna', '/api/products/'): 500, ('idna', '/'): 500}）
- 原因: config.wsgi.application が呼ぶ common.middleware.is_unusable_charset は codecs の _is_text_encoding が偽の符号化方式（rot13 等）だけを除外し、テキスト用として登録されているが入力を復号できない 'undefined'・'idna' を通過させる。このため Django の WSGIRequest 生成時（クエリ文字列の復号）に UnicodeError となり、RequestCharsetMiddleware・WebExceptionMiddleware を経ずにアプリケーション外へ例外が送出される（AP サーバーでは 500、LOG-03 も出力されない）
- 箇所: WSGI 入口・共通ミドルウェア — app/config/wsgi.py, app/common/middleware.py（config.wsgi.application, common.middleware.is_unusable_charset）、API: 全要求（/api/products/、/ ほか。Content-Type に charset=undefined／idna とクエリを伴う GET）
- 対応: Production Code は変更していない（Integration Test Agent の責務外）。既知の未解決 UNRESOLVED-6de5eec64599b907 のため新しい3回ループにせず、IMPLEMENTATION_FIX_REQUIRED として親へ返す。修正候補：is_unusable_charset で空文字列・非 ASCII を実際に復号して失敗する指定も入力エラーとする
- 再試験: 対象 NOT_EXECUTED・関連 NOT_EXECUTED・全体 NOT_EXECUTED（Production Code の修正が行われていないため修正後の再試験は未実行（結果を PASS にしない））
- 推奨対応先: IMPLEMENTATION（新しい3回ループは開始しない）

## 試行実行で検出し修正した TEST_ERROR（一時 JUnit。正式結果ではない）

| Case | 時点 | 原因 | 箇所 | 修正 | 正式実行の結果 |
|---|---|---|---|---|---|
| IT-020 | implementation_trial_run（一時 JUnit。正式結果ではない、it-exec-1 前） | 固定した現在日時（2027年）より前の実時刻で発行した Bearer が有効期限切れとなり 401（試験データの不備） | app/tests/integration/test_it_cart.py::test_it_020_coupon_apply_validity_recalc_remove | 固定日時ごとにログイン状態を発行し直すよう試験手順を修正（期待値は変更なし） | PASS |
| IT-031 | implementation_trial_run（一時 JUnit。正式結果ではない、it-exec-1 前） | 注文詳細の coupon に ADDR-001 R-4 の discount_type_label があるのに完全一致で比較していた（期待値の記述誤り） | app/tests/integration/test_it_orders.py::test_it_031_history_and_detail_contents | R-4 どおり値と _label の両方を確認する比較に修正（要件の期待値に合わせた。弱体化なし） | PASS |
| IT-051 | implementation_trial_run（一時 JUnit。正式結果ではない、it-exec-1 前） | manage.py 実行（run_from_argv）が終了時に DB 接続を閉じ、ロールバック方式の試験トランザクションが失われた（試験環境の不備） | app/tests/integration/test_it_initial_data.py::test_it_051_load_then_login_and_listings | コマンドを実行するケースを transaction=True（コミット方式、ADDR-011 DD-010 と同じ）に変更 | PASS |
| IT-052 | implementation_trial_run（一時 JUnit。正式結果ではない、it-exec-1 前） | 同上（コマンド終了時の DB 接続の切断） | app/tests/integration/test_it_initial_data.py::test_it_052_reset_deletes_all_and_invalidates_tokens | transaction=True に変更 | PASS |
| IT-053 | implementation_trial_run（一時 JUnit。正式結果ではない、it-exec-1 前） | 同上（コマンド終了時の DB 接続の切断） | app/tests/integration/test_it_initial_data.py::test_it_053_violations_reported_nothing_loaded | transaction=True に変更 | PASS |
| IT-054 | implementation_trial_run（一時 JUnit。正式結果ではない、it-exec-1 前） | 同上（コマンド終了時の DB 接続の切断） | app/tests/integration/test_it_initial_data.py::test_it_054_argument_read_and_format_errors | transaction=True に変更 | PASS |
| GF-009 | implementation_trial_run（一時 JUnit。正式結果ではない、it-exec-1 前） | 同上（コマンド終了時の DB 接続の切断） | app/tests/integration/test_it_gap_fill.py::test_gf_009_seed_file_loadable | transaction=True に変更 | PASS |
| GF-002 | implementation_trial_run（一時 JUnit。正式結果ではない、it-exec-1 前） | 二重送信の再現で、先着の応答で更新された CSRF Cookie を後着に使い 403（二重送信は先着の応答前の Cookie で送られる） | app/tests/integration/test_it_gap_fill.py::test_gf_002_web_login_double_submit_same_token | 先着の応答前の Cookie を複製したクライアントから後着を送るよう再現手順を修正（期待値は変更なし） | PASS |
| IT-058 | implementation_trial_run（一時 JUnit。正式結果ではない、it-exec-1 前） | ASCII だけのクエリでは idna で復号でき『復号に使えない指定』の条件を満たさず、試験データが条件を再現していなかった | app/tests/integration/test_it_cross_cutting.py::test_it_058_wsgi_unusable_charset_with_query | 非 ASCII（UTF-8 のあ）を含むクエリに変更（期待値 400 は変更なし）。修正後は IT-DEF-001（既知の未解決）として FAIL | FAIL |
| GF-034 | cycle1_trial_run（一時 JUnit。正式結果ではない、it-exec-2 前） | 使用済みトークンの注文確定の後着に先着と同じ遷移先を期待していたが、ADDR-004 DD-010・DD-013 では注文確定は省略対象外で再判定の結果（カートが空、AC-UC-006-021）を通知する（期待値の導出誤り） | app/tests/integration/test_it_gap_fill_flows.py::test_gf_034_double_submit_place_pay | 後着はカートへ遷移（cart_empty）と ADDR-004 どおりに修正。注文1件の確認は変更なし（弱体化なし） | PASS |
| GF-028 | cycle1_trial_run（一時 JUnit。正式結果ではない、it-exec-2 前） | ログイン失敗の種類を error.reason で比較していた（ADDR-001 の封筒では type=authentication_failed、reason は null） | app/tests/integration/test_it_gap_fill_nfr_web.py::test_gf_028_auth_means | error.type で比較するよう修正（2つの失敗の本文が同一であることの確認は変更なし） | PASS |
| GF-024 | cycle1_trial_run（一時 JUnit。正式結果ではない、it-exec-2 前） | 注文を含む定義ファイルの拒否（監査ログに失敗1件）より前に監査ログを記録し、移行リハーサルの実行で1件増加の判定に失敗を含めていた | app/tests/integration/test_it_gap_fill_nfr_batch.py::test_gf_024_vdc04_rehearsal | 拒否の失敗1件を別に確認し、--reset の実行直前の監査ログに対して1件増加を判定するよう修正 | PASS |
| GF-039 | cycle2_trial_run（一時 JUnit。正式結果ではない、it-exec-3 前） | 送信トークンの記録の確認で、同じ操作種別（order_pay）の記録が試験全体で1件と仮定していた（承認・否認の2注文で2件。試験コードの誤り） | app/tests/integration/test_it_gap_fill_inflight.py::test_gf_039_inflight_repeat_pay_approved_declined | 対象トークン（操作種別＋照合値）の記録が1件であることだけを確認するよう修正（期待値は変更なし） | PASS |
| GF-040 | cycle2_trial_run（一時 JUnit。正式結果ではない、it-exec-3 前） | システムエラー画面の文言を「システムエラーが発生しました。」（句点付き）で照合したが、画面は見出し（句点なし）と本文に分けて表示する（試験コードの照合文字列の誤り） | app/tests/integration/test_it_gap_fill_inflight.py::test_gf_040_inflight_repeat_pay_system_error_and_interrupted | ERR-08 の本文「時間をおいて再度操作してください。解消しない場合は当社までお問い合わせください。」と 500 で照合（期待値は変更なし） | PASS |
| GF-050 | trace_c10_cycle1_trial_run（一時 JUnit。正式結果ではない、UNRESOLVED-e1d9dfe900863622、it-exec-5 前） | Dockerfile に開発用サーバーが無いことを、コメント行（「runserver を起動構成に含めない」）を含む全文で判定していた（試験コードの判定対象の誤り） | app/tests/integration/test_it_gap_fill_nfr_config.py::test_gf_050_compose_single_start_gunicorn | コメントを除く Dockerfile の命令行で判定するよう修正（起動定義に runserver を含まないという期待値は変更なし） | PASS |
| GF-059 | trace_c10_cycle2_trial_run（一時 JUnit。正式結果ではない、UNRESOLVED-e1d9dfe900863622、it-exec-6 前） | 購入者のログインフォームをエラー画面（SCR-901）の表示中に送信し、カートに入れるフォームを商品詳細を表示せずに送信していた（試験手順の誤り） | app/tests/integration/test_it_gap_fill_nfr_browser.py::test_gf_059_browser_compatibility | ログイン画面・商品詳細を表示してからフォームを送信するよう修正（全画面の表示・代表操作・横スクロールなしの期待値は変更なし） | PASS |
| GF-068 | trace_c10_cycle2_trial_run（一時 JUnit。正式結果ではない、UNRESOLVED-e1d9dfe900863622、it-exec-6 前） | LOG-05 を manage.py の起動経路（execute_from_command_line）で発生させたため、ログ設定の読み直しで捕捉用のハンドラーが外れ、LOG-05 を捕捉できなかった（試験コードの誤り） | app/tests/integration/test_it_gap_fill_nfr_ops.py::test_gf_068_application_log_output | 初期データ一括投入を call_command で実行するよう修正（LOG-01〜03・05・06 の出力の期待値は変更なし） | PASS |
| GF-062 | formal_execution（it-exec-6） | 仮想利用者（_Buyer）がカートのクーポンの適用状態を応答から同期せず、カートの明細を全て削除した時点で「クーポンなし」とみなしていた。カートの明細の削除ではクーポンは外れない（carts.services.delete_item）ため、適用中のカートへ再びクーポン適用を要求し、業務エラー（E-024-05 クーポンは1注文につき1枚まで、422）を2件発生させた。測定条件の「業務エラーとならない条件で要求する」を試験側が満たしていなかった（試験コードの誤り。Production Code の不具合ではない） | app/tests/integration/test_it_gap_fill_nfr_perf.py::_Buyer（_update の cart_delete・coupon_apply） | カートの応答（明細追加・数量変更・削除・クーポン適用/解除・カート照会）の coupon からクーポンの適用状態を同期するよう修正（業務エラー0件・システムエラー0件・95パーセンタイルの期待値は変更なし） | PASS |
