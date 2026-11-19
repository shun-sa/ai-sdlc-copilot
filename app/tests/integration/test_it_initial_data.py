# trace: FR-002, FR-011, FR-040, FR-060, ADDR-002, ADDR-003, ADDR-004, ADDR-009, ADDR-010
"""結合試験：初期データ一括投入（管理コマンド→定義ファイルの解釈→全件検証→DB→監査ログ→Web API）。

IT-051〜IT-055（AI INITIAL）。期待結果は FR-060（6.26）、CMN-24/25/37/38/39、NFR-OM-04/13、NFR-SC-15、
ADDR-009（定義ファイルの形式）・ADDR-010（起動手段・結果の提示）・ADDR-002（削除指定時のログイン状態の無効化）から導出する。
コマンドは運用者の実行と同じく `manage.py load_initial_data` の引数解析から実行する。
コマンドは終了時に DB 接続を閉じるため、コマンドを実行するケースは transaction=True のコミット方式で行う。
定義ファイルは架空の値だけで作る。
"""

import json
import re

import pytest
from django.core.management import execute_from_command_line

from tests.integration._helpers import PASSWORD, add_item, api, body, order_of, pay

pytestmark = pytest.mark.django_db

DEFINITION = {
    "users": [
        {"email": "Admin.IT@example.test", "password": "Kanri01Pass", "name": "管理 架空", "user_type": "admin"},
        {"email": "buyer.it@example.test", "password": "Kounyu01Pass", "name": "購入 架空", "user_type": "buyer"},
    ],
    "suppliers": [{"supplier_code": "SUP-IT1", "name": "架空仕入先"}],
    "categories": [
        {"category_code": "it-kitchen", "name": "キッチン", "display_order": 1},
        {"category_code": "it-mug", "name": "マグ", "parent_category_code": "it-kitchen"},
    ],
    "products": [
        {
            "product_code": "IT-MUG",
            "name": "ITマグ",
            "description": "説明",
            "category_codes": ["it-mug"],
            "registered_at": "2027-03-01T10:00:00+09:00",
        },
        {"product_code": "IT-HIDE", "name": "非公開皿", "visibility": "private", "category_codes": ["it-kitchen"]},
    ],
    "stock_units": [
        {
            "sku": "IT-MUG-WH",
            "product_code": "IT-MUG",
            "supplier_code": "SUP-IT1",
            "variant_name": "白",
            "price_excluding_tax": 1000,
            "stock_quantity": 10,
        },
        {
            "sku": "IT-MUG-BK",
            "product_code": "IT-MUG",
            "supplier_code": "SUP-IT1",
            "variant_name": "黒",
            "price_excluding_tax": 1100,
            "stock_quantity": 4,
        },
        {
            "sku": "IT-HIDE-01",
            "product_code": "IT-HIDE",
            "supplier_code": "SUP-IT1",
            "variant_name": "標準",
            "price_excluding_tax": 2000,
            "stock_quantity": 3,
        },
    ],
    "coupons": [
        {
            "coupon_code": "IT-WELCOME",
            "name": "架空クーポン",
            "discount_type": "fixed_amount",
            "discount_value": 300,
            "valid_from": "2026-01-01T00:00:00",
            "valid_to": "2099-12-31T23:59:59+09:00",
        },
    ],
}
EXPECTED_COUNTS = {"利用者": 2, "仕入先": 1, "商品分類": 2, "商品": 2, "商品分類所属": 2, "在庫単位": 3, "クーポン": 1}
_COUNT = re.compile(r"(商品分類所属|商品分類|在庫単位|クーポン|利用者|仕入先|商品)\D{0,4}?(\d+)")
SENSITIVE = (
    "Admin.IT@example.test",
    "admin.it@example.test",
    "buyer.it@example.test",
    "Kanri01Pass",
    "Kounyu01Pass",
    "管理 架空",
    "購入 架空",
)


# trace: FR-060, ADDR-010
def _cli(capsys, *args):
    """`manage.py load_initial_data ...` を実行し (終了コード, 標準出力, 標準エラー) を返す。"""
    capsys.readouterr()
    code = 0
    try:
        execute_from_command_line(["manage.py", "load_initial_data", *args])
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
    captured = capsys.readouterr()
    out = "\n".join(line for line in captured.out.splitlines() if not line.startswith('{"timestamp"'))
    return code, out, captured.err


