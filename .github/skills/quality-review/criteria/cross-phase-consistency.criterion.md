# Cross Phase Consistency Criterion

## Purpose

SDLC工程を進む過程で、
Requirementの意味や期待Behaviorが
変質していないことを確認する。

## Applies To

- ARCHITECTURE
- IMPLEMENTATION
- UNIT_TEST
- INTEGRATION_TEST
- FULL

## Required Review

以下を意味的に比較する。

Requirements
→ Accepted ADR
→ Implementation
→ Unit Test
→ Integration Test

以下を確認する。

- RequirementとADRが矛盾しない
- ADRとImplementationが矛盾しない
- RequirementとImplementationが矛盾しない
- RequirementとUnit Test Expected Resultが矛盾しない
- RequirementとIntegration Test Expected Resultが矛盾しない
- Unit TestとIntegration Testで同一Behaviorの期待値が矛盾しない

## Example

Requirement:

数量は1〜10

Implementation:

1〜20を許可

Unit Test:

20を正常扱い

この場合、
ID上Traceabilityが成立していてもFAIL。

## Pass Conditions

対象ScopeまでのArtifactで、
同一Behaviorの意味が一貫している。

## Not Applicable

REQUIREMENTS単独ScopeではNOT_APPLICABLE。

## Failure Handling

`CROSS_PHASE_CONSISTENCY_ISSUE`

Recommended Routeは、
矛盾を最初に発生させた
最上流工程とする。

## Evidence

- Requirement
- ADR
- Implementation
- Test
- 各Artifactの期待Behavior
- Root Cause
