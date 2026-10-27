# Architecture Quality Criterion

## Purpose

Architecture DecisionがRequirementに対して
妥当かつ必要十分であることを確認する。

## Applies To

- ARCHITECTURE
- ADDR
- IMPLEMENTATION
- UNIT_TEST
- INTEGRATION_TEST
- FULL

## Required Review

設計書・実装タスク・ADDRの3種を対象とする。ADDRの判断基準、選択肢、決定理由、
DD/INV/ASM、設計種別、旧Accepted ADRとの整合と、Taskの依存・網羅性を確認する。
ADDRが不要な対象であることと、設計書が不要であることを混同しない。
DB管理データがある対象はArchitectureの論理DB設計書を確認し、対象外なら根拠を確認する。
Entity/属性/識別子/関連・多重度/論理制約/正規化結果とデータ要件・UC/AC・Taskの整合を検査する。
ADDRへのモデル定義の重複、Architectureによる重要判断の先取り、物理型・DDL等の論理設計への混入がないことを確認する。
Architectureが作成したcross-artifact-consistency分析を読取り、独立した所見をQuality Reportへ記録する。
ARCHITECTUREはADDR引渡し品質、ADDRは判断と設計資料/Taskの最終整合を検査する。
本文修正が必要な不整合はArchitecture、判断の不備はADDRへ戻す。未解決を品質PASSにしない。

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

重要判断/ADDRの問題:

`ADDR_QUALITY_ISSUE`（Route: ADDR）

不必要な複雑性:

`UNNECESSARY_COMPLEXITY`

## Evidence

- ADR ID
- Related Requirement
- Context
- Decision
- 問題内容
