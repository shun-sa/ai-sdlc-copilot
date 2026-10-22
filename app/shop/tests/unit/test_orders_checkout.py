# trace: FR-021, FR-026, FR-030, ADDR-001, ADDR-003
"""注文確定（FR-030）の単体テスト。

期待値は FR-030 6.15.3・6.15.4 の入力条件と処理手順、および FR-026 の金額計算から導出する。
"""
from datetime import timedelta

import pytest

from shop.common import timeutils
from shop.common.errors import (
    CartEmptyError,
    CouponExpiredError,
    CouponMinSpendNotMetError,
    CouponNotYetValidError,
    InsufficientStockError,
    ItemNotAvailableError,
    ValidationError,
)
from shop.models import (
    Cart,
    CartStatus,
    PurchaseOrder,
    PurchaseOrderStatus,
    PurchaseOrderStatusHistory,
    Role,
    ShippingAddress,
    StockUnit,
)
from shop.services import carts, orders
from shop.tests.unit import _helpers

pytestmark = pytest.mark.django_db


# trace: FR-030
def _address(**overrides):
    """正常な配送先入力に上書きを適用して返す。"""
    data = dict(_helpers.VALID_ADDRESS)
    data.update(overrides)
    return data


# trace: FR-030
def test_checkout_creates_order_from_cart(buyer, stock_unit):
    """利用中カートの内容から注文・注文明細・配送先・状態履歴を登録する。"""
    carts.add_line(buyer, stock_unit.stock_unit_id, 2)

    result = orders.checkout(buyer, _address())

    order = PurchaseOrder.objects.get()
    assert result["purchase_order_id"] == order.purchase_order_id
    assert order.status == PurchaseOrderStatus.CREATED
    assert order.user_id == buyer.user_id
    assert order.order_number.startswith("PO-")
    assert len(order.order_number) == 11
    line = order.lines.get()
    assert (line.sku, line.item_name, line.variant_name) == (
        stock_unit.sku,
        stock_unit.item.name,
        stock_unit.variant_name,
    )
    assert (line.unit_price, line.quantity, line.line_amount) == (1000, 2, 2000)
    history = PurchaseOrderStatusHistory.objects.get()
    assert (history.from_status, history.to_status) == (None, PurchaseOrderStatus.CREATED)
    assert history.actor_user_id == buyer.user_id
    assert history.actor_role == Role.BUYER


# trace: FR-026, FR-030
def test_checkout_fixes_amounts_at_confirmation(buyer, stock_unit):
    """注文の金額は FR-026 の計算結果で確定する。"""
    carts.add_line(buyer, stock_unit.stock_unit_id, 2)

    orders.checkout(buyer, _address())

    order = PurchaseOrder.objects.get()
    assert (order.subtotal, order.discount_amount, order.discounted_subtotal) == (2000, 0, 2000)
    assert (order.shipping_fee, order.tax_amount, order.total) == (500, 250, 2750)


# trace: FR-030
def test_checkout_allocates_stock(buyer, stock_unit):
    """確定時に在庫数量を引き当てる（減算する）。"""
    carts.add_line(buyer, stock_unit.stock_unit_id, 3)

    orders.checkout(buyer, _address())

    assert StockUnit.objects.get(pk=stock_unit.pk).quantity == 7


# trace: FR-030
def test_checkout_converts_cart(buyer, stock_unit):
    """確定後に利用中カートを注文済へ変更する。"""
    carts.add_line(buyer, stock_unit.stock_unit_id, 1)

    orders.checkout(buyer, _address())

    cart = Cart.objects.get(user=buyer)
    assert cart.status == CartStatus.CONVERTED
    assert cart.converted_at is not None


# trace: FR-030
def test_checkout_registers_normalized_address(buyer, stock_unit):
    """配送先は前後空白除去・ハイフン除去後の値で登録する。"""
    carts.add_line(buyer, stock_unit.stock_unit_id, 1)

    orders.checkout(
        buyer,
        _address(recipient_name="  佐藤 花子  ", postal_code=" 123-4567 ", phone_number="090-1234-5678"),
    )

    address = ShippingAddress.objects.get()
    assert address.recipient_name == "佐藤 花子"
    assert address.postal_code == "1234567"
    assert address.phone_number == "09012345678"


