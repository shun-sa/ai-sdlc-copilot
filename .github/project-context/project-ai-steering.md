# Project AI Steering

## 1. 文書情報

| 項目 | 内容 |
| --- | --- |
| 文書ID | `DOC-PROJECT-AI-STEERING-001` |
| 対象プロジェクト | MiniCommerce |
| バージョン | 1.0 |
| ステータス | DRAFT |
| Owner | MiniCommerce 要件定義チーム |
| 最終更新日 | 2026-10-09 |

## 2. Project Context

### 2.1 プロジェクト概要

- Project Name: MiniCommerce
- System / Product: MiniCommerce（株式会社あおば雑貨の会員向け自社ECサイト。購入者・管理者向けの Web 画面（PC ブラウザ）と、同じ機能を提供する Web API（JSON/REST）。画面と API は同一の業務ルールに従う）
- Purpose: 会員向けに WEB での注文受付（商品閲覧→カート→クーポン適用→注文確定→支払（模擬決済）→出荷→配達完了）を提供し、在庫と注文の整合、金額計算の自動化、注文状況の可視化を実現する。初期リリース（第1期）、稼働開始予定 2027-04-01。

### 2.2 参照すべき業務・要件文書

| 種別 | Path / Reference | 備考 |
| --- | --- | --- |
| Requirements | `docs/requirements/requirements.md` | 分割成果物・全UC・FR/NFRへの派生索引。本文は各正本参照 |
| Business Requirements | `docs/requirements/business_requirements.md` | 業務要件定義書。業務ルール（BR-xx）・業務量の Source of Truth |
| Functional Requirements | `docs/requirements/functional_requirements.md` | 機能要件定義書。機能（FR-xxx）・判定順序・エラー種別（ERR-01〜ERR-08）の Source of Truth |
| Non-functional Requirements | `docs/requirements/non_functional_requirements.md` | 非機能要件定義書。非機能要件（NFR-xx-xx）の Source of Truth |
| Data Requirements | `docs/requirements/data_requirements.md` | データ要件定義書。データ（D-01〜D-15）・項目英名・コード値（CD-xx）の Source of Truth。API の JSON 項目名の正本 |
| External Interface Requirements | `docs/requirements/external_interface_requirements.md` | 外部インターフェース要件一覧。IF-01 決済要求（売上確定）の Source of Truth |
| UI Requirements | `docs/requirements/ui_report_requirements.md` | 画面・帳票要件レイアウト/一覧。画面（SCR-xxx）の Source of Truth（帳票は該当なし） |
| Use Case Index | `docs/requirements/use-case-user-story-index.md` | US/UC一覧（US-001〜US-020、UC-001〜UC-013） |
| Use Case Details | `docs/requirements/use-cases/` | Flow / Acceptance Criteria（UC-001〜UC-013） |
| Glossary | `docs/requirements/glossary.md` | 用語定義（TERM-001〜TERM-053） |
| ADR | `docs/addr/` | 現行の重要判断は独立ADDR工程で作成する。旧ADRは互換参照のみ。現時点で採択済み判断はない |

## 3. Technology Stack

| Layer / Purpose | Technology | Version / Policy | Related ADR | Notes |
| --- | --- | --- | --- | --- |
| Frontend | Django テンプレートによるサーバーサイドレンダリング（HTML＋CSS、JavaScript は最小限） | Backend と同じ Django 5.2 LTS のテンプレート機能を使う | None | SPA フレームワーク・フロントエンドのビルド工程は使わない。外部 CDN に依存しない（NFR-EN-05）。対象ブラウザは Google Chrome・Microsoft Edge 最新版（PC）、画面幅 1280px 以上（NFR-US-01, NFR-US-02） |
| Backend | Python／Django／Django REST Framework | Python 3.12、Django 5.2 LTS、Django REST Framework 3.15 以上 | None | API・画面・業務ロジックを同一 Django プロジェクトに置く（NFR-EN-01） |
| Database | PostgreSQL | 16 | None | 主データストア（NFR-EN-02） |
| Runtime | Docker Compose | サービスは app・db の2つ | None | タイムゾーン Asia/Tokyo、文字コード UTF-8（NFR-EN-03, NFR-EN-04） |
| Test | pytest＋pytest-django | バージョン指定なし（Python 3.12・Django 5.2 で動作する版） | None | テストファイル名は `test_*.py` |
| Static Analysis | ruff | バージョン指定なし（Python 3.12 に対応する版） | None | 指摘0件とする（NFR-OM-07） |

