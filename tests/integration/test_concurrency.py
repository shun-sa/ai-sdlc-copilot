# trace: FR-001, FR-021, FR-030, FR-031, FR-034, FR-043, FR-045, ADDR-001, ADDR-009
# trace: NFR-PF-07, NFR-LG-06
# trace: AC-UC-001-017, AC-UC-004-025, AC-UC-007-013, AC-UC-007-019, AC-UC-009-007
# trace: AC-UC-011-020, AC-UC-012-009, AC-UC-012-010, AC-UC-012-011
"""同時実行（7.4 排他制御方針、CMN-19・CMN-20）の結合試験。

期待結果は機能要件定義書 6.15.9（排他・同時実行）・7.4、各FRの処理内容、
UC の同時実行受入基準（AC-UC-001-017、AC-UC-004-025、AC-UC-007-013、AC-UC-007-019、
AC-UC-009-007、AC-UC-011-020、AC-UC-012-009、AC-UC-012-010、AC-UC-012-011）、
非機能要件定義書 5章 NFR-PF-07（整合性を伴う同時実行性能。検証データ条件 VDC-05）と
11章 NFR-LG-06（EC販売規程の業務ルール）、
ADDR-001（行ロックによる直列化）・ADDR-009（決済反映の境界）から導出する。
実DBの行ロックを確認するため、トランザクションを確定するテストDBと複数接続を用いる。
"""
import threading

import pytest
from django.db import connections
from django.test import Client

from shop.models import (
    CartLine,
    PaymentRecord,
    PaymentResult,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseOrderStatus,
    PurchaseOrderStatusHistory,
    StockUnit,
    User,
)
from shop.payments import mock as payment_mock
from tests.integration import _helpers

pytestmark = pytest.mark.django_db(transaction=True)

# 各受入基準が定める試行回数（10試行中10試行で Then を満たすこと）。
TRIALS = 10


# trace: FR-030
def _prepare_buyer(email, unit_id):
    """購入者を作成し、カートへ数量1の明細を追加してトークンを返す。"""
    _helpers.make_user(email=email)
    client = _helpers.ApiClient(Client())
    token = client.login(email)
    response = client.post("/api/cart/lines", {"stock_unit_id": unit_id, "quantity": 1}, token=token)
    assert response.status_code == 200, response.content
    return token


# trace: FR-030, ADDR-001
@pytest.mark.case("IT-AI-GF-011")
def test_concurrent_checkout_on_single_stock_is_serialized():
    """在庫1の在庫単位への同時注文確定は逐次実行と同じ結果となる（CMN-19、CMN-20）。"""
    supplier = _helpers.make_supplier()
    item = _helpers.make_item()
    unit = _helpers.make_stock_unit(item, supplier, quantity=1)
    tokens = [
        _prepare_buyer("buyer1@example.com", unit.stock_unit_id),
        _prepare_buyer("buyer2@example.com", unit.stock_unit_id),
    ]

    barrier = threading.Barrier(len(tokens))
    results: list[tuple[int, dict]] = []
    lock = threading.Lock()

    def checkout(token):
        """同時に注文確定を要求する。"""
        client = _helpers.ApiClient(Client())
        try:
            barrier.wait(timeout=10)
            response = client.post("/api/checkout", dict(_helpers.VALID_ADDRESS), token=token)
            with lock:
                results.append((response.status_code, response.json()))
        finally:
            connections.close_all()

    threads = [threading.Thread(target=checkout, args=(token,)) for token in tokens]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
        assert not thread.is_alive()

    statuses = sorted(status for status, _body in results)
    assert statuses == [201, 409]
    failure = next(body for status, body in results if status == 409)
    assert failure["error"]["code"] == "INSUFFICIENT_STOCK"
    assert failure["error"]["context"]["shortages"][0] == {
        "stock_unit_id": unit.stock_unit_id,
        "sku": unit.sku,
        "requested_quantity": 1,
        "available_quantity": 0,
    }

    assert PurchaseOrder.objects.count() == 1
    assert StockUnit.objects.get(stock_unit_id=unit.stock_unit_id).quantity == 0


