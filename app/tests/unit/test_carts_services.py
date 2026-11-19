# trace: FR-020, FR-021, FR-022, FR-023, FR-024, FR-025, FR-026, NFR-SC-04, ADDR-001, ADDR-004, ADDR-012
"""カートの業務処理（carts.services：FR-020〜FR-025。金額内訳は FR-026）の単体テスト。

期待値は functional_requirements.md 6.8〜6.13（処理内容・事後条件・例外）、ADDR-001 DD-015・DD-016（利用中カートの作成の
冪等性・一意性）、4.3 の10・12（カート内容・values のキー）、ADDR-004 DD-013（FR-021 の使用済みトークン）、
ADDR-012 DD-003（判定順序は業務処理層）と AC-UC-004-027・AC-UC-005-030（複数条件が同時に成立する場合の
判定順序）から導出する。
DB Test Strategy：CONTAINER（ORM の永続化・条件付き一意制約・トランザクションのロールバックを検証）。
障害の経路は DB 例外を差し込む（MOCK）。行ロックによる排他（複数接続の並行実行）は単体テストでは扱わず、
結合テスト工程（ADDR-011 DD-010：transaction=True の同時実行試験）で確認する。
"""

from unittest import mock

import pytest
from django.db import DatabaseError, IntegrityError

from carts import services
from carts.models import Cart, CartItem
from catalog.models import StockUnit
from common import errors
from common.submit_token import TokenContext
from tests.unit.conftest import jst

pytestmark = pytest.mark.django_db
NOW = jst(2027, 4, 15, 10, 0, 0)


# trace: FR-021
def _items(cart):
    return list(CartItem.objects.filter(cart=cart).order_by("pk").values_list("stock_unit_id", "quantity"))


# trace: FR-021
def _fields(exc_info):
    return {(f.field, f.reason) for f in exc_info.value.fields}


# ---------------------------------------------------------------------------
# FR-020 カート照会
# ---------------------------------------------------------------------------


# trace: FR-020, ADDR-001
def test_get_cart_creates_one_empty_active_cart_when_missing(buyer, freeze):
    freeze(NOW)
    content = services.get_cart(buyer)
    assert content == {
        "items": [],
        "total_quantity": 0,
        "coupon": None,
        "amounts": {
            "subtotal": 0,
            "discount_amount": 0,
            "discounted_subtotal": 0,
            "shipping_fee": 0,
            "tax_amount": 0,
            "total_amount": 0,
        },
    }
    cart = Cart.objects.get(buyer=buyer)
    assert (cart.status, cart.coupon_id, cart.created_at, cart.ordered_at) == ("active", None, NOW, None)
    services.get_cart(buyer)  # DD-016：2回目以降は既存の利用中カート
    assert Cart.objects.filter(buyer=buyer, status="active").count() == 1


# trace: FR-020, ADDR-001
def test_get_cart_concurrent_creation_rereads_existing_cart(buyer, make_cart):
    """DD-016：一意違反となった側は作成済みの利用中カートを読み直す。"""
    existing = make_cart(buyer)
    real_lock = services._lock_active_cart
    calls = []

    def lock_first_missing(user):
        calls.append(user)
        return None if len(calls) == 1 else real_lock(user)

    with mock.patch.object(services, "_lock_active_cart", side_effect=lock_first_missing):
        with mock.patch.object(Cart.objects, "create", side_effect=IntegrityError("cart_one_active_per_buyer")):
            assert services._lock_or_create_active_cart(buyer, NOW) == existing
    assert len(calls) == 2


# trace: FR-020
def test_lock_or_create_reraises_when_reread_finds_nothing(buyer):
    with mock.patch.object(Cart.objects, "create", side_effect=IntegrityError("x")):
        with pytest.raises(IntegrityError):
            services._lock_or_create_active_cart(buyer, NOW)


