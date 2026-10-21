# ArchitectureとADDRの独立工程

## 通常順序

Requirements → Architecture → ADDR → Implementation → Unit Test → Integration Test → Final Assurance。
ArchitectureとADDRはOrchestrator直下の対等な専門Agentである。
Architectureの中でADDRを実行したり、通常経路でArchitectureのFINALIZEを再実行したりしない。

## 重複させない責務

| 対象 | Architecture | ADDR |
| --- | --- | --- |
| 既存仕様の再構成・ファイル項目表 | 作成する | パス/IDで参照。表全体を複製しない |
| 成果物間整合性分析 | 現在の入力時点の資料を作成する | 同じ分析資料を再作成しない |
| 実装タスク・依存・Wave・検証方法 | 根拠のある作業計画として作成する | Taskを再定義しない |
| 重要判断の必要箇所 | 場所・対象・根拠を渡すだけ | 全対象で要否と理由を確認する |
| 重要方式の選択肢・比較・採否・理由 | 新しい判断をしない | 唯一の作成者 |
| DD/INV/ASM・判断から生じる実装拘束 | 新規に決めない | 正本ADDRの既存欄に記録する |
| 設計本文を変える必要 | 自分の資料だけ修正する | 直接編集せず具体的変更要求を返す |
| 実装可能性・独立品質検査 | 自己分析だけで許可しない | ACTIVEだけで許可しない |

Architectureの出力は既存テンプレートのfile-definition（該当時）、
cross-artifact-consistency-analysis、implementation-task-listである。
未提供の設計種別のテンプレートは追加せず、提供済み仕様を参照する。
ADDRの出力は既存ADDRテンプレートの1〜9章と対応design_type節で、設計資料の丸写しではない。
既に要件・受領仕様で一意に決まる内容に、比較案や新しい判断を捏造しない。

整合性分析はArchitecture Producerの資料であって独立合格証拠ではない。
Quality/Security/Traceabilityは別の検査結果を作る。Qualityは同じ分析ファイルを上書きしない。
ADDR前の分析では未実施判断を明示し、Required ADRs Acceptedや実装Readinessを先取りしてYES/READYにしない。
Architectureの品質検査は資料の品質とADDRへの引渡し準備を対象にし、実装開始許可と区別する。
ADDR後のQualityは全設計・Task・判断の最終整合と重複/不足を独立検査する。

## 新規Runの入力契約

Architectureはversion=2 / stage=FINALのreports/architecture/design-manifest.jsonを一度出力する。
このFINALはArchitecture資料の公開版であって、全ての判断の完了ではない。
sources（要件索引・全リンク先・UC/AC・Steering・受領仕様・参照済み判断）、
artifacts、targets（対象・根拠付き重要度）、unresolved_design_decisionsを実ファイルのハッシュで固定する。
unresolved_design_decisionsは後続ADDRへの委譲事項として残せるが、TaskやFILEの重要方式を推測して確定しない。
重要方式がなくても根拠付き空配列で渡す。架空の将来ADDR IDは設計書へ書かない。

artifactsのtemplateはfile-definition / cross-artifact-consistency-analysis /
implementation-task-list / provided。実装タスクと分析資料は各1件必須。
providedは実際の受領資料だけでsourcesにも同じパスを記録する。
各成果物はartifact_id/path/template/sha256/target_id/related_requirement_ids/related_addr_idsを持つ。
例えばPLAN-001はTask一覧という成果物IDで、TASK-001は文書内に定義する個別Task IDである。
両者を混同しない。Taskは根拠と検証方法を整理し、実装時に後続ADDRも読むことを明示する。
version=2に旧design_input_sha256を付けず、DRAFT/FINALIZEの自己循環を作らない。

## 2段階のGate

1. validate_design.py --stage finalで構造・出典・Task依存を検証する。
2. ARCHITECTURE Scopeで3つのAssuranceとValidatorを実行する。
   各source_baseline_sha256はFINAL manifestのSHA-256。
3. validate_design.py --write-design-gateでreports/architecture/design-gate.jsonを固定する。
   設計資料と検査結果の固定コピーを持ち、未来の新規ADDRを待たずに成立する。
4. ADDR工程でvalidate_addr.py --prepare-requestを実行し、予約ID・入力版を渡す。
5. ADDRが判断・明示参照・必要時の設計変更要求を返す。validate_addr.py --finalで検証する。
6. validate_addr.py --write-handoffでreports/addr/implementation-handoff.jsonを機械生成する。
   設計manifest/設計Gate/ADDR結果のハッシュ、明示参照と出力を束ねるだけで、新しい設計判断を生成しない。
