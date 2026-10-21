# trace: FR-030, FR-031, FR-032, FR-033, FR-034, FR-043, FR-044, FR-045, NFR-EN-04, NFR-PF-08
# trace: ADDR-003, ADDR-008, ADDR-010
"""注文履歴・注文詳細・注文キャンセル（購入者）の結合試験（IT-AI-INIT-117〜128）。

検証対象の連携は API → Service → ORM → PostgreSQL、共通ページング基盤 → 一覧API、
権限判定 → 業務機能API、トランザクション・同時実行制御 → PostgreSQL。

期待結果は FR-032・FR-033・FR-034 の処理内容・出力・例外、CMN-26（状態履歴）、
ST-PO-03/ST-PO-04、PRM-01（他人の注文は存在を明かさない）、提供済みAPI契約 6.1/6.2
から導出する。
"""

from __future__ import annotations

import datetime as dt

import pytest
from rest_framework.test import APIClient

from orders.models import (
    STATUS_CANCELLED,
    STATUS_CREATED,
    STATUS_DELIVERED,
    STATUS_PAID,
    STATUS_SHIPPED,
    PaymentRecord,
    PurchaseOrder,
)

pytestmark = pytest.mark.django_db

SHIPPING = {
    "recipient_name": "結合 受取人",
    "postal_code": "1234567",
    "prefecture_code": "13",
    "address_line1": "千代田区1-1-1",
    "address_line2": "結合ビル101",
    "phone_number": "09012345678",
}


# trace: FR-030
def place_order(client, f, *, price: int = 1000, quantity: int = 1, coupon_code: str | None = None) -> dict:
    """注文受付の注文を1件作る（試験前提データの準備）。"""
    unit = f.sellable(price=price, quantity=quantity + 20)
    client.post("/api/cart/lines", {"stock_unit_id": unit.pk, "quantity": quantity}, format="json")
    if coupon_code:
        client.post("/api/cart/apply-coupon", {"code": coupon_code}, format="json")
    response = client.post("/api/checkout", SHIPPING, format="json")
    assert response.status_code == 201
    return response.json()


# trace: FR-032
def test_it_ai_init_117_order_history_returns_own_orders_in_order(
    api_as, buyer, other_buyer, f
):
    """IT-AI-INIT-117 / COV-101：注文履歴は自分の注文のみを注文日時降順（同値は注文ID降順）で返す。"""
    client = api_as(buyer)
    other_client = api_as(other_buyer)
    first = place_order(client, f)
    second = place_order(client, f)
    third = place_order(client, f)
    others = place_order(other_client, f)
    same_moment = dt.datetime(2027, 8, 1, 12, 0, 0, tzinfo=dt.timezone(dt.timedelta(hours=9)))
    PurchaseOrder.objects.filter(
        pk__in=[first["purchase_order_id"], second["purchase_order_id"]]
    ).update(ordered_at=same_moment)
    PurchaseOrder.objects.filter(pk=third["purchase_order_id"]).update(
        ordered_at=same_moment - dt.timedelta(hours=1)
    )

    response = client.get("/api/purchase-orders")

    assert response.status_code == 200
    body = response.json()
    ids = [row["purchase_order_id"] for row in body["results"]]
    assert ids == [second["purchase_order_id"], first["purchase_order_id"], third["purchase_order_id"]]
    assert others["purchase_order_id"] not in ids
    assert body["total_count"] == 3
    summary = body["results"][0]
    assert summary["order_number"] == second["order_number"]
    assert summary["status"] == STATUS_CREATED
    assert summary["total"] == second["amounts"]["total"]
    assert summary["total_quantity"] == 1


