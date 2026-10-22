# trace: NFR-EN-08, NFR-EN-09, NFR-EN-11, NFR-EN-12, NFR-OM-07, NFR-PF-17, NFR-SC-07
# trace: FR-001, FR-002, FR-004, FR-010, FR-011, FR-012, FR-020, FR-021, FR-024, FR-026
# trace: FR-030, FR-031, FR-032, FR-033, FR-040, FR-041, FR-043, FR-044
# trace: ADDR-004, ADDR-007, ADDR-009, ADDR-011, ADDR-012
"""開発標準・技術制約・秘密情報の取り扱いに関する非機能要件の結合試験。

期待結果は非機能要件定義書 10章（NFR-EN-08 ミドルウェア、NFR-EN-09 フレームワーク、
NFR-EN-11 開発標準・規約、NFR-EN-12 OSS・ライセンス）、6章（NFR-OM-07 コード品質）、
5章（NFR-PF-17 将来の拡張）、8章（NFR-SC-07 認証情報・鍵の管理）の
「要件内容」「目標値」「検証方法」欄から導出する。

いずれも要件本文の検証方法が「静的解析・コードレビュー」であり、解析対象（app の全 Python
ソースコード・依存ライブラリ・画面の JavaScript・起動設定）が結合試験環境の中に存在するため、
解析をテストとして実行して判定する。要件本文が「構成・設定レビュー」と定める事項のうち、
compose.yaml・README.md などリポジトリ直下の資料は app イメージへ同梱されないため対象としない
（reports/integration-test/non-automatable-requirements.md に理由を記録している）。

本ファイルのテストは、要件が定める実行方法（NFR-OM-06 `docker compose exec app pytest`）どおり、
app サービスのコンテナ内で実行することを前提とする。
"""
import ast
import importlib.metadata
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest
from django.conf import settings
from django.test import Client
from django.urls import get_resolver

from shop.payments import mock as payment_mock
from shop.payments.gateway import PaymentRequest, PaymentResponse
from tests.integration import _helpers

pytestmark = pytest.mark.django_db

# app のソースツリーの根（コンテナ内では /app）。
APP_ROOT = Path(settings.BASE_DIR)

# 解析から除外するディレクトリ（収集済みの第三者資産・キャッシュ・出力先）。
EXCLUDED_DIRS = {"staticfiles", "__pycache__", ".ruff_cache", ".pytest_cache", "reports", "migrations"}

# 本文を走査する対象の拡張子。
TEXT_SUFFIXES = {".py", ".html", ".css", ".js", ".json", ".toml", ".cfg", ".ini", ".txt", ".md", ".yaml", ".yml"}

# API の JSON 項目名の規約（NFR-EN-11 の目標値：snake_case）。
SNAKE_CASE = re.compile(r"^[a-z][a-z0-9_]*$")

# URL パスの規約（NFR-EN-11 の目標値：小文字・ハイフン区切り）。
URL_SEGMENT = re.compile(r"^[a-z0-9-]*$")

# URL の可変部分（`<str:purchase_order_id>` 形式）。
URL_CONVERTER = re.compile(r"^<(?P<converter>[a-z_]+):(?P<name>[a-z][a-z0-9_]*)>$")

# 利用条件を満たせないライセンス（NFR-EN-12：AGPL を使わない）。
FORBIDDEN_LICENSE = re.compile(r"\bA-?GPL", re.IGNORECASE)

# 決済連携の境界が参照してはならない業務処理（NFR-PF-17：注文・在庫・金額計算から分離する）。
BUSINESS_PACKAGES = ("shop.models", "shop.services", "shop.api", "shop.web")

# 決済要求・決済応答の項目（IF-01-DAT-01〜08。NFR-PF-17 の検証方法が挙げる項目）。
PAYMENT_REQUEST_FIELDS = ("order_number", "amount", "currency", "mock_result")
PAYMENT_RESPONSE_FIELDS = ("result", "transaction_ref", "declined_reason_code", "processed_at")

