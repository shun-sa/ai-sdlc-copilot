---
document_type: "ADDR（Architecture Decision & Design Record）"
system_name: "MiniCommerce"
addr_id: "ADDR-014"
title: "環境別設定値の管理・本番構成（Web/AP サーバー・HTTPS・開発用機能の無効化）と依存の版固定の方式"
design_type: "非機能"
target_id: "application"
status: "ACTIVE"
generated_by: "ADDR Agent（RUN-AOBA-EC-1118）"
generated_at: "2026-11-19T07:40:00Z"
source_revision: "958677fe4a672dc82902289cfd4b0da5cfac39e5+worktree(RUN-AOBA-EC-1118 requirements 2026-11-19)"
generation_id: "RUN-AOBA-EC-1118"
primary_decision: "同一のプログラム・コンテナイメージを環境変数だけで環境ごとに切り替え、本番プロファイルでは安全側の設定を起動時に強制し、Gunicorn＋WhiteNoise で起動し、依存はハッシュ付きの版固定とダイジェスト固定のイメージで再現する"
---

# ADDR：環境別設定値の管理・本番構成（Web/AP サーバー・HTTPS・開発用機能の無効化）と依存の版固定の方式

## 1. 対象範囲

| 項目 | 内容 |
|---|---|
| 対象ID・名称 | application：環境ごとの設定値と本番の起動構成、依存ライブラリ・実行環境の版固定（manifest 候補 environment-configuration） |
| 対象機能・業務 | 全機能の実行環境（ENV-01・本番環境）、開発用の機能（試験用状態：ADDR-011）の有効・無効 |
| 対象環境・リリース | 第1期。リポジトリに含める構成（compose.yaml、.env.example、Dockerfile、app/ の設定、依存の記録） |
| 対象外 | 本番基盤そのもの（HTTPS 終端・サーバー証明書・TLS 1.2 以上・ネットワーク・保存媒体の暗号化・監視：NOQ-01、NOQ-02、NOQ-04、NFR-SC-20、NFR-SC-26）、稼働後のパッチ適用（NFR-OM-14）、脆弱性確認ツールの選定（NCN-07） |

## 2. 関連要件・参照成果物

本ADDRの判断または設計差分に直接関係する成果物だけを記載する。
論理DB設計はArchitectureの正本をパス・版・Entity IDで参照し、Entity/属性/識別子/関連/制約の定義表やER図を本書へ複製しない。

| 区分 | 参照先 | 関係 |
|---|---|---|
| 要件 | NFR-OM-17、NFR-OM-05、NFR-OM-06、NFR-OM-19、NFR-SC-02、NFR-SC-07、NFR-SC-10、NFR-SC-11、NFR-SC-19、NFR-SC-21、NFR-EN-01、NFR-EN-02、NFR-EN-03、NFR-EN-05、NFR-EN-07、NFR-EN-08、NFR-EN-10、NFR-EN-12、NFR-PF-16（docs/requirements/non_functional_requirements.md 1.4） | 設定値をプログラム変更なしで環境ごとに変更・一覧と秘密情報なしの記入例（NFR-OM-17）、本番は HTTPS のみ（NFR-SC-02）、Web/AP サーバーは設計で選定し本番で開発用サーバーを使わない（NFR-EN-08）、VUL-08〜VUL-10・VUL-13（NFR-SC-21 の対策方針）、data_requirements.md 8.1 CLS-01〜CLS-04 の通信時の暗号化 |
| 受入条件 | N/A（構成・設定レビューで確認する非機能要件。UC の AC は全 AC の実行前提） | 該当なし |
| AIステアリング文書 | .github/project-context/project-ai-steering.md 1.3（3章 技術・版、4章 compose.yaml・.env.example・README.md、app の HTTP localhost:8000・db 5432、外部接続は取得時のみ、6.2 秘密情報は環境変数・.env をリポジトリに含めない） | 構成の前提 |
| システム構成図 | N/A（受領なし） | 該当なし |
| データモデル | N/A | 該当なし |
| 関連ADDR | ADDR-002（Cookie の Secure）、ADDR-008（AP サーバーの要求処理の上限は10秒の待機より長く）、ADDR-011（開発用機能フラグ・使い捨て試験用 DB）、ADDR-013（AP サーバーのアクセスログ無効化） | 依存 |
| 設計資料 | PLAN-001 docs/architecture/implementation-task-list.md：TASK-001、TASK-002、TASK-017、TASK-019、TASK-021 | 設定と起動構成（TASK-001）、デバッグ表示の無効（TASK-002）、開発用機能の無効化（TASK-017・TASK-019）、依存の最終確認（TASK-021）。ANALYSIS-001 ARCH-CI-012・ARCH-CI-017・ARCH-CI-022 の委譲先 |

