# Project AI Steering 見直し（AI-SDLC-Copilot）

## 目的

`project-ai-steering.md` をRequirements時点で作成する「プロジェクト固有の事前前提・制約」に限定し、Architecture / ADDR / Implementation以降で初めて確定する情報を先取りして記述させない。

## 変更範囲

- `.github/project-context/templates/project-ai-steering.md`：13章→8章。既定の技術スタック・開発環境・外部制約・指定済み規約・禁止事項・要件参照は維持。設計ID、ADR関連列、依存方向、詳細API/監視方式、後続工程でしか分からないコマンドの記載欄を削除。
- `.github/skills/requirements/SKILL.md`：Steeringの責務、記載の根拠、設計引継ぎ・未確認前提の区別を明示。12章参照を8.1節に更新。
- `.github/agents/requirements.agent.md`：設計の先取りを禁止し、Steering作成・引継ぎ責務を補強。
- `.github/copilot-instructions.md`：全Agent共通で、Steeringを事前条件に限定することを明示。
- `.github/agents/sdlc-orchestrator.agent.md`：Requirements工程でのSteering記載境界を明示。
- `.github/skills/unit-test/SKILL.md`：Steeringに未記載の場合、実際のリポジトリ設定からテストコマンドを確認するよう補正。
- `.github/skills/architecture/templates/implementation-task-list.template.md`：SteeringにBuild/Testコマンドがあることを前提としない表記へ補正（表列は維持）。
- `.github/skills/requirements/scripts/validate_requirements_structure.py`：Steeringの設計ID・後続工程生成パスの混入を検出。
- `.github/skills/requirements/scripts/test_validate_requirements_structure.py`：構造改訂・後続工程ID/パス排除の回帰テストを追加。

## 注意点

1. **この修正は `ai-sdlc-copilot-AI-traceability-full.zip` を基準にしています。** 直前のトレーサビリティ改善（C12、DR/IFR、Trace Map）はそのまま残しています。
2. 差分ZIPを展開する場合は、`ai-sdlc-copilot/` を既存リポジトリのルートに重ねて配置してください。既存の編集内容がある場合は先に差分確認・バックアップを推奨します。
3. 既に旧13章形式で生成した `.github/project-context/project-ai-steering.md` がある場合、構造Validatorの新しい正本に合わせて8章へ移行する必要があります。今回の配布はテンプレートとAgent/Validator更新であり、既存の生成済みSteeringを自動変換しません。
4. 技術スタックや既定制約が未指定なら、その項目に「指定なし」「未確認」を区別して記載します。後続の設計事項はSteeringの8.1節には混ぜず、入力対応記録・設計引継ぎに残します。
5. 実装後に判明した実際のBuild/Testコマンドは実行証跡や該当工程の成果物に記録し、Steeringへ後書きしません。

## テスト

2026-11-18実行（`python .../test_*.py -q`）：

| テスト | 結果 |
| --- | --- |
| Requirements structure | 45件 PASS |
| Architecture design split | 42件 PASS |
| Independent ADDR | 30件 PASS |
| Logical DB design | 14件 PASS |
| Traceability audit | 54件 PASS |
| Unit test validator | 44件 PASS |
| Integration test validator | 17件 PASS |

**合計：246件 PASS**。この7群以外の全体一括回帰テスト、実案件を入力にしたAgentの通し実行は今回実施していません。
