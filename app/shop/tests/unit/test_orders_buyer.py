# trace: FR-032, FR-033, FR-034, ADDR-001
"""注文履歴一覧・注文詳細・注文キャンセル（購入者）（FR-032〜FR-034）の単体テスト。

期待値は FR-032〜FR-034 の処理内容・注文詳細内容（6.18.5）・状態遷移（ST-PO）から導出する。
"""
from datetime import timedelta

import pytest

from shop.common import timeutils
from shop.common.errors import InvalidStatusTransitionError, NotFoundError, ValidationError
from shop.models import PurchaseOrder, PurchaseOrderStatus, Role, StockUnit
from shop.services import orders, representations
from shop.tests.unit import _helpers

pytestmark = pytest.mark.django_db


# trace: FR-032
def test_list_orders_returns_only_own_orders(buyer, other_buyer, stock_unit):
    """注文履歴は本人の注文だけを返す。"""
    _helpers.make_order(buyer, stock_unit, order_number="PO-00000001")
    _helpers.make_order(other_buyer, stock_unit, order_number="PO-00000002")

    result = orders.list_orders(buyer)

    assert [row["order_number"] for row in result["results"]] == ["PO-00000001"]
    assert result["total_count"] == 1


# trace: FR-032
def test_list_orders_sorted_by_ordered_at_desc(buyer, stock_unit):
    """注文履歴は注文日時の降順で返す。"""
    older = _helpers.make_order(buyer, stock_unit, order_number="PO-00000001")
    older.ordered_at = timeutils.now() - timedelta(days=1)
    older.save(update_fields=["ordered_at"])
    _helpers.make_order(buyer, stock_unit, order_number="PO-00000002")

    result = orders.list_orders(buyer)

    assert [row["order_number"] for row in result["results"]] == ["PO-00000002", "PO-00000001"]


# trace: FR-032
def test_list_orders_returns_summary_fields(buyer, stock_unit):
    """一覧は注文番号・注文日時・状態・合計・合計点数を返す。"""
    order = _helpers.make_order(buyer, stock_unit, quantity=3, order_number="PO-00000001")

    row = orders.list_orders(buyer)["results"][0]

    assert row["purchase_order_id"] == order.purchase_order_id
    assert row["status"] == PurchaseOrderStatus.CREATED
    assert row["total"] == order.total
    assert row["total_quantity"] == 3


# trace: FR-032
def test_list_orders_paginates_20_per_page(buyer, stock_unit):
    """注文履歴は1ページ20件で返す。"""
    for index in range(21):
        order = _helpers.make_order(buyer, stock_unit, order_number=f"PO-{index:08d}")
        order.ordered_at = timeutils.now() - timedelta(minutes=index)
        order.save(update_fields=["ordered_at"])

    first_page = orders.list_orders(buyer)
    second_page = orders.list_orders(buyer, "2")

    assert len(first_page["results"]) == 20
    assert first_page["total_count"] == 21
    assert first_page["total_pages"] == 2
    assert len(second_page["results"]) == 1


# trace: FR-032
def test_list_orders_returns_empty_result_for_no_orders(buyer):
    """注文が0件の場合は空の一覧（総ページ数0）を返す。"""
    result = orders.list_orders(buyer)

    assert (result["results"], result["total_count"], result["total_pages"]) == ([], 0, 0)


# trace: FR-032
@pytest.mark.parametrize("raw_page", ["0", "-1", "abc"])
def test_list_orders_rejects_invalid_page(buyer, raw_page):
    """ページ番号が1以上の整数でない場合は入力エラーとする。"""
    with pytest.raises(ValidationError) as exc:
        orders.list_orders(buyer, raw_page)

    assert exc.value.details[0]["field"] == "page"


# trace: FR-033
def test_get_order_detail_returns_detail(buyer, stock_unit):
    """注文詳細は明細・金額内訳・配送先・状態履歴と操作可否を返す。"""
    order = _helpers.make_order(buyer, stock_unit, quantity=2, order_number="PO-00000001")
    orders.record_status_change(order, None, PurchaseOrderStatus.CREATED, order.ordered_at, buyer)

    detail = orders.get_order_detail(buyer, order.purchase_order_id)

    assert detail["order_number"] == "PO-00000001"
    assert detail["lines"][0]["quantity"] == 2
    assert detail["amounts"]["total"] == order.total
    assert detail["shipping_address"]["postal_code"] == "1234567"
    assert detail["status_history"][0]["to_status"] == PurchaseOrderStatus.CREATED
    assert detail["can_pay"] is True
    assert detail["can_cancel"] is True


# trace: FR-033
def test_get_order_detail_excludes_payment_records_and_actor_user_id(buyer, stock_unit):
    """購入者向け注文詳細には決済記録・実行者の利用者IDを含めない（MSG-04）。"""
    order = _helpers.make_order(buyer, stock_unit, order_number="PO-00000001")
    orders.record_status_change(order, None, PurchaseOrderStatus.CREATED, order.ordered_at, buyer)

    detail = orders.get_order_detail(buyer, order.purchase_order_id)

    assert "payment_records" not in detail
    assert "buyer" not in detail
    assert "actor_user_id" not in detail["status_history"][0]
    assert detail["status_history"][0]["actor_role"] == Role.BUYER


