# Requirements Quality Criterion

## Purpose

Requirementsが、
後続工程で一貫した解釈と検証が可能な品質か確認する。

## Applies To

- REQUIREMENTS
- ARCHITECTURE
- IMPLEMENTATION
- UNIT_TEST
- INTEGRATION_TEST
- FULL

## Required Review

以下を確認する。

- Materialな曖昧性がない
- Requirement同士が矛盾していない
- Acceptance Criteriaと矛盾していない
- Out of Scopeと矛盾していない
- 入力・出力・Error Behaviorが必要十分
- Test可能なBehaviorとして記述されている
- 不必要にImplementation Detailへ踏み込んでいない
- Global RequirementとFRが矛盾していない

## Pass Conditions

Materialな曖昧性・矛盾・欠落がない。

後続工程がRequirementを
追加解釈せずBehaviorを導出できる。

## Not Applicable

原則としてREQUIREMENTS以降はApplicable。

## Failure Handling

Requirement自体に問題がある場合:

`REQUIREMENT_QUALITY_ISSUE`

Route:

`REQUIREMENTS`

## Evidence

- Requirement Reference
- 問題箇所
- 矛盾対象
- 影響する後続Artifact
