# trace: FR-030, FR-031, FR-032, FR-033, FR-034, FR-041, FR-042, FR-043, FR-044, FR-045
# trace: NFR-SC-03, NFR-SC-23, ADDR-003, ADDR-009
"""注文（FR-030〜FR-034）・管理者の注文操作（FR-041〜FR-045）の単体テスト。

期待結果は機能要件 6.15（注文確定）・6.16（支払）・6.17（注文履歴）・6.18（注文詳細）・
6.19（キャンセル）・6.21（注文一覧検索）・6.23〜6.25（出荷・配達完了・管理者キャンセル）、
提供済みAPI契約 6.2／6.3、ADDR-003（行ロックと状態の再判定）、ADDR-009（決済要求は
トランザクションの外で1回）から導出する。
"""

from __future__ import annotations

import datetime as dt

import pytest
from _helpers import make_coupon, make_item, make_stock_unit, make_user, shipping_input
from accounts.models import ROLE_ADMIN, ROLE_BUYER
from carts import services as cart_services
from carts.models import DISCOUNT_PERCENTAGE, Cart, CartLine
from common import timeutils
from common.exceptions import (
    CartEmpty,
    CouponExpired,
    CouponMinSpendNotMet,
    CouponNotYetValid,
    InsufficientStock,
    InvalidStatusTransition,
    ItemNotAvailable,
    NotFoundError,
    PaymentDeclined,
    PaymentServiceError,
    QuantityLimitExceeded,
    ValidationFailed,
)
from orders import services
from orders.models import (
    PAYMENT_APPROVED,
    PAYMENT_DECLINED,
    PAYMENT_ERROR,
    STATUS_CANCELLED,
    STATUS_CREATED,
    STATUS_DELIVERED,
    STATUS_PAID,
    STATUS_SHIPPED,
    PaymentRecord,
    PurchaseOrder,
)
from payments import services as payment_services
from payments.gateway import PaymentGatewayError

pytestmark = pytest.mark.django_db


# trace: FR-030
def prepare_cart(user, *, price: int = 3000, quantity: int = 2, stock: int = 10, coupon=None):
    """カートに明細1行を用意する（テスト補助）。"""
    unit = make_stock_unit(make_item(name="試験商品"), price=price, quantity=stock, variant_name="青")
    cart_services.add_line(user, {"stock_unit_id": unit.pk, "quantity": quantity})
    if coupon is not None:
        cart = Cart.objects.get(user=user, status="open")
        cart.coupon = coupon
        cart.save(update_fields=["coupon"])
    return unit


# trace: FR-030
def test_validate_shipping_input_normalizes_values():
    """FR-030 6.15.3：郵便番号・電話番号はハイフンを除いて登録する。"""
    normalized = services.validate_shipping_input(
        shipping_input(postal_code=" 123-4567 ", phone_number="03-1234-5678", recipient_name="  受取 太郎 ")
    )

    assert normalized["postal_code"] == "1234567"
    assert normalized["phone_number"] == "0312345678"
    assert normalized["recipient_name"] == "受取 太郎"


# trace: FR-030
def test_validate_shipping_input_reports_every_missing_field():
    """E-030-03／CMN-16：条件を満たさない全項目を1回で通知する。"""
    with pytest.raises(ValidationFailed) as error:
        services.validate_shipping_input({})

    assert {detail["field"] for detail in error.value.details} == {
        "recipient_name",
        "postal_code",
        "prefecture_code",
        "address_line1",
        "phone_number",
    }


# trace: FR-030
@pytest.mark.parametrize(
    ("override", "expected_field"),
    [
        ({"recipient_name": "あ" * 51}, "recipient_name"),
        ({"postal_code": "12345"}, "postal_code"),
        ({"postal_code": "1234-567"}, "postal_code"),
        ({"prefecture_code": "48"}, "prefecture_code"),
        ({"prefecture_code": "00"}, "prefecture_code"),
        ({"address_line1": "あ" * 101}, "address_line1"),
        ({"address_line2": "あ" * 101}, "address_line2"),
        ({"phone_number": "090123456"}, "phone_number"),
        ({"phone_number": "090123456789"}, "phone_number"),
        ({"phone_number": "090-abcd-efgh"}, "phone_number"),
    ],
)
def test_validate_shipping_input_rejects_values_outside_conditions(override, expected_field):
    """FR-030 6.15.3：桁数・形式・都道府県コードの条件を満たさない値は入力エラーとする。"""
    with pytest.raises(ValidationFailed) as error:
        services.validate_shipping_input(shipping_input(**override))

    assert expected_field in [detail["field"] for detail in error.value.details]


