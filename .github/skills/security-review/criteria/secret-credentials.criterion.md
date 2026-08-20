# Secrets and Credentials Criterion

## Purpose

SecretおよびCredentialが
安全に管理されていることを確認する。

## Applies To

- ARCHITECTURE
- IMPLEMENTATION
- UNIT_TEST
- INTEGRATION_TEST
- FULL

## Required Review

以下を確認する。

- Hard-coded Secretがない
- RepositoryにCredentialを保存していない
- Production CredentialをTestで使用していない
- SecretをLogへ出力していない
- SecretをError Responseへ返していない
- Secret取得方法がADR / Constraintと矛盾しない

## Pass Conditions

SecretまたはCredentialの
MaterialなExposure Riskがない。

## Not Applicable

Secret / Credentialを扱わない場合は
理由付きNOT_APPLICABLE可。

## Failure Handling

`SECRET_MANAGEMENT_ISSUE`

## Evidence

Secret値そのものを記録してはいけない。

以下のみ記録する。

- File
- Line / Symbol
- Secret種別
- Risk
