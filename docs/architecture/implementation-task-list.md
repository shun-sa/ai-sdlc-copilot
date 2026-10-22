# 実装タスク一覧・進捗

## 1. 文書情報

| 項目 | 内容 |
| --- | --- |
| Document ID | DOC-IMPL-TASK-001 |
| 対象システム | MiniCommerce |
| Baseline / Commit | 2e9703ddd0c7bb5e71d270783a5efd5e016d2f4d+WORKTREE（RUN-20261022-MC） |
| Version | 1.1 |
| Status | DRAFT |
| Owner | Architecture Agent（MiniCommerce SDLC Phase 2） |
| Last Updated | 2026-10-22 |

## 2. Source Baseline

| Source Type | ID / Path | Required Status / Version | Purpose |
| --- | --- | --- | --- |
| Requirements | docs/requirements/requirements.md（索引） | 構造Validator PASS / 1.0 | 分割要件・UCへの派生索引 |
| Requirements | docs/requirements/functional_requirements.md | 作成中 / 1.0-adapted.1 | 機能（FR-001〜FR-060）・判定順序・共通機能（CMN）・エラー種別（ERR-01〜ERR-08） |
| Requirements | docs/requirements/non_functional_requirements.md | 作成中 / 1.0-adapted.1 | 非機能（NFR）・検証方法 |
| Requirements | docs/requirements/data_requirements.md | 作成中 / 1.0-adapted.1 | データ（D-01〜D-15）・項目英名・品質ルール・初期投入（INI） |
| Requirements | docs/requirements/external_interface_requirements.md | 作成中 / 1.0-adapted.1 | IF-01 決済要求（売上確定）の要件 |
| Requirements | docs/requirements/ui_report_requirements.md | 作成中 / 1.0-adapted.1 | 画面（SCR-001〜SCR-901）の項目・操作・メッセージ |
| Requirements | docs/requirements/glossary.md | 作成中 / 1.0-adapted.1 | 用語（TERM-001〜TERM-053）と項目英名の整合 |
| Use Case | docs/requirements/use-cases/UC-001.md〜UC-013.md | 作成中 / 1.0-adapted.1 | Flow と Acceptance Criteria（Pass / Fail Rule） |
| Use Case | docs/requirements/use-case-user-story-index.md | 作成中 / 1.0-adapted.1 | Actor・US・UCと要件の対応 |
| ADR | 該当なし（docs/addr/ 未作成） | 採択済み判断なし | 重要方式の判断は後続の独立ADDR工程で確定する |
| Detailed Design | docs/architecture/files/FILE-001.md（FILE-001） | DRAFT / 1.0 | 初期データ定義ファイルの項目・異常処理（TASK-014 の詳細仕様） |
| Detailed Design | docs/specifications/api-contract.md | 提供済み / 受領版 | エンドポイント・エラーコード・context・応答項目の命名 |
| Project AI Steering | .github/project-context/project-ai-steering.md | DRAFT / 1.0 | 技術スタック・配置・コマンド・禁止事項 |

## 3. Task Decomposition Rules

Taskは以下の条件を満たす単位へ分解する。

- 1 Taskの目的と完了条件を明確に説明できる。
- Related Requirement / ADR / Design Referenceが特定できる。
- 依存Taskを明示できる。
- 実装後にBuild / Test / Validator等で完了を確認できる。
- 複数の独立した変更目的を不必要に1 Taskへまとめない。
- Requirementに存在しない機能追加をTask化しない。
- 新たなArchitecture Decisionが必要なTaskは実装開始前に解決する。

本書は作業の分解・依存・検証方法だけを整理し、方式の採否は行わない。
実装時は本書に加えて、後続の独立ADDR工程が確定する判断（docs/addr/）を必ず参照する。
9章に記録した未確定判断は、ADDRで確定してから該当Taskの実装を開始する。

## 4. Task Summary

| Task ID | Title | Type | Related Requirement | Related ADR | Target Area | Depends On | Priority | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| TASK-001 | 実行基盤とプロジェクト雛形の構築 | CONFIG | NFR-EN-01, NFR-EN-02, NFR-EN-03, NFR-EN-04, NFR-EN-07, NFR-EN-08, NFR-EN-09, NFR-EN-10, NFR-EN-11, NFR-EN-12, NFR-OM-05, NFR-OM-06, NFR-OM-07, NFR-OM-17, NFR-SC-07, NFR-SC-11 | None | リポジトリルート（compose.yaml、.env.example）、app（Django プロジェクト設定） | None | HIGH | TODO |
| TASK-002 | 永続データモデルとマイグレーションの作成 | MIGRATION | NFR-EN-02, NFR-EN-04, FR-001, FR-011, FR-020, FR-030, FR-031, FR-040, FR-060 | None | app（データモデル・マイグレーション） | TASK-001 | HIGH | TODO |
| TASK-003 | 共通API基盤（判定順序・入力検証・エラー応答）の実装 | IMPLEMENT | NFR-SC-03, NFR-SC-04, NFR-SC-10, NFR-US-04, NFR-PF-08 | None | app（共通処理・例外ハンドリング・ページング） | TASK-001 | HIGH | TODO |
| TASK-004 | ログ・監査ログ基盤の実装 | IMPLEMENT | NFR-OM-01, NFR-OM-02, NFR-OM-03, NFR-OM-11, NFR-OM-18, NFR-SC-06, NFR-SC-22, NFR-SC-23 | None | app（ログ出力・要求ID相関・監査ログ記録） | TASK-001 | HIGH | TODO |
| TASK-005 | 認証・利用者機能の実装 | IMPLEMENT | FR-001, FR-002, FR-003, FR-004, NFR-SC-01, NFR-SC-08, NFR-SC-09, NFR-SC-12, NFR-SC-16, NFR-SC-18, NFR-SC-19, NFR-PF-09 | None | app（認証・利用者） | TASK-002, TASK-003, TASK-004 | HIGH | TODO |
| TASK-006 | 商品カタログ参照機能の実装 | IMPLEMENT | FR-010, FR-011, FR-012, NFR-PF-01, NFR-PF-08, NFR-SC-04, NFR-LG-02 | None | app（商品・商品分類・在庫単位の参照） | TASK-002, TASK-003 | HIGH | TODO |
| TASK-007 | 注文金額計算の実装 | IMPLEMENT | FR-026, NFR-LG-02 | None | app（金額計算の共通ロジック） | TASK-002, TASK-003 | HIGH | TODO |
| TASK-008 | カート機能の実装 | IMPLEMENT | FR-020, FR-021, FR-022, FR-023, FR-026, NFR-PF-02, NFR-PF-07 | None | app（カート） | TASK-005, TASK-006, TASK-007 | HIGH | TODO |
| TASK-009 | クーポン適用・解除の実装 | IMPLEMENT | FR-024, FR-025, FR-026 | None | app（カート・クーポン） | TASK-008 | HIGH | TODO |
| TASK-010 | 注文確定の実装 | IMPLEMENT | FR-030, FR-026, NFR-PF-02, NFR-PF-07, NFR-LG-03 | None | app（注文確定・在庫引当） | TASK-008, TASK-009 | HIGH | TODO |
| TASK-011 | 支払（模擬決済）と決済インターフェースの実装 | IMPLEMENT | FR-031, NFR-PF-02, NFR-EN-05, NFR-LG-05 | None | app（支払・決済サービス模擬機能） | TASK-010 | HIGH | TODO |
| TASK-012 | 購入者の注文照会・キャンセルの実装 | IMPLEMENT | FR-032, FR-033, FR-034, NFR-PF-01, NFR-PF-08, NFR-SC-24 | None | app（購入者の注文参照・キャンセル） | TASK-010 | HIGH | TODO |
| TASK-013 | 管理者機能（在庫単位一覧・注文管理）の実装 | IMPLEMENT | FR-040, FR-041, FR-042, FR-043, FR-044, FR-045, NFR-PF-01, NFR-PF-08, NFR-SC-03, NFR-SC-04 | None | app（管理者API） | TASK-011, TASK-012 | HIGH | TODO |
| TASK-014 | 初期データ一括投入コマンドの実装 | IMPLEMENT | FR-060, NFR-OM-04, NFR-MG-02, NFR-PF-10, NFR-SC-01, NFR-SC-04, NFR-SC-06 | None | app（管理コマンド・seed） | TASK-002, TASK-004 | HIGH | TODO |
| TASK-015 | 画面（購入者・管理者・エラー）の実装 | IMPLEMENT | FR-001, FR-002, FR-003, FR-011, FR-012, FR-020, FR-030, FR-031, FR-033, FR-040, FR-041, FR-043, NFR-US-01, NFR-US-02, NFR-US-03, NFR-US-04, NFR-US-07, NFR-US-09, NFR-US-10, NFR-SC-05, NFR-PF-03 | None | app（テンプレート・画面ビュー） | TASK-005, TASK-006, TASK-008, TASK-009, TASK-010, TASK-011, TASK-012, TASK-013 | HIGH | TODO |
| TASK-016 | 起動・運用手順ドキュメントの整備 | OTHER | NFR-OM-19, NFR-OM-04, NFR-OM-05, NFR-OM-14, NFR-OM-15, NFR-SC-07, NFR-SC-11 | None | リポジトリルート（README） | TASK-014, TASK-015 | MEDIUM | TODO |

## 5. Execution Order / Dependency

| Wave | Task IDs | Start Condition |
| ---: | --- | --- |
| 1 | TASK-001 | Source Baseline確定（本書2章）とADDRによる基盤方式の確定 |
| 2 | TASK-002, TASK-003, TASK-004 | TASK-001 DONE |
| 3 | TASK-005, TASK-006, TASK-007, TASK-014 | TASK-002, TASK-003, TASK-004 のうち各Taskの依存がDONE |
| 4 | TASK-008 | TASK-005, TASK-006, TASK-007 DONE |
| 5 | TASK-009 | TASK-008 DONE |
| 6 | TASK-010 | TASK-008, TASK-009 DONE |
| 7 | TASK-011, TASK-012 | TASK-010 DONE |
| 8 | TASK-013 | TASK-011, TASK-012 DONE |
| 9 | TASK-015 | API側Task（TASK-005, TASK-006, TASK-008〜TASK-013）DONE |
| 10 | TASK-016 | TASK-014, TASK-015 DONE |

## 6. Task Details

### TASK-001 `実行基盤とプロジェクト雛形の構築`

#### Metadata

| 項目 | 内容 |
| --- | --- |
| Type | CONFIG |
| Priority | HIGH |
| Status | TODO |
| Target Area | リポジトリルート（compose.yaml、.env.example）、app（Django プロジェクト設定） |
| Depends On | None |
| Blocks | TASK-002, TASK-003, TASK-004 |

#### Source References

