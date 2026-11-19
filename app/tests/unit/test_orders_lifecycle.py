# trace: FR-032, FR-033, FR-034, FR-041, FR-042, FR-043, FR-044, FR-045, NFR-SC-03, NFR-SC-04, NFR-SC-24
# trace: ADDR-001, ADDR-004
"""注文の照会・状態遷移の業務処理（orders.services：FR-032〜FR-034、FR-041〜FR-045）の単体テスト。

期待値は functional_requirements.md 6.17〜6.19・6.21〜6.25（処理内容・事後条件・例外）、CMN-04・18・26・35、
8章の注文の状態遷移（ST-PO-01〜06）、NFR-SC-03（他の購入者のデータは対象なし）、NFR-SC-24（決済記録を購入者に返さない）
から導出する。DB Test Strategy：CONTAINER（集計・日付範囲の SQL・トランザクションのロールバックを含めて検証）。
障害の経路は DB 例外を差し込む（MOCK）。行ロックによる排他（複数接続の並行実行）は単体テストでは扱わず、
結合テスト工程（ADDR-011 DD-010：transaction=True の同時実行試験）で確認する。
"""

from unittest import mock

import pytest
from django.db import DatabaseError

from catalog.models import StockUnit
from common import errors
from orders import services
from orders.models import Order, OrderStatusHistory, PaymentRecord
from tests.unit.conftest import jst, snapshot_order

pytestmark = pytest.mark.django_db
NOW = jst(2027, 4, 25, 16, 0, 0)
LATER = jst(2027, 4, 26, 10, 30, 0)
STATUS_LABELS = {
    "accepted": "注文受付",
    "paid": "支払済",
    "shipped": "出荷済",
    "delivered": "配達完了",
    "cancelled": "キャンセル済",
}
# キャンセル（FR-034・FR-045 手順5〜7）の障害点：状態の更新、1件目・2件目の在庫戻し、注文状態履歴の記録
CANCEL_FAULTS = [
    pytest.param(Order, "UPDATE", 1, [], id="order_update"),
    pytest.param(StockUnit, "UPDATE", 1, [("UPDATE", Order._meta.db_table)], id="first_stock_return"),
    pytest.param(
        StockUnit,
        "UPDATE",
        2,
        [("UPDATE", Order._meta.db_table), ("UPDATE", StockUnit._meta.db_table)],
        id="second_stock_return",
    ),
    pytest.param(
        OrderStatusHistory,
        "INSERT",
        1,
        [("UPDATE", Order._meta.db_table), ("UPDATE", StockUnit._meta.db_table), ("UPDATE", StockUnit._meta.db_table)],
        id="history_after_stock_return",
    ),
]
# 出荷登録・配達完了登録（FR-043・FR-044）の障害点：状態の更新、注文状態履歴の記録
TRANSITION_FAULTS = [
    pytest.param(Order, "UPDATE", [], id="order_update"),
    pytest.param(OrderStatusHistory, "INSERT", [("UPDATE", Order._meta.db_table)], id="history_after_order_update"),
]


# trace: FR-041
def _fields(exc_info):
    return {(f.field, f.reason) for f in exc_info.value.fields}


# trace: FR-034
def _history(order):
    return list(
        OrderStatusHistory.objects.filter(order=order)
        .order_by("pk")
        .values_list("from_status", "to_status", "actor_user_type")
    )


# trace: FR-034, FR-043, FR-044, FR-045
def _assert_unchanged_except(before, after, *updated_fields):
    """正常終了の事後条件のうち「処理前と同じ」項目の確認（6.19.6・6.23.6・6.24.6・6.25.6）。

    データ更新（6.19.5・6.23.5・6.24.5・6.25.5）の対象として updated_fields に挙げた注文の項目以外
    （注文日時・支払日時等の各日時、配送伝票番号、各金額）、注文明細、配送先、決済記録（件数と全項目）が
    処理前と同じであることを確認する。
    """
    for key, value in before["order"].items():
        if key not in updated_fields:
            assert after["order"][key] == value, key
    assert after["items"] == before["items"]
    assert after["address"] == before["address"]
    assert after["payments"] == before["payments"]  # 決済記録は追加・変更・削除されない


# ---------------------------------------------------------------------------
# FR-032 注文履歴一覧照会・FR-033 注文詳細照会（購入者）
# ---------------------------------------------------------------------------


# trace: FR-032
def test_list_my_orders_only_own_orders_newest_first_with_totals(buyer, other_buyer, catalog, make_order):
    unit = catalog.stock_unit(price=100)
    unit2 = catalog.stock_unit(price=100)
    old = make_order(buyer, [(unit, 2), (unit2, 3)], ordered_at=jst(2027, 4, 1))
    cancelled = make_order(buyer, [(unit, 1)], ordered_at=jst(2027, 4, 2), status="cancelled")
    same_time_a = make_order(buyer, [(unit, 1)], ordered_at=jst(2027, 4, 3))
    same_time_b = make_order(buyer, [(unit, 1)], ordered_at=jst(2027, 4, 3))
    make_order(other_buyer, [(unit, 1)], ordered_at=jst(2027, 4, 9))
    result = services.list_my_orders(buyer, None)
    assert [i["order_id"] for i in result["items"]] == [same_time_b.pk, same_time_a.pk, cancelled.pk, old.pk]
    assert result["total_count"] == 4 and result["page_size"] == 20 and result["total_pages"] == 1
    last = result["items"][-1]
    assert last == {
        "order_id": old.pk,
        "order_number": old.order_number,
        "ordered_at": jst(2027, 4, 1),
        "status": "accepted",
        "status_label": "注文受付",
        "total_amount": old.total_amount,
        "total_quantity": 5,
    }
    assert result["items"][2]["status_label"] == "キャンセル済"


