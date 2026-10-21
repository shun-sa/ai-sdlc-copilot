# Project AI Steering

<!--
位置付け:
- 本文書は「PJ固有情報」をAI Agentへ与えるためのSource Artifactである。
- Framework共通のAgent動作、工程手順、Routing、Validator実行方法は記載しない。
  それらは Agent / Skill / Policy をSource of Truthとする。
- RequirementやADRの内容を本書へ複製しない。必要な場合はID/Pathで参照する。
- .github/copilot-instructions.md 等から本書を参照させる。
- Secret、Password、Token、個人情報等の実値は記載しない。
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
| Requirements | `<docs/requirements/requirements.md>` | 要求のSource of Truth |
| Use Case Index | `<docs/requirements/use-case-user-story-index.md>` | US/UC一覧 |
| Use Case Details | `<docs/requirements/use-cases/>` | Flow / Acceptance Criteria |
| Glossary | `<docs/requirements/glossary.md>` | 用語定義 |
| ADR | `<docs/adr/>` | Accepted ADRを設計判断のSource of Truthとする |

## 3. Technology Stack

<!--
ここには「このPJで採用している技術」を記載する。
採用理由や重要な設計判断はADRへ記載し、本書ではADR IDを参照する。
-->

| Layer / Purpose | Technology | Version / Policy | Related ADR | Notes |
| --- | --- | --- | --- | --- |
| Frontend | `<React / TypeScript 等>` | `<Version / LTS方針>` | `<ADR-xxx / None>` | `<補足>` |
| Backend | `<Java / Spring Boot 等>` | `<...>` | `<...>` | `<...>` |
| Database | `<PostgreSQL 等>` | `<...>` | `<...>` | `<...>` |
| Runtime | `<ECS / Lambda 等>` | `<...>` | `<...>` | `<...>` |
| Test | `<Jest / JUnit 等>` | `<...>` | `<...>` | `<...>` |

## 4. Repository / Project Structure

```text
<repository-root>/
├─ <directory>/   # <責務>
├─ <directory>/   # <責務>
└─ <directory>/   # <責務>
```

### 4.1 PJ固有の配置ルール

- `<例: Frontendは frontend/ 配下に置く>`
- `<例: Backendの各Domainは modules/<domain>/ 配下に置く>`

### 4.2 PJ固有のDependency Rules

- `<許可する依存方向>`
- `<禁止する依存方向>`
- `<Module間アクセス規則>`

関連ADR: `<ADR-xxx / None>`

## 5. Project-Specific Coding Conventions

<!--
組織・Framework共通規約ではなく、このPJでのみ必要な差分を記載する。
-->

### 5.1 Naming

| 対象 | PJ固有規則 |
| --- | --- |
| File | `<規則 / 共通規約に従う>` |
| Class / Component | `<規則 / 共通規約に従う>` |
| Function / Method | `<規則 / 共通規約に従う>` |
| Test | `<規則 / 共通規約に従う>` |

### 5.2 その他のPJ固有規則

- `<例: Custom Hookは *Hooks.ts とする>`
- `<該当なしの場合は None>`

## 6. Interface / API Conventions

| 項目 | PJ固有ルール | Related ADR / Spec |
| --- | --- | --- |
| API Style | `<REST / GraphQL 等>` | `<ADR-xxx>` |
| Request Correlation | `<traceId等>` | `<ADR-xxx / Spec>` |
| Date / Time | `<ISO 8601等>` | `<...>` |
| Error Response | `<PJ固有形式>` | `<...>` |
| Pagination | `<PJ固有形式>` | `<...>` |

## 7. Error / Logging / Observability Conventions

### 7.1 Error Handling

- `<PJ固有の利用者向けエラー表現>`
- `<PJ固有の回復・Retryルール>`

### 7.2 Logging

- Required Fields: `<traceId, user-independent correlation key 等>`
- Prohibited Fields: `<PJ固有の機密情報区分>`
- Log Format: `<JSON / text 等>`
- Masking: `<PJ固有方針>`

### 7.3 Monitoring

- Required Metrics: `<PJ固有Metric>`
- Alert / SLO Reference: `<文書Path / None>`

## 8. Security / Data Project Constraints

<!--
共通SecurityルールはSkill/Policyへ置く。
ここには案件固有の認証方式、データ区分、ネットワーク制約等だけを記載する。
-->

### 8.1 Security

- Authentication: `<Cognito等 / Related ADR>`
- Authorization: `<PJ固有方式 / Related ADR>`
- Network Constraint: `<閉域網等>`
- Secret Management: `<利用サービス / Related ADR>`

### 8.2 Data

- Primary Data Store: `<RDS PostgreSQL等>`
- Transaction Boundary: `<PJ固有ルール / Related ADR>`
- Sensitive Data Classification: `<PJ固有区分 / None>`
- Retention / Deletion Reference: `<文書 / None>`

## 9. Build / Test / Local Execution

<!--
AIがこのRepositoryで実行すべき「PJ固有コマンド」を記載する。
どの工程で何を実行するかはSkill側で定義する。
-->

| Purpose | Command | Working Directory | Notes |
| --- | --- | --- | --- |
| Dependency Install | `<npm ci / mvn ...>` | `<path>` | `<...>` |
| Build | `<command>` | `<path>` | `<...>` |
| Lint / Static Check | `<command>` | `<path>` | `<...>` |
| Unit Test | `<command>` | `<path>` | `<...>` |
| Integration Test | `<command>` | `<path>` | `<...>` |

## 10. External Systems / Environment Constraints

| System / Constraint | 内容 | Mock / Real | Reference |
| --- | --- | --- | --- |
| `<External API>` | `<利用目的・制約>` | `MOCK / REAL` | `<Spec / ADR>` |
| `<Network>` | `<インターネット接続不可等>` | `N/A` | `<Reference>` |

## 11. Project-Specific Prohibitions

<!--
「全PJ共通の禁止事項」はSkill/Policyへ置く。
ここにはこのPJに固有の禁止事項のみを書く。
-->

- `<例: 外部Internetへ直接接続する実装は禁止>`
- `<例: 特定の共通基盤リソースをIaCで作成しない>`
- `<該当なしの場合は None>`

## 12. Open Project Decisions

| Decision / Question ID | 内容 | 影響 | 解決先 | 状態 |
| --- | --- | --- | --- | --- |
| OQ-PJ-001 | `<PJ固有の未決事項>` | `<影響>` | `<Requirements / ADR / Owner>` | `OPEN / RESOLVED` |

## 13. Change Notes

| Date | Change | Reason | Related Requirement / ADR |
| --- | --- | --- | --- |
| `<YYYY-MM-DD>` | `<変更>` | `<理由>` | `<ID / None>` |
