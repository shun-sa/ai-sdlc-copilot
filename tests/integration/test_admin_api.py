# trace: FR-040, FR-041, FR-042, FR-043, FR-044, FR-045, ADDR-001, ADDR-004, ADDR-006, ADDR-007
"""管理者機能（FR-040〜FR-045）の結合試験。

期待結果は機能要件定義書 6.20〜6.25（処理内容・出力項目・例外）、
8.1 注文の状態遷移（ST-PO-05、ST-PO-06）、api-contract 6.1〜6.3 から導出する。
"""
from datetime import datetime

import pytest
from django.utils import timezone

from shop.models import PaymentRecord, PurchaseOrder, PurchaseOrderStatus, PurchaseOrderStatusHistory
from tests.integration import _helpers

pytestmark = pytest.mark.django_db


# trace: FR-040
def _admin_token(api):
    """管理者を作成し、認証トークンを返す。"""
    _helpers.make_admin(email="admin@example.com")
    return api.login("admin@example.com")


# trace: FR-041
def _buyer_order(api, email="buyer@example.com", sku="SKU-001", quantity=2, stock=10):
    """購入者の注文を1件作成し、購入者トークン・注文・在庫単位を返す。"""
    _helpers.make_user(email=email)
    token = api.login(email)
    supplier = _helpers.make_supplier(supplier_code=f"SUP-{sku}")
    item = _helpers.make_item(item_code=f"ITEM-{sku}", name=f"商品{sku}")
    unit = _helpers.make_stock_unit(item, supplier, sku=sku, quantity=stock)
    api.post("/api/cart/lines", {"stock_unit_id": unit.stock_unit_id, "quantity": quantity}, token=token)
    response = api.post("/api/checkout", dict(_helpers.VALID_ADDRESS), token=token)
    assert response.status_code == 201, response.content
    return token, PurchaseOrder.objects.get(purchase_order_id=response.json()["purchase_order_id"]), unit


# trace: FR-040, ADDR-006
@pytest.mark.case("IT-AI-046")
def test_admin_stock_unit_list_includes_private_items(api):
    """在庫単位一覧（管理者）は非公開商品を含む全在庫単位を50件/ページで返す（FR-040 手順5・12）。"""
    token = _admin_token(api)
    supplier = _helpers.make_supplier(supplier_code="SUP-001", name="サンプル商事")
    public_item = _helpers.make_item(item_code="ITEM-PUB", name="公開商品")
    private_item = _helpers.make_item(item_code="ITEM-PRI", name="非公開商品", is_public=False)
    low = _helpers.make_stock_unit(public_item, supplier, sku="SKU-001", quantity=5)
    private_unit = _helpers.make_stock_unit(private_item, supplier, sku="SKU-002", quantity=6)

    response = api.get("/api/admin/stock-units", token=token)

    assert response.status_code == 200
    body = response.json()
    assert body["page"] == 1
    assert body["page_size"] == 50
    assert body["total_count"] == 2
    assert body["total_pages"] == 1
    assert [row["stock_unit_id"] for row in body["results"]] == [low.stock_unit_id, private_unit.stock_unit_id]
    assert body["results"][0]["quantity"] == 5
    assert body["results"][0]["is_low_stock"] is True
    assert body["results"][0]["item_name"] == public_item.name
    assert body["results"][0]["item_is_public"] is True
    assert body["results"][0]["supplier_name"] == supplier.name
    assert body["results"][1]["item_is_public"] is False
    assert body["results"][1]["is_low_stock"] is False


