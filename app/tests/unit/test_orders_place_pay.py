# trace: FR-030, FR-031, FR-026, NFR-SC-04, NFR-SC-23, ADDR-001, ADDR-004, ADDR-005, ADDR-008, ADDR-011, ADDR-012
"""注文確定（FR-030）・支払（FR-031）の業務処理（orders.services）の単体テスト。

期待値は functional_requirements.md 6.15・6.16（入力・処理内容・事後条件・例外）、CMN-21・23・26・29、
ADDR-004 DD-005〜DD-007・DD-013、ADDR-005（注文番号）、ADDR-008（模擬決済）、ADDR-011（障害注入）、
ADDR-012 DD-003（判定順序は業務処理層）と AC-UC-006-032（複数の確定条件に該当する場合の判定順序）から導出する。
DB Test Strategy：CONTAINER（注文番号の採番・条件付き一意制約・追記のみの記録・トランザクションのロールバックを検証）。
行ロック・アドバイザリロックによる排他（複数接続の並行実行）は単体テストでは扱わず、
結合テスト工程（ADDR-011 DD-010：transaction=True の同時実行試験）で確認する。
決済サービス（模擬）は本システム内の模擬機能で外部へ通信しない（NFR-EN-05）。
"""

from types import SimpleNamespace
from unittest import mock

import pytest
from django.db import IntegrityError

from carts import services as cart_services
from carts.models import Cart
from catalog.models import StockUnit
from common import errors
from common.submit_token import TokenContext
from orders import services
from orders.models import AppendOnlyError, Order, OrderItem, OrderStatusHistory, PaymentRecord, ShippingAddress
from tests.unit.conftest import jst, snapshot_order

pytestmark = pytest.mark.django_db
NOW = jst(2027, 4, 20, 14, 30, 5)
ADDRESS = {
    "recipient_name": " 受取 太郎 ",
    "postal_code": "100-0001",
    "prefecture": "13",
    "address_line1": " 千代田区千代田1-1 ",
    "address_line2": "",
    "phone_number": "03-1234-5678",
}


# trace: FR-030
def _fields(exc_info):
    return {(f.field, f.reason) for f in exc_info.value.fields}


# trace: FR-030
def _stock(*units):
    return [StockUnit.objects.get(pk=u.pk).stock_quantity for u in units]


# trace: FR-030
def _assert_nothing_changed(buyer, cart, units, stocks):
    assert Order.objects.count() == 0 and OrderItem.objects.count() == 0
    assert ShippingAddress.objects.count() == 0 and OrderStatusHistory.objects.count() == 0
    assert _stock(*units) == stocks
    cart.refresh_from_db()
    assert cart.status == "active" and cart.ordered_at is None


# trace: FR-031
def _assert_unchanged_except(before, after, *updated):
    """6.16.5 データ更新の対象として updated に挙げた注文の項目（決済記録は "payments"）以外が処理前と同じ。

    注文の各項目（状態・各日時・各金額等）、注文明細、配送先、決済記録（件数と全項目）を比較する（6.16.6）。
    """
    for key, value in before["order"].items():
        if key not in updated:
            assert after["order"][key] == value, key
    assert after["items"] == before["items"] and after["address"] == before["address"]
    if "payments" not in updated:
        assert after["payments"] == before["payments"]


# ---------------------------------------------------------------------------
# FR-030 注文確定
# ---------------------------------------------------------------------------