# trace: FR-060, ADDR-009
def _write(tmp_path, name, data):
    path = tmp_path / name
    if isinstance(data, bytes):
        path.write_bytes(data)
    else:
        path.write_text(data if isinstance(data, str) else json.dumps(data, ensure_ascii=False), encoding="utf-8")
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


# trace: FR-060, FR-002, FR-011, FR-040, ADDR-009, ADDR-010, ADDR-003
@pytest.mark.django_db(transaction=True)
def test_it_051_load_then_login_and_listings(api_client, tmp_path, capsys):
    """IT-051 初期データ一括投入→投入利用者のログイン・商品一覧・在庫一覧への反映・監査ログ。"""
    from audit.models import AuditLog
    from catalog.models import Product

    path = _write(tmp_path, "definition.json", DEFINITION)
    code, out, err = _cli(capsys, path)
    assert code == 0, err
    assert "成功" in out
    shown = {label: int(n) for label, n in _COUNT.findall(out)}
    assert shown == EXPECTED_COUNTS, out
    assert not any(word in out + err for word in SENSITIVE)
    counts = _counts()
    assert (
        counts["User"],
        counts["Supplier"],
        counts["Category"],
        counts["Product"],
        counts["ProductCategory"],
        counts["StockUnit"],
        counts["Coupon"],
    ) == (2, 1, 2, 2, 2, 3, 1)

    hidden = Product.objects.get(product_code="IT-HIDE")
    assert hidden.is_public is False and hidden.description == ""
    assert Product.objects.get(product_code="IT-MUG").is_public is True

    admin_login = api(
        api_client, "post", "/api/auth/login/", data={"email": "admin.it@example.test", "password": "Kanri01Pass"}
    )
    buyer_login = api(
        api_client, "post", "/api/auth/login/", data={"email": "buyer.it@example.test", "password": "Kounyu01Pass"}
    )
    assert admin_login.status_code == 200 and body(admin_login)["user"]["user_type"] == "admin"
    assert buyer_login.status_code == 200 and body(buyer_login)["user"]["user_type"] == "buyer"

    listing = body(api(api_client, "get", "/api/products/"))
    assert [i["name"] for i in listing["items"]] == ["ITマグ"]
    stock = body(api(api_client, "get", "/api/admin/stock-units/", f"Bearer {body(admin_login)['token']}"))
    assert [(i["sku"], i["visibility"]) for i in stock["items"]] == [
        ("IT-HIDE-01", "private"),
        ("IT-MUG-BK", "public"),
        ("IT-MUG-WH", "public"),
    ]

    log = AuditLog.objects.get(event_type="initial_data_load")
    assert log.result == "success" and log.target_user_id is None
    detail = log.detail or ""
    assert all(word not in detail for word in SENSITIVE)
    for value in ("2", "3"):
        assert value in detail


# trace: FR-060, ADDR-010, ADDR-002, ADDR-004
@pytest.mark.django_db(transaction=True)
def test_it_052_reset_deletes_all_and_invalidates_tokens(api_client, buyer, admin, catalog, tmp_path, capsys):
    """IT-052 削除指定（--reset）による全データ削除とログイン状態の無効化。"""
    from accounts.models import ApiLoginState
    from audit.models import AuditLog

    login = body(api(api_client, "post", "/api/auth/login/", data={"email": buyer.email, "password": PASSWORD}))
    token = f"Bearer {login['token']}"
    unit = catalog.stock_unit(stock=10)
    order = order_of(api_client, token, [(unit, 1)])
    assert pay(api_client, token, order["order_id"]).status_code == 200
    assert add_item(api_client, token, unit.pk, 1).status_code == 200
    before = _counts()
    assert before["Order"] == 1 and before["PaymentRecord"] == 1 and before["CartItem"] >= 1
    audit_before = AuditLog.objects.count()
    assert audit_before >= 1

    code, out, err = _cli(capsys, _write(tmp_path, "definition.json", DEFINITION), "--reset")
    assert code == 0, err
    after = _counts()
    assert after == {
        "User": 2,
        "Supplier": 1,
        "Category": 2,
        "Product": 2,
        "ProductCategory": 2,
        "StockUnit": 3,
        "Coupon": 1,
        "Cart": 0,
        "CartItem": 0,
        "Order": 0,
        "OrderItem": 0,
        "ShippingAddress": 0,
        "PaymentRecord": 0,
        "OrderStatusHistory": 0,
    }
    assert AuditLog.objects.count() == audit_before + 1
    assert ApiLoginState.objects.count() == 0
    stale = api(api_client, "get", "/api/auth/me/", token)
    assert stale.status_code == 401


