# API Integration Criterion

## Purpose

複数のComponent間を接続するAPIについて、
RequestからResponseまでの連携が
RequirementおよびAccepted ADRに従って
正しく機能することを確認する。

## Applies To

以下のような連携に適用する。

- Frontend → Backend API
- API Gateway → Application
- Controller → Service
- Service間API
- REST API
- GraphQL API
- その他システム内部または外部API

## Required Test Design

対象APIについて、
Requirementに基づいて必要な連携を確認する。

## Normal Request

正常なRequestについて確認する。

最低限必要に応じて以下を確認する。

- Request受付
- Parameter受け渡し
- Business Logic実行
- Response
- HTTP Status
- Response Body

## Invalid Request

不正Requestについて確認する。

例:

- 必須項目不足
- 不正形式
- 不正値
- 不正な組み合わせ

## Response Contract

RequirementまたはAccepted ADRで定義された
Response Contractを確認する。

確認例:

- Status
- Response項目
- Data Type
- Nullability
- Error Structure

## Component Integration

API入口だけでなく、
必要な内部Componentまで正しく連携していることを確認する。

## Pass Conditions

以下をすべて満たすこと。

1. Requirement上必要なAPI連携を確認している
2. 正常Requestが期待結果になる
3. 必要な異常Requestを確認している
4. Response Contractが正しい
5. Component間の値の受け渡しが正しい
6. Error時の結果がRequirementと一致する

## Not Applicable

対象RequirementにAPI連携が存在しない場合は
NOT_APPLICABLEとできる。

理由を記録する。

## Failure Handling

API連携のProduction Codeに問題がある場合は
IMPLEMENTATION_ERRORとして扱う。

API方式そのもののArchitecture Decisionが不足している場合は
ADR_REQUIREDとして扱う。

## Evidence

最低限以下を記録する。

- Requirement ID
- Related ADR
- Case ID
- Origin
- API
- Request
- Expected Response
- Actual Response
- PASS / FAIL
