# trace: FR-040, FR-041, FR-042, FR-043, FR-044, FR-045, ADDR-006
"""管理者機能（FR-040〜FR-045）の単体テスト。

期待値は FR-040〜FR-045 の処理内容・例外、管理者向け注文詳細内容（6.22.5）から導出する。
"""
from datetime import timedelta

import pytest

from shop.common import timeutils
from shop.common.errors import InvalidStatusTransitionError, NotFoundError, ValidationError
from shop.models import PurchaseOrder, PurchaseOrderStatus, Role, StockUnit
from shop.services import admin_orders
from shop.tests.unit import _helpers

pytestmark = pytest.mark.django_db


# trace: FR-040
def test_search_stock_units_returns_all_units_in_sku_order(db, supplier):
    """在庫単位一覧は非公開商品の在庫単位も含め SKU 昇順で返す。"""
    public_item = _helpers.make_item("ITEM-001", "公開商品")
    private_item = _helpers.make_item("ITEM-002", "非公開商品", is_public=False)
    _helpers.make_stock_unit(public_item, supplier, sku="SKU-B", price=1000, quantity=3)
    _helpers.make_stock_unit(private_item, supplier, sku="SKU-A", price=500, quantity=7)

    result = admin_orders.search_stock_units()

    assert [row["sku"] for row in result["results"]] == ["SKU-A", "SKU-B"]
    assert result["page_size"] == 50
    assert result["results"][0]["item_is_public"] is False
    assert result["results"][0]["supplier_name"] == supplier.name


# trace: FR-040
def test_search_stock_units_marks_low_stock(db, supplier, item):
    """在庫数量が5以下の在庫単位を低在庫とする（境界値）。"""
    _helpers.make_stock_unit(item, supplier, sku="SKU-A", quantity=5)
    _helpers.make_stock_unit(item, supplier, sku="SKU-B", quantity=6)

    rows = {row["sku"]: row for row in admin_orders.search_stock_units()["results"]}

    assert rows["SKU-A"]["is_low_stock"] is True
    assert rows["SKU-B"]["is_low_stock"] is False


# trace: FR-040
def test_search_stock_units_filters_by_low_stock_only(db, supplier, item):
    """低在庫のみ指定時は在庫数量5以下の在庫単位だけを返す。"""
    _helpers.make_stock_unit(item, supplier, sku="SKU-A", quantity=5)
    _helpers.make_stock_unit(item, supplier, sku="SKU-B", quantity=6)

    result = admin_orders.search_stock_units(raw_low_stock_only="true")

    assert [row["sku"] for row in result["results"]] == ["SKU-A"]


# trace: FR-040
def test_search_stock_units_filters_by_sku_prefix_and_item_name(db, supplier):
    """SKU は前方一致、商品名は部分一致で絞り込む。"""
    first = _helpers.make_item("ITEM-001", "デジタルカメラ")
    second = _helpers.make_item("ITEM-002", "書籍")
    _helpers.make_stock_unit(first, supplier, sku="CAM-001")
    _helpers.make_stock_unit(second, supplier, sku="BOOK-001")

    assert [row["sku"] for row in admin_orders.search_stock_units(raw_sku="CAM")["results"]] == ["CAM-001"]
    assert admin_orders.search_stock_units(raw_sku="AM")["total_count"] == 0
    assert [row["sku"] for row in admin_orders.search_stock_units(raw_item_name="カメラ")["results"]] == ["CAM-001"]


# trace: FR-040
def test_search_stock_units_filters_by_supplier(db, item):
    """仕入先で絞り込む。"""
    first = _helpers.make_supplier("SUP-101", "仕入先A")
    second = _helpers.make_supplier("SUP-102", "仕入先B")
    _helpers.make_stock_unit(item, first, sku="SKU-A")
    _helpers.make_stock_unit(item, second, sku="SKU-B")

    result = admin_orders.search_stock_units(raw_supplier_id=second.supplier_id)

    assert [row["sku"] for row in result["results"]] == ["SKU-B"]


# trace: FR-040
@pytest.mark.parametrize(
    ("kwargs", "expected_field"),
    [
        ({"raw_sku": "A" * 33}, "sku"),
        ({"raw_item_name": "あ" * 101}, "item_name"),
        ({"raw_supplier_id": "999999"}, "supplier_id"),
        ({"raw_supplier_id": "abc"}, "supplier_id"),
        ({"raw_low_stock_only": "yes"}, "low_stock_only"),
        ({"raw_page": "0"}, "page"),
    ],
)
def test_search_stock_units_rejects_invalid_conditions(db, kwargs, expected_field):
    """検索条件の不備は入力エラーとして通知する。"""
    with pytest.raises(ValidationError) as exc:
        admin_orders.search_stock_units(**kwargs)

    assert any(detail["field"] == expected_field for detail in exc.value.details)