# trace: FR-020, FR-026
def test_get_cart_returns_items_in_added_order_with_current_prices(buyer, catalog, make_cart, make_coupon):
    product = catalog.product("マグ")
    first = catalog.stock_unit(product, price=1200, stock=3, sku="MUG-1", variant_name="青")
    second = catalog.stock_unit(product, price=800, stock=1, sku="MUG-2", variant_name="白")
    coupon = make_coupon("SPRING", discount_type="percentage", discount_value=10, minimum_purchase_amount=1000)
    make_cart(buyer, [(first, 2), (second, 3)], coupon=coupon)
    StockUnit.objects.filter(pk=first.pk).update(price_excluding_tax=1500)  # 現在の価格で計算
    content = services.get_cart(buyer)
    assert [i["stock_unit_id"] for i in content["items"]] == [first.pk, second.pk]
    assert content["items"][0] == {
        "cart_item_id": content["items"][0]["cart_item_id"],
        "stock_unit_id": first.pk,
        "sku": "MUG-1",
        "product_id": product.pk,
        "product_name": "マグ",
        "variant_name": "青",
        "unit_price_excluding_tax": 1500,
        "quantity": 2,
        "line_amount": 3000,
        "stock_quantity": 3,
    }
    assert content["total_quantity"] == 5
    assert content["amounts"]["subtotal"] == 3000 + 2400
    assert content["amounts"]["discount_amount"] == 540
    assert content["coupon"]["coupon_code"] == "SPRING"
    assert content["coupon"]["discount_type_label"] == "定率"
    assert content["coupon"]["is_applicable"] is True and content["coupon"]["not_applicable_reason"] is None
    assert services.shortage_item_ids(content) == [content["items"][1]["cart_item_id"]]  # 3個＞在庫1


# trace: FR-020, FR-026
def test_get_cart_shows_not_applicable_coupon_without_removing_it(buyer, catalog, make_cart, make_coupon, freeze):
    freeze(jst(2027, 5, 1, 0, 0, 0))
    coupon = make_coupon(valid_from=jst(2027, 4, 1), valid_to=jst(2027, 4, 30, 23, 59, 59))
    cart = make_cart(buyer, [(catalog.stock_unit(price=6000), 1)], coupon=coupon)
    content = services.get_cart(buyer)
    assert content["coupon"]["is_applicable"] is False
    assert content["coupon"]["not_applicable_reason"] == "expired"
    assert content["amounts"]["discount_amount"] == 0
    cart.refresh_from_db()
    assert cart.coupon_id == coupon.pk  # 条件を満たさない場合もクーポンは自動では外さない


# trace: FR-020
def test_get_cart_database_failure_is_system_error_and_creates_nothing(buyer):
    with mock.patch.object(Cart.objects, "create", side_effect=DatabaseError("x")):
        with pytest.raises(errors.SystemFailureError) as info:
            services.get_cart(buyer)
    assert info.value.code == "E-020-03"
    assert not Cart.objects.filter(buyer=buyer).exists()


# ---------------------------------------------------------------------------
# FR-021 カート明細追加
# ---------------------------------------------------------------------------


# trace: FR-021
def test_add_item_creates_cart_and_line_without_changing_stock(buyer, catalog, freeze):
    freeze(NOW)
    unit = catalog.stock_unit(price=1000, stock=10)
    content = services.add_item(buyer, str(unit.pk), "3")
    cart = Cart.objects.get(buyer=buyer, status="active")
    assert _items(cart) == [(unit.pk, 3)]
    assert CartItem.objects.get(cart=cart).added_at == NOW and cart.updated_at == NOW
    assert content["total_quantity"] == 3
    assert StockUnit.objects.get(pk=unit.pk).stock_quantity == 10  # 在庫は引き当てない


# trace: FR-021
def test_add_item_merges_same_stock_unit_into_one_line(buyer, catalog, make_cart):
    unit = catalog.stock_unit(stock=10)
    cart = make_cart(buyer, [(unit, 8)])
    services.add_item(buyer, unit.pk, 2)  # 既存8＋2＝10 は可
    assert _items(cart) == [(unit.pk, 10)]


# trace: FR-021
@pytest.mark.parametrize(("existing", "added", "ok"), [(8, 2, True), (8, 3, False), (0, 10, True), (0, 11, False)])
def test_add_item_quantity_limit_10_per_stock_unit(buyer, catalog, make_cart, existing, added, ok):
    unit = catalog.stock_unit(stock=99)
    cart = make_cart(buyer, [(unit, existing)] if existing else [])
    if ok:
        services.add_item(buyer, unit.pk, added)
        assert _items(cart) == [(unit.pk, existing + added)]
    else:
        with pytest.raises(errors.BusinessError) as info:
            services.add_item(buyer, unit.pk, added)
        assert info.value.code == "E-021-05"
        assert info.value.reason == "quantity_limit_exceeded"
        assert info.value.values == {
            "stock_unit_id": unit.pk,
            "max_quantity": 10,
            "current_quantity": existing,
            "resulting_quantity": existing + added,
        }
        assert _items(cart) == ([(unit.pk, existing)] if existing else [])