# trace: FR-030
@pytest.mark.parametrize("prefecture_code", ["01", "13", "47"])
def test_validate_shipping_input_accepts_all_prefecture_codes(prefecture_code):
    """CD-06：都道府県コードは01〜47（境界値）。"""
    normalized = services.validate_shipping_input(shipping_input(prefecture_code=prefecture_code))

    assert normalized["prefecture_code"] == prefecture_code


# trace: FR-030
@pytest.mark.parametrize("phone_number", ["0312345678", "09012345678"])
def test_validate_shipping_input_accepts_ten_or_eleven_digits(phone_number):
    """FR-030 6.15.3：電話番号は数字10桁または11桁（境界値）。"""
    assert services.validate_shipping_input(shipping_input(phone_number=phone_number))


# trace: FR-030
def test_validate_shipping_input_allows_empty_address_line2():
    """住所2は任意項目とする。"""
    normalized = services.validate_shipping_input(shipping_input(address_line2=""))

    assert normalized["address_line2"] == ""


# trace: FR-030
def test_checkout_creates_order_with_fixed_amounts(buyer):
    """FR-030：注文を1件作成し、注文確定時点の金額を確定する。"""
    prepare_cart(buyer, price=3000, quantity=2, stock=10)

    order = services.checkout(buyer, shipping_input())

    assert order.status == STATUS_CREATED
    assert order.subtotal == 6000
    assert order.discount_amount == 0
    assert order.shipping_fee == 0
    assert order.tax_amount == 600
    assert order.total == 6600
    assert order.order_number.startswith("PO-")
    assert len(order.order_number) == 11


# trace: FR-030
def test_checkout_allocates_stock_and_converts_cart(buyer):
    """FR-030 事後条件：在庫数量を引き当て、カートを注文済にする。"""
    unit = prepare_cart(buyer, quantity=3, stock=10)

    services.checkout(buyer, shipping_input())

    unit.refresh_from_db()
    assert unit.quantity == 7
    assert Cart.objects.filter(user=buyer, status="converted").count() == 1
    assert Cart.objects.filter(user=buyer, status="open").count() == 0


# trace: FR-030
def test_checkout_snapshots_lines_and_shipping_address(buyer):
    """FR-030：注文明細は注文確定時点のスナップショットとし、配送先を1件登録する。"""
    unit = prepare_cart(buyer, price=3000, quantity=2)

    order = services.checkout(buyer, shipping_input())

    line = order.lines.get()
    assert line.sku == unit.sku
    assert line.item_name == unit.item.name
    assert line.variant_name == unit.variant_name
    assert line.unit_price == 3000
    assert line.quantity == 2
    assert line.line_amount == 6000
    assert order.shipping_address.postal_code == "1234567"
    assert order.shipping_address.prefecture_code == "13"


# trace: NFR-SC-23
def test_checkout_records_status_history(buyer):
    """CMN-26：注文確定時に注文状態履歴を1件記録する。"""
    prepare_cart(buyer)

    order = services.checkout(buyer, shipping_input())

    history = order.status_history.get()
    assert history.from_status is None
    assert history.to_status == STATUS_CREATED
    assert history.actor_user_id == buyer.pk
    assert history.actor_role == ROLE_BUYER


# trace: FR-030
def test_checkout_applies_coupon_and_keeps_snapshot(buyer):
    """FR-030：適用中クーポンの割引を反映し、クーポンの内容を注文へ記録する。"""
    coupon = make_coupon(code="ORDER-10", discount_type=DISCOUNT_PERCENTAGE, discount_value=10, min_spend=0)
    prepare_cart(buyer, price=5550, quantity=1, coupon=coupon)

    order = services.checkout(buyer, shipping_input())

    assert order.coupon_code == coupon.code
    assert order.coupon_discount_type == DISCOUNT_PERCENTAGE
    assert order.coupon_discount_value == 10
    assert order.discount_amount == 555
    assert order.total == 6044


