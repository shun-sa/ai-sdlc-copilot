# ファイル定義書

<!--
目的:
- システム内外で交換・入出力されるファイルについて、実装・結合・運用に必要な仕様を定義する。
- 外部インターフェースとしてのファイル仕様を、項目レベルまで一貫して記録する。

適用:
- CSV、TSV、固定長、JSON/XMLファイル、バッチ入出力、外部システム連携ファイル等が存在する場合に作成する。
- ファイル連携が存在しない場合は作成不要。

設計原則:
- Requirement / Accepted ADR / 外部IF仕様をSource of Truthとして参照し、内容を不要に複製しない。
- 未確定事項を推測して確定しない。
- 実装者・テスト担当が曖昧なく判断できる粒度で、形式、項目、制約、異常時動作を定義する。
-->

## 1. 文書情報

| 項目 | 内容 |
| --- | --- |
| Document ID | `<DOC-FILE-001>` |
| File Interface ID | `<FILE-001>` |
| 対象システム | `<システム名>` |
| ファイル名／論理名 | `<名称>` |
| Version | `<1.0>` |
| Status | `DRAFT / REVIEW / APPROVED / DEPRECATED` |
| Owner | `<担当>` |
| Last Updated | `<YYYY-MM-DD>` |

## 2. 関連情報

| 種別 | ID / Path | 関係 |
| --- | --- | --- |
| Requirement | `<FR-xxx / NFR-xxx>` | `<このファイルで満たす要求>` |
| Use Case | `<UC-xxx / None>` | `<関連する業務フロー>` |
| ADR | `<ADR-xxx / None>` | `<方式・技術判断>` |
| External IF | `<IF-xxx / None>` | `<外部インターフェース>` |
| Glossary | `<TERM-xxx / path>` | `<用語定義>` |

## 3. ファイル概要

| 項目 | 内容 |
| --- | --- |
| 目的 | `<何のために使用するファイルか>` |
| 方向 | `INBOUND / OUTBOUND / INTERNAL` |
| 送信元 | `<システム／Component / Actor>` |
| 送信先 | `<システム／Component / Actor>` |
| 生成契機 | `<画面操作、バッチ時刻、イベント等>` |
| 生成／受信頻度 | `<随時 / 日次 / 月次 / ...>` |
| 想定最大件数 | `<件数 / 未定>` |
| 想定最大サイズ | `<MB等 / 未定>` |
| 保持期間 | `<期間 / 別Requirement参照>` |
| 再送・再取込 | `<可否と条件>` |

## 4. ファイル物理仕様

| 項目 | 内容 |
| --- | --- |
| ファイル形式 | `CSV / TSV / FIXED / JSON / XML / OTHER` |
| 文字コード | `<UTF-8等>` |
| BOM | `YES / NO / N/A` |
| 改行コード | `LF / CRLF / OTHER` |
| 区切り文字 | `<comma / tab / None>` |
| 囲み文字 | `<double quote / None>` |
| エスケープ規則 | `<規則>` |
| ヘッダ | `REQUIRED / OPTIONAL / NONE` |
| トレーラ | `REQUIRED / OPTIONAL / NONE` |
| 圧縮 | `<ZIP / GZIP / NONE>` |
| 暗号化 | `<方式 / NONE / ADR参照>` |
| 拡張子 | `<.csv等>` |
| MIME Type | `<text/csv等 / N/A>` |

## 5. ファイル命名規則

| 項目 | 内容 |
| --- | --- |
| Naming Pattern | `<例: ORDER_YYYYMMDD_HHMMSS.csv>` |
| 日時基準 | `<JST / UTC / N/A>` |
| 連番 | `<有無・桁数>` |
| 再送識別 | `<方法 / None>` |
| 重複判定Key | `<ファイル名 / Control ID / Hash 等>` |

### 5.1 命名例

```text
<実例>
```

## 6. レコード構成

| Record ID | Record Type | 出現条件 | 繰返し | 説明 |
| --- | --- | --- | --- | --- |
| REC-001 | `<HEADER / DETAIL / TRAILER>` | `<条件>` | `<1 / 0..N等>` | `<説明>` |

## 7. 項目定義

<!--
固定長の場合は Start Position / Length を必須とする。
区切り形式の場合は Column No. を必須とする。
-->

