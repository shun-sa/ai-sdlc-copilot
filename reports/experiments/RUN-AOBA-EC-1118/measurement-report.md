# 実験測定結果 RUN-AOBA-EC-1118

- Run状態: COMPLETE_WITH_UNRESOLVED
- 設計開始→最後の結合試験終了（秒）: 52365.042622
- 結合試験の終了状態: CONTINUE_WITH_UNRESOLVED
- 手戻り総数: 9
- 分岐網羅率: 96.97 / MEASURED
- 受入テスト合格率: None / NOT_YET_IMPORTED
- トークン数: VSCodeで取得（未入力を0とみなさない）

## 工程別（待機・同一工程内の修正を含む。子活動は二重加算しない）

- REQUIREMENTS: 40763.336273 秒 / 2 visits / MEASURED
- ARCHITECTURE: 5894.568798 秒 / 2 visits / MEASURED
- ADDR: 6171.820756 秒 / 3 visits / MEASURED
- IMPLEMENTATION: 9694.698169 秒 / 4 visits / MEASURED
- UNIT_TEST: 9617.464676 秒 / 5 visits / MEASURED
- INTEGRATION_TEST: 18445.161051 秒 / 6 visits / MEASURED
- FULL: 2572.392849 秒 / 4 visits / MEASURED

## 設計開始→最後の結合試験終了の区間内だけの工程時間

- REQUIREMENTS: 890.566676 秒 / MEASURED
- ARCHITECTURE: 5894.568798 秒 / MEASURED
- ADDR: 6171.820756 秒 / MEASURED
- IMPLEMENTATION: 9694.698169 秒 / MEASURED
- UNIT_TEST: 9420.45969 秒 / MEASURED
- INTEGRATION_TEST: 18445.161051 秒 / MEASURED
- FULL: 1847.673815 秒 / MEASURED

## 子活動（親工程へ加算しない）

- UNIT_TEST_EXECUTION: 546.510196 秒 / 10 visits
- addr_assurance: 508.062747 秒 / 1 visits
- addr_assurance_addr003r2: 309.514029 秒 / 1 visits
- addr_assurance_recheck_cycle1: 357.246813 秒 / 1 visits
- addr_assurance_recheck_cycle2: 319.807144 秒 / 1 visits
- addr_assurance_recheck_cycle3: 289.431063 秒 / 1 visits
- addr_assurance_rework: 804.444128 秒 / 1 visits
- architecture_assurance: 357.412439 秒 / 1 visits
- architecture_assurance_recheck_cycle1: 247.930025 秒 / 1 visits
- architecture_assurance_recheck_cycle2: 316.080033 秒 / 1 visits
- architecture_assurance_recheck_cycle3: 263.473515 秒 / 1 visits
- architecture_assurance_rework: 377.306964 秒 / 1 visits
- build_validation: 288.650537 秒 / 1 visits
- build_validation_rework: 140.42041 秒 / 1 visits
- build_validation_rework2: 140.487283 秒 / 1 visits
- build_validation_rework3: 140.50817 秒 / 1 visits
- full_assurance: 576.653098 秒 / 1 visits
- full_assurance_final: 693.459418 秒 / 1 visits
- full_traceability_recheck_c10_cycle1: 592.611896 秒 / 1 visits
- full_traceability_recheck_c10_cycle2: 658.441782 秒 / 1 visits
- implementation_assurance: 583.085141 秒 / 1 visits
- implementation_assurance_rework: 602.694897 秒 / 1 visits
- implementation_assurance_rework2: 1490.780348 秒 / 1 visits
- implementation_assurance_rework3: 485.277937 秒 / 1 visits
- integration_test_assurance: 1184.441355 秒 / 1 visits
- integration_test_assurance_final: 1484.618688 秒 / 1 visits
- integration_test_assurance_recheck: 1904.383947 秒 / 1 visits
- integration_test_assurance_recheck2: 1109.261725 秒 / 1 visits
- requirements_assurance_quality_security_traceability: 503.726367 秒 / 1 visits
- requirements_assurance_recheck_cycle1: 335.472337 秒 / 1 visits
- requirements_assurance_recheck_cycle2: 233.762919 秒 / 1 visits
- requirements_assurance_recheck_cycle3: 183.898983 秒 / 1 visits
- requirements_assurance_rework: 214.598292 秒 / 1 visits
- requirements_validator: 0.49794 秒 / 1 visits
- unit_test_assurance: 528.874678 秒 / 1 visits
- unit_test_assurance_recheck: 526.682914 秒 / 1 visits
- unit_test_assurance_recheck2: 541.196325 秒 / 1 visits
- unit_test_assurance_recheck3: 286.217515 秒 / 1 visits
- validate_design_final: 0.384167 秒 / 1 visits
- validate_integration_test: 0.448967 秒 / 1 visits
- validate_unit_test: 0.268753 秒 / 1 visits

## 手戻り：実際に戻した工程別

- FULL → INTEGRATION_TEST: 3
- IMPLEMENTATION → ADDR: 1
- IMPLEMENTATION → REQUIREMENTS: 1
- INTEGRATION_TEST → UNIT_TEST: 3
- UNIT_TEST → IMPLEMENTATION: 1

## 注意

nullは未取得・未確認・非該当。0や100%に補完しない。
計測は開発Gateや品質合格を代替しない。
