# Integration Test Quality Criterion

## Purpose

Integration Testが、
実際のComponent間連携およびBusiness Behaviorを
Requirementに基づいて検証していることを確認する。

## Applies To

- INTEGRATION_TEST
- FULL

## Required Review

以下を確認する。

- 実際のIntegration PointをTestしている
- Component間のData伝播を確認している
- 必要なError Propagationを確認している
- 必要なTransactionを確認している
- 必要なState Transitionを確認している
- Business FlowがRequirementと一致する
- Expected ResultがRequirement / ADR由来
- AI INITIALがExternal Caseから独立している
- GAP_FILLがINITIALと区別されている
- External Caseの意味を変更していない
- Required CoverageにMaterialな抜けがない

## Pass Conditions

Requirementで必要なIntegration Behaviorが
意味的に十分検証されている。

## Not Applicable

Integration Test対象外Requirementについては
理由付きNOT_APPLICABLE可。

## Failure Handling

Integration Test品質問題:

`INTEGRATION_TEST_QUALITY_ISSUE`

Behavior不足:

`MISSING_BEHAVIOR_COVERAGE`

Expected Result不一致:

`EXPECTED_BEHAVIOR_MISMATCH`

## Evidence

- Requirement
- Integration Point
- Case ID
- Origin
- Generation Stage
- Expected Result
- Missing Behavior
