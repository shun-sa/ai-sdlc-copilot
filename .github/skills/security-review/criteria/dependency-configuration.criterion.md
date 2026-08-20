# Dependency and Configuration Security Criterion

## Purpose

Dependency利用およびConfigurationによって
Security Controlが弱体化していないことを確認する。

## Applies To

- ARCHITECTURE
- IMPLEMENTATION
- UNIT_TEST
- INTEGRATION_TEST
- FULL

## Required Review

以下を確認する。

- Production Security Controlを無効化していない
- Debug Security Bypassが残っていない
- Test用BypassがProductionへ混入していない
- Environment依存Security設定が不適切にHard Codeされていない
- Dependency利用がADRと矛盾しない

## Pass Conditions

MaterialなSecurity Configuration Riskがない。

## Not Applicable

対象Configuration / Dependencyがない場合は
理由付きNOT_APPLICABLE可。

## Failure Handling

`DEPENDENCY_CONFIGURATION_ISSUE`

## Evidence

- Configuration
- Dependency
- File
- Risk
