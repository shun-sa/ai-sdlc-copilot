---
name: integration-test
description: >
  要件定義成果物、Accepted ADR、Production Codeを基に
  結合試験ケースを生成・実行するためのSkill。
  AI生成ケースと外部持込ケースを明確に区別し、
  Required Coverageとの差分からケースの抜け漏れを分析する。
  外部ケースは意味を変更せず取り込み、
  AIケース・外部ケースそれぞれの試験結果、
  不具合原因、不具合数、不具合箇所、Coverage差分を
  reports/integration-test配下へ出力する。
user-invocable: false
disable-model-invocation: false
---

# Integration Test Skill

## Purpose

このSkillは、
システムを構成する複数のComponent、Module、
Service、API、Database等の連携を
自動的に検証するための標準手順を定義します。

結合試験では、
AI自身がTest Caseを作成・実行します。

さらに、
外部で作成された結合試験項目表が提供された場合は、
その内容を変更せず取り込み、
AI生成Caseとは独立した評価データとして実行します。

以下を最終的に確認してください。

- AIがどのCaseを生成したか
- External CaseにどのCaseが存在したか
- 双方に共通するCoverage
- AIのみがCoverageした項目
- ExternalのみがCoverageした項目
- 双方から漏れたCoverage
- AI Caseが検出したDefect
- External Caseが検出したDefect
- 双方が検出したDefect
- Error原因
- Error数
- Error箇所

# Policy

結合試験の品質基準は、
以下のPolicyを唯一の正としてください。

`.github/skills/integration-test/policy/integration-test-policy.yaml`

Test Result、Final Coverage、
External Case保護、
Error許容数、
Regression、
Report等の判定基準を
このSKILL.mdへ固定値として定義してはいけません。

必ずPolicyを読み込んで判断してください。


# Test Criteria

具体的な結合試験観点は、
以下のDirectoryから取得してください。

`.github/skills/integration-test/criteria/`

Policyで指定されたPatternに一致する
Criterionファイルをすべて読み込んでください。

標準:

`*.criterion.md`

各Criterionについて、

- 適用対象か
- PASSか
- NOT_APPLICABLEか
- FAILか

を判定してください。

NOT_APPLICABLEの場合は、
理由を必ず記録してください。

Criterionの追加・削除によって
結合試験観点を変更できる状態を維持してください。

# Output Directory

結合試験実行時に、
以下のDirectoryを作成してください。

`reports/integration-test/`

事前作成されている必要はありません。

実行時に必要に応じて作成してください。


# External Test Case Format

外部結合試験項目表は、
以下のCanonical Columnsを使用します。

必須項目:

- case_id
- title
- requirement_id
- test_category
- criterion
- steps
- expected_result
- execution_type

任意項目:

- related_adr
- precondition
- input
- notes

外部ファイル内のCaseは、
取り込み後に以下を設定してください。

origin:
  EXTERNAL

元のCase IDは維持してください。

必要に応じて内部管理用IDを追加できますが、
元Case IDを失ってはいけません。


# AI Test Case Format

AI生成Caseも
外部Caseと同じCanonical Structureを使用してください。

追加メタデータ:

origin:
  AI_GENERATED

generation_stage:
  INITIAL | GAP_FILL


# Procedure

## Step 1. Unit Test完了を確認する

結合試験開始前に、
Unit Test工程が完了していることを確認してください。

未解決Unit Test Errorが存在する場合は、
結合試験を開始してはいけません。


## Step 2. 要件定義成果物を確認する

結合試験観点で要件全体を確認してください。

特に以下を確認します。

- Acceptance Criteria
- 業務フロー
- ユーザーストーリー
- 共通機能要件
- 認証・認可
- 共通エラー仕様
- NFR
- データモデル
- FR
- FR間連携
- 制約条件
- Out of Scope


## Step 3. Accepted ADRを確認する

関連するAccepted ADRを確認してください。

特に以下を確認します。

- Related Requirements
- Decision
- Consequences
- AI Guardrails

結合試験の期待結果を
Accepted ADRに反する形で定義してはいけません。


## Step 4. Integration Pointsを抽出する

結合試験対象となる連携箇所を抽出してください。

例:

