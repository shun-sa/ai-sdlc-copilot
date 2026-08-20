---
name: unit-test
description: >
  要件定義成果物、Accepted ADR、Production Codeを基に
  単体テストを設計・作成・実行・検証するためのSkill。
  Unit Test Policyおよび有効なTest Criteriaを読み込み、
  RequirementとTestのトレーサビリティを維持しながら、
  Coverage計測、DBテスト、エラー原因分類、Regression Test、
  修正後の再実行までを行う。
  単体テストで発生したエラーを未解決のまま後工程へ持ち越さない。
user-invocable: false
disable-model-invocation: false
---

# Unit Test Skill

## Purpose

このSkillは、
要件定義成果物およびAccepted ADRに基づいて
Production Codeの単体テストを設計・作成・実行し、
プロジェクトで定義された品質基準を満たすための
標準的な単体テスト手順を定義します。

単体テスト工程では、
単にTest Suiteを実行するだけではなく、
以下を保証してください。

- 単体テスト可能なRequirementがテストされている
- Test Criteriaに基づく必要なテストケースが存在する
- Unit Test Policyを満たしている
- テストで発見された不具合が修正されている
- 同一不具合を再検出できるRegression Testが存在する
- 修正後に対象テスト、関連テスト、全Unit Testを再実行している
- 未解決エラーが後工程へ持ち越されていない


# Policy

単体テストの品質基準は、
以下のPolicyを唯一の正としてください。

`.github/skills/unit-test/policy/unit-test-policy.yaml`

Coverage値、許容Failure数、
Skipped Test、Flaky Test再実行回数、
DBテスト方針などを
このSKILL.mdへ固定値として定義してはいけません。

必ずPolicyを読み込んで判断してください。


# Test Criteria

具体的なテスト観点は、
以下のディレクトリから取得してください。

`.github/skills/unit-test/criteria/`

Policyで指定されたPatternに一致する
Criterionファイルを有効なTest Criteriaとして扱います。

標準:

`*.criterion.md`

単体テスト開始時に、
現在有効なCriterionファイルをすべて確認してください。

Test Criteriaの追加・削除・変更は、
Criterionファイルで管理します。

SKILL.mdおよびAgentへ
個別テスト観点を固定的に埋め込まないでください。


# References

単体テスト基準の参考情報は以下を確認してください。

`.github/skills/unit-test/references.md`

Referencesは基準設定の根拠情報です。

実際の工程判定には
`unit-test-policy.yaml` を使用してください。


# Inputs

Unit Test Agentから渡された情報を確認してください。

最低限以下を確認します。

- 要件定義成果物
- Accepted ADR
- Production Code
- Implementation工程のRequirement Coverage
- Implementation工程のTraceability情報
- 既存Unit Test
- プロジェクト共通Instructions
- Unit Test Policy
- Unit Test Criteria
- Requirements工程のASSUMPTION
- Architecture工程のASSUMPTION
- Implementation工程のASSUMPTION

必要な情報がリポジトリ内に存在する場合は、
検索して確認してください。


# Source of Expected Behavior

単体テストの期待結果は、
Production Codeの現在の挙動から決定してはいけません。

期待結果は原則として以下から導出してください。

1. 要件定義成果物
2. Accepted ADR
3. プロジェクト共通Instructions
4. 明示的な制約
5. Production Code

Production Codeと要件が異なる場合、
Production Codeへ合わせてTestを変更してはいけません。


# Procedure

## Step 1. Unit Test Policyを読み込む

以下を読み込んでください。

`.github/skills/unit-test/policy/unit-test-policy.yaml`

最低限以下の設定を確認します。

- Test Result基準
- Coverage Threshold
- Requirement Coverage
- Skipped Test Policy
- Database Test Policy
- Regression Policy
- Flaky Test Policy
- Failure Handling
- Criteria Directory
- Criteria Pattern

Policyに存在しない数値基準を
独自に追加してはいけません。


## Step 2. 有効なTest Criteriaを読み込む

Policyで指定されたCriteria Directoryから、
Patternに一致するCriterionファイルをすべて読み込んでください。

各Criterionについて以下を確認します。

- どの処理に適用するか
- どのような入力をテストするか
- 期待結果をどう確認するか
- 適用除外条件が存在するか

存在するCriterionを理由なく無視してはいけません。


## Step 3. 要件定義成果物を確認する

単体テスト観点で要件定義成果物全体を確認してください。

