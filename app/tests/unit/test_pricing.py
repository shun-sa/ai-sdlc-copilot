# trace: FR-026, ADDR-012
"""FR-026 注文金額計算（carts.pricing・common.tax）の単体テスト。

期待値は functional_requirements.md 6.14.4 の手順1〜8 と計算例1〜7、CMN-29〜CMN-32 から導出する。
DB を使わない純粋な計算（DB Test Strategy：NOT_APPLICABLE）。
"""

from dataclasses import dataclass
from datetime import datetime

import pytest

from carts import pricing
from common import tax
from tests.unit.conftest import jst

AT = jst(2027, 4, 15, 12, 0, 0)


# trace: FR-026, ADDR-012
@dataclass(frozen=True)
class _Coupon:
    discount_type: str
    discount_value: int
    minimum_purchase_amount: int = 0
    valid_from: datetime = jst(2027, 4, 1, 0, 0, 0)
    valid_to: datetime = jst(2027, 4, 30, 23, 59, 59)


# trace: FR-026, ADDR-012
@pytest.mark.parametrize(
    ("lines", "coupon", "expected"),
    [
        # 例1：小計5,000円・クーポンなし
        ([(5000, 1)], None, (5000, 0, 5000, 0, 500, 5500)),
        # 例2：小計4,999円・クーポンなし（送料500円、消費税549.9の切捨て）
        ([(4999, 1)], None, (4999, 0, 4999, 500, 549, 6048)),
        # 例3：小計5,550円・定率10%
        ([(1850, 3)], _Coupon("percentage", 10), (5550, 555, 4995, 500, 549, 6044)),
        # 例4：小計6,000円・定額1,000円
        ([(2000, 3)], _Coupon("fixed_amount", 1000), (6000, 1000, 5000, 0, 500, 5500)),
        # 例5：小計800円・定額1,000円（min(1000,800)）
        ([(800, 1)], _Coupon("fixed_amount", 1000), (800, 800, 0, 500, 50, 550)),
        # 例6：小計1,999円・定率15%（299.85の切捨て）
        ([(1999, 1)], _Coupon("percentage", 15), (1999, 299, 1700, 500, 220, 2420)),
    ],
    ids=["example1", "example2", "example3", "example4", "example5", "example6"],
)
def test_calculate_matches_requirement_examples(lines, coupon, expected):
    amounts = pricing.calculate(lines, coupon, AT)
    assert (
        amounts.subtotal,
        amounts.discount_amount,
        amounts.discounted_subtotal,
        amounts.shipping_fee,
        amounts.tax_amount,
        amounts.total_amount,
    ) == expected
    if coupon is not None:
        assert amounts.is_coupon_applicable is True
        assert amounts.not_applicable_reason is None
    else:
        assert amounts.is_coupon_applicable is None


# trace: FR-026, ADDR-012
def test_calculate_example7_empty_cart_with_coupon_is_all_zero_and_not_applicable():
    amounts = pricing.calculate([], _Coupon("fixed_amount", 1000), AT)
    assert amounts.as_dict() == {
        "subtotal": 0,
        "discount_amount": 0,
        "discounted_subtotal": 0,
        "shipping_fee": 0,
        "tax_amount": 0,
        "total_amount": 0,
    }
    assert amounts.is_coupon_applicable is False
    assert amounts.not_applicable_reason == "empty_cart"


# trace: FR-026, ADDR-012
def test_calculate_empty_cart_without_coupon_has_no_applicability():
    amounts = pricing.calculate([], None, AT)
    assert amounts.total_amount == 0
    assert amounts.is_coupon_applicable is None
    assert amounts.not_applicable_reason is None


# trace: FR-026, ADDR-012
def test_subtotal_is_sum_of_price_times_quantity_over_all_lines():
    amounts = pricing.calculate([(1200, 2), (350, 3), (1, 10)], None, AT)
    assert amounts.subtotal == 1200 * 2 + 350 * 3 + 10


# trace: FR-026, ADDR-012
@pytest.mark.parametrize(
    ("discounted", "shipping"),
    [(4999, 500), (5000, 0), (5001, 0)],
    ids=["below-threshold", "threshold", "above-threshold"],
)
def test_shipping_fee_boundary_on_discounted_subtotal_5000(discounted, shipping):
    amounts = pricing.calculate([(discounted, 1)], None, AT)
    assert amounts.shipping_fee == shipping


# trace: FR-026, ADDR-012
def test_shipping_is_judged_on_discounted_subtotal_not_subtotal():
    # 小計5,400円・定額500円引き → 割引後小計4,900円 → 送料500円
    amounts = pricing.calculate([(5400, 1)], _Coupon("fixed_amount", 500), AT)
    assert amounts.discounted_subtotal == 4900
    assert amounts.shipping_fee == 500
    assert amounts.tax_amount == (4900 + 500) * 10 // 100


