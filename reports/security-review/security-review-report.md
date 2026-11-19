# Security Review Report（FULL）

- run_id: RUN-AOBA-EC-1118
- Audit Scope: FULL
- Status: **FAIL**
- 生成日時: 2026-11-20T04:55:00+09:00
- source_baseline_sha256（FINAL design-manifest）: `fea9a82a98b5e04a5b79e5e0fbbff4cddf37a3b19748634ee5d47b7bbe69865c`
- 推奨差し戻し先（Recommended Route）: **REQUIREMENTS**

過去Runブランチ・過去Runの reports を参照せず、前回 Security 判定を流用せず、現版の要件・Steering・設計・ADDR-001〜014・app/・compose.yaml・.env.example・requirements*.txt・Dockerfile・app/seed・UT/IT コードと結果（unit-exec-10、it-exec-7、security-reference.json、dependency-vulnerability-osv.json）・unresolved-results.json を独立評価。前回監査以降の変更は結合試験コードのみ（Production Code・構成は未変更）を確認。テストは再実行していない。成果物は修正していない。Secret 値は記録していない。

## Security Summary

- Criteria: 8 FAIL / 0 PASS / 0 NOT_APPLICABLE（計 8）
- Issues: 3件（新規 0、既知 LOW 再掲 3）、Blocking: 0
- 既知の未解決参照: 12件
- 上流 Validator: Unit Test FAIL（729/737）、Integration Test FAIL（133/134）

## Criteria Results

