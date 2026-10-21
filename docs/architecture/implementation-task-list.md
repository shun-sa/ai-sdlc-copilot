# 実装タスク一覧・進捗

## 1. 文書情報

| 項目 | 内容 |
| --- | --- |
| Document ID | DOC-IMPL-TASK-001 |
| 対象システム | MiniCommerce |
| Baseline / Commit | RUN-002 Architecture（source_revision: requirements-2026-10-21） |
| Version | 1.1 |
| Status | DRAFT |
| Owner | Architecture Agent（RUN-002） |
| Last Updated | 2026-10-21 |

## 2. Source Baseline

| Source Type | ID / Path | Required Status / Version | Purpose |
| --- | --- | --- | --- |
| Requirements | docs/requirements/requirements.md（分割正本へのリンク索引） | 構造Validator PASS / 2026-10-21 | Scope / Requirement |
| Requirements | docs/requirements/functional_requirements.md | 構造Validator PASS / 2026-10-21 | FR-001〜FR-060・ERR-01〜ERR-08・判定順序 |
| Requirements | docs/requirements/non_functional_requirements.md | 構造Validator PASS / 2026-10-21 | NFR-xx-xx |
| Requirements | docs/requirements/data_requirements.md | 構造Validator PASS / 2026-10-21 | D-01〜D-15・項目英名・CD-xx・CLS-xx |
| Requirements | docs/requirements/external_interface_requirements.md | 構造Validator PASS / 2026-10-21 | IF-01 決済要求 |
| Requirements | docs/requirements/ui_report_requirements.md | 構造Validator PASS / 2026-10-21 | SCR-xxx |
| Use Case | docs/requirements/use-cases/UC-001.md 〜 UC-013.md | 構造Validator PASS / 2026-10-21 | Behavior / AC |
| ADR | None | 未実施（独立ADDR工程で作成） | Architecture Decision |
| Detailed Design | docs/architecture/files/FILE-001.md | DRAFT / 1.1 | 初期データ定義ファイルの詳細仕様 |
| Detailed Design | docs/specifications/api-contract.md | 提供済み / 2026-10-21 | エンドポイント・エラーコード・context |
| Project AI Steering | .github/project-context/project-ai-steering.md | DRAFT / 1.0 | PJ固有環境・配置・コマンド |

## 3. Task Decomposition Rules

Taskは以下の条件を満たす単位へ分解する。

- 1 Taskの目的と完了条件を明確に説明できる。
- Related Requirement / ADR / Design Referenceが特定できる。
- 依存Taskを明示できる。
- 実装後にBuild / Test / Validator等で完了を確認できる。
- 複数の独立した変更目的を不必要に1 Taskへまとめない。
- Requirementに存在しない機能追加をTask化しない。
- 新たなArchitecture Decisionが必要なTaskは実装開始前に解決する。

## 4. Task Summary

| Task ID | Title | Type | Related Requirement | Related ADR | Target Area | Depends On | Priority | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| TASK-001 | 実行基盤とプロジェクト構成の初期化 | CONFIG | NFR-EN-01, NFR-EN-02, NFR-EN-03, NFR-EN-04, NFR-EN-05, NFR-EN-07, NFR-EN-08, NFR-EN-10, NFR-EN-11, NFR-EN-12, NFR-OM-05, NFR-OM-06, NFR-OM-07, NFR-OM-17, NFR-PF-05, NFR-SC-07, NFR-SC-10, NFR-SC-11, NFR-SC-21, NFR-US-03, NFR-LG-07 | None | repository root / app | None | HIGH | TODO |
| TASK-002 | データモデルとマイグレーションの定義 | MIGRATION | FR-001, FR-030, FR-060, NFR-EN-02, NFR-EN-04, NFR-PF-06, NFR-PF-16, NFR-SC-23, NFR-LG-09 | None | app（データモデル） | TASK-001 | HIGH | TODO |
| TASK-003 | API共通基盤（エラー応答・判定順序・ページング・リクエストID・ログ） | IMPLEMENT | NFR-EN-11, NFR-OM-01, NFR-OM-11, NFR-OM-18, NFR-PF-08, NFR-PF-11, NFR-SC-04, NFR-SC-06, NFR-SC-10, NFR-SC-21, NFR-LG-07 | None | app（共通基盤） | TASK-001 | HIGH | TODO |
| TASK-004 | 認証・認可・監査ログ基盤 | IMPLEMENT | FR-002, FR-003, NFR-OM-11, NFR-PF-16, NFR-SC-01, NFR-SC-03, NFR-SC-06, NFR-SC-08, NFR-SC-09, NFR-SC-12, NFR-SC-15, NFR-SC-18, NFR-SC-19, NFR-SC-21, NFR-SC-22, NFR-SC-23, NFR-LG-01, NFR-LG-07 | None | app（認証・認可） | TASK-002, TASK-003 | HIGH | TODO |
| TASK-005 | 商品カタログ参照API（分類一覧・商品検索・商品詳細） | IMPLEMENT | FR-010, FR-011, FR-012, NFR-PF-01, NFR-PF-05, NFR-PF-06, NFR-PF-08, NFR-SC-04, NFR-SC-21, NFR-LG-02 | None | app（カタログ） | TASK-002, TASK-003 | HIGH | TODO |
| TASK-006 | 注文金額計算（小計・割引・送料・消費税・合計） | IMPLEMENT | FR-026, NFR-LG-06 | None | app（金額計算） | TASK-002, TASK-003 | HIGH | TODO |
| TASK-007 | 決済サービス（模擬）内部インターフェース | IMPLEMENT | FR-031, NFR-EN-05, NFR-PF-17, NFR-SC-24 | None | app（決済模擬） | TASK-002, TASK-003 | HIGH | TODO |
| TASK-008 | 会員登録API（FR-001） | IMPLEMENT | FR-001, NFR-SC-01, NFR-SC-04, NFR-SC-15, NFR-SC-16 | None | app（会員） | TASK-004 | HIGH | TODO |
| TASK-009 | 認証API（ログイン・ログアウト・ログイン利用者情報照会） | IMPLEMENT | FR-002, FR-003, FR-004, NFR-PF-09, NFR-SC-08, NFR-SC-12, NFR-SC-18, NFR-SC-22 | None | app（認証） | TASK-004 | HIGH | TODO |
| TASK-010 | カート照会・明細追加・数量変更・削除API | IMPLEMENT | FR-020, FR-021, FR-022, FR-023, NFR-PF-01, NFR-PF-02, NFR-PF-16, NFR-SC-03, NFR-LG-06 | None | app（カート） | TASK-004, TASK-006 | HIGH | TODO |
| TASK-011 | クーポン適用・解除API（FR-024, FR-025） | IMPLEMENT | FR-024, FR-025, NFR-PF-02, NFR-LG-06 | None | app（カート） | TASK-010 | HIGH | TODO |
| TASK-012 | 注文確定API（FR-030） | IMPLEMENT | FR-030, NFR-PF-02, NFR-PF-04, NFR-PF-05, NFR-PF-07, NFR-PF-11, NFR-SC-22, NFR-LG-06, NFR-LG-09 | None | app（注文） | TASK-006, TASK-010 | HIGH | TODO |
| TASK-013 | 支払API（FR-031、模擬決済の結果反映） | IMPLEMENT | FR-031, NFR-PF-02, NFR-PF-07, NFR-PF-17, NFR-SC-22 | None | app（注文・決済） | TASK-007, TASK-012 | HIGH | TODO |
| TASK-014 | 購入者向け注文照会API（FR-032, FR-033） | IMPLEMENT | FR-032, FR-033, NFR-PF-01, NFR-PF-08, NFR-SC-03, NFR-SC-24, NFR-LG-01 | None | app（注文） | TASK-012 | HIGH | TODO |
| TASK-015 | 購入者の注文キャンセルAPI（FR-034） | IMPLEMENT | FR-034, NFR-PF-02, NFR-SC-22, NFR-LG-06 | None | app（注文） | TASK-012 | HIGH | TODO |
| TASK-016 | 管理者向け照会API（在庫単位一覧・注文一覧・注文詳細） | IMPLEMENT | FR-040, FR-041, FR-042, NFR-PF-01, NFR-PF-06, NFR-PF-08, NFR-SC-03, NFR-SC-23, NFR-SC-24, NFR-LG-01 | None | app（管理） | TASK-012 | HIGH | TODO |
| TASK-017 | 管理者向け注文更新API（出荷・配達完了・キャンセル） | IMPLEMENT | FR-043, FR-044, FR-045, NFR-PF-02, NFR-PF-07, NFR-SC-03, NFR-SC-22, NFR-LG-06 | None | app（管理） | TASK-016 | HIGH | TODO |
| TASK-018 | 初期データ一括投入コマンド（FR-060） | IMPLEMENT | FR-060, NFR-OM-04, NFR-OM-11, NFR-OM-13, NFR-PF-10, NFR-SC-01, NFR-SC-04, NFR-SC-06, NFR-SC-15, NFR-SC-16, NFR-SC-22, NFR-SC-23, NFR-SC-25, NFR-MG-02, NFR-MG-03, NFR-MG-04, NFR-MG-07 | None | app（運用コマンド） | TASK-002, TASK-004 | HIGH | TODO |
| TASK-019 | 来訪者・購入者向け画面（SCR-001〜SCR-010, SCR-901） | IMPLEMENT | FR-001, FR-002, FR-010, FR-011, FR-012, FR-020, FR-021, FR-022, FR-023, FR-024, FR-025, FR-030, FR-031, FR-032, FR-033, FR-034, NFR-EN-05, NFR-EN-09, NFR-PF-03, NFR-SC-03, NFR-SC-05, NFR-SC-09, NFR-SC-12, NFR-SC-19, NFR-SC-21, NFR-US-01, NFR-US-02, NFR-US-03, NFR-US-04, NFR-US-05, NFR-US-06, NFR-US-07, NFR-US-08, NFR-US-09, NFR-US-10, NFR-LG-02, NFR-LG-07, NFR-LG-08 | None | app（画面） | TASK-011, TASK-013, TASK-015 | MEDIUM | TODO |
| TASK-020 | 管理者向け画面（SCR-101〜SCR-103） | IMPLEMENT | FR-040, FR-041, FR-042, FR-043, FR-044, FR-045, NFR-EN-09, NFR-PF-03, NFR-SC-03, NFR-SC-05, NFR-SC-21, NFR-SC-23, NFR-SC-24, NFR-US-01, NFR-US-02, NFR-US-03, NFR-US-04, NFR-US-05, NFR-US-06, NFR-US-07, NFR-US-09, NFR-US-10, NFR-LG-01, NFR-LG-07, NFR-LG-08 | None | app（画面） | TASK-017 | MEDIUM | TODO |
| TASK-021 | 起動・運用手順の整備（README・環境変数雛形） | OTHER | FR-060, NFR-OM-04, NFR-OM-05, NFR-OM-17, NFR-OM-19, NFR-SC-07, NFR-SC-25 | None | repository root | TASK-001, TASK-018 | MEDIUM | TODO |

## 5. Execution Order / Dependency

| Wave | Task IDs | Start Condition |
| ---: | --- | --- |
| 1 | TASK-001 | Source Baseline（要件・Steering・提供済みAPI契約・FINAL design manifest）が確定していること |
| 2 | TASK-002, TASK-003 | TASK-001 DONE（実行基盤が起動すること） |
| 3 | TASK-004, TASK-005, TASK-006, TASK-007 | TASK-002・TASK-003 DONE（モデルと共通基盤が利用できること） |
| 4 | TASK-008, TASK-009, TASK-010, TASK-018 | TASK-004 DONE（認証・認可・監査ログ基盤が利用できること） |
| 5 | TASK-011, TASK-012, TASK-021 | TASK-010・TASK-006 DONE（カートと金額計算が利用できること） |
| 6 | TASK-013, TASK-014, TASK-015, TASK-016 | TASK-012 DONE（注文が作成できること） |
| 7 | TASK-017, TASK-019 | TASK-016・TASK-013・TASK-015・TASK-011 DONE |
| 8 | TASK-020 | TASK-017 DONE（管理者向け更新APIが利用できること） |

## 6. Task Details

### TASK-001 `実行基盤とプロジェクト構成の初期化`

#### Metadata

| 項目 | 内容 |
| --- | --- |
| Type | CONFIG |
| Priority | HIGH |
| Status | TODO |
| Target Area | repository root / app |
| Depends On | None |
| Blocks | TASK-002, TASK-003, TASK-021 |

#### Source References

| Type | ID / Path | Relevant Section / Reason |
| --- | --- | --- |
| Requirement | NFR-EN-01, NFR-EN-02, NFR-EN-03, NFR-EN-04 | Python 3.12・Django 5.2 LTS・DRF・PostgreSQL 16・Docker Compose（app／db）・JST／UTF-8 |
| Requirement | NFR-EN-05, NFR-EN-07, NFR-EN-10, NFR-EN-12 | 外部インターネット非依存、ホストOS非依存、サポート期限内の版、利用条件を満たすライセンスの依存のみ |
| Requirement | NFR-EN-08, NFR-OM-17, NFR-SC-10, NFR-SC-11 | 本番でDjango付属の開発用サーバーを使わない、環境別設定（デバッグ表示・許可ホスト名・Cookie Secure属性）、本番のデバッグ表示無効化、依存の既知重大脆弱性の確認 |
| Requirement | NFR-OM-05, NFR-OM-06, NFR-OM-07, NFR-SC-07 | 1コマンド起動、pytest 1コマンド実行、ruff 指摘0件、秘密情報は環境変数 |
| Requirement | NFR-EN-11, NFR-PF-05, NFR-SC-21, NFR-US-03, NFR-LG-07 | コーディング規約、同時155利用者を前提とする構成、8.2 の対策方針（VUL-08・VUL-09・VUL-10）、UTF-8、OWASP Top 10 |
| Use Case / AC | UC-013 | 運用コマンドを実行できる環境が前提となる |
| ADR | None | 実行基盤の方式判断は独立ADDR工程で決定する（本Taskは要件・Steeringで一意な範囲のみ） |
| Detailed Design | .github/project-context/project-ai-steering.md 4章・9章 | 配置ルールと実行コマンド |

#### Objective

Steering 4章の配置ルールに従って Docker Compose（app／db）と単一 Django プロジェクトの実行基盤を用意し、起動・マイグレーション・静的解析・テストの各コマンドが1コマンドで実行できる状態にする。

#### Scope

##### In Scope

