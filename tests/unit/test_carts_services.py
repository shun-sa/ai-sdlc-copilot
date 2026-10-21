# trace: FR-020, FR-021, FR-022, FR-023, FR-024, FR-025, FR-030, NFR-SC-03, ADDR-003
"""カート・クーポン（FR-020〜FR-025）の単体テスト。

期待結果は機能要件 6.8（カート照会）・6.9（明細追加）・6.10（数量変更）・6.11（明細削除）・
6.12（クーポン適用）・6.13（クーポン解除）の処理内容・事後条件・例外、提供済みAPI契約 6.3
（業務エラーの context）、ADDR-003（在庫判定時の行ロック）から導出する。
"""

from __future__ import annotations

import datetime as dt

import pytest
from _helpers import add_cart_line, make_coupon, make_item, make_open_cart, make_stock_unit, make_user
from carts import services
from carts.models import CART_CONVERTED, CART_OPEN, DISCOUNT_PERCENTAGE, QUANTITY_LIMIT, Cart, CartLine
from common import timeutils
from common.exceptions import (
    CartEmpty,
    CouponAlreadyApplied,
    CouponExpired,
    CouponMinSpendNotMet,
    CouponNotFound,
    CouponNotYetValid,
    InsufficientStock,
    NotFoundError,
    QuantityLimitExceeded,
    ValidationFailed,
)

pytestmark = pytest.mark.django_db


# trace: FR-020
def test_show_cart_creates_open_cart_when_absent(buyer):
    """FR-020 手順3：利用中カートがない場合は明細0件のカートを1件作成する。"""
    view = services.show_cart(buyer)

    assert Cart.objects.filter(user=buyer, status=CART_OPEN).count() == 1
    assert view["lines"] == []
    assert view["total_quantity"] == 0
    assert view["amounts"]["total"] == 0


# trace: FR-020
def test_show_cart_reuses_existing_open_cart(buyer):
    """DQ-09：利用中カートは購入者1名につき最大1件とする。"""
    cart = make_open_cart(buyer)

    view = services.show_cart(buyer)

    assert view["cart"].pk == cart.pk
    assert Cart.objects.filter(user=buyer, status=CART_OPEN).count() == 1


# trace: FR-020
def test_show_cart_returns_lines_in_added_order(buyer):
    """FR-020 6.8.5：カート明細は追加日時の昇順で返す。"""
    cart = make_open_cart(buyer)
    first = add_cart_line(cart, make_stock_unit(make_item()), quantity=1)
    second = add_cart_line(cart, make_stock_unit(make_item()), quantity=2)

    view = services.show_cart(buyer)

    assert [line.pk for line in view["lines"]] == [first.pk, second.pk]
    assert view["total_quantity"] == 3


# trace: FR-021
def test_add_line_creates_line_without_reserving_stock(buyer):
    """FR-021 手順9：明細を1行追加し、在庫数量は変更しない。"""
    unit = make_stock_unit(make_item(), price=1000, quantity=10)

    view = services.add_line(buyer, {"stock_unit_id": unit.pk, "quantity": "2"})

    unit.refresh_from_db()
    assert unit.quantity == 10
    assert view["total_quantity"] == 2
    assert view["amounts"]["subtotal"] == 2000


# trace: FR-021
def test_add_line_merges_quantity_into_existing_line(buyer):
    """FR-021 手順6・9：同一在庫単位の明細は1行とし、数量を合算する。"""
    unit = make_stock_unit(make_item(), quantity=10)
    services.add_line(buyer, {"stock_unit_id": unit.pk, "quantity": 3})

    view = services.add_line(buyer, {"stock_unit_id": unit.pk, "quantity": 2})

    assert CartLine.objects.filter(stock_unit=unit).count() == 1
    assert view["lines"][0].quantity == 5


# trace: FR-021
def test_add_line_accepts_combined_quantity_of_ten(buyer):
    """FR-021 手順7：合算数量10は上限内（境界値）。"""
    unit = make_stock_unit(make_item(), quantity=20)
    services.add_line(buyer, {"stock_unit_id": unit.pk, "quantity": 8})

    view = services.add_line(buyer, {"stock_unit_id": unit.pk, "quantity": 2})

    assert view["lines"][0].quantity == QUANTITY_LIMIT == 10