# trace: FR-030
def _response_body(response):
    """応答本文（JSON）を返す。JSON でない場合は None を返す。"""
    try:
        return response.json()
    except ValueError:
        return None


# trace: FR-030
def _api_post(path, data, token):
    """同時送信用に、1本の接続で POST を1回行う処理を組み立てる。"""

    def action():
        """新しい接続で POST を送信し、(ステータス, 本文) を返す。"""
        client = _helpers.ApiClient(Client())
        response = client.post(path, data, token=token)
        return response.status_code, _response_body(response)

    return action


# trace: FR-030, ADDR-001
def _concurrent(actions):
    """名前つきの複数要求を同時に送信し、{名前: (ステータス, 本文)} を返す。"""
    barrier = threading.Barrier(len(actions))
    results = {}
    failures = []
    lock = threading.Lock()

    def run(name, action):
        """他の要求と足並みをそろえてから1件の要求を送信する。"""
        try:
            barrier.wait(timeout=30)
            status, body = action()
            with lock:
                results[name] = (status, body)
        except BaseException as error:  # noqa: BLE001
            with lock:
                failures.append(error)
        finally:
            connections.close_all()

    threads = [threading.Thread(target=run, args=(name, action)) for name, action in actions]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
        assert not thread.is_alive()
    if failures:
        raise failures[0]
    assert len(results) == len(actions)
    return results


# trace: FR-030
def _statuses(results):
    """同時送信の結果のステータスを昇順で返す。"""
    return sorted(status for status, _body in results.values())


# trace: FR-030
def _picked(results, wanted_status):
    """指定したステータスとなった1件の (名前, 本文) を返す。"""
    for name, (status, body) in results.items():
        if status == wanted_status:
            return name, body
    raise AssertionError(f"ステータス {wanted_status} の応答がない: {results}")


# trace: FR-021, FR-030
def _catalog_unit(sku, price=2500, quantity=100, supplier_code=None):
    """同時実行の試行で使う在庫単位を1件作る。"""
    supplier = _helpers.make_supplier(supplier_code=supplier_code or f"SUP-{sku}")
    item = _helpers.make_item(item_code=f"ITEM-{sku}", name=f"商品{sku}")
    return _helpers.make_stock_unit(item, supplier, sku=sku, price=price, quantity=quantity)


# trace: FR-030
def _create_order(token, lines):
    """カートへ明細を追加して注文確定し、作成した注文を返す。"""
    client = _helpers.ApiClient(Client())
    for stock_unit_id, quantity in lines:
        added = client.post(
            "/api/cart/lines", {"stock_unit_id": stock_unit_id, "quantity": quantity}, token=token
        )
        assert added.status_code == 200, added.content
    created = client.post("/api/checkout", dict(_helpers.VALID_ADDRESS), token=token)
    assert created.status_code == 201, created.content
    return PurchaseOrder.objects.get(purchase_order_id=created.json()["purchase_order_id"])


# trace: FR-031
def _pay(token, order):
    """注文を支払済にする（事前条件の用意に使う）。"""
    client = _helpers.ApiClient(Client())
    response = client.post(
        f"/api/purchase-orders/{order.purchase_order_id}/pay", {"mock_result": "approve"}, token=token
    )
    assert response.status_code == 200, response.content


# trace: FR-030
def _history(order):
    """注文状態履歴を登録順に返す。"""
    return list(PurchaseOrderStatusHistory.objects.filter(purchase_order=order).order_by("status_history_id"))


