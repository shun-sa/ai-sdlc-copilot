# trace: FR-031, FR-032, FR-033, FR-034, ADDR-001, ADDR-004, ADDR-006, ADDR-007, ADDR-009
"""支払・注文照会・注文キャンセル（FR-031〜FR-034）の結合試験。

期待結果は機能要件定義書 6.16〜6.19（処理内容・事後条件・例外 E-031-03〜E-031-07、E-034-05）、
8.1 注文の状態遷移（ST-PO-02〜ST-PO-04）、api-contract 6.2・6.3、ADDR-009 から導出する。
"""
import re
import time

import pytest

from shop.models import PaymentRecord, PaymentResult, PurchaseOrder, PurchaseOrderStatus, PurchaseOrderStatusHistory
from shop.payments import mock as payment_mock
from shop.payments.gateway import PaymentResponse
from tests.integration import _helpers

pytestmark = pytest.mark.django_db

TRANSACTION_REF_PATTERN = re.compile(r"^MOCK-[A-Za-z0-9]{16}$")


# trace: FR-031
def _ordered(api, email="buyer@example.com", sku="SKU-001", quantity=2, stock=10, price=1000):
    """購入者・注文を1件作成し、トークン・注文・在庫単位を返す。"""
    _helpers.make_user(email=email)
    token = api.login(email)
    supplier = _helpers.make_supplier(supplier_code=f"SUP-{sku}")
    item = _helpers.make_item(item_code=f"ITEM-{sku}", name=f"商品{sku}")
    unit = _helpers.make_stock_unit(item, supplier, sku=sku, price=price, quantity=stock)
    assert (
        api.post("/api/cart/lines", {"stock_unit_id": unit.stock_unit_id, "quantity": quantity}, token=token)
    ).status_code == 200
    response = api.post("/api/checkout", dict(_helpers.VALID_ADDRESS), token=token)
    assert response.status_code == 201, response.content
    order = PurchaseOrder.objects.get(purchase_order_id=response.json()["purchase_order_id"])
    return token, order, unit


# trace: FR-031, ADDR-009
@pytest.mark.case("IT-AI-037")
def test_payment_approved_moves_order_to_paid(api):
    """支払（承認）で注文が支払済になり決済記録と状態履歴が登録される（ST-PO-02）。"""
    token, order, unit = _ordered(api)

    response = api.post(f"/api/purchase-orders/{order.purchase_order_id}/pay", {"mock_result": "approve"}, token=token)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == PurchaseOrderStatus.PAID
    assert body["paid_at"] is not None
    assert body["can_pay"] is False
    assert "payment_records" not in body

    order.refresh_from_db()
    assert order.status == PurchaseOrderStatus.PAID
    assert order.paid_at is not None

    record = PaymentRecord.objects.get()
    assert record.result == PaymentResult.APPROVED
    assert record.amount == order.total
    assert TRANSACTION_REF_PATTERN.match(record.transaction_ref)

    history = list(PurchaseOrderStatusHistory.objects.order_by("status_history_id"))
    assert [(entry.from_status, entry.to_status) for entry in history] == [
        (None, PurchaseOrderStatus.CREATED),
        (PurchaseOrderStatus.CREATED, PurchaseOrderStatus.PAID),
    ]
    assert history[1].actor_role == "buyer"
    unit.refresh_from_db()
    assert unit.quantity == 8


# trace: FR-031, ADDR-007, ADDR-009
@pytest.mark.case("IT-AI-038")
def test_payment_declined_keeps_order_created(api):
    """支払が否認された場合は注文受付のままで否認の決済記録が残る（E-031-06、CMN-21）。"""
    token, order, unit = _ordered(api)

    response = api.post(f"/api/purchase-orders/{order.purchase_order_id}/pay", {"mock_result": "decline"}, token=token)

    assert response.status_code == 409
    assert _helpers.error_code(response) == "PAYMENT_DECLINED"
    order.refresh_from_db()
    assert order.status == PurchaseOrderStatus.CREATED
    assert order.paid_at is None

    record = PaymentRecord.objects.get()
    assert record.result == PaymentResult.DECLINED
    assert record.transaction_ref is None
    assert record.amount == order.total
    assert PurchaseOrderStatusHistory.objects.count() == 1
    unit.refresh_from_db()
    assert unit.quantity == 8


