# State Transition Integration Criterion

## Purpose

複数の機能またはComponentを跨いで
状態が変化する処理について、
Requirementで定義された状態遷移が
正しく実現されていることを確認する。

## Applies To

以下のような処理に適用する。

- Status変更
- Workflow
- Approval
- Reservation
- Order
- Registration
- Cancellation
- 複数画面・複数APIを跨ぐ状態遷移

## Required Test Design

Requirementで定義された状態について、
必要なTransitionを確認する。

## Valid Transition

許可された状態遷移が成功することを確認する。

## Invalid Transition

禁止された状態遷移が拒否されることを確認する。

## Persistent State

状態変更後、
Database等に期待する状態が保存されていることを確認する。

## Subsequent Behavior

状態変更後の後続処理が
新しい状態に応じて正しく動作することを確認する。

## Failure Transition

処理途中でFailureした場合に
不正な状態へ遷移していないことを確認する。

## Pass Conditions

以下をすべて満たすこと。

1. Requirement上必要な状態遷移を確認している
2. 有効なTransitionが成功する
3. 無効なTransitionが拒否される
4. 永続化状態が正しい
5. 状態変更後の後続処理が正しい
6. Failure時に不正状態が残らない

## Not Applicable

対象Requirementに
状態という概念が存在しない場合は
NOT_APPLICABLEとできる。

理由を記録する。

## Failure Handling

Production Codeの状態遷移実装に問題がある場合は
IMPLEMENTATION_ERRORとして扱う。

状態モデルそのものが不明確な場合は
REQUIREMENT_ERRORまたはADR_REQUIREDとして扱う。

## Evidence

最低限以下を記録する。

- Requirement ID
- Case ID
- Origin
- Initial State
- Operation
- Expected State
- Actual State
- PASS / FAIL
