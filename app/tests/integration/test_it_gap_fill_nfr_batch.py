# trace: FR-060, FR-002, FR-030, FR-031, NFR-PF-10, NFR-MG-01, NFR-MG-02, NFR-MG-03, NFR-MG-04, NFR-MG-07
# trace: NFR-MG-08, NFR-OM-04, NFR-OM-11, NFR-OM-13, NFR-OM-17, NFR-EN-01, NFR-EN-02, NFR-EN-09
# trace: ADDR-007, ADDR-009, ADDR-010, ADDR-011, ADDR-013, ADDR-014
"""結合試験：AI GAP_FILL（運用・移行・環境の非機能要件のうち結合試験で自動検証できる範囲。Revision 2）。

GF-024〜GF-027・GF-035（origin=AI_GENERATED、generation_stage=GAP_FILL）。AI INITIAL は変更しない。
期待結果は NFR-PF-10・NFR-MG-01〜04/07/08・NFR-OM-04/11/13/17・NFR-EN-01/02/09 の測定条件・検証方法と、
ADDR-009・ADDR-010（定義ファイル・起動手段）・ADDR-013（ログ）・ADDR-014（設定・実行環境）から導出する。
本番環境・本番の定義ファイル・保管期間・運用手順に依存する部分は検証しない（nfr-verification-scope.json に記録）。
定義ファイル・認証情報はすべて架空の値で作る。
"""

import json
import os
import re
import secrets
import subprocess
import sys
import time
from pathlib import Path

import pytest
from django.core.management import execute_from_command_line

from tests.integration._helpers import PASSWORD, add_item, api, body, order_of, pay, place

pytestmark = pytest.mark.django_db(transaction=True)

APP_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = APP_DIR.parent
_COUNT = re.compile(r"(商品分類所属|商品分類|在庫単位|クーポン|利用者|仕入先|商品)\D{0,4}?(\d+)")


# trace: FR-060, ADDR-010
def _cli(capsys, *args):
    """`manage.py load_initial_data ...` を実行し (終了コード, 通知, JSON ログ行, 標準エラー) を返す。"""
    capsys.readouterr()
    code = 0
    try:
        execute_from_command_line(["manage.py", "load_initial_data", *args])
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
    captured = capsys.readouterr()
    lines = captured.out.splitlines()
    logs = [json.loads(line) for line in lines if line.startswith('{"timestamp"')]
    notice = "\n".join(line for line in lines if not line.startswith('{"timestamp"'))
    return code, notice, logs, captured.err


# trace: FR-060, ADDR-009
def _write(tmp_path, name, data):
    path = tmp_path / name
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return str(path)


# trace: FR-060, ADDR-010
def _counts():
    from accounts.models import User
    from carts.models import Cart, CartItem
    from catalog.models import Category, Product, ProductCategory, StockUnit, Supplier
    from orders.models import Order, OrderItem, OrderStatusHistory, PaymentRecord, ShippingAddress
    from promotions.models import Coupon

    models = (
        User,
        Supplier,
        Category,
        Product,
        ProductCategory,
        StockUnit,
        Coupon,
        Cart,
        CartItem,
        Order,
        OrderItem,
        ShippingAddress,
        PaymentRecord,
        OrderStatusHistory,
    )
    return {m.__name__: m.objects.count() for m in models}


