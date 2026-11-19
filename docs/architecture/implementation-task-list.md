# 実装タスク一覧・進捗

## 1. 文書情報

| 項目 | 内容 |
| --- | --- |
| Document ID | DOC-IMPL-TASK-001 |
| 対象システム | MiniCommerce（株式会社あおば雑貨 会員向け自社ECサイト） |
| Baseline / Commit | 958677fe4a672dc82902289cfd4b0da5cfac39e5＋作業ツリーの要件改版（RUN-AOBA-EC-1118 Requirements 工程 2026-11-19） |
| Version | 1.3 |
| Status | DRAFT |
| Owner | Architecture Agent（RUN-AOBA-EC-1118）／ Implementation Team |
| Last Updated | 2026-11-19 |

## 2. Source Baseline

| Source Type | ID / Path | Required Status / Version | Purpose |
| --- | --- | --- | --- |
| Requirements | docs/requirements/requirements.md と全リンク先（functional 1.4、data 1.4、non_functional 1.4、external_interface 1.2、ui_report、business、glossary）、docs/requirements/expected-fr.txt（26件） | レビュー中（REQUIREMENTS: CONTINUE_WITH_UNRESOLVED） | Scope / Requirement |
| Use Case | docs/requirements/use-cases/UC-001.md〜UC-013.md（9章 AC が正本） | 作成中 | Behavior / AC |
| ADR | None（docs/addr・docs/adr に既存判断なし。後続ADDR工程で作成される判断を実装時に必ず読む） | ACTIVE の ADDR のみ有効 | Architecture Decision |
| Detailed Design | ENT-001〜ENT-015（docs/architecture/db-logical-design.md）、FILE-001（docs/architecture/files/FILE-001.md） | REVIEW 1.1（db-logical-design.md 1.1、FILE-001.md 1.1） | Implementation Detail |
| Project AI Steering | .github/project-context/project-ai-steering.md | 1.3（DRAFT） | PJ-specific confirmed Preconditions / Constraints |

## 3. Task Decomposition Rules

Taskは以下の条件を満たす単位へ分解する。

- 1 Taskの目的と完了条件を明確に説明できる。
- Related Requirement / ADR / Design Referenceが特定できる。
- 依存Taskを明示できる。
- 実装後にBuild / Test / Validator等で完了を確認できる。
- 複数の独立した変更目的を不必要に1 Taskへまとめない。
- Requirementに存在しない機能追加をTask化しない。
- 新たなArchitecture Decisionが必要なTaskは実装開始前に解決する。
- 本書は ADDR 工程の前に作成した。実装担当は各 Task の着手前に、本書と論理DB設計・FILE定義に加えて後続ADDR（docs/addr/ の ACTIVE な ADDR）と reports/addr/implementation-handoff.json を読み、Task・Entity・File に結び付いた判断（DD/INV/ASM・実装拘束）に従う。判断が未作成の重要方式は推測で実装せず ADDR へ戻す。
- 画面と Web API は同一の業務ルール・判定順序・通知内容に従う（CMN-34、FCN-09、Steering 5章）。業務規則を画面側に重複実装しない。
- Completion Criteria / Validation で使う他 Task の成果（試験用状態の設定手段、ログイン機能等）は Depends On に宣言し、後続 Wave の Task の成果を完了条件にしない。後続 Task でしか成立しない検証はその Task の完了条件へ置く。
- 非機能要件は、実装または検証を要するものを1件以上の Task の Related Requirement と完了条件・検証方法に割り当て、実装 Task の対象外とするもの（本番基盤・運用・移行工程・試験工程・該当なし）は 7章に理由を記録する。画面を持つ Task は、自 Task の画面について画面共通の非機能要件（NFR-US-01、NFR-US-02、NFR-US-05、NFR-US-06、NFR-US-07、NFR-PF-03）を完了条件・検証方法に含め、画面をまたぐ一連の操作は TASK-020 で確認する。性能の測定（NFR-PF-01〜NFR-PF-04、NFR-PF-09）は試験工程の性能テスト（later phase）とする。
- 完了条件に含める UC の AC は、AC 単位で、Given の前提操作（ログイン状態、試験用状態の設定、障害状態）と When・Then が用いる機能（FR・画面 SCR）を実装する Task がすべて当該 Task 自身または Depends On（直接または推移的）に含まれるものに限る。Given の業務データの状態（登録済みの利用者・商品・注文等）は試験データとして用意でき、その作成機能の Task への依存としない。複数の機能 Task を横断する AC は、それらを Depends On に持つ TASK-020 の完了条件で確認する。各機能 Task の完了条件は除外する AC の ID を明記する。

## 4. Task Summary

| Task ID | Title | Type | Related Requirement | Related ADR | Target Area | Depends On | Priority | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| TASK-001 | 開発・実行基盤（Docker Compose、Django 設定、環境別設定、試験用DB切替、静的解析・テスト実行環境） | CONFIG | NFR-EN-01、NFR-EN-02、NFR-EN-03、NFR-EN-04、NFR-EN-09、NFR-EN-10、NFR-EN-11、NFR-OM-05、NFR-OM-06、NFR-OM-17、NFR-SC-07、NFR-SC-10、NFR-SC-11、NFR-SC-21、NFR-EN-05、NFR-EN-08、NFR-SC-02、NFR-SC-19、NFR-PF-16、NFR-EN-07、NFR-EN-12、NFR-OM-19、NFR-LG-01、NFR-LG-07 | None（後続ADDR確認） | リポジトリ直下・app/ のプロジェクト設定 | None | HIGH | TODO |
| TASK-002 | 共通基盤（時刻、入力正規化、判定順序・エラー種別、ページング、ログ、共通画面） | IMPLEMENT | FR-001、FR-011、FR-032、FR-040、FR-041、NFR-OM-01、NFR-OM-02、NFR-SC-04、NFR-SC-05、NFR-SC-06、NFR-SC-10、NFR-US-04、NFR-PF-08、NFR-US-01、NFR-US-02、NFR-US-05、NFR-US-06、NFR-US-07、NFR-LG-08、NFR-PF-03、NFR-US-03、NFR-OM-11、NFR-OM-18、NFR-LG-01、NFR-EN-04、NFR-EN-05 | None（後続ADDR確認） | 共通コンポーネント | TASK-001 | HIGH | TODO |
| TASK-003 | 利用者・監査ログのデータモデル（ENT-001、ENT-015） | MIGRATION | FR-001、FR-002、FR-003、FR-060、NFR-SC-01、NFR-SC-23、NFR-OM-03 | None（後続ADDR確認） | データモデル・マイグレーション | TASK-001 | HIGH | TODO |
| TASK-004 | 商品カタログ・在庫・クーポンのデータモデル（ENT-002〜ENT-007） | MIGRATION | FR-010、FR-011、FR-012、FR-024、FR-040、FR-060 | None（後続ADDR確認） | データモデル・マイグレーション | TASK-001 | HIGH | TODO |
| TASK-005 | カート・注文系のデータモデル（ENT-008〜ENT-014） | MIGRATION | FR-020、FR-030、FR-031、FR-033、FR-042、NFR-LG-03、NFR-SC-23、NFR-LG-09、NFR-OM-11 | None（後続ADDR確認） | データモデル・マイグレーション | TASK-003、TASK-004 | HIGH | TODO |
| TASK-006 | 会員登録・ログイン・ログアウト・利用者情報照会と認証・権限判定 | IMPLEMENT | FR-001、FR-002、FR-003、FR-004、FR-060、NFR-SC-01、NFR-SC-03、NFR-SC-08、NFR-SC-09、NFR-SC-12、NFR-SC-15、NFR-SC-18、NFR-SC-19、NFR-SC-22、NFR-US-01、NFR-US-02、NFR-US-05、NFR-US-06、NFR-US-07、NFR-LG-08、NFR-PF-03、NFR-PF-09、NFR-PF-16、NFR-SC-16、NFR-US-03、NFR-US-10、NFR-OM-11、NFR-LG-01、NFR-EN-05、NFR-SC-24 | None（後続ADDR確認） | 会員・認証（業務処理・Web API・画面） | TASK-002、TASK-003、TASK-017 | HIGH | TODO |
| TASK-007 | 商品分類一覧・商品一覧検索・商品詳細照会 | IMPLEMENT | FR-010、FR-011、FR-012、NFR-PF-01、NFR-PF-08、NFR-US-01、NFR-US-02、NFR-US-05、NFR-US-06、NFR-US-07、NFR-LG-08、NFR-PF-03、NFR-LG-02、NFR-EN-05 | None（後続ADDR確認） | 商品カタログ（業務処理・Web API・画面） | TASK-002、TASK-004 | HIGH | TODO |
| TASK-008 | 決済サービス（模擬）と決済要求の呼出し（IFR-001） | IMPLEMENT | FR-031、NFR-EN-05、NFR-SC-24、NFR-OM-11、NFR-OM-18、NFR-PF-17、NFR-LG-05、NFR-LG-01、NFR-SC-21、NFR-SC-06 | None（後続ADDR確認） | 外部IF（模擬決済） | TASK-002 | HIGH | TODO |
| TASK-009 | 注文金額計算（FR-026） | IMPLEMENT | FR-026、FR-020、FR-024、FR-030、NFR-LG-06、NFR-PF-11 | None（後続ADDR確認） | カート・注文の業務処理 | TASK-002、TASK-005 | HIGH | TODO |
| TASK-010 | 在庫単位一覧照会（管理者） | IMPLEMENT | FR-040、NFR-PF-08、NFR-US-01、NFR-US-02、NFR-US-05、NFR-US-06、NFR-US-07、NFR-LG-08、NFR-PF-03、NFR-PF-01、NFR-EN-05 | None（後続ADDR確認） | 管理（業務処理・Web API・画面） | TASK-004、TASK-006 | MEDIUM | TODO |
| TASK-011 | 初期データ一括投入（FILE-001） | IMPLEMENT | FR-060、NFR-OM-04、NFR-OM-13、NFR-PF-10、NFR-SC-08、NFR-SC-15、NFR-EN-04、NFR-MG-04、NFR-MG-07、NFR-OM-11、NFR-OM-19、NFR-MG-03、NFR-SC-22、NFR-SC-23 | None（後続ADDR確認） | 運用機能（サーバー上での実行） | TASK-002、TASK-003、TASK-004、TASK-005、TASK-006 | HIGH | TODO |
| TASK-012 | カート照会・明細追加・数量変更・削除・クーポン適用・解除 | IMPLEMENT | FR-020、FR-021、FR-022、FR-023、FR-024、FR-025、NFR-US-01、NFR-US-02、NFR-US-05、NFR-US-06、NFR-US-07、NFR-LG-08、NFR-PF-03、NFR-PF-01、NFR-PF-02、NFR-PF-16、NFR-US-09、NFR-US-10、NFR-LG-02、NFR-LG-06、NFR-EN-05 | None（後続ADDR確認） | カート（業務処理・Web API・画面） | TASK-005、TASK-006、TASK-007、TASK-009、TASK-017 | HIGH | TODO |
| TASK-013 | 検証用初期データ定義ファイル（架空データ） | TEST_SUPPORT | FR-060、NFR-SC-25、NFR-OM-04、NFR-LG-01 | None（後続ADDR確認） | app/seed/ | TASK-011 | MEDIUM | TODO |
| TASK-014 | 注文確定（在庫一括引当・注文番号発行） | IMPLEMENT | FR-030、NFR-PF-07、NFR-PF-11、NFR-US-10、NFR-US-01、NFR-US-02、NFR-US-05、NFR-US-06、NFR-US-07、NFR-LG-08、NFR-PF-03、NFR-PF-02、NFR-PF-04、NFR-US-03、NFR-US-09、NFR-LG-02、NFR-LG-06、NFR-LG-09、NFR-EN-05 | None（後続ADDR確認） | 注文（業務処理・Web API・画面） | TASK-009、TASK-012、TASK-017 | HIGH | TODO |
| TASK-015 | 支払（模擬決済） | IMPLEMENT | FR-031、NFR-PF-02、NFR-US-01、NFR-US-02、NFR-US-05、NFR-US-06、NFR-US-07、NFR-LG-08、NFR-PF-03、NFR-US-10、NFR-PF-17、NFR-LG-05、NFR-EN-05 | None（後続ADDR確認） | 注文（業務処理・Web API・画面） | TASK-008、TASK-014、TASK-016、TASK-017 | HIGH | TODO |
| TASK-016 | 注文履歴一覧・注文詳細照会・注文キャンセル（購入者）と在庫戻し | IMPLEMENT | FR-032、FR-033、FR-034、NFR-US-01、NFR-US-02、NFR-US-05、NFR-US-06、NFR-US-07、NFR-LG-08、NFR-PF-03、NFR-PF-01、NFR-PF-02、NFR-US-09、NFR-US-10、NFR-LG-06、NFR-EN-05、NFR-SC-24 | None（後続ADDR確認） | 注文（業務処理・Web API・画面） | TASK-014 | HIGH | TODO |
| TASK-017 | 試験用状態の設定手段（現在時刻・模擬決済の異常応答） | TEST_SUPPORT | NFR-OM-06、NFR-OM-17、FR-002、FR-024、FR-031 | None（後続ADDR確認） | 試験支援（ENV-01 限定） | TASK-002、TASK-008 | HIGH | TODO |
| TASK-018 | 注文一覧検索・注文詳細照会・出荷登録・配達完了登録・注文キャンセル（管理者） | IMPLEMENT | FR-041、FR-042、FR-043、FR-044、FR-045、NFR-SC-06、NFR-US-01、NFR-US-02、NFR-US-05、NFR-US-06、NFR-US-07、NFR-LG-08、NFR-PF-03、NFR-PF-01、NFR-PF-02、NFR-US-09、NFR-US-10、NFR-LG-06、NFR-EN-05、NFR-SC-24 | None（後続ADDR確認） | 管理（業務処理・Web API・画面） | TASK-015、TASK-016、TASK-017 | HIGH | TODO |
| TASK-019 | 注文確定途中の障害の設定手段と途中障害時の無変更の検証 | TEST_SUPPORT | NFR-OM-06、FR-030、NFR-SC-10、NFR-OM-17 | None（後続ADDR確認） | 試験支援（ENV-01 限定）・注文確定の結合テスト | TASK-014、TASK-017 | HIGH | TODO |
| TASK-020 | 機能横断の受入条件の結合確認（画面遷移・権限判定・機能間の反映） | TEST_SUPPORT | FR-001、FR-002、FR-003、FR-010、FR-011、FR-012、FR-020、FR-021、FR-026、FR-030、FR-033、FR-034、FR-040、FR-041、FR-060、NFR-SC-03、NFR-SC-09、NFR-OM-11、NFR-OM-18、NFR-US-01、NFR-US-06、NFR-US-07、NFR-US-08、NFR-SC-25 | None（後続ADDR確認） | 結合テスト（複数の機能 Task を横断する UC の AC） | TASK-006、TASK-007、TASK-010、TASK-011、TASK-012、TASK-014、TASK-015、TASK-016、TASK-017、TASK-018 | HIGH | TODO |
| TASK-021 | 依存ライブラリ・実行環境の取得元・版の確認と既知脆弱性の確認（リリース前） | OTHER | NFR-SC-11、NFR-SC-21、NFR-EN-10、NFR-EN-12、NFR-LG-07 | None（後続ADDR確認） | 依存ライブラリ・実行環境の構成（リポジトリ全体） | TASK-013、TASK-019、TASK-020 | HIGH | TODO |

## 5. Execution Order / Dependency

| Wave | Task IDs | Start Condition |
| ---: | --- | --- |
| 1 | TASK-001 | 設計Gate・後続ADDRの実装引渡しGate（reports/architecture/architecture-gate.json）が成立していること |
| 2 | TASK-002、TASK-003、TASK-004 | TASK-001 DONE |
| 3 | TASK-005、TASK-007、TASK-008 | TASK-005 は TASK-003・TASK-004、TASK-007 は TASK-002・TASK-004、TASK-008 は TASK-002 が DONE |
| 4 | TASK-009、TASK-017 | TASK-009 は TASK-002・TASK-005、TASK-017 は TASK-002・TASK-008 が DONE |
| 5 | TASK-006 | TASK-002・TASK-003・TASK-017 DONE |
| 6 | TASK-010、TASK-011、TASK-012 | TASK-010 は TASK-004・TASK-006、TASK-011 は TASK-002〜TASK-006、TASK-012 は TASK-005・TASK-006・TASK-007・TASK-009・TASK-017 が DONE |
| 7 | TASK-013、TASK-014 | TASK-013 は TASK-011、TASK-014 は TASK-009・TASK-012・TASK-017 が DONE |
| 8 | TASK-016、TASK-019 | TASK-016 は TASK-014、TASK-019 は TASK-014・TASK-017 が DONE |
| 9 | TASK-015 | TASK-008・TASK-014・TASK-016・TASK-017 DONE |
| 10 | TASK-018 | TASK-015・TASK-016・TASK-017 DONE |
| 11 | TASK-020 | TASK-006・TASK-007・TASK-010・TASK-011・TASK-012・TASK-014〜TASK-018 DONE |
| 12 | TASK-021 | TASK-013・TASK-019・TASK-020 DONE（推移的に TASK-001〜TASK-020 の全 Task が DONE） |

## 6. Task Details

### TASK-001 `開発・実行基盤（Docker Compose、Django 設定、環境別設定、試験用DB切替、静的解析・テスト実行環境）`

#### Metadata

| 項目 | 内容 |
| --- | --- |
| Type | CONFIG |
| Priority | HIGH |
| Status | TODO |
| Target Area | リポジトリ直下（compose.yaml、.env.example、README.md）、app/ の Django プロジェクト設定 |
| Depends On | None |
| Blocks | TASK-002、TASK-003、TASK-004 |

#### Source References

| Type | ID / Path | Relevant Section / Reason |
| --- | --- | --- |
| Requirement | NFR-EN-01、NFR-EN-02、NFR-EN-03、NFR-EN-04、NFR-EN-05、NFR-EN-08、NFR-EN-09、NFR-EN-10、NFR-EN-11、NFR-OM-05、NFR-OM-06、NFR-OM-17、NFR-SC-07、NFR-SC-10、NFR-SC-11、NFR-SC-21（VUL-08、VUL-09、VUL-10）、NFR-SC-02、NFR-SC-19、NFR-PF-16、NFR-EN-07、NFR-EN-12、NFR-OM-19、NFR-LG-01、NFR-LG-07 | Python 3.12・Django 5.2 LTS・DRF・PostgreSQL 16、JST/UTF-8、外部接続なし、1操作での起動・全テスト実行、秘密情報をリポジトリに含めない、環境ごとに異なる設定値をプログラム変更なしで変更（NFR-OM-17）、本番でデバッグ用情報を表示しない（NFR-SC-10 後段）、本番で Django 付属の開発用サーバーを使用しない（NFR-EN-08、VUL-08）、依存ライブラリ・実行環境の取得元と版を特定でき同じ構成を再現できる（VUL-10）、採用製品をサポート期限内の版とする（NFR-EN-10、VUL-09）、依存ライブラリに既知の重大な脆弱性（CVSS 7.0以上）が無い（NFR-SC-11、VUL-09。リリース前の最終確認は TASK-021） |
| Use Case / AC | UC-001〜UC-013（全 AC の実行前提） | 全機能の実行・試験環境 |
| ADR | None（後続ADDR：試験用DB切替・試験用状態の方式（manifest 候補 test-state-control）、画面と Web API の構成（候補 application-structure）、環境別設定値の管理・本番での開発用機能の無効化・本番用 Web/AP サーバー・依存ライブラリと実行環境の取得元・版の固定と記録の方式（候補 environment-configuration）を確認。本番環境で、ログイン状態を示す情報・CSRF 対策の値を暗号化された通信でのみ送信させ、HTTP で業務データを受け付けない設定の実現方式（候補 environment-configuration・authentication-session）、処理能力の増強をプログラムの変更なしに行える構成（候補 environment-configuration・authentication-session・application-structure）、依存ライブラリのライセンスの確認・記録（候補 environment-configuration）も確認） | 方式判断は ADDR 工程 |
| Detailed Design | .github/project-context/project-ai-steering.md 3章・4章・5章・6.2 | Docker Compose の app・db 2サービス、localhost:8000、5432、app/ 配置、.env.example |

#### Objective

全機能の実装・自動テストの前提となる実行環境を整備し、DB 接続先を環境変数で切り替えて、自動テストを使い捨ての試験用データベース（Docker の PostgreSQL 16 等の Disposable Test DB）で実行できる構造にする。

#### Scope

##### In Scope

