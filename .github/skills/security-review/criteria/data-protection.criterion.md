# Data Protection Criterion

## Purpose

Sensitive Dataが必要以上に
取得・保持・公開されないことを確認する。

## Applies To

- REQUIREMENTS
- ARCHITECTURE
- IMPLEMENTATION
- UNIT_TEST
- INTEGRATION_TEST
- FULL

## Required Review

以下を確認する。

- Sensitive Dataを必要以上にResponseへ含めない
- Sensitive Dataを必要以上に保持しない
- Error ResponseへSensitive Dataを含めない
- LogへSensitive Dataを含めない
- Production Sensitive DataをTestで使用しない
- Data AccessがAuthorization Boundaryと一致する

## Pass Conditions

MaterialなSensitive Data Exposureがない。

## Not Applicable

Sensitive Dataを扱わない場合は
理由付きNOT_APPLICABLE可。

## Failure Handling

- DATA_PROTECTION_ISSUE
- SENSITIVE_DATA_EXPOSURE

## Evidence

Sensitive Data実値を記録してはいけない。

- Data Type
- Artifact
- Exposure Point
- Risk
