# 実装タスク一覧・進捗

<!--
目的:
- RequirementとAccepted Architecture/Designを、Implementation Agentが実行可能な作業単位へ分解する。
- 作業の依存関係、順序、完了条件、進捗を一元管理する。
- 「何を実装するか」を明確にし、不要なScope Expansionを防ぐ。

重要:
- TaskはRequirement / Accepted ADR / Design Referenceのいずれかに根拠を持つ。
- Task内でRequirementやArchitecture Decisionを新規に決定しない。
- 実装方法に新たな重要判断が必要な場合はADR_REQUIRED等の所定ルートへ戻す。
- Production Codeの構造そのものを本書へ過度に複製しない。
-->

## 1. 文書情報

| 項目 | 内容 |
| --- | --- |
| Document ID | `<DOC-IMPL-TASK-001>` |
| 対象システム | `<システム名>` |
| Baseline / Commit | `<commit / revision>` |
| Version | `<1.0>` |
| Status | `DRAFT / READY / IN_PROGRESS / COMPLETE` |
| Owner | `<Architecture / Implementation Team>` |
| Last Updated | `<YYYY-MM-DD>` |

## 2. Source Baseline

| Source Type | ID / Path | Required Status / Version | Purpose |
| --- | --- | --- | --- |
| Requirements | `<path>` | `<APPROVED / version>` | Scope / Requirement |
| Use Case | `<path>` | `<APPROVED / version>` | Behavior / AC |
| ADR | `<ADR-xxx>` | `ACCEPTED` | Architecture Decision |
| Detailed Design | `<FILE-xxx / Other / None>` | `<APPROVED>` | Implementation Detail |
| Project AI Steering | `<path>` | `<APPROVED / version>` | PJ-specific Environment / Commands |

## 3. Task Decomposition Rules

Taskは以下の条件を満たす単位へ分解する。

- 1 Taskの目的と完了条件を明確に説明できる。
- Related Requirement / ADR / Design Referenceが特定できる。
- 依存Taskを明示できる。
- 実装後にBuild / Test / Validator等で完了を確認できる。
- 複数の独立した変更目的を不必要に1 Taskへまとめない。
- Requirementに存在しない機能追加をTask化しない。
- 新たなArchitecture Decisionが必要なTaskは実装開始前に解決する。

## 4. Task Summary

| Task ID | Title | Type | Related Requirement | Related ADR | Target Area | Depends On | Priority | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| TASK-001 | `<タイトル>` | `IMPLEMENT / CONFIG / MIGRATION / TEST_SUPPORT / OTHER` | `<FR-xxx>` | `<ADR-xxx / None>` | `<module/component>` | `<TASK-xxx / None>` | `HIGH / MEDIUM / LOW` | `TODO / READY / IN_PROGRESS / BLOCKED / DONE / CANCELLED` |

## 5. Execution Order / Dependency

<!--
依存のないTaskは同一Waveで並行実行可能。
Cycleが存在してはならない。
-->

| Wave | Task IDs | Start Condition |
| ---: | --- | --- |
| 1 | `<TASK-001, TASK-002>` | `<Source Baseline確定>` |
| 2 | `<TASK-003>` | `<TASK-001 DONE>` |

## 6. Task Details

### TASK-001 `<Task Title>`

#### Metadata

| 項目 | 内容 |
| --- | --- |
| Type | `IMPLEMENT / CONFIG / MIGRATION / TEST_SUPPORT / OTHER` |
| Priority | `HIGH / MEDIUM / LOW` |
| Status | `TODO / READY / IN_PROGRESS / BLOCKED / DONE / CANCELLED` |
| Target Area | `<module / component / layer>` |
| Depends On | `<TASK-xxx / None>` |
| Blocks | `<TASK-xxx / None>` |

#### Source References

