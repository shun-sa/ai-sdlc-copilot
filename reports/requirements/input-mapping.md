# Requirements 入力対応記録（RUN-AOBA-EC-1118）

- 作成日: 2026-11-19
- 作成者: Requirements Agent（SDLC Orchestrator から委譲）
- 入力版: コミット `958677f`「要件定義書の格納」（ブランチ `task/aoba_EC_1118`）の `docs/requirements/` 一式と `.github/project-context/project-ai-steering.md`
- 構造正本: `.github/skills/requirements/templates/`（10文書）、`.github/project-context/templates/project-ai-steering.md`（いずれも変更なし）
- 今回の対象範囲: 構造検証 FAIL の解消（DR/IFR 主IDの正規化、未定義参照の解消、索引の Steering リンク、`expected-fr.txt` の作成）と、それに伴う参照・Steering の整合確認。要求の意味・AC・数値・Scope は変更しない。
- 注記: 本記録は Agent の作業記録であり、人レビュー・承認の記録ではない（`requirements_quality_checklist.md` の総合判定 BLOCKED／レビュー未実施は変更していない）。

## 1. 入力対応

| 入力Path・版・箇所 | 入力IDまたは要点 | 出力Path・章・ID | 処理 | 根拠・理由 |
| --- | --- | --- | --- | --- |
| docs/requirements/business_requirements.md（958677f） | 業務要件 BR/BP/BEX/BCN、BOQ-01〜07 | 同ファイル（変更なし） | 既存参照 | 構造検証の指摘なし。今回の変更対象 ID の参照なし |
| docs/requirements/functional_requirements.md 1.1（958677f）4章 | FR-001〜FR-060 の26件 | docs/requirements/expected-fr.txt | 再配置 | 4章機能一覧の全FRを実装対象として1行1件で列挙。2.3 の FR-OUT-01〜16 は FR-nnn ではない対象外機能のため一覧外（EXCLUDE 行は不要） |
| docs/requirements/functional_requirements.md 1.1 6章・7章 | 各FRの入力・処理・データ更新、CMN-24〜27 | docs/requirements/data_requirements.md 2.1 各DR行「意味・説明」 | 既存参照 | テンプレート（2.1の意味・説明に対応FRを明記）に従い、FR 6章「データ更新」・処理内容とデータ要件 9.1 UPD／9.2 REF の記載を照合して対応FRを記載（下表3） |
| docs/requirements/data_requirements.md 1.1 2.1 | D-01〜D-15（主データID） | data_requirements.md 1.2 2.1 DR-001〜DR-015 | 再配置（ID正規化） | Skill／テンプレート：2.1主IDは DR-nnn。Orchestrator 依頼による改番。本書内の参照（3章・6章・7章・8.2・9章・10章・11章・12章・1.2）109箇所を同値に置換 |
| docs/requirements/data_requirements.md 1.1 3章ほか | 項目ID D-nn-mm（例 D-13-05） | 同ファイル（変更なし）、1.2「本書で用いるID」に説明を追記 | 既存参照 | 補助IDは主IDと別系列で管理（Skill 手順2）。機能要件・外部IF要件・用語集から既存参照があり、改番すると参照先への影響が広がるため維持。要求IDの接頭辞（DR）を補助行IDへ流用しない |
| docs/requirements/external_interface_requirements.md 1.1 4章 | IF-01（主IF ID） | external_interface_requirements.md 1.2 4章 IFR-001 | 再配置（ID正規化） | Skill／テンプレート：4章主IDは IFR-nnn。本書内の IF ID 参照（1.2、1.3、2.1図、2.2、5.1見出し、5.1.1、5章本文、6章・7章 IF ID 列、8章関連ID、9章影響範囲）43箇所を同値に置換 |
| docs/requirements/external_interface_requirements.md 1.1 4章 連携目的 | IF-01 の親FR（未記載） | 同 1.2 4章 IFR-001 連携目的 | 既存参照 | テンプレート：4章連携目的に対応FRを含める。1.2「本書で用いるID（機能）」・1.3・5.1.3 に FR-031 が IF を起動すると明記済みのため FR-031 を記載 |
| docs/requirements/external_interface_requirements.md 1.1 5章〜7章 | IF-01-TRG-01、IF-01-PRF-04、IF-01-EXC-04 等の個別要件ID | 同ファイル（変更なし）、1.2「本書で用いるID（IF・補助ID）」に説明を追記 | 既存参照 | 補助IDは別系列で管理。非機能要件（NFR-OM-06 の IF-01-EXC-04）・用語集（TCH-03）・UC-007 から既存参照があるため維持 |
| docs/requirements/glossary.md 1.2 TERM-056 関連Requirement ID | CMN-25（未定義参照） | glossary.md 1.3 TERM-056 関連Requirement ID から除外 | RESOLVED（重複整理） | CMN-25 は functional_requirements.md 7.5 に実在する共通機能要件の補助ID（Requirement ID ではない）。対象機能 FR-002・FR-003 は同欄に記載済み。CMN-25 との関係は glossary 5章 TCH-01・TCH-05 に記録済みのため追跡は失われない |
| docs/requirements/use-cases/UC-007.md 1.2 2章・AC-UC-007-016 関連Requirement ID | IF-01-PRF-04（未定義参照 2件） | UC-007.md 1.3 2章・9.16 関連Requirement ID から除外、10章 外部仕様に IFR-001（5.1.8 IF-01-PRF-04）を記載、9.16 Then・測定条件の参照を「外部IF要件 IFR-001 の IF-01-PRF-04」と明記 | RESOLVED（再配置） | IF-01-PRF-04 は外部IF要件 5.1.8 に実在する補助ID（模擬機能の応答1秒以内）で、Requirement ID（FR/NFR）ではない。テンプレート 10章「外部仕様」行が外部IF仕様の参照先。AC の Given/When/Then・目標値・Pass/Fail は不変 |
| docs/requirements/use-cases/UC-007.md 10章 Requirement 行 | IF-01-PRF-04 | 同 10章 外部仕様 行 | 再配置 | 上記と同じ理由で Requirement 行から外部仕様行へ移動 |
| docs/requirements/requirements.md（958677f） | Steering リンク欠落 | requirements.md 成果物一覧に `../../.github/project-context/project-ai-steering.md` を追加 | 再配置 | Skill 手順4：索引に全文書・全UC詳細・Steering へのリンクを置く。FR/NFR の ID 一覧は変更なし（FR 26件・NFR 一覧は検証で一致） |
| .github/project-context/project-ai-steering.md 1.1 2.2・4章・5章 | `docs/specifications/api-contract.md` を「提供済みAPI契約の正本」として参照 | project-ai-steering.md 1.2 2.2 備考、8.1 OQ-PJ-001 | 未決 | 作業ツリーにファイルが存在しない（`Test-Path` False。過去の別ブランチ履歴にのみ存在し、本 Run の入力として提供されていない）。PJ 前提の根拠資料の確認が必要なため Steering 8.1 に記録。要件本文は API 呼出し方式を定義しない範囲のため要件内容には影響しない |
| .github/project-context/project-ai-steering.md 1.1 6.2 Logging | 「認証トークン」 | 同 1.2 6.2「ログイン状態を示す情報」 | 重複整理（表記統一） | 用語集 TERM-056 で「認証トークン」は非推奨表記。引用元 NFR-SC-06 の表記に合わせた。制約範囲は不変 |
| .github/project-context/project-ai-steering.md 1.1 6.3 Sensitive Data Classification | CLS-04「パスワードハッシュ」 | 同 1.2 6.3「パスワード（照合用）」 | 重複整理（表記統一） | 引用元 data_requirements.md 8.1 CLS-04 の定義（パスワード（照合用）、平文・復号可能な形式で保持しない）に合わせた。保持方式（ハッシュ等）は要件で指定しておらず設計に委ねる |
| .github/project-context/project-ai-steering.md 1.1 3章〜7章（上記以外） | 技術スタック・実行環境・規約・禁止事項（旧Steering 由来） | 同ファイル（変更なし） | 既存参照 | 指定元（旧Steering、NFR-EN/OM/SC 等）付きの事前前提。ADR/ADDR/TASK 等の後続工程ID・設計パスは含まれない（Validator で確認）。7章の `--reset` 表記は旧Steering 由来の既存禁止事項として維持 |
| docs/requirements/requirements_quality_checklist.md 1.2 3章 | 対象成果物の版 | 同 1.3 3章（データ要件1.2、外部IF要件1.2、用語集1.3、UC-007 1.3） | 再配置 | 改版に合わせて対象版のみ更新。レビュー結果・総合判定（BLOCKED／未実施）は変更しない |
| docs/requirements/non_functional_requirements.md、ui_report_requirements.md、use-case-user-story-index.md、use-cases/UC-001〜006・008〜013（958677f） | NFR、SCR/UI、Actor/US/UC、AC | 各ファイル（変更なし） | 既存参照 | 構造検証の指摘なし。旧主ID（D-nn／IF-01）の参照なし（NFR の IF-01-EXC-04 は補助IDで維持） |
| 各文書の未決事項（BOQ-01〜04・06・07、FOQ-01、DOQ-01〜03、XOQ-01〜06、NOQ-01〜07、SOQ-01〜05、ISSUE-REVIEW-001） | 既存の未決・確認事項 | 各文書の未決事項欄（変更なし） | 未決（既存） | いずれも後続フェーズ・本番基盤選定・人レビューに関する事項で、各記載で「本リリースの実装には影響しない」または後続フェーズと明記。今回の範囲で新たな判断はしない |