# trace: FR-032, NFR-PF-08
def test_it_ai_init_118_order_history_pagination(api_as, buyer, other_buyer, f, err):
    """IT-AI-INIT-118 / COV-102：注文履歴は1ページ20件で、0件・超過ページは空、不正ページは入力エラーとする。"""
    client = api_as(buyer)
    unit = f.sellable(price=1000, quantity=100)
    for _ in range(21):
        client.post("/api/cart/lines", {"stock_unit_id": unit.pk, "quantity": 1}, format="json")
        assert client.post("/api/checkout", SHIPPING, format="json").status_code == 201

    first = client.get("/api/purchase-orders").json()
    second = client.get("/api/purchase-orders", {"page": 2}).json()
    beyond = client.get("/api/purchase-orders", {"page": 3})
    empty = api_as(other_buyer).get("/api/purchase-orders")

    assert first["page_size"] == 20 and first["total_count"] == 21 and first["total_pages"] == 2
    assert len(first["results"]) == 20
    assert len(second["results"]) == 1
    assert beyond.status_code == 200 and beyond.json()["results"] == []
    assert empty.status_code == 200 and empty.json()["results"] == [] and empty.json()["total_count"] == 0

    for page in (0, "abc"):
        invalid = client.get("/api/purchase-orders", {"page": page})
        assert invalid.status_code == 400, page
        assert err.code(invalid) == "VALIDATION_ERROR"
        assert "page" in err.fields(invalid)


# trace: FR-033
def test_it_ai_init_119_order_detail_returns_snapshot(api_as, buyer, f):
    """IT-AI-INIT-119 / COV-103：注文詳細は金額・明細・クーポン・配送先・各日時を返す。"""
    client = api_as(buyer)
    f.coupon(code="DETAILCPN1", discount_value=1000)
    first = f.sellable(price=4000, quantity=10)
    second = f.sellable(price=3000, quantity=10)
    client.post("/api/cart/lines", {"stock_unit_id": first.pk, "quantity": 1}, format="json")
    client.post("/api/cart/lines", {"stock_unit_id": second.pk, "quantity": 2}, format="json")
    client.post("/api/cart/apply-coupon", {"code": "DETAILCPN1"}, format="json")
    created = client.post("/api/checkout", SHIPPING, format="json").json()

    response = client.get(f"/api/purchase-orders/{created['purchase_order_id']}")

    assert response.status_code == 200
    body = response.json()
    assert body["order_number"] == created["order_number"]
    assert body["amounts"] == {
        "subtotal": 10000,
        "discount_amount": 1000,
        "discounted_subtotal": 9000,
        "shipping_fee": 0,
        "tax_amount": 900,
        "total": 9900,
    }
    line_ids = [line["purchase_order_line_id"] for line in body["lines"]]
    assert line_ids == sorted(line_ids)
    assert [line["quantity"] for line in body["lines"]] == [1, 2]
    assert body["coupon"] == {"code": "DETAILCPN1", "discount_type": "fixed", "discount_value": 1000}
    assert body["shipping_address"] == {
        "recipient_name": "結合 受取人",
        "postal_code": "1234567",
        "prefecture_code": "13",
        "address_line1": "千代田区1-1-1",
        "address_line2": "結合ビル101",
        "phone_number": "09012345678",
    }
    assert body["ordered_at"].endswith("+09:00")
    assert body["paid_at"] is None


# trace: FR-033
def test_it_ai_init_120_status_history_is_ordered_by_changed_at(api_as, buyer, admin_user, f):
    """IT-AI-INIT-120 / COV-104：状態履歴は変更日時の昇順で実行者区分とともに返す（CMN-26）。"""
    client = api_as(buyer)
    admin_client = api_as(admin_user)
    order = place_order(client, f)
    order_id = order["purchase_order_id"]
    client.post(f"/api/purchase-orders/{order_id}/pay", {}, format="json")
    admin_client.post(f"/api/admin/purchase-orders/{order_id}/ship", {}, format="json")

    response = client.get(f"/api/purchase-orders/{order_id}")

    history = response.json()["status_history"]
    assert [(row["from_status"], row["to_status"]) for row in history] == [
        (None, STATUS_CREATED),
        (STATUS_CREATED, STATUS_PAID),
        (STATUS_PAID, STATUS_SHIPPED),
    ]
    assert [row["actor_role"] for row in history] == ["buyer", "buyer", "admin"]
    changed = [row["changed_at"] for row in history]
    assert changed == sorted(changed)
    assert all("actor_user_id" not in row for row in history)