# trace: FR-040
def test_search_stock_units_paginates_50_per_page(db, supplier, item):
    """在庫単位一覧は1ページ50件で返す。"""
    for index in range(51):
        _helpers.make_stock_unit(item, supplier, sku=f"SKU-{index:03d}")

    first_page = admin_orders.search_stock_units()
    second_page = admin_orders.search_stock_units(raw_page="2")

    assert len(first_page["results"]) == 50
    assert first_page["total_count"] == 51
    assert first_page["total_pages"] == 2
    assert len(second_page["results"]) == 1


# trace: FR-041
def test_search_orders_returns_all_buyers_orders(db, stock_unit):
    """注文一覧（管理者）は全購入者の注文を注文日時の降順で返す。"""
    first_buyer = _helpers.make_user(email="buyer1@example.com")
    second_buyer = _helpers.make_user(email="buyer2@example.com")
    older = _helpers.make_order(first_buyer, stock_unit, order_number="PO-00000001")
    older.ordered_at = timeutils.now() - timedelta(days=1)
    older.save(update_fields=["ordered_at"])
    _helpers.make_order(second_buyer, stock_unit, order_number="PO-00000002")

    result = admin_orders.search_orders()

    assert [row["order_number"] for row in result["results"]] == ["PO-00000002", "PO-00000001"]
    assert result["results"][0]["buyer_email"] == "buyer2@example.com"
    assert result["page_size"] == 20


# trace: FR-041
def test_search_orders_filters_by_order_number_and_status(buyer, stock_unit):
    """注文番号（完全一致）・注文状態（複数指定）で絞り込む。"""
    _helpers.make_order(buyer, stock_unit, order_number="PO-00000001")
    paid = _helpers.make_order(buyer, stock_unit, status=PurchaseOrderStatus.PAID, order_number="PO-00000002")

    by_number = admin_orders.search_orders(raw_order_number="PO-00000002")
    by_status = admin_orders.search_orders(raw_statuses=[PurchaseOrderStatus.PAID])

    assert [row["purchase_order_id"] for row in by_number["results"]] == [paid.purchase_order_id]
    assert [row["purchase_order_id"] for row in by_status["results"]] == [paid.purchase_order_id]


# trace: FR-041
def test_search_orders_filters_by_ordered_date_range(buyer, stock_unit):
    """注文日（開始・終了）は JST の日付境界で絞り込む（終了日を含む）。"""
    today = timeutils.now()
    yesterday_order = _helpers.make_order(buyer, stock_unit, order_number="PO-00000001")
    yesterday_order.ordered_at = today - timedelta(days=1)
    yesterday_order.save(update_fields=["ordered_at"])
    today_order = _helpers.make_order(buyer, stock_unit, order_number="PO-00000002")

    date_text = today.date().isoformat()
    result = admin_orders.search_orders(raw_ordered_from=date_text, raw_ordered_to=date_text)

    assert [row["purchase_order_id"] for row in result["results"]] == [today_order.purchase_order_id]


# trace: FR-041
def test_search_orders_filters_by_buyer_email_partial_match(db, stock_unit):
    """購入者のメールアドレスは部分一致で絞り込む。"""
    target = _helpers.make_user(email="target.buyer@example.com")
    other = _helpers.make_user(email="another@example.com")
    _helpers.make_order(target, stock_unit, order_number="PO-00000001")
    _helpers.make_order(other, stock_unit, order_number="PO-00000002")

    result = admin_orders.search_orders(raw_buyer_email="TARGET")

    assert [row["buyer_email"] for row in result["results"]] == ["target.buyer@example.com"]


# trace: FR-041
@pytest.mark.parametrize(
    ("kwargs", "expected_field"),
    [
        ({"raw_order_number": "PO-1234"}, "order_number"),
        ({"raw_order_number": "XX-12345678"}, "order_number"),
        ({"raw_statuses": ["unknown"]}, "status"),
        ({"raw_ordered_from": "2026/01/01"}, "ordered_from"),
        ({"raw_ordered_to": "2026-02-30"}, "ordered_to"),
        ({"raw_buyer_email": "a" * 255}, "buyer_email"),
        ({"raw_page": "abc"}, "page"),
    ],
)
def test_search_orders_rejects_invalid_conditions(db, kwargs, expected_field):
    """検索条件の不備は入力エラーとして通知する。"""
    with pytest.raises(ValidationError) as exc:
        admin_orders.search_orders(**kwargs)

    assert any(detail["field"] == expected_field for detail in exc.value.details)


