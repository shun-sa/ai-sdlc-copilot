# Acceptance Test Execution Skill

## Purpose

人が事前作成またはレビュー・確定したHidden Acceptance Testを
SDLC COMPLETE後に実行し、
Evaluation Agentへ渡す測定結果を生成します。

新しい受入条件は生成しません。外部表の確定条件を実行コードへ翻訳する準備だけを分離して行います。

# Sheet Input

人が開発完了後にAcceptanceTestExecutorを起動し、受入表のパスと外部workspaceを指定します。
開発RunはCOMPLETE / COMPLETE_WITH_UNRESOLVEDであること。ABORTED/実行中は不可です。
元表を初めて読む前に実際の読込開始時刻を取得し、evaluation_data_exposed_atとして使います。
実際のrun-context.jsonを使い、時刻やrun_idを捏造・さかのぼって変更しません。

対応入力:
- 今回配布の全ブックXLSX（受入項目・受入詳細。集計・結果・補足NFRは主分母へ加算しない）。
- 標準列のCSV / 単一表XLSX: case_id,title,requirement_id,requirement_type,precondition,steps,expected_result。
- acceptance-case-definitions.json。JSONは実行manifestと区別する。

CSV/JSONにあるPASS/FAIL/BLOCKED条件、測定条件、証跡等も省略せず読む。
全ブックでは分割番号順に本文を連結し、非機能区分は関連NFRを主参照にする。
主参照IDが一意に選べない/不適切な場合は人へ確認し、元表を黙って変更しない。
XLSXは文字列・数値の固定値を読み、式・マクロ・外部リンクを実行しない。追加Python依存は不要です。

1. `prepare_acceptance.py import`で元表を複写し、全ケースをcase-bundle.jsonへ保持する。新しい空のworkspaceのみ使う。
2. AcceptanceTestPrepareへworkspace/testsとbindings.jsonだけの編集を委譲する。実アプリの試験はまだ実行しない。
3. `review`で件数・対応・テストファイルのハッシュとreview_sha256を提示する。人は元の全期待条件とassertion_map/コードを確認する。
4. **人の明示承認待ちで停止する**。AI自身や未回答を承認者にしない。承認はケース定義と外部コマンドの実行許可の両方が対象。
5. 人が承認した同じreview_sha256と実際の承認者で`seal`を実行する。UNBOUNDが残れば凍結不可。実行不能は理由付きBLOCKEDとして全分母に残す。
6. 凍結manifestを既存Executorで実行・検証する。期待値、コード、bindings、対象ソースの変更は検出して実行/評価を停止する。

コマンド例（実際のパス・時刻・承認者・ハッシュへ置換）:

```text
python .github/skills/acceptance-test-execution/scripts/prepare_acceptance.py import --repo-root . --source ../human-evaluation/acceptance-case-definitions.json --workspace ../human-evaluation/RUN-001 --run-context reports/experiments/RUN-001/run-context.json --exposed-at <actual-exposure-time>
python .github/skills/acceptance-test-execution/scripts/prepare_acceptance.py review --workspace ../human-evaluation/RUN-001
python .github/skills/acceptance-test-execution/scripts/prepare_acceptance.py seal --workspace ../human-evaluation/RUN-001 --reviewer <actual-human-reviewer> --review-sha256 <approved-review-sha256>
```

準備テストは前提不足なら125、期待不一致なら非0（125以外）、全期待条件成立時だけ0を返す。
Bindingsのtest_files、assertion_mapを省略しない。構文確認等で発生する__pycache__/pycだけは凍結対象外です。
凍結後の同じ評価Runでは、PASSにするためのテスト修正・期待値変更・再実行をしません。
準備不具合を修正する必要があれば人へ返却し、新しい評価試行・workspaceとして条件差を記録します。
準備の同一エラーは最大3修正後に理由付きBLOCKEDで残します。承認・隔離・定義保全のGateはループ上限で免除しません。


# 実験計測との連携

開発終端COMPLETE/COMPLETE_WITH_UNRESOLVED後に人が本Agentへ入力する。
`reports/experiments/<run-id>/run-context.json` の実際の完了時刻をmanifestの
sdlc_completed_atへ反映し、同じrun_idと実際のevaluation_data_exposed_atを使う。
人の試験項目・期待値は開発中に公開せず、変更も補完もしない。

既存COMMAND manifestはそのまま対応する。表入力は上記Sheet Inputで準備・人承認を経て対応付ける。
Agentが未対応操作を実施済みとしたり、期待値を都合よく作ってはいけない。

既存Scriptを実行すると、同run_idの観測journalがある場合はCSVとexecution-evidenceを自動で保存・集計する。
合格率は `PASS / 人が与えた全ケース * 100`。FAIL/BLOCKEDを分母から除外しない。
ケース欠落・別Run・実装変更・証跡不整合時は未確定とし、警告を確認する。
自動連携の失敗は本来の受入結果を書き換えない。修復後の手動import方法は
`docs/ai-sdlc/experiment-measurement.md` を参照する。

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

`COMMAND`（または表入力の承認済みmanifestに限り、理由付き`BLOCKED`）

を扱います。BLOCKEDケースのコマンドは実行しませんが分母から除外しません。

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
