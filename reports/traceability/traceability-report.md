# Traceability Report

- Audit Scope: FULL
- 判定: **FAIL**（不合格 85件・警告 0件）
- 方式: 注釈方式（AST解析なし）

## 定義されたIDの数

| 種類 | 件数 |
| --- | ---: |
| requirement | 200 |
| acceptance | 240 |
| addr | 14 |
| entity | 15 |
| file_definition | 23 |
| task | 21 |
| change | 0 |

## Coverage

| 項目 | 件数 | 率 |
| --- | ---: | ---: |
| expected_fr_to_implementation | 26/26 | 100.0% |
| requirement_to_addr | 82/200 | 41.0% |
| requirement_to_implementation | 107/200 | 53.5% |
| requirement_to_unit_test | 46/200 | 23.0% |
| requirement_to_integration_test | 114/200 | 57.0% |

## 注釈の量（付与の手間の目安）

| 対象 | ファイル | 注釈ありファイル | 注釈行 | 定義ごとの注釈 |
| --- | ---: | ---: | ---: | ---: |
| code | 114 | 114 | 482 | 364 |
| unit_test | 14 | 14 | 395 | 372 |
| integration_test | 24 | 24 | 273 | 224 |

## Issues

## 3回修正後の未解決事項

工程継続許可は検査PASSではありません。

- UNRESOLVED-05b079507f12a077: QR-IT-1118-001〜004 Required Coverage漏れ(同時実行キャンセル/支払、未ログインカート投入フロー、要求ID横断ログ・模擬決済送信内容、採番の重複なし・非巻戻し) / 対応先 INTEGRATION_TEST
- UNRESOLVED-0b5694db22a0bead: SR-ARCH-001 本番デバッグ無効化/環境別設定の設計・ADDR引渡し漏れ、002/003 advisory / 対応先 ARCHITECTURE
- UNRESOLVED-32af0f4a0ca9c80f: SEC-REQ-001..004 Blocking: 本番模擬決済、総当たり対策欠如、管理者初期PW平文、全削除投入の本番矛盾 / 対応先 REQUIREMENTS
- UNRESOLVED-34471205dd0539bc: expected-fr.txtにFR-OUT-01〜16の対象/対象外分類なし(C12 16件) / 対応先 REQUIREMENTS
- UNRESOLVED-60a549ca11f16034: QR-ARCH-001 Task依存矛盾、002 FR-060削除後のログイン状態無効化の引渡し漏れ / 対応先 ARCHITECTURE
- UNRESOLVED-6de5eec64599b907: SEC-IMPL-001 NUL文字入力でDB DataError→500(NFR-SC-04)、002 compose公開範囲 / 対応先 IMPLEMENTATION
- UNRESOLVED-c0b4f02168099ecc: QR-UT-1118-001 判定順序ACの単体テスト欠落、002 evidence文字化け、003-006 LOW / 対応先 UNIT_TEST

