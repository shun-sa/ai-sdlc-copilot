# Traceability Phase 2–4 Implementation

## 1. Purpose

本変更は、調査結果で示された以下のTraceability機構を既存AI SDLC Frameworkへ追加する。

- FQN / Symbolを利用した物理Artifact特定
- ASTによるFQN / Symbol実在確認
- Repository全体のProduction Symbol列挙と未Mapping実装の検出
- Test CodeのAST解析によるProduction Call / Assertion確認
- `trace-map.json`をSource Code / Test Code外のDerived Indexとして維持

AIによる意味的なRequirement / ADR / Implementation判断はTraceability Auditorに残し、ASTは決定論的Evidenceとして分離する。

---

## 2. Implemented Phases

### Phase 2 — Symbol / FQN AST Validation

以下のLanguageをFramework共通Analyzerで扱う。

| Language | Analyzer |
|---|---|
| Python | Python標準`ast` |
| Java | JDK Compiler Tree API |
| TypeScript / JavaScript | TypeScript Compiler API |

AST対応SourceのImplementation / Unit Test Mappingは原則として以下を保持する。

```json
{
  "file": "src/user_service.py",
  "symbol": "register_user",
  "qualified_name": "src.user_service.register_user"
}
```

Validatorは`file / symbol / qualified_name`が現在のASTに実在するかを確認する。

### Phase 3 — Orphan Implementation Detection

Repository内のProduction SymbolをASTで列挙し、Trace MapでCoverageされていないSymbolを検出する。

```text
Repository Production Symbols
          -
Trace Map Covered Symbols
          =
ORPHAN_IMPLEMENTATION candidates
```

標準Policyでは`ORPHAN_IMPLEMENTATION`を許可しない。

Project固有のGenerated Code、Migration等はPolicyのignore patternで除外可能。

### Phase 4 — Code → Unit Test AST Traceability

Unit Test ASTから以下を決定論的に確認する。

- Test File / Symbol / FQNが存在する
- Testが同じRequirementへMappingされたProduction SymbolをCallしている
- Production内Call Graphを経由した間接CallもPolicy範囲で追跡する
- TestにAssertionが存在する
- Trace Mapの`implementation_targets`がAST実測値と一致する
- Trace Mapの`assertion_count`がAST実測値と一致する

例:

```json
{
  "test_id": "test_register_user",
  "file": "tests/test_user_service.py",
  "symbol": "test_register_user",
  "qualified_name": "tests.test_user_service.test_register_user",
  "implementation_targets": [
    "src.user_service.register_user"
  ],
  "assertion_count": 1
}
```

Integration TestはExternal / API / E2EのようにProduction Functionを直接Callしないケースがあるため、Case IDによるTraceabilityをPrimaryとする。直接AST解析可能なIntegration Testへ将来同じEvidenceを追加することは可能だが、Framework標準では直接FQN Callを必須化しない。

---

## 3. Derived Artifacts

### AST Index

```text
reports/traceability/ast-index.json
```

Source / Test Codeの物理構造を表すDerived Evidence。

主な内容:

- Source fingerprint
- Analyzer availability
- Production symbols
- Test symbols
- Function / Method Call
- Assertion count

### Trace Map v2

```text
reports/traceability/trace-map.json
```

Trace Map Schema Versionを`2`へ更新する。

最低限以下を持つ。

```json
{
  "version": 2,
  "audit_scope": "FULL",
  "ast_index": {
    "path": "reports/traceability/ast-index.json",
    "version": 1,
    "source_fingerprint": "..."
  },
  "entries": []
}
```

Trace MapはSource of Truthではない。
Requirements / ADR / Code / Test変更後は、AST IndexとTrace Mapを現在Artifactから再生成する。

---

## 4. Test File Classification

以下のTest Rootに加えて、`src`配下へTestを共置するFrontend構成も扱う。

標準例:

```text
tests/
test/
src/test/
**/test_*.py
**/*_test.py
**/*.test.ts
**/*.test.tsx
**/*.spec.ts
**/*.spec.tsx
**/__tests__/**
```

これによりReact / TypeScript等の共置TestをProduction Symbolとして誤認しない。

---

## 5. Runtime Requirements

### Python

追加Runtime不要。Python標準`ast`を使用する。

### Java

JDKが必要。JREのみではJava AST Analyzerを実行できない。

### TypeScript / JavaScript

Node.jsからTypeScript Compiler APIを解決できる必要がある。
通常はProjectの`typescript` dependencyを利用する。

標準Policyでは、対象LanguageのSourceが存在するにもかかわらずResolverが利用できない場合はFAILする。

```yaml
symbol_validation:
  fail_when_resolver_unavailable: true
```

Project事情でToolchainを利用できない場合だけ、明示的に`false`へ変更する。

---

## 6. Commands

### AST Index生成

```bash
python .github/skills/traceability-audit/scripts/build_traceability_ast_index.py
```

### Traceability Validation

Traceability AuditorがAST Index / Trace Map / Reportを生成した後に実行する。

```bash
python .github/skills/traceability-audit/scripts/validate_traceability.py
```

Validatorは現在RepositoryからAST Indexを独立再生成し、保存済み`ast-index.json`と一致することも確認する。

### Unit Tests

```bash
python .github/skills/traceability-audit/scripts/test_traceability_ast.py
python .github/skills/traceability-audit/scripts/test_validate_traceability.py
```

---

## 7. Modified Existing Files

```text
.github/agents/sdlc-orchestrator.agent.md
.github/agents/traceability-auditor.agent.md
.github/copilot-instructions.md
.github/skills/traceability-audit/SKILL.md
.github/skills/traceability-audit/policy/traceability-policy.yaml
.github/skills/traceability-audit/scripts/validate_traceability.py
.github/skills/traceability-audit/scripts/test_validate_traceability.py
README.md
docs/ai-sdlc/agent-framework-guide.md
```

---

## 8. New Files

```text
.github/skills/traceability-audit/scripts/traceability_ast.py
.github/skills/traceability-audit/scripts/build_traceability_ast_index.py
.github/skills/traceability-audit/scripts/JavaAstAnalyzer.java
.github/skills/traceability-audit/scripts/typescript_ast_analyzer.cjs
.github/skills/traceability-audit/scripts/test_traceability_ast.py
```

---

## 9. Deliberate Differences from Research Proposal

以下は未実装ではなく、Framework上の意図的な責務分離である。

### FQNをADR本文へ持たせない

ADRはArchitecture DecisionのSource of Truthとして安定させる。
FQNはImplementation構造へ依存するため、Derived Trace Map / AST Index側で扱う。

### Source / Test CodeへRequirement IDを埋め込まない

Traceability維持を目的とした`// REQ-001`等のコメントは使用しない。

### CI製品へ依存しない

AST Builder / Validatorは通常のCLIとして提供する。
GitHub Actions、CodePipeline等、任意のCI/CDから同じCommandを呼び出せる。

### Human ApprovalをTrace Mapの必須状態にしない

Trace Mapは再生成可能なDerived IndexでありSource of Truthではないため、Map自体を人手で維持・承認する方式にはしない。
重要なArchitecture Decisionの承認はADRのProposed → Accepted Lifecycleで扱う。

---

## 10. Validation Result

作成時点で以下を確認済み。

```text
test_traceability_ast.py       8 tests PASS
test_validate_traceability.py 48 tests PASS
Python py_compile             PASS
Java AST synthetic test       PASS
TypeScript AST synthetic test PASS
```
