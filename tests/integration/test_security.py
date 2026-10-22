# trace: NFR-SC-04, NFR-SC-05, FR-001, FR-011, FR-012, FR-021, FR-030, FR-031
# trace: FR-033, FR-040, FR-042, FR-043, ADDR-002, ADDR-006, ADDR-007
"""脆弱性対策（NFR-SC-04 入力値検証、NFR-SC-05 XSS・CSRF 対策）の結合試験。

期待結果は非機能要件定義書 8.1（NFR-SC-04、NFR-SC-05）と 8.2（VUL-04、VUL-05、VUL-06）の
「検証方法」欄、および各FRの入力条件から導出する。
Cookie のログインセッションで認証する画面経路（ミドルウェア→URL ルーティング→画面→Service→DB）を
実際に通し、CSRF 対策用トークンの検証とテンプレートの自動エスケープを確認する。
"""
from urllib.parse import quote

import pytest
from django.test import Client

from shop.models import (
    Cart,
    CartLine,
    Collection,
    Coupon,
    Item,
    ItemCollection,
    PurchaseOrder,
    PurchaseOrderStatus,
    PurchaseOrderStatusHistory,
    StockUnit,
    Supplier,
    User,
)
from tests.integration import _helpers

pytestmark = pytest.mark.django_db

# SQL インジェクション・OS コマンドインジェクションの攻撃文字列（NFR-SC-04 の検証方法）。
# 実在するテーブル名（user, item, stock_unit）を狙う文字列を含める。
ATTACK_STRINGS = [
    "' OR '1'='1",
    "'; DROP TABLE item; --",
    '" UNION SELECT NULL--',
    "1 OR 1=1; DELETE FROM stock_unit; --",
    "; rm -rf /tmp/shop; echo pwned",
    "$(id)",
    "`id`",
    "| cat /etc/passwd",
]

# 画面出力のエスケープを確認する値（NFR-SC-05 の検証方法。VDC-06 と同じ考え方の架空データ）。
SCRIPT_FULL_NAME = "<script>alert('name')</script>"
SCRIPT_RECIPIENT = "<script>alert('to')</script>"
IMG_ADDRESS_LINE1 = "<img src=x onerror=alert(1)>千代田区一番町1-1"
SCRIPT_ITEM_NAME = "<script>alert('item')</script>マグカップ"


# trace: NFR-SC-05, ADDR-002
def _csrf_token(client: Client, path: str) -> str:
    """画面を表示して CSRF 対策用トークンを取得する。"""
    response = client.get(path)
    assert response.status_code == 200, response.content
    cookie = client.cookies.get("csrftoken")
    assert cookie is not None, "画面が CSRF 対策用トークンを発行していない"
    return cookie.value


# trace: NFR-SC-05, ADDR-002
def _screen_login(client: Client, email: str) -> None:
    """画面（SCR-004）からログインし、Cookie のログインセッションを開始する。"""
    token = _csrf_token(client, "/login")
    response = client.post(
        "/login",
        {"email": email, "password": _helpers.TEST_PASSWORD, "csrfmiddlewaretoken": token},
    )
    assert response.status_code == 302, response.content


# trace: FR-030, FR-031
def _paid_order(api, buyer_email: str = "buyer@example.com", sku: str = "SKU-001"):
    """支払済の注文を1件作成し、注文を返す。"""
    _helpers.make_user(email=buyer_email)
    token = api.login(buyer_email)
    supplier = _helpers.make_supplier(supplier_code=f"SUP-{sku}")
    item = _helpers.make_item(item_code=f"ITEM-{sku}", name=f"商品{sku}")
    unit = _helpers.make_stock_unit(item, supplier, sku=sku, quantity=10)
    assert (
        api.post("/api/cart/lines", {"stock_unit_id": unit.stock_unit_id, "quantity": 2}, token=token)
    ).status_code == 200
    created = api.post("/api/checkout", dict(_helpers.VALID_ADDRESS), token=token)
    assert created.status_code == 201, created.content
    order_id = created.json()["purchase_order_id"]
    paid = api.post(f"/api/purchase-orders/{order_id}/pay", {"mock_result": "approve"}, token=token)
    assert paid.status_code == 200, paid.content
    return PurchaseOrder.objects.get(purchase_order_id=order_id)


