# trace: NFR-AV-10, NFR-PF-11, NFR-PF-12, NFR-LG-03
# trace: FR-010, FR-011, FR-012, FR-020, FR-021, FR-030, FR-031, FR-032, FR-033, FR-034, FR-060
# trace: ADDR-001, ADDR-003, ADDR-005, ADDR-007, ADDR-009, ADDR-010
"""縮退運転・定期処理・帳簿書類の保存・上限超過時の整合性に関する非機能要件の結合試験。

期待結果は非機能要件定義書 4章（NFR-AV-10 障害時の縮退）、5章（NFR-PF-11 上限超過時の挙動、
NFR-PF-12 バッチ処理時間）、11章（NFR-LG-03 法人税法：帳簿書類の保存）の
「要件内容」「目標値」「備考」欄から導出する。

NFR-AV-10・NFR-PF-12 は要件本文が「該当なし」（当該の機能・構成を設けない）と定めるため、
対象外機能（FR-OUT-01〜16）と同じく「設けられていないこと」を積極的に確認する。
NFR-PF-11 は負荷の測定値（310利用者・10分間での 5xx 応答率）ではなく、
要件本文が定める不変条件（受け付けた要求には正常応答または業務エラー応答を返す、
在庫数量が0未満にならない、金額整合を満たさない注文が無い）だけを判定する。
NFR-LG-03 は保存期間（7年）そのものではなく、
システムが帳簿書類を書き換えず、削除する手段も自動削除の仕組みも持たないことを判定する。
"""
import importlib.metadata
import threading
from pathlib import Path

import pytest
from django.core.management import call_command, get_commands
from django.db import connections
from django.db.backends.utils import CursorWrapper
from django.db.utils import OperationalError
from django.test import Client

from shop.common import timeutils
from shop.models import (
    PaymentRecord,
    PaymentResult,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseOrderStatus,
    PurchaseOrderStatusHistory,
    ShippingAddress,
    StockUnit,
)
from tests.integration import _helpers

# 定期実行の仕組みを提供するライブラリ（NFR-PF-12：定期バッチを持たない）。
SCHEDULER_PACKAGES = {
    "celery",
    "django-celery-beat",
    "django-celery-results",
    "apscheduler",
    "django-apscheduler",
    "schedule",
    "rq",
    "django-rq",
    "huey",
    "django-q",
    "django-q2",
    "django-crontab",
    "django-cron",
}

# 上限超過時に許容する応答（正常応答または業務エラー応答。NFR-PF-11 の要件内容）。
ACCEPTED_STATUSES = {200, 201, 400, 401, 403, 404, 409, 422}

# 同時に送信する要求数（想定を超える同時要求。在庫 3×4単位に対して 24 要求）。
OVER_CAPACITY_REQUESTS = 24
STOCK_UNITS = 4
STOCK_PER_UNIT = 3


# trace: FR-030
def _buyer_with_cart_line(email: str, unit_id) -> str:
    """購入者を作成し、カートへ数量1の明細を追加して認証トークンを返す。"""
    _helpers.make_user(email=email)
    client = _helpers.ApiClient(Client())
    token = client.login(email)
    response = client.post("/api/cart/lines", {"stock_unit_id": unit_id, "quantity": 1}, token=token)
    assert response.status_code == 200, response.content
    return token


# trace: FR-030, FR-031
def _run_concurrently(actions: list[tuple[str, object]]) -> dict[str, tuple[int, dict | None]]:
    """名前つきの複数要求を同時に送信し、{名前: (ステータス, 本文)} を返す。"""
    barrier = threading.Barrier(len(actions))
    results: dict[str, tuple[int, dict | None]] = {}
    lock = threading.Lock()

    def run(name: str, action) -> None:
        """同時に1要求を送信して結果を記録する。"""
        try:
            barrier.wait(timeout=60)
            status, body = action()
            with lock:
                results[name] = (status, body)
        finally:
            connections.close_all()

    threads = [threading.Thread(target=run, args=(name, action)) for name, action in actions]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=180)
        assert not thread.is_alive(), "同時要求が時間内に完了しなかった"
    assert len(results) == len(actions)
    return results