# trace: NFR-MG-02, NFR-MG-08, NFR-PF-10, ADDR-009
def _vdc04_definition():
    """VDC-04 と同じ件数構成（管理者7・仕入先20・商品分類30・商品300・在庫単位800）の架空の定義ファイル。"""
    users = [
        {
            "email": f"rehearsal.admin{i:02d}@example.test",
            "password": f"Rehearsal{i:02d}Pass",
            "name": f"移行 管理者{i:02d}",
            "user_type": "admin",
        }
        for i in range(1, 8)
    ]
    suppliers = [{"supplier_code": f"SUP-R{i:03d}", "name": f"架空仕入先{i:03d}"} for i in range(1, 21)]
    categories = [
        {"category_code": f"r-top-{i:02d}", "name": f"大分類{i:02d}", "display_order": i} for i in range(1, 11)
    ]
    categories += [
        {
            "category_code": f"r-sub-{i:02d}",
            "name": f"小分類{i:02d}",
            "parent_category_code": f"r-top-{(i - 1) % 10 + 1:02d}",
            "display_order": i,
        }
        for i in range(1, 21)
    ]
    products = [
        {
            "product_code": f"R-P{i:04d}",
            "name": f"移行商品{i:04d}",
            "description": "移行リハーサル用の架空の商品です。",
            "category_codes": [f"r-sub-{(i - 1) % 20 + 1:02d}"],
            "registered_at": "2027-03-01T10:00:00+09:00",
            **({"visibility": "private"} if i % 50 == 0 else {}),
        }
        for i in range(1, 301)
    ]
    stock_units = [
        {
            "sku": f"R-P{(i - 1) % 300 + 1:04d}-{(i - 1) // 300 + 1:02d}",
            "product_code": f"R-P{(i - 1) % 300 + 1:04d}",
            "supplier_code": f"SUP-R{(i - 1) % 20 + 1:03d}",
            "variant_name": f"規格{(i - 1) // 300 + 1}",
            "price_excluding_tax": 500 + (i % 40) * 50,
            "stock_quantity": i % 30,
        }
        for i in range(1, 801)
    ]
    return {
        "users": users,
        "suppliers": suppliers,
        "categories": categories,
        "products": products,
        "stock_units": stock_units,
    }


# trace: NFR-PF-10, NFR-MG-01, NFR-MG-02, NFR-MG-03, NFR-MG-04, NFR-MG-08, NFR-OM-04, FR-060, ADDR-009, ADDR-010
def test_gf_024_vdc04_rehearsal(api_client, buyer, bearer, catalog, tmp_path, capsys):
    """GF-024 VDC-04 相当の初期データを注文作成後の環境へ --reset で1回の実行で投入（移行リハーサル）。"""
    from accounts.models import User
    from audit.models import AuditLog
    from catalog.models import Category, Product, StockUnit, Supplier

    token = bearer(buyer)
    unit = catalog.stock_unit(stock=10)
    order = order_of(api_client, token, [(unit, 1)])
    assert pay(api_client, token, order["order_id"], "approved").status_code == 200
    assert add_item(api_client, token, unit.pk, 1).status_code == 200
    assert (
        api(api_client, "post", "/api/auth/login/", data={"email": buyer.email, "password": "Wrong0Pass"}).status_code
        == 401
    )
    definition = _vdc04_definition()
    assert sum(len(v) for v in definition.values()) == 1157
    rejected = _write(tmp_path, "with-orders.json", {**definition, "orders": [{"order_number": "PO-00000001"}]})
    failures = AuditLog.objects.filter(event_type="initial_data_load", result="failure").count()
    code, _, _, err = _cli(capsys, rejected, "--reset")
    assert code == 1 and "失敗" in err
    assert _counts()["Order"] == 1
    assert AuditLog.objects.filter(event_type="initial_data_load", result="failure").count() == failures + 1

    # 移行リハーサル（--reset 指定の1回の実行）の直前の監査ログ
    audit_before = set(AuditLog.objects.values_list("pk", flat=True))
    assert audit_before
    path = _write(tmp_path, "vdc04.json", definition)
    start = time.monotonic()
    code, notice, logs, err = _cli(capsys, path, "--reset")
    elapsed = time.monotonic() - start
    assert code == 0, err
    assert elapsed <= 60.0, f"初期データ一括投入 {elapsed:.1f} 秒（目標 60 秒以内）"
    shown = {label: int(n) for label, n in _COUNT.findall(notice)}
    expected = {
        "利用者": 7,
        "仕入先": 20,
        "商品分類": 30,
        "商品": 300,
        "商品分類所属": 300,
        "在庫単位": 800,
        "クーポン": 0,
    }
    assert shown == expected, notice
    job = [r for r in logs if r["log_type"] == "LOG-05"]
    assert len(job) == 1 and job[0]["result"] == "success"

    counts = _counts()
    assert counts == {
        "User": 7,
        "Supplier": 20,
        "Category": 30,
        "Product": 300,
        "ProductCategory": 300,
        "StockUnit": 800,
        "Coupon": 0,
        "Cart": 0,
        "CartItem": 0,
        "Order": 0,
        "OrderItem": 0,
        "ShippingAddress": 0,
        "PaymentRecord": 0,
        "OrderStatusHistory": 0,
    }
    assert set(User.objects.values_list("email", flat=True)) == {u["email"] for u in definition["users"]}
    assert set(Supplier.objects.values_list("supplier_code", flat=True)) == {
        s["supplier_code"] for s in definition["suppliers"]
    }
    assert set(Category.objects.values_list("category_code", flat=True)) == {
        c["category_code"] for c in definition["categories"]
    }
    assert set(Product.objects.values_list("product_code", flat=True)) == {
        p["product_code"] for p in definition["products"]
    }
    assert set(StockUnit.objects.values_list("sku", "stock_quantity")) == {
        (s["sku"], s["stock_quantity"]) for s in definition["stock_units"]
    }
    after = set(AuditLog.objects.values_list("pk", flat=True))
    assert audit_before < after and len(after - audit_before) == 1
    assert AuditLog.objects.get(pk=next(iter(after - audit_before))).event_type == "initial_data_load"

    for user in definition["users"]:
        login = api(api_client, "post", "/api/auth/login/", data={"email": user["email"], "password": user["password"]})
        assert login.status_code == 200, user["email"]
        assert body(login)["user"]["user_type"] == "admin"