特に以下を確認します。

- Acceptance Criteria
- 共通機能要件
- 認証・認可
- 共通エラー仕様
- NFR
- データモデル
- FR
- FRの入力項目
- バリデーション
- エラー条件
- 制約条件
- 出力/挙動・完了条件

FRだけを確認してテスト対象を決定してはいけません。


## Step 4. Accepted ADRを確認する

対象Requirementに関連するAccepted ADRを確認してください。

特に以下を確認します。

- Related Requirements
- Decision
- Consequences
- AI Guardrails

Accepted ADRによって
期待する振る舞いまたは制約が決まる場合は、
Testへ反映してください。

Production CodeがAccepted ADRに反している場合、
TestをProduction Codeへ合わせてはいけません。


## Step 5. Implementation Traceabilityを確認する

Implementation工程から返された
Requirementと実装箇所の対応を確認してください。

最低限以下を把握します。

- Requirement ID
- 実装ファイル
- 主要Symbolまたは責務
- Related ADR

実装箇所だけを見て
Requirementを推測してはいけません。


## Step 6. 単体テスト可能なRequirementを特定する

各Requirementについて、
Unit Testで検証可能か確認してください。

Unit Testで検証可能なRequirementは
テスト対象として管理してください。

Unit Testだけでは検証できないRequirementについては、
理由を記録してください。

Integration Testや他工程で検証すべきRequirementを
無理にUnit Testだけで検証しようとしてはいけません。


## Step 7. Unit Test Coverage Mapを作成する

単体テスト可能なRequirementについて、
Testとの対応を整理してください。

最低限以下を管理します。

- Requirement ID
- Related ADR
- Production Code
- Test File
- Test Case
- 適用するCriterion
- Test Result

既存Testが存在する場合は、
そのTestが本当にRequirementを検証しているか確認してください。

Testが存在するだけで
Coveredと判断してはいけません。


## Step 8. 既存Unit Testを確認する

新しいTestを作成する前に、
既存Unit Testを確認してください。

確認対象:

- 同じRequirementのTestが存在しないか
- 同じ処理のTestが存在しないか
- Test Fixtureを再利用できないか
- 共通Mockを再利用できないか
- 既存Regression Testがないか
- 無効化されたTestがないか

重複するTestを不要に追加しないでください。


## Step 9. Test Caseを設計する

各Requirementに対して、
有効なTest Criteriaを適用してください。

Test Caseは、
RequirementとCriterionの組み合わせから導出してください。

Production Codeの実装内容だけから
Test Caseを作成してはいけません。

Criterionが適用可能なのに
対応Testが存在しない場合は、
必要なTest Caseを追加してください。


## Step 10. Test Caseの期待結果を定義する

期待結果は要件およびAccepted ADRから導出してください。

確認例:

- 戻り値
- 状態変化
- Validation Result
- Error
- Exception
- Authorization Result
- Data Mapping Result
- Repository呼び出し
- 外部依存へのInteraction

単に「Exceptionが発生する」ではなく、
要件で定義されたエラー条件を確認できる形にしてください。


## Step 11. External Dependencyを分離する

Unit Testでは、
テスト対象外の外部依存を適切に分離してください。

例:

- 外部API
- Messaging
- File Storage
- Clock
- Random Generator
- Third Party Service

対象ロジックの検証に不要な外部通信を
Unit Testから実行してはいけません。


## Step 12. DB Test Strategyを決定する

DBアクセスが存在する場合、
Unit Test Policyを確認してください。

DBそのものの動作を確認する必要がないレイヤーでは、
MockまたはStubを使用してください。

例:

- Service
- Domain Logic
- Use Case

Repository、DAOなど、
実DB固有の挙動を確認する必要がある場合は、
Policyに従ってDockerコンテナ等の
一時的なテストDBを使用してください。

例:

- SQL
- ORM Mapping
- Database Constraint
- Transaction
- Database-specific Query

Production DBまたは共有DBを
Unit Testから使用してはいけません。


## Step 13. Container DBを使用する場合の前提を確認する

Container DBを使用する場合、
最低限以下を確認してください。

- Disposableである
- TestごとまたはTest Suiteごとに独立している
- Production Credentialを必要としない
- Production DBへ接続しない
- Schemaを再現できる
- Test Dataを独立して投入できる
- Test終了後に破棄可能である

Implementation工程で
この構造を実現できないことが判明した場合は、
IMPLEMENTATION_FIX_REQUIREDとして扱ってください。