# trace: FR-030
def test_checkout_records_ordered_at_as_confirmation_time(buyer, fixed_now):
    """FR-030 6.15.4 手順13／6.15.6：注文日時＝確定時刻とし、カート・状態履歴も同じ時刻で記録する。"""
    prepare_cart(buyer)
    at = fixed_now(dt.datetime(2026, 5, 1, 10, 30, 0, tzinfo=dt.UTC))

    order = services.checkout(buyer, shipping_input())

    cart = Cart.objects.get(user=buyer, status="converted")
    assert order.ordered_at == at
    assert order.paid_at is None
    assert order.shipped_at is None
    assert order.delivered_at is None
    assert order.cancelled_at is None
    assert order.status_history.get().changed_at == at
    assert cart.converted_at == at


# trace: FR-031
def test_pay_records_paid_at_as_processing_time(buyer, fixed_now):
    """FR-031 6.16.4 手順8／6.16.6：支払日時＝処理時刻とし、状態履歴の変更日時も支払日時と一致させる。"""
    prepare_cart(buyer)
    order = services.checkout(buyer, shipping_input())
    at = fixed_now(dt.datetime(2026, 5, 2, 9, 0, 0, tzinfo=dt.UTC))

    paid = services.pay(buyer, order.pk, {"mock_result": "approve"})

    history = paid.status_history.order_by("-id").first()
    assert paid.paid_at == at
    assert paid.ordered_at != at
    assert history.to_status == STATUS_PAID
    assert history.changed_at == at


# trace: FR-030
def test_checkout_rejects_empty_cart(buyer):
    """E-030-04：カートが空の場合は注文を確定しない。"""
    with pytest.raises(CartEmpty):
        services.checkout(buyer, shipping_input())

    assert PurchaseOrder.objects.count() == 0


# trace: FR-030
def test_checkout_rejects_cart_without_lines(buyer):
    """E-030-04：利用中カートに明細がない場合も空として扱う。"""
    cart_services.show_cart(buyer)

    with pytest.raises(CartEmpty):
        services.checkout(buyer, shipping_input())


# trace: FR-030
def test_checkout_rejects_non_public_item(buyer):
    """E-030-05：販売を終了した商品を含む場合は対象の在庫単位IDを通知する。"""
    unit = prepare_cart(buyer)
    unit.item.is_public = False
    unit.item.save(update_fields=["is_public"])

    with pytest.raises(ItemNotAvailable) as error:
        services.checkout(buyer, shipping_input())

    assert error.value.context == {"stock_unit_ids": [unit.pk]}
    assert PurchaseOrder.objects.count() == 0


# trace: FR-030
def test_checkout_rejects_insufficient_stock_with_all_shortages(buyer):
    """E-030-07：不足する全在庫単位を通知し、在庫数量を変更しない。"""
    first = prepare_cart(buyer, price=1000, quantity=3, stock=10)
    second = make_stock_unit(make_item(), price=1000, quantity=10, sku="SKU-SECOND")
    cart_services.add_line(buyer, {"stock_unit_id": second.pk, "quantity": 2})
    first.quantity = 1
    first.save(update_fields=["quantity"])
    second.quantity = 0
    second.save(update_fields=["quantity"])

    with pytest.raises(InsufficientStock) as error:
        services.checkout(buyer, shipping_input())

    shortages = {shortage["stock_unit_id"]: shortage for shortage in error.value.context["shortages"]}
    assert set(shortages) == {first.pk, second.pk}
    assert shortages[first.pk]["requested_quantity"] == 3
    assert shortages[first.pk]["available_quantity"] == 1
    first.refresh_from_db()
    assert first.quantity == 1


# trace: FR-030
def test_checkout_rejects_quantity_over_limit(buyer):
    """E-030-06：注文確定時も同一在庫単位の上限10を判定する。"""
    unit = prepare_cart(buyer, quantity=1, stock=30)
    CartLine.objects.filter(stock_unit=unit).update(quantity=11)

    with pytest.raises(QuantityLimitExceeded) as error:
        services.checkout(buyer, shipping_input())

    assert error.value.context["limit"] == 10
    assert error.value.context["current_quantity"] == 11


# trace: FR-030
def test_checkout_rejects_coupon_before_valid_period(buyer):
    """E-030-08：クーポンの有効期間開始前は注文を確定しない。"""
    now = timeutils.now()
    coupon = make_coupon(
        code="FUTURE-ORD", valid_from=now + dt.timedelta(days=1), valid_until=now + dt.timedelta(days=2)
    )
    prepare_cart(buyer, coupon=coupon)

    with pytest.raises(CouponNotYetValid):
        services.checkout(buyer, shipping_input())