- Docker Compose（app・db）、Django プロジェクトの生成と基本設定（TIME_ZONE＝Asia/Tokyo、UTF-8、DRF 導入）
- DB 接続情報・秘密鍵を環境変数から読む設定と、実値を含まない .env.example
- 環境ごとに異なる設定値（接続先、秘密情報、デバッグ用情報の表示、試験用状態の設定手段（TASK-017・TASK-019）等の本番環境で無効にする開発用の機能の有効・無効）の一覧と、秘密情報の値を含まない記入例（NFR-OM-17、NFR-SC-07）。設定値はプログラムを変更せずに環境ごとに変更できる構造とする
- 本番環境向けの設定で、デバッグ用情報の表示と開発用の機能が無効となる構成（NFR-SC-10 後段、VUL-08）
- 本番環境向けの起動構成で Django 付属の開発用サーバーを使用しない構成（NFR-EN-08。Web/AP サーバーの選定は ADDR 候補 environment-configuration に従う）
- 試験時に接続先 DB を使い捨ての試験用 DB へ切り替えられる設定構造（本番・検証の DB を試験で使わない）
- 依存ライブラリ（Python パッケージ）と実行環境（コンテナイメージ・Python・PostgreSQL）の取得元と版を特定・固定して記録し、同じ版の構成を再現できる構成（VUL-10。固定・記録の方式は ADDR 候補 environment-configuration に従う）
- 採用製品（Python 3.12、Django 5.2 LTS、PostgreSQL 16 等）をサポート期限内の版とし、各製品の版とサポート期限を記録する（NFR-EN-10、VUL-09）
- 本Taskで導入する依存ライブラリについて、公開されている脆弱性情報と照合し既知の重大な脆弱性（CVSS 7.0以上）が無い版を採用する（NFR-SC-11、VUL-09。後続 Task で追加される依存を含む全依存のリリース前の最終確認は TASK-021）
- 本番環境向けの設定で、ログイン状態を示す情報（画面のログイン状態・Web API のログイン状態を示す情報）と CSRF 対策の値を暗号化された通信（HTTPS）でのみ送信させ、HTTP で業務データ（画面・Web API の要求・応答）を受け付けない構成（NFR-SC-02、NFR-SC-19 の「暗号化されない通信でログイン状態を示す情報を送信しない」、data_requirements.md 8.1 CLS-01〜CLS-04 の通信時の暗号化：本番環境は必須・検証環境は不要。ENV-01 は HTTP を許容し、差は環境ごとの設定値で表す：NFR-OM-17。実現方式は ADDR 候補 environment-configuration・authentication-session に従う）
- 処理能力の増強（アプリケーションの実行単位の追加等）をプログラムの変更なしに構成の追加だけで行える設定構造（NFR-PF-16。ログイン状態の保持は TASK-006、カートの内容は TASK-012。本番基盤の構成は NOQ-01 で対象外）
- 特定のサーバー OS に固有の設定・機能に依存しない構成（NFR-EN-07）
- 本Taskで導入する依存ライブラリのライセンスを記録し、社外へ配布しないサーバー上での利用で利用条件を満たせるライセンスに限る（AGPL のライブラリ・ライセンスが不明なライブラリを採用しない）（NFR-EN-12。後続 Task で追加される依存を含む全依存の最終確認は TASK-021）
- pytest／pytest-django、ruff の設定、開発・検証環境向けの手順書（README.md 等。環境ごとの設定（秘密情報を含む）の作成、環境の構築・起動・停止、データベースの初期化、自動テスト、静的解析の手順。初期データ一括投入の手順は TASK-011）（NFR-OM-19 前段）

##### Out of Scope

- 業務 Entity のモデル定義（TASK-003〜TASK-005）
- 本番基盤・HTTPS 終端・サーバー証明書・TLS 1.2 以上の設定・ネットワーク（NFR-SC-26）・保存媒体の暗号化（NFR-SC-20）・監視の構成（NOQ-01、NOQ-02、NOQ-04。要件未決）。本番の基盤そのものは対象外とし、本Taskはリポジトリに含めるアプリケーション側の本番設定・起動構成までとする（本番環境の構築時の TLS・HTTP 不可の実測は本番基盤の工程）
- 本番運用手順書（NFR-OM-19 後段。本番基盤の選定後に作成）
- 稼働後のセキュリティパッチの適用（NFR-OM-14。運用手順書での運用事項であり、実装 Task の対象外）

#### Expected Change

- compose.yaml、.env.example、README.md、app/ 配下の Django プロジェクト設定、pytest・ruff 設定、依存ライブラリ・実行環境の取得元と版を固定した記録（記録の形式は ADDR 判断に従う）
- テスト配置は app/ 配下の tests/unit・tests/integration（Steering 4章の app/ 配置と traceability-policy の対象パスに合わせる）

#### Constraints

- 実行時に外部インターネットへ接続しない。外部 CDN を使わない（NFR-EN-05、Steering 4章）
- 秘密情報・DB パスワードをリポジトリ・履歴・.env.example に含めない（NFR-SC-07）
- 1回の起動操作で全構成要素、1回の操作で全自動テストを実行できる（NFR-OM-05、NFR-OM-06）
- ENV-01 と本番環境で同じプログラムを使い、環境差は設定値だけで表す（NFR-OM-17）

#### Completion Criteria / Definition of Done

- [ ] 1回の起動操作で app・db が起動し、localhost:8000 で応答する
- [ ] 環境変数で DB 接続先を切り替えられ、自動テストが使い捨ての試験用 DB で実行される
- [ ] 環境ごとに異なる設定値の一覧と秘密情報の値を含まない記入例があり、ENV-01 でプログラムを変更せずに設定値の変更が反映される（NFR-OM-17）
- [ ] 本番環境向けの設定でデバッグ用情報の表示・開発用の機能が無効であり、本番環境向けの起動構成が Django 付属の開発用サーバーを使用しない（NFR-SC-10、NFR-EN-08、VUL-08。構成・設定レビュー）
- [ ] ruff の指摘0件、空のテスト実行が PASS する
- [ ] 依存ライブラリ・実行環境の取得元と版が記録され、記録から同じ版の構成を再現（再構築）できる（VUL-10。構成・設定レビュー）
- [ ] 採用製品の版がサポート期限内であり、版とサポート期限が記録されている（NFR-EN-10、VUL-09。構成・設定レビュー）
- [ ] 本Task時点の依存ライブラリに既知の重大な脆弱性（CVSS 7.0以上）が0件である（NFR-SC-11、VUL-09。照合結果を記録する）
- [ ] .env.example・リポジトリに秘密情報の実値がない
- [ ] 本番環境向けの設定で、ログイン状態を示す情報と CSRF 対策の値が暗号化された通信でのみ送信される設定であり、HTTP で業務データ（画面・Web API の要求・応答）を受け付けない（NFR-SC-02、NFR-SC-19。構成・設定レビュー。ENV-01 は HTTP を許容する設定値で動作する）
- [ ] 処理能力の増強がプログラムの変更を伴わず構成の追加だけで行える設定構造である（NFR-PF-16。構成・設定レビュー）
- [ ] 特定のサーバー OS に固有の設定・機能に依存しない（NFR-EN-07。構成・設定レビュー）
- [ ] 本Task時点の全依存ライブラリのライセンスが記録され、AGPL のライブラリ・ライセンスが不明なライブラリが0件である（NFR-EN-12。静的解析・コードレビュー）
- [ ] 開発・検証環境向けの手順書の手順どおりに、ENV-01 の設定の作成・構築・起動・停止、データベースの初期化、自動テスト、静的解析を実行できる（NFR-OM-19。構成・設定レビュー）
- [ ] 開発言語・フレームワーク・データベース・実行基盤・規約・日時と文字コードが指定どおりである（NFR-EN-01：Python 3.12、NFR-EN-09：Django 5.2 LTS・DRF、画面の作成に SPA フレームワークとフロントエンドのビルド工程を使わない、NFR-EN-02：PostgreSQL 16、NFR-EN-03：Docker Compose、NFR-EN-11：ruff による Python のコーディング規約の確認、NFR-EN-04：JST・UTF-8。構成・設定レビュー）
- [ ] 本Taskの設定・記録が、個人情報の通信時の暗号化（NFR-LG-01）と 8.2 の対策方針のうち VUL-08〜VUL-10（NFR-SC-21、NFR-LG-07）を満たす（構成・設定レビュー）
- [ ] 不要なScope Expansionがない

#### Validation

| Validation Type | Command / Method | Expected Result |
| --- | --- | --- |
| Build | docker compose build（本Taskで整備。コマンドは要確定） | planned |
| Static Check | ruff check（本Taskで設定。対象パスは要確定） | PASS（指摘0件） |
| Unit Test | pytest（本Taskで設定。試験用DBで実行） | planned |
| Other | リポジトリ全体の秘密情報検索（NFR-SC-07）、docker compose up で localhost:8000 の応答確認、環境別設定値の一覧と本番向け設定・起動構成の構成・設定レビュー（NFR-OM-17、NFR-EN-08、VUL-08）、依存ライブラリ・実行環境の取得元と版の記録からの再構築と版・サポート期限の構成・設定レビュー（VUL-10、NFR-EN-10）、依存ライブラリと公開されている脆弱性情報の照合（NFR-SC-11。照合に用いるツールは試験計画で選定：NCN-07） | 0件 / 応答 / PASS / 再現可・期限内 / CVSS 7.0以上 0件 |
| Other | 本番環境向け設定の通信関連の構成・設定レビュー（ログイン状態を示す情報・CSRF 対策の値の暗号化通信に限った送信、HTTP での業務データの不受理：NFR-SC-02、NFR-SC-19）、処理能力の増強・OS 非依存の構成・設定レビュー（NFR-PF-16、NFR-EN-07）、依存ライブラリのライセンスの一覧の確認（NFR-EN-12）、手順書どおりの ENV-01 の構築（NFR-OM-19） | PASS / AGPL・ライセンス不明 0件 |

#### Progress / Result

| 項目 | 内容 |
| --- | --- |
| Started At | None |
| Completed At | None |
| Result | None |
| Evidence | None |
| Blocked Reason | None |
| Required Route | NONE |

#### Notes

- 実装前に後続ADDRと implementation-handoff を読み、本Taskに結び付いた判断（試験用DB・試験用状態の方式、環境別設定・本番構成（environment-configuration）等）に従う。
- 商品一覧画面の表示による起動確認は TASK-007 の完了後に実施できる補足確認であり、本Taskの完了条件には含めない（後続 Wave の成果に依存させない）。
- Steering 2.2 の API 契約資料（docs/specifications/api-contract.md）は未格納（OQ-PJ-001）。他ブランチから取り込まない。

### TASK-002 `共通基盤（時刻、入力正規化、判定順序・エラー種別、ページング、ログ、共通画面）`

#### Metadata

| 項目 | 内容 |
| --- | --- |
| Type | IMPLEMENT |
| Priority | HIGH |
| Status | TODO |
| Target Area | 共通コンポーネント（時刻、入力正規化、エラー通知、ページング、ログ、共通レイアウト・エラー画面） |
| Depends On | TASK-001 |
| Blocks | TASK-006、TASK-007、TASK-008、TASK-009、TASK-011、TASK-017 |

#### Source References

| Type | ID / Path | Relevant Section / Reason |
| --- | --- | --- |
| Requirement | FR-001、FR-011、FR-032、FR-040、FR-041、NFR-OM-01、NFR-OM-02、NFR-SC-04、NFR-SC-05、NFR-SC-06、NFR-SC-10、NFR-US-04、NFR-PF-08、NFR-US-01、NFR-US-02、NFR-US-05、NFR-US-06、NFR-US-07、NFR-LG-08、NFR-PF-03、NFR-US-03、NFR-OM-11、NFR-OM-18、NFR-LG-01、NFR-EN-04、NFR-EN-05 | functional_requirements.md 7章 CMN-13〜CMN-18（入力）、CMN-29〜CMN-30（時刻・金額）、CMN-34〜CMN-36（共通）、10章 ERR-01〜ERR-08・MSG-01〜MSG-07 |
| Use Case / AC | UC-001〜UC-013 の入力エラー・対象なし・システムエラーの AC | 共通の通知・判定順序 |
| ADR | None（後続ADDR：Web API 契約（候補 api-contract）、ログ方式（候補 application-logging。アクセスログの要求先から検索条件を除くことを含む）、構成（候補 application-structure）、CSRF 対策の方式（候補 authentication-session）、本番でのデバッグ表示の無効化（候補 environment-configuration）を確認。要求の識別子の付与と LOG-01〜LOG-03・LOG-06 への出力（候補 application-logging）も確認） | エラー応答形式・ページング表現・ログ形式・CSRF 対策方式は ADDR |
| Detailed Design | docs/architecture/db-logical-design.md 4.1（JST 秒単位・円整数）、ui_report_requirements.md（SCR-901、共通表示） | 共通規則 |

#### Objective

全機能で共通に使う時刻（JST・秒単位切り捨て、試験時に差し替え可能な時刻提供点）、文字列正規化（CMN-15）、判定順序（CMN-14）とエラー種別（ERR-01〜ERR-08）の通知、ページング（CMN-35）、要求ごとのアプリケーションログ（NFR-OM-01）、共通画面（SCR-901・共通表示）を用意する。

#### Scope

##### In Scope

- 処理時刻の取得点（JST、秒未満切り捨て）を1か所に集約し、TASK-017 が試験時に差し替えられる構造
- 前後空白除去（パスワードを除く）、全項目分の入力エラー集約（CMN-16）
- エラー種別ごとの画面・Web API 共通の通知（内部詳細を返さない：NFR-SC-10、MSG-04）
- 一覧の分割表示（ページ番号、総件数・総ページ数、上限超過は0件）
- 要求ごとのログ（日時・重要度・要求識別子・種類・要求先（検索条件を除く：NFR-SC-06）・結果・利用者・処理時間）、機密情報の非出力
- 共通レイアウト、SCR-901、XSS 対策の出力エスケープ・CSRF 対策（NFR-SC-05。CSRF 対策の方式はログイン状態の方式と併せて ADDR 候補 authentication-session の判断に従う。TASK-006 のセッション固定化対策と同じ判断を参照する）
- 要求ごとに要求の識別子を付与し、同じ要求に関する LOG-01（アプリケーションログ）・LOG-02（エラーログ）・LOG-03（アクセスログ）と外部連携ログ（LOG-06、TASK-008）へ同じ識別子を出力できる共通部品（NFR-OM-18、NFR-OM-11。ログ方式は ADDR 候補 application-logging）

##### Out of Scope

- 各機能固有の判定・業務ルール（各機能 Task）
- 監視ツール・通知手段（NOQ-02 未決）

#### Expected Change

- 共通ユーティリティ、例外・エラー応答の変換、ページング、ログ設定、共通テンプレート

#### Constraints

- パスワード・ログイン状態を示す情報・個人情報をログに出力しない（NFR-SC-06、Steering 6.2）
- アクセスログ（要求ごとのログの要求先）に検索条件を含めない（NFR-SC-06。検索条件にメールアドレスが含まれるため。管理者の注文一覧検索のメールアドレス部分一致（FR-041、TASK-018）を含む全検索条件が対象。Web/AP サーバーが出力するアクセスログの扱いは ADDR 候補 application-logging・environment-configuration の判断に従う）
- 画面と Web API で同一の判定順序・通知内容（CMN-34）
- 日時は JST、判定は秒単位（CMN-29、NFR-EN-04）
- エラー応答・画面にスタックトレース・SQL 文・ファイルパス・ライブラリの名称とバージョンを含めない。デバッグ用情報を表示しない設定で動作させる（NFR-SC-10、VUL-13。設定は TASK-001）
- 本Taskの画面（SCR-901、共通レイアウト）は、Windows 11 の PC の Google Chrome 最新版・Microsoft Edge 最新版で全操作を行えること（NFR-US-01、NFR-US-06）、幅 1280px×高さ 720px 以上の表示領域で横スクロール・表示崩れ（要素の重なり・欠け）が無いこと（NFR-US-02）、JIS X 8341-3:2016 適合レベル A に適合すること（NFR-US-05、NFR-LG-08）、キーボード（Tab・Shift+Tab・Enter・Space・矢印キー）だけで全操作を行えること（NFR-US-07）を満たす。画面の表示完了時間 2.0秒以内（NFR-PF-03）を満たせる画面構成とし、外部 CDN に依存しない（NFR-EN-05）
- 入力・保存・表示できる文字は UTF-8 で符号化できる文字（外字は使用しない）、画面の表示言語は日本語のみとする（NFR-US-03、NFR-EN-04）

#### Completion Criteria / Definition of Done

- [ ] 共通部品の単体テストが PASS（境界：秒未満切り捨て、空白除去、ページ番号0・総ページ超過）
- [ ] ログ出力が機械解析可能で必須項目を含み、機密情報を含まない
- [ ] 検索条件（クエリ文字列等）を付けた要求のログの要求先に検索条件が含まれない（NFR-SC-06。単体テストで、試験用のメールアドレスの値でログを検索し0件）
- [ ] デバッグ用情報を表示しない設定で、データベースの停止・存在しない要求先・形式が不正な要求に対する画面・Web API の応答に内部情報が含まれない（NFR-SC-10、VUL-13）
- [ ] Build / ruff が PASS
- [ ] LOG-01〜LOG-03 が 6.3 に定めた項目・出力契機で出力され、各行に要求の識別子が含まれ、1件の要求の識別子で LOG-01〜LOG-03 の当該要求の行を漏れなく抽出できる（NFR-OM-11、NFR-OM-18。LOG-06 は TASK-008、支払要求での LOG-01〜LOG-03・LOG-06 の横断追跡は TASK-020）
- [ ] 本Taskの画面（SCR-901、共通レイアウト）を Windows 11 の Chrome・Edge 最新版で全操作でき、1280×720 の表示領域で横スクロール・表示崩れが無く、JIS X 8341-3:2016 適合レベル A の達成基準のチェックリストを満たし、キーボードだけで全操作を行える（NFR-US-01、NFR-US-02、NFR-US-05、NFR-US-06、NFR-US-07。互換性・操作性テスト。画面をまたぐ一連の操作は TASK-020）
- [ ] 全ての外部入力を画面の入力制御によらずシステムで検証し（NFR-SC-04）、入力エラーは誤りのある全項目分をどの項目の誤りかを識別できる理由とともに通知して入力値（パスワードを除く）を保持し（NFR-US-04）、一覧の応答件数の上限を守る（NFR-PF-08）。日時は JST、文字コードは UTF-8（NFR-EN-04）、画面は外部 CDN に依存しない（NFR-EN-05）
- [ ] LOG-01〜LOG-03 を90日以上保管し期間内を検索できるログ設定であり（NFR-OM-02。保管期間は運用時に測定）、個人情報をログに出力しない（NFR-SC-06、NFR-LG-01）
- [ ] 不要なScope Expansionがない

#### Validation

| Validation Type | Command / Method | Expected Result |
| --- | --- | --- |
| Build | TASK-001 で整備した起動手順 | PASS / planned |
| Static Check | ruff check | PASS |
| Unit Test | pytest（共通部品） | planned |
| Other | ログ全行の機械解析（NFR-OM-01）、検索条件を付けた要求後のログの検索（NFR-SC-06） | PASS / 0件 |
| Other | 要求の識別子による LOG-01〜LOG-03 の抽出（NFR-OM-18） | 漏れ0件 |
| Other | 互換性・操作性テスト（本Taskの画面 SCR-901：2種のブラウザでの全操作（NFR-US-01、NFR-US-06）、1280×720 表示（NFR-US-02）、適合レベル A のチェックリスト（NFR-US-05）、キーボードだけでの全操作（NFR-US-07）） | PASS |
| Other | 性能テスト（SCR-901 の表示完了時間：NFR-PF-03） | later phase（試験工程。ENV-01 のピーク負荷・3年後データ量で測定） |

#### Progress / Result

| 項目 | 内容 |
| --- | --- |
| Started At | None |
| Completed At | None |
| Result | None |
| Evidence | None |
| Blocked Reason | None |
| Required Route | NONE |

#### Notes

- Web API のパス・電文形式・認証ヘッダー・エラー応答形式は要件で定義されず（functional_requirements.md 1.2）、Steering 5章の事前指定（REST/JSON、/api・/api/admin、snake_case）の根拠資料が未格納（OQ-PJ-001）。後続ADDRの判断に従う。

### TASK-003 `利用者・監査ログのデータモデル（ENT-001、ENT-015）`

#### Metadata

| 項目 | 内容 |
| --- | --- |
| Type | MIGRATION |
| Priority | HIGH |
| Status | TODO |
| Target Area | データモデル・マイグレーション（会員・認証、運用記録） |
| Depends On | TASK-001 |
| Blocks | TASK-005、TASK-006、TASK-011 |

#### Source References

| Type | ID / Path | Relevant Section / Reason |
| --- | --- | --- |
| Requirement | FR-001、FR-002、FR-003、FR-060、NFR-SC-01、NFR-SC-23、DR-001、DR-015、NFR-OM-03 | 利用者・監査ログの項目・一意性・追記のみ |
| Use Case / AC | UC-001、UC-002、UC-013 | 利用者登録・ログイン記録・投入記録 |
| ADR | None（後続ADDR：パスワード保持方式（候補 password-storage）、識別子採番（候補 identifier-assignment）、コード値（候補 code-value-assignment）を確認） | 方式判断は ADDR |
| Detailed Design | ENT-001、ENT-015（docs/architecture/db-logical-design.md 7.1、7.15、13章、17章 PHY-HO-005） | 属性・識別子・制約・削除済み利用者を許容する参照 |

#### Objective

ENT-001 利用者と ENT-015 監査ログを、論理DB設計の属性・一意性・条件付き制約どおりに物理化する。

#### Scope

##### In Scope

- 利用者（正規化後メールアドレスの一意性、利用者区分、パスワード（照合用）の保持領域）
- 監査ログ（イベント種別・結果・対象の利用者（削除済み利用者の値を保持できる参照）・詳細）

