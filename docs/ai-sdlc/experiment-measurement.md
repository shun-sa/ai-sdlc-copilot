# 実験計測ガイド

現行の工程分離は [ArchitectureとADDRの独立工程](independent-architecture-addr.md) を参照する。
ADDRは独立主工程であり、旧版のPREPARE→ADDR→FINALIZEやADDR子活動計測は新規Runでは使わない。

## 目的と役割分担

現行の分割要件・設計書・ADDRとトレーサビリティを維持したまま、実験の事実を記録する。
観測Scriptは開発の成功条件ではない。品質FAILをPASSへ変えず、初回失敗cycle=0の後に
修正・再検査を3回行い、残件を未解決として継続する既存方針も維持する。

| 欲しい値 | 開発中/実行時にAgentが残すもの | 人が準備・後から確認するもの |
| --- | --- | --- |
| 設計開始→結合試験終了の実時間 | 最初の設計進入と最後の有効な結合試験終了の実時刻 | 待機・中断を含めて比較する条件、未解決継続か品質合格か |
| 各工程の時間 | 全工程の進入/終了、再訪、独立ADDR工程・検証/Assuranceの子活動 | 記録漏れ、開始前の工程が未計測であること、親子時間の二重加算防止 |
| 前工程への手戻り回数 | 実際の委譲の出発工程・戻り先・理由・分類・検出Agent | 戻り先別集計と元イベント。同一工程内の修正回数とは別物 |
| 単体テスト分岐網羅率 | 実コマンド、同実行の生coverage/JUnit、対象版と固定証跡 | 実験前の対象/除外/分岐設定の固定、計測対象ファイルの妥当性 |
| 結合試験項目 | 外部入力を見る前のAI INITIAL、最終計画、実行結果のsnapshot | 項目・手順・期待値・出自・不足の確認。AI INITIALとGAP_FILL/EXTERNALを分ける |
| 人の受入テスト合格率 | 開発完了後に人の全ケースを実行、結果CSVと実行証跡を固定 | 人が事前に項目・期待値・実行可能なmanifestを準備。BLOCKED理由を確認 |
| トークン消費量 | 自動推計しない。未入力はnull | VSCodeで取得。計測処理を含む範囲、開発と受入/評価の区分をそろえる |

時間と実際の差し戻しは、後から成果物だけを見ても正確に復元できないため途中記録が必須。
網羅率・項目・受入結果は実行時の証跡を固定すれば、集計と人の精査は後から行える。
人が別途全イベントを転記する必要はない。過去の既存Runに記録がなければ遡及値は作らない。

## 指標の定義

### 時間

- 主区間は最初のARCHITECTURE（設計資料作成の委譲直前）から、最後の有効なINTEGRATION_TEST終了まで。
  テストコマンドだけのdurationではなく、設計、ADDR、実装、テスト作成、検証、Assurance、
  修正、ユーザー応答待ち、外部ケース待ち、環境待ち、計測処理の実時間を含む。
- 要件定義から始めるRunはREQUIREMENTSも記録するが、初回要件定義時間は主区間に含めない。
  設計後に要件へ差し戻した時間は含む。設計から開始したRunの初回要件定義時間は未計測。
- `phase_times` はRun全体の各工程の全訪問を合算する。最後のFULLも記録する。
  `measurement_window_phase_times` は主区間内だけの内訳。両者を混同しない。
  最終FULLは主区間外だが、そこから手戻りし結合試験を再実行した場合、途中のFULLは主区間に含む。
- 主工程は相互排他的。検証/各Assuranceは親内の子活動であり、
  `activity_times` を親工程の時間に加算しない。並行した子活動同士の合計も実時間とは限らない。
- 主工程は検証とAssuranceまで終えてから閉じる。次のenterで直前工程を閉じるか、
  実際の終了時にphase-endを実行する。明示的な工程間の空白はunallocated_secondsへ分離する。
- 結合試験がCONTINUE_WITH_UNRESOLVEDで終わっても処理終了までのelapsed_secondsは残す。
  quality_pass_elapsed_secondsは結合試験終了がPASSの場合だけ計算する（全工程品質合格の証明ではない）。
  run_status、integration_result、検査原本・未解決一覧を併記する。
- FULLから上流へ戻った時点で過去の結合試験終了は無効化する。再結合試験の終了までは主区間の終了値はnull。
  `finalized=false` は途中集計。終端ABORTEDは完走Runと分けて扱う。
- 時刻は機械のUTCを採取し、単調時計との差を監視する。時計補正/再起動等の不整合時は要確認とする。
  欠けた工程終了時刻を最終更新日時で補わない。中断区間の工程別秒数はnull、区間全体の実時間には中断も含む。

