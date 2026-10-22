# Traceability Report

- Audit Scope: FULL
- 判定: **FAIL**（不合格 59件・警告 0件）
- 方式: 注釈方式（AST解析なし）

## 定義されたIDの数

| 種類 | 件数 |
| --- | ---: |
| requirement | 173 |
| acceptance | 249 |
| addr | 13 |
| entity | 0 |
| file_definition | 22 |
| task | 16 |
| change | 0 |

## Coverage

| 項目 | 件数 | 率 |
| --- | ---: | ---: |
| requirement_to_addr | 67/173 | 38.7% |
| requirement_to_implementation | 69/173 | 39.9% |
| requirement_to_unit_test | 35/173 | 20.2% |
| requirement_to_integration_test | 93/173 | 53.8% |

## 注釈の量（付与の手間の目安）

| 対象 | ファイル | 注釈ありファイル | 注釈行 | 定義ごとの注釈 |
| --- | ---: | ---: | ---: | ---: |
| code | 83 | 83 | 397 | 279 |
| unit_test | 22 | 22 | 529 | 504 |
| integration_test | 17 | 17 | 239 | 199 |

## Issues

| 検査 | 判定 | 分類 | 場所 | 内容 | 差し戻し先 |
| --- | --- | --- | --- | --- | --- |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/non_functional_requirements.md:101 | NFR-AV-01 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/non_functional_requirements.md:103 | NFR-AV-02 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/non_functional_requirements.md:102 | NFR-AV-03 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/non_functional_requirements.md:110 | NFR-AV-04 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/non_functional_requirements.md:105 | NFR-AV-05 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/non_functional_requirements.md:104 | NFR-AV-06 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/non_functional_requirements.md:106 | NFR-AV-07 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/non_functional_requirements.md:107 | NFR-AV-08 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/non_functional_requirements.md:108 | NFR-AV-09 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/non_functional_requirements.md:111 | NFR-AV-11 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/non_functional_requirements.md:112 | NFR-AV-12 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/non_functional_requirements.md:289 | NFR-EN-06 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/non_functional_requirements.md:295 | NFR-EN-10 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/non_functional_requirements.md:299 | NFR-EN-13 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/non_functional_requirements.md:312 | NFR-LG-07 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/non_functional_requirements.md:313 | NFR-LG-08 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/non_functional_requirements.md:206 | NFR-MG-02 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/non_functional_requirements.md:202 | NFR-MG-03 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/non_functional_requirements.md:203 | NFR-MG-04 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/non_functional_requirements.md:204 | NFR-MG-05 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/non_functional_requirements.md:205 | NFR-MG-06 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/non_functional_requirements.md:208 | NFR-MG-08 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/non_functional_requirements.md:149 | NFR-OM-02 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/non_functional_requirements.md:150 | NFR-OM-03 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/non_functional_requirements.md:156 | NFR-OM-05 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/non_functional_requirements.md:158 | NFR-OM-06 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/non_functional_requirements.md:144 | NFR-OM-08 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/non_functional_requirements.md:145 | NFR-OM-09 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/non_functional_requirements.md:146 | NFR-OM-10 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/non_functional_requirements.md:151 | NFR-OM-12 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/non_functional_requirements.md:154 | NFR-OM-14 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/non_functional_requirements.md:155 | NFR-OM-15 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/non_functional_requirements.md:157 | NFR-OM-16 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/non_functional_requirements.md:162 | NFR-OM-19 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/non_functional_requirements.md:120 | NFR-PF-01 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/non_functional_requirements.md:121 | NFR-PF-02 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/non_functional_requirements.md:122 | NFR-PF-03 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/non_functional_requirements.md:125 | NFR-PF-04 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/non_functional_requirements.md:126 | NFR-PF-05 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/non_functional_requirements.md:133 | NFR-PF-06 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/non_functional_requirements.md:123 | NFR-PF-09 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/non_functional_requirements.md:124 | NFR-PF-10 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/non_functional_requirements.md:130 | NFR-PF-13 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/non_functional_requirements.md:131 | NFR-PF-14 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/non_functional_requirements.md:132 | NFR-PF-15 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/non_functional_requirements.md:230 | NFR-SC-02 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/non_functional_requirements.md:246 | NFR-SC-11 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/non_functional_requirements.md:231 | NFR-SC-20 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/non_functional_requirements.md:236 | NFR-SC-21 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/non_functional_requirements.md:242 | NFR-SC-26 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/non_functional_requirements.md:245 | NFR-SC-29 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/non_functional_requirements.md:272 | NFR-US-01 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/non_functional_requirements.md:274 | NFR-US-02 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/non_functional_requirements.md:275 | NFR-US-05 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/non_functional_requirements.md:273 | NFR-US-06 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/non_functional_requirements.md:276 | NFR-US-07 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/non_functional_requirements.md:277 | NFR-US-08 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/non_functional_requirements.md:278 | NFR-US-09 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/non_functional_requirements.md:279 | NFR-US-10 を確かめるテストがありません。 | INTEGRATION_TEST |