# trace: FR-021
def test_add_line_rejects_combined_quantity_over_limit(buyer):
    """E-021-05：合算数量11は上限超過とし、既存明細の数量を変更しない。"""
    unit = make_stock_unit(make_item(), quantity=20)
    services.add_line(buyer, {"stock_unit_id": unit.pk, "quantity": 8})

    with pytest.raises(QuantityLimitExceeded) as error:
        services.add_line(buyer, {"stock_unit_id": unit.pk, "quantity": 3})

    assert error.value.context == {
        "stock_unit_id": unit.pk,
        "limit": 10,
        "current_quantity": 8,
        "requested_quantity": 11,
    }
    assert CartLine.objects.get(stock_unit=unit).quantity == 8


# trace: FR-021
def test_add_line_rejects_quantity_over_stock(buyer):
    """E-021-06：合算数量が在庫数量を超える場合は不足情報を通知する。"""
    unit = make_stock_unit(make_item(), quantity=4, sku="SKU-SHORT")
    services.add_line(buyer, {"stock_unit_id": unit.pk, "quantity": 3})

    with pytest.raises(InsufficientStock) as error:
        services.add_line(buyer, {"stock_unit_id": unit.pk, "quantity": 2})

    assert error.value.context == {
        "shortages": [
            {
                "stock_unit_id": unit.pk,
                "sku": "SKU-SHORT",
                "requested_quantity": 5,
                "available_quantity": 4,
            }
        ]
    }


# trace: FR-021
def test_add_line_rejects_stock_unit_with_zero_quantity(buyer):
    """E-021-06：在庫数量0の在庫単位は必ず在庫不足とする。"""
    unit = make_stock_unit(make_item(), quantity=0)

    with pytest.raises(InsufficientStock):
        services.add_line(buyer, {"stock_unit_id": unit.pk, "quantity": 1})


# trace: FR-021
@pytest.mark.parametrize(
    ("payload", "expected_fields"),
    [
        ({}, {"stock_unit_id", "quantity"}),
        ({"stock_unit_id": "abc", "quantity": 1}, {"stock_unit_id"}),
        ({"stock_unit_id": 1, "quantity": 0}, {"quantity"}),
        ({"stock_unit_id": 1, "quantity": "-1"}, {"quantity"}),
        ({"stock_unit_id": 1, "quantity": "two"}, {"quantity"}),
    ],
)
def test_add_line_reports_invalid_input(buyer, payload, expected_fields):
    """E-021-03：在庫単位ID・数量の条件を満たさない全項目を通知する。"""
    with pytest.raises(ValidationFailed) as error:
        services.add_line(buyer, payload)

    assert {detail["field"] for detail in error.value.details} == expected_fields
    assert Cart.objects.count() == 0


# trace: FR-021
def test_add_line_rejects_stock_unit_of_non_public_item(buyer):
    """E-021-04：非公開商品の在庫単位は対象なしとする。"""
    unit = make_stock_unit(make_item(is_public=False))

    with pytest.raises(NotFoundError):
        services.add_line(buyer, {"stock_unit_id": unit.pk, "quantity": 1})


# trace: FR-022
def test_change_line_quantity_updates_quantity(buyer):
    """FR-022：指定した明細の数量を入力値に変更する。"""
    unit = make_stock_unit(make_item(), quantity=10)
    view = services.add_line(buyer, {"stock_unit_id": unit.pk, "quantity": 1})
    line = view["lines"][0]

    updated = services.change_line_quantity(buyer, str(line.pk), {"quantity": "4"})

    assert updated["lines"][0].quantity == 4


# trace: FR-022
def test_change_line_quantity_rejects_quantity_over_limit(buyer):
    """E-022-05：数量11は上限超過とする（境界値）。"""
    unit = make_stock_unit(make_item(), quantity=20)
    line = services.add_line(buyer, {"stock_unit_id": unit.pk, "quantity": 1})["lines"][0]

    with pytest.raises(QuantityLimitExceeded) as error:
        services.change_line_quantity(buyer, line.pk, {"quantity": 11})

    assert error.value.context["requested_quantity"] == 11
    assert CartLine.objects.get(pk=line.pk).quantity == 1