## Step 14. Unit Testを実装する

プロジェクトで採用されている
既存Test Frameworkを使用してください。

既存Test Frameworkが存在する場合、
新しいFrameworkを独自に追加してはいけません。

Testは以下を満たしてください。

- Testの意図が明確である
- Requirementとの対応が分かる
- 他Testに不要に依存しない
- 実行順序に依存しない
- Production環境に依存しない
- 再実行可能である
- 決定論的である

Test名は、
何を確認しているTestか理解できるものにしてください。


## Step 15. Unit Testを実行する

作成・更新したUnit Testを実行してください。

まず対象Testを実行し、
Test自体が意図した動作をすることを確認してください。

その後、
Unit Test Suite全体を実行してください。


## Step 16. Coverageを計測する

Unit Test PolicyでCoverageが有効な場合、
プロジェクトの既存Coverage Toolを使用して計測してください。

最低限Policyで指定されたCoverage種類を確認します。

Coverage Thresholdを満たしているか判定してください。

Coverage値だけを上げる目的で
意味のないTestを追加してはいけません。


## Step 17. Requirement Coverageを確認する

単体テスト可能と判断したRequirementについて、
対応するTestが存在することを確認してください。

Coverage Toolの数値が基準を満たしていても、
Requirementに対応するTestが不足している場合は
PASSとしてはいけません。


## Step 18. Test Criteria Coverageを確認する

各対象Requirementについて、
適用可能なCriterionが
Test Caseへ反映されていることを確認してください。

Criterionを適用しなかった場合は、
適用不要と判断した理由を記録してください。


## Step 19. Test Failureを分類する

TestがFAILした場合、
以下のいずれかへ分類してください。

### TEST_ERROR

Test Code、Fixture、Mock、Stub、
Test Data、Assertion等の誤り。

### IMPLEMENTATION_ERROR

Production Codeが
RequirementまたはAccepted ADRを満たしていない。

### ADR_REQUIRED

正しい実装または期待結果を決めるために
新しいArchitecture Decisionが必要。

### REQUIREMENT_ERROR

Requirementの矛盾、不足、曖昧性によって
正しい期待結果を決定できない。

### ENVIRONMENT_ERROR

Test Runner、Docker、
依存ライブラリ、実行環境等による問題。

原因不明のFAILを
一時的なTest Failureとして無視してはいけません。


## Step 20. TEST_ERRORを修正する

TEST_ERRORの場合、
Unit Test工程内でTest Codeを修正してください。

ただし以下を禁止します。

- Testを削除する
- Testをskipする
- Assertionを弱める
- 期待結果をProduction Codeに合わせる
- Requirementと異なる期待結果へ変更する

修正後は対象Testを再実行してください。


## Step 21. IMPLEMENTATION_ERRORを返却する

IMPLEMENTATION_ERRORの場合、
Production CodeをUnit Test Skill自身で変更してはいけません。

以下を整理してUnit Test Agentへ返してください。

- 関連Requirement
- Related ADR
- Failing Test
- Expected Result
- Actual Result
- 原因
- 修正が必要と考えられる実装箇所

Unit Test Agentから
SDLC Orchestratorへ
IMPLEMENTATION_FIX_REQUIREDとして返却します。


## Step 22. ADR_REQUIREDを返却する

正しい期待結果または実装方式が
既存RequirementとAccepted ADRだけでは決定できず、
重要なArchitecture Decisionが必要な場合は、
ADR_REQUIREDとして扱ってください。

Test側でArchitecture Decisionを
独自に確定してはいけません。


## Step 23. REQUIREMENT_ERRORを返却する

Requirementに矛盾、不足、曖昧性がある場合、
Test側でRequirementを変更してはいけません。

BLOCKEDとして返却してください。


## Step 24. ENVIRONMENT_ERRORを確認する

Environment Errorの場合、
Test CodeまたはProduction CodeのFailureと
誤認しないようにしてください。

原因を特定し、
可能な範囲で環境を修復してください。

環境を修復できない場合は、
FAILEDまたはBLOCKEDとして返却してください。


## Step 25. Defect修正後にRegression Testを確認する

単体テストで検出したDefectについて、
修正後に同一不具合を検出できるTestが
存在することを確認してください。

既存Testで再発を検出できない場合は、
Regression Testを追加してください。