# trace: FR-041
def test_search_orders_rejects_reversed_date_range(db):
    """注文日（終了）が注文日（開始）より前の場合は入力エラーとする。"""
    with pytest.raises(ValidationError) as exc:
        admin_orders.search_orders(raw_ordered_from="2026-05-02", raw_ordered_to="2026-05-01")

    assert any(detail["field"] == "ordered_to" for detail in exc.value.details)


# trace: FR-041
def test_search_orders_accepts_same_date_range(db):
    """注文日（開始）と注文日（終了）が同日の場合は有効な条件とする（境界値）。"""
    result = admin_orders.search_orders(raw_ordered_from="2026-05-01", raw_ordered_to="2026-05-01")

    assert result["total_count"] == 0


# trace: FR-042
def test_get_admin_order_detail_includes_buyer_and_payment_records(buyer, stock_unit):
    """管理者向け注文詳細は購入者情報・決済記録・実行者の利用者IDを含む。"""
    order = _helpers.make_order(buyer, stock_unit, order_number="PO-00000001")
    from shop.models import PaymentRecord, PaymentResult

    PaymentRecord.objects.create(
        purchase_order=order,
        result=PaymentResult.APPROVED,
        amount=order.total,
        transaction_ref="MOCK-ABCDEFGHIJ123456",
        processed_at=timeutils.now(),
    )
    from shop.services.orders import record_status_change

    record_status_change(order, None, PurchaseOrderStatus.CREATED, order.ordered_at, buyer)

    detail = admin_orders.get_order_detail(order.purchase_order_id)

    assert detail["buyer"]["email"] == buyer.email
    assert detail["payment_records"][0]["result"] == PaymentResult.APPROVED
    assert detail["status_history"][0]["actor_user_id"] == buyer.user_id
    assert detail["can_ship"] is False
    assert detail["can_deliver"] is False


# trace: FR-042
@pytest.mark.parametrize("raw_order_id", ["abc", "", None, 999999])
def test_get_admin_order_detail_rejects_unknown_order(db, raw_order_id):
    """存在しない注文・解釈できない識別子は対象なしとする。"""
    with pytest.raises(NotFoundError):
        admin_orders.get_order_detail(raw_order_id)


# trace: FR-043
def test_ship_order_moves_paid_order_to_shipped(admin_user, buyer, stock_unit):
    """支払済の注文を出荷済へ遷移させ、配送伝票番号と状態履歴を記録する。"""
    order = _helpers.make_order(buyer, stock_unit, status=PurchaseOrderStatus.PAID, order_number="PO-00000001")

    detail = admin_orders.ship_order(admin_user, order.purchase_order_id, "TRACK-123")

    updated = PurchaseOrder.objects.get(pk=order.pk)
    assert detail["status"] == PurchaseOrderStatus.SHIPPED
    assert updated.status == PurchaseOrderStatus.SHIPPED
    assert updated.shipped_at is not None
    assert updated.tracking_number == "TRACK-123"
    history = updated.status_history.order_by("status_history_id").last()
    assert (history.from_status, history.to_status) == (PurchaseOrderStatus.PAID, PurchaseOrderStatus.SHIPPED)
    assert history.actor_role == Role.ADMIN


# trace: FR-043
def test_ship_order_without_tracking_number(admin_user, buyer, stock_unit):
    """配送伝票番号は任意項目であり、未指定でも出荷登録できる。"""
    order = _helpers.make_order(buyer, stock_unit, status=PurchaseOrderStatus.PAID, order_number="PO-00000001")

    admin_orders.ship_order(admin_user, order.purchase_order_id, "  ")

    assert PurchaseOrder.objects.get(pk=order.pk).tracking_number is None


# trace: FR-043
@pytest.mark.parametrize("tracking_number", ["A" * 31, "TRACK 123", "追跡番号"])
def test_ship_order_rejects_invalid_tracking_number(admin_user, buyer, stock_unit, tracking_number):
    """配送伝票番号は英数字とハイフンで30文字以下とする（境界値・形式）。"""
    order = _helpers.make_order(buyer, stock_unit, status=PurchaseOrderStatus.PAID, order_number="PO-00000001")

    with pytest.raises(ValidationError) as exc:
        admin_orders.ship_order(admin_user, order.purchase_order_id, tracking_number)

    assert exc.value.details[0]["field"] == "tracking_number"
    assert PurchaseOrder.objects.get(pk=order.pk).status == PurchaseOrderStatus.PAID


# trace: FR-043
def test_ship_order_accepts_max_length_tracking_number(admin_user, buyer, stock_unit):
    """配送伝票番号の30文字は受け付ける（境界値）。"""
    order = _helpers.make_order(buyer, stock_unit, status=PurchaseOrderStatus.PAID, order_number="PO-00000001")
    tracking_number = "A" * 30

    admin_orders.ship_order(admin_user, order.purchase_order_id, tracking_number)

    assert PurchaseOrder.objects.get(pk=order.pk).tracking_number == tracking_number


