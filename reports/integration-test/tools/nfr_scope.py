"""NFR の結合試験での検証可否の一覧（RUN-AOBA-EC-1118）。

python reports/integration-test/tools/nfr_scope.py

- 一覧の対象は、TEST_ERROR 修正 cycle=1/3（Scope Assurance）の時点で Traceability C10 が要件→テスト未到達とした NFR 92件。
  以後のケース追加でテストに到達した NFR も、検証範囲・結果とともに一覧に残す（行を削除しない）。
- 結合試験で自動検証したもの（VERIFIED_IT）、一部だけ検証したもの（PARTIAL_IT：未検証部分と検証すべき工程を併記）、
  要件が「該当なし」と定め、その根拠の前提（機能・処理・接続が無いこと）だけを結合試験で確かめたもの
  （NOT_APPLICABLE_PREMISE_IT）、結合試験では検証できないもの（NOT_VERIFIED：理由・検証すべき工程）、
  要件が「該当なし」で前提も確かめられないもの（NOT_APPLICABLE）に分ける。
- 推測で合格扱いにしない。PARTIAL_IT・NOT_APPLICABLE_PREMISE_IT・NOT_VERIFIED・NOT_APPLICABLE は品質上の PASS ではない。
- 結果（PASS/FAIL）は integration-test-evidence.json の case_results から転記する（本スクリプトは期待値を持たない）。
- 件数は3種を区別して記録する（QR-FULL-1118-001）：一覧の件数（92）、差し戻し時点の FULL 監査の C10 の NFR 件数
  （traceability-report.json の C10）、本対応後にテスト・計画の要件 ID から到達しない NFR 件数（trace 注釈と計画から算出）。
"""

import json
import re
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
ROOT = HERE.parents[2]

PERF = "性能試験（負荷・耐久。ENV-01 にピーク負荷・3年後データ量を与える）"
COMPAT = "互換性・操作性テスト（対応ブラウザ・PC での画面操作。受入試験）"
OPS = "運用時の測定・運用テスト（本番環境 ENV-02 の構築時・稼働後）"
REVIEW = "構成・設定レビュー（Quality／Security Review、本番基盤の選定・構築時）"
MIGRATION = "移行（移行計画・本番相当データでの移行リハーサル・本番投入）"
VULN = "脆弱性診断（Security Review、稼働開始前の動的診断・依存ライブラリ照合）"
STATIC = "静的解析・コードレビュー（Implementation／Quality Review）"

V, P, N, NA = "VERIFIED_IT", "PARTIAL_IT", "NOT_VERIFIED", "NOT_APPLICABLE"
NAP = "NOT_APPLICABLE_PREMISE_IT"
STATUSES = (V, P, NAP, N, NA)
NA_PREMISE = "要件は「該当なし」。結合試験は根拠の前提だけを確認し、要件の合否は判定しない"

