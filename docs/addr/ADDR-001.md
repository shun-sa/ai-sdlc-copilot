---
document_type: "ADDR（Architecture Decision & Design Record）"
system_name: "MiniCommerce"
addr_id: "ADDR-001"
title: "app/ 内部のモジュール分割とModule間アクセス規則"
design_type: "非機能"
target_id: "TGT-PLATFORM"
status: "ACTIVE"
generated_by: "ADDR Agent（独立ADDR工程 / RUN-002）"
generated_at: "2026-10-21T19:20:00+09:00"
source_revision: "requirements-2026-10-21"
generation_id: "RUN-002"
primary_decision: "app/ 配下を機能別Djangoアプリケーションと横断共通パッケージへ分割し、依存方向を一方向に固定する"
---

# ADDR：app/ 内部のモジュール分割とModule間アクセス規則

## 1. 対象範囲

| 項目 | 内容 |
|---|---|
| 対象ID・名称 | TGT-PLATFORM：実行基盤・API共通基盤（Docker Compose／Django／共通エラー・ログ） |
| 対象機能・業務 | app/ 配下の全機能（FR-001〜FR-060 の実装配置）と共通基盤。実装タスクは TASK-001・TASK-003 |
| 対象環境・リリース | 第1期リリース（2027-04-01 稼働開始予定）。検証環境 ENV-01（Docker Compose の app・db） |
| 対象外 | 共通例外ハンドラの実現方式（ADDR-011）、ログ出力先（ADDR-007）、画面テンプレートの構成（ADDR-010）、リポジトリ直下の構成（Steering 4章で確定済み） |

## 2. 関連要件・参照成果物

本ADDRの判断または設計差分に直接関係する成果物だけを記載する。

| 区分 | 参照先 | 関係 |
|---|---|---|
| 要件 | NFR-EN-01, NFR-EN-09, NFR-OM-07, NFR-OM-06, NFR-EN-12 | 単一Djangoプロジェクト、画面と同一業務ロジック、静的解析0件、テスト実行性、OSS追加の抑制 |
| 受入条件 | docs/requirements/use-cases/UC-004.md AC-UC-004-001、docs/requirements/use-cases/UC-006.md AC-UC-006-001 | 画面とAPIが同一業務ロジックで同じ結果を返すことの検証 |
| AIステアリング文書 | .github/project-context/project-ai-steering.md 4.1・4.2（版 1.0） | app/ 内部のモジュール分割とModule間アクセス規則の設計への委任 |
| システム構成図 | 該当なし（本Runでは構成図成果物を作成していない） | 参照しない |
| データモデル | docs/requirements/data_requirements.md 3章（D-01〜D-15） | モデル定義の配置先を決める対象データ |
| 設計成果物 | docs/architecture/implementation-task-list.md（PLAN-001）：TASK-001, TASK-003 | 本ADDRが実装配置を拘束するTask（BLK-004・ARCH-CI-001の解決） |
| 関連ADDR | ADDR-007, ADDR-009, ADDR-010, ADDR-011 | 本配置を前提にログ・決済模擬・画面テンプレート・例外ハンドラの配置を決める |

## 3. 背景

### 3.1 判断が必要な理由

Steering 4.1・4.2 は「app/ 内部のモジュール分割」「Module 間アクセス規則」を設計へ明示的に委任している。要件・提供済みAPI契約は機能とエンドポイントを定めるが、Djangoアプリケーションの分割単位と依存方向を定めていない。配置が未確定のままでは TASK-001・TASK-003 以降の全Taskが異なる前提で実装され、業務ルールの重複実装（Steering 4.2 の禁止事項）を静的に判別できない。

### 3.2 判断時の制約

- 技術スタック（Python 3.12／Django 5.2 LTS／DRF 3.15以上／PostgreSQL 16／Docker Compose の app・db／pytest＋pytest-django／ruff）を変更しない。
- API・画面・業務ロジック・テストは app/ 配下の単一Djangoプロジェクトへ置く（NFR-EN-01、Steering 4.1）。
- 初期データ定義ファイルの配置先 app/seed/ と Steering 9章の運用コマンドを変更しない。
- 追加の外部依存（新規OSSパッケージ）を導入しない。

## 4. 設計判断

### 4.1 判断基準

