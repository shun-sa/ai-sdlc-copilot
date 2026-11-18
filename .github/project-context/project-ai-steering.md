# Project AI Steering

<!--
本文書の位置付け:
- Requirements工程で共有するMiniCommerce固有の事前前提・制約を記録する。
- 内容は旧Steering（2026-10-21時点）に記載されていた既知の条件から移行したもので、別資料の内容を新たに検証・承認したものではない。
- 業務・機能・非機能要件およびAPI契約の詳細は、2.2の参照文書を正本とする。
- 後続工程で決定する設計要素、内部モジュール依存、実装・監視方式、実行コマンドを本書で新たに決めない。
- 秘密情報・個人情報の実値を記載しない。
-->

## 1. 文書情報

| 項目 | 内容 |
| --- | --- |
| 文書ID | `DOC-PROJECT-AI-STEERING-001` |
| 対象プロジェクト | MiniCommerce |
| バージョン | 1.1（新Steering形式への移行版） |
| ステータス | DRAFT |
| Owner | MiniCommerce 要件定義チーム |
| 最終更新日 | 2026-11-18 |

## 2. Project Context

### 2.1 プロジェクト概要

- Project Name: MiniCommerce
- System / Product: 株式会社あおば雑貨の会員向け自社ECサイト。購入者・管理者向けWeb画面（PCブラウザ）と、対応するWeb API（JSON/REST）を提供する。画面とAPIは同一の業務ルールに従う。
- Purpose: 商品閲覧からカート、クーポン適用、注文確定、模擬決済、出荷、配達完了までの注文受付を提供し、在庫・注文の整合、金額計算の自動化および注文状況の可視化を実現する。初期リリース（第1期）の稼働開始予定日は2027-04-01。

### 2.2 参照すべき業務・要件文書

| 種別 | Path / Reference | 備考 |
| --- | --- | --- |
| Requirements | `docs/requirements/requirements.md` | 分割要件成果物、UC、FR/NFR等の派生索引。本文は各正本を参照 |
| Business Requirements | `docs/requirements/business_requirements.md` | 業務ルール・業務量の正本（BR） |
| Functional Requirements | `docs/requirements/functional_requirements.md` | 機能要件、判定順序、エラー種別の正本（FR） |
| Non-functional Requirements | `docs/requirements/non_functional_requirements.md` | 性能、可用性、運用、セキュリティ、環境等の正本（NFR） |
| Data Requirements | `docs/requirements/data_requirements.md` | データ・項目名・コード値・取扱い等の正本。実際のIDは当該要件書と照合する |
| External Interface Requirements | `docs/requirements/external_interface_requirements.md` | 模擬決済などの連携要件の正本。実際のIDは当該要件書と照合する |
| UI Requirements | `docs/requirements/ui_report_requirements.md` | 画面・帳票要件の正本（画面IDはSCR体系、帳票は該当なし） |
| Use Case Index | `docs/requirements/use-case-user-story-index.md` | US/UC一覧 |
| Use Case Details | `docs/requirements/use-cases/` | UCごとのフローと受入基準（AC） |
| Glossary | `docs/requirements/glossary.md` | 用語定義の正本 |
| Provided API Contract | `docs/specifications/api-contract.md` | 提供済みAPI契約の正本。エンドポイント、入出力、エラー形式などの詳細は本書へ複製しない |

## 3. Technology Stack / Technical Constraints

| Layer / Purpose | 指定済みTechnology | Version / Policy | 指定元・根拠 | Notes |
| --- | --- | --- | --- | --- |
| Frontend | Djangoテンプレートによるサーバーサイドレンダリング（HTML/CSS、JavaScriptは最小限） | Django 5.2 LTSのテンプレート機能 | 旧Steering §3、`docs/requirements/non_functional_requirements.md`（NFR-EN-05、NFR-US-01/02） | SPAフレームワークやフロントエンド専用ビルドは使わない。Google Chrome・Microsoft Edgeの最新版（PC）、画面幅1280px以上を対象とする |
| Backend | Python / Django / Django REST Framework | Python 3.12、Django 5.2 LTS、DRF 3.15以上 | 旧Steering §3、同NFR（NFR-EN-01） | 画面・API・業務処理を単一Djangoプロジェクトに置くことが事前指定されている。内部モジュール構造は本書で決めない |
| Database | PostgreSQL | 16 | 旧Steering §3、同NFR（NFR-EN-02） | 主データストア |
| Runtime | Docker Compose | `app`・`db`の2サービス、Asia/Tokyo、UTF-8 | 旧Steering §3、同NFR（NFR-EN-03/04） | 現行の検証・実行環境に関する指定。本番の基盤方式は未決定 |
| Test | pytest / pytest-django | Python 3.12・Django 5.2と互換性のある版（バージョン個別指定なし） | 旧Steering §3・§5、同NFR（NFR-OM-06） | テストファイル名は`test_*.py` |
| Static Analysis | ruff | Python 3.12に対応する版（バージョン個別指定なし） | 旧Steering §3、同NFR（NFR-OM-07） | 指摘0件を要求 |

