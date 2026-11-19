---
document_type: "ADDR（Architecture Decision & Design Record）"
system_name: "MiniCommerce"
addr_id: "ADDR-009"
title: "初期データ定義ファイル（FILE-001）の記載形式"
design_type: "外部インターフェース"
target_id: "initial-data-file"
status: "ACTIVE"
generated_by: "ADDR Agent（RUN-AOBA-EC-1118）"
generated_at: "2026-11-19T06:56:00Z"
source_revision: "958677fe4a672dc82902289cfd4b0da5cfac39e5+worktree(RUN-AOBA-EC-1118 requirements 2026-11-19)"
generation_id: "RUN-AOBA-EC-1118"
primary_decision: "定義ファイルを、6種類のデータ名をキーとし各データを行オブジェクトの配列とする1つの JSON オブジェクトとし、項目キー名・値表現・日時表記・BOM の扱いを確定する"
---

# ADDR：初期データ定義ファイル（FILE-001）の記載形式

## 1. 対象範囲

| 項目 | 内容 |
|---|---|
| 対象ID・名称 | initial-data-file：FILE-001 初期データ定義ファイル（OQ-FILE-001、manifest 候補 initial-data-file-format） |
| 対象機能・業務 | FR-060 初期データ一括投入の手順3〜7（解釈・値域判定）、検証用定義ファイルの作成（TASK-013） |
| 対象環境・リリース | 第1期。全環境 |
| 対象外 | 起動手段・結果の提示（ADDR-010）、項目の値域・一意性・参照整合性の規則（FR-060 6.26.3・FILE-001 7章が正本）、本番投入用定義ファイルの保管・廃棄（NOQ-10、UNRESOLVED-32af0f4a0ca9c80f。未決のため範囲を拡大しない） |

## 2. 関連要件・参照成果物

本ADDRの判断または設計差分に直接関係する成果物だけを記載する。
論理DB設計はArchitectureの正本をパス・版・Entity IDで参照し、Entity/属性/識別子/関連/制約の定義表やER図を本書へ複製しない。

| 区分 | 参照先 | 関係 |
|---|---|---|
| 要件 | FR-060、NFR-EN-04、NFR-SC-04、NFR-OM-04（docs/requirements/functional_requirements.md 1.4 6.26.2〜6.26.4・6.26.7、non_functional_requirements.md 1.4） | 「設計で定める記載形式」（6.26.2・E-060-03）、E-060-04・E-060-05 の違反提示、UTF-8、全外部入力の検証 |
| 受入条件 | docs/requirements/use-cases/UC-013.md 9章 AC-UC-013-001、AC-UC-013-003、AC-UC-013-006、AC-UC-013-009 | 正常投入・既定値・違反の全件提示・解釈できないファイル |
| AIステアリング文書 | .github/project-context/project-ai-steering.md 1.3（4章 初期データ定義（UTF-8/JSON）の配置先 app/seed/、5章 snake_case） | JSON・UTF-8、キー名の規約 |
| システム構成図 | N/A（受領なし） | 該当なし |
| データモデル | docs/architecture/db-logical-design.md（LDB-001、1.1）ENT-001〜ENT-007、15章 MAP-009 | 項目と属性の対応は FILE-001 7章と MAP-009 を正とする |
| 関連ADDR | ADDR-007（user_type・discount_type の値）、ADDR-010（起動と違反の提示） | 依存 |
| 設計資料 | FDEF-001 docs/architecture/files/FILE-001.md：FILE-001（4章・6章 REC-001〜REC-006・7章 FLD-001〜FLD-029・14章 OQ-FILE-001）、PLAN-001 docs/architecture/implementation-task-list.md TASK-011・TASK-013 | 本 ADDR が OQ-FILE-001 を決定する。FILE-001 の項目定義の内容は変更しない |

## 3. 背景

### 3.1 判断が必要な理由

FR-060 は定義ファイルを「NFR-EN-04 の文字コードと、設計で定める記載形式」で作成するとし（6.26.2、E-060-03）、Steering は UTF-8/JSON を指定するが、JSON の全体構造・データの配置・項目キー名・公開状態等の値表現・日時表記・BOM の扱いは定まっていない（FILE-001 OQ-FILE-001 の各欄が「未確定」）。

### 3.2 判断時の制約

UTF-8（NFR-EN-04）、JSON（Steering 4章）。行番号は各データの記載順に1から付ける（FILE-RULE-004）。記載のないデータは0行（FILE-RULE-007）。データ間の参照は業務キー（DCN-08）。値域違反は判定を中断せず全件提示（E-060-04）。

## 4. 設計判断

### 4.1 判断基準

| ID | 判断基準 | 優先度 | 根拠ID |
|---|---|---|---|
| DC-001 | データ名・行番号・項目名で違反の位置を一意に示せること | 必須 | E-060-04、E-060-05、FILE-RULE-004 |
| DC-002 | 「解釈できない」（E-060-03）と「値域の違反」（E-060-04）の境界が明確であること | 必須 | FR-060 手順3・手順5 |
| DC-003 | 運用者（EC運営担当）が手で作成・確認しやすく、Python 標準の JSON 解析で読めること | 重視 | UC-013、Steering 4章 |
| DC-004 | 項目キー名が Web API の項目名規約と揃っていること | 参考 | Steering 5章 |