## 2. 旧ID → 新ID 対応

| 区分 | 旧ID（版1.1） | 新ID（版1.2） | 名称 | 参照更新範囲 |
| --- | --- | --- | --- | --- |
| データ要件 主ID | D-01 | DR-001 | 利用者 | data_requirements.md 内 |
| データ要件 主ID | D-02 | DR-002 | 仕入先 | 同上 |
| データ要件 主ID | D-03 | DR-003 | 商品分類 | 同上 |
| データ要件 主ID | D-04 | DR-004 | 商品 | 同上 |
| データ要件 主ID | D-05 | DR-005 | 商品分類所属 | 同上 |
| データ要件 主ID | D-06 | DR-006 | 在庫単位 | 同上 |
| データ要件 主ID | D-07 | DR-007 | クーポン | 同上 |
| データ要件 主ID | D-08 | DR-008 | カート | 同上 |
| データ要件 主ID | D-09 | DR-009 | カート明細 | 同上 |
| データ要件 主ID | D-10 | DR-010 | 注文 | 同上 |
| データ要件 主ID | D-11 | DR-011 | 注文明細 | 同上 |
| データ要件 主ID | D-12 | DR-012 | 配送先 | 同上 |
| データ要件 主ID | D-13 | DR-013 | 決済記録 | 同上 |
| データ要件 主ID | D-14 | DR-014 | 注文状態履歴 | 同上 |
| データ要件 主ID | D-15 | DR-015 | 監査ログ | 同上 |
| 外部IF要件 主ID | IF-01 | IFR-001 | 決済要求（売上確定） | external_interface_requirements.md 内（他文書は補助IDのみ参照） |
| 範囲表記 | D-01〜D-14、D-08〜D-14、D-01〜D-07、D-10〜D-14、D-01〜D-15 | DR-001〜DR-014、DR-008〜DR-014、DR-001〜DR-007、DR-010〜DR-014、DR-001〜DR-015 | － | data_requirements.md 内 |
| 補助ID（変更なし） | D-nn-mm（項目ID）、IF-01-xxx-nn（IF個別要件ID） | 変更なし | － | 他文書からの既存参照を保持 |

旧ID D-01〜D-15・IF-01 は欠番とし、再利用しない。

## 3. DR／IFR の対応FR（テンプレート必須欄への記載内容）

| 主ID | 対応FR | 根拠 |
| --- | --- | --- |
| DR-001 利用者 | FR-001、FR-002、FR-004、FR-041、FR-042、FR-060 | FR 6章（登録・照合・照会・購入者情報）、UPD-01・UPD-02、REF-01〜REF-03 |
| DR-002 仕入先 | FR-040、FR-060 | UPD-03、REF-04、FR-040 入力・出力 |
| DR-003 商品分類 | FR-010、FR-011、FR-012、FR-060 | UPD-04、REF-06、FR-011 分類ID絞り込み、FR-012 所属分類 |
| DR-004 商品 | FR-011、FR-012、FR-021、FR-030、FR-040、FR-060 | UPD-05・UPD-15・UPD-20、REF-07・REF-08 |
| DR-005 商品分類所属 | FR-011、FR-012、FR-060 | UPD-06、REF-09 |
| DR-006 在庫単位 | FR-011、FR-012、FR-020、FR-021、FR-022、FR-030、FR-034、FR-040、FR-045、FR-060 | UPD-07〜UPD-09・UPD-15〜UPD-17、REF-10・REF-11、FR-020 手順5 |
| DR-007 クーポン | FR-024、FR-025、FR-026、FR-030、FR-060 | UPD-10・UPD-12・UPD-13・UPD-20、REF-12 |
| DR-008 カート | FR-020〜FR-025、FR-026、FR-030 | UPD-11〜UPD-14、REF-14 |
| DR-009 カート明細 | FR-020、FR-021、FR-022、FR-023、FR-026、FR-030 | UPD-15〜UPD-18、UPD-26、REF-15 |
| DR-010 注文 | FR-030〜FR-034、FR-041〜FR-045 | UPD-20〜UPD-25、REF-17・REF-18 |
| DR-011 注文明細 | FR-030、FR-033、FR-034、FR-042、FR-045 | UPD-26、UPD-09、REF-19・REF-20 |
| DR-012 配送先 | FR-030、FR-033、FR-042 | UPD-27、REF-21・REF-22 |
| DR-013 決済記録 | FR-031、FR-042 | UPD-28、REF-24、IFR-001 |
| DR-014 注文状態履歴 | FR-030、FR-031、FR-033、FR-034、FR-042、FR-043、FR-044、FR-045 | UPD-29、CMN-26、REF-25・REF-26 |
| DR-015 監査ログ | FR-002、FR-003、FR-060 | UPD-31、CMN-24・CMN-25・CMN-27 |
| IFR-001 決済要求（売上確定） | FR-031 | EIR 1.2・1.3・5.1.3、FR-031 機能種別「連携」 |