# trace: FR-021
def test_add_item_limit_counts_each_stock_unit_separately(buyer, catalog, make_cart):
    product = catalog.product()
    a, b = catalog.stock_unit(product, stock=20), catalog.stock_unit(product, stock=20)
    cart = make_cart(buyer, [(a, 10)])
    content = services.add_item(buyer, b.pk, 10)  # 同一商品でも在庫単位が異なれば別に数える（TERM-032）
    assert _items(cart) == [(a.pk, 10), (b.pk, 10)]
    assert content["total_quantity"] == 20
    assert [(i["stock_unit_id"], i["quantity"]) for i in content["items"]] == [(a.pk, 10), (b.pk, 10)]
    with pytest.raises(errors.BusinessError) as info:
        services.add_item(buyer, b.pk, 1)  # 在庫単位ごとの上限は維持される
    assert info.value.code == "E-021-05" and info.value.values["current_quantity"] == 10


# trace: FR-021
@pytest.mark.parametrize(("existing", "added", "stock", "ok"), [(3, 2, 4, False), (3, 1, 4, True), (0, 1, 0, False)])
def test_add_item_stock_check_uses_resulting_quantity(buyer, catalog, make_cart, existing, added, stock, ok):
    unit = catalog.stock_unit(stock=stock, sku=f"STK-{existing}-{added}-{stock}")
    cart = make_cart(buyer, [(unit, existing)] if existing else [])
    if ok:
        services.add_item(buyer, unit.pk, added)
    else:
        with pytest.raises(errors.BusinessError) as info:
            services.add_item(buyer, unit.pk, added)
        assert info.value.code == "E-021-06" and info.value.reason == "insufficient_stock"
        assert info.value.values == {
            "stock_units": [
                {
                    "stock_unit_id": unit.pk,
                    "sku": unit.sku,
                    "requested_quantity": existing + added,
                    "stock_quantity": stock,
                }
            ]
        }
        assert _items(cart) == ([(unit.pk, existing)] if existing else [])


# trace: FR-021, NFR-SC-04
@pytest.mark.parametrize(
    ("stock_unit_id", "quantity", "expected"),
    [
        (None, "1", {("stock_unit_id", "required")}),
        ("abc", "1", {("stock_unit_id", "invalid_type")}),
        ("1", None, {("quantity", "required")}),
        ("1", "1.5", {("quantity", "invalid_type")}),
        ("1", "0", {("quantity", "out_of_range")}),
        ("1", "-1", {("quantity", "out_of_range")}),
        ("", "", {("stock_unit_id", "required"), ("quantity", "required")}),
        ("1", True, {("quantity", "invalid_type")}),
    ],
)
def test_add_item_input_errors(buyer, stock_unit_id, quantity, expected):
    with pytest.raises(errors.InputError) as info:
        services.add_item(buyer, stock_unit_id, quantity)
    assert info.value.code == "E-021-03"
    assert _fields(info) == expected
    assert not Cart.objects.exists()


# trace: FR-021
def test_add_item_unknown_or_private_stock_unit_is_not_found_and_creates_no_cart(buyer, catalog):
    private = catalog.stock_unit(catalog.product(is_public=False))
    for target in (999999999, private.pk, -5, "9" * 30):
        with pytest.raises(errors.NotFoundError) as info:
            services.add_item(buyer, target, 1)
        assert info.value.code == "E-021-04"
    assert not Cart.objects.exists()  # 異常終了時は利用中カートも作成しない