| ID | 判断基準 | 優先度 | 根拠ID |
|---|---|---|---|
| DC-001 | 画面とAPIが同一の業務ロジックを呼び出せる配置であること | 必須 | NFR-EN-09 |
| DC-002 | 業務ルールの重複実装と循環依存をレビュー・静的解析で判別できること | 必須 | NFR-OM-07 |
| DC-003 | 単一Djangoプロジェクト・単一コマンド体系を維持すること | 必須 | NFR-EN-01 |
| DC-004 | 単体・結合テストでテスト用DBへ切り替えられる構成であること | 重視 | NFR-OM-06 |
| DC-005 | 追加の依存ライブラリを必要としないこと | 重視 | NFR-EN-12 |

### 4.2 検討した選択肢

| 選択肢ID | 選択肢 | 利点 | 欠点・リスク | 選定結果 | 根拠 |
|---|---|---|---|---|---|
| OPT-001 | 機能別Djangoアプリケーション（accounts／catalog／carts／orders／payments／seeding／web）＋横断共通パッケージ common＋設定 config とし、各アプリ内を views→services→models の一方向にする | 機能単位で責務が閉じ、画面とAPIが同じ services を共有できる。Django標準の構成で追加依存が不要 | アプリ間参照の規則を明文化しないと相互参照が生じる | SELECTED | DC-001, DC-002, DC-003, DC-005 |
| OPT-002 | 単一Djangoアプリケーション（app/core）内をモジュールファイルで分割する | 構成が最も単純で初期実装が速い | 26機能・21Taskが同一名前空間へ集まり依存方向を機械的に判別できない。重複実装の検出が目視頼りになる | NOT_SELECTED | DC-002 |
| OPT-003 | レイヤ単位のトップレベル分割（models／services／views を機能横断で束ねる） | 層の責務が明確になる | Djangoのアプリケーション単位（マイグレーション・管理コマンド・テスト）と不整合になり、機能追加時の影響が層全体へ広がる | NOT_SELECTED | DC-002, DC-003 |

### 4.3 決定内容

app/ 配下を次のパッケージへ分割する。

- `app/config/`：settings・urls・wsgi/asgi（Djangoプロジェクト設定）
- `app/common/`：エラーコード定義と例外、判定順序、入力検証、ページング、X-Request-ID、ログ出力の共通処理
- `app/accounts/`：利用者・認証・認可・監査ログ（FR-001〜FR-004）
- `app/catalog/`：商品分類・商品・在庫単位の参照（FR-010〜FR-012）
- `app/carts/`：カート・クーポン・注文金額計算（FR-020〜FR-026）
- `app/orders/`：注文確定・支払結果の反映・注文照会・キャンセル・管理者向け注文更新（FR-030〜FR-034、FR-040〜FR-045）
- `app/payments/`：決済サービス（模擬）の内部インターフェースと模擬実装（FR-031）
- `app/seeding/`：初期データ一括投入の管理コマンド（FR-060）
- `app/web/`：画面のビューとテンプレート（SCR-001〜SCR-103、SCR-901）
- `app/seed/`：初期データ定義ファイルの配置先（Steering 4.1。Pythonパッケージではない）

各機能アプリケーションは `models.py`／`serializers.py`／`services.py`／`views.py`／`urls.py`／`tests/` を持つ。依存方向は次のとおり一方向に固定する。

1. APIビューと web のビューは、同一機能の `services` の公開関数だけを呼ぶ。
2. `services` は同一アプリの `models` と、他アプリの `services` の公開関数だけを呼ぶ。
3. `common` は全アプリから参照してよく、`common` から機能アプリを参照しない。
4. `config` は全アプリを参照し、アプリ側は `django.conf.settings` 経由でのみ設定値を読む。
5. 他アプリのモデルは外部キー定義と参照系クエリで用いてよいが、他アプリのデータ更新は相手アプリの `services` を経由する。
6. 循環 import を作らない。

### 4.4 決定理由

DC-001・DC-002 を同時に満たせるのは、機能境界とDjangoの管理単位（マイグレーション・管理コマンド・テスト）が一致する OPT-001 である。OPT-002 は全機能が単一名前空間へ集まり依存方向を判別できず、OPT-003 はDjangoのアプリケーション単位と不整合になるため、いずれも DC-002・DC-003 を満たさない。OPT-001 はDjango標準機能のみで実現でき追加依存を必要としない（DC-005）。

## 5. 設計差分

要件定義、AIステアリング文書、システム構成図およびデータモデルから一意に導出できない事項だけを記載する。