# trace: NFR-OM-13, NFR-MG-07, FR-060, ADDR-010
def test_gf_025_failed_load_corrected_rerun(make_user, catalog, tmp_path, capsys):
    """GF-025 違反を含む定義ファイルの失敗（無投入・無削除）→修正版の同じ指定での再実行と重複なし。"""
    from audit.models import AuditLog

    make_user("keep.user@example.test")
    catalog.supplier("SUP-KEEP", "既存仕入先")
    before = _counts()
    failures_before = AuditLog.objects.filter(event_type="initial_data_load", result="failure").count()

    definition = _vdc04_definition()
    definition["stock_units"][399]["price_excluding_tax"] = -1
    code, _, logs, err = _cli(capsys, _write(tmp_path, "bad.json", definition), "--reset")
    started = time.monotonic()
    assert code == 1
    assert "在庫単位 400行目" in err and "price_excluding_tax" in err and "何も投入" in err
    assert _counts() == before
    assert AuditLog.objects.filter(event_type="initial_data_load", result="failure").count() == failures_before + 1
    job = [r for r in logs if r["log_type"] == "LOG-05"]
    assert len(job) == 1 and job[0]["result"] == "failure" and job[0]["violations"]

    definition["stock_units"][399]["price_excluding_tax"] = 1200
    corrected = _write(tmp_path, "corrected.json", definition)
    code, _, _, err = _cli(capsys, corrected, "--reset")
    assert code == 0, err
    assert time.monotonic() - started <= 3600
    expected = {**_counts()}
    assert (
        expected["User"],
        expected["Supplier"],
        expected["Category"],
        expected["Product"],
        expected["StockUnit"],
    ) == (
        7,
        20,
        30,
        300,
        800,
    )

    code, _, _, err = _cli(capsys, corrected, "--reset")
    assert code == 0, err
    assert _counts() == expected
    code, _, _, err = _cli(capsys, corrected)
    assert code == 1 and "重複" in err
    assert _counts() == expected


