# Cross Phase Security Consistency Criterion

## Purpose

Security BehaviorがSDLC工程を進む過程で
変質していないことを確認する。

## Applies To

- ARCHITECTURE
- IMPLEMENTATION
- UNIT_TEST
- INTEGRATION_TEST
- FULL

## Required Review

以下を比較する。

Requirements
→ Accepted ADR
→ Implementation
→ Unit Test
→ Integration Test

以下を確認する。

- Authentication Behaviorが一貫している
- Authorization Boundaryが一貫している
- Error Behaviorが一貫している
- Sensitive Data Handlingが一貫している
- Security Test Expected ResultがRequirementと一致する

## Example

Requirement:

一般Userは管理機能を利用不可

Implementation:

Authentication済みなら利用可能

Unit Test:

一般UserのAccessを正常扱い

この場合はFAIL。

## Pass Conditions

対象ScopeまでのSecurity Behaviorに
Materialな矛盾がない。

## Not Applicable

REQUIREMENTS単独Scopeでは
NOT_APPLICABLE。

## Failure Handling

`CROSS_PHASE_SECURITY_CONSISTENCY_ISSUE`

Recommended Routeは
Root Causeとなる最上流工程とする。

## Evidence

- Requirement
- ADR
- Implementation
- Test
- Security Behavior差分
- Root Cause