関連FRのないDR／IFRはない。

## 4. 実装対象FR（expected-fr.txt）

- 出典: `docs/requirements/functional_requirements.md` 4章 機能一覧（26件）。Trace Map・監査結果からの逆生成ではない。
- 実装対象: FR-001、FR-002、FR-003、FR-004、FR-010、FR-011、FR-012、FR-020〜FR-026、FR-030〜FR-034、FR-040〜FR-045、FR-060（26件）
- 対象外（EXCLUDE）: なし。要件上、FR-nnn を実装対象外とする承認済みの根拠はない（対象外機能は FR-OUT-01〜16 として別系列で定義済みで、FR-nnn ではない）。
- 備考: FR-026 は単独起動しない計算機能（FR-020〜FR-025・FR-030 の実行時に適用）だが、正本で必須の機能であり実装対象に含める。

## 5. 設計引継ぎ（Architecture／ADDR で決定する事項）

| 対象 | 根拠となる要件ID・出典 | 引継ぎ内容 |
| --- | --- | --- |
| IFR-001 の方式 | external_interface_requirements.md 4章（方式「設計で決定」） | 模擬決済の呼出し方式。業務条件（同期、10秒上限、模擬機能1秒以内、自動再送なし、二重決済防止）は IFR-001 5.1.3〜5.1.10 で確定済み |
| IFR-001 の認証方式 | IF-01-SEC-01（設計で決定） | 本リリースの模擬機能に対する認証方式。認可範囲は IF-01-SEC-02 で確定済み |
| コード値の割当て | data_requirements.md 4章 CD-01〜CD-05・CD-07・CD-08（「設計で決定」23箇所） | コード値（物理値）の割当て。区分の意味・値の集合は確定済み |
| 識別子の採番方式・物理データ構造 | data_requirements.md 1.2「本書で定義しない」、DR-001〜DR-015 | 内部採番方式、テーブル定義、物理型、インデックス |
| パスワード（照合用）の保持方式 | data_requirements.md CLS-04、D-01-03、FR CMN-06 | 平文・復号可能な形式で保持しないことのみ確定。具体方式は設計 |
| Web API 呼出し方式（パス・電文形式） | functional_requirements.md 1.2「本書で定義しない」、Steering 5章 | Steering の事前指定（REST/JSON 等）の根拠資料が未格納（OQ-PJ-001）。資料の提供有無の確認後に設計で扱う |

## 6. 不足・仮定・矛盾の分類

| 区分 | 内容 | 対応 |
| --- | --- | --- |
| RESOLVED | glossary TERM-056 の CMN-25 未定義参照 | 1章のとおり。実在ID（FR-002・FR-003）で関係を表し、CMN-25 との関係は TCH-01・TCH-05 に保持 |
| RESOLVED | UC-007 の IF-01-PRF-04 未定義参照（2件） | 1章のとおり。10章外部仕様へ IFR-001（5.1.8 IF-01-PRF-04）を記載 |
| RESOLVED | データ主ID D-nn、外部IF主ID IF-01 の形式不正 | DR-001〜DR-015、IFR-001 へ改番（2章） |
| RESOLVED | requirements.md の Steering リンク欠落、expected-fr.txt 不在 | 追加・作成 |
| ASSUMPTION | 補助ID（D-nn-mm、IF-01-xxx-nn）を旧接頭辞のまま維持 | 主IDではなく別系列の補助IDとして扱う。改番する場合は機能要件・非機能要件・用語集・UC-007 の参照更新が必要 |
| 未決（Steering 8.1） | OQ-PJ-001：`docs/specifications/api-contract.md` が作業ツリーに存在しない | PJ Owner への確認。要件本文には影響しないが、後続 Architecture/ADDR の入力・Steering 5章／6.2 の API 形式指定の根拠に影響 |
| 未決（既存） | BOQ／FOQ／DOQ／XOQ／NOQ／SOQ、ISSUE-REVIEW-001 | 変更なし。本リリースの要件確定を妨げる記載はない。人レビューは未実施 |

## 7. 検証

- コマンド: `python .github/skills/requirements/scripts/validate_requirements_structure.py`
- 実施前: FAIL（exit 1、指摘20件）
- 実施後: PASS（exit 0、1回目の再検査で解消）
- 追加照合: `expected-fr.txt`（26件）と機能一覧4章の FR（26件）が完全一致。docs/requirements と Steering に旧主ID（D-nn、IF-01 単独）の残存なし（改訂履歴・ID説明行の記載を除く）。

## 8. 修正cycle 1（REQUIREMENTS Scope Assurance 指摘対応、2026-11-19）

- 入力: `reports/traceability/validation-result.json`（C01 FAIL 9件）、`reports/quality-review/quality-review-report.json`（QR-REQ-001〜007）、`reports/security-review/security-review-report.json`（SEC-REQ-001〜005。JSON・MD とも本文の日本語が文字化けして判読できないため、Orchestrator の指摘要約と判読可能な Evidence の行番号・ID で照合した）。過去実験ブランチ・その reports は参照していない。
- 方針: 入力資料（要件書群 958677f 版と本 Run の改版）に根拠がある文書間の矛盾・誤ID・表記は修正し、どちらを正としたかの根拠を下表に記録した。根拠のない業務判断（本番の決済の扱い、総当たり対策の採否、本番での削除指定の使用可否等）は決定せず、既存の未決事項欄に影響範囲・担当・暫定扱いとともに登録した。テンプレートの章構成、既存の要件ID・AC ID、Scope（FR-OUT-01〜16）、数値は変更していない。新規の FR／NFR ID はない。`expected-fr.txt` は変更しない（26件）。

### 8.1 入力対応

