# Project-wide Copilot Instructions

## Purpose

このRepositoryでは、
AIによるRequirements、Architecture、Implementation、
Unit Test、Integration Testまでの
一気通貫Software Development Lifecycleを実行する。

各工程の具体的な作業手順は
Custom AgentおよびSkillに定義する。

このFileには、
すべてのAgentが常に遵守すべき
Project-wide invariantのみを定義する。


# SDLC Control

SDLC全体の工程制御は
SDLC Orchestratorのみが担当する。

専門Agentは自身の工程完了後、
次工程を直接起動してはいけない。

専門Agentは結果をSDLC Orchestratorへ返却する。

各工程のSUCCESSは
専門Agent自身の処理完了を意味し、
工程全体のPASSを意味しない。


# Phase Order

標準工程順序は以下とする。

Requirements
→ Architecture
→ Implementation
→ Unit Test
→ Integration Test

工程遷移は
SDLC Orchestratorが制御する。


# Source of Truth

RequirementのSource of Truthは
Requirements成果物とする。

重要なArchitecture DecisionのSource of Truthは
Accepted ADRとする。

Production Codeの現在の挙動を
Requirementの代わりに使用してはいけない。

Testの期待結果を
Production Codeから逆算してはいけない。


# Requirements Structure

Requirements Templateの構成を
変更してはいけない。

Sectionの追加、削除、名称変更、
順序変更を行ってはいけない。

Requirement IDを
後続工程の都合で変更してはいけない。


# Architecture Decision

重要なArchitecture Decisionは
ADRへ記録する。

Accepted ADRのDecisionおよび
AI Guardrailsを後続工程で遵守する。

Accepted ADRに反する実装を
独自判断で行ってはいけない。

重要な設計判断が不足する場合は
ADR_REQUIREDとしてOrchestratorへ返却する。


# Implementation

Implementationは
Requirements全体およびAccepted ADRに従う。

FRだけでなく、
Acceptance Criteria、
共通機能要件、
認証・認可、
Error仕様、
NFR、
Data Model、
Constraint、
Out of Scopeを確認する。

Out of Scopeを
利便性やBest Practiceだけを理由に実装してはいけない。


# Database Testability

Databaseを利用するProduction Codeは、
Production Databaseへ固定依存してはいけない。

TestではProduction Database、
Production Credential、
Production Dataを使用してはいけない。

必要に応じてDocker Container等の
Disposable Test Databaseを使用可能な構造とする。


# Test Expectations

Unit TestおよびIntegration Testの期待結果は
RequirementsおよびAccepted ADRから導出する。

TestをPASSさせる目的で
Expected ResultをProduction Codeへ合わせてはいけない。

Failureを隠す目的で
Testを削除、skip、無効化、
Assertion弱体化してはいけない。


# Error Carry Forward

既知のErrorを
後工程へ持ち越してはいけない。

Production CodeのErrorは
Implementation Agentで修正する。

Test CodeのErrorは
対象Test Agentで修正する。

重要な設計判断不足は
Architecture工程へ戻す。

Requirementの問題は
Requirements工程へ戻す。

修正後は、
影響するTestおよびValidatorを
必ず再実行する。


# Upstream Change Invalidation

上流成果物を変更した場合、
変更前に取得した後続工程のPASSを
自動的に有効とみなしてはいけない。

Requirements変更:
Architecture以降を再検証する。

Accepted ADR変更:
Implementation以降を再検証する。

Production Code変更:
影響するUnit TestおよびIntegration Testを再実行する。


# External Integration Test Cases

External Integration Test Caseは
実験用評価データとして扱う。

External Caseの意味、
Input、
Steps、
Expected Resultを
AIの都合で変更してはいけない。

External Caseは
origin=EXTERNALとして管理する。

AI生成Caseは
origin=AI_GENERATEDとして管理する。

AI INITIAL Caseは
External Caseを確認する前に生成・固定する。

External Case確認後に
AI INITIAL Caseを書き換えてはいけない。

Coverage Gap補完Caseは
AI GAP_FILLとして区別する。

External Test Caseが配置されていない場合、
AI自身の判断でExternal Caseなしとして
処理を継続してはいけない。

External Caseなしで処理を継続する場合は、
ユーザーによる明示的な確認が必要である。

External Case未配置と、
ユーザーがExternal Caseなしを明示的に選択した状態を
同一として扱ってはいけない。


# Deterministic Validation

Validatorが存在する工程では、
Validator結果を工程Gateとして使用する。

ValidatorがFAILしている状態で
次工程へ進んではいけない。

AIの自己評価を
Deterministic Validatorの代わりにしてはいけない。


# Traceability

以下のTraceabilityを維持する。

Requirement
→ ADR
→ Implementation
→ Unit Test
→ Integration Test

既存IDを変更して
Traceability Failureを隠してはいけない。

存在しないRequirement IDやADR IDを
推測で作成してはいけない。


# Security

Credential、
Secret、
Production Token、
Production Dataを
Source CodeまたはTest Dataへハードコードしてはいけない。

Security Requirementおよび
Accepted ADRのSecurity Guardrailを遵守する。


# Repository Independence

Git hosting service、
CI/CD service、
Cloud providerを
明示的なRequirementまたはAccepted ADRなしに仮定しない。

GitHub Actions等の
特定CI/CD機能への依存を
暗黙的に追加してはいけない。


# Responsibility Separation

Agent:
責務、境界、Input、Outputを定義する。

Skill:
具体的な実行方法を定義する。

Template:
成果物の構造を定義する。

Policy:
合否基準を定義する。

Criterion:
試験観点を定義する。

Validator:
機械的に判定可能なGateを定義する。

同じ詳細手順を複数箇所へ重複定義しない。


# Final Principle

不確実な内容を
暗黙の事実として確定しない。

解消可能な場合は
既存Requirement、ADR、Code、Testを確認する。

解消できない重要事項は
ASSUMPTION、ADR_REQUIRED、BLOCKED等の
明示的な状態として扱う。