# trace: NFR-SC-04
def _business_row_counts() -> dict[str, int]:
    """業務データの件数（監査ログを除く）を返す。"""
    return {
        "user": User.objects.count(),
        "supplier": Supplier.objects.count(),
        "collection": Collection.objects.count(),
        "item": Item.objects.count(),
        "item_collection": ItemCollection.objects.count(),
        "stock_unit": StockUnit.objects.count(),
        "coupon": Coupon.objects.count(),
        "cart": Cart.objects.count(),
        "cart_line": CartLine.objects.count(),
        "purchase_order": PurchaseOrder.objects.count(),
    }


# trace: NFR-SC-05, FR-021, ADDR-002
@pytest.mark.case("IT-AI-GF-012")
def test_buyer_screen_update_without_csrf_token_is_rejected():
    """CSRF 対策用トークンの無い購入者画面の更新要求は拒否され、データが変わらない（NFR-SC-05、VUL-06）。"""
    user = _helpers.make_user()
    item, unit = _helpers.catalog()
    client = Client(enforce_csrf_checks=True)
    _screen_login(client, user.email)

    rejected = client.post(
        "/cart/lines",
        {"stock_unit_id": unit.stock_unit_id, "quantity": 1, "item_id": item.item_id},
    )

    assert rejected.status_code == 403
    assert CartLine.objects.count() == 0

    token = _csrf_token(client, f"/items/{item.item_id}")
    accepted = client.post(
        "/cart/lines",
        {
            "stock_unit_id": unit.stock_unit_id,
            "quantity": 1,
            "item_id": item.item_id,
            "csrfmiddlewaretoken": token,
        },
    )

    assert accepted.status_code == 302
    assert CartLine.objects.count() == 1


# trace: NFR-SC-05, FR-043, ADDR-002
@pytest.mark.case("IT-AI-GF-013")
def test_admin_screen_update_without_csrf_token_is_rejected(api):
    """CSRF 対策用トークンの無い管理者画面の更新要求は拒否され、注文状態が変わらない（NFR-SC-05、VUL-06）。"""
    order = _paid_order(api)
    admin = _helpers.make_admin()
    client = Client(enforce_csrf_checks=True)
    _screen_login(client, admin.email)

    rejected = client.post(
        f"/admin/purchase-orders/{order.purchase_order_id}/ship",
        {"tracking_number": "TRK-0001"},
    )

    assert rejected.status_code == 403
    order.refresh_from_db()
    assert order.status == PurchaseOrderStatus.PAID
    assert order.tracking_number is None
    assert order.shipped_at is None
    assert PurchaseOrderStatusHistory.objects.filter(purchase_order=order).count() == 2

    token = _csrf_token(client, f"/admin/purchase-orders/{order.purchase_order_id}")
    accepted = client.post(
        f"/admin/purchase-orders/{order.purchase_order_id}/ship",
        {"tracking_number": "TRK-0001", "csrfmiddlewaretoken": token},
    )

    assert accepted.status_code == 302
    order.refresh_from_db()
    assert order.status == PurchaseOrderStatus.SHIPPED
    assert order.tracking_number == "TRK-0001"


