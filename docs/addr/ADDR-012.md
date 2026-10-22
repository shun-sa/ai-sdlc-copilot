---
document_type: "ADDR（Architecture Decision & Design Record）"
system_name: "MiniCommerce"
addr_id: "ADDR-012"
title: "自動テストの配置と ENV-01 におけるコマンド1回実行方式"
design_type: "非機能"
target_id: "TGT-002"
status: "ACTIVE"
generated_by: "ADDR Agent（ai-sdlc-copilot addr skill / workflow_version 2）"
generated_at: "2026-10-22T05:10:00Z"
source_revision: "2e9703ddd0c7bb5e71d270783a5efd5e016d2f4d+WORKTREE"
generation_id: "RUN-20261022-MC"
primary_decision: "結合テストの正本配置をリポジトリ直下 tests/integration/ に保ったまま、ENV-01 の app サービスへ読取り専用バインドマウントで与え、本番イメージにテストコードを含めずに `docker compose exec app pytest` 1回で単体・結合の全自動テストを実行する"
---

# ADDR：自動テストの配置と ENV-01 におけるコマンド1回実行方式

## 1. 対象範囲

| 項目 | 内容 |
|---|---|
| 対象ID・名称 | TGT-002：MiniCommerce アプリケーション実装計画と成果物整合性 |
| 対象機能・業務 | app の全自動テスト（単体テスト・結合テスト）の配置と実行方式。NFR-OM-06 の達成手段 |
| 対象環境・リリース | 初期リリース（第1期）。検証は開発・検証環境（ENV-01）。本番環境（ENV-02）では本ADDRのテスト用マウントを適用しない |
| 対象外 | 個々のテストケースの内容と網羅範囲、単体テストを HTTP 層なしで実行する方針（ADDR-004 DD-005 を維持）、性能試験・移行リハーサル・受入試験の実施計画、トレーサビリティ基準そのもの（Framework 側の成果物であり変更しない） |

## 2. 関連要件・参照成果物

本ADDRの判断または設計差分に直接関係する成果物だけを記載する。

| 区分 | 参照先 | 関係 |
|---|---|---|
| 要件 | NFR-OM-06, NFR-OM-05, NFR-OM-17, NFR-OM-19, NFR-EN-03, NFR-EN-05, NFR-EN-10, NFR-EN-12, NFR-SC-01, NFR-SC-11 | コマンド1回での全自動テスト実行、ENV-01 のサービス構成、本番イメージへ持ち込む依存・資産の管理、テストデータと資格情報の扱い |
| 受入条件 | NFR-OM-06 の検証方法（ENV-01 でコマンドを1回実行し、全テストが実行され失敗が0件であること）、NFR-OM-05 の検証方法（`docker compose up -d` 1回で app・db が起動すること） | 判断の成立可否を検証する条件 |
| AIステアリング文書 | .github/project-context/project-ai-steering.md 3章（技術スタック）、4章（リポジトリ構成・compose.yaml・サービスは app・db）、9章（起動コマンド） | 適用する共通方針 |
| システム構成図 | 該当なし（構成図は提供されていない）。Docker Compose の app（8000番）・db（5432番）を前提とする | 参照する構成情報 |
| データモデル | docs/requirements/data_requirements.md D-01〜D-15（テストは pytest-django が作成・破棄する使い捨てテストDB上の同一スキーマを用いる） | 参照するデータ情報 |
| 設計成果物 | PLAN-001 ／ docs/architecture/implementation-task-list.md（TASK-001, TASK-016） | 本判断が拘束する実装Task |
| 関連ADDR | ADDR-004（app 内部のモジュール構成。DD-005 の単体テスト配置を維持し変更しない）, ADDR-011（Web・APサーバーとコンテナ構成。DD-006・INV-002 のサービス追加禁止を維持する） | 依存／補足 |

## 3. 背景

### 3.1 判断が必要な理由

NFR-OM-06 は「単体・結合の自動テストを、コマンド1回（`docker compose exec app pytest`）で全件実行できること」を必須で求めるが、その達成手段（結合テストの配置先と、コンテナ内での収集方法）はどの入力でも一意に定まっていない。ADDR-004 DD-005 は services の単体テストを `shop/tests` に置くことだけを決めており、結合テストの配置・実行方法を決めていない。