# trace: FR-021, ADDR-004
def test_add_item_used_token_does_not_add_again(buyer, catalog, make_cart):
    """ADDR-004 DD-013：FR-021 の使用済みトークンは加算せず先着の結果（現在のカート内容）を通知する。"""
    unit = catalog.stock_unit(stock=10)
    cart = make_cart(buyer, [(unit, 2)])
    replay = TokenContext(active=True, used=True, prior={"status": "success", "redirect": "/"})
    content = services.add_item(buyer, unit.pk, 2, replay)
    assert _items(cart) == [(unit.pk, 2)] and content["total_quantity"] == 2
    prior_error = errors.BusinessError("E-021-06", "在庫不足", reason="insufficient_stock").to_record()
    with pytest.raises(errors.BusinessError) as info:
        services.add_item(buyer, unit.pk, 2, TokenContext(active=True, used=True, prior=prior_error))
    assert info.value.code == "E-021-06"
    with pytest.raises(errors.SystemFailureError) as info:
        services.add_item(buyer, unit.pk, 2, TokenContext(active=True, used=True, prior=None))
    assert info.value.code == "E-021-07"
    assert _items(cart) == [(unit.pk, 2)]


# trace: FR-021
def test_add_item_database_failure_rolls_back(buyer, catalog):
    unit = catalog.stock_unit(stock=10)
    with mock.patch.object(CartItem.objects, "create", side_effect=DatabaseError("x")):
        with pytest.raises(errors.SystemFailureError) as info:
            services.add_item(buyer, unit.pk, 1)
    assert info.value.code == "E-021-07"
    assert not Cart.objects.exists()


# ---------------------------------------------------------------------------
# FR-022 カート明細数量変更
# ---------------------------------------------------------------------------


# trace: FR-022
def test_change_quantity_updates_only_target_line(buyer, catalog, make_cart, freeze):
    freeze(NOW)
    a, b = catalog.stock_unit(stock=10), catalog.stock_unit(stock=10)
    cart = make_cart(buyer, [(a, 1), (b, 2)])
    item = CartItem.objects.get(cart=cart, stock_unit=a)
    content = services.change_quantity(buyer, str(item.pk), "7")
    assert _items(cart) == [(a.pk, 7), (b.pk, 2)]
    cart.refresh_from_db()
    assert cart.updated_at == NOW and content["total_quantity"] == 9
    services.change_quantity(buyer, item.pk, 7)  # 同じ数量への変更も正常終了


# trace: FR-022
@pytest.mark.parametrize(("quantity", "code"), [(10, None), (11, "E-022-05")])
def test_change_quantity_limit_boundary(buyer, catalog, make_cart, quantity, code):
    unit = catalog.stock_unit(stock=99)
    cart = make_cart(buyer, [(unit, 10)])
    item = CartItem.objects.get(cart=cart)
    if code is None:
        services.change_quantity(buyer, item.pk, quantity)
        assert _items(cart) == [(unit.pk, 10)]
    else:
        with pytest.raises(errors.BusinessError) as info:
            services.change_quantity(buyer, item.pk, quantity)
        assert info.value.code == code
        assert info.value.values == {
            "stock_unit_id": unit.pk,
            "max_quantity": 10,
            "current_quantity": 10,
            "resulting_quantity": 11,
        }


# trace: FR-022
@pytest.mark.parametrize(("new", "ok"), [(6, False), (5, True)])
def test_change_quantity_stock_check_even_when_decreasing(buyer, catalog, make_cart, new, ok):
    """6.10.4 手順6 の例：明細8個・在庫数量5で6個→E-022-06、5個→正常。"""
    unit = catalog.stock_unit(stock=5)
    cart = make_cart(buyer, [(unit, 8)])
    item = CartItem.objects.get(cart=cart)
    if ok:
        services.change_quantity(buyer, item.pk, new)
        assert _items(cart) == [(unit.pk, 5)]
    else:
        with pytest.raises(errors.BusinessError) as info:
            services.change_quantity(buyer, item.pk, new)
        assert info.value.code == "E-022-06"
        assert info.value.values["stock_units"][0]["requested_quantity"] == 6
        assert _items(cart) == [(unit.pk, 8)]