# trace: FR-030, FR-031
def _post(path: str, data: dict, token: str):
    """同時送信用に、新しい接続で POST を1回行う処理を組み立てる。"""

    def action() -> tuple[int, dict | None]:
        """POST を送信して (ステータス, 本文) を返す。"""
        client = _helpers.ApiClient(Client())
        response = client.post(path, data, token=token)
        try:
            return response.status_code, response.json()
        except ValueError:
            return response.status_code, None

    return action


# trace: FR-030
def _place_order(api, token, unit, quantity: int = 2):
    """カート投入から注文確定までを行い、注文IDを返す。"""
    added = api.post("/api/cart/lines", {"stock_unit_id": unit.stock_unit_id, "quantity": quantity}, token=token)
    assert added.status_code == 200, added.content
    created = api.post("/api/checkout", dict(_helpers.VALID_ADDRESS), token=token)
    assert created.status_code == 201, created.content
    return created.json()["purchase_order_id"]


# trace: NFR-AV-10, FR-010, FR-011, FR-012, FR-020, FR-032, ADDR-007
@pytest.mark.django_db(transaction=True)
@pytest.mark.case("IT-AI-GF-077")
def test_no_degraded_operation_is_provided_when_the_database_stops(api, monkeypatch):
    """DB が停止した場合に一部機能だけを継続する縮退運転を行わない（NFR-AV-10）。"""
    collection = _helpers.make_collection()
    item = _helpers.make_item(collections=[collection])
    supplier = _helpers.make_supplier()
    unit = _helpers.make_stock_unit(item, supplier, price=1500, quantity=5)
    _helpers.make_user()
    token = api.login("buyer@example.com")
    assert api.post(
        "/api/cart/lines", {"stock_unit_id": unit.stock_unit_id, "quantity": 1}, token=token
    ).status_code == 200

    public_paths = ["/api/collections", "/api/items", f"/api/items/{item.item_id}"]
    private_paths = ["/api/cart", "/api/purchase-orders"]
    # 停止前は全経路が正常に応答する（比較の基準）。
    for path in public_paths + private_paths:
        assert api.get(path, token=token).status_code == 200, path

    def unavailable(*args, **kwargs):
        """DB 接続の停止を模擬する。"""
        raise OperationalError("database is not available")

    monkeypatch.setattr(CursorWrapper, "execute", unavailable)
    monkeypatch.setattr(CursorWrapper, "executemany", unavailable)
    try:
        failing = _helpers.ApiClient(Client(raise_request_exception=False))
        for path in public_paths + private_paths:
            response = failing.get(path, token=token)
            assert response.status_code == 500, f"{path} が縮退して応答した: {response.status_code}"
            assert response.json()["error"]["code"] == "INTERNAL_ERROR", path

        for path in ("/", f"/items/{item.item_id}", "/cart"):
            screen = Client(raise_request_exception=False).get(path)
            assert screen.status_code == 500, f"{path} が縮退して応答した: {screen.status_code}"
            assert b"<table" not in screen.content, f"{path} が一部のデータを表示した"
    finally:
        monkeypatch.undo()
        for connection in connections.all():
            connection.close()

    # 復旧後は同じ経路が再び正常に応答する（恒久的な代替経路へ切り替わっていない）。
    for path in public_paths + private_paths:
        assert api.get(path, token=token).status_code == 200, path