# trace: FR-041, ADDR-006
@pytest.mark.case("IT-AI-047")
def test_admin_order_search_filters(api):
    """注文一覧検索（管理者）は注文番号・状態複数指定・注文日・購入者メールで絞り込む（FR-041 手順5〜10）。"""
    admin_token = _admin_token(api)
    buyer_token, first_order, _first_unit = _buyer_order(api, sku="SKU-A")
    _other_token, second_order, _second_unit = _buyer_order(api, email="other@example.com", sku="SKU-B")
    assert api.post(f"/api/purchase-orders/{first_order.purchase_order_id}/pay", {}, token=buyer_token).status_code == 200

    old_day = timezone.make_aware(datetime(2027, 3, 1, 23, 59, 59), timezone.get_current_timezone())
    new_day = timezone.make_aware(datetime(2027, 3, 2, 0, 0, 0), timezone.get_current_timezone())
    PurchaseOrder.objects.filter(purchase_order_id=first_order.purchase_order_id).update(ordered_at=old_day)
    PurchaseOrder.objects.filter(purchase_order_id=second_order.purchase_order_id).update(ordered_at=new_day)

    by_number = api.get("/api/admin/purchase-orders", {"order_number": first_order.order_number}, token=admin_token)
    by_status = api.get("/api/admin/purchase-orders", {"status": ["paid", "created"]}, token=admin_token)
    by_date = api.get("/api/admin/purchase-orders", {"ordered_from": "2027-03-02"}, token=admin_token)
    by_email = api.get("/api/admin/purchase-orders", {"buyer_email": "other@example.com"}, token=admin_token)
    by_and = api.get(
        "/api/admin/purchase-orders",
        {"status": ["created"], "buyer_email": "buyer@example.com"},
        token=admin_token,
    )

    assert by_number.status_code == 200
    assert [row["purchase_order_id"] for row in by_number.json()["results"]] == [first_order.purchase_order_id]
    assert by_number.json()["page_size"] == 20
    assert by_number.json()["results"][0]["buyer_email"] == "buyer@example.com"
    assert by_number.json()["results"][0]["buyer_name"] == "山田 太郎"

    assert {row["purchase_order_id"] for row in by_status.json()["results"]} == {
        first_order.purchase_order_id,
        second_order.purchase_order_id,
    }
    assert [row["purchase_order_id"] for row in by_date.json()["results"]] == [second_order.purchase_order_id]
    assert [row["purchase_order_id"] for row in by_email.json()["results"]] == [second_order.purchase_order_id]
    assert by_and.json()["results"] == []


# trace: FR-042, ADDR-004
@pytest.mark.case("IT-AI-048")
def test_admin_order_detail_includes_buyer_and_payment_records(api):
    """注文詳細（管理者）は購入者情報・決済記録・実行者の利用者IDを含めて返す（FR-042 6.22.5）。"""
    admin_token = _admin_token(api)
    buyer_token, order, _unit = _buyer_order(api)
    assert api.post(f"/api/purchase-orders/{order.purchase_order_id}/pay", {}, token=buyer_token).status_code == 200

    response = api.get(f"/api/admin/purchase-orders/{order.purchase_order_id}", token=admin_token)

    assert response.status_code == 200
    body = response.json()
    assert body["buyer"] == {
        "user_id": order.user_id,
        "email": "buyer@example.com",
        "full_name": "山田 太郎",
    }
    record = PaymentRecord.objects.get()
    assert body["payment_records"] == [
        {
            "result": record.result,
            "amount": record.amount,
            "transaction_ref": record.transaction_ref,
            "processed_at": body["payment_records"][0]["processed_at"],
        }
    ]
    assert set(body["status_history"][0]) == {"from_status", "to_status", "changed_at", "actor_role", "actor_user_id"}
    assert body["status_history"][0]["actor_user_id"] == order.user_id
    assert set(body) >= {"lines", "amounts", "shipping_address", "can_ship", "can_deliver"}


# trace: FR-043, ADDR-001, ADDR-007
@pytest.mark.case("IT-AI-049")
def test_admin_ship_only_from_paid(api):
    """出荷登録は支払済からのみ成功し、それ以外は状態遷移エラーとなる（ST-PO-05）。"""
    admin_token = _admin_token(api)
    buyer_token, paid_order, _paid_unit = _buyer_order(api, sku="SKU-A")
    assert api.post(f"/api/purchase-orders/{paid_order.purchase_order_id}/pay", {}, token=buyer_token).status_code == 200
    created_token, created_order, _created_unit = _buyer_order(api, email="other@example.com", sku="SKU-B")
    cancel = api.post(f"/api/purchase-orders/{created_order.purchase_order_id}/cancel", token=created_token)
    assert cancel.status_code == 200
    _third_token, third_order, _third_unit = _buyer_order(api, email="third@example.com", sku="SKU-C")

    shipped = api.post(
        f"/api/admin/purchase-orders/{paid_order.purchase_order_id}/ship",
        {"tracking_number": "TRK-0001"},
        token=admin_token,
    )
    on_created = api.post(
        f"/api/admin/purchase-orders/{third_order.purchase_order_id}/ship", {}, token=admin_token
    )
    on_cancelled = api.post(
        f"/api/admin/purchase-orders/{created_order.purchase_order_id}/ship", {}, token=admin_token
    )

    assert shipped.status_code == 200
    assert shipped.json()["status"] == PurchaseOrderStatus.SHIPPED
    assert shipped.json()["tracking_number"] == "TRK-0001"
    assert shipped.json()["shipped_at"] is not None
    history = PurchaseOrderStatusHistory.objects.filter(purchase_order=paid_order).order_by("status_history_id").last()
    assert (history.from_status, history.to_status) == (PurchaseOrderStatus.PAID, PurchaseOrderStatus.SHIPPED)
    assert history.actor_role == "admin"

    assert on_created.status_code == 409
    assert on_created.json()["error"]["context"] == {"current_status": PurchaseOrderStatus.CREATED}
    assert on_cancelled.status_code == 409
    assert on_cancelled.json()["error"]["context"] == {"current_status": PurchaseOrderStatus.CANCELLED}
    third_order.refresh_from_db()
    assert third_order.status == PurchaseOrderStatus.CREATED