- Frontend → Backend
- API → Service
- Service → Repository
- Application → Database
- Service → External Service
- Authentication → API
- Authorization → Business Function
- 複数Module間
- 複数FR間
- 状態遷移
- Transaction


## Step 5. Required Coverage Setを作成する

AI Test Caseを作る前に、
Requirements、Accepted ADR、
Integration Pointから
本来必要なIntegration Test Coverageを作成してください。

Required Coverageには最低限以下を持たせます。

- coverage_id
- requirement_id
- related_adr
- integration_point
- test_category
- criterion
- condition
- expected_behavior

Required Coverageを
AI CaseまたはExternal Caseから逆算してはいけません。


## Step 6. AI INITIAL Caseを生成する

Required Coverageそのものの一覧を
機械的に1:1変換するのではなく、
RequirementsとADRを基に
結合試験Caseを生成してください。

この時点で生成したCaseは必ず、

origin:
  AI_GENERATED

generation_stage:
  INITIAL

としてください。


## Step 7. AI INITIAL Caseを固定する

INITIAL Case生成後は、
そのCase Setを初期AI生成結果として固定してください。

Coverage Gapを確認した後に
INITIAL Caseを追加・変更してはいけません。

これにより、
AIが最初に生成できたCaseのCoverageを
後から評価可能にしてください。


## Step 8. External Caseの存在を確認する

AI INITIAL Caseを生成・固定した後に、
External Test Caseの存在を確認してください。

標準配置先:

`external-tests/integration-test/`

External Caseを
AI INITIAL Case生成前に読み込んではいけません。

これによりExternal Caseの内容が
AI INITIAL Case生成へ影響することを防止します。

External Test Caseが存在する場合は、

`external_input.provided = true`

`external_input.user_confirmed_without_external_cases = false`

として最終的なIntegration Test Evidenceへ記録してください。

この時点でExternal Caseを読み込む前に、
既に生成済みのAI INITIAL Caseを変更してはいけません。


## Step 9. External Caseが存在しない場合

External Caseが存在しない場合、
自動的にExternal Caseなしとして
処理を継続してはいけません。

以下のStatusをIntegration Test Agentへ返してください。

`EXTERNAL_TEST_INPUT_REQUIRED`

SDLC Orchestratorからユーザーへ、
以下のTemplateを使用して
External Test Caseを配置するよう案内してください。

`.github/skills/integration-test/templates/integration-test-case-template.xlsx`

標準配置先:

`external-tests/integration-test/`

ユーザーによる入力を待つ間も、
既に生成したAI INITIAL Caseを変更してはいけません。


## Step 10. External Caseなしの明示的選択

External Test Caseが存在しない場合でも、
Integration Test AgentまたはSkill自身の判断で
External Caseなしとして処理を継続してはいけません。

ユーザーが明示的に
External Test Caseを使用しないことを選択した場合、
SDLC Orchestratorから以下の情報が渡されます。

`external_cases_confirmed_absent: true`

この値が明示的に渡された場合のみ、
External Caseなしで処理を継続できます。

Integration Test AgentまたはSkill自身で
`external_cases_confirmed_absent`をtrueにしてはいけません。

External Caseなしで続行する場合は、

`.github/skills/integration-test/scripts/normalize_external_test_cases.py --allow-none`

相当の処理を実行してください。

その場合、最終的なIntegration Test Evidenceへ
以下を記録してください。

`external_input.provided = false`

`external_input.user_confirmed_without_external_cases = true`

単にFileが存在しないことを理由に、
この状態へ遷移してはいけません。

以下の状態で処理を継続してはいけません。

`external_input.provided = false`

`external_input.user_confirmed_without_external_cases = false`


## Step 11. External Caseを読み込む

External Test Caseが提供された場合、
以下を使用して正規化してください。

`.github/skills/integration-test/scripts/normalize_external_test_cases.py`

正規化結果:

`reports/integration-test/external-test-cases.normalized.json`

External Caseはすべて、

`origin: EXTERNAL`

として扱ってください。

元Fileおよび元Caseの意味を変更してはいけません。

正規化結果から取得した
External CaseおよびExternal Case Integrity情報は、
後続のIntegration Test Evidence生成時に使用してください。

