# Exception Criterion

## Purpose

依存処理の失敗や例外発生時に、
対象UnitがRequirementおよびError仕様に従って
正しく処理することを確認する。

例外が握り潰されたり、
正常処理として扱われたりしないことを確認する。

## Applies To

以下を利用するUnitに適用する。

- Repository
- External API Client
- File Access
- Messaging
- Authentication Service
- External Service
- その他失敗可能なDependency

## Required Test Design

対象Unitで発生可能かつ
Requirement上意味を持つException Pathを確認する。

## Dependency Failure

依存先の失敗をMockまたはStubで再現し、
対象Unitの挙動を確認する。

例:

- Repository Error
- External API Error
- Timeout
- Authentication Failure

## Error Propagation

例外を上位へ通知すべき設計の場合、
正しく伝播することを確認する。

## Error Conversion

共通エラー仕様等によって
Error変換が必要な場合は、
期待するErrorへ変換されることを確認する。

## State Integrity

Exception発生時に、
不正な状態変更や部分更新が発生しないことを確認する。

## Resource Handling

対象UnitがResourceを管理する場合、
Exception発生時にも適切に解放されることを確認する。

ただし、
実装詳細に過度に依存したTestは避ける。

## Pass Conditions

以下をすべて満たすこと。

1. Requirement上意味のあるException Pathがテストされている
2. Exceptionが不当に握り潰されない
3. 正常結果として扱われない
4. Error仕様に従った結果になる
5. 不正な状態が残らない

## Not Applicable

対象Unitに失敗可能なDependencyや
Exception Pathが存在しない場合は
NOT_APPLICABLEとできる。

理由を記録する。

## Failure Handling

Production CodeのException Handlingが
RequirementまたはAccepted ADRと異なる場合は
IMPLEMENTATION_ERRORとして扱う。

Error Handling方式自体に
新しい重要設計判断が必要な場合は
ADR_REQUIREDとして扱う。

## Evidence

最低限以下を記録する。

- Requirement ID
- Dependency / Failure
- Expected Behavior
- Actual Behavior
- PASS / FAIL