##### Out of Scope

- 認証処理（TASK-006）、投入処理（TASK-011）
- ログイン状態の保持（データ要件の対象外。OQ-LDB-005 の ADDR 判断に従い TASK-006 で扱う）

#### Expected Change

- 利用者・監査ログのモデル定義とマイグレーション

#### Constraints

- パスワードを平文・復号可能な形式で保持しない（NFR-SC-01、CMN-06）
- 監査ログを変更する手段を設けない（NFR-SC-23）
- DBMS 固有の物理設計は PHY-HO-001〜PHY-HO-009 の前提に従う
- 監査ログを画面・Web API から削除する手段を設けない。保管期間（1年以上）を経過した監査ログの年1回の削除の実施手段は ADDR 候補 retention-deletion の判断に従う（NFR-OM-03）

#### Completion Criteria / Definition of Done

- [ ] マイグレーションが試験用DBに適用できる
- [ ] 一意性・条件付き制約（LDC-ENT-001-001、LDC-ENT-015-001）の単体テストが PASS
- [ ] Build / ruff が PASS
- [ ] 不要なScope Expansionがない

#### Validation

| Validation Type | Command / Method | Expected Result |
| --- | --- | --- |
| Build | マイグレーション適用（コマンドは TASK-001 で整備） | PASS |
| Static Check | ruff check | PASS |
| Unit Test | pytest（モデル制約） | planned |
| Other | 論理DB設計との属性対応のレビュー | 差異なし |

#### Progress / Result

| 項目 | 内容 |
| --- | --- |
| Started At | None |
| Completed At | None |
| Result | None |
| Evidence | None |
| Blocked Reason | None |
| Required Route | NONE |

#### Notes

- NOQ-10（管理者アカウントの無効化・パスワード変更手段なし。UNRESOLVED-32af0f4a0ca9c80f）は未決。暫定扱いにより無効化状態等の属性は追加しない（OQ-LDB-010）。

### TASK-004 `商品カタログ・在庫・クーポンのデータモデル（ENT-002〜ENT-007）`

#### Metadata

| 項目 | 内容 |
| --- | --- |
| Type | MIGRATION |
| Priority | HIGH |
| Status | TODO |
| Target Area | データモデル・マイグレーション（商品カタログ、販促） |
| Depends On | TASK-001 |
| Blocks | TASK-005、TASK-007、TASK-010、TASK-011 |

#### Source References

| Type | ID / Path | Relevant Section / Reason |
| --- | --- | --- |
| Requirement | FR-010、FR-011、FR-012、FR-024、FR-040、FR-060、DR-002、DR-003、DR-004、DR-005、DR-006、DR-007 | マスタの項目・業務キー・階層・在庫数量の値域 |
| Use Case / AC | UC-003、UC-005、UC-010、UC-013 | 照会・クーポン判定・投入 |
| ADR | None（後続ADDR：識別子採番（候補 identifier-assignment）、コード値（候補 code-value-assignment）を確認） | 方式判断は ADDR |
| Detailed Design | ENT-002、ENT-003、ENT-004、ENT-005、ENT-006、ENT-007（docs/architecture/db-logical-design.md 7.2〜7.7、8章、10章、17章） | 属性・識別子・関連・制約 |

#### Objective

仕入先・商品分類・商品・商品分類所属・在庫単位・クーポンを、論理DB設計の識別子・業務キー・関連・値域どおりに物理化する。

#### Scope

##### In Scope

- 6 Entity のモデルとマイグレーション、業務キーの一意性、分類名の親内一意性、在庫数量0以上の制約
- 商品の登録順・在庫単位の SKU 順を判定できる構造（LDR-015、CMN-36）

##### Out of Scope

- マスタの画面・API による登録・更新・削除（FR-OUT-02）
- 階層・循環の投入時判定（TASK-011）

#### Expected Change

- 6 Entity のモデル定義とマイグレーション

#### Constraints

- 導出値（税込価格・最低価格・在庫有無・低在庫）は保持しない（LDM-DEC-004）
- 在庫数量は初期投入・注文確定・注文キャンセルでのみ変化する（CMN-38）

#### Completion Criteria / Definition of Done

- [ ] マイグレーションが試験用DBに適用できる
- [ ] 業務キー一意性・在庫数量の値域の単体テストが PASS
- [ ] Build / ruff が PASS
- [ ] 不要なScope Expansionがない

#### Validation

| Validation Type | Command / Method | Expected Result |
| --- | --- | --- |
| Build | マイグレーション適用 | PASS |
| Static Check | ruff check | PASS |
| Unit Test | pytest（モデル制約） | planned |
| Other | 論理DB設計との属性対応のレビュー | 差異なし |

#### Progress / Result

| 項目 | 内容 |
| --- | --- |
| Started At | None |
| Completed At | None |
| Result | None |
| Evidence | None |
| Blocked Reason | None |
| Required Route | NONE |

#### Notes

- クーポンの論理上の識別子はクーポンコード（IDF-ENT-007-001）。物理上の代替キーの要否は PHY-HO-003。

### TASK-005 `カート・注文系のデータモデル（ENT-008〜ENT-014）`

#### Metadata

| 項目 | 内容 |
| --- | --- |
| Type | MIGRATION |
| Priority | HIGH |
| Status | TODO |
| Target Area | データモデル・マイグレーション（カート、注文） |
| Depends On | TASK-003、TASK-004 |
| Blocks | TASK-009、TASK-011、TASK-012 |

#### Source References

| Type | ID / Path | Relevant Section / Reason |
| --- | --- | --- |
| Requirement | FR-020、FR-030、FR-031、FR-033、FR-042、NFR-LG-03、NFR-SC-23、DR-008、DR-009、DR-010、DR-011、DR-012、DR-013、DR-014、NFR-LG-09、NFR-OM-11 | カート・注文・明細・配送先・決済記録・状態履歴の項目と整合性 |
| Use Case / AC | UC-004〜UC-009、UC-011、UC-012 | 生成・更新・参照の契機 |
| ADR | None（後続ADDR：識別子採番（候補 identifier-assignment）、注文番号（候補 order-number-issuance）、コード値（候補 code-value-assignment）、同時実行制御（候補 concurrency-transaction）を確認） | 方式判断は ADDR |
| Detailed Design | ENT-008、ENT-009、ENT-010、ENT-011、ENT-012、ENT-013、ENT-014（docs/architecture/db-logical-design.md 7.8〜7.14、8章、11章、17章 PHY-HO-002・PHY-HO-004・PHY-HO-006） | 属性・条件付き一意性・並び順の再現 |

#### Objective

カート・カート明細・注文・注文明細・配送先・決済記録・注文状態履歴を、論理DB設計の制約（利用中カート最大1件、承認の決済記録最大1件、状態と日時の整合、明細の並びの再現）どおりに物理化する。

#### Scope

##### In Scope

- 7 Entity のモデルとマイグレーション、条件付き一意性（LDC-ENT-008-001、LDC-ENT-013-001）
- 状態・日時・クーポン複写値の組合せ制約（LDC-ENT-010-001〜LDC-ENT-010-007）のうちデータ層で表現する部分
- 注文明細・決済記録・状態履歴の並び順を再現できる構造（LDR-014）

##### Out of Scope

- 状態遷移・在庫引当の業務処理（TASK-014〜TASK-016、TASK-018）
- 保存期間経過データの削除手段（OQ-LDB-006。ADDR 判断待ち）

#### Expected Change

- 7 Entity のモデル定義とマイグレーション

#### Constraints

- 注文明細・配送先・決済記録・注文状態履歴は登録後に変更しない（DR-011〜DR-014 備考、NFR-SC-23）
- 金額は円整数、日時は JST 秒単位（DCN-12）
- 配送先の都道府県は JIS X 0401 の都道府県コード（CD-06）の47都道府県で扱う（NFR-LG-09）
- 注文状態履歴（LOG-07）は注文状態の全遷移ごとに1件記録できる構造とする（NFR-OM-11。記録は TASK-014〜TASK-016、TASK-018）

#### Completion Criteria / Definition of Done

- [ ] マイグレーションが試験用DBに適用できる
- [ ] 条件付き一意性・状態と日時の整合の単体テストが PASS
- [ ] Build / ruff が PASS
- [ ] 注文・注文明細・配送先・決済記録を7年間保持できる（自動で削除しない）構造である（NFR-LG-03）
- [ ] 不要なScope Expansionがない

#### Validation

| Validation Type | Command / Method | Expected Result |
| --- | --- | --- |
| Build | マイグレーション適用 | PASS |
| Static Check | ruff check | PASS |
| Unit Test | pytest（モデル制約） | planned |
| Other | 論理DB設計との属性対応のレビュー | 差異なし |

#### Progress / Result

| 項目 | 内容 |
| --- | --- |
| Started At | None |
| Completed At | None |
| Result | None |
| Evidence | None |
| Blocked Reason | None |
| Required Route | NONE |

#### Notes

- BOQ-08（本番での模擬決済の扱い。UNRESOLVED-32af0f4a0ca9c80f）は未決。暫定扱いにより本番のみの挙動差・区別属性を追加しない（OQ-LDB-010）。

### TASK-006 `会員登録・ログイン・ログアウト・利用者情報照会と認証・権限判定`

#### Metadata

| 項目 | 内容 |
| --- | --- |
| Type | IMPLEMENT |
| Priority | HIGH |
| Status | TODO |
| Target Area | 会員・認証（業務処理・Web API・画面 SCR-003、SCR-004、共通表示） |
| Depends On | TASK-002、TASK-003、TASK-017 |
| Blocks | TASK-010、TASK-011、TASK-012、TASK-020 |

#### Source References

| Type | ID / Path | Relevant Section / Reason |
| --- | --- | --- |
| Requirement | FR-001、FR-002、FR-003、FR-004、FR-060、NFR-SC-01、NFR-SC-03、NFR-SC-08、NFR-SC-09、NFR-SC-12、NFR-SC-15、NFR-SC-18、NFR-SC-19、NFR-SC-22、NFR-US-01、NFR-US-02、NFR-US-05、NFR-US-06、NFR-US-07、NFR-LG-08、NFR-PF-03、NFR-PF-09、NFR-PF-16、NFR-SC-16、NFR-US-03、NFR-US-10、NFR-OM-11、NFR-LG-01、NFR-EN-05、NFR-SC-24 | functional_requirements.md 6.1〜6.4、7.1〜7.2（CMN-01〜CMN-12）、5.1 権限表、6.26.4 手順9・6.26.9（削除指定で削除した利用者のログイン状態は無効、完了後は削除前のログイン状態による要求は認証エラー） |
| Use Case / AC | UC-001（AC-UC-001-001〜AC-UC-001-019）、UC-002（AC-UC-002-001〜AC-UC-002-021） | 会員登録・ログイン・ログアウト・利用者情報（他 Task の画面・機能を用いる AC-UC-001-002、AC-UC-002-003、AC-UC-002-009、AC-UC-002-014、AC-UC-002-015、AC-UC-002-016、AC-UC-002-018 は TASK-020 で確認） |
| ADR | None（後続ADDR：ログイン状態・セッション方式（候補 authentication-session）、パスワード保持方式（候補 password-storage）、Web API 契約（候補 api-contract）、利用者識別子の採番と削除指定後の扱い（候補 identifier-assignment）を確認。ログイン状態の保持方式は処理能力の増強でログイン状態が失われないこと（NFR-PF-16）、パスワード保持方式は認証系 API の応答時間（NFR-PF-09）を満たすことを根拠に含む） | 方式判断は ADDR |
| Detailed Design | ENT-001、ENT-015（docs/architecture/db-logical-design.md 7.1、7.15、OQ-LDB-001、OQ-LDB-005） | 利用者の一意性・監査ログの記録規則 |

#### Objective

会員登録（購入者のみ作成）、メールアドレスとパスワードによるログイン（Web API はログイン状態を示す情報を返し24時間有効、画面は無操作30分で切断）、要求したログイン状態のみを解除するログアウト、本人の利用者情報照会と、全機能共通の認証・権限判定（ERR-03、ERR-04）を実装する。

#### Scope

##### In Scope

- FR-001〜FR-004 の処理・例外（E-001-01〜E-001-03、E-002-01〜E-002-03 ほか）
- 監査ログ（ログイン成功・失敗・ログアウト）の記録と機密情報の非記録（CMN-24、CMN-25）
- 認証要否・利用者区分による権限判定と、他の購入者の注文を対象なしとする所有者判定の共通部品（CMN-02〜CMN-04）
- 多重ログイン、ログイン状態の推測困難性（128ビット以上相当）、セッション固定化防止
- 初期データ一括投入の削除指定で削除された利用者のログイン状態を無効とし、投入完了後は削除前のログイン状態による要求を認証エラーとする（FR-060 手順9・6.26.9、CMN-02。削除後に投入された利用者として認証されないことを含む。無効化の実現方式は ADDR 候補 authentication-session・identifier-assignment の判断に従う。削除指定の投入処理は TASK-011）

##### Out of Scope

- アカウントロック・試行回数制限・多要素認証（FR-OUT-11。NOQ-08 未決でも追加しない）
- 会員情報の変更・パスワード再設定・退会（FR-OUT-09）

#### Expected Change

- 会員・認証の業務処理、Web API、SCR-003・SCR-004、認証・権限判定の共通部品

#### Constraints

- ログイン失敗時にメールアドレス・パスワードのどちらが誤りかを区別しない（CMN-05）
- 会員登録の利用者区分は購入者固定（CMN-08、NFR-SC-15）
- 画面の表示制御によらず要求時点で権限を判定（NFR-SC-03）
- 本Taskの画面（SCR-003、SCR-004）は、Windows 11 の PC の Google Chrome 最新版・Microsoft Edge 最新版で全操作を行えること（NFR-US-01、NFR-US-06）、幅 1280px×高さ 720px 以上の表示領域で横スクロール・表示崩れ（要素の重なり・欠け）が無いこと（NFR-US-02）、JIS X 8341-3:2016 適合レベル A に適合すること（NFR-US-05、NFR-LG-08）、キーボード（Tab・Shift+Tab・Enter・Space・矢印キー）だけで全操作を行えること（NFR-US-07）を満たす。画面の表示完了時間 2.0秒以内（NFR-PF-03）を満たせる画面構成とし、外部 CDN に依存しない（NFR-EN-05）

#### Completion Criteria / Definition of Done

- [ ] UC-001・UC-002 の AC を満たせる（AC-UC-001-002、AC-UC-002-003、AC-UC-002-009、AC-UC-002-014、AC-UC-002-015、AC-UC-002-016、AC-UC-002-018 を除く。これらはカート・商品一覧・注文履歴・在庫単位一覧・注文一覧（管理）等の他 Task の画面・機能を用いるため TASK-020 で確認する。AC-UC-002-002 の管理者は試験データで用意し、初期データ一括投入を経由した確認は AC-UC-013-002（TASK-020）で行う）
- [ ] 境界（有効期限ちょうど、無操作29分・31分）を TASK-017 の時刻設定で検証できる（TASK-017 は Depends On に宣言済み）
- [ ] Build / ruff / 単体テストが PASS
- [ ] 会員登録のパスワードが 7文字・65文字・英字のみ・数字のみ・メールアドレスと同一・メールアドレスを英大文字に変換した文字列の場合に入力エラーとなる（NFR-SC-16。セキュリティテスト）
- [ ] 氏名に JIS 第3・第4水準の漢字を入力して登録し、同じ文字が表示される（NFR-US-03）
- [ ] ログイン成功・ログイン失敗・ログアウトが LOG-04（監査ログ）の記録項目で記録され、入力されたメールアドレス・パスワード・ログイン状態を示す情報・個人情報を含まない（NFR-SC-22、NFR-OM-11）
- [ ] 会員登録の画面操作を処理が完了するまでの間に繰り返しても、登録は1回分だけ反映される（NFR-US-10）
- [ ] アプリケーションの実行単位を追加して処理能力を増強しても、ログイン状態が失われない構造である（NFR-PF-16。静的解析・コードレビュー。保持方式は ADDR 候補 authentication-session）
- [ ] 本Taskの画面（SCR-003、SCR-004）を Windows 11 の Chrome・Edge 最新版で全操作でき、1280×720 の表示領域で横スクロール・表示崩れが無く、JIS X 8341-3:2016 適合レベル A の達成基準のチェックリストを満たし、キーボードだけで全操作を行える（NFR-US-01、NFR-US-02、NFR-US-05、NFR-US-06、NFR-US-07。互換性・操作性テスト。画面をまたぐ一連の操作は TASK-020）
- [ ] パスワードを復元できない形式で保存し（NFR-SC-01）、Web API のログイン状態はログインから24時間・ログアウトで無効で推測困難（NFR-SC-08）、画面のログイン状態は無操作30分で無効（NFR-SC-09）、メールアドレスとパスワードで認証し（NFR-SC-12）、多重ログインを許可し（NFR-SC-18）、セッションの乗っ取り・固定化を防止して画面上のスクリプトからログイン状態を示す情報を参照できず（NFR-SC-19。暗号化通信に限った送信の本番設定は TASK-001）、利用者情報を本人にのみ返す（NFR-SC-24、NFR-LG-01）ことを単体テスト・セキュリティテストで確認できる
- [ ] 不要なScope Expansionがない

#### Validation

| Validation Type | Command / Method | Expected Result |
| --- | --- | --- |
| Build | TASK-001 の起動手順 | PASS |
| Static Check | ruff check | PASS |
| Unit Test | pytest（会員・認証） | planned |
| Other | 本Taskの Web API に対し、未ログイン・ログアウト後・有効期限切れのログイン状態での要求を画面を経由せず送る試験（NFR-SC-03。他機能の要求先に対する権限外要求の試験は各機能 Task と TASK-020） | 拒否・データ変更0件 |
| Other | 互換性・操作性テスト（本Taskの画面 SCR-003、SCR-004：2種のブラウザでの全操作（NFR-US-01、NFR-US-06）、1280×720 表示（NFR-US-02）、適合レベル A のチェックリスト（NFR-US-05）、キーボードだけでの全操作（NFR-US-07）） | PASS |
| Other | 性能テスト（認証系 API の応答時間 2.0秒以内（パスワードの照合・保存を含む）：NFR-PF-09、SCR-003・SCR-004 の表示完了時間：NFR-PF-03） | later phase（試験工程。ENV-01 のピーク負荷・3年後データ量で測定） |

#### Progress / Result

| 項目 | 内容 |
| --- | --- |
| Started At | None |
| Completed At | None |
| Result | None |
| Evidence | None |
| Blocked Reason | None |
| Required Route | NONE |

#### Notes

- NOQ-08（総当たり・リスト型攻撃への対策なし、E-001-02 による登録有無の判別。UNRESOLVED-32af0f4a0ca9c80f）は未決。暫定扱いにより現行 FR のとおり実装し、対策機能を追加しない。稼働開始判定の未充足事項として残る。

### TASK-007 `商品分類一覧・商品一覧検索・商品詳細照会`

#### Metadata

| 項目 | 内容 |
| --- | --- |
| Type | IMPLEMENT |
| Priority | HIGH |
| Status | TODO |
| Target Area | 商品カタログ（業務処理・Web API・画面 SCR-001、SCR-002） |
| Depends On | TASK-002、TASK-004 |
| Blocks | TASK-012、TASK-020 |

#### Source References

| Type | ID / Path | Relevant Section / Reason |
| --- | --- | --- |
| Requirement | FR-010、FR-011、FR-012、NFR-PF-01、NFR-PF-08、NFR-US-01、NFR-US-02、NFR-US-05、NFR-US-06、NFR-US-07、NFR-LG-08、NFR-PF-03、NFR-LG-02、NFR-EN-05 | functional_requirements.md 6.5〜6.7（分類の木構造順、配下を含む絞り込み、4種の並び順、20件ページング、税込価格） |
| Use Case / AC | UC-003（AC-UC-003-001〜AC-UC-003-021 のうち定義済みの AC） | 商品を探して閲覧する（ログイン（TASK-006）・カート投入（TASK-012）を用いる AC-UC-003-017、AC-UC-003-018、AC-UC-003-021 は TASK-020 で確認） |
| ADR | None（後続ADDR：Web API 契約（候補 api-contract）を確認） | 方式判断は ADDR |
| Detailed Design | ENT-003、ENT-004、ENT-005、ENT-006（docs/architecture/db-logical-design.md 7.3〜7.6、LDR-015、PHY-HO-008） | 公開範囲・登録順・導出値 |

#### Objective

来訪者・購入者・管理者に、公開かつ在庫単位を持つ商品の検索・詳細と全商品分類を、総額表示（税込価格主・税抜価格併記）で返す。

#### Scope

##### In Scope

- FR-010〜FR-012 の処理・例外、Unicode コードポイント順の並べ替え（CMN-36）
- 最低税抜価格・税込価格・在庫有無の算出（1円未満切り捨て）

##### Out of Scope

- 商品画像・レビュー・おすすめ（FR-OUT-13）
- カートへの追加処理（TASK-012。SCR-002 の「カートに入れる」の操作・その表示可否は TASK-012 が本Taskの SCR-002 に接続する）

#### Expected Change

- 商品カタログの照会処理、Web API、SCR-001・SCR-002

#### Constraints