# trace: FR-031, ADDR-009
@pytest.mark.case("IT-AI-039")
def test_payment_gateway_error_records_error_without_retry(api, monkeypatch, settings):
    """決済サービスの応答不正・締切超過は連携エラーの決済記録を残し、自動再送しない（E-031-07）。"""
    token, order, unit = _ordered(api)
    original_authorize = payment_mock.MockPaymentGateway.authorize
    calls: list[str] = []

    def invalid_response(self, request):
        """応答不正（結果が承認・否認のいずれでもない）を返す。"""
        calls.append("invalid")
        return PaymentResponse(result="unknown", transaction_ref=None, declined_reason_code=None, processed_at=None)

    def slow_response(self, request):
        """締切を超えてから正常な承認応答を返す。"""
        calls.append("slow")
        time.sleep(0.05)
        return original_authorize(self, request)

    monkeypatch.setattr(payment_mock.MockPaymentGateway, "authorize", invalid_response)
    invalid = api.post(
        f"/api/purchase-orders/{order.purchase_order_id}/pay", {"mock_result": "approve"}, token=token
    )

    settings.PAYMENT_TIMEOUT_SECONDS = 0.01
    monkeypatch.setattr(payment_mock.MockPaymentGateway, "authorize", slow_response)
    timed_out = api.post(
        f"/api/purchase-orders/{order.purchase_order_id}/pay", {"mock_result": "approve"}, token=token
    )

    assert invalid.status_code == 502
    assert _helpers.error_code(invalid) == "PAYMENT_SERVICE_ERROR"
    assert timed_out.status_code == 502
    assert _helpers.error_code(timed_out) == "PAYMENT_SERVICE_ERROR"
    assert calls == ["invalid", "slow"]

    records = list(PaymentRecord.objects.order_by("payment_record_id"))
    assert [record.result for record in records] == [PaymentResult.ERROR, PaymentResult.ERROR]
    assert all(record.transaction_ref is None for record in records)
    order.refresh_from_db()
    assert order.status == PurchaseOrderStatus.CREATED
    assert order.paid_at is None
    assert PurchaseOrderStatusHistory.objects.count() == 1
    unit.refresh_from_db()
    assert unit.quantity == 8


# trace: FR-031, ADDR-007
@pytest.mark.case("IT-AI-040")
def test_payment_rejected_for_non_created_orders(api):
    """注文受付以外の注文への支払は状態遷移エラーとなり決済記録も増えない（E-031-05）。"""
    token, paid_order, _unit = _ordered(api)
    assert (
        api.post(f"/api/purchase-orders/{paid_order.purchase_order_id}/pay", {}, token=token).status_code == 200
    )
    cancelled_token, cancelled_order, _cancelled_unit = _ordered(api, email="other@example.com", sku="SKU-002")
    assert (
        api.post(f"/api/purchase-orders/{cancelled_order.purchase_order_id}/cancel", token=cancelled_token)
    ).status_code == 200
    payment_count = PaymentRecord.objects.count()

    on_paid = api.post(f"/api/purchase-orders/{paid_order.purchase_order_id}/pay", {}, token=token)
    on_cancelled = api.post(
        f"/api/purchase-orders/{cancelled_order.purchase_order_id}/pay", {}, token=cancelled_token
    )

    assert on_paid.status_code == 409
    assert _helpers.error_code(on_paid) == "INVALID_STATUS_TRANSITION"
    assert on_paid.json()["error"]["context"] == {"current_status": PurchaseOrderStatus.PAID}
    assert on_cancelled.status_code == 409
    assert on_cancelled.json()["error"]["context"] == {"current_status": PurchaseOrderStatus.CANCELLED}
    assert PaymentRecord.objects.count() == payment_count