| Type | ID / Path | Relevant Section / Reason |
| --- | --- | --- |
| Requirement | NFR-EN-01, NFR-EN-02, NFR-EN-03, NFR-EN-04, NFR-EN-07, NFR-EN-09 | 開発言語・フレームワーク・DB・コンテナ構成・タイムゾーン／文字コード・OS非依存・サーバーサイドレンダリングの指定 |
| Requirement | NFR-EN-08 | app サービス内で動作する Web サーバー・AP サーバーは**指定なしで設計が選定する**（要件は方式を定めない）。本番環境で Django 付属の開発用サーバーを使用しないことのみが制約。選定は未確定判断（本書9章 BLK-011） |
| Requirement | NFR-EN-10, NFR-EN-12, NFR-SC-11 | 依存ライブラリをサポート期限内の版で運用すること、ライセンス条件、リリース前の既知の重大な脆弱性（CVSS 7.0以上）0件の確認対象が依存定義ファイルであること |
| Requirement | NFR-EN-11 | Python のコーディング規約（PEP 8／ruff）、JSON 項目名 snake_case、URL は小文字・ハイフン区切り、テストファイル名 test_*.py |
| Requirement | NFR-OM-05, NFR-OM-06, NFR-OM-07, NFR-OM-17 | コマンド1回での全サービス起動、テスト実行、静的解析の指摘0件、環境ごとの設定を環境変数で与えること |
| Requirement | NFR-SC-07 | 秘密情報を環境変数で与え、リポジトリに実値を置かない |
| Requirement | VUL-10（non_functional_requirements.md 8.2） | 依存定義ファイルでのバージョン固定と、取得元を公式の配布元に限ること。外部CDNを参照しないこと |
| Use Case / AC | 該当なし（全UCの前提である実行環境） | UC-001〜UC-013 の Given に共通する app・db の起動前提 |
| ADR | 該当なし | 構成の重要方式はADDRで確定する（本書9章 BLK-004、BLK-011） |
| Detailed Design | .github/project-context/project-ai-steering.md（3章、4章、9章） | 技術スタック・ディレクトリ・コマンドの正本 |

#### Objective

Docker Compose（app・db）で起動し、Django プロジェクト・テスト・静的解析をコマンド1回で実行できる基盤を用意する。

#### Scope

##### In Scope

- compose.yaml（サービス app・db、app は 8000、db は 5432）と .env.example（実値なし）の作成。
- Django プロジェクトの初期化、タイムゾーン Asia/Tokyo・文字コード UTF-8・PostgreSQL 16 接続設定。
- 依存定義ファイルの作成（全依存ライブラリのバージョン固定、取得元は公式の配布元に限定。NFR-SC-11 のリリース前確認の対象一覧となる）。
- app サービスの起動設定（本番環境で Django 付属の開発用サーバーを使用しないこと。NFR-EN-08。Web サーバー・AP サーバーの選定自体は BLK-011 の確定に従う）。
- pytest・pytest-django・ruff の実行設定（テストファイル名は test_*.py）。

##### Out of Scope

- 業務モデル・API・画面の実装（TASK-002 以降）。
- 本番環境の基盤・HTTPS終端の構成（OQ-PJ-001、OQ-PJ-003 により本リリース対象外。NFR-SC-02 を含む）。
- Web サーバー・AP サーバーの方式選定そのもの（BLK-011 としてADDRへ委譲。本Taskでは選定しない）。
- リリース前の依存ライブラリ脆弱性確認ツールの実行（NFR-SC-11 はリリース作業で実施。本Taskの範囲は確認対象となる依存定義ファイルの整備）。

#### Expected Change

- リポジトリルートに compose.yaml、.env.example、依存定義（コンテナイメージへ取り込む形。全依存ライブラリのバージョンを固定し、取得元を公式の配布元に限る）。
- app 配下に Django プロジェクト設定とテスト・静的解析の設定。

#### Constraints

- SPA フレームワーク・フロントエンドのビルド工程・外部CDNを使わない（Steering 3章、NFR-EN-05）。
- 秘密情報をソースコード・リポジトリに含めない（NFR-SC-07）。環境ごとに異なる設定は環境変数で与える（NFR-OM-17）。
- 外部ネットワーク接続はイメージ作成時のみ許容（NFR-EN-05）。
- 本番環境では Django 付属の開発用サーバーを使用しない（NFR-EN-08）。app サービスで動作する Web サーバー・AP サーバーの選定は未確定判断（本書9章 BLK-011）であり、ADDRの確定に従う。
- 依存ライブラリは依存定義ファイルでバージョンを固定し、取得元を公式の配布元（Python パッケージの公式リポジトリ、公式のコンテナイメージ）に限る（VUL-10）。
- 依存ライブラリはサポート期限内の版を用いる（NFR-EN-10）。AGPL・ライセンス不明のライブラリを使わない（NFR-EN-12）。
- Python のコーディング規約・命名規約（PEP 8、JSON 項目名 snake_case、URL は小文字・ハイフン区切り、テストファイル名 test_*.py）に従う（NFR-EN-11）。

#### Completion Criteria / Definition of Done

- [ ] docker compose build と docker compose up -d が成功し、app と db が起動する。
- [ ] docker compose exec app python manage.py migrate が成功する。
- [ ] docker compose exec app pytest がコマンド1回で実行できる。
- [ ] docker compose exec app ruff check . の指摘が0件である（NFR-EN-11、NFR-OM-07）。
- [ ] .env.example に実値を含めず、.env をリポジトリに含めない。環境依存の設定が環境変数で与えられる（NFR-OM-17）。
- [ ] 依存定義ファイルで全依存ライブラリのバージョンが固定され、取得元が公式の配布元に限られている（VUL-10）。
- [ ] 依存ライブラリの版がサポート期限内であり（NFR-EN-10）、ライセンスが利用条件を満たす（NFR-EN-12）。依存定義ファイルがリリース前の脆弱性確認（NFR-SC-11）の対象一覧として参照できる。
- [ ] app サービスの起動設定に Django 付属の開発用サーバーを使用しない構成が用意されている（NFR-EN-08。具体的な Web サーバー・AP サーバーは BLK-011 の確定後に反映する）。
- [ ] 要件に無い構成要素を追加していない。

#### Validation

| Validation Type | Command / Method | Expected Result |
| --- | --- | --- |
| Build | docker compose build | PASS |
| Static Check | docker compose exec app ruff check . | PASS（指摘0件） |
| Unit Test | docker compose exec app pytest | 実行できること（この時点のテストは後続Taskで追加） |
| Other | docker compose up -d と docker compose exec app python manage.py migrate | 全サービス起動とマイグレーション成功 |
| Other | 依存定義ファイルと起動設定の構成・設定レビュー（バージョン固定・公式の配布元・サポート期限内の版・ライセンス・開発用サーバーの不使用） | 違反0件（NFR-EN-08、NFR-EN-10、NFR-EN-12、VUL-10） |

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

- 実装前に、ADDRが確定する app 内部のモジュール構成（BLK-004）と、app サービスで動作する Web サーバー・AP サーバーの選定（BLK-011）に従うこと。
- NFR-SC-11（リリース前の依存ライブラリ脆弱性確認）はツール実行を伴うリリース作業であり、本Taskでは確認対象（依存定義ファイル）の整備までを担当する。実行手順の記載は TASK-016。

### TASK-002 `永続データモデルとマイグレーションの作成`

#### Metadata

| 項目 | 内容 |
| --- | --- |
| Type | MIGRATION |
| Priority | HIGH |
| Status | TODO |
| Target Area | app（データモデル・マイグレーション） |
| Depends On | TASK-001 |
| Blocks | TASK-005, TASK-006, TASK-007, TASK-014 |

#### Source References

| Type | ID / Path | Relevant Section / Reason |
| --- | --- | --- |
| Requirement | FR-001, FR-011, FR-020, FR-030, FR-031, FR-040, FR-060 | 各機能が参照・更新するデータの保持内容 |
| Requirement | NFR-EN-02, NFR-EN-04 | PostgreSQL 16、JST・UTF-8の扱い |
| Use Case / AC | UC-001, UC-004, UC-006, UC-007, UC-013 | 登録・更新結果として確認されるデータの状態 |
| ADR | 該当なし | 物理設計の重要方式はADDRで確定する（本書9章 BLK-001、BLK-006） |
| Detailed Design | docs/requirements/data_requirements.md（D-01〜D-15、DQ、UPD、RET） | 項目英名・一意制約・値域・保存期間の正本 |

#### Objective

D-01〜D-15 のデータを PostgreSQL 上に定義し、要件の一意性・値域・参照関係を満たすマイグレーションを作成する。

#### Scope

##### In Scope

- 利用者・仕入先・商品分類・商品・商品分類所属・在庫単位・クーポン・カート・カート明細・注文・注文明細・配送先・決済記録・注文状態履歴・監査ログのモデル定義とマイグレーション。
- 要件が定める一意制約（メールアドレス、各業務キー、注文番号、カート明細の重複禁止等）と値域の表現。

##### Out of Scope

- 業務処理（登録・更新のロジック）の実装（TASK-005 以降）。
- 性能のための索引方式の決定（ADDRの判断対象。BLK-006）。

#### Expected Change

- app 配下のデータモデル定義とマイグレーションファイル。

#### Constraints

- 項目英名は data_requirements.md と api-contract.md の命名に一致させる（Steering 5.2）。
- 税込価格は保持せず税抜価格から算出する（DCN-11）。
- パスワードは平文を保持しない（NFR-SC-01）。

#### Completion Criteria / Definition of Done

- [ ] D-01〜D-15 に対応するモデルが定義されている。
- [ ] 要件の一意制約・必須・値域がマイグレーションに反映されている。
- [ ] docker compose exec app python manage.py migrate が成功する。
- [ ] ruff check の指摘が0件である。
- [ ] 要件に無いデータ項目・テーブルを追加していない。
- [ ] 索引・排他方式など未確定判断を本Taskで独自に決めていない。

#### Validation

| Validation Type | Command / Method | Expected Result |
| --- | --- | --- |
| Build | docker compose build | PASS |
| Static Check | docker compose exec app ruff check . | PASS（指摘0件） |
| Unit Test | docker compose exec app pytest | PASS（モデル制約のテストは後続Taskと合わせて追加） |
| Other | docker compose exec app python manage.py migrate | 適用成功 |

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

- 注文番号の採番方式（BLK-003）はADDR確定後に実装する。

### TASK-003 `共通API基盤（判定順序・入力検証・エラー応答）の実装`

#### Metadata

| 項目 | 内容 |
| --- | --- |
| Type | IMPLEMENT |
| Priority | HIGH |
| Status | TODO |
| Target Area | app（共通処理・例外ハンドリング・ページング） |
| Depends On | TASK-001 |
| Blocks | TASK-005, TASK-006, TASK-007 |

#### Source References

