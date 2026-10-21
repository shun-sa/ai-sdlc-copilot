# 注釈方式トレーサビリティ

2026-10-21更新。トレーサビリティ方針を、最新の分割要件とArchitecture/ADDR分離契約へ適合したものです。
チームZIPにある旧要件・旧ADR-only設計Agentは採用せず、既存テンプレートも変更していません。

## 処理と担当

1. Requirementsが分割本文・UC/ACを再構成します。IDと既存の関連参照を保持します。
2. Architecture→ADDRの独立工程で、設計資料・判断・TASKの既存欄に実在根拠IDを記入します。
   後続ADDRのFILE/TASK参照は正本2章と検証済み派生handoffで結び、通常FINALIZEは行いません。
3. Architectureの構造検証とQuality/Security/Traceabilityを経て既存のハッシュ固定Gateを保存します。
4. Implementationはコード作成と同時にADDR/DBD/FILEの先頭注釈を付けます。
5. UnitTest/IntegrationTestは要件と関連ADDRの注釈を付け、実行でJUnitを生成して実行版を記録します。
6. Auditorが各工程のC01〜C11を機械検査し、正本からMap・表・Reportを生成します。
7. 同一条件で独立再計算する--no-write検証がPASSした後、既存の工程Gateで遷移します。

正本は成果物内参照・注釈です。表やMapは編集しません。
AST/FQN/Callによるリンク生成・AIの意味推論によるリンク補完は使いません。
意味的な懸念はsemantic-review.mdの助言とし、Traceの機械PASS/FAILと分離します。
既存Quality/Security/Test Validatorの内容妥当性・安全性・実行成功のGateは残します。
同じ原因を3回修正しても残れば未解決として記録し、CONTINUE_WITH_UNRESOLVEDで次へ進めます。

## 現在の資産への適合

- 定義はdocs/requirementsの分割本文・UC/AC。requirements.md索引、旧features、
  業務背景・用語・品質チェックリスト・Steeringはグラフから除外します。設計入力としては保持します。
- ADDRはdocs/addr、旧ADRはdocs/adrから読みます。新状態はACTIVE/SUPERSEDEDを維持します。
  2章の「要件」行を読取り、DBD等の別行にある参照は要件リンクに混ぜません。
- FILEはdocs/architecture/filesの正本「File Interface ID」欄を読取ります。
  TASKはdocs/architecture/implementation-task-list.md。既存のRelated ADR欄をADDRにも使います。
- DBDは提供済みのdocs/architecture/db-logical-design*.md等を使用します。
  今回存在しないDB/API/画面設計テンプレートを追加しません。
- ADDR不要の正常系は保持します。実装以降の検証済みGate・needed=falseが承認した対象の
  basis_idsだけ、コードの直接要件参照を許可します。有効ADDRがある要件には例外を使いません。
- 既存Integration Planのrequirement_id/related_adrを維持します。
  requirement_idは実在要件、related_adrは実在判断でなければ不合格です。

## 注釈と検査

```python
# trace: ADDR-001, FILE-001

# trace: ADDR-001
def apply_policy():
    return True

# trace: FILE-001
def export_result():
    return "result"
```

Djangoは `{# trace: ADDR-001 #}`、テストは `# trace: FR-001, ADDR-001`。
先頭注釈はdocstring/importより前です。
先頭IDが2つ以上かつトップレベルclass/defが2つ以上なら、private/helperを含む全定義直前
（decoratorより前）にも先頭の部分集合を付けます。クラスのメソッドごとは要求しません。

既定の対象はsrc/app配下Python・Django HTMLとtests/unit・tests/integrationのPythonです。
別配置・ID接頭辞はPolicyで明示します。非Pythonの定義別解析は未対応でファイル注釈のみです。
対象外ファイルは自動的に網羅した扱いにしません。採用言語・配置に合わせPolicyを確認してください。

C01=実在/重複、C02=廃止/未確定判断参照、C03=判断の状態/関連要件、
C04=TASK根拠、C05=先頭/種別、C06=定義注釈、C07=テスト要件、
C08=コミット先頭TASK/CR、C09=未実装判断、C10=未テストFR/NFR/SEC、C11=再生成一致。
C08は範囲指定時のみの警告。C09/C10は開発中警告、FULLでは不合格です。
要件・設計工程では未生成コード/テストを要求しません。

```text
python .github/skills/traceability-audit/scripts/trace_check.py --scope ARCHITECTURE
python .github/skills/traceability-audit/scripts/trace_check.py --scope ARCHITECTURE --no-write
```

Scopeは現在工程に置換します。--commitsを使う場合は生成・検証の両方に同じ範囲を渡します。
終了値0のみPASS、1は機械不合格、2は入力/設定等のエラーです。
--no-writeは表を修復しません。validation-result.jsonのみを更新します。

## 実行版と確認表

テスト担当は実テスト直後に次を実行し、入力とJUnitのハッシュを結び付けます。

```text
python .github/skills/traceability-audit/scripts/trace_check.py --record-test-run unit_test
python .github/skills/traceability-audit/scripts/trace_check.py --record-test-run integration_test
```

このコマンドはテストを実行しません。古いJUnitの付替えは認めません。
実行記録なし・入力/JUnit変更・skip・未実行は「充足」にしません。
記録された版はGit commitまたはWORKTREEハッシュです。監査時HEADを実行版として代入しません。
JUnitとの一致は名前だけでなく役割・正確なモジュール名でも確認します。
Git履歴に基づく保守時の再実行選定・影響探索の自動化は今回の対象外です。

## 出力と移行

reports/traceabilityにTrace Map v3、機械Report、要件対応表MD/CSV、
確認結果表MD/CSV（単体テスト工程以降）、ADDR別一覧MD/CSV、validation-resultを生成します。
C11はMap・Report・各表を再計算して比較します。FINAL manifestのハッシュは既存Gate契約へ渡します。
TRACEABILITY_REGENERATEは派生物のみ再生成、元成果物問題はIssue.routeの作成工程へ差し戻します。

旧ASTツール7ファイルは削除します。旧ast-index.jsonやv2 Reportは証拠として再利用しません。
既存プロジェクトでは旧派生Reportを履歴へ退避し、作成担当が正本参照・注釈を付けてから、
現在Scopeの生成と独立検証を実施します。既存コードの注釈を推測で一括生成しません。
古い設計Gateは新しいTraceability検証後に再発行します。旧要件・旧Agentへ戻しません。

## 工程継続の基本方針（2026-10-21更新）

全工程は、初回失敗とは別に修正・再検査を最大3回行い、残れば未解決を記録して次へ進めます。
旧来の停止条件は品質PASSの判定として維持し、工程継続では共通3回方針を優先します。
検査FAILは変更しません。最終結果もCOMPLETE_WITH_UNRESOLVEDとして正常完了と区別します。
詳細は [共通3回ループ](bounded-repair-loop.md) を参照してください。