# trace: FR-031, ADDR-007
@pytest.mark.case("IT-AI-041")
def test_payment_for_other_buyers_order_is_not_found(api):
    """他の購入者の注文への支払は対象なしとし、決済要求を送信しない（PRM-01、CMN-04）。"""
    _token, other_order, _unit = _ordered(api, email="other@example.com")
    _helpers.make_user(email="buyer@example.com")
    token = api.login("buyer@example.com")

    response = api.post(f"/api/purchase-orders/{other_order.purchase_order_id}/pay", {}, token=token)

    assert response.status_code == 404
    assert _helpers.error_code(response) == "NOT_FOUND"
    assert PaymentRecord.objects.count() == 0
    other_order.refresh_from_db()
    assert other_order.status == PurchaseOrderStatus.CREATED


# trace: FR-032, ADDR-006
@pytest.mark.case("IT-AI-042")
def test_order_list_returns_only_own_orders_newest_first(api):
    """注文履歴一覧は本人の注文のみを注文日時の新しい順・20件/ページで返す（FR-032）。"""
    token, first_order, _unit = _ordered(api, sku="SKU-A", quantity=1)
    supplier = _helpers.make_supplier(supplier_code="SUP-B")
    item = _helpers.make_item(item_code="ITEM-B", name="商品B")
    second_unit = _helpers.make_stock_unit(item, supplier, sku="SKU-B")
    api.post("/api/cart/lines", {"stock_unit_id": second_unit.stock_unit_id, "quantity": 1}, token=token)
    second = api.post("/api/checkout", dict(_helpers.VALID_ADDRESS), token=token)
    _other_token, other_order, _other_unit = _ordered(api, email="other@example.com", sku="SKU-C")

    response = api.get("/api/purchase-orders", token=token)

    assert response.status_code == 200
    body = response.json()
    assert body["page"] == 1
    assert body["page_size"] == 20
    assert body["total_count"] == 2
    returned = [row["purchase_order_id"] for row in body["results"]]
    assert returned == [second.json()["purchase_order_id"], first_order.purchase_order_id]
    assert other_order.purchase_order_id not in returned
    assert set(body["results"][0]) >= {"order_number", "ordered_at", "status", "total", "total_quantity"}


# trace: FR-033, ADDR-004, ADDR-007
@pytest.mark.case("IT-AI-043")
def test_order_detail_for_buyer_hides_payment_records_and_other_orders(api):
    """購入者向け注文詳細は明細・金額・配送先・状態履歴を返し、他人の注文は対象なしとなる（MSG-04、PRM-01）。"""
    token, order, _unit = _ordered(api)
    assert api.post(f"/api/purchase-orders/{order.purchase_order_id}/pay", {}, token=token).status_code == 200
    _other_token, other_order, _other_unit = _ordered(api, email="other@example.com", sku="SKU-002")

    own = api.get(f"/api/purchase-orders/{order.purchase_order_id}", token=token)
    other = api.get(f"/api/purchase-orders/{other_order.purchase_order_id}", token=token)
    unknown = api.get("/api/purchase-orders/999999", token=token)

    assert own.status_code == 200
    body = own.json()
    assert set(body) >= {"lines", "amounts", "coupon", "shipping_address", "status_history"}
    assert "payment_records" not in body
    assert "buyer" not in body
    assert body["coupon"] is None
    assert body["shipping_address"]["postal_code"] == "1234567"
    assert set(body["status_history"][0]) == {"from_status", "to_status", "changed_at", "actor_role"}
    assert other.status_code == 404
    assert unknown.status_code == 404
    assert other.json()["error"] == unknown.json()["error"]