| 入力Path・版・箇所 | 入力IDまたは要点 | 出力Path・章・ID | 処理 | 根拠・理由 |
| --- | --- | --- | --- | --- |
| traceability validation-result.json C01（UC-003:269、UC-004:367、UC-005:368、UC-006:338、UC-007:361、UC-008:267、UC-010:237、UC-011:328） | 欠番注記に未定義の AC ID 文字列を記載 | use-cases/UC-003〜006・008・010・011（1.3）、UC-007（1.4）9章冒頭の欠番注記 | 重複整理（表記変更） | 欠番の AC は定義されていないため ID 文字列を書くと未定義参照になる。「AC の連番 nnn（理由。連番は再利用しない）」の表記に変更。AC の採番・本文・Pass/Fail は不変。BR の欠番注記（BR-UC-xxx-nnn）は C01 の指摘対象外のため変更しない |
| QR-REQ-002（NFR-LG-03 vs FR-031/034/043/044/045、UPD-21〜25） | NFR-LG-03「登録後に更新・削除しない」が注文の状態遷移と矛盾 | non_functional_requirements.md（1.2）NFR-LG-03 対応方針 | RESOLVED（矛盾） | データ要件 9.1 が正。UPD-26〜UPD-29 は注文明細・配送先・決済記録・注文状態履歴を「登録後は変更しない」とし、注文は UPD-21〜UPD-25 で状態・日時・配送伝票番号を更新する。機能要件 6章・8章の状態遷移も同じ。NFR-LG-03 の目的（法人税法の7年保存）は削除しないことで満たされるため、7年保存・削除しない条件は維持し、更新の範囲を UPD-21〜UPD-25 に限ると明記 |
| QR-REQ-004（UI-02 vs NFR-US-06） | 対応OS「限定しない」と「PC（Windows 11）」の不一致 | ui_report_requirements.md（1.2）2.1 UI-02 | RESOLVED（矛盾） | 品質条件（対応環境）の正本は非機能要件（Skill 正本表、Steering 2.2）。NFR-US-06 の目標値・検証方法（Windows 11）、NFR-US-01 の測定条件（PC：NFR-US-06）に一致させた。ブラウザ・画面幅は不変 |
| QR-REQ-005（Steering 3章・4章・5章） | 根拠ID誤り：NFR-OM-07（不存在）、Backend の NFR-EN-09 欠落、Frontend の NFR-EN-05 | project-ai-steering.md（1.3）3章 Frontend・Backend・Static Analysis、4章 Development / CI、5章 Build / Test Standards | RESOLVED（誤ID） | NFR 10章で照合：静的解析は NFR-EN-11（PEP 8、規約違反0件、ツール指定なし）、フレームワーク・SPA 不使用は NFR-EN-09、PC は NFR-US-06。ruff と「指摘0件」は旧Steering §3 由来の事前指定として保持し、要件上の基準（NFR-EN-11）と区別して記載。技術・版は不変 |
| SEC-REQ-005（CLS-03 vs NFR-SC-20） | CLS-03「保存時：不要」と NFR-SC-20 の保護層が不明確 | data_requirements.md（1.3）8.1 CLS-01〜CLS-03 暗号化欄 | RESOLVED（表記） | NFR-SC-20 は「ENV-02 のデータベースの全データ（個人情報を含む）とバックアップ」を対象とし、データ要件 1.2 は暗号化方式を定義しない。CLS の保存時欄は項目単位の暗号化の要否であると明記し、媒体・バックアップの判読防止は全データに NFR-SC-20 を適用すると記載。NFR-SC-20 の優先度（推奨）・目標値は不変 |
| SEC-REQ-002（NFR-SC-13/14/27、VUL-02、VUL-11、NOQ-06） | VUL-02（A07）・VUL-11（A09）と対象外（FR-OUT-11）の矛盾、NFR-SC-13 根拠と NFR-SC-15 の食い違い | non_functional_requirements.md（1.2）NFR-SC-13 根拠、VUL-02・VUL-11 対策方針、14章 NOQ-08 | 矛盾の表記整理＋未決 | FR-OUT-11（承認済みの対象外）に合わせ、VUL-02 の充足条件から試行回数制限・アカウントロック・多要素認証を除くことを明記（Scope は変更しない）。VUL-11 にログイン失敗の監視が 6.2 に無く監査ログで事後調査する現状（NFR-SC-14）を明記。NFR-SC-13 の根拠に管理者の参照範囲（NFR-SC-15、NFR-SC-24）を追記。対象外のまま本番稼働することの受容可否・代替策は業務判断のため NOQ-08 に登録（暫定：実装範囲は変更しない） |
| QR-REQ-001／SEC-REQ-004（NFR-MG-04/05/07 vs UPD-33・DCN-07・UC-013・Steering 7章、FR-060） | 本番環境で「既存データ（監査ログを除く）を削除してから投入する指定」を使ってよいか | non_functional_requirements.md NOQ-09（正）、NFR-MG-04・NFR-MG-07 根拠に参照追記／functional_requirements.md（1.2）FOQ-02／data_requirements.md（1.3）DCN-07 追記・DOQ-04／Steering 7章 注記・8.1 OQ-PJ-002 | 未決 | 稼働開始後の本番環境で使わないことは全文書で一致（NFR-MG-04/07 は稼働開始前の移行のみが対象、DCN-07 の理由は注文関連データの7年保存）。不一致は稼働開始前（注文関連データ 0件：NFR-MG-01）の本番移行に限られるが、どちらを正とするか（NFR-MG-04 の目標値を変えるか、DCN-07・UPD-33・Steering の制約を緩めるか、FR-060 に本番での制限を設けるか）は双方に明示の記載があり入力からは決められない。暫定：FR-060 の振る舞いは変更しない、稼働開始後の本番では使わない。担当：EC事業責任者・システム運用担当 |
| QR-REQ-003／SEC-REQ-001（FR-031、FR-043、BR-15、BCN-02、SCR-008） | 本番で模擬決済（購入者が承認を選択）により支払済となる業務前提が未定義 | business_requirements.md（1.2）BOQ-08（正）、BCN-02 関連ID／functional_requirements.md FOQ-03 | 未決 | BCN-02 は「模擬決済で稼働確認を行う」とするのみで、本番での代金回収・出荷・返金の扱い、購入者が結果を選べる画面を社外公開で提供することの受容可否はどの要件にもない。新機能（実決済連携 FR-OUT-01）は追加しない。暫定：機能・画面の要件は変更しない。担当：EC事業責任者 |
| SEC-REQ-003（FR-060、NFR-SC-07/17、DCN-08、Steering 4章 `app/seed/`） | 本番管理者の初期パスワードを定義ファイルに平文、変更機能なし、保管・廃棄の要件なし | non_functional_requirements.md NOQ-10（正）／Steering 4章 注記・8.1 OQ-PJ-003 | 未決 | 確定済みの事項（DCN-08 本システム外での保管、VUL-08 管理者ごとの作成、NFR-SC-17 個別伝達、FR-OUT-09 変更機能なし）を確認。保管場所・アクセス者・廃棄、変更手段なしの受容可否は入力に無く、パスワード変更機能の追加は Scope 外（FR-OUT-09）のため決定しない。暫定：実装範囲は変更しない、本番投入用定義ファイルはリポジトリに置かない（DCN-08 と Steering 7章の実在個人情報の使用禁止に基づく） |
| QR-REQ-006（BCN-05、FCN-07、NFR-LG-06、用語集） | EC販売規程（2026年10月制定予定）の制定状況の記録がない | business_requirements.md BOQ-09、BCN-05 関連ID／functional_requirements.md FCN-07 関連ID | 未決 | 制定の記録は入力に無い。確認事項として登録し、暫定で BR-01〜BR-19 を現行の記載のまま扱う。NFR-LG-06・用語集の「（案）」表記は状況が不明のため変更しない |
| QR-REQ-007（FOQ-01、BOQ-07、CMN-38、FR-060、DCN-07） | 在庫補充の「運用で対応」が受ける本リリースの制約が未記載 | business_requirements.md BOQ-07、functional_requirements.md FOQ-01 | RESOLVED（記載追加）＋未決（既存） | CMN-38・FR-060（E-060-05）・DCN-07・BCN-08 の既存の記載から、登録済み在庫単位の在庫数量を補充する手段が本リリースにないこと、未登録 SKU の追加投入は FR-060 の範囲で可能なこと、制約を超える選択は変更要求となることを明記。決定自体（期限 2027-02-26）は既存のまま |
| requirements_quality_checklist.md 3章 | 対象成果物の版 | 同（1.4）3章 | 再配置 | 改版に合わせて対象版のみ更新。総合判定 BLOCKED／人レビュー未実施は変更しない |