# trace: FR-030, FR-026, ADDR-005
def test_place_order_allocates_stock_and_records_order(buyer, catalog, make_cart, make_coupon, freeze):
    freeze(NOW.replace(microsecond=999000))
    product = catalog.product("マグ")
    a = catalog.stock_unit(product, price=1850, stock=5, sku="A-1", variant_name="青")
    b = catalog.stock_unit(product, price=1850, stock=1, sku="B-1", variant_name="白")
    coupon = make_coupon("TEN", discount_type="percentage", discount_value=10)
    cart = make_cart(buyer, [(a, 2), (b, 1)], coupon=coupon)
    detail = services.place_order(buyer, dict(ADDRESS))

    order = Order.objects.get()
    assert order.buyer == buyer and order.status == "accepted" and order.ordered_at == NOW
    assert order.order_number.startswith("PO-") and len(order.order_number) == 11
    # 例3と同じ金額：小計5,550円・定率10%
    assert (order.subtotal, order.discount_amount, order.discounted_subtotal) == (5550, 555, 4995)
    assert (order.shipping_fee, order.tax_amount, order.total_amount) == (500, 549, 6044)
    assert (order.coupon_id, order.coupon_code, order.discount_type, order.discount_value) == (
        coupon.pk,
        "TEN",
        "percentage",
        10,
    )
    assert order.paid_at is None and order.shipped_at is None and order.tracking_number is None
    items = list(OrderItem.objects.filter(order=order).order_by("pk"))
    assert [
        (i.stock_unit_id, i.sku, i.product_name, i.variant_name, i.unit_price, i.quantity, i.line_amount)
        for i in items
    ] == [
        (a.pk, "A-1", "マグ", "青", 1850, 2, 3700),
        (b.pk, "B-1", "マグ", "白", 1850, 1, 1850),
    ]
    assert sum(i.line_amount for i in items) == order.subtotal
    address = ShippingAddress.objects.get(order=order)
    assert (address.recipient_name, address.postal_code, address.prefecture) == ("受取 太郎", "1000001", "13")
    assert (address.address_line1, address.address_line2, address.phone_number) == (
        "千代田区千代田1-1",
        None,
        "0312345678",
    )
    history = OrderStatusHistory.objects.get(order=order)
    assert (history.from_status, history.to_status, history.changed_at) == (None, "accepted", NOW)
    assert (history.actor_id, history.actor_user_type) == (buyer.pk, "buyer")
    assert _stock(a, b) == [3, 0]  # 減算後の在庫数量は0以上
    assert StockUnit.objects.get(pk=a.pk).updated_at == NOW
    cart.refresh_from_db()
    assert cart.status == "ordered" and cart.ordered_at == NOW and cart.coupon_id == coupon.pk
    # 返却は注文詳細内容（6.18.5）
    assert detail["order_number"] == order.order_number and detail["status_label"] == "注文受付"
    assert detail["can_pay"] is True and detail["can_cancel"] is True
    assert detail["shipping_address"]["prefecture_label"] == "東京都"
    assert detail["coupon"] == {
        "coupon_code": "TEN",
        "discount_type": "percentage",
        "discount_type_label": "定率",
        "discount_value": 10,
    }
    assert "payments" not in detail and "buyer" not in detail
    # 以後は新しい利用中カートを使う（合計点数0点）
    assert cart_services.get_cart(buyer)["total_quantity"] == 0


# trace: FR-030, ADDR-005
def test_order_numbers_are_unique_and_increase(buyer, catalog, make_cart):
    unit = catalog.stock_unit(stock=10)
    numbers = []
    for _ in range(2):
        make_cart(buyer, [(unit, 1)])
        numbers.append(services.place_order(buyer, dict(ADDRESS))["order_number"])
    assert numbers[0] != numbers[1] and int(numbers[1][3:]) > int(numbers[0][3:])


# trace: FR-030, ADDR-005
def test_order_number_exhaustion_is_system_error(buyer, catalog, make_cart):
    cart = make_cart(buyer, [(catalog.stock_unit(stock=3), 1)])
    with mock.patch.object(services, "ORDER_NUMBER_MAX", 0):
        with pytest.raises(errors.SystemFailureError) as info:
            services.place_order(buyer, dict(ADDRESS))
    assert info.value.code == "E-030-11"
    cart.refresh_from_db()
    assert cart.status == "active" and Order.objects.count() == 0


# trace: FR-030, NFR-SC-04
def test_place_order_reports_all_address_errors_at_once(buyer):
    with pytest.raises(errors.InputError) as info:
        services.place_order(buyer, {})
    assert info.value.code == "E-030-03"
    assert _fields(info) == {
        ("shipping_address.recipient_name", "required"),
        ("shipping_address.postal_code", "required"),
        ("shipping_address.prefecture", "required"),
        ("shipping_address.address_line1", "required"),
        ("shipping_address.phone_number", "required"),
    }
    with pytest.raises(errors.InputError):
        services.place_order(buyer, "not-an-object")


# trace: FR-030, NFR-SC-04
@pytest.mark.parametrize(
    ("key", "value", "reason"),
    [
        ("recipient_name", "名" * 50, None),
        ("recipient_name", "名" * 51, "invalid_length"),
        ("recipient_name", 5, "invalid_type"),
        ("recipient_name", "名\x00", "invalid_format"),
        ("postal_code", "1234567", None),
        ("postal_code", "123-4567", None),
        ("postal_code", "1234-567", "invalid_format"),
        ("postal_code", "123456", "invalid_format"),
        ("postal_code", "１２３４５６７", "invalid_format"),
        ("prefecture", "01", None),
        ("prefecture", "47", None),
        ("prefecture", "48", "invalid_choice"),
        ("prefecture", "1", "invalid_choice"),
        ("address_line1", "住" * 100, None),
        ("address_line1", "住" * 101, "invalid_length"),
        ("address_line1", 1, "invalid_type"),
        ("address_line1", "住\x00", "invalid_format"),
        ("address_line2", "建" * 100, None),
        ("address_line2", "建" * 101, "invalid_length"),
        ("address_line2", 1, "invalid_type"),
        ("address_line2", "建\x00", "invalid_format"),
        ("phone_number", "012345678", "invalid_format"),
        ("phone_number", "0123456789", None),
        ("phone_number", "090-1234-5678", None),
        ("phone_number", "012345678901", "invalid_format"),
        ("phone_number", "03(1234)5678", "invalid_format"),
    ],
)
def test_address_field_rules(buyer, key, value, reason):
    address = {**ADDRESS, key: value}
    if reason is None:
        with pytest.raises(errors.BusinessError) as info:  # 入力は通過し、カートが空の判定へ進む
            services.place_order(buyer, address)
        assert info.value.code == "E-030-04"
    else:
        with pytest.raises(errors.InputError) as info:
            services.place_order(buyer, address)
        assert _fields(info) == {(f"shipping_address.{key}", reason)}