- 非公開商品・その在庫単位を来訪者・購入者に返さない。仕入先・更新日時を返さない（REF-07、REF-10）
- 本Taskの画面（SCR-001、SCR-002）は、Windows 11 の PC の Google Chrome 最新版・Microsoft Edge 最新版で全操作を行えること（NFR-US-01、NFR-US-06）、幅 1280px×高さ 720px 以上の表示領域で横スクロール・表示崩れ（要素の重なり・欠け）が無いこと（NFR-US-02）、JIS X 8341-3:2016 適合レベル A に適合すること（NFR-US-05、NFR-LG-08）、キーボード（Tab・Shift+Tab・Enter・Space・矢印キー）だけで全操作を行えること（NFR-US-07）を満たす。画面の表示完了時間 2.0秒以内（NFR-PF-03）を満たせる画面構成とし、外部 CDN に依存しない（NFR-EN-05）
- 商品価格は税込価格を主に表示し、税抜価格を併記する（NFR-LG-02）

#### Completion Criteria / Definition of Done

- [ ] UC-003 の AC を満たせる（AC-UC-003-017、AC-UC-003-018、AC-UC-003-021 を除く。これらは購入者・管理者のログイン（TASK-006）、SCR-002 のカートに入れる操作（TASK-012）を用いるため TASK-020 で確認する）
- [ ] 1応答の件数上限（NFR-PF-08）を満たす
- [ ] Build / ruff / 単体テストが PASS
- [ ] 本Taskの画面（SCR-001、SCR-002）を Windows 11 の Chrome・Edge 最新版で全操作でき、1280×720 の表示領域で横スクロール・表示崩れが無く、JIS X 8341-3:2016 適合レベル A の達成基準のチェックリストを満たし、キーボードだけで全操作を行える（NFR-US-01、NFR-US-02、NFR-US-05、NFR-US-06、NFR-US-07。互換性・操作性テスト。画面をまたぐ一連の操作は TASK-020）
- [ ] 不要なScope Expansionがない

#### Validation

| Validation Type | Command / Method | Expected Result |
| --- | --- | --- |
| Build | TASK-001 の起動手順 | PASS |
| Static Check | ruff check | PASS |
| Unit Test | pytest（商品カタログ） | planned |
| Other | 3年後データ量での応答時間測定（NFR-PF-01） | later phase |
| Other | 互換性・操作性テスト（本Taskの画面 SCR-001、SCR-002：2種のブラウザでの全操作（NFR-US-01、NFR-US-06）、1280×720 表示（NFR-US-02）、適合レベル A のチェックリスト（NFR-US-05）、キーボードだけでの全操作（NFR-US-07）） | PASS |
| Other | 性能テスト（SCR-001・SCR-002 の表示完了時間：NFR-PF-03） | later phase（試験工程。ENV-01 のピーク負荷・3年後データ量で測定） |

#### Progress / Result

| 項目 | 内容 |
| --- | --- |
| Started At | None |
| Completed At | None |
| Result | None |
| Evidence | None |
| Blocked Reason | None |
| Required Route | NONE |

#### Notes

- 実装前に後続ADDRと implementation-handoff を読む。

### TASK-008 `決済サービス（模擬）と決済要求の呼出し（IFR-001）`

#### Metadata

| 項目 | 内容 |
| --- | --- |
| Type | IMPLEMENT |
| Priority | HIGH |
| Status | TODO |
| Target Area | 外部IF（本システム内の模擬決済と呼出し側） |
| Depends On | TASK-002 |
| Blocks | TASK-015、TASK-017 |

#### Source References

| Type | ID / Path | Relevant Section / Reason |
| --- | --- | --- |
| Requirement | FR-031、NFR-EN-05、NFR-SC-24、IFR-001、NFR-OM-11、NFR-OM-18、NFR-PF-17、NFR-LG-05、NFR-LG-01、NFR-SC-21、NFR-SC-06 | external_interface_requirements.md 5.1.3〜5.1.10（同期、10秒上限、模擬機能1秒以内、応答検証、自動再送なし） |
| Use Case / AC | UC-007（AC-UC-007-001〜AC-UC-007-019 のうち定義済みの AC） | 支払の承認・否認・連携エラー |
| ADR | None（後続ADDR：IFR-001 の方式・認証方式（候補 mock-payment-interface）を確認。外部連携ログ（LOG-06）の方式（候補 application-logging）、決済サービスとの連携部分だけを差し替えられる構成（候補 mock-payment-interface・application-structure）も確認） | external_interface_requirements.md 4章「方式：設計で決定」、IF-01-SEC-01 |
| Detailed Design | ENT-013（docs/architecture/db-logical-design.md 7.13、15章 MAP-001〜MAP-008） | 要求・応答項目と決済記録の対応 |

#### Objective

模擬決済指示どおりに承認（MOCK-＋英数字16文字の取引参照番号付き）・否認を1秒以内に返す決済サービス（模擬）と、決済要求を1回送り10秒を上限に応答を待ち、応答不正・接続不可・タイムアウトを連携エラーとして判定する呼出し側を実装する。

#### Scope

##### In Scope

- 要求（注文番号・決済金額・通貨・模擬決済指示）と応答（結果・取引参照番号・否認理由・処理日時）の受け渡し
- IF-01-EXC-01〜IF-01-EXC-05 の判定、自動再送なし
- TASK-017 が遅延・接続不可・応答不正を注入できる差し替え点
- 外部連携ログ（LOG-06）の出力。呼出し元の要求の識別子（TASK-002）を含める（NFR-OM-11、NFR-OM-18。ログ方式は ADDR 候補 application-logging）
- 決済サービスとの連携部分を注文・在庫・金額計算・状態遷移の処理から分離し、連携部分だけを差し替えられる構造（NFR-PF-17。分離の方式は ADDR 候補 mock-payment-interface・application-structure）

##### Out of Scope

- 実在の決済サービス・外部 API への接続（FR-OUT-01、XCN-03、Steering 7章）
- 決済記録・注文状態の更新（TASK-015）

#### Expected Change

- 模擬決済コンポーネントと決済要求の呼出しコンポーネント

#### Constraints

- 外部ネットワークに接続しない（XCN-02）
- 送信項目に個人情報を含めない（IF-01-SEC-04、NFR-SC-24）
- クレジットカード番号・有効期限・セキュリティコードを入力・保存・送信しない（NFR-LG-05）
- 決済サービスの接続先を利用者の入力で変更できない（NFR-SC-21 VUL-12）

#### Completion Criteria / Definition of Done

- [ ] 承認・否認・10秒超過・接続不可・各種応答不正の判定を単体テストで確認できる
- [ ] Build / ruff / 単体テストが PASS
- [ ] 決済要求の送信時と応答受信時（10秒の応答待ち超過・応答不正を含む）に LOG-06（外部連携ログ）が 6.3 の項目（日時、要求の識別子、注文番号、決済金額、通貨、結果、取引参照番号（承認時）、所要時間）で出力され、NFR-SC-06 の項目を含まない（NFR-OM-11、NFR-SC-06）
- [ ] LOG-06 に呼出し元の要求の識別子が出力され、同じ識別子で LOG-01〜LOG-03 と関連付けられる（NFR-OM-18。支払要求での横断追跡は TASK-020）
- [ ] 決済サービスとの連携部分の差替えが、注文・在庫・金額計算・状態遷移の処理の変更を伴わない構造である（NFR-PF-17。静的解析・コードレビュー）
- [ ] 外部ネットワークへ接続せず（NFR-EN-05）、決済要求の送信項目に個人情報を含めない（NFR-SC-24、NFR-LG-01）
- [ ] 不要なScope Expansionがない

#### Validation

| Validation Type | Command / Method | Expected Result |
| --- | --- | --- |
| Build | TASK-001 の起動手順 | PASS |
| Static Check | ruff check | PASS |
| Unit Test | pytest（模擬決済・応答検証） | planned |
| Other | 模擬機能の応答時間（IF-01-PRF-04：1秒以内） | later phase |
| Other | LOG-06 の出力項目と要求の識別子の確認（NFR-OM-11、NFR-OM-18）、連携部分の分離のコードレビュー（NFR-PF-17） | PASS |

#### Progress / Result

| 項目 | 内容 |
| --- | --- |
| Started At | None |
| Completed At | None |
| Result | None |
| Evidence | None |
| Blocked Reason | None |
| Required Route | NONE |

#### Notes

- BOQ-08／FOQ-03（本番で購入者が模擬決済の結果を選べることの受容。UNRESOLVED-32af0f4a0ca9c80f）は未決。暫定扱いにより本番のみの挙動差を設計・実装で追加しない。

### TASK-009 `注文金額計算（FR-026）`

#### Metadata

| 項目 | 内容 |
| --- | --- |
| Type | IMPLEMENT |
| Priority | HIGH |
| Status | TODO |
| Target Area | カート・注文の業務処理（金額計算・クーポン適用可否） |
| Depends On | TASK-002、TASK-005 |
| Blocks | TASK-012、TASK-014 |

#### Source References

| Type | ID / Path | Relevant Section / Reason |
| --- | --- | --- |
| Requirement | FR-026、FR-020、FR-024、FR-030、NFR-LG-06、NFR-PF-11 | functional_requirements.md 6.14（小計・割引額・割引後小計・送料・消費税額・合計、適用可否と理由）、CMN-29〜CMN-31 |
| Use Case / AC | UC-004、UC-005、UC-006 の金額・クーポン適用可否の AC | 金額内訳の表示・確定 |
| ADR | None（後続ADDR：構成（候補 application-structure）を確認） | 業務規則の配置 |
| Detailed Design | ENT-007、ENT-008、ENT-009、ENT-010（LDC-ENT-010-002、LDR-007、LDM-DEC-003、LDM-DEC-004） | 算出式と保持・非保持 |

#### Objective

カート（参照のたび現在値・現在時刻で算出）と注文確定（確定時刻で算出して確定）で共通に使う金額計算と、クーポンの適用可否（有効期間前・終了・最低購入金額未満・カートが空）の判定を、画面と Web API で同一の規則として実装する。

#### Scope

##### In Scope

- DQ-20〜DQ-26 の算出式、1円未満切り捨て、送料0/500、税率10%
- 秒単位の有効期間判定（両端を含む）

##### Out of Scope

- カートの更新処理（TASK-012）、注文の登録（TASK-014）

#### Expected Change

- 金額計算・クーポン判定の業務コンポーネント

#### Constraints

- 画面側に金額計算を重複実装しない（Steering 5章、FCN-09）

#### Completion Criteria / Definition of Done

- [ ] 境界値（最低購入金額ちょうど、有効期間端、割引額＝小計、送料境界5,000円）の単体テストが PASS
- [ ] Build / ruff が PASS
- [ ] 送料・消費税額・合計金額の計算規則を、画面と Web API で共通の業務処理として同じ規則で判定する（NFR-LG-06）
- [ ] 不要なScope Expansionがない

#### Validation

| Validation Type | Command / Method | Expected Result |
| --- | --- | --- |
| Build | TASK-001 の起動手順 | PASS |
| Static Check | ruff check | PASS |
| Unit Test | pytest（金額計算） | planned |
| Other | 金額整合の照合（NFR-PF-11） | later phase |

#### Progress / Result

| 項目 | 内容 |
| --- | --- |
| Started At | None |
| Completed At | None |
| Result | None |
| Evidence | None |
| Blocked Reason | None |
| Required Route | NONE |

#### Notes

- BOQ-09（EC販売規程の制定状況）は未決。暫定で BR-01〜BR-19 の現行記載を前提とする。

### TASK-010 `在庫単位一覧照会（管理者）`

#### Metadata

| 項目 | 内容 |
| --- | --- |
| Type | IMPLEMENT |
| Priority | MEDIUM |
| Status | TODO |
| Target Area | 管理（業務処理・Web API・画面 SCR-101） |
| Depends On | TASK-004、TASK-006 |
| Blocks | TASK-020 |

#### Source References

| Type | ID / Path | Relevant Section / Reason |
| --- | --- | --- |
| Requirement | FR-040、NFR-PF-08、NFR-US-01、NFR-US-02、NFR-US-05、NFR-US-06、NFR-US-07、NFR-LG-08、NFR-PF-03、NFR-PF-01、NFR-EN-05 | functional_requirements.md 6.20（SKU 前方一致、商品名部分一致、仕入先、低在庫5以下、SKU 昇順、50件ページング） |
| Use Case / AC | UC-010（AC-UC-010-001〜AC-UC-010-011） | 在庫を確認する（注文確定（TASK-014）・購入者の注文キャンセル（TASK-016）を用いる AC-UC-010-008 は TASK-020 で確認） |
| ADR | None（後続ADDR：Web API 契約（候補 api-contract）を確認） | 方式判断は ADDR |
| Detailed Design | ENT-002、ENT-004、ENT-006（docs/architecture/db-logical-design.md 7.2、7.4、7.6、PHY-HO-008） | 非公開商品を含む全件参照 |

#### Objective

管理者に、非公開商品の在庫単位を含む全在庫単位の在庫数量・低在庫を条件指定・ページ単位で返す。

#### Scope

##### In Scope

- FR-040 の処理・例外、低在庫しきい値5の固定

##### Out of Scope

- 在庫数量の変更・補充（FR-OUT-03、FOQ-01）

#### Expected Change

- 在庫単位一覧の照会処理、Web API、SCR-101

#### Constraints

- 購入者の要求は権限エラー（CMN-03）
- 本Taskの画面（SCR-101）は、Windows 11 の PC の Google Chrome 最新版・Microsoft Edge 最新版で全操作を行えること（NFR-US-01、NFR-US-06）、幅 1280px×高さ 720px 以上の表示領域で横スクロール・表示崩れ（要素の重なり・欠け）が無いこと（NFR-US-02）、JIS X 8341-3:2016 適合レベル A に適合すること（NFR-US-05、NFR-LG-08）、キーボード（Tab・Shift+Tab・Enter・Space・矢印キー）だけで全操作を行えること（NFR-US-07）を満たす。画面の表示完了時間 2.0秒以内（NFR-PF-03）を満たせる画面構成とし、外部 CDN に依存しない（NFR-EN-05）

#### Completion Criteria / Definition of Done

- [ ] UC-010 の AC を満たせる（AC-UC-010-008 を除く。注文確定（TASK-014）・購入者の注文キャンセル（TASK-016）を用いるため TASK-020 で確認する）
- [ ] Build / ruff / 単体テストが PASS
- [ ] 本Taskの画面（SCR-101）を Windows 11 の Chrome・Edge 最新版で全操作でき、1280×720 の表示領域で横スクロール・表示崩れが無く、JIS X 8341-3:2016 適合レベル A の達成基準のチェックリストを満たし、キーボードだけで全操作を行える（NFR-US-01、NFR-US-02、NFR-US-05、NFR-US-06、NFR-US-07。互換性・操作性テスト。画面をまたぐ一連の操作は TASK-020）
- [ ] 在庫単位一覧の応答件数の上限を守る（NFR-PF-08）
- [ ] 不要なScope Expansionがない

#### Validation

| Validation Type | Command / Method | Expected Result |
| --- | --- | --- |
| Build | TASK-001 の起動手順 | PASS |
| Static Check | ruff check | PASS |
| Unit Test | pytest（在庫単位一覧） | planned |
| Other | N/A | N/A |
| Other | 互換性・操作性テスト（本Taskの画面 SCR-101：2種のブラウザでの全操作（NFR-US-01、NFR-US-06）、1280×720 表示（NFR-US-02）、適合レベル A のチェックリスト（NFR-US-05）、キーボードだけでの全操作（NFR-US-07）） | PASS |
| Other | 性能テスト（在庫単位一覧照会の応答時間 1.0秒以内：NFR-PF-01、SCR-101 の表示完了時間：NFR-PF-03） | later phase（試験工程。ENV-01 のピーク負荷・3年後データ量で測定） |

#### Progress / Result

| 項目 | 内容 |
| --- | --- |
| Started At | None |
| Completed At | None |
| Result | None |
| Evidence | None |
| Blocked Reason | None |
| Required Route | NONE |

#### Notes

- 実装前に後続ADDRと implementation-handoff を読む。

### TASK-011 `初期データ一括投入（FILE-001）`

#### Metadata

| 項目 | 内容 |
| --- | --- |
| Type | IMPLEMENT |
| Priority | HIGH |
| Status | TODO |
| Target Area | 運用機能（運用者がサーバー上で実行。画面・Web API なし） |
| Depends On | TASK-002、TASK-003、TASK-004、TASK-005、TASK-006 |
| Blocks | TASK-013、TASK-020 |

#### Source References

| Type | ID / Path | Relevant Section / Reason |
| --- | --- | --- |
| Requirement | FR-060、NFR-OM-04、NFR-OM-13、NFR-PF-10、NFR-SC-08、NFR-SC-15、NFR-EN-04、NFR-MG-04、NFR-MG-07、NFR-OM-11、NFR-OM-19、NFR-MG-03、NFR-SC-22、NFR-SC-23 | functional_requirements.md 6.26（手順1〜12、手順9 削除した利用者のログイン状態の無効化、E-060-01〜E-060-06、6.26.9 同時実行・削除指定投入完了後の削除前ログイン状態は認証エラー） |
| Use Case / AC | UC-013（AC-UC-013-001〜AC-UC-013-011） | 初期データを一括投入する（投入した利用者のログイン（Web API）は TASK-006 で確認。注文一覧（管理）画面・商品一覧・在庫単位一覧・全画面を用いる AC-UC-013-002、AC-UC-013-003、AC-UC-013-011 は TASK-020 で確認） |
| ADR | None（後続ADDR：記載形式（候補 initial-data-file-format）、起動手段（候補 initial-data-invocation）、パスワード保持方式（候補 password-storage）、同時実行制御（候補 concurrency-transaction）、削除した利用者のログイン状態の無効化（候補 authentication-session）、削除指定後の利用者識別子の扱い（候補 identifier-assignment）を確認。ジョブ実行ログ（LOG-05）の方式（候補 application-logging）も確認） | 方式判断は ADDR |
| Detailed Design | FILE-001（docs/architecture/files/FILE-001.md）、ENT-001〜ENT-015（LDR-002、LDR-013、PHY-HO-007） | 定義ファイルの項目・変換・異常処理、削除指定の全件削除と削除した利用者のログイン状態の無効化 |

#### Objective

運用者が指定した定義ファイル1件を検証し（値域・一意性・参照整合性・階層の違反を全件収集）、違反0件の場合のみ（削除指定時は監査ログ以外の全データを削除してから）全データを記載順に登録し、成功・失敗とも監査ログを1件記録して結果を運用者に示す。

#### Scope

##### In Scope

- FR-060 の手順1〜12と E-060-01〜E-060-06、全件成功か無変更、違反全件の提示（値は示さない）
- 業務キーによる参照解決、行番号の付与、既定値設定、パスワードの保持（平文で保持しない）
- 同時実行時に逐次実行と同じ結果（6.26.9）
- 削除指定時に削除した利用者のログイン状態を無効にし、投入完了後は削除前のログイン状態による要求を認証エラーとする（手順9、6.26.9。認証側の判定は TASK-006）
- ジョブ実行ログ（LOG-05）の出力：データ別の投入件数、検証エラー時の違反内容（データ名・行番号・項目・理由。項目の値は出力しない）（NFR-OM-11。バックアップの LOG-05 は本番基盤の対象で本Task外）
- 管理者アカウントと初期パスワードの登録（NFR-MG-03、NFR-SC-15）
- 初期データ一括投入の実行手順を開発・検証環境向けの手順書（TASK-001）へ記載（NFR-OM-19）

##### Out of Scope

- 画面・Web API からの起動・ファイル受付（CMN-37）
- 本番環境で削除指定を拒否する条件の追加（NOQ-09 未決。暫定扱いで FR-060 の振る舞いを変更しない）

#### Expected Change

- 初期データ一括投入の運用コマンド相当の機能（起動手段は ADDR 判断に従う）

#### Constraints

- 削除指定でも監査ログは削除しない（NFR-SC-23、NFR-OM-04）
- 違反通知・ログ・監査ログに項目の値（パスワード・メールアドレス・氏名）を出さない
- 処理完了 60秒以内（NFR-PF-10、推奨）

#### Completion Criteria / Definition of Done

- [ ] UC-013 の AC と FILE-001 13章の FILE-V-001〜FILE-V-009 を満たせる（AC-UC-013-002、AC-UC-013-003、AC-UC-013-011 を除く。これらは注文一覧（管理）画面（TASK-018）、商品一覧（TASK-007）、在庫単位一覧（TASK-010）、全画面を用いるため TASK-020 で確認する。ログイン・会員登録との競合の確認は TASK-006 の機能を使う。TASK-006 は Depends On に宣言済み）
- [ ] 削除指定ありの投入完了後、削除前のログイン状態（Web API・画面）による要求が認証エラーとなり、削除後に投入された利用者として認証されない（FR-060 手順9・6.26.9、FILE-V-009）
- [ ] Build / ruff / 単体テストが PASS
- [ ] 初期データ一括投入の実行ごとに LOG-05（ジョブ実行ログ）がデータ別の投入件数、検証エラー時の違反内容（データ名・行番号・項目・理由）で出力され、項目の値を含まない。LOG-04（監査ログ）に成功・失敗が記録される（NFR-OM-11、NFR-SC-22）
- [ ] 初期データ一括投入の実行手順が開発・検証環境向けの手順書に記載され、手順どおりに ENV-01 で実行できる（NFR-OM-19）
- [ ] 1回の実行操作で完了し、異常時は全件取消し（何も削除・投入しない）となる（NFR-OM-04、NFR-MG-04、NFR-MG-07）。定義ファイルを UTF-8 で読み日時を JST で扱い（NFR-EN-04）、削除指定で削除した利用者のログイン状態を無効にし（NFR-SC-08）、監査ログを削除・変更しない（NFR-SC-23）
- [ ] 不要なScope Expansionがない

