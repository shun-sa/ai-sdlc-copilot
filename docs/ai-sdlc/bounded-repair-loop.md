# 共通3回ループ：未解決を記録して継続する

2026-10-21更新。要件・設計・ADDR・実装・テスト・Assuranceの全工程に適用します。
工程遷移については、旧資料の「全PASSまで停止」「未解決の持越し禁止」より本方針を優先します。
正本テンプレート・Agentの専門分担・検査の合否基準を変更するものではありません。

## 基本動作

1. 同じ原因の初回検出をcycle=0で記録します。初回検査は修正回数に含めません。
2. 担当Agentで修正・確認し、実際に再検査します。これをcycle=1,2,3の最大3回行います。
3. 解決すれば実際の成功証拠でRESOLVEDにします。
4. 3回修正しても残る場合、UNRESOLVEDとして原因・影響・修正履歴・再検査結果・対応先を保存します。
5. OrchestratorはCONTINUE_WITH_UNRESOLVEDの継続判定を保存して次工程へ進みます。
6. 後続工程は未解決事項を引き継ぎ、実行可能な処理を続けます。依存して実行不能な項目は未実行として残します。

3回とは「修正・再検査のループ3回」です。したがって初回検査を含めると最大4回の検査になります。
不足資料を自動で見つけられない等の場合も、実際に行った入力探索・確認と再検査を記録します。
架空の修正・未実行の検査で回数だけを埋めません。台帳登録コマンド自体は修正・再検査を実行しません。

担当Agent変更、設計PREPARE/ADDR/FINALIZE、差戻し、最終Assuranceで同じ原因を検出しても回数をリセットしません。
Agent内と親の回数を二重計上せず、4回目の修正ループを自動開始しません。
異なる原因には別signatureを使います。日時、request ID、行番号の変動等を原因識別に使いません。
後続工程で同じ未解決原因を再検出しただけならOBSERVEで現況を記録します。
後続の別原因は別途3回ループで扱います。Failの文言が変わっただけで別原因にしません。

## 品質と進行の区別

| 状態 | 意味 |
| --- | --- |
| PASS | 必須検査が成功し、未解決0件 |
| FAIL/BLOCKED/未実行 | 元成果物・検査の実際の結果。継続しても変更しない |
| CONTINUE_WITH_UNRESOLVED | 3回修正後の未解決を記録し、後続処理へ進める状態 |
| COMPLETE | 全工程を終え、品質条件を満たし未解決0件 |
| COMPLETE_WITH_UNRESOLVED | 全工程の処理・検査・記録を終えたが、未解決や依存する未実行が残る |

既存ValidatorとArchitecture品質Gateは厳格なままです。
通常の品質GateがFAILでも、別の共通継続判定が有効なら次工程へ進めます。
この許可は品質PASS、有効ADDR、ADDR不要承認、全機能完成、本番反映許可を意味しません。
欠落仕様の捏造、正本・期待値の弱体化、外部ケース変更、失敗ケースの削除/skipで回避しません。
必要な権限・ユーザー承認、秘密情報保護、不可逆操作の制約は回数で解除しません。
対象操作ができない場合はその事実を残し、可能な開発・検査を継続します。

## 記録先

- `reports/loop-control/retry-ledger.json`: 全原因の初回・修正履歴・状態
- `reports/loop-control/evidence/*.json`: ハッシュ固定した実際の結果のコピー
- `reports/loop-control/unresolved-results.json/.md`: 未解決の検査結果・影響・推奨対応先
- `reports/loop-control/phase-<PHASE>.json`: 必須検査の実施結果と工程継続判定

後続Agentへ未解決issue ID、関連要件、対象、影響、未承認範囲、対応先を渡します。
Traceability Reportは台帳の未解決状態を投影し、関連要件の確認表を「未解決あり」とします。
元のTraceability ValidatorのFAILは書き換えません。
最終結果には未解決件数・一覧・未実行範囲・実際の検査結果を必ず含めます。

## 失敗・修正のイベント

Orchestratorが実際の結果に基づき、次のJSONを `reports/loop-control/events/failure.json` 等へ保存します。

```json
{
  "signature": {
    "origin_phase": "ARCHITECTURE",
    "classification": "ADR_REQUIRED",
    "artifact": "docs/addr/ADDR-001.md",
    "requirement_reference": "FR-001",
    "test_case": "",
    "stable_error_type": "decision_missing"
  },
  "action": "FAILURE",
  "cycle": 0,
  "run_id": "actual-execution-000",
  "validation_result": "reports/loop-control/checks/architecture-gate.json",
  "errors": ["architecture_gate: command exit code 1"],
  "repair": "",
  "impact": "FR-001の設計判断が未確定。依存実装・試験は未実行の可能性あり",
  "recommended_route": "ADDR"
}
```