# trace: FR-030
def test_place_order_empty_or_missing_cart_is_business_error_and_creates_no_cart(buyer, make_cart):
    with pytest.raises(errors.BusinessError) as info:
        services.place_order(buyer, dict(ADDRESS))
    assert info.value.code == "E-030-04" and info.value.reason == "cart_empty"
    assert not Cart.objects.exists()  # 利用中カートを作成しない
    make_cart(buyer)
    with pytest.raises(errors.BusinessError):
        services.place_order(buyer, dict(ADDRESS))


# trace: FR-030
def test_place_order_rejects_private_products_listing_all_in_added_order(buyer, catalog, make_cart):
    public = catalog.stock_unit(stock=5)
    hidden1 = catalog.stock_unit(catalog.product("非公開1", is_public=False), stock=0)
    hidden2 = catalog.stock_unit(catalog.product("非公開2", is_public=False), stock=5)
    cart = make_cart(buyer, [(hidden2, 1), (public, 1), (hidden1, 1)])
    with pytest.raises(errors.BusinessError) as info:
        services.place_order(buyer, dict(ADDRESS))
    assert info.value.code == "E-030-05" and info.value.reason == "unavailable_product"
    assert info.value.values == {"unavailable_stock_unit_ids": [hidden2.pk, hidden1.pk]}
    _assert_nothing_changed(buyer, cart, [public, hidden1, hidden2], [5, 0, 5])


# trace: FR-030
def test_place_order_quantity_over_10_is_rejected(buyer, catalog, make_cart):
    """6.15.4 手順6（明細の数量11以上）。DB の検査制約で通常は作れないため、明細の読込み結果を差し替える。"""
    unit = catalog.stock_unit(stock=50)
    cart = make_cart(buyer, [(unit, 1)])
    fake = [SimpleNamespace(stock_unit_id=unit.pk, quantity=11)]
    with mock.patch.object(services.CartItem.objects, "filter") as filtered:
        filtered.return_value.order_by.return_value = fake
        with pytest.raises(errors.BusinessError) as info:
            services.place_order(buyer, dict(ADDRESS))
    assert info.value.code == "E-030-06" and info.value.reason == "quantity_limit_exceeded"
    assert info.value.values == {
        "stock_unit_id": unit.pk,
        "max_quantity": 10,
        "current_quantity": 11,
        "resulting_quantity": 11,
    }
    _assert_nothing_changed(buyer, cart, [unit], [50])


# trace: FR-030
@pytest.mark.parametrize(
    ("moment", "code"),
    [
        (jst(2027, 3, 31, 23, 59, 59), "E-030-07"),
        (jst(2027, 4, 1, 0, 0, 0), None),
        (jst(2027, 4, 30, 23, 59, 59), None),
        (jst(2027, 5, 1, 0, 0, 0), "E-030-08"),
    ],
)
def test_place_order_rechecks_coupon_period_at_confirmation(
    buyer, catalog, make_cart, make_coupon, freeze, moment, code
):
    freeze(moment)
    coupon = make_coupon("PERIOD", valid_from=jst(2027, 4, 1), valid_to=jst(2027, 4, 30, 23, 59, 59))
    unit = catalog.stock_unit(price=1000, stock=5)
    cart = make_cart(buyer, [(unit, 1)], coupon=coupon)
    if code is None:
        assert services.place_order(buyer, dict(ADDRESS))["coupon"]["coupon_code"] == "PERIOD"
    else:
        with pytest.raises(errors.BusinessError) as info:
            services.place_order(buyer, dict(ADDRESS))
        assert info.value.code == code
        assert info.value.reason == ("coupon_not_yet_valid" if code == "E-030-07" else "coupon_expired")
        _assert_nothing_changed(buyer, cart, [unit], [5])
        cart.refresh_from_db()
        assert cart.coupon_id == coupon.pk  # クーポンは外さない


# trace: FR-030
@pytest.mark.parametrize(("price", "ok"), [(2999, False), (3000, True)])
def test_place_order_rechecks_minimum_purchase_amount(buyer, catalog, make_cart, make_coupon, price, ok):
    unit = catalog.stock_unit(price=price, stock=5)
    cart = make_cart(buyer, [(unit, 1)], coupon=make_coupon(minimum_purchase_amount=3000))
    if ok:
        services.place_order(buyer, dict(ADDRESS))
    else:
        with pytest.raises(errors.BusinessError) as info:
            services.place_order(buyer, dict(ADDRESS))
        assert info.value.code == "E-030-09"
        assert info.value.values == {"minimum_purchase_amount": 3000, "subtotal": 2999}
        _assert_nothing_changed(buyer, cart, [unit], [5])


