# Database Integration Criterion

## Purpose

ApplicationとDatabaseの連携について、
Data Persistence、Query、Transaction、
Constraint等がRequirementおよびAccepted ADRに従って
正しく動作することを確認する。

## Applies To

以下のようなDB連携に適用する。

- Application → Database
- Service → Repository → Database
- ORM → Database
- Transaction
- Database Constraint
- 複数Table間連携

## Required Test Design

実際のDB動作を確認する必要がある結合試験では、
Docker Container等のDisposable Databaseを使用する。

## Persistence

登録・更新等によって
期待するDataがDatabaseへ保存されることを確認する。

## Retrieval

保存されたDataを
期待する条件で取得できることを確認する。

## Data Mapping

以下のMappingを必要に応じて確認する。

- Entity
- Domain Object
- DTO
- Database Record

## Constraints

Requirement上意味を持つDatabase Constraintを確認する。

例:

- NOT NULL
- UNIQUE
- Foreign Key
- Check Constraint

## Transaction

Transactionが必要な処理について、
成功時・失敗時の状態を確認する。

Failure時に部分更新が残らないことを
必要に応じて確認する。

## Data Isolation

Test Case間でData状態が不当に共有されないことを確認する。

Test実行順序によって結果が変わってはいけない。

## Test Database

以下を禁止する。

- Production Database
- Shared Databaseへの依存
- Production Credential
- Production Data
- 手動投入済みDataへの依存

## Pass Conditions

以下をすべて満たすこと。

1. ApplicationとDatabaseの連携が成功する
2. 保存内容が期待結果と一致する
3. 取得内容が期待結果と一致する
4. 必要なConstraintが機能する
5. 必要なTransactionが機能する
6. Test Dataが独立している
7. Production Databaseを利用していない

## Not Applicable

対象RequirementがDatabaseを使用しない場合は
NOT_APPLICABLEとする。

## Failure Handling

ApplicationまたはPersistence実装に問題がある場合は
IMPLEMENTATION_ERRORとして扱う。

DB方式やTransaction方式等の設計判断が不足している場合は
ADR_REQUIREDとして扱う。

## Evidence

最低限以下を記録する。

- Requirement ID
- Case ID
- Origin
- Database Type
- Target Table / Entity
- Expected Result
- Actual Result
- PASS / FAIL
