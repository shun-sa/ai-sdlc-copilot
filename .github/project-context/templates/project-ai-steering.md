# Project AI Steering

<!--
位置付け・作成時点:
- 本文書はRequirements工程で作成する「PJ固有の事前前提・制約」のSource Artifactである。
- 着手前に提供済み・承認済みの事項だけを記載し、指定元（入力資料・既存規約等）を明確にする。
- 設計工程以降で初めて決まる構成、依存関係、API内部形式、監視方式、コマンド等を推測で埋めない。
  これらは後続工程の成果物で管理し、本書に設計結果を追記しない。
- Requirement / UC / AC の本文や設計判断を複製せず、既存の要件文書への参照のみ置く。
- Framework共通のAgent動作、工程手順、Routing、Validator実行方法は記載しない。
- Secret、Password、Token、個人情報等の実値は記載しない。
- 事前指定がなければ「指定なし」、資料では判断できなければ「未確認」と区別する。
  「未確認」でPJ前提の確認が必要な場合のみ8.1へ記録する。
-->

## 1. 文書情報

| 項目 | 内容 |
| --- | --- |
| 文書ID | `<DOC-PROJECT-AI-STEERING-001>` |
| 対象プロジェクト | `<プロジェクト名>` |
| バージョン | `<1.0>` |
| ステータス | `DRAFT / APPROVED` |
| Owner | `<担当チーム／担当者>` |
| 最終更新日 | `<YYYY-MM-DD>` |

## 2. Project Context

### 2.1 プロジェクト概要

- Project Name: `<名称>`
- System / Product: `<対象システム>`
- Purpose: `<このPJで実現することの短い説明>`

### 2.2 参照すべき業務・要件文書

| 種別 | Path / Reference | 備考 |
| --- | --- | --- |
| Requirements | `<docs/requirements/requirements.md>` | 要件の派生索引（本文は分割要件を参照） |
| Use Case Index | `<docs/requirements/use-case-user-story-index.md>` | US/UC一覧 |
| Use Case Details | `<docs/requirements/use-cases/>` | Flow / Acceptance Criteria |
| Glossary | `<docs/requirements/glossary.md>` | 用語定義 |

## 3. Technology Stack / Technical Constraints

<!--
採用技術・バージョン・利用禁止事項がPJ開始前に確定している場合にだけ記載する。
候補の比較、採用理由の設計判断、後続工程で決める具体的な構成を記載しない。
-->

| Layer / Purpose | 指定済みTechnology | Version / Policy | 指定元・根拠 | Notes |
| --- | --- | --- | --- | --- |
| Frontend | `<React / TypeScript / 指定なし>` | `<指定版・LTS方針 / 指定なし>` | `<入力資料Path / 指定なし>` | `<事前制約 / なし>` |
| Backend | `<Java / Spring Boot / 指定なし>` | `<指定版 / 指定なし>` | `<入力資料Path / 指定なし>` | `<事前制約 / なし>` |
| Database | `<PostgreSQL / 指定なし>` | `<指定版 / 指定なし>` | `<入力資料Path / 指定なし>` | `<事前制約 / なし>` |
| Runtime | `<ECS / Lambda / 指定なし>` | `<指定版 / 指定なし>` | `<入力資料Path / 指定なし>` | `<事前制約 / なし>` |
| Test | `<Jest / JUnit / 指定なし>` | `<指定版 / 指定なし>` | `<入力資料Path / 指定なし>` | `<事前制約 / なし>` |

## 4. Development / Runtime Preconditions

<!--
PJ開始時点で指定されたリポジトリ・環境・実行制約を記載する。
ソース構成やモジュール依存は設計成果物または実装で決める。未確定の構成図は作らない。
-->

| 項目 | 事前に確定した前提・制約 | 指定元・根拠 |
| --- | --- | --- |
| Repository / Workspaces | `<既存のRepo構成・配置指定 / 指定なし>` | `<入力資料Path / 指定なし>` |
| Runtime / Deployment Environment | `<指定済み実行環境・利用可能サービス / 指定なし>` | `<入力資料Path / 指定なし>` |
| Network / Access | `<閉域網・外部接続等の制約 / 指定なし>` | `<入力資料Path / 指定なし>` |
| Development / CI Environment | `<利用ツール・実行条件 / 指定なし>` | `<入力資料Path / 指定なし>` |