# trace: FR-030
def test_checkout_rejects_expired_coupon(buyer):
    """E-030-09：クーポンの有効期間終了後は注文を確定しない。"""
    now = timeutils.now()
    coupon = make_coupon(
        code="PAST-ORD", valid_from=now - dt.timedelta(days=2), valid_until=now - dt.timedelta(days=1)
    )
    prepare_cart(buyer, coupon=coupon)

    with pytest.raises(CouponExpired):
        services.checkout(buyer, shipping_input())


# trace: FR-030
def test_checkout_rejects_coupon_below_minimum_spend(buyer):
    """E-030-10：小計が最低購入金額未満の場合は注文を確定しない。"""
    coupon = make_coupon(code="MINORD-1", min_spend=100000)
    prepare_cart(buyer, price=1000, quantity=1, coupon=coupon)

    with pytest.raises(CouponMinSpendNotMet) as error:
        services.checkout(buyer, shipping_input())

    assert error.value.context == {"min_spend": 100000, "subtotal": 1000}


# trace: FR-030
def test_checkout_rejects_invalid_shipping_input_before_allocating_stock(buyer):
    """E-030-03：入力エラーの場合は在庫数量・カートを変更しない。"""
    unit = prepare_cart(buyer, quantity=2, stock=10)

    with pytest.raises(ValidationFailed):
        services.checkout(buyer, shipping_input(postal_code=""))

    unit.refresh_from_db()
    assert unit.quantity == 10
    assert Cart.objects.filter(user=buyer, status="open").count() == 1


# trace: FR-030
def test_order_numbers_increase_in_order_of_confirmation(buyer):
    """FR-030：注文番号は確定の順に大きくなる（欠番は許容する）。"""
    prepare_cart(buyer)
    first = services.checkout(buyer, shipping_input())
    prepare_cart(buyer)
    second = services.checkout(buyer, shipping_input())

    assert second.order_number > first.order_number


# trace: FR-031
def test_pay_approves_and_marks_order_paid(buyer):
    """FR-031 手順8：承認時に決済記録・支払済への状態変更・履歴を記録する。"""
    prepare_cart(buyer)
    order = services.checkout(buyer, shipping_input())

    paid = services.pay(buyer, order.pk, {"mock_result": "approve"})

    assert paid.status == STATUS_PAID
    assert paid.paid_at is not None
    record = PaymentRecord.objects.get(purchase_order=order)
    assert record.result == PAYMENT_APPROVED
    assert record.amount == order.total
    assert record.transaction_ref.startswith("MOCK-")
    history = paid.status_history.order_by("pk").last()
    assert (history.from_status, history.to_status) == (STATUS_CREATED, STATUS_PAID)
    assert history.actor_role == ROLE_BUYER


# trace: FR-031
def test_pay_defaults_to_approve_when_mock_result_is_omitted(buyer):
    """FR-031 手順3：模擬決済指示の省略時は承認とする。"""
    prepare_cart(buyer)
    order = services.checkout(buyer, shipping_input())

    paid = services.pay(buyer, order.pk, {})

    assert paid.status == STATUS_PAID


# trace: FR-031
def test_pay_does_not_change_stock_quantity(buyer):
    """FR-031 事後条件：支払では在庫数量を変更しない。"""
    unit = prepare_cart(buyer, quantity=2, stock=10)
    order = services.checkout(buyer, shipping_input())
    unit.refresh_from_db()
    allocated = unit.quantity

    services.pay(buyer, order.pk, {"mock_result": "approve"})

    unit.refresh_from_db()
    assert unit.quantity == allocated == 8


# trace: FR-031
def test_pay_declined_keeps_order_created_and_records_payment(buyer):
    """FR-031 手順10：否認時は決済記録だけを残し、注文受付のままとする。"""
    prepare_cart(buyer)
    order = services.checkout(buyer, shipping_input())

    with pytest.raises(PaymentDeclined):
        services.pay(buyer, order.pk, {"mock_result": "decline"})

    order.refresh_from_db()
    assert order.status == STATUS_CREATED
    assert order.paid_at is None
    record = PaymentRecord.objects.get(purchase_order=order)
    assert record.result == PAYMENT_DECLINED
    assert record.transaction_ref is None
    assert order.status_history.count() == 1


