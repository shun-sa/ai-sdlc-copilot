---
name: traceability-audit
description: >
  成果物内のID参照とtrace注釈を正本としてC01〜C11を機械検査し、
  Trace Mapと3種の表を再生成する。元成果物は修正せず原因工程へ返す。
user-invocable: false
disable-model-invocation: false
---

# Traceability Audit Skill

## 正本と境界

正本は要件・ADDR・設計・TASK・CRのID参照と、コード・テストのtrace注釈です。
推測した意味リンク、AST、FQN、呼出し解析は使いません。
既存IDを改番せず、表やTrace Mapを手編集しません。Producerが成果物作成時に参照を記入します。
Auditorは元成果物・注釈・テスト結果を修正しません。生成・検証対象はPolicyのoutputs.dirのみです。

要件の正本は分割された要件本文・UC・ACです。requirements.mdは派生索引なので定義から除外します。
旧features、業務背景、用語集、品質チェックリスト、Steeringはグラフ対象外ですが設計の入力として保持します。
正本テンプレート・要件再構成・Architecture PREPARE→ADDR→FINALIZEを変更しません。
FILEは既存テンプレートの「File Interface ID」欄を読みます。DBDは既存入力がある場合のみ使い、
未提供の設計テンプレートを作りません。配置・接頭辞はpolicy/traceability-policy.yamlで指定します。

## 作成時の参照

- ADDR: 正本の2章「関連要件・参照成果物」の「要件」行に実在要件IDを記入します。
  他種成果物行のIDは要件リンクに代用しません。ACだけでは関連要件を満たしません。
- 設計・TASK: 要件・ADDR・DBDへの参照を既存欄で維持します。TASKだけを実装根拠にしません。
- Production: ファイル先頭、docstring/importより前に `# trace: ADDR-001, FILE-001`。
  Djangoは `{# trace: ADDR-001 #}`。TASK/要件を通常のコード注釈へ書きません。
- Test: `# trace: FR-001, ADDR-001` のように要件と関連判断を記入します。
  AC・FILEだけでは要件への参照を満たしません。
- Pythonの先頭IDが2つ以上、かつトップレベルclass/defが2つ以上なら、
  private/helperを含む全トップレベル定義の直前（decoratorより前）にもtraceを記入します。
  定義注釈は先頭IDの部分集合です。メソッドごと・FQN単位の永続IDは作りません。
- 既存のArchitecture Gateを検証でき、ADDR結果がneeded=falseとした対象だけは、
  その対象のbasis_idsの要件へ直接参照できます。有効ADDRが覆う要件は例外から除外します。
  Gateなし・古いGate・未承認対象には例外を適用しません。空のADDRは作りません。
- コミットを行うよう依頼された場合だけ、件名先頭に既存の `[TASK-001]` / `[CR-001]`。
  注釈維持のための自動コミットはしません。

## 実行

Python 3.10以上とPyYAMLを利用します。Orchestratorから受領したaudit_scopeを変更しません。
REQUIREMENTS / ARCHITECTURE / IMPLEMENTATION / UNIT_TEST / INTEGRATION_TEST / FULLに対応します。

```text
python .github/skills/traceability-audit/scripts/trace_check.py --scope ARCHITECTURE
python .github/skills/traceability-audit/scripts/trace_check.py --scope ARCHITECTURE --no-write
```

1回目で現在の正本から表・Map・機械Reportを生成します。
2回目で同じScope・Policy・コミット範囲を指定し、独立再計算してC11を検証します。
`--no-write` は派生成果物を修復せず、validation-result.jsonだけを更新します。
`--commits main..HEAD` はC08用の任意入力です。指定しない場合はコミット監査未実施とします。
終了値0=PASS（警告可）、1=FAIL、2=入力/設定/読取りエラー。0以外で先に進みません。

| 検査 | 内容 |
| --- | --- |
| C01 | ID実在・重複・計画参照。実装以降は既存Architecture Gateも検証 |
| C02 | 下流から廃止・未確定判断を参照しない |
| C03 | ADDRの状態・関連要件欄 |
| C04 | TASKの要件/ADDR/DBD根拠 |
| C05 | 先頭注釈と許可ID種別 |
| C06 | 定義ごとの注釈と先頭との整合 |
| C07 | 各テストの要件参照 |
| C08 | コミット件名先頭のTASK/CR（警告） |
| C09 | 有効ADDRの実装漏れ（開発中警告、FULL不合格） |
| C10 | FR/NFR/SECのテスト漏れ（開発中警告、FULL不合格） |
| C11 | 保存済み派生成果物と再計算結果の一致 |

## テスト結果と実行版

JUnit XMLは各テスト担当が実際にテストを実行して生成します。
直後、成果物を変更する前に次でその入力とJUnitのSHA-256を結び付けます。
このコマンド自体はテストを実行しません。過去のJUnitを現在の実行結果として登録してはいけません。

```text
python .github/skills/traceability-audit/scripts/trace_check.py --record-test-run unit_test
python .github/skills/traceability-audit/scripts/trace_check.py --record-test-run integration_test
```

結果は各reports/<test>/trace-execution.jsonです。
確認表は記録された実行版のみを使用し、現在HEADをテスト実行版として代入しません。
実行記録なし・入力/JUnitハッシュ不一致・未実行・skipは充足にしません。
JUnitは役割と正確なモジュール名・テスト名で照合し、同名別ファイルのPASSを流用しません。
Integration Planのrequirement_id/related_adrは既存契約名を維持し、実在要件/判断IDを使います。
外部ケースを改変したり計画だけを実行成功と見なしたりしません。

## 派生成果物

reports/traceability/以下に生成します。

- trace-map.json: version=3、elements/sources/integration_test_casesと入力ハッシュ
- traceability-report.json/.md: 機械検査の結果・Issue・Coverage・注釈量
- requirements-traceability-matrix.md/.csv: 要件→判断/設計/実装/テスト/AC
- requirements-traceability-check.md/.csv: UNIT_TEST以降、実行版・JUnit結果・確認判定
- addr-index.md/.csv: 判断別の参照一覧
- validation-result.json: 既存Assurance契約のstatus/audit_scope/errors/warnings、
  source_baseline_sha256（現在のFINAL manifestのハッシュ）、issues

Semantic Reviewは任意の別文書semantic-review.mdに助言として記録します。
traceability-reportの機械statusやvalidation-resultを意味判断で上書きしません。
Trace PASSは仕様の意味的充足・品質・安全性やテスト成功を保証しません。
独立したQuality/Security/Test ValidatorのGateは従来どおり必須です。

## 差戻し・完了

validation-resultのissues[].routeとclassification/locationを親へ返します。
REQUIREMENTS、ARCHITECTURE、IMPLEMENTATION、UNIT_TEST、INTEGRATION_TESTの原因工程が修正します。
ARCHITECTUREの判断不備はADDR、設計反映/TASK不備はArchitecture FINALIZE、
入力不備はPREPAREへ親が振り分けます。変更後は既存の無効化規則で再Gateします。
TRACEABILITY_REGENERATEはAuditorが現在の正本から派生物のみを再生成します。

同じ原因を3回修正しても残れば、共通ループ台帳の未解決結果を親へ返し、継続判定で次工程へ進みます。
検査PASSは生成・独立検証とも成功した場合のみです。工程継続と区別します。
台帳のUNRESOLVEDを機械Reportと確認表へ投影し、該当要件の判定は「未解決あり」にします。
OBSERVEによる履歴更新だけでC11を再び古くしないよう、派生Mapには安定した未解決状態を記録します。