## 5. Predefined Project-Specific Conventions

<!--
PJ開始前に明示されている規約だけを記載する。共通規約は再掲しない。
API内部仕様、実装クラス設計、モジュール依存方向、ログ形式等を新しく決めない。
-->

| 対象 | PJ固有の指定済み規約 | 指定元・根拠 |
| --- | --- | --- |
| Naming / Coding | `<PJ固有規約 / 指定なし>` | `<入力資料Path / 指定なし>` |
| Repository Layout | `<既存の配置規則 / 指定なし>` | `<入力資料Path / 指定なし>` |
| Build / Test Standards | `<事前指定された品質・試験上の制約 / 指定なし>` | `<入力資料Path / 指定なし>` |
| External Interface Standards | `<外部から指定された規格・形式 / 指定なし>` | `<入力資料Path / 指定なし>` |

## 6. External Systems / Security / Data Constraints

<!--
外部から指定された業務・技術上の制約のみを整理する。
具体的な認可実装、データモデル、トランザクション境界、リトライ方式等は後続工程に委ねる。
セキュリティ・データの個別要求本文は対応する要件書を正本とする。
-->

### 6.1 External Systems

| System / Constraint | 指定済みの内容・境界 | Mock / Real | 指定元・根拠 |
| --- | --- | --- | --- |
| `<外部システム名 / なし>` | `<既知の連携目的・接続制約 / 該当なし>` | `MOCK / REAL / N/A` | `<入力資料Path / 指定なし>` |

### 6.2 Security / Operation Constraints

| 項目 | PJ開始前に指定された制約 | 指定元・根拠 |
| --- | --- | --- |
| Authentication / Authorization | `<利用必須の基盤・認証上の制約 / 指定なし>` | `<入力資料Path / 指定なし>` |
| Network / Secret Handling | `<PJ固有のアクセス・秘密情報管理制約 / 指定なし>` | `<入力資料Path / 指定なし>` |
| Logging / Monitoring Restrictions | `<記録禁止情報・監査上の制約 / 指定なし>` | `<入力資料Path / 指定なし>` |

### 6.3 Data Constraints

| 項目 | PJ開始前に指定された制約 | 指定元・根拠 |
| --- | --- | --- |
| Required Data Platform | `<利用必須のデータ基盤 / 指定なし>` | `<入力資料Path / 指定なし>` |
| Sensitive Data Classification | `<PJ固有の情報区分 / 指定なし>` | `<入力資料Path / 指定なし>` |
| Retention / Deletion Rules | `<事前指定された保存・削除の制約 / 指定なし>` | `<入力資料Path / 指定なし>` |

## 7. Project-Specific Prohibitions

<!--
Framework共通ではなくPJ固有で、事前に明示された禁止事項のみ記載する。
-->

- `<例: 外部Internetへ直接接続する実装は禁止 / 指定なし>`
- `<例: 共通基盤側のリソースをPJ側IaCで作成しない / 指定なし>`

## 8. Open Preconditions / Change Notes

### 8.1 未確認のPJ前提・制約

<!--
Requirements時点で確認が必要な「事前前提」のみ記録する。
後続工程で新たに判断する設計事項はここに書かず、Requirementsの設計引継ぎ記録へ渡す。
-->

| Question ID | 未確認事項 | 影響 | 確認先 | 状態 |
| --- | --- | --- | --- | --- |
| OQ-PJ-001 | `<事前制約に関する確認事項 / なし>` | `<影響 / なし>` | `<Owner / なし>` | `OPEN / RESOLVED / N/A` |

### 8.2 Change Notes

| Date | Change | Reason | Reference |
| --- | --- | --- | --- |
| `<YYYY-MM-DD>` | `<変更内容>` | `<理由>` | `<入力資料 / なし>` |
