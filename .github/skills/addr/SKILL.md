---
name: addr
description: >
  設計書作成後の重要な未確定判断を比較・決定し、既存ADDRテンプレートで
  判断・設計差分・AI実装制約を記録する。IDプール・入力版・復旧境界を検証する。
user-invocable: false
disable-model-invocation: false
---

# ADDR Skill

添付ADDR案の役割・自律実行原則を現在のOrchestratorへ接続する。
`templates/addr.md` を構造の正本とし、既存Agentの数値名AG-00/03/04は使用せず、
親はSDLCOrchestrator、前後の設計作業はArchitectureとする。

## 実験Runの計測

ADDRはARCHITECTURE内の子活動としてOrchestratorが計測する。
親からのrun_idを保持し、別Runや主工程遷移を作らず、実結果を返す。
所要時間を推測しない。判断・差分・ID予約・検証契約は変更しない。

## Input

OrchestratorはDRAFT設計検証後、次で予約IDと入力契約を準備する。

```text
python .github/skills/addr/scripts/validate_addr.py --prepare-request
```

出力 `reports/architecture/addr-request.json` は以下を持つ。
`source_revision`, `design_input_sha256`, `addr_id_pool`, `target_criticality`,
`recovery_policy.max_attempts`, `attempt`。重要度は設計入力の根拠付き値を保持する。
既存ADDRと予約済みIDを確認し、要否判断後に作成対象だけへプール順で割り当てる。
不足・衝突時は親へFAILEDを返し、プール外IDを生成しない。
既存requestがある場合は上書きせず、再予約は親が古い結果を無効化し明示的に行う。
Gate未通過の旧候補が残る場合は、親が `reports/architecture/failed/` 等へ履歴として退避してから
再予約する。未検証の候補を既存有効判断に昇格させない。

## 判断と生成

1. 入力版と出典、関連要件・AC、設計、Steering、既存ADDR/Accepted ADRを照合する。
2. 候補一覧が空でも対象全体から判断漏れを確認する。対象ごとに要否と理由を記録する。
3. 一意に導出できる定型処理は不要。複数の合理的方式、重要な責任・例外・保証・非機能等は検討する。
4. 1 ADDR = 1中心判断 = 1設計種別。現実的な案だけを比較し、架空の代替案を追加しない。
5. `docs/addr/ADDR-xxx.md` へ正本で生成する。design_typeに対応する6章の節は1つだけ残す。
   その他の1〜9章を維持する。非該当の行はガイドに従い削除または「なし」とする。
6. DC/OPT/DD/INV/ASMは文書内の定義ID。実装拘束はMUST / MUST_NOT / SHOULDのみ。
   関連要件の不存在、独立判断の混在、要件の変更、秘密・契約・法令・根拠のない値の補完は禁止する。
7. 前工程設計書を直接編集せずLINK_ADDR要求を返す。親がArchitectureのFINALIZEへ渡す。

## Output

`reports/architecture/addr-result.json` に次の必須項目を保存する。

```json
{
  "status": "SUCCESS",
  "result": "SUCCESS",
  "source_revision": "入力版",
  "design_input_sha256": "受領値",
  "output_artifacts": [{"addr_id": "ADDR-001", "path": "docs/addr/ADDR-001.md", "sha256": "実SHA-256"}],
  "addr_creation_results": [{"candidate_key": "file-retry", "target_id": "FR-001", "needed": true, "reason": "重要な判断理由", "addr_id": "ADDR-001"}],
  "unused_addr_ids": [],
  "artifact_link_updates": [{"artifact_id": "FILE-001", "target_id": "FR-001", "related_addr_id": "ADDR-001", "requested_action": "LINK_ADDR"}],
  "assumptions": [],
  "blocking_issues": [],
  "human_intervention_requested": false,
  "autonomous_recovery": {"action": "NONE", "attempt": 0, "max_attempts": 3}
}
```

不要判断はneeded=false、addr_id=nullとし、未使用IDを全件返す。ADDR不要は正常終了であり、空の文書を作らない。
対象ごとに少なくとも1つの要否結果を返し、入力候補も全件説明する。追加候補は一意なcandidate_keyで記録する。
assumptionsはassumption_id/statement/basis_ids/affected_target_ids/reversible/verification_methodを持つ。
安全側仮定は要件・受入条件を変えず、セキュリティを弱めず、可逆または検証可能である場合だけ採用する。

result=SUCCESS_WITH_ASSUMPTIONSはstatus=SUCCESSとし、根拠付き仮定を必須にする。
PARTIAL_SUCCESSはstatus=BLOCKEDへ写像する。OPTIONAL対象の隔離候補と理由を親へ返すが、
部分成功は品質PASSにしない。3回後の工程継続は共通ループ判定へ返す。MANDATORYの未達も隠さない。
FAILUREはstatus=FAILED。未解決の重大事項を成功として隠さない。
自動復旧の試行回数・上限は受領値を保持し、同一failure_signatureについて親が上限を管理する。
安全に継続できなければ人へ質問せず、復旧要求を親へ返す。

```text
python .github/skills/addr/scripts/validate_addr.py
```

## 状態と旧ADRとの互換

正本のstatusはACTIVE / SUPERSEDEDを使い、Proposed/Acceptedを追加しない。
ACTIVEで出力されてもArchitecture Gate前は候補であり、実装へ渡さない。
旧Accepted ADRは維持し、新判断と矛盾する場合は置換計画を親へ返す。旧判断を黙って上書きしない。
判断変更時は新IDで新ADDRを作り、置換対象・理由を報告して古いADDRをSUPERSEDEDにする。
変更後は設計反映・Assurance・Gateを再実行する。
設計書・Integration Planのadr_id/related_adr等の欄はADDR IDにも使う。Trace Map v3はelements/sourcesを使う。旧ADRの重複投影を作らない。

# Inline Traceability

ADDR作成時に正本2章「関連要件・参照成果物」の「要件」行へ実在要件IDを記入します。
UC/AC等の設計入力も保持しますがAC・DBD・FILEだけで関連要件を代用しません。
正本1〜9章とdesign_type対応節を維持し、存在しないRelatedArtifacts/TestStrategy欄は追加しません。
テスト拘束が判断から生じる場合は正本の不変条件・9章AI実装指示の既存欄に記録します。
ACTIVEはGate通過を意味しません。SUPERSEDEDへの下流参照は更新対象として親へ返します。

## 共通3回ループ

修正・再検査は `docs/ai-sdlc/bounded-repair-loop.md` に集約します。
初回失敗0＋実修正1〜3の後も残る場合、FAIL/BLOCKEDを維持して親へ未解決として返し、
親が履歴・影響を記録して次工程への継続を許可します。4回目を自己開始しません。
未解決継続を品質SUCCESS/PASSへ変換せず、原因を隠す修正・捏造・削除・skipをしません。

新requestはmax_attempts=3です。旧2回requestは親が未検証候補を退避・旧結果を無効化して明示再予約します。
Agentが受領済み契約を勝手に改変せず、既に実施した修正回数は共通台帳から引き継ぎます。