## 3. 背景

### 3.1 判断が必要な理由

NFR-EN-08 は Web/AP サーバーを設計で選定するとし、環境ごとの設定値の管理方式、本番での開発用機能・デバッグ表示の無効化の保証方法、本番での HTTPS のみの送受信のアプリケーション側設定、依存ライブラリ・実行環境の取得元と版の固定・記録の方式は要件・Steering で指定されていない（ARCH-CI-012、ARCH-CI-017、ARCH-CI-022）。本番基盤が未決（NOQ-01）のため、リポジトリに含める構成の範囲で判断する。

### 3.2 判断時の制約

Python 3.12・Django 5.2 LTS・DRF・PostgreSQL 16・Docker Compose の app・db（Steering 3章）。秘密情報を環境変数で与えリポジトリに含めない（Steering 6.2、NFR-SC-07）。実行時に外部接続しない（NFR-EN-05）。AGPL・ライセンス不明の依存を使わない（NFR-EN-12）。特定のサーバー OS に依存しない（NFR-EN-07）。

## 4. 設計判断

### 4.1 判断基準

| ID | 判断基準 | 優先度 | 根拠ID |
|---|---|---|---|
| DC-001 | ENV-01 と本番で同じプログラムを使い、差を設定値だけで表すこと | 必須 | NFR-OM-17 |
| DC-002 | 本番で開発用機能・デバッグ表示が有効になる設定誤りを起動時に拒否できること | 必須 | NFR-SC-10、VUL-08、NFR-OM-06 |
| DC-003 | 本番で Django 付属の開発用サーバーを使わず、静的ファイルを外部 CDN なしで配信できること | 必須 | NFR-EN-08、NFR-EN-05 |
| DC-004 | 依存ライブラリ・実行環境の取得元と版を特定し、同じ構成を再現できること | 必須 | NFR-SC-21（VUL-10）、NFR-EN-10 |
| DC-005 | 構成の追加（実行単位の追加）だけで処理能力を増強できること | 必須 | NFR-PF-16 |
| DC-006 | 追加サービス・追加依存を最小にすること | 重視 | Steering 3章、NFR-EN-12、NFR-SC-11 |

### 4.2 検討した選択肢

