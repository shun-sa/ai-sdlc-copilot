# 工程別トークンの取得・連携手順

この手順は開発Agentを変更せず、実験終了後にCopilotのモデル呼び出し記録と工程レポートを突き合わせます。設計あり・設計なし（C0）の両方に適用できます。取得元は、このPCで2026-10-27に確認した場所です。

## 受け渡し方法（基本）

実験終了後、次の**フォルダを丸ごと**コピーして、それぞれZIPにして渡してください。ファイルを一つずつ選ぶ必要はありません。

1. 実験作業先の reports フォルダ。例：C:\Users\shuns\Desktop\project\ai-sdlc-copilot\reports（C0なら ai-sdlc-copilot-no-design\reports）。最低限、対象の reports\experiments\<run_id> フォルダが入っていれば足ります。
2. C:\Users\shuns\.copilot\session-state フォルダ。容量や共有範囲を抑えたい場合は、対象の <session_id> フォルダだけでも構いません。セッションIDが不明なら、session-state 全体を渡してください。AIが開始時刻・作業先・ブランチで対象を探します。

メッセージには「今回のrun_id」と「設計あり／C0」を添えてください。ZIPの名前は任意です。重要なのは、中に reports\experiments\<run_id>\metrics.json と、対象セッションの events.jsonl があることです。.session-operation-locks だけではトークンを集計できません。

AIは受領後、対象Runとセッションを対応付け、工程別の呼び出し数・入力・出力・合計トークンを集計します。期間前・期間後・未配賦を残して総数と照合し、集計表と計算根拠を出力します。複数のセッションが候補になる場合は、根拠を示して判定し、特定できないものは勝手に合算しません。

**元の作業先からは実験終了後、ブランチを切り替える前にコピーしてください。** セッションログにはプロンプトや作業内容も含まれるため、共有先と機密情報を確認してください。

## 設計なし（C0）の違い

C0の作業先は C:\Users\shuns\Desktop\project\ai-sdlc-copilot-no-design です。下の採取コマンドでは $repo をその実験の作業先に変更します。取得するファイルの種類とCopilotセッションログの場所は設計ありと同じです。

C0は condition_id が C0、workflow_profile が NO_DESIGN_ADDR です。主計測期間は最初の IMPLEMENTATION から最後の有効な INTEGRATION_TEST 終了までです。ARCHITECTURE と ADDR は EXCLUDED_BY_PROFILE（対象外）として表示し、0トークンの実施済み工程にはしません。REQUIREMENTS は、Implementation開始後の差し戻し分だけ主計測期間に入ります。

## 取得するファイル

| 役割 | 取得元 | ZIP内の配置 |
| --- | --- | --- |
| 工程訪問時刻と計測期間（必須） | 実験作業先\reports\experiments\<run_id>\metrics.json | reports/metrics.json |
| Run終了状態（推奨） | 同じ場所のrun-context.json | reports/run-context.json |
| 工程記録の正本（再検証用） | 同じ場所のevents.sqlite3 | reports/events.sqlite3 |
| 工程記録の可読版（推奨） | 同じ場所のevents.jsonl | reports/events.jsonl |
| 呼び出し別トークン（必須） | C:\Users\shuns\.copilot\session-state\<session_id>\events.jsonl | copilot/events.jsonl |

前回のZIP名に含まれた .session-operation-locks はロック用です。トークンの取得元は、セッションIDのフォルダにある events.jsonl です。session.db やセッションフォルダ全体は不要です。metrics.json の tokens.value が null でも、Copilot側の呼び出し記録から計算できます。

## 必要なファイルだけ集める場合（任意）

1. 開発・計測を終え、SQLiteへの書き込みが止まったことを確認します。実験ブランチや作業先を切り替える前に採取します。別ブランチでは reports が見えなくなる場合があります。
2. 実験作業先の reports\experiments\ にある対象の RUN-... フォルダを確認します。metrics.json に run_id、time_window、phase_visits があることを確認します。metrics.json がまだ無ければ、実験終了後、リポジトリで次を実行します。
   python .github/skills/evaluation/scripts/experiment_recorder.py summarize --run-id <run_id>
3. 次の「セッション一覧」でCopilotの親session_idを確認します。開始時刻、リポジトリ、ブランチを照合してください。最新フォルダという理由だけで決めないでください。
4. 下の「採取コマンド」の3つの変数を今回の値に変え、PowerShellで実行します。元ファイルはコピーするだけで、移動・編集しません。
5. 作成されたZIPとこの手順書をAIに渡します。ログにはプロンプト、ツール引数、作業内容も含まれるため、共有先と機密情報を確認してください。

### セッション一覧（PowerShell）