| Type | ID / Path | Relevant Section / Reason |
| --- | --- | --- |
| Requirement | NFR-SC-03, NFR-SC-04, NFR-SC-10 | サーバー側での権限判定・入力検証・内部情報の非表示 |
| Requirement | NFR-US-04, NFR-PF-08 | 入力エラーの表示、一覧の応答件数上限 |
| Use Case / AC | UC-002, UC-003, UC-011 の例外フロー | 認証・権限・入力・対象なし・状態・業務ルールの判定順序 |
| ADR | 該当なし | 共通化の方式はADDRで確定する（本書9章 BLK-007） |
| Detailed Design | docs/specifications/api-contract.md（6.2、6.3）、functional_requirements.md（CMN-14、CMN-35、ERR-01〜ERR-08） | エラーコード・HTTPステータス・context・ページング形式 |

#### Objective

全APIで共通となるエラー応答形式、判定順序、ページング、要求ヘッダーの引き継ぎを共通基盤として実装する。

#### Scope

##### In Scope

- エラー応答（code、message、details、context）とHTTPステータス対応の共通化。
- 判定順序（認証→権限→入力→対象の存在・所有→状態→業務ルール）の共通適用。
- ページング応答形式（results、page、page_size、total_count、total_pages）の共通化。
- X-Request-ID の受領・生成・応答付与の共通処理。

##### Out of Scope

- 個別機能の入力条件・業務判定（各機能Task）。
- ログ出力そのもの（TASK-004）。

#### Expected Change

- app 配下の共通例外ハンドラ・共通バリデーション・ページング・ミドルウェア相当の処理。

#### Constraints

- スタックトレース・SQLなど内部情報を応答へ含めない（NFR-SC-10）。
- VALIDATION_ERROR は不備のある全項目を details に列挙する（api-contract.md 6.2）。
- 画面とAPIで同一の業務ルール・エラーコードに従う（CMN-34）。

#### Completion Criteria / Definition of Done

- [ ] 共通エラー応答がapi-contract.md 6.2・6.3の形式と一致する。
- [ ] 判定順序が共通処理として適用できる。
- [ ] ページング応答形式が共通化されている。
- [ ] X-Request-ID の引き継ぎ・生成が動作する。
- [ ] ruff check の指摘が0件である。
- [ ] 要件に無いエラーコード・応答項目を追加していない。

#### Validation

| Validation Type | Command / Method | Expected Result |
| --- | --- | --- |
| Build | docker compose build | PASS |
| Static Check | docker compose exec app ruff check . | PASS（指摘0件） |
| Unit Test | docker compose exec app pytest | PASS |
| Other | api-contract.md 6.2・6.3 と応答JSONの項目照合 | 一致 |

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

- 共通化の実現方式（例外ハンドラの配置等）はADDR確定後に実装する（BLK-007）。

### TASK-004 `ログ・監査ログ基盤の実装`

#### Metadata

| 項目 | 内容 |
| --- | --- |
| Type | IMPLEMENT |
| Priority | HIGH |
| Status | TODO |
| Target Area | app（ログ出力・要求ID相関・監査ログ記録） |
| Depends On | TASK-001 |
| Blocks | TASK-005, TASK-014 |

#### Source References

| Type | ID / Path | Relevant Section / Reason |
| --- | --- | --- |
| Requirement | NFR-OM-01, NFR-OM-02, NFR-OM-03, NFR-OM-11, NFR-OM-18 | JSON Lines形式、保管期間、LOG-01〜LOG-07 の出力、障害調査の容易さ（request_id 相関） |
| Requirement | NFR-SC-06, NFR-SC-22, NFR-SC-23 | 機密情報の非出力（path にクエリ文字列を含めないことを含む）、記録対象操作、改ざん防止 |
| Use Case / AC | UC-002（ログイン・ログアウトの記録）、UC-013（AC-UC-013-008） | 監査ログの記録内容と非出力項目 |
| ADR | 該当なし | ログ出力方式はADDRで確定する（本書9章 BLK-005） |
| Detailed Design | .github/project-context/project-ai-steering.md（7.2）、functional_requirements.md（CMN-24、CMN-25） | 必須項目・禁止項目・監査ログの対象 |

#### Objective

アプリケーションログ（JSON Lines）と監査ログ（D-15）の共通記録基盤を用意し、機密情報を出力しない制御を行う。

#### Scope

##### In Scope

- アプリケーションログの必須項目（timestamp、level、request_id、method、path、status、user_id、duration_ms）の出力。path はクエリ文字列を除いたパスのみを出力する（NFR-SC-06 後段）。
- 監査ログ（login_success、login_failure、logout、initial_data_load）の記録インターフェース。
- 禁止項目（パスワード、トークン、メールアドレス、氏名、住所、電話番号）の非出力制御。

##### Out of Scope

- 各機能での監査ログ記録の呼び出し（TASK-005、TASK-014）。
- 監視基盤・通知設定（本番運用時に設定、NFR-OM-09）。

#### Expected Change

- app 配下のログ設定・ログ出力処理・監査ログ記録処理。

#### Constraints

- Authorization ヘッダー・要求本文をそのまま出力しない（Steering 7.2）。
- 全てのログ（LOG-01〜LOG-06）および初期データ一括投入の標準出力に禁止項目を出力しない。アクセスログ・アプリケーションログの path にクエリ文字列を含めない（NFR-SC-06。FR-041 の注文検索が購入者メールアドレスをクエリで受け取るため）。
- 監査ログは DB（D-15）に記録し、アプリケーションログとは分離する。

#### Completion Criteria / Definition of Done

- [ ] アプリケーションログが1行1イベントのJSONで出力される。
- [ ] request_id が応答ヘッダーとログで一致する。
- [ ] 禁止項目がログ・監査ログに出力されない。
- [ ] ログの path にクエリ文字列が含まれない（NFR-SC-06）。
- [ ] 監査ログの記録インターフェースが利用できる。
- [ ] ruff check の指摘が0件である。
- [ ] 要件に無いログ項目を追加していない。

#### Validation

| Validation Type | Command / Method | Expected Result |
| --- | --- | --- |
| Build | docker compose build | PASS |
| Static Check | docker compose exec app ruff check . | PASS（指摘0件） |
| Unit Test | docker compose exec app pytest | PASS |
| Other | ログ出力の文字列検索（禁止項目が含まれないこと） | 検出0件 |
| Other | クエリ文字列を伴う要求（FR-041 の注文検索）実行後のログ確認 | path にクエリ文字列が含まれない（検出0件） |

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

- 監査ログの保管1年、アプリケーションログの保管90日は運用設定として記録する。

### TASK-005 `認証・利用者機能の実装`

#### Metadata

| 項目 | 内容 |
| --- | --- |
| Type | IMPLEMENT |
| Priority | HIGH |
| Status | TODO |
| Target Area | app（認証・利用者） |
| Depends On | TASK-002, TASK-003, TASK-004 |
| Blocks | TASK-008, TASK-015 |

#### Source References

| Type | ID / Path | Relevant Section / Reason |
| --- | --- | --- |
| Requirement | FR-001, FR-002, FR-003, FR-004 | 会員登録・ログイン・ログアウト・ログイン利用者情報照会 |
| Requirement | NFR-SC-01, NFR-SC-08, NFR-SC-09, NFR-SC-12, NFR-SC-16, NFR-SC-18, NFR-SC-19, NFR-PF-09 | パスワード保存方式・トークン保護・無操作タイムアウト・多重ログイン・認証系応答時間 |
| Use Case / AC | UC-001（AC-UC-001-001〜019）、UC-002（AC-UC-002-001〜021） | 登録・ログイン・ログアウトの合否判定基準 |
| ADR | 該当なし | 認証方式・パスワードハッシュはADDRで確定する（本書9章 BLK-002、BLK-008） |
| Detailed Design | docs/specifications/api-contract.md（6.1 FR-001〜FR-004、6.2） | エンドポイント・成功ステータス・エラーコード |

#### Objective

会員登録と認証（トークン・ログインセッション）およびログイン利用者情報照会を、要件の判定順序・エラーコードどおりに実装する。

#### Scope

##### In Scope

- 会員登録（購入者のみ作成、メールアドレス正規化、重複時 EMAIL_ALREADY_REGISTERED）。
- ログイン（INVALID_CREDENTIALS の区別なし、token・expires_at・user の応答、監査ログ記録）。
- ログアウト（トークン無効化、204、監査ログ記録）とログイン利用者情報照会。
- ロール（buyer／admin）と所有者判定の共通適用。

##### Out of Scope

- 画面側のフォーム・遷移（TASK-015）。
- アカウントロック・試行回数制限（FR-OUT-11 により対象外）。

#### Expected Change

- app 配下の認証・利用者機能のAPI、認証情報の保持・検証処理。

#### Constraints

- 管理者は初期データ一括投入でのみ作成する（CMN-08）。
- 認証トークンの有効期間は発行時刻から24時間（CMN-09）。ログアウトは要求に使われた認証トークン（画面ではそのログインセッション）のみを無効化する（CMN-12）。同一利用者の多重ログインを認め、既存のトークン・セッションは有効期間内であれば有効のままとする（CMN-11）。
- パスワードはソルト付き一方向ハッシュで保存する（NFR-SC-01）。

#### Completion Criteria / Definition of Done

- [ ] FR-001〜FR-004 の入力検証・判定順序・エラーコードが要件どおりである。
- [ ] UC-001・UC-002 の Acceptance Criteria を満たせる状態である。
- [ ] 監査ログ（login_success、login_failure、logout）が記録される。
- [ ] ruff check の指摘が0件である。
- [ ] docker compose exec app pytest がPASSする。
- [ ] 要件に無い認証機能（ロック等）を追加していない。

#### Validation

| Validation Type | Command / Method | Expected Result |
| --- | --- | --- |
| Build | docker compose build | PASS |
| Static Check | docker compose exec app ruff check . | PASS（指摘0件） |
| Unit Test | docker compose exec app pytest | PASS |
| Other | UC-001・UC-002 の AC と応答・DB状態の照合 | 一致 |

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

- 画面セッションとAPIトークンの併存方式はADDR確定後に実装する（BLK-002）。

### TASK-006 `商品カタログ参照機能の実装`

#### Metadata

| 項目 | 内容 |
| --- | --- |
| Type | IMPLEMENT |
| Priority | HIGH |
| Status | TODO |
| Target Area | app（商品・商品分類・在庫単位の参照） |
| Depends On | TASK-002, TASK-003 |
| Blocks | TASK-008, TASK-015 |

#### Source References

| Type | ID / Path | Relevant Section / Reason |
| --- | --- | --- |
| Requirement | FR-010, FR-011, FR-012 | 商品分類一覧・商品一覧検索・商品詳細照会 |
| Requirement | NFR-PF-01, NFR-PF-08, NFR-SC-04, NFR-LG-02 | 参照系応答時間、件数上限、外部入力の検証とプレースホルダによるDB操作、総額表示 |
| Use Case / AC | UC-003（AC-UC-003-001〜021） | 検索・並べ替え・税込表示・在庫表示の合否判定基準 |
| ADR | 該当なし | 検索・索引方式はADDRで確定する（本書9章 BLK-006） |
| Detailed Design | docs/specifications/api-contract.md（6.1 FR-010〜FR-012、応答項目の命名） | collections、stock_units、min_price 等の応答項目 |