- compose.yaml（サービス app・db）と app コンテナの作業ディレクトリ設定
- app/ 配下の Django プロジェクト雛形（manage.py、設定、DRF 導入）
- タイムゾーン Asia/Tokyo・文字コード UTF-8・PostgreSQL 16 接続設定（環境変数から取得）
- .env.example（実値を含まない雛形）の作成
- 環境ごとに異なる設定（デバッグ表示の有効・無効、接続を受け付けるホスト名、セッション Cookie の Secure 属性、DB 接続情報、アプリケーションの秘密鍵）を環境変数から取得する設定（NFR-OM-17）
- 本番環境で Django 付属の開発用サーバーを使用しないための Web／AP サーバーの導入と起動設定（NFR-EN-08）
- 依存定義ファイルでの依存ライブラリのバージョン固定と取得元の公式配布元への限定（VUL-10）
- バージョン管理の除外設定（.env と app/seed/ 配下の初期データ定義ファイルを追跡しない）（NFR-SC-07、CLS-04）
- pytest＋pytest-django と ruff の設定ファイル

##### Out of Scope

- 業務ロジック・モデル・画面・APIの実装（TASK-002 以降）
- 本番基盤・HTTPS 終端・監視の構成（OQ-PJ-001、OQ-PJ-003 として未決）
- app/ 内部のモジュール分割方針の確定（独立ADDR工程の判断対象）

#### Expected Change

- compose.yaml（app・db の2サービス、app は 8000、db は 5432）
- app/ 配下の Django プロジェクト設定と依存定義
- .env.example、README.md の起動手順の受け皿（本文整備は TASK-021）
- ruff・pytest の設定

#### Constraints

- 外部インターネットへ接続せずに起動・動作すること（イメージ・依存取得時を除く。NFR-EN-05）
- 秘密情報をリポジトリに含めないこと（.env は追跡しない。NFR-SC-07）
- 本番環境ではデバッグ表示を無効化し、接続を受け付けるホスト名を限定すること（NFR-SC-10 後段、NFR-OM-17、VUL-08）
- セッション Cookie の Secure 属性を環境別に切り替えられること（本番は有効。NFR-SC-09、NFR-OM-17）
- 本番環境で Django 付属の開発用サーバーを使用しないこと（NFR-EN-08、VUL-08）
- 依存ライブラリはバージョンを固定し、取得元を公式の配布元に限ること。AGPL とライセンス不明のライブラリを使わないこと（VUL-10、NFR-EN-12）
- SPA フレームワーク・フロントエンドビルド工程・外部 CDN を使わないこと

#### Completion Criteria / Definition of Done

- [ ] docker compose build と docker compose up -d が成功する
- [ ] docker compose exec app python manage.py migrate が実行できる（初期状態）
- [ ] docker compose exec app ruff check . の指摘が0件である
- [ ] docker compose exec app pytest がコマンド1回で実行できる
- [ ] デバッグ表示・許可ホスト名・Cookie Secure 属性・DB 接続情報・秘密鍵が、プログラム変更なしで環境別に切り替えられる（NFR-OM-17）
- [ ] 本番相当の設定でデバッグ表示が無効であり、Django 付属の開発用サーバーを使用しない構成になっている（NFR-SC-10、NFR-EN-08）
- [ ] 依存定義ファイルで全依存ライブラリのバージョンが固定され、取得元が公式の配布元に限定されている（VUL-10）
- [ ] バージョン管理の除外設定に .env と app/seed/ 配下の初期データ定義ファイルが含まれている（NFR-SC-07）
- [ ] リリース前に依存ライブラリの既知の重大な脆弱性（CVSS 7.0 以上）が無いことを確認した記録がある（NFR-SC-11、VUL-09）
- [ ] 要件にない機能・依存を追加していない
- [ ] 実行結果を Implementation 工程の報告へ残せる

#### Validation

| Validation Type | Command / Method | Expected Result |
| --- | --- | --- |
| Build | docker compose build | PASS |
| Static Check | docker compose exec app ruff check . | PASS（指摘0件） |
| Unit Test | docker compose exec app pytest | planned（テストは後続工程で追加） |
| Other | docker compose up -d の後に http://localhost:8000 が応答する | 起動確認 PASS |

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

- app/ 内部のモジュール分割と依存規則は Steering で設計へ委任されており、独立ADDR工程の判断を参照して実装する（BLK-004）。
- 実装時は本書と併せて、独立ADDR工程が公開する重要判断を参照する。

### TASK-002 `データモデルとマイグレーションの定義`

#### Metadata

| 項目 | 内容 |
| --- | --- |
| Type | MIGRATION |
| Priority | HIGH |
| Status | TODO |
| Target Area | app（データモデル） |
| Depends On | TASK-001 |
| Blocks | TASK-004, TASK-005, TASK-006, TASK-007, TASK-018 |

#### Source References

| Type | ID / Path | Relevant Section / Reason |
| --- | --- | --- |
| Requirement | FR-001, FR-030, FR-060 | 利用者・カート・注文・在庫単位・監査ログの生成と更新 |
| Requirement | NFR-EN-02, NFR-EN-04, NFR-SC-23, NFR-PF-06, NFR-PF-16, NFR-LG-09 | PostgreSQL・JST／UTF-8、監査ログと注文状態履歴の追記のみ、将来データ量での性能、利用者の状態を DB に保持、都道府県コード |
| Use Case / AC | UC-004, UC-006, UC-013 | カート・注文・初期データの各フローが参照するデータ |
| ADR | None | 物理設計（索引・制約の実現方式）の判断は独立ADDR工程 |
| Detailed Design | docs/requirements/data_requirements.md 2章・3章・5章 | D-01〜D-15 の項目英名・値域・一意条件・整合性ルール |

#### Objective

データ要件（D-01〜D-15）の項目・値域・一意条件・関連を Django モデルとマイグレーションとして定義し、以降の全機能が同一のデータ定義を参照できるようにする。

#### Scope

##### In Scope

- 利用者・仕入先・商品分類・商品・商品分類所属・在庫単位・クーポン・カート・カート明細・注文・注文明細・配送先・決済記録・注文状態履歴・監査ログのモデル定義
- 項目英名・データ形式・桁・必須・一意条件（分類名の同一親内一意等）の反映
- 保持しない算出項目（税込価格・最低価格・在庫有無）をモデルへ持たせないこと
- 初期マイグレーションの作成

##### Out of Scope

- 業務ロジック・API・画面（各機能Task）
- 索引設計・物理チューニングの方式判断（独立ADDR工程）
- 保存期間経過データの自動削除（本リリース対象外）

#### Expected Change

- app/ 配下のモデル定義とマイグレーションファイル
- コード値（CD-01〜CD-07）の定義箇所
- 数量・金額・日時の型（整数の円、JST 日時）の統一

#### Constraints

- 項目英名はデータ要件の英名に一致させること（API 応答項目名の正本）
- 税込価格を保持せず税抜価格から算出すること（DCN-11）
- 金額は整数の円、日時は JST の秒単位とすること（DCN-12）
- 監査ログと注文状態履歴のモデルは追記のみとし、更新・削除の操作経路をモデル側に設けないこと（NFR-SC-23）
- ログインセッション・認証トークン・カートを app の内部メモリではなく DB に保持できるモデルとすること（NFR-PF-16）
- 配送先の都道府県は JIS X 0401 のコード（01〜47）で保持すること（NFR-LG-09）

#### Completion Criteria / Definition of Done

- [ ] D-01〜D-15 の必須項目・値域・一意条件がモデル定義に反映されている
- [ ] migrate が成功し、データ要件の関連（REL-01〜REL-18）と矛盾しない
- [ ] docker compose exec app ruff check . の指摘が0件である
- [ ] 監査ログと注文状態履歴のモデルに更新・削除の操作経路が無い（NFR-SC-23）
- [ ] モデル定義に要件外の項目・エンティティを追加していない
- [ ] マイグレーション実行結果を報告へ残せる

#### Validation

| Validation Type | Command / Method | Expected Result |
| --- | --- | --- |
| Build | docker compose build | PASS |
| Static Check | docker compose exec app ruff check . | PASS |
| Unit Test | docker compose exec app pytest | planned |
| Other | docker compose exec app python manage.py migrate | PASS |

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

- 一意制約・索引の具体的な実現方式（部分一意制約の採否等）は独立ADDR工程の判断対象として残す。
- 実装時は本書と併せて、独立ADDR工程が公開する重要判断を参照する。

### TASK-003 `API共通基盤（エラー応答・判定順序・ページング・リクエストID・ログ）`

#### Metadata

| 項目 | 内容 |
| --- | --- |
| Type | IMPLEMENT |
| Priority | HIGH |
| Status | TODO |
| Target Area | app（共通基盤） |
| Depends On | TASK-001 |
| Blocks | TASK-004, TASK-005, TASK-006, TASK-007 |

#### Source References

| Type | ID / Path | Relevant Section / Reason |
| --- | --- | --- |
| Requirement | NFR-SC-04, NFR-SC-10, NFR-SC-06, NFR-OM-01 | サーバー側入力検証、プレースホルダによる DB 操作、内部情報の非返却、ログの禁止項目、JSON Lines ログ |
| Requirement | NFR-OM-11, NFR-OM-18, NFR-PF-08, NFR-PF-11, NFR-SC-21, NFR-EN-11, NFR-LG-07 | LOG-01〜03・06 の出力、request_id の引継ぎ、一覧件数上限、上限超過時も正常応答または業務エラー応答、8.2 の対策方針（VUL-04・VUL-05・VUL-13）、API・URL の命名規約 |
| Use Case / AC | UC-001〜UC-013 の例外フロー | 全機能に共通するエラー応答と判定順序 |
| ADR | None | 例外ハンドラ・ログ出力先の実現方式は独立ADDR工程 |
| Detailed Design | docs/specifications/api-contract.md 6.2・6.3 | エラーコード・HTTP ステータス・context の正本 |

#### Objective

全 API が同一のエラー表現・判定順序・ページング形式・相関IDとログ項目を用いるための共通基盤を用意し、個別機能Taskでの重複実装と仕様差異を防ぐ。

#### Scope

##### In Scope

- エラー応答形式（error.code／message／details／context）と HTTP ステータス対応の共通実装
- 判定順序（認証→権限→入力→対象の存在・所有→状態→業務ルール）を適用する共通処理
- 外部入力（要求本文・クエリ・パス・フォーム）の型・桁数・値域・形式をサーバー側で検証する共通処理（NFR-SC-04）
- ページング応答（results／page／page_size／total_count／total_pages）とページ番号の検証
- X-Request-ID の引継ぎ・生成と応答ヘッダー付与
- JSON Lines の構造化ログ（timestamp・level・request_id・method・path・status・user_id・duration_ms）と禁止項目の非出力

##### Out of Scope

- 各機能固有の入力検証・業務判定（各機能Task）
- 監視・アラート設定（本番運用時に設定）
- ログ保管・ローテーションの基盤方式（独立ADDR工程・運用）

#### Expected Change

- 共通例外ハンドラとエラーコード定義
- ページング共通処理
- リクエストID のミドルウェアとログフォーマッタ

#### Constraints

- スタックトレース・SQL など内部情報を応答へ含めないこと（NFR-SC-10）
- パスワード・トークン・メールアドレス・氏名・住所・電話番号をログへ出力しないこと（NFR-SC-06）
- VALIDATION_ERROR は不備のある全項目を details に列挙すること
- DB の操作はプレースホルダ（パラメータ化）で行い、SQL 文を入力値の文字列連結で組み立てないこと（NFR-SC-04、VUL-04）
- 外部入力を OS コマンドへ渡さないこと（NFR-SC-04、VUL-04）
- API 応答の Content-Type を application/json とすること（VUL-05）
- 1件のリクエストに関する全ログ行へ同一の request_id を出力し、応答ヘッダー X-Request-ID に付与すること（NFR-OM-18）

#### Completion Criteria / Definition of Done

- [ ] api-contract.md 6.2 のエラーコードと HTTP ステータスが共通基盤から一貫して返る
- [ ] ページング応答が FR-011／FR-032／FR-040／FR-041 の件数指定で使える形になっている
- [ ] ログに禁止項目が出力されない
- [ ] DB 操作がプレースホルダで行われ、入力値の文字列連結による SQL 組み立てと OS コマンド実行が無い（NFR-SC-04）
- [ ] 同一リクエストの全ログ行に同じ request_id が出力され、応答ヘッダーへ付与される（NFR-OM-18）
- [ ] ruff の指摘が0件である
- [ ] 共通基盤に要件外の機能を追加していない
- [ ] 動作確認結果を報告へ残せる

#### Validation

| Validation Type | Command / Method | Expected Result |
| --- | --- | --- |
| Build | docker compose build | PASS |
| Static Check | docker compose exec app ruff check . | PASS |
| Unit Test | docker compose exec app pytest | planned |
| Other | エラー応答・ログ出力の手動確認（api-contract.md 6.2 と突き合わせ） | 一致 |

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

- ログ出力先（標準出力かファイルか）と保管方式は要件に明記がなく、独立ADDR工程の判断対象として残す。
- 実装時は本書と併せて、独立ADDR工程が公開する重要判断を参照する。

### TASK-004 `認証・認可・監査ログ基盤`

#### Metadata

| 項目 | 内容 |
| --- | --- |
| Type | IMPLEMENT |
| Priority | HIGH |
| Status | TODO |
| Target Area | app（認証・認可） |
| Depends On | TASK-002, TASK-003 |
| Blocks | TASK-008, TASK-009, TASK-010, TASK-018 |

#### Source References

| Type | ID / Path | Relevant Section / Reason |
| --- | --- | --- |
| Requirement | FR-002, FR-003, NFR-SC-01, NFR-SC-08, NFR-SC-09 | トークン発行・無効化、パスワードのハッシュ保存、トークン保護、無操作タイムアウト |
| Requirement | NFR-SC-12, NFR-SC-15, NFR-SC-18, NFR-SC-19 | メールアドレス＋パスワードによる認証、ロール変更手段を設けない、多重ログイン許容、ログイン時のセッション識別子の再発行 |
| Requirement | NFR-SC-03, NFR-SC-21, NFR-SC-22, NFR-SC-23, NFR-LG-01, NFR-LG-07 | サーバー側の区分・所有者判定、8.2 の対策方針（VUL-01・VUL-02・VUL-11）、監査ログの記録対象、監査ログと注文状態履歴の追記のみ、個人情報の安全管理措置 |
| Requirement | NFR-OM-11, NFR-PF-16, NFR-SC-06 | LOG-04（監査ログ）の出力、利用者の状態を DB に保持、ログの禁止項目 |
| Use Case / AC | UC-002 | ログイン・ログアウトの正常／例外フローと AC |
| ADR | None | ハッシュアルゴリズム・トークン保持方式の判断は独立ADDR工程 |
| Detailed Design | docs/specifications/api-contract.md 認証ヘッダー節 | Bearer トークン・24時間有効期間・認証不要APIの範囲 |

#### Objective

API の認証トークンと画面のログインセッション、ロール・所有者によるサーバー側認可、監査ログ記録を共通機能として用意し、各機能Taskが同じ判定を再利用できるようにする。

#### Scope

##### In Scope

