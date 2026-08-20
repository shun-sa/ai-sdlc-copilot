# End-to-End Flow Integration Criterion

## Purpose

複数のFR、Component、API、Database等を跨ぐ
業務フローまたはUser Storyについて、
開始から完了まで期待された連携が
成立することを確認する。

## Applies To

以下に適用する。

- 業務フロー
- User Story
- Acceptance Criteria
- 複数FRを組み合わせた処理
- Frontend → Backend → Database
- Authentication → Business Function
- 登録 → 更新 → 参照等の一連処理

## Required Test Design

Requirementに
業務フローまたはUser Storyが存在する場合、
一連の処理として確認する。

## Happy Path

代表的な正常業務フローについて、
開始から完了まで確認する。

## Multi-Function Flow

複数Requirementを組み合わせて
成立する処理について確認する。

単一FR単体では成功していても、
組み合わせた場合に問題がないことを確認する。

## Data Continuity

前工程で生成したDataが
後続処理へ正しく引き継がれることを確認する。

## Authentication Continuity

認証状態が必要なFlowでは、
一連の処理で正しく維持されることを確認する。

## Completion Condition

Acceptance Criteriaや
FRの完了条件が最終的に満たされることを確認する。

## Error Flow

Requirementで定義されている場合、
途中Failure時のFlowについても確認する。

## Pass Conditions

以下をすべて満たすこと。

1. 必要な業務フローを確認している
2. 複数Componentが正しく連携する
3. 複数Requirement間の連携が成立する
4. Dataが正しく引き継がれる
5. 最終的なCompletion Conditionを満たす
6. 必要なError Flowが正しく動作する

## Not Applicable

対象Requirementが完全に独立しており、
複数Componentや複数機能のFlowを持たない場合は
NOT_APPLICABLEとできる。

理由を記録する。

## Failure Handling

業務フロー内のProduction Codeに問題がある場合は
IMPLEMENTATION_ERRORとして扱う。

Requirement間の矛盾によってFlowを確定できない場合は
REQUIREMENT_ERRORとして扱う。

重要な設計判断不足の場合は
ADR_REQUIREDとして扱う。

## Evidence

最低限以下を記録する。

- Related Requirement IDs
- Related ADRs
- Case ID
- Origin
- Flow
- Expected Result
- Actual Result
- PASS / FAIL