# trace: FR-001, AC-UC-001-017
@pytest.mark.case("IT-AI-GF-020")
def test_concurrent_registration_of_same_email_creates_one_user():
    """正規化後が同一のメールアドレスの同時登録は1件だけ成功する（FR-001 手順、AC-UC-001-017）。"""
    for index in range(1, TRIALS + 1):
        normalized = f"kenta.ito{index:02d}@example.com"
        variants = [
            normalized,
            f"Kenta.Ito{index:02d}@example.com",
            f"KENTA.ITO{index:02d}@example.com",
            f"kenta.ito{index:02d}@EXAMPLE.com",
            f" kenta.ito{index:02d}@example.com",
        ]
        results = _concurrent(
            [
                (
                    f"register-{position}",
                    _api_post(
                        "/api/auth/register",
                        {
                            "email": variant,
                            "password": "Passw0rd",
                            "password_confirmation": "Passw0rd",
                            "full_name": "伊藤 健太",
                        },
                        None,
                    ),
                )
                for position, variant in enumerate(variants)
            ]
        )

        assert _statuses(results) == [201, 409, 409, 409, 409]
        for status, body in results.values():
            if status == 409:
                assert body["error"]["code"] == "EMAIL_ALREADY_REGISTERED"
        assert User.objects.filter(email=normalized).count() == 1


# trace: FR-021, AC-UC-004-025
@pytest.mark.case("IT-AI-GF-021")
def test_concurrent_cart_line_add_does_not_exceed_quantity_limit():
    """同一在庫単位への同時のカート明細追加でも合算数量は10個を超えない（FR-021、AC-UC-004-025）。"""
    user = _helpers.make_user()
    unit = _catalog_unit("MUG-001-BL", price=1500, quantity=20)
    client = _helpers.ApiClient(Client())
    token = client.login(user.email)
    assert client.get("/api/cart", token=token).status_code == 200

    for _trial in range(TRIALS):
        CartLine.objects.all().delete()

        results = _concurrent(
            [
                (
                    f"add-{position}",
                    _api_post(
                        "/api/cart/lines", {"stock_unit_id": unit.stock_unit_id, "quantity": 6}, token
                    ),
                )
                for position in range(2)
            ]
        )

        assert _statuses(results) == [200, 409]
        _name, failure = _picked(results, 409)
        assert failure["error"]["code"] == "QUANTITY_LIMIT_EXCEEDED"
        lines = list(CartLine.objects.all())
        assert len(lines) == 1
        assert lines[0].quantity == 6
        unit.refresh_from_db()
        assert unit.quantity == 20


# trace: FR-031, AC-UC-007-013
@pytest.mark.case("IT-AI-GF-022")
def test_concurrent_payments_record_single_approved_payment():
    """同一注文への同時支払では承認済み決済記録が1件だけ登録される（FR-031、AC-UC-007-013）。"""
    user = _helpers.make_user()
    unit = _catalog_unit("MUG-WHT-01")
    client = _helpers.ApiClient(Client())
    token = client.login(user.email)

    for _trial in range(TRIALS):
        order = _create_order(token, [(unit.stock_unit_id, 2)])
        unit.refresh_from_db()
        stock_before = unit.quantity

        results = _concurrent(
            [
                (
                    f"pay-{position}",
                    _api_post(
                        f"/api/purchase-orders/{order.purchase_order_id}/pay",
                        {"mock_result": "approve"},
                        token,
                    ),
                )
                for position in range(2)
            ]
        )

        assert _statuses(results) == [200, 409]
        _success_name, success = _picked(results, 200)
        assert success["status"] == PurchaseOrderStatus.PAID
        _failure_name, failure = _picked(results, 409)
        assert failure["error"]["code"] == "INVALID_STATUS_TRANSITION"
        assert failure["error"]["context"]["current_status"] == PurchaseOrderStatus.PAID

        records = list(PaymentRecord.objects.filter(purchase_order=order))
        assert len(records) == 1
        assert records[0].result == PaymentResult.APPROVED
        history = _history(order)
        assert [(entry.from_status, entry.to_status) for entry in history] == [
            (None, PurchaseOrderStatus.CREATED),
            (PurchaseOrderStatus.CREATED, PurchaseOrderStatus.PAID),
        ]
        order.refresh_from_db()
        assert order.paid_at is not None
        unit.refresh_from_db()
        assert unit.quantity == stock_before