# trace: FR-030
def test_checkout_stores_empty_address_line2_as_unset(buyer, stock_unit):
    """住所2が0文字の場合は未設定として登録する。"""
    carts.add_line(buyer, stock_unit.stock_unit_id, 1)

    orders.checkout(buyer, _address(address_line2="  "))

    assert ShippingAddress.objects.get().address_line2 is None


# trace: FR-030
def test_checkout_applies_coupon_snapshot(buyer, stock_unit):
    """クーポン適用中はクーポンのスナップショットを注文へ複写する。"""
    coupon = _helpers.make_coupon(code="SAVE500", discount_value=500)
    carts.add_line(buyer, stock_unit.stock_unit_id, 2)
    carts.apply_coupon(buyer, coupon.code)

    orders.checkout(buyer, _address())

    order = PurchaseOrder.objects.get()
    assert order.coupon_id == coupon.coupon_id
    assert order.coupon_code == "SAVE500"
    assert order.coupon_discount_value == 500
    assert order.discount_amount == 500
    assert order.discounted_subtotal == 1500


# trace: FR-030
def test_checkout_rejects_empty_cart(buyer):
    """利用中カートが無い場合は明細0件として E-030-04 とする。"""
    with pytest.raises(CartEmptyError):
        orders.checkout(buyer, _address())

    assert PurchaseOrder.objects.count() == 0
    assert Cart.objects.count() == 0


# trace: FR-030
def test_checkout_rejects_cart_without_lines(buyer):
    """明細0件の利用中カートは E-030-04 とする。"""
    _helpers.make_cart(buyer)

    with pytest.raises(CartEmptyError):
        orders.checkout(buyer, _address())


# trace: FR-030
def test_checkout_rejects_private_item(buyer, stock_unit):
    """非公開商品の明細を含む場合は E-030-05 とし、在庫を減らさない。"""
    carts.add_line(buyer, stock_unit.stock_unit_id, 1)
    item = stock_unit.item
    item.is_public = False
    item.save(update_fields=["is_public"])

    with pytest.raises(ItemNotAvailableError) as exc:
        orders.checkout(buyer, _address())

    assert exc.value.context["stock_unit_ids"] == [stock_unit.stock_unit_id]
    assert StockUnit.objects.get(pk=stock_unit.pk).quantity == 10
    assert PurchaseOrder.objects.count() == 0


# trace: FR-021, FR-030
def test_cart_line_quantity_over_limit_is_rejected_by_database_constraint(buyer, item, supplier):
    """カート明細の数量は1〜10に制約され、11個の明細はDBの検査制約で登録できない（D-09-04、DQ-19）。

    D-09-04（カート明細：数量の値域1以上10以下）と DQ-19（同一在庫単位の数量が10以下）により、
    FR-030 手順6（数量11以上の明細の判定）の対象となる明細は存在し得ないことを確認する。
    """
    from django.db import IntegrityError, transaction

    unit = _helpers.make_stock_unit(item, supplier, sku="SKU-010", quantity=50)
    cart = _helpers.make_cart(buyer)

    with pytest.raises(IntegrityError), transaction.atomic():
        _helpers.add_cart_line(cart, unit, quantity=11)

    assert StockUnit.objects.get(pk=unit.pk).quantity == 50