# trace: NFR-OM-11, FR-002, FR-030, FR-031, FR-060, ADDR-007, ADDR-011, ADDR-013
def test_gf_026_log_types_output(api_client, buyer, admin, bearer, catalog, app_logs, set_state, tmp_path, capsys):
    """GF-026 全機能の実行で LOG-01〜LOG-07 が定めた内容で出力・記録される（NFR-OM-11 の出力。保管期間は対象外）。"""
    from audit.models import AuditLog
    from orders.models import OrderStatusHistory

    login = api(api_client, "post", "/api/auth/login/", data={"email": buyer.email, "password": PASSWORD})
    token = f"Bearer {body(login)['token']}"
    api(api_client, "post", "/api/auth/login/", data={"email": buyer.email, "password": "Wrong0Pass"})
    admin_token = bearer(admin)
    unit = catalog.stock_unit(price=1000, stock=20)
    first = order_of(api_client, token, [(unit, 1)])
    assert pay(api_client, token, first["order_id"], "approved").status_code == 200
    oid = first["order_id"]
    assert (
        api(api_client, "post", f"/api/admin/orders/{oid}/ship/", admin_token, {"tracking_number": "T-1"}).status_code
        == 200
    )
    assert api(api_client, "post", f"/api/admin/orders/{oid}/deliver/", admin_token).status_code == 200
    second = order_of(api_client, token, [(unit, 1)])
    assert api(api_client, "post", f"/api/orders/{second['order_id']}/cancel/", token).status_code == 200
    assert add_item(api_client, token, unit.pk, 1).status_code == 200
    set_state(order_fault_point="after_stock_decrement")
    assert api(api_client, "post", "/api/orders/", token, {"shipping_address": {}}).status_code == 400
    assert place(api_client, token).status_code == 500
    set_state(order_fault_point="none")
    assert api(api_client, "post", "/api/auth/logout/", token).status_code == 204

    records = app_logs.records()
    by_type = {}
    for record in records:
        assert {"timestamp", "level", "log_type", "request_id"} <= set(record)
        by_type.setdefault(record["log_type"], []).append(record)
    assert {"LOG-01", "LOG-02", "LOG-03", "LOG-06"} <= set(by_type), sorted(by_type)
    assert all({"operation", "event", "result"} <= set(r) for r in by_type["LOG-01"])
    assert any(r["result"].startswith("input_error") for r in by_type["LOG-01"])
    assert any(r["error_type"] == "system_error" and r["exception_class"] and r["location"] for r in by_type["LOG-02"])
    assert all({"method", "path", "status", "duration_ms"} <= set(r) for r in by_type["LOG-03"])
    assert {r["phase"] for r in by_type["LOG-06"]} == {"request", "response"}

    events = set(AuditLog.objects.values_list("event_type", "result"))
    assert {("login_success", "success"), ("login_failure", "failure"), ("logout", "success")} <= events
    history = list(OrderStatusHistory.objects.filter(order_id=oid).order_by("pk"))
    assert [(h.from_status, h.to_status, h.actor_user_type) for h in history] == [
        (None, "accepted", "buyer"),
        ("accepted", "paid", "buyer"),
        ("paid", "shipped", "admin"),
        ("shipped", "delivered", "admin"),
    ]
    assert all(h.changed_at is not None for h in history)
    assert OrderStatusHistory.objects.filter(order_id=second["order_id"], to_status="cancelled").count() == 1

    small = {"suppliers": [{"supplier_code": "SUP-LOG", "name": "ログ確認仕入先"}]}
    code, _, logs, err = _cli(capsys, _write(tmp_path, "log.json", small))
    assert code == 0, err
    job = [r for r in logs if r["log_type"] == "LOG-05"]
    assert len(job) == 1 and job[0]["job"] == "initial_data_load" and job[0]["result"] == "success"
    assert job[0]["counts"]["suppliers"] == 1
    assert AuditLog.objects.filter(event_type="initial_data_load", result="success").count() == 1


# trace: NFR-OM-17, ADDR-014
def _settings_probe(**overrides):
    """環境変数だけを変えた別プロセスで設定モジュールを読み込み、反映された設定値を返す（プログラムは変更しない）。"""
    env = {key: value for key, value in os.environ.items() if not key.startswith(("DB_", "DJANGO_", "MINICOMMERCE_"))}
    env.update(
        {
            "DJANGO_SETTINGS_MODULE": "config.settings",
            "DJANGO_SECRET_KEY": secrets.token_urlsafe(32),
            "DB_USER": "probe_user",
            "DB_PASSWORD": secrets.token_urlsafe(16),
            "PYTHONIOENCODING": "utf-8",
        }
    )
    env.update(overrides)
    code = (
        "import json, django; from django.conf import settings; django.setup(); "
        "db = settings.DATABASES['default']; "
        "print(json.dumps({'env': settings.MINICOMMERCE_ENV, 'debug': settings.DEBUG, "
        "'dev': settings.MINICOMMERCE_DEV_FEATURES, 'test_support': 'test_support' in settings.INSTALLED_APPS, "
        "'hosts': settings.ALLOWED_HOSTS, 'db': [db['HOST'], db['PORT'], db['NAME']], "
        "'secure_cookie': settings.SESSION_COOKIE_SECURE, 'hsts': settings.SECURE_HSTS_SECONDS}))"
    )
    completed = subprocess.run(
        [sys.executable, "-c", code], cwd=APP_DIR, env=env, capture_output=True, text=True, timeout=120, check=False
    )
    return (
        completed.returncode,
        completed.stdout.strip().splitlines()[-1] if completed.stdout.strip() else "",
        completed.stderr,
    )