# trace: FR-021, FR-022, ADDR-012
def test_quantity_limit_is_judged_before_insufficient_stock(buyer, catalog, make_cart, freeze):
    """AC-UC-004-027：上限10と在庫数量の両方を超える場合は数量上限超過（在庫不足ではない）。上限内なら在庫不足。"""
    freeze(jst(2027, 4, 10, 10, 0, 0))
    unit = catalog.stock_unit(price=400, stock=5, sku="CLO-002-WH")
    cart = make_cart(buyer, [(unit, 4)])
    item = CartItem.objects.get(cart=cart)
    limit_values = {"stock_unit_id": unit.pk, "max_quantity": 10, "current_quantity": 4, "resulting_quantity": 11}
    with pytest.raises(errors.BusinessError) as info:  # (1) 追加：合算11（上限・在庫の両方を超える）
        services.add_item(buyer, unit.pk, 7)
    assert (info.value.code, info.value.reason) == ("E-021-05", "quantity_limit_exceeded")
    assert info.value.values == limit_values
    with pytest.raises(errors.BusinessError) as info:  # (2) 数量変更：変更後11
        services.change_quantity(buyer, item.pk, 11)
    assert (info.value.code, info.value.reason) == ("E-022-05", "quantity_limit_exceeded")
    assert info.value.values == limit_values
    with pytest.raises(errors.BusinessError) as info:  # (3) 追加：合算6（上限以下・在庫数量5を超える）
        services.add_item(buyer, unit.pk, 2)
    assert (info.value.code, info.value.reason) == ("E-021-06", "insufficient_stock")
    assert info.value.values == {
        "stock_units": [
            {"stock_unit_id": unit.pk, "sku": "CLO-002-WH", "requested_quantity": 6, "stock_quantity": 5}
        ]
    }
    assert _items(cart) == [(unit.pk, 4)]
    assert services.get_cart(buyer)["items"][0]["quantity"] == 4
    assert StockUnit.objects.get(pk=unit.pk).stock_quantity == 5


# trace: FR-022, NFR-SC-04
@pytest.mark.parametrize(("quantity", "reason"), [(None, "required"), ("x", "invalid_type"), ("0", "out_of_range")])
def test_change_quantity_input_errors_come_before_target_check(buyer, quantity, reason):
    with pytest.raises(errors.InputError) as info:
        services.change_quantity(buyer, "999999", quantity)
    assert info.value.code == "E-022-03" and _fields(info) == {("quantity", reason)}


# trace: FR-022
def test_change_quantity_not_found_cases(buyer, other_buyer, catalog, make_cart):
    unit = catalog.stock_unit()
    others = make_cart(other_buyer, [(unit, 1)])
    other_item = CartItem.objects.get(cart=others)
    for target in (other_item.pk, "abc", "0", 99999999):
        with pytest.raises(errors.NotFoundError) as info:
            services.change_quantity(buyer, target, 1)  # 利用中カートがない場合を含む
        assert info.value.code == "E-022-04"
    ordered = make_cart(buyer, [(unit, 1)])
    Cart.objects.filter(pk=ordered.pk).update(status="ordered", ordered_at=NOW)
    with pytest.raises(errors.NotFoundError):
        services.change_quantity(buyer, CartItem.objects.get(cart=ordered).pk, 1)  # 注文済のカートの明細


# trace: FR-022
def test_change_quantity_database_failure(buyer, catalog, make_cart):
    unit = catalog.stock_unit()
    item = CartItem.objects.get(cart=make_cart(buyer, [(unit, 1)]))
    with mock.patch.object(CartItem, "save", side_effect=DatabaseError("x")):
        with pytest.raises(errors.SystemFailureError) as info:
            services.change_quantity(buyer, item.pk, 2)
    assert info.value.code == "E-022-07"


# ---------------------------------------------------------------------------
# FR-023 カート明細削除
# ---------------------------------------------------------------------------


# trace: FR-023, FR-026
def test_delete_item_keeps_coupon_and_empty_cart_amounts_are_zero(buyer, catalog, make_cart, make_coupon):
    unit = catalog.stock_unit()
    coupon = make_coupon()
    cart = make_cart(buyer, [(unit, 2)], coupon=coupon)
    content = services.delete_item(buyer, CartItem.objects.get(cart=cart).pk)
    cart.refresh_from_db()
    assert _items(cart) == [] and cart.coupon_id == coupon.pk
    assert content["amounts"]["total_amount"] == 0
    assert content["coupon"]["is_applicable"] is False
    assert content["coupon"]["not_applicable_reason"] == "empty_cart"
    assert StockUnit.objects.get(pk=unit.pk).stock_quantity == 10


