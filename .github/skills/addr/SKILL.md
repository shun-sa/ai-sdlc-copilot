---
name: addr
description: >
  独立した重要判断工程。設計資料を再作成せず、判断・差分・実装拘束と明示的な参照を記録する。
user-invocable: false
disable-model-invocation: false
---

# ADDR Skill

## 責務

通常順序はRequirements→Architecture→ADDR→Implementation。親はSDLCOrchestrator。
Architectureは既存テンプレートによる設計資料、ADDRは重要判断の唯一の作成者である。
仕様で確定している項目表・手順・Taskや全体整合性分析をADDRへ丸ごと複製しない。
入力の章構成を作り直したり、ADDRを詳細設計書の代わりにしたりしない。

## Input

Architectureのversion=2 FINAL manifestと設計Gateを検証後、親が以下を実行する。

```text
python .github/skills/addr/scripts/validate_addr.py --prepare-request
```

互換パスreports/architecture/addr-request.jsonはsource_revision、design_input_sha256、
design_input_path=reports/architecture/design-manifest.json、workflow_version=2、予約IDプール、
target_criticality、recovery_policy.max_attempts=3、attemptを持つ。
design_input_sha256という既存フィールド名は「受領FINAL manifestのハッシュ」を意味する。
同一版は再利用。変更時は親が旧未公開候補を退避し--renew-requestで再予約する。
予約外ID・過去の予約IDを使わず、実施済み共通ループ回数を維持する。

## 判断と生成

1. 要件・UC/AC・Steering・設計成果物・既存判断を照合し、全対象のADDR要否と理由を記録する。
2. 一意に定まる定型処理は不要。複数の合理的方式、重要な責任/例外/保証/非機能等だけを比較・決定する。
3. 1 ADDR = 1中心判断 = 1設計種別。実在する合理的な選択肢だけを比較し、架空の代替案を追加しない。
4. 正本templates/addr.mdを使いdocs/addr/ADDR-xxx.mdへ生成する。1〜9章を維持し、
   6章のdesign_type対応節は1つだけ残す。DD/INV/ASM、MUST/MUST_NOT/SHOULDを既存欄へ記録する。
   要件・受入条件・根拠のない値を補完せず、既存仕様はID/Pathで参照する。
5. 2章の既存「関連要件・参照成果物」へ実在要件IDと、影響するFILE/TASK ID・設計パスを記載する。
   related-artifactsという新しい章やTrace専用表は追加しない。
6. 前工程を変更せず、artifact_link_updatesでその明示的参照を機械可読にする。
   このLINK_ADDRは通常の設計書編集依頼ではなく、ADDR側からの関連付けである。
7. 設計本文・Taskの内容変更が本当に必要ならdesign_change_requestsへ対象/理由/変更内容を記録し、
   status=BLOCKEDとして親へ返す。Architectureへ実際に差し戻した後にADDRを再検査する。
   参照追加だけなら差し戻さず、通常FINALIZEも行わない。

## Result

互換パスreports/architecture/addr-result.jsonへ、既存のstatus/result/source_revision/
design_input_sha256/output_artifacts/addr_creation_results/unused_addr_ids/artifact_link_updates/
assumptions/blocking_issues/human_intervention_requested/autonomous_recoveryを保持する。
追加するdesign_change_requestsは通常[]。

関連付け1件の形式例（IDは実在値へ置換）：

```json
{"artifact_id":"PLAN-001","target_id":"FR-001","related_addr_id":"ADDR-001","requested_action":"LINK_ADDR","element_ids":["TASK-001"]}
```

artifact_idは受領manifestの成果物ID、element_idsはその文書が定義する実在FILE/TASK ID。
正本2章にも同じ設計パスまたは成果物IDとelement_idsを記載する。別対象へ一括関連付けしない。
全生成ADDRには少なくとも1件の明示的関連付けが必要。不要ならneeded=false、addr_id=null、
出力/関連付けは空とし、全未使用IDを返す。空のADDRは作らない。

SUCCESS_WITH_ASSUMPTIONSは根拠付きassumptionsを持つstatus=SUCCESS。
assumptionsはassumption_id/statement/basis_ids/affected_target_ids/reversible/verification_methodを保持する。
要件変更・安全性低下で仮定を成立させない。PARTIAL_SUCCESSはstatus=BLOCKED、FAILUREはFAILED。
復旧回数・上限は受領契約と共通台帳を維持し、人への承認待ちを標準動作にしない。

```text
python .github/skills/addr/scripts/validate_addr.py --final
```

## 実装引渡しと検査

親が--write-handoffを実行し、機械的にreports/addr/implementation-handoff.jsonを生成する。
Architecture資料は変更しない。handoffは入力ハッシュ・明示的関連付け・ADDR出力を束ねる派生成果物で、
新たな判断や設計本文は含めない。Agentが手で補完しない。
Quality/Security/Traceabilityをaudit_scope=ADDRで独立実行し、handoffハッシュへ結び付ける。
その後の--write-gateで実装引渡しGateを固定する。Architectureの検査結果をADDR検査へ流用しない。

正本状態はACTIVE/SUPERSEDED。ACTIVEだけでは実装可能でなく、実装引渡しGateを必要とする。
旧Accepted ADRは維持する。判断変更時は新ADDRと置換理由を返し、SUPERSEDEDへの下流参照を更新対象とする。
設計を変えない判断変更ならADDRから、設計資料を変えるならArchitectureから再開する。

## 共通ループと計測

初回失敗0＋修正/再検査1〜3で残れば未解決として親へ返し、継続判定で次工程へ進める。
検査FAIL/BLOCKEDをPASSへ変えず、既知原因を別工程の新しい3回ループにしない。
ADDRは独立主工程として時間・手戻りを記録する。同じ実験run_idを維持し、主工程記録は親が担当する。