- パスワードのソルト付き一方向ハッシュ保存と照合（CMN-06）
- 認証トークンの発行（128ビット以上相当の乱数、発行から24時間）・検証・ログアウトによる無効化・多重ログイン許容
- 画面のログインセッション（無操作30分で切断、HttpOnly、本番は Secure）
- 画面のログインセッション識別子の生成（推測困難な乱数）、ログイン成功時の再発行とログイン前の識別子の無効化、ログアウト時の破棄（NFR-SC-19）
- 利用者のロールを画面・API から変更させない認可設計（会員登録はロール指定を受けても buyer として扱う。NFR-SC-15、CMN-08）
- ロール（buyer／admin）と所有者判定の共通処理（他人の注文は NOT_FOUND）
- 監査ログ（ログイン成功・失敗・ログアウト）の記録と禁止項目の非記録

##### Out of Scope

- 会員登録・ログインの各 API エンドポイント本体（TASK-008、TASK-009）
- アカウントロック・試行回数制限（FR-OUT-11 のため実装しない）
- パスワード変更・再設定（FR-OUT-09 のため実装しない）

#### Expected Change

- 認証バックエンド・トークンモデル・認可判定の共通処理
- 監査ログ記録の共通処理
- 認証不要 API（FR-001, FR-002, FR-010, FR-011, FR-012）の除外設定

#### Constraints

- 認証失敗はメールアドレスとパスワードのどちらが誤りかを区別しないこと（CMN-05）
- 権限判定は画面・API ともサーバー側で行うこと（NFR-SC-03）
- 監査ログにメールアドレス・パスワード・トークン・氏名を記録しないこと（CMN-25）
- ログイン成功時に画面のセッション識別子を再発行し、ログイン前の識別子を無効化すること（NFR-SC-19、VUL-02）
- 画面・API に利用者の作成・ロール変更の手段を設けないこと（NFR-SC-15）
- 監査ログと注文状態履歴は追記のみとし、画面・API に更新・削除の手段を設けないこと（NFR-SC-23、VUL-11）
- ログインセッション・認証トークンを app の内部メモリではなく DB に保持すること（NFR-PF-16）

#### Completion Criteria / Definition of Done

- [ ] 有効なトークンのない要求が AUTHENTICATION_REQUIRED（401）になる
- [ ] ロール不一致が PERMISSION_DENIED（403）、他人の注文指定が NOT_FOUND（404）になる
- [ ] ログイン成功・失敗・ログアウトの監査ログが1件ずつ記録される
- [ ] ログイン成功時にセッション識別子が再発行され、ログイン前の識別子では操作できない（NFR-SC-19）
- [ ] 画面・API に利用者の作成・ロール変更の経路が無い（NFR-SC-15）
- [ ] 監査ログと注文状態履歴に対する更新・削除の経路が画面・API に無い（NFR-SC-23）
- [ ] ruff の指摘が0件である
- [ ] 要件にない認証機能を追加していない
- [ ] 確認結果を報告へ残せる

#### Validation

| Validation Type | Command / Method | Expected Result |
| --- | --- | --- |
| Build | docker compose build | PASS |
| Static Check | docker compose exec app ruff check . | PASS |
| Unit Test | docker compose exec app pytest | planned |
| Other | 認証・権限・所有者判定の手動確認（UC-002 の例外フロー） | 一致 |

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

- ハッシュアルゴリズム・トークンの保存形式・セッションストアの選択は独立ADDR工程の判断対象（BLK-002）。
- 実装時は本書と併せて、独立ADDR工程が公開する重要判断を参照する。

### TASK-005 `商品カタログ参照API（分類一覧・商品検索・商品詳細）`

#### Metadata

| 項目 | 内容 |
| --- | --- |
| Type | IMPLEMENT |
| Priority | HIGH |
| Status | TODO |
| Target Area | app（カタログ） |
| Depends On | TASK-002, TASK-003 |
| Blocks | None |

#### Source References

| Type | ID / Path | Relevant Section / Reason |
| --- | --- | --- |
| Requirement | FR-010, FR-011, FR-012 | 分類の木構造、検索条件・並び順・ページング、在庫単位ごとの価格と在庫 |
| Requirement | NFR-SC-04, NFR-SC-21, NFR-PF-01, NFR-PF-05, NFR-PF-06, NFR-PF-08, NFR-LG-02 | サーバー側検証とプレースホルダによる DB 操作、8.2 の対策方針（VUL-04）、照会系応答時間、同時利用者数、将来データ量、1ページ20件、総額表示 |
| Use Case / AC | UC-003 | 商品を探して閲覧するフローと AC |
| ADR | None | 検索の実装方式（クエリ構成）の判断は独立ADDR工程 |
| Detailed Design | docs/specifications/api-contract.md 6.1 | GET /api/collections、/api/items、/api/items/{item_id} |

#### Objective

認証不要の商品カタログ参照APIを実装し、来訪者・購入者・管理者が分類とキーワードで公開中の商品を探し、在庫単位ごとの税抜・税込価格と在庫を確認できるようにする。

#### Scope

##### In Scope

- 商品分類一覧（親子の木構造順、全件を配列で返す）
- 商品一覧検索（分類・キーワード絞り込み、並び順、20件/ページ）
- 商品詳細（説明・所属分類・在庫単位一覧、SKU昇順）
- 税込価格・最低価格・在庫有無の算出（税抜価格×110÷100 の1円未満切り捨て）

##### Out of Scope

- 非公開商品の提供（来訪者・購入者には提供しない）
- カート投入・注文（TASK-010 以降）
- 管理者向け在庫単位一覧（TASK-016）

#### Expected Change

- カタログ参照のビュー・シリアライザ・クエリ
- 算出項目（min_price, min_price_incl_tax, price_incl_tax, in_stock）の算出処理

#### Constraints

- 保持しない算出項目を永続化しないこと（DCN-11）
- 名称・コードの並べ替えは Unicode コードポイント順とすること（CMN-36）
- 総ページ数を超えるページ番号はエラーにせず空配列を返すこと（CMN-35）
- キーワード検索を含む全ての DB 操作をプレースホルダ（パラメータ化）で行い、入力値の文字列連結で SQL 文を組み立てないこと（NFR-SC-04、VUL-04）
- 検索条件・並び順・ページ番号をサーバー側で検証すること（NFR-SC-04）
- 商品価格は税込の総額を表示できる形で返すこと（NFR-LG-02）

#### Completion Criteria / Definition of Done

- [ ] FR-010・FR-011・FR-012 の出力項目が api-contract.md の項目名と一致する
- [ ] UC-003 の AC に対応する振る舞い（絞り込み・並び順・ページング・0件表示）が実現できる
- [ ] ruff の指摘が0件である
- [ ] キーワード検索を含む DB 操作に、入力値の文字列連結による SQL 組み立てが無い（NFR-SC-04）
- [ ] 要件にない検索条件・並び順を追加していない
- [ ] 確認結果を報告へ残せる

#### Validation

| Validation Type | Command / Method | Expected Result |
| --- | --- | --- |
| Build | docker compose build | PASS |
| Static Check | docker compose exec app ruff check . | PASS |
| Unit Test | docker compose exec app pytest | planned |
| Other | 応答項目名と api-contract.md の突き合わせ | 一致 |

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

- 応答時間 NFR-PF-01（照会系 1.0秒以内）と NFR-PF-06（3年後のデータ量）の達成方式（索引・一意制約・クエリ最適化を含む物理設計）は独立ADDR工程の判断対象として残す（BLK-006、ARCH-CI-008）。
- 方式が未判断であっても、プレースホルダによる安全なクエリ構成（NFR-SC-04）は本Taskの制約として先に固定する。
- 実装時は本書と併せて、独立ADDR工程が公開する重要判断を参照する。

### TASK-006 `注文金額計算（小計・割引・送料・消費税・合計）`

#### Metadata

| 項目 | 内容 |
| --- | --- |
| Type | IMPLEMENT |
| Priority | HIGH |
| Status | TODO |
| Target Area | app（金額計算） |
| Depends On | TASK-002, TASK-003 |
| Blocks | TASK-010, TASK-012 |

#### Source References

| Type | ID / Path | Relevant Section / Reason |
| --- | --- | --- |
| Requirement | FR-026, NFR-LG-06 | 金額内訳の算出とクーポン適用可否の判定 |
| Use Case / AC | UC-004, UC-005, UC-006 | カート表示・クーポン適用・注文確定で同じ計算を用いる |
| ADR | None | 計算処理の配置（モジュール分割）は独立ADDR工程 |
| Detailed Design | docs/specifications/api-contract.md amounts 節 | subtotal, discount_amount, discounted_subtotal, shipping_fee, tax_amount, total |

#### Objective

カート操作・クーポン操作・注文確定が共通で呼び出す金額計算を1か所に実装し、画面と API で同一の金額内訳とクーポン適用可否を返す。

#### Scope

##### In Scope

- 小計・割引額・割引後小計・送料・消費税額・合計の算出
- クーポンの適用可否（有効期間・最低購入金額）と不可理由の判定
- 端数処理（各計算段階で1円未満切り捨て）と税率10%の適用

##### Out of Scope

- クーポンの適用・解除操作そのもの（TASK-011）
- 在庫引当・注文作成（TASK-012）
- 業務ルール値の新規定義（要件・業務要件の値のみを用いる）

#### Expected Change

- 金額計算の共通処理と適用可否判定
- カート表現・注文詳細表現から参照できる amounts 構造

#### Constraints

- 業務ルールを画面側（テンプレート・JavaScript）へ重複実装しないこと（Steering 4.2）
- 消費税額は（割引後小計＋送料）×10÷100 の1円未満切り捨てとし、明細ごとに計算しないこと（CMN-31）
- 金額は整数の円のみとすること（CMN-30）

#### Completion Criteria / Definition of Done

- [ ] UC-004・UC-005 の金額内訳に関する AC を満たす計算結果になる
- [ ] クーポン適用可否と不可理由が FR-026 の定義と一致する
- [ ] ruff の指摘が0件である
- [ ] 要件にない割引・送料ルールを追加していない
- [ ] 計算結果の確認を報告へ残せる

#### Validation

| Validation Type | Command / Method | Expected Result |
| --- | --- | --- |
| Build | docker compose build | PASS |
| Static Check | docker compose exec app ruff check . | PASS |
| Unit Test | docker compose exec app pytest | planned |
| Other | 業務要件（BR-06〜BR-09, BR-17）の金額例との突き合わせ | 一致 |

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

- 送料・税率・割引の値は業務要件・機能要件の既定値を参照し、本Taskで新たに決めない。
- 実装時は本書と併せて、独立ADDR工程が公開する重要判断を参照する。

### TASK-007 `決済サービス（模擬）内部インターフェース`

#### Metadata

| 項目 | 内容 |
| --- | --- |
| Type | IMPLEMENT |
| Priority | HIGH |
| Status | TODO |
| Target Area | app（決済模擬） |
| Depends On | TASK-002, TASK-003 |
| Blocks | TASK-013 |

#### Source References

| Type | ID / Path | Relevant Section / Reason |
| --- | --- | --- |
| Requirement | FR-031 | 支払要求の項目と結果の受け取り |
| Requirement | NFR-EN-05, NFR-PF-17, NFR-SC-24 | 外部サービスへ接続しない、決済連携部分の分離、決済要求に個人情報を含めない |
| Use Case / AC | UC-007 | 承認・否認・応答なしの各フロー |
| ADR | None | 模擬決済の実装配置・呼出し方式は独立ADDR工程 |
| Detailed Design | docs/requirements/external_interface_requirements.md 5.1（IF-01） | 要求・応答項目、取引参照番号の書式、タイムアウト |

#### Objective

IF-01（決済要求）を本システム内の模擬機能として実装し、注文番号・決済金額・通貨 JPY・模擬決済指示に対して承認／否認の結果を返す。

#### Scope

##### In Scope

- 模擬決済の要求・応答項目（注文番号、決済金額、通貨 JPY、模擬決済指示）
- approve は承認と取引参照番号（MOCK-＋英数字16桁）、decline は否認理由コード DECLINED を返す
- 応答待ち最大10秒・自動再送なしの呼出し制御
- 1秒以内の応答

##### Out of Scope

- 実在の決済サービスへの接続（Steering 11章で禁止）
- 注文状態の更新・決済記録の確定（TASK-013）
- 返金処理（本システム外）

#### Expected Change

- 模擬決済の内部インターフェースと応答生成
- タイムアウト・異常応答の扱い（PAYMENT_SERVICE_ERROR へ写像する入力）

#### Constraints

- 外部ネットワークへ接続しないこと（NFR-EN-05）
- 自動再送しないこと（二重決済防止）
- 取引参照番号の書式は IF-01 の定義に従うこと
- 決済要求の送信・応答の受信を行う部分を注文・在庫・金額計算から分離すること（NFR-PF-17）
- 決済サービスへの要求に個人情報を含めないこと（NFR-SC-24）
- 接続先を設定で固定し、利用者の入力で変更できないようにすること（VUL-12）

#### Completion Criteria / Definition of Done

- [ ] approve で承認、decline で否認が返る
- [ ] 応答待ちが10秒を超えた場合に外部連携エラーとして扱える形になっている
- [ ] ruff の指摘が0件である
- [ ] 実在サービスへの接続処理を含まない
- [ ] 確認結果を報告へ残せる

#### Validation

| Validation Type | Command / Method | Expected Result |
| --- | --- | --- |
| Build | docker compose build | PASS |
| Static Check | docker compose exec app ruff check . | PASS |
| Unit Test | docker compose exec app pytest | planned |
| Other | IF-01 の項目・書式との突き合わせ | 一致 |

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

- 模擬決済（IF-01）の実装配置（app 内のどの層へ置くか）と呼出し方式、模擬決済指示の受け渡し方法（API 入力かテスト用設定か）は独立ADDR工程の判断対象として残す（BLK-007、ARCH-CI-009）。
- 実装時は本書と併せて、独立ADDR工程が公開する重要判断を参照する。

### TASK-008 `会員登録API（FR-001）`

#### Metadata

| 項目 | 内容 |
| --- | --- |
| Type | IMPLEMENT |
| Priority | HIGH |
| Status | TODO |
| Target Area | app（会員） |
| Depends On | TASK-004 |
| Blocks | None |

#### Source References

| Type | ID / Path | Relevant Section / Reason |
| --- | --- | --- |
| Requirement | FR-001 | 入力条件・重複判定・登録内容 |
| Requirement | NFR-SC-01, NFR-SC-04, NFR-SC-15, NFR-SC-16 | パスワードのソルト付きハッシュ保存、サーバー側入力検証、ロール指定を受け付けない、パスワードの文字数・文字種 |
| Use Case / AC | UC-001 | 会員登録の正常・例外フローと AC |
| ADR | None | 方式判断は独立ADDR工程 |
| Detailed Design | docs/specifications/api-contract.md 6.1・6.2 | POST /api/auth/register（201）、EMAIL_ALREADY_REGISTERED |

#### Objective

メールアドレス・パスワード・氏名を受け付けてロール buyer の利用者を登録する API を実装する（自動ログインしない）。

