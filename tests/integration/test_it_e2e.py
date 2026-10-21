# trace: FR-001, FR-002, FR-011, FR-012, FR-021, FR-024, FR-030, FR-031, FR-032, FR-033
# trace: FR-034, FR-040, FR-041, FR-042, FR-043, FR-044
# trace: ADDR-002, ADDR-003, ADDR-008
"""業務フロー（End to End）の結合試験（IT-AI-INIT-160〜162）。

検証対象の連携は カート → 注文 → 在庫 を跨ぐ複数FR連携と、購入者・管理者の業務フロー全体。

期待結果は 利用者ストーリー US-001〜US-020、UC-001〜UC-013 の主フロー、FR-026 の金額計算、
ST-PO-01〜ST-PO-06、CMN-38（在庫の反映）から導出する。
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from orders.models import STATUS_CANCELLED, STATUS_CREATED, STATUS_DELIVERED, STATUS_PAID, STATUS_SHIPPED

pytestmark = pytest.mark.django_db

SHIPPING = {
    "recipient_name": "結合 受取人",
    "postal_code": "1234567",
    "prefecture_code": "13",
    "address_line1": "千代田区1-1-1",
    "address_line2": "結合ビル101",
    "phone_number": "09012345678",
}


# trace: FR-001, FR-002, FR-011, FR-012, FR-021, FR-024, FR-030, FR-031, FR-032, FR-033
def test_it_ai_init_160_buyer_end_to_end_flow(api, f):
    """IT-AI-INIT-160 / COV-151：購入者の一連の業務フローが成立する。"""
    collection = f.collection(name="E2E分類")
    item = f.item(name="E2Eノート", description="E2E用の商品", collections=[collection])
    unit = f.stock_unit(item, sku="SKU-E2E-1", variant_name="標準", price=3000, quantity=10)
    f.coupon(code="E2ECPN1", discount_value=1000)

    # 1) 会員登録（自動ログインしない）
    registered = api.post(
        "/api/auth/register",
        {
            "email": "e2e-buyer@example.test",
            "password": "Passw0rdA",
            "password_confirmation": "Passw0rdA",
            "full_name": "E2E 購入者",
        },
        format="json",
    )
    assert registered.status_code == 201

    # 2) ログイン
    login = api.post(
        "/api/auth/login",
        {"email": "e2e-buyer@example.test", "password": "Passw0rdA"},
        format="json",
    )
    assert login.status_code == 200
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.json()['token']}")

    # 3) 商品検索 → 4) 商品詳細
    search = client.get("/api/items", {"keyword": "E2E", "sort": "price_asc"})
    assert search.status_code == 200
    assert [row["item_id"] for row in search.json()["results"]] == [item.pk]
    detail = client.get(f"/api/items/{item.pk}")
    assert detail.status_code == 200
    assert detail.json()["stock_units"][0]["stock_unit_id"] == unit.pk

    # 5) カート投入 → 6) クーポン適用
    added = client.post("/api/cart/lines", {"stock_unit_id": unit.pk, "quantity": 2}, format="json")
    assert added.status_code == 200
    assert added.json()["amounts"]["subtotal"] == 6000
    with_coupon = client.post("/api/cart/apply-coupon", {"code": "E2ECPN1"}, format="json")
    assert with_coupon.status_code == 200
    assert with_coupon.json()["amounts"] == {
        "subtotal": 6000,
        "discount_amount": 1000,
        "discounted_subtotal": 5000,
        "shipping_fee": 0,
        "tax_amount": 500,
        "total": 5500,
    }

    # 7) 注文確定
    created = client.post("/api/checkout", SHIPPING, format="json")
    assert created.status_code == 201
    order = created.json()
    assert order["status"] == STATUS_CREATED
    assert order["amounts"]["total"] == 5500
    unit.refresh_from_db()
    assert unit.quantity == 8

    # 8) 支払
    paid = client.post(
        f"/api/purchase-orders/{order['purchase_order_id']}/pay", {"mock_result": "approve"}, format="json"
    )
    assert paid.status_code == 200
    assert paid.json()["status"] == STATUS_PAID

    # 9) 注文履歴 → 10) 注文詳細
    history = client.get("/api/purchase-orders")
    assert history.status_code == 200
    assert [row["purchase_order_id"] for row in history.json()["results"]] == [order["purchase_order_id"]]
    assert history.json()["results"][0]["status"] == STATUS_PAID

    final = client.get(f"/api/purchase-orders/{order['purchase_order_id']}")
    body = final.json()
    assert body["coupon"]["code"] == "E2ECPN1"
    assert body["amounts"]["total"] == 5500
    assert body["lines"][0]["unit_price"] == 3000
    assert body["shipping_address"]["postal_code"] == "1234567"
    assert [(row["from_status"], row["to_status"]) for row in body["status_history"]] == [
        (None, STATUS_CREATED),
        (STATUS_CREATED, STATUS_PAID),
    ]


# trace: FR-002, FR-033, FR-040, FR-041, FR-042, FR-043, FR-044
def test_it_ai_init_161_admin_end_to_end_flow(api, api_as, buyer, f):
    """IT-AI-INIT-161 / COV-152：管理者の一連の業務フローが成立し、購入者の注文詳細へも反映される。"""
    f.admin(email="e2e-admin@example.test", password="Passw0rdA")
    buyer_client = api_as(buyer)
    unit = f.sellable(price=2500, quantity=10, name="E2E管理商品")
    buyer_client.post("/api/cart/lines", {"stock_unit_id": unit.pk, "quantity": 2}, format="json")
    order = buyer_client.post("/api/checkout", SHIPPING, format="json").json()
    order_id = order["purchase_order_id"]
    buyer_client.post(f"/api/purchase-orders/{order_id}/pay", {}, format="json")

    # 1) 管理者ログイン
    login = api.post(
        "/api/auth/login", {"email": "e2e-admin@example.test", "password": "Passw0rdA"}, format="json"
    )
    assert login.status_code == 200
    admin_client = APIClient()
    admin_client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.json()['token']}")

    # 2) 在庫単位一覧
    stock_units = admin_client.get("/api/admin/stock-units", {"sku": unit.sku})
    assert stock_units.status_code == 200
    assert stock_units.json()["results"][0]["quantity"] == 8

    # 3) 注文検索 → 4) 注文詳細
    searched = admin_client.get("/api/admin/purchase-orders", {"order_number": order["order_number"]})
    assert [row["purchase_order_id"] for row in searched.json()["results"]] == [order_id]
    detail = admin_client.get(f"/api/admin/purchase-orders/{order_id}")
    assert detail.status_code == 200
    assert detail.json()["buyer"]["user_id"] == buyer.pk
    assert detail.json()["can_ship"] is True

    # 5) 出荷登録 → 6) 配達完了登録
    shipped = admin_client.post(
        f"/api/admin/purchase-orders/{order_id}/ship", {"tracking_number": "TRK-E2E-1"}, format="json"
    )
    assert shipped.status_code == 200
    assert shipped.json()["status"] == STATUS_SHIPPED
    delivered = admin_client.post(f"/api/admin/purchase-orders/{order_id}/deliver", {}, format="json")
    assert delivered.status_code == 200
    assert delivered.json()["status"] == STATUS_DELIVERED

    buyer_view = buyer_client.get(f"/api/purchase-orders/{order_id}")
    body = buyer_view.json()
    assert body["status"] == STATUS_DELIVERED
    assert body["tracking_number"] == "TRK-E2E-1"
    assert body["delivered_at"] is not None
    assert [(row["from_status"], row["to_status"]) for row in body["status_history"]] == [
        (None, STATUS_CREATED),
        (STATUS_CREATED, STATUS_PAID),
        (STATUS_PAID, STATUS_SHIPPED),
        (STATUS_SHIPPED, STATUS_DELIVERED),
    ]


# trace: FR-030, FR-034, FR-040, ADDR-003
def test_it_ai_init_162_stock_is_consistent_through_cancel(api_as, buyer, admin_user, f):
    """IT-AI-INIT-162 / COV-153：注文確定とキャンセルによる在庫の増減が一貫する（2重戻しなし）。"""
    buyer_client = api_as(buyer)
    admin_client = api_as(admin_user)
    unit = f.sellable(price=1000, quantity=12, name="在庫整合商品")

    def admin_quantity() -> int:
        response = admin_client.get("/api/admin/stock-units", {"sku": unit.sku})
        assert response.status_code == 200
        return response.json()["results"][0]["quantity"]

    assert admin_quantity() == 12

    buyer_client.post("/api/cart/lines", {"stock_unit_id": unit.pk, "quantity": 4}, format="json")
    order = buyer_client.post("/api/checkout", SHIPPING, format="json").json()
    assert admin_quantity() == 8

    cancelled = buyer_client.post(
        f"/api/purchase-orders/{order['purchase_order_id']}/cancel", {}, format="json"
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == STATUS_CANCELLED
    assert admin_quantity() == 12

    repeated = buyer_client.post(
        f"/api/purchase-orders/{order['purchase_order_id']}/cancel", {}, format="json"
    )
    assert repeated.status_code == 409
    assert admin_quantity() == 12
    unit.refresh_from_db()
    assert unit.quantity == 12