# trace: FR-026, ADDR-012
@pytest.mark.parametrize(
    ("moment", "reason"),
    [
        (jst(2027, 3, 31, 23, 59, 59), "not_yet_valid"),
        (jst(2027, 4, 1, 0, 0, 0), None),
        (jst(2027, 4, 30, 23, 59, 59), None),
        (jst(2027, 5, 1, 0, 0, 0), "expired"),
    ],
    ids=["before-start", "start-inclusive", "end-inclusive", "after-end"],
)
def test_coupon_period_boundaries_are_inclusive(moment, reason):
    coupon = _Coupon("fixed_amount", 100)
    amounts = pricing.calculate([(3000, 1)], coupon, moment)
    assert amounts.not_applicable_reason == reason
    if reason is None:
        assert amounts.is_coupon_applicable is True
        assert amounts.discount_amount == 100
    else:
        assert amounts.is_coupon_applicable is False
        assert amounts.discount_amount == 0


# trace: FR-026, ADDR-012
def test_coupon_period_ignores_milliseconds_at_end_boundary():
    """CMN-29：23:59:59.900 は秒単位で 23:59:59 として有効。"""
    coupon = _Coupon("fixed_amount", 100)
    moment = jst(2027, 4, 30, 23, 59, 59).replace(microsecond=900000)
    assert pricing.coupon_period_state(coupon, moment) is None


# trace: FR-026, ADDR-012
@pytest.mark.parametrize(
    ("subtotal", "applicable"),
    [(2999, False), (3000, True), (3001, True)],
    ids=["below-minimum", "minimum", "above-minimum"],
)
def test_minimum_purchase_amount_boundary(subtotal, applicable):
    coupon = _Coupon("fixed_amount", 100, minimum_purchase_amount=3000)
    amounts = pricing.calculate([(subtotal, 1)], coupon, AT)
    assert amounts.is_coupon_applicable is applicable
    assert amounts.discount_amount == (100 if applicable else 0)
    assert amounts.not_applicable_reason == (None if applicable else "below_minimum_purchase_amount")


# trace: FR-026, ADDR-012
def test_period_is_judged_before_minimum_purchase_amount():
    """手順3：①有効期間を先に判定する（期間外かつ最低購入金額未満は期間の理由）。"""
    coupon = _Coupon("fixed_amount", 100, minimum_purchase_amount=99999)
    amounts = pricing.calculate([(100, 1)], coupon, jst(2027, 5, 1))
    assert amounts.not_applicable_reason == "expired"


# trace: FR-026, ADDR-012
def test_percentage_100_discount_makes_discounted_subtotal_zero():
    amounts = pricing.calculate([(3333, 1)], _Coupon("percentage", 100), AT)
    assert amounts.discount_amount == 3333
    assert amounts.discounted_subtotal == 0
    assert amounts.shipping_fee == 500
    assert amounts.total_amount == 500 + 50


# trace: FR-026, ADDR-012
def test_amounts_invariants_hold():
    """6.14.6：割引後小計＝小計−割引額、合計＝割引後小計＋送料＋消費税額、全て0以上の整数。"""
    for lines, coupon in [
        ([(123, 7)], _Coupon("percentage", 33)),
        ([(9999999, 10)], _Coupon("fixed_amount", 9999999)),
        ([(1, 1)], None),
    ]:
        a = pricing.calculate(lines, coupon, AT)
        assert a.discounted_subtotal == a.subtotal - a.discount_amount
        assert a.total_amount == a.discounted_subtotal + a.shipping_fee + a.tax_amount
        assert all(isinstance(v, int) and v >= 0 for v in a.as_dict().values())


# trace: FR-026, ADDR-012
def test_calculate_is_deterministic_for_same_input_and_time():
    coupon = _Coupon("percentage", 7)
    assert pricing.calculate([(1234, 3)], coupon, AT) == pricing.calculate([(1234, 3)], coupon, AT)


# trace: FR-026, ADDR-012
@pytest.mark.parametrize(("excluding", "including"), [(1000, 1100), (999, 1098), (1, 1), (0, 0), (9999999, 10999998)])
def test_price_including_tax_truncates_below_one_yen(excluding, including):
    """CMN-32：税込価格＝税抜価格×110÷100 の1円未満切り捨て。"""
    assert tax.price_including_tax(excluding) == including


# trace: FR-026, ADDR-012
@pytest.mark.parametrize(("taxable", "expected"), [(5499, 549), (5495, 549), (10, 1), (9, 0)])
def test_consumption_tax_truncates_below_one_yen(taxable, expected):
    """CMN-31：消費税額＝課税対象額×10÷100 の1円未満切り捨て。"""
    assert tax.consumption_tax(taxable) == expected
