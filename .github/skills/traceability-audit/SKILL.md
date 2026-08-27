---
name: traceability-audit
description: >
  Requirements、Architecture Decision、Production Code、
  Unit Test、Integration Testを解析し、
  Derived Trace Mapを生成するとともに、
  成果物間のTraceabilityを監査するSkill。
  前方向・逆方向のTraceability、参照切れ、孤立Artifact、
  Test Coverage Evidence、Stale Evidenceを確認し、
  問題の原因工程を特定する。
user-invocable: false
disable-model-invocation: false
---

# Purpose

このSkillは、
SDLC成果物間のTraceabilityを独立監査します。

目的は単にIDが書かれていることではなく、

Requirement
→ Architecture Decision
→ Implementation
→ Test

が意味的にも成立していることを確認することです。

また、
現在のSource Artifactから成果物間の関係を抽出し、

`reports/traceability/trace-map.json`

として生成します。

Trace Mapは、
Source Artifactから再生成可能なDerived Indexであり、
Source of Truthではありません。

既存Trace Mapを
現在も正しいMappingであるという前提で
再利用してはいけません。


# Policy

以下を唯一の合否基準として使用してください。

`.github/skills/traceability-audit/policy/traceability-policy.yaml`


# Output

以下へ出力してください。

`reports/traceability/ast-index.json`

`reports/traceability/trace-map.json`

`reports/traceability/traceability-report.json`

`reports/traceability/traceability-report.md`

# Procedure

## Step 1. Audit Scopeを確認する

SDLC Orchestratorから
audit_scopeを取得してください。

対応値:

- ARCHITECTURE
- IMPLEMENTATION
- UNIT_TEST
- INTEGRATION_TEST
- FULL


## Step 2. Requirementsを読み込む

以下を読み込んでください。

`docs/requirements/requirements.md`

`docs/requirements/features/`

実在するRequirement ID一覧を作成してください。

存在しないIDを追加してはいけません。


## Step 3. Global Requirementを抽出する

IDがないProject-wide Requirementについては、
IDを生成せずSource Referenceとして保持してください。

例:

`docs/requirements/requirements.md#認証・認可`


## Step 4. ADRを読み込む

`docs/adr/`

を読み込んでください。

各ADRについて以下を取得します。

- ADR ID
- Status
- Related Requirements
- Decision
- AI Guardrails


## Step 5. ADR Referenceを検証する

各ADRのRelated Requirementsについて、
実在するRequirementか確認してください。

存在しないRequirementを参照していた場合:

`INVALID_REQUIREMENT_REFERENCE`


## Step 6. Scopeに応じた有効ADRを特定する

`audit_scope=ARCHITECTURE`の場合は、
Acceptance候補となるProposed ADRを
Traceability監査対象として扱ってください。

この時点では、
Proposedであること自体を
Traceability Failureとして扱ってはいけません。

`audit_scope=IMPLEMENTATION`、
`UNIT_TEST`、
`INTEGRATION_TEST`、
`FULL`
の場合は、
Accepted ADRのみを
現在有効なArchitecture Decisionとして扱ってください。

Superseded ADRを現在Decisionとして使用してはいけません。


## Step 7. Requirement → ADRを確認する

Architecture Decisionを必要とするRequirementについて、
Scopeに応じた適切なADRが存在することを確認してください。

`audit_scope=ARCHITECTURE`では、
Acceptance候補となるProposed ADRとの
Traceabilityを確認してください。

Implementation以降では、
Accepted ADRとのTraceabilityを確認してください。

すべてのRequirementへ
ADRを強制してはいけません。


## Step 8. AST Indexを生成する

現在のRepositoryから、決定論的なSource構造Evidenceを生成してください。

実行:

`python .github/skills/traceability-audit/scripts/build_traceability_ast_index.py`

出力:

`reports/traceability/ast-index.json`

AST IndexはDerived Indexであり、Source of Truthではありません。

最低限以下を保持します。

