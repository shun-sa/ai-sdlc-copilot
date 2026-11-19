---
document_type: "ADDR（Architecture Decision & Design Record）"
system_name: "MiniCommerce"
addr_id: "ADDR-007"
title: "コード値（CD-01〜CD-05、CD-07、CD-08）の外部に出る値の割当て"
design_type: "外部インターフェース"
target_id: "data-model"
status: "ACTIVE"
generated_by: "ADDR Agent（RUN-AOBA-EC-1118）"
generated_at: "2026-11-19T06:52:00Z"
source_revision: "958677fe4a672dc82902289cfd4b0da5cfac39e5+worktree(RUN-AOBA-EC-1118 requirements 2026-11-19)"
generation_id: "RUN-AOBA-EC-1118"
primary_decision: "設計で決定とされたコード値を英小文字 snake_case の固定文字列に割り当て、保持値・Web API・定義ファイルで同じ値を用い、表示名は要件の日本語名とする"
---

# ADDR：コード値（CD-01〜CD-05、CD-07、CD-08）の外部に出る値の割当て

## 1. 対象範囲

| 項目 | 内容 |
|---|---|
| 対象ID・名称 | data-model：CODE-001〜CODE-005、CODE-007、CODE-008（データ要件 CD-01〜CD-05、CD-07、CD-08。OQ-LDB-003、manifest 候補 code-value-assignment） |
| 対象機能・業務 | コード値を保持・返却・受け付ける機能（FR-002、FR-004、FR-031、FR-032、FR-033、FR-041、FR-042、FR-060 ほか） |
| 対象環境・リリース | 第1期。全環境 |
| 対象外 | 都道府県（CD-06。JIS X 0401 の2桁で確定済み）、表示名の文言（要件の名称・MSG-06 が正本）、定義ファイルの構造（ADDR-009） |

## 2. 関連要件・参照成果物

本ADDRの判断または設計差分に直接関係する成果物だけを記載する。
論理DB設計はArchitectureの正本をパス・版・Entity IDで参照し、Entity/属性/識別子/関連/制約の定義表やER図を本書へ複製しない。

| 区分 | 参照先 | 関係 |
|---|---|---|
| 要件 | FR-002、FR-004、FR-024、FR-031、FR-033、FR-041、FR-042、FR-060、NFR-EN-04（docs/requirements/functional_requirements.md 1.4） | data_requirements.md 4章（CD-01〜CD-05・CD-07・CD-08 の値（外部に出る場合）は「設計で決定」）、MSG-06（注文状態の表示名） |
| 受入条件 | docs/requirements/use-cases/UC-001.md 9章 AC-UC-001-001（利用者区分「購入者」の通知）、UC-002.md 9章 AC-UC-002-001・AC-UC-002-002、UC-011.md 9章 AC-UC-011-003 | コード値と表示名の通知・検索条件 |
| AIステアリング文書 | .github/project-context/project-ai-steering.md 1.3（5章 snake_case、6.2 権限は buyer・admin およびデータ所有者） | 利用者区分の値 buyer・admin の事前指定 |
| システム構成図 | N/A（受領なし） | 該当なし |
| データモデル | docs/architecture/db-logical-design.md（LDB-001、1.1）10章 CODE-001〜CODE-008、ENT-001、ENT-007、ENT-008、ENT-010、ENT-013、ENT-014、ENT-015 の区分属性、18章 OQ-LDB-003 | 本 ADDR が OQ-LDB-003 を決定する。Code Set の意味は変更しない |
| 関連ADDR | ADDR-001（コード値と _label の併記）、ADDR-008（模擬決済指示と決済結果）、ADDR-009（定義ファイルの値表現） | 依存 |
| 設計資料 | FDEF-001 docs/architecture/files/FILE-001.md FLD-004・FLD-025、PLAN-001 docs/architecture/implementation-task-list.md TASK-003〜TASK-005 | 定義ファイル・モデルの値 |

## 3. 背景