### 手戻り

REQUIREMENTS → ARCHITECTURE → ADDR → IMPLEMENTATION → UNIT_TEST → INTEGRATION_TEST → FULLの
順序に対し、実際に前の主工程へ委譲したPHASE_ENTEREDを1回とする。
出発工程別、戻り先別、出発→戻り先の組合せ別に集計する。
指摘件数・FailureTriageの提案数ではない。複数指摘をまとめて1回委譲したら1回。
同一工程の再試行は主工程手戻りに含めず、
checkpoint/子活動と既存loop-controlの履歴で確認する。計測回数と3回修正ループの回数は別管理。

### テスト関連

- 分岐網羅率 = covered branches / total branches × 100。
  coverage.pyのbranch有効JSON（totals.covered_branches/num_branches）、または
  Istanbul JSON summary（total.branches.covered/total）の整数カウントに対応する。
  coverage.pyのpercent_coveredは行と分岐の合算なので使わない。
  既存の派生coverage-summary.jsonの数値だけでは実験値を確定しない。
  分岐が0個ならNO_BRANCHES・rate=null（非該当）。未取得を0%や100%にしない。
- 最後の実測単体テストを選ぶ。最大の網羅率を選ばない。失敗したテストの実測値もexit_codeとともに保持する。
  テストコマンドが新しくcoverage/JUnitを書かなかった場合はUNCONFIRMED、
  対象ソース/設定が変わった場合はSTALEにする。必要な再試験を実行するまで旧値を現行値にしない。
- 結合項目はcase_id、title、requirement_id、手順、入力、期待値、origin、generation_stageと結果を保持する。
  AI INITIALはRun中に固定し、計画/結果は試行ごとにsnapshotする。古い結果を新しい計画へ付け替えない。
- 受入合格率 = PASS / 人が渡した全ケース × 100。
  FAILとBLOCKEDも分母に含む。CSV/証跡の欠落・重複・別Run・定義不一致・開発完了後の実装変更は
  INVALIDとしてrate=nullにする。結果を改善するためにケースを削除/skipしたり期待値を変更しない。

## 記録の開始と工程境界

Repositoryルートで実行する。以下のRUN-001とevent-idは例であり、実験ごとに一意にする。
既存Runを上書きするために同じIDを使わない。ユーザー指定がなければstartがrun_idを生成する。

```text
python .github/skills/evaluation/scripts/experiment_recorder.py start --run-id RUN-001 --condition-id C1 --phase REQUIREMENTS
python .github/skills/evaluation/scripts/experiment_recorder.py enter --run-id RUN-001 --event-id dispatch-arch-1 --phase ARCHITECTURE --result PASS
```

要件定義済みなら1行目を `--phase ARCHITECTURE` で実行し、そのままArchitectureへ委譲する。
同じ工程へのenterは実行しない。startで時計を動かしてから作業を開始し、run_idを全子Agentへ渡す。

独立ADDRへの委譲例（親が実際の委譲直前に記録する）：

```text
python .github/skills/evaluation/scripts/experiment_recorder.py enter --run-id RUN-001 --event-id dispatch-addr-1 --phase ADDR --result PASS
python .github/skills/evaluation/scripts/experiment_recorder.py enter --run-id RUN-001 --event-id dispatch-impl-1 --phase IMPLEMENTATION --result PASS
```

ADDRは独立したphase_timesの対象で、子活動へ二重記録しない。
Validator、QualityReview、SecurityReview、TraceabilityAuditorだけをactivity-start/endで親内に記録する。
resultは実際の工程/活動結果。Agent処理SUCCESSだけで品質PASSを指定しない。
検査FAILのまま継続許可された主工程はCONTINUE_WITH_UNRESOLVEDとし、検査原本を保持する。

実際の差し戻し・同一工程内修正・中断復旧の例：

```text
python .github/skills/evaluation/scripts/experiment_recorder.py enter --run-id RUN-001 --event-id dispatch-back-impl-1 --phase IMPLEMENTATION --result FAIL --classification IMPLEMENTATION_ERROR --reason "結合試験で実装不備を検出" --trigger-agent IntegrationTest
python .github/skills/evaluation/scripts/experiment_recorder.py checkpoint --run-id RUN-001 --event-id repair-issue-1-cycle-1 --reason "同一工程内の修正と再検査1回目"
python .github/skills/evaluation/scripts/experiment_recorder.py interrupt --run-id RUN-001 --event-id interruption-1 --reason "停止時刻不明の中断を検出"
python .github/skills/evaluation/scripts/experiment_recorder.py enter --run-id RUN-001 --event-id resume-impl-1 --phase IMPLEMENTATION --result BLOCKED
```

