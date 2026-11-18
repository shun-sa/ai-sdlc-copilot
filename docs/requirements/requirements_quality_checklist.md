---
document_type: "仕様品質チェックリスト"
system_name: "MiniCommerce"
version: "1.2"
status: "作成中"
created: "2026-10-09"
last_updated: "2026-11-09"
author: "MiniCommerce 要件定義チーム"
---

# 仕様品質チェックリスト：MiniCommerce

## 0. 文書管理

### 0.1 改訂履歴

| 版数 | 日付 | 改訂内容 | 作成・改訂者 |
|---|---|---|---|
| 1.1 | 2026-10-21 | テンプレート改訂に合わせて構成を更新 | MiniCommerce 要件定義チーム |
| 1.2 | 2026-11-09 | 設計情報（API物理仕様・物理名・実装方式・画面配置等）を削除し要件表現に整理 | MiniCommerce 要件定義チーム |

## 1. 本書の目的と適用範囲

### 1.1 目的

本書は、MiniCommerce の要件・仕様成果物について、完全性、明確性、一貫性、検証可能性、参照整合性等をレビューし、次工程へ進める品質に達しているかを判定することを目的とする。

### 1.2 適用範囲

| 区分 | 内容 |
|---|---|
| 対象成果物 | 業務要件、機能要件、非機能要件、データ要件、外部IF要件、画面・帳票要件、ユースケース／ユーザーストーリー一覧、ユースケース定義書（全13件）、用語集、要件索引 |
| 対象Revision / Commit | 3章に記載の各成果物の版（Commit は該当なし） |
| 本書で確認する | 要件・仕様の完全性、明確性、一貫性、検証可能性、参照整合性、未決事項、Scope |
| 本書で確認しない | 詳細設計、実装、Test Coverage、最終Trace Map |

## 2. Review情報

| 項目 | 内容 |
|---|---|
| Review ID | REVIEW-MINICOMMERCE-PENDING |
| 実施日 | 未実施 |
| Reviewer | 未定 |
| Review Method | 未実施（文書レビュー予定） |
| 総合判定 | BLOCKED |

## 3. Review対象成果物

| Artifact ID / Path | Artifact Type | Version / Status | 備考 |
|---|---|---|---|
| business_requirements.md（業務要件定義書） | 業務要件 | 1.1 / レビュー中 | レビュー未実施 |
| functional_requirements.md（機能要件定義書） | 機能要件 | 1.1 / レビュー中 | レビュー未実施 |
| non_functional_requirements.md（非機能要件定義書） | 非機能要件 | 1.1 / レビュー中 | レビュー未実施 |
| data_requirements.md（データ要件定義書） | データ要件 | 1.1 / レビュー中 | レビュー未実施 |
| external_interface_requirements.md（外部インターフェース要件一覧） | 外部IF要件 | 1.1 / レビュー中 | レビュー未実施 |
| ui_report_requirements.md（画面・帳票要件レイアウト/一覧） | 画面帳票要件 | 1.1 / レビュー中 | レビュー未実施 |
| use-case-user-story-index.md（ユースケース／ユーザーストーリー一覧） | Use Case | 1.2 / 作成中 | レビュー未実施 |
| use-cases/UC-001.md（ユースケース定義書） | Use Case | 1.2 / 作成中 | レビュー未実施 |
| use-cases/UC-002.md（ユースケース定義書） | Use Case | 1.2 / 作成中 | レビュー未実施 |
| use-cases/UC-003.md（ユースケース定義書） | Use Case | 1.2 / 作成中 | レビュー未実施 |
| use-cases/UC-004.md（ユースケース定義書） | Use Case | 1.2 / 作成中 | レビュー未実施 |
| use-cases/UC-005.md（ユースケース定義書） | Use Case | 1.2 / 作成中 | レビュー未実施 |
| use-cases/UC-006.md（ユースケース定義書） | Use Case | 1.2 / 作成中 | レビュー未実施 |
| use-cases/UC-007.md（ユースケース定義書） | Use Case | 1.2 / 作成中 | レビュー未実施 |
| use-cases/UC-008.md（ユースケース定義書） | Use Case | 1.2 / 作成中 | レビュー未実施 |
| use-cases/UC-009.md（ユースケース定義書） | Use Case | 1.2 / 作成中 | レビュー未実施 |
| use-cases/UC-010.md（ユースケース定義書） | Use Case | 1.2 / 作成中 | レビュー未実施 |
| use-cases/UC-011.md（ユースケース定義書） | Use Case | 1.2 / 作成中 | レビュー未実施 |
| use-cases/UC-012.md（ユースケース定義書） | Use Case | 1.2 / 作成中 | レビュー未実施 |
| use-cases/UC-013.md（ユースケース定義書） | Use Case | 1.2 / 作成中 | レビュー未実施 |
| glossary.md（用語集） | Glossary | 1.2 / 作成中 | レビュー未実施 |
| requirements.md（要件索引） | その他 | 版なし / 該当なし | レビュー未実施 |