### 8.2 不足・仮定・矛盾の分類（本cycle）

| 区分 | 内容 | 対応 |
| --- | --- | --- |
| RESOLVED | Traceability C01 9件、QR-REQ-002、QR-REQ-004、QR-REQ-005、SEC-REQ-005、QR-REQ-007（制約の明記） | 8.1 のとおり |
| RESOLVED（一部）＋未決 | SEC-REQ-002 | 文書間の矛盾（VUL-02/11 と FR-OUT-11、NFR-SC-13 根拠）は解消。対策の採否・リスク受容は NOQ-08 |
| 未決（BLOCKED 候補） | SEC-REQ-001／QR-REQ-003（BOQ-08、FOQ-03） | 本番での模擬決済の業務前提。決定によって FR-031・SCR-008・FR-043 の振る舞いの変更が必要になり得るため、PJ Owner の判断が必要（HIGH） |
| 未決 | QR-REQ-001／SEC-REQ-004（NOQ-09、FOQ-02、DOQ-04、OQ-PJ-002）、SEC-REQ-003（NOQ-10、OQ-PJ-003）、QR-REQ-006（BOQ-09） | 担当・暫定扱い・期限の考え方を各未決事項欄に記載 |
| ASSUMPTION | 未決事項の期限 | 入力に日付の根拠がないため、既存の XOQ と同じく「〜の前（日付は担当が設定）」と相対的な時点で記載した |

### 8.3 設計引継ぎ（追加）

| 対象 | 根拠となる要件ID・出典 | 引継ぎ内容 |
| --- | --- | --- |
| FR-060 の本番環境での削除指定の扱い | NOQ-09、FOQ-02、DOQ-04、Steering OQ-PJ-002 | 決定前は FR-060 の要件（6.26）どおりとし、実行環境による制限を設計で追加しない。決定後に要件が変わる場合は Requirements へ差し戻す |
| 支払（FR-031）・支払画面（SCR-008）の本番での扱い | BOQ-08、FOQ-03 | 決定前は現行要件どおり（模擬決済、模擬決済の結果の選択）。本番環境のみの挙動差を設計で追加しない |

### 8.4 検証（本cycle）

- `python .github/skills/requirements/scripts/validate_requirements_structure.py`：PASS（exit 0）
- `python .github/skills/traceability-audit/scripts/trace_check.py --scope REQUIREMENTS --no-write`：C01 は 0件に解消。C11 3件（`reports/traceability/trace-map.json`、`traceability-report.json`、`traceability-report.md` が正本から再生成した内容と不一致。差し戻し先 TRACEABILITY_REGENERATE）。要件書の改版に伴う派生成果物の再生成待ちであり、Requirements Agent は派生成果物を生成しない
- 追加照合：`expected-fr.txt` 26件と機能一覧4章の FR 26件の一致（変更なし）。新規の NOQ-08〜10、FOQ-02・03、DOQ-04、BOQ-08・09、OQ-PJ-002・003 は既存IDと重複しない（BOQ-05 は欠番のまま再利用しない）

## 9. 修正cycle 2（REQUIREMENTS Scope Security 再監査・品質 advisory 対応、2026-11-19）

- 入力: `reports/security-review/security-review-report.json`（修正cycle1後の再監査。UTF-8 で判読可。SEC-REQ-001〜004・006・007 未解決、SEC-REQ-005 解消済み）、`reports/quality-review/quality-review-report.json`（PASS、advisory QR-REQ-008・009。本文は文字化けのため Orchestrator の要約と requirement_reference で照合）。過去 Run のブランチ・reports は参照していない。
- 方針: 入力資料に根拠がある文書間の矛盾（SEC-REQ-006 の表記、SEC-REQ-007、QR-REQ-008、QR-REQ-009）は解消し、どちらを正としたかを下表に記録した。業務判断（本番での模擬決済の扱い、総当たり対策の採否、資格情報の失効手段の追加）は決めず、未決事項の記載（判断期限、決定・受容の記録方法、残存リスク、リスク受容の判断者、受容記録の有無、設計での暫定扱い、稼働開始の判定時の確認）を補った。テンプレートの章構成、既存の要件ID・AC ID、Scope（FR-OUT-01〜16）、目標値・数値、`expected-fr.txt`（26件）は変更していない。新規の FR／NFR／未決事項 ID はない。成果物の改訂履歴にはレビュー指摘ID（成果物に定義されない ID）を書かず、指摘の要点で記載した（trace_check C01 の未定義参照を避けるため）。

### 9.1 入力対応