# trace: FR-030
def test_place_order_insufficient_stock_lists_all_shortages_and_allocates_nothing(buyer, catalog, make_cart):
    """6.15.4 手順9 の例：A 3個（在庫5）・B 2個（在庫1）・C 4個（在庫0）→ 不足 B と C、在庫は 5・1・0 のまま。"""
    a = catalog.stock_unit(stock=5, sku="SKU-A")
    b = catalog.stock_unit(stock=1, sku="SKU-B")
    c = catalog.stock_unit(stock=0, sku="SKU-C")
    cart = make_cart(buyer, [(a, 3), (b, 2), (c, 4)])
    with pytest.raises(errors.BusinessError) as info:
        services.place_order(buyer, dict(ADDRESS))
    assert info.value.code == "E-030-10" and info.value.reason == "insufficient_stock"
    assert info.value.values == {
        "stock_units": [
            {"stock_unit_id": b.pk, "sku": "SKU-B", "requested_quantity": 2, "stock_quantity": 1},
            {"stock_unit_id": c.pk, "sku": "SKU-C", "requested_quantity": 4, "stock_quantity": 0},
        ]
    }
    _assert_nothing_changed(buyer, cart, [a, b, c], [5, 1, 0])


# trace: FR-030
def test_place_order_check_order_private_before_stock(buyer, catalog, make_cart):
    """CMN-14・6.15.4：公開状態（手順5）は在庫（手順9）より先に判定する。"""
    hidden = catalog.stock_unit(catalog.product(is_public=False), stock=0)
    make_cart(buyer, [(hidden, 3)])
    with pytest.raises(errors.BusinessError) as info:
        services.place_order(buyer, dict(ADDRESS))
    assert info.value.code == "E-030-05"


# trace: FR-030, ADDR-012
def test_place_order_judgement_order_when_several_conditions_hold(make_user, catalog, make_cart, make_coupon, freeze):
    """AC-UC-006-032：非公開の商品→クーポン条件→在庫の順に先に該当したエラーを通知し、何も変更しない。"""
    freeze(jst(2027, 5, 1, 0, 0, 0))
    spring = make_coupon(
        "SPRING10",
        discount_type="percentage",
        discount_value=10,
        valid_from=jst(2027, 4, 1),
        valid_to=jst(2027, 4, 30, 23, 59, 59),
    )
    welcome = make_coupon(
        "WELCOME1000",
        discount_value=1000,
        minimum_purchase_amount=5000,
        valid_from=jst(2027, 4, 1),
        valid_to=jst(2027, 6, 30, 23, 59, 59),
    )
    mug = catalog.stock_unit(catalog.product("ステンレスマグ"), price=1500, stock=10, sku="MUG-001-BL")
    pot = catalog.stock_unit(catalog.product("ミルクパン"), price=1850, stock=20, sku="POT-005-S")
    kettle = catalog.stock_unit(catalog.product("ステンレスケトル"), price=3000, stock=5, sku="KTL-006-ST")
    buyer_a, buyer_b, buyer_c = make_user(), make_user(), make_user()
    cart_a = make_cart(buyer_a, [(mug, 1), (pot, 3)], coupon=spring)
    cart_b = make_cart(buyer_b, [(pot, 3)], coupon=spring)
    cart_c = make_cart(buyer_c, [(kettle, 1)], coupon=welcome)
    # カートを作った後に、商品の非公開化と在庫数量の変更が行われた状態
    mug.product.is_public = False
    mug.product.save()
    StockUnit.objects.filter(pk=pot.pk).update(stock_quantity=2)
    StockUnit.objects.filter(pk=kettle.pk).update(stock_quantity=0)

    with pytest.raises(errors.BusinessError) as info:  # (a) 非公開・有効期間終了・在庫不足 → 非公開
        services.place_order(buyer_a, dict(ADDRESS))
    assert (info.value.code, info.value.reason) == ("E-030-05", "unavailable_product")
    assert info.value.values == {"unavailable_stock_unit_ids": [mug.pk]}
    with pytest.raises(errors.BusinessError) as info:  # (b) 有効期間終了・在庫不足 → 有効期間終了
        services.place_order(buyer_b, dict(ADDRESS))
    assert (info.value.code, info.value.reason) == ("E-030-08", "coupon_expired")
    assert info.value.values == {"valid_from": jst(2027, 4, 1), "valid_to": jst(2027, 4, 30, 23, 59, 59)}
    with pytest.raises(errors.BusinessError) as info:  # (c) 最低購入金額未満・在庫不足 → 最低購入金額未満
        services.place_order(buyer_c, dict(ADDRESS))
    assert (info.value.code, info.value.reason) == ("E-030-09", "below_minimum_purchase_amount")
    assert info.value.values == {"minimum_purchase_amount": 5000, "subtotal": 3000}

    assert Order.objects.count() == 0 and OrderItem.objects.count() == 0 and OrderStatusHistory.objects.count() == 0
    assert _stock(mug, pot, kettle) == [10, 2, 0]
    for cart, coupon, lines in ((cart_a, spring, 2), (cart_b, spring, 1), (cart_c, welcome, 1)):
        cart.refresh_from_db()
        assert (cart.status, cart.ordered_at, cart.coupon_id) == ("active", None, coupon.pk)
        assert cart.items.count() == lines