### 4.2 検討した選択肢

| 選択肢ID | 選択肢 | 利点 | 欠点・リスク | 選定結果 | 根拠 |
|---|---|---|---|---|---|
| OPT-001 | 最上位を1つの JSON オブジェクトとし、6種類のデータ名（users 等）をキー、各データを行オブジェクトの配列とする。行オブジェクトは snake_case の項目キーで値を持つ | 配列の位置がそのまま行番号になり、データ名・行番号・項目キーで違反位置を示せる。記載のないデータはキーの省略で表せる | 同じキー名を各行に繰り返し書く | SELECTED | DC-001〜DC-004 |
| OPT-002 | データごとに列名の配列と値の配列の配列（表形式）を持つ | ファイルが短い | 列の位置ずれが値域違反と区別しにくく、手で作成・確認しにくい | NOT_SELECTED | DC-002、DC-003 |
| OPT-003 | 1行1レコードの JSON Lines（各行にデータ種別を持つ） | 行単位で処理できる | 「1つの定義ファイル」の構文誤りの範囲が行ごとになり、データ別の行番号と物理行がずれる | NOT_SELECTED | DC-001、DC-002 |

### 4.3 決定内容

OPT-001 を採用する。

1. 文字コード：UTF-8。先頭の BOM は有っても無くてもよい（読み込み時に除く）。UTF-8 として復号できないバイトを含む場合は E-060-03（文字コードの誤り）。改行・インデントは JSON の空白として扱う。
2. 全体構造：最上位は JSON オブジェクト。キーは users（利用者）、suppliers（仕入先）、categories（商品分類）、products（商品）、stock_units（在庫単位）、coupons（クーポン）の6種類だけとし、各値は行オブジェクトの配列。キーを省略したデータは0行。次は E-060-03（記載形式の誤り）とする：JSON として解析できない、最上位がオブジェクトでない、6種類以外のキー、データの値が配列でない、配列の要素がオブジェクトでない、同じオブジェクト内のキーの重複。
3. 行オブジェクトの項目キー（FILE-001 の Field ID との対応）：
   - users：email（FLD-001）、password（FLD-002）、name（FLD-003）、user_type（FLD-004）
   - suppliers：supplier_code（FLD-005）、name（FLD-006）
   - categories：category_code（FLD-007）、name（FLD-008）、parent_category_code（FLD-009）、display_order（FLD-010）
   - products：product_code（FLD-011）、name（FLD-012）、description（FLD-013）、visibility（FLD-014）、category_codes（FLD-015）、registered_at（FLD-016）
   - stock_units：sku（FLD-017）、product_code（FLD-018）、supplier_code（FLD-019）、variant_name（FLD-020）、price_excluding_tax（FLD-021）、stock_quantity（FLD-022）
   - coupons：coupon_code（FLD-023）、name（FLD-024）、discount_type（FLD-025）、discount_value（FLD-026）、minimum_purchase_amount（FLD-027）、valid_from（FLD-028）、valid_to（FLD-029）
   行オブジェクトに上記以外のキーがある場合は E-060-03（記載形式の誤り）とする。
4. 値表現：文字列項目は JSON 文字列。整数項目（display_order、price_excluding_tax、stock_quantity、discount_value、minimum_purchase_amount）は JSON の整数のみ（文字列・小数・真偽値は「数値として解釈できない値」の値域違反）。user_type は buyer・admin、discount_type は fixed_amount・percentage（ADDR-007）、visibility は public（公開）・private（非公開）。category_codes は文字列の配列。日時（registered_at、valid_from、valid_to）は日本時間の YYYY-MM-DDThh:mm:ss とし、末尾の +09:00 は有っても無くてもよい（他のオフセット・秒未満・日付のみは「日時として解釈できない値」の値域違反）。任意項目のキー省略と null は省略として既定値を適用し、必須項目のキー省略・null は必須項目の欠落とする。型の誤りは値域違反（E-060-04）として行・項目ごとに全件記録する。
5. 違反の提示：データ名は日本語名（利用者等）、項目名は FILE-001 の論理名に項目キーを併記する（例：メールアドレス（email））。値は示さない。

```json
{"users": [{"email": "admin01@example.com", "password": "（平文。検証用の架空の値）", "name": "管理 太郎", "user_type": "admin"}], "categories": [{"category_code": "kitchen", "name": "キッチン", "display_order": 1}], "products": [{"product_code": "MUG-001", "name": "マグカップ", "category_codes": ["kitchen"], "registered_at": "2027-03-31T10:00:00+09:00"}]}
```

### 4.4 決定理由

OPT-001 は配列の位置が FILE-RULE-004 の行番号と一致し、データ名・行番号・項目キーで違反位置を示せる（DC-001）。構造の誤り（E-060-03）と行内の値の誤り（E-060-04）を、最上位・配列・オブジェクトの形と未定義キーまでを構造、個々の値の型・値域を値域として切り分けられる（DC-002）。Python 標準の json で解析でき、手で書いても項目の取り違えが起きにくい（DC-003）。キー名を snake_case の英字とし Web API と揃えた（DC-004）。