中断の実際の終了時刻を知っている場合も、後付け日時を入力する機能は設けない。
記録操作の再送は同じevent-idで冪等、実際の別試行は新しいID。journalはSQLiteのtransactionで追記する。
event-idを変えて同じ委譲を二重記録しない。計測エラーは警告と欠測として報告し、開発品質結果を変更しない。

## 単体テストの実測

Steeringで採用した実際のテストツールを分岐有効で設定する。実験前に対象と除外を固定する。
試行開始時にそのツールの計測データをクリアし、同一試行で生JSONとJUnitを新規出力する。
以下はスキーマの説明例であり、`実際の...` を実在するargvへ置換するまで実行しない。

```json
{
  "commands": [["実際のテスト実行ファイル", "実際の分岐計測・JUnit出力引数"], ["必要な場合の生JSONエクスポート実行ファイル", "その引数"]],
  "coverage": "reports/unit-test/coverage.json",
  "junit": "reports/unit-test/junit.xml",
  "timeout_seconds": 600
}
```

commandsは順に実行される。各コマンドのtimeoutはtimeout_seconds。Shell展開は行わない。
失敗後もcoverage exportが必要なため後続コマンドは実行し、最初の非0終了値を保持する。
必要なコマンドだけを定義し、後続を実行してよいことを確認する。stdout/stderr本文を観測journalへ収集しない。
コマンド仕様自体は固定証跡に保存するため、認証情報を引数へ直接埋め込まない。

仕様を `reports/experiments/RUN-001/unit-command.json` に保存し、親がUNIT_TESTへ入ってから実行する。

```text
python .github/skills/evaluation/scripts/experiment_recorder.py run-unit --run-id RUN-001 --event-id unit-exec-1 --spec reports/experiments/RUN-001/unit-command.json
```

記録器は実コマンドを実行して証跡を直後に固定する。別途同じテストを重複実行しない。
終了値非0は実テスト失敗または計測失敗であり、既存報告・Validatorで区別する。
旧Unit Test Skillが要求するcoverage-summary/evidence/JUnit、trace_checkの実行版記録も維持する。
この記録器は不足する言語用coverageツールを自動導入したり、未対応形式の値を推定したりしない。

## 結合項目の固定

```text
python .github/skills/evaluation/scripts/experiment_recorder.py snapshot --run-id RUN-001 --event-id initial-1 --kind AI_INITIAL --source reports/integration-test/ai-initial-cases.json
python .github/skills/evaluation/scripts/experiment_recorder.py snapshot --run-id RUN-001 --event-id it-plan-1 --kind INTEGRATION_PLAN --source reports/integration-test/integration-test-plan.json
python .github/skills/evaluation/scripts/experiment_recorder.py snapshot --run-id RUN-001 --event-id it-result-1 --kind INTEGRATION_RESULT --source reports/integration-test/integration-test-evidence.json
```

INITIALは外部ケースを読む前。計画は確定時と実装済みテスト実行直前、結果は実行直後に取得する。
実装・テストが変わった場合は新しい計画/結果snapshotを取る。原本を書き換えても固定証跡は失われない。

## 開発終了と人の受入試験

結合試験の検証・Assuranceを終えた時点で終了を記録し、FULLへ進む。

```text
python .github/skills/evaluation/scripts/experiment_recorder.py phase-end --run-id RUN-001 --event-id it-end-1 --phase INTEGRATION_TEST --result PASS
python .github/skills/evaluation/scripts/experiment_recorder.py enter --run-id RUN-001 --event-id full-1 --phase FULL
python .github/skills/evaluation/scripts/experiment_recorder.py phase-end --run-id RUN-001 --event-id full-end-1 --phase FULL --result PASS
python .github/skills/evaluation/scripts/experiment_recorder.py end --run-id RUN-001 --status COMPLETE
python .github/skills/evaluation/scripts/experiment_recorder.py summarize --run-id RUN-001
```

例は実結果PASSの場合。未解決なら既存継続判定に従いCONTINUE_WITH_UNRESOLVED/
COMPLETE_WITH_UNRESOLVEDを使う。FULLから手戻りしたら必要工程から記録を続け、再結合試験を行う。

開発終端後、人がAcceptanceTestExecutorを明示起動する。Hiddenケースは開発中に見せない。
受入入力はRepository外の兄弟Directoryを推奨する。完了後Repository内に置く必要がある場合は
`evaluation-input/<run-id>/` に置き、ソース領域へ評価専用ファイルを混ぜない。
run-context.jsonのrun_id/sdlc_completed_atと実際のevaluation_data_exposed_atをmanifestへ記入する。