# trace: FR-022
def test_change_line_quantity_rejects_quantity_over_stock(buyer):
    """E-022-06：在庫数量を超える数量は在庫不足とする。"""
    unit = make_stock_unit(make_item(), quantity=3, sku="SKU-LIMIT")
    line = services.add_line(buyer, {"stock_unit_id": unit.pk, "quantity": 1})["lines"][0]

    with pytest.raises(InsufficientStock) as error:
        services.change_line_quantity(buyer, line.pk, {"quantity": 4})

    assert error.value.context["shortages"][0]["available_quantity"] == 3


# trace: FR-022
@pytest.mark.parametrize("quantity", [0, "", "abc", -1])
def test_change_line_quantity_rejects_invalid_quantity(buyer, quantity):
    """E-022-03：数量が1以上の整数でない場合は入力エラーとする。"""
    unit = make_stock_unit(make_item(), quantity=10)
    line = services.add_line(buyer, {"stock_unit_id": unit.pk, "quantity": 1})["lines"][0]

    with pytest.raises(ValidationFailed):
        services.change_line_quantity(buyer, line.pk, {"quantity": quantity})

    assert CartLine.objects.get(pk=line.pk).quantity == 1


# trace: FR-023
def test_delete_line_removes_only_target_line(buyer):
    """FR-023：指定した明細だけを削除し、クーポンの適用は変更しない。"""
    coupon = make_coupon()
    unit_a = make_stock_unit(make_item(), quantity=10, price=5000)
    unit_b = make_stock_unit(make_item(), quantity=10)
    services.add_line(buyer, {"stock_unit_id": unit_a.pk, "quantity": 1})
    view = services.add_line(buyer, {"stock_unit_id": unit_b.pk, "quantity": 1})
    cart = view["cart"]
    cart.coupon = coupon
    cart.save(update_fields=["coupon"])
    target = [line for line in view["lines"] if line.stock_unit_id == unit_b.pk][0]

    result = services.delete_line(buyer, target.pk)

    assert [line.stock_unit_id for line in result["lines"]] == [unit_a.pk]
    assert result["cart"].coupon_id == coupon.pk


# trace: NFR-SC-03
def test_find_own_line_rejects_other_buyers_line(buyer):
    """CMN-18：他の購入者のカート明細は対象なしとする（存在有無を明かさない）。"""
    other = make_user(email="other@example.test")
    unit = make_stock_unit(make_item(), quantity=10)
    line = services.add_line(other, {"stock_unit_id": unit.pk, "quantity": 1})["lines"][0]

    with pytest.raises(NotFoundError):
        services.find_own_line(buyer, line.pk)


# trace: FR-023
@pytest.mark.parametrize("cart_line_id", ["abc", 999999])
def test_delete_line_rejects_unknown_line(buyer, cart_line_id):
    """E-023-04：該当しない明細IDは対象なしとする。"""
    with pytest.raises(NotFoundError):
        services.delete_line(buyer, cart_line_id)


# trace: FR-022
def test_change_line_quantity_rejects_line_of_converted_cart(buyer):
    """注文済カートの明細は変更できない（ST-CART-02）。"""
    unit = make_stock_unit(make_item(), quantity=10)
    view = services.add_line(buyer, {"stock_unit_id": unit.pk, "quantity": 1})
    services.mark_converted(view["cart"], timeutils.now())

    with pytest.raises(NotFoundError):
        services.change_line_quantity(buyer, view["lines"][0].pk, {"quantity": 2})


# trace: FR-024
def test_apply_coupon_sets_coupon_on_cart(buyer):
    """FR-024：有効なクーポンを利用中カートへ適用する。"""
    coupon = make_coupon(code="SAVE-1000", discount_value=1000, min_spend=0)
    unit = make_stock_unit(make_item(), price=6000, quantity=10)
    services.add_line(buyer, {"stock_unit_id": unit.pk, "quantity": 1})

    view = services.apply_coupon(buyer, {"code": " save-1000 "})

    assert view["cart"].coupon_id == coupon.pk
    assert view["is_applicable"] is True
    assert view["amounts"]["discount_amount"] == 1000