# trace: FR-043
@pytest.mark.parametrize(
    "status",
    [
        PurchaseOrderStatus.CREATED,
        PurchaseOrderStatus.SHIPPED,
        PurchaseOrderStatus.DELIVERED,
        PurchaseOrderStatus.CANCELLED,
    ],
)
def test_ship_order_rejects_non_paid_status(admin_user, buyer, stock_unit, status):
    """出荷登録できるのは支払済の注文に限る。"""
    order = _helpers.make_order(buyer, stock_unit, status=status, order_number="PO-00000001")

    with pytest.raises(InvalidStatusTransitionError) as exc:
        admin_orders.ship_order(admin_user, order.purchase_order_id, None)

    assert exc.value.context["current_status"] == status


# trace: FR-044
def test_deliver_order_moves_shipped_order_to_delivered(admin_user, buyer, stock_unit):
    """出荷済の注文を配達完了へ遷移させ、状態履歴を記録する。"""
    order = _helpers.make_order(buyer, stock_unit, status=PurchaseOrderStatus.SHIPPED, order_number="PO-00000001")

    detail = admin_orders.deliver_order(admin_user, order.purchase_order_id)

    updated = PurchaseOrder.objects.get(pk=order.pk)
    assert detail["status"] == PurchaseOrderStatus.DELIVERED
    assert updated.delivered_at is not None
    history = updated.status_history.order_by("status_history_id").last()
    assert (history.from_status, history.to_status) == (PurchaseOrderStatus.SHIPPED, PurchaseOrderStatus.DELIVERED)


# trace: FR-044
@pytest.mark.parametrize(
    "status",
    [
        PurchaseOrderStatus.CREATED,
        PurchaseOrderStatus.PAID,
        PurchaseOrderStatus.DELIVERED,
        PurchaseOrderStatus.CANCELLED,
    ],
)
def test_deliver_order_rejects_non_shipped_status(admin_user, buyer, stock_unit, status):
    """配達完了登録できるのは出荷済の注文に限る。"""
    order = _helpers.make_order(buyer, stock_unit, status=status, order_number="PO-00000001")

    with pytest.raises(InvalidStatusTransitionError):
        admin_orders.deliver_order(admin_user, order.purchase_order_id)


# trace: FR-045
@pytest.mark.parametrize("status", [PurchaseOrderStatus.CREATED, PurchaseOrderStatus.PAID])
def test_admin_cancel_order_restores_stock(admin_user, buyer, stock_unit, status):
    """管理者は出荷前の注文をキャンセルでき、在庫を戻す。"""
    stock_unit.quantity = 4
    stock_unit.save(update_fields=["quantity"])
    order = _helpers.make_order(buyer, stock_unit, quantity=2, status=status, order_number="PO-00000001")

    detail = admin_orders.cancel_order(admin_user, order.purchase_order_id)

    assert detail["status"] == PurchaseOrderStatus.CANCELLED
    assert StockUnit.objects.get(pk=stock_unit.pk).quantity == 6
    history = PurchaseOrder.objects.get(pk=order.pk).status_history.order_by("status_history_id").last()
    assert history.actor_role == Role.ADMIN
    assert history.actor_user_id == admin_user.user_id


# trace: FR-045
@pytest.mark.parametrize(
    "status", [PurchaseOrderStatus.SHIPPED, PurchaseOrderStatus.DELIVERED, PurchaseOrderStatus.CANCELLED]
)
def test_admin_cancel_order_rejects_shipped_or_later(admin_user, buyer, stock_unit, status):
    """出荷済以降・キャンセル済の注文はキャンセルできない。"""
    order = _helpers.make_order(buyer, stock_unit, status=status, order_number="PO-00000001")
    before = StockUnit.objects.get(pk=stock_unit.pk).quantity

    with pytest.raises(InvalidStatusTransitionError):
        admin_orders.cancel_order(admin_user, order.purchase_order_id)

    assert StockUnit.objects.get(pk=stock_unit.pk).quantity == before


# trace: FR-040
def test_list_suppliers_in_code_order(db):
    """画面の検索条件に表示する仕入先は仕入先コード昇順で返す。"""
    _helpers.make_supplier("SUP-002", "仕入先B")
    _helpers.make_supplier("SUP-001", "仕入先A")

    assert [supplier.supplier_code for supplier in admin_orders.list_suppliers()] == ["SUP-001", "SUP-002"]


# trace: FR-041
def test_list_order_statuses_returns_code_values():
    """注文状態の選択肢は CD-02 の値と表示名を返す。"""
    statuses = admin_orders.list_order_statuses()

    assert [value for value, _ in statuses] == ["created", "paid", "shipped", "delivered", "cancelled"]
