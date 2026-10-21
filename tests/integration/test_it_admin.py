# trace: FR-030, FR-031, FR-033, FR-034, FR-040, FR-041, FR-042, FR-043, FR-044, FR-045
# trace: NFR-PF-08, NFR-US-09
# trace: ADDR-003, ADDR-008, ADDR-010
"""管理者向け機能（在庫単位一覧・注文検索・注文詳細・出荷・配達完了・キャンセル）の結合試験
（IT-AI-INIT-129〜148）。

検証対象の連携は 管理者向けAPI → Service → ORM → PostgreSQL、権限判定 → 業務機能API、
トランザクション・同時実行制御 → PostgreSQL、画面 → Service → DB。

期待結果は FR-040〜FR-045 の処理内容・出力・例外・排他、ST-PO-05/ST-PO-06、CMN-19/CMN-29/
CMN-38、提供済みAPI契約 6.1/6.2 から導出する。
"""

from __future__ import annotations

import datetime as dt

import pytest
from rest_framework.test import APIClient

from common import timeutils
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
def place_order(client, f, *, price: int = 1000, quantity: int = 1) -> dict:
    """注文受付の注文を1件作る（試験前提データの準備）。"""
    unit = f.sellable(price=price, quantity=quantity + 20)
    client.post("/api/cart/lines", {"stock_unit_id": unit.pk, "quantity": quantity}, format="json")
    response = client.post("/api/checkout", SHIPPING, format="json")
    assert response.status_code == 201
    return response.json()


# trace: FR-031, FR-043, FR-044
def advance(buyer_client, admin_client, order_id: int, target: str) -> None:
    """注文を目的の状態まで進める（試験前提データの準備）。"""
    if target in (STATUS_PAID, STATUS_SHIPPED, STATUS_DELIVERED):
        assert buyer_client.post(f"/api/purchase-orders/{order_id}/pay", {}, format="json").status_code == 200
    if target in (STATUS_SHIPPED, STATUS_DELIVERED):
        assert (
            admin_client.post(
                f"/api/admin/purchase-orders/{order_id}/ship", {}, format="json"
            ).status_code
            == 200
        )
    if target == STATUS_DELIVERED:
        assert (
            admin_client.post(
                f"/api/admin/purchase-orders/{order_id}/deliver", {}, format="json"
            ).status_code
            == 200
        )
    if target == STATUS_CANCELLED:
        assert (
            buyer_client.post(f"/api/purchase-orders/{order_id}/cancel", {}, format="json").status_code
            == 200
        )


# trace: FR-040, NFR-PF-08
def test_it_ai_init_129_stock_unit_list_returns_all_units(api_as, admin_user, f):
    """IT-AI-INIT-129 / COV-114：在庫単位一覧は非公開商品・在庫0も含め SKU 昇順・50件/ページで返す。"""
    public_item = f.item(name="管理公開商品")
    hidden_item = f.item(name="管理非公開商品", is_public=False)
    for index in range(49):
        f.stock_unit(public_item, sku=f"SKU-ADM-{index:03d}", price=1000, quantity=10)
    f.stock_unit(hidden_item, sku="SKU-ADM-900", price=1000, quantity=10)
    f.stock_unit(public_item, sku="SKU-ADM-901", price=1000, quantity=0)
    f.stock_unit(public_item, sku="SKU-ADM-902", price=1000, quantity=3)
    client = api_as(admin_user)

    first = client.get("/api/admin/stock-units")
    second = client.get("/api/admin/stock-units", {"page": 2})
    beyond = client.get("/api/admin/stock-units", {"page": 3})

    assert first.status_code == 200
    body = first.json()
    assert body["page_size"] == 50
    assert body["total_count"] == 52
    assert body["total_pages"] == 2
    skus = [row["sku"] for row in body["results"]]
    assert skus == sorted(skus)
    assert len(skus) == 50
    second_skus = [row["sku"] for row in second.json()["results"]]
    assert second_skus == ["SKU-ADM-901", "SKU-ADM-902"]
    assert beyond.status_code == 200 and beyond.json()["results"] == []
    hidden_row = next(
        row for row in body["results"] + second.json()["results"] if row["sku"] == "SKU-ADM-900"
    )
    assert hidden_row["item_is_public"] is False