#### Objective

来訪者・購入者が認証なしで商品を検索・閲覧でき、税込価格と在庫の有無を確認できる参照APIを実装する。

#### Scope

##### In Scope

- 商品分類一覧（ページングなし、全件配列）。
- 商品一覧検索（分類・キーワード絞り込み、並べ替え、20件/ページ）。
- 商品詳細（在庫単位ごとの税抜・税込価格、在庫数量、SKU昇順）。

##### Out of Scope

- カート投入操作（TASK-008）。
- 管理者向けの在庫単位一覧（TASK-013）。

#### Expected Change

- app 配下の商品カタログ参照API。

#### Constraints

- 非公開商品・在庫単位を持たない商品の扱いは FR-011・FR-012 の規定に従う。
- 検索条件（分類・キーワード・並べ替え）をサーバー側で検証し、DB の操作はプレースホルダ（パラメータ化）で行う。SQL 文を入力値の文字列連結で組み立てない（NFR-SC-04）。
- 並べ替えは Unicode のコードポイント順で判定する（CMN-36）。
- 税込価格は税抜価格×110÷100 の1円未満切り捨て（CMN-32）。

#### Completion Criteria / Definition of Done

- [ ] FR-010〜FR-012 の検索条件・並び順・ページングが要件どおりである。
- [ ] UC-003 の Acceptance Criteria を満たせる状態である。
- [ ] 応答項目名が api-contract.md の命名と一致する。
- [ ] ruff check の指摘が0件である。
- [ ] docker compose exec app pytest がPASSする。
- [ ] 要件に無い検索条件を追加していない。

#### Validation

| Validation Type | Command / Method | Expected Result |
| --- | --- | --- |
| Build | docker compose build | PASS |
| Static Check | docker compose exec app ruff check . | PASS（指摘0件） |
| Unit Test | docker compose exec app pytest | PASS |
| Other | UC-003 の AC と応答の照合 | 一致 |

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

- 応答性能に関する索引方式はADDR確定後に反映する（BLK-006）。索引・問い合わせ方式を変更する場合も NFR-SC-04（プレースホルダ、文字列連結の禁止）を満たすこと。

### TASK-007 `注文金額計算の実装`

#### Metadata

| 項目 | 内容 |
| --- | --- |
| Type | IMPLEMENT |
| Priority | HIGH |
| Status | TODO |
| Target Area | app（金額計算の共通ロジック） |
| Depends On | TASK-002, TASK-003 |
| Blocks | TASK-008, TASK-010 |

#### Source References

| Type | ID / Path | Relevant Section / Reason |
| --- | --- | --- |
| Requirement | FR-026 | 小計・割引額・割引後小計・送料・消費税額・合計の算出手順と適用可否判定 |
| Requirement | NFR-LG-02 | 総額表示（税込）の法令要件 |
| Use Case / AC | UC-004（AC-UC-004-008 他の金額内訳）、UC-005（クーポン適用時の金額） | 金額内訳の期待値 |
| ADR | 該当なし | 重要判断は不要と見込むが、要否はADDRが判定する |
| Detailed Design | functional_requirements.md（CMN-30、CMN-31、CMN-32） | 端数処理・税率・表示方針 |

#### Objective

カートと注文で共通に使用する金額計算を、要件の手順・端数処理どおりに単一の業務ロジックとして実装する。

#### Scope

##### In Scope

- 小計、クーポン適用可否判定（有効期間→最低購入金額の順）、割引額、割引後小計、送料、消費税額、合計の算出。
- 明細0件時の金額0とクーポン適用不可理由 CART_EMPTY の返却。

##### Out of Scope

- クーポンの適用・解除操作（TASK-009）。
- 注文確定時の在庫引当（TASK-010）。

#### Expected Change

- app 配下の金額計算ロジック（画面・APIから共通に呼び出す）。

#### Constraints

- 端数は各計算段階で1円未満切り捨て（CMN-30）。
- 送料は割引後小計5,000円以上で0円、未満で500円。
- 業務ルールを画面側に重複実装しない（Steering 4.2）。

#### Completion Criteria / Definition of Done

- [ ] FR-026 の手順1〜8と計算例7件の結果が一致する。
- [ ] 適用不可理由（COUPON_NOT_YET_VALID、COUPON_EXPIRED、COUPON_MIN_SPEND_NOT_MET、CART_EMPTY）を返せる。
- [ ] 金額計算がカートと注文確定から共通に呼び出せる。
- [ ] ruff check の指摘が0件である。
- [ ] docker compose exec app pytest がPASSする。
- [ ] 要件に無い割引・送料条件を追加していない。

#### Validation

| Validation Type | Command / Method | Expected Result |
| --- | --- | --- |
| Build | docker compose build | PASS |
| Static Check | docker compose exec app ruff check . | PASS（指摘0件） |
| Unit Test | docker compose exec app pytest | PASS（FR-026 の計算例を網羅） |
| Other | FR-026 の計算例と算出結果の照合 | 一致 |

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

- 本Taskは計算のみを担当し、データ更新は行わない（FR-026 事後条件）。

### TASK-008 `カート機能の実装`

#### Metadata

| 項目 | 内容 |
| --- | --- |
| Type | IMPLEMENT |
| Priority | HIGH |
| Status | TODO |
| Target Area | app（カート） |
| Depends On | TASK-005, TASK-006, TASK-007 |
| Blocks | TASK-009, TASK-010, TASK-015 |

#### Source References

| Type | ID / Path | Relevant Section / Reason |
| --- | --- | --- |
| Requirement | FR-020, FR-021, FR-022, FR-023, FR-026 | カート照会・明細追加・数量変更・削除と金額表示 |
| Requirement | NFR-PF-02, NFR-PF-07 | 更新系応答時間、整合性を伴う同時実行性能 |
| Use Case / AC | UC-004（AC-UC-004-001〜027） | 数量上限10・在庫数量以下・明細操作の合否判定基準 |
| ADR | 該当なし | 同時実行制御方式はADDRで確定する（本書9章 BLK-001） |
| Detailed Design | docs/specifications/api-contract.md（6.1 FR-020〜FR-023、6.3） | 応答形式とエラーの context |

#### Objective

購入者のカート操作を実装し、更新後は常にカート表現（明細・クーポン・金額）を返す。

#### Scope

##### In Scope

- 利用中カートの特定・作成（1購入者につき最大1件）。
- 明細追加（同一在庫単位は既存明細へ加算）、数量変更、削除。
- QUANTITY_LIMIT_EXCEEDED・INSUFFICIENT_STOCK・NOT_FOUND の判定と context 返却。

##### Out of Scope

- クーポン適用・解除（TASK-009）。
- 在庫の引当（注文確定時に行う。TASK-010）。

#### Expected Change

- app 配下のカートAPIとカート業務ロジック。

#### Constraints

- カート投入時に在庫を引き当てない（UC-004）。
- 同一在庫単位は1カートにつき10個以下（US-018、FR-021、FR-022）。
- admin は購入機能を利用できない（PERMISSION_DENIED）。

#### Completion Criteria / Definition of Done

- [ ] FR-020〜FR-023 の判定順序・エラーコード・context が要件どおりである。
- [ ] 更新後の応答が FR-020 と同じカート表現である。
- [ ] UC-004 の Acceptance Criteria を満たせる状態である。
- [ ] ruff check の指摘が0件である。
- [ ] docker compose exec app pytest がPASSする。
- [ ] 要件に無いカート操作を追加していない。

#### Validation

| Validation Type | Command / Method | Expected Result |
| --- | --- | --- |
| Build | docker compose build | PASS |
| Static Check | docker compose exec app ruff check . | PASS（指摘0件） |
| Unit Test | docker compose exec app pytest | PASS |
| Other | UC-004 の AC と応答・DB状態の照合 | 一致 |

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

- 同一カートへの同時操作の直列化方式はADDR確定後に実装する（BLK-001）。

### TASK-009 `クーポン適用・解除の実装`

#### Metadata

| 項目 | 内容 |
| --- | --- |
| Type | IMPLEMENT |
| Priority | HIGH |
| Status | TODO |
| Target Area | app（カート・クーポン） |
| Depends On | TASK-008 |
| Blocks | TASK-010, TASK-015 |

#### Source References

| Type | ID / Path | Relevant Section / Reason |
| --- | --- | --- |
| Requirement | FR-024, FR-025, FR-026 | クーポン適用・解除と適用可否の判定 |
| Use Case / AC | UC-005（AC-UC-005-001〜030） | 有効期間・最低購入金額・1枚制限の合否判定基準 |
| ADR | 該当なし | 重要判断の要否はADDRが判定する |
| Detailed Design | docs/specifications/api-contract.md（6.1 FR-024・FR-025、6.3） | coupon 応答項目とエラーの context |

#### Objective

カートへのクーポン適用・解除を実装し、適用中クーポンの可否と理由をカート表現へ反映する。

#### Scope

##### In Scope

- クーポン適用（1枚のみ、COUPON_NOT_FOUND・COUPON_ALREADY_APPLIED・期間外・最低購入金額未達・CART_EMPTY の判定）。
- クーポン解除と、解除後の金額再計算。
- 適用後に条件を満たさなくなった場合も自動で外さない扱い。

##### Out of Scope

- 注文確定時のクーポン再判定（TASK-010）。
- クーポンのマスタ登録（TASK-014）。

#### Expected Change

- app 配下のクーポン適用・解除APIとカートへの反映処理。

#### Constraints

- 1カートに適用できるクーポンは1枚（FR-024）。
- 判定順序は有効期間→最低購入金額（FR-026 手順3）。
- 日時判定は秒単位・JST（CMN-29）。

#### Completion Criteria / Definition of Done

- [ ] FR-024・FR-025 の判定順序とエラーコードが要件どおりである。
- [ ] 適用不可理由がカート表現に反映される。
- [ ] UC-005 の Acceptance Criteria を満たせる状態である。
- [ ] ruff check の指摘が0件である。
- [ ] docker compose exec app pytest がPASSする。
- [ ] 要件に無いクーポン種別・併用を追加していない。

#### Validation

| Validation Type | Command / Method | Expected Result |
| --- | --- | --- |
| Build | docker compose build | PASS |
| Static Check | docker compose exec app ruff check . | PASS（指摘0件） |
| Unit Test | docker compose exec app pytest | PASS |
| Other | UC-005 の AC と応答の照合 | 一致 |

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

- 境界値（有効終了日時と同秒）の扱いは CMN-29 に従う。

### TASK-010 `注文確定の実装`

#### Metadata

| 項目 | 内容 |
| --- | --- |
| Type | IMPLEMENT |
| Priority | HIGH |
| Status | TODO |
| Target Area | app（注文確定・在庫引当） |
| Depends On | TASK-008, TASK-009 |
| Blocks | TASK-011, TASK-012, TASK-015 |

#### Source References