### 3.1 判断が必要な理由

データ要件 4章は CD-01〜CD-05・CD-07・CD-08 の外部に出る値を「設計で決定」としており（23箇所）、API 応答・定義ファイル・保持値の表現が一意に決まらない（OQ-LDB-003）。

### 3.2 判断時の制約

Steering 6.2 は権限を buyer・admin で表し、5章は API 項目名を snake_case とする。文字コード UTF-8（NFR-EN-04）。画面の表示は日本語のみ（FR-OUT-06）、注文状態は表示名で表示（MSG-06）。

## 4. 設計判断

### 4.1 判断基準

| ID | 判断基準 | 優先度 | 根拠ID |
|---|---|---|---|
| DC-001 | Steering の事前指定（buyer・admin、snake_case）と整合すること | 必須 | Steering 5章・6.2 |
| DC-002 | 保持値・API・定義ファイルで同じ値を使い、変換表を持たないこと | 重視 | CMN-34、NFR-LG-06 |
| DC-003 | 値から意味を読み取れ、誤った値を値域検査で確実に拒否できること | 重視 | NFR-SC-04 |

### 4.2 検討した選択肢

| 選択肢ID | 選択肢 | 利点 | 欠点・リスク | 選定結果 | 根拠 |
|---|---|---|---|---|---|
| OPT-001 | 英小文字 snake_case の固定文字列（例 buyer、paid）を保持値・API・定義ファイルで共通に用い、日本語表示名を別に持つ | Steering の buyer・admin と一致し、値から意味が分かる。変換が不要 | 値の文字列が数値コードより長い | SELECTED | DC-001、DC-002、DC-003 |
| OPT-002 | 数値コード（1、2、…） | 保持値が短い | 値から意味が分からず、Steering の buyer・admin と合わない | NOT_SELECTED | DC-001、DC-003 |
| OPT-003 | 日本語の表示名そのもの（例 購入者、支払済） | 表示に変換不要 | 表示名の変更が保持値・API の変更になる。snake_case 規約の API で日本語の列挙値となる | NOT_SELECTED | DC-001、DC-002 |

### 4.3 決定内容

OPT-001 を採用する。値（表示名）は次のとおり。保持値・Web API・定義ファイルで同じ値を用い、Web API では値と表示名（項目名に _label を付ける：ADDR-001）を返す。

- CD-01 利用者区分（CODE-001）：buyer（購入者）、admin（管理者）
- CD-02 注文状態（CODE-002）：accepted（注文受付）、paid（支払済）、shipped（出荷済）、delivered（配達完了）、cancelled（キャンセル済）
- CD-03 割引方式（CODE-003）：fixed_amount（定額）、percentage（定率）
- CD-04 カート状態（CODE-004）：active（利用中）、ordered（注文済）
- CD-05 決済結果（CODE-005）：approved（承認）、declined（否認）、integration_error（連携エラー）
- CD-07 監査イベント種別（CODE-007）：login_success（ログイン成功）、login_failure（ログイン失敗）、logout（ログアウト）、initial_data_load（初期データ一括投入）
- CD-08 監査ログの結果（CODE-008）：success（成功）、failure（失敗）

注文状態履歴の変更前の状態の「なし」（注文確定時）はコード値を割り当てず値なし（null）とする。値の大文字・小文字は区別し、上記以外の値は入力・定義ファイルで値域の違反とする。

### 4.4 決定理由

OPT-001 は Steering の buyer・admin と一致し（DC-001）、保持値と外部表現を同じにすることで画面・API・定義ファイルの間の変換誤りをなくす（DC-002）。英小文字の固定集合は値域検査で明確に判定できる（DC-003）。表示名は要件の日本語名を別に持つため、画面表示（MSG-06）と Web API の _label に同じ名称を使える。

## 5. 設計差分

要件定義、AIステアリング文書、システム構成図およびデータモデルから一意に導出できない事項だけを記載する。
データに関する重要判断は、判断で追加・確定した差分と拘束だけを記録する。モデル本文の更新はArchitectureへの変更要求として返す。