- Source Fingerprint
- Analyzer Status
- Production Symbol / FQN
- Test Symbol / FQN
- Symbol間Call
- Test Assertion Count

対応Analyzer:

- Python: Python標準`ast`
- Java: JDK Compiler Tree API
- TypeScript / JavaScript: TypeScript Compiler API

対象LanguageのSourceが存在するのにResolverが利用できない場合の扱いはPolicyに従ってください。

既存AST Indexを現在も正しいEvidenceとして再利用してはいけません。
Source Artifactから毎回再生成してください。


## Step 9. Implementation Symbol / FQNを検証する

Implementation Mappingの対象がAST対応Sourceの場合、
AST Indexを使って以下の実在を確認してください。

- file
- symbol
- qualified_name

AST対応Sourceでは、Policyが要求する場合、
`symbol`および`qualified_name`をTrace Mapへ必ず記録してください。

存在しないSymbol / FQNを推測してはいけません。


## Step 10. Repository全Production Symbolを確認する

AST IndexのProduction Symbol一覧と、
Requirement / ADRから導出したImplementation Mappingを比較してください。

正当な除外理由がなく、どのRequirement / ADRにも紐付かないPublic Implementationが存在する場合:

`ORPHAN_IMPLEMENTATION`

file-only Mappingは当該File内のSymbolをCoverage済みとして扱えます。
Class Mappingは当該Class配下MethodをCoverage済みとして扱えます。

Private / Generated / Migration等の除外条件はPolicyに従ってください。


## Step 11. Implementationを調査する

Production Codeを調査してください。

Requirementおよび
現在のScopeで有効なADRが
どのProduction Artifactへ実装されているか確認します。

Implementation Mappingには、
以下を保持してください。

- file
- symbol
- qualified_name

`file`は必須です。
AST対応Sourceでは`symbol`および`qualified_name`も必須です。

`symbol`は、
Class、Method、Function、Component等を
識別できる場合に記録してください。

`qualified_name`は、
対象Language / Frameworkで
安定したQualified Nameを取得可能な場合に記録してください。

例:

Java:

`com.example.user.UserService.registerUser`

TypeScript:

file:

`src/features/user/useCreateUser.ts`

symbol:

`useCreateUser`

AST対応Sourceでは、Policyに従い
`symbol`および`qualified_name`を必須としてください。

AST Resolverが対象Languageをサポートしていない場合のみ、
`fail_when_resolver_unavailable=false`のPolicyで明示的に許可されているときに限り、
`qualified_name`未取得だけを理由としたFailureを回避できます。

存在しないsymbolやqualified_nameを
推測で生成してはいけません。


## Step 12. Requirement → Implementationを確認する

Implementation-responsible Requirementについて、
対応するProduction Artifactを確認してください。

存在しない場合:

`IMPLEMENTATION_TRACEABILITY_MISSING`


## Step 13. ADR → Implementationを確認する

Accepted ADRのDecisionおよびAI Guardrailsが
Production Codeへ反映されているか確認してください。

重大な不一致:

`ADR_IMPLEMENTATION_MISMATCH`


## Step 14. Unit Test Evidenceを読み込む

以下を確認してください。

`reports/unit-test/unit-test-evidence.json`

`reports/unit-test/validation-result.json`

Unit Test Codeも必要に応じて確認してください。

Unit Test Mappingでは以下を取得してください。

- test_id
- file
- symbol
- qualified_name
- implementation_targets
- assertion_count

AST対応Test Codeでは`file`、`symbol`、`qualified_name`を使用し、
`implementation_targets`と`assertion_count`はAST Indexから取得してください。
存在しない値を推測してはいけません。

## Step 15. Requirement → Unit Testを確認する

Unit Test対象Requirementについて、

Requirement
→ Production Code
→ Unit Test

を確認してください。

対応がない場合:

`UNIT_TEST_TRACEABILITY_MISSING`


## Step 16. Unit Testの逆方向を確認する