# trace: FR-032
def test_list_my_orders_pagination_and_input_errors(buyer, other_buyer, catalog, make_order):
    unit = catalog.stock_unit()
    for _ in range(21):
        make_order(buyer, [(unit, 1)])
    page1 = services.list_my_orders(buyer, "1")
    assert len(page1["items"]) == 20 and page1["total_count"] == 21 and page1["total_pages"] == 2
    assert len(services.list_my_orders(buyer, "2")["items"]) == 1
    assert services.list_my_orders(buyer, "3")["items"] == []  # 総ページ数超過は0件（エラーにしない）
    for page, reason in (("0", "out_of_range"), ("x", "invalid_type")):
        with pytest.raises(errors.InputError) as info:
            services.list_my_orders(buyer, page)
        assert info.value.code == "E-032-03" and _fields(info) == {("page", reason)}
    empty = services.list_my_orders(other_buyer, None)
    assert empty["items"] == [] and empty["total_count"] == 0 and empty["total_pages"] == 0


# trace: FR-033, NFR-SC-24
def test_get_my_order_returns_detail_without_payments_or_actor_ids(buyer, catalog, make_order):
    unit = catalog.stock_unit(price=2500, sku="DET-1", variant_name="L")
    order = make_order(buyer, [(unit, 2)], status="paid")
    PaymentRecord.objects.create(
        order=order,
        result="approved",
        amount=order.total_amount,
        transaction_ref="MOCK-0123456789abcdef",
        processed_at=NOW,
    )
    detail = services.get_my_order(buyer, str(order.pk))
    assert detail["order_id"] == order.pk and detail["status"] == "paid" and detail["status_label"] == "支払済"
    assert detail["items"] == [
        {
            "stock_unit_id": unit.pk,
            "sku": "DET-1",
            "product_name": unit.product.name,
            "variant_name": "L",
            "unit_price_excluding_tax": 2500,
            "quantity": 2,
            "line_amount": 5000,
        }
    ]
    assert detail["coupon"] is None
    assert detail["shipping_address"]["address_line2"] is None
    assert detail["status_history"] == [
        {
            "from_status": None,
            "from_status_label": None,
            "to_status": "accepted",
            "to_status_label": "注文受付",
            "changed_at": order.ordered_at,
            "actor_user_type": "buyer",
            "actor_user_type_label": "購入者",
        }
    ]
    assert (detail["can_pay"], detail["can_cancel"]) == (False, True)
    assert "payments" not in detail and "buyer" not in detail and "MOCK-" not in str(detail)


# trace: FR-033
@pytest.mark.parametrize(
    ("status", "can_pay", "can_cancel"),
    [
        ("accepted", True, True),
        ("paid", False, True),
        ("shipped", False, False),
        ("delivered", False, False),
        ("cancelled", False, False),
    ],
)
def test_detail_operation_flags_by_status(buyer, catalog, make_order, status, can_pay, can_cancel):
    order = make_order(buyer, [(catalog.stock_unit(), 1)], status=status)
    detail = services.get_my_order(buyer, order.pk)
    assert (detail["can_pay"], detail["can_cancel"]) == (can_pay, can_cancel)
    admin_detail = services.admin_get_order(order.pk)
    assert admin_detail["can_ship"] is (status == "paid")
    assert admin_detail["can_deliver"] is (status == "shipped")


# trace: FR-033, NFR-SC-03
def test_get_my_order_other_buyers_order_is_indistinguishable_from_missing(buyer, other_buyer, catalog, make_order):
    others = make_order(other_buyer, [(catalog.stock_unit(), 1)])
    messages = set()
    for target in (others.pk, "abc", "0", 99999999, None):
        with pytest.raises(errors.NotFoundError) as info:
            services.get_my_order(buyer, target)
        assert info.value.code == "E-033-03"
        messages.add(info.value.message)
    assert len(messages) == 1


# ---------------------------------------------------------------------------
# FR-034 注文キャンセル（購入者）・FR-045 注文キャンセル（管理者）
# ---------------------------------------------------------------------------


# trace: FR-034
@pytest.mark.parametrize("status", ["accepted", "paid"])
def test_cancel_my_order_returns_stock_once_and_records_history(buyer, catalog, make_order, freeze, status):
    """6.19.4 手順6 の例：A 3個（在庫2）・B 1個（在庫0）→ 在庫 A 5・B 1。

    6.19.4 手順8・6.19.6 正常終了：決済記録の件数・内容（支払済の場合の承認の決済記録）、支払日時を含む注文の各日時、
    注文の金額・注文明細・配送先は処理前と同じ（ST-PO-04 でも支払日時・決済記録は変化しない）。
    """
    freeze(NOW)
    a = catalog.stock_unit(stock=2)
    b = catalog.stock_unit(stock=0)
    order = make_order(buyer, [(a, 3), (b, 1)], status=status)
    paid_at = jst(2027, 4, 1, 11, 5, 0)
    if status == "paid":
        Order.objects.filter(pk=order.pk).update(paid_at=paid_at)
        PaymentRecord.objects.create(
            order=order,
            result="approved",
            amount=order.total_amount,
            transaction_ref="MOCK-Q1W2E3R4T5Y6U7I8",
            processed_at=paid_at,
        )
    before = snapshot_order(order, [a, b])
    detail = services.cancel_my_order(buyer, order.pk)
    after = snapshot_order(order, [a, b])
    order.refresh_from_db()
    assert order.status == "cancelled" and order.cancelled_at == NOW
    assert [StockUnit.objects.get(pk=u.pk).stock_quantity for u in (a, b)] == [5, 1]
    assert StockUnit.objects.get(pk=a.pk).updated_at == NOW
    assert _history(order)[-1] == (status, "cancelled", "buyer")
    assert after["history"][:-1] == before["history"] and len(after["history"]) == len(before["history"]) + 1
    _assert_unchanged_except(before, after, "status", "cancelled_at")
    assert order.paid_at == (paid_at if status == "paid" else None)  # 支払日時は変更しない
    expected_payments = [("approved", order.total_amount, "MOCK-Q1W2E3R4T5Y6U7I8", paid_at)] if status == "paid" else []
    keys = ("result", "amount", "transaction_ref", "processed_at")
    assert [tuple(p[key] for key in keys) for p in after["payments"]] == expected_payments  # 決済記録は変更しない
    assert (detail["can_pay"], detail["can_cancel"]) == (False, False)
    # 2回目は状態不正となり在庫を2回以上戻さない
    with pytest.raises(errors.BusinessError) as info:
        services.cancel_my_order(buyer, order.pk)
    assert info.value.code == "E-034-04" and info.value.values["current_status"] == "cancelled"
    assert [StockUnit.objects.get(pk=u.pk).stock_quantity for u in (a, b)] == [5, 1]
    assert len(_history(order)) == 2