#### Validation

| Validation Type | Command / Method | Expected Result |
| --- | --- | --- |
| Build | TASK-001 の起動手順 | PASS |
| Static Check | ruff check | PASS |
| Unit Test | pytest（定義ファイル検証・投入・削除指定） | planned |
| Other | 違反行1件を含むファイルで投入件数0、修正後の再実行で件数一致（NFR-OM-13） | PASS |
| Other | 正常・検証エラーの投入後の LOG-05・LOG-04 の出力内容の確認（NFR-OM-11）、手順書どおりの実行（NFR-OM-19） | PASS |

#### Progress / Result

| 項目 | 内容 |
| --- | --- |
| Started At | None |
| Completed At | None |
| Result | None |
| Evidence | None |
| Blocked Reason | None |
| Required Route | NONE |

#### Notes

- NOQ-10（本番投入用定義ファイルの保管・廃棄、管理者の資格情報の失効手段。UNRESOLVED-32af0f4a0ca9c80f）は未決。暫定扱いにより本番投入用ファイルはリポジトリに置かず、機能を追加しない。
- NOQ-09／DOQ-04／FOQ-02（削除指定の本番移行での使用可否）は未決。

### TASK-012 `カート照会・明細追加・数量変更・削除・クーポン適用・解除`

#### Metadata

| 項目 | 内容 |
| --- | --- |
| Type | IMPLEMENT |
| Priority | HIGH |
| Status | TODO |
| Target Area | カート（業務処理・Web API・画面 SCR-005、SCR-002 のカート投入） |
| Depends On | TASK-005、TASK-006、TASK-007、TASK-009、TASK-017 |
| Blocks | TASK-014、TASK-020 |

#### Source References

| Type | ID / Path | Relevant Section / Reason |
| --- | --- | --- |
| Requirement | FR-020、FR-021、FR-022、FR-023、FR-024、FR-025、NFR-US-01、NFR-US-02、NFR-US-05、NFR-US-06、NFR-US-07、NFR-LG-08、NFR-PF-03、NFR-PF-01、NFR-PF-02、NFR-PF-16、NFR-US-09、NFR-US-10、NFR-LG-02、NFR-LG-06、NFR-EN-05 | functional_requirements.md 6.8〜6.13、8.2（ST-CART-01）、CMN-19〜CMN-23 |
| Use Case / AC | UC-004（AC-UC-004-001〜AC-UC-004-027 のうち定義済みの AC）、UC-005（AC-UC-005-001〜AC-UC-005-030 のうち定義済みの AC） | カート操作・クーポン適用・解除 |
| ADR | None（後続ADDR：同時実行制御（候補 concurrency-transaction）、Web API 契約（候補 api-contract）を確認） | 方式判断は ADDR |
| Detailed Design | ENT-006、ENT-007、ENT-008、ENT-009（LDC-ENT-008-001、LDC-ENT-009-001〜LDC-ENT-009-003、LDR-003、LDR-006、LDR-014） | 利用中カート一意、数量上限10・在庫数量以下、追加順 |

#### Objective

購入者本人の利用中カートについて、照会（なければ作成）、明細の追加（同一在庫単位は加算）・数量変更・削除、クーポンの適用（1枚）・解除を、金額内訳（TASK-009）とともに提供する。

#### Scope

##### In Scope

- FR-020〜FR-025 の処理・例外、利用中カートの同時作成で1件のみ（DQ-09）
- 削除済み明細への操作は対象なし（CMN-19）、注文済カートの明細指定は対象なし

##### Out of Scope

- 在庫の引当（注文確定のみ：TASK-014）
- ゲスト購入（FR-OUT-10）、複数クーポン併用（FR-OUT-05）

#### Expected Change

- カートの業務処理、Web API、SCR-005、SCR-002 の「カートに入れる」

#### Constraints

- 管理者の要求は権限エラー（CMN-03）
- 適用中のクーポンが条件を満たさなくなっても自動解除しない（DR-008 備考、MSG-07）
- 本Taskの画面（SCR-005、SCR-002 のカートに入れる操作）は、Windows 11 の PC の Google Chrome 最新版・Microsoft Edge 最新版で全操作を行えること（NFR-US-01、NFR-US-06）、幅 1280px×高さ 720px 以上の表示領域で横スクロール・表示崩れ（要素の重なり・欠け）が無いこと（NFR-US-02）、JIS X 8341-3:2016 適合レベル A に適合すること（NFR-US-05、NFR-LG-08）、キーボード（Tab・Shift+Tab・Enter・Space・矢印キー）だけで全操作を行えること（NFR-US-07）を満たす。画面の表示完了時間 2.0秒以内（NFR-PF-03）を満たせる画面構成とし、外部 CDN に依存しない（NFR-EN-05）

#### Completion Criteria / Definition of Done

- [ ] UC-004・UC-005 の AC を満たせる（クーポン有効期間の境界は TASK-017 の時刻設定で確認。SCR-002 からのカート投入（AC-UC-004-023、AC-UC-004-024）は TASK-007 の SCR-002 と TASK-006 のログイン画面を用いる。TASK-006・TASK-007・TASK-017 は Depends On に宣言済み）
- [ ] Build / ruff / 単体テストが PASS
- [ ] カート明細の削除の実行前に確認を求め、承諾しない場合はデータ変更0件である（NFR-US-09）
- [ ] カートの更新操作を処理が完了するまでの間に繰り返しても、更新は1回分だけ反映される（NFR-US-10）
- [ ] アプリケーションの実行単位を追加して処理能力を増強しても、カートの内容が失われない構造である（NFR-PF-16。静的解析・コードレビュー）
- [ ] 本Taskの画面（SCR-005、SCR-002 のカートに入れる操作）を Windows 11 の Chrome・Edge 最新版で全操作でき、1280×720 の表示領域で横スクロール・表示崩れが無く、JIS X 8341-3:2016 適合レベル A の達成基準のチェックリストを満たし、キーボードだけで全操作を行える（NFR-US-01、NFR-US-02、NFR-US-05、NFR-US-06、NFR-US-07。互換性・操作性テスト。画面をまたぐ一連の操作は TASK-020）
- [ ] カートの内訳に消費税額と税込の合計を表示し（NFR-LG-02）、数量上限・クーポンの適用条件を画面と Web API で同じ規則で判定する（NFR-LG-06）
- [ ] 不要なScope Expansionがない

#### Validation

| Validation Type | Command / Method | Expected Result |
| --- | --- | --- |
| Build | TASK-001 の起動手順 | PASS |
| Static Check | ruff check | PASS |
| Unit Test | pytest（カート操作） | planned |
| Other | 同一購入者の同時カート照会で利用中カート1件 | PASS |
| Other | 互換性・操作性テスト（本Taskの画面 SCR-005：2種のブラウザでの全操作（NFR-US-01、NFR-US-06）、1280×720 表示（NFR-US-02）、適合レベル A のチェックリスト（NFR-US-05）、キーボードだけでの全操作（NFR-US-07）） | PASS |
| Other | 性能テスト（カート照会の応答時間 1.0秒以内：NFR-PF-01、カート操作の応答時間 2.0秒以内：NFR-PF-02、SCR-005 の表示完了時間：NFR-PF-03） | later phase（試験工程。ENV-01 のピーク負荷・3年後データ量で測定） |

#### Progress / Result

| 項目 | 内容 |
| --- | --- |
| Started At | None |
| Completed At | None |
| Result | None |
| Evidence | None |
| Blocked Reason | None |
| Required Route | NONE |

#### Notes

- 実装前に後続ADDRと implementation-handoff を読む。

### TASK-013 `検証用初期データ定義ファイル（架空データ）`

#### Metadata

| 項目 | 内容 |
| --- | --- |
| Type | TEST_SUPPORT |
| Priority | MEDIUM |
| Status | TODO |
| Target Area | app/seed/（検証用定義ファイル） |
| Depends On | TASK-011 |
| Blocks | TASK-021 |

#### Source References

| Type | ID / Path | Relevant Section / Reason |
| --- | --- | --- |
| Requirement | FR-060、NFR-SC-25、NFR-OM-04、NFR-LG-01 | 検証環境の初期化、架空の値のみ |
| Use Case / AC | UC-013、および各 UC の事前条件（購入者・管理者・商品・在庫単位・クーポン） | 試験データの用意 |
| ADR | None（後続ADDR：記載形式（候補 initial-data-file-format）を確認） | ファイル構造は ADDR |
| Detailed Design | FILE-001（docs/architecture/files/FILE-001.md 6〜9章） | 項目・値域・業務キー |

#### Objective

検証環境（ENV-01）を初期状態に戻すための、架空の値だけで作成した定義ファイルを app/seed/ に用意する。

#### Scope

##### In Scope

- 管理者・購入者・仕入先・商品分類（3階層まで）・商品（公開・非公開）・在庫単位（低在庫・在庫0を含む）・クーポンの架空データ

##### Out of Scope

- 本番投入用の定義ファイル（リポジトリに置かない：NOQ-10 暫定扱い、Steering OQ-PJ-003）
- 非機能試験用の大量データ（VDC 系の作成は試験工程）

#### Expected Change

- app/seed/ 配下の検証用定義ファイル（UTF-8/JSON）

#### Constraints

- 実在の個人情報・本番データを使わない（Steering 7章、NFR-SC-25、DCN-15）
- パスワードは架空の値のみ

#### Completion Criteria / Definition of Done

- [ ] TASK-011 の投入（削除指定あり）が違反0件で成功する
- [ ] 実在の個人情報を含まないことをレビューで確認
- [ ] 定義ファイルを1回の実行操作で投入でき（NFR-OM-04）、実在の個人情報を含まない（NFR-SC-25、NFR-LG-01）
- [ ] 不要なScope Expansionがない

#### Validation

| Validation Type | Command / Method | Expected Result |
| --- | --- | --- |
| Build | N/A | N/A |
| Static Check | N/A | N/A |
| Unit Test | 初期データ一括投入の実行（TASK-011 の起動手段） | 成功・件数一致 |
| Other | 架空データであることのレビュー | PASS |

#### Progress / Result

| 項目 | 内容 |
| --- | --- |
| Started At | None |
| Completed At | None |
| Result | None |
| Evidence | None |
| Blocked Reason | None |
| Required Route | NONE |

#### Notes

- 実装前に後続ADDRと implementation-handoff を読む。

### TASK-014 `注文確定（在庫一括引当・注文番号発行）`

#### Metadata

| 項目 | 内容 |
| --- | --- |
| Type | IMPLEMENT |
| Priority | HIGH |
| Status | TODO |
| Target Area | 注文（業務処理・Web API・画面 SCR-006、SCR-007） |
| Depends On | TASK-009、TASK-012、TASK-017 |
| Blocks | TASK-015、TASK-016、TASK-019、TASK-020 |

#### Source References

| Type | ID / Path | Relevant Section / Reason |
| --- | --- | --- |
| Requirement | FR-030、NFR-PF-07、NFR-PF-11、NFR-US-10、NFR-US-01、NFR-US-02、NFR-US-05、NFR-US-06、NFR-US-07、NFR-LG-08、NFR-PF-03、NFR-PF-02、NFR-PF-04、NFR-US-03、NFR-US-09、NFR-LG-02、NFR-LG-06、NFR-LG-09、NFR-EN-05 | functional_requirements.md 6.15（手順1〜18、E-030-01〜E-030-11、6.15.9 同時実行）、8.1 ST-PO-01、8.2 ST-CART-02 |
| Use Case / AC | UC-006（AC-UC-006-001〜AC-UC-006-032 のうち定義済みの AC） | 注文を確定する（注文詳細照会（TASK-016）で確認する AC-UC-006-005・AC-UC-006-006 は TASK-020、注文確定途中の障害の AC-UC-006-022 は TASK-019 で確認） |
| ADR | None（後続ADDR：同時実行制御・トランザクション境界（候補 concurrency-transaction）、注文番号（候補 order-number-issuance）を確認） | 方式判断は ADDR |
| Detailed Design | ENT-006、ENT-008〜ENT-012、ENT-014（LDC-ENT-006-001、LDC-ENT-010-001〜LDC-ENT-010-007、LDC-ENT-011-001〜LDC-ENT-011-003、LDR-004、LDR-011、LDR-016） | 在庫一括引当、全件成功か無変更、確定時点の複写 |

#### Objective

配送先を受け付け、数量上限・公開状態・クーポン条件・在庫を確定時刻で再判定し、全明細の在庫を一括で引き当てて注文・注文明細・配送先・注文状態履歴を登録し、カートを注文済にする（いずれか失敗時はすべて処理前のまま）。

#### Scope

##### In Scope

- FR-030 の判定順序・例外、同一在庫単位への同時確定・同一カートの二重送信の扱い
- 注文番号の発行（PO-＋8桁、確定順に増加）

##### Out of Scope

- 支払（TASK-015）

#### Expected Change

- 注文確定の業務処理、Web API、SCR-006・SCR-007

#### Constraints

- 在庫数量は0未満にならず、引当合計が在庫を超えない（NFR-PF-07：在庫5に10並列で成功5・在庫不足5）
- 非公開・数量超過・クーポン条件違反の明細やクーポンを自動で外さない
- 本Taskの画面（SCR-006、SCR-007）は、Windows 11 の PC の Google Chrome 最新版・Microsoft Edge 最新版で全操作を行えること（NFR-US-01、NFR-US-06）、幅 1280px×高さ 720px 以上の表示領域で横スクロール・表示崩れ（要素の重なり・欠け）が無いこと（NFR-US-02）、JIS X 8341-3:2016 適合レベル A に適合すること（NFR-US-05、NFR-LG-08）、キーボード（Tab・Shift+Tab・Enter・Space・矢印キー）だけで全操作を行えること（NFR-US-07）を満たす。画面の表示完了時間 2.0秒以内（NFR-PF-03）を満たせる画面構成とし、外部 CDN に依存しない（NFR-EN-05）
- 配送先の都道府県は JIS X 0401 の都道府県コード（CD-06）で扱う（NFR-LG-09）

#### Completion Criteria / Definition of Done

- [ ] UC-006 の AC を満たせる（AC-UC-006-005、AC-UC-006-006、AC-UC-006-022 を除く。AC-UC-006-022（注文確定途中の障害：EX-09、BR-UC-006-013）は障害の設定手段を前提とするため TASK-019、AC-UC-006-005・AC-UC-006-006 は確定後の注文詳細照会（FR-033、TASK-016）を用いるため TASK-020 で確認する。確定時刻でのクーポン有効期間の境界は TASK-017 の時刻設定で確認）
- [ ] Build / ruff / 単体テストが PASS
- [ ] 注文確定の実行前に確認を求め、承諾しない場合はデータ変更0件である（NFR-US-09）
- [ ] 配送先に JIS 第3・第4水準の漢字を入力して注文を確定し、同じ文字が表示される（NFR-US-03）
- [ ] 本Taskの画面（SCR-006、SCR-007）を Windows 11 の Chrome・Edge 最新版で全操作でき、1280×720 の表示領域で横スクロール・表示崩れが無く、JIS X 8341-3:2016 適合レベル A の達成基準のチェックリストを満たし、キーボードだけで全操作を行える（NFR-US-01、NFR-US-02、NFR-US-05、NFR-US-06、NFR-US-07。互換性・操作性テスト。画面をまたぐ一連の操作は TASK-020）
- [ ] 注文確定を処理が完了するまでの間に繰り返しても注文は1件だけ作成される（NFR-US-10）
- [ ] 想定を超える負荷でも、受け付けた要求に正常応答またはエラーを返し、在庫・金額の不整合を生じない構造である（NFR-PF-11。測定は試験工程）
- [ ] 注文の内訳に消費税額と税込の合計を表示し（NFR-LG-02）、数量上限・クーポン・在庫引当の確定時の再判定を画面と Web API で同じ規則で判定する（NFR-LG-06）
- [ ] 不要なScope Expansionがない

#### Validation

| Validation Type | Command / Method | Expected Result |
| --- | --- | --- |
| Build | TASK-001 の起動手順 | PASS |
| Static Check | ruff check | PASS |
| Unit Test | pytest（注文確定） | planned |
| Other | 10並列同時確定の結合試験（NFR-PF-07） | later phase |
| Other | 互換性・操作性テスト（本Taskの画面 SCR-006、SCR-007：2種のブラウザでの全操作（NFR-US-01、NFR-US-06）、1280×720 表示（NFR-US-02）、適合レベル A のチェックリスト（NFR-US-05）、キーボードだけでの全操作（NFR-US-07）） | PASS |
| Other | 性能テスト（注文確定の応答時間 2.0秒以内：NFR-PF-02、60分間に240件以上：NFR-PF-04、SCR-006・SCR-007 の表示完了時間：NFR-PF-03） | later phase（試験工程。ENV-01 のピーク負荷・3年後データ量で測定） |

#### Progress / Result

| 項目 | 内容 |
| --- | --- |
| Started At | None |
| Completed At | None |
| Result | None |
| Evidence | None |
| Blocked Reason | None |
| Required Route | NONE |

#### Notes

- 実装前に後続ADDRと implementation-handoff を読む。
- 注文確定途中の障害の AC（AC-UC-006-022。EX-09、BR-UC-006-013）は、障害の設定手段とともに後続の TASK-019 の完了条件で検証する（修正cycle 1、QR-ARCH-001）。
- 確定後の注文詳細で確認する AC-UC-006-005・AC-UC-006-006 は TASK-020 で検証する（修正cycle 2、QR-ARCH-R1-002）。

### TASK-015 `支払（模擬決済）`

#### Metadata

| 項目 | 内容 |
| --- | --- |
| Type | IMPLEMENT |
| Priority | HIGH |
| Status | TODO |
| Target Area | 注文（業務処理・Web API・画面 SCR-008） |
| Depends On | TASK-008、TASK-014、TASK-016、TASK-017 |
| Blocks | TASK-018、TASK-020 |

#### Source References

| Type | ID / Path | Relevant Section / Reason |
| --- | --- | --- |
| Requirement | FR-031、NFR-PF-02、IFR-001、NFR-US-01、NFR-US-02、NFR-US-05、NFR-US-06、NFR-US-07、NFR-LG-08、NFR-PF-03、NFR-US-10、NFR-PF-17、NFR-LG-05、NFR-EN-05 | functional_requirements.md 6.16（手順1〜11、E-031-01〜E-031-08、6.16.9）、8.1 ST-PO-02 |
| Use Case / AC | UC-007（AC-UC-007-001〜AC-UC-007-019 のうち定義済みの AC） | 注文の代金を支払う（注文詳細画面 SCR-010・注文詳細照会 FR-033・購入者の注文キャンセル FR-034 を用いる AC-UC-007-002・004・005・014・018・019 は TASK-016 の成果を用いる。TASK-016 を Depends On に宣言） |
| ADR | None（後続ADDR：IFR-001 の方式（候補 mock-payment-interface）、同時実行制御（候補 concurrency-transaction）を確認） | 方式判断は ADDR |
| Detailed Design | ENT-010、ENT-013、ENT-014（LDC-ENT-013-001〜LDC-ENT-013-004、LDR-009、MAP-001〜MAP-008） | 承認最大1件、否認・連携エラーの記録 |

#### Objective

本人の注文受付の注文について決済要求を1回送り、承認なら決済記録・支払済・状態履歴を一括で反映し、否認・連携エラーなら決済記録のみを登録して注文受付のまま再支払可能とする。

#### Scope

##### In Scope

- FR-031 の判定順序・例外、同時支払・支払とキャンセルの競合の扱い（6.16.9）
- 二重操作時の決済要求1回（CMN-22）

##### Out of Scope

- 返金処理（FR-OUT-04。本システム外）
- 本番環境のみの挙動差（BOQ-08 未決。暫定扱いで追加しない）

#### Expected Change

- 支払の業務処理、Web API、SCR-008

#### Constraints

- 購入者に決済記録の内容を表示しない（MSG-04、REF-23）
- 自動再送しない（IF-01-CON-01）
- 本Taskの画面（SCR-008）は、Windows 11 の PC の Google Chrome 最新版・Microsoft Edge 最新版で全操作を行えること（NFR-US-01、NFR-US-06）、幅 1280px×高さ 720px 以上の表示領域で横スクロール・表示崩れ（要素の重なり・欠け）が無いこと（NFR-US-02）、JIS X 8341-3:2016 適合レベル A に適合すること（NFR-US-05、NFR-LG-08）、キーボード（Tab・Shift+Tab・Enter・Space・矢印キー）だけで全操作を行えること（NFR-US-07）を満たす。画面の表示完了時間 2.0秒以内（NFR-PF-03）を満たせる画面構成とし、外部 CDN に依存しない（NFR-EN-05）
- クレジットカード番号・有効期限・セキュリティコードを入力させない。支払の入力は模擬決済の指示（承認／否認）のみ（NFR-LG-05）

