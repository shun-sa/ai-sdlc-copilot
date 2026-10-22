# trace: FR-026, ADDR-007
"""注文金額計算（FR-026）の単体テスト。

期待値は FR-026 6.14.4 の手順1〜8と計算例から導出する。
"""
from datetime import datetime, timedelta

import pytest
from django.utils import timezone

from shop.models import Coupon, DiscountType
from shop.services.amounts import (
    REASON_CART_EMPTY,
    REASON_EXPIRED,
    REASON_MIN_SPEND_NOT_MET,
    REASON_NOT_YET_VALID,
    AmountLine,
    calculate_amounts,
    calculate_discount_amount,
    coupon_not_applicable_reason,
    tax_included_price,
)


# trace: FR-026
def _at():
    """計算時刻（固定値。現在時刻へ依存しない）を返す。"""
    return timezone.make_aware(datetime(2026, 5, 1, 12, 0, 0), timezone.get_current_timezone())


# trace: FR-026
def _coupon(discount_type=DiscountType.FIXED, discount_value=1000, min_spend=0, days_before=1, days_after=1):
    """永続化しないクーポン（DB非依存）を組み立てる。"""
    at = _at()
    return Coupon(
        code="TESTCOUPON",
        name="試験用クーポン",
        discount_type=discount_type,
        discount_value=discount_value,
        min_spend=min_spend,
        valid_from=at - timedelta(days=days_before),
        valid_until=at + timedelta(days=days_after),
    )


# trace: FR-026
@pytest.mark.parametrize(
    ("subtotal", "expected"),
    [
        # FR-026 計算例1：小計5,000円・クーポンなし
        (5000, {"shipping_fee": 0, "tax_amount": 500, "total": 5500}),
        # FR-026 計算例2：小計4,999円・クーポンなし
        (4999, {"shipping_fee": 500, "tax_amount": 549, "total": 6048}),
    ],
)
def test_calculate_amounts_without_coupon_matches_requirement_examples(subtotal, expected):
    """クーポンなしの金額内訳が FR-026 の計算例と一致する。"""
    result = calculate_amounts([AmountLine(unit_price=subtotal, quantity=1)], None, _at())

    assert result.subtotal == subtotal
    assert result.discount_amount == 0
    assert result.discounted_subtotal == subtotal
    assert result.shipping_fee == expected["shipping_fee"]
    assert result.tax_amount == expected["tax_amount"]
    assert result.total == expected["total"]
    assert result.is_applicable is None
    assert result.not_applicable_reason is None


# trace: FR-026
def test_calculate_amounts_percentage_coupon_matches_requirement_example():
    """定率クーポン（計算例3）の割引額は1円未満切り捨てで算出される。"""
    coupon = _coupon(discount_type=DiscountType.PERCENTAGE, discount_value=10)

    result = calculate_amounts([AmountLine(unit_price=5550, quantity=1)], coupon, _at())

    assert (result.subtotal, result.discount_amount, result.discounted_subtotal) == (5550, 555, 4995)
    assert (result.shipping_fee, result.tax_amount, result.total) == (500, 549, 6044)
    assert result.is_applicable is True
    assert result.not_applicable_reason is None


# trace: FR-026
def test_calculate_amounts_fixed_coupon_matches_requirement_example():
    """定額クーポン（計算例4）で割引後小計が送料無料の境界値となる。"""
    coupon = _coupon(discount_type=DiscountType.FIXED, discount_value=1000)

    result = calculate_amounts([AmountLine(unit_price=6000, quantity=1)], coupon, _at())

    assert (result.discount_amount, result.discounted_subtotal) == (1000, 5000)
    assert (result.shipping_fee, result.tax_amount, result.total) == (0, 500, 5500)
    assert result.is_applicable is True


# trace: FR-026
def test_calculate_amounts_fixed_coupon_is_capped_by_subtotal():
    """定額クーポンの割引額は min（割引値, 小計）となる（計算例5）。"""
    coupon = _coupon(discount_type=DiscountType.FIXED, discount_value=1000)

    result = calculate_amounts([AmountLine(unit_price=800, quantity=1)], coupon, _at())

    assert (result.discount_amount, result.discounted_subtotal) == (800, 0)
    assert (result.shipping_fee, result.tax_amount, result.total) == (500, 50, 550)


# trace: FR-026
def test_calculate_amounts_percentage_coupon_truncates_fraction():
    """定率15%の割引額は299.85円を切り捨てて299円となる（計算例6）。"""
    coupon = _coupon(discount_type=DiscountType.PERCENTAGE, discount_value=15)

    result = calculate_amounts([AmountLine(unit_price=1999, quantity=1)], coupon, _at())

    assert (result.discount_amount, result.discounted_subtotal) == (299, 1700)
    assert (result.shipping_fee, result.tax_amount, result.total) == (500, 220, 2420)


# trace: FR-026
def test_calculate_amounts_empty_cart_with_coupon_returns_cart_empty_reason():
    """明細0件ではすべて0円で、クーポン適用中は適用不可理由が CART_EMPTY となる（計算例7）。"""
    coupon = _coupon()

    result = calculate_amounts([], coupon, _at())

    assert result.as_amounts() == {
        "subtotal": 0,
        "discount_amount": 0,
        "discounted_subtotal": 0,
        "shipping_fee": 0,
        "tax_amount": 0,
        "total": 0,
    }
    assert result.is_applicable is False
    assert result.not_applicable_reason == REASON_CART_EMPTY