# trace: FR-034
@pytest.mark.parametrize("status", ["shipped", "delivered", "cancelled"])
def test_cancel_my_order_invalid_status_keeps_stock(buyer, catalog, make_order, status):
    unit = catalog.stock_unit(stock=3)
    order = make_order(buyer, [(unit, 2)], status=status)
    before = snapshot_order(order, [unit])
    with pytest.raises(errors.BusinessError) as info:
        services.cancel_my_order(buyer, order.pk)
    assert info.value.code == "E-034-04" and info.value.reason == "invalid_status"
    assert StockUnit.objects.get(pk=unit.pk).stock_quantity == 3
    # 異常終了：注文の状態・キャンセル日時、在庫数量、注文状態履歴、決済記録は処理前から変化していない
    assert snapshot_order(order, [unit]) == before


# trace: FR-034, NFR-SC-03
def test_cancel_my_order_not_found_for_other_buyer(buyer, other_buyer, catalog, make_order):
    others = make_order(other_buyer, [(catalog.stock_unit(), 1)])
    for target in (others.pk, "x"):
        with pytest.raises(errors.NotFoundError) as info:
            services.cancel_my_order(buyer, target)
        assert info.value.code == "E-034-03"
    others.refresh_from_db()
    assert others.status == "accepted"


# trace: FR-034
def test_cancel_my_order_database_failure_rolls_back(buyer, catalog, make_order):
    unit = catalog.stock_unit(stock=1)
    order = make_order(buyer, [(unit, 2)])
    with mock.patch.object(OrderStatusHistory.objects, "create", side_effect=DatabaseError("x")):
        with pytest.raises(errors.SystemFailureError) as info:
            services.cancel_my_order(buyer, order.pk)
    assert info.value.code == "E-034-05"
    order.refresh_from_db()
    assert order.status == "accepted" and StockUnit.objects.get(pk=unit.pk).stock_quantity == 1


# trace: FR-034
@pytest.mark.parametrize(("model", "verb", "occurrence", "done_before_fault"), CANCEL_FAULTS)
def test_cancel_my_order_database_failure_at_each_step_rolls_back_everything(
    buyer, catalog, make_order, fail_sql, freeze, model, verb, occurrence, done_before_fault
):
    """E-034-05：手順5〜7 のどこで障害が起きても、状態・キャンセル日時・在庫数量・注文状態履歴・決済記録は処理前のまま。

    （6.19.6 異常終了）
    """
    freeze(NOW)
    a = catalog.stock_unit(stock=2)
    b = catalog.stock_unit(stock=0)
    order = make_order(buyer, [(a, 3), (b, 1)], status="paid")
    PaymentRecord.objects.create(order=order, result="approved", amount=1, transaction_ref="MOCK-X", processed_at=NOW)
    before = snapshot_order(order, [a, b])
    with fail_sql(model, verb, occurrence) as fault:
        with pytest.raises(errors.SystemFailureError) as info:
            services.cancel_my_order(buyer, order.pk)
    assert info.value.code == "E-034-05" and fault.injected
    assert fault.executed == done_before_fault  # 障害の前に行われた更新（在庫戻しを含む）も取り消されている
    assert snapshot_order(order, [a, b]) == before


# trace: FR-045
def test_admin_cancel_accepted_order_returns_stock_and_keeps_amounts(admin, buyer, catalog, make_order, freeze):
    """AC-UC-012-001：注文受付（税抜2,500円×2、在庫数量8、決済記録0件）を管理者がキャンセルすると在庫数量10。

    状態履歴は2件（2件目 注文受付→キャンセル済・実行者 管理者）、決済記録0件、
    各金額・明細・配送先は変化しない（6.25.6）。
    """
    freeze(NOW)
    mug = catalog.stock_unit(price=2500, stock=8)
    order = make_order(buyer, [(mug, 2)])
    before = snapshot_order(order, [mug])
    amounts = ("subtotal", "shipping_fee", "tax_amount", "total_amount")
    assert [before["order"][key] for key in amounts] == [5000, 0, 500, 5500]
    detail = services.admin_cancel_order(admin, order.pk)
    after = snapshot_order(order, [mug])
    assert after["stock"] == [(mug.pk, 10, NOW)]
    assert (after["order"]["status"], after["order"]["cancelled_at"]) == ("cancelled", NOW)
    assert after["order"]["paid_at"] is None
    assert after["order"]["ordered_at"] == before["order"]["ordered_at"]
    keys = ("from_status", "to_status", "changed_at", "actor_id", "actor_user_type")
    history = [tuple(h[key] for key in keys) for h in after["history"]]
    assert history == [
        (None, "accepted", before["history"][0]["changed_at"], buyer.pk, "buyer"),
        ("accepted", "cancelled", NOW, admin.pk, "admin"),
    ]
    assert after["payments"] == [] and detail["payments"] == []
    for key in ("subtotal", "discount_amount", "discounted_subtotal", "shipping_fee", "tax_amount", "total_amount"):
        assert after["order"][key] == before["order"][key]
    assert after["items"] == before["items"] and after["address"] == before["address"]
    assert (detail["status"], detail["status_label"], detail["cancelled_at"]) == ("cancelled", "キャンセル済", NOW)
    assert detail["buyer"]["email"] == buyer.email
    assert (detail["can_ship"], detail["can_deliver"], detail["can_cancel"]) == (False, False, False)