# trace: FR-040
def test_it_ai_init_130_stock_unit_search_conditions(api_as, admin_user, f):
    """IT-AI-INIT-130 / COV-115：SKU前方一致・商品名部分一致・仕入先完全一致を AND で絞り込む。"""
    supplier_a = f.supplier(name="仕入先A")
    supplier_b = f.supplier(name="仕入先B")
    note = f.item(name="ノートPC")
    pen = f.item(name="ボールペン")
    target = f.stock_unit(note, supplier=supplier_a, sku="KC-01-TARGET", price=1000, quantity=5)
    other_sku = f.stock_unit(note, supplier=supplier_b, sku="ZZ-02", price=1000, quantity=5)
    other_item = f.stock_unit(pen, supplier=supplier_a, sku="KC-03", price=1000, quantity=5)
    client = api_as(admin_user)

    def skus(params: dict) -> list[str]:
        response = client.get("/api/admin/stock-units", params)
        assert response.status_code == 200
        return [row["sku"] for row in response.json()["results"]]

    assert skus({"sku": "kc-01"}) == [target.sku]
    assert sorted(skus({"sku": "KC"})) == sorted([target.sku, other_item.sku])
    assert sorted(skus({"item_name": "ノート"})) == sorted([target.sku, other_sku.sku])
    assert sorted(skus({"supplier_id": supplier_a.pk})) == sorted([target.sku, other_item.sku])
    assert skus({"sku": "kc", "item_name": "ノート", "supplier_id": supplier_a.pk}) == [target.sku]


# trace: FR-040
def test_it_ai_init_131_low_stock_only_boundary(api_as, admin_user, f):
    """IT-AI-INIT-131 / COV-116：low_stock_only は在庫数量5以下のみを返し、6は含めない。"""
    item = f.item(name="低在庫判定商品")
    zero = f.stock_unit(item, sku="LOW-000", price=1000, quantity=0)
    five = f.stock_unit(item, sku="LOW-005", price=1000, quantity=5)
    six = f.stock_unit(item, sku="LOW-006", price=1000, quantity=6)
    client = api_as(admin_user)

    only_low = client.get("/api/admin/stock-units", {"low_stock_only": "true"}).json()["results"]
    not_filtered = client.get("/api/admin/stock-units", {"low_stock_only": "false"}).json()["results"]
    omitted = client.get("/api/admin/stock-units").json()["results"]

    assert sorted(row["sku"] for row in only_low) == [zero.sku, five.sku]
    assert sorted(row["sku"] for row in not_filtered) == sorted([zero.sku, five.sku, six.sku])
    assert len(omitted) == 3
    flags = {row["sku"]: row["is_low_stock"] for row in omitted}
    assert flags[zero.sku] is True
    assert flags[five.sku] is True
    assert flags[six.sku] is False


# trace: FR-040
def test_it_ai_init_132_stock_unit_list_errors(api, api_as, buyer, admin_user, f, err):
    """IT-AI-INIT-132 / COV-118：不正条件は入力エラー、購入者は権限エラー、未ログインは認証エラーとする。"""
    client = api_as(admin_user)

    single_cases = [
        ({"sku": "A" * 33}, "sku"),
        ({"item_name": "あ" * 101}, "item_name"),
        ({"supplier_id": 999999}, "supplier_id"),
        ({"low_stock_only": "yes"}, "low_stock_only"),
        ({"page": 0}, "page"),
    ]
    for params, field in single_cases:
        response = client.get("/api/admin/stock-units", params)
        assert response.status_code == 400, params
        assert err.code(response) == "VALIDATION_ERROR"
        assert field in err.fields(response)

    combined = client.get(
        "/api/admin/stock-units", {"sku": "A" * 33, "item_name": "あ" * 101, "page": 0}
    )
    assert set(err.fields(combined)) >= {"sku", "item_name", "page"}

    as_buyer = api_as(buyer).get("/api/admin/stock-units")
    anonymous = api.get("/api/admin/stock-units")
    assert as_buyer.status_code == 403
    assert err.code(as_buyer) == "PERMISSION_DENIED"
    assert anonymous.status_code == 401
    assert err.code(anonymous) == "AUTHENTICATION_REQUIRED"