| ID | 要件・成果物参照先 | 条件・対象 | 追加・確定した内容 | 実装拘束 |
|---|---|---|---|---|
| DD-001 | data_requirements.md 4章、CODE-001〜CODE-005・CODE-007・CODE-008 | コード値 | 4.3 の値を保持値・Web API・定義ファイルで共通に用いる | MUST |
| DD-002 | MSG-06、ADDR-001 | 表示名 | 画面と Web API の _label には要件の日本語名を用いる | MUST |
| DD-003 | NFR-SC-04 | 値域検査 | 4.3 以外の値（大文字違い・前後空白除去後に一致しない値を含む）は入力エラー・値域の違反とする | MUST |
| DD-004 | CODE-002、ENT-014 | 注文確定時の変更前の状態 | 値なし（null）で保持・返却する | MUST |
| DD-005 | ENT-001、ENT-007、ENT-008、ENT-010、ENT-013、ENT-014、ENT-015 | データベースの区分属性 | 4.3 の値の集合に限る検査制約を定義する | SHOULD |

## 6. 種別固有差分

`design_type`に対応する節を1つだけ残し、その他の節は生成結果から削除する。要件等から一意に決まらない差分だけを記載し、該当する差分がない項目は `なし` とする。

### C. 外部インターフェースの場合

| 項目 | 設計差分 | 根拠・参照先 |
|---|---|---|
| 方式・プロトコル | なし（電文は ADDR-001、定義ファイルは ADDR-009） | ADDR-001、ADDR-009 |
| 同期・非同期 | なし | なし |
| 契約の正本・版 | 本 ADDR-007 の 4.3 をコード値の正本とする | DD-001 |
| 互換性・バージョニング | 第1期内に値を変更しない。値の追加は新 ADDR で行う | DD-001 |
| タイムアウト | なし | なし |
| 冪等性・重複制御 | なし | なし |
| 再送・補償 | なし | なし |
| トランザクション境界 | なし | なし |
| 責任分界 | 値の正本は本 ADDR、表示名の正本は要件（データ要件 4章、MSG-06） | DD-002 |

## 7. AI実装制約

当該ADDR固有の不変条件・禁止事項だけを記載する。一般的な実装規約はAIステアリング文書を参照する。

| ID | 種別 | 内容 | 根拠ID |
|---|---|---|---|
| INV-001 | 不変条件 | コード値は1か所（列挙型等）で定義し、画面・API・一括投入・モデルの全てがその定義を参照する | DD-001 |
| INV-002 | 禁止事項 | 画面・API で表示名から値への逆変換を独自に実装しない（受け付けるのは値のみ） | DD-003 |

## 8. 仮定事項

設計を一意に確定できない場合に、AIが処理継続のために採用した仮定を記載する。外部契約、法令、認証情報、秘密情報など、推測してはならない事項は仮定しない。

| ID | 不足・曖昧な情報 | 採用した仮定 | 根拠 | リスク |
|---|---|---|---|---|
| ASM-001 | 提供済み API 契約（OQ-PJ-001）に別のコード値が定められている可能性 | 未格納の間は本 ADDR の値を正とし、格納された場合は差異を新 ADDR で置換する（ADDR-001 ASM-001 と同じ扱い） | Steering 6.2・8.1 | LOW |

## 9. 後続工程への引継ぎ事項

設計判断または設計差分によって、後続工程で追加考慮が必要となる事項だけを記載する。

| 区分 | 引継ぎ事項 | 参照先 |
|---|---|---|
| 実装 | TASK-003〜TASK-005 で Django の列挙型（TextChoices）として定義し、ラベルに日本語名を設定する | DD-001、DD-002、INV-001 |
| テスト | 定義ファイル・API 入力の未定義値・大文字違いが値域の違反・入力エラーになることを確認する | DD-003 |
| 運用 | なし | ASM-001 |
