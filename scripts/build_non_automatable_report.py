"""C10（テストされていない要件）のうち、自動テストで検証できない要件を整理して出力する。

入力（正本）
  - docs/requirements/non_functional_requirements.md（4〜12章の要件表。検証方法・確認方法の欄）
  - docs/requirements/functional_requirements.md 2.3（対象外機能）
  - reports/integration-test/ai-gap-fill-cases.json（今回追加した Test Case の対象要件）

出力
  - reports/integration-test/non-automatable-requirements.json
  - reports/integration-test/non-automatable-requirements.md

判定の考え方
  要件本文の「検証方法」（11章は「確認方法」）の区分を正本とし、
  非機能要件定義書 3.2 の区分のうち、結合試験（自動テスト）で判定できないものを対象外とする。
  自動テストで判定できる要件は Required Coverage へ追加し Test Case を実装済みのため、本表には含めない。

再精査（修正2回目）
  修正1回目で対象外とした 74 件を、要件本文の検証方法欄で1件ずつ再精査した。
  区分名ではなく「結合試験環境（app サービスのコンテナ）の中に解析・判定の対象が存在するか」
  「形骸的（常に真・ファイル存在確認のみ）でない検証ができるか」で判定し、
  11 件を自動検証へ移した。残りは REEXAMINATION に再精査の結論と根拠を記録する。
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "reports" / "integration-test"
NFR_PATH = ROOT / "docs" / "requirements" / "non_functional_requirements.md"

RUN_ID = "RUN-20261022-MC"

# Traceability Audit（FULL Scope）の C10 で不合格となった 124 件。
C10_REQUIREMENTS = (
    [f"FR-OUT-{number:02d}" for number in range(1, 17)]
    + [f"NFR-AV-{number:02d}" for number in range(1, 13)]
    + [f"NFR-EN-{number:02d}" for number in range(1, 14)]
    + [f"NFR-LG-{number:02d}" for number in range(1, 11)]
    + [f"NFR-MG-{number:02d}" for number in range(1, 9)]
    + [f"NFR-OM-{number:02d}" for number in [2, 3, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19]]
    + [f"NFR-PF-{number:02d}" for number in range(1, 18)]
    + [
        f"NFR-SC-{number:02d}"
        for number in [2, 7, 8, 10, 11, 12, 13, 14, 15, 17, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29]
    ]
    + [f"NFR-US-{number:02d}" for number in range(1, 11)]
)

# 検証方法の区分（非機能要件定義書 3.2）ごとの、自動テスト対象外とする理由。
CATEGORY_REASONS = {
    "NOT_APPLICABLE": (
        "要件本文が「該当なし」（当該の機能・構成を設けない）と定め、検証方法も「該当なし」と定義されている。"
        "本リリースの構成・基盤に関する事項であり、結合試験で判定できる振る舞いが存在しない。"
    ),
    "OPERATIONAL_MEASUREMENT": (
        "検証方法が「運用時に測定」。本番環境（ENV-02）の稼働実績・監視記録でのみ測定できる指標であり、"
        "ENV-01 の結合試験では測定できない（代替確認として構成・設定レビューが定められている）。"
    ),
    "PERFORMANCE_TEST": (
        "検証方法が「性能テスト」または「負荷テスト・耐久テスト」。ピーク負荷（同時155利用者）と"
        "3年後データ量（VDC-01〜VDC-03）を与えて応答時間・スループット・資源使用率を測定する試験であり、"
        "機能の正否を確かめる結合試験とは測定条件・判定基準が異なる。"
    ),
    "MIGRATION_REHEARSAL": (
        "検証方法が「移行リハーサル」。本番と同じ手順・コマンドで本番相当の件数（VDC-04：1,157件）を投入し、"
        "件数照合・所要時間を確認する作業であり、結合試験の対象ではない。"
    ),
    "CONFIG_REVIEW": (
        "検証方法が「構成・設定レビュー」。構成ファイル・設定値・手順書の記載内容を確認する作業であり、"
        "実行時の振る舞いとして現れないため結合試験では判定できない。"
    ),
    "STATIC_ANALYSIS": (
        "検証方法が「静的解析・コードレビュー」。ソースコード・依存定義の内容を解析・レビューして確認する"
        "要件であり、実行時の振る舞いの確認では充足を判定できない。"
    ),
    "COMPATIBILITY_TEST": (
        "検証方法が「互換性・操作性テスト」。対象ブラウザでの表示・解像度・キーボード操作・"
        "アクセシビリティ基準の適合など、ブラウザを操作して確認する試験であり、"
        "サーバー側の結合試験では判定できない。"
    ),
    "VULNERABILITY_SCAN": (
        "検証方法が「脆弱性診断」。診断ツールまたは診断者が実施する診断であり、結合試験の対象ではない。"
    ),
    "OPERATION_TEST": (
        "検証方法が「運用テスト」のうち、コンテナ基盤の起動・環境変数の変更・監視通知など、"
        "テストプロセスの外側（基盤・運用手順）を操作して確認する要件であり、結合試験では判定できない。"
    ),
}

# 要件ごとの区分と補足（要件本文の検証方法に基づく）。
CLASSIFICATION = {
    "NFR-AV-01": ("OPERATIONAL_MEASUREMENT", "月次の提供時間の集計。代替確認は構成・設定レビュー。"),
    "NFR-AV-02": ("OPERATIONAL_MEASUREMENT", "月次の稼働率（MON-01 の記録）から算出する。"),
    "NFR-AV-03": ("OPERATIONAL_MEASUREMENT", "計画停止の実績時刻の記録による。"),
    "NFR-AV-04": ("OPERATIONAL_MEASUREMENT", "日次バックアップの取得結果（MON-07）の確認による。"),
    "NFR-AV-05": ("OPERATIONAL_MEASUREMENT", "障害発生時の検知時刻・再開時刻の記録による（RTO 6時間以内）。"),
    "NFR-AV-06": ("NOT_APPLICABLE", "単一構成のため冗長化を行わない（要件内容・検証方法とも該当なし）。"),
    "NFR-AV-07": ("OPERATIONAL_MEASUREMENT", "本番環境でのリストア実施による（RPO 24時間）。"),
    "NFR-AV-08": ("OPERATIONAL_MEASUREMENT", "復旧後の全機能の操作確認による（RLO）。"),
    "NFR-AV-09": ("NOT_APPLICABLE", "別拠点での復旧方式を設けない（該当なし）。"),
    "NFR-AV-10": ("NOT_APPLICABLE", "縮退運転を行わない（該当なし）。"),
    "NFR-AV-11": ("OPERATIONAL_MEASUREMENT", "本番環境構築時のバックアップ保管先の確認による。"),
    "NFR-AV-12": ("OPERATIONAL_MEASUREMENT", "本番稼働前のリストア実施と所要時間の計測による（4時間以内）。"),
    "NFR-EN-03": (
        "CONFIG_REVIEW",
        "compose.yaml のサービス構成（app・db の2つ）の確認。結合試験は app・db のコンテナ上で実行しているが、"
        "構成そのものの妥当性は設定レビューで判定する。",
    ),
    "NFR-EN-06": ("OPERATIONAL_MEASUREMENT", "本番基盤の選定・構築時の設置場所（日本国内）の確認による。"),
    "NFR-EN-07": ("CONFIG_REVIEW", "ホスト OS 固有の設定・パスに依存しないことの確認。"),
    "NFR-EN-08": ("CONFIG_REVIEW", "本番環境の起動設定（開発用サーバーを使用しない）の確認。"),
    "NFR-EN-09": ("STATIC_ANALYSIS", "依存定義・リポジトリにフロントエンドのビルド設定が無いことの確認。"),
    "NFR-EN-10": ("CONFIG_REVIEW", "採用製品のサポート期限と更新計画の確認。"),
    "NFR-EN-11": ("STATIC_ANALYSIS", "ruff による静的解析と命名規約のレビュー。"),
    "NFR-EN-12": ("STATIC_ANALYSIS", "依存ライブラリの一覧とライセンスの確認。"),
    "NFR-EN-13": ("NOT_APPLICABLE", "機器・消費エネルギーの制約が無い（該当なし）。"),
    "NFR-LG-03": (
        "CONFIG_REVIEW",
        "保存期間経過データの削除手順が注文日から7年以内のデータを削除しない条件であることの確認。"
        "保存期間そのものは運用で判定する。",
    ),
    "NFR-LG-07": ("VULNERABILITY_SCAN", "OWASP Top 10 への対策は脆弱性診断とセキュリティテストの結果で確認する。"),
    "NFR-LG-08": ("COMPATIBILITY_TEST", "JIS X 8341-3:2016 適合レベル A のチェックリストによる確認。"),
    "NFR-MG-02": ("MIGRATION_REHEARSAL", "VDC-04 の件数照合・内容照合による。"),
    "NFR-MG-03": ("MIGRATION_REHEARSAL", "VDC-04 投入後に管理者7名がログインできることの確認による。"),
    "NFR-MG-04": ("MIGRATION_REHEARSAL", "本番と同じ手順・コマンドでの一括投入による。"),
    "NFR-MG-05": ("CONFIG_REVIEW", "移行計画の実施日・実施者・在庫数量の確定時刻の記載確認による。"),
    "NFR-MG-06": ("NOT_APPLICABLE", "新規システムのため移行による停止が無い（該当なし）。"),
    "NFR-MG-08": ("MIGRATION_REHEARSAL", "本番と同じ件数構成の定義ファイルでのリハーサル実施による。"),
    "NFR-OM-02": ("OPERATIONAL_MEASUREMENT", "90日経過後のログ検索による（保管期間）。"),
    "NFR-OM-03": ("OPERATIONAL_MEASUREMENT", "年1回の削除作業前の確認による（監査ログ1年保管）。"),
    "NFR-OM-05": (
        "OPERATION_TEST",
        "`docker compose up -d` 1回での全サービス起動の確認。テストプロセスの外側（コンテナ基盤）の操作であり、"
        "結合試験の中では判定しない。",
    ),
    "NFR-OM-06": (
        "OPERATION_TEST",
        "`docker compose exec app pytest` 1コマンドでの全件実行と失敗0件の確認。"
        "結合試験の実行そのものが対象であり、Test Case として自己言及的に判定しない"
        "（実測値は integration-test-report.md の実行結果に記録している）。",
    ),
    "NFR-OM-07": ("STATIC_ANALYSIS", "ruff による静的解析の指摘0件の確認。"),
    "NFR-OM-08": ("OPERATIONAL_MEASUREMENT", "対応記録の対応時刻による（有人運用時間）。"),
    "NFR-OM-09": ("OPERATIONAL_MEASUREMENT", "本番環境での監視設定と通知到達の確認による。"),
    "NFR-OM-10": ("OPERATIONAL_MEASUREMENT", "検知から通知までの時間（5分以内）の測定による。"),
    "NFR-OM-12": ("CONFIG_REVIEW", "本番基盤のスケジュール設定と運用手順書の記載確認による。"),
    "NFR-OM-14": ("OPERATIONAL_MEASUREMENT", "パッチの公開日と適用日の記録による。"),
    "NFR-OM-15": (
        "OPERATION_TEST",
        "コンテナイメージの再構築・migrate・起動と切戻しの所要時間計測（120分以内）。基盤操作であり結合試験の対象外。",
    ),
    "NFR-OM-16": ("OPERATIONAL_MEASUREMENT", "問い合わせの受付時刻と一次回答時刻の記録による。"),
    "NFR-OM-17": (
        "OPERATION_TEST",
        "環境変数を変更して app を再起動し設定が反映されることの確認。プロセス再起動を伴うため結合試験では判定しない"
        "（設定値が環境変数から読み込まれる実装であることは構成・設定レビューの対象）。",
    ),
    "NFR-OM-19": ("CONFIG_REVIEW", "README.md・本番運用手順書の記載内容の確認による。"),
    "NFR-PF-01": ("PERFORMANCE_TEST", "照会系APIの応答時間95パーセンタイル 1.0秒以内の測定。"),
    "NFR-PF-02": ("PERFORMANCE_TEST", "更新系APIの応答時間95パーセンタイル 2.0秒以内の測定。"),
    "NFR-PF-03": ("PERFORMANCE_TEST", "画面の表示完了時間 2.0秒以内の測定（ブラウザ計測を含む）。"),
    "NFR-PF-04": ("PERFORMANCE_TEST", "ピーク時処理能力 240件/時以上の測定。"),
    "NFR-PF-05": ("PERFORMANCE_TEST", "同時155利用者の負荷での目標値充足の判定。"),
    "NFR-PF-06": ("PERFORMANCE_TEST", "3年後データ量での応答時間の測定。"),
    "NFR-PF-09": ("PERFORMANCE_TEST", "認証系APIの応答時間 2.0秒以内の測定。"),
    "NFR-PF-10": ("MIGRATION_REHEARSAL", "初期データ一括投入の所要時間 60秒以内の計測（VDC-04）。"),
    "NFR-PF-11": (
        "PERFORMANCE_TEST",
        "想定を超える負荷での 5xx 応答率1%以下・在庫数量0未満0件・金額整合の確認。"
        "整合性そのものは IT-AI-GF-069（NFR-PF-07）で10並列・10試行を確認済みだが、"
        "上限超過時の負荷条件は性能・耐久試験で与える。",
    ),
    "NFR-PF-12": ("NOT_APPLICABLE", "定期的なバッチ処理を持たない（該当なし）。"),
    "NFR-PF-13": ("OPERATIONAL_MEASUREMENT", "バックアップの開始・終了時刻（MON-07）の記録による。"),
    "NFR-PF-14": ("OPERATIONAL_MEASUREMENT", "ピーク負荷時の CPU・メモリ使用率（MON-02）の測定による。"),
    "NFR-PF-15": ("PERFORMANCE_TEST", "2時間の連続負荷での応答時間推移・メモリ推移の記録による。"),
    "NFR-PF-17": (
        "STATIC_ANALYSIS",
        "決済サービスとの連携部分が独立したモジュールであることのコードレビュー。"
        "連携境界の項目（4項目）だけで動作することは IT-AI-GF-029・055 で確認済み。",
    ),
    "NFR-SC-02": ("OPERATIONAL_MEASUREMENT", "本番環境の TLS 1.2 以上での接続確認による（ENV-01 は HTTP を許容）。"),
    "NFR-SC-07": ("STATIC_ANALYSIS", "リポジトリ内の秘密情報の検索と .env の非含有の確認。"),
    "NFR-SC-11": ("VULNERABILITY_SCAN", "依存ライブラリの既知脆弱性（CVSS 7.0以上 0件）の照合。"),
    "NFR-SC-20": ("OPERATIONAL_MEASUREMENT", "本番環境の保存時暗号化設定の確認による。"),
    "NFR-SC-21": (
        "VULNERABILITY_SCAN",
        "8.2 の VUL-01〜VUL-13 全項目の充足確認。うち VUL-04（入力値検証）・VUL-05（XSS）・VUL-06（CSRF）は "
        "IT-AI-GF-012〜019 で確認済みだが、全項目の判定は脆弱性診断による。",
    ),
    "NFR-SC-25": ("CONFIG_REVIEW", "検証データの作成手順と初期データ定義ファイルの内容の確認による。"),
    "NFR-SC-26": ("OPERATIONAL_MEASUREMENT", "本番環境での外部からのポート到達性の確認による。"),
    "NFR-SC-29": ("VULNERABILITY_SCAN", "稼働開始前の動的診断の実施による。"),
    "NFR-US-01": ("COMPATIBILITY_TEST", "Chrome・Edge 最新版での全画面・全操作の確認。"),
    "NFR-US-02": ("COMPATIBILITY_TEST", "幅1280px×高さ720px での表示崩れ・横スクロールの確認。"),
    "NFR-US-05": ("COMPATIBILITY_TEST", "JIS X 8341-3:2016 適合レベル A のチェックリストによる確認。"),
    "NFR-US-06": ("COMPATIBILITY_TEST", "Windows 11 の PC での確認。"),
    "NFR-US-07": ("COMPATIBILITY_TEST", "キーボードだけでの全操作の確認。"),
    "NFR-US-08": ("COMPATIBILITY_TEST", "商品一覧から支払完了までの画面数（7画面以内）の確認。"),
    "NFR-US-09": (
        "COMPATIBILITY_TEST",
        "確認ダイアログの表示と取消時にデータが変更されないことの確認。ブラウザの JavaScript 実行と"
        "利用者操作を伴うため結合試験では判定しない。",
    ),
    "NFR-US-10": (
        "COMPATIBILITY_TEST",
        "ボタン連続押下時に要求が1回だけ送信されることの確認。ブラウザ操作を伴うため結合試験では判定しない。",
    ),
}

# 再精査（修正2回目）の結論。修正1回目で対象外とした 74 件を1件ずつ見直した記録。
# AUTOMATED : 結合試験へ移した（本表から外れる）。case は追加した Test Case の ID。
# KEEP      : 対象外のまま。reason に「要件本文の検証方法欄のどこが結合試験で扱えないか」を記す。
REEXAMINATION = {
    # --- 静的解析・コードレビュー（6件）：解析対象が app のイメージ内に存在するため全件を自動検証へ ---
    "NFR-OM-07": ("AUTOMATED", "IT-AI-GF-070", "検証方法が指定するコマンド（ruff）を結合試験の中で実行し、指摘0件を判定できる。"),
    "NFR-EN-11": ("AUTOMATED", "IT-AI-GF-071", "URL・API の JSON 項目名・テストファイル名は実行時に収集でき、規約との照合を自動判定できる。"),
    "NFR-EN-12": ("AUTOMATED", "IT-AI-GF-072", "依存ライブラリの一覧とライセンスはイメージ内のメタデータから解決でき、AGPL・不明を判定できる。"),
    "NFR-PF-17": ("AUTOMATED", "IT-AI-GF-073", "モジュールの依存方向と境界の項目は AST で解析でき、実際の決済要求の内容も併せて判定できる。"),
    "NFR-SC-07": ("AUTOMATED", "IT-AI-GF-074", "app に同梱される全ソースを実行中の秘密情報の値で走査でき、既定値に固定値が無いことも読み込みで判定できる。"),
    "NFR-EN-09": ("AUTOMATED", "IT-AI-GF-075", "ビルド設定の不存在・JavaScript の用途・サーバー描画の成立は、イメージ内の資産と実際の応答から判定できる。"),
    # --- 構成・設定レビュー（9件中2件を自動検証へ） ---
    "NFR-EN-08": ("AUTOMATED", "IT-AI-GF-076", "本番と同一イメージの起動プロセスを結合試験の実行環境そのもので確認でき、開発用サーバー不使用を判定できる。"),
    "NFR-LG-03": (
        "AUTOMATED",
        "IT-AI-GF-079",
        "対応方針欄の「登録後に更新・削除しない」は実行時の振る舞いとして判定できる。"
        "確認方法欄が指す「保存期間経過データの削除手順（7年以内を削除しない条件）」は運用手順書の記載確認であり、残課題として扱う。",
    ),
    "NFR-EN-03": (
        "KEEP",
        None,
        "検証方法欄が「構成・設定レビュー（compose.yaml のサービスが app・db の2つであることを確認する）」。"
        "compose.yaml は app イメージへ同梱されず（Dockerfile は app/ のみを COPY）、結合試験環境から内容を参照できない。"
        "サービス数を実行時の振る舞いへ置き換えると「app が起動している」ことの確認にしかならず、形骸的なテストになる。",
    ),
    "NFR-EN-07": (
        "KEEP",
        None,
        "検証方法欄が「構成・設定レビュー（ホスト OS 固有の設定・パスに依存しないことを確認する）」。"
        "結合試験は Linux コンテナ1種類でしか実行されないため、他のホスト OS で成立することを示せない。"
        "ソース内の絶対パス検索に置き換えても常に真となり、形骸的なテストになる。",
    ),
    "NFR-EN-10": (
        "KEEP",
        None,
        "検証方法欄が「構成・設定レビュー（稼働開始前に各製品のサポート期限を確認し、更新計画に記載されていることを確認する）」。"
        "判定対象はサポート期限の調査結果と更新計画の記載であり、実行環境には存在しない。"
        "採用製品の版そのものは IT-AI-GF-056（NFR-EN-01・NFR-EN-02）で確認済みで、版の確認を本要件の充足とすると要件の意味（期限管理）を置き換えてしまう。",
    ),
    "NFR-MG-05": (
        "KEEP",
        None,
        "検証方法欄が「構成・設定レビュー（移行計画に実施日・実施者・在庫数量の確定時刻が記載されていることを確認する）」。"
        "判定対象は移行計画書の記載であり、システムの振る舞いとして現れない。",
    ),
    "NFR-OM-12": (
        "KEEP",
        None,
        "検証方法欄が「構成・設定レビュー（本番環境構築時にスケジュール設定を確認する。運用手順書に手動実行の手順が記載されていることを確認する）」。"
        "判定対象は本番基盤（未決、NOQ-01）のスケジュール設定と運用手順書の記載である。"
        "app 側に定期ジョブが無いことは IT-AI-GF-078（NFR-PF-12）で確認しているが、本要件の目標値はバックアップの起動時刻（毎日3:00）であり結合試験では判定できない。",
    ),
    "NFR-OM-19": (
        "KEEP",
        None,
        "検証方法欄が「構成・設定レビュー（README.md の手順どおりに ENV-01 を構築・起動できることを確認する。本番運用手順書は本番稼働前に記載項目を確認する）」。"
        "README.md は app イメージへ同梱されず、記載の有無を文字列照合で代替すると手順の妥当性を確認したことにならない（形骸的なテストになる）。",
    ),
    "NFR-SC-25": (
        "KEEP",
        None,
        "検証方法欄が「構成・設定レビュー（12.2 の検証データの作成手順と初期データ定義ファイルの内容を確認する）」。"
        "「架空の値だけで作成されているか」は値の意味の判断であり、機械的な判定条件を要件が与えていない。"
        "本番データを使っていないことの立証は環境・運用の確認による。",
    ),
    # --- 該当なし（6件中2件を自動検証へ） ---
    "NFR-AV-10": ("AUTOMATED", "IT-AI-GF-077", "「縮退運転を行わない」は、DB 停止時に全機能が一律にシステムエラーとなる（部分継続が無い）ことで判定できる。"),
    "NFR-PF-12": ("AUTOMATED", "IT-AI-GF-078", "「定期バッチを持たない」は、定期実行の仕組み・cron 定義・管理コマンド・古い注文の残存で判定できる。"),
    "NFR-AV-06": (
        "KEEP",
        None,
        "要件内容・目標値・検証方法の全欄が「該当なし」。冗長化しない構成であることは compose.yaml の"
        "サービス定義（app・db 各1）に現れるが、同ファイルは app イメージへ同梱されず結合試験環境から参照できない。"
        "実行時の振る舞いとして「冗長化していないこと」を示す観測点が無い。",
    ),
    "NFR-AV-09": (
        "KEEP",
        None,
        "要件内容・目標値・検証方法の全欄が「該当なし」。別拠点での復旧方式を設けないことは本番基盤の構成（未決、NOQ-01）に属し、"
        "app の実行時の振る舞いに観測点が無い。「設けられていないこと」を示す対象コード・設定が存在しない。",
    ),
    "NFR-EN-13": (
        "KEEP",
        None,
        "要件内容・目標値・検証方法の全欄が「該当なし」。機器の設置スペース・消費電力に関する制約が無く、"
        "ソフトウェア側に検証対象となる仕様・設定・振る舞いが存在しない。",
    ),
    "NFR-MG-06": (
        "KEEP",
        None,
        "要件内容・目標値・検証方法の全欄が「該当なし」。新規システムのため移行で停止する稼働中サービスが無く、"
        "停止許容時間という判定対象そのものが存在しない。",
    ),
    # --- 性能テスト（9件中1件の不変条件のみを自動検証へ） ---
    "NFR-PF-11": (
        "AUTOMATED",
        "IT-AI-GF-080",
        "要件内容欄の「受け付けた要求に対しては正常応答または業務エラー応答を返し、在庫数量・注文状態・金額の"
        "不整合を発生させないこと」は負荷の大きさによらない不変条件であり、同時要求で判定できる。"
        "目標値欄の測定条件（同時310利用者を10分間、5xx 応答率1%以下）は負荷テストで与えるため、残課題として扱う。",
    ),
    "NFR-PF-01": ("KEEP", None, "検証方法欄が「性能テスト（負荷テストツールで ENV-01 に NFR-PF-05 の操作内容で負荷をかけ、API種別ごとの応答時間の95パーセンタイルを算出する）」。判定対象は測定値そのもので、仕様として表明できる部分が無い。"),
    "NFR-PF-02": ("KEEP", None, "検証方法欄が「性能テスト（NFR-PF-01 と同じ負荷の中で、API種別ごとの応答時間の95パーセンタイルを算出する）」。判定対象は測定値そのもので、仕様として表明できる部分が無い。"),
    "NFR-PF-03": ("KEEP", None, "検証方法欄が「性能テスト（負荷をかけた状態でブラウザの開発者ツールまたは負荷テストツールで表示完了時間を計測する）」。ブラウザでの計測を要し、サーバー側の結合試験では判定できない。"),
    "NFR-PF-04": ("KEEP", None, "検証方法欄が「性能テスト（60分間に成功した注文確定の件数を数え、240件以上であることを確認する）」。判定対象は単位時間あたりの処理件数の測定値である。"),
    "NFR-PF-05": ("KEEP", None, "検証方法欄が「性能テスト（負荷テストツールで155の仮想利用者を同時に動作させ、NFR-PF-01〜NFR-PF-03・NFR-PF-09 を判定する）」。判定は応答時間の目標値への適合であり測定が必須である。"),
    "NFR-PF-06": ("KEEP", None, "検証方法欄が「性能テスト（3年後データ量を投入した状態で NFR-PF-01〜NFR-PF-03 を測定する）」。3年後データ量（注文11万件）の投入と応答時間の測定を要する。"),
    "NFR-PF-09": ("KEEP", None, "検証方法欄が「性能テスト（NFR-PF-01 と同じ負荷の中で計測する）」。判定対象は認証系APIの応答時間の測定値である。"),
    "NFR-PF-15": ("KEEP", None, "検証方法欄が「負荷テスト・耐久テスト（2時間の連続負荷で応答時間の推移と app・db のメモリ使用量の推移を記録する）」。2時間の連続負荷と資源使用量の記録を要する。"),
}

# 自動検証へ移したが、要件の一部が別工程に残るもの（部分充足の明示）。
RESIDUAL_MANUAL_CHECKS = {
    "NFR-PF-11": (
        "目標値欄の測定条件（同時310利用者・10分間でのシステムエラー応答率1%以下）は負荷テスト・耐久テストで確認する。"
        "IT-AI-GF-080 が判定したのは、負荷の大きさによらない不変条件（システムエラー0件、在庫数量0未満0件、金額整合）である。"
    ),
    "NFR-SC-07": (
        "対象欄の「リポジトリの履歴」と「.env がリポジトリに含まれないこと」は、app イメージへリポジトリが"
        "同梱されないため結合試験では判定できない。Quality / Security Review のリポジトリ走査で確認する。"
        "IT-AI-GF-074 が判定したのは、app に同梱される全ソース・設定への平文混入0件と、既定値に固定値が無いことである。"
    ),
    "NFR-LG-03": (
        "確認方法欄の「保存期間経過データの削除手順が注文日から7年以内のデータを削除しない条件であること」は"
        "運用手順書の記載確認であり、構成・設定レビューで確認する。"
        "IT-AI-GF-079 が判定したのは、システムが帳簿書類を書き換えず、削除する手段も自動削除の仕組みも持たないことである。"
    ),
    "NFR-EN-11": (
        "目標値欄のうち「命名規約のレビュー」の定性的な部分（識別子の意味の妥当性）は Quality Review で確認する。"
        "IT-AI-GF-070・071 が判定したのは、PEP 8（ruff 指摘0件）と機械的に照合できる命名規約である。"
    ),
}


def nfr_rows() -> dict[str, dict[str, str]]:
    """非機能要件定義書の要件表を ID ごとの辞書として読み込む。"""
    header: list[str] | None = None
    rows: dict[str, dict[str, str]] = {}
    for line in NFR_PATH.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text.startswith("|"):
            continue
        cells = [cell.strip() for cell in text.strip("|").split("|")]
        if cells and cells[0] == "ID":
            header = cells
            continue
        if header and cells and re.fullmatch(r"NFR-[A-Z]{2}-\d+", cells[0]):
            rows[cells[0]] = {
                header[index] if index < len(header) else f"col{index}": cells[index]
                for index in range(len(cells))
            }
    return rows

def covered_requirements() -> set[str]:
    """今回追加した Test Case が対象とする要件IDを返す。"""
    cases = json.loads((REPORT_DIR / "ai-gap-fill-cases.json").read_text(encoding="utf-8"))["cases"]
    covered: set[str] = set()
    for case in cases:
        for identifier in re.split(r"[,、\s]+", str(case["requirement_id"])):
            if identifier:
                covered.add(identifier)
    return covered


def main() -> int:
    """自動テスト対象外の要件を整理して出力する。"""
    rows = nfr_rows()
    covered = covered_requirements()
    remaining = [identifier for identifier in C10_REQUIREMENTS if identifier not in covered]

    items = []
    for identifier in remaining:
        category, note = CLASSIFICATION.get(identifier, ("CONFIG_REVIEW", ""))
        row = rows.get(identifier, {})
        # 11章（法令・規約・標準）の表は列構成が異なる（要件項目→法令・規約名、検証方法→確認方法）。
        item_name = row.get("要件項目") or row.get("法令・規約名", "")
        content = row.get("要件内容") or row.get("求められる事項", "")
        target = row.get("目標値（単位付き）") or row.get("対応方針", "")
        method = row.get("検証方法") or row.get("確認方法", "")
        items.append(
            {
                "requirement_id": identifier,
                "requirement_item": item_name,
                "requirement_content": content,
                "target_value": target,
                "verification_method_in_requirement": method,
                "category": category,
                "reason_not_automatable": CATEGORY_REASONS[category],
                "note": note,
                "reexamination_round2": (
                    REEXAMINATION[identifier][2]
                    if identifier in REEXAMINATION and REEXAMINATION[identifier][0] == "KEEP"
                    else "修正1回目の分類を維持（再精査の対象区分外）。"
                ),
                "responsible_phase": {
                    "NOT_APPLICABLE": "対応不要（要件が機能を設けないと定めている）",
                    "OPERATIONAL_MEASUREMENT": "本番稼働後の運用（ENV-02）",
                    "PERFORMANCE_TEST": "性能・負荷試験（ENV-01、別工程）",
                    "MIGRATION_REHEARSAL": "移行リハーサル（稼働開始前）",
                    "CONFIG_REVIEW": "構成・設定レビュー（設計・運用準備）",
                    "STATIC_ANALYSIS": "静的解析・コードレビュー（Quality / Security Review）",
                    "COMPATIBILITY_TEST": "互換性・操作性テスト（受入試験）",
                    "VULNERABILITY_SCAN": "脆弱性診断（稼働開始前）",
                    "OPERATION_TEST": "運用テスト（基盤・運用手順）",
                }[category],
            }
        )

    by_category: dict[str, list[str]] = {}
    for item in items:
        by_category.setdefault(item["category"], []).append(item["requirement_id"])

    document = {
        "run_id": RUN_ID,
        "phase": "INTEGRATION_TEST",
        "purpose": (
            "Traceability Audit（FULL Scope）の C10（TEST_TRACEABILITY_MISSING、124件）について、"
            "要件本文の検証方法を正本として自動テストの対象可否を判定し、対象外とした要件の理由を記録する。"
            "修正2回目では、修正1回目で対象外とした74件を1件ずつ再精査し、結合試験環境の中に解析・判定の"
            "対象が存在し形骸的でない検証ができる11件を自動検証へ移した。"
        ),
        "source_of_truth": [
            "docs/requirements/non_functional_requirements.md 3.2 検証方法の区分、4〜12章の要件表",
            "docs/requirements/functional_requirements.md 2.3 対象外機能",
        ],
        "summary": {
            "c10_total": len(C10_REQUIREMENTS),
            "covered_by_new_integration_tests": len(C10_REQUIREMENTS) - len(remaining),
            "not_automatable": len(remaining),
            "by_category": {key: len(value) for key, value in sorted(by_category.items())},
        },
        "reexamination_round2": {
            "scope": "修正1回目で自動テスト対象外とした74件すべて",
            "criteria": [
                "要件本文の「検証方法」（11章は「確認方法」）欄を正本とする",
                "結合試験環境（app サービスのコンテナ）の中に解析・判定の対象が存在するか",
                "形骸的（常に真になる・実質何も検証しない・ファイル存在確認のみ）でない検証ができるか",
                "負荷の測定値そのもの、本番環境でのみ測定できる指標、ブラウザ操作、移行リハーサル、"
                "脆弱性診断を要するものは対象としない",
            ],
            "moved_to_automated": [
                {
                    "requirement_id": identifier,
                    "case_id": entry[1],
                    "rationale": entry[2],
                    "residual_manual_check": RESIDUAL_MANUAL_CHECKS.get(identifier),
                }
                for identifier, entry in REEXAMINATION.items()
                if entry[0] == "AUTOMATED"
            ],
            "kept_not_automatable": [
                {
                    "requirement_id": identifier,
                    "category": CLASSIFICATION[identifier][0],
                    "verification_method_in_requirement": (
                        rows.get(identifier, {}).get("検証方法")
                        or rows.get(identifier, {}).get("確認方法", "")
                    ),
                    "rationale": entry[2],
                }
                for identifier, entry in REEXAMINATION.items()
                if entry[0] == "KEEP"
            ],
            "not_reexamined": {
                "categories": [
                    "OPERATIONAL_MEASUREMENT",
                    "MIGRATION_REHEARSAL",
                    "VULNERABILITY_SCAN",
                    "COMPATIBILITY_TEST",
                    "OPERATION_TEST",
                ],
                "reason": (
                    "いずれも本質的に自動テストの対象外（本番環境での測定、移行リハーサル、脆弱性診断、"
                    "ブラウザ操作、基盤・運用手順の操作）であり、修正1回目の分類を維持した。"
                ),
            },
        },
        "covered_requirements": sorted(identifier for identifier in C10_REQUIREMENTS if identifier in covered),
        "not_automatable_requirements": items,
    }
    (REPORT_DIR / "non-automatable-requirements.json").write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    lines = [
        "# 自動テスト対象外の要件（Traceability C10 の分類）",
        "",
        f"- run_id: {RUN_ID}",
        "- 工程: INTEGRATION_TEST",
        f"- C10 不合格件数: {len(C10_REQUIREMENTS)} 件",
        f"- 結合試験ケース追加で検証した要件: {len(C10_REQUIREMENTS) - len(remaining)} 件",
        f"- 自動テスト対象外と判定した要件: {len(remaining)} 件",
        "",
        "判定は要件本文の「検証方法」（11章は「確認方法」）の欄を正本とする。",
        "非機能要件定義書 3.2 の検証方法のうち、結合試験（自動テスト）で判定できない区分を対象外とした。",
        "",
        "修正2回目では、修正1回目で対象外とした 74 件を1件ずつ再精査した。",
        "区分名ではなく、次の2点で判定している。",
        "",
        "1. 結合試験環境（app サービスのコンテナ）の中に、解析・判定の対象が存在するか",
        "2. 形骸的（常に真になる・実質何も検証しない・ファイル存在確認のみ）でない検証ができるか",
        "",
        "## 1. 区分別の件数と理由",
        "",
        "| 区分 | 件数 | 対象外とする理由 | 実施する工程 |",
        "| --- | --- | --- | --- |",
    ]
    phase_by_category = {item["category"]: item["responsible_phase"] for item in items}
    for category, identifiers in sorted(by_category.items()):
        lines.append(
            f"| {category} | {len(identifiers)} | {CATEGORY_REASONS[category]} | {phase_by_category[category]} |"
        )

    lines += [
        "",
        "## 2. 要件ごとの検証方法と対象外理由",
        "",
        "| 要件ID | 要件項目 | 検証方法（要件本文の記載） | 区分 | 補足 | 再精査（修正2回目）の判断 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for item in items:
        method = item["verification_method_in_requirement"].replace("|", "／")
        reexamined = item["reexamination_round2"].replace("|", "／")
        lines.append(
            f"| {item['requirement_id']} | {item['requirement_item']} | {method} | "
            f"{item['category']} | {item['note']} | {reexamined} |"
        )

    moved = document["reexamination_round2"]["moved_to_automated"]
    kept = document["reexamination_round2"]["kept_not_automatable"]
    lines += [
        "",
        "## 3. 再精査（修正2回目）で自動検証へ移した要件",
        "",
        f"修正1回目で対象外とした 74 件のうち、次の {len(moved)} 件は結合試験環境の中に解析・判定の対象が存在し、",
        "形骸的でない検証ができると判断して Test Case を追加した。",
        "",
        "| 要件ID | 追加した Case | 自動検証できると判断した根拠 | 別工程に残る部分 |",
        "| --- | --- | --- | --- |",
    ]
    for entry in sorted(moved, key=lambda value: value["requirement_id"]):
        residual = (entry["residual_manual_check"] or "なし").replace("|", "／")
        lines.append(
            f"| {entry['requirement_id']} | {entry['case_id']} | "
            f"{entry['rationale'].replace('|', '／')} | {residual} |"
        )

    lines += [
        "",
        "## 4. 再精査しても対象外のままとした要件（再精査の対象区分）",
        "",
        "性能テスト・構成設定レビュー・静的解析・該当なしの区分について1件ずつ再精査した結果、",
        f"次の {len(kept)} 件は自動テストで正当に検証できないと判断した。",
        "",
        "| 要件ID | 区分 | 検証方法（要件本文の記載） | 対象外のままとする根拠 |",
        "| --- | --- | --- | --- |",
    ]
    for entry in sorted(kept, key=lambda value: value["requirement_id"]):
        method = entry["verification_method_in_requirement"].replace("|", "／")
        lines.append(
            f"| {entry['requirement_id']} | {entry['category']} | {method} | "
            f"{entry['rationale'].replace('|', '／')} |"
        )

    lines += [
        "",
        "## 5. 再精査の対象としなかった区分",
        "",
        "OPERATIONAL_MEASUREMENT・MIGRATION_REHEARSAL・VULNERABILITY_SCAN・COMPATIBILITY_TEST・OPERATION_TEST は、",
        "いずれも本番環境での測定、移行リハーサル、脆弱性診断、ブラウザ操作、基盤・運用手順の操作を要し、",
        "本質的に結合試験の対象外であるため修正1回目の分類を維持した。",
        "",
        "## 6. 結合試験で検証した要件（参考）",
        "",
        "C10 の 124 件のうち、次の要件は要件本文から結合試験で判定できると整理し、",
        "Required Coverage（ICOV-088〜ICOV-139）と AI GAP_FILL Case（IT-AI-GF-029〜080）を追加して検証した。",
        "",
        "```",
        ", ".join(document["covered_requirements"]),
        "```",
        "",
    ]
    (REPORT_DIR / "non-automatable-requirements.md").write_text("\n".join(lines), encoding="utf-8")
    print(
        f"C10={len(C10_REQUIREMENTS)} / 検証済={len(C10_REQUIREMENTS) - len(remaining)} / 対象外={len(remaining)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