Regression Testは、
今回発生した具体的な不具合が再発した場合に
FAILするTestである必要があります。


## Step 26. 修正対象Testを再実行する

Defect修正後、
最初にFailureを検出したTestまたは
追加したRegression Testを再実行してください。

PASSしない場合は
修正完了として扱ってはいけません。


## Step 27. 関連Testを再実行する

修正対象と同じModule、Class、Service、
Repository、Component等の関連Testを再実行してください。

局所修正によるRegressionがないことを確認します。


## Step 28. Unit Test Suite全体を再実行する

修正後は必ず
Unit Test Suite全体を再実行してください。

一部の対象TestだけがPASSした状態で
Unit Test工程を完了してはいけません。


## Step 29. Flaky Testを確認する

非決定的な失敗が疑われる場合は、
Unit Test Policyに従って
対象Testを複数回実行してください。

1回PASSしただけで
Flaky Testを解決済みにしてはいけません。

Flaky Testを検出した場合は、
原因を修正するか、
解決できない場合はFAILEDとして扱ってください。


## Step 30. Skipped Testを確認する

Skipped、Disabled、Ignored等のTestを確認してください。

Unit Test Policyで許可されていない
Skipped Testが存在する場合はFAILです。

既存のSkipped Testが存在する場合も
Policy Allowlistに含まれているか確認してください。


## Step 31. Final Coverageを計測する

すべての修正完了後、
Coverageを再計測してください。

途中計測結果ではなく、
最終Unit Test Suite実行時のCoverageを
最終結果として使用してください。


## Step 32. Final Requirement Coverageを確認する

単体テスト可能なRequirementについて、
すべて対応Testが存在することを確認してください。

最低限以下を確認します。

- Requirement ID
- Related ADR
- Test File
- Test Case
- Test Result

未対応Requirementが存在する場合は
SUCCESSとしてはいけません。


## Step 33. Final Criteria Coverageを確認する

すべての有効Criterionについて、
適用対象に必要なTestが存在することを確認してください。

Criterion追加・削除後も、
このStepによって現在有効なCriterionだけを評価してください。


## Step 34. Unresolved Errorを確認する

以下が残っていないことを確認してください。

- Failed Test
- Error Test
- 原因不明Failure
- 未修正Implementation Error
- 未解決ADR_REQUIRED
- 未解決Requirement Error
- Flaky Test
- 未許可Skipped Test
- Coverage未達
- Requirement Coverage不足
- Criteria Coverage不足

1件でも存在する場合、
Unit Test工程をSUCCESSとしてはいけません。


# Failure Routing

Failureの分類と返却先は以下とします。

TEST_ERROR:
Unit Test工程内で修正する。

IMPLEMENTATION_ERROR:
Implementation工程でProduction Codeを修正する必要がある。

ADR_REQUIRED:
Architecture工程でArchitecture Decisionを
ADRへ反映する必要がある。

REQUIREMENT_ERROR:
Requirements工程でRequirementを
確認または修正する必要がある。

ENVIRONMENT_ERROR:
環境原因を解消する必要がある。

Unit Test Skillから
他Agentを直接起動してはいけません。

Unit Test Agentを経由して
SDLC Orchestratorへ返却してください。


# Regression Rules

Defectが検出された場合、
以下を必須とします。

1. 原因を特定する
2. 正しい工程で修正する
3. Regression Testの有無を確認する
4. 必要ならRegression Testを追加する
5. Failureを検出したTestを再実行する
6. 関連Testを再実行する
7. Unit Test Suite全体を再実行する
8. Coverageを再計測する
9. 同一Failureが再発しないことを確認する

修正だけで終了してはいけません。


# Test Quality Rules

以下のようなTestを作成してはいけません。

- 常にPASSするTest
- Assertionが存在しないTest
- Production Codeと同じロジックをTest側に再実装したTest
- Requirementを確認していないTest
- 実装詳細だけを固定してRequirementを確認していないTest
- Test実行順序へ依存するTest
- Production環境へ依存するTest
- 共有状態へ不要に依存するTest
- Sleepなど不安定な時間待ちへ依存するTest
- Coverageだけを増やすためのTest


# Database Test Rules

DB TestではUnit Test Policyを正とします。

Service / Domain等で
DBそのものの動作がTest対象でない場合は、
MockまたはStubを利用します。

Repository / DAO等で
実DB挙動がTest対象となる場合は、
Dockerコンテナ等のDisposable Databaseを利用します。