# trace: FR-045
def test_admin_cancel_invalid_status_keeps_order_stock_and_history(admin, buyer, other_buyer, catalog, make_order):
    """AC-UC-012-005：出荷済（履歴3件）・配達完了（履歴4件）・キャンセル済（履歴2件）はキャンセルできない。

    キャンセル済の注文のキャンセル日時は 2027-04-02 09:00:00。
    3件とも E-045-04（現在の状態を通知）。状態・各日時・注文状態履歴・決済記録は変化せず、
    在庫数量は MUG 8・PLATE 5 のまま（キャンセル済の注文の在庫を再び戻して11にしない）。
    """
    mug = catalog.stock_unit(stock=8)
    plate = catalog.stock_unit(stock=5)
    shipped = make_order(buyer, [(mug, 1)], status="shipped")
    delivered = make_order(other_buyer, [(plate, 2)], status="delivered")
    cancelled = make_order(buyer, [(mug, 3)], status="cancelled")
    Order.objects.filter(pk=cancelled.pk).update(cancelled_at=jst(2027, 4, 2, 9, 0, 0))
    transitions = {
        shipped: [("accepted", "paid", buyer), ("paid", "shipped", admin)],
        delivered: [("accepted", "paid", other_buyer), ("paid", "shipped", admin), ("shipped", "delivered", admin)],
        cancelled: [("accepted", "cancelled", buyer)],
    }
    for order, steps in transitions.items():
        for from_status, to_status, actor in steps:
            OrderStatusHistory.objects.create(
                order=order,
                from_status=from_status,
                to_status=to_status,
                changed_at=jst(2027, 4, 2, 9, 0, 0),
                actor=actor,
                actor_user_type=actor.user_type,
            )
    units = [mug, plate]
    cases = ((shipped, "shipped", 3), (delivered, "delivered", 4), (cancelled, "cancelled", 2))
    for order, status, history_count in cases:
        before = snapshot_order(order, units)
        assert len(before["history"]) == history_count
        with pytest.raises(errors.BusinessError) as info:
            services.admin_cancel_order(admin, order.pk)
        label = STATUS_LABELS[status]
        assert info.value.code == "E-045-04" and info.value.reason == "invalid_status"
        assert info.value.values == {"current_status": status, "current_status_label": label}
        assert info.value.message == f"この注文はキャンセルできません（現在の状態：{label}）。"
        assert snapshot_order(order, units) == before
    assert [StockUnit.objects.get(pk=u.pk).stock_quantity for u in units] == [8, 5]
    assert Order.objects.get(pk=cancelled.pk).cancelled_at == jst(2027, 4, 2, 9, 0, 0)
    assert [OrderStatusHistory.objects.filter(order=o).count() for o in (shipped, delivered, cancelled)] == [3, 4, 2]


# trace: FR-045
@pytest.mark.parametrize("status", ["accepted", "paid"])
def test_admin_cancel_resend_is_invalid_status_and_returns_stock_once(
    admin, buyer, catalog, make_order, freeze, status
):
    """6.25 二重実行防止：同一内容の再送信は E-045-04（現在の状態＝キャンセル済）。

    在庫数量を2回以上戻さない（注文状態履歴は1件だけ増える）。
    """
    freeze(NOW)
    a = catalog.stock_unit(stock=5)
    b = catalog.stock_unit(stock=0)
    order = make_order(buyer, [(a, 3), (b, 2)], status=status)
    before = snapshot_order(order, [a, b])
    services.admin_cancel_order(admin, order.pk)
    after_first = snapshot_order(order, [a, b])
    assert after_first["stock"] == [(a.pk, 8, NOW), (b.pk, 2, NOW)]
    assert len(after_first["history"]) == 2
    _assert_unchanged_except(before, after_first, "status", "cancelled_at")  # 注文日時・支払日時は変更しない
    freeze(LATER)
    with pytest.raises(errors.BusinessError) as info:
        services.admin_cancel_order(admin, order.pk)
    assert info.value.code == "E-045-04"
    assert info.value.values == {"current_status": "cancelled", "current_status_label": "キャンセル済"}
    after_second = snapshot_order(order, [a, b])
    assert after_second == after_first  # 在庫数量8・2のまま、キャンセル日時は1回目のまま、履歴は2件のまま
    with pytest.raises(errors.BusinessError):
        services.cancel_my_order(buyer, order.pk)  # 購入者経路からも在庫を再度戻さない
    assert snapshot_order(order, [a, b]) == after_first


# trace: FR-045
@pytest.mark.parametrize(("model", "verb", "occurrence", "done_before_fault"), CANCEL_FAULTS)
def test_admin_cancel_database_failure_at_each_step_rolls_back_everything(
    admin, buyer, catalog, make_order, fail_sql, freeze, model, verb, occurrence, done_before_fault
):
    """E-045-05：状態の変更・在庫戻し・注文状態履歴の記録をすべて取り消す（在庫戻しの後の障害でも在庫は処理前のまま）。"""
    freeze(NOW)
    a = catalog.stock_unit(stock=5)
    b = catalog.stock_unit(catalog.product(is_public=False), stock=0)
    order = make_order(buyer, [(a, 3), (b, 2)], status="paid")
    PaymentRecord.objects.create(order=order, result="approved", amount=1, transaction_ref="MOCK-Y", processed_at=NOW)
    before = snapshot_order(order, [a, b])
    with fail_sql(model, verb, occurrence) as fault:
        with pytest.raises(errors.SystemFailureError) as info:
            services.admin_cancel_order(admin, order.pk)
    assert info.value.code == "E-045-05" and fault.injected
    assert fault.executed == done_before_fault  # 障害の前に行われた在庫戻し等も取り消されている
    assert snapshot_order(order, [a, b]) == before
    # 取り消し後の再実行（自動再試行はしない）では在庫を1回だけ戻す
    services.admin_cancel_order(admin, order.pk)
    assert [StockUnit.objects.get(pk=u.pk).stock_quantity for u in (a, b)] == [8, 2]
    after = snapshot_order(order, [a, b])
    assert len(after["history"]) == 2
    _assert_unchanged_except(before, after, "status", "cancelled_at")  # 支払日時・承認の決済記録は処理前のまま