# trace: NFR-SC-05, FR-042, ADDR-006
@pytest.mark.case("IT-AI-GF-014")
def test_admin_screens_escape_buyer_supplied_values(api):
    """管理者画面に表示する氏名・配送先・商品名は HTML エスケープされる（NFR-SC-05、VUL-05）。"""
    registered = api.post(
        "/api/auth/register",
        {
            "email": "xss-buyer@example.com",
            "password": _helpers.TEST_PASSWORD,
            "password_confirmation": _helpers.TEST_PASSWORD,
            "full_name": SCRIPT_FULL_NAME,
        },
    )
    assert registered.status_code == 201, registered.content
    token = api.login("xss-buyer@example.com")

    supplier = _helpers.make_supplier()
    item = _helpers.make_item(name=SCRIPT_ITEM_NAME)
    unit = _helpers.make_stock_unit(item, supplier)
    assert (
        api.post("/api/cart/lines", {"stock_unit_id": unit.stock_unit_id, "quantity": 1}, token=token)
    ).status_code == 200
    address = dict(_helpers.VALID_ADDRESS)
    address["recipient_name"] = SCRIPT_RECIPIENT
    address["address_line1"] = IMG_ADDRESS_LINE1
    created = api.post("/api/checkout", address, token=token)
    assert created.status_code == 201, created.content
    order_id = created.json()["purchase_order_id"]

    admin = _helpers.make_admin()
    client = Client()
    _screen_login(client, admin.email)

    for path in ("/admin/purchase-orders", f"/admin/purchase-orders/{order_id}", "/admin/stock-units"):
        response = client.get(path)
        assert response.status_code == 200, response.content
        body = response.content.decode("utf-8")
        assert "<script>alert(" not in body
        assert "<img src=x" not in body

    detail = client.get(f"/admin/purchase-orders/{order_id}").content.decode("utf-8")
    assert "&lt;script&gt;alert(&#x27;name&#x27;)&lt;/script&gt;" in detail
    assert "&lt;script&gt;alert(&#x27;to&#x27;)&lt;/script&gt;" in detail
    assert "&lt;img src=x onerror=alert(1)&gt;" in detail
    assert "&lt;script&gt;alert(&#x27;item&#x27;)&lt;/script&gt;" in detail


# trace: NFR-SC-05, FR-012, FR-033, ADDR-006
@pytest.mark.case("IT-AI-GF-015")
def test_buyer_screens_escape_buyer_supplied_values(api):
    """購入者画面に表示する氏名・商品名・配送先は HTML エスケープされる（NFR-SC-05、VUL-05）。"""
    registered = api.post(
        "/api/auth/register",
        {
            "email": "xss-buyer2@example.com",
            "password": _helpers.TEST_PASSWORD,
            "password_confirmation": _helpers.TEST_PASSWORD,
            "full_name": SCRIPT_FULL_NAME,
        },
    )
    assert registered.status_code == 201, registered.content
    token = api.login("xss-buyer2@example.com")

    supplier = _helpers.make_supplier()
    item = _helpers.make_item(name=SCRIPT_ITEM_NAME)
    unit = _helpers.make_stock_unit(item, supplier)
    assert (
        api.post("/api/cart/lines", {"stock_unit_id": unit.stock_unit_id, "quantity": 1}, token=token)
    ).status_code == 200
    address = dict(_helpers.VALID_ADDRESS)
    address["recipient_name"] = SCRIPT_RECIPIENT
    address["address_line1"] = IMG_ADDRESS_LINE1
    created = api.post("/api/checkout", address, token=token)
    assert created.status_code == 201, created.content
    order_id = created.json()["purchase_order_id"]

    client = Client()
    _screen_login(client, "xss-buyer2@example.com")

    for path in ("/", f"/items/{item.item_id}", "/purchase-orders", f"/purchase-orders/{order_id}"):
        response = client.get(path)
        assert response.status_code == 200, response.content
        body = response.content.decode("utf-8")
        assert "<script>alert(" not in body
        assert "<img src=x" not in body

    detail = client.get(f"/purchase-orders/{order_id}").content.decode("utf-8")
    assert "&lt;script&gt;alert(&#x27;name&#x27;)&lt;/script&gt;" in detail
    assert "&lt;script&gt;alert(&#x27;to&#x27;)&lt;/script&gt;" in detail
    assert "&lt;img src=x onerror=alert(1)&gt;" in detail
    assert "&lt;script&gt;alert(&#x27;item&#x27;)&lt;/script&gt;" in detail


