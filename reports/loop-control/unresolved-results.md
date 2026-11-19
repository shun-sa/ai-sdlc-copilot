# 未解決の検査結果

検査FAILは変更しない。3回の修正後も残った事項を次工程へ引き継ぐ。

## UNRESOLVED-32af0f4a0ca9c80f
- 原因工程: REQUIREMENTS
- 修正・再検査: 3回
- 影響: SEC-REQ-001..004 Blocking: 本番模擬決済、総当たり対策欠如、管理者初期PW平文、全削除投入の本番矛盾
- 推奨対応先: REQUIREMENTS
- 対象: docs/requirements
- 検査結果: FAIL（未解決）

## UNRESOLVED-0b5694db22a0bead
- 原因工程: ARCHITECTURE
- 修正・再検査: 3回
- 影響: SR-ARCH-001 本番デバッグ無効化/環境別設定の設計・ADDR引渡し漏れ、002/003 advisory
- 推奨対応先: ARCHITECTURE
- 対象: docs/architecture
- 検査結果: FAIL（未解決）

## UNRESOLVED-60a549ca11f16034
- 原因工程: ARCHITECTURE
- 修正・再検査: 3回
- 影響: QR-ARCH-001 Task依存矛盾、002 FR-060削除後のログイン状態無効化の引渡し漏れ
- 推奨対応先: ARCHITECTURE
- 対象: docs/architecture
- 検査結果: FAIL（未解決）

## UNRESOLVED-34471205dd0539bc
- 原因工程: IMPLEMENTATION
- 修正・再検査: 3回
- 影響: expected-fr.txtにFR-OUT-01〜16の対象/対象外分類なし(C12 16件)
- 推奨対応先: REQUIREMENTS
- 対象: docs/requirements/expected-fr.txt
- 検査結果: FAIL（未解決）

## UNRESOLVED-6de5eec64599b907
- 原因工程: IMPLEMENTATION
- 修正・再検査: 3回
- 影響: SEC-IMPL-001 NUL文字入力でDB DataError→500(NFR-SC-04)、002 compose公開範囲
- 推奨対応先: IMPLEMENTATION
- 対象: app
- 検査結果: FAIL（未解決）

## UNRESOLVED-c0b4f02168099ecc
- 原因工程: UNIT_TEST
- 修正・再検査: 3回
- 影響: QR-UT-1118-001 判定順序ACの単体テスト欠落、002 evidence文字化け、003-006 LOW
- 推奨対応先: UNIT_TEST
- 対象: app/tests/unit
- 検査結果: FAIL（未解決）

## UNRESOLVED-05b079507f12a077
- 原因工程: INTEGRATION_TEST
- 修正・再検査: 3回
- 影響: QR-IT-1118-001〜004 Required Coverage漏れ(同時実行キャンセル/支払、未ログインカート投入フロー、要求ID横断ログ・模擬決済送信内容、採番の重複なし・非巻戻し)
- 推奨対応先: INTEGRATION_TEST
- 対象: reports/integration-test/required-coverage.json
- 検査結果: FAIL（未解決）

## UNRESOLVED-e1d9dfe900863622
- 原因工程: FULL
- 修正・再検査: 3回
- 影響: FULL C10: NFR 60件にテスト到達なし(検証不能48・該当なし12、nfr-verification-scope)
- 推奨対応先: INTEGRATION_TEST
- 対象: docs/requirements/non_functional_requirements.md
- 検査結果: FAIL（未解決）

