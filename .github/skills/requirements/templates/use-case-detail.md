# `<UC-001>` `<ユースケース名>`

<!--
目的:
- 1つのユースケースについて、目的、前提、基本・代替・例外フロー、事後条件を定義する。
- 当該ユースケースのAcceptance Criteria / Pass-Fail Ruleを同一ファイルで管理する。

重要:
- 本ファイル内のAcceptance Criteriaを当該ユースケースのSource of Truthとする。
- Acceptance Criteriaの独立した手入力一覧は作らない。必要な一覧は本ファイル群から生成する。
- Acceptance Criteriaには AC-UC-xxx-xxx の一意IDを付与する。
- 実装方式ではなく、Actorまたは外部から観測できる振る舞い・結果を中心に記載する。
- 不明な仕様をAIが推測して確定しない。Open Questionsへ記録する。
-->

## 1. Metadata

| 項目 | 内容 |
| --- | --- |
| Use Case ID | `UC-001` |
| Title | `<ユースケース名>` |
| Primary Actor | `<ACT-001 / アクター名>` |
| Secondary Actors | `<ACT-XXX / None>` |
| Related User Stories | `<US-001 / None>` |
| Related Requirements | `<FR-001, NFR-001>` |
| Priority | `HIGH / MEDIUM / LOW` |
| Status | `DRAFT / REVIEW / APPROVED` |
| Version | `<1.0>` |
| Last Updated | `<YYYY-MM-DD>` |

## 2. Goal

`<このユースケースでActorが達成したい目的・価値>`

## 3. Scope / Boundary

### In Scope

- `<このユースケースで扱う範囲>`

### Out of Scope

- `<このユースケースでは扱わない範囲>`

## 4. Trigger

`<ユースケース開始の契機>`

## 5. Preconditions

1. `<開始前に成立している必要がある条件>`
2. `<...>`

## 6. Main Flow

| Step | Actor / System | Action / Behavior | Expected State |
| ---: | --- | --- | --- |
| 1 | `<Actor>` | `<操作・イベント>` | `<状態>` |
| 2 | `<System>` | `<応答・処理>` | `<状態>` |

## 7. Alternative Flows

### ALT-01 `<代替フロー名>`

- Branch From: `<Main Flow Step>`
- Condition: `<分岐条件>`

| Step | Actor / System | Action / Behavior | Expected State |
| ---: | --- | --- | --- |
| 1 | `<...>` | `<...>` | `<...>` |

## 8. Exception Flows

### EX-01 `<例外フロー名>`

- Occurs At: `<Main/Alternative Flow Step>`
- Condition: `<例外条件>`

| Step | Actor / System | Action / Behavior | Expected State |
| ---: | --- | --- | --- |
| 1 | `<System>` | `<例外時の振る舞い>` | `<不整合を残さない等>` |
| 2 | `<Actor>` | `<確認できる結果>` | `<...>` |

## 9. Postconditions

### Success

- `<正常終了後に成立する状態>`

### Failure

- `<失敗時にも保証される状態>`

## 10. Business Rules / Constraints

| Rule ID | 内容 | 関連Requirement ID | 備考 |
| --- | --- | --- | --- |
| BR-UC-001-001 | `<業務ルール・制約>` | `<FR-001 / None>` | `<備考>` |

## 11. Acceptance Criteria / Pass-Fail Rules

<!--
ID形式: AC-<Use Case ID>-<連番>
例: AC-UC-001-001

原則:
- 正常系だけでなく、重要な代替・例外・境界・権限・失敗時も対象にする。
- Given / When / Thenは観測可能な条件として記載する。
- 数値要件がある場合はMeasurement / Toleranceを明記する。
-->

### AC-UC-001-001 `<Acceptance Criteria名>`

- Type: `FUNCTIONAL / NON_FUNCTIONAL / SECURITY / DATA / OPERATIONAL`
- Related Requirements: `<FR-001, NFR-001>`
- Related Flow: `<MAIN / ALT-01 / EX-01 / CROSS_CUTTING>`
- Priority: `HIGH / MEDIUM / LOW`

#### Given

- `<開始時点の状態・前提条件>`

#### When

- `<Actorまたは外部システムが行う操作・イベント>`

#### Then

- `<観測可能な期待結果>`
- `<必要に応じて複数記載>`

#### Measurement / Tolerance

- Metric: `<応答時間、成功率、件数等 / None>`
- Target: `<目標値 / None>`
- Tolerance: `<許容値・許容範囲 / None>`
- Measurement Method: `<確認方法 / None>`

#### Pass / Fail Rule

- PASS: `<合格条件。期待結果・許容値をすべて満たす等>`
- FAIL: `<不合格条件>`
- BLOCKED: `<環境・前提不足等で客観的判定不能となる条件>`

#### Evidence Hint

- `<画面表示、APIレスポンス、DB状態、ログ、計測結果等>`

## 12. Cross-Cutting References

| Reference Type | ID / Path | Purpose |
| --- | --- | --- |
| Glossary | `<TERM-001 / path>` | `<用語>` |
| Other Use Case | `<UC-XXX / None>` | `<関係>` |
| External Specification | `<reference / None>` | `<関係>` |

## 13. Open Questions

| Question ID | 関連Section / AC ID | 内容 | 影響 | 決定者／確認先 | 状態 |
| --- | --- | --- | --- | --- | --- |
| OQ-UC-001-001 | `<AC-UC-001-001>` | `<未確定事項>` | `<影響>` | `<担当>` | `OPEN / RESOLVED` |