| Type | ID / Path | Relevant Section / Reason |
| --- | --- | --- |
| Requirement | FR-030, FR-026 | 配送先入力、確定時の再判定、在庫一括引当、注文番号採番、金額確定 |
| Requirement | NFR-PF-02, NFR-PF-07, NFR-LG-03 | 更新系応答時間、同時実行整合、帳簿保存 |
| Use Case / AC | UC-006（AC-UC-006-001〜032） | 注文確定の合否判定基準（在庫・数量上限・クーポン再判定・二重送信） |
| ADR | 該当なし | 同時実行制御と採番方式はADDRで確定する（本書9章 BLK-001、BLK-003） |
| Detailed Design | docs/specifications/api-contract.md（6.1 FR-030、6.2、6.3） | 201応答・注文詳細表現・業務エラーの context |

#### Objective

カート内容と配送先から注文を1件作成し、全明細の在庫引当・金額確定・状態履歴記録までを一括で確定する。

#### Scope

##### In Scope

- 配送先の入力検証、確定時の再判定（公開状態・数量上限・クーポン条件・在庫数量）。
- 全明細の在庫引当、注文・注文明細・配送先・注文状態履歴の登録、カートの注文済への変更。
- 注文番号の採番（PO-＋8桁ゼロ埋め、欠番許容）と 201 応答。

##### Out of Scope

- 支払処理（TASK-011）。
- 管理者による状態変更（TASK-013）。

#### Expected Change

- app 配下の注文確定APIと注文確定の業務ロジック。

#### Constraints

- すべて成功するか何も変更しないかのどちらかとする（CMN-21）。
- 在庫数量は0未満にならない（CMN-20）。
- 同一カートからの二重送信で作成する注文は1件（CMN-23）。

#### Completion Criteria / Definition of Done

- [ ] FR-030 の手順・判定順序・エラーコード・context が要件どおりである。
- [ ] UC-006 の Acceptance Criteria を満たせる状態である。
- [ ] 注文状態履歴が1件記録される（CMN-26）。
- [ ] ruff check の指摘が0件である。
- [ ] docker compose exec app pytest がPASSする。
- [ ] 要件に無い注文項目・状態を追加していない。

#### Validation

| Validation Type | Command / Method | Expected Result |
| --- | --- | --- |
| Build | docker compose build | PASS |
| Static Check | docker compose exec app ruff check . | PASS（指摘0件） |
| Unit Test | docker compose exec app pytest | PASS |
| Other | UC-006 の AC と応答・DB状態の照合 | 一致 |

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

- 在庫引当の直列化と注文番号採番はADDR確定後に実装する（BLK-001、BLK-003）。

### TASK-011 `支払（模擬決済）と決済インターフェースの実装`

#### Metadata

| 項目 | 内容 |
| --- | --- |
| Type | IMPLEMENT |
| Priority | HIGH |
| Status | TODO |
| Target Area | app（支払・決済サービス模擬機能） |
| Depends On | TASK-010 |
| Blocks | TASK-013, TASK-015 |

#### Source References

| Type | ID / Path | Relevant Section / Reason |
| --- | --- | --- |
| Requirement | FR-031 | 支払の判定順序、決済記録の登録、状態遷移 |
| Requirement | NFR-PF-02, NFR-EN-05, NFR-LG-05 | 更新系応答時間、外部接続禁止、クレジットカード情報の非保持 |
| Use Case / AC | UC-007（AC-UC-007-001〜019） | 承認・否認・連携エラー・二重送信の合否判定基準 |
| ADR | 該当なし | 模擬機能の配置・呼出境界はADDRで確定する（本書9章 BLK-009） |
| Detailed Design | docs/requirements/external_interface_requirements.md（IF-01、IF-01-DAT、IF-01-EXC、IF-01-CON） | 要求・応答項目、例外、整合性ルール |

#### Objective

注文受付状態の自分の注文に対する支払を実装し、決済サービス（模擬）の結果に応じて注文状態と決済記録を更新する。

#### Scope

##### In Scope

- 決済要求（注文番号・決済金額・通貨JPY・模擬決済指示）と応答（結果・取引参照番号・否認理由コード・処理日時）の取り扱い。
- 承認時の決済記録登録・支払済への状態変更・支払日時・状態履歴記録の一括確定。
- 否認・応答不正・タイムアウト（10秒）時の決済記録登録と PAYMENT_DECLINED／PAYMENT_SERVICE_ERROR の返却。

##### Out of Scope

- 実決済サービスへの接続（Steering 11章で禁止、OQ-PJ-002）。
- 返金処理（本システム外）。

#### Expected Change

- app 配下の支払APIと決済サービス模擬機能、決済記録の登録処理。

#### Constraints

- 自動再送しない（二重決済防止、IF-01-EXC-02）。
- 1注文につき承認済みの決済記録は最大1件（IF-01-CON-01）。
- 外部ネットワークへ接続しない（NFR-EN-05）。

#### Completion Criteria / Definition of Done

- [ ] FR-031 の判定順序・エラーコード・状態遷移が要件どおりである。
- [ ] 否認・連携エラー時も決済記録が登録され、注文は注文受付のままである。
- [ ] UC-007 の Acceptance Criteria を満たせる状態である。
- [ ] ruff check の指摘が0件である。
- [ ] docker compose exec app pytest がPASSする。
- [ ] 実決済サービスへの接続処理を含んでいない。

#### Validation

| Validation Type | Command / Method | Expected Result |
| --- | --- | --- |
| Build | docker compose build | PASS |
| Static Check | docker compose exec app ruff check . | PASS（指摘0件） |
| Unit Test | docker compose exec app pytest | PASS |
| Other | UC-007 の AC と応答・決済記録の照合 | 一致 |

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

- 模擬決済指示（approve／decline、既定 approve）の受け渡し経路はADDR確定後に実装する（BLK-009）。

### TASK-012 `購入者の注文照会・キャンセルの実装`

#### Metadata

| 項目 | 内容 |
| --- | --- |
| Type | IMPLEMENT |
| Priority | HIGH |
| Status | TODO |
| Target Area | app（購入者の注文参照・キャンセル） |
| Depends On | TASK-010 |
| Blocks | TASK-013, TASK-015 |

#### Source References

| Type | ID / Path | Relevant Section / Reason |
| --- | --- | --- |
| Requirement | FR-032, FR-033, FR-034 | 注文履歴一覧・注文詳細・注文キャンセル（購入者） |
| Requirement | NFR-PF-01, NFR-PF-08, NFR-SC-24 | 参照系応答時間、件数上限、個人情報の参照範囲 |
| Use Case / AC | UC-008（AC-UC-008-001〜015）、UC-009（AC-UC-009-001〜010） | 一覧・詳細・キャンセルと在庫戻しの合否判定基準 |
| ADR | 該当なし | 同時実行制御方式はADDRで確定する（本書9章 BLK-001） |
| Detailed Design | docs/specifications/api-contract.md（6.1 FR-032〜FR-034、応答項目の命名） | ページング形式・注文詳細表現・status_history |

#### Objective

購入者が自分の注文だけを一覧・詳細で確認でき、出荷前の注文をキャンセルして在庫を戻せるようにする。

#### Scope

##### In Scope

- 注文履歴一覧（自分の注文のみ、20件/ページ）。
- 注文詳細（明細・金額・配送先・状態履歴、can_pay／can_cancel）。
- キャンセル（注文受付・支払済のみ、全明細の在庫戻し、状態履歴記録）。

##### Out of Scope

- 管理者による注文参照・キャンセル（TASK-013）。
- 返金処理（本システム外）。

#### Expected Change

- app 配下の購入者向け注文参照・キャンセルAPI。

#### Constraints

- 他人の注文の指定は NOT_FOUND とし存在有無を明かさない（CMN-04、PRM-01）。
- 出荷済・配達完了・キャンセル済は INVALID_STATUS_TRANSITION（409）。
- キャンセルは全明細の在庫戻しを一括で確定する（CMN-21）。

#### Completion Criteria / Definition of Done

- [ ] FR-032〜FR-034 の判定順序・エラーコードが要件どおりである。
- [ ] UC-008・UC-009 の Acceptance Criteria を満たせる状態である。
- [ ] キャンセル時に在庫数量が戻り、状態履歴が記録される。
- [ ] ruff check の指摘が0件である。
- [ ] docker compose exec app pytest がPASSする。
- [ ] 他購入者の注文が参照できないことを確認している。

#### Validation

| Validation Type | Command / Method | Expected Result |
| --- | --- | --- |
| Build | docker compose build | PASS |
| Static Check | docker compose exec app ruff check . | PASS（指摘0件） |
| Unit Test | docker compose exec app pytest | PASS |
| Other | UC-008・UC-009 の AC と応答・DB状態の照合 | 一致 |

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

- 支払とキャンセルの競合時の扱いは IF-01-CON-01 と CMN-19 に従う。

### TASK-013 `管理者機能（在庫単位一覧・注文管理）の実装`

#### Metadata

| 項目 | 内容 |
| --- | --- |
| Type | IMPLEMENT |
| Priority | HIGH |
| Status | TODO |
| Target Area | app（管理者API） |
| Depends On | TASK-011, TASK-012 |
| Blocks | TASK-015 |

#### Source References

| Type | ID / Path | Relevant Section / Reason |
| --- | --- | --- |
| Requirement | FR-040, FR-041, FR-042, FR-043, FR-044, FR-045 | 在庫単位一覧・注文検索・注文詳細・出荷登録・配達完了登録・キャンセル |
| Requirement | NFR-PF-01, NFR-PF-08, NFR-SC-03, NFR-SC-04 | 参照系応答時間、件数上限、ロールによるアクセス制御、外部入力の検証とプレースホルダによるDB操作 |
| Use Case / AC | UC-010（AC-UC-010-001〜012）、UC-011（AC-UC-011-001〜021）、UC-012（AC-UC-012-001〜011） | 在庫確認・出荷登録・配達完了・管理者キャンセルの合否判定基準 |
| ADR | 該当なし | 同時実行制御方式はADDRで確定する（本書9章 BLK-001） |
| Detailed Design | docs/specifications/api-contract.md（6.1 FR-040〜FR-045、応答項目の命名） | 管理者向け注文詳細表現・payment_records・buyer |

#### Objective

管理者が在庫単位と注文を確認し、支払済注文の出荷登録・出荷済注文の配達完了登録・出荷前注文のキャンセルを行えるようにする。

#### Scope

##### In Scope

- 在庫単位一覧（50件/ページ、低在庫絞り込み）。
- 注文検索（注文番号・状態の複数指定・注文日範囲・購入者メールアドレス、20件/ページ）と管理者向け注文詳細。
- 出荷登録（配送伝票番号は任意）、配達完了登録、管理者キャンセル（在庫戻し）と状態履歴記録。

##### Out of Scope

- マスタの登録・更新（初期データ一括投入のみ。CMN-38）。
- 購入機能の利用（admin は利用不可）。

#### Expected Change

- app 配下の管理者向けAPI。

#### Constraints

