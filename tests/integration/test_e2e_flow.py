# trace: FR-001, FR-002, FR-011, FR-012, FR-021, FR-024, FR-030, FR-031, FR-034, FR-042, FR-043, FR-044
# trace: ADDR-001, ADDR-002, ADDR-003, ADDR-009
"""複数FRを跨ぐ業務フロー（E2E）の結合試験。

期待結果は機能要件定義書 6.1〜6.25 の各機能の事後条件、8.1 注文の状態遷移、
api-contract 6.1〜6.3、ADDR-001・ADDR-003・ADDR-009 から導出する。
"""
import pytest

from shop.models import PaymentRecord, PaymentResult, PurchaseOrder, PurchaseOrderStatus, PurchaseOrderStatusHistory
from tests.integration import _helpers

pytestmark = pytest.mark.django_db


# trace: FR-001, FR-002, FR-011, FR-012, FR-021, FR-024, FR-030, FR-031, FR-043, FR-044
@pytest.mark.case("IT-AI-052")
def test_register_to_delivered_flow(api):
    """会員登録から配達完了までの業務フローが一連で成立する（FR-001→FR-044）。"""
    supplier = _helpers.make_supplier()
    collection = _helpers.make_collection()
    item = _helpers.make_item(name="Sample ノート", collections=[collection])
    unit = _helpers.make_stock_unit(item, supplier, price=3000, quantity=10)
    _helpers.make_coupon(code="SAVE1000", discount_value=1000, min_spend=3000)
    _helpers.make_admin(email="admin@example.com")

    registered = api.post(
        "/api/auth/register",
        {
            "email": "flow@example.com",
            "password": _helpers.TEST_PASSWORD,
            "password_confirmation": _helpers.TEST_PASSWORD,
            "full_name": "佐藤 花子",
        },
    )
    assert registered.status_code == 201
    token = api.login("flow@example.com")

    searched = api.get("/api/items", {"keyword": "sample"})
    assert [row["item_id"] for row in searched.json()["results"]] == [item.item_id]
    detail = api.get(f"/api/items/{item.item_id}")
    assert detail.json()["stock_units"][0]["quantity"] == 10

    assert api.post(
        "/api/cart/lines", {"stock_unit_id": unit.stock_unit_id, "quantity": 2}, token=token
    ).status_code == 200
    applied = api.post("/api/cart/apply-coupon", {"code": "SAVE1000"}, token=token)
    assert applied.json()["amounts"]["total"] == 5500

    checkout = api.post("/api/checkout", dict(_helpers.VALID_ADDRESS), token=token)
    assert checkout.status_code == 201
    order_id = checkout.json()["purchase_order_id"]
    ordered_amounts = checkout.json()["amounts"]
    assert ordered_amounts["discount_amount"] == 1000
    assert checkout.json()["coupon"]["code"] == "SAVE1000"

    paid = api.post(f"/api/purchase-orders/{order_id}/pay", {"mock_result": "approve"}, token=token)
    assert paid.status_code == 200

    admin_token = api.login("admin@example.com")
    shipped = api.post(
        f"/api/admin/purchase-orders/{order_id}/ship", {"tracking_number": "TRK-0001"}, token=admin_token
    )
    delivered = api.post(f"/api/admin/purchase-orders/{order_id}/deliver", {}, token=admin_token)
    assert shipped.status_code == 200
    assert delivered.status_code == 200

    final = api.get(f"/api/purchase-orders/{order_id}", token=token)
    assert final.status_code == 200
    assert final.json()["status"] == PurchaseOrderStatus.DELIVERED
    assert final.json()["amounts"] == ordered_amounts
    assert [
        (entry["from_status"], entry["to_status"]) for entry in final.json()["status_history"]
    ] == [
        (None, PurchaseOrderStatus.CREATED),
        (PurchaseOrderStatus.CREATED, PurchaseOrderStatus.PAID),
        (PurchaseOrderStatus.PAID, PurchaseOrderStatus.SHIPPED),
        (PurchaseOrderStatus.SHIPPED, PurchaseOrderStatus.DELIVERED),
    ]
    unit.refresh_from_db()
    assert unit.quantity == 8
    assert PurchaseOrderStatusHistory.objects.filter(purchase_order_id=order_id).count() == 4


