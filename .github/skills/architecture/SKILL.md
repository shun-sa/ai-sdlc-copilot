---
name: architecture
description: >
  分割要件と既存設計テンプレートから設計成果物を作成し、未確定判断をADDRへ渡し、
  確定差分と実装タスクを整えて実装へ引き継ぐ。
user-invocable: false
disable-model-invocation: false
---

# Architecture / Design Skill

## 実験Runの計測

親から渡されたrun_idを維持する。PREPARE/FINALIZEの開始・終了とADDR委譲は
Orchestratorが観測記録するため、本Skillは別Runや主工程の遷移を作らない。
各operationの実結果と中断・待機・差し戻し理由を親へ返す。設計/ADDRの正本とGateは変更しない。
詳細は `docs/ai-sdlc/experiment-measurement.md`。

## 正本と責務

| テンプレート | 出力 | 作成者 |
| --- | --- | --- |
| `templates/file-definition.template.md` | `docs/architecture/files/FILE-xxx.md` | Architecture。ファイル連携がある場合 |
| `templates/implementation-task-list.template.md` | `docs/architecture/implementation-task-list.md` | Architecture。FINALIZEで必須 |
| `templates/cross-artifact-consistency-analysis.template.md` | `reports/architecture/cross-artifact-consistency.md` | Quality Review / Assurance |

正本の見出し・階層・固定表列を維持し、記入欄と必要な行・Taskブロックだけを展開する。
ファイル連携がない場合はファイル定義を捏造せず、対象・理由をmanifestに記録する。
構成図、データモデル、画面・API等は提供済み仕様・既存成果物を参照する。
今回のZIPにこれら専用の設計テンプレートは存在しない。未提供の必須仕様・テンプレートを
架空の標準として追加せず、未確定事項と不足成果物を親へ返す。

重要判断と差分はADDR Agentの担当である。旧ADRを新規量産しない。
有効な旧Accepted ADRは履歴と制約として読み、ADDRと矛盾すれば親へ返す。
要件・UC/ACが正、設計は実現仕様、ADDRは重要判断の正本、Taskは作業計画である。
ADDRを設計書・実装タスクの代わりにしない。

## PREPARE

1. 要件索引の全リンク先、UC/AC、Steering、既存設計、現行判断を読む。
2. 対象と重要度を根拠から決める。MANDATORYは隔離すると受入不能、OPTIONALは独立して除外可能な対象。
   根拠がなければ重要度を推測せずBLOCKEDとする。任意の機能縮退で受入条件を変えない。
3. 指定済み・一意に導出可能な設計を書き、重要な未確定方式を候補として切り出す。
4. 必要なファイル定義をテンプレートで作成し、未決はOpen Questionsへ記録する。
5. 下記manifestをDRAFTで `reports/architecture/design-input.json` へ保存する。
   出典は要件索引・リンク先・Steering・参照した旧ADR等をSHA-256で固定する。

```json
{
  "version": 1,
  "stage": "DRAFT",
  "source_revision": "入力版またはcommit",
  "sources": [{"path": "docs/requirements/requirements.md", "sha256": "実ファイルのSHA-256"}],
  "artifacts": [{"artifact_id": "FILE-001", "path": "docs/architecture/files/FILE-001.md", "template": "file-definition", "sha256": "実SHA-256", "target_id": "FR-001", "related_requirement_ids": ["FR-001"], "related_addr_ids": []}],
  "targets": [{"target_id": "FR-001", "criticality": "MANDATORY", "basis_ids": ["FR-001"]}],
  "unresolved_design_decisions": [{"candidate_key": "file-retry", "target_id": "FR-001", "topic": "再送方式", "related_requirement_ids": ["FR-001"], "candidate_options": [], "reason_unresolved": "要件から方式が一意に決まらない"}],
  "not_applicable": []
}
```

上記は形式例であり、ID・ハッシュ・判断・配列は実資料で置換する。
artifactsのtemplateは `file-definition / implementation-task-list / provided`。
providedは提供済みの他設計仕様で、出典sourcesにも同じパスを記録する。
新規に推測して作った設計書をprovidedとして登録しない。
候補がなくても空配列を渡す。ADR/ADDRやコードはartifactsとして新規作成しない。
テンプレート内のADR列は互換欄としてADDR IDも格納できる。列名は変更しない。

```text
python .github/skills/architecture/scripts/validate_design.py --stage draft
```

## FINALIZE

1. Orchestratorが返すADDR結果とLINK_ADDR要求を読む。前工程の入力manifestは変更しない。
2. 同一入力版の重要判断だけを反映し、設計書の参照欄へADDR IDを追加する。
   決定内容はADDR参照とし、物理仕様として必要な値のみ設計書へ具体化する。
3. Taskテンプレートで全実装対象を計画する。Task Summary・Details・Wave・Coverageを照合する。
   依存Taskは実在し循環しないこと。Taskで新たな重要判断や受入条件を作らない。
4. 未確定判断が増えればADDR_REQUIREDで返す。通常の局所的設計を全件ADDR化しない。
5. 全入力sourcesを維持し、最新成果物のハッシュ・関連ADDRを持つFINAL manifestを
   `reports/architecture/design-manifest.json` へ保存する。`design_input_sha256` にDRAFT manifestの
   SHA-256を記録する。DRAFT成果物の旧ハッシュは入力履歴として保存し、FINALに最新値を記録する。
6. 全体を検証して親へ返す。実装計画の初期進捗は未着手。実行中の進捗は別Reportへ記録し、
   Gateで固定した設計・計画を無断更新しない。

```text
python .github/skills/architecture/scripts/validate_design.py --stage final
python .github/skills/addr/scripts/validate_addr.py
```

重大な未決・入力の変化・不整合はBLOCKED、生成・検証失敗はFAILED。
内容の意味的整合、設計不足、Scope、セキュリティは既存Assuranceが評価する。
構造PASSとProducer SUCCESSだけで実装へ進めない。

# Inline Traceability

PREPARE/FINALIZEの責務・正本テンプレート・manifest・Gateは維持します。
作成時に既存の関連要件/ADR欄へ実在IDを記入し、FILEの「File Interface ID」を保持します。
Task Summary/Detailsの関連要件・ADDR/DBD根拠を一致させ、TASKだけを設計根拠にしません。
提供済みDB論理設計がある場合はそのDBDを使用し、未提供のテンプレートは作りません。
ADDR文書はADDR Agentが作成します。正本外のTraceability専用章やFQN欄を設計書へ追加しません。
Trace Map/表はAuditorの派生成果物です。手編集での維持は行いません。

## 共通3回ループ

修正・再検査は `docs/ai-sdlc/bounded-repair-loop.md` に集約します。
初回失敗0＋実修正1〜3の後も残る場合、FAIL/BLOCKEDを維持して親へ未解決として返し、
親が履歴・影響を記録して次工程への継続を許可します。4回目を自己開始しません。
未解決継続を品質SUCCESS/PASSへ変換せず、原因を隠す修正・捏造・削除・skipをしません。