| Field ID | Record ID | Column No. | 項目名 | 論理名 | 型 | 桁数／長さ | 必須 | Null | Format | Default | 制約／Code Set | 説明 |
| --- | --- | ---: | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| FLD-001 | REC-001 | 1 | `<field_name>` | `<項目名>` | `<STRING/INTEGER/DECIMAL/DATE/...>` | `<10>` | `YES / NO` | `ALLOW / DENY` | `<yyyy-MM-dd等>` | `<None>` | `<値域・コード>` | `<意味>` |

### 7.1 固定長項目位置（固定長のみ）

| Field ID | Start Position | Length | Padding | Alignment | 備考 |
| --- | ---: | ---: | --- | --- | --- |
| FLD-001 | `<1>` | `<10>` | `<space / zero>` | `LEFT / RIGHT` | `<...>` |

## 8. 編集・変換ルール

| Rule ID | 対象Field / Record | 条件 | 変換・編集内容 | 異常時 |
| --- | --- | --- | --- | --- |
| FILE-RULE-001 | `<FLD-001>` | `<条件>` | `<Trim、丸め、コード変換等>` | `<ERROR / REJECT / DEFAULT>` |

## 9. 整合性・Control情報

| 項目 | ルール |
| --- | --- |
| 件数整合 | `<Header/Trailer件数との一致等>` |
| 金額等の集計整合 | `<集計値照合 / N/A>` |
| 一意性 | `<重複不可Field / 複合Key>` |
| 並び順 | `<Sort Key / 順序保証なし>` |
| Checksum / Hash | `<方式 / N/A>` |
| Control ID | `<採番・利用方法 / N/A>` |

## 10. 入出力・転送条件

| 項目 | 内容 |
| --- | --- |
| Transfer Method | `<SFTP / S3 / Shared Folder / API Upload / ...>` |
| Location / Path | `<論理Path。Secretは記載しない>` |
| 認証・認可 | `<方式 / ADR・Security Spec参照>` |
| Polling / Event | `<方式>` |
| Timeout | `<値 / N/A>` |
| Retry | `<回数・間隔 / N/A>` |
| Atomicity | `<一時名→rename等>` |
| Archive | `<処理>` |
| Delete | `<処理・保持期間>` |

## 11. 異常・Reject処理

| Error ID | 検出条件 | 処理 | 利用者／連携先への通知 | Log / Evidence | Retry |
| --- | --- | --- | --- | --- | --- |
| FILE-ERR-001 | `<形式不正等>` | `<Reject / Skip / 全件Rollback>` | `<通知方法>` | `<記録内容>` | `<可否>` |

### 11.1 部分成功の扱い

- `<全件成功のみ / 行単位成功を許可 / その他>`
- `<部分成功時の整合性保証方法>`

## 12. Security / Privacy

- Data Classification: `<PUBLIC / INTERNAL / CONFIDENTIAL / ...>`
- Personal / Sensitive Data: `<有無。実値は書かない>`
- Encryption at Rest: `<方式 / Reference>`
- Encryption in Transit: `<方式 / Reference>`
- Masking / Redaction: `<方針 / N/A>`
- Access Control: `<Role / Reference>`

## 13. 検証・テスト観点

<!--
詳細設計として、実装後に検証可能な設計であることを確認する。
テストケースそのものは別成果物で管理してよい。
-->

| Verification ID | 観点 | 条件／入力 | 期待される設計上の結果 | 関連Requirement |
| --- | --- | --- | --- | --- |
| FILE-V-001 | `<正常形式>` | `<条件>` | `<期待結果>` | `<FR-xxx>` |
| FILE-V-002 | `<形式不正>` | `<条件>` | `<Reject等>` | `<FR/NFR-xxx>` |

## 14. Open Questions

| Question ID | 内容 | 影響 | 解決先 | 状態 |
| --- | --- | --- | --- | --- |
| OQ-FILE-001 | `<未確定事項>` | `<実装/テスト等への影響>` | `<Requirements / ADR / External Owner>` | `OPEN / RESOLVED` |

## 15. Change History

| Version | Date | Change | Reason | Related ID |
| --- | --- | --- | --- | --- |
| `<1.0>` | `<YYYY-MM-DD>` | `<変更内容>` | `<理由>` | `<FR/ADR等>` |