#### Scope

##### In Scope

- 入力検証（メールアドレス正規化、パスワード条件、氏名、確認用パスワードの一致）
- メールアドレス重複時の EMAIL_ALREADY_REGISTERED（409）
- パスワードのハッシュ保存と登録日時の設定
- ログイン中の buyer・admin からの要求も受け付ける（登録されるのは buyer）

##### Out of Scope

- 管理者利用者の作成（FR-060 でのみ作成。CMN-08）
- 会員情報の変更・退会（本リリース対象外）
- 登録完了メール送信（FR-OUT-08 のため実装しない）

#### Expected Change

- 会員登録のビュー・入力検証・応答
- 重複判定と同時登録競合時の業務エラー

#### Constraints

- VALIDATION_ERROR は不備のある全項目を列挙すること（CMN-16）
- 判定順序に従うこと（入力→業務ルール）
- パスワードを応答・ログへ出力しないこと
- 要求にロールの指定が含まれても購入者（buyer）として登録し、画面・API にロール変更の手段を設けないこと（NFR-SC-15、CMN-08）
- パスワードは要件の文字数・文字種の条件を満たす場合のみ受け付けること（NFR-SC-16）
- パスワードはソルト付き一方向ハッシュで保存し、平文・可逆暗号で保存しないこと（NFR-SC-01）

#### Completion Criteria / Definition of Done

- [ ] UC-001 の AC に対応する正常・例外の振る舞いが実現できる
- [ ] 201 応答の項目が api-contract.md と一致する
- [ ] ruff の指摘が0件である
- [ ] ロール指定を含む要求でも buyer として登録され、管理者を作成できない（NFR-SC-15）
- [ ] 要件にない項目（住所等）を登録に追加していない
- [ ] 確認結果を報告へ残せる

#### Validation

| Validation Type | Command / Method | Expected Result |
| --- | --- | --- |
| Build | docker compose build | PASS |
| Static Check | docker compose exec app ruff check . | PASS |
| Unit Test | docker compose exec app pytest | planned |
| Other | UC-001 の例外フローとの突き合わせ | 一致 |

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

- 同一メールアドレスの同時登録は EMAIL_ALREADY_REGISTERED で返す（CMN-19）。実現方式は独立ADDR工程の判断に従う。
- 実装時は本書と併せて、独立ADDR工程が公開する重要判断を参照する。

### TASK-009 `認証API（ログイン・ログアウト・ログイン利用者情報照会）`

#### Metadata

| 項目 | 内容 |
| --- | --- |
| Type | IMPLEMENT |
| Priority | HIGH |
| Status | TODO |
| Target Area | app（認証） |
| Depends On | TASK-004 |
| Blocks | None |

#### Source References

| Type | ID / Path | Relevant Section / Reason |
| --- | --- | --- |
| Requirement | FR-002, FR-003, FR-004 | 照合・トークン発行・無効化・本人情報の応答 |
| Requirement | NFR-SC-08, NFR-SC-12, NFR-SC-18, NFR-SC-22, NFR-PF-09 | トークンの生成・有効期間・無効化、認証方式、多重ログイン、監査ログの記録対象、認証系応答時間 |
| Use Case / AC | UC-002 | ログイン・ログアウトの正常・例外フローと AC |
| ADR | None | 方式判断は独立ADDR工程 |
| Detailed Design | docs/specifications/api-contract.md 6.1・6.2 | POST /api/auth/login（200）、/logout（204）、GET /api/auth/me |

#### Objective

メールアドレスとパスワードの照合によるトークン発行、要求に使われたトークンの無効化、ログイン中利用者情報の応答を実装する。

#### Scope

##### In Scope

- ログイン（token・expires_at・user の応答、監査ログ記録）
- 認証失敗時の INVALID_CREDENTIALS（401）とメールアドレス形式不正の扱い
- ログアウト（204、要求に使われたトークンのみ無効化）
- ログイン利用者情報照会（user_id・email・full_name・role）

##### Out of Scope

- アカウントロック・試行回数制限（FR-OUT-11）
- パスワード再設定（FR-OUT-09）
- 画面側のログインフォーム（TASK-019）

#### Expected Change

- 認証系3エンドポイントのビューと応答
- 監査ログ（login_success／login_failure／logout）の記録呼び出し

#### Constraints

- 未入力のみ VALIDATION_ERROR、形式不正は INVALID_CREDENTIALS とすること
- 多重ログインを許容し、他のトークンを無効化しないこと（CMN-11、CMN-12）
- 監査ログにメールアドレス・パスワードを記録しないこと

#### Completion Criteria / Definition of Done

- [ ] UC-002 の AC に対応する正常・例外の振る舞いが実現できる
- [ ] 成功ステータス（200／204／200）が api-contract.md と一致する
- [ ] ログイン失敗時も監査ログが1件記録される
- [ ] ruff の指摘が0件である
- [ ] 要件にない認証方式を追加していない

#### Validation

| Validation Type | Command / Method | Expected Result |
| --- | --- | --- |
| Build | docker compose build | PASS |
| Static Check | docker compose exec app ruff check . | PASS |
| Unit Test | docker compose exec app pytest | planned |
| Other | 認証応答時間 NFR-PF-09 の測定計画の確認 | 計測方法が定まっている |

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

- 認証系の応答時間（NFR-PF-09）はハッシュ方式の選択に影響されるため、独立ADDR工程の判断を参照する。
- 実装時は本書と併せて、独立ADDR工程が公開する重要判断を参照する。

### TASK-010 `カート照会・明細追加・数量変更・削除API`

#### Metadata

| 項目 | 内容 |
| --- | --- |
| Type | IMPLEMENT |
| Priority | HIGH |
| Status | TODO |
| Target Area | app（カート） |
| Depends On | TASK-004, TASK-006 |
| Blocks | TASK-011, TASK-012 |

#### Source References

| Type | ID / Path | Relevant Section / Reason |
| --- | --- | --- |
| Requirement | NFR-PF-01, NFR-PF-02, NFR-PF-16, NFR-SC-03, NFR-LG-06 | 参照系・更新系の応答時間、カートを DB に保持、所有者判定、数量上限・業務ルール |
| Requirement | FR-020, FR-021, FR-022, FR-023 | 利用中カートの作成、数量上限10、在庫数量以下、明細削除 |
| Use Case / AC | UC-004 | カート操作のフローと AC |
| ADR | None | 方式判断は独立ADDR工程 |
| Detailed Design | docs/specifications/api-contract.md 6.1・6.3 | カート表現、QUANTITY_LIMIT_EXCEEDED・INSUFFICIENT_STOCK の context |

#### Objective

購入者の利用中カートの照会と明細の追加・数量変更・削除を実装し、いずれも更新後のカート表現（明細・クーポン・金額内訳）を返す。

#### Scope

##### In Scope

- 利用中カートがない場合の空カート作成（FR-020）
- 同一在庫単位の合算数量10個以下・在庫数量以下の判定と context 付きエラー
- 明細の追加・数量変更・削除と更新後カート表現の応答
- 削除済み明細への操作を NOT_FOUND とする扱い

##### Out of Scope

- カート投入時の在庫引当（引当は注文確定時。FR-030）
- クーポンの適用・解除（TASK-011）
- 注文確定（TASK-012）

#### Expected Change

- カート系4エンドポイントのビューと共通のカート表現
- 数量・在庫判定と context 生成

#### Constraints

- admin からの要求は PERMISSION_DENIED とすること
- カート表現は FR-020 と同一形式を保つこと
- 業務判定をサーバー側で行うこと（CMN-13）

#### Completion Criteria / Definition of Done

- [ ] UC-004 の AC に対応する正常・例外の振る舞いが実現できる
- [ ] QUANTITY_LIMIT_EXCEEDED・INSUFFICIENT_STOCK の context が 6.3 と一致する
- [ ] ruff の指摘が0件である
- [ ] 要件にない数量ルールを追加していない
- [ ] 確認結果を報告へ残せる

#### Validation

| Validation Type | Command / Method | Expected Result |
| --- | --- | --- |
| Build | docker compose build | PASS |
| Static Check | docker compose exec app ruff check . | PASS |
| Unit Test | docker compose exec app pytest | planned |
| Other | カート表現の項目名と api-contract.md の突き合わせ | 一致 |

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

- カート明細の在庫判定は判定時点の在庫数量で行う（CMN-20）。同時実行の実現方式は独立ADDR工程の判断に従う。
- 実装時は本書と併せて、独立ADDR工程が公開する重要判断を参照する。

### TASK-011 `クーポン適用・解除API（FR-024, FR-025）`

#### Metadata

| 項目 | 内容 |
| --- | --- |
| Type | IMPLEMENT |
| Priority | HIGH |
| Status | TODO |
| Target Area | app（カート） |
| Depends On | TASK-010 |
| Blocks | TASK-019 |

#### Source References

| Type | ID / Path | Relevant Section / Reason |
| --- | --- | --- |
| Requirement | NFR-PF-02, NFR-LG-06 | 更新系の応答時間、クーポン1枚の適用条件 |
| Requirement | FR-024, FR-025 | クーポン1枚の適用条件と解除 |
| Use Case / AC | UC-005 | クーポン適用・解除のフローと AC |
| ADR | None | 方式判断は独立ADDR工程 |
| Detailed Design | docs/specifications/api-contract.md 6.2・6.3 | COUPON_* エラーコードと context |

#### Objective

クーポンコードの判定（存在・有効期間・最低購入金額・適用済み・空カート）と1カート1枚の適用・解除を実装し、更新後のカート表現を返す。

#### Scope

##### In Scope

- クーポンコードの正規化（英大文字）と存在判定
- 有効期間・最低購入金額・適用済み・空カートの判定順序とエラーコード
- 適用・解除後のカート表現（coupon・amounts の再計算）

##### Out of Scope

- クーポンの登録・更新（FR-060 でのみ行う）
- 複数クーポンの併用（要件外）
- 注文確定時の再判定（TASK-012）

#### Expected Change

- クーポン適用・解除のビューと判定
- 適用可否・不可理由を含むカート表現

#### Constraints

- 1カートにつきクーポンは1枚までとすること
- 有効期間の判定は秒単位の JST で行うこと（CMN-29）
- エラー時の context を 6.3 に一致させること

#### Completion Criteria / Definition of Done

- [ ] UC-005 の AC に対応する正常・例外の振る舞いが実現できる
- [ ] COUPON_NOT_FOUND・COUPON_EXPIRED 等が判定順序どおりに返る
- [ ] ruff の指摘が0件である
- [ ] 要件にない割引条件を追加していない
- [ ] 確認結果を報告へ残せる

#### Validation

| Validation Type | Command / Method | Expected Result |
| --- | --- | --- |
| Build | docker compose build | PASS |
| Static Check | docker compose exec app ruff check . | PASS |
| Unit Test | docker compose exec app pytest | planned |
| Other | 判定順序と FR-024 の手順の突き合わせ | 一致 |

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

- 適用中クーポンが条件を満たさなくなった場合の表示（is_applicable, not_applicable_reason）は FR-026 の算出に従う。
- 実装時は本書と併せて、独立ADDR工程が公開する重要判断を参照する。

### TASK-012 `注文確定API（FR-030）`

#### Metadata

| 項目 | 内容 |
| --- | --- |
| Type | IMPLEMENT |
| Priority | HIGH |
| Status | TODO |
| Target Area | app（注文） |
| Depends On | TASK-006, TASK-010 |
| Blocks | TASK-013, TASK-014, TASK-015, TASK-016 |

#### Source References

| Type | ID / Path | Relevant Section / Reason |
| --- | --- | --- |
| Requirement | NFR-PF-02, NFR-PF-04, NFR-PF-05, NFR-PF-07, NFR-PF-11, NFR-SC-22, NFR-LG-06, NFR-LG-09 | 更新系の応答時間、ピーク時処理能力、同時利用者数、同時実行時の在庫整合、上限超過時の挙動、注文状態履歴の記録、在庫引当・状態遷移、都道府県コード |
| Requirement | FR-030 | 配送先入力、再判定、全明細の一括在庫引当、注文作成 |
| Use Case / AC | UC-006 | 注文確定のフローと AC |
| ADR | None | 同時実行制御の方式判断は独立ADDR工程 |
| Detailed Design | docs/specifications/api-contract.md 6.1・6.3 | POST /api/checkout（201）、注文詳細表現、ITEM_NOT_AVAILABLE の context |

#### Objective

配送先を受け付け、数量上限・公開状態・クーポン条件・在庫を再判定して全明細の在庫を一括で引き当て、注文・注文明細・配送先・注文状態履歴を作成する。

#### Scope

##### In Scope

- 配送先の入力検証と保存（D-12 の項目）
- 注文確定時の再判定（数量10以下、商品の公開、クーポンの有効期間・最低購入金額、全明細の在庫）
- 全明細の在庫数量減算と注文番号の採番、カート状態の注文済への変更
- 注文状態履歴の記録（遷移元なし→注文受付）と注文詳細表現の応答
- 二重送信時に注文を1件だけ作成し、後続を CART_EMPTY とする扱い

##### Out of Scope

- 支払（TASK-013）
- キャンセル・在庫戻し（TASK-015、TASK-017）
- 配送業者連携（要件外）

#### Expected Change

- 注文確定のビュー・トランザクション処理・在庫引当
- 注文詳細表現（lines・amounts・shipping_address・status_history）

#### Constraints

- 全成功か無変更のどちらかとすること（Steering 8.2、CMN-21）
- 在庫数量が0未満にならないこと（CMN-20）
- 不足が複数ある場合は INSUFFICIENT_STOCK の context に全件を含めること

#### Completion Criteria / Definition of Done

- [ ] UC-006 の AC に対応する正常・例外の振る舞いが実現できる
- [ ] 注文確定の成功時に注文・明細・配送先・状態履歴・在庫減算が一括で確定する
- [ ] エラー時にデータ変更が残らない
- [ ] ruff の指摘が0件である
- [ ] 要件にない注文項目を追加していない

#### Validation

| Validation Type | Command / Method | Expected Result |
| --- | --- | --- |
| Build | docker compose build | PASS |
| Static Check | docker compose exec app ruff check . | PASS |
| Unit Test | docker compose exec app pytest | planned |
| Other | 同時実行時の在庫整合の確認計画（NFR-PF-07） | 計測方法が定まっている |

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

- 在庫引当の排他方式（行ロック等）は要件が結果のみを定めるため、独立ADDR工程の判断対象（BLK-003）。
- 実装時は本書と併せて、独立ADDR工程が公開する重要判断を参照する。

### TASK-013 `支払API（FR-031、模擬決済の結果反映）`

#### Metadata

| 項目 | 内容 |
| --- | --- |
| Type | IMPLEMENT |
| Priority | HIGH |
| Status | TODO |
| Target Area | app（注文・決済） |
| Depends On | TASK-007, TASK-012 |
| Blocks | TASK-019 |

#### Source References