# trace: NFR-SC-04, FR-011, FR-021, FR-040, ADDR-007
@pytest.mark.case("IT-AI-GF-016")
def test_api_inputs_reject_injection_strings(api):
    """Web API の入力項目へ攻撃文字列を送っても入力エラーか通常処理になる（NFR-SC-04、VUL-04）。"""
    _helpers.make_user()
    buyer_token = api.login("buyer@example.com")
    _helpers.make_admin()
    admin_token = api.login("admin@example.com")
    _helpers.catalog()
    baseline = _business_row_counts()

    for attack in ATTACK_STRINGS:
        escaped = quote(attack, safe="")
        responses = [
            api.post(
                "/api/auth/register",
                {
                    "email": attack,
                    "password": attack,
                    "password_confirmation": attack,
                    "full_name": attack,
                },
            ),
            api.post("/api/auth/login", {"email": attack, "password": attack}),
            api.get("/api/items", {"keyword": attack}),
            api.get("/api/items", {"collection_id": attack}),
            api.get("/api/items", {"sort": attack}),
            api.get(f"/api/items/{escaped}"),
            api.post("/api/cart/lines", {"stock_unit_id": attack, "quantity": attack}, token=buyer_token),
            api.post("/api/cart/apply-coupon", {"code": attack}, token=buyer_token),
            api.get("/api/admin/stock-units", {"sku": attack, "item_name": attack}, token=admin_token),
            api.get(
                "/api/admin/purchase-orders",
                {"order_number": attack, "buyer_email": attack},
                token=admin_token,
            ),
            api.post(f"/api/purchase-orders/{escaped}/pay", {}, token=buyer_token),
        ]
        for response in responses:
            assert response.status_code in {200, 400, 401, 404, 409}, (attack, response.status_code)
            if response.status_code == 200 and response["Content-Type"].startswith("application/json"):
                body = response.json()
                if isinstance(body, dict) and "results" in body:
                    assert body["results"] == [], (attack, body)

    assert _business_row_counts() == baseline
    # 攻撃文字列の送信後も DB が通常どおり参照できる（表が削除・破壊されていない）。
    assert api.get("/api/items").status_code == 200
    assert StockUnit.objects.count() == 1


# trace: NFR-SC-04, FR-001, FR-011, FR-040, ADDR-006
@pytest.mark.case("IT-AI-GF-017")
def test_screen_form_inputs_reject_injection_strings(api):
    """画面のフォーム・検索条件へ攻撃文字列を送っても入力エラーか通常処理になり、データが変わらない（NFR-SC-04、VUL-04）。"""
    _helpers.make_admin()
    _helpers.catalog()
    admin_client = Client(enforce_csrf_checks=True)
    _screen_login(admin_client, "admin@example.com")
    guest_client = Client(enforce_csrf_checks=True)
    baseline = _business_row_counts()

    for attack in ATTACK_STRINGS:
        register_token = _csrf_token(guest_client, "/register")
        registered = guest_client.post(
            "/register",
            {
                "email": attack,
                "password": attack,
                "password_confirmation": attack,
                "full_name": attack,
                "csrfmiddlewaretoken": register_token,
            },
        )
        assert registered.status_code == 400, (attack, registered.status_code)

        login_token = _csrf_token(guest_client, "/login")
        logged_in = guest_client.post(
            "/login",
            {"email": attack, "password": attack, "csrfmiddlewaretoken": login_token},
        )
        assert logged_in.status_code in {400, 401}, (attack, logged_in.status_code)

        assert guest_client.get("/", {"keyword": attack}).status_code in {200, 400}
        assert guest_client.get("/", {"collection_id": attack}).status_code in {200, 400}
        assert admin_client.get("/admin/stock-units", {"sku": attack, "item_name": attack}).status_code in {200, 400}
        assert admin_client.get(
            "/admin/purchase-orders", {"order_number": attack, "buyer_email": attack}
        ).status_code in {200, 400}

    assert _business_row_counts() == baseline
    assert api.get("/api/items").status_code == 200