# trace: FR-033
def test_it_ai_init_121_can_pay_and_can_cancel_per_status(api_as, buyer, admin_user, f):
    """IT-AI-INIT-121 / COV-105：can_pay は注文受付のみ、can_cancel は注文受付・支払済のみ true とする。"""
    client = api_as(buyer)
    admin_client = api_as(admin_user)

    created = place_order(client, f)
    paid = place_order(client, f)
    client.post(f"/api/purchase-orders/{paid['purchase_order_id']}/pay", {}, format="json")
    shipped = place_order(client, f)
    client.post(f"/api/purchase-orders/{shipped['purchase_order_id']}/pay", {}, format="json")
    admin_client.post(f"/api/admin/purchase-orders/{shipped['purchase_order_id']}/ship", {}, format="json")
    delivered = place_order(client, f)
    client.post(f"/api/purchase-orders/{delivered['purchase_order_id']}/pay", {}, format="json")
    admin_client.post(f"/api/admin/purchase-orders/{delivered['purchase_order_id']}/ship", {}, format="json")
    admin_client.post(f"/api/admin/purchase-orders/{delivered['purchase_order_id']}/deliver", {}, format="json")
    cancelled = place_order(client, f)
    client.post(f"/api/purchase-orders/{cancelled['purchase_order_id']}/cancel", {}, format="json")

    expected = {
        created["purchase_order_id"]: (STATUS_CREATED, True, True),
        paid["purchase_order_id"]: (STATUS_PAID, False, True),
        shipped["purchase_order_id"]: (STATUS_SHIPPED, False, False),
        delivered["purchase_order_id"]: (STATUS_DELIVERED, False, False),
        cancelled["purchase_order_id"]: (STATUS_CANCELLED, False, False),
    }
    for order_id, (status, can_pay, can_cancel) in expected.items():
        body = client.get(f"/api/purchase-orders/{order_id}").json()

        assert body["status"] == status
        assert body["can_pay"] is can_pay
        assert body["can_cancel"] is can_cancel

    created_body = client.get(f"/api/purchase-orders/{created['purchase_order_id']}").json()
    assert created_body["paid_at"] is None
    assert created_body["shipped_at"] is None
    assert created_body["delivered_at"] is None
    assert created_body["cancelled_at"] is None
    assert created_body["tracking_number"] is None
    assert created_body["coupon"] is None


# trace: FR-033
def test_it_ai_init_122_other_order_detail_is_not_found(api_as, buyer, other_buyer, f, err):
    """IT-AI-INIT-122 / COV-106：他人・存在しない注文の詳細は対象なしとする（PRM-01）。"""
    other_order = place_order(api_as(other_buyer), f)
    client = api_as(buyer)

    responses = [
        client.get(f"/api/purchase-orders/{other_order['purchase_order_id']}"),
        client.get("/api/purchase-orders/999999"),
    ]

    for response in responses:
        assert response.status_code == 404
        assert err.code(response) == "NOT_FOUND"


# trace: FR-032, FR-033
def test_it_ai_init_123_order_views_require_buyer(api, api_as, buyer, admin_user, f, err):
    """IT-AI-INIT-123 / COV-107：管理者は権限エラー、未ログインは認証エラーとする。"""
    order = place_order(api_as(buyer), f)
    paths = ["/api/purchase-orders", f"/api/purchase-orders/{order['purchase_order_id']}"]
    admin_client = api_as(admin_user)

    for path in paths:
        administrator = admin_client.get(path)
        anonymous = api.get(path)

        assert administrator.status_code == 403, path
        assert err.code(administrator) == "PERMISSION_DENIED"
        assert anonymous.status_code == 401, path
        assert err.code(anonymous) == "AUTHENTICATION_REQUIRED"


