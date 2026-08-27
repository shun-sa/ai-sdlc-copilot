# Acceptance Test Executor Implementation

## 結論

Acceptance Test Executorは、
**SDLC COMPLETE後に人が明示的に起動**します。

SDLC Orchestratorには登録しません。

```text
SDLC COMPLETE
    ↓
HumanがHidden Acceptance Testを公開
    ↓
HumanがAcceptance Test Executorを起動
    ↓
acceptance-test-results.csv
    ↓
HumanがEvaluation Agentを起動
    ↓
evaluation-report.json
```

## Framework本体への変更

ありません。

以下は変更しません。

- SDLC Orchestrator
- Existing Producer Agents
- Existing Assurance Agents
- Existing Skills / Policies / Validators
- Evaluation Agent

## 新規ファイル

```text
.github/agents/acceptance-test-executor.agent.md

.github/skills/acceptance-test-execution/
├── SKILL.md
├── policy/
│   └── acceptance-test-policy.yaml
├── templates/
│   └── acceptance-test-manifest.json
└── scripts/
    ├── acceptance_common.py
    ├── run_acceptance_tests.py
    ├── validate_acceptance_results.py
    └── test_acceptance_test_execution.py
```

## Humanが作るもの

事前に人が作成し、
SDLC COMPLETEまでHiddenにします。

```text
acceptance-test-manifest.json
Acceptance Test Script群
```

Agentはこれらを生成・変更しません。

## Manifest例

```json
{
  "schema_version": 1,
  "run_id": "RUN-001",
  "sdlc_completed_at": "2026-01-01T12:00:00+09:00",
  "evaluation_data_exposed_at": "2026-01-01T12:05:00+09:00",
  "cases": [
    {
      "case_id": "AC-001",
      "requirement_id": "FR-001",
      "requirement_type": "FUNCTIONAL",
      "execution_type": "COMMAND",
      "command": [
        "python",
        "evaluation/acceptance/test_fr001.py"
      ],
      "expected": {
        "exit_code": 0
      }
    }
  ]
}
```

## 実行

```bash
python .github/skills/acceptance-test-execution/scripts/run_acceptance_tests.py \
  --repo-root . \
  --input-dir /path/to/evaluation-input/RUN-001
```

## Validation

```bash
python .github/skills/acceptance-test-execution/scripts/validate_acceptance_results.py \
  --manifest /path/to/evaluation-input/RUN-001/acceptance-test-manifest.json \
  --results /path/to/evaluation-input/RUN-001/acceptance-test-results.csv \
  --evidence reports/evaluation/RUN-001/acceptance-test/execution-evidence.json
```

## Evaluation Agent

Acceptance Test Executor実行後に、

```text
/path/to/evaluation-input/RUN-001/acceptance-test-results.csv
```

が生成されます。

既存Evaluation Agentはこのファイルを
そのままInputとして使用できます。

## FAILの意味

Acceptance Test CaseがFAILしても、
Executorの処理異常ではありません。

```text
Test Result FAIL
= 測定された品質結果

Validator FAIL
= 測定処理または記録の整合性異常
```

この区別を維持してください。