# trace: FR-023
def test_delete_item_not_found_including_already_deleted(buyer, other_buyer, catalog, make_cart):
    unit = catalog.stock_unit()
    cart = make_cart(buyer, [(unit, 1)])
    item_pk = CartItem.objects.get(cart=cart).pk
    services.delete_item(buyer, item_pk)
    for target in (item_pk, "x", None):
        with pytest.raises(errors.NotFoundError) as info:
            services.delete_item(buyer, target)
        assert info.value.code == "E-023-03"
    other = make_cart(other_buyer, [(unit, 1)])
    with pytest.raises(errors.NotFoundError):
        services.delete_item(buyer, CartItem.objects.get(cart=other).pk)
    assert CartItem.objects.filter(cart=other).exists()


# trace: FR-023
def test_delete_item_database_failure(buyer, catalog, make_cart):
    cart = make_cart(buyer, [(catalog.stock_unit(), 1)])
    with mock.patch.object(CartItem, "delete", side_effect=DatabaseError("x")):
        with pytest.raises(errors.SystemFailureError) as info:
            services.delete_item(buyer, CartItem.objects.get(cart=cart).pk)
    assert info.value.code == "E-023-04"


# ---------------------------------------------------------------------------
# FR-024 クーポン適用
# ---------------------------------------------------------------------------


# trace: FR-024, FR-026
def test_apply_coupon_normalizes_code_and_applies(buyer, catalog, make_cart, make_coupon, freeze):
    freeze(NOW)
    coupon = make_coupon("SPRING-10", discount_type="fixed_amount", discount_value=1000)
    cart = make_cart(buyer, [(catalog.stock_unit(price=6000), 1)])
    content = services.apply_coupon(buyer, "  spring-10 ")
    cart.refresh_from_db()
    assert cart.coupon_id == coupon.pk and cart.updated_at == NOW
    assert content["coupon"]["is_applicable"] is True
    assert content["amounts"] == {
        "subtotal": 6000,
        "discount_amount": 1000,
        "discounted_subtotal": 5000,
        "shipping_fee": 0,
        "tax_amount": 500,
        "total_amount": 5500,
    }


# trace: FR-024, NFR-SC-04
@pytest.mark.parametrize(
    ("code", "reason"),
    [
        (None, "required"),
        ("   ", "required"),
        (123, "invalid_type"),
        ("A" * 21, "invalid_length"),
        ("COUPON_1", "invalid_format"),
        ("クーポン", "invalid_format"),
        ("A\x00", "invalid_format"),
    ],
)
def test_apply_coupon_input_errors(buyer, code, reason):
    with pytest.raises(errors.InputError) as info:
        services.apply_coupon(buyer, code)
    assert info.value.code == "E-024-03" and _fields(info) == {("coupon_code", reason)}


# trace: FR-024
def test_apply_coupon_20_chars_is_accepted_as_format(buyer, catalog, make_cart, make_coupon):
    make_coupon("A" * 20)
    make_cart(buyer, [(catalog.stock_unit(), 1)])
    assert services.apply_coupon(buyer, "a" * 20)["coupon"]["coupon_code"] == "A" * 20


# trace: FR-024
def test_apply_coupon_requires_items_including_missing_cart(buyer, make_cart, make_coupon):
    make_coupon("OK")
    with pytest.raises(errors.BusinessError) as info:
        services.apply_coupon(buyer, "OK")
    assert info.value.code == "E-024-04" and info.value.reason == "cart_empty"
    assert not Cart.objects.exists()
    make_cart(buyer)
    with pytest.raises(errors.BusinessError) as info:
        services.apply_coupon(buyer, "OK")
    assert info.value.code == "E-024-04"


# trace: FR-024
def test_apply_coupon_only_one_per_cart_even_same_code(buyer, catalog, make_cart, make_coupon):
    applied = make_coupon("FIRST")
    make_coupon("SECOND")
    cart = make_cart(buyer, [(catalog.stock_unit(), 1)], coupon=applied)
    for code in ("FIRST", "SECOND"):
        with pytest.raises(errors.BusinessError) as info:
            services.apply_coupon(buyer, code)
        assert info.value.code == "E-024-05" and info.value.reason == "coupon_already_applied"
        assert "FIRST" in info.value.message
    cart.refresh_from_db()
    assert cart.coupon_id == applied.pk


