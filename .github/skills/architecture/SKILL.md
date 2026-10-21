---
name: architecture
description: >
  準備済み仕様を設計資料へ再構成し、独立したADDR工程へ一度引き渡す。
user-invocable: false
disable-model-invocation: false
---

# Architecture / Design Skill

## 責務と正本

| 正本テンプレート | 出力 | 条件 |
| --- | --- | --- |
| templates/file-definition.template.md | docs/architecture/files/FILE-xxx.md | ファイル連携がある場合 |
| templates/cross-artifact-consistency-analysis.template.md | reports/architecture/cross-artifact-consistency.md | 必須。Producerによる入力時点の分析 |
| templates/implementation-task-list.template.md | docs/architecture/implementation-task-list.md | 必須。新しい設計判断を含めない |

見出し・固定表列は維持する。必要な行・Taskブロックだけを展開する。
要件本文・UC/AC・Steering・提供済み設計仕様・有効な既存判断を根拠に記入する。
未提供の画面/API/DB等の専用テンプレートを追加せず、必要な不足は根拠と影響を返す。
仕様に一意な定型詳細は記入するが、重要方式の案比較・採否・理由・新しい実装拘束を決めない。
それらは独立したADDRの担当。ADDRや旧ADRを新規作成しない。

## Procedure

1. 分割要件の全リンク先、UC/AC、Steeringと準備済み仕様を読み、対象と根拠付き重要度を決める。
2. ファイル定義と実装タスクを既存テンプレートへ再構成する。該当しないファイル定義は作らず理由を記録する。
3. 重要判断が未定なら、候補キー・対象・根拠・判断が必要な理由だけをunresolved_design_decisionsへ記録する。
   候補方式を先回りして比較・選定しない。Taskで新しい方式や受入条件を作らない。
4. 整合性分析は現在の要件と設計資料を対象に作成する。ADDR未実施はその旨を記載し、
   Required ADRs AcceptedやImplementation Readinessを先取りしてYES/READYにしない。
   分析のFAIL/BLOCKEDは原文のまま保持し、未解決継続が必要なら共通3回ループへ返す。
5. version=2、stage=FINALのmanifestをreports/architecture/design-manifest.jsonへ出力する。
   DRAFT入力やFINALIZEは不要。FINALは「Architecture成果物の確定版」であり、重要判断完了を意味しない。
6. 構造Validatorを実行し親へ返す。独立Assurance・設計Gate・ADDR起動は親が担当する。

## Manifest

既存version=1と同じsources/artifacts/targets/unresolved_design_decisionsを持ち、versionだけ2とする。
sourcesは要件索引・全リンク先・Steering・参照した既存設計/判断の実SHA-256を固定する。
source_revision、target_id、criticality（MANDATORY/OPTIONAL）、basis_idsは必須。
artifactsはartifact_id/path/template/sha256/target_id/related_requirement_ids/related_addr_idsを持つ。
templateはfile-definition / cross-artifact-consistency-analysis / implementation-task-list / provided。
providedは本当に受領した他設計資料だけで、sourcesへも登録する。
task一覧は1件、整合性分析は1件必須。FILEのFile Interface IDとTASKの実在ID・依存・Waveを保持する。
新規ADDRはまだないので将来IDを予約・推測して関連欄へ記入しない。既存判断だけを参照する。
新規ADDRとの関連付けは後続ADDRの正本2章と機械可読結果に記録し、派生handoffで接続する。
design_input_sha256は付けない（自己参照/DRAFT依存を作らない）。

```text
python .github/skills/architecture/scripts/validate_design.py --stage final
```

## Gateと修正

Quality/Security/TraceabilityはARCHITECTURE Scopeで現在の資料の品質を独立検査する。
Producerの整合性分析をそのまま独立検査のPASS証拠にはしない。同じ分析文書を上書きしない。
設計GateはADDRへの引渡しを固定し、Implementation開始許可とは区別する。

ADDRから設計本文・Taskの具体的修正が要求されたときだけ、親がArchitectureへ差し戻す。
要求された資料だけを修正し、ADDR本体を編集しない。新manifest/Assurance/設計Gateを作り、
旧ADDR入力・handoff・実装引渡しGateと影響する後続結果を無効化する。
参照を追加するだけのために通常FINALIZEを行わない。

## 共通ループ・トレーサビリティ・計測

初回失敗0＋実修正/再検査1〜3で残ればFAIL/BLOCKEDと影響を親へ返す。PASSに偽装せず4回目を開始しない。
正本の既存ID欄を使用し、Trace専用章やFQN欄を追加しない。表はAuditorが派生生成する。
実験run_idを維持する。Architecture/ADDRは独立主工程で、開始・終了・実際の手戻りは親が記録する。