Unit Testから、
実在するRequirementへTraceできるか確認してください。

正当な理由なくRequirementとの対応がない場合:

`ORPHAN_TEST`


## Step 17. Integration Test Evidenceを読み込む

以下を確認してください。

`reports/integration-test/integration-test-plan.json`

`reports/integration-test/integration-test-evidence.json`

`reports/integration-test/coverage-gap-report.json`

`reports/integration-test/validation-result.json`


## Step 18. Requirement → Integration Testを確認する

Integration Test対象Requirementについて、

Requirement
→ Integration Point
→ Test Case

の対応を確認してください。


## Step 19. AI Caseを確認する

以下を区別してください。

- AI_GENERATED / INITIAL
- AI_GENERATED / GAP_FILL

どちらもRequirementへのTraceabilityを確認します。


## Step 20. External Caseを確認する

origin=EXTERNALのCaseについて、
Requirement IDが実在することを確認してください。

External Caseの内容を修正してはいけません。


## Step 21. Integration Testの逆方向を確認する

Integration Test Caseから
Requirementへ戻れることを確認してください。

不正なCaseは:

`ORPHAN_TEST`

または

`INVALID_REQUIREMENT_REFERENCE`

として扱います。

## Step 22. Code → Test AST Traceabilityを確認する

Unit Test Mappingについて、AST Indexから以下を決定論的に確認してください。

1. Test File / Symbol / qualified_nameが実在する
2. TestからRequirementに紐づくProduction SymbolへCallが到達する
3. Test内にAssertionが存在する

Production内のCall Graphについて、Policyで許可される場合は
`max_call_depth`までTransitive Callを辿って構いません。

Trace MapのUnit Test Mappingには、ASTから確認した以下を記録してください。

- implementation_targets
- assertion_count

AIが意味的に関係があると判断しただけで、
AST上Callが存在しないRelationを物理Edgeとして記録してはいけません。

Integration TestについてもTest CodeのFile / Symbolを特定できる場合は
同じAST Evidenceを補助情報として使用できます。
ただしExternal Test Caseの意味・Steps・Expected Resultは変更してはいけません。


## Step 23. AST EvidenceとSemantic Mappingを統合する

ASTは「物理的に存在する・Callされる」ことを保証し、
Traceability Auditorは「Requirement / ADRと意味的に対応する」ことを監査してください。

ASTだけを理由にRequirementとの意味的対応を作成してはいけません。
AIの意味判断だけを理由に存在しないFQNを作成してはいけません。


## Step 24. Trace Mapを生成する

ここまでに確認した
現在のSource Artifactから、
Trace Mapを生成してください。

出力:

`reports/traceability/trace-map.json`

Trace Map Schema Versionは`2`としてください。

最低限以下を保持してください。

- version
- audit_scope
- ast_index.path
- ast_index.version
- ast_index.source_fingerprint
- requirement_reference
- ADR
- Implementation Mapping
- Unit Test Mapping
- Integration Test Mapping

Implementation Mappingでは、AST対応Sourceについて、

- file
- symbol
- qualified_name

を保持してください。

Unit Test Mappingでは、

- test_id
- file
- symbol
- qualified_name
- implementation_targets
- assertion_count

を保持してください。

Integration Test Mappingでは、
Test Case IDを保持してください。

既存Trace Mapが存在していても、
そのMappingを現在も正しいものとして
そのまま継承してはいけません。

現在のSource Artifactを基準として
Trace Mapを再生成してください。

既存Trace Mapは、
Stale Mappingを調査するための
参考情報として使用できます。

## Step 25. Coverage整合性を確認する

Unit Test Evidence、
Integration Test Evidence、
Coverage Gap Report等のCoverage情報と、
生成したTrace MapのMappingを比較してください。

自己申告されたCoverage率だけで
PASS判定してはいけません。


## Step 26. Stale Evidenceを確認する

Requirements、
Accepted ADR、
Production Codeが変更された後に
後続Testが再実行されているか確認してください。