#### Completion Criteria / Definition of Done

- [ ] UC-007 の AC を満たせる（模擬決済の遅延・接続不可・応答不正は TASK-017、注文詳細画面への遷移・注文詳細照会・支払とキャンセルの競合（AC-UC-007-002、AC-UC-007-004、AC-UC-007-005、AC-UC-007-014、AC-UC-007-018、AC-UC-007-019）は TASK-016 の機能を用いる。TASK-016・TASK-017 は Depends On に宣言済み）
- [ ] Build / ruff / 単体テストが PASS
- [ ] 支払を処理が完了するまでの間に繰り返し操作しても決済要求は1回分だけ送信され、決済記録が1件だけ作成される（NFR-US-10）
- [ ] 支払の処理（決済記録・注文状態の更新）が、決済サービスとの連携部分（TASK-008）の差替えで変更を要しない構造である（NFR-PF-17。静的解析・コードレビュー）
- [ ] 本Taskの画面（SCR-008）を Windows 11 の Chrome・Edge 最新版で全操作でき、1280×720 の表示領域で横スクロール・表示崩れが無く、JIS X 8341-3:2016 適合レベル A の達成基準のチェックリストを満たし、キーボードだけで全操作を行える（NFR-US-01、NFR-US-02、NFR-US-05、NFR-US-06、NFR-US-07。互換性・操作性テスト。画面をまたぐ一連の操作は TASK-020）
- [ ] 不要なScope Expansionがない

#### Validation

| Validation Type | Command / Method | Expected Result |
| --- | --- | --- |
| Build | TASK-001 の起動手順 | PASS |
| Static Check | ruff check | PASS |
| Unit Test | pytest（支払） | planned |
| Other | 遅延・接続不可・応答不正（TASK-017。Depends On に宣言済み）での連携エラー確認 | PASS |
| Other | 互換性・操作性テスト（本Taskの画面 SCR-008：2種のブラウザでの全操作（NFR-US-01、NFR-US-06）、1280×720 表示（NFR-US-02）、適合レベル A のチェックリスト（NFR-US-05）、キーボードだけでの全操作（NFR-US-07）） | PASS |
| Other | 性能テスト（支払の応答時間 2.0秒以内（模擬機能の応答時間を含む）：NFR-PF-02、SCR-008 の表示完了時間：NFR-PF-03） | later phase（試験工程。ENV-01 のピーク負荷・3年後データ量で測定） |

#### Progress / Result

| 項目 | 内容 |
| --- | --- |
| Started At | None |
| Completed At | None |
| Result | None |
| Evidence | None |
| Blocked Reason | None |
| Required Route | NONE |

#### Notes

- BOQ-08／FOQ-03（本番で購入者の選択だけで支払済・出荷対象となる扱いの決定・受容。UNRESOLVED-32af0f4a0ca9c80f、HIGH）は未決。暫定扱いにより現行 FR-031 のとおり実装し範囲を拡大しない。稼働開始判定の未充足事項（Blocking）として残る。

### TASK-016 `注文履歴一覧・注文詳細照会・注文キャンセル（購入者）と在庫戻し`

#### Metadata

| 項目 | 内容 |
| --- | --- |
| Type | IMPLEMENT |
| Priority | HIGH |
| Status | TODO |
| Target Area | 注文（業務処理・Web API・画面 SCR-009、SCR-010）、在庫戻しの共通処理 |
| Depends On | TASK-014 |
| Blocks | TASK-015、TASK-018、TASK-020 |

#### Source References

| Type | ID / Path | Relevant Section / Reason |
| --- | --- | --- |
| Requirement | FR-032、FR-033、FR-034、NFR-US-01、NFR-US-02、NFR-US-05、NFR-US-06、NFR-US-07、NFR-LG-08、NFR-PF-03、NFR-PF-01、NFR-PF-02、NFR-US-09、NFR-US-10、NFR-LG-06、NFR-EN-05、NFR-SC-24 | functional_requirements.md 6.17〜6.19、8.1 ST-PO-03・ST-PO-04、PRM-01 |
| Use Case / AC | UC-008（AC-UC-008-001〜AC-UC-008-015 のうち定義済みの AC）、UC-009（AC-UC-009-001〜AC-UC-009-010） | 注文状況の確認・キャンセル |
| ADR | None（後続ADDR：同時実行制御（候補 concurrency-transaction）を確認） | 方式判断は ADDR |
| Detailed Design | ENT-006、ENT-010〜ENT-014（LDC-ENT-006-002、LDR-005、LDR-010、LDR-014、13章） | 在庫戻し1回、本人分のみ、実行者を購入者に提供しない |

#### Objective

購入者本人の注文の一覧・詳細（明細・金額・配送先・状態履歴）を返し、注文受付・支払済の本人の注文をキャンセル済にして全明細の数量を在庫へ1回だけ戻す。在庫戻しは管理者キャンセル（TASK-018）と共通の処理とする。

#### Scope

##### In Scope

- FR-032〜FR-034 の処理・例外、他の購入者の注文は対象なし（CMN-04）
- 支払とキャンセルの競合、二重キャンセルの状態不正（支払との同時実行の確認は支払（TASK-015）を要するため AC-UC-007-019 として TASK-015 で行う）

##### Out of Scope

- 返金（FR-OUT-04）、未払い注文の自動キャンセル（FR-OUT-12）

#### Expected Change

- 注文照会・キャンセルの業務処理、在庫戻しの共通処理、Web API、SCR-009・SCR-010

#### Constraints

- 決済記録は変更しない（DQ-34）
- 本Taskの画面（SCR-009、SCR-010）は、Windows 11 の PC の Google Chrome 最新版・Microsoft Edge 最新版で全操作を行えること（NFR-US-01、NFR-US-06）、幅 1280px×高さ 720px 以上の表示領域で横スクロール・表示崩れ（要素の重なり・欠け）が無いこと（NFR-US-02）、JIS X 8341-3:2016 適合レベル A に適合すること（NFR-US-05、NFR-LG-08）、キーボード（Tab・Shift+Tab・Enter・Space・矢印キー）だけで全操作を行えること（NFR-US-07）を満たす。画面の表示完了時間 2.0秒以内（NFR-PF-03）を満たせる画面構成とし、外部 CDN に依存しない（NFR-EN-05）

#### Completion Criteria / Definition of Done

- [ ] UC-008・UC-009 の AC を満たせる
- [ ] Build / ruff / 単体テストが PASS
- [ ] 注文キャンセル（購入者）の実行前に確認を求め、承諾しない場合はデータ変更0件である（NFR-US-09）
- [ ] 注文キャンセルを処理が完了するまでの間に繰り返しても、更新は1回分だけ反映される（NFR-US-10）
- [ ] 本Taskの画面（SCR-009、SCR-010）を Windows 11 の Chrome・Edge 最新版で全操作でき、1280×720 の表示領域で横スクロール・表示崩れが無く、JIS X 8341-3:2016 適合レベル A の達成基準のチェックリストを満たし、キーボードだけで全操作を行える（NFR-US-01、NFR-US-02、NFR-US-05、NFR-US-06、NFR-US-07。互換性・操作性テスト。画面をまたぐ一連の操作は TASK-020）
- [ ] 注文詳細を本人にのみ返し（NFR-SC-24）、キャンセル可否と在庫戻しを画面と Web API で同じ規則で判定する（NFR-LG-06）
- [ ] 不要なScope Expansionがない

#### Validation

| Validation Type | Command / Method | Expected Result |
| --- | --- | --- |
| Build | TASK-001 の起動手順 | PASS |
| Static Check | ruff check | PASS |
| Unit Test | pytest（注文照会・キャンセル） | planned |
| Other | 在庫数量と明細数量の照合（DQ-39） | PASS |
| Other | 互換性・操作性テスト（本Taskの画面 SCR-009、SCR-010：2種のブラウザでの全操作（NFR-US-01、NFR-US-06）、1280×720 表示（NFR-US-02）、適合レベル A のチェックリスト（NFR-US-05）、キーボードだけでの全操作（NFR-US-07）） | PASS |
| Other | 性能テスト（注文履歴一覧・注文詳細照会の応答時間 1.0秒以内：NFR-PF-01、注文キャンセルの応答時間 2.0秒以内：NFR-PF-02、SCR-009・SCR-010 の表示完了時間：NFR-PF-03） | later phase（試験工程。ENV-01 のピーク負荷・3年後データ量で測定） |

#### Progress / Result

| 項目 | 内容 |
| --- | --- |
| Started At | None |
| Completed At | None |
| Result | None |
| Evidence | None |
| Blocked Reason | None |
| Required Route | NONE |

#### Notes

- FR-034（支払済注文のキャンセル）は BOQ-08 の未決の影響対象（UNRESOLVED-32af0f4a0ca9c80f）。暫定扱いにより現行 FR のとおり実装する。

### TASK-017 `試験用状態の設定手段（現在時刻・模擬決済の異常応答）`

#### Metadata

| 項目 | 内容 |
| --- | --- |
| Type | TEST_SUPPORT |
| Priority | HIGH |
| Status | TODO |
| Target Area | 試験支援（ENV-01 限定。本番では設定不可） |
| Depends On | TASK-002、TASK-008 |
| Blocks | TASK-006、TASK-012、TASK-014、TASK-015、TASK-018、TASK-019、TASK-020 |

#### Source References

| Type | ID / Path | Relevant Section / Reason |
| --- | --- | --- |
| Requirement | NFR-OM-06、NFR-OM-17、FR-002、FR-024、FR-031 | NFR-OM-06 (1) 現在時刻の任意設定（秒未満含む。クーポン有効期間・ログイン状態の有効期限の境界）、(2) 模擬決済の遅延・接続不可・応答不正、本番で設定不可。NFR-OM-17（本番環境で無効にする開発用の機能の有効・無効を環境別設定値として扱う） |
| Use Case / AC | UC-002、UC-004、UC-005、UC-006、UC-007、UC-011 の境界・異常系の AC | 有効期限・有効期間の境界、連携エラー、注文日の境界 |
| ADR | None（後続ADDR：試験用状態・試験用DBの方式（候補 test-state-control）、本番での開発用機能の無効化（候補 environment-configuration）を確認） | 方式判断は ADDR |
| Detailed Design | ENT-013、TASK-002 の時刻提供点、TASK-008 の差し替え点 | 再現すべき状態 |

#### Objective

NFR-OM-06 (1)（判定に用いる現在日時の設定）と (2)（模擬決済の応答遅延・接続不可・応答不正）の状態を検証環境で設定・再現でき、本番環境では設定できない手段を、これらを完了条件で使う Task（TASK-006、TASK-012、TASK-014、TASK-015、TASK-018、TASK-019、TASK-020）より前に用意する。(3)（注文確定途中の障害）は注文確定（TASK-014）を前提とするため TASK-019 で扱う。

#### Scope

##### In Scope

- 判定用の現在時刻の設定（秒未満を含む）
- 模擬決済の応答遅延（秒数指定）・接続不可・応答不正（IF-01-EXC-04 の各応答）の各状態
- 本番環境で無効であることの構成上の保証（TASK-001 の環境別設定値一覧に開発用の機能として含める）

##### Out of Scope

- 注文確定途中の障害の状態（NFR-OM-06 (3)。TASK-019）
- 業務機能の振る舞いの変更

#### Expected Change

- 試験用の設定・差し替え手段（方式は ADDR 判断に従う）

#### Constraints

- 本番環境では設定できない（NFR-OM-06、NFR-OM-17、VUL-08）
- 自動テストは外部インターネットに接続しない

#### Completion Criteria / Definition of Done

- [ ] (1)・(2) の各状態を検証環境で再現できる（TASK-002 の時刻提供点、TASK-008 の差し替え点に対して確認）
- [ ] 本番設定で無効であることを構成レビューで確認できる
- [ ] Build / ruff / 単体テストが PASS
- [ ] 不要なScope Expansionがない

#### Validation

| Validation Type | Command / Method | Expected Result |
| --- | --- | --- |
| Build | TASK-001 の起動手順 | PASS |
| Static Check | ruff check | PASS |
| Unit Test | pytest（試験用状態の設定） | planned |
| Other | 構成・設定レビュー（本番で設定不可） | PASS |

#### Progress / Result

| 項目 | 内容 |
| --- | --- |
| Started At | None |
| Completed At | None |
| Result | None |
| Evidence | None |
| Blocked Reason | None |
| Required Route | NONE |

#### Notes

- 実装前に後続ADDRと implementation-handoff を読む。
- 修正cycle 1（QR-ARCH-001）で、注文確定途中の障害（旧 TASK-017 の (3)）を TASK-019 へ分割し、完了条件の依存順を Wave と一致させた。

### TASK-018 `注文一覧検索・注文詳細照会・出荷登録・配達完了登録・注文キャンセル（管理者）`

#### Metadata

| 項目 | 内容 |
| --- | --- |
| Type | IMPLEMENT |
| Priority | HIGH |
| Status | TODO |
| Target Area | 管理（業務処理・Web API・画面 SCR-102、SCR-103） |
| Depends On | TASK-015、TASK-016、TASK-017 |
| Blocks | TASK-020 |

#### Source References

| Type | ID / Path | Relevant Section / Reason |
| --- | --- | --- |
| Requirement | FR-041、FR-042、FR-043、FR-044、FR-045、NFR-SC-06、NFR-US-01、NFR-US-02、NFR-US-05、NFR-US-06、NFR-US-07、NFR-LG-08、NFR-PF-03、NFR-PF-01、NFR-PF-02、NFR-US-09、NFR-US-10、NFR-LG-06、NFR-EN-05、NFR-SC-24 | functional_requirements.md 6.21〜6.25、8.1 ST-PO-03〜ST-PO-06。NFR-SC-06（アクセスログの要求先に検索条件を含めない。検索条件にメールアドレスが含まれるため） |
| Use Case / AC | UC-011（AC-UC-011-001〜AC-UC-011-020）、UC-012（AC-UC-012-001〜AC-UC-012-011） | 注文の確認・出荷・配達完了・キャンセル（UC-011 の注文日の境界（日本時間 23:59:59／00:00:00）の事前条件は TASK-017 の時刻設定で作成。AC-UC-012-011 は購入者の支払（FR-031、TASK-015）と同時実行するため TASK-015 を Depends On に宣言） |
| ADR | None（後続ADDR：同時実行制御（候補 concurrency-transaction）、Web API 契約（候補 api-contract）を確認） | 方式判断は ADDR |
| Detailed Design | ENT-001、ENT-010〜ENT-014（LDC-ENT-010-003〜LDC-ENT-010-005、LDR-008、LDR-010、13章） | 状態と日時・配送伝票番号、購入者情報・決済記録の参照 |

#### Objective

管理者に全注文の検索・詳細（購入者情報・決済記録・状態履歴を含む）を返し、支払済の出荷登録、出荷済の配達完了登録、注文受付・支払済のキャンセル（在庫戻しは TASK-016 の共通処理）を行う。

#### Scope

##### In Scope

- FR-041〜FR-045 の処理・例外、注文日の JST 日付範囲、メールアドレス部分一致、20件ページング
- 状態遷移の競合時の状態不正

##### Out of Scope

- 配送業者連携・部分出荷（FR-OUT-04、FR-OUT-07）、帳票・CSV 出力（FR-OUT-15）

#### Expected Change

- 管理者向け注文の業務処理、Web API、SCR-102・SCR-103

#### Constraints

- 購入者の要求は権限エラー（CMN-03）
- 注文一覧検索の検索条件（メールアドレスの部分一致を含む）をアクセスログ・アプリケーションログの要求先に含めない（NFR-SC-06。共通のログ処理は TASK-002）
- 本Taskの画面（SCR-102、SCR-103）は、Windows 11 の PC の Google Chrome 最新版・Microsoft Edge 最新版で全操作を行えること（NFR-US-01、NFR-US-06）、幅 1280px×高さ 720px 以上の表示領域で横スクロール・表示崩れ（要素の重なり・欠け）が無いこと（NFR-US-02）、JIS X 8341-3:2016 適合レベル A に適合すること（NFR-US-05、NFR-LG-08）、キーボード（Tab・Shift+Tab・Enter・Space・矢印キー）だけで全操作を行えること（NFR-US-07）を満たす。画面の表示完了時間 2.0秒以内（NFR-PF-03）を満たせる画面構成とし、外部 CDN に依存しない（NFR-EN-05）

#### Completion Criteria / Definition of Done

- [ ] UC-011・UC-012 の AC を満たせる（AC-UC-012-011 の支払は TASK-015、在庫戻しは TASK-016、注文日の境界は TASK-017 を用いる。いずれも Depends On に宣言済み）
- [ ] メールアドレスを検索条件とした注文一覧検索の実行後、全ログに当該メールアドレスの値が含まれない（NFR-SC-06）
- [ ] Build / ruff / 単体テストが PASS
- [ ] 出荷登録・配達完了登録・注文キャンセル（管理者）の実行前に確認を求め、承諾しない場合はデータ変更0件である（NFR-US-09）
- [ ] 出荷登録・配達完了登録・注文キャンセルを処理が完了するまでの間に繰り返しても、更新は1回分だけ反映される（NFR-US-10）
- [ ] 本Taskの画面（SCR-102、SCR-103）を Windows 11 の Chrome・Edge 最新版で全操作でき、1280×720 の表示領域で横スクロール・表示崩れが無く、JIS X 8341-3:2016 適合レベル A の達成基準のチェックリストを満たし、キーボードだけで全操作を行える（NFR-US-01、NFR-US-02、NFR-US-05、NFR-US-06、NFR-US-07。互換性・操作性テスト。画面をまたぐ一連の操作は TASK-020）
- [ ] 注文・配送先の個人情報を管理者にのみ返し（NFR-SC-24）、状態遷移の順序を画面と Web API で同じ規則で判定する（NFR-LG-06）
- [ ] 不要なScope Expansionがない

#### Validation

| Validation Type | Command / Method | Expected Result |
| --- | --- | --- |
| Build | TASK-001 の起動手順 | PASS |
| Static Check | ruff check | PASS |
| Unit Test | pytest（管理者注文） | planned |
| Other | 状態ごとの日時整合の照合（DQ-30） | PASS |
| Other | 互換性・操作性テスト（本Taskの画面 SCR-102、SCR-103：2種のブラウザでの全操作（NFR-US-01、NFR-US-06）、1280×720 表示（NFR-US-02）、適合レベル A のチェックリスト（NFR-US-05）、キーボードだけでの全操作（NFR-US-07）） | PASS |
| Other | 性能テスト（注文一覧検索・注文詳細照会の応答時間 1.0秒以内：NFR-PF-01、出荷登録・配達完了登録・注文キャンセルの応答時間 2.0秒以内：NFR-PF-02、SCR-102・SCR-103 の表示完了時間：NFR-PF-03） | later phase（試験工程。ENV-01 のピーク負荷・3年後データ量で測定） |

#### Progress / Result

| 項目 | 内容 |
| --- | --- |
| Started At | None |
| Completed At | None |
| Result | None |
| Evidence | None |
| Blocked Reason | None |
| Required Route | NONE |

#### Notes

- FR-043（模擬決済で支払済となった注文の出荷）・FR-045 は BOQ-08 の未決の影響対象（UNRESOLVED-32af0f4a0ca9c80f）。暫定扱いにより現行 FR のとおり実装し、本番のみの出荷停止等を追加しない。

### TASK-019 `注文確定途中の障害の設定手段と途中障害時の無変更の検証`

#### Metadata

| 項目 | 内容 |
| --- | --- |
| Type | TEST_SUPPORT |
| Priority | HIGH |
| Status | TODO |
| Target Area | 試験支援（ENV-01 限定。本番では設定不可）・注文確定の結合テスト |
| Depends On | TASK-014、TASK-017 |
| Blocks | TASK-021 |

#### Source References

| Type | ID / Path | Relevant Section / Reason |
| --- | --- | --- |
| Requirement | NFR-OM-06、FR-030、NFR-SC-10、NFR-OM-17 | NFR-OM-06 (3) 注文確定の処理の途中（在庫数量の減算・注文の作成の一部が行われた後）でデータを更新できない障害が発生する状態、本番で設定不可。FR-030（全件成功か無変更）、NFR-SC-10（システムエラーの内部詳細を通知しない） |
| Use Case / AC | UC-006（AC-UC-006-022。EX-09、BR-UC-006-013 に対応する AC） | 注文確定途中の障害で処理前の状態から変化しない |
| ADR | None（後続ADDR：試験用状態の方式（候補 test-state-control）、トランザクション境界（候補 concurrency-transaction）、本番での開発用機能の無効化（候補 environment-configuration）を確認） | 方式判断は ADDR |
| Detailed Design | ENT-006、ENT-008、ENT-010、ENT-011、ENT-012、ENT-014（LDR-004、LDR-011）、TASK-014 の注文確定処理、TASK-017 の設定手段 | 再現すべき状態と処理前と一致すべきデータ |

#### Objective

NFR-OM-06 (3) の状態を検証環境で設定・再現でき本番環境では設定できない手段を用意し、TASK-014 の注文確定が途中障害時に在庫数量・注文・注文明細・配送先・注文状態履歴・カートを処理前のまま保つこと（LDR-011、BR-UC-006-013）を検証する。

