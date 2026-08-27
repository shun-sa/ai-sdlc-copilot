# Evaluation Skill

## Purpose

SDLC COMPLETE後のRunを、
開発プロセスへ介入せず外部から評価します。

本Skillは、
Evaluation Agent専用です。

SDLC Producer Agent、
Assurance Agent、
SDLC Orchestratorから
自動実行してはいけません。


# Measurement Model

評価は以下の4観点を扱います。

- Q: Quality
- C: Cost
- D: Efficiency
- P: Process

単一RunではQ / C / Dを測定し、
複数Run集約でPの再現性・汎用性を評価します。


# Input Isolation

Evaluation用のHidden Acceptance Testと
Human Traceability Matrixは、
SDLC COMPLETE前に開発Agentへ公開してはいけません。

`external-tests/integration-test/`
は開発中にIntegration Test Agentが参照するため、
Hidden Acceptance Test置場として使用してはいけません。

推奨:

```text
<repository>/                    # SDLC対象
<sibling>/evaluation-input/
  RUN-001/
```

Workspace制約等によりRepository配下へ置く場合は、
SDLC COMPLETE後に配置し、
`evaluation_data_exposed_at >= sdlc_completed_at`
をManifestへ記録してください。


# Input Files

標準Input Directory:

```text
evaluation-input/<run-id>/
```

実データはSDLC COMPLETE後に配置します。

必要Input:

```text
experiment-manifest.json
acceptance-test-results.csv
human-traceability-matrix.csv
human-interaction-log.json
ai-usage-log.json
rework-events.json
```

Templateは以下です。

`.github/skills/evaluation/templates/`


# Step 1. Manifestを確認する

`experiment-manifest.json`
から以下を確認します。

- run_id
- condition_id
- task_id
- task_category
- model
- model_version
- prompt_profile_id
- sdlc_completed_at
- evaluation_data_exposed_at
- Input File Path

`evaluation_data_exposed_at`
が`SDLC COMPLETE`より前の場合、
Hidden Evaluation Data Isolation違反としてFAILしてください。


# Step 2. Requirement Satisfactionを測定する

Human Acceptance Test Resultsから、

```text
合格件数 / 総試験件数 * 100
```

を算出します。

以下を分離集計してください。

- Overall
- FUNCTIONAL
- NON_FUNCTIONAL

PASSだけを合格として扱います。

FAIL / BLOCKED / NOT_RUNは
合格へ含めません。

Acceptance Testは
SDLC開発中に使用したExternal Integration Testとは
別のHidden Evaluation Setを使用してください。


# Step 3. Unit Test Coverageを測定する

標準Source:

`reports/unit-test/coverage-summary.json`

Policyで指定されたCoverage Metricを使用します。

標準:

`branches`

Condition CoverageがRepositoryで取得可能で、
Policyを`condition`へ変更した場合のみ
Condition Coverageを使用してください。

Coverage値をAIが推測してはいけません。


# Step 4. AI Generated Integration Test Coverageを測定する

Human Traceability Matrixと、

`reports/integration-test/ai-initial-cases.json`

を比較します。

AI側は以下だけを使用します。

```text
origin = AI_GENERATED
generation_stage = INITIAL
```

AI GAP_FILL / EXTERNALは除外してください。

Main Metrics:

1. Requirement Coverage
   - Human Matrix上のRequirementのうち、
     AI INITIALがRequirement IDでCoverageした割合

2. Trace Item Coverage
   - Human Matrixに`coverage_key`がある場合、
     Human Matrix上のTrace Itemのうち、
     AI INITIALの`coverage_key`と一致した割合

`coverage_key`がない行は、
Trace Item CoverageではRequirement IDをFallback Keyとして使用します。


# Step 5. Human Effortを測定する

`human-interaction-log.json`
から以下を取得します。

- Input Count
- Input Characters
- Review Count
- Correction Count
- Human Active Work Seconds
- Experiment Elapsed Seconds

Input Count対象:

- PROMPT
- CORRECTION
- OTHER_INPUT

ReviewはInput Countへ含めません。

Human Active Work Timeは、
Logで明示された値だけを使用してください。

Start / End時刻から
Active Work Timeを推測してはいけません。


# Step 6. Reworkを測定する

`rework-events.json`
から、

後工程からIMPLEMENTATIONへ戻った
実装修正Cycleを数えます。

標準対象From Phase:

- UNIT_TEST
- INTEGRATION_TEST
- FINAL_ASSURANCE
- QUALITY_REVIEW
- SECURITY_REVIEW
- TRACEABILITY

以下は除外します。

- minor_refactoring = true
- classification = REFACTOR
- classification = FORMAT_ONLY

1回のRoute back to IMPLEMENTATIONを
1 Reworkとして数えます。


# Step 7. AI Usageを測定する

`ai-usage-log.json`
から以下を合計します。

- input_tokens
- output_tokens
- total_tokens
- cache_read_tokens
- cache_write_tokens
- design_context_tokens

`total_tokens`がRecordへ明示されている場合は
その値を使用します。

明示されていない場合だけ、

```text
input_tokens + output_tokens
```

をTotalとして使用します。

Token数を文字数から推測してはいけません。

Evaluation Agent自身のUsageは、
開発RunのUsage Logへ含めてはいけません。


# Step 8. Single Run Reportを生成する

実行:

```bash
python .github/skills/evaluation/scripts/evaluate_run.py \
  --repo-root . \
  --input-dir <evaluation-input-dir>
```

Outputs:

```text
reports/evaluation/<run-id>/metrics.json
reports/evaluation/<run-id>/evaluation-report.json
reports/evaluation/<run-id>/evaluation-report.md
```


# Step 9. Evaluation ReportをValidationする

```bash
python .github/skills/evaluation/scripts/validate_evaluation.py \
  --report reports/evaluation/<run-id>/evaluation-report.json
```

ValidatorがPASSしない場合、
Evaluation結果を確定値として使用してはいけません。

Source Artifactを修正してはいけません。

不足・不整合のあるEvaluation Inputを確認してください。


# Step 10. Reproducibilityを集計する

同一:

- condition_id
- requirements
- prompt_profile_id
- model / model_version

で複数Runを実施します。

標準では5 Run程度を想定します。

実行:

```bash
python .github/skills/evaluation/scripts/aggregate_experiments.py \
  --reports-root reports/evaluation
```

同一`condition_id`ごとに、
主要Metricの平均値と標準偏差を算出します。


# Step 11. Generalityを集計する

異なる`task_category`のRunを集約します。

例:

- CRUD
- BUSINESS_LOGIC
- EXTERNAL_API

Task Categoryごとの
平均値・標準偏差を比較します。

特定Categoryのみ
著しく評価値が低い場合、
汎用性上の差としてReportします。

本Scriptは差を計測するだけで、
原因を自動的に断定しません。


# Integrity Principles

- Measurement CodeをSDLC Phaseへ混ぜない
- Hidden Evaluation Dataを開発前に公開しない
- Evaluation ResultからSourceを修正しない
- Missing Measurementを0扱いしない
- AIの自己申告値をDeterministic Metricの代替にしない
- Runtime ReportはSource of Truthではない