禁止:

- Production DB
- Production Credential
- Shared Test DBへの必須依存
- Production Dataへの依存
- 固定された既存データへの依存

Container DBが必要なのに
Production Codeが接続先を差し替えられない場合は、
IMPLEMENTATION_ERRORとして扱ってください。


# Traceability

Unit Test工程では、
以下のトレーサビリティを維持してください。

Requirement
  ↓
ADR
  ↓
Implementation
  ↓
Unit Test

最低限以下を記録してください。

- Requirement ID
- Related ADR
- Implementation File / Symbol
- Unit Test File
- Unit Test Case
- 適用Criterion
- Test Result

Requirement IDやADR IDを
Unit Test Skillが変更してはいけません。

# Deterministic Validation

最終Unit Test Suite実行後、
以下の機械判定用成果物を生成してください。

- JUnit XML
- Coverage Summary
- Unit Test Evidence

標準配置:

`reports/unit-test/junit.xml`

`reports/unit-test/coverage-summary.json`

`reports/unit-test/unit-test-evidence.json`

その後、以下を実行してください。

`python .github/skills/unit-test/scripts/validate_unit_test.py`

ValidatorがFAILの場合は、
Unit Test工程をSUCCESSとしてはいけません。

FAIL原因を確認し、
適切な工程で修正した後に
Unit Test Suite全体を再実行し、
ValidatorがPASSすることを確認してください。

# Completion Check

Unit Test Skillの処理完了前に、
以下を確認してください。

- Unit Test Policyを読み込んだ
- 現在有効なTest Criteriaをすべて読み込んだ
- 要件定義成果物を確認した
- Accepted ADRを確認した
- Implementation Traceabilityを確認した
- 単体テスト可能なRequirementを特定した
- RequirementとTestを対応付けた
- 必要なTest Caseを作成した
- DB Test StrategyがPolicyに従っている
- 全Unit Testを実行した
- Coverageを計測した
- Coverage基準を満たした
- Requirement Coverageを満たした
- Criteria Coverageを満たした
- Failed Testが0件である
- Error Testが0件である
- 未許可Skipped Testが0件である
- Flaky Testが残っていない
- 検出Defectがすべて修正済みである
- 必要なRegression Testが存在する
- 修正対象Testを再実行した
- 関連Testを再実行した
- Unit Test Suite全体を再実行した
- 修正後の全Unit TestがPASSした
- 未解決IMPLEMENTATION_ERRORが存在しない
- 未解決ADR_REQUIREDが存在しない
- 未解決REQUIREMENT_ERRORが存在しない


# Output

処理完了後、
Unit Test Agentが判断できるように
以下を返してください。

status:
  SUCCESS | IMPLEMENTATION_FIX_REQUIRED | ADR_REQUIRED | BLOCKED | FAILED

test_summary:
  total:
  passed:
  failed:
  errors:
  skipped:

coverage:
  statements:
  branches:
  functions:
  lines:
  policy_result:
    PASS | FAIL

requirement_coverage:
  - requirement:
    related_adrs:
      - ADR-xxx
    implementation:
      - path:
        symbol:
    tests:
      - path:
        test:
        criteria:
          - criterion-name
        result:
          PASS | FAIL

criteria_coverage:
  - criterion:
    applicable:
      true | false
    result:
      PASS | NOT_APPLICABLE | FAIL
    reason:

defects:
  - classification:
      TEST_ERROR | IMPLEMENTATION_ERROR | ADR_REQUIRED | REQUIREMENT_ERROR | ENVIRONMENT_ERROR
    related_requirement:
    related_adr:
    failing_test:
    expected:
    actual:
    cause:
    action:
    regression_test:
    rerun:
      target_test:
        PASS | FAIL
      related_tests:
        PASS | FAIL
      full_suite:
        PASS | FAIL

database_tests:
  - target:
    strategy:
      MOCK | CONTAINER | NOT_APPLICABLE
    production_database_used:
      false
    shared_database_used:
      false

validation:
  all_tests_passed:
    PASS | FAIL
  coverage:
    PASS | FAIL
  requirement_coverage:
    PASS | FAIL
  criteria_coverage:
    PASS | FAIL
  regression:
    PASS | FAIL
  skipped_tests:
    PASS | FAIL
  flaky_tests:
    PASS | FAIL
  unresolved_errors:
    PASS | FAIL

summary:
  Unit Test工程で実施した内容の要約