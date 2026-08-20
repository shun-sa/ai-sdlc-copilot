# Implementation Quality Criterion

## Purpose

Production CodeがRequirementsおよびAccepted ADRを
必要十分な形で実装していることを確認する。

## Applies To

- IMPLEMENTATION
- UNIT_TEST
- INTEGRATION_TEST
- FULL

## Required Review

以下を確認する。

- Requirement Behaviorを実装している
- Accepted ADRを遵守している
- Out of Scopeを実装していない
- 不要なAbstractionがない
- 不要なGeneralizationがない
- 責務が不自然に混在していない
- Error BehaviorがRequirementと一致する
- State変更がRequirementと一致する
- DB CodeがTest可能
- Environment依存を不必要にHard Codeしていない
- TestのためにProduction Behaviorを変更していない

## Pass Conditions

RequirementとADRを満たし、
不要なScope ExpansionやComplexityがない。

## Not Applicable

IMPLEMENTATIONより前のScope。

## Failure Handling

Implementation問題:

`IMPLEMENTATION_QUALITY_ISSUE`

Scope追加:

`SCOPE_EXPANSION`

過剰設計:

`UNNECESSARY_COMPLEXITY`

## Evidence

- Requirement Reference
- ADR
- File
- Symbol
- 問題内容
