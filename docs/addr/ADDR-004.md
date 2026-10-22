---
document_type: "ADDR（Architecture Decision & Design Record）"
system_name: "MiniCommerce"
addr_id: "ADDR-004"
title: "app 内部のモジュール構成と画面・API の業務ロジック共有"
design_type: "非機能"
target_id: "TGT-002"
status: "ACTIVE"
generated_by: "ADDR Agent（ai-sdlc-copilot addr skill / workflow_version 2）"
generated_at: "2026-10-21T22:45:00Z"
source_revision: "2e9703ddd0c7bb5e71d270783a5efd5e016d2f4d+WORKTREE"
generation_id: "RUN-20261022-MC"
primary_decision: "app を単一 Django アプリの層別モジュール構成（models・services・api・web・common・payments）とし、画面とAPIが services 層の同一業務ロジックを呼び出す"
---

# ADDR：app 内部のモジュール構成と画面・API の業務ロジック共有

## 1. 対象範囲

| 項目 | 内容 |
|---|---|
| 対象ID・名称 | TGT-002：MiniCommerce アプリケーション実装計画と成果物整合性 |
| 対象機能・業務 | app 配下の全実装（FR-001〜FR-045, FR-060）。特に画面とAPIが共有する業務ルール（FR-026 ほか） |
| 対象環境・リリース | 初期リリース（第1期）。リポジトリの app/ 配下 |
| 対象外 | リポジトリ全体の配置（Steering 4章で確定）、Web・APサーバーの選定（ADDR-011）、個別機能のロジック内容 |

## 2. 関連要件・参照成果物

本ADDRの判断または設計差分に直接関係する成果物だけを記載する。

| 区分 | 参照先 | 関係 |
|---|---|---|
| 要件 | FR-026, NFR-EN-01, NFR-EN-09, NFR-EN-11, NFR-OM-06, NFR-OM-07, NFR-OM-17, NFR-OM-18, NFR-PF-17 | 業務ルールの重複実装防止、テスト容易性、設定分離、決済連携部分の分離 |
| 受入条件 | NFR-OM-06 の検証方法（コマンド1回で全自動テスト実行）、NFR-PF-17 の検証方法（決済連携部分が独立モジュールであること） | 判断の成立可否を検証する条件 |
| AIステアリング文書 | .github/project-context/project-ai-steering.md 4.1・4.2（app 内部の分割と Module 間アクセス規則は設計で決めると明記）、3章（技術スタック） | 設計へ委譲された範囲 |
| システム構成図 | 該当なし（構成図は提供されていない）。Steering 4章のディレクトリ構成を前提とする | 参照する構成情報 |
| データモデル | docs/requirements/data_requirements.md D-01〜D-15 | models 層が表現する永続データ |
| 受領仕様 | docs/specifications/api-contract.md 6.1（エンドポイントとロール） | api 層が実装する契約 |
| 設計成果物 | PLAN-001 ／ docs/architecture/implementation-task-list.md（TASK-001, TASK-015） | 本判断が拘束する実装Task（BLK-004） |
| 関連ADDR | ADDR-005（ログ基盤）, ADDR-007（共通エラー応答）, ADDR-009（決済模擬の境界）, ADDR-011（Web・APサーバー） | 本構成の上に配置する判断 |

## 3. 背景

### 3.1 判断が必要な理由

Project AI Steering 4.1・4.2 は「app 内部のモジュール分割」と「Module 間アクセス規則」を明示的に設計へ委譲している。構成を決めないと、画面（Django テンプレート）とAPI（DRF）の双方に同じ業務ルールが実装される危険があり、NFR-OM-06・NFR-OM-07・NFR-OM-18 の達成手段も定まらない。

### 3.2 判断時の制約

- API・画面・業務ロジック・テストは app 配下の単一 Django プロジェクトに置く（Steering 4.1、NFR-EN-01）。
- 業務ルール（数量上限・クーポン判定・金額計算・在庫引当・状態遷移）を画面側に重複実装しない（Steering 4.2）。
- 決済サービスとの連携部分を他の処理から分離する（NFR-PF-17）。
- 環境ごとに異なる設定は環境変数で与える（NFR-OM-17）。
- テストは pytest＋pytest-django でコマンド1回で全件実行できること（NFR-OM-06）。

## 4. 設計判断

### 4.1 判断基準

| ID | 判断基準 | 優先度 | 根拠ID |
|---|---|---|---|
| DC-001 | 画面とAPIが同一の業務ロジックを呼び出し、業務ルールが1か所にあること | 必須 | FR-026, Steering 4.2 |
| DC-002 | 決済連携部分を他の処理から分離できること | 必須 | NFR-PF-17 |
| DC-003 | 業務ロジックを HTTP 層から独立して単体テストできること | 必須 | NFR-OM-06 |
| DC-004 | 単一 Django プロジェクトの構成を保ち、マイグレーションの管理が複雑にならないこと | 重視 | NFR-EN-01, NFR-OM-07 |
| DC-005 | 設定・秘密情報を環境変数で与えられること | 必須 | NFR-OM-17, NFR-SC-07 |