External Test Caseが提供されている場合、
最終Evidenceでは必ず以下となる必要があります。

`external_input.provided = true`

`external_input.user_confirmed_without_external_cases = false`


## Step 12. External Caseを正規化する
External CaseをCanonical Formatへ変換してください。

形式変換のみ許可します。

禁止:

- Expected Result変更
- Input変更
- Step変更
- Case削除
- 意味の変更

変換不能なCaseは削除せず、
AUTOMATION_BLOCKED候補として保持してください。


## Step 13. Coverage Keyを生成する

Required Coverageと
AI / External Caseを比較するため、
CaseごとにCoverage Keyを生成してください。

Coverage Keyは最低限以下を使用して生成します。

- Requirement ID
- Integration Point
- Test Category
- Criterion
- Condition

文言が異なっていても
意味的に同じCoverageであれば
同一Coverageとして比較できるようにしてください。


## Step 14. Case Coverageを比較する

Required Coverageに対し、

- AI INITIAL Case
- External Case

のCoverage状況を比較してください。

以下へ分類します。

COMMON

AI_ONLY

EXTERNAL_ONLY

MISSING


## Step 15. Initial Coverage Metricsを保存する

Gap Fill前に必ず以下を保存してください。

- Required Coverage数
- COMMON数
- AI_ONLY数
- EXTERNAL_ONLY数
- MISSING数
- AI INITIAL Coverage Rate
- External Coverage Rate
- Combined Initial Coverage Rate

後からGap Fill Caseを追加して
この値を書き換えてはいけません。


## Step 16. Coverage Gapを分析する

MISSINGとなったCoverageを
Gapとして記録してください。

最低限以下を記録します。

- Gap ID
- Requirement ID
- Related ADR
- Criterion
- Missing内容
- AI INITIAL
- External


## Step 17. AI GAP_FILL Caseを生成する

品質保証のため、
MISSING Coverageを補うTest Caseを生成してください。

追加Caseは必ず、

origin:
  AI_GENERATED

generation_stage:
  GAP_FILL

としてください。


## Step 18. Final Test Planを作成する

以下を統合してください。

- AI INITIAL
- AI GAP_FILL
- EXTERNAL

以下へ保存します。

`reports/integration-test/integration-test-plan.json`


## Step 19. Test Environmentを準備する

結合試験に必要な環境を自動的に準備してください。

可能な限り、
再現可能でDisposableな環境を使用してください。

DBを利用する場合は、
Production DBを使用してはいけません。

Docker Container等による
一時的なテストDBを使用してください。


## Step 20. Test Dataを準備する

各Test Caseに必要なTest Dataを準備してください。

以下へ依存してはいけません。

- Production Data
- 手動作成済み共有データ
- 前回試験の残データ

Test間の状態依存を最小化してください。


## Step 21. Automation Feasibilityを判定する

各Caseについて
AIによる自動実行可能性を確認してください。

実行可能:

AUTOMATABLE

意味を変更せず自動実行できない:

AUTOMATION_BLOCKED

AUTOMATION_BLOCKED Caseを
勝手に削除してはいけません。


## Step 22. External Specification Conflictを確認する

External CaseのExpected Resultと
Requirement / Accepted ADRを比較してください。

矛盾する場合は、

TEST_SPEC_CONFLICT

として記録してください。

External Caseを変更して解消してはいけません。


## Step 23. 結合試験を実装する

AI INITIAL Case、
AI GAP_FILL Case、
External Caseについて
自動実行可能なTestを実装してください。

External CaseのTest Codeを作成する際も、
External Caseの意味を変更してはいけません。


## Step 24. 結合試験を実行する

すべてのAUTOMATABLE Caseを実行してください。

Caseごとに最低限以下を記録します。

- Case ID
- Origin
- Generation Stage
- Requirement
- Related ADR
- Expected Result
- Actual Result
- PASS / FAIL
- Execution Time
- Error Message


## Step 25. Errorを分類する

Failureについて以下へ分類してください。

- TEST_ERROR
- IMPLEMENTATION_ERROR
- ADR_REQUIRED
- REQUIREMENT_ERROR
- ENVIRONMENT_ERROR
- TEST_SPEC_CONFLICT
- AUTOMATION_BLOCKED