- buyer の管理者APIアクセスは PERMISSION_DENIED（403）。
- 注文検索の条件（注文番号・状態・注文日範囲・購入者メールアドレス）をサーバー側で検証し、DB の操作はプレースホルダ（パラメータ化）で行う。SQL 文を入力値の文字列連結で組み立てない（NFR-SC-04）。
- 状態遷移は注文受付→支払済→出荷済→配達完了の順のみ（ST-PO）。
- 管理者キャンセルは出荷前のみ、全明細の在庫を戻す。

#### Completion Criteria / Definition of Done

- [ ] FR-040〜FR-045 の検索条件・判定順序・エラーコードが要件どおりである。
- [ ] UC-010〜UC-012 の Acceptance Criteria を満たせる状態である。
- [ ] 状態変更ごとに注文状態履歴が記録される（CMN-26）。
- [ ] ruff check の指摘が0件である。
- [ ] docker compose exec app pytest がPASSする。
- [ ] 要件に無い管理機能を追加していない。

#### Validation

| Validation Type | Command / Method | Expected Result |
| --- | --- | --- |
| Build | docker compose build | PASS |
| Static Check | docker compose exec app ruff check . | PASS（指摘0件） |
| Unit Test | docker compose exec app pytest | PASS |
| Other | UC-010〜UC-012 の AC と応答・DB状態の照合 | 一致 |

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

- 管理者向け応答に含める購入者情報の範囲は NFR-SC-24 に従う。
- 購入者メールアドレスは検索条件としてクエリで受け取るため、ログ出力では path にクエリ文字列を含めない（NFR-SC-06。基盤は TASK-004）。
- 索引・問い合わせ方式はADDR確定後に反映する（BLK-006）。方式の変更時も NFR-SC-04 を満たすこと。

### TASK-014 `初期データ一括投入コマンドの実装`

#### Metadata

| 項目 | 内容 |
| --- | --- |
| Type | IMPLEMENT |
| Priority | HIGH |
| Status | TODO |
| Target Area | app（管理コマンド・seed） |
| Depends On | TASK-002, TASK-004 |
| Blocks | TASK-016 |

#### Source References

| Type | ID / Path | Relevant Section / Reason |
| --- | --- | --- |
| Requirement | FR-060 | 定義ファイルの読込・検証・全削除・登録・監査ログ・終了コード |
| Requirement | NFR-OM-04, NFR-MG-02, NFR-PF-10, NFR-SC-01, NFR-SC-04, NFR-SC-06 | 投入操作、件数一致の検証、投入時間の目標値（60秒以内）、パスワード保存方式、定義ファイルの全件検証、機密情報の非出力 |
| Use Case / AC | UC-013（AC-UC-013-001〜011） | 投入・違反・全削除・監査ログ・起動経路の合否判定基準 |
| ADR | 該当なし | 定義ファイルの構造はADDRで確定する（本書9章 BLK-010） |
| Detailed Design | docs/architecture/files/FILE-001.md（FILE-001） | 項目定義・編集変換ルール・異常処理・検証観点 |

#### Objective

運用者がコマンド1回で定義ファイルから初期データを投入でき、違反時は何も変更しない管理コマンドを実装する。

#### Scope

##### In Scope

- 引数・オプション判定、UTF-8 JSON の読込、値域・一意性・参照整合性の全件判定。
- 全削除指定時の監査ログ以外の全データ削除と、業務キーによる参照解決を伴う登録。
- データ別投入件数の標準出力、違反の全件出力、監査ログ1件記録、終了コード制御。

##### Out of Scope

- Web画面・Web APIからの実行手段（CMN-37 により提供しない）。
- 本番環境での全削除指定の実行（Steering 11章で禁止）。

#### Expected Change

- app 配下の管理コマンド（load_initial_data）と定義ファイル読込・検証・登録処理。
- app/seed/ 配下の検証用定義ファイル（架空値のみ）。

#### Constraints

- 違反が1件でもあれば削除も登録も行わない（FR-060、AC-UC-013-007）。
- 定義ファイルの全項目をサーバー側で検証し（型・桁数・値域・形式）、DB の操作はプレースホルダで行う。外部入力を OS コマンドに渡さない（NFR-SC-04）。
- パスワードはハッシュ化して保持し、平文・個人情報を出力しない（NFR-SC-01、NFR-SC-06）。
- 定義ファイルの仕様は FILE-001 に従い、未確定項目（OQ-FILE-001、OQ-FILE-002）はADDR確定後に実装する。

#### Completion Criteria / Definition of Done

- [ ] FR-060 の手順1〜13と例外（E-060-01〜E-060-06）が要件どおりである。
- [ ] UC-013 の Acceptance Criteria を満たせる状態である。
- [ ] 成功・失敗とも監査ログが1件記録される。
- [ ] ruff check の指摘が0件である。
- [ ] docker compose exec app pytest がPASSする。
- [ ] 定義ファイル・テストデータに実在の個人情報を使用していない。

#### Validation

| Validation Type | Command / Method | Expected Result |
| --- | --- | --- |
| Build | docker compose build | PASS |
| Static Check | docker compose exec app ruff check . | PASS（指摘0件） |
| Unit Test | docker compose exec app pytest | PASS |
| Other | docker compose exec app python manage.py load_initial_data seed/initial_data.json --reset | 終了コード0と件数一致（AC-UC-013-001、AC-UC-013-004） |

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

- 本Taskは FILE-001 の項目定義を実装の詳細仕様として参照する。
- NFR-PF-10（初期データ1,157件の投入を60秒以内、推奨）は移行リハーサル（VDC-04）で計測する項目であり、本コマンドが計測対象となる。

### TASK-015 `画面（購入者・管理者・エラー）の実装`

#### Metadata

| 項目 | 内容 |
| --- | --- |
| Type | IMPLEMENT |
| Priority | HIGH |
| Status | TODO |
| Target Area | app（テンプレート・画面ビュー） |
| Depends On | TASK-005, TASK-006, TASK-008, TASK-009, TASK-010, TASK-011, TASK-012, TASK-013 |
| Blocks | TASK-016 |

#### Source References

| Type | ID / Path | Relevant Section / Reason |
| --- | --- | --- |
| Requirement | FR-001, FR-002, FR-003, FR-011, FR-012, FR-020, FR-030, FR-031, FR-033, FR-040, FR-041, FR-043 | 各画面が起動する機能と表示・操作 |
| Requirement | NFR-US-01, NFR-US-02, NFR-US-03, NFR-US-04, NFR-US-07, NFR-US-09, NFR-US-10, NFR-SC-05, NFR-PF-03 | 対応ブラウザ・解像度・表示言語と使用可能文字・入力エラー表示・キーボード操作・取消できない操作の確認ダイアログ・二重送信防止・XSS/CSRF対策・画面表示時間 |
| Use Case / AC | UC-001〜UC-012 の画面操作に関する AC | 画面での表示項目・メッセージ・遷移の合否判定基準 |
| ADR | 該当なし | 画面とAPIの共通化方式はADDRで確定する（本書9章 BLK-002、BLK-004） |
| Detailed Design | docs/requirements/ui_report_requirements.md（SCR-001〜SCR-103、SCR-901） | 画面項目・操作・メッセージ・遷移の正本 |

#### Objective

サーバーサイドレンダリングで購入者・管理者の各画面を実装し、APIと同一の業務ロジック・エラーコードで動作させる。

#### Scope

##### In Scope

- 購入者・来訪者の画面（商品一覧・商品詳細・会員登録・ログイン・カート・注文手続き・注文完了・支払・注文履歴・注文詳細）。
- 管理者の画面（在庫単位一覧・注文一覧・注文詳細）とエラー画面。
- 入力エラーの項目近傍表示、業務エラーの上部表示、二重送信防止、CSRF対策、出力のエスケープ。
- 取消できない操作（注文確定、注文キャンセル、出荷登録、配達完了登録、カート明細の削除）の実行前の確認ダイアログ表示と、承諾した場合のみの実行（NFR-US-09。JavaScript の用途は確認ダイアログと二重送信防止に限る：NFR-EN-09）。

##### Out of Scope

- SPAフレームワーク・フロントエンドのビルド工程・外部CDNの利用（Steering 3章で禁止）。
- 要件に無い画面の追加。

#### Expected Change

- app 配下の画面ビューとDjangoテンプレート、画面用の静的ファイル（最小限）。

#### Constraints

- 業務ルールを画面側へ重複実装しない（Steering 4.2）。
- 画面とAPIは同一の判定順序・エラーコードに従う（CMN-34）。
- 画面幅1280px以上、Chrome・Edge最新版（NFR-US-01、NFR-US-02）。

#### Completion Criteria / Definition of Done

- [ ] SCR-001〜SCR-103 と SCR-901 の表示項目・操作・遷移が要件どおりである。
- [ ] 画面経由でも UC-001〜UC-012 の Acceptance Criteria を満たせる状態である。
- [ ] 入力エラー時に入力値が保持される（CMN-17。パスワードは除く）。
- [ ] 取消できない5操作で確認ダイアログが表示され、取消を選んだ場合にデータが変更されない（NFR-US-09）。
- [ ] 表示言語が日本語のみで、UTF-8 で符号化できる文字を表示・保持できる（NFR-US-03）。
- [ ] キーボードだけで全画面の全操作を行える（NFR-US-07、推奨）。
- [ ] ruff check の指摘が0件である。
- [ ] docker compose exec app pytest がPASSする。
- [ ] 要件に無い画面・操作を追加していない。

#### Validation

| Validation Type | Command / Method | Expected Result |
| --- | --- | --- |
| Build | docker compose build | PASS |
| Static Check | docker compose exec app ruff check . | PASS（指摘0件） |
| Unit Test | docker compose exec app pytest | PASS |
| Other | ui_report_requirements.md の画面項目・メッセージとの照合 | 一致 |

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

- 画面側の認証保持方式（ログインセッション）はADDR確定後に実装する（BLK-002）。

### TASK-016 `起動・運用手順ドキュメントの整備`

#### Metadata

| 項目 | 内容 |
| --- | --- |
| Type | OTHER |
| Priority | MEDIUM |
| Status | TODO |
| Target Area | リポジトリルート（README） |
| Depends On | TASK-014, TASK-015 |
| Blocks | None |

#### Source References

| Type | ID / Path | Relevant Section / Reason |
| --- | --- | --- |
| Requirement | NFR-OM-19, NFR-OM-04, NFR-OM-05, NFR-OM-15, NFR-SC-07 | 運用手順書の整備、初期データ投入の操作、起動、リリース作業、秘密情報の扱い |
| Requirement | NFR-SC-11, NFR-OM-14 | リリース前の依存ライブラリ脆弱性確認（CVSS 7.0以上 0件）と、稼働後の確認頻度（月1回）・パッチ適用手順の記載（NFR-OM-14 の代替確認） |
| Use Case / AC | UC-013（AC-UC-013-010、AC-UC-013-011） | 運用者が実行する手順と実行経路の限定 |
| ADR | 該当なし | 文書化対象は確定済み。重要判断は含まない |
| Detailed Design | .github/project-context/project-ai-steering.md（9章）、docs/architecture/files/FILE-001.md | 実行コマンドと定義ファイルの配置・仕様 |