| Type | ID / Path | Relevant Section / Reason |
| --- | --- | --- |
| Requirement | `<FR-xxx>` | `<対象要求>` |
| Use Case / AC | `<UC-xxx / AC-...>` | `<対象振る舞い>` |
| ADR | `<ADR-xxx / None>` | `<設計制約>` |
| Detailed Design | `<FILE-xxx / path / None>` | `<詳細仕様>` |

#### Objective

`<このTaskで達成する変更目的>`

#### Scope

##### In Scope

- `<実施すること>`

##### Out of Scope

- `<このTaskでは行わないこと>`

#### Expected Change

- `<追加・変更すべきComponent / Interface / Configuration等>`
- `<必要に応じて対象Path候補。現在のSource構造を不要に固定しない>`

#### Constraints

- `<Requirement / ADR / Project AI Steering由来の制約>`
- `<破ってはいけないInterface / Compatibility等>`

#### Completion Criteria / Definition of Done

- [ ] `<目的に対応する実装が完了している>`
- [ ] `<関連Acceptance Criteriaを満たせる状態である>`
- [ ] `<Build / CompileがPASSする>`
- [ ] `<Required Test / ValidatorがPASSする>`
- [ ] `<不要なScope Expansionがない>`
- [ ] `<必要なEvidence / Reportが生成されている>`

#### Validation

| Validation Type | Command / Method | Expected Result |
| --- | --- | --- |
| Build | `<Project AI Steering参照 / command>` | `PASS` |
| Static Check | `<command / N/A>` | `PASS` |
| Unit Test | `<command / later phase / N/A>` | `<PASS / planned>` |
| Other | `<Validator等>` | `<Expected>` |

#### Progress / Result

| 項目 | 内容 |
| --- | --- |
| Started At | `<YYYY-MM-DDThh:mm / None>` |
| Completed At | `<YYYY-MM-DDThh:mm / None>` |
| Result | `<DONE / BLOCKED / FAILED / None>` |
| Evidence | `<commit / report / test result / None>` |
| Blocked Reason | `<理由 / None>` |
| Required Route | `<ARCHITECTURE / REQUIREMENTS / NONE>` |

#### Notes

- `<補足>`

## 7. Coverage / Scope Check

<!--
Trace Mapそのものではない。
Task Planning時点で、実装対象Requirement/DesignにTaskが存在するかを確認するための計画用Summary。
最終的なTraceabilityはTraceability Auditorが生成する。
-->

| Source ID | Source Type | Required Implementation | Related Task IDs | Planning Status |
| --- | --- | --- | --- | --- |
| `<FR-001>` | `REQUIREMENT` | `YES / NO` | `<TASK-001>` | `COVERED / MISSING / N/A` |
| `<ADR-001>` | `ADR` | `YES / NO` | `<TASK-001>` | `<...>` |

## 8. Progress Summary

| Status | Count |
| --- | ---: |
| TODO | `<AUTO / 0>` |
| READY | `<AUTO / 0>` |
| IN_PROGRESS | `<AUTO / 0>` |
| BLOCKED | `<AUTO / 0>` |
| DONE | `<AUTO / 0>` |
| CANCELLED | `<AUTO / 0>` |

### Overall Progress

- Total Tasks: `<AUTO>`
- Completed Tasks: `<AUTO>`
- Completion Rate: `<AUTO>`
- Blocking Tasks: `<AUTO>`

## 9. Blockers / Open Decisions

| Blocker ID | Related Task | Classification | Description | Impact | Recommended Route | Status |
| --- | --- | --- | --- | --- | --- | --- |
| BLK-001 | `<TASK-001>` | `REQUIREMENT / ARCHITECTURE / ENVIRONMENT / EXTERNAL` | `<内容>` | `<影響>` | `<REQUIREMENTS / ARCHITECTURE / USER_INPUT>` | `OPEN / RESOLVED` |

## 10. Change History

| Version | Date | Change | Reason | Related ID |
| --- | --- | --- | --- | --- |
| `<1.0>` | `<YYYY-MM-DD>` | `<Task追加・変更等>` | `<理由>` | `<FR/ADR/TASK>` |