# trace: FR-031
def test_pay_allows_retry_after_decline(buyer):
    """FR-031 手順10：否認後も同じ注文に再度支払える。"""
    prepare_cart(buyer)
    order = services.checkout(buyer, shipping_input())
    with pytest.raises(PaymentDeclined):
        services.pay(buyer, order.pk, {"mock_result": "decline"})

    paid = services.pay(buyer, order.pk, {"mock_result": "approve"})

    assert paid.status == STATUS_PAID
    assert PaymentRecord.objects.filter(purchase_order=order).count() == 2


# trace: FR-031, ADDR-009
def test_pay_records_link_error_without_retry(buyer, monkeypatch):
    """FR-031 手順11：連携エラー時は決済記録（連携エラー）を残し、自動再送しない。"""
    prepare_cart(buyer)
    order = services.checkout(buyer, shipping_input())
    calls = {"count": 0}

    def fail(order_number, amount, mock_result):
        calls["count"] += 1
        raise PaymentGatewayError("timeout")

    monkeypatch.setattr(payment_services, "authorize", fail)

    with pytest.raises(PaymentServiceError) as error:
        services.pay(buyer, order.pk, {"mock_result": "approve"})

    assert error.value.status_code == 502
    assert calls["count"] == 1
    record = PaymentRecord.objects.get(purchase_order=order)
    assert record.result == PAYMENT_ERROR
    order.refresh_from_db()
    assert order.status == STATUS_CREATED


# trace: FR-031
def test_pay_rejects_invalid_mock_result(buyer):
    """E-031-03：模擬決済指示が approve／decline と一致しない場合は入力エラーとする。"""
    prepare_cart(buyer)
    order = services.checkout(buyer, shipping_input())

    with pytest.raises(ValidationFailed) as error:
        services.pay(buyer, order.pk, {"mock_result": "APPROVE"})

    assert error.value.details[0]["field"] == "mock_result"
    assert PaymentRecord.objects.count() == 0


# trace: FR-031
def test_pay_rejects_order_that_is_not_created(buyer):
    """E-031-05：注文受付以外の状態では決済要求を送信しない。"""
    prepare_cart(buyer)
    order = services.checkout(buyer, shipping_input())
    services.pay(buyer, order.pk, {"mock_result": "approve"})

    with pytest.raises(InvalidStatusTransition) as error:
        services.pay(buyer, order.pk, {"mock_result": "approve"})

    assert error.value.context == {"current_status": STATUS_PAID}
    assert PaymentRecord.objects.filter(purchase_order=order).count() == 1


# trace: NFR-SC-03
def test_pay_rejects_other_buyers_order(buyer):
    """PRM-01：他の購入者の注文は対象なしとし、存在有無を明かさない。"""
    other = make_user(email="other-pay@example.test")
    prepare_cart(other)
    order = services.checkout(other, shipping_input())

    with pytest.raises(NotFoundError):
        services.pay(buyer, order.pk, {"mock_result": "approve"})


# trace: FR-032
def test_list_buyer_orders_returns_only_own_orders_in_descending_order(buyer):
    """FR-032：本人の注文のみを注文日時の降順で返す。"""
    other = make_user(email="other-list@example.test")
    prepare_cart(other)
    services.checkout(other, shipping_input())
    prepare_cart(buyer)
    first = services.checkout(buyer, shipping_input())
    prepare_cart(buyer)
    second = services.checkout(buyer, shipping_input())

    orders, meta = services.list_buyer_orders(buyer, {})

    assert [order.pk for order in orders] == [second.pk, first.pk]
    assert meta["total_count"] == 2
    assert meta["page_size"] == services.ORDER_PAGE_SIZE == 20


# trace: FR-032
def test_list_buyer_orders_rejects_invalid_page(buyer):
    """E-032-03：ページ番号が1未満・整数でない場合は入力エラーとする。"""
    with pytest.raises(ValidationFailed):
        services.list_buyer_orders(buyer, {"page": "0"})


# trace: FR-033
def test_get_buyer_order_returns_own_order(buyer):
    """FR-033：本人の注文詳細を取得する。"""
    prepare_cart(buyer)
    order = services.checkout(buyer, shipping_input())

    assert services.get_buyer_order(buyer, str(order.pk)).pk == order.pk


# trace: NFR-SC-03
@pytest.mark.parametrize("order_id", ["abc", 999999])
def test_find_buyer_order_rejects_unresolvable_identifier(buyer, order_id):
    """CMN-04：識別子として解釈できない値・該当なしは対象なしとする。"""
    with pytest.raises(NotFoundError):
        services.find_buyer_order(buyer, order_id)