| Type | ID / Path | Relevant Section / Reason |
| --- | --- | --- |
| Requirement | NFR-PF-02, NFR-PF-07, NFR-PF-17, NFR-SC-22 | 更新系の応答時間、同時実行時の整合、決済連携部分の分離、注文状態履歴の記録 |
| Requirement | FR-031 | 決済要求・結果反映・決済記録の登録 |
| Use Case / AC | UC-007 | 承認・否認・応答なしのフローと AC |
| ADR | None | 方式判断は独立ADDR工程 |
| Detailed Design | docs/specifications/api-contract.md 6.1・6.2 | POST /api/purchase-orders/{purchase_order_id}/pay、PAYMENT_DECLINED・PAYMENT_SERVICE_ERROR |

#### Objective

注文受付の自分の注文について模擬決済へ支払を要求し、承認時に支払済へ遷移、否認・外部連携エラー時は決済記録のみ登録して注文を注文受付のまま維持する。

#### Scope

##### In Scope

- 本人所有・状態の判定（他人の注文は NOT_FOUND、状態不正は INVALID_STATUS_TRANSITION）
- IF-01 への要求と結果の反映、決済記録（approved／declined／error）の登録
- 承認時の注文状態更新・支払日時・注文状態履歴の記録
- 承認済み決済を1注文につき最大1件とする扱い（後着は INVALID_STATUS_TRANSITION）

##### Out of Scope

- 返金（本システム外）
- 自動再送（二重決済防止のため行わない）
- 決済記録の照会画面（管理者詳細は TASK-016）

#### Expected Change

- 支払のビュー・決済記録登録・状態遷移
- 否認・外部連携エラー時の例外的なデータ保存（CMN-21 のただし書き）

#### Constraints

- 否認・外部連携エラーでも決済記録を残し注文は created のままとすること
- 応答待ち最大10秒・自動再送なしとすること
- 決済金額は注文の合計金額（整数円）、通貨は JPY とすること

#### Completion Criteria / Definition of Done

- [ ] UC-007 の AC に対応する正常・例外の振る舞いが実現できる
- [ ] 承認時に注文詳細表現（FR-033 と同じ形）が返る
- [ ] 二重送信時に承認済み決済が1件を超えない
- [ ] ruff の指摘が0件である
- [ ] 要件にない決済機能を追加していない

#### Validation

| Validation Type | Command / Method | Expected Result |
| --- | --- | --- |
| Build | docker compose build | PASS |
| Static Check | docker compose exec app ruff check . | PASS |
| Unit Test | docker compose exec app pytest | planned |
| Other | 決済記録と注文状態の整合確認（UC-007 の事後条件） | 一致 |

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

- 支払の同時要求に対する一意性の実現方式は独立ADDR工程の判断対象。
- 実装時は本書と併せて、独立ADDR工程が公開する重要判断を参照する。

### TASK-014 `購入者向け注文照会API（FR-032, FR-033）`

#### Metadata

| 項目 | 内容 |
| --- | --- |
| Type | IMPLEMENT |
| Priority | HIGH |
| Status | TODO |
| Target Area | app（注文） |
| Depends On | TASK-012 |
| Blocks | None |

#### Source References

| Type | ID / Path | Relevant Section / Reason |
| --- | --- | --- |
| Requirement | NFR-PF-01, NFR-PF-08, NFR-SC-03, NFR-SC-24, NFR-LG-01 | 照会系の応答時間、1ページ20件、所有者判定、決済記録を購入者へ返さない、個人情報の取扱い |
| Requirement | FR-032, FR-033 | 注文履歴一覧（20件/ページ）と注文詳細 |
| Use Case / AC | UC-008 | 注文履歴・注文状況の確認フローと AC |
| ADR | None | 方式判断は独立ADDR工程 |
| Detailed Design | docs/specifications/api-contract.md status_history 節 | 購入者の状態履歴は actor_user_id を含めない |

#### Objective

購入者本人の注文履歴一覧と注文詳細（明細・金額・配送先・状態履歴）を返す API を実装する。

#### Scope

##### In Scope

- 自分の注文のみを注文日時の新しい順に20件/ページで返す
- 注文詳細の明細・金額内訳・配送先・状態履歴・操作可否（can_pay, can_cancel）
- 他人の注文指定時の NOT_FOUND

##### Out of Scope

- 管理者向け注文照会（TASK-016）
- 注文状態履歴の独立した検索機能（CMN-27 のため提供しない）
- CSV 等の出力（CMN-37 のため提供しない）

#### Expected Change

- 注文一覧・注文詳細のビューと表現
- 購入者向け status_history（actor_role のみ）

#### Constraints

- 購入者には実行者利用者IDを提供しないこと（REF-25）
- ページング形式を共通基盤に合わせること
- 決済記録を購入者へ提供しないこと（REF-23）

#### Completion Criteria / Definition of Done

- [ ] UC-008 の AC に対応する振る舞いが実現できる
- [ ] 応答項目名が api-contract.md と一致する
- [ ] ruff の指摘が0件である
- [ ] 要件にない項目を購入者へ返していない
- [ ] 確認結果を報告へ残せる

#### Validation

| Validation Type | Command / Method | Expected Result |
| --- | --- | --- |
| Build | docker compose build | PASS |
| Static Check | docker compose exec app ruff check . | PASS |
| Unit Test | docker compose exec app pytest | planned |
| Other | 参照ルール（REF-23, REF-25）との突き合わせ | 一致 |

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

- 一覧の応答件数上限（NFR-PF-08）は共通ページング基盤に従う。
- 実装時は本書と併せて、独立ADDR工程が公開する重要判断を参照する。

### TASK-015 `購入者の注文キャンセルAPI（FR-034）`

#### Metadata

| 項目 | 内容 |
| --- | --- |
| Type | IMPLEMENT |
| Priority | HIGH |
| Status | TODO |
| Target Area | app（注文） |
| Depends On | TASK-012 |
| Blocks | TASK-019 |

#### Source References

| Type | ID / Path | Relevant Section / Reason |
| --- | --- | --- |
| Requirement | NFR-PF-02, NFR-SC-22, NFR-LG-06 | 更新系の応答時間、注文状態履歴の記録、キャンセル可能状態の判定 |
| Requirement | FR-034 | 出荷前の本人注文のキャンセルと在庫戻し |
| Use Case / AC | UC-009 | 購入者キャンセルのフローと AC |
| ADR | None | 方式判断は独立ADDR工程 |
| Detailed Design | docs/specifications/api-contract.md 6.2・6.3 | INVALID_STATUS_TRANSITION の context（current_status） |

#### Objective

注文受付・支払済の本人注文をキャンセル済へ遷移させ、全明細の数量を在庫数量へ戻し、注文状態履歴を記録する。

#### Scope

##### In Scope

- 本人所有・状態の判定と例外（他人は NOT_FOUND、状態不正は INVALID_STATUS_TRANSITION）
- 全明細の在庫戻しと状態遷移・履歴記録の一括確定
- キャンセル後の注文詳細表現の応答

##### Out of Scope

- 返金処理（本システム外で EC運営担当が行う）
- 管理者によるキャンセル（TASK-017）
- 出荷済・配達完了注文のキャンセル（要件外）

#### Expected Change

- キャンセルのビューとトランザクション処理
- 在庫戻しと状態履歴の記録

#### Constraints

- 全成功か無変更のどちらかとすること（CMN-21）
- キャンセル済は終端状態とし再遷移しないこと（ST-PO-03〜ST-PO-04）
- 同時実行の競合は INVALID_STATUS_TRANSITION とすること（CMN-19）

#### Completion Criteria / Definition of Done

- [ ] UC-009 の AC に対応する正常・例外の振る舞いが実現できる
- [ ] キャンセル後に在庫数量が戻り、注文状態履歴が1件増える
- [ ] ruff の指摘が0件である
- [ ] 要件にないキャンセル条件を追加していない
- [ ] 確認結果を報告へ残せる

#### Validation

| Validation Type | Command / Method | Expected Result |
| --- | --- | --- |
| Build | docker compose build | PASS |
| Static Check | docker compose exec app ruff check . | PASS |
| Unit Test | docker compose exec app pytest | planned |
| Other | 状態遷移表（ST-PO-03, ST-PO-04）との突き合わせ | 一致 |

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

- 購入者と管理者のキャンセルは同じ状態遷移を用いるため、共通処理の再利用方針は独立ADDR工程の判断に従う。
- 実装時は本書と併せて、独立ADDR工程が公開する重要判断を参照する。

### TASK-016 `管理者向け照会API（在庫単位一覧・注文一覧・注文詳細）`

#### Metadata

| 項目 | 内容 |
| --- | --- |
| Type | IMPLEMENT |
| Priority | HIGH |
| Status | TODO |
| Target Area | app（管理） |
| Depends On | TASK-012 |
| Blocks | TASK-017 |

#### Source References

| Type | ID / Path | Relevant Section / Reason |
| --- | --- | --- |
| Requirement | NFR-PF-01, NFR-PF-06, NFR-PF-08, NFR-SC-03, NFR-SC-23, NFR-SC-24, NFR-LG-01 | 照会系の応答時間、将来データ量、1ページ50件／20件、権限判定、履歴の追記のみ、決済記録・個人情報の表示範囲、個人情報の安全管理措置 |
| Requirement | FR-040, FR-041, FR-042 | 在庫単位50件/ページ、注文検索20件/ページ、管理者向け注文詳細 |
| Use Case / AC | UC-010, UC-011 | 在庫確認・注文確認のフローと AC |
| ADR | None | 方式判断は独立ADDR工程 |
| Detailed Design | docs/specifications/api-contract.md 6.1 | /api/admin/stock-units、/api/admin/purchase-orders |

#### Objective

管理者が在庫単位の在庫数量・低在庫を確認し、注文を注文番号・状態・注文日・購入者メールアドレスで検索して詳細（購入者情報・決済記録・状態履歴）を確認できる API を実装する。

#### Scope

##### In Scope

- 在庫単位一覧（非公開商品を含む、低在庫の絞り込み、50件/ページ）
- 注文一覧検索（status の複数指定、ordered_from／ordered_to は JST の日付で両端を含む、20件/ページ）
- 管理者向け注文詳細（buyer・payment_records・actor_user_id を含む status_history）

##### Out of Scope

- 在庫数量の更新（FR-060・注文確定・キャンセルでのみ変化。CMN-38）
- 出荷・配達完了・キャンセル登録（TASK-017）
- 帳票・CSV 出力（CMN-37）

#### Expected Change

- 管理者向け3エンドポイントのビューと表現
- 低在庫判定と検索条件の処理

#### Constraints

- buyer からの要求は PERMISSION_DENIED とすること
- 個人情報（buyer_email, buyer_name）は管理者のみへ提供すること（DCN-10）
- 注文状態履歴・監査ログは参照のみとし、更新・削除の API を設けないこと（NFR-SC-23）
- ページングは共通基盤に合わせること

#### Completion Criteria / Definition of Done

- [ ] UC-010・UC-011 の照会に関する AC を満たす
- [ ] 応答項目名が api-contract.md と一致する
- [ ] ruff の指摘が0件である
- [ ] 要件にない検索条件・項目を追加していない
- [ ] 確認結果を報告へ残せる

#### Validation

| Validation Type | Command / Method | Expected Result |
| --- | --- | --- |
| Build | docker compose build | PASS |
| Static Check | docker compose exec app ruff check . | PASS |
| Unit Test | docker compose exec app pytest | planned |
| Other | 低在庫しきい値（在庫数量5以下）の確認 | FR-040 と一致 |

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

- 3年後の想定データ量での応答時間（NFR-PF-06）の達成方式は独立ADDR工程の判断に従う。
- 実装時は本書と併せて、独立ADDR工程が公開する重要判断を参照する。

### TASK-017 `管理者向け注文更新API（出荷・配達完了・キャンセル）`

#### Metadata

| 項目 | 内容 |
| --- | --- |
| Type | IMPLEMENT |
| Priority | HIGH |
| Status | TODO |
| Target Area | app（管理） |
| Depends On | TASK-016 |
| Blocks | TASK-020 |

#### Source References

| Type | ID / Path | Relevant Section / Reason |
| --- | --- | --- |
| Requirement | NFR-PF-02, NFR-PF-07, NFR-SC-03, NFR-SC-22, NFR-LG-06 | 更新系の応答時間、同時実行時の整合、権限判定、注文状態履歴の記録、状態遷移の順序 |
| Requirement | FR-043, FR-044, FR-045 | 出荷登録・配達完了登録・管理者キャンセル |
| Use Case / AC | UC-011, UC-012 | 出荷・配達完了・キャンセルのフローと AC |
| ADR | None | 方式判断は独立ADDR工程 |
| Detailed Design | docs/specifications/api-contract.md 6.1 | /ship、/deliver、/cancel（管理者向け注文詳細表現） |

#### Objective

支払済注文の出荷登録、出荷済注文の配達完了登録、出荷前注文の管理者キャンセル（在庫戻し）を実装し、いずれも管理者向け注文詳細表現を返す。

#### Scope

##### In Scope

- 状態判定と遷移（支払済→出荷済、出荷済→配達完了、注文受付・支払済→キャンセル済）
- 出荷日時・配送伝票番号（任意）・配達完了日時の記録
- 管理者キャンセル時の全明細の在庫戻し
- 注文状態履歴（実行者利用者ID・実行者ロールを含む）の記録

##### Out of Scope

- 配送業者システム連携（要件外）
- 購入者向けの通知（FR-OUT-08）
- 出荷済・配達完了注文のキャンセル（要件外）

#### Expected Change

- 管理者向け更新3エンドポイントのビューとトランザクション処理
- 状態遷移と履歴記録の共通処理の再利用

#### Constraints

- 全成功か無変更のどちらかとすること（CMN-21）
- 状態不正は INVALID_STATUS_TRANSITION（context に current_status）とすること
- 配送伝票番号は任意入力とすること（FR-043）

#### Completion Criteria / Definition of Done

- [ ] UC-011・UC-012 の AC に対応する正常・例外の振る舞いが実現できる
- [ ] キャンセル時に在庫数量が戻り、状態履歴が記録される
- [ ] ruff の指摘が0件である
- [ ] 要件にない状態・操作を追加していない
- [ ] 確認結果を報告へ残せる

#### Validation

| Validation Type | Command / Method | Expected Result |
| --- | --- | --- |
| Build | docker compose build | PASS |
| Static Check | docker compose exec app ruff check . | PASS |
| Unit Test | docker compose exec app pytest | planned |
| Other | 状態遷移表（ST-PO-01〜ST-PO-06）との突き合わせ | 一致 |

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

- 出荷・配達・キャンセルの同時操作の競合は業務エラーで返す（CMN-19）。実現方式は独立ADDR工程の判断に従う。
- 実装時は本書と併せて、独立ADDR工程が公開する重要判断を参照する。

### TASK-018 `初期データ一括投入コマンド（FR-060）`

#### Metadata

