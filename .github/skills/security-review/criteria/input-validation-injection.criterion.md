# Input Validation and Injection Criterion

## Purpose

External InputがSecurity Boundaryを越える際に
安全に処理されていることを確認する。

## Applies To

- REQUIREMENTS
- ARCHITECTURE
- IMPLEMENTATION
- UNIT_TEST
- INTEGRATION_TEST
- FULL

## Required Review

以下を確認する。

- Trust BoundaryでValidationされている
- Client-side Validationだけに依存していない
- DB Queryへ危険な文字列結合をしていない
- Command Inputが安全に扱われている
- Path Inputが安全に扱われている
- Template等へのInputが安全に扱われている
- Invalid Input BehaviorがTestされている

## Pass Conditions

MaterialなInput Validation不足または
Injection Riskが存在しない。

## Not Applicable

External Inputを扱わない場合は
理由付きNOT_APPLICABLE可。

## Failure Handling

- INPUT_VALIDATION_ISSUE
- INJECTION_RISK

## Evidence

- Input Source
- Trust Boundary
- Sink
- File / Symbol
- Test
