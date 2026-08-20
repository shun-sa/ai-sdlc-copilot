---
name: architecture
description: >
  要件定義成果物から重要なArchitecture Decisionを抽出し、
  プロジェクト標準の軽量ADR形式で設計判断を作成・更新するSkill。
  設計工程、ADR候補の抽出、設計選択肢の比較、
  Related Requirementsによる要件トレーサビリティ設定、
  AI Guardrailsの定義を行う場合に使用する。
user-invocable: false
disable-model-invocation: false
---

# Architecture Skill

## Purpose

このSkillは、
要件定義成果物から重要な設計判断を抽出し、
Architecture Decision Record（ADR）として
記録するための手順を定義します。

本プロジェクトでは、
設計工程の正式な成果物をADRに限定します。

ADRは詳細設計書ではありません。

AIが後続工程において
誤った設計・実装判断を行わないようにするための
軽量な設計判断記録として作成してください。


# Canonical ADR Template

ADRを作成または更新するときは、
必ず以下を使用してください。

`.github/skills/architecture/templates/adr-template.md`

Canonical ADR Templateの構造を
Skillの判断で変更してはいけません。


# Fundamental Rules

以下を常に守ってください。

1. 設計成果物はADRのみとする
2. ADRが不要な判断を無理にADR化しない
3. 1つのADRには1つの重要判断だけを記録する
4. ADRは要件を根拠として作成する
5. Related Requirementsを必ず確認する
6. 採用案だけでなく重要な代替案も確認する
7. DecisionからAI Guardrailsを導出する
8. Accepted ADRの履歴を失わない
9. ADRを詳細設計書化しない


# Procedure

## Step 1. 要件定義成果物を確認する

設計対象に関連する以下を確認してください。

- 機能要件（FR）
- 非機能要件（NFR）
- 認証・認可
- エラー仕様
- データモデル
- 制約条件
- Out of Scope
- Acceptance Criteria

設計判断を要件から切り離して行ってはいけません。


## Step 2. 既存ADRを確認する

新しいADRを作成する前に
既存ADRを確認してください。

特に以下を確認します。

- Accepted ADR
- Proposed ADR
- Superseded ADR
- 同じ判断を扱うADR
- 関連要件を扱うADR

同じ設計判断について
重複ADRを作成しないでください。


## Step 3. ADR候補を抽出する

要件から設計上の判断が必要となる事項を抽出してください。

以下に該当する場合、
ADR候補として扱います。

1. 複数案が存在する
2. 後から変更すると高コスト
3. 非機能要件に影響する
4. AIの誤判断による手戻りが大きい
5. 複数の後続成果物に影響する


## Step 4. ADR化の必要性を判定する

各候補について
本当にADRが必要か確認してください。

以下のようなものは
原則としてADR化しません。

- 入力項目
- 表示文言
- 単純なバリデーション
- 細かな画面配置
- 単純なCRUD
- 一時的な実装都合

軽微な判断を大量にADR化してはいけません。


## Step 5. Related Requirementsを特定する

ADRの判断根拠となるRequirement IDを特定してください。

参照可能な例:

- FR-xxx
- NFR-xxx
- SEC-xxx
- CON-xxx

ただし、
Requirements成果物に存在しないIDを
新しく作成してはいけません。

現在FR/NFRのみがID管理されている場合は、
存在するFR/NFRを使用してください。

関連要件が1件も存在しない場合、
その設計判断が本当に必要か再確認してください。


## Step 6. 設計判断のContextを整理する

以下を簡潔に整理してください。

- なぜ判断が必要か
- どの要件が関係するか
- どの制約が関係するか
- 何が問題となっているか

Contextは原則3〜5行程度としてください。


## Step 7. 選択肢を洗い出す

現実的な設計選択肢を確認してください。

必要以上に選択肢を増やしてはいけません。

Alternativesは原則最大3案とします。


## Step 8. 選択肢を比較する

各選択肢について、
関連要件および制約を基準として比較してください。

