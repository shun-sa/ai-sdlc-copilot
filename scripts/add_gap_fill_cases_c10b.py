"""C10 再精査（修正2回目）で追加した AI GAP_FILL Case を登録する。

修正1回目で「自動テスト対象外」と分類した 74 件を要件本文の「検証方法」欄で個別に再精査し、
結合試験環境の中に解析・判定の対象が存在する 11 観点（ICOV-129〜ICOV-139）を補う Test Case を、
既存の IT-AI-GF-001〜069 に続けて IT-AI-GF-070〜080 として追加する。

AI INITIAL Case（ai-initial-cases.json、snapshot initial-1）は変更しない。
既存 GAP_FILL Case の内容（期待結果・手順・入力）も変更しない。
gap_id は Required Coverage の MISSING 一覧から毎回導出する参照値のため、
全 GAP_FILL Case について現在の Required Coverage に合わせて付け直す。
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "reports" / "integration-test"
PATH = REPORT_DIR / "ai-gap-fill-cases.json"

AUTOMATABLE = "AUTOMATABLE"

NEW_CASES = [
    {
        "case_id": "IT-AI-GF-070",
        "title": "app の全 Python ソースコードが静的解析の指摘0件である",
        "requirement_id": "NFR-OM-07",
        "related_adr": "ADDR-012",
        "test_category": "保守性（コード品質）",
        "criterion": "api",
        "coverage_keys": ["CK-NFROM07-01"],
        "precondition": "ENV-01 の app コンテナで、依存定義ファイルで固定した ruff が利用できる",
        "input": "app のソースツリー（/app）と pyproject.toml の解析設定",
        "steps": (
            "1. `ruff check --show-files` で解析対象のファイル一覧を取得する\n"
            "2. 業務ロジック・API・設定のファイルが対象に含まれ、ENV-01 のテスト用マウント（/app/tests）が"
            "含まれないことを確認する\n"
            "3. `ruff check --output-format json` を実行し、指摘の一覧を取得する"
        ),
        "expected_result": (
            "解析対象は 50 ファイル以上で、shop/services/orders.py・shop/api/views_orders.py・"
            "config/settings.py を含み、/app/tests を含まない。指摘は0件で終了コードは0である"
            "（NFR-OM-07 の目標値。NFR-EN-11 の PEP 8 適合を機械的に確認する）"
        ),
    },
    {
        "case_id": "IT-AI-GF-071",
        "title": "URL・API の JSON 項目名・テストファイル名が命名規約に準拠する",
        "requirement_id": "NFR-EN-11",
        "related_adr": "ADDR-004",
        "test_category": "準拠標準（開発標準・規約）",
        "criterion": "api",
        "coverage_keys": ["CK-NFREN11-01"],
        "precondition": "商品・在庫単位・クーポン・購入者・管理者が登録済み",
        "input": "URLconf の全経路、購入者・管理者の主要 API を一巡した応答、自動テストのファイル名",
        "steps": (
            "1. URLconf を再帰的にたどって全経路のパスを収集する\n"
            "2. 各パスの固定部分と可変部分を規約（小文字・ハイフン区切り／snake_case）と照合する\n"
            "3. 会員情報照会・分類一覧・商品一覧・商品詳細・カート操作・クーポン適用・入力エラー・注文確定・"
            "注文履歴・注文詳細・支払・在庫単位一覧・注文一覧（管理者）・注文詳細（管理者）・出荷登録・"
            "配達完了登録を実行し、応答の JSON 項目名をすべて収集する\n"
            "4. 単体・結合のテストファイル名を収集する"
        ),
        "expected_result": (
            "URL パスは25件以上収集され、固定部分は小文字・ハイフン区切り（アンダースコアを含まない）、"
            "可変部分名は snake_case である。収集した JSON 項目名は40件以上で、purchase_order_id・"
            "stock_unit_id・discounted_subtotal・tracking_number を含み、すべて snake_case である。"
            "テスト関数を含むファイルはすべて test_*.py である（NFR-EN-11 の目標値）"
        ),
    },
    {
        "case_id": "IT-AI-GF-072",
        "title": "依存ライブラリのライセンスがすべて判明し AGPL を含まない",
        "requirement_id": "NFR-EN-12",
        "related_adr": "ADDR-011",
        "test_category": "技術制約（OSS・ライセンス）",
        "criterion": "api",
        "coverage_keys": ["CK-NFREN12-01"],
        "precondition": "依存定義ファイルで固定したライブラリが app のイメージへ導入されている",
        "input": "導入済み全ディストリビューションのメタデータ（License-Expression・License・分類子）",
        "steps": (
            "1. 導入済みの全ディストリビューションを列挙する\n"
            "2. 各ディストリビューションのライセンスを License-Expression・License・分類子の順に解決する\n"
            "3. 解決できないもの、AGPL に該当するものを数える\n"
            "4. 依存定義ファイルで固定した製品が導入されていることを確認する"
        ),
        "expected_result": (
            "すべての依存ライブラリでライセンスが判明し（ライセンス不明 0件）、AGPL のライブラリは0件である。"
            "Django・djangorestframework・psycopg・gunicorn・whitenoise・pytest・ruff が導入されている"
            "（NFR-EN-12 の目標値：違反件数0件）"
        ),
    },
    {
        "case_id": "IT-AI-GF-073",
        "title": "決済連携部分が注文・在庫・金額計算から分離されている",
        "requirement_id": "NFR-PF-17",
        "related_adr": "ADDR-009",
        "test_category": "拡張性（将来の拡張）",
        "criterion": "api",
        "coverage_keys": ["CK-NFRPF17-01"],
        "precondition": "購入者がログインしており、在庫単位が登録済み",
        "input": "shop/payments 配下の全モジュール、shop 配下の全モジュールの import、mock_result=approve の支払",
        "steps": (
            "1. 決済連携部分（shop/payments）の各モジュールの import を解析する\n"
            "2. shop 配下で決済連携部分を import しているモジュールを列挙する\n"
            "3. 決済要求・決済応答の項目定義を確認する\n"
            "4. 決済ゲートウェイへ渡される決済要求を記録したうえで、カート投入→注文確定→支払を実行する"
        ),
        "expected_result": (
            "決済連携部分は shop.models / shop.services / shop.api / shop.web を参照せず、利用箇所は "
            "shop/services/orders.py の1箇所だけである。決済要求は注文番号・決済金額・通貨・模擬決済指示の"
            "4項目、決済応答は結果・取引参照番号・否認理由コード・処理日時の4項目で、実際に渡される値は"
            "文字列・整数のみ（業務オブジェクトを渡さない）であり、注文番号・決済金額は支払応答と一致する"
            "（NFR-PF-17：変更範囲を連携部分のみに限定できる）"
        ),
    },
    {
        "case_id": "IT-AI-GF-074",
        "title": "秘密情報が環境変数で与えられソースに平文で存在しない",
        "requirement_id": "NFR-SC-07",
        "related_adr": "ADDR-004",
        "test_category": "暗号化（認証情報・鍵の管理）",
        "criterion": "authentication",
        "coverage_keys": ["CK-NFRSC07-01"],
        "precondition": "app サービスが環境変数（秘密鍵・DB パスワード）を与えられて稼働している",
        "input": "実行中の秘密鍵・DB パスワードの値、app に同梱される全ソース・設定・テンプレート",
        "steps": (
            "1. 秘密鍵・DB パスワードが環境変数で与えられ、Django 設定の値と一致することを確認する\n"
            "2. app に同梱される全ソース・設定・テンプレートを当該の値で走査する\n"
            "3. 環境変数を与えない状態で設定モジュールを2回読み込む\n"
            "4. DB パスワードの既定値と、2回の秘密鍵の値を比較する"
        ),
        "expected_result": (
            "秘密鍵・DB パスワードは環境変数の値と一致し、走査した50ファイル以上のいずれにも平文の混入が無い"
            "（0件）。環境変数が無い場合の DB パスワードの既定値は空文字、秘密鍵は読み込みごとに異なる32文字"
            "以上の値であり、ソースに固定値が存在しない（NFR-SC-07 の目標値：平文混入0件）"
        ),
    },
    {
        "case_id": "IT-AI-GF-075",
        "title": "画面がサーバーサイドレンダリングで SPA・ビルド工程を使わない",
        "requirement_id": "NFR-EN-09",
        "related_adr": "ADDR-004",
        "test_category": "技術制約（フレームワーク）",
        "criterion": "end-to-end-flow",
        "coverage_keys": ["CK-NFREN09-01"],
        "precondition": "商品・在庫単位・購入者が登録済み",
        "input": "リポジトリ内の定義ファイル、画面の JavaScript、商品詳細画面、カート画面とカート照会API",
        "steps": (
            "1. フロントエンドのビルド設定（package.json・各種ロックファイル・webpack/vite/rollup/babel/"
            "tsconfig の設定）と node_modules の有無を確認する\n"
            "2. 画面が読み込む JavaScript の本数と内容を確認する\n"
            "3. 商品詳細画面を要求し、HTML の内容と script タグを確認する\n"
            "4. カートへ3個投入し、カート照会APIの金額内訳とカート画面の表示を比較する"
        ),
        "expected_result": (
            "フロントエンドのビルド設定と node_modules は存在しない（0件）。画面の JavaScript は app.js の"
            "1本だけで、innerHTML・document.write・createElement・fetch・XMLHttpRequest 等を含まず、"
            "確認ダイアログと二重送信の防止だけに用いている。商品詳細画面は Django テンプレートで描画され、"
            "商品名・バリエーション名が HTML に含まれ、script タグは app.js の1本だけである。"
            "カート画面の小計・送料・消費税額・合計はカート照会APIの値と一致する（NFR-EN-09 の目標値）"
        ),
    },
    {
        "case_id": "IT-AI-GF-076",
        "title": "app サービスが Gunicorn で稼働し開発用サーバーを使用しない",
        "requirement_id": "NFR-EN-08",
        "related_adr": "ADDR-011",
        "test_category": "実行環境（ミドルウェア）",
        "criterion": "api",
        "coverage_keys": ["CK-NFREN08-01"],
        "precondition": "要件が定める実行方法（`docker compose exec app pytest`）で app サービスのコンテナ内から実行する",
        "input": "app サービスの起動プロセスのコマンドライン、WSGI エントリポイントの設定",
        "steps": (
            "1. app サービスの起動プロセスのコマンドラインを取得する\n"
            "2. 開発用サーバー（runserver）・manage.py による起動でないことを確認する\n"
            "3. WSGI サーバー（gunicorn）と提供対象（config.wsgi:application）を確認する\n"
            "4. Django 設定の WSGI_APPLICATION と呼び出し可能性を確認する"
        ),
        "expected_result": (
            "起動コマンドは gunicorn で config.wsgi:application を提供しており、runserver・manage.py の"
            "使用は0件である。WSGI_APPLICATION は config.wsgi.application で、application は呼び出し可能である"
            "（NFR-EN-08 の目標値：開発用サーバーの使用0件）"
        ),
    },
    {
        "case_id": "IT-AI-GF-077",
        "title": "DB 停止時に一部機能だけを継続する縮退運転を行わない",
        "requirement_id": "NFR-AV-10",
        "related_adr": "ADDR-007",
        "test_category": "可用性（障害時の縮退）",
        "criterion": "error-handling",
        "coverage_keys": ["CK-NFRAV10-01"],
        "precondition": "商品・在庫単位・購入者とカート明細が登録済みで、全経路が正常応答する",
        "input": "DB が応答しない状態、認証不要の照会API・認証が必要なAPI・画面の各要求",
        "steps": (
            "1. 停止前に分類一覧・商品一覧・商品詳細・カート照会・注文履歴が200で応答することを確認する\n"
            "2. DB が応答しない状態を作る\n"
            "3. 同じAPI経路と、商品一覧画面・商品詳細画面・カート画面を要求する\n"
            "4. DB を復旧させ、同じ経路を再度要求する"
        ),
        "expected_result": (
            "停止中はAPIがすべて500（INTERNAL_ERROR）、画面がすべて500のエラー画面となり、"
            "キャッシュ・代替経路による部分的な表示（データを含む表）は発生しない。"
            "復旧後は同じ経路が再び200で応答し、恒久的な代替経路へ切り替わっていない"
            "（NFR-AV-10：縮退運転を行わない）"
        ),
    },
    {
        "case_id": "IT-AI-GF-078",
        "title": "定期的に実行するバッチ処理を持たない",
        "requirement_id": "NFR-PF-12",
        "related_adr": "ADDR-010",
        "test_category": "性能（バッチ処理）",
        "criterion": "database",
        "coverage_keys": ["CK-NFRPF12-01"],
        "precondition": "app のイメージが稼働しており、購入者・在庫単位が登録済み",
        "input": "導入済みライブラリ、コンテナの cron 定義、shop の管理コマンド、注文日が8年前の注文",
        "steps": (
            "1. 定期実行のライブラリ（celery・apscheduler・schedule・rq・django-crontab 等）の導入状況を確認する\n"
            "2. コンテナの cron 定義（/etc/crontab・/etc/cron.d）を確認する\n"
            "3. shop が提供する管理コマンドを列挙し、引数なしでの実行を試みる\n"
            "4. 注文を1件確定して注文日を8年前に変更し、以後の照会・カート操作・注文確定を行う"
        ),
        "expected_result": (
            "定期実行のライブラリは0件、cron の定義も存在しない。shop の管理コマンドは初期データ一括投入の"
            "1つだけで、定義ファイルの指定が無い実行は終了コード0以外で失敗する。注文日が8年前の注文は"
            "自動削除されず、注文詳細を200で照会できる（NFR-PF-12：定期バッチ・自動キャンセル・"
            "保存期間経過データの自動削除を持たない）"
        ),
    },
    {
        "case_id": "IT-AI-GF-079",
        "title": "注文関連の帳簿書類が書き換えも削除もされない",
        "requirement_id": "NFR-LG-03",
        "related_adr": "ADDR-001",
        "test_category": "法令（帳簿書類の保存）",
        "criterion": "database",
        "coverage_keys": ["CK-NFRLG03-01"],
        "precondition": "購入者がログインしており、2件の在庫単位が登録済み",
        "input": "2明細の注文確定→支払（承認）→キャンセル、注文を削除する DELETE 要求",
        "steps": (
            "1. 2明細をカートへ投入して注文確定し、支払（承認）を行う\n"
            "2. 注文・注文明細・配送先・決済記録・注文状態履歴の内容を記録する\n"
            "3. 注文をキャンセルする\n"
            "4. 2で記録した内容と比較する\n"
            "5. 注文に対する DELETE 要求を送信し、記録の残存と注文詳細の照会可否を確認する"
        ),
        "expected_result": (
            "キャンセル後も注文・注文明細2件・配送先・決済記録1件（承認）はすべて残り、注文番号・金額内訳・"
            "注文日時・支払日時・明細の数量と金額・配送先・決済結果・取引参照番号・処理日時は書き換わらない。"
            "注文状態履歴は既存の2件を保ったまま「支払済→キャンセル済」が追記される。DELETE 要求はいずれも"
            "成功せず（2xx を返さない）、キャンセル後も注文詳細を200で照会でき明細2件と合計金額が一致する"
            "（NFR-LG-03：登録後に更新・削除しない）"
        ),
    },
    {
        "case_id": "IT-AI-GF-080",
        "title": "想定を超える同時要求でも在庫・注文状態・金額の不整合が生じない",
        "requirement_id": "NFR-PF-11",
        "related_adr": "ADDR-001",
        "test_category": "同時利用者（上限超過時の挙動）",
        "criterion": "state-transition",
        "coverage_keys": ["CK-NFRPF11-01"],
        "precondition": "在庫3の在庫単位4件（合計12個）、カート明細を持つ購入者24名、500円割引クーポン",
        "input": "24件の同時注文確定（半数はクーポン適用済み）、成立した注文への同時の支払・キャンセル",
        "steps": (
            "1. 在庫3の在庫単位4件と、各在庫単位に数量1のカート明細を持つ購入者24名を用意し、"
            "半数にクーポンを適用する\n"
            "2. 24件の注文確定を同時に送信する\n"
            "3. 応答のHTTPステータスとエラーコードを集計する\n"
            "4. 成立した注文に対して支払・キャンセルを同時に要求する\n"
            "5. 在庫数量・注文の金額内訳・明細・引当合計を確認する"
        ),
        "expected_result": (
            "すべての要求が正常応答または業務エラー応答で、システムエラー（HTTP 500・INTERNAL_ERROR）は0件。"
            "成立した注文は在庫の総数と同じ12件で、在庫数量が0未満の在庫単位は0件。全注文が"
            "割引後小計＝小計−割引額、合計＝割引後小計＋送料＋消費税額、小計＝明細金額の合計、"
            "明細金額＝単価×数量を満たし、注文状態は定義された5状態のいずれかである。"
            "各在庫単位で在庫数量＋未キャンセルの引当数量＝初期の在庫数量3が成立する"
            "（NFR-PF-11 の目標値のうち、負荷の測定条件によらない不変条件）"
        ),
    },
]


def gap_ids(cases: list[dict]) -> dict[str, str]:
    """Required Coverage の MISSING 一覧から coverage_key ごとの Gap ID を導出する。"""
    required = json.loads((REPORT_DIR / "required-coverage.json").read_text(encoding="utf-8"))
    initial = json.loads((REPORT_DIR / "ai-initial-cases.json").read_text(encoding="utf-8"))["cases"]
    covered: set[str] = set()
    for case in initial:
        covered.update(case.get("coverage_keys") or [case["coverage_key"]])
    missing = sorted({item["coverage_key"] for item in required["required_coverage"]} - covered)
    return {key: f"GAP-{index:03d}" for index, key in enumerate(missing, start=1)}


def main() -> int:
    """GAP_FILL Case を追記し、gap_id を現在の Required Coverage に合わせる。"""
    document = json.loads(PATH.read_text(encoding="utf-8"))
    existing = {case["case_id"] for case in document["cases"]}
    added = [case for case in NEW_CASES if case["case_id"] not in existing]
    for case in added:
        document["cases"].append(
            {
                "case_id": case["case_id"],
                "origin": "AI_GENERATED",
                "generation_stage": "GAP_FILL",
                "gap_id": None,
                "title": case["title"],
                "requirement_id": case["requirement_id"],
                "related_adr": case["related_adr"],
                "test_category": case["test_category"],
                "criterion": case["criterion"],
                "coverage_keys": case["coverage_keys"],
                "precondition": case["precondition"],
                "input": case["input"],
                "steps": case["steps"],
                "expected_result": case["expected_result"],
                "execution_type": AUTOMATABLE,
            }
        )

    mapping = gap_ids(document["cases"])
    for case in document["cases"]:
        case["gap_id"] = mapping.get(case["coverage_keys"][0], case.get("gap_id"))

    document["note"] = (
        "Coverage Gap Analysis（case-comparison.json / coverage-gap-report.json）で MISSING と判定された "
        "Required Coverage を補うために追加した Test Case。IT-AI-GF-001〜011 は初回の Gap Fill、"
        "IT-AI-GF-012〜028 は repair cycle 1 で Required Coverage の導出元を是正（NFR-SC の検証方法・"
        "UC の同時実行観点を追加）した結果の Gap Fill、IT-AI-GF-029〜069 は Traceability Audit の C10"
        "（テストされていない要件）是正として、対象外機能（FR-OUT-01〜16）と結合試験で検証できる非機能要件を"
        "補う Gap Fill、IT-AI-GF-070〜080 は C10 の再精査（修正2回目）で、自動テスト対象外としていた 74 件を"
        "要件本文の検証方法欄で個別に再精査し、結合試験環境の中に解析・判定の対象が存在する 11 件"
        "（静的解析6・構成設定2・該当なし2・性能1）を補う Gap Fill。"
        "AI INITIAL Case（ai-initial-cases.json、snapshot initial-1）は変更していない。"
        "gap_id は Required Coverage の MISSING 一覧から毎回導出する参照値であり、追加に伴い付け直している"
        "（各ケースの内容・期待結果は変更していない）。"
    )
    document["derived_from"] = sorted(
        set(document.get("derived_from", []))
        | {"docs/requirements/non_functional_requirements.md 5章・6章・8章・10章・11章（検証方法欄の再精査）"}
    )
    PATH.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"追加: {len(added)} 件 / 合計: {len(document['cases'])} 件")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