## Step 26. Error Locationを特定する

可能な限り、
Error発生箇所を特定してください。

最低限以下を確認します。

- Layer
- File
- Symbol
- API
- Database
- Service
- External Interface

確定できない情報を
推測で断定してはいけません。


## Step 27. Defectを集約する

複数Test Caseが
同じProduction DefectによってFAILする場合があります。

Case Failure数と
Unique Defect数を区別してください。

同じDefectと判断する場合は、
最低限以下を確認します。

- Root Cause
- Error Location
- Requirement
- Failure内容


## Step 28. Defect Detection Sourceを比較する

各Defectについて、
どのCase Sourceが検出したか確認してください。

分類:

COMMON_DEFECT

AI_ONLY_DEFECT

EXTERNAL_ONLY_DEFECT

AI GAP_FILLのみで検出した場合も
AIによる検出として扱いますが、
INITIALとGAP_FILLの内訳は保持してください。


## Step 29. TEST_ERRORを修正する

TEST_ERRORは
Integration Test工程内で修正できます。

ただし、

- Expected Result変更
- Case削除
- Assertion弱体化

によってPASSさせてはいけません。


## Step 30. IMPLEMENTATION_ERRORを返却する

IMPLEMENTATION_ERRORの場合、
Integration Test Skill自身で
Production Codeを変更してはいけません。

以下を整理してください。

- Case ID
- Requirement ID
- Related ADR
- Expected
- Actual
- Root Cause
- Error Location

Implementation Agentでの修正が必要であることを
Integration Test Agentへ返却してください。


## Step 31. ADR_REQUIREDを返却する

重要Architecture Decisionが不足している場合は
ADR_REQUIREDとして返却してください。

Test側で設計判断を確定してはいけません。


## Step 32. REQUIREMENT_ERRORを返却する

Requirementに問題がある場合は
Requirementを直接修正せず、
BLOCKEDとして返却してください。


## Step 33. 修正後に対象Caseを再実行する

修正完了後、
最初にFailureしたCaseを再実行してください。

PASSしない場合は
修正完了として扱ってはいけません。


## Step 34. 関連Caseを再実行する

同じRequirement、Module、
Integration Point等に関連するCaseを再実行してください。


## Step 35. Integration Test Suite全体を再実行する

修正後は必ず
Integration Test Suite全体を再実行してください。

すべてPASSするまで
工程を完了してはいけません。


## Step 36. Error Reportを生成する

以下を生成してください。

`reports/integration-test/error-report.json`

`reports/integration-test/error-report.md`

最低限以下を含めます。

- Failed Case数
- Unique Defect数
- Error原因
- Error箇所
- Requirement
- Related ADR
- Expected
- Actual
- 修正内容
- 再試験結果

さらに、

- AI INITIAL
- AI GAP_FILL
- EXTERNAL

で分離集計してください。


## Step 37. Coverage Gap Reportを生成する

以下へ出力してください。

`reports/integration-test/coverage-gap-report.json`

最低限以下を含めます。

- Required Coverage数
- COMMON
- AI_ONLY
- EXTERNAL_ONLY
- MISSING
- AI INITIAL Coverage Rate
- External Coverage Rate
- Combined Initial Coverage Rate
- Gap Fill後Final Coverage Rate
- Gap一覧


## Step 38. Case Comparison Reportを生成する

以下へ出力してください。

`reports/integration-test/case-comparison.json`

AI INITIAL CaseとExternal Caseを比較し、

- COMMON
- AI_ONLY
- EXTERNAL_ONLY
- MISSING

を確認可能にしてください。


## Step 39. Integration Test Reportを生成する

以下を生成してください。

`reports/integration-test/integration-test-report.json`

`reports/integration-test/integration-test-report.md`

人向けReportでは最低限以下を表示してください。

1. Test Summary
2. AI / External Case数
3. Coverage比較
4. Coverage Gap
5. Error数
6. Unique Defect数
7. Error原因別件数
8. AI / External別Error件数
9. COMMON_DEFECT
10. AI_ONLY_DEFECT
11. EXTERNAL_ONLY_DEFECT
12. Error箇所
13. 修正結果
14. 再試験結果