表入力は [受入表の手順](acceptance-sheet-input.md) に従い、開発後にAcceptanceTestPrepareが外部コードへ対応付ける。
期待値・ケースを変えず、元表とコードの対応を人が承認してから凍結・実行する。
既存COMMAND manifestは互換維持し、表入力の実行不能項目だけ理由付きBLOCKED型として全分母へ残す。
manifestの形式は `.github/skills/acceptance-test-execution/templates/` を参照する。

```text
python .github/skills/acceptance-test-execution/scripts/run_acceptance_tests.py --repo-root . --input-dir ../evaluation-input/RUN-001
```

同run_idのjournalがあれば結果が自動連携される。失敗時はMEASUREMENT WARNINGを確認する。
修復後の手動import例（実際のファイルパスに合わせる）：

```text
python .github/skills/evaluation/scripts/experiment_recorder.py acceptance --run-id RUN-001 --event-id acceptance-import-1 --manifest ../evaluation-input/RUN-001/acceptance-test-manifest.json --results ../evaluation-input/RUN-001/acceptance-test-results.csv --evidence reports/evaluation/RUN-001/acceptance-test/execution-evidence.json
python .github/skills/evaluation/scripts/experiment_recorder.py summarize --run-id RUN-001
```

受入試験は主区間の所要時間に含めない。ケースコマンドの実行秒数は既存execution-evidenceの
duration_secondsで確認できるが、準備/入力/人の確認を含む受入工程全体時間ではない。
受入がFAILでも開発Runを自動再開・修正しない。改修実験は新しいrun_idで行う。

## 保存先と監査

`reports/`を一括ignoreしない。正本journal、固定証跡、集計、工程状態を実験ブランチへ保存する。
結果の保存後にmainへ戻り、次の実験は結果をマージしていない共通基準版から開始する。
終了・機密確認・コミット・切替と、外部の受入作業先の保存方法は
[実験ブランチと結果の保存](experiment-git-workflow.md) に従う。
Git管理対象への変更だけで過去の欠測時間を復元したり、計測の正本をevents.jsonlへ変更したりしない。

`reports/experiments/<run-id>/` に以下を置く。

| ファイル | 内容 |
| --- | --- |
| events.sqlite3 | 正本の追記イベントjournal。UTC、単調時計、連番、run_id、ハッシュ連鎖 |
| events.jsonl | summarize時の可読export。正本ではない |
| artifacts/ | SHA-256名の固定証跡。単体実行コマンド仕様/coverage/JUnit、INITIAL/計画/結果、受入manifest/CSV/evidence |
| metrics.json | 主区間・全工程時間・子活動時間・手戻り行列・生分岐・項目・受入・警告 |
| measurement-report.md | 人向け要約 |
| integration-cases.json | 全結合項目と出自・期待値・結果、固定原本参照 |
| rework-events.json | 既存Evaluation向けPHASE_ROUTE互換export。FULLはFINAL_ASSURANCEに変換 |
| run-context.json | 実際のSDLC終端時刻と状態。受入manifestへ引き継ぐ |

summarizeを途中実行しても開発イベントを追加しない。空欄は0ではない。
ソース版はRepositoryのファイル内容から識別する（reports、evaluation-input、build/dist、
依存/cache/.git、DB/SQLite、coverageデータ、symlinkを除外）。アプリ/テスト/設定/設計の変更は
保守的に証跡の再確認を要求する。外部DBの内容・外部サービス・インストール済み依存物の同一性までは
保証しないため、人が実験環境・ツール版・除外条件を別途固定する。
ハッシュ連鎖は破損検出であって、管理者による全記録の改竄や末尾削除を防ぐ認証基盤ではない。
journalと証跡をまとめて退避し、機密データを含む受入証跡の公開範囲を確認する。

## 既存Evaluationとの使い分け

今回の値だけならsummarizeと人のVSCodeトークン記録でよく、総合Evaluationの追加Inputは不要。
既存のevaluate_run.pyによるQ/C/D/P総合評価も使う場合は、従来Inputをそろえた上で
experiment-manifest.jsonへ `"experiment_run_id": "RUN-001"` を追加する。
`metrics.process.experiment_measurement` に今回の新指標が読み取り専用で併記される。
旧humanログ由来elapsedとIMPLEMENTATION戻りのみの手戻りは互換維持し、新指標とは別欄にする。
aggregate_experimentsの既存集計対象は自動で新定義へ置換されない。

既存experiment_logger.pyは人の作業時間/関与・外部トークンの手動入力に使える。
そのrouteコマンドで今回の自動手戻りを再記録しない。手動ログは別Directoryに保持し、
総合評価用のrework-events.jsonが必要なら観測exportをコピーして参照する。
トークンはVSCode実測を使い、計測Agentの処理を含む/除く範囲を全Runで統一する。