#### Scope

##### In Scope

- 注文確定の処理途中のデータ更新障害の状態の設定（ENV-01 限定）
- 途中障害時の全件無変更とシステムエラー通知（内部詳細なし）の結合テスト
- 本番環境で無効であることの構成上の保証（TASK-001 の環境別設定値一覧に開発用の機能として含める）

##### Out of Scope

- 注文確定の業務処理の変更（TASK-014）
- 現在時刻・模擬決済の試験用状態（TASK-017）

#### Expected Change

- 試験用の障害注入手段（方式は ADDR 判断に従う）と注文確定の結合テスト

#### Constraints

- 本番環境では設定できない（NFR-OM-06、NFR-OM-17、VUL-08）
- 自動テストは外部インターネットに接続しない

#### Completion Criteria / Definition of Done

- [ ] NFR-OM-06 (3) の状態を検証環境で再現できる
- [ ] 途中障害時に在庫数量・注文・注文明細・配送先・注文状態履歴・カートが処理前と一致し、通知に内部詳細を含まない（AC-UC-006-022）
- [ ] 本番設定で無効であることを構成レビューで確認できる
- [ ] Build / ruff / 単体テストが PASS
- [ ] 途中障害時の画面・Web API の応答にスタックトレース・SQL 文等の内部情報を含めない（NFR-SC-10）
- [ ] 不要なScope Expansionがない

#### Validation

| Validation Type | Command / Method | Expected Result |
| --- | --- | --- |
| Build | TASK-001 の起動手順 | PASS |
| Static Check | ruff check | PASS |
| Unit Test | pytest（注文確定途中の障害の結合テスト） | planned |
| Other | 構成・設定レビュー（本番で設定不可） | PASS |

#### Progress / Result

| 項目 | 内容 |
| --- | --- |
| Started At | None |
| Completed At | None |
| Result | None |
| Evidence | None |
| Blocked Reason | None |
| Required Route | NONE |

#### Notes

- 修正cycle 1（QR-ARCH-001）で旧 TASK-017 の (3) と旧 TASK-014 の途中障害の完了条件を本Taskへ移し、TASK-014 ⇄ TASK-017 の完了条件上の循環を解消した。
- 実装前に後続ADDRと implementation-handoff を読む。

### TASK-020 `機能横断の受入条件の結合確認（画面遷移・権限判定・機能間の反映）`

#### Metadata

| 項目 | 内容 |
| --- | --- |
| Type | TEST_SUPPORT |
| Priority | HIGH |
| Status | TODO |
| Target Area | 結合テスト（複数の機能 Task の画面・機能を横断する UC の AC。app/ 配下の tests/integration） |
| Depends On | TASK-006、TASK-007、TASK-010、TASK-011、TASK-012、TASK-014、TASK-015、TASK-016、TASK-017、TASK-018 |
| Blocks | TASK-021 |

#### Source References

| Type | ID / Path | Relevant Section / Reason |
| --- | --- | --- |
| Requirement | FR-001、FR-002、FR-003、FR-010、FR-011、FR-012、FR-020、FR-021、FR-026、FR-030、FR-033、FR-034、FR-040、FR-041、FR-060、NFR-SC-03、NFR-SC-09、NFR-OM-11、NFR-OM-18、NFR-US-01、NFR-US-06、NFR-US-07、NFR-US-08、NFR-SC-25 | 各 AC の関連 Requirement（画面遷移、ログイン後の遷移先、利用者区分による権限判定、無操作30分、機能間のデータ反映、初期データ一括投入の結果の反映） |
| Use Case / AC | AC-UC-001-002、AC-UC-002-003、AC-UC-002-009、AC-UC-002-014、AC-UC-002-015、AC-UC-002-016、AC-UC-002-018、AC-UC-003-017、AC-UC-003-018、AC-UC-003-021、AC-UC-006-005、AC-UC-006-006、AC-UC-010-008、AC-UC-013-002、AC-UC-013-003、AC-UC-013-011 | 各 UC の機能 Task だけでは成立しない AC（機能 Task の完了条件から除外したもの。3章の規則） |
| ADR | None（後続ADDR：Web API 契約（候補 api-contract）、ログイン状態・セッション（候補 authentication-session）、試験用状態（候補 test-state-control）、初期データ一括投入の起動手段（候補 initial-data-invocation）を確認。ログ方式（候補 application-logging）も確認） | 方式判断は ADDR |
| Detailed Design | ui_report_requirements.md（SCR-001〜SCR-010、SCR-101〜SCR-103、SCR-901 の画面遷移）、FILE-001、TASK-006・TASK-007・TASK-010〜TASK-012・TASK-014〜TASK-018 の成果 | 結合する画面・機能 |

#### Objective

複数の機能 Task の画面・機能を組み合わせて初めて成立する UC の AC（画面遷移、ログイン後の遷移先、利用者区分による権限判定、機能間のデータの反映、初期データ一括投入の結果の各画面への反映）を、関連するすべての機能 Task の完了後に結合テストで確認する。

#### Scope

##### In Scope

- 会員登録・ログイン・ログアウトと他画面の遷移（AC-UC-001-002、AC-UC-002-003、AC-UC-002-015、AC-UC-002-016、AC-UC-002-018）
- ログアウト後・利用者区分による他機能の要求の拒否（AC-UC-002-009、AC-UC-002-014。他機能の要求先に対して画面を経由せず送る権限外要求の試験：NFR-SC-03）
- 利用者区分ごとの商品閲覧とカートに入れる操作（AC-UC-003-017、AC-UC-003-018、AC-UC-003-021）
- 注文確定後の注文詳細、注文確定・キャンセル後の在庫単位一覧への反映（AC-UC-006-005、AC-UC-006-006、AC-UC-010-008）
- 初期データ一括投入の結果の画面・一覧への反映と、画面・Web API から投入できないこと（AC-UC-013-002、AC-UC-013-003、AC-UC-013-011）
- ENV-01 で全機能を1回以上実行し、LOG-01〜LOG-07 が 6.3 に定めた内容で出力・記録されることの運用テスト（NFR-OM-11）
- 支払要求1件に関するログを、要求の識別子で LOG-01〜LOG-03・LOG-06 から横断して抽出する運用テスト（NFR-OM-18）
- 画面をまたぐ一連の操作（会員登録から支払まで、管理者のログインから出荷登録まで）の2種のブラウザ・キーボードだけでの操作と、購入の画面数の確認（NFR-US-01、NFR-US-06、NFR-US-07、NFR-US-08）

##### Out of Scope

- 各機能の業務処理・画面の実装・変更（各機能 Task。結合テストで検出した不備は当該 Task の修正として扱う）
- 性能・負荷・脆弱性診断の試験（試験工程）

#### Expected Change

- 結合テスト（app/ 配下の tests/integration）。業務コードの追加・変更は含めない

#### Constraints

- 試験データは架空の値のみ（NFR-SC-25、Steering 7章）
- 自動テストは外部インターネットに接続しない。試験用状態（現在時刻等）は ENV-01 限定の手段（TASK-017）を用いる

#### Completion Criteria / Definition of Done

- [ ] 次の AC を満たせる：AC-UC-001-002、AC-UC-002-003、AC-UC-002-009、AC-UC-002-014、AC-UC-002-015、AC-UC-002-016、AC-UC-002-018、AC-UC-003-017、AC-UC-003-018、AC-UC-003-021、AC-UC-006-005、AC-UC-006-006、AC-UC-010-008、AC-UC-013-002、AC-UC-013-003、AC-UC-013-011（各 AC が用いる機能 Task はすべて Depends On に宣言済み）
- [ ] Build / ruff / 結合テストが PASS
- [ ] ENV-01 で全機能を1回以上実行し、LOG-01〜LOG-07 が 6.3 に定めた内容で出力・記録される（NFR-OM-11。運用テスト。保管期間は運用時に測定）
- [ ] 注文受付の状態の注文1件に支払要求を行い、その要求の識別子で LOG-01〜LOG-03・LOG-06 から当該要求のログを漏れなく抽出できる（NFR-OM-18。運用テスト）
- [ ] Windows 11 の Chrome・Edge 最新版で、キーボードだけで会員登録から支払まで、管理者のログインから出荷登録までを操作できる（NFR-US-01、NFR-US-06、NFR-US-07。互換性・操作性テスト）
- [ ] ログイン済みの購入者が商品一覧から支払を完了するまでの画面数が7画面以内（SCR-001→SCR-002→SCR-005→SCR-006→SCR-007→SCR-008→SCR-010）である（NFR-US-08）
- [ ] 無操作30分経過後の操作がログイン画面へ遷移すること（NFR-SC-09）を上記 AC で確認する
- [ ] 不要なScope Expansionがない

#### Validation

| Validation Type | Command / Method | Expected Result |
| --- | --- | --- |
| Build | TASK-001 の起動手順 | PASS |
| Static Check | ruff check | PASS |
| Unit Test | pytest（結合テスト） | planned |
| Other | AC 単位の Task 依存の照合（3章の規則。各 AC の Given の前提操作・When・Then が用いる FR・画面の実装 Task が Depends On に含まれること） | 違反0件 |
| Other | 運用テスト（LOG-01〜LOG-07 の出力：NFR-OM-11、要求の識別子による LOG-01〜LOG-03・LOG-06 の横断抽出：NFR-OM-18）、互換性・操作性テスト（一連の操作：NFR-US-01、NFR-US-06、NFR-US-07、画面数：NFR-US-08） | PASS / 抽出漏れ0件 / 7画面以内 |

#### Progress / Result

| 項目 | 内容 |
| --- | --- |
| Started At | None |
| Completed At | None |
| Result | None |
| Evidence | None |
| Blocked Reason | None |
| Required Route | NONE |

#### Notes

- 修正cycle 2（QR-ARCH-R1-002）で新設。機能 Task の完了条件が後続・同一 Wave の Task の機能を要していた AC を本Taskへ移し、全 Task の完了条件を依存先 Task だけで成立させた。
- 実装前に後続ADDRと implementation-handoff を読む。

### TASK-021 `依存ライブラリ・実行環境の取得元・版の確認と既知脆弱性の確認（リリース前）`

#### Metadata

| 項目 | 内容 |
| --- | --- |
| Type | OTHER |
| Priority | HIGH |
| Status | TODO |
| Target Area | 依存ライブラリ・実行環境の構成（リポジトリ全体） |
| Depends On | TASK-013、TASK-019、TASK-020 |
| Blocks | None |

#### Source References

| Type | ID / Path | Relevant Section / Reason |
| --- | --- | --- |
| Requirement | NFR-SC-11、NFR-SC-21（VUL-09、VUL-10）、NFR-EN-10、NFR-EN-12、NFR-LG-07 | NFR-SC-11（全依存ライブラリに既知の重大な脆弱性（CVSS 7.0以上）0件。リリース前に公開されている脆弱性情報と照合）、VUL-09（サポート期限内の版、リリース時点で CVSS 7.0以上 0件）、VUL-10（依存ライブラリ・実行環境の取得元と版が特定でき同じ構成を再現できる）、NFR-EN-10（採用製品をサポート期限内の版で運用）、NCN-07（照合ツールは試験計画で選定） |
| Use Case / AC | None（非機能要件の確認。UC の AC なし） | — |
| ADR | None（後続ADDR：依存ライブラリ・実行環境の取得元・版の固定と記録の方式（候補 environment-configuration）を確認） | 方式判断は ADDR |
| Detailed Design | TASK-001 で作成した依存ライブラリ・実行環境の取得元と版の記録 | 照合・再現の対象 |

#### Objective

全 Task の完了後（依存ライブラリが確定した時点）に、依存ライブラリ・実行環境の取得元と版が記録されて同じ構成を再現できること、採用製品がサポート期限内の版であること、全依存ライブラリに既知の重大な脆弱性（CVSS 7.0以上）が無いことを確認し、結果を記録する。

#### Scope

##### In Scope

- TASK-001〜TASK-020 で追加された依存を含む全依存ライブラリ・実行環境の取得元と版の記録の確認（VUL-10）と、記録からの再構築による再現確認
- 採用製品の版とサポート期限の確認（NFR-EN-10）
- 全依存ライブラリと公開されている脆弱性情報の照合（NFR-SC-11、VUL-09）。CVSS 7.0以上が検出された場合は修正済みの版への更新と影響する Task の自動テストの再実行を行い、解消できない場合は Blocked Reason に記録して親へ返す
- 全依存ライブラリのライセンスの確認（社外へ配布しないサーバー上での利用で利用条件を満たせるライセンスに限る。AGPL・ライセンス不明 0件：NFR-EN-12）

##### Out of Scope

- 脆弱性診断（NFR-SC-29。試験工程）
- 稼働後のセキュリティパッチの適用（NFR-OM-14。運用手順書での運用事項）
- 照合に用いるツールの選定（試験計画：NCN-07）

#### Expected Change

- 依存ライブラリ・実行環境の取得元と版の記録（TASK-001 で作成）の更新と、照合日・照合対象の版・結果の記録

#### Constraints

- 実行時に外部インターネットへ接続しない（依存パッケージ・コンテナイメージの取得時のみ例外：Steering 4章、NFR-EN-05）
- 照合に用いるツールは試験計画で選定されたものを用いる（NCN-07）

#### Completion Criteria / Definition of Done

- [ ] 全依存ライブラリ・実行環境の取得元と版が記録され、記録から同じ版の構成を再現（再構築）できる（VUL-10）
- [ ] 採用製品がサポート期限内の版である（NFR-EN-10、VUL-09）
- [ ] 全依存ライブラリについて既知の重大な脆弱性（CVSS 7.0以上）が0件であり、照合日・照合対象の版・結果が記録されている（NFR-SC-11、VUL-09）
- [ ] 再構築した構成で全自動テストが PASS する
- [ ] 全依存ライブラリのライセンスが記録され、AGPL のライブラリ・ライセンスが不明なライブラリが0件である（NFR-EN-12。静的解析・コードレビュー）
- [ ] 8.2 の対策方針のうち VUL-09・VUL-10（NFR-SC-21、NFR-LG-07）を満たすことを上記の確認結果で示す
- [ ] 不要なScope Expansionがない

#### Validation

| Validation Type | Command / Method | Expected Result |
| --- | --- | --- |
| Build | 依存ライブラリ・実行環境の記録からの再構築（TASK-001 の起動手順） | PASS |
| Static Check | ruff check | PASS |
| Unit Test | pytest（再構築した構成で全自動テスト） | PASS |
| Other | 全依存ライブラリと公開されている脆弱性情報の照合（NFR-SC-11）、版・サポート期限・取得元の構成・設定レビュー（VUL-10、NFR-EN-10） | CVSS 7.0以上 0件 / PASS |
| Other | 全依存ライブラリのライセンスの一覧の確認（NFR-EN-12） | AGPL・ライセンス不明 0件 |

#### Progress / Result

| 項目 | 内容 |
| --- | --- |
| Started At | None |
| Completed At | None |
| Result | None |
| Evidence | None |
| Blocked Reason | None |
| Required Route | NONE |

#### Notes

- 修正cycle 2（SR-ARCH-R1-002）で新設。TASK-001 は導入時点の版の固定・記録と照合を、本Taskは全 Task 完了後（リリース前）の最終確認を担う。
- 照合に用いるツールが試験計画で未選定の場合は着手前に親へ返す（NCN-07）。
- 実装前に後続ADDRと implementation-handoff を読む。

## 7. Coverage / Scope Check