| 入力Path・版・箇所 | 入力IDまたは要点 | 出力Path・章・ID | 処理 | 根拠・理由 |
| --- | --- | --- | --- | --- |
| SEC-REQ-007（FR 10.1 ERR-01・03・04・06 の「ログ記録 不要」vs NFR 6.3 LOG-01） | エラー応答時のアプリケーションログ出力の有無が文書間で不一致 | functional_requirements.md（1.3）10.1 ERR-01〜ERR-04・ERR-06 を「要（アプリケーションログ：LOG-01。監査ログへの記録は CMN-24・LOG-04 の対象（初期データ一括投入の失敗を含む）に限る）」、ERR-05 に記録先（LOG-04・LOG-01）を明記 | RESOLVED（矛盾） | LOG-01 を正とした。根拠：Skill 手順2「運用ログの要求は非機能要件で扱う」、LOG-01 の出力契機（業務・入力・認証・権限・対象なしエラーの応答時）、NFR-OM-18（要求ごとの識別子での追跡）、VUL-11。10.1 は ERR-07・ERR-08 でもアプリケーションログを「ログ記録」欄に記載しており、同欄はアプリケーションログを含む。監査ログの対象は CMN-24・LOG-04（ログイン・ログアウト・一括投入）のまま。ERR-02 も LOG-01（業務エラー時はエラーの種類）と同じ不一致のため併せて訂正。利用者への通知内容は不変 |
| SEC-REQ-006（FR-001 E-001-02 vs NFR-SC-12・CMN-05・MSG-04③） | 会員登録で登録済みメールアドレスが判別できる | non_functional_requirements.md（1.3）NFR-SC-12 根拠、14章 NOQ-08 | 表記整理＋未決 | 区別しない応答の適用範囲はログイン（CMN-05 の対象機能 FR-002、MSG-04③「認証失敗時」）であり、E-001-02 は承認済みの会員登録の振る舞い。両者は適用範囲が異なることを NFR-SC-12 根拠に明記。登録有無の判別を許すことの受容可否は業務判断のため NOQ-08 の対象に追加（E-001-02 の振る舞いは変更しない） |
| QR-REQ-008（NFR-MG-01「稼働開始時の監査ログ 0件」vs FR-060・UPD-31・LOG-04） | 本番の初期データ一括投入で監査ログが登録される | non_functional_requirements.md（1.3）NFR-MG-01 要件 | RESOLVED（矛盾） | FR-060・UPD-31・LOG-04・NFR-SC-22 を正とした。データ要件 DR-015 の初期件数の注記が「稼働開始前の初期データ一括投入と投入後確認のログイン・ログアウトの記録（15件）は初期件数に含めない」と稼働開始時の監査ログの存在を前提としているため。NFR-MG-01 の目的（現行データを移行しない）に合わせ「監査ログは移行しない（稼働開始時は投入と投入後確認の記録に限る）」と訂正。指標（移行件数）・目標値（0件）・検証方法は不変 |
| QR-REQ-009（UPD-33 実行条件「検証環境に限る」に DOQ-04 参照なし） | DCN-07・NOQ-09 と記載粒度の不一致 | data_requirements.md（1.4）9.1 UPD-33、use-cases/UC-013.md（1.3）BR-UC-013-006 備考 | RESOLVED（参照追記） | DCN-07（1.3 で追記済み）と同じく、稼働開始前の本番移行での使用可否は DOQ-04（正：NOQ-09）で確認、稼働開始後の本番環境で指定しないことは確定、と記載。条件そのもの（検証環境に限る）は未決のため変更しない |
| SEC-REQ-001（BOQ-08・FOQ-03） | 本番で購入者の選択のみで支払済→出荷可能。暫定扱いが現行どおりでリスク低減・受容の記録なし | business_requirements.md（1.3）BOQ-08（正）、functional_requirements.md（1.3）FOQ-03 | 未決（記載補強） | 決定の記録方法（決定内容または受容者・根拠・条件）、残存リスク（ST-PO-02・ST-PO-05 による代金未回収のままの出荷）、リスク受容の判断者（担当欄の EC事業責任者。STK-05 本書の承認者）、受容の記録なし、設計での暫定扱い（現行要件で設計し本番のみの挙動差を追加しない。8.3 と同じ）、稼働開始の判定時の確認を追記。期限を「設計（Architecture）着手前、遅くとも稼働開始の判定前」に明確化（BOQ-08 自身が「機能・画面の変更を要する場合は設計前」としていたことに基づく）。代金回収・出荷停止・画面の提供可否は決めていない |
| SEC-REQ-002（NOQ-08） | 総当たり・リスト型攻撃への対策なし、受容未記録、期限が実装後 | non_functional_requirements.md（1.3）NOQ-08、14章前文 | 未決（記載補強） | 受容する場合の記録項目（受容者・根拠・条件、管理者を対象に含めるか）、受容しない場合は代替策を検証可能な NFR として定義すること、残存リスク、リスク受容の判断者（EC事業責任者）、受容の記録なし、暫定扱い（ログイン失敗は LOG-04 に記録し事後調査）を追記。期限を設計（Architecture）着手前（遅くとも NFR-SC-29 の診断前）へ前倒し。FR-OUT-11 は対象外のまま |
| SEC-REQ-003（NOQ-10） | 管理者の資格情報の失効（無効化・変更）手段が要件になく、NOQ-10 の対象にも未記載 | non_functional_requirements.md（1.3）NOQ-10 | 未決（記載補強） | 漏えい疑い・退職・異動時の無効化／パスワード変更手段（運用手順を含む）の有無を NOQ-10 の対象に追加。手段がないことの根拠（FR-OUT-09、CMN-07、CMN-08、E-060-05、DCN-07）、残存リスク、リスク受容の判断者、受容の記録なしを追記。期限を「失効・変更手段：設計着手前／保管・廃棄：本番投入の開始前」に分けて明確化。機能は追加しない。Steering OQ-PJ-003（配置先の前提）は対象が異なるため変更しない |
| SEC-REQ-004（NOQ-09）advisory | 稼働後の本番での削除指定の誤実行を防ぐ手段が運用手順のみ | non_functional_requirements.md（1.3）NOQ-09 | 未決（記載補強） | 決定時に誤実行の防止手段（運用手順か FR-060 のシステム上の条件か）を明記すること、残存リスク（7年保存データ・注文状態履歴の消失、実行者は運用者2名：NFR-SC-15）を追記。FR-060 の振る舞いは不変 |
| 稼働開始判定への組込み | 未決のまま稼働することの扱い | non_functional_requirements.md（1.3）14章前文、BOQ-08、NOQ-08、NOQ-10 | 未決（記載補強） | 判定時に決定または受容の記録の有無を確認し、記録がない事項は判定の未充足事項として EC事業責任者へ報告すると記載。稼働可否そのものは決めていない（判定者は EC事業責任者） |
| requirements_quality_checklist.md 3章 | 対象成果物の版 | 同（1.5）3章 | 再配置 | 改版に合わせて対象版のみ更新。総合判定 BLOCKED／人レビュー未実施は不変 |

### 9.2 不足・仮定・矛盾の分類（本cycle）

| 区分 | 内容 | 対応 |
| --- | --- | --- |
| RESOLVED | SEC-REQ-007、QR-REQ-008、QR-REQ-009、SEC-REQ-006 の文書間表記 | 9.1 のとおり |
| 未決（BLOCKED、HIGH） | SEC-REQ-001：BOQ-08／FOQ-03 | EC事業責任者の決定またはリスク受容の記録が設計（Architecture）着手前に必要 |
| 未決（BLOCKED、MEDIUM） | SEC-REQ-002：NOQ-08（SEC-REQ-006 の受容可否を含む）、SEC-REQ-003：NOQ-10 | EC事業責任者・システム運用担当の決定または受容の記録が設計着手前に必要 |
| 未決（advisory） | SEC-REQ-004：NOQ-09／FOQ-02／DOQ-04／OQ-PJ-002 | 期限は FR-060 の設計と移行リハーサルの前（変更なし） |
| ASSUMPTION | リスク受容の判断者を EC事業責任者（取締役）とした | 各未決事項の担当欄と業務要件 STK-05（本書の承認者）に基づく。別の受容者を定める場合は各行を更新する |
| ASSUMPTION | 期限「設計（Architecture）着手前」 | 入力に日付の根拠がないため工程上の時点で記載（日付は担当が設定）。セキュリティ再監査の推奨と BOQ-08 の既存記載に基づく |

### 9.3 検証（本cycle）

- `python .github/skills/requirements/scripts/validate_requirements_structure.py`：PASS（exit 0）
- `python .github/skills/traceability-audit/scripts/trace_check.py --scope REQUIREMENTS --no-write`：C01 0件。C11 1件（`reports/traceability/trace-map.json` が正本から再生成した内容と不一致。差し戻し先 TRACEABILITY_REGENERATE。要件書の改版に伴う派生成果物の再生成待ちで、Requirements Agent は生成しない）
- 追加照合：FR 26件・`expected-fr.txt` 26件の一致、要件ID・AC ID の追加・削除なし、数値（目標値）の変更なし

## 10. 修正cycle 3（REQUIREMENTS Scope Security 最終修正、2026-11-19）

