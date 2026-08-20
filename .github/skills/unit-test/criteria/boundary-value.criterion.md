# Boundary Value Criterion

## Purpose

Requirementで定義された範囲、上限、下限、桁数、
日時、件数などの境界付近で
正しい処理が行われることを確認する。

境界値は不具合が発生しやすいため、
範囲条件を持つRequirementには原則適用する。

## Applies To

以下のような条件を持つ処理に適用する。

- 数値範囲
- 文字列長
- 配列件数
- 数量
- 金額
- 日付
- 時刻
- 有効期限
- ページサイズ
- 最大登録件数
- 最小登録件数
- 業務上の上限・下限

## Required Test Design

Requirementに境界が定義されている場合、
境界の内側・境界値・境界の外側を確認する。

## Lower Boundary

下限が存在する場合、
意味のある範囲で以下を確認する。

- 下限より小さい値
- 下限値
- 下限より大きい直近の値

## Upper Boundary

上限が存在する場合、
意味のある範囲で以下を確認する。

- 上限より小さい直近の値
- 上限値
- 上限より大きい値

## Length Boundary

文字列やCollectionに長さ制約がある場合、
以下を確認する。

- 最小長
- 最小長付近
- 最大長
- 最大長付近
- 制約外の長さ

## Date and Time Boundary

日時条件については、
Requirementに応じて以下を確認する。

- 境界時刻より前
- 境界時刻
- 境界時刻より後

現在日時に依存する場合は、
Clock等を固定または差し替え可能な方法を使用し、
非決定的なTestにしない。

## Inclusive / Exclusive

境界条件が

- 以上
- 以下
- より大きい
- より小さい

のどれであるかをRequirementから確認する。

Agentの推測でInclusive / Exclusiveを決めてはいけない。

## Example

Requirement:

数量は1〜10の範囲である。

代表的なTest:

- 0 → Error
- 1 → Success
- 2 → Success
- 9 → Success
- 10 → Success
- 11 → Error

ただし、
Requirementに存在しない具体値を
このCriterionから追加してはいけない。

## Pass Conditions

以下をすべて満たすこと。

1. Requirementの境界条件を特定している
2. 境界値そのものをテストしている
3. 境界の内側をテストしている
4. 境界の外側をテストしている
5. Inclusive / Exclusiveの条件がRequirementと一致している

## Not Applicable

対象Requirementに
範囲・長さ・日時等の境界条件が存在しない場合は
NOT_APPLICABLEとできる。

理由を記録する。

## Failure Handling

境界条件でProduction Codeが
Requirementと異なる挙動をした場合は、
IMPLEMENTATION_ERRORとして扱う。

境界条件自体がRequirementから判断できない場合は
REQUIREMENT_ERRORとして扱う。

## Evidence

最低限以下を記録する。

- Requirement ID
- 対象となる境界条件
- Input
- Expected Result
- Actual Result
- PASS / FAIL
