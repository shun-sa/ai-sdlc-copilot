# Unit Test Quality Criterion

## Purpose

Unit TestがProduction Codeの現状確認ではなく、
Requirement Behaviorを有効に検証していることを確認する。

## Applies To

- UNIT_TEST
- INTEGRATION_TEST
- FULL

## Required Review

以下を確認する。

- Expected ResultがRequirement / ADR由来
- Production CodeからExpected Resultを逆算していない
- AssertionがBehaviorを実際に検証する
- 無意味なAssertionがない
- 正常系だけに偏っていない
- 必要なBoundary Caseが存在する
- 必要なInvalid Caseが存在する
- 必要なException Caseが存在する
- Mockが対象Behaviorを隠していない
- Test間の不要な依存がない
- Regression TestがBugを再検知できる

## Pass Conditions

対象Behaviorを失敗時に確実に検出できる
意味のあるUnit Testになっている。

## Not Applicable

Unit Test対象外Requirementについては
理由付きNOT_APPLICABLE可。

## Failure Handling

Test品質問題:

`UNIT_TEST_QUALITY_ISSUE`

Assertion不足:

`INSUFFICIENT_TEST_ASSERTION`

Behavior抜け:

`MISSING_BEHAVIOR_COVERAGE`

## Evidence

- Requirement
- Test
- Expected Result
- Assertion
- Missing Behavior
