---
name: security-review
description: >
  Requirements、Architecture Decision、Production Code、
  Unit Test、Integration Testを対象として、
  Authentication、Authorization、Secret管理、
  Input Validation、Injection、Data Protection、
  Error/Logging、Configuration、Security Testの
  意味的Security品質を独立監査するSkill。
user-invocable: false
disable-model-invocation: false
---

# Purpose

このSkillは、
SDLC成果物のSecurity品質を
独立監査するために使用します。

成果物を修正するSkillではありません。


# Policy

以下を唯一の合否基準として使用してください。

`.github/skills/security-review/policy/security-review-policy.yaml`


# Criteria

以下のDirectoryから
Policyで指定されたCriterionをすべて読み込んでください。

`.github/skills/security-review/criteria/`


# Output

以下を生成してください。

`reports/security-review/security-review-report.json`

`reports/security-review/security-review-report.md`


# Procedure

## Step 1. Audit Scopeを確認する

以下のいずれかを取得してください。

- REQUIREMENTS
- ARCHITECTURE
- IMPLEMENTATION
- UNIT_TEST
- INTEGRATION_TEST
- FULL


## Step 2. Policyを読み込む

以下を読み込んでください。

`.github/skills/security-review/policy/security-review-policy.yaml`


## Step 3. Criteriaを読み込む

PolicyのPatternに一致する
すべてのCriterionを読み込んでください。


## Step 4. Requirementsを読み込む

以下を確認してください。

`docs/requirements/requirements.md`

`docs/requirements/features/`

特にSecurityに関係する、

- 認証・認可
- エラー仕様
- NFR
- Data Model
- FR
- Constraint

を確認してください。


## Step 5. Security Requirement Qualityを確認する

Security上重要なBehaviorについて、
Requirementが矛盾・不足していないか確認してください。

Requirement自体のSecurity問題を検出した場合は、

`SECURITY_REQUIREMENT_ISSUE`

としてください。


## Step 6. ADRを読み込む

`docs/adr/`

からScopeに応じてADRを取得してください。

`audit_scope=ARCHITECTURE`の場合は、
Acceptance候補となるProposed ADRを
Architecture Securityの監査対象として扱ってください。

既存のAccepted ADRが存在する場合は、
Acceptance候補のProposed ADRとの
Security上の矛盾・重複・Guardrail不整合も確認してください。

`audit_scope=IMPLEMENTATION`、
`UNIT_TEST`、
`INTEGRATION_TEST`、
`FULL`
の場合は、
Accepted ADRのみを
現在有効なArchitecture Decisionとして扱ってください。

Superseded ADRを
現在有効なDecisionとして扱ってはいけません。


## Step 7. Architecture Securityを確認する

Authentication、
Authorization、
Data Access、
Secret Management等に関するDecisionが
Requirementと矛盾していないか確認してください。


## Step 8. Production Codeを確認する

ScopeがIMPLEMENTATION以上の場合、
Production CodeおよびConfigurationを確認してください。


## Step 9. Authentication / Authorizationを確認する

Applicableな場合、
AuthenticationとAuthorizationを個別に確認してください。


## Step 10. Secret / Credentialを確認する

Source Code、
Configuration、
Test Code、
Logging等に
SecretやCredentialが露出していないか確認してください。

Secretの実値をReportへ出力してはいけません。


## Step 11. Input Validationを確認する

External InputのTrust Boundaryを確認してください。


## Step 12. Injection Riskを確認する

DB、
Command、
Path、
Template等への入力利用方法を確認してください。


## Step 13. Data Protectionを確認する

Sensitive Dataの
取得、返却、保存、Log、Test利用を確認してください。


## Step 14. Error / Loggingを確認する

Security上危険な情報公開や
Security Eventの誤処理がないか確認してください。


## Step 15. Dependency / Configurationを確認する

Security Controlを弱める設定、
Debug Bypass、
危険なEnvironment依存等を確認してください。


## Step 16. Unit Testを確認する

ScopeがUNIT_TEST以上の場合、
Security BehaviorのUnit Testを確認してください。


## Step 17. Integration Testを確認する

ScopeがINTEGRATION_TEST以上の場合、
Authentication、
Authorization、
Error、
Invalid Input、
Data Access等のIntegration Behaviorを確認してください。


## Step 18. Expected ResultのSourceを確認する

Security TestのExpected Resultは
Production Codeの現在動作ではなく、

Requirements
および
Accepted ADR

から導出してください。


## Step 19. Cross Phase Security Consistencyを確認する

以下を意味的に比較してください。

Requirements
→ Accepted ADR
→ Implementation
→ Unit Test
→ Integration Test


## Step 20. Criteriaを評価する

各Criterionを以下で評価します。

- PASS
- NOT_APPLICABLE
- FAIL

NOT_APPLICABLEの場合は
理由を必須としてください。


## Step 21. Security Issueを作成する

Security問題を検出した場合、
Issueを作成してください。


## Step 22. SecretをEvidenceへ記録しない

Evidenceには、

- File
- LineまたはSymbol
- 問題の種類

を記録できます。

Secret値そのものを
Reportへ記録してはいけません。


## Step 23. Severityを決定する

Security Impactに基づいて、

- CRITICAL
- HIGH
- MEDIUM
- LOW

を指定してください。


## Step 24. Root Causeを特定する

問題を検出した工程ではなく、
問題を最初に作った工程を特定してください。


## Step 25. Recommended Routeを決定する

以下から指定してください。

- REQUIREMENTS
- ARCHITECTURE
- IMPLEMENTATION
- UNIT_TEST
- INTEGRATION_TEST


## Step 26. 同一Root Causeを集約する

同一Security Root CauseによるIssueは
必要に応じて集約してください。

ただし影響Artifactを失わないでください。


## Step 27. JSON Reportを生成する

以下へ生成してください。

`reports/security-review/security-review-report.json`


## Step 28. Markdown Reportを生成する

以下へ生成してください。

`reports/security-review/security-review-report.md`

最低限以下を含めてください。

- Audit Scope
- Criteria Results
- Security Summary
- Issues
- Evidence
- Severity
- Recommended Route


## Step 29. Final判定

Policyを使用して判定してください。

Applicable CriterionがFAIL、
または未解決Blocking Issueが存在する場合は
PASSとしてはいけません。


# Do Not Leak Secrets

Secretを検出した場合でも
値をReportへコピーしてはいけません。

例えば、

悪い例:

`API_KEY=abcd1234...`

良い例:

`src/config.py:12 にHard-coded API Credentialを検出`


# Do Not Fix

Security Issueを検出しても、
このSkill内で成果物を修正してはいけません。

SDLC Orchestratorへ返却してください。


# Completion

以下が完了するまで終了してはいけません。

- Policy読込
- Criteria読込
- Scope Artifact確認
- Authentication / Authorization確認
- Secret / Credential確認
- Input / Injection確認
- Data Protection確認
- Error / Logging確認
- Configuration確認
- Security Test確認
- Cross Phase確認
- Issue分類
- Severity判定
- Recommended Route決定
- JSON Report生成
- Markdown Report生成