# Error Handling Integration Criterion

## Purpose

複数Componentの連携途中でErrorが発生した場合に、
Requirementおよび共通Error仕様に従って
適切に処理・伝播されることを確認する。

## Applies To

以下のような処理に適用する。

- API Error
- Database Error
- External Service Error
- Authentication Error
- Validation Error
- Timeout
- Dependency Failure
- Transaction Failure

## Required Test Design

Requirement上意味を持つFailureについて、
連携全体としての挙動を確認する。

## Error Propagation

下位Componentで発生したErrorが
必要な上位Componentへ正しく伝播することを確認する。

## Error Conversion

内部Errorを
共通Error仕様へ変換する必要がある場合は
正しく変換されることを確認する。

## Error Response

外部へ返却するErrorについて
必要に応じて以下を確認する。

- Status
- Error Code
- Message
- Trace ID等の識別情報

## Sensitive Information

Error Responseに
内部実装情報、Credential、
Stack Trace等の不要な機密情報が
含まれないことを確認する。

## State Integrity

連携途中でFailureした場合に
不正な中間状態が残らないことを確認する。

## Pass Conditions

以下をすべて満たすこと。

1. 必要なFailure Pathを確認している
2. Errorが握り潰されていない
3. Errorが正しく伝播または変換される
4. Error Responseが仕様と一致する
5. 不要な機密情報を外部へ返さない
6. 不正な中間状態が残らない

## Not Applicable

対象連携に
Requirement上確認すべきError Pathが存在しない場合は
NOT_APPLICABLEとできる。

理由を記録する。

## Failure Handling

Error Handling実装の不具合は
IMPLEMENTATION_ERRORとして扱う。

Error方式自体の判断不足は
ADR_REQUIREDとして扱う。

## Evidence

最低限以下を記録する。

- Requirement ID
- Case ID
- Origin
- Failure Point
- Expected Error
- Actual Error
- PASS / FAIL
