"""C10 再精査（修正2回目）で新たに自動検証できると判定した観点を Required Coverage へ追加する。

修正1回目で「自動テスト対象外」と分類した 74 件を、要件本文の「検証方法」欄を正本として
個別に再精査した。その結果、次の 11 件は結合試験環境（app サービスのコンテナ）の中に
解析・判定の対象が存在し、形骸的でない検証ができると判断した。

  静的解析・コードレビュー（6件）： NFR-OM-07 / NFR-EN-11 / NFR-EN-12 / NFR-PF-17 /
                                   NFR-SC-07 / NFR-EN-09
  構成・設定レビュー（2件）    ： NFR-EN-08（実行中の起動設定）/ NFR-LG-03（帳簿書類の不変性）
  該当なし（2件）              ： NFR-AV-10（縮退運転を行わない）/ NFR-PF-12（定期バッチを持たない）
  性能テスト（1件）            ： NFR-PF-11（負荷の測定値ではなく、要件が定める不変条件のみ）

既存の 128 件（ICOV-001〜ICOV-128）は変更しない。
初回測定値（initial-coverage-metrics.json）も変更しない。
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "reports" / "integration-test" / "required-coverage.json"

NEW_SOURCES = [
    "docs/requirements/non_functional_requirements.md 5章・6章・8章・10章・11章（検証方法欄の再精査）",
]

NEW_INTEGRATION_POINTS = [
    "app のソースツリー（静的解析・依存ライブラリ・画面の JavaScript）→ 解析結果",
    "app サービスの起動プロセス（WSGI サーバー）→ config.wsgi:application",
    "Web API・画面 → PostgreSQL（停止時の応答）",
    "Web API → orders / carts → PurchaseOrder・StockUnit（同時要求時の整合）",
]

NEW_ITEMS = [
    {
        "coverage_id": "ICOV-129",
        "coverage_key": "CK-NFROM07-01",
        "requirement_id": "NFR-OM-07",
        "related_adr": ["ADDR-012"],
        "integration_point": "app の全 Python ソースコード → ruff（静的解析）→ 指摘一覧",
        "test_category": "保守性（コード品質）",
        "criterion": "api",
        "condition": "ENV-01 で app のソースツリーに対し ruff を実行し、解析対象のファイル一覧と指摘件数を確認する",
        "expected_behavior": "解析対象に app の業務ロジック・API・設定が含まれ（ENV-01 のテスト用マウント /app/tests は対象外）、指摘は0件である（NFR-OM-07 の目標値。NFR-EN-11 の PEP 8 適合を機械的に確認する）",
    },
    {
        "coverage_id": "ICOV-130",
        "coverage_key": "CK-NFREN11-01",
        "requirement_id": "NFR-EN-11",
        "related_adr": ["ADDR-004", "ADDR-007"],
        "integration_point": "URLconf・Web API の応答（JSON）・テストファイル名 → 命名規約",
        "test_category": "準拠標準（開発標準・規約）",
        "criterion": "api",
        "condition": "URLconf に登録された全経路のパス、購入者・管理者の主要 API を一巡した応答の全 JSON 項目名（入力エラー応答の項目名を含む）、自動テストのファイル名を収集して規約と照合する",
        "expected_behavior": "URL パスは小文字・ハイフン区切り（アンダースコアを含まない）、可変部分名と API の JSON 項目名は snake_case、テストファイル名は test_*.py である（NFR-EN-11 の目標値）",
    },
    {
        "coverage_id": "ICOV-131",
        "coverage_key": "CK-NFREN12-01",
        "requirement_id": "NFR-EN-12",
        "related_adr": ["ADDR-011"],
        "integration_point": "導入済み依存ライブラリのメタデータ → ライセンス判定",
        "test_category": "技術制約（OSS・ライセンス）",
        "criterion": "api",
        "condition": "app のイメージへ導入済みの全依存ライブラリについて、ライセンス（License-Expression・License・分類子）を解決して照合する",
        "expected_behavior": "すべての依存ライブラリでライセンスが判明し、AGPL のライブラリは0件である。依存定義ファイルで固定した製品（Django・djangorestframework・psycopg・gunicorn・whitenoise・pytest・ruff）が導入されている（NFR-EN-12 の目標値：違反0件）",
    },
    {
        "coverage_id": "ICOV-132",
        "coverage_key": "CK-NFRPF17-01",
        "requirement_id": "NFR-PF-17",
        "related_adr": ["ADDR-009"],
        "integration_point": "shop.payments（決済連携の境界）↔ shop.services.orders → PaymentRecord",
        "test_category": "拡張性（将来の拡張）",
        "criterion": "api",
        "condition": "決済連携部分の各モジュールの import、shop 配下で決済連携部分を利用しているモジュール、決済要求・決済応答の項目定義を解析し、あわせて実際の支払で境界へ渡される決済要求を記録する",
        "expected_behavior": "決済連携部分は注文・在庫・金額計算（shop.models / shop.services / shop.api / shop.web）を参照せず、利用箇所は shop/services/orders.py の1箇所だけである。決済要求は注文番号・決済金額・通貨・模擬決済指示の4項目、決済応答は結果・取引参照番号・否認理由コード・処理日時の4項目で、業務オブジェクトを境界の向こう側へ渡さない（NFR-PF-17 の目標値：影響範囲を連携部分のみに限定できる）",
    },
    {
        "coverage_id": "ICOV-133",
        "coverage_key": "CK-NFRSC07-01",
        "requirement_id": "NFR-SC-07",
        "related_adr": ["ADDR-004", "ADDR-011"],
        "integration_point": "環境変数 → Django 設定 → app のソース・設定ファイル（平文混入の有無）",
        "test_category": "暗号化（認証情報・鍵の管理）",
        "criterion": "authentication",
        "condition": "実行中の秘密鍵・DB パスワードが環境変数から与えられていることを確認し、app に同梱される全ソース・設定・テンプレートを当該の値で走査する。あわせて環境変数を与えずに設定を2回読み込み、既定値を確認する",
        "expected_behavior": "秘密鍵・DB パスワードは環境変数の値と一致し、ソース・設定ファイルへの平文混入は0件である。環境変数が無い場合の DB パスワードの既定値は空文字で、秘密鍵は読み込みごとに異なる（ソースに固定値が無い）（NFR-SC-07 の目標値：平文混入0件）",
    },
    {
        "coverage_id": "ICOV-134",
        "coverage_key": "CK-NFREN09-01",
        "requirement_id": "NFR-EN-09",
        "related_adr": ["ADDR-004"],
        "integration_point": "リポジトリ内の定義ファイル・画面の JavaScript → Django テンプレート（サーバーサイドレンダリング）→ ブラウザ",
        "test_category": "技術制約（フレームワーク）",
        "criterion": "end-to-end-flow",
        "condition": "フロントエンドのビルド設定の有無、画面が読み込む JavaScript の内容と本数、商品詳細画面の HTML、カート画面と カート照会API の金額を確認する",
        "expected_behavior": "フロントエンドのビルド設定（package.json・webpack/vite/rollup 等）と node_modules は存在せず、画面の JavaScript は app.js の1本だけで、HTML の生成・通信（innerHTML・document.write・createElement・fetch・XMLHttpRequest 等）に用いていない（用途は確認ダイアログと二重送信の防止に限る）。画面は Django テンプレートで描画され、商品名・バリエーション名が HTML に含まれる。画面と API は同じ金額（小計・送料・消費税額・合計）を示す（NFR-EN-09 の目標値：SPA・ビルド工程の使用0件）",
    },
    {
        "coverage_id": "ICOV-135",
        "coverage_key": "CK-NFREN08-01",
        "requirement_id": "NFR-EN-08",
        "related_adr": ["ADDR-011", "ADDR-012"],
        "integration_point": "app サービスの起動プロセス → config.wsgi:application",
        "test_category": "実行環境（ミドルウェア）",
        "criterion": "api",
        "condition": "app サービスのコンテナで実行中の起動コマンドと WSGI エントリポイントを確認する（要件が定める実行方法 `docker compose exec app pytest` での実行を前提とする）",
        "expected_behavior": "起動コマンドは Gunicorn で config.wsgi:application を提供しており、Django 付属の開発用サーバー（runserver）・manage.py による起動は0件である（NFR-EN-08 の目標値）",
    },
    {
        "coverage_id": "ICOV-136",
        "coverage_key": "CK-NFRLG03-01",
        "requirement_id": "NFR-LG-03",
        "related_adr": ["ADDR-001", "ADDR-005"],
        "integration_point": "Web API → orders → PurchaseOrder・PurchaseOrderLine・ShippingAddress・PaymentRecord・PurchaseOrderStatusHistory",
        "test_category": "法令（帳簿書類の保存）",
        "criterion": "database",
        "condition": "注文確定→支払→キャンセルまで実行し、キャンセル前後の注文・注文明細・配送先・決済記録・注文状態履歴の内容を比較する。あわせて注文を削除する要求（DELETE）を送信する",
        "expected_behavior": "キャンセル後も注文・注文明細・配送先・決済記録はすべて残り、金額・数量・配送先・決済結果・取引参照番号・処理日時は書き換わらない。注文状態履歴は既存の記録を保ったまま追記される。削除を意図した要求はいずれも成功せず、キャンセル後も注文詳細を照会できる（NFR-LG-03 の対応方針：登録後に更新・削除しない）",
    },
    {
        "coverage_id": "ICOV-137",
        "coverage_key": "CK-NFRAV10-01",
        "requirement_id": "NFR-AV-10",
        "related_adr": ["ADDR-007"],
        "integration_point": "Web API・画面 → PostgreSQL（停止時）→ 共通エラー応答",
        "test_category": "可用性（障害時の縮退）",
        "criterion": "error-handling",
        "condition": "DB が応答しない状態を作り、認証不要の照会API・認証が必要なAPI・画面を要求する。その後 DB を復旧させて同じ経路を再度要求する",
        "expected_behavior": "停止中はすべての経路が共通のシステムエラー（API は 500／INTERNAL_ERROR、画面は 500 のエラー画面）となり、一部の機能だけを継続する応答（キャッシュ・代替経路による部分表示）は発生しない。復旧後は同じ経路が再び正常応答する（NFR-AV-10：縮退運転を行わない）",
    },
    {
        "coverage_id": "ICOV-138",
        "coverage_key": "CK-NFRPF12-01",
        "requirement_id": "NFR-PF-12",
        "related_adr": ["ADDR-010"],
        "integration_point": "app のイメージ（導入ライブラリ・cron 設定・管理コマンド）→ PurchaseOrder",
        "test_category": "性能（バッチ処理）",
        "criterion": "database",
        "condition": "定期実行のライブラリの導入状況・コンテナの cron 定義・shop の管理コマンドを確認し、引数なしでの管理コマンド実行を試みる。あわせて注文日を8年前にした注文を残したまま業務操作を続ける",
        "expected_behavior": "定期実行のライブラリ（celery・apscheduler 等）は導入されておらず、cron の定義も無い。shop の管理コマンドは初期データ一括投入の1つだけで、定義ファイルの指定が無い実行は失敗する。注文日が8年前の注文も自動削除されず照会できる（NFR-PF-12：定期的に実行するバッチ処理を持たない）",
    },
    {
        "coverage_id": "ICOV-139",
        "coverage_key": "CK-NFRPF11-01",
        "requirement_id": "NFR-PF-11",
        "related_adr": ["ADDR-001", "ADDR-003"],
        "integration_point": "Web API（注文確定・支払・キャンセル）→ orders → PurchaseOrder・StockUnit → PostgreSQL",
        "test_category": "同時利用者（上限超過時の挙動）",
        "criterion": "state-transition",
        "condition": "在庫3の在庫単位4件（合計12個）に対し、クーポン適用の有無を混在させた24件の注文確定を同時に送信し、続けて成立した注文へ支払・キャンセルを同時に要求する",
        "expected_behavior": "すべての要求が正常応答または業務エラー応答で、システムエラー（HTTP 500・INTERNAL_ERROR）は0件である。成立した注文は在庫の総数と同じ12件で、在庫数量が0未満の在庫単位は0件、全注文が金額整合（割引後小計＝小計−割引額、合計＝割引後小計＋送料＋消費税額、小計＝明細金額の合計）を満たし、在庫数量と未キャンセルの引当数量の合計が初期の在庫数量と一致する（NFR-PF-11 の目標値のうち、負荷の測定条件によらない不変条件）",
    },
]


def main() -> int:
    """Required Coverage へ再精査で特定した観点を追加する。"""
    document = json.loads(PATH.read_text(encoding="utf-8"))
    existing = {item["coverage_id"] for item in document["required_coverage"]}
    added = [item for item in NEW_ITEMS if item["coverage_id"] not in existing]
    document["required_coverage"].extend(added)

    derivation = document["derivation"]
    derivation["sources"] = sorted(set(derivation.get("sources", [])) | set(NEW_SOURCES))
    derivation["integration_points"] = sorted(
        set(derivation.get("integration_points", [])) | set(NEW_INTEGRATION_POINTS)
    )
    notes = derivation.setdefault("notes", [])
    note = (
        "ICOV-129〜ICOV-139 は Traceability Audit C10 の再精査（修正2回目）で追加した観点。"
        "修正1回目で「自動テスト対象外」と分類した 74 件を要件本文の検証方法欄で個別に再精査し、"
        "結合試験環境の中に解析・判定の対象が存在し、形骸的でない検証ができる 11 件を追加した。"
        "負荷の測定値（応答時間・スループット・稼働率）、本番環境でのみ測定できる指標、"
        "ブラウザ操作・移行リハーサル・脆弱性診断を要する要件は追加していない。"
    )
    if note not in notes:
        notes.append(note)

    PATH.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"追加: {len(added)} 件 / 合計: {len(document['required_coverage'])} 件")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
