# Acceptance Test Execution Skill

## Purpose

人間が事前作成したHidden Acceptance Testを
SDLC COMPLETE後に実行し、
Evaluation Agentへ渡す測定結果を生成します。

本SkillはAcceptance Testを生成しません。


# Principle

```text
Human
  ↓
Acceptance Test Definition
  ↓
Acceptance Test Executor
  ↓
Actual Result
  ↓
Deterministic Comparison
  ↓
PASS / FAIL / BLOCKED
```

Expected Resultは人間が事前定義します。

AgentがExpected Resultを補完してはいけません。


# Step 1. SDLC COMPLETEを確認する

`acceptance-test-manifest.json`の

- sdlc_completed_at
- evaluation_data_exposed_at

を確認します。

`evaluation_data_exposed_at < sdlc_completed_at`

の場合は、
Hidden Evaluation Data Isolation違反として
実行を開始してはいけません。


# Step 2. Manifestを読み込む

標準:

`<evaluation-input-dir>/acceptance-test-manifest.json`

各Caseの必須項目:

```text
case_id
requirement_id
requirement_type
execution_type
command
expected.exit_code
```

`execution_type`は現在、

`COMMAND`

のみ対応します。

CommandはShell文字列ではなく、
Argument Arrayとして定義してください。

例:

```json
{
  "command": [
    "python",
    "evaluation/acceptance/test_login.py"
  ]
}
```

Shellを経由しないことで、
評価定義以外の解釈を減らします。


# Step 3. Test Definitionを変更しない

本Executorは以下を変更しません。

- command
- expected
- requirement_id
- requirement_type
- case_id

Test Caseの意味的妥当性は
人間の事前レビュー責任です。


# Step 4. Commandを実行する

各Caseを独立して実行します。

標準TimeoutはPolicyに従います。

Caseに`timeout_seconds`がある場合は、
Policy上限以内でOverride可能です。

Commandが起動できない場合:

`BLOCKED`

Timeout:

`BLOCKED`

正常起動しExpected Result不一致:

`FAIL`

Expected Result一致:

`PASS`


# Step 5. Expected Resultを比較する

対応項目:

```text
expected.exit_code
expected.stdout_contains[]
expected.stderr_contains[]
expected.stdout_not_contains[]
expected.stderr_not_contains[]
```

最低限、

`expected.exit_code`

が必要です。

Test Script自身がAssertionを持つ場合は、
`exit_code = 0`
だけで十分です。


# Step 6. Resultを出力する

Evaluation Agentが読むCSV:

```text
case_id,requirement_id,requirement_type,result
```

追加列:

```text
exit_code
duration_seconds
blocked_reason
```

監査用Evidenceには、
Command、Expected Result、
Actual Exit Code、
stdout/stderrのHashを保持します。

Policy既定では
stdout/stderr本文をEvidenceへ保存しません。


# Step 7. ResultをValidationする

Validatorは以下を機械検証します。

- Manifest Case数とResult Case数が一致する
- Case IDが一致する
- 重複Caseがない
- Requirement情報がManifestと一致する
- PASS / FAIL / BLOCKED以外がない
- Evidenceに全Caseが存在する
- ResultとEvidence Statusが一致する
- Manifest HashがEvidenceと一致する

Acceptance TestにFAILがあること自体は、
Validator Failureではありません。

Validatorは、
「測定結果が正しく記録されたか」を検証します。


# Step 8. Evaluation Agentへ渡す

`acceptance-test-results.csv`

をそのままEvaluation Agentへ渡します。

Evaluation Agentは、

```text
PASS件数 / 総Case数
```

からRequirement Satisfactionを算出します。

BLOCKEDはPASSへ含めません。


# Important Separation

Acceptance Test Executor:

`試験を実行する`

Evaluation Agent:

`結果から評価値を計算する`

Aggregate Script:

`複数Runを統計集約する`

これらの責務を混在させてはいけません。
