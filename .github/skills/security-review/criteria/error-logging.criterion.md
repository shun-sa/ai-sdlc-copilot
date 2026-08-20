# Error and Logging Security Criterion

## Purpose

Error HandlingおよびLoggingによって
Security情報が不必要に公開されないことを確認する。

## Applies To

- REQUIREMENTS
- ARCHITECTURE
- IMPLEMENTATION
- UNIT_TEST
- INTEGRATION_TEST
- FULL

## Required Review

以下を確認する。

- Internal Error DetailをExternal Responseへ不要に公開しない
- Stack Traceを利用者へ返さない
- SecretをLogへ出力しない
- Sensitive DataをLogへ出力しない
- Security上重要な失敗を正常扱いしない
- 必要なSecurity Eventを追跡できる

## Pass Conditions

Error / LoggingにMaterialなSecurity Riskがない。

## Not Applicable

原則Applicable。

## Failure Handling

`ERROR_LOGGING_SECURITY_ISSUE`

## Evidence

- Error Flow
- File / Symbol
- Response
- Log Behavior