# trace: FR-012, FR-030, FR-031, FR-034
@pytest.mark.case("IT-AI-053")
def test_cancel_restores_stock_and_allows_repurchase(api):
    """キャンセル後に在庫が復元され、同じ在庫単位を再度購入できる（ST-PO-03、FR-012）。"""
    supplier = _helpers.make_supplier()
    item = _helpers.make_item()
    unit = _helpers.make_stock_unit(item, supplier, quantity=1)
    _helpers.make_user(email="buyer@example.com")
    token = api.login("buyer@example.com")

    api.post("/api/cart/lines", {"stock_unit_id": unit.stock_unit_id, "quantity": 1}, token=token)
    checkout = api.post("/api/checkout", dict(_helpers.VALID_ADDRESS), token=token)
    order_id = checkout.json()["purchase_order_id"]
    assert api.post(f"/api/purchase-orders/{order_id}/pay", {}, token=token).status_code == 200

    sold_out = api.get(f"/api/items/{item.item_id}")
    assert sold_out.json()["stock_units"][0]["quantity"] == 0
    assert sold_out.json()["stock_units"][0]["in_stock"] is False
    assert api.get("/api/items").json()["results"][0]["in_stock"] is False

    assert api.post(f"/api/purchase-orders/{order_id}/cancel", token=token).status_code == 200

    restored = api.get(f"/api/items/{item.item_id}")
    assert restored.json()["stock_units"][0]["quantity"] == 1
    assert restored.json()["stock_units"][0]["in_stock"] is True
    assert api.get("/api/items").json()["results"][0]["in_stock"] is True

    api.post("/api/cart/lines", {"stock_unit_id": unit.stock_unit_id, "quantity": 1}, token=token)
    second_checkout = api.post("/api/checkout", dict(_helpers.VALID_ADDRESS), token=token)
    assert second_checkout.status_code == 201
    assert PurchaseOrder.objects.count() == 2
    unit.refresh_from_db()
    assert unit.quantity == 0


# trace: FR-031, FR-042
@pytest.mark.case("IT-AI-GF-007")
def test_declined_payment_can_be_retried_and_is_visible_to_admin(api):
    """否認後も再支払でき、管理者向け注文詳細に否認・承認の決済記録が残る（FR-031 手順10、FR-042）。"""
    supplier = _helpers.make_supplier()
    item = _helpers.make_item()
    unit = _helpers.make_stock_unit(item, supplier, quantity=5)
    _helpers.make_user(email="buyer@example.com")
    _helpers.make_admin(email="admin@example.com")
    token = api.login("buyer@example.com")

    api.post("/api/cart/lines", {"stock_unit_id": unit.stock_unit_id, "quantity": 1}, token=token)
    order_id = api.post("/api/checkout", dict(_helpers.VALID_ADDRESS), token=token).json()["purchase_order_id"]

    declined = api.post(f"/api/purchase-orders/{order_id}/pay", {"mock_result": "decline"}, token=token)
    assert declined.status_code == 409
    assert _helpers.error_code(declined) == "PAYMENT_DECLINED"
    after_decline = api.get(f"/api/purchase-orders/{order_id}", token=token)
    assert after_decline.json()["status"] == PurchaseOrderStatus.CREATED
    assert after_decline.json()["can_pay"] is True

    approved = api.post(f"/api/purchase-orders/{order_id}/pay", {"mock_result": "approve"}, token=token)
    assert approved.status_code == 200
    assert approved.json()["status"] == PurchaseOrderStatus.PAID

    admin_token = api.login("admin@example.com")
    admin_detail = api.get(f"/api/admin/purchase-orders/{order_id}", token=admin_token)
    results = [record["result"] for record in admin_detail.json()["payment_records"]]
    assert results == [PaymentResult.DECLINED, PaymentResult.APPROVED]
    assert PaymentRecord.objects.filter(purchase_order_id=order_id).count() == 2
    assert PurchaseOrderStatusHistory.objects.filter(purchase_order_id=order_id).count() == 2
    unit.refresh_from_db()
    assert unit.quantity == 4