# trace: NFR-PF-12, FR-060, ADDR-010
@pytest.mark.django_db
@pytest.mark.case("IT-AI-GF-078")
def test_no_periodic_batch_processing_is_provided(api):
    """定期的に実行するバッチ処理を持たない（NFR-PF-12。初期データ投入は運用者の手動実行）。"""
    installed = {
        (distribution.metadata["Name"] or "").lower().replace("_", "-")
        for distribution in importlib.metadata.distributions()
    }
    assert "django" in installed, "導入済みライブラリの取得に失敗している"
    assert SCHEDULER_PACKAGES.isdisjoint(installed), f"定期実行のライブラリが導入されている: {SCHEDULER_PACKAGES & installed}"

    assert not Path("/etc/crontab").exists(), "コンテナに cron の定義がある"
    cron_directory = Path("/etc/cron.d")
    assert not cron_directory.exists() or not list(cron_directory.iterdir()), "コンテナに cron の定義がある"

    shop_commands = {name for name, source in get_commands().items() if source == "shop"}
    assert shop_commands == {"load_initial_data"}, f"想定外の管理コマンドがある: {shop_commands}"
    # 初期データ一括投入は定義ファイルの指定を必須とする手動実行のコマンドであり、
    # 定期ジョブとして無人で実行できる既定動作を持たない（FR-060）。
    with pytest.raises(SystemExit) as failure:
        call_command("load_initial_data")
    assert failure.value.code != 0

    # 保存期間を過ぎた注文が自動削除されない（保存期間経過データの自動削除は本リリースの対象外）。
    _helpers.make_user()
    item, unit = _helpers.catalog(price=2000, quantity=5)
    token = api.login("buyer@example.com")
    order_id = _place_order(api, token, unit, quantity=1)
    aged = PurchaseOrder.objects.get(purchase_order_id=order_id)
    aged.ordered_at = timeutils.now().replace(year=timeutils.now().year - 8)
    aged.save(update_fields=["ordered_at"])

    # 以後の業務操作（照会・カート操作・注文確定）を行っても、古い注文は残り続ける。
    assert api.get("/api/purchase-orders", token=token).status_code == 200
    assert api.post(
        "/api/cart/lines", {"stock_unit_id": unit.stock_unit_id, "quantity": 1}, token=token
    ).status_code == 200
    assert api.post("/api/checkout", dict(_helpers.VALID_ADDRESS), token=token).status_code == 201
    assert PurchaseOrder.objects.filter(purchase_order_id=order_id).exists(), "古い注文が自動削除された"
    assert api.get(f"/api/purchase-orders/{order_id}", token=token).status_code == 200