# trace: FR-045
def test_admin_cancel_any_buyers_order_returns_stock_regardless_of_visibility(
    buyer, admin, catalog, make_order, freeze
):
    """6.25.4 手順6 の例：A 3個・B 2個、処理前 A 5・B 0 → A 8・B 2（非公開の商品も戻す）。

    6.25.4 手順5・手順8、6.25.6 正常終了：注文日時・支払日時、決済記録の件数・内容は処理前と同じ。
    """
    freeze(NOW)
    a = catalog.stock_unit(stock=5)
    b = catalog.stock_unit(catalog.product(is_public=False), stock=0)
    order = make_order(buyer, [(a, 3), (b, 2)], status="paid")
    PaymentRecord.objects.create(
        order=order,
        result="approved",
        amount=order.total_amount,
        transaction_ref="MOCK-A1B2C3D4E5F6G7H8",
        processed_at=order.paid_at,
    )
    before = snapshot_order(order, [a, b])
    detail = services.admin_cancel_order(admin, str(order.pk))
    assert [StockUnit.objects.get(pk=u.pk).stock_quantity for u in (a, b)] == [8, 2]
    history = OrderStatusHistory.objects.filter(order=order).order_by("pk").last()
    assert (history.from_status, history.to_status, history.actor_id, history.actor_user_type) == (
        "paid",
        "cancelled",
        admin.pk,
        "admin",
    )
    assert detail["buyer"] == {"user_id": buyer.pk, "email": buyer.email, "name": buyer.name}
    assert detail["status_history"][-1]["actor_user_id"] == admin.pk
    after = snapshot_order(order, [a, b])
    assert (after["order"]["status"], after["order"]["cancelled_at"]) == ("cancelled", NOW)
    assert after["order"]["paid_at"] == before["order"]["paid_at"] != NOW  # 支払日時は変更しない
    _assert_unchanged_except(before, after, "status", "cancelled_at")


# trace: FR-045
def test_admin_cancel_paid_order_keeps_paid_at_and_payment_record(admin, other_buyer, catalog, make_order, freeze):
    """AC-UC-012-002：支払済（支払日時 2027-04-01 11:05:00、PLATE 税抜1,850円×3、合計6,105円、在庫数量5）の注文を
    管理者がキャンセルする。

    状態 キャンセル済・キャンセル日時記録、支払日時は 2027-04-01 11:05:00 のまま、状態履歴3件
    （3件目 支払済→キャンセル済・実行者 管理者）、在庫数量8。決済記録は1件のままで、承認・6,105円・
    MOCK-Q1W2E3R4T5Y6U7I8・2027-04-01 11:05:00 から変化しない（追加・変更・削除されない）。
    """
    freeze(NOW)
    paid_at = jst(2027, 4, 1, 11, 5, 0)
    plate = catalog.stock_unit(price=1850, stock=5)
    order = make_order(other_buyer, [(plate, 3)], status="paid", ordered_at=jst(2027, 4, 1, 11, 0, 0))
    Order.objects.filter(pk=order.pk).update(paid_at=paid_at)
    OrderStatusHistory.objects.create(
        order=order,
        from_status="accepted",
        to_status="paid",
        changed_at=paid_at,
        actor=other_buyer,
        actor_user_type="buyer",
    )
    PaymentRecord.objects.create(
        order=order, result="approved", amount=6105, transaction_ref="MOCK-Q1W2E3R4T5Y6U7I8", processed_at=paid_at
    )
    before = snapshot_order(order, [plate])
    amounts = ("subtotal", "shipping_fee", "tax_amount", "total_amount")
    assert [before["order"][key] for key in amounts] == [5550, 0, 555, 6105]
    assert len(before["history"]) == 2

    detail = services.admin_cancel_order(admin, order.pk)

    after = snapshot_order(order, [plate])
    assert (after["order"]["status"], after["order"]["cancelled_at"]) == ("cancelled", NOW)
    assert after["order"]["paid_at"] == paid_at
    assert after["stock"] == [(plate.pk, 8, NOW)]
    keys = ("from_status", "to_status", "changed_at", "actor_id", "actor_user_type")
    assert len(after["history"]) == 3 and after["history"][:2] == before["history"]
    assert tuple(after["history"][2][key] for key in keys) == ("paid", "cancelled", NOW, admin.pk, "admin")
    payment_keys = ("result", "amount", "transaction_ref", "processed_at")
    assert [tuple(p[key] for key in payment_keys) for p in after["payments"]] == [
        ("approved", 6105, "MOCK-Q1W2E3R4T5Y6U7I8", paid_at)
    ]
    assert after["payments"] == before["payments"]  # 全項目（識別子を含む）が処理前と同じ
    _assert_unchanged_except(before, after, "status", "cancelled_at")
    # 結果として示す注文詳細（管理者）の決済記録・支払日時・状態履歴
    assert [(p["result"], p["amount"], p["transaction_ref"], p["processed_at"]) for p in detail["payments"]] == [
        ("approved", 6105, "MOCK-Q1W2E3R4T5Y6U7I8", paid_at)
    ]
    assert (detail["status"], detail["paid_at"], detail["cancelled_at"]) == ("cancelled", paid_at, NOW)
    assert len(detail["status_history"]) == 3
    assert (detail["status_history"][-1]["from_status"], detail["status_history"][-1]["actor_user_id"]) == (
        "paid",
        admin.pk,
    )


# trace: FR-045
def test_admin_cancel_errors(admin, buyer, catalog, make_order):
    unit = catalog.stock_unit(stock=4)
    shipped = make_order(buyer, [(unit, 1)], status="shipped")
    before = snapshot_order(shipped, [unit])
    with pytest.raises(errors.BusinessError) as info:
        services.admin_cancel_order(admin, shipped.pk)
    assert info.value.code == "E-045-04" and info.value.values["current_status_label"] == "出荷済"
    assert snapshot_order(shipped, [unit]) == before  # 在庫数量を戻さない
    with pytest.raises(errors.NotFoundError) as info:
        services.admin_cancel_order(admin, "zz")
    assert info.value.code == "E-045-03"
    accepted = make_order(buyer, [(unit, 1)])
    before = snapshot_order(accepted, [unit])
    with mock.patch.object(OrderStatusHistory.objects, "create", side_effect=DatabaseError("x")):
        with pytest.raises(errors.SystemFailureError) as info:
            services.admin_cancel_order(admin, accepted.pk)
    assert info.value.code == "E-045-05"
    assert snapshot_order(accepted, [unit]) == before  # 在庫戻しの後の障害でも状態・在庫・履歴は処理前のまま


# ---------------------------------------------------------------------------
# FR-043 出荷登録・FR-044 配達完了登録
# ---------------------------------------------------------------------------