## 4. Repository / Project Structure

```text
./                   # リポジトリルート
├─ docs/
│  ├─ requirements/  # 要件定義資料（use-cases/ を含む）
│  ├─ architecture/  # Architectureの設計資料
│  ├─ addr/          # 独立ADDR工程の重要判断
│  └─ specifications/ # 提供済みAPI仕様
├─ app/              # Django プロジェクト（manage.py、API・画面・業務ロジック・テスト）
│  └─ seed/          # 初期データ定義ファイル（例 app/seed/initial_data.json）
├─ compose.yaml      # Docker Compose 定義（サービス app・db）
├─ .env.example      # 環境変数の雛形（実値は書かない。.env はリポジトリに含めない）
└─ README.md         # 起動・実行手順
```

### 4.1 PJ固有の配置ルール

- 要件定義資料は `docs/requirements/`、ユースケース詳細は `docs/requirements/use-cases/`、現行ADDRは `docs/addr/`、設計資料は `docs/architecture/` に置く。旧 `docs/adr/` は移行時の参照のみ。
- API・画面・業務ロジック・テストは `app/` 配下の単一の Django プロジェクトに置く。`app/` 内部のモジュール分割は設計で決める（本書では定めない）。
- 初期データ定義ファイル（JSON、UTF-8）は `app/seed/` に置く（FR-060）。定義ファイルに記載する個人情報は架空の値のみとする。
- `app` コンテナの作業ディレクトリはリポジトリの `app/` に対応させる。9章のコマンドはこの作業ディレクトリで実行され、`manage.py` と `seed/initial_data.json`（リポジトリ上は `app/seed/initial_data.json`）を相対パスで参照する。
- 秘密情報は `.env`（リポジトリに含めない）で与え、雛形 `.env.example`（実値を含めない）をリポジトリルートに置く（NFR-SC-07）。

### 4.2 PJ固有のDependency Rules

- 画面と API は同じ業務ロジックを呼び出す。
- 業務ルール（数量上限・クーポン判定・金額計算・在庫引当・状態遷移）を画面側（テンプレート・JavaScript）に重複実装しない（BR-01〜BR-19、FR-026）。
- `app/` 内部の Module 間アクセス規則は設計で決める（本書では定めない）。

関連ADR: None

## 5. Project-Specific Coding Conventions

### 5.1 Naming

| 対象 | PJ固有規則 |
| --- | --- |
| File | 共通規約に従う（Python は PEP 8） |
| Class / Component | 共通規約に従う（Python は PEP 8） |
| Function / Method | 共通規約に従う（Python は PEP 8） |
| Test | テストファイル名は `test_*.py` とし、pytest＋pytest-django で実行する |

### 5.2 その他のPJ固有規則

- API項目名はsnake_case。提供済み応答項目の詳細は `docs/specifications/api-contract.md` の「応答項目の命名」を参照する。
- URLパスは小文字・ハイフン区切り。用語は `docs/requirements/glossary.md` に従う。

## 6. Interface / API Conventions

