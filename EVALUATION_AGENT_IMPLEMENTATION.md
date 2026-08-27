# Evaluation Agent Implementation

## 目的

SDLC Frameworkへの影響を最小化しつつ、
研究評価値をSDLC COMPLETE後に外部測定するための追加Componentです。

## Framework本体への変更

**ありません。**

以下は変更しません。

- SDLC Orchestrator
- Producer Agents
- Assurance Agents
- Existing Skills / Policies / Validators
- copilot-instructions.md

Evaluation Agentは独立した`user-invocable` Agentとして追加します。

## 新規ファイル

```text
.github/agents/evaluation.agent.md

.github/skills/evaluation/
├── SKILL.md
├── policy/
│   └── evaluation-policy.yaml
├── templates/
│   ├── experiment-manifest.json
│   ├── acceptance-test-results.csv
│   ├── human-traceability-matrix.csv
│   ├── human-interaction-log.json
│   ├── ai-usage-log.json
│   └── rework-events.json
└── scripts/
    ├── evaluation_common.py
    ├── evaluate_run.py
    ├── validate_evaluation.py
    ├── aggregate_experiments.py
    ├── experiment_logger.py
    └── test_evaluation.py
```

## 評価Inputは開発中に置かない

Hidden Acceptance Test / Human Traceability Matrixは、
開発Agentから見えない場所に保持し、
SDLC COMPLETE後にEvaluation Agentへ提供してください。

`external-tests/integration-test/`は
開発中にIntegration Test Agentが参照するため、
Hidden Acceptance Testとして使用しません。

## 1 Runの実行

```bash
python .github/skills/evaluation/scripts/evaluate_run.py \
  --repo-root . \
  --input-dir /path/to/evaluation-input/RUN-001
```

続けて:

```bash
python .github/skills/evaluation/scripts/validate_evaluation.py \
  --report reports/evaluation/RUN-001/evaluation-report.json
```

## 複数Runの集約

```bash
python .github/skills/evaluation/scripts/aggregate_experiments.py \
  --repo-root . \
  --reports-root reports/evaluation
```

## 外部Logger

`experiment_logger.py`は任意です。

SDLCへ組み込まず、
別Terminalや外部Wrapperから使用します。

開始:

```bash
python .github/skills/evaluation/scripts/experiment_logger.py start \
  --input-dir /path/to/evaluation-input/RUN-001
```

Human Prompt:

```bash
python .github/skills/evaluation/scripts/experiment_logger.py human \
  --input-dir /path/to/evaluation-input/RUN-001 \
  --type PROMPT \
  --characters 1200
```

Correction:

```bash
python .github/skills/evaluation/scripts/experiment_logger.py human \
  --input-dir /path/to/evaluation-input/RUN-001 \
  --type CORRECTION \
  --characters 300
```

Review:

```bash
python .github/skills/evaluation/scripts/experiment_logger.py human \
  --input-dir /path/to/evaluation-input/RUN-001 \
  --type REVIEW
```

終了:

```bash
python .github/skills/evaluation/scripts/experiment_logger.py finish \
  --input-dir /path/to/evaluation-input/RUN-001 \
  --active-seconds 7200
```

## 測定Metric

### Quality

- Requirement Satisfaction Rate
- Functional Satisfaction Rate
- Non-functional Satisfaction Rate
- Unit Test Branch Coverage
- AI INITIAL Integration Requirement Coverage
- AI INITIAL Integration Trace Item Coverage

### Cost / Efficiency

- Human Input Count
- Human Input Characters
- Review Count
- Correction Count
- Human Active Work Time
- Experiment Elapsed Time
- Rework Count
- AI Input / Output / Total Tokens
- Cache Read / Write Tokens
- Design Context Tokens

### Process

複数Runの:

- Mean
- Sample Standard Deviation
- Task Category別比較

## 重要な研究上の分離

```text
SDLC Framework
= 実験対象

Evaluation Agent
= 測定器
```

Evaluation Agentの結果は、
開発Runを修正するためにFeedbackしません。
