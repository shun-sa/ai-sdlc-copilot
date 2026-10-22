# 実験測定結果 RUN-20261022-MC

- Run状態: COMPLETE_WITH_UNRESOLVED
- 設計開始→最後の結合試験終了（秒）: 50019.322083
- 結合試験の終了状態: PASS
- 手戻り総数: 9
- 分岐網羅率: None / STALE
- 受入テスト合格率: None / NOT_YET_IMPORTED
- トークン数: VSCodeで取得（未入力を0とみなさない）

## 工程別（待機・同一工程内の修正を含む。子活動は二重加算しない）

- REQUIREMENTS: None 秒 / 0 visits / NOT_ENTERED
- ARCHITECTURE: 3327.459184 秒 / 1 visits / MEASURED
- ADDR: 6211.959943 秒 / 3 visits / MEASURED
- IMPLEMENTATION: 8385.443381 秒 / 6 visits / MEASURED
- UNIT_TEST: 11258.883083 秒 / 5 visits / MEASURED
- INTEGRATION_TEST: 16888.733544 秒 / 6 visits / MEASURED
- FULL: 4478.820928 秒 / 4 visits / MEASURED

## 設計開始→最後の結合試験終了の区間内だけの工程時間

- REQUIREMENTS: None 秒 / NOT_ENTERED
- ARCHITECTURE: 3327.459184 秒 / MEASURED
- ADDR: 6211.959943 秒 / MEASURED
- IMPLEMENTATION: 8385.443381 秒 / MEASURED
- UNIT_TEST: 11258.883083 秒 / MEASURED
- INTEGRATION_TEST: 16888.733544 秒 / MEASURED
- FULL: 3940.177879 秒 / MEASURED

## 子活動（親工程へ加算しない）

- ADDR scope assurance: 1719.430258 秒 / 1 visits
- ADDR scope assurance (ADDR-012): 612.390108 秒 / 1 visits
- ADDR scope assurance (ADDR-013): 624.82826 秒 / 1 visits
- ARCHITECTURE scope assurance: 1997.329799 秒 / 1 visits
- IMPLEMENTATION scope assurance: 2522.899574 秒 / 1 visits
- INTEGRATION_TEST scope assurance: 777.167689 秒 / 1 visits
- INTEGRATION_TEST scope assurance re-run: 849.655489 秒 / 1 visits
- UNIT_TEST scope assurance: 2624.826783 秒 / 1 visits
- UNIT_TEST scope assurance re-run: 2358.26442 秒 / 1 visits
- UNIT_TEST_EXECUTION: 770.072268 秒 / 14 visits

## 手戻り：実際に戻した工程別

- FULL → INTEGRATION_TEST: 2
- FULL → UNIT_TEST: 1
- INTEGRATION_TEST → ADDR: 2
- INTEGRATION_TEST → IMPLEMENTATION: 1
- INTEGRATION_TEST → UNIT_TEST: 1
- UNIT_TEST → IMPLEMENTATION: 2

## 注意

nullは未取得・未確認・非該当。0や100%に補完しない。
計測は開発Gateや品質合格を代替しない。