# trace: FR-030, FR-034, FR-040
def test_it_ai_init_133_stock_changes_are_visible_to_admin(api_as, buyer, admin_user, f):
    """IT-AI-INIT-133 / COV-117：注文確定・キャンセルの在庫増減が在庫単位一覧へ反映される（CMN-38）。"""
    buyer_client = api_as(buyer)
    admin_client = api_as(admin_user)
    unit = f.sellable(price=1000, quantity=10)

    def quantity_of(sku: str) -> int:
        response = admin_client.get("/api/admin/stock-units", {"sku": sku})
        assert response.status_code == 200
        return response.json()["results"][0]["quantity"]

    assert quantity_of(unit.sku) == 10

    buyer_client.post("/api/cart/lines", {"stock_unit_id": unit.pk, "quantity": 3}, format="json")
    order = buyer_client.post("/api/checkout", SHIPPING, format="json").json()
    assert quantity_of(unit.sku) == 7

    buyer_client.post(f"/api/purchase-orders/{order['purchase_order_id']}/cancel", {}, format="json")

    assert quantity_of(unit.sku) == 10


# trace: FR-041, NFR-PF-08
def test_it_ai_init_134_admin_order_list(api_as, buyer, other_buyer, admin_user, f):
    """IT-AI-INIT-134 / COV-119：管理者の注文一覧は全購入者・全状態を注文日時降順20件/ページで返す。"""
    buyer_client = api_as(buyer)
    other_client = api_as(other_buyer)
    admin_client = api_as(admin_user)
    unit = f.sellable(price=1000, quantity=100)
    created_ids = []
    for index in range(21):
        client = buyer_client if index % 2 == 0 else other_client
        client.post("/api/cart/lines", {"stock_unit_id": unit.pk, "quantity": 1}, format="json")
        created_ids.append(client.post("/api/checkout", SHIPPING, format="json").json()["purchase_order_id"])
    advance(buyer_client, admin_client, created_ids[0], STATUS_CANCELLED)

    first = admin_client.get("/api/admin/purchase-orders").json()
    second = admin_client.get("/api/admin/purchase-orders", {"page": 2}).json()
    beyond = admin_client.get("/api/admin/purchase-orders", {"page": 3})

    assert first["page_size"] == 20
    assert first["total_count"] == 21
    assert len(first["results"]) == 20
    assert len(second["results"]) == 1
    assert beyond.status_code == 200 and beyond.json()["results"] == []
    ids = [row["purchase_order_id"] for row in first["results"] + second["results"]]
    assert ids == sorted(created_ids, reverse=True)
    assert {row["buyer_email"] for row in first["results"]} >= {buyer.email, other_buyer.email}
    statuses = {row["purchase_order_id"]: row["status"] for row in first["results"] + second["results"]}
    assert statuses[created_ids[0]] == STATUS_CANCELLED


# trace: FR-041
def test_it_ai_init_135_admin_order_search_conditions(api_as, buyer, other_buyer, admin_user, f):
    """IT-AI-INIT-135 / COV-120：注文番号完全一致・状態のOR・購入者メールの部分一致を AND で絞り込む。"""
    buyer_client = api_as(buyer)
    other_client = api_as(other_buyer)
    admin_client = api_as(admin_user)
    created = place_order(buyer_client, f)
    paid = place_order(buyer_client, f)
    advance(buyer_client, admin_client, paid["purchase_order_id"], STATUS_PAID)
    others = place_order(other_client, f)

    def ids(params) -> list[int]:
        if isinstance(params, str):
            response = admin_client.get(f"/api/admin/purchase-orders?{params}")
        else:
            response = admin_client.get("/api/admin/purchase-orders", params)
        assert response.status_code == 200
        return [row["purchase_order_id"] for row in response.json()["results"]]

    assert ids({"order_number": created["order_number"]}) == [created["purchase_order_id"]]
    assert sorted(ids("status=created&status=paid")) == sorted(
        [created["purchase_order_id"], paid["purchase_order_id"], others["purchase_order_id"]]
    )
    assert ids({"status": "paid"}) == [paid["purchase_order_id"]]
    assert sorted(ids({"buyer_email": buyer.email.upper()[:12]})) == sorted(
        [created["purchase_order_id"], paid["purchase_order_id"]]
    )
    assert ids({"buyer_email": buyer.email, "status": "paid"}) == [paid["purchase_order_id"]]