# 画面の JavaScript に現れてはならない記述（NFR-EN-09：画面の描画に用いない）。
FORBIDDEN_JS = (
    "innerHTML",
    "outerHTML",
    "insertAdjacentHTML",
    "document.write",
    "createElement",
    "appendChild",
    "XMLHttpRequest",
    "fetch(",
    "import(",
    "React",
    "Vue",
    "angular",
)

# フロントエンドのビルド工程を示す定義ファイル（NFR-EN-09：使わない）。
FRONTEND_BUILD_FILES = (
    "package.json",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "webpack.config.js",
    "vite.config.js",
    "vite.config.ts",
    "rollup.config.js",
    "babel.config.js",
    ".babelrc",
    "tsconfig.json",
)

# 秘密情報を与える環境変数（NFR-SC-07 の対象：アプリケーションの秘密鍵・DB のパスワード）。
SECRET_ENV_VARS = ("DJANGO_SECRET_KEY", "DB_PASSWORD")


# trace: NFR-OM-07, NFR-EN-11
def _ruff(*arguments: str) -> subprocess.CompletedProcess:
    """app のソースツリーに対して ruff を実行する（NFR-OM-07 の検証方法のコマンド）。"""
    return subprocess.run(  # noqa: S603
        [sys.executable, "-m", "ruff", "check", "--no-cache", *arguments, "."],
        cwd=str(APP_ROOT),
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )


# trace: NFR-SC-07, NFR-EN-09
def _source_files() -> list[Path]:
    """app に同梱されるソース・設定・テンプレートのファイル一覧を返す。"""
    files = []
    for path in APP_ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in EXCLUDED_DIRS for part in path.relative_to(APP_ROOT).parts):
            continue
        if path.suffix.lower() in TEXT_SUFFIXES:
            files.append(path)
    return files


# trace: NFR-PF-17
def _imported_modules(path: Path) -> set[str]:
    """Python ファイルが import しているモジュール名の集合を返す。"""
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module)
    return names


# trace: NFR-EN-11
def _routes() -> list[str]:
    """URLconf に登録された全経路（URL パス）を返す。"""
    found: list[str] = []

    def walk(patterns, prefix: str) -> None:
        """URL パターンを再帰的にたどる。"""
        for entry in patterns:
            route = getattr(entry.pattern, "_route", None)
            if route is None:
                continue
            full = prefix + route
            children = getattr(entry, "url_patterns", None)
            if children is None:
                found.append(full)
            else:
                walk(children, full)

    walk(get_resolver().url_patterns, "")
    return found


# trace: NFR-EN-11
def _json_keys(payload, collected: set[str]) -> set[str]:
    """JSON 本文に現れる項目名をすべて集める。"""
    if isinstance(payload, dict):
        for key, value in payload.items():
            collected.add(key)
            _json_keys(value, collected)
    elif isinstance(payload, list):
        for value in payload:
            _json_keys(value, collected)
    return collected