## 4. Development / Runtime Preconditions

| 項目 | 事前に確定した前提・制約 | 指定元・根拠 |
| --- | --- | --- |
| Repository / Workspaces | 要件文書は`docs/requirements/`（UC詳細は`docs/requirements/use-cases/`）、提供済みAPI契約は`docs/specifications/`。アプリケーション（画面・API・業務処理・テスト）は単一のDjangoプロジェクトとして`app/`に配置する。初期データ定義（UTF-8/JSON）の配置先は`app/seed/`。ルートに`compose.yaml`、実値を含まない`.env.example`、`README.md`を置く。`app/`内部のモジュール分割は未指定 | 旧Steering §4、`docs/requirements/functional_requirements.md`（FR-060）、`docs/requirements/non_functional_requirements.md`（NFR-EN-01、NFR-SC-07） |
| Runtime / Deployment Environment | ローカルの実行・検証はDocker Composeの`app`・`db`を利用する。`app`はHTTPのlocalhost:8000、`db`はPostgreSQLの5432ポートを前提とする。`app`コンテナの作業ディレクトリはリポジトリ上の`app/`に対応する。本番基盤・HTTPS終端などの具体方式は本書では決定しない | 旧Steering §4・§9、同NFR（NFR-OM-05、NFR-SC-02） |
| Network / Access | 実行時は外部インターネットへ接続しない。コンテナイメージ・依存パッケージの取得時のみ例外。外部CDNを利用しない。検証環境はHTTP、本番環境はHTTPS（TLS 1.2以上）が必要 | 旧Steering §3・§8・§10、同NFR（NFR-EN-05、NFR-SC-02） |
| Development / CI Environment | Pythonベースの開発環境、Docker Compose、pytest/pytest-django、ruffを利用する。起動とテストはそれぞれ一括実行できることが要求される。CIサービス・パイプライン構成は事前指定なし | 旧Steering §3・§9、同NFR（NFR-OM-05/06/07） |

## 5. Predefined Project-Specific Conventions

| 対象 | PJ固有の指定済み規約 | 指定元・根拠 |
| --- | --- | --- |
| Naming / Coding | PythonコードはPEP 8に従う。API項目名は`snake_case`、URLパスは小文字・ハイフン区切り。用語はGlossaryを正本とする | 旧Steering §5、`docs/specifications/api-contract.md`、`docs/requirements/glossary.md` |
| Repository Layout | 既知の配置規則は4章のとおり。画面とAPIは同一の業務ルールに従い、数量制約・クーポン判定・金額計算・在庫引当・状態遷移の業務規則を画面側に重複実装しない。内部のクラス分割・依存方向は未指定 | 旧Steering §2・§4、`docs/requirements/business_requirements.md`（BR-01〜BR-19）、`docs/requirements/functional_requirements.md`（FR-026） |
| Build / Test Standards | pytest/pytest-django、テスト命名`test_*.py`、ruffの指摘0件が事前条件。テストを一括実行できること。具体的なビルド・起動・DB更新・データ投入コマンドは後続工程で実装・整備する | 旧Steering §3・§5・§9、`docs/requirements/non_functional_requirements.md`（NFR-OM-05/06/07） |
| External Interface Standards | 提供済みAPIの方式はREST/JSON（UTF-8）。APIベースパスは`/api`、管理者向けは`/api/admin`。項目・認証ヘッダー・エラー応答・ページング・ステータス対応等の詳細は、既存の`docs/specifications/api-contract.md`と各要件書を正本とする | 旧Steering §6、`docs/specifications/api-contract.md`（6.1〜6.3） |

## 6. External Systems / Security / Data Constraints

### 6.1 External Systems

| System / Constraint | 指定済みの内容・境界 | Mock / Real | 指定元・根拠 |
| --- | --- | --- | --- |
| 決済サービス（EXT-01） | 支払い機能はシステム内の模擬決済として提供する。実際の決済サービスや外部ネットワークには接続しない。決済要求・結果・タイムアウト・再送に関する業務条件は外部IF要件・FR-031を正本とする | MOCK | 旧Steering §7・§10、`docs/requirements/external_interface_requirements.md`、`docs/requirements/functional_requirements.md`（FR-031） |
| その他の外部システム | メール送信・配送業者・会計システムとは連携しない | N/A | 旧Steering §10、`docs/requirements/external_interface_requirements.md`（1.3） |