# trace: FR-031, FR-034, ADDR-009, AC-UC-007-019
@pytest.mark.case("IT-AI-GF-023")
def test_concurrent_payment_and_cancel_matches_sequential_result(monkeypatch):
    """同一注文への支払とキャンセルの同時実行は逐次実行のいずれかの順序と一致する（FR-031 手順5、AC-UC-007-019）。"""
    requested_order_numbers: list[str] = []
    record_lock = threading.Lock()
    original_authorize = payment_mock.MockPaymentGateway.authorize

    def recording_authorize(self, request):
        """決済サービス（模擬）が受け取った決済要求の注文番号を記録する。"""
        with record_lock:
            requested_order_numbers.append(request.order_number)
        return original_authorize(self, request)

    monkeypatch.setattr(payment_mock.MockPaymentGateway, "authorize", recording_authorize)

    user = _helpers.make_user()
    unit = _catalog_unit("MUG-WHT-01")
    client = _helpers.ApiClient(Client())
    token = client.login(user.email)

    for _trial in range(TRIALS):
        order = _create_order(token, [(unit.stock_unit_id, 2)])
        unit.refresh_from_db()
        stock_before = unit.quantity
        with record_lock:
            requested_order_numbers.clear()

        results = _concurrent(
            [
                (
                    "pay",
                    _api_post(
                        f"/api/purchase-orders/{order.purchase_order_id}/pay",
                        {"mock_result": "approve"},
                        token,
                    ),
                ),
                (
                    "cancel",
                    _api_post(f"/api/purchase-orders/{order.purchase_order_id}/cancel", {}, token),
                ),
            ]
        )

        cancel_status, cancel_body = results["cancel"]
        assert cancel_status == 200, cancel_body
        assert cancel_body["status"] == PurchaseOrderStatus.CANCELLED

        pay_status, pay_body = results["pay"]
        records = list(PaymentRecord.objects.filter(purchase_order=order))
        history = [(entry.from_status, entry.to_status) for entry in _history(order)]
        if pay_status == 409:
            assert pay_body["error"]["code"] == "INVALID_STATUS_TRANSITION"
            assert pay_body["error"]["context"]["current_status"] == PurchaseOrderStatus.CANCELLED
            assert records == []
            assert history == [
                (None, PurchaseOrderStatus.CREATED),
                (PurchaseOrderStatus.CREATED, PurchaseOrderStatus.CANCELLED),
            ]
            assert order.order_number not in requested_order_numbers
        else:
            assert pay_status == 200, pay_body
            assert pay_body["status"] == PurchaseOrderStatus.PAID
            assert len(records) == 1
            assert records[0].result == PaymentResult.APPROVED
            assert history == [
                (None, PurchaseOrderStatus.CREATED),
                (PurchaseOrderStatus.CREATED, PurchaseOrderStatus.PAID),
                (PurchaseOrderStatus.PAID, PurchaseOrderStatus.CANCELLED),
            ]

        order.refresh_from_db()
        assert order.status == PurchaseOrderStatus.CANCELLED
        unit.refresh_from_db()
        assert unit.quantity == stock_before + 2


# trace: FR-034, AC-UC-009-007
@pytest.mark.case("IT-AI-GF-024")
def test_concurrent_cancels_restore_stock_once():
    """同一注文への同時キャンセルでは在庫が1回だけ戻る（FR-034、AC-UC-009-007）。"""
    user = _helpers.make_user()
    mug = _catalog_unit("MUG-WHT-01")
    plate = _catalog_unit("PLATE-BLU-02")
    client = _helpers.ApiClient(Client())
    token = client.login(user.email)

    for _trial in range(TRIALS):
        order = _create_order(token, [(mug.stock_unit_id, 2), (plate.stock_unit_id, 3)])
        mug.refresh_from_db()
        plate.refresh_from_db()
        mug_before, plate_before = mug.quantity, plate.quantity

        results = _concurrent(
            [
                (
                    f"cancel-{position}",
                    _api_post(f"/api/purchase-orders/{order.purchase_order_id}/cancel", {}, token),
                )
                for position in range(2)
            ]
        )

        assert _statuses(results) == [200, 409]
        _success_name, success = _picked(results, 200)
        assert success["status"] == PurchaseOrderStatus.CANCELLED
        _failure_name, failure = _picked(results, 409)
        assert failure["error"]["code"] == "INVALID_STATUS_TRANSITION"
        assert failure["error"]["context"]["current_status"] == PurchaseOrderStatus.CANCELLED

        mug.refresh_from_db()
        plate.refresh_from_db()
        assert mug.quantity == mug_before + 2
        assert plate.quantity == plate_before + 3
        history = _history(order)
        assert len(history) == 2
        assert [entry.to_status for entry in history].count(PurchaseOrderStatus.CANCELLED) == 1


