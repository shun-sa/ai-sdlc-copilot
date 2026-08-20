```markdown
---
name: implementation
description: >
  要件定義成果物に定義された内容を漏れなく実装し、
  Accepted ADRのDecisionおよびAI Guardrailsを遵守するための実装Skill。
  Requirementsから実装対象を抽出し、実装網羅性の確認、既存実装の確認、
  Production Codeの作成・変更、Build検証を行う場合に使用する。
  実装中に新たな重要設計判断を検出した場合はADR_REQUIREDとして報告し、
  Architecture工程でADRへ反映された後に実装を継続する。
  DBを使用する実装では、単体テスト・結合テストでDockerコンテナ等の
  一時的なテストDBを利用可能な構造とする。
user-invocable: false
disable-model-invocation: false
---

# Implementation Skill

## Purpose

このSkillは、
要件定義成果物に定義された内容を漏れなくProduction Codeへ実装するための
標準的な実装手順を定義します。

Implementation工程では以下を重視します。

1. 要件定義成果物の内容をすべて確認する
2. 実装対象となる要件を漏れなく実装する
3. Accepted ADRのDecisionを遵守する
4. Accepted ADRのAI Guardrailsを遵守する
5. 実装中に発生した重要な設計判断を必ずADRへ反映する
6. 後続の単体テスト・結合テストでテスト可能な構造にする
7. DBを使用する場合、Dockerコンテナ等のテストDBへ切り替え可能にする

このSkillは、
要件やArchitecture Decisionを独自に変更するためのものではありません。


# Fundamental Rules

実装時は以下を必ず守ってください。

1. 要件定義成果物全体を確認する
2. FRだけでなく、実装に影響する他の要件も確認する
3. 要件を理由なく未実装のまま残さない
4. Accepted ADRを実装前に確認する
5. Accepted ADRと異なる方式を独自に採用しない
6. Out of Scopeを実装しない
7. 根拠のない機能を追加しない
8. 重要な設計判断を実装コードだけに残さない
9. Production Codeを本番環境固有のDBへ密結合させない
10. 後続Test Agentが自動テスト可能な構造を維持する


# Inputs

実装開始前に以下を確認してください。

- 要件定義成果物
- 起動ファイル
- Accepted状態のADR
- 既存ソースコード
- プロジェクト共通Instructions
- Implementation Agentから渡された対象範囲
- Requirements工程のASSUMPTION
- Architecture工程のASSUMPTION

要件定義成果物およびADRを確認せずに
Production Codeの変更を開始してはいけません。


# Procedure

## Step 1. 要件定義成果物をすべて確認する

要件定義成果物について、
最低限以下を実装観点で確認してください。

1. 用語集
2. 背景
3. 目的
4. 誰のために
5. 開発のスコープ外（Out of Scope）
6. 成功条件（Acceptance Criteria）
7. 業務フロー/ユーザーストーリー
8. 共通機能要件
9. 認証・認可
10. エラー仕様（共通）
11. 非機能要件（NFR）
12. データモデル
13. 機能要件（FR）
14. 制約条件

FRだけを読んで実装を開始してはいけません。

各項目について、
Production Codeへの影響があるか確認してください。


## Step 2. 実装対象を整理する

要件から実装対象を抽出してください。

特に以下を確認します。

- 各FR
- 各FRの入力項目
- バリデーション
- エラー条件
- 出力/挙動・完了条件
- 共通機能要件
- 認証・認可
- 共通エラー仕様
- NFR
- データモデル
- 技術制約
- 業務制約
- Acceptance Criteria

要件に記載された内容を、
「重要ではない」などの理由で独自に除外してはいけません。


## Step 3. Requirement Coverageを作成する

実装開始前に、
実装対象となるRequirementと実装状態を整理してください。

各Requirementを以下のいずれかに分類します。

### NOT_IMPLEMENTED

まだ実装されていない。

### IMPLEMENTED

今回のImplementation工程で実装した。

### VERIFIED_EXISTING

既存実装を確認し、
要件を既に満たしていることを確認した。

### BLOCKED

情報不足または矛盾により実装できない。

### ADR_REQUIRED

重要な設計判断が不足しており、
ADRが確定するまで実装できない。

### DELEGATION_REQUIRED

Implementation工程以外での対応が必要。

Implementation工程完了時には、
実装対象のRequirementが原則として

- IMPLEMENTED
- VERIFIED_EXISTING

のいずれかになっている必要があります。


## Step 4. Accepted ADRを確認する

実装対象Requirementに関連するADRを確認してください。

最低限以下を確認します。

- Status
- Related Requirements
- Decision
- Consequences
- AI Guardrails

StatusがAcceptedのADRについては、
確定済みArchitecture Decisionとして扱ってください。

Decisionと異なる実装を行ってはいけません。

AI Guardrailsに反する実装を行ってはいけません。


## Step 5. 既存実装を確認する

新しいコードを書く前に、
既存実装を検索してください。

最低限以下を確認します。

- 同じ機能が既に存在しないか
- 共通処理が存在しないか
- 既存Architectureに従うべき実装がないか
- 同じデータアクセス処理がないか
- 共通エラー処理がないか
- 既存の設定方式がないか
- 既存のDB接続方式がないか

既存実装を確認せずに
重複機能を新規作成してはいけません。


## Step 6. 実装前にArchitecture Decisionの不足を確認する

Production Codeを変更する前に、
実装に必要な重要なArchitecture Decisionが
ADRとして確定しているか確認してください。

以下のいずれかに該当する判断が必要な場合、
ADR化対象として扱ってください。

1. 複数案がある
2. 後から変更すると高コスト
3. 非機能要件に影響する
4. AIが誤判断すると手戻りが大きい
5. 要件・設計・実装・テストの複数成果物に影響する

代表例:

- 認証方式
- 認可方式
- DB方式
- API方式
- 外部連携方式
- データ永続化方式
- トランザクション方式
- キャッシュ方式
- 可用性方式
- ログ・監視方式
- バックアップ方式

既存ADRまたは要件・制約から一意に決まらない場合は、
Implementation工程だけで決定してはいけません。


## Step 7. ADR_REQUIREDを処理する

実装中または実装前に
新たな重要設計判断を検出した場合、
その判断をProduction Codeだけに反映してはいけません。

Implementation AgentへADR_REQUIREDとして返してください。

最低限以下を整理します。

- 関連Requirement
- 関連する既存ADR
- 判断が必要となったContext
- 必要なArchitecture Decision
- 確認できた選択肢
- 各選択肢の影響
- 判断が確定するまで実装できない範囲

Implementation Skill自身で
新しいADRを作成・Acceptedにしてはいけません。

SDLC Orchestratorを経由してArchitecture工程へ戻し、
Architecture AgentによってADRが作成または更新され、
必要な検証を経てAcceptedとなった後に実装を再開してください。


## Step 8. 局所的な実装判断を行う

すべての実装判断をADR化する必要はありません。

以下のような局所的かつ容易に変更可能な判断は、
既存のInstructions、コード規約、Accepted ADRに従って
Implementation工程内で決定できます。

例:

- 変数名
- privateメソッドの分割
- 単純な関数分割
- 同一Architecture内のコード整理
- 既存規約に沿ったファイル配置
- 単純なリファクタリング

重要なArchitecture Decisionか判断できない場合は、
ADR_REQUIREDを優先してください。


## Step 9. Production Codeを実装する

要件、制約、Accepted ADRに従って
Production Codeを実装してください。

実装時は以下を確認してください。

- FRを満たす
- Acceptance Criteriaを満たせる
- 共通機能要件を満たす
- 認証・認可要件を満たす
- エラー仕様を満たす
- 必要なNFRを反映する
- データモデルと整合する
- 業務制約を守る
- 技術制約を守る
- Out of Scopeを実装しない
- Accepted ADRを守る
- AI Guardrailsを守る


## Step 10. DBアクセスをテスト可能な構造にする

DBを利用するProduction Codeは、
単体テストおよび結合テストにおいて
Dockerコンテナ等で起動する一時的なテストDBへ
接続できる構造としてください。

Production環境のDBへ固定依存してはいけません。


## Step 11. DB接続情報を外部化する

DB接続に必要な情報を
Production Codeへハードコードしてはいけません。

最低限以下を外部から設定可能にしてください。

- Host
- Port
- Database Name
- User
- Password
- その他接続に必要な値

既存プロジェクトで採用されている
設定方式を優先してください。

例:

- 環境変数
- 設定ファイル
- Dependency Injection

新しい設定方式を導入すること自体が
重要なArchitecture Decisionになる場合は、
ADR_REQUIREDとして扱ってください。


## Step 12. テスト用DBへの差し替え可能性を確認する

以下を確認してください。

- Production DBとテストDBの接続先を切り替えられる
- Dockerコンテナ等で割り当てられたHost/Portを利用できる
- Production Credentialがなくてもテストできる
- Production DBがなくてもテストを実行できる
- テスト環境ごとに独立したDBを利用できる
- テスト終了後に破棄可能なDBを利用できる

以下は禁止します。

- Production DBエンドポイントのハードコード
- Production Credentialへの必須依存
- 固定された共有テストDBへの必須依存
- Productionデータが存在することを前提とした実装


## Step 13. DB Schemaを再現可能にする

DB Schemaが必要な場合、
Dockerコンテナ等のテストDBへ
同じSchemaを再現できるようにしてください。

既存プロジェクトにMigration方式がある場合は、
その方式を使用してください。

例:

- Flyway
- Liquibase
- Prisma Migration
- ORM Migration
- SQL Migration

ただし、
既存方式が存在しない場合に
Implementation Skill独自でMigration技術を決定してはいけません。

その選択が重要なArchitecture Decisionに該当する場合は、
ADR_REQUIREDとして扱ってください。


## Step 14. DB初期状態への依存を避ける

Production Codeは、
特定のテストデータやProductionデータが
事前に存在することを前提にしてはいけません。

以下を避けてください。

- 固定IDへの依存
- Productionデータへの依存
- 特定の共有DB状態への依存
- テストから初期化できない永続状態への依存

テストデータそのものの作成は、
後続Test Agentの責務です。


## Step 15. Testabilityを確認する

後続のUnit Test AgentおよびIntegration Test Agentが
Production Codeを自動テストできることを確認してください。

以下のようなテスト困難な実装を避けてください。

- 環境依存値のハードコード
- 外部サービスへの固定接続
- DB接続先の固定
- 隠れたグローバル状態
- テストから差し替えられない外部依存
- 起動時にProduction環境への接続を必須とする構造

テストしやすくするために
要件そのものを変更してはいけません。


## Step 16. エラー処理を実装する

以下を確認してください。

- 共通エラー仕様
- FR固有のエラー条件
- バリデーションエラー
- 認証エラー
- 認可エラー
- データアクセスエラー
- 外部サービスエラー

要件で定義されたエラー条件を
正常系のみの実装で回避してはいけません。


## Step 17. 認証・認可を実装する

認証・認可要件が存在する場合は、
要件およびAccepted ADRに従って実装してください。

特に認可について、
Frontend側の表示制御だけで
満たしたことにしてはいけません。

ADRにAI Guardrailsが存在する場合は、
必ず遵守してください。


## Step 18. NFRを実装へ反映する

NFRを
後続テストで確認するだけの項目として扱ってはいけません。

Production Codeの実装に影響するNFRについては、
必要な実装を行ってください。

Implementation工程だけでは対応できないNFRについては、
DELEGATION_REQUIREDとして記録してください。


## Step 19. Requirement Coverageを再確認する

実装後、
Step 3で作成したRequirement Coverageを更新してください。

各Requirementについて以下を確認します。

- IMPLEMENTED
- VERIFIED_EXISTING
- ADR_REQUIRED
- BLOCKED
- DELEGATION_REQUIRED

未確認のRequirementを残してはいけません。


## Step 20. Requirementと実装箇所を紐づける

各Requirementについて、
実装箇所を特定してください。

最低限以下を記録します。

- Requirement ID
- 実装ファイル
- 主要Symbolまたは責務
- Related ADR

例:

FR-001

implementation:
- src/user/UserService.ts
- src/user/UserController.ts

related_adrs:
- ADR-001

後続のTraceability Auditorが利用できる状態にしてください。


## Step 21. Build Validationを実行する

プロジェクトに存在する
Build・Compile・静的検証を実行してください。

利用可能な場合は以下を確認します。

- Formatter
- Linter
- Type Check
- Compile
- Build

既存テストが存在する場合は、
Regression確認のために実行してください。

新しいテストケースを作成することは
後続Test Agentの責務です。


## Step 22. Validation Errorを処理する

Buildまたは既存テストが失敗した場合、
原因を確認してください。

### IMPLEMENTATION_ERROR

Production Codeの実装ミス。

Implementation工程内で修正してください。

### ADR_REQUIRED

Architecture Decisionが不足している、
または既存ADRの変更が必要。

Implementation工程だけで修正せず、
ADR_REQUIREDとして返してください。

### REQUIREMENT_ERROR

要件の矛盾・不足が原因。

要件を勝手に変更せず、
BLOCKEDとして返してください。

### ENVIRONMENT_ERROR

実行環境または外部依存が原因。

原因と影響を記録してください。


## Step 23. Retryを制御する

同一原因に対する修正を
無制限に繰り返してはいけません。

同一原因について3回修正しても
BuildまたはValidationが成功しない場合は、
FAILEDとしてImplementation Agentへ返してください。

以下を記録してください。

- 原因
- 実施した修正
- 各修正結果


# ADR Compliance Check

Implementation工程完了前に、
Accepted ADRごとに以下を確認してください。

- Decisionに反する実装がない
- AI Guardrailsに反する実装がない
- 新しい重要設計判断がコードだけに存在していない
- 既存ADRと実装が矛盾していない

実装から新しいArchitecture Decisionが発生しているにもかかわらず、
ADRへ反映されていない状態で完了してはいけません。


# Requirement Coverage Check

Implementation工程完了前に、
要件定義成果物をもう一度確認してください。

以下を確認します。

- Acceptance Criteria
- 共通機能要件
- 認証・認可
- エラー仕様
- NFR
- データモデル
- FR
- 制約条件

「FRをすべて実装した」だけで
実装完了と判断してはいけません。


# Database Testability Check

DBを使用する場合、
最低限以下を確認してください。

- DB接続設定が外部化されている
- Docker等のテストDBへ接続できる
- Production DBへの固定依存がない
- Production Credentialへの固定依存がない
- SchemaをテストDBへ再現できる
- テストデータを独立して投入可能である
- テスト終了後にDBを破棄してもProduction Codeに影響しない

DBを使用しない場合はNOT_APPLICABLEとして扱ってください。


# Prohibited Actions

以下を禁止します。

- 要件を理由なく未実装にする
- FRだけを実装して全要件実装済みと判断する
- 要件定義成果物を勝手に変更する
- Accepted ADRを勝手に変更する
- Accepted ADRを無視する
- ADR化すべき重要判断をコードだけに埋め込む
- ADR_REQUIRED事項を独自判断で確定する
- Out of Scopeの機能を実装する
- 根拠のない機能を追加する
- DB接続情報をハードコードする
- Production DBをテストに必要とする
- 共有DBの状態へテストが依存する構造にする
- テストを通すために要件を変更する
- テストを通すためにAccepted ADRを無視する
- 次工程のAgentを直接起動する


# Completion Check

Implementation Skillを完了する前に、
以下をすべて確認してください。

- 要件定義成果物全体を確認した
- 実装対象Requirementをすべて確認した
- 各Requirementの実装状態を確認した
- 必要なRequirementを実装した
- 既存実装については実際にコードを確認した
- Accepted ADRを確認した
- Decisionを遵守した
- AI Guardrailsを遵守した
- 新しいArchitecture Decisionが未反映のまま残っていない
- Out of Scopeを実装していない
- Requirementと実装箇所を紐づけた
- DB利用時のTestabilityを確認した
- BuildまたはCompileが成功した
- BLOCKED事項を明示した
- ADR_REQUIRED事項を明示した
- DELEGATION_REQUIRED事項を明示した


# Output

処理完了後、
Implementation Agentが判断できるように
以下を返してください。

- 作成・更新・削除したファイル
- Requirementごとの実装状態
- Requirementごとの実装箇所
- RequirementごとのRelated ADR
- 新たに検出したArchitecture Decision
- ADR_REQUIRED事項
- BLOCKED事項
- DELEGATION_REQUIRED事項
- DB Testability確認結果
- Build結果
- 既存テスト実行結果
- Accepted ADR遵守確認結果
- Out of Scope確認結果
- ASSUMPTION
```