#### Objective

起動・マイグレーション・初期データ投入・テスト・静的解析の手順を、運用者と開発者が再現できる形でREADMEへ記載する。

#### Scope

##### In Scope

- 起動・停止、マイグレーション、初期データ投入（全削除指定の注意を含む）、テスト、静的解析の手順。
- 依存ライブラリの脆弱性確認（リリース前：NFR-SC-11）とセキュリティパッチ適用（稼働後：月1回、NFR-OM-14）の手順の記載。
- .env.example の利用方法と秘密情報の取り扱い。

##### Out of Scope

- 本番環境固有の構築手順（OQ-PJ-001 により未確定）。
- 監視・バックアップの運用設定（本番運用時に設定）。

#### Expected Change

- README.md の起動・実行手順の節。

#### Constraints

- 記載するコマンドは Steering 9章と一致させる。
- 秘密情報の実値を記載しない（NFR-SC-07）。
- 本番環境での全削除指定の禁止を明記する（Steering 11章）。

#### Completion Criteria / Definition of Done

- [ ] Steering 9章の全コマンドが手順として記載されている。
- [ ] 初期データ投入の成功・失敗時の確認方法が記載されている。
- [ ] 依存ライブラリの脆弱性確認（リリース前、CVSS 7.0以上 0件）と確認頻度（月1回）・パッチ適用の手順が記載されている（NFR-SC-11、NFR-OM-14）。
- [ ] 秘密情報の実値を含まない。
- [ ] 記載手順どおりに起動・投入・テストが再現できる。
- [ ] 要件に無い運用機能を前提とした記載がない。
- [ ] 記載内容が実装済みの挙動と一致している。

#### Validation

| Validation Type | Command / Method | Expected Result |
| --- | --- | --- |
| Build | docker compose build | PASS |
| Static Check | 該当なし（Markdownのため静的解析対象外） | 該当なし |
| Unit Test | 該当なし（文書のためテスト対象外） | 該当なし |
| Other | 記載手順の再現実行（起動・migrate・seed・pytest） | 手順どおりに成功 |

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

- 運用手順の対象読者は運用者（ACT-005）と開発者とする。

## 7. Coverage / Scope Check

| Source ID | Source Type | Required Implementation | Related Task IDs | Planning Status |
| --- | --- | --- | --- | --- |
| FR-001 | REQUIREMENT | YES | TASK-005, TASK-015 | COVERED |
| FR-002 | REQUIREMENT | YES | TASK-005, TASK-015 | COVERED |
| FR-003 | REQUIREMENT | YES | TASK-005, TASK-015 | COVERED |
| FR-004 | REQUIREMENT | YES | TASK-005 | COVERED |
| FR-010 | REQUIREMENT | YES | TASK-006 | COVERED |
| FR-011 | REQUIREMENT | YES | TASK-006, TASK-015 | COVERED |
| FR-012 | REQUIREMENT | YES | TASK-006, TASK-015 | COVERED |
| FR-020 | REQUIREMENT | YES | TASK-008, TASK-015 | COVERED |
| FR-021 | REQUIREMENT | YES | TASK-008, TASK-015 | COVERED |
| FR-022 | REQUIREMENT | YES | TASK-008, TASK-015 | COVERED |
| FR-023 | REQUIREMENT | YES | TASK-008, TASK-015 | COVERED |
| FR-024 | REQUIREMENT | YES | TASK-009, TASK-015 | COVERED |
| FR-025 | REQUIREMENT | YES | TASK-009, TASK-015 | COVERED |
| FR-026 | REQUIREMENT | YES | TASK-007, TASK-008, TASK-010 | COVERED |
| FR-030 | REQUIREMENT | YES | TASK-010, TASK-015 | COVERED |
| FR-031 | REQUIREMENT | YES | TASK-011, TASK-015 | COVERED |
| FR-032 | REQUIREMENT | YES | TASK-012, TASK-015 | COVERED |
| FR-033 | REQUIREMENT | YES | TASK-012, TASK-015 | COVERED |
| FR-034 | REQUIREMENT | YES | TASK-012, TASK-015 | COVERED |
| FR-040 | REQUIREMENT | YES | TASK-013, TASK-015 | COVERED |
| FR-041 | REQUIREMENT | YES | TASK-013, TASK-015 | COVERED |
| FR-042 | REQUIREMENT | YES | TASK-013, TASK-015 | COVERED |
| FR-043 | REQUIREMENT | YES | TASK-013, TASK-015 | COVERED |
| FR-044 | REQUIREMENT | YES | TASK-013, TASK-015 | COVERED |
| FR-045 | REQUIREMENT | YES | TASK-013, TASK-015 | COVERED |
| FR-060 | REQUIREMENT | YES | TASK-014 | COVERED |
| NFR-EN-01 | REQUIREMENT | YES | TASK-001 | COVERED |
| NFR-EN-02 | REQUIREMENT | YES | TASK-001, TASK-002 | COVERED |
| NFR-EN-03 | REQUIREMENT | YES | TASK-001 | COVERED |
| NFR-EN-04 | REQUIREMENT | YES | TASK-001, TASK-002 | COVERED |
| NFR-EN-05 | REQUIREMENT | YES | TASK-001, TASK-011, TASK-015 | COVERED |
| NFR-EN-07 | REQUIREMENT | YES | TASK-001 | COVERED（コンテナ化によりホストOSに依存しない） |
| NFR-EN-08 | REQUIREMENT | YES | TASK-001 | COVERED（制約「本番で Django 付属の開発用サーバーを使用しない」はTASK-001。Web サーバー・AP サーバーの選定方式は要件が設計へ委譲しており未確定判断 BLK-011 としてADDRへ引き渡す） |
| NFR-EN-09 | REQUIREMENT | YES | TASK-001, TASK-015 | COVERED |
| NFR-EN-10 | REQUIREMENT | YES | TASK-001, TASK-016 | COVERED（サポート期限内の版での依存定義＝TASK-001、更新・パッチ適用手順の記載＝TASK-016） |
| NFR-EN-11 | REQUIREMENT | YES | TASK-001（規約・静的解析の設定）、TASK-002〜TASK-016（各実装の命名と ruff check） | COVERED |
| NFR-EN-12 | REQUIREMENT | YES | TASK-001 | COVERED（依存ライブラリのライセンス確認。推奨） |
| VUL-09 | REQUIREMENT | YES | TASK-001, TASK-016 | COVERED（確認対象＝依存定義ファイルの整備はTASK-001、リリース前・稼働後の確認手順はTASK-016） |
| VUL-10 | REQUIREMENT | YES | TASK-001, TASK-014, TASK-015 | COVERED（バージョン固定・公式配布元限定＝TASK-001、違反時に何も投入しない＝TASK-014、外部CDN不使用＝TASK-015） |
| NFR-OM-01 | REQUIREMENT | YES | TASK-004 | COVERED |
| NFR-OM-02 | REQUIREMENT | YES | TASK-004 | COVERED（出力側の実装はTASK-004。保管90日は運用設定） |
| NFR-OM-03 | REQUIREMENT | YES | TASK-004, TASK-005, TASK-014 | COVERED |
| NFR-OM-04 | REQUIREMENT | YES | TASK-014, TASK-016 | COVERED |
| NFR-OM-05 | REQUIREMENT | YES | TASK-001, TASK-016 | COVERED |
| NFR-OM-06 | REQUIREMENT | YES | TASK-001 | COVERED |
| NFR-OM-07 | REQUIREMENT | YES | TASK-001 | COVERED |
| NFR-OM-11 | REQUIREMENT | YES | TASK-004（LOG-01〜LOG-04 の基盤）、TASK-005・TASK-010〜TASK-014（各記録の呼び出し・LOG-07） | COVERED |
| NFR-OM-14 | REQUIREMENT | YES | TASK-016 | COVERED（手順書への記載。パッチ適用自体は運用作業） |
| NFR-OM-15 | REQUIREMENT | YES | TASK-016 | COVERED（リリース・切戻し手順の記載） |
| NFR-OM-17 | REQUIREMENT | YES | TASK-001 | COVERED（環境変数と .env.example による設定分離） |
| NFR-OM-18 | REQUIREMENT | YES | TASK-004 | COVERED（request_id の引き継ぎ・付与。方式は BLK-005） |
| NFR-OM-19 | REQUIREMENT | YES | TASK-016 | COVERED |
| NFR-PF-01 | REQUIREMENT | YES | TASK-006, TASK-012, TASK-013 | COVERED |
| NFR-PF-02 | REQUIREMENT | YES | TASK-008, TASK-010, TASK-011 | COVERED |
| NFR-PF-03 | REQUIREMENT | YES | TASK-015 | COVERED |
| NFR-PF-06 | REQUIREMENT | YES | TASK-006, TASK-012, TASK-013 | COVERED（将来データ量での応答時間。索引・問い合わせ方式は BLK-006 の確定後に反映） |
| NFR-PF-07 | REQUIREMENT | YES | TASK-008, TASK-010 | COVERED |
| NFR-PF-08 | REQUIREMENT | YES | TASK-003, TASK-006, TASK-012, TASK-013 | COVERED |
| NFR-PF-09 | REQUIREMENT | YES | TASK-005 | COVERED（認証系応答時間。ハッシュ方式は BLK-008 の確定後に反映） |
| NFR-PF-10 | REQUIREMENT | YES | TASK-014 | COVERED（推奨。移行リハーサルで計測する） |
| NFR-SC-01 | REQUIREMENT | YES | TASK-005, TASK-014 | COVERED |
| NFR-SC-03 | REQUIREMENT | YES | TASK-003, TASK-013 | COVERED |
| NFR-SC-04 | REQUIREMENT | YES | TASK-003, TASK-006, TASK-013, TASK-014 | COVERED（入力検証＝TASK-003・TASK-014、クエリ組み立てのプレースホルダ＝TASK-006・TASK-013） |
| NFR-SC-05 | REQUIREMENT | YES | TASK-015 | COVERED |
| NFR-SC-06 | REQUIREMENT | YES | TASK-004, TASK-013, TASK-014 | COVERED（禁止項目の非出力と path にクエリ文字列を含めない制御＝TASK-004、クエリでメールアドレスを受け取る機能＝TASK-013、標準出力＝TASK-014） |
| NFR-SC-07 | REQUIREMENT | YES | TASK-001, TASK-016 | COVERED |
| NFR-SC-08 | REQUIREMENT | YES | TASK-005 | COVERED |
| NFR-SC-09 | REQUIREMENT | YES | TASK-005, TASK-015 | COVERED |
| NFR-SC-10 | REQUIREMENT | YES | TASK-003 | COVERED |
| NFR-SC-11 | REQUIREMENT | YES | TASK-001, TASK-016 | COVERED（確認対象の依存定義ファイルの整備＝TASK-001、リリース前確認手順の記載＝TASK-016。診断ツールの実行自体はリリース作業） |
| NFR-SC-12 | REQUIREMENT | YES | TASK-005, TASK-015 | COVERED（保持・検証方式は BLK-002 の確定後に反映） |
| NFR-SC-16 | REQUIREMENT | YES | TASK-005 | COVERED（パスワードの長さ・文字種の検証） |
| NFR-SC-18 | REQUIREMENT | YES | TASK-005, TASK-015 | COVERED（方式は BLK-002） |
| NFR-SC-19 | REQUIREMENT | YES | TASK-005, TASK-015 | COVERED（方式は BLK-002） |
| NFR-SC-21 | REQUIREMENT | YES | TASK-001, TASK-003, TASK-004, TASK-006, TASK-013, TASK-014, TASK-015 | COVERED（8.2 VUL-01〜VUL-13 の対策方針を各Taskの Constraints へ展開。診断は NFR-SC-29） |
| NFR-SC-22 | REQUIREMENT | YES | TASK-004, TASK-005, TASK-014 | COVERED |
| NFR-SC-23 | REQUIREMENT | YES | TASK-004, TASK-013 | COVERED（追記のみ・更新削除手段を設けない） |
| NFR-SC-24 | REQUIREMENT | YES | TASK-012, TASK-013 | COVERED |
| NFR-US-01 | REQUIREMENT | YES | TASK-015 | COVERED |
| NFR-US-02 | REQUIREMENT | YES | TASK-015 | COVERED |
| NFR-US-03 | REQUIREMENT | YES | TASK-015 | COVERED |
| NFR-US-04 | REQUIREMENT | YES | TASK-003, TASK-015 | COVERED |
| NFR-US-07 | REQUIREMENT | YES | TASK-015 | COVERED（推奨。キーボード操作） |
| NFR-US-09 | REQUIREMENT | YES | TASK-015 | COVERED（取消できない5操作の確認ダイアログ） |
| NFR-US-10 | REQUIREMENT | YES | TASK-015 | COVERED |
| NFR-LG-02 | REQUIREMENT | YES | TASK-006, TASK-007, TASK-015 | COVERED |
| NFR-LG-03 | REQUIREMENT | YES | TASK-010 | COVERED（注文関連データを更新・削除しない） |
| NFR-LG-05 | REQUIREMENT | YES | TASK-011 | COVERED（カード番号を入力・保存・送信しない） |
| NFR-MG-02 | REQUIREMENT | YES | TASK-014 | COVERED（投入件数と定義ファイル件数の一致） |
| NFR-SC-29 | REQUIREMENT | NO | 該当なし（稼働開始前の診断作業） | N/A（全画面・全APIへの動的脆弱性診断は稼働開始前に実施する作業であり、実装成果物を生む担当Taskを置かない。対策方針の実装は NFR-SC-21 の各Task） |
| NFR-SC-02 | REQUIREMENT | NO | 該当なし（本リリースの実装対象外） | N/A（本番のHTTPS終端は OQ-PJ-003 で未確定。検証環境はHTTPを許容） |
| NFR-SC-13 | REQUIREMENT | NO | 該当なし | N/A（要件本文が「該当なし」。多要素認証を設けない） |
| NFR-SC-14 | REQUIREMENT | NO | 該当なし | N/A（要件本文が「該当なし」。アカウントロック・試行回数制限は FR-OUT-11 で対象外） |
| NFR-SC-17 | REQUIREMENT | NO | 該当なし | N/A（要件本文が「該当なし」。パスワード変更・再設定は FR-OUT-09 で対象外） |
| NFR-SC-27 | REQUIREMENT | NO | 該当なし | N/A（要件本文が「該当なし」。本番基盤でのアクセス制限の要否は NOQ-06） |
| NFR-SC-28 | REQUIREMENT | NO | 該当なし | N/A（要件本文が「該当なし」。アップロード機能を持たない） |
| NFR-AV-09 | REQUIREMENT | NO | 該当なし（本リリースの実装対象外） | N/A（大規模災害対応は本番基盤 OQ-PJ-001 の決定後） |
| NFR-OM-09 | REQUIREMENT | NO | 該当なし（運用設定で対応） | N/A（監視は本番運用時に設定、検証環境は対象外） |
| FILE-001 | DETAILED_DESIGN | YES | TASK-014 | COVERED |