# trace: FR-033
def test_get_order_detail_rejects_other_buyers_order(buyer, other_buyer, stock_unit):
    """他の購入者の注文は対象なしとする（存在有無を明かさない）。"""
    order = _helpers.make_order(buyer, stock_unit, order_number="PO-00000001")

    with pytest.raises(NotFoundError) as exc:
        orders.get_order_detail(other_buyer, order.purchase_order_id)

    assert exc.value.http_status == 404


# trace: FR-033
@pytest.mark.parametrize("raw_order_id", ["abc", "", None, 999999])
def test_get_order_detail_rejects_unknown_order(buyer, raw_order_id):
    """識別子として解釈できない値・存在しない注文は対象なしとする。"""
    with pytest.raises(NotFoundError):
        orders.get_order_detail(buyer, raw_order_id)


# trace: FR-034
@pytest.mark.parametrize("status", [PurchaseOrderStatus.CREATED, PurchaseOrderStatus.PAID])
def test_cancel_order_restores_stock_and_records_history(buyer, stock_unit, status):
    """注文受付・支払済の注文はキャンセルでき、在庫を戻して状態履歴を記録する。"""
    stock_unit.quantity = 5
    stock_unit.save(update_fields=["quantity"])
    order = _helpers.make_order(buyer, stock_unit, quantity=2, status=status, order_number="PO-00000001")

    result = orders.cancel_order(buyer, order.purchase_order_id)

    updated = PurchaseOrder.objects.get(pk=order.pk)
    assert result["status"] == PurchaseOrderStatus.CANCELLED
    assert updated.status == PurchaseOrderStatus.CANCELLED
    assert updated.cancelled_at is not None
    assert StockUnit.objects.get(pk=stock_unit.pk).quantity == 7
    history = updated.status_history.order_by("status_history_id").last()
    assert (history.from_status, history.to_status) == (status, PurchaseOrderStatus.CANCELLED)
    assert history.actor_role == Role.BUYER


# trace: FR-034
@pytest.mark.parametrize(
    "status", [PurchaseOrderStatus.SHIPPED, PurchaseOrderStatus.DELIVERED, PurchaseOrderStatus.CANCELLED]
)
def test_cancel_order_rejects_shipped_or_later(buyer, stock_unit, status):
    """出荷済以降・キャンセル済の注文はキャンセルできず、在庫も変更しない。"""
    order = _helpers.make_order(buyer, stock_unit, quantity=2, status=status, order_number="PO-00000001")
    before = StockUnit.objects.get(pk=stock_unit.pk).quantity

    with pytest.raises(InvalidStatusTransitionError) as exc:
        orders.cancel_order(buyer, order.purchase_order_id)

    assert exc.value.context["current_status"] == status
    assert StockUnit.objects.get(pk=stock_unit.pk).quantity == before
    assert PurchaseOrder.objects.get(pk=order.pk).status == status


# trace: FR-034
def test_cancel_order_rejects_other_buyers_order(buyer, other_buyer, stock_unit):
    """他の購入者の注文はキャンセルできない（対象なし）。"""
    order = _helpers.make_order(buyer, stock_unit, order_number="PO-00000001")

    with pytest.raises(NotFoundError):
        orders.cancel_order(other_buyer, order.purchase_order_id)


# trace: FR-033
@pytest.mark.parametrize(
    ("status", "can_pay", "can_cancel", "can_ship", "can_deliver"),
    [
        (PurchaseOrderStatus.CREATED, True, True, False, False),
        (PurchaseOrderStatus.PAID, False, True, True, False),
        (PurchaseOrderStatus.SHIPPED, False, False, False, True),
        (PurchaseOrderStatus.DELIVERED, False, False, False, False),
        (PurchaseOrderStatus.CANCELLED, False, False, False, False),
    ],
)
def test_order_operation_availability_by_status(buyer, stock_unit, status, can_pay, can_cancel, can_ship, can_deliver):
    """状態ごとに実行できる操作（支払・キャンセル・出荷・配達完了）が決まる（ST-PO）。"""
    order = _helpers.make_order(buyer, stock_unit, status=status, order_number="PO-00000001")

    assert representations.can_pay(order) is can_pay
    assert representations.can_cancel(order) is can_cancel
    assert representations.can_ship(order) is can_ship
    assert representations.can_deliver(order) is can_deliver


# trace: FR-033
def test_order_detail_coupon_snapshot(buyer, stock_unit):
    """注文詳細のクーポンは注文へ複写した値を返し、未適用は None を返す。"""
    order = _helpers.make_order(buyer, stock_unit, order_number="PO-00000001")

    assert representations.order_detail(order)["coupon"] is None

    order.coupon_code = "SAVE500"
    order.coupon_discount_type = "fixed"
    order.coupon_discount_value = 500
    order.save(update_fields=["coupon_code", "coupon_discount_type", "coupon_discount_value"])

    coupon = representations.order_detail(order)["coupon"]
    assert coupon == {"code": "SAVE500", "discount_type": "fixed", "discount_value": 500}
