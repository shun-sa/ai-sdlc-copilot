---
name: failure-triage
description: >
  同一Root CauseによるFailureが通常の修正・再実行を
  繰り返しても解決しない場合に、
  Failure HistoryとSDLC成果物を分析し、
  Root Cause ClassificationとRecommended Routeを決定するSkill。
  成果物は修正しない。
user-invocable: false
disable-model-invocation: false
---

# Purpose

このSkillは、
SDLCの修正ループが収束しない場合に
Root Causeを診断するために使用します。

このSkillは修正を実施しません。


# Policy

以下を唯一の基準として使用してください。

`.github/skills/failure-triage/policy/failure-triage-policy.yaml`


# Output

以下を生成してください。

`reports/failure-triage/failure-triage-report.json`

`reports/failure-triage/failure-triage-report.md`


# Procedure

## Step 1. Invocation情報を確認する

SDLC Orchestratorから以下を取得してください。

- current_phase
- retry_count
- failure_history
- latest_failure
- previous_routes
- affected_artifacts


## Step 2. Invocation Conditionを確認する

PolicyのRetry Thresholdを確認してください。

Retry CountがThreshold未満の場合は、

`INVALID_INVOCATION`

を返してください。

Failure Triageを通常のFailure Routing代わりに
使用してはいけません。


## Step 3. Direct User Gate Failureを除外する

以下の場合はFailure Triage対象外です。

- EXTERNAL_TEST_INPUT_REQUIRED
- TEST_SPEC_CONFLICT
- AUTOMATION_BLOCKED

これらが入力された場合は、

`INVALID_INVOCATION`

としてSDLC Orchestratorへ返してください。


## Step 4. Failure Historyを時系列化する

以下をAttemptごとに整理してください。

- Failure
- Classification
- Route
- Changed Artifact
- Retry Result


## Step 5. Same Failureか確認する

単に同一Test CaseがFailしているだけではなく、
Root Causeが同じか確認してください。


## Step 6. Failure Signatureを生成する

可能な範囲で以下を使用してください。

- source_phase
- classification
- requirement_reference
- artifact
- error_location
- test_case
- stable_error_type

動的IDはSignatureから除外してください。


## Step 7. Previous Routeを確認する

これまでどの工程へ戻したか確認してください。

同じ工程へ繰り返し戻している場合、
そのRouteがRoot Causeと一致していたか確認します。


## Step 8. Requirementsを確認する

Expected BehaviorがRequirementsから
一意に決定できるか確認してください。


## Step 9. Accepted ADRを確認する

Architecture Decisionが必要な場合、
Accepted ADRを確認してください。


## Step 10. Implementationを確認する

RequirementおよびADRと
Production Codeを比較してください。


## Step 11. Testを確認する

Test Expected Result、
Assertion、
Setup、
Mock、
Test Data等を確認してください。


## Step 12. Environmentを確認する

FailureがEnvironment由来か確認してください。

例:

- Container
- Test DB
- Runtime
- Toolchain
- Dependency
- Network
- Local Configuration


## Step 13. Expected BehaviorとActual Behaviorを比較する

以下を明示してください。

Expected:

Requirements / Accepted ADRから導出

Actual:

Failure Evidenceから確認


## Step 14. 過去修正が失敗した理由を分析する

各Attemptについて、

「何を変更したか」

だけでなく、

「なぜその変更ではRoot Causeを除去できなかったか」

を確認してください。


## Step 15. Root Cause Priorityを適用する

複数工程に問題が現れている場合は、
最上流のRoot Causeを優先してください。


## Step 16. Classificationを決定する

以下から選択してください。

- REQUIREMENT_ERROR
- ADR_REQUIRED
- IMPLEMENTATION_ERROR
- TEST_ERROR
- ENVIRONMENT_ERROR
- CROSS_PHASE_CONFLICT
- UNKNOWN_ROOT_CAUSE


## Step 17. Recommended Routeを決定する

REQUIREMENT_ERROR:

`REQUIREMENTS`

ADR_REQUIRED:

`ARCHITECTURE`

IMPLEMENTATION_ERROR:

`IMPLEMENTATION`

TEST_ERROR:

`UNIT_TEST`

または

`INTEGRATION_TEST`

ENVIRONMENT_ERROR:

`SDLC_ORCHESTRATOR`

CROSS_PHASE_CONFLICT:

Root Cause工程。
決定不能なら`BLOCKED`。

UNKNOWN_ROOT_CAUSE:

`BLOCKED`。


## Step 18. Invalidated Phasesを決定する

修正対象工程から後続工程を
どこまで無効化する必要があるか記録してください。

例:

REQUIREMENTSへ戻る:

- ARCHITECTURE
- IMPLEMENTATION
- UNIT_TEST
- INTEGRATION_TEST

ARCHITECTUREへ戻る:

- IMPLEMENTATION
- UNIT_TEST
- INTEGRATION_TEST

IMPLEMENTATIONへ戻る:

- UNIT_TEST
- INTEGRATION_TEST

UNIT_TESTへ戻る:

- UNIT_TEST

INTEGRATION_TESTへ戻る:

- INTEGRATION_TEST


## Step 19. Recommended Actionを記述する

修正内容そのものを実装してはいけません。

何を再確認・修正すべきかを
診断結果として記述してください。


## Step 20. Evidenceを記録する

最低限以下を記録してください。

- Failure History
- Error Location / Test Case
- Expected Behavior
- Actual Behavior
- Previous Changes
- Root Cause根拠


## Step 21. JSON Reportを生成する

以下へ生成してください。

`reports/failure-triage/failure-triage-report.json`


## Step 22. Markdown Reportを生成する

以下へ生成してください。

`reports/failure-triage/failure-triage-report.md`

最低限以下を含めてください。

- Source Phase
- Retry Count
- Failure Signature
- Failure Timeline
- Previous Attempts
- Expected Behavior
- Actual Behavior
- Root Cause
- Classification
- Recommended Route
- Invalidated Phases
- Recommended Action


## Step 23. Final Statusを決定する

Root CauseとRouteを合理的に決定できた場合:

`TRIAGED`

Evidence不足またはRoot Cause決定不能:

`BLOCKED`

Invocation Conditionを満たしていない:

`INVALID_INVOCATION`


# Important Rule

Failure Triageは、

「3回失敗したから別のAgentを試す」

ための仕組みではありません。

Failure Historyを分析し、
なぜ通常Routingでは解決しなかったかを
説明できなければなりません。


# No Fix

成果物を修正してはいけません。


# No Direct Routing

他Agentを直接起動してはいけません。

SDLC Orchestratorへ診断結果だけを返してください。


# Completion

以下が完了するまで終了してはいけません。

- Invocation Condition確認
- Failure History整理
- Same Failure確認
- Failure Signature生成
- Previous Route分析
- Requirements確認
- ADR確認
- Implementation確認
- Test確認
- Environment確認
- Root Cause分析
- Classification
- Recommended Route
- Invalidated Phases
- Evidence
- JSON Report
- Markdown Report