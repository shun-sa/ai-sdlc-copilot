# AI SDLC Agent Framework Guide

現行の独立工程は [ArchitectureとADDRの独立工程](independent-architecture-addr.md) を正とします。
Requirements→Architecture→ADDR→Implementationの順で、ADDRをArchitecture内の子活動にしません。
旧版のPREPARE/FINALIZEの記述は新規Runには適用せず、本文修正時だけ実際に差し戻します。

実験の記録担当・指標の定義・出力・開始方法は [実験計測ガイド](experiment-measurement.md) を参照してください。
観測用Scriptと、開発後に人が起動するEvaluation/AcceptanceTestExecutorを区別します。
外部受入表のコード化はAcceptanceTestExecutor専用のAcceptanceTestPrepareへ委譲し、
人の承認後だけ既存Executorで実行します。[受入表の手順](acceptance-sheet-input.md) を参照してください。

設計工程の現行仕様は [設計書とADDRの分離](design-addr-workflow.md) を参照してください。
Architectureは設計書、ADDRは重要判断・差分を担当し、既存ADRの記述には共通の互換契約を適用します。

## 1. このドキュメントの目的

本ドキュメントは、本Repositoryで利用するAI SDLC Agent Frameworkについて、
以下を理解・運用・カスタマイズできるようにするためのガイドです。

- 各Agentの役割
- Agent間の関係
- SDLC全体の動作
- Validator / Assurance / Policy / Criterionの位置づけ
- Failure時のRouting
- Failure Triageの役割
- Final Assuranceの考え方
- カスタマイズ時に変更すべき場所
- 新しいAgent / Criterion / Validatorの追加方法

詳細な実行ルールのSource of Truthは、
各Agent、Skill、Policy、Criterion、Validatorです。

このドキュメントはそれらを横断的に理解するための説明資料であり、
実行時のRuleそのものを置き換えるものではありません。

---

## 2. Frameworkの基本思想

本Frameworkでは責務を以下のように分離します。

| 要素 | 役割 |
| --- | --- |
| Agent | WHO：誰がその責務を持つか |
| Skill | HOW：具体的にどう作業するか |
| Template | WHAT：成果物をどの構造で作るか |
| Policy | PASS / FAIL条件やRouting Rule |
| Criterion | AIが意味的に確認する個別観点 |
| Validator | 機械的に判定可能なGate |
| Orchestrator | Agent起動、工程遷移、差し戻し、再実行を制御 |
| Report | Agent / ValidatorのRuntime結果 |

重要な原則は以下です。

1. 専門Agentの`SUCCESS`だけではPhase PASSとしない。
2. Validatorが存在する工程ではValidator PASSを必須とする。
3. Assurance Agentは成果物を修正しない。
4. 専門Agent同士は直接呼び出さない。
5. Agent間の遷移は必ずSDLC Orchestratorを経由する。
6. 後工程の都合でRequirementやAccepted ADRを勝手に変更しない。
7. 上流成果物が変わった場合は古い後続PASSを再利用しない。
8. Test Expected ResultをProduction Codeから逆算しない。

---

## 3. Agent全体構成

本Frameworkは大きく3種類のAgentで構成されます。

- Orchestrator
- Producer Agent
- Assurance / Diagnosis Agent

```mermaid
flowchart TB
    O[SDLC Orchestrator]

    subgraph Producer["Producer Agents"]
        R[Requirements Agent]
        A[Architecture Agent]
        AD[ADDR Agent]
        I[Implementation Agent]
        U[Unit Test Agent]
        IT[Integration Test Agent]
    end

    subgraph Assurance["Assurance Agents"]
        Q[Quality Review Agent]
        S[Security Review Agent]
        T[Traceability Auditor]
    end

    F[Failure Triage Agent]

    O --> R
    O --> A
    O --> AD
    O --> I
    O --> U
    O --> IT

    O --> Q
    O --> S
    O --> T

    O --> F

    R -. result .-> O
    A -. result .-> O
    AD -. result .-> O
    I -. result .-> O
    U -. result .-> O
    IT -. result .-> O

    Q -. report / route .-> O
    S -. report / route .-> O
    T -. report / route .-> O
    F -. diagnosis / route .-> O
```