# trace: FR-024
def test_apply_coupon_not_found(buyer, catalog, make_cart):
    make_cart(buyer, [(catalog.stock_unit(), 1)])
    with pytest.raises(errors.BusinessError) as info:
        services.apply_coupon(buyer, "NOPE")
    assert info.value.code == "E-024-06" and info.value.reason == "coupon_not_found"


# trace: FR-024
@pytest.mark.parametrize(
    ("moment", "code"),
    [
        (jst(2027, 3, 31, 23, 59, 59), "E-024-07"),
        (jst(2027, 4, 1, 0, 0, 0), None),
        (jst(2027, 4, 30, 23, 59, 59), None),
        (jst(2027, 5, 1, 0, 0, 0), "E-024-08"),
    ],
)
def test_apply_coupon_validity_period_boundaries(buyer, catalog, make_cart, make_coupon, freeze, moment, code):
    freeze(moment)
    start, end = jst(2027, 4, 1), jst(2027, 4, 30, 23, 59, 59)
    make_coupon("PERIOD", valid_from=start, valid_to=end)
    cart = make_cart(buyer, [(catalog.stock_unit(), 1)])
    if code is None:
        services.apply_coupon(buyer, "PERIOD")
        cart.refresh_from_db()
        assert cart.coupon is not None
    else:
        with pytest.raises(errors.BusinessError) as info:
            services.apply_coupon(buyer, "PERIOD")
        assert info.value.code == code
        assert info.value.reason == ("coupon_not_yet_valid" if code == "E-024-07" else "coupon_expired")
        assert info.value.values == {"valid_from": start, "valid_to": end}
        assert "2027/04/01 00:00〜2027/04/30 23:59" in info.value.message
        cart.refresh_from_db()
        assert cart.coupon is None


# trace: FR-024
@pytest.mark.parametrize(("subtotal", "ok"), [(2999, False), (3000, True)])
def test_apply_coupon_minimum_purchase_amount(buyer, catalog, make_cart, make_coupon, subtotal, ok):
    make_coupon("MIN", minimum_purchase_amount=3000)
    make_cart(buyer, [(catalog.stock_unit(price=subtotal), 1)])
    if ok:
        services.apply_coupon(buyer, "MIN")
    else:
        with pytest.raises(errors.BusinessError) as info:
            services.apply_coupon(buyer, "MIN")
        assert info.value.code == "E-024-09"
        assert info.value.values == {"minimum_purchase_amount": 3000, "subtotal": 2999}


# trace: FR-024
def test_apply_coupon_usage_is_not_limited_across_buyers(buyer, other_buyer, catalog, make_cart, make_coupon):
    shared = make_coupon("SHARED")
    unit = catalog.stock_unit()
    mine = make_cart(buyer, [(unit, 1)])
    theirs = make_cart(other_buyer, [(unit, 1)])
    first = services.apply_coupon(buyer, "SHARED")
    second = services.apply_coupon(other_buyer, "SHARED")  # 他の購入者が適用中でも利用回数で拒否しない
    assert first["coupon"]["coupon_code"] == second["coupon"]["coupon_code"] == "SHARED"
    assert first["coupon"]["is_applicable"] is True and second["coupon"]["is_applicable"] is True
    mine.refresh_from_db()
    theirs.refresh_from_db()
    assert mine.coupon_id == theirs.coupon_id == shared.pk


# trace: FR-024
def test_apply_coupon_database_failure(buyer, catalog, make_cart, make_coupon):
    make_coupon("DBF")
    make_cart(buyer, [(catalog.stock_unit(), 1)])
    with mock.patch.object(Cart, "save", side_effect=DatabaseError("x")):
        with pytest.raises(errors.SystemFailureError) as info:
            services.apply_coupon(buyer, "DBF")
    assert info.value.code == "E-024-10"