`errors`は参照する実結果のerrorsの部分集合です。省略時は全errorsを使います。
errorsがないBLOCKED等は `status=BLOCKED` のような状態文字列で扱います。
1つの結果の別原因はerrorsを分け、別signatureで記録します。
修正1〜3ではcycleを順に増やし、実際の実行ごとに異なるrun_idと修正・確認内容を記入します。
同じrun_idの再登録は回数を増やさず、証拠を差し替えた再利用は拒否します。

```text
python .github/skills/failure-triage/scripts/loop_control.py --record reports/loop-control/events/failure.json
```

3回後の再観測はaction=OBSERVE、cycle=3、新しいrun_idと現況結果を指定します。
追加修正を行ったように記録しません。解決した場合はaction=RESOLVEDと実際のPASS結果を指定します。

## 既存コマンドの結果を残す

JSONを出さない構造ValidatorやBuildは、実コマンドを実行するラッパーを使用できます。
例：次を `reports/loop-control/run-architecture-gate.json` に保存します。

```json
{
  "check_id": "architecture_gate",
  "command": ["python", ".github/skills/addr/scripts/validate_addr.py", "--write-gate"],
  "result_path": "reports/loop-control/checks/architecture-gate.json",
  "timeout_seconds": 300
}
```

```text
python .github/skills/failure-triage/scripts/loop_control.py --run-check reports/loop-control/run-architecture-gate.json
```

引数配列で実行し、終了値とPASS/FAILを記録します。エラー終了・タイムアウト・起動不能もFAILを保存します。
stdout/stderrと秘密情報を自動複製しません。詳細原因は元の安全な検査結果に基づき分類します。
Producer結果は実際のSUCCESS/BLOCKED等を保持したJSONで渡します。
実行不能な依存処理はBLOCKEDの理由を明記し、成功Reportを作りません。

## 工程の継続判定

共通Policyのrequired_checksにある全Check IDを、実結果の別々のパスへ対応付けます。
例：`reports/loop-control/checks-ARCHITECTURE.json` はprepare/design_draft/addr/addr_validation/
finalize/design_final/addr_final/quality/security/traceability/architecture_gateの全IDを持つJSONです。
実行しなかった工程・検査もその理由をBLOCKED結果へ記録して対応付け、省略しません。

```text
python .github/skills/failure-triage/scripts/loop_control.py --decide-phase ARCHITECTURE --checks reports/loop-control/checks-ARCHITECTURE.json
python .github/skills/failure-triage/scripts/loop_control.py --check-phase ARCHITECTURE
```

全Check成功・未解決0ならPASS、失敗がすべて3回後の未解決に対応付く場合だけCONTINUE_WITH_UNRESOLVEDです。
未記録の失敗、1〜2回しか修正していない原因、検査の省略、別工程Scopeの流用、証拠改変は継続不可です。
元検査の終了値1/2を0へ偽装せず、この別コマンドの終了値0を工程継続の許可として扱います。
失敗履歴の証拠は固定コピーなので、後工程による通常Reportの上書きで消えません。
設計・要件・入力等が変更されると継続許可を再検証できなくなります。現況を検査し、同じ未解決原因はOBSERVEで再対応付けして許可を再発行します。
Architectureの継続判定は実装コードの新規生成だけでは無効にしません。

## ADDRとFailure Triage

新しいADDR requestはmax_attempts=3です。親の台帳が工程横断の総修正回数を管理します。
古い2回requestは、未検証候補の退避・旧結果の無効化後に親が明示的に再予約します。
受領済みrequestやIDを勝手に書き換えず、再予約でも既実施回数を引き継ぎます。
ADDR不要の正常系と、ADDR未解決だが継続する状態を混同しません。
Failure Triageは3回後の任意の原因・対応先の診断であり、4回目の修正命令でも継続を無期限に止めるGateでもありません。

## 検証

```text
python .github/skills/failure-triage/scripts/test_loop_control.py
```

初回と3修正の区別、早期継続拒否、4回目拒否、二重計数防止、異原因の分離、未解決の引継ぎ、
証拠改変・古い入力・欠落検査の拒否、解決時の状態更新を検証します。