実装・結合試験工程の結果、単体テストは `app/shop/tests/unit/` にあり本番イメージへ同梱されるため 742件がコンテナ内で実行できる一方、結合テストはリポジトリ直下 `tests/integration/` にあり、Dockerfile が `COPY app/` のみであるためコンテナ内に存在せず、`docker compose exec -T app pytest` では 742件（単体のみ）しか収集されない。結合テストをホストから実行している現状では、NFR-OM-06 の「コマンド1回で全件」が成立しない。

結合テストを単体と同じく `app/` 配下へ移す手段は採れない。トレーサビリティ基準（`.github/skills/traceability-audit/policy/traceability-policy.yaml`）の `integration_test.include` は `tests/integration/**/*.py` のみで、単体テストの `**/tests/unit/**` のようなサブディレクトリ指定を持たず、かつ本基準は Framework 側の成果物であり変更できない。したがって「テストコードの正本配置」と「コンテナ内での実行可能性」を両立させる方式を設計判断として確定する必要がある。

### 3.2 判断時の制約

- 結合テストのソースはリポジトリ直下 `tests/integration/**/*.py` に置かれていなければ、結合試験のトレーサビリティ（要件とテストの対応、未テスト要件の検出）が成立しない。基準ファイルは変更しない。
- NFR-OM-06 が検証に用いるコマンドは `docker compose exec app pytest`（コンテナ内実行）であり、ホスト上での実行は代替にならない。
- 自動テストは外部インターネットに接続せずに実行できること（NFR-OM-06）。
- Docker Compose のサービスは app・db の2つで、追加サービスを置かない（NFR-EN-03、ADDR-011 DD-006・INV-002）。
- 本番イメージへ導入する依存ライブラリは requirements.txt を正本として脆弱性確認（NFR-SC-11）・サポート期限確認（NFR-EN-10）・ライセンス確認（NFR-EN-12）の対象とする。計測専用依存は requirements-dev.txt に分離済み。
- 検証環境と本番環境で同じプログラム（同一イメージ）を使い、環境ごとに異なる値は環境変数で与える（NFR-OM-17）。
- 自動テストは本番DB・本番データ・本番資格情報を用いない（NFR-SC-01）。

## 4. 設計判断

### 4.1 判断基準

| ID | 判断基準 | 優先度 | 根拠ID |
|---|---|---|---|
| DC-001 | `docker compose exec app pytest` 1回で単体・結合の全自動テストが収集・実行され、失敗0件を確認できること | 必須 | NFR-OM-06 |
| DC-002 | 結合テストのソースがリポジトリ直下 tests/integration/ にあり、トレーサビリティ基準の対象範囲と一致すること | 必須 | NFR-OM-06, 3.2の制約 |
| DC-003 | 本番イメージにテストコードおよびテスト専用依存を含めず、脆弱性・サポート期限・ライセンスの確認対象資産を増やさないこと | 必須 | NFR-SC-11, NFR-EN-10, NFR-EN-12 |
| DC-004 | 外部インターネットへ接続せず、本番DB・本番資格情報を用いずに実行できること | 必須 | NFR-OM-06, NFR-SC-01 |
| DC-005 | compose のサービス構成（app・db の2つ）と、検証環境・本番環境で同一イメージを使う方針を崩さないこと | 重視 | NFR-EN-03, NFR-OM-17 |
| DC-006 | 同一のテストコードを複数個所へ複製せず、1か所で保守できること | 重視 | NFR-EN-05, NFR-OM-06 |

### 4.2 検討した選択肢