# (ID, 区分, 結合試験ケース, 結合試験で確認した内容, 未検証の内容・理由, 検証すべき工程)
SCOPE = [
    ("NFR-AV-01", P, ["GF-044"], "代替確認（計画停止以外にサービス停止を要する定期処理が無い）のうち、リポジトリの起動定義（compose の app・db、Dockerfile）・依存・管理コマンドに定期処理の定義が無いこと", "毎日終日の提供（月次の提供時間の集計）と本番環境の構成の確認", f"{OPS}／{REVIEW}"),
    ("NFR-AV-02", N, [], "", "稼働率99.0%は本番環境の監視記録（MON-01）から算出する", OPS),
    ("NFR-AV-03", N, [], "", "計画停止の実績・事前周知は運用手順と運用記録で確認する", f"{OPS}／{REVIEW}"),
    ("NFR-AV-04", P, ["GF-072"], "3年後相当のデータで、利用者の要求の処理中（全件成功）に全データ（監査ログを含む）のバックアップを取得できる（PostgreSQL 標準の論理バックアップ pg_dump による参考確認）", "本番のバックアップ方式・毎日 3:00 の取得・7世代保持（NOQ-01、DIF-03）と MON-07 での毎日の確認", f"{OPS}／{REVIEW}"),
    ("NFR-AV-05", N, [], "", "障害検知から再開までの時間は本番の障害対応記録・復旧手順書で確認する", f"{OPS}／{REVIEW}"),
    ("NFR-AV-07", P, ["GF-072"], "全データの喪失後にバックアップから復元すると取得時点のデータに戻る（取得前の注文あり・取得後の注文なし、件数が取得の前後の間）", "本番環境でのリストアと復元されたデータの最終更新日時の確認、日次バックアップの設定", f"{OPS}／{REVIEW}"),
    ("NFR-AV-08", P, ["GF-072"], "復元後に障害前の全業務（来訪者の閲覧・会員登録、購入者のログイン・カート・クーポン・注文確定・支払・照会・キャンセル、管理者の在庫確認・注文照会・出荷登録・配達完了登録・キャンセル、運用者の初期データ一括投入）を再開できる（使い捨て DB での参考確認）", "ENV-02 での復旧後の操作確認と、復旧手順書に全機能の確認手順が含まれることの構成・設定レビュー", f"{OPS}／{REVIEW}"),
    ("NFR-AV-09", NA, [], "", "要件が「要否：否」（拠点・地域単位の障害時の再開は不要）", "該当なし"),
    ("NFR-AV-10", NAP, ["GF-049"], "根拠の前提：決済サービスは本システム内の模擬機能で外部連携先を持たない（接続先・認証情報の設定・連携ライブラリなし。外部通信0件は GF-015）", NA_PREMISE, "該当なし"),
    ("NFR-AV-11", N, [], "", "バックアップの保管場所は本番基盤の設定", f"{OPS}／{REVIEW}"),
    ("NFR-AV-12", P, ["GF-072"], "3年後相当のデータの全データを pg_restore で復元しサービスを再開できる。リストア所要時間を参考計測（recovery-reference.json）", "本番環境（ENV-02）でのリストアの所要時間（4時間以内）とリストア手順書のレビュー", f"{OPS}／{REVIEW}"),
    ("NFR-EN-01", P, ["GF-035"], "結合試験の実行環境が Python 3.12、Dockerfile のベースイメージが python:3.12", "本番環境で使う版の確認", REVIEW),
    ("NFR-EN-02", P, ["GF-035"], "接続先の試験用 DB が PostgreSQL 16（server_version 16.x）", "本番環境のデータベースの版の確認", REVIEW),
    ("NFR-EN-03", P, ["GF-050"], "Docker Compose の定義が app・db の2サービス（db の正常性確認後に app を起動）で、依存に本番基盤に固有の SDK を含まない", "コンテナ実行環境での実際の起動（運用テスト：NFR-OM-05 の方法）と、本番基盤に固有の機能に依存しないことの構成・設定レビュー", f"{OPS}（ENV-01 の運用テスト）／{REVIEW}"),
    ("NFR-EN-06", N, [], "", "本番のサーバー・DB・バックアップ・ログの所在地は本番基盤の選定・構築で確認する", REVIEW),
    ("NFR-EN-07", P, ["GF-051"], "Production Code が OS に固有のモジュール・絶対パスを使わず、OS はダイジェスト固定のベースイメージ（python:3.12-slim）だけで決まる。結合試験は Windows のホスト上でアプリケーションを実行（コンテナは Linux）", "AP サーバー（Gunicorn）は POSIX 環境（コンテナ）での動作が前提。特定のサーバー OS に固有の設定・機能に依存しないことの構成・設定レビュー", REVIEW),
    ("NFR-EN-08", P, ["GF-050"], "リポジトリの起動定義（Dockerfile の CMD・compose の起動コマンド）が Gunicorn で runserver を含まず、gunicorn.conf.py の WSGI アプリケーションが商品一覧画面を返す", "本番環境で用いる Web サーバー・AP サーバーの確認（本番基盤 NOQ-01）", REVIEW),
    ("NFR-EN-09", P, ["GF-035"], "Django 5.2・DRF 3.15 以上、フロントエンドのビルド構成なし・静的スクリプトはモジュール読込なし", "本番イメージの版・構成の確認", REVIEW),
    ("NFR-EN-10", P, ["GF-052"], "採用製品の版が Django 5.2 LTS（2028-04）・Python 3.12（2028-10）・PostgreSQL 16（2028-11）で、依存の一覧（dependency-inventory.md）に期限と固定版を記録", "稼働開始前のサポート期限の確認と更新計画への記載（NOQ-07）", REVIEW),
    ("NFR-EN-11", P, ["GF-054"], "リポジトリの規約設定 ruff.toml（E・W・F・I・B・UP・N・BLE）で全ソースコードの違反0件", "ruff.toml の line-length=120 は PEP 8 の行長（79、合意時 99 まで）と異なり、規則の選択が PEP 8 準拠として十分かは静的解析・コードレビューの事項", STATIC),
    ("NFR-EN-12", P, ["GF-053"], "固定した全依存（app/requirements.txt・requirements-dev.txt）のライセンスがパッケージのメタデータから特定でき、AGPL・ライセンス不明0件", "社外へ配布しないサーバー上での利用で利用条件を満たせるかの判断（LGPL-3.0 の psycopg 等）", STATIC),
    ("NFR-EN-13", NA, [], "", "要件が「該当なし」", "該当なし"),
    ("NFR-LG-01", P, ["GF-065"], "安全管理措置のうち、個人情報（メールアドレス・氏名・配送先）・パスワードをログに出力せず、ファイルとして出力する要求先・応答が無く、外部へ送信せず、注文の参照が本人と管理者に限られる", "利用目的の特定・表示（本システム外）、本番の通信の暗号化、検証環境で本番データを使わない運用、個人情報保護法への適合の判断（関連要件のテスト結果とレビュー）", f"{REVIEW}／{VULN}"),
    ("NFR-LG-02", P, ["GF-036"], "商品一覧・商品詳細・カート・注文詳細で税込価格を主表示し税抜を併記、カート・注文手続き・注文完了・注文詳細に消費税額と税込合計", "対応ブラウザでの全画面の表示確認", COMPAT),
    ("NFR-LG-03", P, ["GF-058"], "注文明細・配送先・決済記録・注文状態履歴が登録後に変わらず（決済記録・履歴は追記のみ）、注文の更新は状態・日時・配送伝票番号だけ（支払の否認・承認、出荷登録、配達完了登録、管理者キャンセル）", "注文日から7年の保存と、保存期間経過データの削除手順が7年以内のデータを削除しない条件であること（構成・設定レビュー）、バックアップの対象", f"{REVIEW}／{OPS}"),
    ("NFR-LG-04", NAP, ["GF-047"], "根拠の前提：本システムに特定商取引法に基づく表記の画面・要求先・表示が無い（FR-OUT-16）", "本システムの対象外（静的ページはサイト運営側）。結合試験は前提だけを確認し、要件の合否は判定しない", "該当なし（本システム外）"),
    ("NFR-LG-06", P, ["GF-016", "IT-040", "IT-039", "IT-022"], "同時確定で在庫が0未満にならず引当合計が在庫以下（10並列×10回）、画面と API で同じ判定（IT-022）", "負荷・耐久試験の条件での確認", PERF),
    ("NFR-LG-07", P, ["GF-066"], "全画面・全 API の簡易な動的診断で、VUL-01（区分ごとのアクセス制御）・VUL-04/05（攻撃文字列で 5xx・無害化されない反映なし）・VUL-06（CSRF トークンなしの更新要求の拒否、参照用の要求で更新しない）・VUL-12（外部へ要求する部品なし）・VUL-13（内部情報の露出なし）の一部を確認", "VUL-01〜VUL-13 の全項目の充足（脆弱性診断ツールによる診断とセキュリティテスト）。VUL-02/03/08/09/10/11 の診断", VULN),
    ("NFR-LG-08", P, ["GF-031"], "全画面の HTML の機械判定可能な達成基準（言語・ページタイトル・ラベル・表見出し・代替テキスト・キーボード操作可能な部品）", "適合レベル A のチェックリストによる全達成基準の確認", COMPAT),
    ("NFR-LG-09", V, ["GF-037"], "都道府県は 01〜47 だけを受け付け名称で表示、画面の選択肢は47件", "", ""),
    ("NFR-LG-10", NAP, ["GF-049"], "根拠の前提：実在の決済サービス・外部サービスと接続しない（模擬機能のみ、接続先・認証情報の設定・連携ライブラリなし。外部通信0件は NFR-EN-05 の GF-015）", NA_PREMISE, "該当なし"),
    ("NFR-MG-01", P, ["GF-024"], "定義ファイルに注文等のデータを含める指定は受け付けず、投入後の注文・カート・決済記録・状態履歴は0件", "本番で投入する定義ファイルの内容確認", MIGRATION),
    ("NFR-MG-02", P, ["GF-024"], "VDC-04 と同じ件数構成の架空の定義ファイルで件数照合・業務キーの内容照合の不一致0", "本番の定義ファイルでの照合", MIGRATION),
    ("NFR-MG-03", P, ["GF-024"], "初期データ一括投入で管理者7名を登録し全員ログイン可", "本番の管理者アカウントでの確認", MIGRATION),
    ("NFR-MG-04", P, ["GF-024"], "--reset 指定の1回の実行で一括登録", "本番環境での当該指定の使用可否（NOQ-09）と本番手順での実施", MIGRATION),
    ("NFR-MG-05", P, ["GF-071"], "初期データ一括投入が投入時点の在庫数量（定義ファイルの値）をそのまま反映し、更新後の在庫管理表の値で再投入（--reset）すると置き換わる（2027-03-29・03-31 の日時で実行）", "移行計画に実施日・実施者・在庫数量の確定時刻が記載されていることのレビュー", MIGRATION),
    ("NFR-MG-06", NA, [], "", "要件が「該当なし」", "該当なし"),
    ("NFR-MG-07", P, ["GF-025"], "違反を含む定義ファイルで失敗（無投入・無削除）後、修正版を同じ指定で再実行して1時間以内に登録をやり直せる", "本番相当データ量・本番手順での切戻し時間の計測", MIGRATION),
    ("NFR-MG-08", P, ["GF-024"], "本番と同じ件数構成の架空の定義ファイルでのリハーサル（結合試験の環境）", "ENV-01 での正式な移行リハーサルの実施記録", MIGRATION),
    ("NFR-OM-02", P, ["GF-068"], "LOG-01〜03・05・06 が標準出力へ1行1件の JSON（日本時間・ミリ秒の日時、ログの種類、要求の識別子）で出力され、ファイル・ローテーションのハンドラーが無く、アプリケーションがログを削除しない（ログ基盤で期間検索できる形式）", "ENV-02 のログ基盤での90日保管と期間内の検索（稼働後90日経過時点の確認）、ログの保管期間の設定のレビュー", f"{OPS}／{REVIEW}"),
    ("NFR-OM-03", P, ["GF-069"], "監査ログは DB に発生日時（タイムゾーン付き）とともに追記のみで記録され、更新・削除は拒否され、利用者への外部キーを持たず、初期データ一括投入（--reset）を含む本システムのどの処理も削除しない", "ENV-02 での1年保管と、運用手順書の削除手順が1年以内の監査ログを削除しない条件であることのレビュー", f"{OPS}／{REVIEW}"),
    ("NFR-OM-04", V, ["GF-024", "IT-052"], "注文作成後の環境で --reset を1回実行し、注文・カート0件、定義どおりの件数、実行前の監査ログが残り1件増加", "", ""),
    ("NFR-OM-05", P, ["GF-050"], "compose の定義で app は db の正常性確認後に migrate→collectstatic→Gunicorn を1つの起動コマンドで行い（docker compose up の1回の操作で全構成要素が起動する定義）、Gunicorn の WSGI アプリケーションが商品一覧画面を返す", "全構成要素を停止した状態から起動操作を1回行い商品一覧画面が表示されることの運用テスト（イメージ構築を伴う）", f"{OPS}（ENV-01 の運用テスト）"),
    ("NFR-OM-08", N, [], "", "有人運用時間は運用体制", f"{OPS}／{REVIEW}"),
    ("NFR-OM-09", N, [], "", "監視の実装は本番環境の監視設定", OPS),
    ("NFR-OM-10", N, [], "", "通知までの時間は本番の監視・通知設定", OPS),
    ("NFR-OM-11", P, ["GF-026", "GF-014", "IT-056"], "LOG-01〜LOG-07 が定めた内容で出力・記録される（ENV-01 相当）", "保管期間（90日・1年・7年）", OPS),
    ("NFR-OM-13", P, ["GF-025", "IT-053"], "初期データ一括投入の違反時の無投入・全件通知と、修正後の再実行で重複しない", "バックアップの異常終了時の通知（MON-07）と手動再実行", OPS),
    ("NFR-OM-14", N, [], "", "セキュリティパッチの適用期間は運用記録", f"{OPS}／{REVIEW}"),
    ("NFR-OM-15", P, ["GF-073"], "3年後相当のデータで、データ構造の変更（catalog 0002）を含む更新と起動確認、更新直前のバックアップからの切戻し（データ構造・件数が更新前に戻る）を行い、所要時間を参考計測", "プログラム（イメージ）の入替えを含む ENV-01（compose）での更新・起動と切戻し手順の実施（運用テスト）", f"{OPS}（ENV-01 の運用テスト）"),
    ("NFR-OM-16", N, [], "", "問い合わせの一次回答時間は運用体制", OPS),
    ("NFR-OM-17", P, ["GF-027"], "環境変数だけで接続先・許可ホスト・環境プロファイル・開発用機能を変更でき、本番では開発用機能・デバッグを有効にできない、記入例に秘密情報の値なし", "環境ごとに異なる設定値の全項目の網羅性", REVIEW),
    ("NFR-OM-19", P, ["GF-057"], "README の開発・検証環境向けの手順書に設定の作成・構築・起動・停止・DB の初期化・初期データ一括投入・自動テスト・静的解析の手順があり、参照先が存在し、初期データ一括投入の手順（seed/initial_data.json、--reset）が成功", "手順どおりの ENV-01 の構築・起動（compose）の確認と、本番運用手順書（本番基盤の選定後）の記載項目の確認", REVIEW),
    ("NFR-PF-01", P, ["GF-022"], "照会系9種の応答時間の95パーセンタイルを単一利用者・小データ量で参考計測（各100要求、エラー0件）", "ピーク負荷（同時155利用者）・3年後データ量・ENV-01 での判定（API 種別により1,000要求以上）", PERF),
    ("NFR-PF-02", P, ["GF-022"], "更新系11種の応答時間の95パーセンタイルを単一利用者・小データ量で参考計測（各100要求以上、エラー0件）", "ピーク負荷・3年後データ量・ENV-01 での判定", PERF),
    ("NFR-PF-03", P, ["GF-060", "GF-062"], "全画面（14画面）を Edge・Chrome（Windows 11、ヘッドレス、キャッシュ無効）で各30回表示し、画面要求の開始から load イベント終了までの95パーセンタイルが単一利用者で 2.0秒以内（GF-060）。同時155仮想利用者の負荷中に Edge で購入者の4画面を表示し 2.0秒以内（GF-062）", "ピーク負荷（同時155利用者）・3年後データ量・ENV-01 での全画面の判定（性能テスト）", PERF),
    ("NFR-PF-04", P, ["GF-062"], "同時155仮想利用者の負荷中に、注文確定を 4件/分の一定間隔（要求ごとに異なる購入者、3明細・5点）で5分間到着させ全件成功、応答時間の95パーセンタイルを記録", "60分間・240件以上の処理と 3年後データ量・ENV-01 での判定（性能テスト）", PERF),
    ("NFR-PF-05", P, ["GF-062"], "同時155仮想利用者（購入者・来訪者 150、管理者 5、思考時間 5〜15秒、照会：更新＝8：2＋認証系）の負荷を5分間かけ、システムエラー0件・全要求成功・照会 1.0秒・更新 2.0秒・認証 2.0秒以内（95パーセンタイル）", "3年後データ量・ENV-01（compose・Gunicorn）での判定（性能テスト）", PERF),
    ("NFR-PF-06", P, ["GF-061"], "3年後相当のデータ量（VDC-01〜VDC-03 の件数）で、照会系 API 9種・更新系 4種・画面 7種の95パーセンタイルが単一利用者で目標値以内", "ピーク負荷（同時155利用者）・ENV-01 での判定とブラウザの表示完了時間（性能テスト）", PERF),
    ("NFR-PF-07", V, ["GF-016"], "在庫数量5の同一在庫単位を1個ずつカートに入れた10名の同時確定を10回、全回で成功5・在庫不足5・在庫0以上・引当合計5以下（使い捨て PostgreSQL 16、試験クライアント経由）", "", ""),
    ("NFR-PF-08", P, ["GF-023"], "分割表示の一覧の先頭・最終ページの件数が50件以下、商品分類一覧は分割しない", "3年後データ量での確認と商品分類45件以下（データ量に依存）", f"{PERF}／{OPS}"),
    ("NFR-PF-09", P, ["GF-022"], "認証系4種の応答時間の95パーセンタイルを単一利用者・小データ量で参考計測（各100要求、エラー0件）", "ピーク負荷・会員10,000件・ENV-01 での判定", PERF),
    ("NFR-PF-10", P, ["GF-024"], "1,157件（VDC-04 の件数構成）の --reset 投入が60秒以内（結合試験の環境）", "ENV-01 での移行リハーサルでの計測", MIGRATION),
    ("NFR-PF-11", P, ["GF-063"], "想定の2倍（310仮想利用者）で在庫不足が起きる負荷を2分間かけ、システムエラーとなる応答の割合 1%以下、在庫数量0未満 0件、金額整合を満たさない注文 0件、在庫の増減と注文明細が一致", "10分間・3年後データ量・ENV-01 での判定（負荷テスト・耐久テスト）", PERF),
    ("NFR-PF-12", NAP, ["GF-044"], "根拠の前提：定期的に実行するバッチ処理を持たない（起動定義・依存・管理コマンドに定期処理なし）", NA_PREMISE, "該当なし"),
    ("NFR-PF-13", P, ["GF-072"], "バックアップ（pg_dump）の取得中も画面・API の要求（照会・カート・注文確定）が全件成功し、サービスを停止せずに取得できる（参考確認）", "定期ジョブが本番のバックアップだけであることと 3:00〜4:00 の実行・1時間以内の完了（MON-07）", f"{OPS}／{REVIEW}"),
    ("NFR-PF-14", P, ["GF-062"], "代替確認（性能テストで CPU・メモリ使用率を記録し参考値とする）のうち、同時155仮想利用者の負荷中のアプリケーション（試験プロセス）の CPU 時間・ワーキングセットと DB コンテナの CPU・メモリ使用率を10秒ごとに記録（参考値。判定しない）", "ピーク負荷・3年後データ量・ENV-02 での 30分平均 80%以下の判定（MON-02）", f"{OPS}／{PERF}"),
    ("NFR-PF-15", P, ["GF-062"], "5分間の連続負荷で、システムエラー0件と、最初と最後の60秒の95パーセンタイル・メモリ使用量の推移を記録（劣化率は参考値。判定しない）", "2時間の連続負荷・3年後データ量・ENV-01 での劣化率 20%以内の判定（負荷テスト・耐久テスト）", PERF),
    ("NFR-PF-16", P, ["GF-055"], "GUNICORN_WORKERS だけでプロセス数を変更でき、画面・API のログイン状態とカートが DB に保持され別プロセスから同じ Cookie・Bearer で参照できる", "処理能力の増強手順がプログラム変更を伴わないことの構成・設定レビュー（実行単位の追加を含む）と、2倍の業務量での性能目標の確認", f"{REVIEW}／{STATIC}／{PERF}"),
    ("NFR-PF-17", P, ["GF-038"], "決済ゲートウェイの実装だけを別実装に差し替えても注文・在庫・金額・状態遷移の処理が変更なしで動き、注文の業務処理は模擬機能を参照しない", "実決済サービスとの連携部分の差替え（後続フェーズ）と静的解析", STATIC),
    ("NFR-SC-11", P, ["GF-064"], "固定した全依存ライブラリ 23件（app/requirements.txt・requirements-dev.txt）を開発時に公開脆弱性情報（OSV）と照合し、照合対象が固定した版と一致、CVSS 7.0以上・重大度不明の既知の脆弱性 0件", "リリース前の全依存の再照合（TASK-021）とコンテナイメージの OS パッケージの照合、脆弱性診断としての確認", VULN),
    ("NFR-SC-12", P, ["GF-028", "IT-055"], "購入者・管理者のメールアドレス＋パスワードでの認証、失敗時の区別しない応答（API・画面）、来訪者は認証不要、初期データ一括投入は Web・API から実行できない", "運用者のサーバーへのログイン権限による判定", f"{OPS}／{REVIEW}"),
    ("NFR-SC-13", NAP, ["GF-046", "GF-047"], "根拠の前提：多要素認証を設けない（メールアドレス＋パスワードの1回の要求でログインが完了し、追加の認証要素の入力項目・応答項目・要求先なし）", "要件は「該当なし」（受容可否は NOQ-08）。結合試験は前提だけを確認し、要件の合否は判定しない", "該当なし"),
    ("NFR-SC-14", NAP, ["GF-046"], "根拠の前提：アカウントロック・ログイン試行回数制限なし（API・画面で各10回失敗した後も正しいパスワードでログイン可）、ログイン失敗は監査ログに1件ずつ記録", "要件は「該当なし」（FR-OUT-11）。結合試験は前提だけを確認し、要件の合否は判定しない", "該当なし"),
    ("NFR-SC-17", NAP, ["GF-047"], "根拠の前提：パスワードの変更・再設定の機能なし（画面・API の要求先なし、Django 付属の changepassword は何も変更せずエラー終了）", "要件は「該当なし」（FR-OUT-09）。結合試験は前提だけを確認し、要件の合否は判定しない", "該当なし"),
    ("NFR-SC-20", P, ["GF-067"], "保存データの所在がデータベースだけ（ファイル項目・ファイル型のセッション/キャッシュ・ファイル書込み・ログファイルなし）で、DB とバックアップの暗号化で全保存データが対象になる前提", "ENV-02 のデータベースの保存媒体・バックアップが判読できない設定（DIF-07）", f"{OPS}／{REVIEW}"),
    ("NFR-SC-21", P, ["GF-052"], "VUL-10（構成・設定レビュー）のうち依存・実行環境の版固定（ハッシュ・ダイジェスト）と試験環境・依存の一覧との一致。関連項目（VUL-01 認可、VUL-04/05/06 入力・XSS・CSRF、VUL-07 同時実行、VUL-13 内部情報）は既存の結合ケースで実施", "VUL-01〜VUL-13 の全項目の充足（脆弱性診断・セキュリティテスト）", VULN),
    ("NFR-SC-25", P, ["GF-056"], "リポジトリの初期データ（seed/initial_data.json）の利用者のメールアドレスが全件 example.com で他のドメインなし、試験用の利用者は example.test", "検証データの作成手順（12.2）のレビューと、ENV-01 へ本番データ・バックアップを持ち込まない運用の確認", REVIEW),
    ("NFR-SC-26", P, ["GF-070"], "利用者向けサービス（画面・API）は1つの待受け（bind 0.0.0.0:8000、EXPOSE 8000）だけで提供し、本番プロファイルでは全要求先（44件）で HTTPS 以外を拒否、管理サイト・デバッグ用の要求先・遠隔ログインのソフトウェアなし", "本番のネットワーク設定（外部から HTTPS の利用者向けサービスだけ、DB へ外部から到達不可、サーバーへのログインは社内ネットワークから）。compose.yaml（ENV-01）の公開範囲は既知の未解決 UNRESOLVED-6de5eec64599b907 の SEC-IMPL-002 の対象で本要件の根拠に用いない", f"{OPS}／{REVIEW}"),
    ("NFR-SC-27", NAP, ["GF-048"], "根拠の前提：アプリケーションで送信元単位のリクエスト数の制限を行わない（同一送信元の連続要求で 429 なし、制限の設定なし）", "要件は「該当なし」（本番基盤でのアクセス制限の要否は NOQ-06）。結合試験は前提だけを確認し、要件の合否は判定しない", "該当なし"),
    ("NFR-SC-28", NAP, ["GF-045"], "根拠の前提：画面・API にファイルをアップロードする機能が無い（ファイル項目・ファイル選択部品・FILES 参照なし、ファイル付き multipart の API 要求は 400 でデータ変更なし）", NA_PREMISE, "該当なし"),
    ("NFR-SC-29", P, ["GF-066"], "全画面・全 API（44件の URL パターン）へ攻撃文字列8種・区分ごとのアクセス・CSRF トークンなしの更新要求を送る簡易な動的診断で、システムエラー・無害化されない反映・内部情報の露出・セキュリティヘッダーの欠落が0件", "脆弱性診断ツール（動的診断）による全画面・全 API の診断、重大度 高以上の指摘の対処と再診断", VULN),
    ("NFR-US-01", P, ["GF-059"], "Microsoft Edge 157.0.4341.60・Google Chrome 158.0.8127.36（Windows 11 の PC、ヘッドレス）で全画面（14画面）を表示し、来訪者・購入者・管理者の代表操作（会員登録・ログイン・カート・クーポン・注文確定・支払・キャンセル・出荷登録・配達完了登録・ログアウト、確認ダイアログを含む）を行える。取得時点の最新安定版は Edge 157.0.4341.60（一致）・Chrome 159.0.8154.13（PC の Chrome は1版古い）", "最新版（取得時点で Chrome 159）での確認、通常のウィンドウ表示での全画面の全操作の網羅（互換性・操作性テスト）", COMPAT),
    ("NFR-US-02", P, ["GF-059"], "表示領域 1280×720・表示倍率 100% で、両ブラウザの全画面（14画面）の文書の幅が表示領域の幅以下（横スクロールなし）、表示領域外の要素なし", "通常のウィンドウ表示での横スクロールバーの有無と、要素の重なり・欠けの目視確認（互換性・操作性テスト）", COMPAT),
    ("NFR-US-03", P, ["GF-029"], "氏名・配送先の JIS 第3・第4水準の漢字（𠮟・𩸽）が登録・画面・API で同じ文字、画面は lang=ja・UTF-8", "対応ブラウザでの字形の表示確認", COMPAT),
    ("NFR-US-04", P, ["GF-030", "GF-001", "GF-004"], "会員登録・注文手続きで誤りのある全項目の理由を項目名付きで1回で表示し入力値を保持（パスワード除く）", "対応ブラウザでの表示確認", COMPAT),
    ("NFR-US-05", P, ["GF-031"], "全画面の HTML の機械判定可能な達成基準", "適合レベル A のチェックリストによる全画面の確認", COMPAT),
    ("NFR-US-06", P, ["GF-059"], "Windows 11（ビルド 26300）の PC で NFR-US-01 の確認（GF-059）を行った", "受入環境の Windows 11 の PC での互換性・操作性テスト（通常のウィンドウ表示）", COMPAT),
    ("NFR-US-07", P, ["GF-031"], "全操作がネイティブのリンク・フォーム部品で構成され、正の tabindex・インラインのイベント処理がない", "キーボードだけでの会員登録〜支払・管理者のログイン〜出荷登録の実操作", COMPAT),
    ("NFR-US-08", V, ["GF-032"], "商品一覧→商品詳細→カート→注文手続き→注文完了→支払→注文詳細の7画面を画面のリンク・フォームだけで遷移", "", ""),
    ("NFR-US-09", P, ["GF-033"], "取消できない5操作のフォームに確認文言（data-confirm）があり、確認の補助（承諾しない場合は送信を取り消す）が全画面で読み込まれる", "ブラウザでの確認ダイアログの操作と承諾しない場合のデータ変更0件", COMPAT),
    ("NFR-US-10", V, ["GF-039", "GF-040", "GF-041", "GF-042", "GF-043", "GF-034", "IT-050", "GF-002", "GF-003"],
     "処理が完了するまでの間の繰り返し操作：先着が送信トークンのロックを保持して業務処理中に、同じトークンの後着を別接続から送り、"
     "後着がロック待ちに入ったことを確認（GF-039〜GF-043）。支払（承認・否認）で決済要求1回・決済記録1件、先着が E-031-08・結果の記録前の"
     "中断で終わる間も決済要求1回、注文確定で注文1件・在庫減算1回分（後着はカートが空）、カートに入れるで加算1回分、ログイン（先着 E-002-02）で"
     "失敗の監査ログ1件・ログイン状態なし。処理の完了後の操作は新たな操作（否認・システムエラー後の新しい支払画面からの支払：GF-034・GF-040）。"
     "先着の応答後の逐次再送（使用済みトークン）は GF-034・IT-050・GF-002・GF-003",
     "", ""),
]