| 項目 | 内容 |
| --- | --- |
| Type | IMPLEMENT |
| Priority | HIGH |
| Status | TODO |
| Target Area | app（運用コマンド） |
| Depends On | TASK-002, TASK-004 |
| Blocks | TASK-021 |

#### Source References

| Type | ID / Path | Relevant Section / Reason |
| --- | --- | --- |
| Requirement | FR-060, NFR-OM-04, NFR-PF-10 | 定義ファイルからの一括投入、運用操作、60秒以内 |
| Requirement | NFR-SC-01, NFR-SC-04, NFR-SC-06, NFR-SC-15, NFR-SC-16 | パスワードのハッシュ保存、全項目の検証とプレースホルダによる DB 操作、標準出力への機密情報非出力、管理者アカウントは本コマンドでのみ作成、初期パスワードの条件 |
| Requirement | NFR-SC-22, NFR-SC-25, NFR-OM-11, NFR-OM-13, NFR-MG-02, NFR-MG-03, NFR-MG-04, NFR-MG-07 | 監査ログ1件の記録、検証環境で本番データを使わない、LOG-04 の出力、異常終了時の全件取消しと再実行、投入件数の一致、管理者アカウントの登録、一括登録、切戻し |
| Use Case / AC | UC-013 | 初期データ一括投入のフローと AC |
| ADR | None | 定義ファイルの項目名・読込方式の判断は独立ADDR工程 |
| Detailed Design | docs/architecture/files/FILE-001.md | 定義ファイルの項目・変換・異常処理・検証観点 |

#### Objective

定義ファイル（JSON、UTF-8）から利用者・仕入先・商品分類・商品・商品分類所属・在庫単位・クーポンを一括投入する管理コマンドを実装し、違反が1件でもあれば何も投入しないようにする。

#### Scope

##### In Scope

- 引数（定義ファイルのパス）と全削除指定オプションの判定
- 値域・一意性・参照整合性の全件判定と違反の全件出力（データ名・行番号・項目名・理由）
- 全削除指定時の監査ログ以外の全データ削除と、業務キーによる参照解決・識別子の付与
- パスワードのハッシュ化保存、商品分類の深さ算出、既定値の設定
- 監査ログ1件の記録と標準出力のデータ別投入件数、終了コードの制御

##### Out of Scope

- 画面・Web API からのファイル受け付け（CMN-37 のため提供しない）
- 保存期間経過データの自動削除（本リリース対象外）
- 定義ファイルそのものの作成（運用者の作業）

#### Expected Change

- 管理コマンド（load_initial_data）と検証・投入処理
- FILE-001 の編集・変換ルールと異常処理の実装
- app/seed/ に配置する定義ファイルの読み取り

#### Constraints

- 削除・登録・監査ログを一括確定とすること（CMN-21、Steering 8.2）
- 標準出力・標準エラー出力に項目の値（パスワード・メールアドレス・氏名）を出力しないこと
- 検証データには架空の値のみを用いること。本番環境のデータ（個人情報を含む DB・バックアップ）を検証環境で利用しないこと（DCN-15、NFR-SC-25、Steering 11章）
- 定義ファイルの全項目をサーバー側で検証し、DB の操作はプレースホルダ（パラメータ化）で行うこと（NFR-SC-04、VUL-04）
- 管理者アカウント（ロール admin）は本コマンドでのみ作成し、画面・API から作成できないこと（NFR-SC-15）
- 管理者の初期パスワードに共通の既定値を用いず、要件の文字数・文字種の条件を満たすこと（NFR-SC-16、VUL-08）
- 監査ログは削除せず、本コマンドの結果を追記するのみとすること（NFR-SC-23、CMN-21）

#### Completion Criteria / Definition of Done

- [ ] UC-013 の AC に対応する正常・例外の振る舞いが実現できる
- [ ] FILE-001 の検証観点（FILE-V-001〜FILE-V-007）を確認できる状態である
- [ ] 成功時は終了コード0、失敗時は0以外となる
- [ ] ruff の指摘が0件である
- [ ] 定義ファイル由来の値で SQL 文を文字列連結していない（NFR-SC-04）
- [ ] 全削除指定でも監査ログが削除されず、結果が1件追記される（NFR-SC-23）
- [ ] 要件にないオプション・出力を追加していない

#### Validation

| Validation Type | Command / Method | Expected Result |
| --- | --- | --- |
| Build | docker compose build | PASS |
| Static Check | docker compose exec app ruff check . | PASS |
| Unit Test | docker compose exec app pytest | planned |
| Other | docker compose exec app python manage.py load_initial_data seed/initial_data.json --reset | 終了コード0・件数一致 |

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

- 定義ファイルのトップレベルキー名と参照項目名は要件未定義のため、独立ADDR工程の判断を受けてから実装を確定する（BLK-001、OQ-FILE-001）。
- 実装時は本書と併せて、独立ADDR工程が公開する重要判断を参照する。

### TASK-019 `来訪者・購入者向け画面（SCR-001〜SCR-010, SCR-901）`

#### Metadata

| 項目 | 内容 |
| --- | --- |
| Type | IMPLEMENT |
| Priority | MEDIUM |
| Status | TODO |
| Target Area | app（画面） |
| Depends On | TASK-011, TASK-013, TASK-015 |
| Blocks | None |

#### Source References

| Type | ID / Path | Relevant Section / Reason |
| --- | --- | --- |
| Requirement | FR-001, FR-002, FR-010, FR-011, FR-012 | 会員登録・ログイン・分類表示・商品一覧・商品詳細の各画面が呼び出す業務機能 |
| Requirement | FR-020, FR-021, FR-022, FR-023, FR-024, FR-025 | カート画面の表示・明細追加・数量変更・削除・クーポン適用／解除 |
| Requirement | FR-030, FR-031, FR-032, FR-033, FR-034 | 注文手続き・支払・注文履歴・注文詳細・キャンセルの各画面 |
| Requirement | NFR-SC-03, NFR-SC-05, NFR-SC-09, NFR-SC-12, NFR-SC-19, NFR-SC-21 | サーバー側の区分判定、出力エスケープと CSRF トークン検証、無操作30分、画面はログインセッションで識別、ログイン時のセッション識別子の再発行、8.2 の対策方針（VUL-05・VUL-06） |
| Requirement | NFR-EN-05, NFR-EN-09, NFR-PF-03, NFR-US-01, NFR-US-02, NFR-US-03, NFR-US-04, NFR-US-05, NFR-US-06, NFR-US-07, NFR-US-08, NFR-US-09, NFR-US-10, NFR-LG-02, NFR-LG-08 | 外部 CDN 不使用、サーバーサイドレンダリング、表示完了時間、対応ブラウザ・解像度・言語・アクセシビリティ・手順数・確認ダイアログ・二重送信防止、総額表示 |
| Use Case / AC | UC-003, UC-004, UC-005, UC-006, UC-007, UC-008, UC-009 | 画面操作としてのフローと AC |
| ADR | None | テンプレート構成・セッション方式の判断は独立ADDR工程 |
| Detailed Design | docs/requirements/ui_report_requirements.md 2章・5.1〜5.10・5.14 | 画面項目・操作・メッセージ表示位置 |

#### Objective

Django テンプレートによる来訪者・購入者向け画面を実装し、API と同一の業務ロジック・判定順序・エラーコードで商品閲覧から注文・支払・キャンセルまでを操作できるようにする。

#### Scope

##### In Scope

- 商品一覧・商品詳細・会員登録・ログイン・カート・注文手続き・注文完了・支払・注文履歴・注文詳細・エラー画面
- 共通レイアウト（ヘッダー・メッセージ領域）と入力エラーの項目近傍表示
- ログイン要否による遷移（未ログイン時は SCR-004 へ遷移し、ログイン後に元の画面へ戻る）
- 二重送信防止（送信後の再押下抑止）と CSRF 対策用トークンの検証、出力の HTML エスケープ
- ログイン成功時のセッション識別子の再発行とログイン前の識別子の無効化、ログアウト時の破棄（NFR-SC-19）

##### Out of Scope

- 業務ルールの画面側での再実装（Steering 4.2 で禁止）
- SPA 化・外部 CDN の利用（NFR-EN-05）
- 管理者向け画面（TASK-020）

#### Expected Change

- 購入者向けテンプレートとビュー
- 画面セッション（無操作30分）とログイン後復帰の処理
- 総額表示（税込価格を主、税抜価格を併記）

#### Constraints

- 対象ブラウザは Chrome・Edge 最新版、画面幅1280px 以上とすること（NFR-US-01, NFR-US-02）
- 業務判定結果はサーバー側を正とすること（CMN-13）
- 画面表示2.0秒以内の目標（NFR-PF-03）を妨げる構成にしないこと
- 画面に出力する全ての値を HTML エスケープし、テンプレートの自動エスケープを無効化しないこと（NFR-SC-05、VUL-05）
- Cookie のログインセッションで認証する全ての更新要求で CSRF 対策用トークンを検証し、トークンが無い・一致しない要求を拒否すること。更新操作は GET 以外のメソッドに限ること（NFR-SC-05、VUL-06）
- ログイン成功時にセッション識別子を再発行し、ログイン前の識別子を無効化すること（NFR-SC-19、VUL-02）
- JavaScript は確認ダイアログの表示と二重送信の防止に限って使い、HTML の生成に用いないこと（NFR-EN-09、NFR-US-09、NFR-US-10）

#### Completion Criteria / Definition of Done

- [ ] SCR-001〜SCR-010・SCR-901 の画面要件に対応する表示・操作が実現できる
- [ ] 画面と API が同一のエラー文言・判定順序に従う
- [ ] ruff の指摘が0件である
- [ ] 全ての画面出力値が HTML エスケープされ、自動エスケープを無効化した箇所が無い（NFR-SC-05）
- [ ] 画面からの全ての更新要求で CSRF 対策用トークンが検証される（NFR-SC-05）
- [ ] ログイン成功時にセッション識別子が再発行され、ログイン前の識別子では操作できない（NFR-SC-19）
- [ ] 要件にない画面・操作を追加していない
- [ ] 確認結果を報告へ残せる

#### Validation

| Validation Type | Command / Method | Expected Result |
| --- | --- | --- |
| Build | docker compose build | PASS |
| Static Check | docker compose exec app ruff check . | PASS |
| Unit Test | docker compose exec app pytest | planned |
| Other | 画面要件（ui_report_requirements.md 5章）との突き合わせ | 一致 |

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

- 画面セッションの保存方式と CSRF の実現方式は独立ADDR工程の判断対象（BLK-005、ARCH-CI-005）。方式が未判断でも、再発行・トークン検証・自動エスケープの要求自体は本Taskの制約として固定する。
- 画面テンプレートの構成（共通レイアウトの分割単位と再利用方法）は独立ADDR工程の判断対象として残す（BLK-008、ARCH-CI-010）。
- 実装時は本書と併せて、独立ADDR工程が公開する重要判断を参照する。

### TASK-020 `管理者向け画面（SCR-101〜SCR-103）`

#### Metadata

| 項目 | 内容 |
| --- | --- |
| Type | IMPLEMENT |
| Priority | MEDIUM |
| Status | TODO |
| Target Area | app（画面） |
| Depends On | TASK-017 |
| Blocks | None |

#### Source References

| Type | ID / Path | Relevant Section / Reason |
| --- | --- | --- |
| Requirement | FR-040, FR-041, FR-042, FR-043, FR-044, FR-045 | 管理者が操作する業務機能 |
| Requirement | NFR-SC-03, NFR-SC-05, NFR-SC-21, NFR-SC-23, NFR-SC-24, NFR-LG-01 | サーバー側の権限判定、出力エスケープと CSRF トークン検証、8.2 の対策方針（VUL-05・VUL-06）、履歴の追記のみ、個人情報・決済記録の表示範囲、個人情報の安全管理措置 |
| Requirement | NFR-EN-09, NFR-PF-03, NFR-US-01, NFR-US-02, NFR-US-03, NFR-US-04, NFR-US-05, NFR-US-06, NFR-US-07, NFR-US-09, NFR-US-10, NFR-LG-08 | サーバーサイドレンダリング、表示完了時間、対応ブラウザ・解像度・言語・入力エラー表示・アクセシビリティ・確認ダイアログ・二重送信防止 |
| Use Case / AC | UC-010, UC-011, UC-012 | 在庫確認・出荷登録・配達完了登録・キャンセルのフローと AC |
| ADR | None | 方式判断は独立ADDR工程 |
| Detailed Design | docs/requirements/ui_report_requirements.md 5.11〜5.13 | 在庫単位一覧・注文一覧・注文詳細（管理）の画面項目 |

#### Objective

管理者向けの在庫単位一覧・注文一覧・注文詳細の画面を実装し、出荷登録・配達完了登録・キャンセルを画面から実行できるようにする。

#### Scope

##### In Scope

- 在庫単位一覧（低在庫絞り込み、50件/ページ）
- 注文一覧（検索条件・20件/ページ、管理者のログイン後トップ）
- 注文詳細（決済記録・状態履歴の表示、出荷・配達完了・キャンセルの操作）
- 購入者向け機能を管理者へ表示しないこと
- 出力の HTML エスケープと、更新操作（出荷・配達完了・キャンセル）の CSRF 対策用トークン検証
- 取消できない操作の確認ダイアログ表示と二重送信の防止（NFR-US-09、NFR-US-10）

##### Out of Scope

- マスタ保守画面（FR-OUT-02 のため提供しない）
- 購入機能（admin は利用できない）
- 帳票出力（FR-OUT-15）

#### Expected Change

- 管理者向けテンプレートとビュー
- 操作可否（can_ship, can_deliver, can_cancel）に応じた操作の表示制御

#### Constraints

- 権限判定をサーバー側で行い、buyer のアクセスは SCR-901 とすること（CMN-03）
- 個人情報の表示は管理者に限ること（DCN-10）
- 業務ルールを画面側で再実装しないこと
- 画面に出力する全ての値を HTML エスケープし、テンプレートの自動エスケープを無効化しないこと（NFR-SC-05、VUL-05）
- Cookie のログインセッションで認証する全ての更新要求で CSRF 対策用トークンを検証し、更新操作は GET 以外のメソッドに限ること（NFR-SC-05、VUL-06）
- 注文状態履歴・監査ログは参照のみとし、更新・削除の操作を画面に設けないこと（NFR-SC-23）
- JavaScript は確認ダイアログの表示と二重送信の防止に限って使うこと（NFR-EN-09）

#### Completion Criteria / Definition of Done

- [ ] SCR-101〜SCR-103 の画面要件に対応する表示・操作が実現できる
- [ ] 出荷・配達完了・キャンセルが画面から実行でき、結果が注文詳細へ反映される
- [ ] ruff の指摘が0件である
- [ ] 管理者画面の全出力値が HTML エスケープされ、自動エスケープを無効化した箇所が無い（NFR-SC-05）
- [ ] 出荷・配達完了・キャンセルの更新要求で CSRF 対策用トークンが検証される（NFR-SC-05）
- [ ] 注文状態履歴・監査ログの更新・削除の操作が画面に無い（NFR-SC-23）
- [ ] 要件にない管理機能を追加していない
- [ ] 確認結果を報告へ残せる

