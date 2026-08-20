# Invalid Input Criterion

## Purpose

Requirementで許可されていない入力、
不正形式、欠落値、不正な組み合わせに対して、
対象Unitが正しく拒否またはエラー処理することを確認する。

## Applies To

入力を受け取る単体テスト可能な処理に適用する。

例:

- API入力を扱うLogic
- Service
- Domain Object
- Validator
- Form Logic
- Command
- DTO変換
- Data Mapping

## Required Test Design

Requirementに基づき、
適用可能な不正入力を確認する。

## Missing Required Value

必須項目について、
技術的に入力可能な場合は以下を確認する。

- null
- undefined
- 項目欠落

使用言語・Frameworkによって
発生し得ないケースを無理に作らない。

## Empty Value

空値が禁止されている場合、
以下を必要に応じて確認する。

- 空文字
- 空Collection
- 空白のみ

## Invalid Format

形式が定義されている場合、
不正形式を確認する。

例:

- 不正な日付形式
- 不正なメール形式
- 不正なID形式
- 不正なEnum値

## Invalid Combination

個別項目は正常でも、
組み合わせとして禁止される入力がある場合は
その組み合わせをテストする。

## Business Rule Violation

Requirementで禁止されている業務条件を
不正入力として確認する。

例:

- 過去日時の指定
- 許可されていない状態からの操作
- 上限を超える数量

## Expected Behavior

不正入力時の期待結果は
Requirementおよび共通エラー仕様から決定する。

例:

- Validation Error
- Domain Error
- 処理拒否
- 状態変更なし

Agent独自のErrorを期待結果として追加してはいけない。

## Pass Conditions

以下をすべて満たすこと。

1. Requirement上禁止された入力を特定している
2. 適用可能な不正入力Testが存在する
3. 不正入力が正常処理されない
4. Requirementで定義されたErrorとなる
5. 不正入力によって不正な状態変更が発生しない

## Not Applicable

外部入力を一切受け取らず、
不正入力という概念が存在しないUnitでは
NOT_APPLICABLEとできる。

理由を記録する。

## Failure Handling

Requirementで禁止された入力が
正常処理された場合は
IMPLEMENTATION_ERRORとして扱う。

期待するErrorがRequirementから判断できない場合は
REQUIREMENT_ERRORとして扱う。

## Evidence

最低限以下を記録する。

- Requirement ID
- Invalid Input
- Expected Error / Behavior
- Actual Result
- PASS / FAIL