# trace: NFR-OM-17, ADDR-014
def test_gf_027_env_specific_settings():
    """GF-027 環境ごとの設定値を環境変数だけで変更でき、本番では開発用機能を有効にできない（NFR-OM-17）。"""
    code, out, err = _settings_probe(
        MINICOMMERCE_ENV="production",
        DJANGO_DEBUG="false",
        MINICOMMERCE_DEV_FEATURES="false",
        DJANGO_ALLOWED_HOSTS="shop.example.test",
        DB_HOST="db.internal.example.test",
        DB_PORT="6543",
        DB_NAME="minicommerce_prod_probe",
    )
    assert code == 0, err
    prod = json.loads(out)
    assert prod == {
        "env": "production",
        "debug": False,
        "dev": False,
        "test_support": False,
        "hosts": ["shop.example.test"],
        "db": ["db.internal.example.test", "6543", "minicommerce_prod_probe"],
        "secure_cookie": True,
        "hsts": 31536000,
    }
    code, out, err = _settings_probe(
        MINICOMMERCE_ENV="development", MINICOMMERCE_DEV_FEATURES="true", DB_NAME="dev_probe"
    )
    assert code == 0, err
    dev = json.loads(out)
    assert (dev["env"], dev["dev"], dev["test_support"], dev["db"][2], dev["secure_cookie"]) == (
        "development",
        True,
        True,
        "dev_probe",
        False,
    )
    for unsafe in ({"MINICOMMERCE_DEV_FEATURES": "true"}, {"DJANGO_DEBUG": "true"}):
        code, _, err = _settings_probe(MINICOMMERCE_ENV="production", **unsafe)
        assert code != 0 and "ImproperlyConfigured" in err, unsafe

    example = (REPO_DIR / ".env.example").read_text(encoding="utf-8")
    values = dict(
        line.split("=", 1) for line in example.splitlines() if line and not line.startswith("#") and "=" in line
    )
    for secret in ("DJANGO_SECRET_KEY", "DB_USER", "DB_PASSWORD"):
        assert secret in values and values[secret].strip() == "", secret


# trace: NFR-EN-01, NFR-EN-02, NFR-EN-09, ADDR-014
def test_gf_035_tech_stack_versions():
    """GF-035 Python 3.12・Django 5.2・DRF 3.15 以上・PostgreSQL 16 で、SPA・ビルド工程を持たない。"""
    import django
    import rest_framework
    from django.db import connection

    assert sys.version_info[:2] == (3, 12)
    dockerfile = (APP_DIR / "Dockerfile").read_text(encoding="utf-8")
    assert re.search(r"^FROM python:3\.12[-.@:]", dockerfile, re.M)
    assert django.VERSION[:2] == (5, 2)
    assert tuple(int(x) for x in rest_framework.VERSION.split(".")[:2]) >= (3, 15)
    connection.ensure_connection()
    assert connection.pg_version // 10000 == 16
    with connection.cursor() as cursor:
        cursor.execute("SHOW server_version")
        assert cursor.fetchone()[0].startswith("16.")

    build_files = {"package.json", "webpack.config.js", "vite.config.js", "vite.config.ts", "tsconfig.json"}
    skipped = {".venv", "node_modules", ".git", "reports", "__pycache__", ".pytest_cache", ".ruff_cache"}
    found = []
    for current, dirs, files in os.walk(REPO_DIR):
        dirs[:] = [d for d in dirs if d not in skipped]
        found += [str(Path(current, f).relative_to(REPO_DIR)) for f in files if f in build_files]
    assert found == []
    static = sorted(p.name for p in (APP_DIR / "common" / "static" / "common").iterdir())
    assert static == ["site.css", "site.js"]
    script = (APP_DIR / "common" / "static" / "common" / "site.js").read_text(encoding="utf-8")
    assert "import " not in script and "require(" not in script