## 4. 判定基準

### 4.1 Result

| Result | 定義 |
|---|---|
| PASS | 問題なし |
| FAIL | 修正が必要 |
| N/A | 対象外。理由必須 |
| BLOCKED | 情報不足等で客観的に判定できない。理由必須 |

### 4.2 総合判定の目安

- CRITICALまたはHIGHの未解決FAILが1件以上ある場合：FAIL
- BLOCKEDがあり、品質を保証できない場合：BLOCKED
- 必須チェックがPASSまたは妥当なN/Aであり、重大な未解決指摘がない場合：PASS

| Gate ID | 判定条件 |
|---|---|
| 該当なし | プロジェクト固有のGateの指定なし。レビュー未実施の項目をPASSとはしない |

## 5. 仕様品質チェック

| Check ID | 観点 | チェック内容 | 重要度 | Result | Evidence / 対象ID | Issue ID / N/A・BLOCKED理由 |
|---|---|---|---|---|---|---|
| QC-001 | 完全性 | スコープ内の主要な業務目的、利用者、主要機能が定義されているか | HIGH | BLOCKED | 対象版の成果物一覧は3章参照 | ISSUE-REVIEW-001：レビュー未実施。確認先は未定 |
| QC-002 | 完全性 | 正常系だけでなく主要な異常系、境界条件、権限、失敗時の要求が定義されているか | HIGH | BLOCKED | 対象版の成果物一覧は3章参照 | ISSUE-REVIEW-001：レビュー未実施。確認先は未定 |
| QC-003 | 明確性 | 「適切に」「必要に応じて」「可能な限り」等の曖昧語が判定条件なしで使用されていないか | MEDIUM | BLOCKED | 対象版の成果物一覧は3章参照 | ISSUE-REVIEW-001：レビュー未実施。確認先は未定 |
| QC-004 | 明確性 | 業務・技術用語が用語集と矛盾せず、一貫した意味で使用されているか | MEDIUM | BLOCKED | 対象版の成果物一覧は3章参照 | ISSUE-REVIEW-001：レビュー未実施。確認先は未定 |
| QC-005 | 単一性 | 1つのRequirementに独立して判定すべき複数の要求を過剰に含めていないか | MEDIUM | BLOCKED | 対象版の成果物一覧は3章参照 | ISSUE-REVIEW-001：レビュー未実施。確認先は未定 |
| QC-006 | 一貫性 | Requirement同士に相互矛盾がないか | HIGH | BLOCKED | 対象版の成果物一覧は3章参照 | ISSUE-REVIEW-001：レビュー未実施。確認先は未定 |
| QC-007 | 一貫性 | Scope、Constraint、Business RuleとRequirementが矛盾していないか | HIGH | BLOCKED | 対象版の成果物一覧は3章参照 | ISSUE-REVIEW-001：レビュー未実施。確認先は未定 |
| QC-008 | 検証可能性 | 重要なRequirementに観測可能なAcceptance Criteriaが定義されているか | HIGH | BLOCKED | 対象版の成果物一覧は3章参照 | ISSUE-REVIEW-001：レビュー未実施。確認先は未定 |
| QC-009 | 検証可能性 | Acceptance Criteriaの条件・操作・期待結果・合否条件が客観的に判定可能か | HIGH | BLOCKED | 対象版の成果物一覧は3章参照 | ISSUE-REVIEW-001：レビュー未実施。確認先は未定 |
| QC-010 | 検証可能性 | NFRの目標値、単位、測定条件、検証方法が必要な範囲で定義されているか | HIGH | BLOCKED | 対象版の成果物一覧は3章参照 | ISSUE-REVIEW-001：レビュー未実施。確認先は未定 |
| QC-011 | 参照整合性 | Requirement、User Story、Use Case、Acceptance Criteria等のIDが一意であるか | HIGH | BLOCKED | 対象版の成果物一覧は3章参照 | ISSUE-REVIEW-001：レビュー未実施。確認先は未定 |
| QC-012 | 参照整合性 | User Story / Use Case / Acceptance Criteriaが実在するRequirementを参照しているか | HIGH | BLOCKED | 対象版の成果物一覧は3章参照 | ISSUE-REVIEW-001：レビュー未実施。確認先は未定 |
| QC-013 | 参照整合性 | 存在しないID、廃止済みID、古いReferenceへの参照がないか | HIGH | BLOCKED | 対象版の成果物一覧は3章参照 | ISSUE-REVIEW-001：レビュー未実施。確認先は未定 |
| QC-014 | 必要性 | 利用者価値、業務目的、制約に結び付かない不要なRequirementがないか | MEDIUM | BLOCKED | 対象版の成果物一覧は3章参照 | ISSUE-REVIEW-001：レビュー未実施。確認先は未定 |
| QC-015 | 実装非依存 | 物理名・英字識別子、API・電文の物理仕様（パス・ステータス・コード）、製品・言語の選定、データの物理設計・排他方式、画面配置・UI部品、インフラ構成・設定値、テストツール・コマンドが、制約として根拠のある場合を除き含まれていないか | HIGH | BLOCKED | 対象版の成果物一覧は3章参照 | ISSUE-REVIEW-001：レビュー未実施。確認先は未定 |
| QC-016 | データ | 主要データの意味、必須性、整合性、保持、削除、機密性等が必要な範囲で定義されているか | MEDIUM | BLOCKED | 対象版の成果物一覧は3章参照 | ISSUE-REVIEW-001：レビュー未実施。確認先は未定 |
| QC-017 | 外部IF | 外部連携がある場合、相手、目的、データ、タイミング、責任分界等が定義されているか | HIGH | BLOCKED | 対象版の成果物一覧は3章参照 | ISSUE-REVIEW-001：レビュー未実施。確認先は未定 |
| QC-018 | セキュリティ | 認証、認可、入力検証、機密データ等の主要Security Requirementが必要な範囲で定義されているか | HIGH | BLOCKED | 対象版の成果物一覧は3章参照 | ISSUE-REVIEW-001：レビュー未実施。確認先は未定 |
| QC-019 | 未決事項 | 未決事項・確認事項が識別され、影響、担当、期限、状態が記録されているか | MEDIUM | BLOCKED | 対象版の成果物一覧は3章参照 | ISSUE-REVIEW-001：レビュー未実施。確認先は未定 |
| QC-020 | 重複 | 同じ意味のRequirement、Use Case、Acceptance Criteriaが重複していないか | MEDIUM | BLOCKED | 対象版の成果物一覧は3章参照 | ISSUE-REVIEW-001：レビュー未実施。確認先は未定 |
| QC-021 | スコープ | 対象外の要求や不要な機能追加が仕様に混入していないか | HIGH | BLOCKED | 対象版の成果物一覧は3章参照 | ISSUE-REVIEW-001：レビュー未実施。確認先は未定 |
| QC-022 | 失敗時整合性 | 失敗時にデータ不整合や不完全状態を残さない要求が必要な範囲で定義されているか | HIGH | BLOCKED | 対象版の成果物一覧は3章参照 | ISSUE-REVIEW-001：レビュー未実施。確認先は未定 |
| QC-023 | 変更影響 | 変更されたRequirementに関連するUse Case、Acceptance Criteria、Glossary等が必要に応じて更新されているか | MEDIUM | BLOCKED | 対象版の成果物一覧は3章参照 | ISSUE-REVIEW-001：レビュー未実施。確認先は未定 |
| QC-024 | 記載先 | 各成果物で「本書で定義しない」とした事項が、その成果物に記載されていないか。同一事項が複数の成果物に重複して記載されていないか | MEDIUM | BLOCKED | 対象版の成果物一覧は3章参照 | ISSUE-REVIEW-001：レビュー未実施。確認先は未定 |