| Criterion | Result | FAIL の原因（既知ID） | 理由 |
|---|---|---|---|
| authentication-authorization | FAIL | UNRESOLVED-32af0f4a0ca9c80f | 実装は要件どおり：API は Bearer（照合値のみ保持・256bit乱数・期限判定）、画面はセッション（django_login でキー更新・HttpOnly・無操作30分）。require_user で認証→区分の順に判定し、注文・カートは buyer=user で絞り込み（他購入者は404）。GF-066 の全44 URL のアクセス表で来訪者401/302、購入者→管理403、他購入者→404、管理者→購入者機能403、CSRF なし更新は全て403を確認。ただし要件段階の既知の未解決 UNRESOLVED-32af0f4a0ca9c80f（総当たり・多要素認証を対象外のまま本番稼働する受容可否 NOQ-08 未決、本番でも購入者入力 mock_instruction の承認だけで支払済となる模擬決済固定）が現版でも残るため FAIL（新規 Issue にしない）。 |
| data-protection | FAIL | UNRESOLVED-32af0f4a0ca9c80f, UNRESOLVED-6de5eec64599b907 | 応答・ログの機密非出力（IT-056・GF-026・GF-065 leaked={}、ログ出力先は標準出力のみ・LOG-03 はパスのみ）、パスワードは独自ハッシャーで保持、ログイン状態は照合値のみ保持。ただし既知 UNRESOLVED-32af0f4a0ca9c80f（SEC-REQ-004：load_initial_data --reset に実行環境の制限がなく、本番で注文・注文状態履歴等を全削除し得る。NFR-LG-03 の7年保存と要件内で矛盾）が残る。加えて既知 UNRESOLVED-6de5eec64599b907 の経路では、アプリの共通処理を経ずに Gunicorn の error log に要求 URI（クエリを含む）付きトレースバックが出る。 |
| dependency-configuration | FAIL | UNRESOLVED-32af0f4a0ca9c80f, UNRESOLVED-0b5694db22a0bead, SR-ADDR-R5-001, SR-ADDR-R6-001 | 実装の制御：MINICOMMERCE_ENV 必須・真偽値は小文字 true/false 以外で起動失敗、production で DEBUG/開発用機能 true は ImproperlyConfigured、test_support は開発用機能時のみ INSTALLED_APPS、時刻固定・障害注入・模擬決済異常は同フラグで遮断、production で Secure Cookie・HSTS・非HTTPS 403、compose は 127.0.0.1 公開・秘密は必須参照形式、依存はハッシュ固定（--require-hashes）・ベースイメージはダイジェスト固定・非root 実行、OSV 照合 23件で既知脆弱性0件（requirements の SHA-256 は現版と一致）。ただし既知 UNRESOLVED-0b5694db22a0bead（本番制御の設計→ADDR 引渡し漏れ）・SR-ADDR-R5-001/R6-001（環境別設定・本番制御の ADDR 判断）・UNRESOLVED-32af0f4a0ca9c80f（本番の模擬決済固定、--reset の環境無制限）が未解決。LOW：SR-FULL-1118-001・SR-UT-R3-001。 |
| error-logging | FAIL | UNRESOLVED-6de5eec64599b907 | DRF 共通例外ハンドラ・WebExceptionMiddleware・handler400/403/404/500 で内部情報なしの応答、LOG-02 は例外クラス・発生箇所のみ、django.* ロガーは NullHandler。しかし既知 UNRESOLVED-6de5eec64599b907：Content-Type の charset=undefined/idna と非 ASCII クエリで WSGIRequest 生成時に UnicodeError がアプリ外へ送出され 500（UT 8件・IT-058 FAIL）、LOG-03 が出ず Gunicorn error log に URI 付きトレースバックが出力される。LOW：SR-FULL-1118-002（Server: gunicorn ヘッダー）。 |
| input-validation-injection | FAIL | UNRESOLVED-6de5eec64599b907 | DB 操作は ORM とパラメータ化 SQL（cursor.execute の %s のみ）で文字列連結なし、subprocess/eval/mark_safe/｜safe なし、テンプレート自動エスケープ有効、戻り先 next は同一サイト相対パスのみ。GF-066 動的簡易診断 417 probe（XSS・SQLi・パス・テンプレート・NUL・全角長大値）で findings 0件、IT-059（NUL）・IT-060（XSS）・UT の SQL/OS コマンド注入文字列は PASS。しかし既知 UNRESOLVED-6de5eec64599b907：config/wsgi.py → common/middleware.py is_unusable_charset が _is_text_encoding 偽の方式（rot13 等）しか拒否せず、undefined/idna を通過させるため NFR-SC-04（全外部入力をシステムが検証し入力エラー）を満たさない（UT test_undecodable_text_charset_with_query_is_input_error_400 ×4、test_multipart_with_undecodable_charset_is_input_error_400 ×4、IT-058 FAIL）。 |
| secret-credentials | FAIL | UNRESOLVED-32af0f4a0ca9c80f | settings.py は秘密鍵・DB 利用者名/パスワードを既定値なしの必須環境変数から取得、.env は .gitignore 対象で未保存、.env.example の秘密項目は空欄、compose は未設定時に起動失敗、Production Code に Hard-coded Secret なし、ログ・エラー応答に秘密情報なし。試験の資格情報は架空値（example.com）で本番資格情報の利用なし。ただし既知 UNRESOLVED-32af0f4a0ca9c80f（SEC-REQ-003：管理者2名を含む5利用者の初期パスワードを平文で定義ファイル app/seed/initial_data.json に保持する要件・OQ-PJ-003 未決）が残る。同ファイルが本番イメージにも同梱される点は SR-FULL-1118-001（LOW）。値は本レポートに記録しない。 |
| security-test-coverage | FAIL | UNRESOLVED-e1d9dfe900863622 | UT/IT に要件由来の期待値でセキュリティ試験が存在（IT-002 認証失敗の非区別・監査、IT-006/IT-008 権限表、IT-010・UT CSRF、IT-060 XSS、IT-059 NUL、UT SQL注入、IT-056/GF-026 ログ機密非出力、UT 本番プロファイル強制・非HTTPS拒否、GF-064 OSV 照合、GF-065 個人情報、GF-066 動的簡易診断、GF-070 本番 HTTP 拒否）。失敗中の UT 8件・IT-058 は欠陥検出であり試験欠落ではない。しかし既知 UNRESOLVED-e1d9dfe900863622：必須の NFR-SC-29（稼働開始前の脆弱性診断ツールによる全画面・全API 動的診断と高以上0件の再診断）、NFR-SC-21/NFR-LG-07 の VUL-02/03/08/09/10/11 診断、NFR-SC-11 のコンテナ OS パッケージ照合が未実施（nfr-verification-scope で PARTIAL_IT・counts_as_quality_pass=false）であり、検証は簡易診断に留まる。LOW：SR-UT-R2-001。 |
| cross-phase-security-consistency | FAIL | UNRESOLVED-6de5eec64599b907, UNRESOLVED-60a549ca11f16034, UNRESOLVED-0b5694db22a0bead, SR-ADDR-R5-001, SR-ADDR-R6-001, UNRESOLVED-32af0f4a0ca9c80f | 要件 NFR-SC-04 → ADDR-001 4.3 の7・ADDR-012 → UT/IT（400 を期待）は一貫しているが、実装は undefined/idna で 500（既知 UNRESOLVED-6de5eec64599b907）。reports/addr/implementation-handoff.json・reports/architecture/design-gate.json が存在せず実装引渡し Gate 未成立のため、IMPLEMENTATION 以降で有効な ADDR 判断を確認できない（既知 UNRESOLVED-60a549ca11f16034、UNRESOLVED-0b5694db22a0bead、SR-ADDR-R5-001/R6-001）。要件段階のセキュリティ未決（UNRESOLVED-32af0f4a0ca9c80f）が実装・試験に“対象外/模擬固定”として引き継がれている。 |

