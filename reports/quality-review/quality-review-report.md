# Quality Review Report（audit_scope = FULL / Final Assurance 最終再検査）

| 項目 | 内容 |
| --- | --- |
| Report ID | QR-FULL-20261022-003 |
| Audit Scope | **FULL** |
| Status | **PASS**（未解決Blocking 0件） |
| Recommended Route | INTEGRATION_TEST（残存LOWの主な修正先） |
| Generated At | 2026-10-22T19:50:00+09:00 |
| source_baseline_sha256 | `2b6347ba4d4fa89cb00733f4a27f8760e043f593fb4a0f56a97081731b88a19d`（結合 junit） |

> 前回FULL（FAIL）および各Phase判定は流用せず再検査。成果物は一切修正していません。

## 1. 実機検証

| 検証 | 結果 |
| --- | --- |
| `docker compose exec -T -e DB_NAME=qrexec1 app pytest` | **925 passed / 0 failed / 0 skipped**（単体791＋結合134、110秒） |
| `ruff check .` / `manage.py check` / `makemigrations --check` | All checks passed / 0 issues / No changes |
| コード同一性 | コンテナ＝ホスト現物の **MD5一致**。かつ当方が18時台に記録した値と**同一**＝19:09 の一時改変→復元が**完全復元**であることを独立確認 |
| 失敗隠蔽 | skip/skipif/xfail **0件**、junit skipped 0、結合はケースIDと1:1（134:134） |
| 出自管理 | AI INITIAL `94f1d865…` 不変、Initial Metrics 保持、結合 required 139／final **100%** |

## 2. Criteria Results（6/6 PASS）

requirements / architecture / implementation / unit-test / integration-test / cross-phase-consistency ＝ **すべて PASS**

## 3. ①Blocking 2件の解消確認

- **QR-FULL-002 → 解消**：`test_fullwidth_digit_rejection.py`（21関数/44ケース）を実査。期待値は**要件本文由来**（FR-030/021/022/040/041/043/060・CMN-15）で Docstring に明記、**半角受理と全角拒否を対で検証**。パターン単体に加え `checkout`／`add_line`／`update_line`／管理者検索／seeding まで services 経由で確認し、**注文0件・配送先0件・在庫不変・カートOPEN維持**の副作用不在も検証。`[0-9]`→`\d` で失敗する設計。
- **QR-FULL-003 → 解消**：単体証跡は junit 19:18:01／coverage 19:18:36（**658/722＝91.14%**）／evidence・trace 19:18:42 と、コード最終更新（19:09:22）より新しい。結合証跡（18:54:50）は 19:09 の mtime より前だが、**当方の18時台 MD5 と現在値が一致**するため内容同一を独立確認。

## 4. ②追加11ケースの実質性 → **形骸的ではない**

- **GF-070（ruff）**：`--show-files` で解析対象を取得し「50件以上」「orders.py/views_orders.py/settings.py を含む」「/app/tests を含まない」を**先にアサート**してから JSON 出力の指摘0件を判定。
- **GF-071（命名規約）**：URL 25経路以上＋代表経路、JSON 項目名40種以上＋代表項目、テストファイル20件以上を確認してから snake_case 判定。
- **GF-072（ライセンス）**：`importlib.metadata` で実導入物のライセンスを解決し、**不明を失敗**、固定7製品の導入を確認後に AGPL 検出。
- **GF-073（決済境界）**：payments 配下3件以上を収集し **AST の import 解析**で業務パッケージ参照なしを判定。
- GF-074 秘密情報／GF-075 SPA不使用／GF-076 Gunicorn／上限超過時整合（在庫12・24並列）も実質的。
- すべてのケースで**空集合素通りを構造的に排除**。

## 5. ④C10 残存63件の分類 → **妥当**

`not_automatable_requirements` 63件について、(1) 引用された「検証方法」が要件本文に**逐語で存在：63/63**、(2) 付与区分と引用文のキーワード整合：**63/63**（OPERATIONAL_MEASUREMENT 22／COMPATIBILITY_TEST 9／PERFORMANCE_TEST 8／CONFIG_REVIEW 7／MIGRATION_REHEARSAL 5／OPERATION_TEST 4／VULNERABILITY_SCAN 4／NOT_APPLICABLE 4）。再検討の判定基準と自動化へ移した根拠も記録済み。**自動検証可能な要件の逃がしなし**。

## 6. ⑤AC充足（791＋134）

機能・データ・セキュリティ系に加え、FR-OUT 不実装・自動検証可能なNFR・今回の半角数字条件まで検証済み。**未検証は応答時間AC 8件（性能試験）と確認ダイアログAC 6件（受入試験）**＝Final Assurance の適用範囲外として明示。

## 7. ③残存LOWの最終的な扱い

| Issue | Route | 判断 |
| --- | --- | --- |
| **QR-IT-003** | INTEGRATION_TEST | **未解消**。①`test_checkout_api.py:267` の `DQ-10` 誤記が**結合側に残存**（Orchestrator 報告の「残存0件」と不一致。単体側は訂正済み）②**E501 5件**（4→5に増加）。`ruff check .` は PASS で**要件違反ではない** |
| **QR-FULL-004（新規）** | INTEGRATION_TEST | 同時実行ケースが **idle in transaction 接続を残す**ことがあり、その状態では次回の `docker compose exec app pytest` が大量失敗（3/101/102 failed を観測）。DB名を変えると **925 passed**＝テスト基盤の後始末の問題（製品欠陥ではない） |
| QR-ADDR-003 | ADDR | 未解消（ADDR-012 に Steering 4.1 逸脱の記載0件） |
| QR-ADDR-004 | ADDR | 未解消（ADDR-013 89行目の「締切10秒＝ロック保持時間の上限」記述） |
| QR-UT-006 | UNIT_TEST | **解消**（単体側 DQ-10 = 0件、UT-DEF-017 記録済み） |

いずれも**要件違反ではなく振る舞いに影響しない**ため Blocking としない。

## 8. ⑥Failure隠蔽 → **0件**

## 9. Observations

1. **GF-076 は実行方法依存**（`docker compose run` の使い捨てコンテナでは Gunicorn でないため失敗）。NFR-OM-06 の `docker compose exec` では成立。
2. 応答時間AC 8件・確認ダイアログAC 6件はリリース判断前に実施要否の決定を。
3. traceability／security-review の validation-result は `audit_scope=INTEGRATION_TEST` のまま。
4. **検証行為の開示**：全件実行・静的解析・validators 直接呼び出し、切り分け用の使い捨てDB名（qrfullcheck/qrfull2/qrexec1）での実行、原因特定のため使い捨てテストDBの残存セッション1件を停止。**成果物は未変更**。
5. 当方の実行で `case-run-results.json` が再生成（最終状態134件すべてPASS）。`validate_integration_test.py` 再実行で **exit 0** を確認。

## 10. 結論

**FULL Scope Final Assurance は PASS**。残存LOW 4件は記述・体裁・テスト基盤の堅牢性に限られ、製品の要件適合に影響しません。