### 4.2 検討した選択肢

| 選択肢ID | 選択肢 | 利点 | 欠点・リスク | 選定結果 | 根拠 |
|---|---|---|---|---|---|
| OPT-001 | 単一 Django アプリの中を層で分ける（models・services・api・web・common・payments）。画面とAPIは services を呼ぶ | 業務ルールが services に1か所化され、画面・APIから共有できる。models とマイグレーションが1つにまとまり管理が単純。services を HTTP 非依存で単体テストできる | 1アプリが大きくなるため、モジュール分割と依存規則の明文化が必要 | SELECTED | DC-001, DC-002, DC-003, DC-004 |
| OPT-002 | 業務ドメインごとに Django アプリを分割する（accounts・catalog・cart・orders・admin） | ドメイン境界が明確で、将来の分離がしやすい | 本リリースの16Taskの規模に対しアプリ間の相互参照とマイグレーションの分散が増え、同一業務ロジック共有の確認が難しくなる | NOT_SELECTED | DC-004 |
| OPT-003 | 層を設けず、Django 標準のアプリ構成（models・views・serializers）だけで実装する | 実装開始が速い | 画面ビューとAPIビューの双方に業務ルールが書かれやすく、Steering 4.2 の重複実装禁止を満たせない | NOT_SELECTED | DC-001, DC-003 |
| OPT-004 | リポジトリ抽象・依存性注入を伴うヘキサゴナル構成にする | フレームワーク非依存の業務ロジックを得られる | ORM の上に抽象層を重ねる保守コストが本リリースの規模に見合わず、NFR-OM-07（ruff 指摘0件・単純さ）に対する利点が小さい | NOT_SELECTED | DC-004 |

### 4.3 決定内容

- app 配下を次の構成とする。config（Django プロジェクト設定。settings・urls・wsgi）、shop（単一 Django アプリ）、manage.py、seed（初期データ定義ファイル）。
- shop の内部モジュールを次のとおりとする。models（永続データモデル。D-01〜D-15）、services（業務ロジック。金額計算・カート・注文確定・支払・状態遷移・認証・初期データ投入）、api（DRF のシリアライザ・ビュー・ルーティング）、web（画面ビュー・テンプレート・フォーム）、common（共通エラー・判定順序・ページング・ログ・要求ID）、payments（決済ゲートウェイのインターフェースと模擬実装）、management/commands（load_initial_data）、tests（pytest のテスト）。
- 依存規則（Module 間アクセス規則）を次のとおり固定する。api と web は services と common のみを呼ぶ。services は models・common・payments を呼ぶ。models は services・api・web を参照しない。common は models 以外の業務モジュールを参照しない。payments は models・services を参照しない。
- 業務ルール（数量上限・クーポン判定・金額計算・在庫引当・状態遷移・権限と所有の判定）は services にのみ実装し、api のシリアライザ・web のテンプレート・JavaScript に重複実装しない。
- api と web は同じ services 関数を呼び、表示整形（日時書式・金額書式・メッセージ配置）だけを各層で行う。
- 設定は config/settings に集約し、環境ごとに異なる値（DB 接続・秘密鍵・Cookie の Secure 属性・ログ出力レベル・ワーカー数）は環境変数から読む。
- テストは shop/tests 配下に test_*.py として置き、services の単体テストを HTTP 層を介さずに実行できるようにする。

### 4.4 決定理由

DC-001 を満たすには、画面・APIの双方から呼ばれる単一の業務ロジック層が必要であり、層別モジュール（OPT-001）が最小の構成でこれを実現する。ドメイン別アプリ分割（OPT-002）は将来の分離に有利だが、本リリースは単一デプロイ単位（app サービス1つ）であり、マイグレーション分散と相互参照の管理コストが先行する。標準構成のみ（OPT-003）は重複実装を構造的に防げず、Steering 4.2 の禁止事項に反しやすい。payments を独立モジュールとすることで NFR-PF-17 の「差替え時の変更範囲を連携部分に限定する」を構造として満たす（DC-002）。

## 5. 設計差分

要件定義、AIステアリング文書、システム構成図およびデータモデルから一意に導出できない事項だけを記載する。