## Issues

| Issue ID | 区分 | Classification | Severity | Recommended Route | Resolved |
|---|---|---|---|---|---|
| SR-FULL-1118-001 | 既知（再確認） | DEPENDENCY_CONFIGURATION_ISSUE | LOW | IMPLEMENTATION | False |
| SR-FULL-1118-002 | 既知（再確認） | ERROR_LOGGING_SECURITY_ISSUE | LOW | IMPLEMENTATION | False |
| SR-UT-R3-001 | 既知（再確認） | DEPENDENCY_CONFIGURATION_ISSUE | LOW | IMPLEMENTATION | False |

### SR-FULL-1118-001（LOW）

- Classification: DEPENDENCY_CONFIGURATION_ISSUE
- Source: app/Dockerfile
- Affected: app/Dockerfile, .dockerignore, app/seed/initial_data.json, app/initial_data/management/commands/load_initial_data.py
- Requirement: NFR-SC-25, VUL-08, FR-060
- Related ADDR: ADDR-009 INV-002, ADDR-010 DD-007, ADDR-014
- Description: 本番用を含むアプリケーションイメージに検証用定義ファイル app/seed/initial_data.json（架空の管理者を含む利用者の平文初期パスワード）が同梱され、.dockerignore で除外されていない。load_initial_data に実行環境の制限がないため、本番で誤投入されるとリポジトリ上で既知の資格情報を持つ管理者が作成され得る。
- Evidence: app/Dockerfile の COPY app/（全体複製）、.dockerignore に app/seed の除外なし、app/seed/initial_data.json の users[] の初期パスワード項目（平文。値は記録しない。ドメインは example.com）、load_initial_data.py docstring『実行環境による --reset の制限は設けない』。現版で再確認（前回から未変更）。
- Severity: LOW（非 Blocking）
- Recommended Route: IMPLEMENTATION

### SR-FULL-1118-002（LOW）

- Classification: ERROR_LOGGING_SECURITY_ISSUE
- Source: app/gunicorn.conf.py
- Affected: app/gunicorn.conf.py
- Requirement: NFR-SC-10, NFR-SC-29
- Related ADDR: ADDR-014
- Description: 全応答（エラー応答を含む）に Gunicorn 既定の Server: gunicorn ヘッダーが付く（版は含まない）。NFR-SC-10 はライブラリの名称と版を含めないことを求めており、名称の露出は動的診断で情報露出として指摘され得る。
- Evidence: app/gunicorn.conf.py に Server ヘッダーを抑止・置換する設定なし（Gunicorn 既定動作）。現版で再確認（前回から未変更）。
- Severity: LOW（非 Blocking）
- Recommended Route: IMPLEMENTATION

### SR-UT-R3-001（LOW）

- Classification: DEPENDENCY_CONFIGURATION_ISSUE
- Source: app/requirements-dev.in
- Affected: app/requirements-dev.in, app/requirements-dev.txt, app/tests/unit/coverage.ini
- Requirement: VUL-10, NFR-SC-11
- Related ADDR: ADDR-014 DD-008
- Description: 単体試験のカバレッジ計測に用いる coverage・pytest-cov がハッシュ固定の開発依存に含まれず、試験環境の再現性・供給網固定の範囲外となっている。
- Evidence: app/requirements-dev.in / requirements-dev.txt に coverage・pytest-cov の記載なし、app/tests/unit/coverage.ini は存在。現版で再確認。
- Severity: LOW（非 Blocking）
- Recommended Route: IMPLEMENTATION