## Step 40. Traceability Evidenceを生成する

以下へ出力してください。

`reports/integration-test/integration-test-evidence.json`

最低限以下を記録します。

Requirement
  ↓
ADR
  ↓
Implementation
  ↓
Unit Test
  ↓
Integration Test

各Integration Testについて、

- Case ID
- Origin
- Requirement ID
- Related ADR
- Integration Point
- Test Result

を記録してください。


## Step 41. JUnit XMLを生成する

利用するTest Frameworkが対応している場合、
JUnit XML形式で結果を出力してください。

標準配置:

`reports/integration-test/junit.xml`


## Step 42. Final Error Check

以下が残っていないことを確認してください。

- Failed Case
- Error Case
- 未解決IMPLEMENTATION_ERROR
- ADR_REQUIRED
- REQUIREMENT_ERROR
- TEST_SPEC_CONFLICT
- AUTOMATION_BLOCKED
- ENVIRONMENT_ERROR
- 原因不明Error


## Step 43. Final Coverage Check

Required Coverageについて
最終的にすべてTestされていることを確認してください。

Initial CoverageのMISSINGは
実験結果として保持します。

ただし品質保証上は、
GAP_FILL Caseによって最終Coverageを補完してください。


# External Case Protection Rules

External Caseは実験データです。

以下を絶対に変更してはいけません。

- Case ID
- Testの意味
- Inputの意味
- Stepの意味
- Expected Result
- 判定条件

元ファイル自体を書き換えてはいけません。


# Experimental Metrics

実験用に最低限以下を保存してください。

- AI INITIAL Case Count
- AI GAP_FILL Case Count
- External Case Count
- COMMON Coverage Count
- AI_ONLY Coverage Count
- EXTERNAL_ONLY Coverage Count
- MISSING Coverage Count
- AI INITIAL Coverage Rate
- External Coverage Rate
- Combined Initial Coverage Rate
- Final Coverage Rate
- AI INITIAL Defect Detection Count
- AI GAP_FILL Defect Detection Count
- External Defect Detection Count
- COMMON_DEFECT Count
- AI_ONLY_DEFECT Count
- EXTERNAL_ONLY_DEFECT Count


# Completion Check

Integration Test Skill完了前に、
以下をすべて確認してください。

- Unit Test工程が完了している
- Requirementsを確認した
- Accepted ADRを確認した
- Required Coverageを作成した
- AI INITIAL Caseを生成した
- INITIAL Caseを固定した
- External Caseをすべて取り込んだ、または未提供を確認した
- External Caseを変更していない
- AI / Externalを区別している
- Case Coverage比較を実施した
- MISSINGを特定した
- Initial Coverage Metricsを保存した
- 必要なGAP_FILL Caseを作成した
- Test Environmentを準備した
- すべてのAUTOMATABLE Caseを実行した
- Error原因を分類した
- Error箇所を分析した
- Unique Defectを集約した
- AI / ExternalのDefect差分を確認した
- 必要な修正が完了した
- Failure Caseを再実行した
- 関連Caseを再実行した
- 全Integration Testを再実行した
- 最終実行がすべてPASSした
- 未解決Errorが0件である
- Required Coverageを最終的に満たしている
- 必要なReportをすべて生成した


# Output

処理完了後、
Integration Test Agentへ以下を返してください。

status:
  SUCCESS | IMPLEMENTATION_FIX_REQUIRED | ADR_REQUIRED | BLOCKED | FAILED

test_summary:
  ai_initial:
    total:
    passed:
    failed:
  ai_gap_fill:
    total:
    passed:
    failed:
  external:
    provided:
      true | false
    total:
    passed:
    failed:

coverage:
  required:
  common:
  ai_only:
  external_only:
  missing:
  ai_initial_coverage_rate:
  external_coverage_rate:
  combined_initial_coverage_rate:
  final_coverage_rate:

defects:
  total_unique:
  common:
  ai_only:
  external_only:

reports:
  integration_test_plan:
  case_comparison:
  coverage_gap_report:
  integration_test_evidence:
  error_report_json:
  error_report_md:
  integration_test_report_json:
  integration_test_report_md:
  junit:

summary:
  Integration Test工程で実施した内容の要約