## 5. 設計差分

要件定義、AIステアリング文書、システム構成図およびデータモデルから一意に導出できない事項だけを記載する。
データに関する重要判断は、判断で追加・確定した差分と拘束だけを記録する。モデル本文の更新はArchitectureへの変更要求として返す。

| ID | 要件・成果物参照先 | 条件・対象 | 追加・確定した内容 | 実装拘束 |
|---|---|---|---|---|
| DD-001 | FILE-001 4章、NFR-EN-04 | 文字コード・BOM | UTF-8（BOM の有無は問わない）。復号できない場合は E-060-03（文字コードの誤り） | MUST |
| DD-002 | FILE-001 6章 REC-001〜REC-006 | 全体構造 | 6種類のデータ名をキーとする最上位オブジェクト、各データは行オブジェクトの配列。4.3 の2の構造誤りは E-060-03 | MUST |
| DD-003 | FILE-001 7章 FLD-001〜FLD-029 | 項目キー名 | 4.3 の3のキー名を用い、未定義キーは E-060-03 | MUST |
| DD-004 | FILE-001 FLD-004・FLD-014・FLD-016・FLD-025・FLD-028・FLD-029 | 値表現 | 4.3 の4の値表現（コード値、public・private、日本時間の日時表記、整数は JSON 整数のみ）。型・値の誤りは値域違反として全件記録 | MUST |
| DD-005 | FILE-RULE-003 | 任意項目の省略 | キーの省略と null を省略として既定値を適用する。必須項目の省略・null は必須項目の欠落 | MUST |
| DD-006 | E-060-04、NFR-SC-06 | 違反の提示 | データの日本語名・行番号・項目の論理名（項目キー）・理由を示し、値を示さない | MUST |
| DD-007 | NFR-SC-04 | 解析 | 定義ファイルの値を評価・実行（eval 等）せず、JSON として解析するだけとする | MUST_NOT |

## 6. 種別固有差分

`design_type`に対応する節を1つだけ残し、その他の節は生成結果から削除する。要件等から一意に決まらない差分だけを記載し、該当する差分がない項目は `なし` とする。

### C. 外部インターフェースの場合

| 項目 | 設計差分 | 根拠・参照先 |
|---|---|---|
| 方式・プロトコル | サーバー上の UTF-8 JSON ファイル（転送なし） | DD-001、DD-002 |
| 同期・非同期 | なし（起動は ADDR-010） | ADDR-010 |
| 契約の正本・版 | FILE-001（1.1）の項目定義＋本 ADDR-009 の記載形式 | DD-002〜DD-004 |
| 互換性・バージョニング | 版の項目を持たない。第1期内にキー名・構造を変えない | DD-003 |
| タイムアウト | なし | なし |
| 冪等性・重複制御 | なし（業務キーによる重複判定は FR-060 どおり） | FILE-001 5章 |
| 再送・補償 | なし | なし |
| トランザクション境界 | なし（ADDR-004・ADDR-010） | ADDR-004 |
| 責任分界 | 定義ファイルの作成・保管は運用者（DCN-08）、解析・検証は MiniCommerce | DD-006 |

## 7. AI実装制約

当該ADDR固有の不変条件・禁止事項だけを記載する。一般的な実装規約はAIステアリング文書を参照する。

| ID | 種別 | 内容 | 根拠ID |
|---|---|---|---|
| INV-001 | 不変条件 | 行番号は各データの配列の位置（1から）とし、記載順に登録する | FILE-RULE-004、CMN-39 |
| INV-002 | 禁止事項 | 検証用定義ファイル（app/seed/）に実在の個人情報・本番の管理者の資格情報を含めない。本番投入用の定義ファイルをリポジトリに置かない | NFR-SC-25、Steering 7章・OQ-PJ-003 |

## 8. 仮定事項

設計を一意に確定できない場合に、AIが処理継続のために採用した仮定を記載する。外部契約、法令、認証情報、秘密情報など、推測してはならない事項は仮定しない。

| ID | 不足・曖昧な情報 | 採用した仮定 | 根拠 | リスク |
|---|---|---|---|---|
| ASM-001 | なし | なし | なし | LOW |

## 9. 後続工程への引継ぎ事項

設計判断または設計差分によって、後続工程で追加考慮が必要となる事項だけを記載する。

| 区分 | 引継ぎ事項 | 参照先 |
|---|---|---|
| 実装 | TASK-011 の解析は構造検査（E-060-03）→全行の値域検査（E-060-04）→一意性・参照整合性（E-060-05）の順に行う。TASK-013 の検証用定義ファイルは本形式で作成する | DD-002〜DD-005 |
| テスト | BOM 付き・BOM なし、UTF-8 以外、構造誤り、未定義キー、型誤り、日時表記の誤り、null の扱いを検証する | DD-001〜DD-005、FILE-V-002 |
| 運用 | 運用者向け手順書に記載形式と例を載せる | DD-002〜DD-004 |