| 選択肢ID | 選択肢 | 利点 | 欠点・リスク | 選定結果 | 根拠 |
|---|---|---|---|---|---|
| OPT-001 | 結合テストを tests/integration/ に置いたまま、ENV-01 の app サービスへ読取り専用バインドマウント（./tests → /app/tests）で与え、pytest の testpaths に shop/tests と tests の両方を指定する | コマンド1回でコンテナ内から単体・結合の全件を収集・実行できる。正本配置がトレーサビリティ基準と一致する。本番イメージはテストコードを含まないまま変わらない。追加依存が不要（pytest・pytest-django は requirements.txt に既存）。テストコードの複製が発生しない | compose.yaml にマウント定義を追加する必要があり、ENV-01 では実行中コンテナからテストコードが見える。ホスト側ファイルに依存するためイメージ単体では結合テストを実行できない | SELECTED | DC-001, DC-002, DC-003, DC-004, DC-005, DC-006 |
| OPT-002 | Dockerfile でリポジトリ直下 tests/ とテスト設定を本番イメージへ COPY する | 追加のマウント設定なしでコマンド1回を満たせる。イメージ単体で全テストを実行できる | 本番イメージにテストコードとテスト用設定が常駐し、攻撃面と確認対象資産が増える（NFR-SC-11・NFR-EN-10・NFR-EN-12 の対象が本番に不要なコードへ広がる）。テスト変更のたびに本番イメージの再ビルドが必要になる | NOT_SELECTED | DC-003 |
| OPT-003 | 結合テスト専用のサービス（またはビルドステージ）を compose.yaml へ追加し、`docker compose run` で実行する | 本番イメージを汚さずテスト専用の依存を分離できる | NFR-OM-06 が指定する `docker compose exec app pytest` 1回にならず、単体と結合で別コマンドが必要になる。app・db 以外のサービス追加は ADDR-011 DD-006・INV-002 に反する | NOT_SELECTED | DC-001, DC-005 |
| OPT-004 | 結合テストを app/shop/tests/integration/ へ移し、単体テストと同じく本番イメージへ同梱する | 単体テストと同一の手段で解決でき、マウントが不要 | トレーサビリティ基準の integration_test.include（tests/integration/**）に一致せず、結合試験の要件対応・未テスト要件検出が成立しない。基準は Framework 側成果物であり変更できない。本番イメージに結合テストが常駐する | NOT_SELECTED | DC-002, DC-003 |
| OPT-005 | ホスト上で pytest を1回実行する方式を正とし、コンテナ内実行を行わない | 現状のまま追加変更が不要。実行が速い | NFR-OM-06 が検証に用いるコマンド（`docker compose exec app pytest`）と異なり、ホストへ Python 実行環境と依存の導入が必要になる。ENV-01 の前提（コンテナ内で実行する構成）を満たさず、要件が不成立のまま残る | NOT_SELECTED | DC-001 |

### 4.3 決定内容

- 自動テストの正本配置を次のとおり固定する。単体テストは `app/shop/tests/unit/`（ADDR-004 DD-005 を維持）、結合テストはリポジトリ直下 `tests/integration/`。同一のテストコードをリポジトリ内の別の場所へ複製しない。
- ENV-01 の compose.yaml の app サービスへ、リポジトリ直下 `./tests` を `/app/tests` へ読取り専用（`:ro`）、`./reports` を `/app/reports` へ読み書き可でバインドマウントする。app/ のアプリケーションソースをマウントで上書きしない。本決定のために app・db 以外のサービスやビルドステージを追加しない。
- app/pyproject.toml の `[tool.pytest.ini_options]` の `testpaths` を `["shop/tests", "tests"]` とする。これによりコンテナ内（rootdir=/app）でパス引数を与えずに単体・結合の双方が収集される。リポジトリ直下 pytest.ini（ホスト実行用）は本決定の対象外とし、コンテナ内へ持ち込まない。
- NFR-OM-06 の検証コマンドは `docker compose exec -T app pytest` の1回とし、テスト種別ごとの分割実行やパス引数の指定を前提にしない。ENV-01 での期待結果は、単体742件と結合65件の合計807件が収集され、失敗0件であること（件数は実装の増減に応じて更新されるが、単体と結合の双方が収集されることを満たす）。
- 本番イメージ（Dockerfile）はテストコードを含めない。`COPY app/` のみを維持し、リポジトリ直下 tests/ を .dockerignore の除外対象として明示する。テスト専用依存（coverage 等）は requirements-dev.txt に限定し、requirements.txt へ追加しない。pytest・pytest-django は NFR-OM-06 の達成に必要なため requirements.txt の既存定義をそのまま用い、依存一覧を増やさない。
- テスト実行時のDB接続は config/settings の環境変数のみで切り替える。コンテナ内実行では compose の既定値（DB_HOST=db、DB_PORT=5432）をそのまま用い、ホストから実行する場合に限り DB_HOST・DB_PORT を公開ポートの値で上書きする。使用するDBは pytest-django が作成・破棄する `test_<DB_NAME>` に限り、本番DB・本番データ・本番資格情報へ接続しない。
- 結合試験の実行証跡（reports/integration-test/ 配下）は `/app/reports` マウント経由でホストへ出力する。結合テストの conftest がリポジトリ基点を `tests/integration/conftest.py` の2階層上として解決する実装は、コンテナ内でも `/app` を指すためテストコードを変更しない。
- 本番環境（ENV-02）ではテスト用マウントを適用せず、同一イメージをそのまま用いる。ENV-01 の自動テスト実行手順と、本番ではマウントを適用しないことを運用手順書（README）に記載する。
- 今後 tests/ 配下へ追加する自動テストは、DBとアプリケーション内テストクライアントのみに依存し、外部インターネット・外部ブラウザ・外部サービスへ接続せずに同一コマンドで収集・実行できるものに限る。

### 4.4 決定理由

DC-001 と DC-002 は同時に満たす必要があり、「正本はリポジトリ直下 tests/integration/、コンテナ内には写しをマウントで与える」ことが両立する唯一の方式である（OPT-001）。OPT-004 は単体テストで有効だった手段だが、トレーサビリティ基準の対象範囲と一致せず結合試験の要件対応が追えなくなるため採れない。OPT-002 は要件を満たすものの、本番イメージへテストコードを常駐させ、脆弱性確認・サポート期限確認・ライセンス確認（NFR-SC-11・NFR-EN-10・NFR-EN-12）の対象資産を本番に不要なコードへ広げるため DC-003 に反する。OPT-003 は ADDR-011 で確定した app・db の2サービス構成を崩し、かつ NFR-OM-06 が指定する単一コマンドにならない。OPT-005 は要件の検証方法そのものを満たさない。

OPT-001 は追加依存を必要とせず（pytest・pytest-django は requirements.txt に既存）、本番イメージとその依存一覧を変更しないため、依存管理に関する既存の確認結果を無効化しない。マウントを読取り専用とすることで、実行中のコンテナからテストコードを書き換えられないようにし、本番環境ではマウント自体を適用しないことで、検証環境と本番環境で同一イメージを用いる方針（NFR-OM-17）を保つ。

## 5. 設計差分

要件定義、AIステアリング文書、システム構成図およびデータモデルから一意に導出できない事項だけを記載する。

| ID | 要件・成果物参照先 | 条件・対象 | 追加・確定した内容 | 実装拘束 |
|---|---|---|---|---|
| DD-001 | NFR-OM-06 ／ PLAN-001 TASK-001 | ENV-01 の app サービス | compose.yaml の app サービスへ `./tests:/app/tests:ro` と `./reports:/app/reports` のバインドマウントを定義する | MUST |
| DD-002 | NFR-OM-06 ／ TASK-001 | コンテナ内の pytest 設定 | app/pyproject.toml の testpaths を `["shop/tests", "tests"]` とし、`docker compose exec -T app pytest` をパス引数なしで実行したときに単体・結合の双方が収集されるようにする | MUST |
| DD-003 | NFR-SC-11, NFR-EN-10, NFR-EN-12 ／ TASK-001 | 本番イメージと依存一覧 | Dockerfile へテストコードの COPY を追加せず（`COPY app/` のみ）、リポジトリ直下 tests/ を .dockerignore の除外対象とする。テスト専用依存は requirements-dev.txt に限定し requirements.txt へ追加しない | MUST_NOT |
| DD-004 | NFR-OM-06, NFR-EN-05 ／ TASK-001 | 結合テストの配置 | 結合テストの正本配置を tests/integration/ のみとし、コンテナ内の配置はマウントによる写しとする。リポジトリ内に複製を作らない | MUST |
| DD-005 | NFR-OM-17, NFR-SC-01 ／ TASK-001 | テスト実行時のDB接続 | DB接続は config/settings の環境変数のみで切り替え、コンテナ内実行では compose 既定値（DB_HOST=db、DB_PORT=5432）を用いる。使用するDBは pytest-django が作成・破棄する `test_<DB_NAME>` に限る | MUST |
| DD-006 | NFR-EN-03 ／ TASK-001 | ENV-01 のサービス構成 | 自動テスト実行のために compose.yaml へ app・db 以外のサービスを追加せず、Dockerfile へテスト専用ビルドステージを追加しない | MUST_NOT |
| DD-007 | NFR-OM-19 ／ TASK-016 | 運用手順書 | README の手順に、ENV-01 での自動テスト実行が `docker compose exec -T app pytest` 1回であること、本番環境ではテスト用マウントを適用しないことを記載する | MUST |

## 6. 種別固有差分

design_type に対応する節だけを残している。要件等から一意に決まらない差分だけを記載し、該当する差分がない項目は なし とする。

### F. 非機能の場合

| 項目 | 設計差分 | 根拠・参照先 |
|---|---|---|
| 非機能区分 | 保守性（テスト容易性）および運用性 | NFR-OM-06, NFR-OM-19 |
| 達成方式 | ENV-01 限定の読取り専用バインドマウント（./tests → /app/tests）と、testpaths を shop/tests・tests の2系統とする pytest 設定による単一コマンド実行 | DD-001, DD-002 |
| 実装・設定上の制約 | 本番イメージへテストコード・テスト専用依存を含めない。app・db 以外のサービスを追加しない。DB接続は環境変数のみで切り替え、使い捨てテストDBだけを使う | DD-003, DD-005, DD-006 |
| 障害・上限超過時の振る舞い | テスト用マウントが与えられていない場合（本番イメージ単体での実行時）、pytest は結合テストを収集せず単体テストのみを実行する。ENV-01 ではマウントを前提とし、コマンド1回の実行結果で単体・結合の双方が収集されたことを確認する | DD-001, DD-002 |
| 検証方法 | 運用テスト（ENV-01 で `docker compose exec -T app pytest` を1回実行し、単体・結合の双方が収集されること、失敗0件であること、外部インターネットへ接続せずに完了することを確認する） | NFR-OM-06, DD-001, DD-002 |

## 7. AI実装制約

当該ADDR固有の不変条件・禁止事項だけを記載する。一般的な実装規約はAIステアリング文書を参照する。

| ID | 種別 | 内容 | 根拠ID |
|---|---|---|---|
| INV-001 | 禁止事項 | Dockerfile へテストコード（リポジトリ直下 tests/ 等）の COPY を追加しない | DD-003, DC-003 |
| INV-002 | 禁止事項 | 結合テストのソースを tests/integration/ 以外へ置かない。app/ 配下へ複製・移動しない | DD-004, DC-002 |
| INV-003 | 不変条件 | NFR-OM-06 の検証は `docker compose exec -T app pytest` の1回で行い、テスト種別ごとの分割実行やパス引数の指定を前提にしない | DD-002, DC-001 |
| INV-004 | 禁止事項 | テスト専用依存（coverage 等）を requirements.txt へ追加しない。追加する場合は requirements-dev.txt に限る | DD-003, NFR-SC-11 |
| INV-005 | 禁止事項 | テスト用マウントで app/ のアプリケーションソースを上書きしない。tests のマウントは読取り専用とする | DD-001, DC-005 |
| INV-006 | 禁止事項 | 自動テストから外部インターネット・本番DB・本番データ・本番資格情報へ接続しない | DD-005, NFR-SC-01 |
| INV-007 | 不変条件 | tests/ 配下へ追加する自動テストは、DBとアプリケーション内テストクライアントのみに依存し、同一コマンドで収集・実行できるものに限る | DD-002, DC-004 |

## 8. 仮定事項

設計を一意に確定できない場合に、AIが処理継続のために採用した仮定を記載する。外部契約、法令、認証情報、秘密情報など、推測してはならない事項は仮定しない。

本ADDRでは仮定を採用していない。配置先の制約（結合テストは tests/integration/）、実行コマンド（`docker compose exec app pytest`）、サービス構成（app・db）はいずれも要件・基準・既存ADDRで与えられており、それらを満たす実行方式のみを本ADDRで確定している。決定内容は ENV-01 で実行して成立を確認している。

| ID | 不足・曖昧な情報 | 採用した仮定 | 根拠 | リスク |
|---|---|---|---|---|

## 9. 後続工程への引継ぎ事項

設計判断または設計差分によって、後続工程で追加考慮が必要となる事項だけを記載する。

| 区分 | 引継ぎ事項 | 参照先 |
|---|---|---|
| 実装 | TASK-001 で compose.yaml のマウント定義・app/pyproject.toml の testpaths・.dockerignore を実装し、変更したファイルの先頭注釈（app/config/settings.py の DB 接続部分を含む）へ ADDR-012 を追加する。TASK-016 で README に実行手順と本番非適用を記載する | DD-001, DD-002, DD-003, DD-007 |
| テスト | 単体テストと結合テストを移動・複製せず、ENV-01 でコマンド1回の実行結果（収集件数と失敗0件）を NFR-OM-06 の証跡として記録する。結合試験の証跡は /app/reports マウント経由でホストの reports/integration-test/ へ出力する | NFR-OM-06, DD-001, DD-004 |
| 運用 | 本番環境ではテスト用マウントを適用せず同一イメージを用いる。イメージへ持ち込む依存の確認対象は requirements.txt のままとする | DD-003, DD-007, NFR-SC-11 |
