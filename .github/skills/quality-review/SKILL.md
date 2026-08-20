---
name: quality-review
description: >
  Requirements、Architecture、Implementation、
  Unit Test、Integration Test成果物を対象として、
  構造チェックでは判定できない意味的品質をレビューするSkill。
  Requirementとの整合性、設計妥当性、実装の過不足、
  Testの有効性、工程間の意味的矛盾を評価する。
user-invocable: false
disable-model-invocation: false
---

# Purpose

このSkillは、
SDLC成果物の意味的品質を
独立してレビューするために使用します。

成果物を修正するSkillではありません。


# Policy

以下を唯一の合否基準として使用してください。

`.github/skills/quality-review/policy/quality-review-policy.yaml`


# Criteria

以下のDirectoryから、
Policyで指定されたすべてのCriterionを読み込んでください。

`.github/skills/quality-review/criteria/`

Criterionの追加・削除によって
Review観点を変更できる構造とします。


# Output

以下を生成してください。

`reports/quality-review/quality-review-report.json`

`reports/quality-review/quality-review-report.md`


# Procedure

## Step 1. Audit Scopeを確認する

以下のいずれかを取得してください。

- REQUIREMENTS
- ARCHITECTURE
- IMPLEMENTATION
- UNIT_TEST
- INTEGRATION_TEST
- FULL


## Step 2. Policyを読み込む

`quality-review-policy.yaml`

を読み込みます。


## Step 3. Criteriaを読み込む

Policyで指定されたPatternに一致する
Criterionをすべて読み込んでください。


## Step 4. Requirementsを読み込む

以下を読み込んでください。

`docs/requirements/requirements.md`

`docs/requirements/features/`

Requirementsを
Expected BehaviorのSource of Truthとして扱います。


## Step 5. Requirements Qualityを評価する

ScopeがREQUIREMENTS以上の場合、
Requirements Criterionを評価してください。


## Step 6. ADRを読み込む

`docs/adr/`

からScopeに応じてADRを取得してください。

`audit_scope=ARCHITECTURE`の場合は、
Acceptance候補となるProposed ADRを
Architecture Qualityの監査対象として扱ってください。

既存のAccepted ADRが存在する場合は、
Acceptance候補のProposed ADRとの
矛盾・重複・整合性も確認してください。

`audit_scope=IMPLEMENTATION`、
`UNIT_TEST`、
`INTEGRATION_TEST`、
`FULL`
の場合は、
Accepted ADRのみを
現在有効なArchitecture Decisionとして扱ってください。

Superseded ADRを
現在有効なDecisionとして扱ってはいけません。


## Step 7. Architecture Qualityを評価する

ScopeがARCHITECTURE以上の場合、
Architecture Criterionを評価してください。


## Step 8. Production Codeを確認する

ScopeがIMPLEMENTATION以上の場合、
Production Codeを読み込んでください。


## Step 9. Implementation Qualityを評価する

Requirementと、
現在のScopeで有効なADRに対して、
実装内容が意味的に妥当か確認してください。

Implementation以降では、
Accepted ADRのみを使用してください。


## Step 10. Unit Testを確認する

ScopeがUNIT_TEST以上の場合、
Unit Test CodeとEvidenceを読み込んでください。


## Step 11. Unit Test Qualityを評価する

Expected Result、
Assertion、
Boundary、
Invalid、
Exception、
Dependency Isolation等を確認します。


## Step 12. Integration Testを確認する

ScopeがINTEGRATION_TEST以上の場合、
Integration Test Case、Code、Evidenceを読み込んでください。


## Step 13. Integration Test Qualityを評価する

Integration Point、
Business Flow、
Error Propagation、
State Transition、
AI INITIAL / GAP_FILL / EXTERNALの意味的妥当性を確認します。


## Step 14. Cross Phase Consistencyを確認する

現在のScopeまでについて、

Requirements
→ ADR
→ Implementation
→ Test

の意味が変化していないか確認してください。


## Step 15. Expected BehaviorのSourceを確認する

Test Expected Resultを
Production Codeから導出していないか確認してください。

Expected Resultは
Requirementsおよび現在のScopeで有効なADRから導出してください。


## Step 16. Scope Expansionを確認する

Requirementや現在のScopeで有効なADRに根拠のない
機能追加・Technology追加・Behavior追加がないか確認してください。


## Step 17. Complexityを確認する

Requirementを満たすために必要なComplexityか確認してください。

明確な理由のない
Over-engineeringをIssueとしてください。


## Step 18. Criteria Resultを決定する

各Criterionを、

- PASS
- NOT_APPLICABLE
- FAIL

のいずれかで評価してください。

NOT_APPLICABLEの場合は
理由を必須としてください。


## Step 19. Issueを作成する

FAILまたは品質上の問題を検出した場合、
Issueを作成してください。


## Step 20. Root Causeを特定する

問題が検出された工程ではなく、
問題が最初に作られた工程を特定してください。


## Step 21. Recommended Routeを決定する

Root Causeに応じて、

- REQUIREMENTS
- ARCHITECTURE
- IMPLEMENTATION
- UNIT_TEST
- INTEGRATION_TEST

を指定してください。


## Step 22. 同一Root Causeを集約する

同一原因による複数Issueは、
必要に応じて集約してください。

影響Artifactは失わないでください。


## Step 23. JSON Reportを生成する

以下へ生成してください。

`reports/quality-review/quality-review-report.json`


## Step 24. Markdown Reportを生成する

以下へ生成してください。

`reports/quality-review/quality-review-report.md`

最低限以下を含めてください。

- Audit Scope
- Criteria Results
- Quality Summary
- Issues
- Evidence
- Recommended Route


## Step 25. Final判定

Policyを使用して判定してください。

Applicable CriterionがFAILの場合、
または未解決Blocking Issueが存在する場合は
PASSとしてはいけません。


# Review Principles

Quality Reviewは
「もっと良くできる」という理由だけで
FAILにしてはいけません。

Requirementを満たしており、
Accepted ADRに従い、
不必要なRiskやComplexityがなく、
TestがBehaviorを十分に確認している場合は
PASSとしてください。


# Do Not Rewrite Requirements

RequirementsのCanonical Structureを
変更提案してはいけません。

Requirement内容自体に問題がある場合のみ
IssueとしてRequirements工程へ返してください。


# Do Not Fix

Issueを発見しても、
このSkill内で成果物を修正してはいけません。

SDLC Orchestratorへ返却してください。


# Completion

以下が完了するまで終了してはいけません。

- Policy読込
- Criteria読込
- Scopeに応じたArtifact確認
- Criteria評価
- Cross Phase確認
- Issue分類
- Root Cause判定
- Recommended Route決定
- JSON Report
- Markdown Report