| ID | 要件・成果物参照先 | 条件・対象 | 追加・確定した内容 | 実装拘束 |
|---|---|---|---|---|
| DD-001 | NFR-EN-01／docs/architecture/implementation-task-list.md TASK-001 | app/ 配下の初期構成 | config・common・accounts・catalog・carts・orders・payments・seeding・web の各パッケージと app/seed/ を作成し、Djangoアプリケーションとして設定へ登録する | MUST |
| DD-002 | NFR-OM-07／docs/architecture/implementation-task-list.md TASK-003 | モジュール間の参照 | 4.3 の依存方向（views→services→models、common は被参照のみ、機能アプリ間は services 経由、他アプリデータの更新は相手 services 経由）を適用する | MUST |
| DD-003 | NFR-EN-09／docs/architecture/implementation-task-list.md TASK-003 | web アプリケーション | web のビュー・テンプレートに業務判定（数量上限・クーポン判定・金額計算・在庫引当・状態遷移）を実装しない | MUST_NOT |
| DD-004 | NFR-OM-06／docs/architecture/implementation-task-list.md TASK-001 | テスト配置とDB接続 | テストは各アプリケーション配下の tests/test_*.py に置き、DB接続情報は環境変数から読む（テスト実行時にテスト用DBへ切り替えられる状態を保つ） | MUST |

## 6. 種別固有差分

`design_type`に対応する節を1つだけ残し、その他の節は生成結果から削除する。要件等から一意に決まらない差分だけを記載し、該当する差分がない項目は `なし` とする。

### F. 非機能の場合

| 項目 | 設計差分 | 根拠・参照先 |
|---|---|---|
| 非機能区分 | 保守性 | NFR-OM-07 |
| 達成方式 | 機能別Djangoアプリケーション分割と一方向依存（4.3）により、業務ロジックの単一実装箇所を特定できるようにする | DD-001, DD-002 |
| 実装・設定上の制約 | 4.3 に列挙していないトップレベルパッケージを app/ に追加しない。ruff の指摘0件を維持する。循環 import を作らない | DD-001, NFR-OM-07 |
| 障害・上限超過時の振る舞い | なし（配置規約であり実行時の振る舞いを変えない） | DD-002 |
| 検証方法 | 構成・設定レビュー（ディレクトリ構成と import 方向の確認）、`docker compose exec app ruff check .`、`docker compose exec app pytest` | DD-001, DD-002, DD-004 |

## 7. AI実装制約

当該ADDR固有の不変条件・禁止事項だけを記載する。一般的な実装規約はAIステアリング文書を参照する。

| ID | 種別 | 内容 | 根拠ID |
|---|---|---|---|
| INV-001 | 禁止事項 | common から accounts・catalog・carts・orders・payments・seeding・web を import しない | DD-002 |
| INV-002 | 禁止事項 | 機能アプリケーションから他アプリの views・serializers を import せず、他アプリのデータを直接更新しない | DD-002 |
| INV-003 | 不変条件 | 画面とAPIは同一機能の services 関数を経由して業務判定を行い、判定結果はサーバー側を正とする | DD-003, NFR-EN-09 |
| INV-004 | 禁止事項 | 4.3 に列挙していないトップレベルパッケージ・Djangoアプリケーションを app/ へ追加しない | DD-001 |

## 8. 仮定事項

設計を一意に確定できない場合に、AIが処理継続のために採用した仮定を記載する。外部契約、法令、認証情報、秘密情報など、推測してはならない事項は仮定しない。本ADDRで採用した仮定はない。

| ID | 不足・曖昧な情報 | 採用した仮定 | 根拠 | リスク |
|---|---|---|---|---|

## 9. 後続工程への引継ぎ事項

設計判断または設計差分によって、後続工程で追加考慮が必要となる事項だけを記載する。

| 区分 | 引継ぎ事項 | 参照先 |
|---|---|---|
| 実装 | TASK-001 でパッケージを作成し、TASK-003 以降は本ADDRの依存方向に従って配置する。新しいトップレベルパッケージが必要になった場合はADDRへ差し戻す | DD-001, DD-002, INV-004 |
| テスト | 画面経由とAPI経由で同じ入力に対し同じ業務エラー・判定順序になることを検証する | DD-003, INV-003 |
| 運用 | なし（運用手順・コマンド体系に影響しない） | DD-001 |