Producer AgentやAssurance Agentから別Agentへ直接遷移しません。

必ず、

```text
Agent
  ↓ Result
SDLC Orchestrator
  ↓ Route
Next Agent
```

という関係になります。

### 3.1 Agent間の親子関係（起動責務）

以下は、どのAgentがどのAgentを起動できるかを示す親子関係です。

```mermaid
flowchart TB
    O[SDLC Orchestrator]

    R[Requirements Agent]
    A[Architecture Agent]
    AD[ADDR Agent]
    I[Implementation Agent]
    U[Unit Test Agent]
    IT[Integration Test Agent]

    Q[Quality Review Agent]
    S[Security Review Agent]
    T[Traceability Auditor]

    F[Failure Triage Agent]

    O --> R
    O --> A
    O --> AD
    O --> I
    O --> U
    O --> IT
    O --> Q
    O --> S
    O --> T
    O --> F

    classDef parent fill:#eef6ff,stroke:#3566a8,stroke-width:1px;
    classDef child fill:#f8fbff,stroke:#7f9fcf,stroke-width:1px;
    class O parent;
    class R,A,AD,I,U,IT,Q,S,T,F child;
```

### 3.2 Agent呼び出し順序（標準フロー）

以下は、標準フローにおける呼び出し順序と、各AgentからOrchestratorへの結果返却順です。

```mermaid
sequenceDiagram
    participant O as SDLC Orchestrator
    participant R as Requirements
    participant A as Architecture
    participant AD as ADDR
    participant I as Implementation
    participant U as Unit Test
    participant IT as Integration Test
    participant Q as Quality Review
    participant S as Security Review
    participant T as Traceability Auditor

    O->>R: 1. 起動
    R-->>O: Result
    O->>A: 2. 起動
    A-->>O: Result
    O->>AD: 3. 重要判断を依頼（設計資料・manifestを引渡し）
    AD-->>O: ADDR・明示参照・必要時の設計変更要求
    O->>I: 4. 設計資料とADDRを渡して起動
    I-->>O: Result
    O->>U: 5. 起動
    U-->>O: Result
    O->>IT: 6. 起動
    IT-->>O: Result

    O->>Q: 7. Final Assurance
    Q-->>O: Report / Route
    O->>S: 8. Final Assurance
    S-->>O: Report / Route
    O->>T: 9. Final Assurance
    T-->>O: Report / Route
```

---

## 4. SDLC全体のLifecycle

標準Lifecycleは以下です。

```mermaid
flowchart LR
    R[Phase 1<br/>Requirements]
    A[Phase 2<br/>Architecture]
    AD[Phase 3<br/>ADDR]
    I[Phase 4<br/>Implementation]
    U[Phase 5<br/>Unit Test]
    IT[Phase 6<br/>Integration Test]
    FA[Phase 7<br/>Final Assurance]
    C([COMPLETE])

    R --> A --> AD --> I --> U --> IT --> FA --> C
```

各Phaseは原則として以下のGateを通過します。

```mermaid
flowchart LR
    P[Producer Agent SUCCESS]
    V[Deterministic Validator PASS]
    A[Phase Scope Assurance PASS]
    PP([Phase PASS])

    P --> V --> A --> PP
```

つまり、

```text
Agentが処理できた
```

ことと、

```text
工程として次へ進める
```

ことは別です。

---

## 5. 各Agentの役割

### 5.1 SDLC Orchestrator

#### 役割（SDLC Orchestrator）

SDLC全体の制御を担当します。

主な責務:

- 現在Phaseの管理
- Producer Agentの起動
- Validator実行
- Assurance Agentの起動
- Status確認
- Failure Classificationに基づくRouting
- 上流変更時のInvalidation
- Retry回数の管理
- Failure Triageの起動
- User Input Gateの制御
- Final Assurance
- COMPLETE判定

#### やらないこと

Orchestrator自身は以下を実施しません。

- Requirement作成・修正
- Architecture Decisionの設計
- Production Code実装
- Unit Test実装
- Integration Test実装

専門作業は必ず対象Agentへ委譲します。