# trace: FR-030, NFR-SC-04, ADDR-012
def test_place_order_full_judgement_order(buyer, catalog, make_cart, make_coupon, freeze):
    """6.15.4 手順3〜9：入力→明細0件→非公開→数量上限→有効期間→最低購入金額→在庫の順に、先に該当した例外だけを通知する。

    各段で、その段と後続のすべての条件が同時に成立する状態から先頭の条件だけを解消していく。
    """
    freeze(NOW)
    bad_address = dict(ADDRESS, postal_code="1-2", phone_number="abc")
    # 手順3 と 手順4：配送先の入力不備（全項目通知）は明細0件より先
    with pytest.raises(errors.InputError) as info:
        services.place_order(buyer, bad_address)
    assert info.value.code == "E-030-03"
    assert _fields(info) == {
        ("shipping_address.postal_code", "invalid_format"),
        ("shipping_address.phone_number", "invalid_format"),
    }
    assert not Cart.objects.exists()

    not_yet = make_coupon("NOTYET", minimum_purchase_amount=99999, valid_from=jst(2099, 1, 1))
    hidden = catalog.stock_unit(catalog.product(is_public=False), price=100, stock=0)
    short = catalog.stock_unit(price=100, stock=0)
    cart = make_cart(buyer, [(hidden, 2), (short, 3)], coupon=not_yet)
    # 非公開・有効期間前・最低購入金額未満・在庫不足が同時に成立していても入力エラーが先
    with pytest.raises(errors.InputError) as info:
        services.place_order(buyer, bad_address)
    assert info.value.code == "E-030-03"
    # 手順5：非公開が数量上限・クーポン条件・在庫より先（数量11の明細は検査制約で作れないため読込み結果を差し替える）
    fake = [SimpleNamespace(stock_unit_id=hidden.pk, quantity=2), SimpleNamespace(stock_unit_id=short.pk, quantity=11)]
    with mock.patch.object(services.CartItem.objects, "filter") as filtered:
        filtered.return_value.order_by.return_value = fake
        with pytest.raises(errors.BusinessError) as info:
            services.place_order(buyer, dict(ADDRESS))
    assert info.value.code == "E-030-05" and info.value.values == {"unavailable_stock_unit_ids": [hidden.pk]}
    # 手順6：数量上限がクーポン条件・在庫より先
    cart.items.filter(stock_unit=hidden).delete()
    fake = [SimpleNamespace(stock_unit_id=short.pk, quantity=11)]
    with mock.patch.object(services.CartItem.objects, "filter") as filtered:
        filtered.return_value.order_by.return_value = fake
        with pytest.raises(errors.BusinessError) as info:
            services.place_order(buyer, dict(ADDRESS))
    assert info.value.code == "E-030-06" and info.value.values["current_quantity"] == 11
    # 手順7：有効期間（開始前）が最低購入金額・在庫より先
    with pytest.raises(errors.BusinessError) as info:
        services.place_order(buyer, dict(ADDRESS))
    assert info.value.code == "E-030-07" and info.value.reason == "coupon_not_yet_valid"
    # 手順8：最低購入金額が在庫より先
    not_yet.valid_from = jst(2027, 1, 1)
    not_yet.save()
    with pytest.raises(errors.BusinessError) as info:
        services.place_order(buyer, dict(ADDRESS))
    assert info.value.code == "E-030-09"
    assert info.value.values == {"minimum_purchase_amount": 99999, "subtotal": 300}
    # 手順9：クーポン条件を満たせば在庫不足
    not_yet.minimum_purchase_amount = 0
    not_yet.save()
    with pytest.raises(errors.BusinessError) as info:
        services.place_order(buyer, dict(ADDRESS))
    assert info.value.code == "E-030-10"
    assert info.value.values["stock_units"] == [
        {"stock_unit_id": short.pk, "sku": short.sku, "requested_quantity": 3, "stock_quantity": 0}
    ]
    _assert_nothing_changed(buyer, cart, [hidden, short], [0, 0])
    cart.refresh_from_db()
    assert cart.coupon_id == not_yet.pk