古いEvidenceが使用されている場合:

`STALE_EVIDENCE`


## Step 27. Orphan ADRを確認する

Accepted ADRが、
RequirementにもImplementationにも
意味的に対応しない場合は調査してください。

正当な理由がない場合:

`ORPHAN_ADR`


## Step 28. Conflictを確認する

同一Requirementについて、

ADR
Implementation
Unit Test
Integration Test

で期待するBehaviorが矛盾していないか確認してください。

矛盾:

`TRACEABILITY_CONFLICT`


## Step 29. Issueを集約する

同じRoot CauseによるIssueは、
必要に応じて1つのIssueへ集約してください。

ただし影響Artifactを失わないようにしてください。


## Step 30. Recommended Routeを決定する

IssueのRoot Causeが存在する
最上流工程を選択してください。

REQUIREMENTS
ARCHITECTURE
IMPLEMENTATION
UNIT_TEST
INTEGRATION_TEST


## Step 31. Coverageを算出する

最低限以下を算出してください。

- Requirement → ADR
- Requirement → Implementation
- Requirement → Unit Test
- Requirement → Integration Test

ADR不要、
Unit Test対象外、
Integration Test対象外の場合は
妥当なN/Aを除外して計算してください。


## Step 32. JSON Reportを生成する

以下へ生成してください。

`reports/traceability/traceability-report.json`

Traceability Mapping本体は
`trace-map.json`を正としてください。

`traceability-report.json`には、
Trace Mapそのものを重複保持せず、
最低限以下の参照を保持してください。

trace_map:
  path: reports/traceability/trace-map.json
  version: 2


## Step 33. Markdown Reportを生成する

以下へ生成してください。

`reports/traceability/traceability-report.md`

人が読める形式で、
最低限以下を記載してください。

- Audit Scope
- Summary
- Coverage
- Missing Traceability
- Invalid References
- Orphan Artifacts
- Stale Evidence
- Issues
- Recommended Route


## Step 34. Final判定

Policyを確認してください。

Blocking Issueが存在する場合はFAILです。

すべての必須Traceabilityが成立している場合のみ
PASSとしてください。


# Traceability Model

基本Traceability:

Requirements
→ Scope上有効なADR
→ Implementation
→ Unit Test
→ Integration Test

`audit_scope=ARCHITECTURE`では、
Acceptance候補となるProposed ADRを
Traceability監査対象として扱います。

Implementation以降では、
Accepted ADRのみを
現在有効なArchitecture Decisionとして扱います。

ただしADRは
すべてのRequirementへ必須ではありません。

# Forward Traceability

以下を確認してください。

Requirement
→ ADR

Requirement
→ Implementation

Requirement
→ Unit Test

Requirement
→ Integration Test


# Reverse Traceability

以下も確認してください。

ADR
→ Requirement

Implementation
→ Requirement / ADR

Unit Test
→ Requirement

Integration Test
→ Requirement


# Global Requirement Handling

IDが存在しないRequirementへ
新しいIDを生成してはいけません。

FileとHeadingを使用してください。


# Failure Handling

Audit Failureを
Traceability Auditor自身で修正してはいけません。

ただし、

`reports/traceability/ast-index.json`

`reports/traceability/trace-map.json`

およびTraceability Reportは
このSkill自身の生成物であるため、
生成・再生成して構いません。

Issueごとにrecommended_routeを設定し、
SDLC Orchestratorへ返してください。

# Completion

以下を満たすまで完了してはいけません。

- 必要なArtifactをすべて監査
- AST Index生成
- Source Fingerprint整合確認
- Symbol / qualified_name実在確認
- Orphan Implementation確認
- Code → Test Call / Assertion確認
- Trace Map生成
- Forward Traceability確認
- Reverse Traceability確認
- Invalid Reference確認
- Orphan Artifact確認
- Stale Evidence確認
- Coverage算出
- Issue分類
- Recommended Route決定
- JSON Report生成
- Markdown Report生成