# trace: FR-041
def test_it_ai_init_136_admin_order_date_range(api_as, buyer, admin_user, f, err):
    """IT-AI-INIT-136 / COV-121：注文日範囲は JST の両端を含み、不正指定は入力エラーとする（CMN-29）。"""
    buyer_client = api_as(buyer)
    admin_client = api_as(admin_user)
    start_of_day = dt.datetime(2027, 8, 1, 0, 0, 0, tzinfo=timeutils.JST)
    inside_start = place_order(buyer_client, f)
    inside_end = place_order(buyer_client, f)
    before = place_order(buyer_client, f)
    after = place_order(buyer_client, f)
    PurchaseOrder.objects.filter(pk=inside_start["purchase_order_id"]).update(ordered_at=start_of_day)
    PurchaseOrder.objects.filter(pk=inside_end["purchase_order_id"]).update(
        ordered_at=start_of_day + dt.timedelta(days=1) - dt.timedelta(seconds=1)
    )
    PurchaseOrder.objects.filter(pk=before["purchase_order_id"]).update(
        ordered_at=start_of_day - dt.timedelta(seconds=1)
    )
    PurchaseOrder.objects.filter(pk=after["purchase_order_id"]).update(
        ordered_at=start_of_day + dt.timedelta(days=1)
    )

    response = admin_client.get(
        "/api/admin/purchase-orders", {"ordered_from": "2027-08-01", "ordered_to": "2027-08-01"}
    )

    assert response.status_code == 200
    ids = sorted(row["purchase_order_id"] for row in response.json()["results"])
    assert ids == sorted([inside_start["purchase_order_id"], inside_end["purchase_order_id"]])

    invalid_cases = [
        ({"ordered_from": "2027-08-02", "ordered_to": "2027-08-01"}, "ordered_from"),
        ({"ordered_from": "2027/08/01"}, "ordered_from"),
        ({"ordered_to": "2027-02-30"}, "ordered_to"),
    ]
    for params, field in invalid_cases:
        invalid = admin_client.get("/api/admin/purchase-orders", params)
        assert invalid.status_code == 400, params
        assert err.code(invalid) == "VALIDATION_ERROR"
        assert field in err.fields(invalid)