# trace: FR-043, AC-UC-011-020
@pytest.mark.case("IT-AI-GF-025")
def test_concurrent_shipping_registrations_allow_single_success():
    """同一注文への同時の出荷登録は1件だけ成功する（FR-043、AC-UC-011-020）。"""
    buyer = _helpers.make_user(email="buyer-b@example.com")
    admin_x = _helpers.make_admin(email="admin-01@example.com")
    admin_y = _helpers.make_admin(email="admin-02@example.com", full_name="管理 次郎")
    unit = _catalog_unit("CUP-RED-03")
    client = _helpers.ApiClient(Client())
    buyer_token = client.login(buyer.email)
    admin_x_token = client.login(admin_x.email)
    admin_y_token = client.login(admin_y.email)

    for _trial in range(TRIALS):
        order = _create_order(buyer_token, [(unit.stock_unit_id, 1)])
        _pay(buyer_token, order)
        unit.refresh_from_db()
        stock_before = unit.quantity

        results = _concurrent(
            [
                (
                    "admin-x",
                    _api_post(
                        f"/api/admin/purchase-orders/{order.purchase_order_id}/ship",
                        {"tracking_number": "TRK-X"},
                        admin_x_token,
                    ),
                ),
                (
                    "admin-y",
                    _api_post(
                        f"/api/admin/purchase-orders/{order.purchase_order_id}/ship",
                        {"tracking_number": "TRK-Y"},
                        admin_y_token,
                    ),
                ),
            ]
        )

        assert _statuses(results) == [200, 409]
        winner, _success = _picked(results, 200)
        _failure_name, failure = _picked(results, 409)
        assert failure["error"]["code"] == "INVALID_STATUS_TRANSITION"
        assert failure["error"]["context"]["current_status"] == PurchaseOrderStatus.SHIPPED

        expected_admin = admin_x if winner == "admin-x" else admin_y
        expected_tracking = "TRK-X" if winner == "admin-x" else "TRK-Y"
        order.refresh_from_db()
        assert order.status == PurchaseOrderStatus.SHIPPED
        assert order.tracking_number == expected_tracking
        history = _history(order)
        assert len(history) == 3
        shipped = [
            entry
            for entry in history
            if entry.from_status == PurchaseOrderStatus.PAID
            and entry.to_status == PurchaseOrderStatus.SHIPPED
        ]
        assert len(shipped) == 1
        assert shipped[0].actor_user_id == expected_admin.user_id
        unit.refresh_from_db()
        assert unit.quantity == stock_before


# trace: FR-045, FR-034, AC-UC-012-009
@pytest.mark.case("IT-AI-GF-026")
def test_concurrent_admin_and_buyer_cancel_restore_stock_once():
    """管理者キャンセルと購入者キャンセルの同時実行では在庫が1回だけ戻る（FR-045、AC-UC-012-009）。"""
    buyer = _helpers.make_user()
    admin = _helpers.make_admin()
    unit = _catalog_unit("MUG-WHT-01")
    client = _helpers.ApiClient(Client())
    buyer_token = client.login(buyer.email)
    admin_token = client.login(admin.email)

    for _trial in range(TRIALS):
        order = _create_order(buyer_token, [(unit.stock_unit_id, 2)])
        unit.refresh_from_db()
        stock_before = unit.quantity

        results = _concurrent(
            [
                (
                    "admin",
                    _api_post(
                        f"/api/admin/purchase-orders/{order.purchase_order_id}/cancel", {}, admin_token
                    ),
                ),
                (
                    "buyer",
                    _api_post(
                        f"/api/purchase-orders/{order.purchase_order_id}/cancel", {}, buyer_token
                    ),
                ),
            ]
        )

        assert _statuses(results) == [200, 409]
        winner, success = _picked(results, 200)
        assert success["status"] == PurchaseOrderStatus.CANCELLED
        _failure_name, failure = _picked(results, 409)
        assert failure["error"]["code"] == "INVALID_STATUS_TRANSITION"
        assert failure["error"]["context"]["current_status"] == PurchaseOrderStatus.CANCELLED

        unit.refresh_from_db()
        assert unit.quantity == stock_before + 2
        cancelled = [
            entry for entry in _history(order) if entry.to_status == PurchaseOrderStatus.CANCELLED
        ]
        assert len(cancelled) == 1
        assert cancelled[0].actor_role == winner