| 選択肢ID | 選択肢 | 利点 | 欠点・リスク | 選定結果 | 根拠 |
|---|---|---|---|---|---|
| OPT-001 | 単一の設定モジュールが環境変数だけを読み（型変換と必須検査を自前で行う）、本番プロファイルで安全側の値を起動時に強制する。起動は Gunicorn、静的ファイルは WhiteNoise、依存は pip-tools のハッシュ付き版固定、イメージはダイジェスト固定 | 同じイメージで全環境を動かせる。設定誤りを起動時に検出できる。app・db の2サービスのままで本番用の AP サーバーを使える | Gunicorn・WhiteNoise・pip-tools（開発時のみ）の依存が増える | SELECTED | DC-001〜DC-006 |
| OPT-002 | 環境ごとの設定モジュール（開発用・本番用の Python ファイル）を切り替える | 環境ごとの差が読みやすい | 環境差がプログラムの差になり NFR-OM-17 の「プログラムを変更せず」と緊張する。本番用ファイルの誤りを起動時に検出しにくい | NOT_SELECTED | DC-001、DC-002 |
| OPT-003 | nginx 等の Web サーバーを別サービスとして前段に置き Gunicorn と組み合わせる | 静的配信・HTTPS 終端を Web サーバーで行える | Steering の Compose 構成（app・db）に3つ目のサービスを追加することになり、HTTPS 終端は本番基盤（NOQ-01）の決定事項 | NOT_SELECTED | DC-006 |
| OPT-004 | 依存を pip freeze の版指定のみで記録する | 追加ツール不要 | 取得物の同一性（ハッシュ）を確認できず、再現性の保証が弱い | NOT_SELECTED | DC-004 |

### 4.3 決定内容

OPT-001 を採用する。

1. 設定値：Django の設定は単一の設定モジュールで環境変数だけから読む。設定値の一覧（.env.example と README.md に同じ一覧）：MINICOMMERCE_ENV（必須・既定なし。development または production のいずれか。r2 改訂）、DJANGO_SECRET_KEY（必須・既定なし）、DJANGO_DEBUG（未設定時 false。設定時は小文字の true・false だけを受理：2。r3 改訂）、DJANGO_ALLOWED_HOSTS、DB_HOST・DB_PORT・DB_NAME・DB_USER・DB_PASSWORD（DB_USER・DB_PASSWORD は秘密情報として必須・既定なし。r2 で DB_USER を追加）、MINICOMMERCE_DEV_FEATURES（未設定時 false。受理する表記は DJANGO_DEBUG と同じ。ADDR-011。r3 改訂）、MINICOMMERCE_TRUSTED_PROXY_SSL_HEADER（HTTPS を終端する前段がある場合のヘッダー名と値）、GUNICORN_WORKERS（実行単位内のプロセス数）。.env.example には秘密情報（秘密鍵・DB 接続の利用者名・パスワード）の値を書かない（空欄）。compose.yaml の db サービスの利用者名・パスワードも同じ環境変数の参照とし、値・既定値を書かない（未設定なら起動を失敗させる参照形式）。.env はリポジトリに含めない。
2. 本番プロファイルの強制：起動時に MINICOMMERCE_ENV を検査し、未設定・空・development／production 以外の値（大文字違い・前後空白付きを含む）は設定エラーとして起動を拒否する（fail-closed。r2 追加）。真偽値の設定値（DJANGO_DEBUG・MINICOMMERCE_DEV_FEATURES）は、未設定のときだけ false とし、設定されている場合は小文字の true・false だけを受理する。それ以外の値（空、True・TRUE・1・yes・on、前後空白付き等）は環境を問わず設定エラーとして起動を拒否する（r3 追加。SR-ADDR-R2-001）。MINICOMMERCE_ENV=production のとき、解釈後の実効値（Django の DEBUG 設定と開発用機能の有効状態）のいずれかが true であること、秘密鍵・DB 接続の利用者名・DB パスワードの未設定を起動時の設定エラーとして起動を拒否する（本番の検査は環境変数の文字列ではなく解釈後の実効値に対して行う。r3 改訂）。本番では SESSION_COOKIE_SECURE・CSRF_COOKIE_SECURE を true、HSTS を有効にし、HTTPS でない要求は業務処理の前に拒否する（転送先への自動転送で業務データを受け付けない）。HTTPS の判定は前段の終端装置が付けるヘッダー（MINICOMMERCE_TRUSTED_PROXY_SSL_HEADER）で行う。HTTP を許容し開発用機能を有効にできるのは MINICOMMERCE_ENV=development を明示した場合（ENV-01）だけとする。
3. Web/AP サーバー：コンテナの起動コマンドは全環境で Gunicorn（WSGI、sync ワーカー）とし、Gunicorn のアクセスログは出力しない（ADDR-013）。要求処理の上限時間は支払の10秒の待機より十分長くする（30秒以上：ADDR-008）。静的ファイルは collectstatic で集めて WhiteNoise がアプリケーション内から配信する（外部 CDN を使わない）。Django 付属の開発用サーバー（runserver）は本番の起動構成に含めない（開発者が手元で使うことは妨げない）。
4. 増強：アプリケーションの実行単位は状態を持たない（ADDR-002、ADDR-012）。増強は GUNICORN_WORKERS の変更、または同じイメージの実行単位の追加だけで行う。
5. 使い捨て試験用 DB：DB 接続は DB_HOST 等の環境変数だけで切り替える。自動テストは同じ変数で指定した使い捨ての PostgreSQL 16 上に pytest-django が試験用データベースを作成・破棄する（ADDR-011）。
6. 依存の版固定：Python の直接依存を app/requirements.in に書き、pip-tools でハッシュ付きの app/requirements.txt を生成し、イメージ作成時は --require-hashes で取得する。ベースイメージ（Python 3.12・PostgreSQL 16）はタグとダイジェストで固定する。取得元は PyPI と Docker Hub の公式イメージに限る。
7. 依存の記録：docs/operations/dependency-inventory.md に、全依存（間接依存を含む）と実行環境の名称・版・取得元（ダイジェスト）・ライセンス・サポート期限・既知の重大な脆弱性（CVSS 7.0以上）の照合結果と照合日を記録する。AGPL・ライセンス不明のものを採用しない。