# trace: FR-034, ADDR-003
def test_it_ai_init_124_cancel_created_order_restores_stock(api_as, buyer, f):
    """IT-AI-INIT-124 / COV-109：注文受付の注文のキャンセルで在庫が戻る（ST-PO-03）。"""
    client = api_as(buyer)
    first = f.sellable(price=1000, quantity=10)
    second = f.sellable(price=2000, quantity=10)
    client.post("/api/cart/lines", {"stock_unit_id": first.pk, "quantity": 2}, format="json")
    client.post("/api/cart/lines", {"stock_unit_id": second.pk, "quantity": 3}, format="json")
    order = client.post("/api/checkout", SHIPPING, format="json").json()

    response = client.post(
        f"/api/purchase-orders/{order['purchase_order_id']}/cancel", {}, format="json"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == STATUS_CANCELLED
    assert body["cancelled_at"] is not None
    first.refresh_from_db()
    second.refresh_from_db()
    assert first.quantity == 10
    assert second.quantity == 10
    history = [(row["from_status"], row["to_status"]) for row in body["status_history"]]
    assert history[-1] == (STATUS_CREATED, STATUS_CANCELLED)
    assert body["status_history"][-1]["actor_role"] == "buyer"


# trace: FR-034
def test_it_ai_init_125_cancel_paid_order_keeps_payment_records(api_as, buyer, f):
    """IT-AI-INIT-125 / COV-109：支払済の注文のキャンセルで決済記録は変化しない（ST-PO-04）。"""
    client = api_as(buyer)
    unit = f.sellable(price=1000, quantity=10)
    client.post("/api/cart/lines", {"stock_unit_id": unit.pk, "quantity": 2}, format="json")
    order = client.post("/api/checkout", SHIPPING, format="json").json()
    order_id = order["purchase_order_id"]
    client.post(f"/api/purchase-orders/{order_id}/pay", {}, format="json")
    before = list(
        PaymentRecord.objects.filter(purchase_order_id=order_id).values(
            "id", "result", "amount", "transaction_ref"
        )
    )

    response = client.post(f"/api/purchase-orders/{order_id}/cancel", {}, format="json")

    assert response.status_code == 200
    assert response.json()["status"] == STATUS_CANCELLED
    unit.refresh_from_db()
    assert unit.quantity == 10
    after = list(
        PaymentRecord.objects.filter(purchase_order_id=order_id).values(
            "id", "result", "amount", "transaction_ref"
        )
    )
    assert after == before


# trace: FR-034
def test_it_ai_init_126_cancel_is_rejected_for_other_statuses(api_as, buyer, admin_user, f, err):
    """IT-AI-INIT-126 / COV-110：出荷済・配達完了・キャンセル済のキャンセルは状態遷移エラーとする。"""
    client = api_as(buyer)
    admin_client = api_as(admin_user)

    shipped = place_order(client, f, quantity=2)
    client.post(f"/api/purchase-orders/{shipped['purchase_order_id']}/pay", {}, format="json")
    admin_client.post(f"/api/admin/purchase-orders/{shipped['purchase_order_id']}/ship", {}, format="json")
    delivered = place_order(client, f, quantity=2)
    client.post(f"/api/purchase-orders/{delivered['purchase_order_id']}/pay", {}, format="json")
    admin_client.post(f"/api/admin/purchase-orders/{delivered['purchase_order_id']}/ship", {}, format="json")
    admin_client.post(f"/api/admin/purchase-orders/{delivered['purchase_order_id']}/deliver", {}, format="json")
    cancelled = place_order(client, f, quantity=2)
    client.post(f"/api/purchase-orders/{cancelled['purchase_order_id']}/cancel", {}, format="json")

    expected = {
        shipped["purchase_order_id"]: STATUS_SHIPPED,
        delivered["purchase_order_id"]: STATUS_DELIVERED,
        cancelled["purchase_order_id"]: STATUS_CANCELLED,
    }
    for order_id, status in expected.items():
        stock_before = {
            line.stock_unit_id: line.stock_unit.quantity
            for line in PurchaseOrder.objects.get(pk=order_id).lines.select_related("stock_unit")
        }

        response = client.post(f"/api/purchase-orders/{order_id}/cancel", {}, format="json")

        assert response.status_code == 409, status
        assert err.code(response) == "INVALID_STATUS_TRANSITION"
        assert err.context(response) == {"current_status": status}
        stock_after = {
            line.stock_unit_id: line.stock_unit.quantity
            for line in PurchaseOrder.objects.get(pk=order_id).lines.select_related("stock_unit")
        }
        assert stock_after == stock_before


# trace: FR-034, ADDR-003
@pytest.mark.django_db(transaction=True)
def test_it_ai_init_127_concurrent_cancel_restores_stock_once(f, token_for, run_parallel):
    """IT-AI-INIT-127 / COV-111：同一注文への同時キャンセルで在庫は1回だけ戻る（CMN-19）。"""
    buyer = f.user(email="race-cancel@example.test")
    token = token_for(buyer)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    unit = f.sellable(price=1000, quantity=10)
    client.post("/api/cart/lines", {"stock_unit_id": unit.pk, "quantity": 3}, format="json")
    order = client.post("/api/checkout", SHIPPING, format="json").json()
    order_id = order["purchase_order_id"]
    unit.refresh_from_db()
    assert unit.quantity == 7

    def cancel():
        worker = APIClient()
        worker.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        return worker.post(f"/api/purchase-orders/{order_id}/cancel", {}, format="json")

    try:
        results = run_parallel(cancel, cancel)

        statuses = sorted(response.status_code for response in results)
        assert statuses == [200, 409]
        failed = next(response for response in results if response.status_code == 409)
        body = failed.json()
        assert (body.get("error") or body)["code"] == "INVALID_STATUS_TRANSITION"
        unit.refresh_from_db()
        assert unit.quantity == 10
        assert PurchaseOrder.objects.get(pk=order_id).status == STATUS_CANCELLED
    finally:
        PurchaseOrder.objects.all().delete()


# trace: FR-034
def test_it_ai_init_128_cancel_rejects_other_users_and_roles(
    api, api_as, buyer, other_buyer, admin_user, f, err
):
    """IT-AI-INIT-128 / COV-112：他人・存在しない注文は対象なし、管理者は権限、未ログインは認証エラーとする。"""
    client = api_as(buyer)
    own = place_order(client, f)
    other_order = place_order(api_as(other_buyer), f)

    not_found = [
        client.post(f"/api/purchase-orders/{other_order['purchase_order_id']}/cancel", {}, format="json"),
        client.post("/api/purchase-orders/999999/cancel", {}, format="json"),
    ]
    administrator = api_as(admin_user).post(
        f"/api/purchase-orders/{own['purchase_order_id']}/cancel", {}, format="json"
    )
    anonymous = api.post(f"/api/purchase-orders/{own['purchase_order_id']}/cancel", {}, format="json")

    for response in not_found:
        assert response.status_code == 404
        assert err.code(response) == "NOT_FOUND"
    assert administrator.status_code == 403
    assert err.code(administrator) == "PERMISSION_DENIED"
    assert anonymous.status_code == 401
    assert err.code(anonymous) == "AUTHENTICATION_REQUIRED"
    assert PurchaseOrder.objects.get(pk=own["purchase_order_id"]).status == STATUS_CREATED
    assert PurchaseOrder.objects.get(pk=other_order["purchase_order_id"]).status == STATUS_CREATED