# trace: FR-045, FR-043, AC-UC-012-010
@pytest.mark.case("IT-AI-GF-027")
def test_concurrent_admin_cancel_and_shipping_allow_single_success():
    """管理者キャンセルと出荷登録の同時実行ではどちらか一方だけが成功する（FR-045、AC-UC-012-010）。"""
    buyer = _helpers.make_user(email="buyer-b@example.com")
    admin_x = _helpers.make_admin(email="admin-01@example.com")
    admin_y = _helpers.make_admin(email="admin-02@example.com", full_name="管理 次郎")
    unit = _catalog_unit("PLATE-BLU-02")
    client = _helpers.ApiClient(Client())
    buyer_token = client.login(buyer.email)
    admin_x_token = client.login(admin_x.email)
    admin_y_token = client.login(admin_y.email)

    for _trial in range(TRIALS):
        order = _create_order(buyer_token, [(unit.stock_unit_id, 3)])
        _pay(buyer_token, order)
        unit.refresh_from_db()
        stock_before = unit.quantity
        history_before = len(_history(order))

        results = _concurrent(
            [
                (
                    "cancel",
                    _api_post(
                        f"/api/admin/purchase-orders/{order.purchase_order_id}/cancel", {}, admin_x_token
                    ),
                ),
                (
                    "ship",
                    _api_post(
                        f"/api/admin/purchase-orders/{order.purchase_order_id}/ship",
                        {"tracking_number": "TRK-Y"},
                        admin_y_token,
                    ),
                ),
            ]
        )

        assert _statuses(results) == [200, 409]
        winner, _success = _picked(results, 200)
        _failure_name, failure = _picked(results, 409)
        assert failure["error"]["code"] == "INVALID_STATUS_TRANSITION"

        order.refresh_from_db()
        unit.refresh_from_db()
        if winner == "cancel":
            assert failure["error"]["context"]["current_status"] == PurchaseOrderStatus.CANCELLED
            assert order.status == PurchaseOrderStatus.CANCELLED
            assert unit.quantity == stock_before + 3
            assert order.shipped_at is None
            assert order.tracking_number is None
        else:
            assert failure["error"]["context"]["current_status"] == PurchaseOrderStatus.SHIPPED
            assert order.status == PurchaseOrderStatus.SHIPPED
            assert unit.quantity == stock_before
            assert order.tracking_number == "TRK-Y"
            assert order.cancelled_at is None

        assert len(_history(order)) == history_before + 1
        records = list(PaymentRecord.objects.filter(purchase_order=order))
        assert len(records) == 1
        assert records[0].result == PaymentResult.APPROVED