# trace: FR-044, ADDR-001
@pytest.mark.case("IT-AI-050")
def test_admin_deliver_only_from_shipped(api):
    """配達完了登録は出荷済からのみ成功する（ST-PO-06）。"""
    admin_token = _admin_token(api)
    buyer_token, order, _unit = _buyer_order(api)
    api.post(f"/api/purchase-orders/{order.purchase_order_id}/pay", {}, token=buyer_token)

    on_paid = api.post(f"/api/admin/purchase-orders/{order.purchase_order_id}/deliver", {}, token=admin_token)
    api.post(f"/api/admin/purchase-orders/{order.purchase_order_id}/ship", {}, token=admin_token)
    delivered = api.post(f"/api/admin/purchase-orders/{order.purchase_order_id}/deliver", {}, token=admin_token)

    assert on_paid.status_code == 409
    assert on_paid.json()["error"]["context"] == {"current_status": PurchaseOrderStatus.PAID}
    assert delivered.status_code == 200
    assert delivered.json()["status"] == PurchaseOrderStatus.DELIVERED
    assert delivered.json()["delivered_at"] is not None
    history = PurchaseOrderStatusHistory.objects.filter(purchase_order=order).order_by("status_history_id").last()
    assert (history.from_status, history.to_status) == (PurchaseOrderStatus.SHIPPED, PurchaseOrderStatus.DELIVERED)


# trace: FR-045, ADDR-001
@pytest.mark.case("IT-AI-051")
def test_admin_cancel_restores_stock_before_shipment(api):
    """管理者キャンセルは注文受付・支払済から成功して在庫を戻し、出荷済以降は拒否される（FR-045）。"""
    admin_token = _admin_token(api)
    _created_token, created_order, created_unit = _buyer_order(api, sku="SKU-A")
    paid_token, paid_order, paid_unit = _buyer_order(api, email="other@example.com", sku="SKU-B")
    api.post(f"/api/purchase-orders/{paid_order.purchase_order_id}/pay", {}, token=paid_token)
    shipped_token, shipped_order, shipped_unit = _buyer_order(api, email="third@example.com", sku="SKU-C")
    api.post(f"/api/purchase-orders/{shipped_order.purchase_order_id}/pay", {}, token=shipped_token)
    api.post(f"/api/admin/purchase-orders/{shipped_order.purchase_order_id}/ship", {}, token=admin_token)

    from_created = api.post(
        f"/api/admin/purchase-orders/{created_order.purchase_order_id}/cancel", {}, token=admin_token
    )
    from_paid = api.post(f"/api/admin/purchase-orders/{paid_order.purchase_order_id}/cancel", {}, token=admin_token)
    from_shipped = api.post(
        f"/api/admin/purchase-orders/{shipped_order.purchase_order_id}/cancel", {}, token=admin_token
    )

    assert from_created.status_code == 200
    assert from_created.json()["status"] == PurchaseOrderStatus.CANCELLED
    assert from_paid.status_code == 200
    assert from_shipped.status_code == 409
    assert from_shipped.json()["error"]["context"] == {"current_status": PurchaseOrderStatus.SHIPPED}

    created_unit.refresh_from_db()
    paid_unit.refresh_from_db()
    shipped_unit.refresh_from_db()
    assert created_unit.quantity == 10
    assert paid_unit.quantity == 10
    assert shipped_unit.quantity == 8
    last_history = (
        PurchaseOrderStatusHistory.objects.filter(purchase_order=paid_order).order_by("status_history_id").last()
    )
    assert last_history.actor_role == "admin"
    assert last_history.to_status == PurchaseOrderStatus.CANCELLED