補足：

- 本表は計画時点のTask割当の確認であり、Traceability Auditorが生成するTrace Matrixではない。
- 上記以外のNFR（可用性 NFR-AV、移行 NFR-MG の目標値、法令・規格順守 NFR-LG-01・04・06〜10、本番基盤側で満たす NFR-EN-06・NFR-EN-13・NFR-SC-20・NFR-SC-26 等）は、構成・設定レビューまたは運用・移行作業で確認する項目であり、実装成果物を生む担当Taskを持たない。
- NFR-EN-08 の「Web サーバー・AP サーバーの選定」は要件が設計へ委譲した重要判断であり、本工程では確定せず BLK-011 としてADDRへ引き渡す（9章）。

## 8. Progress Summary

| Status | Count |
| --- | ---: |
| TODO | 16 |
| READY | 0 |
| IN_PROGRESS | 0 |
| BLOCKED | 0 |
| DONE | 0 |
| CANCELLED | 0 |

### Overall Progress

- Total Tasks: 16
- Completed Tasks: 0
- Completion Rate: 0%
- Blocking Tasks: 0（Task自体はBLOCKEDではないが、9章の未確定判断を解決してから着手する）

## 9. Blockers / Open Decisions

| Blocker ID | Related Task | Classification | Description | Impact | Recommended Route | Status |
| --- | --- | --- | --- | --- | --- | --- |
| BLK-001 | TASK-008, TASK-010, TASK-011, TASK-012, TASK-013 | ARCHITECTURE | 在庫引当・注文状態遷移・同一カートの直列化を逐次実行と同じ結果にする実現方式が未確定（CMN-19、CMN-20、CMN-23 は結果の要件のみを定める） | 競合時の業務エラー（INSUFFICIENT_STOCK、INVALID_STATUS_TRANSITION、CART_EMPTY）の成立可否と更新系の応答時間 | ADDR | OPEN |
| BLK-002 | TASK-005, TASK-015 | ARCHITECTURE | APIの認証トークン（128ビット以上相当・24時間・ログアウト無効化・多重ログイン）と画面のログインセッション（無操作30分）の保持・検証方式が未確定 | 認証の成立、セッション保護（NFR-SC-08、NFR-SC-09、NFR-SC-19）の実装可否 | ADDR | OPEN |
| BLK-003 | TASK-002, TASK-010 | ARCHITECTURE | 注文番号（PO-＋8桁ゼロ埋め、全注文で一意、確定順に増加、欠番許容）の採番方式が未確定 | 同時注文時の一意性と昇順性（DQ-11、FR-030） | ADDR | OPEN |
| BLK-004 | TASK-001, TASK-015 | ARCHITECTURE | app 内部のモジュール分割と、画面・APIが同一業務ロジックを共有する構成が未確定（Steering 4.1・4.2 が設計へ委譲） | 業務ルールの重複実装防止、保守性・テスト容易性 | ADDR | OPEN |
| BLK-005 | TASK-004 | ARCHITECTURE | JSON Lines のアプリケーションログ出力と X-Request-ID の相関付けの実現方式が未確定 | 必須項目の出力と禁止項目の非出力（NFR-OM-01、NFR-SC-06） | ADDR | OPEN |
| BLK-006 | TASK-002, TASK-006, TASK-013 | ARCHITECTURE | 一覧検索（商品一覧・注文一覧・在庫単位一覧）の索引・問い合わせ方式が未確定 | 将来データ量での参照系応答時間（NFR-PF-01、NFR-PF-06） | ADDR | OPEN |
| BLK-007 | TASK-003 | ARCHITECTURE | 共通エラー応答と判定順序（認証→権限→入力→対象→状態→業務ルール）の共通化方式が未確定 | 全APIのエラーコード・context の一貫性（api-contract.md 6.2、6.3） | ADDR | OPEN |
| BLK-008 | TASK-005, TASK-014 | ARCHITECTURE | ソルト付き一方向ハッシュの具体方式（アルゴリズム・パラメータ）が未確定 | パスワード保存の安全性（NFR-SC-01）と認証系応答時間（NFR-PF-09） | ADDR | OPEN |
| BLK-009 | TASK-011 | ARCHITECTURE | 決済サービス（模擬）の配置・呼び出し境界・10秒の応答待ち制御の実現方式が未確定 | IF-01 の例外（タイムアウト・応答不正）の検出と二重決済防止 | ADDR | OPEN |
| BLK-010 | TASK-014 | ARCHITECTURE | 初期データ定義ファイルのトップレベル構造・キー名・参照項目名が未提供（FILE-001 の OQ-FILE-001、OQ-FILE-002） | 定義ファイルの読込実装と運用者が作成するファイルの互換性 | ADDR | OPEN |
| BLK-011 | TASK-001, TASK-016 | ARCHITECTURE | app サービス内で動作する Web サーバー・AP サーバーの選定が未確定（NFR-EN-08 は「指定なし／設計で選定する」と明示し、本番環境で Django 付属の開発用サーバーを使用しないことのみを定める） | 本番環境の起動設定（NFR-EN-08 の検証方法である構成・設定レビューの対象）、起動手順の記載（NFR-OM-19）、依存定義に追加される実行基盤ライブラリの版（NFR-EN-10、NFR-SC-11） | ADDR | OPEN |

## 10. Change History

| Version | Date | Change | Reason | Related ID |
| --- | --- | --- | --- | --- |
| 1.0 | 2026-10-22 | 初版作成（TASK-001〜TASK-016 の分解、依存・Wave・検証方法、未確定判断の記録） | MiniCommerce Architecture工程（RUN-20261022-MC）の設計資料作成 | FR-001, FR-060, FILE-001 |
| 1.1 | 2026-10-22 | BLK-011（Web サーバー・AP サーバーの選定）を9章へ追加。TASK-001 に NFR-EN-08 の正確な引用と依存定義のバージョン固定・公式配布元限定・サポート期限（NFR-EN-10、NFR-EN-12、NFR-SC-11、VUL-10）を追記。TASK-004 に path のクエリ文字列除外（NFR-SC-06 後段）を追記。TASK-005 の CMN 帰属を CMN-09／CMN-11／CMN-12 へ訂正。TASK-006・TASK-013・TASK-014 に NFR-SC-04 を追記。TASK-015 に NFR-US-03・NFR-US-07・NFR-US-09 を追記。TASK-016 に NFR-SC-11・NFR-OM-14 の手順記載を追記。7章 Coverage を実態に合わせて拡充 | ARCHITECTURE差し戻し（repair cycle 1）：QR-ARCH-001〜003、SR-ARCH-001〜003、Traceability助言 S-02 への対応 | NFR-EN-08, NFR-EN-10, NFR-SC-04, NFR-SC-06, NFR-SC-11, NFR-US-09, CMN-09, CMN-11, CMN-12 |