# trace: FR-043
@pytest.mark.parametrize(("raw", "stored"), [(None, None), ("  ", None), (" Ab-12 ", "Ab-12"), ("A" * 30, "A" * 30)])
def test_ship_order_records_tracking_number_as_entered(admin, buyer, catalog, make_order, freeze, raw, stored):
    """6.23.6 正常終了：注文日時・支払日時は処理前と同じ、配達完了日時・キャンセル日時は「なし」。

    在庫数量と決済記録は処理前と同じ。
    """
    freeze(NOW)
    unit = catalog.stock_unit(stock=7)
    order = make_order(buyer, [(unit, 1)], status="paid")
    PaymentRecord.objects.create(
        order=order,
        result="approved",
        amount=order.total_amount,
        transaction_ref="MOCK-S1S2S3S4S5S6S7S8",
        processed_at=order.paid_at,
    )
    paid_at = order.paid_at
    before = snapshot_order(order, [unit])
    detail = services.ship_order(admin, order.pk, raw)
    order.refresh_from_db()
    assert (order.status, order.shipped_at, order.tracking_number) == ("shipped", NOW, stored)
    assert order.paid_at == paid_at and order.delivered_at is None and order.cancelled_at is None
    assert _history(order)[-1] == ("paid", "shipped", "admin")
    assert StockUnit.objects.get(pk=unit.pk).stock_quantity == 7
    after = snapshot_order(order, [unit])
    assert after["stock"] == before["stock"]  # 在庫単位の在庫数量（更新日時も）は更新しない
    _assert_unchanged_except(before, after, "status", "shipped_at", "tracking_number")
    assert detail["tracking_number"] == stored and detail["can_deliver"] is True


# trace: FR-043, NFR-SC-04
@pytest.mark.parametrize("raw", ["A" * 31, "ab_12", "伝票1", "a b", 123, "a\x00"])
def test_ship_order_invalid_tracking_number_is_input_error_first(admin, raw):
    with pytest.raises(errors.InputError) as info:
        services.ship_order(admin, "999999", raw)
    assert info.value.code == "E-043-03" and _fields(info) == {("tracking_number", "invalid_format")}


# trace: FR-043
@pytest.mark.parametrize("status", ["accepted", "shipped", "delivered", "cancelled"])
def test_ship_order_requires_paid_status(admin, buyer, catalog, make_order, status):
    unit = catalog.stock_unit(stock=6)
    order = make_order(buyer, [(unit, 1)], status=status)
    before = snapshot_order(order, [unit])
    with pytest.raises(errors.BusinessError) as info:
        services.ship_order(admin, order.pk, "T-1")
    assert info.value.code == "E-043-05" and info.value.values["current_status"] == status
    assert info.value.message == f"この注文は出荷登録できません（現在の状態：{STATUS_LABELS[status]}）。"
    order.refresh_from_db()
    assert order.status == status and order.tracking_number is None
    # 異常終了：状態・各日時・配送伝票番号、在庫数量、決済記録、注文状態履歴は処理前から変化していない
    assert snapshot_order(order, [unit]) == before


# trace: FR-043
def test_ship_order_resend_keeps_first_shipment(admin, buyer, catalog, make_order, freeze):
    """6.23 二重実行防止：再送信は E-043-05（現在の状態＝出荷済）。

    1回目の出荷日時・配送伝票番号・注文状態履歴を維持する（注文状態履歴は1件だけ増える）。
    """
    freeze(NOW)
    unit = catalog.stock_unit(stock=3)
    order = make_order(buyer, [(unit, 1)], status="paid")
    services.ship_order(admin, order.pk, "T-1")
    after_first = snapshot_order(order, [unit])
    assert (after_first["order"]["shipped_at"], after_first["order"]["tracking_number"]) == (NOW, "T-1")
    assert len(after_first["history"]) == 2
    freeze(LATER)
    with pytest.raises(errors.BusinessError) as info:
        services.ship_order(admin, order.pk, "T-2")
    assert info.value.code == "E-043-05" and info.value.values["current_status"] == "shipped"
    assert snapshot_order(order, [unit]) == after_first


# trace: FR-043
def test_ship_order_not_found_and_database_failure(admin, buyer, catalog, make_order):
    with pytest.raises(errors.NotFoundError) as info:
        services.ship_order(admin, "-1", None)
    assert info.value.code == "E-043-04"
    order = make_order(buyer, [(catalog.stock_unit(), 1)], status="paid")
    with mock.patch.object(OrderStatusHistory.objects, "create", side_effect=DatabaseError("x")):
        with pytest.raises(errors.SystemFailureError) as info:
            services.ship_order(admin, order.pk, "T-1")
    assert info.value.code == "E-043-06"
    order.refresh_from_db()
    assert order.status == "paid" and order.tracking_number is None


# trace: FR-043
@pytest.mark.parametrize(("model", "verb", "done_before_fault"), TRANSITION_FAULTS)
def test_ship_order_database_failure_at_each_step_rolls_back_everything(
    admin, buyer, catalog, make_order, fail_sql, freeze, model, verb, done_before_fault
):
    """E-043-06：当該操作によるデータ変更をすべて取り消す（状態・出荷日時・配送伝票番号・履歴・在庫・決済記録は処理前のまま）。"""
    freeze(NOW)
    unit = catalog.stock_unit(stock=7)
    order = make_order(buyer, [(unit, 2)], status="paid")
    PaymentRecord.objects.create(order=order, result="approved", amount=1, transaction_ref="MOCK-Z", processed_at=NOW)
    before = snapshot_order(order, [unit])
    with fail_sql(model, verb) as fault:
        with pytest.raises(errors.SystemFailureError) as info:
            services.ship_order(admin, order.pk, "T-9")
    assert info.value.code == "E-043-06" and fault.injected
    assert fault.executed == done_before_fault
    assert snapshot_order(order, [unit]) == before
    services.ship_order(admin, order.pk, "T-9")  # 取り消し後の再実行では履歴は1件だけ増える
    assert len(snapshot_order(order)["history"]) == 2