| Source ID | Source Type | Required Implementation | Related Task IDs | Planning Status |
| --- | --- | --- | --- | --- |
| FR-001 | REQUIREMENT | YES | TASK-003、TASK-006 | COVERED |
| FR-002 | REQUIREMENT | YES | TASK-003、TASK-006 | COVERED |
| FR-003 | REQUIREMENT | YES | TASK-003、TASK-006 | COVERED |
| FR-004 | REQUIREMENT | YES | TASK-006 | COVERED |
| FR-010 | REQUIREMENT | YES | TASK-004、TASK-007 | COVERED |
| FR-011 | REQUIREMENT | YES | TASK-004、TASK-007 | COVERED |
| FR-012 | REQUIREMENT | YES | TASK-004、TASK-007 | COVERED |
| FR-020 | REQUIREMENT | YES | TASK-005、TASK-012 | COVERED |
| FR-021 | REQUIREMENT | YES | TASK-012 | COVERED |
| FR-022 | REQUIREMENT | YES | TASK-012 | COVERED |
| FR-023 | REQUIREMENT | YES | TASK-012 | COVERED |
| FR-024 | REQUIREMENT | YES | TASK-009、TASK-012 | COVERED |
| FR-025 | REQUIREMENT | YES | TASK-012 | COVERED |
| FR-026 | REQUIREMENT | YES | TASK-009 | COVERED |
| FR-030 | REQUIREMENT | YES | TASK-005、TASK-014 | COVERED |
| FR-031 | REQUIREMENT | YES | TASK-008、TASK-015 | COVERED |
| FR-032 | REQUIREMENT | YES | TASK-016 | COVERED |
| FR-033 | REQUIREMENT | YES | TASK-016 | COVERED |
| FR-034 | REQUIREMENT | YES | TASK-016 | COVERED |
| FR-040 | REQUIREMENT | YES | TASK-010 | COVERED |
| FR-041 | REQUIREMENT | YES | TASK-018 | COVERED |
| FR-042 | REQUIREMENT | YES | TASK-018 | COVERED |
| FR-043 | REQUIREMENT | YES | TASK-018 | COVERED |
| FR-044 | REQUIREMENT | YES | TASK-018 | COVERED |
| FR-045 | REQUIREMENT | YES | TASK-016、TASK-018 | COVERED |
| FR-060 | REQUIREMENT | YES | TASK-006、TASK-011、TASK-013 | COVERED |
| IFR-001 | REQUIREMENT | YES | TASK-008、TASK-015 | COVERED |
| NFR-AV-01 | REQUIREMENT | NO | None（本番環境の運用・本番基盤（NOQ-01）で満たし運用時に測定する事項。実装 Task はサービス停止を要する定期処理を追加しない） | N/A |
| NFR-AV-02 | REQUIREMENT | NO | None（本番環境の運用・本番基盤（NOQ-01）で満たし運用時に測定する事項。実装 Task はサービス停止を要する定期処理を追加しない） | N/A |
| NFR-AV-03 | REQUIREMENT | NO | None（本番環境の運用・本番基盤（NOQ-01）で満たし運用時に測定する事項。実装 Task はサービス停止を要する定期処理を追加しない） | N/A |
| NFR-AV-04 | REQUIREMENT | NO | None（バックアップの取得・リストアは本番基盤（NOQ-01）と本番運用手順書（NFR-OM-19 後段）の対象） | N/A |
| NFR-AV-05 | REQUIREMENT | NO | None（本番環境の運用・本番基盤（NOQ-01）で満たし運用時に測定する事項。実装 Task はサービス停止を要する定期処理を追加しない） | N/A |
| NFR-AV-07 | REQUIREMENT | NO | None（本番環境の運用・本番基盤（NOQ-01）で満たし運用時に測定する事項。実装 Task はサービス停止を要する定期処理を追加しない） | N/A |
| NFR-AV-08 | REQUIREMENT | NO | None（本番環境の運用・本番基盤（NOQ-01）で満たし運用時に測定する事項。実装 Task はサービス停止を要する定期処理を追加しない） | N/A |
| NFR-AV-09 | REQUIREMENT | NO | None（要否：否（要件で対応しない）） | N/A |
| NFR-AV-10 | REQUIREMENT | NO | None（要件で「該当なし」） | N/A |
| NFR-AV-11 | REQUIREMENT | NO | None（本番環境の運用・本番基盤（NOQ-01）で満たし運用時に測定する事項。実装 Task はサービス停止を要する定期処理を追加しない） | N/A |
| NFR-AV-12 | REQUIREMENT | NO | None（バックアップの取得・リストアは本番基盤（NOQ-01）と本番運用手順書（NFR-OM-19 後段）の対象） | N/A |
| NFR-PF-01 | REQUIREMENT | YES | TASK-007、TASK-010、TASK-012、TASK-016、TASK-018 | COVERED |
| NFR-PF-02 | REQUIREMENT | YES | TASK-012、TASK-014、TASK-015、TASK-016、TASK-018 | COVERED |
| NFR-PF-03 | REQUIREMENT | YES | TASK-002、TASK-006、TASK-007、TASK-010、TASK-012、TASK-014、TASK-015、TASK-016、TASK-018 | COVERED |
| NFR-PF-04 | REQUIREMENT | YES | TASK-014 | COVERED |
| NFR-PF-05 | REQUIREMENT | NO | None（試験工程の性能・負荷・耐久テストの条件（同時155利用者、3年後データ量、2時間連続負荷）。実装の目標値は NFR-PF-01〜NFR-PF-04・NFR-PF-09 として各 Task に割当て（測定は later phase）。データ量は論理DB設計の保持・データ量と物理設計への引継ぎに記載） | N/A |
| NFR-PF-06 | REQUIREMENT | NO | None（試験工程の性能・負荷・耐久テストの条件（同時155利用者、3年後データ量、2時間連続負荷）。実装の目標値は NFR-PF-01〜NFR-PF-04・NFR-PF-09 として各 Task に割当て（測定は later phase）。データ量は論理DB設計の保持・データ量と物理設計への引継ぎに記載） | N/A |
| NFR-PF-07 | REQUIREMENT | YES | TASK-014 | COVERED |
| NFR-PF-08 | REQUIREMENT | YES | TASK-002、TASK-007、TASK-010 | COVERED |
| NFR-PF-09 | REQUIREMENT | YES | TASK-006 | COVERED |
| NFR-PF-10 | REQUIREMENT | YES | TASK-011 | COVERED |
| NFR-PF-11 | REQUIREMENT | YES | TASK-009、TASK-014 | COVERED |
| NFR-PF-12 | REQUIREMENT | NO | None（要件で「該当なし」） | N/A |
| NFR-PF-13 | REQUIREMENT | NO | None（定期ジョブはバックアップのみ（本番基盤・運用：NOQ-01）。実装 Task は定期ジョブを追加しない） | N/A |
| NFR-PF-14 | REQUIREMENT | NO | None（リソース使用率は運用時に測定（MON-02）。ENV-01 の値は試験工程の性能テストで参考記録） | N/A |
| NFR-PF-15 | REQUIREMENT | NO | None（試験工程の性能・負荷・耐久テストの条件（同時155利用者、3年後データ量、2時間連続負荷）。実装の目標値は NFR-PF-01〜NFR-PF-04・NFR-PF-09 として各 Task に割当て（測定は later phase）。データ量は論理DB設計の保持・データ量と物理設計への引継ぎに記載） | N/A |
| NFR-PF-16 | REQUIREMENT | YES | TASK-001、TASK-006、TASK-012 | COVERED |
| NFR-PF-17 | REQUIREMENT | YES | TASK-008、TASK-015 | COVERED |
| NFR-OM-01 | REQUIREMENT | YES | TASK-002 | COVERED |
| NFR-OM-02 | REQUIREMENT | YES | TASK-002 | COVERED |
| NFR-OM-03 | REQUIREMENT | YES | TASK-003 | COVERED |
| NFR-OM-04 | REQUIREMENT | YES | TASK-011、TASK-013 | COVERED |
| NFR-OM-05 | REQUIREMENT | YES | TASK-001 | COVERED |
| NFR-OM-06 | REQUIREMENT | YES | TASK-001、TASK-017、TASK-019 | COVERED |
| NFR-OM-08 | REQUIREMENT | NO | None（運用体制・問い合わせ対応（本システム外の運用事項。NOQ-03）） | N/A |
| NFR-OM-09 | REQUIREMENT | NO | None（本番環境の監視・通知（NOQ-02。ENV-01 は監視対象外）。監視の入力となるログは NFR-OM-11 で割当て） | N/A |
| NFR-OM-10 | REQUIREMENT | NO | None（本番環境の監視・通知（NOQ-02。ENV-01 は監視対象外）。監視の入力となるログは NFR-OM-11 で割当て） | N/A |
| NFR-OM-11 | REQUIREMENT | YES | TASK-002、TASK-005、TASK-006、TASK-008、TASK-011、TASK-020 | COVERED |
| NFR-OM-13 | REQUIREMENT | YES | TASK-011 | COVERED |
| NFR-OM-14 | REQUIREMENT | NO | None（稼働後のセキュリティパッチ適用は運用事項（TASK-001・TASK-021 の Out of Scope、ARCH-CI-021）） | N/A |
| NFR-OM-15 | REQUIREMENT | NO | None（本番のリリース作業・切戻しは本番運用手順書（NFR-OM-19 後段、本番基盤の選定後）と運用テスト（試験工程）の対象。データ構造の変更は TASK-003〜TASK-005 のマイグレーションで適用） | N/A |
| NFR-OM-16 | REQUIREMENT | NO | None（運用体制・問い合わせ対応（本システム外の運用事項。NOQ-03）） | N/A |
| NFR-OM-17 | REQUIREMENT | YES | TASK-001、TASK-017、TASK-019 | COVERED |
| NFR-OM-18 | REQUIREMENT | YES | TASK-002、TASK-008、TASK-020 | COVERED |
| NFR-OM-19 | REQUIREMENT | YES | TASK-001、TASK-011 | COVERED |
| NFR-MG-01 | REQUIREMENT | NO | None（移行作業での投入データの確認。FILE-001 は注文・注文明細・配送先・決済記録・注文状態履歴・カートを投入対象に持たない（FILE-001 7章）） | N/A |
| NFR-MG-02 | REQUIREMENT | NO | None（移行計画・移行リハーサル（移行工程）。投入機能は TASK-011、架空データは TASK-013） | N/A |
| NFR-MG-03 | REQUIREMENT | YES | TASK-011 | COVERED |
| NFR-MG-04 | REQUIREMENT | YES | TASK-011 | COVERED |
| NFR-MG-05 | REQUIREMENT | NO | None（移行計画・移行リハーサル（移行工程）。投入機能は TASK-011、架空データは TASK-013） | N/A |
| NFR-MG-06 | REQUIREMENT | NO | None（要件で「該当なし」） | N/A |
| NFR-MG-07 | REQUIREMENT | YES | TASK-011 | COVERED |
| NFR-MG-08 | REQUIREMENT | NO | None（移行計画・移行リハーサル（移行工程）。投入機能は TASK-011、架空データは TASK-013） | N/A |
| NFR-SC-01 | REQUIREMENT | YES | TASK-003、TASK-006 | COVERED |
| NFR-SC-02 | REQUIREMENT | YES | TASK-001 | COVERED |
| NFR-SC-03 | REQUIREMENT | YES | TASK-006、TASK-020 | COVERED |
| NFR-SC-04 | REQUIREMENT | YES | TASK-002 | COVERED |
| NFR-SC-05 | REQUIREMENT | YES | TASK-002 | COVERED |
| NFR-SC-06 | REQUIREMENT | YES | TASK-002、TASK-008、TASK-018 | COVERED |
| NFR-SC-07 | REQUIREMENT | YES | TASK-001 | COVERED |
| NFR-SC-08 | REQUIREMENT | YES | TASK-006、TASK-011 | COVERED |
| NFR-SC-09 | REQUIREMENT | YES | TASK-006、TASK-020 | COVERED |
| NFR-SC-10 | REQUIREMENT | YES | TASK-001、TASK-002、TASK-019 | COVERED |
| NFR-SC-11 | REQUIREMENT | YES | TASK-001、TASK-021 | COVERED |
| NFR-SC-12 | REQUIREMENT | YES | TASK-006 | COVERED |
| NFR-SC-13 | REQUIREMENT | NO | None（要件で「該当なし」） | N/A |
| NFR-SC-14 | REQUIREMENT | NO | None（要件で「該当なし」） | N/A |
| NFR-SC-15 | REQUIREMENT | YES | TASK-006、TASK-011 | COVERED |
| NFR-SC-16 | REQUIREMENT | YES | TASK-006 | COVERED |
| NFR-SC-17 | REQUIREMENT | NO | None（要件で「該当なし」） | N/A |
| NFR-SC-18 | REQUIREMENT | YES | TASK-006 | COVERED |
| NFR-SC-19 | REQUIREMENT | YES | TASK-001、TASK-006 | COVERED |
| NFR-SC-20 | REQUIREMENT | NO | None（本番環境の保存媒体・バックアップの暗号化は本番基盤（NOQ-01）の対象） | N/A |
| NFR-SC-21 | REQUIREMENT | YES | TASK-001、TASK-008、TASK-021（VUL-08〜VUL-10。VUL-01〜VUL-07・VUL-11〜VUL-13 は参照先の NFR-SC の割当て Task、VUL-12 は TASK-008） | COVERED |
| NFR-SC-22 | REQUIREMENT | YES | TASK-006、TASK-011 | COVERED |
| NFR-SC-23 | REQUIREMENT | YES | TASK-003、TASK-005、TASK-011 | COVERED |
| NFR-SC-24 | REQUIREMENT | YES | TASK-006、TASK-008、TASK-016、TASK-018 | COVERED |
| NFR-SC-25 | REQUIREMENT | YES | TASK-013、TASK-020 | COVERED |
| NFR-SC-26 | REQUIREMENT | NO | None（本番環境のネットワーク構成は本番基盤（NOQ-01）の対象） | N/A |
| NFR-SC-27 | REQUIREMENT | NO | None（要件で「該当なし」） | N/A |
| NFR-SC-28 | REQUIREMENT | NO | None（要件で「該当なし」） | N/A |
| NFR-SC-29 | REQUIREMENT | NO | None（脆弱性診断（動的診断）は試験工程（TASK-020・TASK-021 の Out of Scope）） | N/A |
| NFR-US-01 | REQUIREMENT | YES | TASK-002、TASK-006、TASK-007、TASK-010、TASK-012、TASK-014、TASK-015、TASK-016、TASK-018、TASK-020 | COVERED |
| NFR-US-02 | REQUIREMENT | YES | TASK-002、TASK-006、TASK-007、TASK-010、TASK-012、TASK-014、TASK-015、TASK-016、TASK-018 | COVERED |
| NFR-US-03 | REQUIREMENT | YES | TASK-002、TASK-006、TASK-014 | COVERED |
| NFR-US-04 | REQUIREMENT | YES | TASK-002 | COVERED |
| NFR-US-05 | REQUIREMENT | YES | TASK-002、TASK-006、TASK-007、TASK-010、TASK-012、TASK-014、TASK-015、TASK-016、TASK-018 | COVERED |
| NFR-US-06 | REQUIREMENT | YES | TASK-002、TASK-006、TASK-007、TASK-010、TASK-012、TASK-014、TASK-015、TASK-016、TASK-018、TASK-020 | COVERED |
| NFR-US-07 | REQUIREMENT | YES | TASK-002、TASK-006、TASK-007、TASK-010、TASK-012、TASK-014、TASK-015、TASK-016、TASK-018、TASK-020 | COVERED |
| NFR-US-08 | REQUIREMENT | YES | TASK-020 | COVERED |
| NFR-US-09 | REQUIREMENT | YES | TASK-012、TASK-014、TASK-016、TASK-018 | COVERED |
| NFR-US-10 | REQUIREMENT | YES | TASK-006、TASK-012、TASK-014、TASK-015、TASK-016、TASK-018 | COVERED |
| NFR-EN-01 | REQUIREMENT | YES | TASK-001 | COVERED |
| NFR-EN-02 | REQUIREMENT | YES | TASK-001 | COVERED |
| NFR-EN-03 | REQUIREMENT | YES | TASK-001 | COVERED |
| NFR-EN-04 | REQUIREMENT | YES | TASK-001、TASK-002、TASK-011 | COVERED |
| NFR-EN-05 | REQUIREMENT | YES | TASK-001、TASK-002、TASK-006、TASK-007、TASK-008、TASK-010、TASK-012、TASK-014、TASK-015、TASK-016、TASK-018 | COVERED |
| NFR-EN-06 | REQUIREMENT | NO | None（本番環境の設置場所は本番基盤（NOQ-01）の対象） | N/A |
| NFR-EN-07 | REQUIREMENT | YES | TASK-001 | COVERED |
| NFR-EN-08 | REQUIREMENT | YES | TASK-001 | COVERED |
| NFR-EN-09 | REQUIREMENT | YES | TASK-001 | COVERED |
| NFR-EN-10 | REQUIREMENT | YES | TASK-001、TASK-021 | COVERED |
| NFR-EN-11 | REQUIREMENT | YES | TASK-001 | COVERED |
| NFR-EN-12 | REQUIREMENT | YES | TASK-001、TASK-021 | COVERED |
| NFR-EN-13 | REQUIREMENT | NO | None（要件で「該当なし」） | N/A |
| NFR-LG-01 | REQUIREMENT | YES | TASK-001、TASK-002、TASK-006、TASK-008、TASK-013 | COVERED |
| NFR-LG-02 | REQUIREMENT | YES | TASK-007、TASK-012、TASK-014 | COVERED |
| NFR-LG-03 | REQUIREMENT | YES | TASK-005 | COVERED |
| NFR-LG-04 | REQUIREMENT | NO | None（本システムの対象外（FR-OUT-16。静的ページで表示）） | N/A |
| NFR-LG-05 | REQUIREMENT | YES | TASK-008、TASK-015 | COVERED |
| NFR-LG-06 | REQUIREMENT | YES | TASK-009、TASK-012、TASK-014、TASK-016、TASK-018 | COVERED |
| NFR-LG-07 | REQUIREMENT | YES | TASK-001、TASK-021（VUL-01〜VUL-13 の個別の対策は NFR-SC-03〜NFR-SC-11・NFR-SC-16・NFR-SC-19・NFR-SC-22 等の割当て Task） | COVERED |
| NFR-LG-08 | REQUIREMENT | YES | TASK-002、TASK-006、TASK-007、TASK-010、TASK-012、TASK-014、TASK-015、TASK-016、TASK-018 | COVERED |
| NFR-LG-09 | REQUIREMENT | YES | TASK-005、TASK-014 | COVERED |
| NFR-LG-10 | REQUIREMENT | NO | None（要件で「該当なし」） | N/A |
| UC-001〜UC-013 の AC（240件） | REQUIREMENT | YES | TASK-006、TASK-007、TASK-010、TASK-011、TASK-012、TASK-014、TASK-015、TASK-016、TASK-018、TASK-019、TASK-020（各 AC は1 Task の完了条件にだけ割り当て、3章の AC 単位の依存規則を満たす） | COVERED |
| ENT-001〜ENT-015 | DESIGN | YES | TASK-003、TASK-004、TASK-005 | COVERED |
| FILE-001 | DESIGN | YES | TASK-011、TASK-013 | COVERED |
| ADDR（後続工程で作成） | ADR | YES | 全 Task（後続ADDR の明示参照に従う） | N/A |

## 8. Progress Summary

| Status | Count |
| --- | ---: |
| TODO | 21 |
| READY | 0 |
| IN_PROGRESS | 0 |
| BLOCKED | 0 |
| DONE | 0 |
| CANCELLED | 0 |

### Overall Progress

- Total Tasks: 21
- Completed Tasks: 0
- Completion Rate: 0%
- Blocking Tasks: 0（実装開始は設計Gate・ADDR の実装引渡しGate成立後）

## 9. Blockers / Open Decisions

| Blocker ID | Related Task | Classification | Description | Impact | Recommended Route | Status |
| --- | --- | --- | --- | --- | --- | --- |
| BLK-001 | 全 Task | ARCHITECTURE | 重要方式15件（Web API 契約、ログイン状態・セッション（CSRF、削除指定で削除した利用者のログイン状態の無効化を含む）、パスワード保持、IFR-001 方式、同時実行制御、注文番号・識別子採番（削除指定後の識別子の扱いを含む）、コード値、定義ファイル形式・起動手段、試験用状態・試験用DB、構成、ログ、保存期間経過削除、環境別設定・本番構成（依存ライブラリ・実行環境の取得元・版の固定と記録の方式を含む））が未判断。manifest の unresolved_design_decisions として ADDR へ委譲（本書の Task 本文の修正が必要な場合のみ ARCHITECTURE へ差し戻し） | 判断前の実装着手不可 | ADDR | OPEN |
| BLK-002 | TASK-008、TASK-015、TASK-016、TASK-018 | REQUIREMENT | UNRESOLVED-32af0f4a0ca9c80f の BOQ-08／FOQ-03（本番での模擬決済の扱い、HIGH）。決定・受容の記録なし | 実装は現行FRで可（範囲拡大なし）。稼働開始判定の未充足 | USER_INPUT | OPEN |
| BLK-003 | TASK-006 | REQUIREMENT | UNRESOLVED-32af0f4a0ca9c80f の NOQ-08（総当たり対策・登録有無の判別の受容） | 実装は現行FRで可。稼働開始判定の未充足 | USER_INPUT | OPEN |
| BLK-004 | TASK-003、TASK-011、TASK-013 | REQUIREMENT | UNRESOLVED-32af0f4a0ca9c80f の NOQ-10（管理者アカウントの無効化・パスワード変更手段、本番定義ファイルの保管・廃棄） | 実装は現行FRで可（機能追加なし）。稼働開始判定の未充足 | USER_INPUT | OPEN |
| BLK-005 | TASK-011 | REQUIREMENT | NOQ-09／FOQ-02／DOQ-04／OQ-PJ-002（削除指定の本番移行での使用可否） | 実装は FR-060 現行どおり。移行手順に影響 | USER_INPUT | OPEN |
| BLK-006 | TASK-002、TASK-006〜TASK-020 | EXTERNAL | OQ-PJ-001：Steering が参照する docs/specifications/api-contract.md が未格納 | Web API 契約は ADDR 判断に依存 | USER_INPUT | OPEN |

## 10. Change History

| Version | Date | Change | Reason | Related ID |
| --- | --- | --- | --- | --- |
| 1.0 | 2026-11-19 | 初版作成（TASK-001〜TASK-018） | RUN-AOBA-EC-1118 Architecture 工程 | FR-001〜FR-060、ENT-001〜ENT-015、FILE-001 |
| 1.1 | 2026-11-19 | TASK-017 から注文確定途中の障害を TASK-019 へ分割。TASK-006・TASK-012・TASK-014・TASK-015・TASK-018 に TASK-017、TASK-011 に TASK-006 の依存を追加し Wave を 1〜9 に再編。TASK-006・TASK-011 に削除指定で削除した利用者のログイン状態の無効化（FR-060 手順9・6.26.9）を追加。TASK-002 に CSRF 対策の参照判断（authentication-session）と NFR-SC-10 の検証を追加。TASK-001 に環境別設定値一覧・本番でのデバッグ表示無効・開発用サーバー不使用を追加（ADDR 候補 environment-configuration）。BLK-001 の Route を ADDR に統一 | ARCHITECTURE Scope Assurance 修正cycle 1（QR-ARCH-001〜QR-ARCH-004、SR-ARCH-001） | TASK-001、TASK-002、TASK-006、TASK-011、TASK-012、TASK-014、TASK-015、TASK-017〜TASK-019、FR-060、NFR-OM-06、NFR-OM-17、NFR-SC-10、NFR-EN-08 |
| 1.2 | 2026-11-19 | 3章に AC 単位の依存規則を追加。全 Task×AC（240件）の照合により、他 Task の機能を要する AC（16件）を新設の TASK-020（機能横断の結合確認）へ移し、各機能 Task の完了条件に除外 AC を明記。TASK-012 に TASK-007、TASK-015 に TASK-016、TASK-018 に TASK-015 の依存を追加し Wave を 1〜12 に再編。依存ライブラリ・実行環境の取得元・版の固定・記録、サポート期限、既知脆弱性（CVSS 7.0以上0件）の確認を TASK-001 に追加し、リリース前の最終確認として TASK-021 を新設。TASK-002・TASK-018 にアクセスログの要求先に検索条件を含めないこと（NFR-SC-06）を追加。2章の詳細設計の参照版を 1.1 に更新 | ARCHITECTURE Scope Assurance 修正cycle 2（QR-ARCH-R1-002、QR-ARCH-R1-003、SR-ARCH-R1-002、SR-ARCH-R1-003） | TASK-001、TASK-002、TASK-006、TASK-007、TASK-010〜TASK-021、NFR-SC-06、NFR-SC-11、NFR-SC-21、NFR-EN-10 |
| 1.3 | 2026-11-19 | TASK-001 に本番環境向け設定でログイン状態を示す情報・CSRF 対策の値を暗号化通信でのみ送信し HTTP で業務データを受け付けないこと（NFR-SC-02、NFR-SC-19）、処理能力の増強（NFR-PF-16）、OS 非依存（NFR-EN-07）、ライセンス（NFR-EN-12）、開発・検証環境向け手順書（NFR-OM-19）を追加。LOG-01〜LOG-03 の要求の識別子（TASK-002）、LOG-06（TASK-008）、LOG-05（TASK-011）、LOG-01〜LOG-07 の運用テストと要求の識別子による横断追跡（TASK-020）を追加（NFR-OM-11、NFR-OM-18）。画面を持つ Task（TASK-002、TASK-006、TASK-007、TASK-010、TASK-012、TASK-014〜TASK-016、TASK-018）に画面共通の非機能要件（NFR-US-01、NFR-US-02、NFR-US-05〜NFR-US-07、NFR-PF-03）、取消できない操作の確認（NFR-US-09）、二重送信の防止（NFR-US-10）を追加。NFR-PF-01〜NFR-PF-04・NFR-PF-09・NFR-PF-17、NFR-SC-16、NFR-US-03、NFR-US-08、NFR-OM-03、NFR-MG-03、NFR-LG-01・NFR-LG-02・NFR-LG-05〜NFR-LG-09 を関連 Task に割当て。7章を全非機能要件（115件）×Task の照合結果に置換し、実装 Task の対象外とする非機能要件に理由を記録。3章に非機能要件の割当て規則を追加 | ARCHITECTURE Assurance 修正cycle 3（SR-ARCH-R2-001、QR-ARCH-R2-001、QR-ARCH-R2-002） | TASK-001〜TASK-003、TASK-005〜TASK-016、TASK-018、TASK-020、TASK-021、NFR-SC-02、NFR-SC-19、NFR-OM-11、NFR-OM-18、NFR-US-01、NFR-US-05、NFR-US-07、NFR-EN-12 |
