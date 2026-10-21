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

設計書・実装タスク・ADDRの3種を対象とする。ADDRの判断基準、選択肢、決定理由、
DD/INV/ASM、設計種別、旧Accepted ADRとの整合と、Taskの依存・網羅性を確認する。
ADDRが不要な対象であることと、設計書が不要であることを混同しない。
既存cross-artifact-consistency-analysis.template.mdで意味的整合のReportを生成し、
未確定判断・設計差分未反映・Task不足があればArchitecture GateをPASSにしない。

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