# trace: FR-030, ADDR-011
@pytest.mark.parametrize("point", ["after_stock_decrement", "after_order_insert"])
def test_place_order_failure_midway_rolls_back_everything(buyer, catalog, make_cart, test_state, point):
    test_state(order_fault_point=point)
    unit = catalog.stock_unit(stock=5)
    cart = make_cart(buyer, [(unit, 2)])
    with pytest.raises(errors.SystemFailureError) as info:
        services.place_order(buyer, dict(ADDRESS))
    assert info.value.code == "E-030-11"
    _assert_nothing_changed(buyer, cart, [unit], [5])


# ---------------------------------------------------------------------------
# FR-031 支払（模擬決済）
# ---------------------------------------------------------------------------


# trace: FR-031, ADDR-008
def test_pay_order_approved_marks_paid_and_records_payment(buyer, catalog, make_order, freeze):
    """6.16.6 正常終了：在庫数量、注文の金額・明細・配送先は処理前と同じ（データ更新は状態・支払日時だけ。6.16.5）。"""
    freeze(NOW)
    unit = catalog.stock_unit(price=3000, stock=4)
    order = make_order(buyer, [(unit, 2)])
    before = snapshot_order(order, [unit])
    detail = services.pay_order(buyer, str(order.pk), None)  # 省略時は承認
    after = snapshot_order(order, [unit])
    order.refresh_from_db()
    assert order.status == "paid" and order.paid_at == NOW
    record = PaymentRecord.objects.get(order=order)
    assert record.result == "approved" and record.amount == order.total_amount
    assert record.transaction_ref.startswith("MOCK-") and len(record.transaction_ref) == 21
    assert record.processed_at == NOW
    history = OrderStatusHistory.objects.filter(order=order).order_by("pk").last()
    assert (history.from_status, history.to_status, history.changed_at, history.actor_id, history.actor_user_type) == (
        "accepted",
        "paid",
        NOW,
        buyer.pk,
        "buyer",
    )
    assert StockUnit.objects.get(pk=unit.pk).stock_quantity == 4  # 在庫数量は変更しない
    _assert_unchanged_except(before, after, "status", "paid_at", "payments")
    assert after["stock"] == before["stock"]
    assert after["history"][:-1] == before["history"] and len(after["history"]) == len(before["history"]) + 1
    assert detail["status"] == "paid" and detail["can_pay"] is False and detail["can_cancel"] is True
    assert "payments" not in detail  # 購入者には決済記録を示さない（MSG-04）


# trace: FR-031, ADDR-004, ADDR-008
def test_pay_order_declined_keeps_order_and_persists_record(buyer, catalog, make_order):
    """6.16.6 異常終了（否認）：状態は注文受付のまま、支払日時は未設定、注文状態履歴・在庫数量は処理前と同じ。

    決済記録（結果＝否認、取引参照番号なし）が1件増え、承認の決済記録は増えない。
    """
    unit = catalog.stock_unit(stock=5)
    order = make_order(buyer, [(unit, 1)])
    before = snapshot_order(order, [unit])
    with pytest.raises(errors.BusinessError) as info:
        services.pay_order(buyer, order.pk, " declined ")
    assert info.value.code == "E-031-06" and info.value.reason == "payment_declined"
    order.refresh_from_db()
    assert order.status == "accepted" and order.paid_at is None
    record = PaymentRecord.objects.get(order=order)
    assert (record.result, record.transaction_ref, record.amount) == ("declined", None, order.total_amount)
    assert OrderStatusHistory.objects.filter(order=order).count() == 1
    after = snapshot_order(order, [unit])
    _assert_unchanged_except(before, after, "payments")
    assert after["history"] == before["history"] and after["stock"] == before["stock"]
    services.pay_order(buyer, order.pk, "approved")  # 同じ注文に再度支払える
    assert PaymentRecord.objects.filter(order=order).count() == 2


# trace: FR-031, ADDR-008
def test_pay_order_integration_error_records_and_logs(buyer, catalog, make_order, test_state, app_logs, freeze):
    """6.16.6 異常終了（外部連携エラー）：状態は注文受付のまま、支払日時は未設定。

    注文状態履歴・在庫数量は処理前と同じ。
    """
    freeze(NOW)
    test_state(payment_mode="connection_error")
    unit = catalog.stock_unit(stock=5)
    order = make_order(buyer, [(unit, 1)])
    before = snapshot_order(order, [unit])
    with pytest.raises(errors.IntegrationError) as info:
        services.pay_order(buyer, order.pk, "approved")
    assert info.value.code == "E-031-07" and info.value.http_status == 502
    record = PaymentRecord.objects.get(order=order)
    assert (record.result, record.transaction_ref, record.processed_at) == ("integration_error", None, NOW)
    assert record.amount == order.total_amount
    order.refresh_from_db()
    assert order.status == "accepted"
    after = snapshot_order(order, [unit])
    _assert_unchanged_except(before, after, "payments")
    assert after["history"] == before["history"] and after["stock"] == before["stock"]
    assert any(r.get("error_type") == "integration_error" for r in app_logs.records())