## 6. 指摘一覧

| Issue ID | Check ID | 対象Artifact / ID | 指摘内容 | Severity | 推奨修正 | Owner / Route | 状態 |
|---|---|---|---|---|---|---|---|
| ISSUE-REVIEW-001 | QC-001〜QC-024 | 全対象成果物 | レビュー未実施 | 未判定 | Reviewerを指定し、実施日・結果を記入する | 未定 | 未着手 |

## 7. 指摘対応確認

| Issue ID | 対応内容 | 修正Artifact / ID | 確認者 | 再確認結果 | 確認日 |
|---|---|---|---|---|---|
| ISSUE-REVIEW-001 | 未実施 | 全対象成果物 | 未定 | BLOCKED | 未実施 |

## 8. Reviewサマリ

### 8.1 Result別件数

| Result | 件数 |
|---|---|
| PASS | 0 |
| FAIL | 0 |
| N/A | 0 |
| BLOCKED | 24 |

### 8.2 Severity別未解決指摘

| Severity | 件数 |
|---|---|
| CRITICAL | 未判定（レビュー未実施） |
| HIGH | 未判定（レビュー未実施） |
| MEDIUM | 未判定（レビュー未実施） |
| LOW | 未判定（レビュー未実施） |

## 9. 未解決事項・残存リスク

| ID | 内容 | 影響 | 対応方針 | 次工程への持越し可否 | 担当 |
|---|---|---|---|---|---|
| ISSUE-REVIEW-001 | レビュー未実施 | 要件の品質を保証できない | Reviewerを指定してレビューを実施する | 未定（レビュー結果に基づき判断する） | 未定 |

## 10. 総合所見

### 10.1 良好な点

- 未判定（レビュー未実施）。

### 10.2 主な問題

- 未判定（レビュー未実施）。

### 10.3 次工程へ進むために必要な対応

- Reviewer・対象版を固定してレビューを実施する。

## 11. 最終判定

| 項目 | 内容 |
|---|---|
| Result | BLOCKED |
| Decision | 判定保留（レビュー未実施） |
| Reviewer | 未定 |
| Date | 未実施 |