7. ADDR Scopeで3つのAssuranceとValidatorを実行する。baselineはhandoffのSHA-256。
8. validate_addr.py --write-gateで実装引渡しGateを固定する。
   互換パスreports/architecture/architecture-gate.json、phase=ADDRである。
9. Implementationはvalidate_design.py --check-gateで実装引渡しを確認し、設計・Task・ADDRを読む。

保存場所の互換性のためaddr-request.json / addr-result.jsonはreports/architectureに残す。
これは旧版の保存パスであり、ADDRがArchitecture内の子工程であるという意味ではない。
ADDR requestのdesign_input_pathはFINAL manifest、workflow_version=2。
既存フィールドdesign_input_sha256には受領FINAL manifestの実ハッシュを保持する。

## 設計書を書き戻さず参照を成立させる

ADDRの正本2章へ実在要件、設計パスと影響するFILE/TASK IDを記載する。
同じ明示参照をaddr-resultのartifact_link_updatesへ保存する。

```json
{
  "artifact_id": "PLAN-001",
  "target_id": "FR-001",
  "related_addr_id": "ADDR-001",
  "requested_action": "LINK_ADDR",
  "element_ids": ["TASK-001"]
}
```

形式例のIDは実在値に置き換える。リンクは同じ対象の凍結成果物と新規ADDRを結び、
element_idsは当該文書で定義するID、かつADDR正本2章にも明示したIDだけにする。
全生成ADDRに関連付けを持たせる。plan全体への関連付けから全Taskを推測して結ばない。
Auditorは設計Gate・ADDR結果・handoffの整合を検証してこの明示参照から表を派生生成する。
凍結設計書へ将来IDを自動追記しないので、参照追加だけを理由とするFINALIZEは不要。
ADDR不要は正常終了で、全未使用IDとneeded=falseを返し、空の文書やリンクを強制作成しない。

## 実際に修正が必要な場合

- 重要判断の不備だけならADDR内で修正する。Implementationで判断不足を検出した場合もADDRへ戻す。
- FILE本文、項目値、異常動作、Task本体などを変えるなら、ADDRはdesign_change_requestsへ
  artifact_id/対象/根拠/必要変更を記載しBLOCKEDで返す。ADDRは設計資料を直接編集しない。
- OrchestratorがARCHITECTUREへ実際に戻し、担当資料だけを修正する。
  新manifest/設計Assurance/設計Gateに更新し、ADDR入力・handoff・実装引渡しGateと影響下流を無効化する。
  判断そのものはADDRが新入力へ照合する。単なる参照追加と本文修正を混同しない。
- 未公開の旧ADDR候補は履歴へ退避してから予約を更新する。旧入力版の候補を公開判断として流用しない。
- 既存Accepted ADRは履歴・制約として維持し、新規判断を旧ADRへ二重生成しない。

## 3回ループと計測

ARCHITECTUREとADDRは別々の必須Check集合を持つ。元品質FAILを保持したまま、
同一原因の初回失敗0の後に実修正・再検査を3回行い、残件を未解決として継続する。
独立工程化や差し戻しでissue ID・原因signature・修正回数をリセットしない。
実行不能な資料・検査は理由を残し、品質Gateを偽装しない。
設計Gateが成立しないままprepare-request/handoff/Gateが失敗する場合もその事実を記録する。

実験計測は同じrun_idでARCHITECTURE→ADDR→IMPLEMENTATIONをenterする。
ADDRは独立工程時間に含み、設計→最後の結合試験終了の主区間にも含む。
ADDR→ARCHITECTURE、Implementation→ADDR等を出発/戻り先別に手戻り計数する。
Validator/Assuranceだけを親内の子活動にし、ADDRを子活動として二重計測しない。
旧RunのADDR子活動を後から独立工程へ再分類・時刻推定しない。

## 旧版互換と適用

version=1の旧DRAFT→ADDR→FINALIZE成果物とGateは読取り・検証互換のため残す。
新規Runは必ずversion=2を使い、通常のOrchestrator経路に旧版操作を戻さない。
実行中の旧Runを途中でこの版へ差し替えず、バックアップし新規Runから適用する。
要件/ADDR/ファイル定義/Taskのテンプレート構造は維持する。
整合性分析テンプレートは作成者・独立検査との区別をコメントだけ更新し、見出し/固定列は変更しない。