---

### 5.2 Requirements Agent

#### 役割（Requirements Agent）

Requirementを定義・更新するProducer Agentです。

主な対象:

- Functional Requirement
- Non-Functional Requirement
- Acceptance Criteria
- Common Requirement
- Authentication / Authorization Requirement
- Error Requirement
- Data Model
- Constraint
- Out of Scope

#### ポイント（Requirements Agent）

後続工程の都合でRequirement IDやCanonical Structureを変更してはいけません。

Requirementに問題が見つかった場合は、
Requirements Phaseへ正式に差し戻して修正します。

---

### 5.3 Architecture Agent

#### 役割（Architecture Agent）

要件・UC/AC・Steering・準備済み仕様を、既存テンプレートに沿った設計資料へ再構成します。

- DB管理データがある場合のlogical-database-design（既存専用テンプレートを使用し、docs/architecture/db-logical-design.mdまたは同名ディレクトリへ出力）
- ファイル連携がある場合のfile-definition
- 現在の入力を対象にしたcross-artifact-consistency-analysis
- 根拠のある実装作業・依存・Wave・検証方法を示すimplementation-task-list
- 出典・成果物・対象・未確定判断の所在をまとめるversion=2のFINAL design-manifest

重要方式の比較・採否は先回りして行わず、必要な場所と根拠だけを次のADDRへ渡します。
FINALはArchitecture資料の公開版であって、全判断完了や実装開始許可を意味しません。
設計Gateと独立ARCHITECTURE Scope検査は、ADDRへ渡す資料を固定するものです。

### 5.3.1 ADDR Agent

#### 役割（ADDR Agent）

Architectureとは対等な独立Producerで、親は同じSDLC Orchestratorです。
Architectureの設計資料・manifest・設計Gateと要件を受け取り、重要判断の要否を確認します。
必要な対象だけ、選択肢・採否理由・判断による設計差分・不変条件・実装拘束を正本ADDRへ記録します。

ADDRは論理DBモデル、FILEの項目表、全体整合性分析、Task一覧を再作成・直接編集しません。
実在ENT/DBD/FILE/TASKへの参照はADDRの正本2章へ明示し、機械可読結果と派生handoffで接続します。
親がADDR Scopeの独立検査と実装引渡しGateを実施し、Implementationへ両方の資料を渡します。

```text
Architectureの設計資料・manifest・設計Gate
  → 親がADDRへ引き渡す
ADDRの重要判断・明示参照
  → 親がhandoff・独立検査・実装引渡しGateを確認
Implementationが設計資料とADDRの両方を読む
```

#### 必要な場合だけの差し戻し

通常のArchitecture FINALIZE再呼出しはありません。
判断の不足・誤りはADDR内で修正します。資料本文/Taskを変える必要があるときだけ、
ADDRが具体的なdesign_change_requestsを返し、親がArchitectureへ実際に戻します。
参照追加だけなら資料を書き戻さず、handoffで結び付けます。