# trace: NFR-LG-03, FR-030, FR-031, FR-033, FR-034, ADDR-001, ADDR-005
@pytest.mark.django_db
@pytest.mark.case("IT-AI-GF-079")
def test_order_ledger_records_are_kept_and_never_rewritten_or_deleted(api):
    """注文・注文明細・配送先・決済記録・注文状態履歴が書き換えも削除もされない（NFR-LG-03）。"""
    _helpers.make_user()
    collection = _helpers.make_collection()
    item = _helpers.make_item(collections=[collection])
    supplier = _helpers.make_supplier()
    unit_a = _helpers.make_stock_unit(item, supplier, sku="SKU-LG-A", price=2500, quantity=5)
    unit_b = _helpers.make_stock_unit(item, supplier, sku="SKU-LG-B", price=1800, quantity=5)
    token = api.login("buyer@example.com")

    for unit, quantity in ((unit_a, 2), (unit_b, 1)):
        added = api.post(
            "/api/cart/lines", {"stock_unit_id": unit.stock_unit_id, "quantity": quantity}, token=token
        )
        assert added.status_code == 200, added.content
    created = api.post("/api/checkout", dict(_helpers.VALID_ADDRESS), token=token)
    assert created.status_code == 201, created.content
    order_id = created.json()["purchase_order_id"]
    assert api.post(
        f"/api/purchase-orders/{order_id}/pay", {"mock_result": "approve"}, token=token
    ).status_code == 200

    order = PurchaseOrder.objects.get(purchase_order_id=order_id)
    before_order = {
        field: getattr(order, field)
        for field in (
            "order_number",
            "subtotal",
            "discount_amount",
            "discounted_subtotal",
            "shipping_fee",
            "tax_amount",
            "total",
            "ordered_at",
            "paid_at",
        )
    }
    before_lines = {
        line.purchase_order_line_id: (line.sku, line.item_name, line.unit_price, line.quantity, line.line_amount)
        for line in PurchaseOrderLine.objects.filter(purchase_order=order)
    }
    address = ShippingAddress.objects.get(purchase_order=order)
    before_address = (
        address.recipient_name,
        address.postal_code,
        address.prefecture_code,
        address.address_line1,
        address.address_line2,
        address.phone_number,
    )
    before_payments = {
        record.payment_record_id: (record.result, record.amount, record.transaction_ref, record.processed_at)
        for record in PaymentRecord.objects.filter(purchase_order=order)
    }
    before_history = [
        (row.from_status, row.to_status, row.changed_at)
        for row in PurchaseOrderStatusHistory.objects.filter(purchase_order=order).order_by("status_history_id")
    ]
    assert len(before_lines) == 2
    assert len(before_payments) == 1
    assert [(row[0], row[1]) for row in before_history] == [
        (None, PurchaseOrderStatus.CREATED),
        (PurchaseOrderStatus.CREATED, PurchaseOrderStatus.PAID),
    ]

    # キャンセルしても帳簿書類は消えず、記録済みの値も書き換わらない。
    cancelled = api.post(f"/api/purchase-orders/{order_id}/cancel", {}, token=token)
    assert cancelled.status_code == 200, cancelled.content

    order.refresh_from_db()
    assert order.status == PurchaseOrderStatus.CANCELLED
    for field, value in before_order.items():
        assert getattr(order, field) == value, f"{field} が書き換えられた"
    assert {
        line.purchase_order_line_id: (line.sku, line.item_name, line.unit_price, line.quantity, line.line_amount)
        for line in PurchaseOrderLine.objects.filter(purchase_order=order)
    } == before_lines
    address.refresh_from_db()
    assert (
        address.recipient_name,
        address.postal_code,
        address.prefecture_code,
        address.address_line1,
        address.address_line2,
        address.phone_number,
    ) == before_address
    assert {
        record.payment_record_id: (record.result, record.amount, record.transaction_ref, record.processed_at)
        for record in PaymentRecord.objects.filter(purchase_order=order)
    } == before_payments
    assert PaymentRecord.objects.get(purchase_order=order).result == PaymentResult.APPROVED
    history = [
        (row.from_status, row.to_status, row.changed_at)
        for row in PurchaseOrderStatusHistory.objects.filter(purchase_order=order).order_by("status_history_id")
    ]
    assert history[: len(before_history)] == before_history, "注文状態履歴が書き換えられた"
    assert history[-1][:2] == (PurchaseOrderStatus.PAID, PurchaseOrderStatus.CANCELLED)

    # 帳簿書類を削除する手段を画面・API に設けていない。
    for path in (
        f"/api/purchase-orders/{order_id}",
        "/api/purchase-orders",
        f"/api/admin/purchase-orders/{order_id}",
    ):
        response = api.delete(path, token=token)
        assert response.status_code not in {200, 201, 202, 204}, f"{path} の DELETE が成功した"
    assert PurchaseOrder.objects.filter(purchase_order_id=order_id).exists()
    assert PurchaseOrderLine.objects.filter(purchase_order=order).count() == 2
    assert ShippingAddress.objects.filter(purchase_order=order).exists()
    assert PaymentRecord.objects.filter(purchase_order=order).count() == 1

    # 削除された注文があると照会できないため、キャンセル後も注文詳細を参照できることを確かめる。
    detail = api.get(f"/api/purchase-orders/{order_id}", token=token)
    assert detail.status_code == 200
    assert len(detail.json()["lines"]) == 2
    assert detail.json()["amounts"]["total"] == before_order["total"]