# trace: FR-044
def test_deliver_order_from_shipped_only_once(admin, buyer, catalog, make_order, freeze):
    """6.24.6 正常終了：注文日時・支払日時・出荷日時・配送伝票番号は処理前と同じ、キャンセル日時は「なし」、
    在庫数量と決済記録は処理前と同じ。"""
    freeze(NOW)
    unit = catalog.stock_unit(stock=6)
    order = make_order(buyer, [(unit, 1)], status="shipped")
    Order.objects.filter(pk=order.pk).update(tracking_number="T-77")
    PaymentRecord.objects.create(
        order=order,
        result="approved",
        amount=order.total_amount,
        transaction_ref="MOCK-D1D2D3D4D5D6D7D8",
        processed_at=order.paid_at,
    )
    before = snapshot_order(order, [unit])
    detail = services.deliver_order(admin, order.pk)
    order.refresh_from_db()
    assert order.status == "delivered" and order.delivered_at == NOW
    assert _history(order)[-1] == ("shipped", "delivered", "admin")
    assert (detail["can_ship"], detail["can_deliver"], detail["can_cancel"]) == (False, False, False)
    after_first = snapshot_order(order, [unit])
    assert after_first["order"]["cancelled_at"] is None and after_first["order"]["tracking_number"] == "T-77"
    assert after_first["stock"] == before["stock"]
    _assert_unchanged_except(before, after_first, "status", "delivered_at")
    freeze(LATER)
    with pytest.raises(errors.BusinessError) as info:
        services.deliver_order(admin, order.pk)  # 再送信は状態不正（現在の状態＝配達完了）
    assert info.value.code == "E-044-04" and info.value.values["current_status"] == "delivered"
    assert len(_history(order)) == 2
    assert snapshot_order(order, [unit]) == after_first  # 1回目の配達完了日時・注文状態履歴を維持


# trace: FR-044
def test_deliver_order_errors(admin, buyer, catalog, make_order):
    unit = catalog.stock_unit(stock=2)
    paid = make_order(buyer, [(unit, 1)], status="paid")
    with pytest.raises(errors.BusinessError) as info:
        services.deliver_order(admin, paid.pk)
    assert info.value.code == "E-044-04" and info.value.values["current_status"] == "paid"
    with pytest.raises(errors.NotFoundError) as info:
        services.deliver_order(admin, "abc")
    assert info.value.code == "E-044-03"
    shipped = make_order(buyer, [(unit, 1)], status="shipped")
    before = snapshot_order(shipped, [unit])
    with mock.patch.object(OrderStatusHistory.objects, "create", side_effect=DatabaseError("x")):
        with pytest.raises(errors.SystemFailureError) as info:
            services.deliver_order(admin, shipped.pk)
    assert info.value.code == "E-044-05"
    assert snapshot_order(shipped, [unit]) == before  # 状態は出荷済・配達完了日時は未設定・履歴の件数は処理前のまま


# trace: FR-044
@pytest.mark.parametrize("status", ["accepted", "paid", "delivered", "cancelled"])
def test_deliver_order_invalid_status_keeps_order(admin, buyer, catalog, make_order, status):
    """E-044-04：出荷済でない注文。状態・各日時・配送伝票番号、在庫数量、決済記録、注文状態履歴を変更しない。"""
    unit = catalog.stock_unit(stock=4)
    order = make_order(buyer, [(unit, 1)], status=status)
    before = snapshot_order(order, [unit])
    with pytest.raises(errors.BusinessError) as info:
        services.deliver_order(admin, order.pk)
    assert info.value.code == "E-044-04" and info.value.reason == "invalid_status"
    assert info.value.values == {"current_status": status, "current_status_label": STATUS_LABELS[status]}
    assert info.value.message == f"この注文は配達完了登録できません（現在の状態：{STATUS_LABELS[status]}）。"
    assert snapshot_order(order, [unit]) == before


# trace: FR-044
@pytest.mark.parametrize(("model", "verb", "done_before_fault"), TRANSITION_FAULTS)
def test_deliver_order_database_failure_at_each_step_rolls_back_everything(
    admin, buyer, catalog, make_order, fail_sql, freeze, model, verb, done_before_fault
):
    """E-044-05：当該操作によるデータ変更をすべて取り消す（状態は出荷済、配達完了日時は未設定、履歴の件数は処理前のまま）。"""
    freeze(NOW)
    unit = catalog.stock_unit(stock=7)
    order = make_order(buyer, [(unit, 1)], status="shipped")
    Order.objects.filter(pk=order.pk).update(tracking_number="T-5")
    before = snapshot_order(order, [unit])
    with fail_sql(model, verb) as fault:
        with pytest.raises(errors.SystemFailureError) as info:
            services.deliver_order(admin, order.pk)
    assert info.value.code == "E-044-05" and fault.injected
    assert fault.executed == done_before_fault
    after = snapshot_order(order, [unit])
    assert after == before
    assert (after["order"]["status"], after["order"]["delivered_at"]) == ("shipped", None)
    services.deliver_order(admin, order.pk)  # 取り消し後の再実行では履歴は1件だけ増える
    assert len(snapshot_order(order)["history"]) == 2


# ---------------------------------------------------------------------------
# FR-041 注文一覧検索（管理者）・FR-042 注文詳細照会（管理者）
# ---------------------------------------------------------------------------


# trace: FR-041
def test_admin_list_orders_without_conditions_returns_all_buyers(buyer, other_buyer, catalog, make_order):
    unit = catalog.stock_unit()
    first = make_order(buyer, [(unit, 2)], ordered_at=jst(2027, 4, 1))
    second = make_order(other_buyer, [(unit, 1)], ordered_at=jst(2027, 4, 2), status="cancelled")
    result = services.admin_list_orders(None, None, None, None, None, None)
    assert [i["order_id"] for i in result["items"]] == [second.pk, first.pk]
    assert result["items"][1] == {
        "order_id": first.pk,
        "order_number": first.order_number,
        "ordered_at": jst(2027, 4, 1),
        "buyer_email": buyer.email,
        "buyer_name": buyer.name,
        "status": "accepted",
        "status_label": "注文受付",
        "total_amount": first.total_amount,
        "total_quantity": 2,
    }