# trace: FR-034
def test_cancel_by_buyer_restores_stock_and_records_history(buyer):
    """FR-034：注文受付の注文をキャンセルし、在庫数量を戻す。"""
    unit = prepare_cart(buyer, quantity=3, stock=10)
    order = services.checkout(buyer, shipping_input())

    cancelled = services.cancel_by_buyer(buyer, order.pk)

    unit.refresh_from_db()
    assert unit.quantity == 10
    assert cancelled.status == STATUS_CANCELLED
    assert cancelled.cancelled_at is not None
    history = cancelled.status_history.order_by("pk").last()
    assert (history.from_status, history.to_status) == (STATUS_CREATED, STATUS_CANCELLED)
    assert history.actor_role == ROLE_BUYER


# trace: FR-034
def test_cancel_by_buyer_allows_paid_order(buyer):
    """FR-034：支払済の注文もキャンセルできる（返金は運用で行う）。"""
    unit = prepare_cart(buyer, quantity=2, stock=10)
    order = services.checkout(buyer, shipping_input())
    services.pay(buyer, order.pk, {"mock_result": "approve"})

    cancelled = services.cancel_by_buyer(buyer, order.pk)

    unit.refresh_from_db()
    assert unit.quantity == 10
    assert cancelled.status == STATUS_CANCELLED
    assert cancelled.paid_at is not None


# trace: FR-034
def test_cancel_by_buyer_rejects_shipped_order(buyer, admin_user):
    """E-034-05：出荷済以降の注文はキャンセルできない。"""
    prepare_cart(buyer)
    order = services.checkout(buyer, shipping_input())
    services.pay(buyer, order.pk, {"mock_result": "approve"})
    services.ship(admin_user, order.pk, {})

    with pytest.raises(InvalidStatusTransition) as error:
        services.cancel_by_buyer(buyer, order.pk)

    assert error.value.context == {"current_status": STATUS_SHIPPED}


# trace: FR-045
def test_cancel_by_admin_records_admin_as_actor(buyer, admin_user):
    """FR-045：管理者は全購入者の注文をキャンセルでき、実行者区分は管理者とする。"""
    unit = prepare_cart(buyer, quantity=2, stock=10)
    order = services.checkout(buyer, shipping_input())

    cancelled = services.cancel_by_admin(admin_user, order.pk)

    unit.refresh_from_db()
    assert unit.quantity == 10
    history = cancelled.status_history.order_by("pk").last()
    assert history.actor_role == ROLE_ADMIN
    assert history.actor_user_id == admin_user.pk


# trace: FR-043
def test_ship_marks_paid_order_as_shipped(buyer, admin_user):
    """FR-043：支払済の注文を出荷済にし、配送伝票番号を記録する。"""
    prepare_cart(buyer)
    order = services.checkout(buyer, shipping_input())
    services.pay(buyer, order.pk, {"mock_result": "approve"})

    shipped = services.ship(admin_user, order.pk, {"tracking_number": " TRACK-0001 "})

    assert shipped.status == STATUS_SHIPPED
    assert shipped.shipped_at is not None
    assert shipped.tracking_number == "TRACK-0001"
    history = shipped.status_history.order_by("pk").last()
    assert (history.from_status, history.to_status) == (STATUS_PAID, STATUS_SHIPPED)
    assert history.actor_role == ROLE_ADMIN


# trace: FR-043
def test_ship_allows_omitted_tracking_number(buyer, admin_user):
    """FR-043 6.23.3：配送伝票番号は任意項目とする。"""
    prepare_cart(buyer)
    order = services.checkout(buyer, shipping_input())
    services.pay(buyer, order.pk, {"mock_result": "approve"})

    shipped = services.ship(admin_user, order.pk, {})

    assert shipped.status == STATUS_SHIPPED
    assert shipped.tracking_number is None


# trace: FR-043
def test_ship_rejects_invalid_tracking_number(buyer, admin_user):
    """E-043-03：配送伝票番号が英数字・ハイフン以外・31文字以上の場合は入力エラーとする。"""
    prepare_cart(buyer)
    order = services.checkout(buyer, shipping_input())
    services.pay(buyer, order.pk, {"mock_result": "approve"})

    with pytest.raises(ValidationFailed) as error:
        services.ship(admin_user, order.pk, {"tracking_number": "A" * 31})

    assert error.value.details[0]["field"] == "tracking_number"
    order.refresh_from_db()
    assert order.status == STATUS_PAID