# trace: NFR-PF-11, FR-021, FR-030, FR-031, FR-034, ADDR-001, ADDR-003
@pytest.mark.django_db(transaction=True)
@pytest.mark.case("IT-AI-GF-080")
def test_over_capacity_concurrent_requests_keep_stock_status_and_amounts_consistent():
    """想定を超える同時要求でもシステムエラーを返さず、在庫・注文状態・金額の不整合が生じない（NFR-PF-11）。"""
    collection = _helpers.make_collection()
    item = _helpers.make_item(collections=[collection])
    supplier = _helpers.make_supplier(supplier_code="SUP-PF11", name="架空商事")
    units = [
        _helpers.make_stock_unit(
            item, supplier, sku=f"SKU-PF11-{index}", price=2000 + index * 100, quantity=STOCK_PER_UNIT
        )
        for index in range(STOCK_UNITS)
    ]
    _helpers.make_coupon(code="PF11OFF", discount_value=500)

    tokens: dict[str, str] = {}
    for index in range(OVER_CAPACITY_REQUESTS):
        unit = units[index % STOCK_UNITS]
        name = f"buyer-{index:02d}"
        token = _buyer_with_cart_line(f"pf11-{index:02d}@example.com", unit.stock_unit_id)
        if index % 2 == 0:
            # 金額計算（割引）を伴う要求を混在させる。
            client = _helpers.ApiClient(Client())
            assert client.post("/api/cart/apply-coupon", {"code": "PF11OFF"}, token=token).status_code == 200
        tokens[name] = token

    checkout_results = _run_concurrently(
        [(name, _post("/api/checkout", dict(_helpers.VALID_ADDRESS), token)) for name, token in tokens.items()]
    )

    created: dict[str, str] = {}
    for name, (status, body) in sorted(checkout_results.items()):
        assert status != 500, f"{name}: システムエラーを返した: {body}"
        assert status in ACCEPTED_STATUSES, f"{name}: 正常応答でも業務エラー応答でもない: {status} {body}"
        if status == 201:
            created[name] = body["purchase_order_id"]
        else:
            assert body["error"]["code"] != "INTERNAL_ERROR", f"{name}: {body}"
    # 在庫の総数（3個×4単位）を超えて注文が成立していない。
    assert len(created) == STOCK_UNITS * STOCK_PER_UNIT, sorted(
        (name, status) for name, (status, _body) in checkout_results.items()
    )

    # 成立した注文に対して、支払とキャンセルを同時に要求する。
    follow_up = []
    for position, (name, order_id) in enumerate(sorted(created.items())):
        cancelling = position % 3 == 0
        path = f"/api/purchase-orders/{order_id}/" + ("cancel" if cancelling else "pay")
        data = {} if cancelling else {"mock_result": "approve"}
        follow_up.append((name, _post(path, data, tokens[name])))
    for name, (status, body) in sorted(_run_concurrently(follow_up).items()):
        assert status != 500, f"{name}: システムエラーを返した: {body}"
        assert status in ACCEPTED_STATUSES, f"{name}: 正常応答でも業務エラー応答でもない: {status} {body}"

    # 在庫数量が0未満の在庫単位が無い（NFR-PF-11 の目標値）。
    for unit in StockUnit.objects.all():
        assert unit.quantity >= 0, f"在庫数量が0未満: {unit.sku}={unit.quantity}"

    # 金額整合を満たさない注文が無い（NFR-PF-11 の目標値）。
    orders = list(PurchaseOrder.objects.all())
    assert len(orders) == len(created)
    for order in orders:
        assert order.discounted_subtotal == order.subtotal - order.discount_amount, order.order_number
        assert order.total == order.discounted_subtotal + order.shipping_fee + order.tax_amount, order.order_number
        lines = PurchaseOrderLine.objects.filter(purchase_order=order)
        assert order.subtotal == sum(line.line_amount for line in lines), order.order_number
        for line in lines:
            assert line.line_amount == line.unit_price * line.quantity, order.order_number
        assert order.status in set(PurchaseOrderStatus.values)

    # 引き当てた数量の合計が初期の在庫数量を超えていない。
    for unit in units:
        unit.refresh_from_db()
        outstanding = sum(
            line.quantity
            for line in PurchaseOrderLine.objects.filter(stock_unit=unit).select_related("purchase_order")
            if line.purchase_order.status != PurchaseOrderStatus.CANCELLED
        )
        assert unit.quantity + outstanding == STOCK_PER_UNIT, f"{unit.sku}: 在庫と引当の合計が一致しない"
