---
name: traceability-audit
description: >
  Requirements、Accepted ADR、Production Code、
  Unit Test、Integration Test間のTraceabilityを監査するSkill。
  前方向・逆方向のTraceability、参照切れ、孤立Artifact、
  Test Coverage Evidence、Stale Evidenceを確認し、
  問題の原因工程を特定する。
user-invocable: false
disable-model-invocation: false
---

# Purpose

このSkillは、
SDLC成果物間のTraceabilityを独立監査します。

目的は単にIDが書かれていることではなく、

Requirement
→ Architecture Decision
→ Implementation
→ Test

が意味的にも成立していることを確認することです。


# Policy

以下を唯一の合否基準として使用してください。

`.github/skills/traceability-audit/policy/traceability-policy.yaml`


# Output

以下へ出力してください。

`reports/traceability/traceability-report.json`

`reports/traceability/traceability-report.md`


# Procedure

## Step 1. Audit Scopeを確認する

SDLC Orchestratorから
audit_scopeを取得してください。

対応値:

- ARCHITECTURE
- IMPLEMENTATION
- UNIT_TEST
- INTEGRATION_TEST
- FULL


## Step 2. Requirementsを読み込む

以下を読み込んでください。

`docs/requirements/requirements.md`

`docs/requirements/features/`

実在するRequirement ID一覧を作成してください。

存在しないIDを追加してはいけません。


## Step 3. Global Requirementを抽出する

IDがないProject-wide Requirementについては、
IDを生成せずSource Referenceとして保持してください。

例:

`docs/requirements/requirements.md#認証・認可`


## Step 4. ADRを読み込む

`docs/adr/`

を読み込んでください。

各ADRについて以下を取得します。

- ADR ID
- Status
- Related Requirements
- Decision
- AI Guardrails


## Step 5. ADR Referenceを検証する

各ADRのRelated Requirementsについて、
実在するRequirementか確認してください。

存在しないRequirementを参照していた場合:

`INVALID_REQUIREMENT_REFERENCE`


## Step 6. Scopeに応じた有効ADRを特定する

`audit_scope=ARCHITECTURE`の場合は、
Acceptance候補となるProposed ADRを
Traceability監査対象として扱ってください。

この時点では、
Proposedであること自体を
Traceability Failureとして扱ってはいけません。

`audit_scope=IMPLEMENTATION`、
`UNIT_TEST`、
`INTEGRATION_TEST`、
`FULL`
の場合は、
Accepted ADRのみを
現在有効なArchitecture Decisionとして扱ってください。

Superseded ADRを現在Decisionとして使用してはいけません。


## Step 7. Requirement → ADRを確認する

Architecture Decisionを必要とするRequirementについて、
Scopeに応じた適切なADRが存在することを確認してください。

`audit_scope=ARCHITECTURE`では、
Acceptance候補となるProposed ADRとの
Traceabilityを確認してください。

Implementation以降では、
Accepted ADRとのTraceabilityを確認してください。

すべてのRequirementへ
ADRを強制してはいけません。


## Step 8. Implementationを調査する

Production Codeを調査してください。

RequirementおよびAccepted ADRが
どのFile、Class、Function、Module等へ
実装されているか確認します。


## Step 9. Requirement → Implementationを確認する

Implementation-responsible Requirementについて、
対応するProduction Artifactを確認してください。

存在しない場合:

`IMPLEMENTATION_TRACEABILITY_MISSING`


## Step 10. ADR → Implementationを確認する

Accepted ADRのDecisionおよびAI Guardrailsが
Production Codeへ反映されているか確認してください。

重大な不一致:

`ADR_IMPLEMENTATION_MISMATCH`


## Step 11. Unit Test Evidenceを読み込む

以下を確認してください。

`reports/unit-test/unit-test-evidence.json`

`reports/unit-test/validation-result.json`

Unit Test Codeも必要に応じて確認してください。


## Step 12. Requirement → Unit Testを確認する

Unit Test対象Requirementについて、

Requirement
→ Production Code
→ Unit Test

を確認してください。

対応がない場合:

`UNIT_TEST_TRACEABILITY_MISSING`


## Step 13. Unit Testの逆方向を確認する

Unit Testから、
実在するRequirementへTraceできるか確認してください。

正当な理由なくRequirementとの対応がない場合:

`ORPHAN_TEST`


## Step 14. Integration Test Evidenceを読み込む

以下を確認してください。

`reports/integration-test/integration-test-plan.json`