# trace: FR-060, ADDR-009, ADDR-010
@pytest.mark.django_db(transaction=True)
def test_it_053_violations_reported_nothing_loaded(make_user, catalog, tmp_path, capsys):
    """IT-053 定義ファイルの違反時の全件提示・無投入（--reset でも削除しない）・既存との重複。"""
    from audit.models import AuditLog

    make_user("existing@example.test")
    catalog.supplier("SUP-OLD", "既存仕入先")
    before = _counts()
    audit_before = AuditLog.objects.filter(event_type="initial_data_load", result="failure").count()

    bad = {
        "users": [{"email": "zz-not-mail", "password": "short1", "name": "", "user_type": "root"}],
        "suppliers": [{"supplier_code": "SUP-1", "name": "一"}, {"supplier_code": "SUP-1", "name": "二"}],
        "stock_units": [
            {
                "sku": "X-1",
                "product_code": "NOPE",
                "supplier_code": "SUP-1",
                "variant_name": "v",
                "price_excluding_tax": -1,
                "stock_quantity": 1,
            }
        ],
    }
    code, out, err = _cli(capsys, _write(tmp_path, "bad.json", bad), "--reset")
    assert code == 1
    for fragment in (
        "利用者 1行目",
        "仕入先 2行目",
        "在庫単位 1行目",
        "email",
        "password",
        "name",
        "user_type",
        "supplier_code",
        "product_code",
        "price_excluding_tax",
    ):
        assert fragment in err, fragment
    assert "何も投入" in err
    assert "zz-not-mail" not in err and "short1" not in err and "root" not in err
    assert _counts() == before

    dup = {"suppliers": [{"supplier_code": "SUP-OLD", "name": "重複"}]}
    code, out, err = _cli(capsys, _write(tmp_path, "dup.json", dup))
    assert code == 1 and "仕入先 1行目" in err and "supplier_code" in err
    assert _counts() == before
    failures = list(AuditLog.objects.filter(event_type="initial_data_load", result="failure").order_by("pk"))
    assert len(failures) == audit_before + 2
    assert all(f.target_user_id is None for f in failures)


# trace: FR-060, ADDR-010
@pytest.mark.django_db(transaction=True)
def test_it_054_argument_read_and_format_errors(make_user, tmp_path, capsys):
    """IT-054 実行時の指定誤り・読込不可・記載形式誤り。"""
    from audit.models import AuditLog

    make_user("keep@example.test")
    before = _counts()
    good = _write(tmp_path, "good.json", {"suppliers": []})
    cases = [
        (),
        (good, good),
        (good, "--force"),
        (str(tmp_path / "missing.json"),),
        (_write(tmp_path, "sjis.json", '{"suppliers": [{"supplier_code": "S-1", "name": "仕入"}]}'.encode("cp932")),),
        (_write(tmp_path, "broken.json", "{not json"),),
        (_write(tmp_path, "unknown.json", {"widgets": []}),),
    ]
    for args in cases:
        failures = AuditLog.objects.filter(event_type="initial_data_load", result="failure").count()
        code, out, err = _cli(capsys, *args)
        assert code == 1, args
        assert "失敗" in err, args
        assert AuditLog.objects.filter(event_type="initial_data_load", result="failure").count() == failures + 1, args
        assert _counts() == before, args
    assert not AuditLog.objects.filter(event_type="initial_data_load", result="success").exists()


# trace: FR-060, ADDR-010
def test_it_055_no_web_or_api_entry(api_client, admin, bearer, web):
    """IT-055 初期データ一括投入は Web 画面・Web API から実行できない。"""
    from django.urls import get_resolver

    from audit.models import AuditLog

    token = bearer(admin)
    client = web()
    client.force_login(admin, backend="accounts.backends.SessionUserBackend")
    for path in (
        "/api/admin/initial-data/",
        "/api/admin/load-initial-data/",
        "/api/initial-data/",
        "/api/admin/initial_data/",
        "/manage/initial-data/",
        "/admin/",
    ):
        assert api(api_client, "post", path, token, {"reset": True}).status_code == 404, path
        assert client.get(path).status_code == 404, path

    def patterns(resolver, prefix=""):
        for entry in resolver.url_patterns:
            if hasattr(entry, "url_patterns"):
                yield from patterns(entry, prefix + str(entry.pattern))
            else:
                yield prefix + str(entry.pattern)

    assert not [p for p in patterns(get_resolver()) if "initial" in p or "load" in p]
    assert not AuditLog.objects.filter(event_type="initial_data_load").exists()