新しい判断の状態はACTIVE / SUPERSEDEDで、ACTIVEだけでは実装開始許可になりません。
旧Accepted ADRは互換入力として残し、新規判断を旧ADRのProposed→Acceptedへ二重生成しません。
詳しくは [独立工程の実行契約](independent-architecture-addr.md) と
[READMEの引渡し図](../../README.md#設計agentとaddr-agentのつながり) を参照してください。

---

### 5.4 Implementation Agent

#### 役割（Implementation Agent）

要件、Architectureの設計資料・Task、ADDRの重要判断に従ってProduction Codeを実装します。

#### 主な責務

- Requirement実装
- Accepted ADR準拠
- Scope外実装の抑止
- Build / Compile / Lint / Type Check可能な状態の作成
- Test可能な構造の維持

#### 戻り先

重要なArchitecture Decisionが不足:

```text
ADR_REQUIRED
→ ADDR
```

Requirement自体に問題:

```text
REQUIREMENT_ERROR
→ Requirements
```

---

### 5.5 Unit Test Agent

#### 役割（Unit Test Agent）

RequirementsおよびAccepted ADRからExpected Resultを導出し、
Unit Testを作成・実行します。

#### 原則

Expected Resultを現在のProduction Codeから逆算してはいけません。

Production Codeに問題がある場合:

```text
IMPLEMENTATION_FIX_REQUIRED
→ Implementation
→ Unit Test再実行
```

Test Code自体の問題:

```text
TEST_ERROR
→ Unit Test
```

---

### 5.6 Integration Test Agent

#### 役割（Integration Test Agent）

複数Component / Dependency / Business Flowを跨ぐIntegration Behaviorを検証します。

本Frameworkでは、
外部から与えられるTest CaseをAI評価用データとして扱うため、
AI生成Caseとの独立性を重要視します。

#### Integration Test Caseの種類

- AI GENERATED / INITIAL
- AI GENERATED / GAP_FILL
- EXTERNAL

#### External Case Independence

```mermaid
flowchart TD
    RC[Required Coverage生成]
    AI[AI INITIAL Case生成]
    LOCK[AI INITIAL固定]
    EXT{External Case確認}
    NONE[Userへ確認]
    LOAD[External Case読込]
    GAP[Coverage Gap分析]
    GF[AI GAP_FILL Case]
    RUN[Test実行]

    RC --> AI --> LOCK --> EXT
    EXT -->|存在| LOAD
    EXT -->|未配置| NONE
    NONE -->|Externalなしを明示確認| GAP
    NONE -->|配置する| LOAD
    LOAD --> GAP
    GAP --> GF --> RUN
```

External Case確認後にAI INITIALを変更してはいけません。

External Caseが未配置の場合、
AI自身の判断で「External Caseなし」として進めることも禁止します。

---

## 6. Assurance Agents

Assurance AgentはProducer Agentとは異なり、
成果物を作るのではなく独立した監査を行います。

```mermaid
flowchart LR
    ART[SDLC Artifacts]
    Q[Quality Review]
    S[Security Review]
    T[Traceability Audit]

    ART --> Q
    ART --> S
    ART --> T

    Q --> R[Report / Recommended Route]
    S --> R
    T --> R

    R --> O[SDLC Orchestrator]
```

Assurance Agent自身が問題を修正してはいけません。

---

### 6.1 Quality Review Agent

#### 目的（Quality Review Agent）

構造Validatorでは判定できない意味的品質を確認します。

主な観点:

- Requirementの内部整合性
- Requirementと設計の整合
- Architectureの妥当性
- 実装の過不足
- Scope Expansion
- 不必要なComplexity
- Unit Testの有効性
- Integration Testの有効性
- Cross Phase Consistency

#### カスタマイズポイント（Quality Review Agent）

意味的品質観点を追加・変更したい場合は、
主に以下を変更します。

```text
.github/skills/quality-review/criteria/
.github/skills/quality-review/policy/quality-review-policy.yaml
```

機械判定ルールを変更する場合:

```text
.github/skills/quality-review/scripts/validate_quality_review.py
```

Validatorを変更した場合は、
対応するUnit Testも更新します。

---

### 6.2 Security Review Agent

#### 目的（Security Review Agent）

SDLC成果物をSecurity観点で独立監査します。

主な観点:

- Authentication
- Authorization
- Secret / Credential
- Input Validation
- Injection
- Data Protection
- Sensitive Data Exposure
- Error / Logging
- Dependency / Configuration
- Security Test Coverage
- Cross Phase Security Consistency

#### Secret取扱い

Secretを検出しても、
Secret値そのものをReportへ出してはいけません。

Evidenceには以下のような情報だけを記録します。

```text
File
Line / Symbol
Issue Type
Risk
```

#### カスタマイズポイント（Security Review Agent）

Semantic Security観点:

```text
.github/skills/security-review/criteria/
```

合否・Severity・Routing:

```text
.github/skills/security-review/policy/security-review-policy.yaml
```

Deterministic Check:

```text
.github/skills/security-review/scripts/validate_security_review.py
```

---

### 6.3 Traceability Auditor

成果物内ID・trace注釈を正本としてC01〜C11を機械検査します。
作成Agentが参照を記入し、Auditorは元成果物を編集せず表とTrace Map v3を再生成します。
意味的レビューは助言として分離し、独立Quality/Security/Test Gateは維持します。
正本構造を維持し、現行はArchitecture→ADDRの独立工程と設計/実装引渡しの2つのGateを使います。

詳細・対象・移行・実行版記録は [注釈方式トレーサビリティ](inline-traceability.md) を参照してください。
手順は `.github/skills/traceability-audit/SKILL.md`、
設定は `policy/traceability-policy.yaml`、
生成・検証は `scripts/trace_check.py`、テストは `scripts/test_trace_check.py` です。

---

## 7. Phase Scope AssuranceとFinal Assurance

Assuranceには2種類あります。

### Phase Scope Assurance

各Phase終了時点で、
現在までに存在するArtifactだけを対象に監査します。

例:

```text
Architecture完了
→ audit_scope=ARCHITECTURE

ADDR完了
→ audit_scope=ADDR

Implementation完了
→ audit_scope=IMPLEMENTATION

Unit Test完了
→ audit_scope=UNIT_TEST

Integration Test完了
→ audit_scope=INTEGRATION_TEST
```

ARCHITECTURE Scopeは設計資料とADDR引渡しの準備、ADDR Scopeは重要判断と設計全体の整合を検査します。
ADDRのACTIVEは実装引渡しGate前の候補。Implementation以降は有効な実装引渡しGateを確認します。
設計分析資料はProducerが作成し、独立Qualityはそれとは別の検査結果を生成します。

### Final Assurance

Integration Test PhaseがPASSした後、
SDLC全体を`audit_scope=FULL`で再監査します。

```mermaid
flowchart TD
    IT[Integration Test Phase PASS]
    Q[Quality Review FULL]
    QV[Quality Validator]
    S[Security Review FULL]
    SV[Security Validator]
    T[Traceability Audit FULL]
    TV[Traceability Validator]
    C([COMPLETE])

    IT --> Q --> QV --> S --> SV --> T --> TV --> C
```

Phase単位のAssurance PASSを
Final Assurance PASSの代わりにしてはいけません。

Final Assuranceで上流修正が発生した場合は、
影響工程を再実行した後、Final Assuranceも再実行します。

---

## 8. Failure Routing

Failureを検出した場合、
発生箇所ではなくRoot Causeに基づいて戻り先を決定します。

| Classification | 基本Route |
| --- | --- |
| REQUIREMENT_ERROR | Requirements |
| ADR_REQUIRED | ADDR |
| IMPLEMENTATION_ERROR | Implementation |
| TEST_ERROR | Unit Test / Integration Test |
| ENVIRONMENT_ERROR | Environment / Orchestrator |
| TEST_SPEC_CONFLICT | User判断 |
| AUTOMATION_BLOCKED | User判断 |

例:

```text
Integration Test FAIL
    ↓
原因はProduction Code
    ↓
IMPLEMENTATION_ERROR
    ↓
Implementationへ戻る
```

TestがFAILしたからといって、
自動的にTest Agentへ戻すわけではありません。

---

## 9. Failure Triage Agent

### 目的（Failure Triage Agent）

通常のFailure Routingを繰り返しても
同一Root CauseのFailureが解消しない場合に、
修正Loopそのものを診断します。

Failure Triage自身は成果物を修正しません。

### 起動

標準では同一Root CauseのFailureについて
通常Routingによる修正・再実行が3回失敗した場合に起動します。

```mermaid
flowchart TD
    F[Failure]
    R1[通常Routing / Retry 1]
    R2[通常Routing / Retry 2]
    R3[通常Routing / Retry 3]
    T[Failure Triage]
    V[Failure Triage Validator]
    ROUTE[Root Cause Route]

    F --> R1
    R1 -->|same root cause| R2
    R2 -->|same root cause| R3
    R3 -->|same root cause| T
    T --> V
    V -->|PASS| ROUTE
```

### 主なClassification

- REQUIREMENT_ERROR
- ADR_REQUIRED
- IMPLEMENTATION_ERROR
- TEST_ERROR
- ENVIRONMENT_ERROR
- CROSS_PHASE_CONFLICT
- UNKNOWN_ROOT_CAUSE

### Result

```text
TRIAGED
BLOCKED
INVALID_INVOCATION
```

`TRIAGED`ならrecommended_routeへ戻します。

`BLOCKED`なら同一修正Loopを停止します。

`INVALID_INVOCATION`なら通常Failure Routingへ戻ります。

### Failure Triage対象外

以下は3回Retryする前にUser Gateへ送ります。

- EXTERNAL_TEST_INPUT_REQUIRED
- TEST_SPEC_CONFLICT
- AUTOMATION_BLOCKED

---

## 10. Invalidation

上流Artifactが変わった場合、
変更前の後続PASSをそのまま利用してはいけません。

```mermaid
flowchart TD
    R[Requirements Changed]
    A[ADDR / Existing Decision Changed]
    I[Production Code Changed]

    RA[Architecture再実行]
    DA[ADDR検証・handoff・実装引渡しGate]
    AI[Implementation再実行]
    UT[Unit Test再実行]
    IT[Integration Test再実行]
    AS[Assurance再実行]

    R --> RA --> DA --> AI --> UT --> IT --> AS
    A --> DA
    I --> UT
```

基本Rule:

| Changed Artifact | 再検証対象 |
| --- | --- |
| Requirements | Architecture以降 |
| 設計資料 / Task | 設計Gate、ADDRと影響する下流 |
| ADDR / 参照中の旧Accepted ADR | ADDR検証・handoff・実装引渡しGateと影響する下流 |
| Production Code | 影響するUnit / Integration Test |
| Unit Test Codeのみ | Unit Test |
| Integration Test Codeのみ | Integration Test |

Assurance対象Artifactが変更された場合は、
Quality / Security / Traceabilityの古いPASSも再利用しません。

Requirements、ADR、Production Code、
Unit Test Code、Integration Test Codeが変更された場合、
変更前のTrace Mapも再利用せず、
現在のSource Artifactから再生成します。

---

## 11. Repository内の役割分担

実際の配置は次のとおりです。生成予定の成果物Directoryを含みます。

```text
.github/agents/                         Agent定義は直下の*.agent.md
  sdlc-orchestrator.agent.md
  architecture.agent.md
  addr.agent.md
  ...
.github/skills/architecture/            設計資料の手順・正本・検証
.github/skills/addr/                    重要判断の手順・正本・検証
.github/skills/failure-triage/           3回ループと原因別Routing
.github/skills/evaluation/              実験記録器・開発後評価
docs/requirements/                     要件本文・UC/AC
docs/architecture/                     設計資料とTask
docs/addr/                             新規重要判断
docs/adr/                              既存ADR（互換入力）
reports/architecture/                  設計Gateと互換名のADDR契約・実装引渡しGate
reports/addr/                          設計と判断を結ぶ派生handoff
reports/experiments/<run-id>/           工程時間・手戻り・試験証跡
reports/loop-control/                  修正履歴・未解決結果・継続判定
```

`reports/`はRuntime Resultです。

RequirementやADRの代わりとなるSource of Truthではありません。

---

## 12. どこを変更すればよいか

### Project全体の不変ルールを変えたい

変更先:

```text
.github/copilot-instructions.md
```

例:

- Agent間直接呼出し禁止
- Source of Truth
- Test Expected Result原則
- External Case不変
- Repository Independence

詳細な工程手順はここへ増やしすぎないでください。

### SDLCの工程順やRoutingを変えたい

変更先:

```text
.github/agents/sdlc-orchestrator.agent.md
```

例:

- Phase順序
- Agent起動タイミング
- Failure Routing
- Invalidation
- Final Assurance
- User Input Gate

### Agentの責務・境界を変えたい

変更先:

```text
.github/agents/**/<agent>.agent.md
```

例:

- Agentが扱うInput
- Output
- 禁止事項
- Parent Agent
- 実行可能Tool

### 作業手順を変えたい

変更先:

```text
.github/skills/<skill>/SKILL.md
```

例:

- 何をどの順番で読むか
- どのArtifactを確認するか
- Report生成手順

### PASS / FAIL条件を変えたい

変更先:

```text
.github/skills/<skill>/policy/*.yaml
```

Policyに置くもの:

- Allowed Scope
- Severity
- Blocking条件
- Routing
- Threshold
- Required Report
- Allowed Classification

### Assuranceの意味的観点を追加したい

変更先:

```text
.github/skills/<assurance-skill>/criteria/*.criterion.md
```

例:

Security Reviewへ新しいSecurity観点を追加する場合、
新しいCriterionを追加します。

Criterionで新しいIssue Classificationを使用する場合は、
Policy側のClassification / Routingも追加してください。

### 機械チェックを変えたい

変更先:

```text
.github/skills/<skill>/scripts/validate_*.py
```

Validatorは機械判定できる内容だけを扱います。

意味的判断をValidatorへ移してはいけません。

Validator変更時は、

```text
test_validate_*.py
```

も同時に更新してください。

---

## 13. カスタマイズ例

### 13.1 Quality Reviewへ新しい観点を追加

例:

「API backward compatibility」を新しい品質観点として追加したい場合。

1. `criteria/`へ新しいCriterionを追加
2. 必要ならPolicyへIssue Classificationを追加
3. RoutingをPolicyへ追加
4. ValidatorがReport構造上そのClassificationを許可できるか確認
5. Validator Testを追加
6. 本ドキュメントの観点一覧も更新

### 13.2 Security Severity Ruleを変更

変更対象:

```text
security-review-policy.yaml
```

例:

特定ClassificationをHIGH以上として扱いたい場合、
Policy / Criterionの責務を確認して変更します。

Validatorは、
ReportされたSeverityがPolicyに適合しているかを検証します。

### 13.3 Failure Triage Retry回数を変更

現在の標準は3回です。

変更する場合は、

```text
.github/skills/failure-triage/policy/failure-triage-policy.yaml
```

のRetry Thresholdを変更します。

また、OrchestratorにRetry回数が固定値として記述されている場合は、
Orchestrator側の記述も同時に同期してください。

将来的に一元化する場合は、
Orchestrator側を「Policyで指定されたRetry Threshold」と表現し、
Threshold値自体をPolicyへ集約する方式が適しています。

---

## 14. 新しいAgentを追加する場合

新Agentを追加する場合は、
Agent Fileを追加するだけでは完了しません。

標準手順:

1. Agentの責務を決める
2. Agent Fileを作成する
3. Skillを作成する
4. 必要ならTemplateを作成する
5. PASS / FAILがある場合はPolicyを作成する
6. Semantic ReviewならCriterionを作成する
7. Deterministic Gateが必要ならValidatorを作成する
8. Validator Testを作成する
9. SDLC Orchestratorの`agents:`へ登録する
10. 起動条件をOrchestratorへ追加する
11. Result Status / Routingを定義する
12. Invalidationへの影響を確認する
13. Completion Conditionsへの影響を確認する
14. 本ドキュメントを更新する

重要なのは、

```text
Agentを作った
```

だけでなく、

```text
Orchestratorからいつ呼ばれ、
何を返し、
その結果でどこへ遷移するか
```

まで定義することです。

---

## 15. やってはいけないカスタマイズ

以下はFrameworkの責務分離を壊すため避けてください。

### Producer Agentから次Agentを直接呼ぶ

悪い例:

```text
Implementation Agent
→ Unit Test Agentを直接起動
```

正しい例:

```text
Implementation Agent
→ Result
→ SDLC Orchestrator
→ Unit Test Agent
```

### Assurance Agentが成果物を修正する

悪い例:

```text
Security Review
→ 脆弱コードを直接修正
```

正しい例:

```text
Security Review
→ IMPLEMENTATION route
→ Orchestrator
→ Implementation Agent
```

### Validatorへ意味的レビューを入れる

悪い例:

```text
ValidatorがArchitectureとして美しいかAI判断する
```

Validatorは、

- 必須Field
- Status
- Count
- Coverage value
- Routing consistency
- Required Report
- Policy consistency

などの決定論的チェックを担当します。

### TestをProduction Codeへ合わせる

Expected ResultのSourceはRequirements / Accepted ADRです。

### External Test CaseをAI都合で変更する

External Caseは評価データです。

Input / Step / Expected Resultを変更してGateを通してはいけません。

### 上流変更後に古いPASSを使う

Requirement / ADR / Codeが変わった場合は、
Invalidation Ruleに従って再実行してください。

---

## 16. Troubleshooting

### Phaseが進まない

確認順:

1. Producer Agent Status
2. Validator exit code
3. Assurance Report
4. Assurance Validator
5. recommended_route
6. unresolved blocking issue
7. invalidated_phases

### 同じ修正を繰り返している

確認:

- Failure Signature
- Root Cause
- retry_count
- previous_routes
- Failure Triage起動条件

### Architectureから先へ進まない

確認:

- version=2のFINAL design-manifestと設計資料が現在版か
- 設計Validator・ARCHITECTURE Scopeの独立検査・設計Gateが揃っているか
- ADDRへ設計資料と予約ID契約が渡され、判断の要否が記録されたか
- ADDRの検証・handoff・独立ADDR Scope検査・実装引渡しGateが揃っているか
- 3回後の未解決継続の場合は、ARCHITECTUREとADDRの継続判定と未実行範囲が明示されているか

### Integration Testで止まる

External Test Input Gateを確認します。

External Case未配置の場合、
ユーザーが以下のどちらかを明示する必要があります。

- External Caseを配置する
- External Caseなしで進める

### Final Assuranceで差し戻された

正常な動作です。

Root Cause工程へ戻し、
Invalidation Ruleに従って後続工程を再実行した後、
`audit_scope=FULL`のFinal Assuranceを再実行してください。

---

## 17. Framework変更時の確認チェックリスト

Frameworkを変更した場合は以下を確認してください。

- [ ] Project-wide invariantと矛盾していない
- [ ] Agentの責務境界が明確
- [ ] Agentが別Agentを直接起動していない
- [ ] SkillとAgentに同じ詳細手順を重複記載していない
- [ ] PolicyとValidatorの役割が分離されている
- [ ] Semantic判断をValidatorへ入れていない
- [ ] 新StatusのRoutingがOrchestratorに存在する
- [ ] 新Routeに必要なInvalidationが定義されている
- [ ] Validator変更に対応するUnit Testがある
- [ ] ArchitectureとADDRのScope・入力版が分離され、ACTIVEだけで実装開始していない
- [ ] Implementation以降はAccepted ADRだけを利用している
- [ ] External Case Independenceが維持されている
- [ ] Final Assuranceが`FULL`で実行される
- [ ] Failure Triage対象外FailureをRetryしていない
- [ ] Runtime ReportをSource of Truth化していない
- [ ] Repository / CI/CD / Cloud Providerを暗黙的に固定していない

---

## 18. まとめ

本Frameworkの中心となる考え方は、

```text
Orchestrator = 制御
Producer Agent = 成果物作成
Assurance Agent = 独立監査
Failure Triage = 非収束Failureの診断
Validator = 決定論的Gate
Policy = 合否・Routing基準
Criterion = 意味的監査観点
```

という責務分離です。

通常フロー:

```text
Requirements
→ Architecture
→ Implementation
→ Unit Test
→ Integration Test
→ Final Assurance
→ COMPLETE
```

各Phase:

```text
Producer Agent
→ Validator
→ Phase Scope Assurance
→ Phase PASS
```

Failure時:

```text
Failure
→ Root Cause Routing
→ 修正
→ 再実行
```

非収束時:

```text
同一Root Cause Retry Threshold到達
→ Failure Triage
→ Validator
→ Root Cause工程へ再Routing
```

最終的に、
すべての工程、Validator、Final AssuranceがPASSし、
未解決Blocking Issueが存在しない場合のみ
SDLC全体をCOMPLETEとします。

## 工程継続の基本方針（2026-10-21更新）

全工程は、初回失敗とは別に修正・再検査を最大3回行い、残れば未解決を記録して次へ進めます。
旧来の停止条件は品質PASSの判定として維持し、工程継続では共通3回方針を優先します。
検査FAILは変更しません。最終結果もCOMPLETE_WITH_UNRESOLVEDとして正常完了と区別します。
詳細は [共通3回ループ](bounded-repair-loop.md) を参照してください。
