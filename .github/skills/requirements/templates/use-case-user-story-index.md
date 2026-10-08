# ユースケース／ユーザーストーリー一覧

<!--
目的:
- 誰が、どのような価値・目的のためにシステムを利用するかを一覧化する。
- 詳細フローや受入条件を一覧へ重複記載せず、個別ユースケースへ参照させる。
- Requirement、User Story、Use Case間の安定した参照関係をSource Artifactとして保持する。

記入ルール:
- User Storyは US-xxx、Use Caseは UC-xxx、Actorは ACT-xxx の一意IDを付与する。
- 詳細フロー・Acceptance Criteriaは個別ユースケースファイルへ記載する。
- 存在しないRequirement IDを推測して作成しない。
- 未確定事項はOpen Questionsへ記録する。
-->

## 1. 文書情報

| 項目 | 内容 |
| --- | --- |
| 文書ID | `<DOC-UCUS-INDEX-001>` |
| 対象システム | `<システム名>` |
| バージョン | `<1.0>` |
| ステータス | `DRAFT / REVIEW / APPROVED` |
| 作成日 | `<YYYY-MM-DD>` |
| 最終更新日 | `<YYYY-MM-DD>` |

## 2. アクター／利用者ロール

| Actor ID | アクター／ロール名 | 説明 | 主な目的 | 関連Requirement ID |
| --- | --- | --- | --- | --- |
| ACT-001 | `<名称>` | `<利用者・外部システム等>` | `<達成したいこと>` | `<FR-001, ...>` |

## 3. ユーザーストーリー一覧

| User Story ID | タイトル | Actor ID | Story | 価値／目的 | 関連Requirement ID | 関連Use Case ID | 優先度 | ステータス |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| US-001 | `<タイトル>` | ACT-001 | `As a <role>, I want <goal>, so that <value>.` | `<価値>` | `<FR-001>` | `<UC-001 / None>` | `HIGH / MEDIUM / LOW` | `DRAFT / READY / DONE` |

## 4. ユースケース一覧

| Use Case ID | タイトル | Primary Actor | 目的 | 関連Requirement ID | 関連User Story ID | 詳細ファイル | 優先度 | ステータス |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| UC-001 | `<タイトル>` | ACT-001 | `<達成したい目的>` | `<FR-001>` | `<US-001 / None>` | `./use-cases/UC-001_<name>.md` | `HIGH / MEDIUM / LOW` | `DRAFT / READY / DONE` |

## 5. 未確定事項

| Question ID | 関連US/UC ID | 内容 | 影響 | 決定者／確認先 | 状態 |
| --- | --- | --- | --- | --- | --- |
| OQ-UCUS-001 | `<UC-001>` | `<未確定事項>` | `<影響範囲>` | `<担当>` | `OPEN / RESOLVED` |