# trace: FR-030, FR-031
def _exercise_api(api) -> list[dict]:
    """購入者・管理者の主要な API を一巡し、応答本文（JSON）の一覧を返す。"""
    collection = _helpers.make_collection()
    item = _helpers.make_item(collections=[collection])
    supplier = _helpers.make_supplier()
    unit = _helpers.make_stock_unit(item, supplier, price=3000, quantity=10)
    _helpers.make_coupon()
    _helpers.make_user()
    _helpers.make_admin()

    bodies = []

    def call(response):
        """応答本文を記録して返す。"""
        bodies.append(response.json())
        return response

    buyer = api.login("buyer@example.com")
    admin = api.login("admin@example.com")

    call(api.get("/api/auth/me", token=buyer))
    call(api.get("/api/collections"))
    call(api.get("/api/items"))
    call(api.get(f"/api/items/{item.item_id}"))
    call(api.post("/api/cart/lines", {"stock_unit_id": unit.stock_unit_id, "quantity": 2}, token=buyer))
    call(api.get("/api/cart", token=buyer))
    call(api.post("/api/cart/apply-coupon", {"code": "SAVE1000"}, token=buyer))
    # 入力エラー応答の項目名（details の field）も規約の対象に含める。
    call(api.post("/api/cart/lines", {"stock_unit_id": unit.stock_unit_id, "quantity": 99}, token=buyer))
    order_id = call(api.post("/api/checkout", dict(_helpers.VALID_ADDRESS), token=buyer)).json()[
        "purchase_order_id"
    ]
    call(api.get("/api/purchase-orders", token=buyer))
    call(api.get(f"/api/purchase-orders/{order_id}", token=buyer))
    call(api.post(f"/api/purchase-orders/{order_id}/pay", {"mock_result": "approve"}, token=buyer))
    call(api.get("/api/admin/stock-units", token=admin))
    call(api.get("/api/admin/purchase-orders", token=admin))
    call(api.get(f"/api/admin/purchase-orders/{order_id}", token=admin))
    call(api.post(f"/api/admin/purchase-orders/{order_id}/ship", {"tracking_number": "TRK-0001"}, token=admin))
    call(api.post(f"/api/admin/purchase-orders/{order_id}/deliver", {}, token=admin))
    return bodies


# trace: NFR-OM-07, NFR-EN-11, ADDR-012
@pytest.mark.case("IT-AI-GF-070")
def test_application_source_passes_static_analysis_with_no_findings():
    """app の全 Python ソースコードが ruff の指摘0件である（NFR-OM-07、NFR-EN-11 の PEP 8）。"""
    listed = _ruff("--show-files")
    assert listed.returncode == 0, listed.stderr
    analysed = [line.strip() for line in listed.stdout.splitlines() if line.strip()]

    # 解析対象が空（＝何も確認していない）でないことを先に確かめる。
    assert len(analysed) >= 50, f"解析対象が少なすぎる: {len(analysed)}件"
    for required in ("shop/services/orders.py", "shop/api/views_orders.py", "config/settings.py"):
        assert any(path.endswith(required) for path in analysed), f"{required} が解析対象に含まれていない"
    # ENV-01 のテスト用マウント（/app/tests）は app のソースではないため対象外（ADDR-012 DD-001）。
    assert not any("/app/tests/" in path for path in analysed)

    result = _ruff("--output-format", "json")
    findings = json.loads(result.stdout or "[]")
    assert findings == [], [
        f"{finding['filename']}:{finding.get('location', {}).get('row')}: {finding['code']} {finding['message']}"
        for finding in findings
    ]
    assert result.returncode == 0, result.stderr