#### Validation

| Validation Type | Command / Method | Expected Result |
| --- | --- | --- |
| Build | docker compose build | PASS |
| Static Check | docker compose exec app ruff check . | PASS |
| Unit Test | docker compose exec app pytest | planned |
| Other | 画面要件（ui_report_requirements.md 5.11〜5.13）との突き合わせ | 一致 |

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

- 管理者の同時利用は最大5人（ACT-003）であり、特別な負荷対策は要件化されていない。
- 画面テンプレートの構成（共通レイアウトの分割単位と購入者向け画面との共有方法）は独立ADDR工程の判断対象として残す（BLK-008、ARCH-CI-010）。
- 実装時は本書と併せて、独立ADDR工程が公開する重要判断を参照する。

### TASK-021 `起動・運用手順の整備（README・環境変数雛形）`

#### Metadata

| 項目 | 内容 |
| --- | --- |
| Type | OTHER |
| Priority | MEDIUM |
| Status | TODO |
| Target Area | repository root |
| Depends On | TASK-001, TASK-018 |
| Blocks | None |

#### Source References

| Type | ID / Path | Relevant Section / Reason |
| --- | --- | --- |
| Requirement | NFR-OM-04, NFR-OM-05, NFR-OM-19, NFR-SC-07 | 運用操作・1コマンド起動・手順書整備・秘密情報の扱い |
| Requirement | NFR-OM-17, NFR-SC-25 | 環境ごとに異なる設定の変更手順、本番以外の環境で本番データを利用しない |
| Use Case / AC | UC-013 | 運用者が手順に従って初期データを投入する |
| ADR | None | 方式判断は独立ADDR工程 |
| Detailed Design | .github/project-context/project-ai-steering.md 9章 | ビルド・起動・マイグレーション・投入・静的解析・テストのコマンド |

#### Objective

README と .env.example を整備し、起動・マイグレーション・初期データ投入・静的解析・テストの手順を Steering 9章のコマンドどおりに実行できるようにする。

#### Scope

##### In Scope

- README の起動・実行手順（build／up／migrate／seed／ruff／pytest）
- .env.example の環境変数項目（実値を含めない）
- 初期データ投入の実行例と --reset の使用上の注意（本番では使用しない）
- バージョン管理の除外設定（.env、app/seed/ 配下の初期データ定義ファイル）の記載と確認手順（NFR-SC-07）
- 環境ごとに異なる設定（デバッグ表示・許可ホスト名・Cookie Secure 属性・DB 接続情報・秘密鍵）の変更手順（NFR-OM-17）
- 検証環境で本番データを使用せず、検証データは架空の値のみとする旨の明記（NFR-SC-25）

##### Out of Scope

- 本番環境の構築手順（OQ-PJ-001 として未決）
- 監視・バックアップ運用手順（本番運用時に設定）
- 秘密情報の実値の記載（禁止）

#### Expected Change

- README.md の手順節
- .env.example の雛形
- 運用上の注意（検証環境限定の --reset）

#### Constraints

- Steering 9章のコマンド・作業ディレクトリと一致させること
- 秘密情報をリポジトリへ含めないこと（NFR-SC-07）
- 本番環境で --reset を実行しない旨を明記すること（Steering 11章）
- 初期データ定義ファイル（平文パスワードを含む。CLS-04）をリポジトリへ含めないこと（NFR-SC-07、NFR-SC-25）

#### Completion Criteria / Definition of Done

- [ ] README の手順どおりに起動から初期データ投入まで実行できる
- [ ] .env.example に実値が含まれていない
- [ ] 手順と Steering 9章の記載が一致する
- [ ] .env と初期データ定義ファイルがバージョン管理の除外設定に含まれていることを手順で確認できる（NFR-SC-07）
- [ ] 環境ごとに異なる設定の変更手順が README に記載されている（NFR-OM-17）
- [ ] 要件にない運用手順を追加していない
- [ ] 実行結果を報告へ残せる

#### Validation

| Validation Type | Command / Method | Expected Result |
| --- | --- | --- |
| Build | docker compose build | PASS |
| Static Check | docker compose exec app ruff check . | PASS |
| Unit Test | docker compose exec app pytest | planned |
| Other | README 手順の通し実行（up・migrate・seed） | 全手順が成功する |

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

- 運用手順書の正式版（NFR-OM-19）は運用部門の成果物であり、本Taskはリポジトリ内の起動・実行手順に限る。
- 実装時は本書と併せて、独立ADDR工程が公開する重要判断を参照する。

## 7. Coverage / Scope Check

本章はTask Planning時点の計画用Summaryであり、Trace Mapではない。判定規則は次のとおりとする。

- COVERED：当該IDの要求が、いずれかのTaskのScope / Constraints / Completion Criteria に具体的な作業・制約として現れている。
- N/A：本リリースのリポジトリ内実装として分解すべき作業が無い（要件本文が「該当なし」、運用体制・運用手順の作業、本番基盤の設定に限られる）。理由をRelated Task IDs欄に記す。
- 非機能要件はレンジでまとめず、要件正本のNFR 118件を1行ずつ判定する。画面要件（SCR）と脆弱性対策方針（VUL）も同じ規則で判定する。
- 本表のRelated Task IDsは4章 Task Summary のRelated Requirementと一対一で対応させている。