### 4.4 決定理由

OPT-001 は同一のイメージを環境変数で切り替えるため環境差がプログラムの差にならず（DC-001）、本番プロファイルで危険な組合せを起動時に拒否するため設定誤りで開発用機能・デバッグ表示が有効になることを防げる（DC-002）。真偽値を小文字の true・false に限り不正な表記で起動を拒否し、本番の検査を解釈後の実効値に対して行うため、表記の揺れ（True・1 等）で検査をすり抜けて有効になる経路がない（DC-002。r3 追加）。環境の指定自体を必須・既定なしとし未設定・不正値で起動しないことで、環境の指定漏れ・誤記で本番の保護が外れる fail-open を防ぐ（DC-002。r2 追加）。Gunicorn は本番運用向けの AP サーバーで、WhiteNoise と組み合わせると app・db の2サービスのまま静的ファイルを CDN なしで配信できる（DC-003、DC-006）。HTTPS 終端は本番基盤の決定事項のため、アプリケーション側は Secure Cookie・HSTS・非 HTTPS 要求の拒否に限る。ハッシュ付きの版固定とダイジェスト固定で取得物の同一性まで再現できる（DC-004）。実行単位が状態を持たないため構成の追加だけで増強できる（DC-005）。

## 5. 設計差分

要件定義、AIステアリング文書、システム構成図およびデータモデルから一意に導出できない事項だけを記載する。
データに関する重要判断は、判断で追加・確定した差分と拘束だけを記録する。モデル本文の更新はArchitectureへの変更要求として返す。

