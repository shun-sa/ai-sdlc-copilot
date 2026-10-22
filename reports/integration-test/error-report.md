# 結合試験 Error Report

- run_id: RUN-20261022-MC
- 工程: INTEGRATION_TEST

## 1. Error 集計

| 区分 | 実行 | PASS | FAIL | ERROR | BLOCKED |
| --- | --- | --- | --- | --- | --- |
| AI_GENERATED / INITIAL | 54 | 54 | 0 | 0 | 0 |
| AI_GENERATED / GAP_FILL | 80 | 80 | 0 | 0 | 0 |
| EXTERNAL | 0 | 0 | 0 | 0 | 0 |
| TOTAL | 134 | 134 | 0 | 0 | 0 |

## 2. Error 原因分類

- Error 総数: 0 件
- AI_GENERATED 起因の Error: 0 件（INITIAL 0 件 / GAP_FILL 0 件）
- EXTERNAL 起因の Error: 0 件（External Case は 0 件）
- TEST_SPEC_CONFLICT: 0 件
- AUTOMATION_BLOCKED: 0 件

| 分類 | 件数 |
| --- | --- |
| TEST_ERROR | 0 |
| IMPLEMENTATION_ERROR | 0 |
| ADR_REQUIRED | 0 |
| REQUIREMENT_ERROR | 0 |
| ENVIRONMENT_ERROR | 0 |
| TEST_SPEC_CONFLICT | 0 |
| AUTOMATION_BLOCKED | 0 |

## 3. Error 一覧（Case ID・原因・箇所・分類）

Error / Failure は発生していない。

## 4. Defect 集計（Case Failure 数とは区別する）

- Case Failure 数: 0 件 / Unique Defect 数: 1 件

| 区分 | 件数 |
| --- | --- |
| COMMON_DEFECT | 0 |
| AI_ONLY_DEFECT | 1 |
| EXTERNAL_ONLY_DEFECT | 0 |
| 未解決 Defect | 0 |

### DEF-IT-001：同時キャンセル時に E-031-05 となる支払でも決済サービスへ決済要求が送信される

- 状態: 解消済み（2026-10-22T16:05:00+09:00）
- 分類: ADR_REQUIRED
- 検出Case: IT-AI-GF-023（AI_ONLY_DEFECT）
- 根拠要件: FR-031 / FR-031 6.16.4 手順5, AC-UC-007-019, NFR-SC-21/VUL-07（二重決済防止）
- 関連ADR: ADDR-009, ADDR-001, ADDR-013
- 期待: 注文受付以外の状態で支払が E-031-05（INVALID_STATUS_TRANSITION）となる場合、決済サービス（模擬）へ決済要求を送信しない（FR-031 手順5）。AC-UC-007-019 (a) は 409 の試行で決済サービスが当該注文の決済要求を受けていないことを求める。
- 実際（検出時）: 10試行の1試行目で、キャンセルが先に確定し支払が 409 INVALID_STATUS_TRANSITION（current_status=cancelled）となったが、決済サービス（模擬）は当該注文（例: PO-00000001）の決済要求を受信済みだった。決済記録は登録されないため、承認された決済要求がシステム上どこにも記録されない。
- 根本原因: ADDR-009 DD-005・INV-006 が『承認の反映は注文行のロックと状態再確認の後に行う』と定め、決済要求の送信はトランザクション外・ロック取得前に行う設計になっている。このため、送信後にキャンセルが確定した場合、FR-031 手順5 の『決済要求を送信しない』を満たせない。実装は Accepted ADR のとおりであり、ADR を変更せずに要件を満たす修正方法が確定できない。
- Error 箇所: app/shop/services/orders.py pay_order（状態判定→決済要求→行ロック再判定の順序）／docs/addr/ADDR-009.md DD-005・INV-006
- 必要だった判断: 同時キャンセル時に決済要求の送信を避ける方式（注文行ロックの保持範囲に決済要求を含める／事前の予約状態を設ける／送信済みの決済要求を打ち消す記録と取消要求を定義する 等）の選択と、ADDR-009 DD-005・INV-006 および ADDR-001 への反映。Integration Test Agent では確定できない。
- 再現性: 決定的（単独実行3回すべて1試行目で再現。flaky ではない）
- 対応内容: ADDR-013（ACTIVE）を採択し、支払では注文行のロックを手順5の状態判定の前に取得して、状態判定→決済要求送信→結果反映を同一トランザクション・同一ロック区間で確定する方式へ決定した（ADDR-009 DD-005・INV-006、ADDR-001 DD-007・INV-004 を更新し、ロック保持中の禁止対象を外部ネットワーク通信・スリープ・他プロセス待ちに限定）。Implementation 工程が ADDR-013 に従って app/shop/services/orders.py の pay_order を是正し、ロック取得後に CREATED 以外であれば決済ゲートウェイを呼び出さずに InvalidStatusTransitionError を送出する実装とした（_authorize_locked_order を新設、否認・連携エラーは決済記録を同一トランザクションで登録しコミット後に例外送出、_record_payment の独立トランザクションを廃止）。Integration Test Agent は Production Code・ADDR・要件を変更していない。
- 対応経路: ADDR（ADDR-013 採択）→ IMPLEMENTATION（app/shop/services/orders.py 是正）
- 修正範囲: ADR=ADDR-013（支払における決済要求送信の排他単位とトランザクション境界。status: ACTIVE） / 実装=app/shop/services/orders.py（pay_order / _authorize_locked_order / _record_payment）のみ変更 / 結合試験コード=なし（Test Case・期待結果・アサーションは変更していない）
- 回帰テスト: IT-AI-GF-023（tests/integration/test_concurrency.py::test_concurrent_payment_and_cancel_matches_sequential_result）
- 検証結果: Production Code 変更後に全ケースを再実行して確認した。IT-AI-GF-023（AC-UC-007-019、各10試行）を単独で3回再実行し3回とも PASS。関連ケース（tests/integration/test_concurrency.py 10件、test_orders_api.py・test_e2e_flow.py・test_admin_api.py 計29件）PASS。結合試験 82ケース全件 PASS（junit.xml 再生成）。全体（単体742件＋結合82件）は docker compose exec -T app pytest で 824 passed / 0 failed。
- 再試験: 対象Case=PASS / 関連Case=PASS / 全体=PASS
  - 対象Case: IT-AI-GF-023 を3回単独再実行し3回とも PASS（1回目 1.59s / 2回目 1.53s / 3回目 1.59s、各10試行）
  - 関連Case: test_concurrency.py（10件）・test_orders_api.py・test_e2e_flow.py・test_admin_api.py の計29ケースが PASS
  - 全体: docker compose exec -T app pytest：824 passed / 0 failed（単体742件・結合82件）。結合のみの再実行（tests/integration）も 82 passed