FR_OUT = [f"FR-OUT-{i:02d}" for i in range(1, 17)]

# UNRESOLVED-e1d9dfe900863622 修正 cycle=1/3 の再評価（FULL C10 の NFR 60件）で、リポジトリ内の成果物・実行環境から確かめられる観点が
# 見つからず NOT_VERIFIED・NOT_APPLICABLE を維持したものの再評価の記録（要件の測定条件・検証方法を読み直した結果）
REEVALUATION = {
    "NFR-AV-02": "稼働率は ENV-02 の MON-01 の記録から算出。代替確認の復旧手順書はリポジトリに無い",
    "NFR-AV-03": "計画停止の実績と運用手順書（停止時間帯・周知手順）はリポジトリに無い",
    "NFR-AV-04": "ENV-01 はバックアップの仕組みを設けない（DIF-03）。バックアップの取得設定はリポジトリに無い",
    "NFR-AV-05": "RTO は ENV-02 の障害対応記録。復旧手順書はリポジトリに無い",
    "NFR-AV-07": "RPO は ENV-02 でのリストア。日次バックアップの設定・リストア手順はリポジトリに無い",
    "NFR-AV-08": "復旧後の全機能の確認は ENV-02。復旧手順書はリポジトリに無い（結合試験スイートは確認手順の一部として利用可能）",
    "NFR-AV-09": "要件が「要否：否」で、根拠（災害時は電話・FAX 受注で代替）にリポジトリで確かめられる前提が無い",
    "NFR-AV-11": "保管先は本番基盤（NOQ-01）の設定。リポジトリに無い",
    "NFR-AV-12": "リストア所要時間は ENV-02 での実施。手順書はリポジトリに無い",
    "NFR-EN-06": "所在地は本番基盤の選定・構築時の確認。リポジトリに無い",
    "NFR-EN-13": "要件が「該当なし」で、根拠（本番基盤が未選定で機器の制約が無い）にリポジトリで確かめられる前提が無い",
    "NFR-LG-01": "法令適合の判断。関連要件（NFR-SC-03/06/24 等）は既存の結合ケースで検証済みだが、本要件 ID を trace しない",
    "NFR-LG-07": "確認方法が脆弱性診断とセキュリティテストの結果（VUL-01〜VUL-13 の充足判定）で、結合試験で判定しない",
    "NFR-MG-05": "移行計画（実施日・実施者・在庫数量の確定時刻）はリポジトリに無い",
    "NFR-MG-06": "要件が「該当なし」で、根拠（新規システムで停止する稼働中のサービスが無い）にリポジトリで確かめられる前提が無い",
    "NFR-OM-02": "リポジトリのログ設定は標準出力への JSON 出力だけで、保管期間（90日）の設定は本番のログ基盤の事項（DIF-06）",
    "NFR-OM-03": "監査ログは DB に追記のみで記録され --reset でも削除されない（GF-024・NFR-SC-23 の既存ケース）が、1年保管と削除手順は運用の事項",
    "NFR-OM-08": "有人運用時間は運用体制・運用手順書の事項",
    "NFR-OM-09": "監視は ENV-02 の設定（ENV-01 は監視の対象外）",
    "NFR-OM-10": "通知時間は ENV-02 の監視・通知設定",
    "NFR-OM-14": "パッチ適用の期間は運用記録。運用手順書はリポジトリに無い",
    "NFR-OM-15": "更新・切戻しの所要時間は 3年後データ量での運用テスト（切戻し手順の実施を含む）",
    "NFR-OM-16": "一次回答時間は運用体制の事項",
    "NFR-PF-03": "画面の表示完了時間はブラウザでの資源読込完了までの計測とピーク負荷が必要",
    "NFR-PF-04": "240件/時の60分間の処理能力はピーク負荷での性能試験",
    "NFR-PF-05": "同時155利用者の負荷は性能試験",
    "NFR-PF-06": "3年後データ量での性能は性能試験",
    "NFR-PF-11": "同時310利用者の超過負荷での整合は負荷試験（同時実行の整合は NFR-PF-07 の GF-016 で別途検証）",
    "NFR-PF-13": "バックアップの実行時間帯は ENV-02 の運用（MON-07）",
    "NFR-PF-14": "ピーク時の CPU・メモリ使用率は ENV-02 の監視・性能試験の参考値",
    "NFR-PF-15": "2時間の連続負荷は耐久試験",
    "NFR-SC-11": "公開脆弱性情報との照合が必要（外部情報源）。依存の一覧に Implementation 工程の照合記録はあるが結合試験では照合しない",
    "NFR-SC-20": "保存データ・バックアップの暗号化は ENV-02 の設定（ENV-01 は対象外：DIF-07）",
    "NFR-SC-26": "外部から到達できる範囲は本番のネットワーク設定。compose（ENV-01）の公開範囲は既知の未解決 SEC-IMPL-002 の対象で、本要件の検証に用いない",
    "NFR-SC-29": "脆弱性診断ツールによる動的診断が必要",
    "NFR-US-01": "対応ブラウザ（Chrome・Edge 最新版）での全画面の全操作の確認が必要",
    "NFR-US-02": "ブラウザの表示領域 1280×720 での横スクロール・表示崩れの確認が必要",
    "NFR-US-06": "Windows 11 の PC のブラウザでの確認が必要",
}


