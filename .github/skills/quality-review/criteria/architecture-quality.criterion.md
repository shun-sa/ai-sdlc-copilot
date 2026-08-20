# Architecture Quality Criterion

## Purpose

Architecture DecisionがRequirementに対して
妥当かつ必要十分であることを確認する。

## Applies To

- ARCHITECTURE
- IMPLEMENTATION
- UNIT_TEST
- INTEGRATION_TEST
- FULL

## Required Review

以下を確認する。

- ContextとDecisionが整合している
- Related Requirementsを満たす
- Alternativesが実質的な比較になっている
- ConsequencesがDecisionと整合する
- AI Guardrailsが具体的
- Constraintと矛盾しない
- 不必要なTechnology導入がない
- Architectureが過剰に複雑でない
- 重要Decisionが暗黙化されていない

## Pass Conditions

Requirementを満たすために
合理的なArchitecture Decisionとなっている。

不要なComplexityがない。

## Not Applicable

Architecture Decisionが存在しないScopeでは
NOT_APPLICABLE可。

## Failure Handling

Architectureの問題:

`ARCHITECTURE_QUALITY_ISSUE`

不必要な複雑性:

`UNNECESSARY_COMPLEXITY`

## Evidence

- ADR ID
- Related Requirement
- Context
- Decision
- 問題内容