# trace: FR-030
def test_checkout_rejects_insufficient_stock_without_partial_allocation(buyer, item, supplier):
    """在庫不足の明細がある場合は不足する全在庫単位を通知し、在庫を一切減らさない（E-030-10）。"""
    enough = _helpers.make_stock_unit(item, supplier, sku="SKU-A", quantity=5)
    short_one = _helpers.make_stock_unit(item, supplier, sku="SKU-B", quantity=1)
    short_two = _helpers.make_stock_unit(item, supplier, sku="SKU-C", quantity=0)
    cart = _helpers.make_cart(buyer)
    _helpers.add_cart_line(cart, enough, quantity=3)
    _helpers.add_cart_line(cart, short_one, quantity=2)
    _helpers.add_cart_line(cart, short_two, quantity=4)

    with pytest.raises(InsufficientStockError) as exc:
        orders.checkout(buyer, _address())

    shortages = {row["sku"]: row for row in exc.value.context["shortages"]}
    assert set(shortages) == {"SKU-B", "SKU-C"}
    assert shortages["SKU-B"]["available_quantity"] == 1
    assert [StockUnit.objects.get(pk=unit.pk).quantity for unit in (enough, short_one, short_two)] == [5, 1, 0]


# trace: FR-030
def test_checkout_allows_quantity_equal_to_stock(buyer, item, supplier):
    """数量が在庫数量と等しい場合は確定でき、在庫数量は0になる（境界値）。"""
    unit = _helpers.make_stock_unit(item, supplier, sku="SKU-010", quantity=2)
    carts.add_line(buyer, unit.stock_unit_id, 2)

    orders.checkout(buyer, _address())

    assert StockUnit.objects.get(pk=unit.pk).quantity == 0


# trace: FR-030
def test_checkout_rejects_coupon_not_yet_valid(buyer, stock_unit):
    """確定時刻が有効開始日時より前のクーポンは E-030-07 とする。"""
    now = timeutils.now()
    coupon = _helpers.make_coupon(code="FUTURE", discount_value=100)
    carts.add_line(buyer, stock_unit.stock_unit_id, 1)
    carts.apply_coupon(buyer, coupon.code)
    coupon.valid_from = now + timedelta(days=1)
    coupon.valid_until = now + timedelta(days=2)
    coupon.save(update_fields=["valid_from", "valid_until"])

    with pytest.raises(CouponNotYetValidError):
        orders.checkout(buyer, _address())

    assert PurchaseOrder.objects.count() == 0


# trace: FR-030
def test_checkout_rejects_expired_coupon(buyer, stock_unit):
    """確定時刻が有効終了日時より後のクーポンは E-030-08 とする。"""
    now = timeutils.now()
    coupon = _helpers.make_coupon(code="PAST", discount_value=100)
    carts.add_line(buyer, stock_unit.stock_unit_id, 1)
    carts.apply_coupon(buyer, coupon.code)
    coupon.valid_from = now - timedelta(days=2)
    coupon.valid_until = now - timedelta(seconds=1)
    coupon.save(update_fields=["valid_from", "valid_until"])

    with pytest.raises(CouponExpiredError):
        orders.checkout(buyer, _address())


# trace: FR-030
def test_checkout_rejects_coupon_min_spend_not_met(buyer, stock_unit):
    """小計が最低購入金額未満の場合は E-030-09 とする。"""
    coupon = _helpers.make_coupon(code="BIG", discount_value=100, min_spend=1000)
    carts.add_line(buyer, stock_unit.stock_unit_id, 1)
    carts.apply_coupon(buyer, coupon.code)
    coupon.min_spend = 3000
    coupon.save(update_fields=["min_spend"])

    with pytest.raises(CouponMinSpendNotMetError) as exc:
        orders.checkout(buyer, _address())

    assert exc.value.context == {"min_spend": 3000, "subtotal": 1000}


# trace: FR-030
@pytest.mark.parametrize(
    ("overrides", "expected_field"),
    [
        ({"recipient_name": "  "}, "recipient_name"),
        ({"recipient_name": "あ" * 51}, "recipient_name"),
        ({"postal_code": ""}, "postal_code"),
        ({"postal_code": "12345"}, "postal_code"),
        ({"postal_code": "1234-567"}, "postal_code"),
        ({"prefecture_code": ""}, "prefecture_code"),
        ({"prefecture_code": "00"}, "prefecture_code"),
        ({"prefecture_code": "48"}, "prefecture_code"),
        ({"prefecture_code": "1"}, "prefecture_code"),
        ({"address_line1": ""}, "address_line1"),
        ({"address_line1": "あ" * 101}, "address_line1"),
        ({"address_line2": "あ" * 101}, "address_line2"),
        ({"phone_number": ""}, "phone_number"),
        ({"phone_number": "090123456"}, "phone_number"),
        ({"phone_number": "090123456789"}, "phone_number"),
        ({"phone_number": "090-1234-567a"}, "phone_number"),
    ],
)
def test_validate_shipping_address_rejects_invalid_values(overrides, expected_field):
    """配送先の入力条件（必須・文字数・形式・桁数）を満たさない値は入力エラーとする。"""
    with pytest.raises(ValidationError) as exc:
        orders.validate_shipping_address(_address(**overrides))

    assert any(detail["field"] == expected_field for detail in exc.value.details)