# trace: FR-031, ADDR-004, ADDR-008, ADDR-011
@pytest.mark.parametrize(
    ("instruction", "payment_mode", "result"),
    [("declined", None, "declined"), ("approved", "connection_error", "integration_error")],
    ids=["declined_record", "integration_error_record"],
)
def test_pay_order_failure_while_recording_declined_or_integration_error_is_system_failure(
    buyer, catalog, make_order, test_state, fail_sql, freeze, instruction, payment_mode, result
):
    """6.16.4 手順10・手順11：否認・連携エラーの決済記録の登録でシステム障害が発生した場合は E-031-08。

    E-031-06・E-031-07 にしない。6.16.6 異常終了（その他）：注文の状態・支払日時、決済記録、注文状態履歴、
    在庫数量は処理前から変化していない（否認・連携エラーの決済記録も残らない）。決済要求は1回だけ送信し自動再送しない。
    """
    freeze(NOW)
    if payment_mode:
        test_state(payment_mode=payment_mode)
    unit = catalog.stock_unit(stock=5)
    order = make_order(buyer, [(unit, 1)])
    before = snapshot_order(order, [unit])
    from payments import client

    original = client.request_payment
    outcomes = []

    def _send(*args):
        outcomes.append(original(*args))
        return outcomes[-1]

    with mock.patch("payments.client.request_payment", side_effect=_send) as sent:
        with fail_sql(PaymentRecord, "INSERT") as fault:
            with pytest.raises(errors.SystemFailureError) as info:
                services.pay_order(buyer, order.pk, instruction)
    assert info.value.code == "E-031-08" and fault.injected
    assert sent.call_count == 1 and sent.call_args.args == (order.order_number, order.total_amount, instruction)
    assert [o.result for o in outcomes] == [result]  # 障害は手順10・手順11（当該結果の決済記録の登録）で発生している
    assert snapshot_order(order, [unit]) == before
    assert not PaymentRecord.objects.filter(order=order).exists()


# trace: FR-031, NFR-SC-04
@pytest.mark.parametrize("instruction", ["maybe", "承認", 1, "APPROVE"])
def test_pay_order_invalid_instruction_is_input_error_before_target_check(buyer, instruction):
    with pytest.raises(errors.InputError) as info:
        services.pay_order(buyer, "999999", instruction)
    assert info.value.code == "E-031-03" and _fields(info) == {("mock_instruction", "invalid_choice")}


# trace: FR-031
def test_pay_order_other_buyers_or_unknown_order_is_not_found(buyer, other_buyer, catalog, make_order):
    others = make_order(other_buyer, [(catalog.stock_unit(), 1)])
    with mock.patch("payments.client.request_payment") as sent:
        for target in (others.pk, "abc", 0, "99999999"):
            with pytest.raises(errors.NotFoundError) as info:
                services.pay_order(buyer, target, "approved")
            assert info.value.code == "E-031-04"
    sent.assert_not_called()
    assert not PaymentRecord.objects.exists()


# trace: FR-031
@pytest.mark.parametrize("status", ["paid", "shipped", "delivered", "cancelled"])
def test_pay_order_wrong_status_does_not_send_request(buyer, catalog, make_order, status):
    unit = catalog.stock_unit(stock=3)
    order = make_order(buyer, [(unit, 1)], status=status)
    before = snapshot_order(order, [unit])
    with mock.patch("payments.client.request_payment") as sent:
        with pytest.raises(errors.BusinessError) as info:
            services.pay_order(buyer, order.pk, "approved")
    sent.assert_not_called()
    assert info.value.code == "E-031-05" and info.value.reason == "invalid_status"
    assert info.value.values["current_status"] == status
    assert info.value.values["current_status_label"] in info.value.message
    # 6.16.6 異常終了（その他）：状態・支払日時、決済記録、注文状態履歴、在庫数量は処理前から変化していない
    assert snapshot_order(order, [unit]) == before


# trace: FR-031, ADDR-008
def test_pay_order_resend_after_approval_keeps_single_approved_record(buyer, catalog, make_order, freeze):
    """6.16 二重実行防止：承認後の再送信は E-031-05（現在の状態＝支払済）。

    承認の決済記録は1件のまま増えず、決済要求は送信しない。
    """
    freeze(NOW)
    unit = catalog.stock_unit(stock=3)
    order = make_order(buyer, [(unit, 1)])
    services.pay_order(buyer, order.pk, "approved")
    after_first = snapshot_order(order, [unit])
    assert [p["result"] for p in after_first["payments"]] == ["approved"] and len(after_first["history"]) == 2
    freeze(jst(2027, 4, 20, 14, 31, 0))
    with mock.patch("payments.client.request_payment") as sent:
        with pytest.raises(errors.BusinessError) as info:
            services.pay_order(buyer, order.pk, "approved")
    sent.assert_not_called()
    assert info.value.code == "E-031-05" and info.value.values["current_status"] == "paid"
    assert snapshot_order(order, [unit]) == after_first  # 支払日時・決済記録・履歴は1回目のまま