# trace: FR-043
def test_ship_rejects_order_that_is_not_paid(buyer, admin_user):
    """E-043-05：支払済以外の注文は出荷登録できない。"""
    prepare_cart(buyer)
    order = services.checkout(buyer, shipping_input())

    with pytest.raises(InvalidStatusTransition) as error:
        services.ship(admin_user, order.pk, {})

    assert error.value.context == {"current_status": STATUS_CREATED}


# trace: FR-044
def test_deliver_marks_shipped_order_as_delivered(buyer, admin_user):
    """FR-044：出荷済の注文を配達完了にする。"""
    prepare_cart(buyer)
    order = services.checkout(buyer, shipping_input())
    services.pay(buyer, order.pk, {"mock_result": "approve"})
    services.ship(admin_user, order.pk, {})

    delivered = services.deliver(admin_user, order.pk)

    assert delivered.status == STATUS_DELIVERED
    assert delivered.delivered_at is not None
    history = delivered.status_history.order_by("pk").last()
    assert (history.from_status, history.to_status) == (STATUS_SHIPPED, STATUS_DELIVERED)


# trace: FR-044
def test_deliver_rejects_order_that_is_not_shipped(buyer, admin_user):
    """E-044-05：出荷済以外の注文は配達完了登録できない。"""
    prepare_cart(buyer)
    order = services.checkout(buyer, shipping_input())

    with pytest.raises(InvalidStatusTransition):
        services.deliver(admin_user, order.pk)


# trace: FR-044
def test_delivered_order_cannot_be_cancelled(buyer, admin_user):
    """ST-PO：配達完了の注文はキャンセルできない。"""
    prepare_cart(buyer)
    order = services.checkout(buyer, shipping_input())
    services.pay(buyer, order.pk, {"mock_result": "approve"})
    services.ship(admin_user, order.pk, {})
    services.deliver(admin_user, order.pk)

    with pytest.raises(InvalidStatusTransition) as error:
        services.cancel_by_admin(admin_user, order.pk)

    assert error.value.context == {"current_status": STATUS_DELIVERED}


# trace: FR-042
def test_get_admin_order_returns_any_buyers_order(buyer):
    """FR-042：管理者は全購入者の注文詳細を取得できる。"""
    prepare_cart(buyer)
    order = services.checkout(buyer, shipping_input())

    assert services.get_admin_order(order.pk).pk == order.pk


# trace: FR-042
def test_find_any_order_rejects_unknown_identifier():
    """E-042-04：該当しない注文IDは対象なしとする。"""
    with pytest.raises(NotFoundError):
        services.find_any_order("abc")
    with pytest.raises(NotFoundError):
        services.find_any_order(999999)


# trace: FR-041
def test_admin_search_orders_filters_by_order_number(buyer):
    """FR-041 手順6：注文番号の完全一致で絞り込む。"""
    prepare_cart(buyer)
    target = services.checkout(buyer, shipping_input())
    prepare_cart(buyer)
    services.checkout(buyer, shipping_input())

    orders, meta, conditions = services.admin_search_orders({"order_number": target.order_number})

    assert [order.pk for order in orders] == [target.pk]
    assert meta["total_count"] == 1
    assert conditions["order_number"] == target.order_number


# trace: FR-041
def test_admin_search_orders_filters_by_multiple_statuses(buyer):
    """FR-041 手順7：複数の注文状態を指定した場合はいずれかに一致する注文を対象とする。"""
    prepare_cart(buyer)
    created = services.checkout(buyer, shipping_input())
    prepare_cart(buyer)
    paid = services.checkout(buyer, shipping_input())
    services.pay(buyer, paid.pk, {"mock_result": "approve"})
    prepare_cart(buyer)
    cancelled = services.checkout(buyer, shipping_input())
    services.cancel_by_buyer(buyer, cancelled.pk)

    orders, _meta, conditions = services.admin_search_orders(
        {"status": ["created", "paid", "created", ""]}
    )

    assert {order.pk for order in orders} == {created.pk, paid.pk}
    assert conditions["statuses"] == ["created", "paid"]


