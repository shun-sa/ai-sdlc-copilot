# AI-SDLC-Copilot トレーサビリティ改修差分（2026-11-18）

対象はAI駆動開発のみです。従来開発・設計書なしのPolicyとAgentは追加していません。

## 内容
- 既存C01〜C11とTrace Map v3を維持し、C12を追加。実装対象FR全件のコード到達、コード注釈から要件への逆引き、独立分母FR一覧の記載漏れ・重複・未定義をFAIL検出。
- 実装対象一覧 `docs/requirements/expected-fr.txt` はRequirements Agentが承認済み正本から新規作成する。実装対象外は `EXCLUDE FR-nnn: 承認済み理由` に分類。提出ZIPにはサンプル案件のFRがないため実体は同梱していない。
- `trace-map.json` に `sources[].resolved_requirements` / `sources[].resolved_fr` を追加。テストでは実際の要件IDのみを検証対象にする（ADDRだけからFRテスト済みにはしない）。
- `DR-nnn` / `IFR-nnn` を要件主IDの標準とし、テンプレート・Requirements Agent/Skill・構造Validator・設計テンプレートを整合。画面のSCR-nnnも旧UIRと共存可。
- Python以外の主要コード拡張子（JS/TS/TSX/Java等）をソース候補に追加。非Pythonの逆引きはファイル単位であり、採用言語／配置に合わせてPolicyのglobを実行前に確認。
- 参照漏れの修正担当はProducer側。Auditorは引き続き正本を自動修復せず、issues[].routeで原因工程へ差戻す。3回の修正ループとGateは維持。

## 動作確認
- Traceability 単体テスト: 54件 PASS
- Requirements 構造・ID Validator: 42件 PASS
- Architecture DesignSplit: 42件 PASS
- Independent ADDR: 30件 PASS
- Logical DB: 14件 PASS
- ADR Validator: 38件 PASS
- Unit Test Validator: 44件 PASS
- Integration Test Validator: 17件 PASS
- 全17群の一括実行: 時間制限で完了せず。上記を含む一部のみ検証済み。
- 映画ECの実再実行・実コードのトレーサビリティ検査は未実施（実験用正本とコード実行環境の確定後に実施）。

## 導入
1. **完全版ZIP** は既存リポジトリへ展開。`.git`、巨大な環境キャッシュは同梱していない。
2. **差分ZIP** は修正・新規ファイルだけ。同じ相対パスへ上書き可能。
3. Requirements Agentで実対象FR一覧を要件正本から作成し、版を固定する。
4. `.github/skills/traceability-audit/policy/traceability-policy.yaml` のinclude/excludeが実コード配置と合致するか確認。
5. `docs/ai-sdlc/traceability-fr-runbook.md` に従い、Implementation以降のC12、最終FULL生成と--no-writeを実行する。
6. 誤参照が見つかったら原因成果物を修正し、影響下流・Gate・JUnitを再検証する。

## 修正・新規ファイル
- `.github/agents/architecture.agent.md`
- `.github/agents/implementation.agent.md`
- `.github/agents/integration-test.agent.md`
- `.github/agents/requirements.agent.md`
- `.github/agents/sdlc-orchestrator.agent.md`
- `.github/agents/traceability-auditor.agent.md`
- `.github/agents/unit-test.agent.md`
- `.github/copilot-instructions.md`
- `.github/skills/architecture/templates/file-definition.template.md`
- `.github/skills/architecture/templates/logical-database-design.template.md`
- `.github/skills/requirements/SKILL.md`
- `.github/skills/requirements/scripts/test_validate_requirements_structure.py`
- `.github/skills/requirements/scripts/validate_requirements_structure.py`
- `.github/skills/requirements/templates/data_requirements.md`
- `.github/skills/requirements/templates/external_interface_requirements.md`
- `.github/skills/requirements/templates/ui_report_requirements.md`
- `.github/skills/traceability-audit/SKILL.md`
- `.github/skills/traceability-audit/policy/traceability-policy.yaml`
- `.github/skills/traceability-audit/scripts/test_trace_check.py`
- `.github/skills/traceability-audit/scripts/trace_check.py`
- `docs/ai-sdlc/inline-traceability.md`
- `docs/ai-sdlc/traceability-fr-runbook.md`