- 入力: `reports/security-review/security-review-report.json`（修正cycle2後の再監査。残件 SEC-REQ-001 HIGH、SEC-REQ-002 MEDIUM、SEC-REQ-003 MEDIUM。いずれも EC事業責任者の決定またはリスク受容の記録が必要）、SDLC Orchestrator の依頼（共通ループ 修正cycle=3/3）。過去 Run のブランチ・reports は参照していない。
- 最終確認の範囲と結果: `docs/requirements/` 全文（分割10文書・UC-001〜UC-013・`expected-fr.txt`）と本ブランチで格納済みの資料（commit「要件定義書の格納」の24ファイル、`.github/project-context/project-ai-steering.md`）を、BOQ-08・FOQ-03・NOQ-08・NOQ-10 の各ID、および「受容」「承認済」「決定済」「模擬決済」「アカウントロック」「ログイン試行」等の語で検索した。判断者（EC事業責任者）による決定、リスク受容の記録（受容者・根拠・条件）、代替統制（送信元単位のリクエスト数の制限、管理者アカウントの無効化・パスワード変更の運用手順等）を定めた記載は見つからなかった（各行の「受容の記録：なし（2026-11-19 時点で未受容）」のみ）。`docs/ai-sdlc/` はフレームワーク文書で本PJの業務判断を含まない。決定・受容は捏造していない。
- 方針: 3件を RECORDED_OPEN とし、各未決事項に cycle3 時点の状況（決定・受容の記録なし、入力資料に根拠なし）、設計・実装は現行の FR と対象外（Out of Scope）のとおり範囲を拡大せずに進めること、稼働開始の判定の未決事項（Blocking）として持ち越すことを明記した。既存ID、章構成、FR の範囲（`expected-fr.txt` 26件）、対象外 FR-OUT-01〜16、目標値・数値は変更していない。新規 ID はない。改訂履歴にはレビュー指摘ID を書いていない。

### 10.1 入力対応

| 入力Path・版・箇所 | 入力IDまたは要点 | 出力Path・章・ID | 処理 | 根拠・理由 |
| --- | --- | --- | --- | --- |
| `reports/security-review/security-review-report.json` SEC-REQ-001（HIGH） | 本番での模擬決済による支払済・出荷の扱い、支払画面の提供の受容可否。決定・受容の記録なし | business_requirements.md（1.4）11章 BOQ-08（正）、functional_requirements.md（1.4）12章 FOQ-03 | 未決（RECORDED_OPEN） | 入力資料に決定・受容・代替統制の根拠なし。cycle3 時点で記録なしであること、設計・実装は現行要件と対象外（FR-OUT-01）のとおり範囲拡大なしで進めること、稼働開始の判定の未決事項（Blocking）として持ち越すことを追記。FR-031・FR-043・SCR-008 の振る舞い、期限（設計着手前、遅くとも稼働開始の判定前）は不変 |
| 同 SEC-REQ-002（MEDIUM） | 総当たり・リスト型攻撃への対策なし、会員登録での登録有無の判別。受容の記録なし | non_functional_requirements.md（1.4）14章 NOQ-08、14章前文 | 未決（RECORDED_OPEN） | 入力資料に受容・代替策の根拠なし。cycle3 時点で記録なし、設計・実装は現行要件と対象外（FR-OUT-11）のとおり範囲拡大なし（代替策の要件は追加しない）、稼働開始の判定の未決事項（Blocking）として持ち越すことを追記。E-001-02・NFR-SC-12〜14 と期限は不変 |
| 同 SEC-REQ-003（MEDIUM） | 管理者アカウントの無効化・パスワード変更の手段なし。受容の記録なし | non_functional_requirements.md（1.4）14章 NOQ-10、14章前文 | 未決（RECORDED_OPEN） | 入力資料に受容・代替手段（運用手順を含む）の根拠なし。cycle3 時点で記録なし、設計・実装は現行要件と対象外（FR-OUT-09）のとおり範囲拡大なし（無効化・変更の機能は追加しない）、稼働開始の判定の未決事項（Blocking）として持ち越すことを追記。期限（失効・変更手段）に「設計着手前に決定できない場合も稼働開始（2027-04-01）の判定前に決定または受容を記録する」を追記（BOQ-08・FOQ-03 と同じ扱いに揃えた。設計着手前の期限は維持） |
| 同 SEC-REQ-004（LOW、advisory） | NOQ-09 | 変更なし | 未決（advisory、持ち越し） | 本cycleの依頼対象外。cycle2 の記載のまま |
| requirements_quality_checklist.md 3章 | 対象成果物の版 | 同（1.6）3章 | 再配置 | 業務要件1.4・機能要件1.4・非機能要件1.4 に更新。総合判定・人レビュー未実施は不変 |

### 10.2 不足・仮定・矛盾の分類（本cycle）

| 区分 | 内容 | 対応 |
| --- | --- | --- |
| 未決（BLOCKED、HIGH、稼働開始の判定へ持ち越し） | SEC-REQ-001：BOQ-08／FOQ-03 | EC事業責任者の決定またはリスク受容の記録。設計・実装は現行要件で進行可（範囲拡大なし）。記録がない限り稼働開始の判定の未充足事項 |
| 未決（BLOCKED、MEDIUM、稼働開始の判定へ持ち越し） | SEC-REQ-002：NOQ-08、SEC-REQ-003：NOQ-10 | 同上（NOQ-08 は遅くとも NFR-SC-29 の診断前） |
| 未決（advisory） | SEC-REQ-004：NOQ-09 | 変更なし |
| 確認事項（Orchestrator へ） | 設計着手前の期限に記録がないまま設計へ進むこと | 依頼に基づき各行へ「範囲拡大なしで進め、稼働開始の判定へ持ち越す」と記載。工程遷移の可否は Orchestrator・PJ Owner が判断する |

### 10.3 検証（本cycle）

- `python .github/skills/requirements/scripts/validate_requirements_structure.py`：PASS（exit 0）
- `python .github/skills/traceability-audit/scripts/trace_check.py --scope REQUIREMENTS --no-write`：exit 1。C01 0件。C11 1件（`reports/traceability/trace-map.json` が正本から再生成した内容と不一致。差し戻し先 TRACEABILITY_REGENERATE。要件書の改版に伴う派生成果物の再生成待ちで、Requirements Agent は生成しない）
- 追加照合：`expected-fr.txt` 未変更（26件）、要件ID・AC ID の追加・削除なし、目標値・数値の変更なし

## 11. 修正cycle 1・2（IMPLEMENTATION Scope Traceability C12 指摘対応、2026-11-19）

- 入力（cycle1）: `expected-fr.txt` に functional_requirements.md 2.3 の FR-OUT-01〜16 の対象外宣言がないとの C12 指摘（EXPECTED_FR_SCOPE_UNDECLARED 16件）。
- 対応（cycle1）: 2.3 の記載を出典として `EXCLUDE FR-OUT-nn: 理由` 形式の16行を `expected-fr.txt` 末尾に追加した。実装対象FR 26行、既存ID、Scope、数値は変更していない。
- 入力（cycle2）: `reports/failure-triage/failure-triage-report.md`（Issue UNRESOLVED-34471205dd0539bc、修正cycle=2/3）。C12 の FR-OUT 問題は trace_check.py の書式不整合（Framework側）で要件側では解消不能。ただし cycle1 で追加した `expected-fr.txt` 27〜43行の日本語が全て「?」(0x3F) に化けて保存されていた（非ASCIIバイト0、「?」868個）。本章（11章）も同様に化けていた。
- 対応（cycle2）: UTF-8 で保存した Python スクリプトから `encoding='utf-8'` で書き出し、`expected-fr.txt` の EXCLUDE FR-OUT-01〜16 の理由（2.3 の「対象外とする機能」「理由」「代替手段・担当」）とコメント行を書き直した。ファイル先頭に「FR-OUT-nn のEXCLUDE行は現行trace_check.pyのC12書式（FR-\d{3,}）では受理されない既知のツール不整合あり（UNRESOLVED-34471205dd0539bc、Framework保守へ申送り）」旨のコメントを1行追加した。本章も UTF-8 で書き直した（cycle1 の記録は残存する判読可能部分と Failure Triage 報告から復元）。実装対象FR 26行、要件ID、Scope、数値は変更していない。