- 修正ループ: 初回失敗 cycle=0 / 修正回数=1 / 状態=RESOLVED（共通3回ループの1回目の修正（ADDR-013 採択＋実装是正）で解消。4回目の修正ループは発生していない。）

## 5. 未解決事項

なし。検出した Unique Defect 1 件はすべて解消済みで、最終実行は全ケース PASS である（DEF-IT-001: ADDR（ADDR-013 採択）→ IMPLEMENTATION（app/shop/services/orders.py 是正））。

## 6. 観測事項（Test Case の失敗ではないが記録する確認結果）

いずれも今回の Test Case の期待結果に含めていない（＝Failure ではない）が、
試験中に実機で確認した事実として記録する。取扱いは SDLC Orchestrator が判定する。

### OBS-IT-001：全角数字の都道府県コード・郵便番号が入力エラーにならず保存される

- 分類: POSSIBLE_IMPLEMENTATION_ERROR（本サイクルの Test Case では判定していない）
- 関連要件: FR-030, NFR-SC-04
- 要件の記載: 機能要件定義書 FR-030 の入力条件は、都道府県コードを「2桁の半角数字で "01" 以上 "47" 以下」、郵便番号を「半角数字7桁」または「半角数字3桁・ハイフン・半角数字4桁」と定める。
- 実測した挙動: prefecture_code="１３"、postal_code="１２３４５６７"（いずれも全角数字）を含む注文確定が 201 で受理され、配送先に全角数字のまま保存された（ShippingAddress.prefecture_code='１３'、postal_code='１２３４５６７'）。原因は、都道府県コードの判定が str.isdigit()＋int() で全角数字を数字として扱うこと、郵便番号・電話番号・日付の正規表現が \d（Unicode 数字）で半角に限定していないこと。
- 確認方法: C10 是正の作業中に、NFR-LG-09（JIS X 0401）のケース設計のため一時的な確認用テストで実測した（確認後に削除済み。コミットした Test Case には含めていない）。
- 影響: 注文の配送先に半角・全角が混在して保存されうる。出荷は手作業で行うため直ちに業務が停止する種類の問題ではないが、検索・集計・外部帳票との突合で不一致が生じうる。NFR-SC-04（型・桁数・値域・形式のサーバー側検証）の観点でも不足である。
- 現状の扱い: 本サイクルの差し戻し範囲（C10 のテスト追加）の外であり、Integration Test Agent は Production Code を変更できないため、期待結果に含めず観測事項として記録した。Test Case 化すると現状の実装では FAIL となるため、是正方針の決定後にケースを追加する。
- 推奨差し戻し先: IMPLEMENTATION（半角限定の検証へ是正）。要件の意図の確認が必要な場合は REQUIREMENTS

## 7. 本サイクル（修正3回目）で是正した Test Error

| Case ID | 分類 | 原因 | 是正内容 | 結果 |
| --- | --- | --- | --- | --- |
| IT-AI-GF-081 | TEST_ERROR | pytest-django が実行時に設定上のDB名をテストDB名へ置き換えるため、Test Code 側の照合条件（設定値と異なること）が成立しなかった | 環境変数 DB_NAME を基準に `test_<DB_NAME>` と一致することを照合する条件へ是正 | 再実行して PASS |
| IT-AI-GF-082 | TEST_ERROR | 環境固有の値の非混入を照合する対象に真偽値（true / false）を含めたため、設定ソース内の真偽値の読み取り定義に一致して失敗した | 照合対象を環境固有の値に限定し、真偽値は設定値の反映で判定する条件へ是正 | 再実行して PASS |

いずれも期待結果を Production Code に合わせて変更していない。Production Code は変更していない。

## 8. 未解決事項の持越し（共通3回ループ）

- issue_id: UNRESOLVED-698b995280f60801（INTEGRATION_TEST / TEST_TRACEABILITY_MISSING）
- 本サイクル（修正3回目）後の残存: Traceability C10 59 件
- 影響: 当該要件が自動テストで確かめられていない。結合試験の失敗・未実行ではなく、結合試験は 138 ケース全件 PASS、未解決 Defect 0 件、TEST_SPEC_CONFLICT 0 件、AUTOMATION_BLOCKED 0 件。
- 根拠: 要件本文の検証方法欄が「運用時に測定」「性能テスト」「負荷テスト・耐久テスト」「移行リハーサル」「脆弱性診断」「互換性・操作性テスト」「本番環境の構成・設定レビュー」「該当なし」である（`non-automatable-requirements.md` 最終版 2章に要件ごとの引用と理由を記録）。
- 推奨対応先: 受入試験・運用準備における人手検証（同 5章の申し送り）。Traceability C10 の扱いは SDLC Orchestrator が継続判定する。