| ID | 要件・成果物参照先 | 条件・対象 | 追加・確定した内容 | 実装拘束 |
|---|---|---|---|---|
| DD-001 | NFR-OM-17、NFR-SC-07 | 設定値 | 4.3 の1の環境変数だけで設定し、一覧と秘密情報なしの記入例を .env.example・README.md に置く | MUST |
| DD-002 | NFR-SC-10、VUL-08、NFR-OM-06、NFR-SC-02 | 本番プロファイル・環境の指定 | MINICOMMERCE_ENV の未設定・空・development／production 以外の値を起動時に拒否する（fail-closed。r2 追加）。真偽値の設定値は未設定時 false、設定時は小文字の true・false だけを受理し、それ以外の表記を環境を問わず起動時に拒否する（r3 追加）。production では解釈後の実効値で DEBUG・開発用機能が true であること、秘密情報（秘密鍵・DB 接続の利用者名・パスワード）の未設定を起動時に拒否する | MUST |
| DD-003 | NFR-SC-02、NFR-SC-19 | 本番の通信 | Secure Cookie・HSTS を有効にし、HTTPS でない要求を業務処理の前に拒否する（ENV-01 は HTTP を許容） | MUST |
| DD-004 | NFR-EN-08 | 起動構成 | 全環境のコンテナ起動は Gunicorn。本番の起動構成に runserver を含めない | MUST |
| DD-005 | NFR-EN-05 | 静的ファイル | WhiteNoise でアプリケーションから配信し、外部 CDN を参照しない | MUST |
| DD-006 | NFR-PF-16 | 増強 | 実行単位に状態を持たせず、プロセス数・実行単位の追加だけで増強する | MUST |
| DD-007 | 依頼の前提（Disposable Test DB）、NFR-OM-06 | DB 接続 | 環境変数だけで接続先を切り替え、自動テストを使い捨ての PostgreSQL 16 で実行できるようにする | MUST |
| DD-008 | VUL-10、NFR-EN-10 | 依存の版固定 | pip-tools のハッシュ付き requirements.txt と --require-hashes、ダイジェスト固定のベースイメージを用いる | MUST |
| DD-009 | NFR-EN-12、NFR-SC-11、VUL-09 | 依存の記録 | docs/operations/dependency-inventory.md に版・取得元・ライセンス・サポート期限・脆弱性照合結果を記録する | MUST |
| DD-010 | NFR-SC-07 | 秘密情報 | 秘密鍵・DB 接続の利用者名・DB パスワードの値をソースコード・設定ファイル（compose.yaml を含む）・.env.example・履歴に含めない。既定値を設けない（r2 で DB 接続の利用者名を追加） | MUST_NOT |
| DD-011 | NFR-SC-10、VUL-08、NFR-OM-06 | 真偽値の解釈と本番の検査（r3 追加。SR-ADDR-R2-001） | 真偽値の設定値を緩い解釈（大文字小文字の無視、1・yes・on の受理、不正な表記の false 扱い・既定値への置換）で読まない。本番の禁止の検査を環境変数の文字列の比較で行わない（解釈後の実効値で行う） | MUST_NOT |

## 6. 種別固有差分

`design_type`に対応する節を1つだけ残し、その他の節は生成結果から削除する。要件等から一意に決まらない差分だけを記載し、該当する差分がない項目は `なし` とする。

### F. 非機能の場合

| 項目 | 設計差分 | 根拠・参照先 |
|---|---|---|
| 非機能区分 | 運用性／セキュリティ | NFR-OM-17、NFR-SC-02、NFR-EN-08、VUL-08〜VUL-10 |
| 達成方式 | 環境変数のみの単一設定モジュール＋本番プロファイルの起動時強制（真偽値の厳格な解釈と実効値での検査を含む）＋Gunicorn・WhiteNoise＋ハッシュ付き版固定・ダイジェスト固定 | DD-001〜DD-009、DD-011 |
| 実装・設定上の制約 | Gunicorn の要求処理の上限は30秒以上、アクセスログ無効。設定の読み込みは起動時だけ | DD-004、ADDR-008、ADDR-013 |
| 障害・上限超過時の振る舞い | 環境の指定・真偽値の設定値が未設定（環境の指定のみ）・不正な表記の場合、および本番プロファイルで禁止の組合せ・必須値の欠落がある場合は起動しない（設定エラーを出力して終了。development への暗黙の切替えをしない） | DD-002 |
| 検証方法 | 構成・設定レビュー（設定値一覧・記入例、本番プロファイルの強制、起動構成、Cookie・HSTS・非 HTTPS の拒否、増強手順、依存の記録からの再構築）、MINICOMMERCE_ENV の未設定・空・不正値（例 prod、Production）で起動しないこと、DJANGO_DEBUG・MINICOMMERCE_DEV_FEATURES の不正な表記（True、TRUE、1、yes、空、前後空白付き）で環境を問わず起動しないこと（r3 追加）、本番プロファイルで DEBUG・開発用機能を有効にすると起動しないこと、DB 接続の利用者名の欠落で起動しないことの自動テスト、リポジトリの秘密情報（DB 接続の利用者名を含む）検索 | NFR-OM-17、NFR-EN-08、NFR-SC-07、VUL-10 |