# trace: FR-024
def test_apply_coupon_rejects_invalid_code_format(buyer):
    """E-024-03：クーポンコードの形式が条件を満たさない場合は入力エラーとする。"""
    with pytest.raises(ValidationFailed) as error:
        services.apply_coupon(buyer, {"code": "invalid code!"})

    assert error.value.details[0]["field"] == "code"


# trace: FR-024
def test_apply_coupon_rejects_empty_cart(buyer):
    """E-024-04：カートが空の場合はクーポンを適用できない。"""
    make_coupon(code="EMPTYCART")
    make_open_cart(buyer)

    with pytest.raises(CartEmpty):
        services.apply_coupon(buyer, {"code": "EMPTYCART"})


# trace: FR-024
def test_apply_coupon_rejects_when_cart_is_absent(buyer):
    """利用中カートがない場合もカートが空として扱う。"""
    with pytest.raises(CartEmpty):
        services.apply_coupon(buyer, {"code": "NOCART"})


# trace: FR-024
def test_apply_coupon_rejects_second_coupon(buyer):
    """E-024-05：クーポンは1カートにつき1枚までとする。"""
    make_coupon(code="FIRST-ONE")
    make_coupon(code="SECOND-ONE")
    unit = make_stock_unit(make_item(), price=5000, quantity=10)
    services.add_line(buyer, {"stock_unit_id": unit.pk, "quantity": 1})
    services.apply_coupon(buyer, {"code": "FIRST-ONE"})

    with pytest.raises(CouponAlreadyApplied):
        services.apply_coupon(buyer, {"code": "SECOND-ONE"})


# trace: FR-024
def test_apply_coupon_rejects_unknown_code(buyer):
    """E-024-06：存在しないクーポンコードは業務エラーとする。"""
    unit = make_stock_unit(make_item(), quantity=10)
    services.add_line(buyer, {"stock_unit_id": unit.pk, "quantity": 1})

    with pytest.raises(CouponNotFound):
        services.apply_coupon(buyer, {"code": "NOT-EXIST"})


# trace: FR-024
def test_apply_coupon_rejects_coupon_before_valid_period(buyer):
    """E-024-07：有効期間の開始前は有効期間を通知する。"""
    now = timeutils.now()
    make_coupon(
        code="FUTURE-1",
        valid_from=now + dt.timedelta(days=1),
        valid_until=now + dt.timedelta(days=2),
    )
    unit = make_stock_unit(make_item(), quantity=10)
    services.add_line(buyer, {"stock_unit_id": unit.pk, "quantity": 1})

    with pytest.raises(CouponNotYetValid) as error:
        services.apply_coupon(buyer, {"code": "FUTURE-1"})

    assert set(error.value.context) == {"valid_from", "valid_until"}


# trace: FR-024
def test_apply_coupon_rejects_expired_coupon(buyer):
    """E-024-08：有効期間の終了後は期限切れとする。"""
    now = timeutils.now()
    make_coupon(
        code="PAST-1",
        valid_from=now - dt.timedelta(days=2),
        valid_until=now - dt.timedelta(days=1),
    )
    unit = make_stock_unit(make_item(), quantity=10)
    services.add_line(buyer, {"stock_unit_id": unit.pk, "quantity": 1})

    with pytest.raises(CouponExpired):
        services.apply_coupon(buyer, {"code": "PAST-1"})


# trace: FR-024
def test_apply_coupon_rejects_subtotal_below_minimum_spend(buyer):
    """E-024-09：小計が最低購入金額未満の場合は最低購入金額と小計を通知する。"""
    make_coupon(code="MIN-3000", min_spend=3000)
    unit = make_stock_unit(make_item(), price=1000, quantity=10)
    services.add_line(buyer, {"stock_unit_id": unit.pk, "quantity": 2})

    with pytest.raises(CouponMinSpendNotMet) as error:
        services.apply_coupon(buyer, {"code": "MIN-3000"})

    assert error.value.context == {"min_spend": 3000, "subtotal": 2000}