# trace: FR-041
def test_admin_search_orders_filters_by_buyer_email_partial_match(buyer):
    """FR-041 手順10：購入者のメールアドレスの部分一致（大文字小文字を区別しない）。"""
    other = make_user(email="target.person@example.test")
    prepare_cart(other)
    target = services.checkout(other, shipping_input())
    prepare_cart(buyer)
    services.checkout(buyer, shipping_input())

    orders, _meta, _conditions = services.admin_search_orders({"buyer_email": "TARGET.PERSON"})

    assert [order.pk for order in orders] == [target.pk]


# trace: FR-041
def test_admin_search_orders_filters_by_ordered_date_range(buyer):
    """FR-041 手順8〜9：注文日（開始）は当日 00:00:00 以降、注文日（終了）は翌日 00:00:00 より前。"""
    prepare_cart(buyer)
    order = services.checkout(buyer, shipping_input())
    ordered_date = timeutils.to_jst(order.ordered_at).date()

    same_day, _meta, _conditions = services.admin_search_orders(
        {"ordered_from": str(ordered_date), "ordered_to": str(ordered_date)}
    )
    next_day, _meta2, _conditions2 = services.admin_search_orders(
        {"ordered_from": str(ordered_date + dt.timedelta(days=1))}
    )

    assert [item.pk for item in same_day] == [order.pk]
    assert next_day == []


# trace: FR-041
def test_admin_search_orders_reports_every_invalid_condition():
    """E-041-03：条件を満たさない全項目を1回で通知する。"""
    with pytest.raises(ValidationFailed) as error:
        services.admin_search_orders(
            {
                "order_number": "PO-1234",
                "status": ["unknown"],
                "ordered_from": "2027-04-10",
                "ordered_to": "2027-04-09",
                "buyer_email": "a" * 255,
                "page": "0",
            }
        )

    assert {detail["field"] for detail in error.value.details} == {
        "order_number",
        "status",
        "ordered_from",
        "buyer_email",
        "page",
    }


# trace: FR-041
def test_admin_search_orders_rejects_non_existing_date():
    """E-041-03：実在しない日付は入力エラーとする。"""
    with pytest.raises(ValidationFailed) as error:
        services.admin_search_orders({"ordered_from": "2027-02-30"})

    assert error.value.details[0]["field"] == "ordered_from"


# trace: FR-041
def test_admin_search_orders_accepts_same_from_and_to_date(buyer):
    """FR-041 手順4：注文日（開始）＝注文日（終了）は許容する（境界値）。"""
    orders, _meta, conditions = services.admin_search_orders(
        {"ordered_from": "2027-04-10", "ordered_to": "2027-04-10"}
    )

    assert orders == []
    assert conditions["ordered_from"] == dt.date(2027, 4, 10)


# trace: FR-041
def test_admin_search_orders_accepts_single_status_string(buyer):
    """FR-041：注文状態は単一指定でも受け付ける。"""
    prepare_cart(buyer)
    order = services.checkout(buyer, shipping_input())

    orders, _meta, conditions = services.admin_search_orders({"status": "created"})

    assert [item.pk for item in orders] == [order.pk]
    assert conditions["statuses"] == ["created"]


# trace: FR-041
def test_parse_date_condition_returns_none_for_empty_value():
    """0文字の日付条件は指定なしとして扱う。"""
    from common.validators import ValidationCollector

    collector = ValidationCollector()

    assert services.parse_date_condition("  ", "ordered_from", collector) is None
    assert collector.has_errors is False


# trace: FR-033
def test_load_order_raises_not_found_for_unknown_order():
    """注文詳細の取得で該当がない場合は対象なしとする。"""
    with pytest.raises(NotFoundError):
        services.load_order(999999)


# trace: FR-033
def test_purchase_order_operation_flags_follow_status(buyer, admin_user):
    """D-10：操作可否（支払・キャンセル・出荷・配達完了）は注文状態から算出する。"""
    prepare_cart(buyer)
    order = services.checkout(buyer, shipping_input())

    assert (order.can_pay, order.can_cancel, order.can_ship, order.can_deliver) == (True, True, False, False)

    paid = services.pay(buyer, order.pk, {"mock_result": "approve"})
    assert (paid.can_pay, paid.can_cancel, paid.can_ship, paid.can_deliver) == (False, True, True, False)

    shipped = services.ship(admin_user, order.pk, {})
    assert (shipped.can_pay, shipped.can_cancel, shipped.can_ship, shipped.can_deliver) == (
        False,
        False,
        False,
        True,
    )
    assert shipped.status_label == "出荷済"