# trace: FR-041
def test_admin_list_orders_filters(buyer, make_user, catalog, make_order):
    unit = catalog.stock_unit()
    hanako = make_user("Hanako.Sato@Example.test")
    a = make_order(buyer, [(unit, 1)], ordered_at=jst(2027, 4, 29, 23, 59, 59), status="paid")
    b = make_order(hanako, [(unit, 1)], ordered_at=jst(2027, 4, 30, 0, 0, 0), status="shipped")
    c = make_order(hanako, [(unit, 1)], ordered_at=jst(2027, 4, 30, 23, 59, 59), status="accepted")
    d = make_order(buyer, [(unit, 1)], ordered_at=jst(2027, 5, 1, 0, 0, 0), status="paid")

    def ids(**kwargs):
        params = {"order_number": None, "statuses": None, "date_from": None, "date_to": None, "email": None}
        params.update(kwargs)
        result = services.admin_list_orders(
            params["order_number"], params["statuses"], params["date_from"], params["date_to"], params["email"], None
        )
        return {i["order_id"] for i in result["items"]}

    assert ids(order_number=f" {c.order_number} ") == {c.pk}
    assert ids(statuses=["paid", "shipped", "paid", "", None]) == {a.pk, b.pk, d.pk}
    assert ids(date_from="2027-04-30", date_to="2027-04-30") == {b.pk, c.pk}  # 同じ日は可・両端を含む
    assert ids(date_from="2027-04-30") == {b.pk, c.pk, d.pk}
    assert ids(date_to="2027-04-30") == {a.pk, b.pk, c.pk}
    assert ids(email="SATO@example") == {b.pk, c.pk}  # 部分一致・大文字小文字を区別しない
    assert ids(email="  ", date_from=" ", order_number="") == {a.pk, b.pk, c.pk, d.pk}
    assert ids(statuses=["paid"], email="sato") == set()
    assert ids(date_to="9999-12-31") == {a.pk, b.pk, c.pk, d.pk}


# trace: FR-041, NFR-SC-04
@pytest.mark.parametrize(
    ("args", "expected"),
    [
        (("PO-1234567", None, None, None, None, None), {("order_number", "invalid_format")}),
        (("po-12345678", None, None, None, None, None), {("order_number", "invalid_format")}),
        ((5, None, None, None, None, None), {("order_number", "invalid_type")}),
        ((None, ["paid", "unknown", "bad"], None, None, None, None), {("status", "invalid_choice")}),
        ((None, None, "2027-02-30", None, None, None), {("order_date_from", "invalid_format")}),
        ((None, None, None, "2027/04/01", None, None), {("order_date_to", "invalid_format")}),
        ((None, None, 20270401, None, None, None), {("order_date_from", "invalid_format")}),
        ((None, None, "2027-04-10", "2027-04-09", None, None), {("order_date_from", "invalid_range")}),
        ((None, None, None, None, "a" * 255, None), {("buyer_email", "invalid_length")}),
        ((None, None, None, None, 1, None), {("buyer_email", "invalid_type")}),
        ((None, None, None, None, "a\x00", None), {("buyer_email", "invalid_format")}),
        ((None, None, None, None, None, "0"), {("page", "out_of_range")}),
    ],
)
def test_admin_list_orders_input_errors(args, expected):
    with pytest.raises(errors.InputError) as info:
        services.admin_list_orders(*args)
    assert info.value.code == "E-041-03" and info.value.message == errors.MSG_SEARCH_CONDITION_ERROR
    assert _fields(info) == expected


# trace: FR-041
def test_admin_list_orders_boundary_accepts_254_char_email_and_valid_number():
    result = services.admin_list_orders("PO-00000001", ["accepted"], "2027-04-10", "2027-04-10", "a" * 254, "1")
    assert result["items"] == [] and result["total_count"] == 0 and result["total_pages"] == 0


# trace: FR-041
def test_admin_list_orders_pagination(buyer, catalog, make_order):
    unit = catalog.stock_unit()
    for _ in range(21):
        make_order(buyer, [(unit, 1)])
    page2 = services.admin_list_orders(None, None, None, None, None, "2")
    assert len(page2["items"]) == 1 and page2["total_count"] == 21 and page2["total_pages"] == 2


# trace: FR-042
def test_admin_get_order_includes_buyer_payments_and_actor_ids(admin, buyer, catalog, make_order):
    order = make_order(buyer, [(catalog.stock_unit(), 1)])
    PaymentRecord.objects.create(
        order=order, result="declined", amount=order.total_amount, processed_at=jst(2027, 4, 10, 12, 5)
    )
    PaymentRecord.objects.create(
        order=order, result="integration_error", amount=order.total_amount, processed_at=jst(2027, 4, 10, 12, 1)
    )
    detail = services.admin_get_order(str(order.pk))
    assert [p["result"] for p in detail["payments"]] == ["integration_error", "declined"]  # 処理日時の昇順
    assert detail["payments"][0] == {
        "result": "integration_error",
        "result_label": "連携エラー",
        "amount": order.total_amount,
        "transaction_ref": None,
        "processed_at": jst(2027, 4, 10, 12, 1),
    }
    assert detail["buyer"]["email"] == buyer.email
    assert detail["status_history"][0]["actor_user_id"] == buyer.pk
    for target in ("abc", 0, 99999999):
        with pytest.raises(errors.NotFoundError) as info:
            services.admin_get_order(target)
        assert info.value.code == "E-042-03"


# trace: FR-042
def test_admin_detail_with_coupon_shows_confirmed_coupon_content(buyer, catalog, make_order, make_coupon):
    order = make_order(buyer, [(catalog.stock_unit(), 1)])
    coupon = make_coupon("FIX", discount_type="fixed_amount", discount_value=300)
    Order.objects.filter(pk=order.pk).update(
        coupon=coupon, coupon_code="FIX", discount_type="fixed_amount", discount_value=300
    )
    coupon.discount_value = 999
    coupon.save()
    detail = services.admin_get_order(order.pk)
    assert detail["coupon"] == {
        "coupon_code": "FIX",
        "discount_type": "fixed_amount",
        "discount_type_label": "定額",
        "discount_value": 300,
    }