# trace: FR-030
@pytest.mark.parametrize(
    "overrides",
    [
        {"recipient_name": "あ"},
        {"recipient_name": "あ" * 50},
        {"postal_code": "1234567"},
        {"postal_code": "123-4567"},
        {"prefecture_code": "01"},
        {"prefecture_code": "47"},
        {"address_line1": "あ" * 100},
        {"address_line2": ""},
        {"address_line2": "あ" * 100},
        {"phone_number": "0312345678"},
        {"phone_number": "09012345678"},
    ],
)
def test_validate_shipping_address_accepts_boundary_values(overrides):
    """配送先の境界値（下限・上限・形式）を受け付ける。"""
    result = orders.validate_shipping_address(_address(**overrides))

    assert result["recipient_name"] != ""


# trace: FR-030
def test_validate_shipping_address_reports_all_invalid_fields():
    """配送先の不備は全項目をまとめて通知する（E-030-03）。"""
    with pytest.raises(ValidationError) as exc:
        orders.validate_shipping_address(
            {
                "recipient_name": "",
                "postal_code": "x",
                "prefecture_code": "99",
                "address_line1": "",
                "address_line2": "あ" * 101,
                "phone_number": "",
            }
        )

    assert {detail["field"] for detail in exc.value.details} == {
        "recipient_name",
        "postal_code",
        "prefecture_code",
        "address_line1",
        "address_line2",
        "phone_number",
    }


# trace: FR-030
def test_checkout_validates_address_before_touching_cart(buyer, stock_unit):
    """配送先の入力不備では在庫・カートを変更しない。"""
    carts.add_line(buyer, stock_unit.stock_unit_id, 1)

    with pytest.raises(ValidationError):
        orders.checkout(buyer, _address(postal_code="abc"))

    assert StockUnit.objects.get(pk=stock_unit.pk).quantity == 10
    assert Cart.objects.get(user=buyer).status == CartStatus.OPEN


# trace: FR-030, ADDR-003
def test_checkout_assigns_increasing_order_numbers(buyer, other_buyer, stock_unit):
    """注文番号は PO-＋8桁のゼロ埋めで、確定した順に大きくなる。"""
    carts.add_line(buyer, stock_unit.stock_unit_id, 1)
    first = orders.checkout(buyer, _address())
    carts.add_line(other_buyer, stock_unit.stock_unit_id, 1)
    second = orders.checkout(other_buyer, _address())

    assert first["order_number"] < second["order_number"]
    assert first["order_number"][3:].isdigit()
    assert len(first["order_number"]) == 11


# trace: FR-030
def test_checkout_orders_lines_by_added_at(buyer, item, supplier):
    """注文明細はカートへの追加日時の昇順で登録する。"""
    first = _helpers.make_stock_unit(item, supplier, sku="SKU-A")
    second = _helpers.make_stock_unit(item, supplier, sku="SKU-B")
    cart = _helpers.make_cart(buyer)
    older = _helpers.add_cart_line(cart, second, quantity=1)
    older.added_at = timeutils.now() - timedelta(minutes=1)
    older.save(update_fields=["added_at"])
    _helpers.add_cart_line(cart, first, quantity=1)

    result = orders.checkout(buyer, _address())

    assert [line["sku"] for line in result["lines"]] == ["SKU-B", "SKU-A"]