# trace: FR-045, FR-031, AC-UC-012-011
@pytest.mark.case("IT-AI-GF-028")
def test_concurrent_admin_cancel_and_payment_matches_sequential_result():
    """管理者キャンセルと購入者の支払の同時実行は逐次実行と同じ結果になる（FR-045、AC-UC-012-011）。"""
    buyer = _helpers.make_user()
    admin = _helpers.make_admin()
    unit = _catalog_unit("MUG-WHT-01", price=2500)
    client = _helpers.ApiClient(Client())
    buyer_token = client.login(buyer.email)
    admin_token = client.login(admin.email)

    for _trial in range(TRIALS):
        order = _create_order(buyer_token, [(unit.stock_unit_id, 2)])
        assert order.total == 5500
        unit.refresh_from_db()
        stock_before = unit.quantity

        results = _concurrent(
            [
                (
                    "cancel",
                    _api_post(
                        f"/api/admin/purchase-orders/{order.purchase_order_id}/cancel", {}, admin_token
                    ),
                ),
                (
                    "pay",
                    _api_post(
                        f"/api/purchase-orders/{order.purchase_order_id}/pay",
                        {"mock_result": "approve"},
                        buyer_token,
                    ),
                ),
            ]
        )

        cancel_status, cancel_body = results["cancel"]
        assert cancel_status == 200, cancel_body
        assert cancel_body["status"] == PurchaseOrderStatus.CANCELLED
        assert cancel_body["can_ship"] is False
        assert cancel_body["can_deliver"] is False
        assert cancel_body["can_cancel"] is False

        pay_status, pay_body = results["pay"]
        records = list(PaymentRecord.objects.filter(purchase_order=order))
        history = [
            (entry.from_status, entry.to_status, entry.actor_role) for entry in _history(order)
        ]
        order.refresh_from_db()
        if pay_status == 409:
            assert pay_body["error"]["code"] == "INVALID_STATUS_TRANSITION"
            assert pay_body["error"]["context"]["current_status"] == PurchaseOrderStatus.CANCELLED
            assert cancel_body["payment_records"] == []
            assert records == []
            assert order.paid_at is None
            assert history == [
                (None, PurchaseOrderStatus.CREATED, "buyer"),
                (PurchaseOrderStatus.CREATED, PurchaseOrderStatus.CANCELLED, "admin"),
            ]
        else:
            assert pay_status == 200, pay_body
            assert pay_body["status"] == PurchaseOrderStatus.PAID
            assert len(cancel_body["payment_records"]) == 1
            assert cancel_body["payment_records"][0]["result"] == PaymentResult.APPROVED
            assert cancel_body["payment_records"][0]["amount"] == 5500
            assert len(records) == 1
            assert records[0].result == PaymentResult.APPROVED
            assert order.paid_at is not None
            assert history == [
                (None, PurchaseOrderStatus.CREATED, "buyer"),
                (PurchaseOrderStatus.CREATED, PurchaseOrderStatus.PAID, "buyer"),
                (PurchaseOrderStatus.PAID, PurchaseOrderStatus.CANCELLED, "admin"),
            ]

        assert order.status == PurchaseOrderStatus.CANCELLED
        unit.refresh_from_db()
        assert unit.quantity == stock_before + 2


# trace: FR-030, NFR-PF-07, NFR-LG-06, ADDR-001
@pytest.mark.case("IT-AI-GF-069")
def test_ten_concurrent_checkouts_on_one_stock_unit_keep_stock_consistent():
    """在庫5への10並列の注文確定は成功5件・在庫不足5件となり、在庫数量が0未満にならない（NFR-PF-07、VDC-05）。"""
    for trial in range(1, TRIALS + 1):
        sku = f"PF07-{trial:02d}"
        unit = _catalog_unit(sku, price=1000, quantity=5)
        tokens = [
            _prepare_buyer(f"pf07-{trial:02d}-{position}@example.com", unit.stock_unit_id)
            for position in range(10)
        ]

        results = _concurrent(
            [
                (f"checkout-{position}", _api_post("/api/checkout", dict(_helpers.VALID_ADDRESS), token))
                for position, token in enumerate(tokens)
            ]
        )

        statuses = _statuses(results)
        assert statuses == [201] * 5 + [409] * 5, f"試行{trial}: {statuses}"
        for status, body in results.values():
            if status == 409:
                assert body["error"]["code"] == "INSUFFICIENT_STOCK"
                assert body["error"]["context"]["shortages"][0]["stock_unit_id"] == unit.stock_unit_id

        unit.refresh_from_db()
        lines = PurchaseOrderLine.objects.filter(stock_unit=unit)
        assert unit.quantity == 0
        assert lines.count() == 5
        assert sum(line.quantity for line in lines) == 5
        assert PurchaseOrder.objects.filter(lines__stock_unit=unit).distinct().count() == 5