### 6.2 Security / Operation Constraints

| 項目 | PJ開始前に指定された制約 | 指定元・根拠 |
| --- | --- | --- |
| Authentication / Authorization | メールアドレスとパスワードによる認証を用い、APIではBearerトークン、Web画面ではセッションを利用する。権限は`buyer`・`admin`およびデータ所有者に基づく。具体的な有効期間・アクセス許可・CSRF等の要件は機能・非機能要件書を正本とし、内部実装方式は本書で定めない | 旧Steering §8、`docs/requirements/functional_requirements.md`（FR-002/003）、`docs/requirements/non_functional_requirements.md`（NFR-SC-01/03/04/05/08/09） |
| Network / Secret Handling | 外部接続の制約は4章のとおり。秘密鍵・DBパスワード等は環境変数から与え、ソースコード・リポジトリへ含めない。実値を含まない`.env.example`は配置し、`.env`はリポジトリに含めない | 旧Steering §4・§8、同NFR（NFR-EN-05、NFR-SC-02/07） |
| Logging / Monitoring Restrictions | パスワード、認証トークン、個人情報をログに出力しない。ログ方式・監査記録・保管期間・監視指標・目標値は非機能・データ要件を正本とし、本書から監視実装方式を指定しない | 旧Steering §7、`docs/requirements/non_functional_requirements.md`（NFR-SC-06、NFR-OM-01/02/03、NFR-PF-01〜04、NFR-AV-02）、`docs/requirements/data_requirements.md` |

### 6.3 Data Constraints

| 項目 | PJ開始前に指定された制約 | 指定元・根拠 |
| --- | --- | --- |
| Required Data Platform | PostgreSQL 16を利用する。データ項目名・コード値、金額計算・在庫・注文の整合条件はデータ・業務・機能要件の正本に従う | 旧Steering §3・§8、`docs/requirements/data_requirements.md`、`docs/requirements/business_requirements.md`、`docs/requirements/functional_requirements.md` |
| Sensitive Data Classification | 既存の区分はCLS-01（公開）、CLS-02（社外秘）、CLS-03（機密：利用者や配送先の個人情報）、CLS-04（厳秘：パスワードハッシュ）。検証・初期データに実在の個人情報を使用しない | 旧Steering §8・§11、`docs/requirements/data_requirements.md` |
| Retention / Deletion Rules | 注文関連データの保存期間は注文日から7年。アプリ・監査ログの保管期間、削除と初期化の詳細な条件はデータ・非機能・機能要件書を正本とする | 旧Steering §7・§8・§9、`docs/requirements/data_requirements.md`、`docs/requirements/non_functional_requirements.md`（NFR-OM-02/03、NFR-LG-03）、`docs/requirements/functional_requirements.md`（FR-060） |

## 7. Project-Specific Prohibitions

- 実在する決済サービス・外部APIへの接続処理を実装しない。
- 本番相当の個人情報を初期データ・テストデータ等の検証データに使用しない（架空の値のみ）。
- 要件外とされている機能（FR-OUT-01〜FR-OUT-16）を実装しない。
- 初期データ一括投入の破壊的初期化（`--reset`）を本番環境で実行しない。これは検証環境の初期化専用とする。

## 8. Open Preconditions / Change Notes

### 8.1 未確認のPJ前提・制約

| Question ID | 未確認事項 | 影響 | 確認先 | 状態 |
| --- | --- | --- | --- | --- |
| なし | 前回Steeringから移行すべき、今回の検証実施前に確認必須のPJ事前前提は記載されていない。後続工程の設計判断はこの表へ転記しない | 該当なし | 該当なし | N/A |

### 8.2 Change Notes

| Date | Change | Reason | Reference |
| --- | --- | --- | --- |
| 2026-10-09 | 初版作成 | MiniCommerce要件定義開始 | 前回Steeringの変更履歴 |
| 2026-10-21 | 要件・設計成果物の配置形式との整合とAPI契約の正本への集約 | 従来の要求内容を維持した形式変更 | 前回Steeringの変更履歴 |
| 2026-11-18 | 現行の8章テンプレートに再編し、後続工程で決定する設計・実行・監視詳細の重複記載を除去 | SteeringをRequirements時点で既知のPJ事前前提に限定するため | 旧Steering（13章版）、現行`project-ai-steering.md`テンプレート |
