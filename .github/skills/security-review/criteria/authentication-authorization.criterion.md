# Authentication and Authorization Criterion

## Purpose

Protected ResourceへのAccessが
RequirementsおよびArchitectureに従って
適切に認証・認可されていることを確認する。

## Applies To

- REQUIREMENTS
- ARCHITECTURE
- IMPLEMENTATION
- UNIT_TEST
- INTEGRATION_TEST
- FULL

## Required Review

以下を確認する。

- Authentication Requirementが明確
- Protected ResourceがAuthenticationなしで利用できない
- Authentication Failureが適切
- AuthenticationとAuthorizationを混同していない
- Resource Access前にAuthorizationされる
- 他User ResourceへのUnauthorized Accessを防止する
- Role / Permission BoundaryがRequirementと一致する
- Deny Behaviorが必要に応じてTestされている

## Pass Conditions

ApplicableなAuthentication / Authorization Boundaryに
Materialな欠落がない。

## Not Applicable

Authentication / Authorizationを必要としないSystemの場合は
理由付きNOT_APPLICABLE可。

## Failure Handling

- AUTHENTICATION_ISSUE
- AUTHORIZATION_ISSUE

## Evidence

- Requirement
- ADR
- File / Symbol
- Test Case
- 問題となるAccess Flow
