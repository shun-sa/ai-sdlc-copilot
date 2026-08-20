# Authentication and Authorization Integration Criterion

## Purpose

認証・認可機構とApplication機能の連携が
RequirementおよびAccepted ADRに従って
正しく機能することを確認する。

## Applies To

以下に適用する。

- Login
- Authentication
- Authorization
- Role
- Permission
- Token
- Session
- Claim
- Protected API
- Protected Function

## Required Test Design

Requirementで定義された
User、Role、Permission等について
必要な連携ケースを確認する。

## Authenticated Access

認証済みユーザーが、
許可された機能を利用できることを確認する。

## Unauthenticated Access

認証が必要な機能について、
未認証ユーザーが利用できないことを確認する。

## Authorized Access

必要な権限を持つユーザーが
対象機能を利用できることを確認する。

## Unauthorized Access

権限を持たないユーザーが
対象機能を利用できないことを確認する。

## Authentication Context Propagation

認証情報が複数Component間で
正しく伝播することを確認する。

例:

Authentication
→ API
→ Service
→ Authorization

## Security Error

認証・認可Failure時に、
Requirementで定義されたErrorが返されることを確認する。

## Pass Conditions

以下をすべて満たすこと。

1. 認証済みAccessが正しく動作する
2. 未認証Accessが正しく拒否される
3. 許可された操作が実行できる
4. 禁止された操作が拒否される
5. 認証情報が必要なComponentまで正しく伝達される
6. Security ErrorがRequirementと一致する

## Not Applicable

対象Requirementに認証・認可が関係しない場合は
NOT_APPLICABLEとできる。

理由を記録する。

## Failure Handling

認証・認可実装に問題がある場合は
IMPLEMENTATION_ERRORとして扱う。

認証・認可方式の設計判断不足は
ADR_REQUIREDとして扱う。

## Evidence

最低限以下を記録する。

- Requirement ID
- Related ADR
- Case ID
- Origin
- User / Role / Permission
- Expected Result
- Actual Result
- PASS / FAIL