# UNRESOLVED-e1d9dfe900863622 修正 cycle=2/3 の再評価（cycle=1/3 の後の FULL C10 の NFR 38件のうち、検証できる観点が
# 見つからず NOT_VERIFIED・NOT_APPLICABLE を維持したもの。PARTIAL_IT にしたものは SCOPE の確認内容を参照）
REEVALUATION_C2 = {
    "NFR-AV-02": "cycle=2/3：稼働率は ENV-02 の MON-01 の記録で、代替確認の復旧手順書（NFR-AV-04・05）はリポジトリに無い。GF-072 は NFR-AV-04/07/08/12 の一部で、稼働率・手順書の整備は確かめられない",
    "NFR-AV-03": "cycle=2/3：計画停止の実績・運用手順書（停止時間帯・周知手順）・周知の静的ページ（本システム外）はリポジトリに無く、機械確認できる対象が無い",
    "NFR-AV-05": "cycle=2/3：RTO は障害の検知から再開までの時間で、障害対応記録と復旧手順書の所要時間見積りが必要。GF-072 のリストア時間は NFR-AV-12 の参考値で、検知・切り分け・基盤の復旧を含まない",
    "NFR-AV-09": "cycle=2/3：要件が「要否：否」（拠点・地域単位の障害時の再開は不要）。根拠（電話・FAX 受注で代替）にリポジトリで確かめられる前提が無い",
    "NFR-AV-11": "cycle=2/3：保管先（DB と同時に失われない場所）は本番基盤（NOQ-01）の設定で、ENV-01 はバックアップの仕組みを設けない（DIF-03）",
    "NFR-EN-06": "cycle=2/3：所在地（日本国内）は本番基盤の選定・構築時の確認（DIF-07）。開発環境の PC の所在は本番の所在の根拠にならない",
    "NFR-EN-13": "cycle=2/3：要件が「該当なし」。根拠（本番基盤が未選定で機器の制約が無い）にリポジトリで確かめられる前提が無い",
    "NFR-MG-06": "cycle=2/3：要件が「該当なし」。根拠（新規システムで停止する稼働中のサービスが無い）は業務上の事実で、リポジトリで確かめられる前提が無い",
    "NFR-OM-08": "cycle=2/3：有人運用時間・連絡先は運用体制と運用手順書の事項（DIF-05）。リポジトリに無い",
    "NFR-OM-09": "cycle=2/3：監視（MON-01〜MON-10）の設定は ENV-02 の監視ツール（NOQ-02）で ENV-01 は監視の対象外（DIF-04）。アプリケーションの出力（LOG-02・LOG-03）は NFR-OM-11・OM-02 の範囲で、監視項目の実装率は確かめられない",
    "NFR-OM-10": "cycle=2/3：検知から通知までの時間は ENV-02 の監視・通知設定（NOQ-02）で、通知手段が未決",
    "NFR-OM-14": "cycle=2/3：パッチの公開日と適用日の記録・運用手順書（確認頻度・適用手順）は運用の事項。GF-064 は現時点の既知の脆弱性の照合（NFR-SC-11）で、適用期間は確かめられない",
    "NFR-OM-16": "cycle=2/3：問い合わせの受付・一次回答の時間は運用体制（DIF-05）の事項",
}