# trace: FR-024, FR-026, ADDR-012
def test_coupon_judgement_order_when_several_conditions_hold(
    buyer, other_buyer, make_user, catalog, make_cart, make_coupon, freeze
):
    """AC-UC-005-030：適用中→コード不存在、有効期間→最低購入金額の順に先に該当したエラー・理由を示す。"""
    spring = make_coupon(
        "SPRING10",
        discount_type="percentage",
        discount_value=10,
        minimum_purchase_amount=0,
        valid_from=jst(2027, 4, 1),
        valid_to=jst(2027, 4, 30, 23, 59, 59),
    )
    spend = make_coupon(
        "SPEND3000",
        discount_type="fixed_amount",
        discount_value=500,
        minimum_purchase_amount=3000,
        valid_from=jst(2027, 4, 1),
        valid_to=jst(2027, 6, 30, 23, 59, 59),
    )
    pot = catalog.stock_unit(price=1850, stock=20, sku="POT-005-S")
    pan = catalog.stock_unit(price=2999, stock=20, sku="PAN-010-24")
    third = make_user(name="購入者 三郎")
    cart_a = make_cart(buyer, [(pot, 3)], coupon=spring)
    cart_b = make_cart(other_buyer, [(pan, 1)])
    cart_c = make_cart(third, [(pan, 1)], coupon=spend)

    # (1) 適用中かつコード不存在 → クーポン適用済み（コード不存在ではない）
    freeze(jst(2027, 4, 10, 10, 0, 0))
    with pytest.raises(errors.BusinessError) as info:
        services.apply_coupon(buyer, "NOCOUPON99")
    assert (info.value.code, info.value.reason) == ("E-024-05", "coupon_already_applied")
    assert "SPRING10" in info.value.message and "1枚" in info.value.message and "解除" in info.value.message
    content = services.get_cart(buyer)
    assert content["coupon"]["coupon_code"] == "SPRING10" and content["amounts"]["total_amount"] == 6044
    cart_a.refresh_from_db()
    assert cart_a.coupon_id == spring.pk

    # (2) 有効終了日時超過かつ最低購入金額未満 → 有効期間終了（最低購入金額未満ではない）
    freeze(jst(2027, 7, 1, 0, 0, 0))
    with pytest.raises(errors.BusinessError) as info:
        services.apply_coupon(other_buyer, "SPEND3000")
    assert (info.value.code, info.value.reason) == ("E-024-08", "coupon_expired")
    assert info.value.values == {"valid_from": jst(2027, 4, 1), "valid_to": jst(2027, 6, 30, 23, 59, 59)}
    assert services.get_cart(other_buyer)["coupon"] is None
    cart_b.refresh_from_db()
    assert cart_b.coupon_id is None

    # (3) 適用中のクーポンが有効終了日時超過かつ最低購入金額未満 → 照会の適用不可理由は「有効期間終了」
    content = services.get_cart(third)
    assert content["coupon"]["coupon_code"] == "SPEND3000"
    assert content["coupon"]["is_applicable"] is False
    assert content["coupon"]["not_applicable_reason"] == "expired"
    assert content["amounts"] == {
        "subtotal": 2999,
        "discount_amount": 0,
        "discounted_subtotal": 2999,
        "shipping_fee": 500,
        "tax_amount": 349,
        "total_amount": 3848,
    }
    cart_c.refresh_from_db()
    assert cart_c.coupon_id == spend.pk  # 自動では外れない


# ---------------------------------------------------------------------------
# FR-025 クーポン解除
# ---------------------------------------------------------------------------


# trace: FR-025
def test_remove_coupon_clears_and_returns_zero_discount(buyer, catalog, make_cart, make_coupon, freeze):
    freeze(NOW)
    cart = make_cart(buyer, [(catalog.stock_unit(price=6000), 1)], coupon=make_coupon(discount_value=1000))
    content = services.remove_coupon(buyer)
    cart.refresh_from_db()
    assert cart.coupon_id is None and cart.updated_at == NOW
    assert content["coupon"] is None and content["amounts"]["discount_amount"] == 0
    assert _items(cart) != []


# trace: FR-025
def test_remove_coupon_without_coupon_or_cart_is_success(buyer, make_cart):
    content = services.remove_coupon(buyer)  # 利用中カートがなければ作成する
    assert content["coupon"] is None
    cart = Cart.objects.get(buyer=buyer)
    before = cart.updated_at
    services.remove_coupon(buyer)  # 未適用は更新しない
    cart.refresh_from_db()
    assert cart.updated_at == before


# trace: FR-025
def test_remove_coupon_database_failure(buyer):
    with mock.patch.object(Cart.objects, "create", side_effect=DatabaseError("x")):
        with pytest.raises(errors.SystemFailureError) as info:
            services.remove_coupon(buyer)
    assert info.value.code == "E-025-03"