~~~powershell
Get-ChildItem (Join-Path $env:USERPROFILE '.copilot\session-state') -Directory |
  ForEach-Object {
    $log = Join-Path $_.FullName 'events.jsonl'
    if (Test-Path -LiteralPath $log) {
      $first = Get-Content -LiteralPath $log -TotalCount 1 | ConvertFrom-Json
      [pscustomobject]@{
        SessionId = $_.Name
        StartedUtc = $first.data.startTime
        Workdir = $first.data.context.cwd
        Repository = $first.data.context.repository
        Branch = $first.data.context.branch
      }
    }
  } | Sort-Object StartedUtc -Descending | Format-Table -AutoSize
~~~

前回の例：RUN-20261022-MC はブランチ task/aoba_EC_retry、親セッション 7c7d3601-ebe1-45df-bcf4-7aa62929806a に対応します。次回は新しいIDを確認してください。実験中に親セッションを切り替えた場合は、使った全セッションのevents.jsonlを収集します。サブエージェントの呼び出しは親セッションのログに含まれます。

### 採取コマンド（PowerShell）

~~~powershell
$repo = 'C:\Users\shuns\Desktop\project\ai-sdlc-copilot'
$runId = 'RUN-今回のID'
$sessionId = '今回のCopilotセッションID'
$sourceReport = Join-Path $repo "reports\experiments\$runId"
$sourceCopilot = Join-Path $env:USERPROFILE ".copilot\session-state\$sessionId\events.jsonl"
$package = Join-Path $env:USERPROFILE "Documents\experiment-token-input\$runId"

New-Item -ItemType Directory -Force -Path (Join-Path $package 'reports'), (Join-Path $package 'copilot') | Out-Null
Copy-Item -LiteralPath (Join-Path $sourceReport 'metrics.json') -Destination (Join-Path $package 'reports\metrics.json')
Copy-Item -LiteralPath (Join-Path $sourceReport 'run-context.json') -Destination (Join-Path $package 'reports\run-context.json')
Copy-Item -LiteralPath (Join-Path $sourceReport 'events.sqlite3') -Destination (Join-Path $package 'reports\events.sqlite3')
Copy-Item -LiteralPath (Join-Path $sourceReport 'events.jsonl') -Destination (Join-Path $package 'reports\events.jsonl')
Copy-Item -LiteralPath $sourceCopilot -Destination (Join-Path $package 'copilot\events.jsonl')
[pscustomobject]@{ run_id = $runId; session_id = $sessionId; source_repo = $repo } |
  ConvertTo-Json | Set-Content -Encoding utf8 (Join-Path $package 'manifest.json')
$zipPath = "$package.zip"
Compress-Archive -LiteralPath $package -DestinationPath $zipPath
~~~

$repo は今回の実験ブランチを開いている実際の作業先に変更します。別のworktreeや作業フォルダを使った場合、例示のパスはそのまま使えません。複数の親セッションを使ったRunは各ログを別名で入れ、manifestに全IDを記録してください。同名のZIPを上書きしないよう、Runごとに新しい保存先を使います。

## AIへ送る短い依頼文

> 添付の手順書に従い、今回のrun_idと設計あり／C0を確認して工程別トークンを集計してください。主計測期間とRun全体を区別し、工程ごとの入力・出力・合計・呼び出し数、期間外・未配賦を示してください。サブエージェント分も含め、計算ルールと根拠を記載してください。

## AIの集計ルール

- reports/metrics.json の phase_visits を工程区間として使います。時刻はUTCに統一し、区間は開始を含み終了を含まないものとします。
- Copilotのevents.jsonlでは、typeがsession.usage_recordの行のみを使います。親Agentとサブエージェントを両方含めます。
- data.usage.accounting.sourceSessionId と usageId の組で重複を除きます。sourceSessionIdはサブエージェントの子セッションIDになるため、親セッションIDとの一致だけで除外しません。
- 各モデル呼び出しを一つの工程訪問へ割り当てます。重複区間・工程間の空白・境界にまたがる呼び出しは検査し、不確定分を別枠にします。同じ呼び出しを二工程へ加算しません。
- inputTokensとoutputTokensを別々に足し、合計は両者の和とします。cacheReadTokens・cacheWriteTokensは入力の内訳、reasoningTokensは出力の内訳として示し、再加算しません。subagent.completed.totalTokensも再加算しません。
- time_window.startからtime_window.endを主計測期間とします。設計ありはARCHITECTURE開始、C0はIMPLEMENTATION開始です。C0のARCHITECTURE・ADDRはEXCLUDED_BY_PROFILEとして扱い、0にしません。期間前・期間後・未配賦も残し、セッション全体との合計を照合します。最終FULL訪問が主計測期間外になる場合があります。
- 工程ログまたはトークン記録が欠けた場合、空欄を0にせず「算出不可」と明示します。

この方法はAgentのプロンプトや実行方法を変えません。events.sqlite3は工程記録の正本で、metrics.jsonとレポート側events.jsonlは集計・書き出しです。工程別トークンはCopilotセッションの呼び出し記録を後から突き合わせた値として扱います。