# trace: FR-026
def test_calculate_amounts_empty_cart_without_coupon_has_no_reason():
    """明細0件でクーポン未適用の場合は適用可否・適用不可理由を返さない。"""
    result = calculate_amounts([], None, _at())

    assert result.total == 0
    assert result.is_applicable is None
    assert result.not_applicable_reason is None


# trace: FR-026
@pytest.mark.parametrize(
    ("discounted_subtotal_price", "expected_shipping_fee"),
    [(4999, 500), (5000, 0), (5001, 0)],
)
def test_shipping_fee_boundary_at_five_thousand_yen(discounted_subtotal_price, expected_shipping_fee):
    """送料は割引後小計5,000円以上で0円、5,000円未満で500円となる（境界値）。"""
    result = calculate_amounts([AmountLine(unit_price=discounted_subtotal_price, quantity=1)], None, _at())

    assert result.shipping_fee == expected_shipping_fee


# trace: FR-026
def test_calculate_amounts_sums_multiple_lines():
    """小計は Σ（税抜単価×数量）で求める。"""
    lines = [AmountLine(unit_price=1200, quantity=3), AmountLine(unit_price=500, quantity=2)]

    result = calculate_amounts(lines, None, _at())

    assert result.subtotal == 1200 * 3 + 500 * 2


# trace: FR-026
def test_coupon_before_valid_from_is_not_applicable():
    """計算時刻が有効開始日時より前のクーポンは COUPON_NOT_YET_VALID となる。"""
    at = _at()
    coupon = _coupon()
    coupon.valid_from = at + timedelta(seconds=1)
    coupon.valid_until = at + timedelta(days=1)

    result = calculate_amounts([AmountLine(unit_price=3000, quantity=1)], coupon, at)

    assert result.discount_amount == 0
    assert result.is_applicable is False
    assert result.not_applicable_reason == REASON_NOT_YET_VALID


# trace: FR-026
def test_coupon_after_valid_until_is_expired():
    """計算時刻が有効終了日時より後のクーポンは COUPON_EXPIRED となる。"""
    at = _at()
    coupon = _coupon()
    coupon.valid_from = at - timedelta(days=2)
    coupon.valid_until = at - timedelta(seconds=1)

    result = calculate_amounts([AmountLine(unit_price=3000, quantity=1)], coupon, at)

    assert result.is_applicable is False
    assert result.not_applicable_reason == REASON_EXPIRED


# trace: FR-026
@pytest.mark.parametrize("offset_seconds", [0, 1])
def test_coupon_period_boundaries_are_inclusive(offset_seconds):
    """有効開始日時・有効終了日時の両端は有効期間に含まれる。"""
    at = _at()
    coupon = _coupon()
    coupon.valid_from = at - timedelta(seconds=offset_seconds)
    coupon.valid_until = at + timedelta(seconds=offset_seconds)

    assert coupon_not_applicable_reason(coupon, 3000, at) is None


# trace: FR-026
@pytest.mark.parametrize(
    ("subtotal", "expected_reason"),
    [(2999, REASON_MIN_SPEND_NOT_MET), (3000, None), (3001, None)],
)
def test_coupon_min_spend_boundary(subtotal, expected_reason):
    """最低購入金額は小計が最低購入金額以上のときに満たされる（境界値）。"""
    coupon = _coupon(min_spend=3000)

    assert coupon_not_applicable_reason(coupon, subtotal, _at()) == expected_reason


# trace: FR-026
def test_coupon_period_is_checked_before_min_spend():
    """有効期間の判定を最低購入金額の判定より先に行う（FR-026 手順3）。"""
    at = _at()
    coupon = _coupon(min_spend=10000)
    coupon.valid_from = at + timedelta(days=1)
    coupon.valid_until = at + timedelta(days=2)

    assert coupon_not_applicable_reason(coupon, 100, at) == REASON_NOT_YET_VALID


# trace: FR-026
@pytest.mark.parametrize(
    ("discount_type", "discount_value", "subtotal", "expected"),
    [
        (DiscountType.FIXED, 1000, 5000, 1000),
        (DiscountType.FIXED, 1000, 800, 800),
        (DiscountType.PERCENTAGE, 10, 5550, 555),
        (DiscountType.PERCENTAGE, 100, 1234, 1234),
    ],
)
def test_calculate_discount_amount(discount_type, discount_value, subtotal, expected):
    """割引額は定額＝min（割引値, 小計）、定率＝小計×割引率÷100 の切り捨てで求める。"""
    coupon = _coupon(discount_type=discount_type, discount_value=discount_value)

    assert calculate_discount_amount(coupon, subtotal) == expected


# trace: FR-026
@pytest.mark.parametrize(("price", "expected"), [(0, 0), (1, 1), (999, 1098), (1000, 1100), (1234, 1357)])
def test_tax_included_price_truncates_fraction(price, expected):
    """税込価格は税抜価格×110÷100 の1円未満切り捨てで求める（CMN-32）。"""
    assert tax_included_price(price) == expected