| 項目 | PJ固有ルール | Related ADR / Spec |
| --- | --- | --- |
| API Style | REST／JSON。ベースパス `/api`（管理者用は `/api/admin`）。要求本文・応答本文は JSON（UTF-8）。エンドポイントは `docs/specifications/api-contract.md` 6.1のとおり | None / FR-001〜FR-045 |
| Request Correlation | 要求ヘッダー `X-Request-ID` を受け取った場合はその値を引き継ぎ、無い場合は生成する。応答ヘッダー `X-Request-ID` に付与し、ログの `request_id` に出力する | None / 7.2 |
| Date / Time | ISO 8601、`+09:00` 付き（例 `2027-04-01T10:00:00+09:00`）。基準タイムゾーンは JST（Asia/Tokyo）。日付のみの入力（FR-041 の `ordered_from`／`ordered_to`）は `YYYY-MM-DD`（JST、両端の日を含む） | None / NFR-EN-04 |
| Error Response | `{"error": {"code": "ERROR_CODE", "message": "利用者向け文言", "details": [{"field": "項目名", "reason": "理由"}], "context": {}}}`。`details`（入力エラーの項目別内容）は無い場合空配列。`VALIDATION_ERROR` は不備のある全項目を列挙する。`context` は業務エラーの機械判読用情報で、該当なしは空オブジェクト。内容は `docs/specifications/api-contract.md` 6.3のとおり。スタックトレース・SQL を含む内部情報は返さない | None / docs/specifications/api-contract.md 6.2, NFR-SC-10 |
| Pagination | クエリ `page`（1以上の整数、既定1。整数でない・1未満は `VALIDATION_ERROR`）。応答形式 `{"results": [...], "page": 1, "page_size": 20, "total_count": 0, "total_pages": 0}`。`page_size` は FR-011・FR-032・FR-041 が20件、FR-040 が50件。総ページ数を超える `page` は `results` を空配列で返す（エラーにしない）。FR-010 はページング形式を用いず全件を配列で返す（0件は空配列） | None / FR-010, FR-011, FR-032, FR-040, FR-041, NFR-PF-08 |
| Authentication Header | `Authorization: Bearer <token>`。トークンは FR-002 で発行し、有効期間は発行から24時間、FR-003 で無効化する。認証不要の API は FR-001, FR-002, FR-010, FR-011, FR-012。認証要の API でトークンが無い・無効・期限切れの場合は `AUTHENTICATION_REQUIRED`（401） | None / FR-002, FR-003, NFR-SC-08 |
| Amount | 金額は整数の円（JSON number）。端数は各計算段階で1円未満切り捨て。通貨は日本円のみ。税抜価格（`price`, `unit_price`, `min_price`）と税込価格（`price_incl_tax`, `min_price_incl_tax`）を項目名で区別する | None / BR-06〜BR-09, BR-17, FR-026 |
| Success Status | 登録系（FR-001, FR-030）は 201、ログアウト（FR-003）は 204（本文なし）、その他は 200。カート系（FR-021〜FR-025）は更新後のカート表現（FR-020 と同じ形）を返す。購入者の注文更新系（FR-030, FR-031, FR-034）は注文詳細表現（FR-033 と同じ形）、管理者の注文更新系（FR-043, FR-044, FR-045）は管理者向け注文詳細表現（FR-042 と同じ形）を返す | None / FR-020, FR-033, FR-042 |
| HTTP Status Mapping | 400 入力エラー（ERR-01）、401 認証エラー（ERR-04）・認証失敗（ERR-05）、403 権限エラー（ERR-03）、404 対象なしエラー（ERR-06）、409 業務エラー（ERR-02）、500 システムエラー（ERR-08）、502 外部連携エラー（ERR-07）。エラーコード別の対応は `docs/specifications/api-contract.md` 6.2 | None / functional_requirements.md（ERR-01〜ERR-08） |


提供済みAPIエンドポイント・エラーコード・contextの正本は `docs/specifications/api-contract.md` の6.1〜6.3を参照する。

## 7. Error / Logging / Observability Conventions

### 7.1 Error Handling

- 利用者向けエラーは `docs/specifications/api-contract.md` 6.2のエラーコードと日本語の `message` で返す。画面では入力エラーを該当項目の近傍に、業務エラーを画面上部のメッセージ領域に表示する（`docs/requirements/ui_report_requirements.md`）。
- 複数のエラーに該当する場合の判定順序：①認証（401）→②権限（403）→③入力形式（400）→④対象の存在・所有（404）→⑤状態（409）→⑥業務ルール（409）。先に該当したエラーを返す。各機能内の判定順は `docs/requirements/functional_requirements.md` の各 FR に従う。
- エラー時は、その操作によるデータ変更を残さない。ただし FR-031 の否認（`PAYMENT_DECLINED`）・外部連携エラー（`PAYMENT_SERVICE_ERROR`）では決済記録（結果 `declined`／`error`）を登録し、注文は `created` のままとする（IF-01）。FR-002 のログイン失敗（`INVALID_CREDENTIALS`）では監査ログ（`login_failure`）を記録する。
- 決済サービス（模擬）への要求は応答待ち最大10秒とし、自動再送しない（二重決済防止）。再実行は購入者の操作で行う。
- 同時実行の結果は逐次実行した結果と同じになること（在庫数量は0未満にならない、承認済み決済は1注文につき最大1件、同一カートの二重送信で作成される注文は1件）。

### 7.2 Logging