# trace: FR-024
def test_apply_coupon_accepts_subtotal_equal_to_minimum_spend(buyer):
    """FR-024：小計＝最低購入金額は適用できる（境界値）。"""
    make_coupon(code="MIN-2000", min_spend=2000, discount_type=DISCOUNT_PERCENTAGE, discount_value=10)
    unit = make_stock_unit(make_item(), price=1000, quantity=10)
    services.add_line(buyer, {"stock_unit_id": unit.pk, "quantity": 2})

    view = services.apply_coupon(buyer, {"code": "MIN-2000"})

    assert view["amounts"]["discount_amount"] == 200


# trace: FR-025
def test_remove_coupon_clears_applied_coupon(buyer):
    """FR-025：適用中のクーポンを解除する。"""
    make_coupon(code="REMOVE-1")
    unit = make_stock_unit(make_item(), price=5000, quantity=10)
    services.add_line(buyer, {"stock_unit_id": unit.pk, "quantity": 1})
    services.apply_coupon(buyer, {"code": "REMOVE-1"})

    view = services.remove_coupon(buyer)

    assert view["cart"].coupon_id is None
    assert view["is_applicable"] is None


# trace: FR-025
def test_remove_coupon_succeeds_without_applied_coupon(buyer):
    """FR-025：クーポン未適用でも正常終了する。"""
    view = services.remove_coupon(buyer)

    assert view["cart"].coupon_id is None
    assert Cart.objects.filter(user=buyer, status=CART_OPEN).count() == 1


# trace: FR-020
def test_cart_view_reports_coupon_not_applicable_reason(buyer):
    """FR-020 6.8.5：適用不可のクーポンは適用可否と理由を返す（自動では外さない）。"""
    coupon = make_coupon(code="MINHIGH-1", min_spend=100000)
    unit = make_stock_unit(make_item(), price=1000, quantity=10)
    services.add_line(buyer, {"stock_unit_id": unit.pk, "quantity": 1})
    cart = Cart.objects.get(user=buyer, status=CART_OPEN)
    cart.coupon = coupon
    cart.save(update_fields=["coupon"])

    view = services.show_cart(buyer)

    assert view["is_applicable"] is False
    assert view["not_applicable_reason"] == services.REASON_MIN_SPEND
    assert view["cart"].coupon_id == coupon.pk


# trace: FR-030
def test_mark_converted_changes_cart_status(buyer):
    """ST-CART-02：注文確定の成功時にカートを注文済へ変更する。"""
    cart = make_open_cart(buyer)
    at = timeutils.now()

    services.mark_converted(cart, at)

    cart.refresh_from_db()
    assert cart.status == CART_CONVERTED
    assert cart.converted_at == at


# trace: FR-021
def test_lock_stock_units_returns_units_by_identifier(buyer):
    """ADDR-003 INV-004：在庫単位は識別子の昇順でロックして取得する。"""
    first = make_stock_unit(make_item(), quantity=5)
    second = make_stock_unit(make_item(), quantity=5)

    locked = services.lock_stock_units([second.pk, first.pk, second.pk])

    assert set(locked) == {first.pk, second.pk}


# trace: FR-020
def test_get_or_create_open_cart_returns_existing_cart_on_conflict(buyer, monkeypatch):
    """DQ-09：同時実行で作成が競合した場合も利用中カートは1件のままとする。"""
    from django.db import IntegrityError

    existing = make_open_cart(buyer)
    calls = {"count": 0}

    def fail_create(**kwargs):
        calls["count"] += 1
        raise IntegrityError("duplicate key value violates unique constraint uq_cart_open_per_user")

    monkeypatch.setattr(Cart.objects, "create", fail_create)
    monkeypatch.setattr(services, "get_open_cart", lambda user: None if calls["count"] == 0 else existing)

    cart = services.get_or_create_open_cart(buyer)

    assert cart.pk == existing.pk
