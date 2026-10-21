---
name: requirements
description: >
  準備済み資料を棚卸しし、既存の分割テンプレートとProject AI Steeringに沿って
  要件定義成果物を再構成・更新・検証する。
user-invocable: false
disable-model-invocation: false
---

# Requirements Skill

## Purpose

大半の入力が準備済みであることを前提に、入力の分類・対応付け・再配置を行う。
資料を確認する前に質問を繰り返さない。不足や矛盾だけを抽出し、
既存資料で解決できない重大事項をまとめてOrchestratorへ返す。

## 正本と出力先

構造の正本は以下の実在するテンプレート群である。本文・記入ガイドも毎回読む。
テンプレートは本Skill相対、出力先はリポジトリルート相対である。

| 正本 | 出力先 | 内容の責務 |
| --- | --- | --- |
| `templates/business_requirements.md` | `docs/requirements/business_requirements.md` | 背景・目的・範囲・課題・業務ルール |
| `templates/functional_requirements.md` | `docs/requirements/functional_requirements.md` | 機能一覧・権限・詳細・共通機能・状態遷移 |
| `templates/non_functional_requirements.md` | `docs/requirements/non_functional_requirements.md` | 品質条件・目標値・測定条件・検証方法 |
| `templates/data_requirements.md` | `docs/requirements/data_requirements.md` | 論理データ・項目・コード・保存・移行 |
| `templates/external_interface_requirements.md` | `docs/requirements/external_interface_requirements.md` | 連携先・IF・責任分界・運用上の要求 |
| `templates/ui_report_requirements.md` | `docs/requirements/ui_report_requirements.md` | 画面・帳票・通知の要求と概略 |
| `templates/use_case_user_story_list.md` | `docs/requirements/use-case-user-story-index.md` | Actor・US・UCと要求の関連 |
| `templates/use_case_detail.md` | `docs/requirements/use-cases/<UC ID>.md` | UCごとのフロー・AC・合否判定基準 |
| `templates/glossary.md` | `docs/requirements/glossary.md` | 用語・同義語・非推奨表記 |
| `templates/requirements_quality_checklist.md` | `docs/requirements/requirements_quality_checklist.md` | 人レビューの準備・提供済みレビュー記録 |
| `../../project-context/templates/project-ai-steering.md` | `.github/project-context/project-ai-steering.md` | PJ固有の事実・制約・参照先・未決判断 |

正本ファイルは編集しない。見出しの名称・順序・階層と固定の表列を維持する。
ガイドが許す行の増減、繰り返しブロックの複製・連番化、権限表のActor列増減は許可する。
非機能要件の代表項目は削除せず、非該当は理由付きで「該当なし」とする。
外部IFがない場合は1.3に「なし」と判断根拠を記載し、2〜7章の見出しと該当なしの表を残し、
5章の繰り返しブロックを削除する。その他も未適用の章を勝手に削除しない。

## 内容の根拠

構造の正本と要求内容の根拠を区別する。内容は、明示された変更要求、起動ファイル、
提供資料、承認済み既存要件、その他の仕様の順に照合する。矛盾は黙って上書きせず記録する。
背景・目的・対象者・Scope外・PJ全体の成功条件・制約を保持する。
起動ファイルや承認済みPJ情報の変更が必要ならchange_requestsで返す。
コードは現状確認にのみ使い、要求や期待結果の根拠にしない。

## 手順

### 1. 入力を棚卸しする

Orchestratorから要求、入力ファイルのパス・版、起動ファイル、既存成果物、対象範囲を受け取る。
リポジトリ内の関連資料も検索する。読めない指定資料は不足として記録する。
要求・制約・用語・フロー・数値・既存ID・未決事項を抽出し、
`reports/requirements/input-mapping.md` に以下の列を持つ作業記録を作る。

| 入力Path・版・箇所 | 入力IDまたは要点 | 出力Path・章・ID | 処理 | 根拠・理由 |
| --- | --- | --- | --- | --- |

処理は「再配置／既存参照／重複整理／対象外／未決／矛盾」。入力の取りこぼしと出典のない追加を
双方向に確認する。対象外・重複として省いた情報にも理由と参照先を残す。

### 2. 用語・IDを保持して再構成する

上表へ内容を割り当て、旧成果物からの移動先を作業記録に残す。
新規機能・非機能要件には既存連携に合わせFR-001、NFR-001等を用いる。
既存の別形式IDは付け替えず、削除IDを再利用しない。
Actor/US/UC/AC等も参照可能な一意のIDで管理し、参照の反復と重複定義を区別する。
後続工程の設計ID・テストIDは生成しない。