- Required Fields: `timestamp`, `level`, `request_id`, `method`, `path`, `status`, `user_id`（ログイン時）, `duration_ms`
- Prohibited Fields: パスワード、認証トークン、メールアドレス、氏名、住所、電話番号（NFR-SC-06）
- Log Format: JSON Lines（1行1イベント、UTF-8）（NFR-OM-01）。アプリケーションログの保管は90日（NFR-OM-02）
- Masking: 禁止項目はマスキングではなく出力しない。`Authorization` ヘッダーと要求本文をそのままログに出力しない
- 監査ログ（D-15）：ログイン成功・失敗、ログアウト、初期データ一括投入をアプリケーションログとは別に DB へ記録する（event_type は CD-07。保管1年、NFR-OM-03）

### 7.3 Monitoring

- Required Metrics: 死活監視（1分間隔）、5xx 応答率、応答時間の95パーセンタイル（照会系 API 1.0秒以内：NFR-PF-01、更新系 API 2.0秒以内：NFR-PF-02、画面表示 2.0秒以内：NFR-PF-03）、ディスク使用率（80% 超で異常）。本番環境は運用時に設定し、検証環境は対象外
- Alert / SLO Reference: `docs/requirements/non_functional_requirements.md`（NFR-AV-02 月間稼働率 99.0%以上、NFR-PF-01〜NFR-PF-04、監視要件）

## 8. Security / Data Project Constraints

### 8.1 Security

- Authentication: メールアドレス＋パスワード。API は認証トークン（Bearer、推測困難な乱数 128ビット以上相当、有効期間24時間、ログアウトで無効化、多重ログイン可）。画面はログインセッション（無操作30分で切断、Cookie に HttpOnly 属性、本番は Secure 属性も付与）。パスワードはソルト付き一方向ハッシュで保存する。アカウントロック・試行回数制限は行わない（FR-OUT-11）。NFR-SC-01, NFR-SC-08, NFR-SC-09 / Related ADR: None
- Authorization: ロール（`buyer`／`admin`）と対象データの所有者を、全 API・全画面でサーバー側で判定する（NFR-SC-03）。admin は購入機能（カート・注文確定・支払）を利用できない。buyer は自分の注文に限り参照・支払・キャンセルできる（PRM-01）。全入力をサーバー側で検証する（NFR-SC-04）。画面出力のエスケープと画面からの更新操作の CSRF 対策を行う（NFR-SC-05） / Related ADR: None
- Network Constraint: 外部インターネットに接続せずに起動・動作すること（コンテナイメージ・依存パッケージの取得時を除く）。外部 CDN を使わない（NFR-EN-05）。本番環境は HTTPS（TLS 1.2以上）のみ、検証環境は HTTP を許容（NFR-SC-02）
- Secret Management: 秘密鍵・DB パスワードは環境変数で与え、ソースコード・リポジトリに含めない。`.env` はリポジトリに含めず、`.env.example`（実値なし）を置く（NFR-SC-07） / Related ADR: None

### 8.2 Data

- Primary Data Store: PostgreSQL 16（Docker Compose の `db` サービス、ポート 5432）
- Transaction Boundary: 注文確定（FR-030）、支払結果の反映（FR-031）、キャンセル（FR-034, FR-045）、出荷登録（FR-043）、配達完了登録（FR-044）、初期データ一括投入（FR-060）は、それぞれ全成功か無変更のどちらかになること / Related ADR: None
- Sensitive Data Classification: CLS-01 公開、CLS-02 社外秘、CLS-03 機密（個人情報：利用者のメールアドレス・氏名、配送先の全項目）、CLS-04 厳秘（パスワードハッシュ）（`docs/requirements/data_requirements.md`）
- Retention / Deletion Reference: `docs/requirements/data_requirements.md`（保存期間：注文関連データは注文日から7年）、`docs/requirements/non_functional_requirements.md`（NFR-OM-02, NFR-OM-03, NFR-LG-03）

## 9. Build / Test / Local Execution

