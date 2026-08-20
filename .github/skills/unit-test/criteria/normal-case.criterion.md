# Normal Case Criterion

## Purpose

要件で定義された正常な入力・状態に対して、
対象Unitが期待された結果を返すことを確認する。

正常系テストは、
Production Codeの現在の動作ではなく、
RequirementおよびAccepted ADRに定義された
期待動作を基準として作成する。

## Applies To

以下のような単体テスト可能な処理に適用する。

- 業務ロジック
- Service
- Domain Logic
- Function
- Method
- Component Logic
- Validation Logic
- Authorization Logic
- Data Mapping
- Repository / DAO

## Required Test Design

対象Requirementで定義された正常な利用方法について、
代表的な正常ケースを作成する。

最低限以下を確認する。

### Input

Requirementで許可された正常な入力を使用する。

複数の正常パターンで挙動が変わる場合は、
各パターンをテストする。

### Output

Requirementで定義された期待結果を確認する。

確認対象の例:

- 戻り値
- Response Object
- Domain Object
- 状態
- DB保存内容
- 呼び出された依存処理

### State Change

処理によって状態が変化する場合は、
期待する状態へ変更されていることを確認する。

### Interaction

外部依存をMockまたはStubしている場合、
Requirement上意味のあるInteractionについて確認する。

例:

- Repositoryが呼び出された
- 必要な引数が渡された
- 不要な処理が呼び出されていない

実装詳細に過度に依存したInteraction Testは避ける。

## Pass Conditions

以下をすべて満たすこと。

1. Requirementで定義された代表的な正常ケースがテストされている
2. 実際の結果が期待結果と一致している
3. 必要な状態変化が正しく行われている
4. Requirement上必要な副作用が正しく発生している
5. Testが安定して再実行可能である

## Not Applicable

正常な処理結果を持たないUnitの場合のみ
NOT_APPLICABLEとできる。

NOT_APPLICABLEとする場合は、
理由を記録する。

## Failure Handling

期待結果と実際の結果が異なる場合、
原因を以下へ分類する。

- TEST_ERROR
- IMPLEMENTATION_ERROR
- ADR_REQUIRED
- REQUIREMENT_ERROR
- ENVIRONMENT_ERROR

Production CodeがRequirementを満たしていない場合は
IMPLEMENTATION_ERRORとして扱う。

## Evidence

Test結果には最低限以下を記録する。

- Requirement ID
- Related ADR
- Test File
- Test Case
- Expected Result
- Actual Result
- PASS / FAIL
