# AI駆動開発：実装対象FRの全件トレーサビリティ検査

## 目的と範囲

AI-SDLC-Copilotのみ対象とする。既存の要件→Architecture→ADDR→実装→単体・結合テストの工程と
注釈方式を変更せず、実装対象FR全件のコード到達とコード／テストからの逆引きをC12で追加検査する。
従来開発・設計書なし向け設定は含めない。注釈が妥当な根拠を指すか、実装やassertが要件本文／ACと
一致するかは、各工程とトレーサビリティチームが実物を確認する。

## 実行開始前

1. `docs/requirements/functional_requirements.md` のFR定義と承認済みスコープを照合する。
2. `docs/requirements/expected-fr.txt` を作成してコミットする。形式例（実データで置き換える）:

   ```text
   # 実装対象の承認済みFR
   FR-001
   FR-002
   EXCLUDE FR-003: 今回の変更範囲から除外することを承認済み
   ```

   コメント行以外の全FRを、実装対象または理由付き対象外として1度だけ記録する。
   この一覧をMapやコードの既存注釈から作らない。例示のIDをそのまま適用しない。
3. `.github/skills/traceability-audit/policy/traceability-policy.yaml` のcode/unit_test/integration_testの
   include/excludeと、今回の対象ソース・テスト言語・配置を突き合わせる。対象外の実装ファイルを
   検査済みとして扱わない。JS/TS/Java等は現行スキャナではファイル単位で解析する。
4. Requirements Validatorでデータ要件の主ID `DR-nnn`、外部IF要件の主ID `IFR-nnn` を検証する。
   旧IDの改番は同一版の要件・設計・実装・テストの参照先も更新し、承認・再検査する。

## 検査

リポジトリルートで、実装直後以降の各工程で次を行う。`FULL`は実装・単体・結合の成果物が
すべて揃った段階で使用する。途中段階のFR→コード未到達はC12 FAILとして元工程へ戻す。

```bash
python .github/skills/traceability-audit/scripts/trace_check.py --scope IMPLEMENTATION
python .github/skills/traceability-audit/scripts/trace_check.py --scope IMPLEMENTATION --no-write

# 実JUnitを生成した直後、内容を変更する前に実行（各担当テスト後にそれぞれ実施）
python .github/skills/traceability-audit/scripts/trace_check.py --record-test-run unit_test
python .github/skills/traceability-audit/scripts/trace_check.py --record-test-run integration_test

# 最終再実行、両回の--commitsは同じ実装範囲を指定する
python .github/skills/traceability-audit/scripts/trace_check.py --scope FULL --commits BASE_SHA..HEAD
python .github/skills/traceability-audit/scripts/trace_check.py --scope FULL --commits BASE_SHA..HEAD --no-write
```

FULLが0を返し、`reports/traceability/traceability-report.json` の
`coverage.expected_fr_to_implementation.rate` が100、`unreachable=[]` であることを確かめる。
`trace-map.json` から `sources[].path`→`resolved_fr` でコード・テストから逆引きし、
`elements`から要件本文・設計の具体的な場所・IDを確認する。
`requirements-traceability-check.csv`では実行版とJUnitの判定を確認する。

C12は **実装対象FR→コード到達およびコード→要件到達** を構文上確認する。
テストの証跡が合格でも、意図したassertかどうかを自動判定しない。誤リンクの検出は
実際のコード/テストを開いて判断し、間違いがあれば該当工程へ差戻し、変更後のテストと監査を再実行する。
最終引渡しではブランチ名、終了コミットSHA、要件版、expected-fr.txt、使用Policy、Trace Map、
マトリクス・確認結果、JUnit、実行版、未解決事項を共有する。