| Purpose | Command | Working Directory | Notes |
| --- | --- | --- | --- |
| Dependency Install | `docker compose build` | リポジトリルート（`compose.yaml` のある場所） | 依存パッケージをコンテナイメージに取り込む（外部接続を許容するのはこの時のみ） |
| Build | `docker compose build` | リポジトリルート（`compose.yaml` のある場所） | フロントエンドのビルド工程はない |
| Start | `docker compose up -d` | リポジトリルート（`compose.yaml` のある場所） | app は http://localhost:8000 、db は 5432。コマンド1回で全サービスが起動する（NFR-OM-05） |
| Migrate | `docker compose exec app python manage.py migrate` | リポジトリルート（`compose.yaml` のある場所） | `app` コンテナの作業ディレクトリで実行される |
| Seed | `docker compose exec app python manage.py load_initial_data seed/initial_data.json --reset` | リポジトリルート（`compose.yaml` のある場所） | FR-060。`--reset` 指定時は監査ログ以外の全データ（注文・カート・決済記録・状態履歴を含む）を削除してから投入。定義ファイルに違反がある場合は削除も投入も行わない。成功・失敗とも監査ログ（`initial_data_load`、`user_id` は空）を1件記録する。終了コードは成功時0、失敗時0以外。指定しない場合は既存データに追加（NFR-OM-04） |
| Lint / Static Check | `docker compose exec app ruff check .` | リポジトリルート（`compose.yaml` のある場所） | 指摘0件（NFR-OM-07） |
| Unit Test | `docker compose exec app pytest` | リポジトリルート（`compose.yaml` のある場所） | コマンド1回で実行できる（NFR-OM-06） |
| Integration Test | `docker compose exec app pytest` | リポジトリルート（`compose.yaml` のある場所） | Unit Test と同じコマンドで実行する |

## 10. External Systems / Environment Constraints

| System / Constraint | 内容 | Mock / Real | Reference |
| --- | --- | --- | --- |
| 決済サービス（EXT-01、IF-01 決済要求（売上確定）） | 支払（FR-031）で注文番号・決済金額（注文の合計金額、整数円）・通貨 `JPY`・模擬決済指示（`approve`／`decline`、既定 `approve`）を渡し、結果（`approved`／`declined`）・取引参照番号（`approved` 時 `MOCK-`＋英数字16桁）・否認理由コード（`declined` 時 `DECLINED`）・処理日時を受け取る。本システム内の模擬機能として実装し、外部ネットワークに接続しない。1秒以内に応答し、`approve`→承認、`decline`→否認を返す。応答待ち最大10秒、自動再送なし | MOCK | `docs/requirements/external_interface_requirements.md`（IF-01）、FR-031 |
| Network | 外部インターネットに接続せずに起動・動作すること（コンテナイメージ・依存パッケージの取得時を除く）。外部 CDN を使わない | N/A | NFR-EN-05 |
| その他の外部システム | メール送信・配送業者・会計システムとは連携しない | N/A | `docs/requirements/external_interface_requirements.md`（1.3） |

## 11. Project-Specific Prohibitions

- 実在の決済サービス・外部 API への接続処理を実装しない。
- 本番相当の個人情報を検証データ（`app/seed/` の定義ファイル、テストデータ）に使わない（架空の値のみ）。
- 要件に無い機能（FR-OUT-01〜FR-OUT-16 の事項）を実装しない。
- 本番環境で初期データ一括投入の `--reset`（監査ログ以外の全データ削除）を実行しない（検証環境の初期化専用）。

## 12. Open Project Decisions

| Decision / Question ID | 内容 | 影響 | 解決先 | 状態 |
| --- | --- | --- | --- | --- |
| OQ-PJ-001 | 本番環境の基盤（クラウドサービスを含む）の選定 | 本番の構成・監視設定・バックアップ方式。本リリースの実装（Docker Compose 構成）には影響しない | ADR / Owner | OPEN |
| OQ-PJ-002 | 実決済サービスの選定と接続方式 | 決済サービスの REAL 化（IF-01 の方式・認証・データ形式）。本リリースの実装（MOCK）には影響しない | Requirements（external_interface_requirements.md）/ ADR | OPEN |
| OQ-PJ-003 | 本番の HTTPS 終端方式 | 本番での TLS 1.2以上の実現方法（NFR-SC-02）。本リリースの実装には影響しない（検証環境は HTTP を許容） | ADR / Owner | OPEN |

## 13. Change Notes

| Date | Change | Reason | Related Requirement / ADR |
| --- | --- | --- | --- |
| 2026-10-09 | 初版作成 | MiniCommerce の要件定義開始に伴う初版 | None |
| 2026-10-21 | 現行テンプレート・配置へ再構成し、API詳細をdocs/specifications/api-contract.mdへ移設 | 要求内容・コマンドは維持。独立Architecture/ADDR構成へ参照のみ整合 | None |