| 入力Path・版・箇所 | 入力IDまたは要点 | 出力Path・章・ID | 処理 | 根拠・理由 |
| --- | --- | --- | --- | --- |
| functional_requirements.md 2.3（FR-OUT-01〜16） | 対象外機能の宣言 | docs/requirements/expected-fr.txt 29〜44行（EXCLUDE FR-OUT-01〜16） | 再配置 | 出典は2.3。cycle2 で文字化けを解消し、2.3 の記載をそのまま転記 |
| reports/failure-triage/failure-triage-report.md | expected-fr.txt 27〜43行の「?」化け（Artifact欠陥） | docs/requirements/expected-fr.txt、本章 | 修正 | UTF-8 で再書き出しし、非ASCII文字の存在と「?」連続・U+FFFD 0件を検証 |
| 同 Root Cause | trace_check.py C12 の EXCLUDE 書式 `FR-\d{3,}` が FR-OUT-nn を受理しない | expected-fr.txt 1行目コメント、本章 | 未決（Framework保守へ申送り） | 要件側で解消不能。ID改番・2.3 の削除は承認済みIDの変更になるため行わない |

### 11.1 検証（cycle1）

- `python .github/skills/requirements/scripts/validate_requirements_structure.py`：PASS（exit 0）
- `python .github/skills/traceability-audit/scripts/trace_check.py --scope IMPLEMENTATION --no-write`：exit 1。EXPECTED_FR_INVALID 16件（追加した EXCLUDE 行）と EXPECTED_FR_SCOPE_UNDECLARED 16件が残存。trace_check.py の EXCLUDE 書式（`EXCLUDE\s+(FR-\d{3,})\s*:`）が `FR-OUT-nn` を受理しないため。要件ID・Scope の変更では解消できない。

### 11.2 検証（cycle2）

- 文字化け検証（Python）: `expected-fr.txt` と本章について、非ASCII文字が存在すること、疑問符の連続（2個以上）と U+FFFD が0件であることを確認した。
- `python .github/skills/requirements/scripts/validate_requirements_structure.py`：結果は Orchestrator への返却に記載。
- 残存: C12 の FR-OUT-nn 不受理は Framework 側（trace_check.py C12 書式）の既知の不整合として UNRESOLVED-34471205dd0539bc で Framework 保守へ申送る。

### 11.3 修正cycle 3（最終、run_id=RUN-AOBA-EC-1118）：代替表現の実試行

- 方法: リポジトリ外の一時ディレクトリ（%TEMP%）へ `.git`・`.venv`・キャッシュを除きコピーし、各案を適用して `python .github/skills/traceability-audit/scripts/trace_check.py --repo-root <copy> --scope IMPLEMENTATION --no-write` を実行した（`--root` は未対応のため `--repo-root` を使用）。Validator・policy・trace_check.py は変更していない。C01 新規は V0（現行）の C01 27件（コピー上の既存分）との差分。
- 一時ディレクトリは試行後に削除した。

| 案 | 内容 | C12件数（内訳） | C01新規 | 採否 |
| --- | --- | --- | --- | --- |
| V0 | 現行（`EXCLUDE FR-OUT-nn: 理由` ×16） | 32（INVALID 16、SCOPE_UNDECLARED 16） | 0 | 基準 |
| V1 | EXCLUDE行なし | 16（SCOPE_UNDECLARED 16） | 0 | 未解消 |
| V2 | EXCLUDE行をコメント化（`# EXCLUDE …`） | 16（SCOPE_UNDECLARED 16） | 0 | 未解消 |
| V3 | 区切り空白変種（`EXCLUDE<TAB>FR-OUT-nn : 理由`） | 32（INVALID 16、SCOPE_UNDECLARED 16） | 0 | 未解消 |
| V4 | 理由なし（`EXCLUDE FR-OUT-nn`） | 32（INVALID 16、SCOPE_UNDECLARED 16） | 0 | 未解消 |
| V5 | 範囲表記1行（`EXCLUDE FR-OUT-01〜FR-OUT-16: …`） | 17（INVALID 1、SCOPE_UNDECLARED 16） | 0 | 未解消 |
| V6 | 裸ID行（`FR-OUT-nn`） | 32（INVALID 16、SCOPE_UNDECLARED 16） | 0 | 未解消 |
| V7 | ID区切り変種 `FR_OUT_nn` | 32（INVALID 16、SCOPE_UNDECLARED 16） | 0 | 採用不可（ID表記変更） |
| V8 | ID区切り変種 `FR-OUTnn` | 32（INVALID 16、SCOPE_UNDECLARED 16） | 0 | 採用不可（ID表記変更） |
| V9 | ID区切り変種 `FR‐OUT‐nn`（U+2010） | 32（INVALID 16、SCOPE_UNDECLARED 16） | 0 | 採用不可（ID表記変更） |
| V10 | 数値別名 `EXCLUDE FR-9nn: FR-OUT-nn …` | 32（UNDEFINED 16、SCOPE_UNDECLARED 16） | 0 | 採用不可（新ID採番） |
| T1 | 2.3表に先頭No.列を追加（FR-OUTを定義扱いにしない）＋EXCLUDE行なし | 0 | 130（INVALID_REQUIREMENT_REFERENCE 128、ARCHITECTURE_GATE_INVALID 1、ADDR_HANDOFF_INVALID 1） | 採用不可（ID定義消失・正本構造変更） |
| T2 | 2.3表ID列をリンク表記＋EXCLUDE行なし | 0 | 130（同上） | 採用不可（ID定義消失） |
| T3 | 2.3表ID列をエスケープ（`FR\-OUT\-nn`）＋EXCLUDE行なし | 0 | 114（INVALID_REQUIREMENT_REFERENCE 112、ARCHITECTURE_GATE_INVALID 1、ADDR_HANDOFF_INVALID 1） | 採用不可（ID定義消失・表記変更） |
| T4 | T1＋EXCLUDE行あり | 16（INVALID 16） | 130（同上） | 採用不可（ID定義消失） |

- 結論: ID変更なし・意味不変で C12 を解消する表現は存在しない。C12 が0件になるのは FR-OUT-nn を要件ID定義として扱わない案（T1〜T3）のみで、承認済みIDの定義消失と C01 の大量新規発生を伴うため採用しない。`expected-fr.txt` と `functional_requirements.md` の実ファイルは本cycleで変更していない。
- 残存: UNRESOLVED-34471205dd0539bc（trace_check.py C12 の EXCLUDE 書式 `FR-\d{3,}` と policy `ids.min_digits: 2`・区分付きID `FR-OUT-nn` の不整合）は Framework 保守へ申送る。