def referenced_requirement_ids() -> set[str]:
    """テストの trace 注釈（app/tests）と結合試験計画の requirement_id に現れる要件 ID（Traceability C10 の到達判定の入力）。"""
    ids: set[str] = set()
    for path in sorted((ROOT / "app" / "tests").rglob("*.py")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.lstrip().startswith("# trace:"):
                ids.update(re.findall(r"\b(?:FR|NFR|SEC)-[A-Z0-9-]*\d+\b", line))
    plan_path = OUT / "integration-test-plan.json"
    if plan_path.exists():
        for case in json.loads(plan_path.read_text(encoding="utf-8")).get("cases", []):
            ids.update(re.findall(r"\b(?:FR|NFR|SEC)-[A-Z0-9-]*\d+\b", str(case.get("requirement_id", ""))))
    return ids


def main() -> None:
    now = datetime.now(UTC).isoformat(timespec="seconds")
    trace_path = ROOT / "reports/traceability/traceability-report.json"
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    c10 = sorted(
        re.match(r"(\S+) を", item["message"]).group(1)
        for item in trace.get("issues", [])
        if item.get("check") == "C10" and item.get("message", "").startswith("NFR-")
    )
    ids = [row[0] for row in SCOPE]
    if len(ids) != len(set(ids)):
        raise SystemExit("NFR の重複")
    unknown = sorted(set(c10) - set(ids))
    if unknown:
        raise SystemExit(f"C10 の NFR が一覧にない: {unknown}")
    referenced = referenced_requirement_ids()
    evidence_path = OUT / "integration-test-evidence.json"
    results = {}
    if evidence_path.exists():
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        results = {c["case_id"]: c["result"] for c in evidence.get("case_results", [])}
    items = []
    for nfr, status, cases, verified, unverified, phase in SCOPE:
        if (status in (N, NA)) != (nfr not in referenced):
            raise SystemExit(f"{nfr}: 区分 {status} とテスト・計画の trace の有無が一致しない")
        if status in (N, NA) and nfr in c10 and nfr not in REEVALUATION_C2:
            raise SystemExit(f"{nfr}: cycle=2/3 の再評価の記録がない")
        items.append(
            {
                "requirement_id": nfr,
                "status": status,
                "integration_cases": [{"case_id": c, "result": results.get(c, "NOT_RECORDED")} for c in cases],
                "verified_in_integration_test": verified or None,
                "not_verified": unverified or None,
                "reason": unverified or None,
                "verify_in": phase or None,
                "in_c10_at_trigger": nfr in c10,
                "reevaluation": REEVALUATION.get(nfr),
                "reevaluation_cycle2": REEVALUATION_C2.get(nfr),
                "test_traceability_reached": nfr in referenced,
                "counts_as_quality_pass": status == V and all(results.get(c) == "PASS" for c in cases),
            }
        )
    summary = {s: sum(1 for i in items if i["status"] == s) for s in STATUSES}
    trigger_items = [i for i in items if i["in_c10_at_trigger"]]
    trigger_summary = {s: sum(1 for i in trigger_items if i["status"] == s) for s in STATUSES}
    remaining = sorted(i["requirement_id"] for i in items if not i["test_traceability_reached"])
    counts = {
        "scope_list_count": len(items),
        "scope_list_basis": "TEST_ERROR 修正 cycle=1/3（Scope Assurance、it-exec-2 前）の時点で Traceability C10 が要件→テスト未到達とした NFR。"
        "以後テストに到達した NFR も検証範囲・結果とともに残す",
        "c10_nfr_count_at_trigger": len(c10),
        "c10_at_trigger_source": "reports/traceability/traceability-report.json（更新日時 "
        f"{datetime.fromtimestamp(trace_path.stat().st_mtime, UTC).isoformat(timespec='seconds')}）の C10。"
        "FULL 監査の差し戻し UNRESOLVED-e1d9dfe900863622 の対象",
        "c10_at_trigger_by_current_status": trigger_summary,
        "c10_nfr_count_cycle1_trigger": 60,
        "c10_cycle1_note": "修正 cycle=1/3 の差し戻し時点の C10 の NFR は 60件（cycle=1/3 後の FULL 監査で 38件）。本対応（cycle=2/3）の"
        "差し戻し時点は c10_nfr_count_at_trigger",
        "c10_nfr_remaining_after_this_change": len(remaining),
        "c10_remaining_source": "app/tests の trace 注釈と integration-test-plan.json の requirement_id から算出（Traceability C10 の到達判定と"
        "同じ入力）。確定値は trace_check.py --scope FULL の C10 で確認する",
        "c10_nfr_remaining_ids": remaining,
    }
    data = {
        "run_id": "RUN-AOBA-EC-1118",
        "generated_at": now,
        "basis": "一覧は Scope Assurance 時点の Traceability C10 の NFR 92件（items）。各 NFR の要件本文・測定条件・検証方法・根拠"
        "（docs/requirements/non_functional_requirements.md）で判定。FULL 監査の差し戻し時点の C10 の NFR は c10_nfr_count_at_trigger 件で、"
        "本対応で再評価した（counts を参照）",
        "policy": "PARTIAL_IT・NOT_APPLICABLE_PREMISE_IT・NOT_VERIFIED・NOT_APPLICABLE は品質上の PASS ではない。PARTIAL_IT はケースが要件 ID を"
        " trace するが、未検証部分を verify_in の工程で確認する。NOT_APPLICABLE_PREMISE_IT は要件が「該当なし」で、根拠の前提だけを"
        "結合試験で確かめた（要件の合否は判定しない）",
        "counts": counts,
        "c10_nfr_count": len(c10),
        "c10_nfr_count_note": "c10_nfr_count は差し戻し時点の FULL 監査の C10 の NFR 件数（counts.c10_nfr_count_at_trigger と同じ）。"
        "一覧（items）は 92件で、両者は別の件数（QR-FULL-1118-001）",
        "summary": summary,
        "summary_scope": f"一覧 {len(items)} 件の現在の区分",
        "items": items,
        "fr_out_of_scope": {
            "ids": FR_OUT,
            "status": NA,
            "reason": "対象外機能（FR-OUT）でテスト対象外。C10 の未到達は expected-fr.txt の EXCLUDE 書式と trace_check C12 の不整合"
            "（既知の未解決 UNRESOLVED-34471205dd0539bc、原因工程 IMPLEMENTATION→REQUIREMENTS）による",
        },
    }
    (OUT / "nfr-verification-scope.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def fmt(s):
        return " / ".join(f"{k} {v}" for k, v in s.items())

    lines = [
        "# NFR の結合試験での検証可否（RUN-AOBA-EC-1118）",
        "",
        f"- 生成: {now}",
        f"- 一覧の件数: {len(items)} 件（Scope Assurance 時点の Traceability C10 の NFR。以後テストに到達した NFR も残す）。"
        f"現在の区分: {fmt(summary)}",
        f"- FULL 監査の差し戻し時点（UNRESOLVED-e1d9dfe900863622）の C10 の NFR: {len(c10)} 件。本対応後の区分: {fmt(trigger_summary)}",
        f"- 本対応後にテスト・計画の要件 ID から到達しない NFR（C10 の見込み）: {len(remaining)} 件（確定値は trace_check.py --scope FULL）",
        "- PARTIAL_IT・NOT_APPLICABLE_PREMISE_IT・NOT_VERIFIED・NOT_APPLICABLE を合格扱いにしない。未検証部分は「検証すべき工程」で確認する",
        "- FR-OUT-01〜16 は対象外機能（NOT_APPLICABLE。C10 の未到達は既知の未解決 UNRESOLVED-34471205dd0539bc）",
        "",
        "| NFR | 区分 | 差し戻し時 C10 | 結合試験ケース（結果） | 結合試験で確認した内容 | 未検証の内容・理由 | 検証すべき工程 | 再評価（cycle=1/3） | 再評価（cycle=2/3） |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for item in items:
        cases = "、".join(f"{c['case_id']}（{c['result']}）" for c in item["integration_cases"]) or "－"
        lines.append(
            f"| {item['requirement_id']} | {item['status']} | {'○' if item['in_c10_at_trigger'] else '－'} | {cases} | "
            f"{item['verified_in_integration_test'] or '－'} | {item['not_verified'] or '－'} | {item['verify_in'] or '－'} | "
            f"{item['reevaluation'] or '－'} | {item['reevaluation_cycle2'] or '－'} |"
        )
    (OUT / "nfr-verification-scope.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"c10_at_trigger": len(c10), "remaining": len(remaining), "summary": summary,
                      "trigger_summary": trigger_summary}, ensure_ascii=False))


if __name__ == "__main__":
    main()
