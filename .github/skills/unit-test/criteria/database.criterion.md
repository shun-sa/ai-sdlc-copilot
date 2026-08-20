# Database Criterion

## Purpose

DBを利用するProduction Codeについて、
対象レイヤーに応じて適切なTest Strategyを選択し、
DBアクセスおよびDB固有動作が正しく機能することを確認する。

Production DBや共有DBへの依存を禁止し、
再現可能で独立したUnit Testを実現する。

## Applies To

DBを利用する以下の処理に適用する。

- Repository
- DAO
- Persistence Adapter
- Service
- Domain Service
- Transaction Logic
- Data Mapping

## Strategy Selection

DB Test Strategyは
`unit-test-policy.yaml` を正とする。

原則として以下の考え方を使用する。

## Service / Domain

DBそのものの動作を確認する必要がない場合、
Repository等をMockまたはStubする。

確認対象:

- Repositoryへ正しい値を渡している
- Repository結果を正しく処理している
- Repository Errorを正しく扱っている

Service Testから
実DBへ不要に接続しない。

## Repository / DAO

以下を確認する必要がある場合は、
Dockerコンテナ等のDisposable Databaseを利用する。

- SQL
- ORM Mapping
- Database Constraint
- Transaction
- Persistence
- DB固有Query
- Schemaとの整合性

## Container Database Requirements

Container DBを使用する場合は、
以下を満たすこと。

- Production DBではない
- Shared DBではない
- Production Credentialを利用しない
- TestごとまたはTest Suiteごとに独立できる
- Schemaを再現できる
- Test Dataを独立して投入できる
- Test終了後に破棄可能である

## Schema

Productionで使用するSchemaまたはMigrationを
テストDBへ適用できることを確認する。

Productionとは異なる簡易Schemaを
Testだけの都合で独自作成してはいけない。

## CRUD Behavior

対象Repositoryが提供する操作について、
Requirementおよび実装責務に応じて確認する。

例:

- Create
- Read
- Update
- Delete

すべてのRepositoryで
機械的にCRUD全部を要求するわけではない。

## Mapping

DB RecordとDomain / Entity / DTO間のMappingを
確認する。

確認例:

- Data Type
- Nullable
- Date / Time
- Enum
- Identifier
- Optional Value

## Constraints

DB Constraintが仕様上重要な場合、
実DBコンテナを使用して確認する。

例:

- NOT NULL
- UNIQUE
- Foreign Key
- Length
- Check Constraint

## Transaction

TransactionがRequirementまたはAccepted ADR上
重要である場合、
成功時および失敗時の状態を確認する。

失敗時に部分的なデータが残らないことを
必要に応じて確認する。

## Data Isolation

各Testは、
他Testによって作成されたDB状態へ依存してはいけない。

Testの実行順序を変更しても
結果が変わらない状態にする。

## Test Data

必要なTest Dataは、
Test自身または共通Fixtureから投入する。

以下へ依存してはいけない。

- Production Data
- 手動投入済みデータ
- 特定の固定Record
- 前に実行されたTestのデータ

## Pass Conditions

以下をすべて満たすこと。

1. 対象レイヤーに適切なDB Test Strategyを使用している
2. Production DBを使用していない
3. Shared DBへ依存していない
4. Repository / DAOで必要なDB固有動作を確認している
5. Test Dataが独立している
6. Test実行順序へ依存しない
7. Schemaを再現可能である
8. 全DB Testが再実行可能である

## Not Applicable

対象UnitがDBを一切使用しない場合は
NOT_APPLICABLEとする。

## Failure Handling

Service等がTest DBへ不要に密結合している場合は、
IMPLEMENTATION_ERRORとして扱う。

Container DBへ接続できないProduction Code構造の場合も、
IMPLEMENTATION_ERRORとして扱う。

DB方式、Migration方式等について
重要なArchitecture Decisionが不足している場合は
ADR_REQUIREDとして扱う。

## Evidence

最低限以下を記録する。

- Requirement ID
- Test Target
- Strategy
  - MOCK
  - CONTAINER
- Database Type
- Test File
- Test Case
- PASS / FAIL
