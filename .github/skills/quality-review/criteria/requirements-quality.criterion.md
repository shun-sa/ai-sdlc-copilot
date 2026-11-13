# Requirements Quality Criterion

## Purpose

Requirementsが、
後続工程で一貫した解釈と検証が可能な品質か確認する。

## Applies To

- REQUIREMENTS
- ARCHITECTURE
- ADDR
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
- QC-015に沿い、物理名・API物理仕様、製品や言語の選定、物理DBや排他方式、画面配置・UI部品、インフラ構成・設定値、テストツールやコマンドが要件に混入していない。顧客・外部契約等の指定がある場合は、テンプレートが許す欄に根拠を付けている
- QC-024に沿い、各文書の記載範囲を守っている。機能権限は機能要件、画面固有の表示条件は画面要件、運用ログは非機能要件に記載し、重複箇所は正本への参照またはテンプレートが求める値の一致を確認する
- UCのフロー・合否条件・Evidenceが利用者や連携先から観測でき、内部処理やAPI・DBの物理仕様に依存していない
- 関連Requirement IDの「未決」は確認事項に登録され、影響が明確になっている。設計へ委ねた事項は確定済みの要求に基づいている
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