## 7. AI実装制約

当該ADDR固有の不変条件・禁止事項だけを記載する。一般的な実装規約はAIステアリング文書を参照する。

| ID | 種別 | 内容 | 根拠ID |
|---|---|---|---|
| INV-001 | 不変条件 | 設定値の既定は安全側（DEBUG false、開発用機能 false、環境の指定は既定なしで未設定・不正値は起動拒否）とし、有効化・development の選択は明示の設定値でだけ行う。真偽値の有効化は小文字の true だけで行い、不正な表記は起動拒否とする（r2 改訂、r3 改訂） | NFR-SC-10、NFR-OM-06、NFR-SC-02 |
| INV-002 | 禁止事項 | 環境の判定をホスト名・OS 固有の機能・ファイルの有無で行わない（MINICOMMERCE_ENV だけで行う） | NFR-EN-07、NFR-OM-17 |
| INV-003 | 禁止事項 | 実行時に外部インターネット・外部 CDN へ接続する設定・依存を含めない（取得時を除く） | NFR-EN-05 |

## 8. 仮定事項

設計を一意に確定できない場合に、AIが処理継続のために採用した仮定を記載する。外部契約、法令、認証情報、秘密情報など、推測してはならない事項は仮定しない。

| ID | 不足・曖昧な情報 | 採用した仮定 | 根拠 | リスク |
|---|---|---|---|---|
| ASM-001 | 本番の HTTPS 終端の位置（本番基盤 NOQ-01・NOQ-04 未決） | 本番では前段の終端装置が HTTPS を終端し、要求が HTTPS であったことを示すヘッダーを付けるものとする。基盤の決定時にヘッダー名・値を設定値で与え、終端装置を置かない構成となる場合は新 ADDR で判断する | NFR-SC-02、NFR-SC-19 | MEDIUM |

## 9. 後続工程への引継ぎ事項

設計判断または設計差分によって、後続工程で追加考慮が必要となる事項だけを記載する。

| 区分 | 引継ぎ事項 | 参照先 |
|---|---|---|
| 実装 | TASK-001 で設定モジュール（真偽値の厳格な解釈と実効値での本番の検査を含む）・本番プロファイルの強制・Dockerfile（Gunicorn・collectstatic）・compose.yaml・.env.example・依存の固定と記録を作る。TASK-021 はリリース前に dependency-inventory.md を全依存で更新し脆弱性を再照合する | DD-001〜DD-011 |
| テスト | MINICOMMERCE_ENV の未設定・空・不正値、DJANGO_DEBUG・MINICOMMERCE_DEV_FEATURES の不正な表記（環境を問わず）、本番プロファイルでの DEBUG・開発用機能の有効化、秘密情報（秘密鍵・DB 接続の利用者名・パスワード）の欠落が起動エラーになること、非 HTTPS 要求の拒否、Cookie の Secure・HttpOnly を自動テストで確認する。自動テストの設定は MINICOMMERCE_ENV=development を明示する | DD-002、DD-003、DD-010、DD-011 |
| 運用 | 本番基盤の決定時に、HTTPS 終端のヘッダー、ログの収集・90日保管、実行単位の追加手順を本番運用手順書に記載する | ASM-001、ADDR-013 |