| 検査 | 判定 | 分類 | 場所 | 内容 | 差し戻し先 |
| --- | --- | --- | --- | --- | --- |
| C01 | FAIL | ADDR_HANDOFF_INVALID | reports/addr/implementation-handoff.json | C:\Users\shuns\Desktop\project\ai-sdlc-copilot\reports\architecture\design-gate.json: [Errno 2] No such file or directory: 'C:\\Users\\shuns\\Desktop\\project\\ai-sdlc-copilot\\reports\\architecture\\design-gate.json' | ADDR |
| C01 | FAIL | ADDR_HANDOFF_INVALID | reports/addr/implementation-handoff.json | Design Gate requires ARCHITECTURE PASS | ADDR |
| C01 | FAIL | ADDR_HANDOFF_INVALID | reports/addr/implementation-handoff.json | Design Gate: expected object array | ADDR |
| C01 | FAIL | ADDR_HANDOFF_INVALID | reports/addr/implementation-handoff.json | Design Gate snapshot coverage differs | ADDR |
| C01 | FAIL | ADDR_HANDOFF_INVALID | reports/addr/implementation-handoff.json | Gate assurance: expected object array | ADDR |
| C01 | FAIL | ADDR_HANDOFF_INVALID | reports/addr/implementation-handoff.json | Gate requires three independent Assurance results | ADDR |
| C01 | FAIL | ADDR_HANDOFF_INVALID | reports/addr/implementation-handoff.json | C:\Users\shuns\Desktop\project\ai-sdlc-copilot\reports\addr\implementation-handoff.json: [Errno 2] No such file or directory: 'C:\\Users\\shuns\\Desktop\\project\\ai-sdlc-copilot\\reports\\addr\\implementation-handoff.json' | ADDR |
| C01 | FAIL | ADDR_HANDOFF_INVALID | reports/addr/implementation-handoff.json | Implementation handoff differs from frozen Architecture/ADDR inputs | ADDR |
| C01 | FAIL | ADDR_HANDOFF_INVALID | reports/addr/implementation-handoff.json | C:\Users\shuns\Desktop\project\ai-sdlc-copilot\reports\architecture\addr-request.json: [Errno 2] No such file or directory: 'C:\\Users\\shuns\\Desktop\\project\\ai-sdlc-copilot\\reports\\architecture\\addr-request.json' | ADDR |
| C01 | FAIL | ARCHITECTURE_GATE_INVALID | reports/architecture/architecture-gate.json | C:\Users\shuns\Desktop\project\ai-sdlc-copilot\reports\architecture\architecture-gate.json: [Errno 2] No such file or directory: 'C:\\Users\\shuns\\Desktop\\project\\ai-sdlc-copilot\\reports\\architecture\\architecture-gate.json' | ARCHITECTURE |
| C01 | FAIL | ARCHITECTURE_GATE_INVALID | reports/architecture/architecture-gate.json | Architecture Gate is not PASS | ARCHITECTURE |
| C01 | FAIL | ARCHITECTURE_GATE_INVALID | reports/architecture/architecture-gate.json | C:\Users\shuns\Desktop\project\ai-sdlc-copilot\reports\architecture\design-gate.json: [Errno 2] No such file or directory: 'C:\\Users\\shuns\\Desktop\\project\\ai-sdlc-copilot\\reports\\architecture\\design-gate.json' | ARCHITECTURE |
| C01 | FAIL | ARCHITECTURE_GATE_INVALID | reports/architecture/architecture-gate.json | Design Gate requires ARCHITECTURE PASS | ARCHITECTURE |
| C01 | FAIL | ARCHITECTURE_GATE_INVALID | reports/architecture/architecture-gate.json | Design Gate: expected object array | ARCHITECTURE |
| C01 | FAIL | ARCHITECTURE_GATE_INVALID | reports/architecture/architecture-gate.json | Design Gate snapshot coverage differs | ARCHITECTURE |
| C01 | FAIL | ARCHITECTURE_GATE_INVALID | reports/architecture/architecture-gate.json | Gate assurance: expected object array | ARCHITECTURE |
| C01 | FAIL | ARCHITECTURE_GATE_INVALID | reports/architecture/architecture-gate.json | Gate requires three independent Assurance results | ARCHITECTURE |
| C01 | FAIL | ARCHITECTURE_GATE_INVALID | reports/architecture/architecture-gate.json | C:\Users\shuns\Desktop\project\ai-sdlc-copilot\reports\addr\implementation-handoff.json: [Errno 2] No such file or directory: 'C:\\Users\\shuns\\Desktop\\project\\ai-sdlc-copilot\\reports\\addr\\implementation-handoff.json' | ARCHITECTURE |
| C01 | FAIL | ARCHITECTURE_GATE_INVALID | reports/architecture/architecture-gate.json | Implementation handoff differs from frozen Architecture/ADDR inputs | ARCHITECTURE |
| C01 | FAIL | ARCHITECTURE_GATE_INVALID | reports/architecture/architecture-gate.json | Implementation release requires an independent ADDR Gate | ARCHITECTURE |
| C01 | FAIL | ARCHITECTURE_GATE_INVALID | reports/architecture/architecture-gate.json | Architecture Gate: expected object array | ARCHITECTURE |
| C01 | FAIL | ARCHITECTURE_GATE_INVALID | reports/architecture/architecture-gate.json | Architecture Gate snapshot coverage differs | ARCHITECTURE |
| C01 | FAIL | ARCHITECTURE_GATE_INVALID | reports/architecture/architecture-gate.json | Gate assurance: expected object array | ARCHITECTURE |
| C01 | FAIL | ARCHITECTURE_GATE_INVALID | reports/architecture/architecture-gate.json | Architecture Gate requires three Assurance results | ARCHITECTURE |
| C12 | FAIL | EXPECTED_FR_INVALID | docs/requirements/expected-fr.txt:29 | 実装対象FRは1行にFR-nnnを1件だけ記載します: 'EXCLUDE FR-OUT-01: 対象外機能「実決済サービスとの連携」。理由: 決済代行事業者が未選定。代替手段・担当: 模擬決済（決済サービス（模擬））で代替する。後続フェーズで検討する' | REQUIREMENTS |
| C12 | FAIL | EXPECTED_FR_INVALID | docs/requirements/expected-fr.txt:30 | 実装対象FRは1行にFR-nnnを1件だけ記載します: 'EXCLUDE FR-OUT-02: 対象外機能「商品・商品分類・仕入先・在庫単位・クーポンの画面／Web API による登録・更新・削除（マスタ保守）」。理由: 初期商品数が限られ、改廃頻度が低い。代替手段・担当: 運用者が初期データ一括投入（FR-060）で登録・再投入する' | REQUIREMENTS |
| C12 | FAIL | EXPECTED_FR_INVALID | docs/requirements/expected-fr.txt:31 | 実装対象FRは1行にFR-nnnを1件だけ記載します: 'EXCLUDE FR-OUT-03: 対象外機能「入荷・在庫補充の登録」。理由: 現行の在庫管理表で運用を継続する。代替手段・担当: 稼働開始時の在庫数量は初期データ一括投入（FR-060）で登録する。稼働後の補充分の反映方法は FOQ-01 で決定する（本リリースは登録済みの在庫数量を補充する機能を持たない）' | REQUIREMENTS |
| C12 | FAIL | EXPECTED_FR_INVALID | docs/requirements/expected-fr.txt:32 | 実装対象FRは1行にFR-nnnを1件だけ記載します: 'EXCLUDE FR-OUT-04: 対象外機能「返品・返金・部分出荷・分割配送」。理由: 件数が少ない。代替手段・担当: 支払済注文のキャンセル時の返金は、EC運営担当が本システム外で手作業で対応する' | REQUIREMENTS |
| C12 | FAIL | EXPECTED_FR_INVALID | docs/requirements/expected-fr.txt:33 | 実装対象FRは1行にFR-nnnを1件だけ記載します: 'EXCLUDE FR-OUT-05: 対象外機能「複数クーポンの併用、ポイント、ギフト券、自動適用の割引キャンペーン」。理由: 割引は単一クーポンに限定する。代替手段・担当: 実施しない' | REQUIREMENTS |
| C12 | FAIL | EXPECTED_FR_INVALID | docs/requirements/expected-fr.txt:34 | 実装対象FRは1行にFR-nnnを1件だけ記載します: 'EXCLUDE FR-OUT-06: 対象外機能「多通貨・多言語・海外配送・多国税制」。理由: 国内向け販売のみ。代替手段・担当: 実施しない（日本語・日本円・国内のみ）' | REQUIREMENTS |
| C12 | FAIL | EXPECTED_FR_INVALID | docs/requirements/expected-fr.txt:35 | 実装対象FRは1行にFR-nnnを1件だけ記載します: 'EXCLUDE FR-OUT-07: 対象外機能「配送業者との連携、住所検証、配送日時指定、送料の地域別設定」。理由: 出荷は運営側の手作業で行う。代替手段・担当: 管理者が出荷登録（FR-043）・配達完了登録（FR-044）を行う' | REQUIREMENTS |
| C12 | FAIL | EXPECTED_FR_INVALID | docs/requirements/expected-fr.txt:36 | 実装対象FRは1行にFR-nnnを1件だけ記載します: 'EXCLUDE FR-OUT-08: 対象外機能「メールその他の手段による利用者への通知（注文確認メールを含む）」。理由: 初期リリースでは画面・Web API での状態確認で代替する。代替手段・担当: 実施しない' | REQUIREMENTS |
| C12 | FAIL | EXPECTED_FR_INVALID | docs/requirements/expected-fr.txt:37 | 実装対象FRは1行にFR-nnnを1件だけ記載します: 'EXCLUDE FR-OUT-09: 対象外機能「会員情報の変更、パスワード再設定、退会」。理由: 初期リリースの範囲を限定する。代替手段・担当: EC運営担当が問い合わせを受けて個別に対応する（本システム外）' | REQUIREMENTS |
| C12 | FAIL | EXPECTED_FR_INVALID | docs/requirements/expected-fr.txt:38 | 実装対象FRは1行にFR-nnnを1件だけ記載します: 'EXCLUDE FR-OUT-10: 対象外機能「未ログイン状態でのカート利用（ゲスト購入）」。理由: 会員向けサービスとして開始する。代替手段・担当: カート・注文はログインを必須とする' | REQUIREMENTS |
| C12 | FAIL | EXPECTED_FR_INVALID | docs/requirements/expected-fr.txt:39 | 実装対象FRは1行にFR-nnnを1件だけ記載します: 'EXCLUDE FR-OUT-11: 対象外機能「認証失敗時のアカウントロック、ログイン試行回数の制限」。理由: 初期リリースの範囲を限定する。代替手段・担当: 実施しない（後続フェーズで検討する）' | REQUIREMENTS |
| C12 | FAIL | EXPECTED_FR_INVALID | docs/requirements/expected-fr.txt:40 | 実装対象FRは1行にFR-nnnを1件だけ記載します: 'EXCLUDE FR-OUT-12: 対象外機能「未払い注文の自動キャンセル（期限切れ処理）」。理由: 初期リリースの範囲を限定する。代替手段・担当: 購入者（FR-034）または管理者（FR-045）がキャンセルする' | REQUIREMENTS |
| C12 | FAIL | EXPECTED_FR_INVALID | docs/requirements/expected-fr.txt:41 | 実装対象FRは1行にFR-nnnを1件だけ記載します: 'EXCLUDE FR-OUT-13: 対象外機能「商品画像、商品レビュー、お気に入り、おすすめ表示」。理由: 初期リリースの範囲を限定する。代替手段・担当: 実施しない' | REQUIREMENTS |
| C12 | FAIL | EXPECTED_FR_INVALID | docs/requirements/expected-fr.txt:42 | 実装対象FRは1行にFR-nnnを1件だけ記載します: 'EXCLUDE FR-OUT-14: 対象外機能「スマートフォン専用画面」。理由: 初期リリースはPCブラウザを対象とする。代替手段・担当: 後続フェーズで検討する' | REQUIREMENTS |
| C12 | FAIL | EXPECTED_FR_INVALID | docs/requirements/expected-fr.txt:43 | 実装対象FRは1行にFR-nnnを1件だけ記載します: 'EXCLUDE FR-OUT-15: 対象外機能「帳票（PDF・CSVを含むファイル出力）」。理由: 一覧画面での確認で足りる。代替手段・担当: 実施しない' | REQUIREMENTS |
| C12 | FAIL | EXPECTED_FR_INVALID | docs/requirements/expected-fr.txt:44 | 実装対象FRは1行にFR-nnnを1件だけ記載します: 'EXCLUDE FR-OUT-16: 対象外機能「「特定商取引法に基づく表記」を含む静的ページ」。理由: サイト運営側の静的コンテンツとして別途用意する。代替手段・担当: 本システムの対象外' | REQUIREMENTS |
| C12 | FAIL | EXPECTED_FR_SCOPE_UNDECLARED | docs/requirements/expected-fr.txt | 正本の FR-OUT-01 が実装対象／対象外のどちらにもありません。 | REQUIREMENTS |
| C12 | FAIL | EXPECTED_FR_SCOPE_UNDECLARED | docs/requirements/expected-fr.txt | 正本の FR-OUT-02 が実装対象／対象外のどちらにもありません。 | REQUIREMENTS |
| C12 | FAIL | EXPECTED_FR_SCOPE_UNDECLARED | docs/requirements/expected-fr.txt | 正本の FR-OUT-03 が実装対象／対象外のどちらにもありません。 | REQUIREMENTS |
| C12 | FAIL | EXPECTED_FR_SCOPE_UNDECLARED | docs/requirements/expected-fr.txt | 正本の FR-OUT-04 が実装対象／対象外のどちらにもありません。 | REQUIREMENTS |
| C12 | FAIL | EXPECTED_FR_SCOPE_UNDECLARED | docs/requirements/expected-fr.txt | 正本の FR-OUT-05 が実装対象／対象外のどちらにもありません。 | REQUIREMENTS |
| C12 | FAIL | EXPECTED_FR_SCOPE_UNDECLARED | docs/requirements/expected-fr.txt | 正本の FR-OUT-06 が実装対象／対象外のどちらにもありません。 | REQUIREMENTS |
| C12 | FAIL | EXPECTED_FR_SCOPE_UNDECLARED | docs/requirements/expected-fr.txt | 正本の FR-OUT-07 が実装対象／対象外のどちらにもありません。 | REQUIREMENTS |
| C12 | FAIL | EXPECTED_FR_SCOPE_UNDECLARED | docs/requirements/expected-fr.txt | 正本の FR-OUT-08 が実装対象／対象外のどちらにもありません。 | REQUIREMENTS |
| C12 | FAIL | EXPECTED_FR_SCOPE_UNDECLARED | docs/requirements/expected-fr.txt | 正本の FR-OUT-09 が実装対象／対象外のどちらにもありません。 | REQUIREMENTS |
| C12 | FAIL | EXPECTED_FR_SCOPE_UNDECLARED | docs/requirements/expected-fr.txt | 正本の FR-OUT-10 が実装対象／対象外のどちらにもありません。 | REQUIREMENTS |
| C12 | FAIL | EXPECTED_FR_SCOPE_UNDECLARED | docs/requirements/expected-fr.txt | 正本の FR-OUT-11 が実装対象／対象外のどちらにもありません。 | REQUIREMENTS |
| C12 | FAIL | EXPECTED_FR_SCOPE_UNDECLARED | docs/requirements/expected-fr.txt | 正本の FR-OUT-12 が実装対象／対象外のどちらにもありません。 | REQUIREMENTS |
| C12 | FAIL | EXPECTED_FR_SCOPE_UNDECLARED | docs/requirements/expected-fr.txt | 正本の FR-OUT-13 が実装対象／対象外のどちらにもありません。 | REQUIREMENTS |
| C12 | FAIL | EXPECTED_FR_SCOPE_UNDECLARED | docs/requirements/expected-fr.txt | 正本の FR-OUT-14 が実装対象／対象外のどちらにもありません。 | REQUIREMENTS |
| C12 | FAIL | EXPECTED_FR_SCOPE_UNDECLARED | docs/requirements/expected-fr.txt | 正本の FR-OUT-15 が実装対象／対象外のどちらにもありません。 | REQUIREMENTS |
| C12 | FAIL | EXPECTED_FR_SCOPE_UNDECLARED | docs/requirements/expected-fr.txt | 正本の FR-OUT-16 が実装対象／対象外のどちらにもありません。 | REQUIREMENTS |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/functional_requirements.md:70 | FR-OUT-01 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/functional_requirements.md:71 | FR-OUT-02 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/functional_requirements.md:72 | FR-OUT-03 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/functional_requirements.md:73 | FR-OUT-04 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/functional_requirements.md:74 | FR-OUT-05 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/functional_requirements.md:75 | FR-OUT-06 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/functional_requirements.md:76 | FR-OUT-07 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/functional_requirements.md:77 | FR-OUT-08 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/functional_requirements.md:78 | FR-OUT-09 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/functional_requirements.md:79 | FR-OUT-10 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/functional_requirements.md:80 | FR-OUT-11 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/functional_requirements.md:81 | FR-OUT-12 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/functional_requirements.md:82 | FR-OUT-13 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/functional_requirements.md:83 | FR-OUT-14 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/functional_requirements.md:84 | FR-OUT-15 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/functional_requirements.md:85 | FR-OUT-16 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/non_functional_requirements.md:107 | NFR-AV-02 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/non_functional_requirements.md:106 | NFR-AV-03 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/non_functional_requirements.md:108 | NFR-AV-05 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/non_functional_requirements.md:111 | NFR-AV-09 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/non_functional_requirements.md:114 | NFR-AV-11 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/non_functional_requirements.md:290 | NFR-EN-06 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/non_functional_requirements.md:300 | NFR-EN-13 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/non_functional_requirements.md:206 | NFR-MG-06 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/non_functional_requirements.md:147 | NFR-OM-08 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/non_functional_requirements.md:148 | NFR-OM-09 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/non_functional_requirements.md:149 | NFR-OM-10 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/non_functional_requirements.md:156 | NFR-OM-14 を確かめるテストがありません。 | INTEGRATION_TEST |
| C10 | FAIL | TEST_TRACEABILITY_MISSING | docs/requirements/non_functional_requirements.md:159 | NFR-OM-16 を確かめるテストがありません。 | INTEGRATION_TEST |