| ID | 要件・成果物参照先 | 条件・対象 | 追加・確定した内容 | 実装拘束 |
|---|---|---|---|---|
| DD-001 | Steering 4.1 ／ docs/architecture/implementation-task-list.md TASK-001 | app 配下の構成 | config（設定）・shop（単一アプリ）・manage.py・seed の構成とし、shop を models・services・api・web・common・payments・management/commands・tests に分ける | MUST |
| DD-002 | Steering 4.2, FR-026 ／ TASK-001, TASK-015 | 業務ルールの配置 | 業務ルールは services にのみ実装し、api・web・テンプレートへ重複実装しない | MUST_NOT |
| DD-003 | Steering 4.2 ／ TASK-001 | Module 間アクセス規則 | api・web → services・common、services → models・common・payments の方向にのみ依存し、逆方向の参照を行わない | MUST |
| DD-004 | NFR-PF-17 ／ TASK-001, TASK-011 | 決済連携の分離 | 決済サービスとの連携は payments モジュールに限定し、services は IF-01 の項目だけを介して利用する | MUST |
| DD-005 | NFR-OM-06 ／ TASK-001 | テスト配置 | services の単体テストを HTTP 層を介さずに実行できるよう shop/tests に test_*.py を置く | MUST |
| DD-006 | NFR-OM-17, NFR-SC-07 ／ TASK-001 | 設定の分離 | 環境ごとに異なる値は config/settings から環境変数で読み、既定値に秘密情報を書かない | MUST |

## 6. 種別固有差分

design_type に対応する節だけを残している。要件等から一意に決まらない差分だけを記載し、該当する差分がない項目は なし とする。

### F. 非機能の場合

| 項目 | 設計差分 | 根拠・参照先 |
|---|---|---|
| 非機能区分 | 保守性（テスト容易性・設定変更の容易さ・障害調査の容易さ）および拡張性 | NFR-OM-06, NFR-OM-17, NFR-OM-18, NFR-PF-17 |
| 達成方式 | 単一 Django アプリ内の層別モジュール（models・services・api・web・common・payments）と一方向の依存規則 | DD-001, DD-003 |
| 実装・設定上の制約 | 業務ルールは services のみ。設定値は環境変数経由。決済連携は payments に限定 | DD-002, DD-004, DD-006 |
| 障害・上限超過時の振る舞い | なし（本判断は障害時の振る舞いを変更しない。異常時の応答は ADDR-007 による） | ADDR-007 |
| 検証方法 | 静的解析・コードレビュー（依存方向の違反0件、業務ルールの重複実装0件）、単体テスト（services を HTTP 層なしで実行）、コマンド1回の pytest 実行 | NFR-OM-06, NFR-OM-07, DD-003 |

## 7. AI実装制約

当該ADDR固有の不変条件・禁止事項だけを記載する。一般的な実装規約はAIステアリング文書を参照する。

| ID | 種別 | 内容 | 根拠ID |
|---|---|---|---|
| INV-001 | 不変条件 | 画面ビューとAPIビューは、同じ業務処理について同じ services 関数を呼び出す | DD-002, DC-001 |
| INV-002 | 禁止事項 | テンプレート・JavaScript・シリアライザに金額計算・在庫引当・状態遷移・クーポン判定を実装しない | Steering 4.2, DD-002 |
| INV-003 | 禁止事項 | models・common・payments から api・web・services を import しない | DD-003 |
| INV-004 | 禁止事項 | 要件に無いモジュール（外部連携・非同期処理・キャッシュ層）を追加しない | Steering 11章, NFR-EN-05 |
| INV-005 | 不変条件 | 新しい業務処理を追加する場合も services に置き、api・web は入出力の変換のみを行う | DD-002, DD-003 |

## 8. 仮定事項

設計を一意に確定できない場合に、AIが処理継続のために採用した仮定を記載する。外部契約、法令、認証情報、秘密情報など、推測してはならない事項は仮定しない。

本ADDRでは仮定を採用していない。配置先（app/・seed/）と禁止事項は Steering 4章・11章で与えられ、内部分割のみを本ADDRで確定している。

| ID | 不足・曖昧な情報 | 採用した仮定 | 根拠 | リスク |
|---|---|---|---|---|

## 9. 後続工程への引継ぎ事項

設計判断または設計差分によって、後続工程で追加考慮が必要となる事項だけを記載する。

| 区分 | 引継ぎ事項 | 参照先 |
|---|---|---|
| 実装 | TASK-001 で本構成の雛形を作成し、TASK-002 以降は該当モジュールにのみ変更を加える。TASK-015 の画面は services を呼び出す | DD-001, DD-002 |
| テスト | services の単体テストと、画面・APIが同一結果を返すことの結合テストを行う | NFR-OM-06, INV-001 |
| 運用 | 設定変更は環境変数で行い、コード変更を伴わないことを運用手順書に記載する | NFR-OM-17, DD-006 |