`reports/integration-test/integration-test-evidence.json`

`reports/integration-test/coverage-gap-report.json`

`reports/integration-test/validation-result.json`


## Step 15. Requirement → Integration Testを確認する

Integration Test対象Requirementについて、

Requirement
→ Integration Point
→ Test Case

の対応を確認してください。


## Step 16. AI Caseを確認する

以下を区別してください。

- AI_GENERATED / INITIAL
- AI_GENERATED / GAP_FILL

どちらもRequirementへのTraceabilityを確認します。


## Step 17. External Caseを確認する

origin=EXTERNALのCaseについて、
Requirement IDが実在することを確認してください。

External Caseの内容を修正してはいけません。


## Step 18. Integration Testの逆方向を確認する

Integration Test Caseから
Requirementへ戻れることを確認してください。

不正なCaseは:

`ORPHAN_TEST`

または

`INVALID_REQUIREMENT_REFERENCE`

として扱います。


## Step 19. Coverage整合性を確認する

Unit Test Evidence、
Integration Test Evidence、
Coverage Gap Report等のCoverage情報と
実際のMappingを比較してください。

自己申告されたCoverage率だけで
PASS判定してはいけません。


## Step 20. Stale Evidenceを確認する

Requirements、
Accepted ADR、
Production Codeが変更された後に
後続Testが再実行されているか確認してください。

古いEvidenceが使用されている場合:

`STALE_EVIDENCE`


## Step 21. Orphan ADRを確認する

Accepted ADRが、
RequirementにもImplementationにも
意味的に対応しない場合は調査してください。

正当な理由がない場合:

`ORPHAN_ADR`


## Step 22. Conflictを確認する

同一Requirementについて、

ADR
Implementation
Unit Test
Integration Test

で期待するBehaviorが矛盾していないか確認してください。

矛盾:

`TRACEABILITY_CONFLICT`


## Step 23. Issueを集約する

同じRoot CauseによるIssueは、
必要に応じて1つのIssueへ集約してください。

ただし影響Artifactを失わないようにしてください。


## Step 24. Recommended Routeを決定する

IssueのRoot Causeが存在する
最上流工程を選択してください。

REQUIREMENTS
ARCHITECTURE
IMPLEMENTATION
UNIT_TEST
INTEGRATION_TEST


## Step 25. Coverageを算出する

最低限以下を算出してください。

- Requirement → ADR
- Requirement → Implementation
- Requirement → Unit Test
- Requirement → Integration Test

ADR不要、
Unit Test対象外、
Integration Test対象外の場合は
妥当なN/Aを除外して計算してください。


## Step 26. JSON Reportを生成する

以下へ生成してください。

`reports/traceability/traceability-report.json`


## Step 27. Markdown Reportを生成する

以下へ生成してください。

`reports/traceability/traceability-report.md`

人が読める形式で、
最低限以下を記載してください。

- Audit Scope
- Summary
- Coverage
- Missing Traceability
- Invalid References
- Orphan Artifacts
- Stale Evidence
- Issues
- Recommended Route


## Step 28. Final判定

Policyを確認してください。

Blocking Issueが存在する場合はFAILです。

すべての必須Traceabilityが成立している場合のみ
PASSとしてください。


# Traceability Model

基本Traceability:

Requirements
→ Accepted ADR
→ Implementation
→ Unit Test
→ Integration Test

ただしADRは
すべてのRequirementへ必須ではありません。


# Forward Traceability

以下を確認してください。

Requirement
→ ADR

Requirement
→ Implementation

Requirement
→ Unit Test

Requirement
→ Integration Test


# Reverse Traceability

以下も確認してください。

ADR
→ Requirement

Implementation
→ Requirement / ADR

Unit Test
→ Requirement

Integration Test
→ Requirement


# Global Requirement Handling

IDが存在しないRequirementへ
新しいIDを生成してはいけません。

FileとHeadingを使用してください。


# Failure Handling

Audit Failureを
Traceability Auditor自身で修正してはいけません。

Issueごとにrecommended_routeを設定し、
SDLC Orchestratorへ返してください。


# Completion

以下を満たすまで完了してはいけません。

- 必要なArtifactをすべて監査
- Forward Traceability確認
- Reverse Traceability確認
- Invalid Reference確認
- Orphan Artifact確認
- Stale Evidence確認
- Coverage算出
- Issue分類
- Recommended Route決定
- JSON Report生成
- Markdown Report生成