# trace: NFR-EN-11, FR-001, FR-011, FR-020, FR-030, FR-031, FR-040, FR-041, ADDR-004, ADDR-007
@pytest.mark.case("IT-AI-GF-071")
def test_url_json_and_test_file_names_follow_the_defined_conventions(api):
    """URL パス・API の JSON 項目名・テストファイル名が規約どおりである（NFR-EN-11 の目標値）。"""
    routes = _routes()
    assert len(routes) >= 25, f"URL の収集に失敗している: {routes}"
    assert "api/purchase-orders/<str:purchase_order_id>/pay" in routes
    for route in routes:
        for segment in [part for part in route.split("/") if part]:
            converter = URL_CONVERTER.match(segment)
            if converter:
                assert SNAKE_CASE.match(converter.group("name")), f"{route}: 可変部分名が snake_case でない"
                continue
            assert URL_SEGMENT.match(segment), f"{route}: URL パスが小文字・ハイフン区切りでない"
            assert "_" not in segment, f"{route}: URL パスにアンダースコアが含まれる"

    keys: set[str] = set()
    for body in _exercise_api(api):
        _json_keys(body, keys)
        if isinstance(body, dict) and "error" in body:
            for detail in body["error"].get("details") or []:
                keys.add(detail["field"].split(".")[-1])
    # 主要な業務項目が実際に収集できていることを確かめる（空集合での素通りを防ぐ）。
    assert len(keys) >= 40, f"収集した JSON 項目名が少なすぎる: {sorted(keys)}"
    assert {"purchase_order_id", "stock_unit_id", "discounted_subtotal", "tracking_number"} <= keys
    for key in sorted(keys):
        assert SNAKE_CASE.match(key), f"API の JSON 項目名が snake_case でない: {key}"

    test_modules = []
    for directory in (APP_ROOT / "shop" / "tests", APP_ROOT / "tests"):
        assert directory.is_dir(), f"{directory} が存在しない"
        for path in sorted(directory.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            if re.search(r"^def test_", path.read_text(encoding="utf-8"), re.MULTILINE):
                test_modules.append(path)
    assert len(test_modules) >= 20, f"テストファイルの収集に失敗している: {len(test_modules)}件"
    for path in test_modules:
        assert path.name.startswith("test_") and path.suffix == ".py", f"テストファイル名が規約外: {path}"


# trace: NFR-EN-12, ADDR-011
@pytest.mark.case("IT-AI-GF-072")
def test_every_dependency_has_a_known_non_agpl_license():
    """依存ライブラリのライセンスがすべて判明し、AGPL が含まれない（NFR-EN-12 の目標値：違反0件）。"""
    resolved: dict[str, str] = {}
    for distribution in importlib.metadata.distributions():
        name = distribution.metadata["Name"]
        if not name:
            continue
        expression = distribution.metadata.get("License-Expression")
        declared = distribution.metadata.get("License")
        classifiers = [
            value.split("::")[-1].strip()
            for value in (distribution.metadata.get_all("Classifier") or [])
            if value.startswith("License ::")
        ]
        license_text = expression or (declared if declared and len(declared) < 200 else None)
        if not license_text and classifiers:
            license_text = " / ".join(classifiers)
        assert license_text, f"{name} のライセンスが判明しない（ライセンス不明のライブラリは使わない）"
        resolved[name] = license_text

    # 依存定義ファイル（requirements.txt）で固定した製品が実際に導入されていることを確かめる。
    for required in ("Django", "djangorestframework", "psycopg", "gunicorn", "whitenoise", "pytest", "ruff"):
        assert required in resolved, f"{required} が導入されていない"

    violations = {name: text for name, text in resolved.items() if FORBIDDEN_LICENSE.search(text)}
    assert violations == {}, f"AGPL のライブラリが含まれる: {violations}"


# trace: NFR-PF-17, FR-031, ADDR-009
@pytest.mark.case("IT-AI-GF-073")
def test_payment_integration_is_isolated_from_order_stock_and_amount_logic(api, monkeypatch):
    """決済連携部分が独立し、決済要求・決済応答の項目だけで業務処理と結び付く（NFR-PF-17）。"""
    payment_modules = sorted(
        path for path in (APP_ROOT / "shop" / "payments").rglob("*.py") if "__pycache__" not in path.parts
    )
    assert len(payment_modules) >= 3, f"決済連携部分のモジュールが見つからない: {payment_modules}"
    for path in payment_modules:
        for name in _imported_modules(path):
            assert not name.startswith(BUSINESS_PACKAGES), f"{path.name} が業務処理 {name} を参照している"

    importers = set()
    for path in sorted((APP_ROOT / "shop").rglob("*.py")):
        parts = path.relative_to(APP_ROOT).parts
        if "__pycache__" in parts or "payments" in parts or "tests" in parts:
            continue
        if any(name.startswith("shop.payments") for name in _imported_modules(path)):
            importers.add("/".join(parts))
    assert importers == {"shop/services/orders.py"}, f"決済連携部分の利用箇所が分離されていない: {importers}"

    assert tuple(PaymentRequest.__dataclass_fields__) == PAYMENT_REQUEST_FIELDS
    assert tuple(PaymentResponse.__dataclass_fields__) == PAYMENT_RESPONSE_FIELDS

    captured: list[PaymentRequest] = []
    original = payment_mock.MockPaymentGateway.authorize

    def capture(self, request):
        """決済要求を記録して模擬実装へ委譲する。"""
        captured.append(request)
        return original(self, request)

    monkeypatch.setattr(payment_mock.MockPaymentGateway, "authorize", capture)

    _helpers.make_user()
    item, unit = _helpers.catalog(price=2500, quantity=5)
    token = api.login("buyer@example.com")
    assert api.post(
        "/api/cart/lines", {"stock_unit_id": unit.stock_unit_id, "quantity": 2}, token=token
    ).status_code == 200
    order_id = api.post("/api/checkout", dict(_helpers.VALID_ADDRESS), token=token).json()["purchase_order_id"]
    paid = api.post(f"/api/purchase-orders/{order_id}/pay", {"mock_result": "approve"}, token=token)
    assert paid.status_code == 200, paid.content

    assert len(captured) == 1
    request = captured[0]
    assert isinstance(request, PaymentRequest)
    assert tuple(vars(request)) == PAYMENT_REQUEST_FIELDS
    # 注文・在庫・金額計算のオブジェクトを境界の向こう側へ渡していない。
    for value in vars(request).values():
        assert isinstance(value, str | int), f"決済要求に業務オブジェクトが含まれる: {type(value)}"
    assert request.order_number == paid.json()["order_number"]
    assert request.amount == paid.json()["amounts"]["total"]
    assert request.currency == "JPY"


# trace: NFR-SC-07, ADDR-004, ADDR-011
@pytest.mark.case("IT-AI-GF-074")
def test_secrets_are_given_by_environment_and_absent_from_the_source_tree():
    """秘密情報が環境変数で与えられ、ソースコード・設定ファイルに平文で存在しない（NFR-SC-07：0件）。"""
    values = {}
    for name in SECRET_ENV_VARS:
        value = os.environ.get(name)
        assert value, f"{name} が環境変数で与えられていない"
        values[name] = value
    assert settings.SECRET_KEY == values["DJANGO_SECRET_KEY"]
    assert settings.DATABASES["default"]["PASSWORD"] == values["DB_PASSWORD"]

    scanned = _source_files()
    assert len(scanned) >= 50, f"走査対象が少なすぎる: {len(scanned)}件"
    assert any(path.name == "settings.py" for path in scanned)
    for path in scanned:
        text = path.read_text(encoding="utf-8", errors="ignore")
        for name, value in values.items():
            assert value not in text, f"{path.relative_to(APP_ROOT)} に {name} の値が含まれている"

    # 環境変数を与えずに設定を読み込んでも、秘密情報の既定値が現れないことを確かめる。
    def load_settings():
        """config/settings.py を環境変数なしで読み込む。"""
        spec = importlib.util.spec_from_file_location("settings_probe", APP_ROOT / "config" / "settings.py")
        module = importlib.util.module_from_spec(spec)
        with mock.patch.dict(os.environ, {}, clear=True):
            spec.loader.exec_module(module)
        return module

    first, second = load_settings(), load_settings()
    assert first.DATABASES["default"]["PASSWORD"] == "", "DB パスワードの既定値がソースに書かれている"
    assert first.SECRET_KEY != second.SECRET_KEY, "秘密鍵の固定値がソースに書かれている"
    assert values["DJANGO_SECRET_KEY"] not in (first.SECRET_KEY, second.SECRET_KEY)
    assert len(first.SECRET_KEY) >= 32


# trace: NFR-EN-09, FR-011, FR-012, FR-020, FR-026, ADDR-004
@pytest.mark.case("IT-AI-GF-075")
def test_screens_are_server_rendered_without_spa_or_frontend_build(api):
    """画面が Django テンプレートのサーバーサイドレンダリングで、SPA・ビルド工程を使わない（NFR-EN-09）。"""
    for name in FRONTEND_BUILD_FILES:
        found = [path for path in APP_ROOT.rglob(name) if "staticfiles" not in path.parts]
        assert found == [], f"フロントエンドのビルド設定が存在する: {found}"
    assert not (APP_ROOT / "node_modules").exists()

    scripts = sorted(
        path for path in (APP_ROOT / "shop" / "static").rglob("*.js") if "__pycache__" not in path.parts
    )
    assert [path.name for path in scripts] == ["app.js"], f"画面の JavaScript が1ファイルでない: {scripts}"
    source = scripts[0].read_text(encoding="utf-8")
    for forbidden in FORBIDDEN_JS:
        assert forbidden not in source, f"画面の描画・通信に JavaScript を用いている: {forbidden}"
    # 用途は確認ダイアログ（NFR-US-09）と二重送信の防止（NFR-US-10）に限る。
    assert "window.confirm" in source
    assert "data-submit-once" in source

    collection = _helpers.make_collection()
    item = _helpers.make_item(name="サーバー描画確認商品", collections=[collection])
    supplier = _helpers.make_supplier()
    unit = _helpers.make_stock_unit(item, supplier, price=4000, quantity=7)
    _helpers.make_user()

    screen = Client()
    detail = screen.get(f"/items/{item.item_id}")
    assert detail.status_code == 200
    assert detail["Content-Type"].startswith("text/html")
    # Django テンプレートで描画されている（SPA のブートストラップ HTML ではない）。
    assert [template.name for template in detail.templates if template.name]
    html = detail.content.decode("utf-8")
    assert item.name in html, "商品名が HTML に含まれていない（描画を JavaScript に委ねている）"
    assert unit.variant_name in html
    # 画面が読み込む JavaScript は app.js の1本だけ（WhiteNoise のハッシュ付き名を含む）。
    assert len(re.findall(r"<script", html)) == 1
    assert re.search(r'<script src="/static/web/app(\.[0-9a-f]+)?\.js" defer></script>', html), html[-400:]

    # 画面と API が同じ業務ロジック（金額計算）を使う。
    token = api.login("buyer@example.com")
    assert api.post(
        "/api/cart/lines", {"stock_unit_id": unit.stock_unit_id, "quantity": 3}, token=token
    ).status_code == 200
    amounts = api.get("/api/cart", token=token).json()["amounts"]
    screen.post("/login", {"email": "buyer@example.com", "password": _helpers.TEST_PASSWORD})
    cart_html = screen.get("/cart").content.decode("utf-8")
    for key in ("subtotal", "shipping_fee", "tax_amount", "total"):
        assert f"{amounts[key]:,}" in cart_html, f"画面と API で {key} が一致しない"


# trace: NFR-EN-08, ADDR-011, ADDR-012
@pytest.mark.case("IT-AI-GF-076")
def test_app_service_is_served_by_a_production_wsgi_server():
    """app サービスが Gunicorn で起動し、Django 付属の開発用サーバーを使用していない（NFR-EN-08：0件）。"""
    cmdline = Path("/proc/1/cmdline").read_bytes().decode("utf-8", errors="ignore")
    arguments = [value for value in cmdline.split("\0") if value]
    assert arguments, "app サービスの起動コマンドを取得できない"

    joined = " ".join(arguments)
    assert "runserver" not in joined, f"開発用サーバーで起動している: {joined}"
    assert "manage.py" not in joined, f"manage.py で起動している: {joined}"
    assert any("gunicorn" in value for value in arguments), f"WSGI サーバーで起動していない: {joined}"
    assert "config.wsgi:application" in joined

    assert settings.WSGI_APPLICATION == "config.wsgi.application"
    from config.wsgi import application

    assert callable(application)