# trace: FR-042
def test_it_ai_init_137_admin_order_detail(api_as, buyer, admin_user, f):
    """IT-AI-INIT-137 / COV-122：管理者の注文詳細は購入者情報・決済記録・状態履歴・操作可否を返す。"""
    buyer_client = api_as(buyer)
    admin_client = api_as(admin_user)
    order = place_order(buyer_client, f)
    order_id = order["purchase_order_id"]
    buyer_client.post(f"/api/purchase-orders/{order_id}/pay", {"mock_result": "decline"}, format="json")
    buyer_client.post(f"/api/purchase-orders/{order_id}/pay", {"mock_result": "approve"}, format="json")

    response = admin_client.get(f"/api/admin/purchase-orders/{order_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["buyer"] == {"user_id": buyer.pk, "email": buyer.email, "full_name": buyer.full_name}
    assert [record["result"] for record in body["payment_records"]] == ["declined", "approved"]
    assert body["payment_records"][1]["amount"] == order["amounts"]["total"]
    assert all("actor_user_id" in row for row in body["status_history"])
    assert body["status_history"][0]["actor_user_id"] == buyer.pk
    assert body["can_ship"] is True
    assert body["can_deliver"] is False
    assert body["can_cancel"] is True


# trace: FR-043
def test_it_ai_init_138_ship_registers_tracking_number(api_as, buyer, admin_user, f):
    """IT-AI-INIT-138 / COV-123：支払済の注文の出荷登録で出荷済となり配送伝票番号を保存する（ST-PO-05）。"""
    buyer_client = api_as(buyer)
    admin_client = api_as(admin_user)
    with_tracking = place_order(buyer_client, f)
    without_tracking = place_order(buyer_client, f)
    advance(buyer_client, admin_client, with_tracking["purchase_order_id"], STATUS_PAID)
    advance(buyer_client, admin_client, without_tracking["purchase_order_id"], STATUS_PAID)

    tracked = admin_client.post(
        f"/api/admin/purchase-orders/{with_tracking['purchase_order_id']}/ship",
        {"tracking_number": "TRK-0001"},
        format="json",
    )
    untracked = admin_client.post(
        f"/api/admin/purchase-orders/{without_tracking['purchase_order_id']}/ship", {}, format="json"
    )

    assert tracked.status_code == 200
    tracked_body = tracked.json()
    assert tracked_body["status"] == STATUS_SHIPPED
    assert tracked_body["shipped_at"] is not None
    assert tracked_body["tracking_number"] == "TRK-0001"
    assert (tracked_body["status_history"][-1]["from_status"], tracked_body["status_history"][-1]["to_status"]) == (
        STATUS_PAID,
        STATUS_SHIPPED,
    )
    assert tracked_body["status_history"][-1]["actor_role"] == "admin"

    assert untracked.status_code == 200
    assert untracked.json()["status"] == STATUS_SHIPPED
    assert untracked.json()["tracking_number"] is None


# trace: FR-043
def test_it_ai_init_139_tracking_number_validation(api_as, buyer, admin_user, f, err):
    """IT-AI-INIT-139 / COV-124：配送伝票番号は英数字とハイフンの30文字以内とする。"""
    buyer_client = api_as(buyer)
    admin_client = api_as(admin_user)
    order = place_order(buyer_client, f)
    order_id = order["purchase_order_id"]
    advance(buyer_client, admin_client, order_id, STATUS_PAID)

    for invalid in ("A" * 31, "TRK 0001", "TRK/0001"):
        response = admin_client.post(
            f"/api/admin/purchase-orders/{order_id}/ship", {"tracking_number": invalid}, format="json"
        )

        assert response.status_code == 400, invalid
        assert err.code(response) == "VALIDATION_ERROR"
        assert "tracking_number" in err.fields(response)
        assert PurchaseOrder.objects.get(pk=order_id).status == STATUS_PAID

    accepted = admin_client.post(
        f"/api/admin/purchase-orders/{order_id}/ship", {"tracking_number": "A" * 30}, format="json"
    )

    assert accepted.status_code == 200
    assert accepted.json()["tracking_number"] == "A" * 30


# trace: FR-043, FR-044
def test_it_ai_init_140_ship_and_deliver_status_transitions(api_as, buyer, admin_user, f, err):
    """IT-AI-INIT-140 / COV-125：出荷済→配達完了のみ成功し、それ以外は状態遷移エラーとする（ST-PO-06）。"""
    buyer_client = api_as(buyer)
    admin_client = api_as(admin_user)
    orders = {}
    for status in (STATUS_CREATED, STATUS_PAID, STATUS_SHIPPED, STATUS_DELIVERED, STATUS_CANCELLED):
        order = place_order(buyer_client, f)
        advance(buyer_client, admin_client, order["purchase_order_id"], status)
        orders[status] = order["purchase_order_id"]

    deliver_shipped = admin_client.post(
        f"/api/admin/purchase-orders/{orders[STATUS_SHIPPED]}/deliver", {}, format="json"
    )
    assert deliver_shipped.status_code == 200
    assert deliver_shipped.json()["status"] == STATUS_DELIVERED

    for status in (STATUS_CREATED, STATUS_DELIVERED, STATUS_CANCELLED):
        ship = admin_client.post(
            f"/api/admin/purchase-orders/{orders[status]}/ship", {}, format="json"
        )
        assert ship.status_code == 409, status
        assert err.code(ship) == "INVALID_STATUS_TRANSITION"
        assert err.context(ship) == {"current_status": status}
        assert PurchaseOrder.objects.get(pk=orders[status]).status == status

    for status in (STATUS_CREATED, STATUS_PAID, STATUS_CANCELLED):
        deliver = admin_client.post(
            f"/api/admin/purchase-orders/{orders[status]}/deliver", {}, format="json"
        )
        assert deliver.status_code == 409, status
        assert err.code(deliver) == "INVALID_STATUS_TRANSITION"
        assert err.context(deliver) == {"current_status": status}


# trace: FR-042, FR-043, FR-044
def test_it_ai_init_141_admin_order_functions_errors(api, api_as, buyer, admin_user, f, err):
    """IT-AI-INIT-141 / COV-126：存在しない注文は対象なし、購入者は権限、未ログインは認証エラーとする。"""
    admin_client = api_as(admin_user)
    buyer_client = api_as(buyer)
    order = place_order(buyer_client, f)
    order_id = order["purchase_order_id"]

    not_found = [
        admin_client.get("/api/admin/purchase-orders/999999"),
        admin_client.post("/api/admin/purchase-orders/999999/ship", {}, format="json"),
        admin_client.post("/api/admin/purchase-orders/999999/deliver", {}, format="json"),
    ]
    for response in not_found:
        assert response.status_code == 404
        assert err.code(response) == "NOT_FOUND"

    for path in (
        f"/api/admin/purchase-orders/{order_id}",
        f"/api/admin/purchase-orders/{order_id}/ship",
        f"/api/admin/purchase-orders/{order_id}/deliver",
    ):
        as_buyer = (
            buyer_client.get(path) if path.endswith(str(order_id)) else buyer_client.post(path, {}, format="json")
        )
        anonymous = api.get(path) if path.endswith(str(order_id)) else api.post(path, {}, format="json")

        assert as_buyer.status_code == 403, path
        assert err.code(as_buyer) == "PERMISSION_DENIED"
        assert anonymous.status_code == 401, path
        assert err.code(anonymous) == "AUTHENTICATION_REQUIRED"
    assert PurchaseOrder.objects.get(pk=order_id).status == STATUS_CREATED


# trace: FR-043, ADDR-003
@pytest.mark.django_db(transaction=True)
def test_it_ai_init_142_concurrent_ship_succeeds_once(f, token_for, run_parallel):
    """IT-AI-INIT-142 / COV-127：同一注文への同時出荷登録は1件だけ成功する。"""
    buyer = f.user(email="race-ship-buyer@example.test")
    admin_user = f.admin(email="race-ship-admin@example.test")
    buyer_token = token_for(buyer)
    admin_token = token_for(admin_user)
    buyer_client = APIClient()
    buyer_client.credentials(HTTP_AUTHORIZATION=f"Bearer {buyer_token}")
    order = place_order(buyer_client, f)
    order_id = order["purchase_order_id"]
    buyer_client.post(f"/api/purchase-orders/{order_id}/pay", {}, format="json")

    def ship():
        worker = APIClient()
        worker.credentials(HTTP_AUTHORIZATION=f"Bearer {admin_token}")
        return worker.post(f"/api/admin/purchase-orders/{order_id}/ship", {}, format="json")

    try:
        results = run_parallel(ship, ship)

        statuses = sorted(response.status_code for response in results)
        assert statuses == [200, 409]
        failed = next(response for response in results if response.status_code == 409)
        body = failed.json()
        assert (body.get("error") or body)["code"] == "INVALID_STATUS_TRANSITION"
        order_row = PurchaseOrder.objects.get(pk=order_id)
        assert order_row.status == STATUS_SHIPPED
        assert order_row.status_history.filter(to_status=STATUS_SHIPPED).count() == 1
    finally:
        PaymentRecord.objects.all().delete()
        PurchaseOrder.objects.all().delete()


# trace: FR-045, ADDR-003
def test_it_ai_init_143_admin_cancel_restores_stock(api_as, buyer, admin_user, f):
    """IT-AI-INIT-143 / COV-129：管理者のキャンセルで在庫が戻り、決済記録は変化しない。"""
    buyer_client = api_as(buyer)
    admin_client = api_as(admin_user)
    created_unit = f.sellable(price=1000, quantity=10)
    buyer_client.post("/api/cart/lines", {"stock_unit_id": created_unit.pk, "quantity": 2}, format="json")
    created = buyer_client.post("/api/checkout", SHIPPING, format="json").json()
    paid_unit = f.sellable(price=1000, quantity=10)
    buyer_client.post("/api/cart/lines", {"stock_unit_id": paid_unit.pk, "quantity": 3}, format="json")
    paid = buyer_client.post("/api/checkout", SHIPPING, format="json").json()
    buyer_client.post(f"/api/purchase-orders/{paid['purchase_order_id']}/pay", {}, format="json")
    records_before = list(
        PaymentRecord.objects.filter(purchase_order_id=paid["purchase_order_id"]).values("id", "result")
    )

    for order in (created, paid):
        response = admin_client.post(
            f"/api/admin/purchase-orders/{order['purchase_order_id']}/cancel", {}, format="json"
        )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == STATUS_CANCELLED
        assert body["status_history"][-1]["actor_role"] == "admin"
        assert body["status_history"][-1]["actor_user_id"] == admin_user.pk

    created_unit.refresh_from_db()
    paid_unit.refresh_from_db()
    assert created_unit.quantity == 10
    assert paid_unit.quantity == 10
    assert (
        list(PaymentRecord.objects.filter(purchase_order_id=paid["purchase_order_id"]).values("id", "result"))
        == records_before
    )


# trace: FR-045
def test_it_ai_init_144_admin_cancel_rejects_invalid_states(api_as, buyer, admin_user, f, err):
    """IT-AI-INIT-144 / COV-130：状態不正は状態遷移エラー、存在しない注文は対象なしとする。"""
    buyer_client = api_as(buyer)
    admin_client = api_as(admin_user)
    orders = {}
    for status in (STATUS_SHIPPED, STATUS_DELIVERED, STATUS_CANCELLED):
        order = place_order(buyer_client, f, quantity=2)
        advance(buyer_client, admin_client, order["purchase_order_id"], status)
        orders[status] = order["purchase_order_id"]

    for status, order_id in orders.items():
        stock_before = {
            line.stock_unit_id: line.stock_unit.quantity
            for line in PurchaseOrder.objects.get(pk=order_id).lines.select_related("stock_unit")
        }

        response = admin_client.post(
            f"/api/admin/purchase-orders/{order_id}/cancel", {}, format="json"
        )

        assert response.status_code == 409, status
        assert err.code(response) == "INVALID_STATUS_TRANSITION"
        assert err.context(response) == {"current_status": status}
        stock_after = {
            line.stock_unit_id: line.stock_unit.quantity
            for line in PurchaseOrder.objects.get(pk=order_id).lines.select_related("stock_unit")
        }
        assert stock_after == stock_before

    missing = admin_client.post("/api/admin/purchase-orders/999999/cancel", {}, format="json")
    assert missing.status_code == 404
    assert err.code(missing) == "NOT_FOUND"


# trace: FR-033, FR-045
def test_it_ai_init_145_buyer_sees_admin_cancellation(api_as, buyer, admin_user, f):
    """IT-AI-INIT-145 / COV-131：管理者のキャンセル結果を購入者が注文詳細で確認できる。"""
    buyer_client = api_as(buyer)
    admin_client = api_as(admin_user)
    order = place_order(buyer_client, f)
    order_id = order["purchase_order_id"]

    admin_client.post(f"/api/admin/purchase-orders/{order_id}/cancel", {}, format="json")

    response = buyer_client.get(f"/api/purchase-orders/{order_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == STATUS_CANCELLED
    assert body["cancelled_at"] is not None
    last = body["status_history"][-1]
    assert (last["from_status"], last["to_status"]) == (STATUS_CREATED, STATUS_CANCELLED)
    assert last["actor_role"] == "admin"


# trace: FR-045
def test_it_ai_init_146_admin_cancel_requires_admin(api, api_as, buyer, admin_user, f, err):
    """IT-AI-INIT-146 / COV-132：購入者は権限エラー、未ログインは認証エラーとする。"""
    buyer_client = api_as(buyer)
    order = place_order(buyer_client, f)
    path = f"/api/admin/purchase-orders/{order['purchase_order_id']}/cancel"

    as_buyer = buyer_client.post(path, {}, format="json")
    anonymous = api.post(path, {}, format="json")

    assert as_buyer.status_code == 403
    assert err.code(as_buyer) == "PERMISSION_DENIED"
    assert anonymous.status_code == 401
    assert err.code(anonymous) == "AUTHENTICATION_REQUIRED"
    assert PurchaseOrder.objects.get(pk=order["purchase_order_id"]).status == STATUS_CREATED


# trace: FR-031, FR-034, FR-043, FR-045, ADDR-003
@pytest.mark.django_db(transaction=True)
def test_it_ai_init_147_admin_cancel_competes_with_other_updates(f, token_for, run_parallel):
    """IT-AI-INIT-147 / COV-133：管理者キャンセルと他の更新の同時実行は逐次実行のいずれかと一致する（CMN-19）。"""
    buyer = f.user(email="race-admin-buyer@example.test")
    admin_user = f.admin(email="race-admin-admin@example.test")
    buyer_token = token_for(buyer)
    admin_token = token_for(admin_user)

    def client_for(token: str) -> APIClient:
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        return client

    def request(token: str, path: str):
        return client_for(token).post(path, {}, format="json")

    try:
        # 1) 管理者キャンセル × 購入者キャンセル（注文受付）
        buyer_client = client_for(buyer_token)
        unit_a = f.sellable(price=1000, quantity=10)
        buyer_client.post("/api/cart/lines", {"stock_unit_id": unit_a.pk, "quantity": 2}, format="json")
        order_a = buyer_client.post("/api/checkout", SHIPPING, format="json").json()
        id_a = order_a["purchase_order_id"]

        results = run_parallel(
            lambda: request(admin_token, f"/api/admin/purchase-orders/{id_a}/cancel"),
            lambda: request(buyer_token, f"/api/purchase-orders/{id_a}/cancel"),
        )
        assert sorted(response.status_code for response in results) == [200, 409]
        unit_a.refresh_from_db()
        assert unit_a.quantity == 10  # 在庫は1回だけ戻る
        assert PurchaseOrder.objects.get(pk=id_a).status == STATUS_CANCELLED

        # 2) 管理者キャンセル × 出荷登録（支払済）
        unit_b = f.sellable(price=1000, quantity=10)
        buyer_client.post("/api/cart/lines", {"stock_unit_id": unit_b.pk, "quantity": 2}, format="json")
        order_b = buyer_client.post("/api/checkout", SHIPPING, format="json").json()
        id_b = order_b["purchase_order_id"]
        buyer_client.post(f"/api/purchase-orders/{id_b}/pay", {}, format="json")

        results = run_parallel(
            lambda: request(admin_token, f"/api/admin/purchase-orders/{id_b}/cancel"),
            lambda: request(admin_token, f"/api/admin/purchase-orders/{id_b}/ship"),
        )
        assert sorted(response.status_code for response in results) == [200, 409]
        order_row = PurchaseOrder.objects.get(pk=id_b)
        unit_b.refresh_from_db()
        if order_row.status == STATUS_CANCELLED:
            assert unit_b.quantity == 10
        else:
            assert order_row.status == STATUS_SHIPPED
            assert unit_b.quantity == 8

        # 3) 管理者キャンセル × 購入者支払（注文受付）
        unit_c = f.sellable(price=1000, quantity=10)
        buyer_client.post("/api/cart/lines", {"stock_unit_id": unit_c.pk, "quantity": 2}, format="json")
        order_c = buyer_client.post("/api/checkout", SHIPPING, format="json").json()
        id_c = order_c["purchase_order_id"]

        results = run_parallel(
            lambda: request(admin_token, f"/api/admin/purchase-orders/{id_c}/cancel"),
            lambda: request(buyer_token, f"/api/purchase-orders/{id_c}/pay"),
        )
        statuses = sorted(response.status_code for response in results)
        order_row = PurchaseOrder.objects.get(pk=id_c)
        unit_c.refresh_from_db()
        approved = PaymentRecord.objects.filter(purchase_order_id=id_c, result="approved").count()
        assert order_row.status == STATUS_CANCELLED
        assert unit_c.quantity == 10
        # 逐次実行の順序は「支払→キャンセル」（200,200）か「キャンセル→支払」（200,409）のいずれか。
        assert statuses in ([200, 200], [200, 409])
        assert approved == (1 if statuses == [200, 200] else 0)
    finally:
        PaymentRecord.objects.all().delete()
        PurchaseOrder.objects.all().delete()


# trace: FR-043, FR-045, ADDR-010, NFR-US-09
def test_it_ai_init_148_admin_screen_confirms_before_updating(screen_as, api_as, buyer, admin_user, f):
    """IT-AI-INIT-148 / COV-128・COV-134：画面の出荷登録・キャンセルは確認を経た送信でのみ状態を変える。"""
    buyer_client = api_as(buyer)
    admin_api = api_as(admin_user)
    unit = f.sellable(price=1000, quantity=10)
    buyer_client.post("/api/cart/lines", {"stock_unit_id": unit.pk, "quantity": 2}, format="json")
    order = buyer_client.post("/api/checkout", SHIPPING, format="json").json()
    order_id = order["purchase_order_id"]
    advance(buyer_client, admin_api, order_id, STATUS_PAID)
    client = screen_as(admin_user)

    detail = client.get(f"/admin-console/orders/{order_id}/")
    body = detail.content.decode()

    assert detail.status_code == 200
    assert "data-confirm" in body
    # 確認ダイアログを取り消した場合は要求が送信されず、状態・在庫は変化しない。
    assert PurchaseOrder.objects.get(pk=order_id).status == STATUS_PAID
    unit.refresh_from_db()
    assert unit.quantity == 8

    shipped = client.post(f"/admin-console/orders/{order_id}/ship/", {"tracking_number": "TRK-SCREEN"})

    assert shipped.status_code == 302
    assert PurchaseOrder.objects.get(pk=order_id).status == STATUS_SHIPPED

    second_unit = f.sellable(price=1000, quantity=10)
    buyer_client.post("/api/cart/lines", {"stock_unit_id": second_unit.pk, "quantity": 2}, format="json")
    cancel_target = buyer_client.post("/api/checkout", SHIPPING, format="json").json()

    cancelled = client.post(f"/admin-console/orders/{cancel_target['purchase_order_id']}/cancel/")

    assert cancelled.status_code == 302
    assert PurchaseOrder.objects.get(pk=cancel_target["purchase_order_id"]).status == STATUS_CANCELLED
    second_unit.refresh_from_db()
    assert second_unit.quantity == 10