# trace: FR-034, ADDR-001
@pytest.mark.case("IT-AI-044")
def test_buyer_cancel_restores_stock_from_created_and_paid(api):
    """購入者キャンセルは注文受付・支払済から成功し、在庫を戻して履歴を追加する（ST-PO-03、ST-PO-04）。"""
    created_token, created_order, created_unit = _ordered(api, sku="SKU-A")
    paid_token, paid_order, paid_unit = _ordered(api, email="other@example.com", sku="SKU-B")
    assert api.post(f"/api/purchase-orders/{paid_order.purchase_order_id}/pay", {}, token=paid_token).status_code == 200
    payment_count = PaymentRecord.objects.count()

    from_created = api.post(f"/api/purchase-orders/{created_order.purchase_order_id}/cancel", token=created_token)
    from_paid = api.post(f"/api/purchase-orders/{paid_order.purchase_order_id}/cancel", token=paid_token)

    assert from_created.status_code == 200
    assert from_paid.status_code == 200
    assert from_created.json()["status"] == PurchaseOrderStatus.CANCELLED
    assert from_created.json()["cancelled_at"] is not None
    assert from_paid.json()["status"] == PurchaseOrderStatus.CANCELLED

    created_unit.refresh_from_db()
    paid_unit.refresh_from_db()
    assert created_unit.quantity == 10
    assert paid_unit.quantity == 10
    assert PurchaseOrderStatusHistory.objects.filter(purchase_order=created_order).count() == 2
    assert PurchaseOrderStatusHistory.objects.filter(purchase_order=paid_order).count() == 3
    assert PaymentRecord.objects.count() == payment_count


# trace: FR-034, ADDR-007
@pytest.mark.case("IT-AI-045")
def test_buyer_cancel_rejected_after_shipment(api):
    """出荷済以降・キャンセル済の注文はキャンセルできず在庫も二重に戻らない（E-034-05）。"""
    token, order, unit = _ordered(api)
    api.post(f"/api/purchase-orders/{order.purchase_order_id}/cancel", token=token)
    unit.refresh_from_db()
    restored_quantity = unit.quantity
    history_count = PurchaseOrderStatusHistory.objects.count()

    second_cancel = api.post(f"/api/purchase-orders/{order.purchase_order_id}/cancel", token=token)

    shipped_token, shipped_order, shipped_unit = _ordered(api, email="other@example.com", sku="SKU-B")
    PurchaseOrder.objects.filter(purchase_order_id=shipped_order.purchase_order_id).update(
        status=PurchaseOrderStatus.SHIPPED
    )
    on_shipped = api.post(f"/api/purchase-orders/{shipped_order.purchase_order_id}/cancel", token=shipped_token)

    PurchaseOrder.objects.filter(purchase_order_id=shipped_order.purchase_order_id).update(
        status=PurchaseOrderStatus.DELIVERED
    )
    on_delivered = api.post(f"/api/purchase-orders/{shipped_order.purchase_order_id}/cancel", token=shipped_token)

    assert second_cancel.status_code == 409
    assert second_cancel.json()["error"]["context"] == {"current_status": PurchaseOrderStatus.CANCELLED}
    assert on_shipped.status_code == 409
    assert on_shipped.json()["error"]["context"] == {"current_status": PurchaseOrderStatus.SHIPPED}
    assert on_delivered.status_code == 409
    assert on_delivered.json()["error"]["context"] == {"current_status": PurchaseOrderStatus.DELIVERED}

    unit.refresh_from_db()
    shipped_unit.refresh_from_db()
    assert unit.quantity == restored_quantity
    assert shipped_unit.quantity == 8
    assert PurchaseOrderStatusHistory.objects.count() == history_count + 1


# trace: FR-031, ADDR-007
@pytest.mark.case("IT-AI-GF-006")
def test_payment_rejects_invalid_mock_result(api):
    """模擬決済指示が approve／decline 以外の場合は入力エラーとし、データを変更しない（E-031-03）。"""
    token, order, unit = _ordered(api)

    response = api.post(
        f"/api/purchase-orders/{order.purchase_order_id}/pay", {"mock_result": "APPROVE"}, token=token
    )

    assert response.status_code == 400
    assert _helpers.error_code(response) == "VALIDATION_ERROR"
    assert "mock_result" in _helpers.error_fields(response)
    assert PaymentRecord.objects.count() == 0
    order.refresh_from_db()
    assert order.status == PurchaseOrderStatus.CREATED
    assert order.paid_at is None
    unit.refresh_from_db()
    assert unit.quantity == 8
