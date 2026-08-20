# Security Criterion

## Purpose

Unit Testで検証可能な認証・認可・入力制御・
機密情報取扱い等のSecurity Logicが、
RequirementおよびAccepted ADRに従っていることを確認する。

このCriterionは、
Security TestやPenetration Test全体を
Unit Testだけで代替するものではない。

## Applies To

Unit Testで検証可能な以下の処理に適用する。

- Authorization Logic
- Role判定
- Permission判定
- Access Control
- Security Validation
- Sensitive Data Masking
- Token / Claim処理
- Security-related Business Rule

## Required Test Design

RequirementおよびAccepted ADRから
適用可能なSecurity Caseを特定する。

## Authorized Case

許可されたUser / Role / Permissionで
処理が成功することを確認する。

## Unauthorized Case

許可されていないUser / Role / Permissionで
処理が拒否されることを確認する。

## Missing Authentication Context

認証情報が必要な処理について、
認証情報が存在しない場合の挙動を確認する。

## Privilege Boundary

複数RoleまたはPermissionが存在する場合、
権限境界を確認する。

高権限ユーザーだけが可能な操作を
低権限ユーザーが実行できないことを確認する。

## Sensitive Information

機密情報を扱うUtilityやLogicがある場合、
Requirementに従って以下を確認する。

- 不要な情報を返さない
- Maskingが必要ならMaskされる
- Errorへ機密情報を含めない

## Security Guardrails

Accepted ADRのAI Guardrailsに
Security関連制約が存在する場合、
Unit Test可能な範囲でTestへ反映する。

## Test Data

実際のCredential、
API Key、
Production Token、
個人情報等をTest Dataとして使用してはいけない。

架空のTest Dataを使用する。

## Pass Conditions

以下をすべて満たすこと。

1. Unit Test可能なSecurity Requirementを特定している
2. 許可された操作を確認している
3. 禁止された操作を確認している
4. 権限境界が正しく機能している
5. Accepted ADRのSecurity Guardrailに反していない

## Not Applicable

Security Requirementが存在しても、
その検証がIntegration Test、
Security Test等でのみ可能な場合は
NOT_APPLICABLEとできる。

その場合は理由と
後続で検証すべき内容を記録する。

## Failure Handling

認証・認可等のProduction Logicが
Requirementと異なる場合は
IMPLEMENTATION_ERRORとして扱う。

Security方式そのものの判断が不足している場合は
ADR_REQUIREDとして扱う。

## Evidence

最低限以下を記録する。

- Requirement ID
- Related ADR
- Security Case
- Expected Result
- Actual Result
- PASS / FAIL