## Evidence（既知の未解決と Criterion FAIL の対応）

| 既知ID | 起点工程 | 起点で Blocking | FAIL 原因とした Criterion | 現版での確認 |
|---|---|---|---|---|
| UNRESOLVED-32af0f4a0ca9c80f | REQUIREMENTS | True | authentication-authorization, secret-credentials, data-protection, dependency-configuration, cross-phase-security-consistency | 現版で残存：payments/gateway.py get_gateway は模擬固定・orders OrderPaymentApi が mock_instruction を購入者入力で受理、FR-OUT-11/NFR-SC-13/14/27（総当たり・MFA 対象外、NOQ-08 未決）、app/seed/initial_data.json の管理者初期パスワード平文、load_initial_data --reset に環境制限なし |
| UNRESOLVED-0b5694db22a0bead | ARCHITECTURE | True | dependency-configuration, cross-phase-security-consistency | 実装（config/settings.py・config/env.py）は本番強制を実装済みだが、設計→ADDR 引渡し（Gate）が未成立 |
| UNRESOLVED-60a549ca11f16034 | ARCHITECTURE | True | cross-phase-security-consistency | reports/addr/implementation-handoff.json・reports/architecture/design-gate.json 不在（実装引渡し Gate 未成立） |
| UNRESOLVED-34471205dd0539bc | REQUIREMENTS | False | - | expected-fr.txt の FR-OUT 分類（Traceability 領域）。Security Criterion の FAIL 原因ではない |
| UNRESOLVED-6de5eec64599b907 | IMPLEMENTATION | True | input-validation-injection, error-logging, data-protection, cross-phase-security-consistency | unit-exec-10：8件 FAIL（charset undefined/idna）、it-exec-7：IT-058 FAIL（undefined/idna で 500）。Production Code は前回監査以降未変更 |
| UNRESOLVED-e1d9dfe900863622 | INTEGRATION_TEST | True | security-test-coverage | NFR-SC-29・NFR-SC-21・NFR-LG-07・NFR-SC-11 が PARTIAL_IT（counts_as_quality_pass=false）。GF-064/065/066/070 の簡易検証は PASS・findings 0件だが、ツールによる動的診断・VUL-02/03/08/09/10/11 診断・コンテナ OS パッケージ照合は未実施 |
| SR-ADDR-R5-001 | ADDR | True | dependency-configuration, cross-phase-security-consistency | 環境別設定・本番制御の ADDR 判断の既知指摘。実装引渡し Gate 不在のため解消を確認できない |
| SR-ADDR-R6-001 | ADDR | True | dependency-configuration, cross-phase-security-consistency | SR-ADDR-R5-001 と同系統。解消を確認できない |
| SR-UT-R2-001 | UNIT_TEST | False | - | LOW・Advisory（台帳管理）。FAIL 要因としない |
| SR-UT-R3-001 | IMPLEMENTATION | False | - | LOW。issues に再掲（現版で残存） |
| SR-FULL-1118-001 | IMPLEMENTATION | False | - | LOW。issues に再掲（現版で残存） |
| SR-FULL-1118-002 | IMPLEMENTATION | False | - | LOW。issues に再掲（現版で残存） |

## Recommended Route

最上流の根本原因は REQUIREMENTS（UNRESOLVED-32af0f4a0ca9c80f）。ARCHITECTURE（UNRESOLVED-0b5694db22a0bead・60a549ca11f16034）、ADDR（SR-ADDR-R5-001/R6-001）、IMPLEMENTATION（UNRESOLVED-6de5eec64599b907 と LOW 3件）、INTEGRATION_TEST（UNRESOLVED-e1d9dfe900863622）も未解決。

## Summary

FULL Security Review は FAIL。8 Criteria 全て FAIL（いずれも既知の未解決に起因）。新規 Issue 0件。再確認した既知 LOW 3件（非 Blocking）を issues に記載。上流 UT/IT Validator も FAIL。