# trace: FR-031, ADDR-004
def test_pay_order_used_token_never_sends_and_reports_prior_result(buyer, catalog, make_order):
    order = make_order(buyer, [(catalog.stock_unit(), 1)])
    prior_error = errors.BusinessError("E-031-06", "否認", reason="payment_declined").to_record()
    with mock.patch("payments.client.request_payment") as sent:
        detail = services.pay_order(buyer, order.pk, "approved", TokenContext(True, True, {"status": "success"}))
        assert detail["status"] == "accepted"
        with pytest.raises(errors.BusinessError) as info:
            services.pay_order(buyer, order.pk, "approved", TokenContext(True, True, prior_error))
        assert info.value.code == "E-031-06"
        with pytest.raises(errors.SystemFailureError) as info:
            services.pay_order(buyer, order.pk, "approved", TokenContext(True, True, None))
        assert info.value.code == "E-031-08"
    sent.assert_not_called()


# trace: FR-031
def test_pay_order_database_failure_changes_nothing(buyer, catalog, make_order):
    unit = catalog.stock_unit(stock=3)
    order = make_order(buyer, [(unit, 1)])
    before = snapshot_order(order, [unit])
    with mock.patch.object(OrderStatusHistory.objects, "create", side_effect=services.DatabaseError("x")):
        with pytest.raises(errors.SystemFailureError) as info:
            services.pay_order(buyer, order.pk, "approved")
    assert info.value.code == "E-031-08"
    order.refresh_from_db()
    assert order.status == "accepted" and not PaymentRecord.objects.exists()
    assert snapshot_order(order, [unit]) == before  # 支払日時・注文状態履歴・在庫数量も処理前のまま


# trace: FR-031, ADDR-008
def test_pay_order_timeout_outcome_is_integration_error_without_resend(buyer, catalog, make_order, app_logs):
    """6.16.4 手順11：10秒以内に結果を受信しない場合は連携エラー。自動再送しない（送信は1回）。"""
    from payments.client import PaymentOutcome

    order = make_order(buyer, [(catalog.stock_unit(), 1)])
    timeout = PaymentOutcome("integration_error", error=TimeoutError("payment timeout"))
    with mock.patch("payments.client.request_payment", return_value=timeout) as sent:
        with pytest.raises(errors.IntegrationError) as info:
            services.pay_order(buyer, order.pk, "approved")
    assert sent.call_count == 1
    assert sent.call_args.args == (order.order_number, order.total_amount, "approved")
    assert info.value.code == "E-031-07"
    assert PaymentRecord.objects.get(order=order).result == "integration_error"
    log = [r for r in app_logs.records() if r.get("error_type") == "integration_error"][-1]
    assert log["exception_class"] == "builtins.TimeoutError"


# trace: FR-031, ADDR-004
def test_only_one_approved_payment_per_order_is_enforced_by_database(buyer, catalog, make_order):
    """ADDR-004 DD-005・CMN-23：承認の決済記録は注文ごとに最大1件（条件付き一意制約）。"""
    order = make_order(buyer, [(catalog.stock_unit(), 1)])
    PaymentRecord.objects.create(order=order, result="approved", amount=1, transaction_ref="MOCK-A", processed_at=NOW)
    PaymentRecord.objects.create(order=order, result="declined", amount=1, processed_at=NOW)
    with pytest.raises(IntegrityError):
        from django.db import transaction

        with transaction.atomic():
            PaymentRecord.objects.create(
                order=order, result="approved", amount=1, transaction_ref="MOCK-B", processed_at=NOW
            )


# trace: FR-031, NFR-SC-23
def test_payment_records_and_status_history_are_append_only(buyer, catalog, make_order):
    order = make_order(buyer, [(catalog.stock_unit(), 1)])
    record = PaymentRecord.objects.create(order=order, result="declined", amount=1, processed_at=NOW)
    history = OrderStatusHistory.objects.get(order=order)
    for instance in (record, history):
        with pytest.raises(AppendOnlyError):
            instance.save()
        with pytest.raises(AppendOnlyError):
            instance.delete()
    for manager in (PaymentRecord.objects, OrderStatusHistory.objects):
        with pytest.raises(AppendOnlyError):
            manager.all().update()
        with pytest.raises(AppendOnlyError):
            manager.all().delete()
    assert PaymentRecord.objects.filter(order=order).count() == 1
    assert OrderStatusHistory.objects.filter(order=order).count() == 1
