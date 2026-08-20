# Security Test Coverage Criterion

## Purpose

ApplicableなSecurity Behaviorが
Unit TestまたはIntegration Testで
実際に検証されていることを確認する。

## Applies To

- UNIT_TEST
- INTEGRATION_TEST
- FULL

## Required Review

SystemにApplicableな以下を確認する。

- Authentication Failure
- Unauthorized Access
- Forbidden Access
- Invalid Input
- Injection-resistant Behavior
- Sensitive Data Exposure防止
- Error Response
- Secret非露出

すべてを一律必須としてはいけない。

## Expected Result

Expected Resultは、

Requirements
および
Accepted ADR

から導出する。

Production Codeの現在動作から
Expected Resultを導出してはいけない。

## Pass Conditions

ApplicableなSecurity Behaviorについて
MaterialなTest Gapがない。

## Not Applicable

Security Test対象Behaviorがない場合のみ
理由付きNOT_APPLICABLE可。

## Failure Handling

`SECURITY_TEST_GAP`

## Evidence

- Requirement
- Security Behavior
- Unit Test
- Integration Test
- Missing Test