一般論だけで決定してはいけません。

例えば以下を確認します。

- FRへの適合
- NFRへの適合
- 制約への適合
- 将来の変更コスト
- 実装への影響
- 運用への影響
- AIによる誤判断リスク


## Step 9. Decisionを決定する

比較結果をもとに
採用する判断を明確にしてください。

Decisionは、
後続AIが再度同じ設計判断を行う必要がない程度に
明確である必要があります。


## Step 10. Consequencesを整理する

採用した判断によって発生する影響を整理してください。

最低限以下を確認します。

- 良い影響
- 悪い影響
- 後続工程への影響

メリットのみを記載してはいけません。


## Step 11. AI Guardrailsを作成する

Decisionから、
後続AIが守るべき制約を抽出してください。

AI Guardrailsでは特に以下を明示します。

- AIが必ず守ること
- AIが提案してはいけないこと
- AIが省略してはいけないこと

最大3項目を目安としてください。

一般的なコーディング規約ではなく、
当該ADR固有のGuardrailを記載してください。


## Step 12. ADRを作成する

Canonical ADR Templateを使用してください。

ADR IDは既存ADRを確認したうえで
未使用番号を採番してください。

ファイル名は以下を基本とします。

`ADR-xxx-<short-title>.md`

配置先:

`docs/adr/`


## Step 13. Statusを設定する

新規ADRは原則として
Proposedとしてください。

Architecture Agent自身の判断で
Acceptedへ変更してはいけません。

SDLC Orchestratorから
Assurance工程PASSの情報を受け取った場合のみ
Acceptedへ変更してください。


## Step 14. トレーサビリティを確認する

各ADRについて、
Related Requirementsが正しいことを確認してください。

最低限以下を確認します。

- Requirement IDが存在する
- Requirement IDが重複していない
- 判断とRequirementに関係がある
- 無関係なRequirementを付与していない

Architecture Skillは
Implementation IDやTest IDを作成してはいけません。


## Step 15. ADR間の整合性を確認する

新しいDecisionが
既存Accepted ADRと矛盾していないことを確認してください。

矛盾が存在する場合は、
既存ADRを直接書き換えて解消してはいけません。

必要に応じて新しいADRとして判断を記録します。


## Step 16. ADR変更を処理する

Accepted ADRの判断自体が変更された場合は、
新しいADRを作成してください。

新しいADRがAcceptedになった後、
古いADRをSupersededとしてください。

設計判断履歴を削除してはいけません。


## Step 17. Completion Checkを行う

ADR作成後、以下を確認してください。

- ADR化すべき判断を見落としていない
- ADR化不要な判断を大量にADR化していない
- 1 ADR = 1 Decisionになっている
- Related Requirementsが存在する
- Decisionが明確である
- Alternativesが適切である
- Consequencesが記録されている
- AI Guardrailsが具体的である
- 既存ADRと矛盾していない
- ADRが過度に長くなっていない
- Canonical ADR Templateに従っている


# ADR Size Guidelines

ADRは軽量にしてください。

原則:

- ADR全体は50行以内
- Contextは3〜5行程度
- Alternativesは最大3案
- Consequencesは必要最小限
- AI Guardrailsは最大3項目

この目安を超える場合は、
複数の独立した設計判断を
1つのADRに含めていないか確認してください。


# Traceability Rules

ADRとRequirementの関連は
ADRのRelated Requirementsを正とします。

Requirement IDを変更してはいけません。

Requirements成果物に存在しないIDを
Architecture Skillが生成してはいけません。

ADR側からRequirementへのリンクを必須とし、
後続のTraceability Auditorが
その整合性を検証できる状態にしてください。


# Output

処理完了後、
Architecture Agentへ以下を返してください。

- 作成したADR
- 更新したADR
- Superseded候補ADR
- ADRごとのRelated Requirements
- ADR化しなかった主要な判断と理由
- ASSUMPTION
- BLOCKED事項
- 既存ADRとの矛盾確認結果
- ADR構造確認結果