業務要件・用語、機能・非機能・データ・IF・画面帳票、US/UC一覧・UC詳細の順に整理する。
機能一覧の全機能に対応する6章の詳細と5章の権限を作る。
UC一覧の全UCについて1UC1ファイルで詳細を作り、関連する実在要求IDを記載する。
UCがない場合も一覧に理由を残し、空のUC詳細を捏造しない。

各テンプレートの責務を守る。論理型・桁・形式はデータ要件、機能の振る舞いは機能要件、
画面帳票の概略は画面帳票要件へ置く。旧来の一律の設計境界で、許容される具体性を削らない。
物理DB・クラス・実装方式・新たな技術判断は後続工程へ渡し、指定済み技術制約は根拠付きで保持する。
AC / Pass-Fail RuleはUC詳細を正本とし、独立した手入力AC一覧へ複製しない。
テンプレートが直接記載を要求する業務ルール・数値は省略せず、出典と重複箇所の値を照合する。

### 3. Steeringとレビュー準備を整える

AI Steeringは上表の実体ファイルへ作成・更新する。提供済みの技術・配置・規約・コマンドだけを整理し、
未採用の技術や設計判断を補完しない。参照先は実在パスにする。
要求本文・AC・Agent手順・Routing・Validator実行方法をSteeringへ複製しない。
未決は12章に登録し、関連Requirement/ADR/Ownerへの解決先を示す。

仕様品質チェックリストは人レビュー用である。提供済み記録は実施者・対象版とともに保持する。
未実施の人レビューを実施済みにせず、判定不能はBLOCKEDと理由・確認先を記録する。
Agentの自己確認やAssurance結果は別の実行結果に記録する。
人レビュー待ちだけでAgent作業を止めないが、人承認が明示的なGateならOrchestratorへ返す。

### 4. 互換索引を作成する

`docs/requirements/requirements.md` は既存Agent/Validator向けの派生索引とする。
要求本文を二重管理せず、上表の全文書・全UC詳細・SteeringへのMarkdownリンクを置く。
機能一覧と非機能要件表の全IDを、それぞれ次の形式で1回ずつ列挙する。

```markdown
# Requirements Index

## 成果物
- [機能要件](functional_requirements.md)

## 機能要件
- FR-001: [名称](functional_requirements.md#6-機能詳細)

## 非機能要件
- NFR-001: [名称](non_functional_requirements.md#4-可用性)
```

上記は形式例である。実際には全成果物・全IDを掲載する。ID一覧にUS/UC/AC等を混在させない。
後続Agent/Assuranceには索引だけでなく分割文書・UC詳細・Steering・未決事項を渡す。
`features/` 等の旧成果物は入力として読み、並行する正本として新規生成しない。
既存資料を勝手に消さず、廃止候補と移動先を報告する。

### 5. 不足・矛盾を分類する

- RESOLVED: 客観的根拠で解決。出典と解決内容を記録する。
- ASSUMPTION: 影響が限定的。仮定・理由・影響・確認先を記録する。
- BLOCKED: 重要な振る舞い・権限・合否条件・Scope等が未確定または矛盾し、後続へ渡せない。

未該当と情報不足を区別する。非該当は「該当なし」と理由、情報不足は「未決」とし、
各文書の未決事項欄へ登録する。空欄や生のプレースホルダーを残さない。
重大な未決があっても確定済みの範囲は再構成する。数値・Actor・ACを推測で確定しない。

### 6. 検証して返却する

リポジトリルートで実行する。別ルートは `--root <repository-root>` を指定する。

```text
python .github/skills/requirements/scripts/validate_requirements_structure.py
```

実テンプレートから構造を導出し、分割文書・Steering・ID・UC参照・派生索引を検証する。
意味の妥当性、出典の十分性、数値の根拠、未決の重大性、人レビュー完了は機械検証の対象外であり、
本Skillの照合とAssuranceで確認する。構造PASSだけでSUCCESSにしない。
成果物、FR/NFR変更、入力対応、RESOLVED/ASSUMPTION/BLOCKED、変更要求、
実行コマンド・終了コード・検証結果をRequirements Agentへ返す。
重大な未決ならBLOCKED、構造不正・処理失敗ならFAILED、再構成・照合・検証完了ならSUCCESS。
工程のPASSと遷移はOrchestratorが決める。