| Source ID | Source Type | Required Implementation | Related Task IDs | Planning Status |
| --- | --- | --- | --- | --- |
| FR-001 | REQUIREMENT | YES | TASK-002, TASK-008, TASK-019 | COVERED |
| FR-002 | REQUIREMENT | YES | TASK-004, TASK-009, TASK-019 | COVERED |
| FR-003 | REQUIREMENT | YES | TASK-004, TASK-009 | COVERED |
| FR-004 | REQUIREMENT | YES | TASK-009 | COVERED |
| FR-010 | REQUIREMENT | YES | TASK-005, TASK-019 | COVERED |
| FR-011 | REQUIREMENT | YES | TASK-005, TASK-019 | COVERED |
| FR-012 | REQUIREMENT | YES | TASK-005, TASK-019 | COVERED |
| FR-020 | REQUIREMENT | YES | TASK-010, TASK-019 | COVERED |
| FR-021 | REQUIREMENT | YES | TASK-010, TASK-019 | COVERED |
| FR-022 | REQUIREMENT | YES | TASK-010, TASK-019 | COVERED |
| FR-023 | REQUIREMENT | YES | TASK-010, TASK-019 | COVERED |
| FR-024 | REQUIREMENT | YES | TASK-011, TASK-019 | COVERED |
| FR-025 | REQUIREMENT | YES | TASK-011, TASK-019 | COVERED |
| FR-026 | REQUIREMENT | YES | TASK-006 | COVERED |
| FR-030 | REQUIREMENT | YES | TASK-002, TASK-012, TASK-019 | COVERED |
| FR-031 | REQUIREMENT | YES | TASK-007, TASK-013, TASK-019 | COVERED |
| FR-032 | REQUIREMENT | YES | TASK-014, TASK-019 | COVERED |
| FR-033 | REQUIREMENT | YES | TASK-014, TASK-019 | COVERED |
| FR-034 | REQUIREMENT | YES | TASK-015, TASK-019 | COVERED |
| FR-040 | REQUIREMENT | YES | TASK-016, TASK-020 | COVERED |
| FR-041 | REQUIREMENT | YES | TASK-016, TASK-020 | COVERED |
| FR-042 | REQUIREMENT | YES | TASK-016, TASK-020 | COVERED |
| FR-043 | REQUIREMENT | YES | TASK-017, TASK-020 | COVERED |
| FR-044 | REQUIREMENT | YES | TASK-017, TASK-020 | COVERED |
| FR-045 | REQUIREMENT | YES | TASK-017, TASK-020 | COVERED |
| FR-060 | REQUIREMENT | YES | TASK-002, TASK-018, TASK-021 | COVERED |
| NFR-EN-01 | REQUIREMENT | YES | TASK-001 | COVERED |
| NFR-EN-02 | REQUIREMENT | YES | TASK-001, TASK-002 | COVERED |
| NFR-EN-03 | REQUIREMENT | YES | TASK-001 | COVERED |
| NFR-EN-04 | REQUIREMENT | YES | TASK-001, TASK-002 | COVERED |
| NFR-EN-05 | REQUIREMENT | YES | TASK-001, TASK-007, TASK-019 | COVERED |
| NFR-EN-06 | REQUIREMENT | NO | 該当なし（本番環境の設置場所・データ所在。本番基盤の選定事項 OQ-PJ-001） | N/A |
| NFR-EN-07 | REQUIREMENT | YES | TASK-001 | COVERED |
| NFR-EN-08 | REQUIREMENT | YES | TASK-001 | COVERED |
| NFR-EN-09 | REQUIREMENT | YES | TASK-019, TASK-020 | COVERED |
| NFR-EN-10 | REQUIREMENT | YES | TASK-001 | COVERED |
| NFR-EN-11 | REQUIREMENT | YES | TASK-001, TASK-003 | COVERED |
| NFR-EN-12 | REQUIREMENT | YES | TASK-001 | COVERED |
| NFR-EN-13 | REQUIREMENT | NO | 該当なし（要件本文が「該当なし」） | N/A |
| NFR-OM-01 | REQUIREMENT | YES | TASK-003 | COVERED |
| NFR-OM-02 | REQUIREMENT | NO | 該当なし（90日保管と検索は本番運用基盤の設定。ログ出力自体は TASK-003） | N/A |
| NFR-OM-03 | REQUIREMENT | NO | 該当なし（1年保管と年1回の削除は運用手順。監査ログの記録は TASK-004） | N/A |
| NFR-OM-04 | REQUIREMENT | YES | TASK-018, TASK-021 | COVERED |
| NFR-OM-05 | REQUIREMENT | YES | TASK-001, TASK-021 | COVERED |
| NFR-OM-06 | REQUIREMENT | YES | TASK-001 | COVERED |
| NFR-OM-07 | REQUIREMENT | YES | TASK-001 | COVERED |
| NFR-OM-08 | REQUIREMENT | NO | 該当なし（有人運用時間は運用体制の取決め） | N/A |
| NFR-OM-09 | REQUIREMENT | NO | 該当なし（本番環境の監視設定。ENV-01 は監視対象外） | N/A |
| NFR-OM-10 | REQUIREMENT | NO | 該当なし（通知経路と所要時間は運用基盤の設定） | N/A |
| NFR-OM-11 | REQUIREMENT | YES | TASK-003, TASK-004, TASK-018 | COVERED |
| NFR-OM-12 | REQUIREMENT | NO | 該当なし（定期ジョブはバックアップのみで本番基盤のスケジュール機能。手動実行手順は TASK-021） | N/A |
| NFR-OM-13 | REQUIREMENT | YES | TASK-018 | COVERED |
| NFR-OM-14 | REQUIREMENT | NO | 該当なし（パッチ適用は計画停止時の運用作業。依存の版固定は TASK-001） | N/A |
| NFR-OM-15 | REQUIREMENT | NO | 該当なし（リリース・切戻しは運用作業） | N/A |
| NFR-OM-16 | REQUIREMENT | NO | 該当なし（問い合わせ受付と一次回答は運用体制） | N/A |
| NFR-OM-17 | REQUIREMENT | YES | TASK-001, TASK-021 | COVERED |
| NFR-OM-18 | REQUIREMENT | YES | TASK-003 | COVERED |
| NFR-OM-19 | REQUIREMENT | YES | TASK-021 | COVERED |
| NFR-PF-01 | REQUIREMENT | YES | TASK-005, TASK-010, TASK-014, TASK-016 | COVERED |
| NFR-PF-02 | REQUIREMENT | YES | TASK-010, TASK-011, TASK-012, TASK-013, TASK-015, TASK-017 | COVERED |
| NFR-PF-03 | REQUIREMENT | YES | TASK-019, TASK-020 | COVERED |
| NFR-PF-04 | REQUIREMENT | YES | TASK-012 | COVERED |
| NFR-PF-05 | REQUIREMENT | YES | TASK-001, TASK-005, TASK-012 | COVERED |
| NFR-PF-06 | REQUIREMENT | YES | TASK-002, TASK-005, TASK-016 | COVERED |
| NFR-PF-07 | REQUIREMENT | YES | TASK-012, TASK-013, TASK-017 | COVERED |
| NFR-PF-08 | REQUIREMENT | YES | TASK-003, TASK-005, TASK-014, TASK-016 | COVERED |
| NFR-PF-09 | REQUIREMENT | YES | TASK-009 | COVERED |
| NFR-PF-10 | REQUIREMENT | YES | TASK-018 | COVERED |
| NFR-PF-11 | REQUIREMENT | YES | TASK-003, TASK-012 | COVERED |
| NFR-PF-12 | REQUIREMENT | NO | 該当なし（要件本文が「該当なし」。バッチ処理を持たない） | N/A |
| NFR-PF-13 | REQUIREMENT | NO | 該当なし（定期ジョブはバックアップのみ。実行時間帯は本番運用） | N/A |
| NFR-PF-14 | REQUIREMENT | NO | 該当なし（本番基盤のリソース測定 OQ-PJ-001） | N/A |
| NFR-PF-15 | REQUIREMENT | NO | 該当なし（連続負荷での劣化確認は後続Test工程・運用測定） | N/A |
| NFR-PF-16 | REQUIREMENT | YES | TASK-002, TASK-004, TASK-010 | COVERED |
| NFR-PF-17 | REQUIREMENT | YES | TASK-007, TASK-013 | COVERED |
| NFR-SC-01 | REQUIREMENT | YES | TASK-004, TASK-008, TASK-018 | COVERED |
| NFR-SC-02 | REQUIREMENT | NO | 該当なし（本番の HTTPS 終端・転送は本番基盤 OQ-PJ-001。ENV-01 は HTTP を許容） | N/A |
| NFR-SC-03 | REQUIREMENT | YES | TASK-004, TASK-010, TASK-014, TASK-016, TASK-017, TASK-019, TASK-020 | COVERED |
| NFR-SC-04 | REQUIREMENT | YES | TASK-003, TASK-005, TASK-008, TASK-018 | COVERED |
| NFR-SC-05 | REQUIREMENT | YES | TASK-019, TASK-020 | COVERED |
| NFR-SC-06 | REQUIREMENT | YES | TASK-003, TASK-004, TASK-018 | COVERED |
| NFR-SC-07 | REQUIREMENT | YES | TASK-001, TASK-021 | COVERED |
| NFR-SC-08 | REQUIREMENT | YES | TASK-004, TASK-009 | COVERED |
| NFR-SC-09 | REQUIREMENT | YES | TASK-004, TASK-019 | COVERED |
| NFR-SC-10 | REQUIREMENT | YES | TASK-001, TASK-003 | COVERED |
| NFR-SC-11 | REQUIREMENT | YES | TASK-001 | COVERED |
| NFR-SC-12 | REQUIREMENT | YES | TASK-004, TASK-009, TASK-019 | COVERED |
| NFR-SC-13 | REQUIREMENT | NO | 該当なし（要件本文が「該当なし」） | N/A |
| NFR-SC-14 | REQUIREMENT | NO | 該当なし（要件本文が「該当なし」。FR-OUT-11 で対象外） | N/A |
| NFR-SC-15 | REQUIREMENT | YES | TASK-004, TASK-008, TASK-018 | COVERED |
| NFR-SC-16 | REQUIREMENT | YES | TASK-008, TASK-018 | COVERED |
| NFR-SC-17 | REQUIREMENT | NO | 該当なし（要件本文が「該当なし」） | N/A |
| NFR-SC-18 | REQUIREMENT | YES | TASK-004, TASK-009 | COVERED |
| NFR-SC-19 | REQUIREMENT | YES | TASK-004, TASK-019 | COVERED |
| NFR-SC-20 | REQUIREMENT | NO | 該当なし（項目単位の暗号化は行わない。保存時暗号化は本番基盤 OQ-PJ-001） | N/A |
| NFR-SC-21 | REQUIREMENT | YES | TASK-001, TASK-003, TASK-004, TASK-005, TASK-019, TASK-020 | COVERED |
| NFR-SC-22 | REQUIREMENT | YES | TASK-004, TASK-009, TASK-012, TASK-013, TASK-015, TASK-017, TASK-018 | COVERED |
| NFR-SC-23 | REQUIREMENT | YES | TASK-002, TASK-004, TASK-016, TASK-018, TASK-020 | COVERED |
| NFR-SC-24 | REQUIREMENT | YES | TASK-007, TASK-014, TASK-016, TASK-020 | COVERED |
| NFR-SC-25 | REQUIREMENT | YES | TASK-018, TASK-021 | COVERED |
| NFR-SC-26 | REQUIREMENT | NO | 該当なし（本番のネットワーク到達制御 OQ-PJ-003） | N/A |
| NFR-SC-27 | REQUIREMENT | NO | 該当なし（要件本文が「該当なし」） | N/A |
| NFR-SC-28 | REQUIREMENT | NO | 該当なし（要件本文が「該当なし」。ファイルアップロード機能を持たない） | N/A |
| NFR-SC-29 | REQUIREMENT | NO | 該当なし（稼働開始前の脆弱性診断は後続Test工程・運用作業） | N/A |
| NFR-US-01 | REQUIREMENT | YES | TASK-019, TASK-020 | COVERED |
| NFR-US-02 | REQUIREMENT | YES | TASK-019, TASK-020 | COVERED |
| NFR-US-03 | REQUIREMENT | YES | TASK-001, TASK-019, TASK-020 | COVERED |
| NFR-US-04 | REQUIREMENT | YES | TASK-019, TASK-020 | COVERED |
| NFR-US-05 | REQUIREMENT | YES | TASK-019, TASK-020 | COVERED |
| NFR-US-06 | REQUIREMENT | YES | TASK-019, TASK-020 | COVERED |
| NFR-US-07 | REQUIREMENT | YES | TASK-019, TASK-020 | COVERED |
| NFR-US-08 | REQUIREMENT | YES | TASK-019 | COVERED |
| NFR-US-09 | REQUIREMENT | YES | TASK-019, TASK-020 | COVERED |
| NFR-US-10 | REQUIREMENT | YES | TASK-019, TASK-020 | COVERED |
| NFR-AV-01 | REQUIREMENT | NO | 該当なし（サービス提供時間は運用。実装作業を伴わない） | N/A |
| NFR-AV-02 | REQUIREMENT | NO | 該当なし（稼働率は運用測定） | N/A |
| NFR-AV-03 | REQUIREMENT | NO | 該当なし（計画停止は運用作業） | N/A |
| NFR-AV-04 | REQUIREMENT | NO | 該当なし（バックアップ取得は本番基盤・運用） | N/A |
| NFR-AV-05 | REQUIREMENT | NO | 該当なし（復旧時間は運用） | N/A |
| NFR-AV-06 | REQUIREMENT | NO | 該当なし（要件本文が「該当なし」） | N/A |
| NFR-AV-07 | REQUIREMENT | NO | 該当なし（復旧時点はバックアップ運用） | N/A |
| NFR-AV-08 | REQUIREMENT | NO | 該当なし（復旧レベルは運用） | N/A |
| NFR-AV-09 | REQUIREMENT | NO | 該当なし（要件本文が「該当なし」） | N/A |
| NFR-AV-10 | REQUIREMENT | NO | 該当なし（要件本文が「該当なし」） | N/A |
| NFR-AV-11 | REQUIREMENT | NO | 該当なし（バックアップ保管先は本番基盤） | N/A |
| NFR-AV-12 | REQUIREMENT | NO | 該当なし（リストア手順は運用） | N/A |
| NFR-MG-01 | REQUIREMENT | NO | 該当なし（現行データを移行しない。稼働開始時0件は TASK-018 の全削除投入で満たす） | N/A |
| NFR-MG-02 | REQUIREMENT | YES | TASK-018 | COVERED |
| NFR-MG-03 | REQUIREMENT | YES | TASK-018 | COVERED |
| NFR-MG-04 | REQUIREMENT | YES | TASK-018 | COVERED |
| NFR-MG-05 | REQUIREMENT | NO | 該当なし（投入の実施時期は運用計画） | N/A |
| NFR-MG-06 | REQUIREMENT | NO | 該当なし（要件本文が「該当なし」） | N/A |
| NFR-MG-07 | REQUIREMENT | YES | TASK-018 | COVERED |
| NFR-MG-08 | REQUIREMENT | NO | 該当なし（本番投入前のリハーサルは運用作業） | N/A |
| NFR-LG-01 | REQUIREMENT | YES | TASK-004, TASK-014, TASK-016, TASK-020 | COVERED |
| NFR-LG-02 | REQUIREMENT | YES | TASK-005, TASK-019 | COVERED |
| NFR-LG-03 | REQUIREMENT | NO | 該当なし（帳簿書類の7年保存は運用。自動削除を実装しない） | N/A |
| NFR-LG-04 | REQUIREMENT | NO | 該当なし（通信販売の法定表示は EC運営担当の掲載運用。SCR-001〜SCR-103・SCR-901 に該当画面がない） | N/A |
| NFR-LG-05 | REQUIREMENT | NO | 該当なし（クレジットカード番号を取り扱わない。決済は本システム内の模擬機能） | N/A |
| NFR-LG-06 | REQUIREMENT | YES | TASK-006, TASK-010, TASK-011, TASK-012, TASK-015, TASK-017 | COVERED |
| NFR-LG-07 | REQUIREMENT | YES | TASK-001, TASK-003, TASK-004, TASK-019, TASK-020 | COVERED |
| NFR-LG-08 | REQUIREMENT | YES | TASK-019, TASK-020 | COVERED |
| NFR-LG-09 | REQUIREMENT | YES | TASK-002, TASK-012 | COVERED |
| NFR-LG-10 | REQUIREMENT | NO | 該当なし（要件本文が「該当なし」。外部サービスと契約・接続しない） | N/A |
| SCR-001 | REQUIREMENT | YES | TASK-019 | COVERED |
| SCR-002 | REQUIREMENT | YES | TASK-019 | COVERED |
| SCR-003 | REQUIREMENT | YES | TASK-019 | COVERED |
| SCR-004 | REQUIREMENT | YES | TASK-019 | COVERED |
| SCR-005 | REQUIREMENT | YES | TASK-019 | COVERED |
| SCR-006 | REQUIREMENT | YES | TASK-019 | COVERED |
| SCR-007 | REQUIREMENT | YES | TASK-019 | COVERED |
| SCR-008 | REQUIREMENT | YES | TASK-019 | COVERED |
| SCR-009 | REQUIREMENT | YES | TASK-019 | COVERED |
| SCR-010 | REQUIREMENT | YES | TASK-019 | COVERED |
| SCR-101 | REQUIREMENT | YES | TASK-020 | COVERED |
| SCR-102 | REQUIREMENT | YES | TASK-020 | COVERED |
| SCR-103 | REQUIREMENT | YES | TASK-020 | COVERED |
| SCR-901 | REQUIREMENT | YES | TASK-019 | COVERED |
| VUL-01 | REQUIREMENT | YES | TASK-004, TASK-010, TASK-014, TASK-015, TASK-016, TASK-017, TASK-019, TASK-020 | COVERED |
| VUL-02 | REQUIREMENT | YES | TASK-004, TASK-009, TASK-019 | COVERED |
| VUL-03 | REQUIREMENT | YES | TASK-004（本番の TLS は NFR-SC-02、保存時暗号化は NFR-SC-20 として N/A） | COVERED |
| VUL-04 | REQUIREMENT | YES | TASK-003, TASK-005, TASK-008, TASK-018 | COVERED |
| VUL-05 | REQUIREMENT | YES | TASK-003, TASK-019, TASK-020 | COVERED |
| VUL-06 | REQUIREMENT | YES | TASK-019, TASK-020 | COVERED |
| VUL-07 | REQUIREMENT | YES | TASK-006, TASK-010, TASK-011, TASK-012, TASK-013, TASK-015, TASK-017 | COVERED |
| VUL-08 | REQUIREMENT | YES | TASK-001, TASK-018 | COVERED |
| VUL-09 | REQUIREMENT | YES | TASK-001 | COVERED |
| VUL-10 | REQUIREMENT | YES | TASK-001, TASK-018 | COVERED |
| VUL-11 | REQUIREMENT | YES | TASK-003, TASK-004 | COVERED |
| VUL-12 | REQUIREMENT | YES | TASK-007 | COVERED |
| VUL-13 | REQUIREMENT | YES | TASK-003 | COVERED |
| IF-01 | EXTERNAL_IF | YES | TASK-007, TASK-013 | COVERED |
| FILE-001 | DESIGN | YES | TASK-018 | COVERED |

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
- Blocking Tasks: 0（Taskの着手前であり、未確定判断は9章のBlockerとして記録する）

## 9. Blockers / Open Decisions

Recommended Route 欄の `ADDR` は、現行契約で重要方式の案比較・採否を唯一作成できる独立ADDR工程を指す
（テンプレートの `ARCHITECTURE` 欄に相当する解決先の具体名）。Architecture工程は候補の所在・対象・根拠だけを
引き渡し、採否・比較・理由は記載しない。

| Blocker ID | Related Task | Classification | Description | Impact | Recommended Route | Status |
| --- | --- | --- | --- | --- | --- | --- |
| BLK-001 | TASK-018 | ARCHITECTURE | 初期データ定義ファイルのトップレベルキー名と参照項目の英名が要件・提供済み仕様に定義されていない（OQ-FILE-001） | 定義ファイルの実体と読取り実装、運用手順の記載が確定しない | ADDR | OPEN |
| BLK-002 | TASK-004 | ARCHITECTURE | パスワードハッシュのアルゴリズムと認証トークン・セッションの保持方式が未判断 | 認証系の応答時間（NFR-PF-09）と安全性の実現方式が定まらない | ADDR | OPEN |
| BLK-003 | TASK-012 | ARCHITECTURE | 在庫引当・状態遷移の同時実行制御の実現方式が未判断（要件は結果のみを定める） | NFR-PF-07 の同時実行整合と競合時の業務エラー返却方式が定まらない | ADDR | OPEN |
| BLK-004 | TASK-003 | ARCHITECTURE | app/ 内部のモジュール分割と依存規則が Steering で設計へ委任されたまま未判断 | 共通基盤と各機能の配置・依存方向が定まらない | ADDR | OPEN |
| BLK-005 | TASK-019 | ARCHITECTURE | 画面のログインセッション保持方式・CSRF 対策の実現方式が未判断 | 無操作30分の切断と画面更新操作の保護の実現方式が定まらない | ADDR | OPEN |
| BLK-006 | TASK-002 | ARCHITECTURE | 一意制約・索引・物理設計の実現方式と、NFR-PF-01・NFR-PF-06 の達成方式が未判断（要件は目標値のみを定める） | 照会系応答時間と3年後データ量での性能の実現方式、TASK-002・TASK-005・TASK-016 のクエリ構成が定まらない | ADDR | OPEN |
| BLK-007 | TASK-007 | ARCHITECTURE | 模擬決済（IF-01）の実装配置と呼出し方式、模擬決済指示の受け渡し方法が未判断 | NFR-PF-17 の分離範囲と TASK-013 からの呼出し境界が定まらない | ADDR | OPEN |
| BLK-008 | TASK-019 | ARCHITECTURE | 画面テンプレートの構成（共通レイアウトの分割単位と購入者・管理者画面での再利用方法）が未判断 | TASK-019・TASK-020 のテンプレート配置と重複実装の防止方法が定まらない | ADDR | OPEN |
| BLK-009 | TASK-003 | ARCHITECTURE | 共通例外ハンドラの実現方式（捕捉範囲とエラーコードへの写像の実装手段）が未判断 | NFR-SC-10 の内部情報非返却を全APIで一貫させる手段が定まらない | ADDR | OPEN |

## 10. Change History

| Version | Date | Change | Reason | Related ID |
| --- | --- | --- | --- | --- |
| 1.0 | 2026-10-21 | 初版作成（FR-001〜FR-060・NFR・UC-001〜UC-013・Steeringから21Taskへ分解） | RUN-002 Architecture 工程の設計資料作成 | FR-060 |
| 1.1 | 2026-10-21 | 7章 Coverage / Scope Check をNFR 118件・SCR 14件・VUL 13件の単位判定へ置換し、4章 Related Requirement と一致させた | Quality Review（ARCHITECTURE Scope, 2026-10-21）の指摘（網羅判定の欠落と根拠IDの不一致）の反映。出典: reports/quality-review/quality-review-report.md | NFR-SC-23 |
| 1.1 | 2026-10-21 | Security要件をTaskのScope / Constraints / DoDへ反映（NFR-SC-19・NFR-SC-15・NFR-SC-23・NFR-SC-04・NFR-SC-05・NFR-OM-17・NFR-SC-10後段・NFR-EN-08・NFR-SC-11・NFR-SC-16・NFR-SC-25・NFR-PF-16・NFR-PF-17） | Security Review（ARCHITECTURE Scope, 2026-10-21）の指摘の反映。出典: reports/security-review/security-review-report.md | NFR-SC-19 |
| 1.1 | 2026-10-21 | 未確定判断の引渡し候補をBLK-006〜BLK-009として追加し、9章のRecommended Route表記をADDRへ統一した | Quality Review（ARCHITECTURE Scope, 2026-10-21）の指摘（未確定判断の引渡し不足と経路表記の不統一）の反映。出典: reports/quality-review/quality-review-report.md | NFR-PF-01 |
