# trace: FR-026, FR-020, FR-024, ADDR-008
"""FR-026 注文金額計算の単体テスト（機能要件 6.14.4 の手順1〜8と計算例1〜7）。

期待結果は機能要件定義書 6.14.4（計算例）およびクーポンの両端を含む有効期間の定義から導出する。
DBは使用しない（金額計算は在庫単位の価格とクーポンの値だけを入力とする純粋な計算である）。
"""

from __future__ import annotations

import datetime as dt

import pytest
from carts.models import DISCOUNT_FIXED, DISCOUNT_PERCENTAGE, Coupon
from carts.services import (
    REASON_CART_EMPTY,
    REASON_EXPIRED,
    REASON_MIN_SPEND,
    REASON_NOT_YET_VALID,
    calculate_amounts,
    discount_for,
)
from common import timeutils

AT = dt.datetime(2027, 4, 10, 12, 0, 0, tzinfo=timeutils.JST)


# trace: FR-026
def build_coupon(
    *,
    discount_type: str = DISCOUNT_FIXED,
    discount_value: int = 1000,
    min_spend: int = 0,
    valid_from: dt.datetime | None = None,
    valid_until: dt.datetime | None = None,
) -> Coupon:
    """判定に用いるクーポン（DBへ保存しない）。"""
    return Coupon(
        code="TEST-COUPON",
        name="試験クーポン",
        discount_type=discount_type,
        discount_value=discount_value,
        min_spend=min_spend,
        valid_from=valid_from or (AT - dt.timedelta(days=1)),
        valid_until=valid_until or (AT + dt.timedelta(days=1)),
    )


# trace: FR-026
def test_example1_subtotal_5000_without_coupon_has_free_shipping():
    """計算例1：小計5,000円・クーポンなし → 送料0円・消費税500円・合計5,500円。"""
    result = calculate_amounts([(5000, 1)], None, AT)

    assert result["amounts"] == {
        "subtotal": 5000,
        "discount_amount": 0,
        "discounted_subtotal": 5000,
        "shipping_fee": 0,
        "tax_amount": 500,
        "total": 5500,
    }
    assert result["is_applicable"] is None
    assert result["not_applicable_reason"] is None


# trace: FR-026
def test_example2_subtotal_4999_charges_shipping_fee():
    """計算例2：小計4,999円 → 送料500円・消費税549円（切り捨て）・合計6,048円。"""
    result = calculate_amounts([(4999, 1)], None, AT)

    assert result["amounts"] == {
        "subtotal": 4999,
        "discount_amount": 0,
        "discounted_subtotal": 4999,
        "shipping_fee": 500,
        "tax_amount": 549,
        "total": 6048,
    }


# trace: FR-026
def test_example3_percentage_coupon_rounds_down_discount():
    """計算例3：小計5,550円・定率10% → 割引555円・送料500円・消費税549円・合計6,044円。"""
    coupon = build_coupon(discount_type=DISCOUNT_PERCENTAGE, discount_value=10)

    result = calculate_amounts([(1850, 3)], coupon, AT)

    assert result["amounts"] == {
        "subtotal": 5550,
        "discount_amount": 555,
        "discounted_subtotal": 4995,
        "shipping_fee": 500,
        "tax_amount": 549,
        "total": 6044,
    }
    assert result["is_applicable"] is True
    assert result["not_applicable_reason"] is None


# trace: FR-026
def test_example4_fixed_coupon_makes_discounted_subtotal_reach_free_shipping():
    """計算例4：小計6,000円・定額1,000円 → 割引後小計5,000円・送料0円・合計5,500円。"""
    coupon = build_coupon(discount_value=1000)

    result = calculate_amounts([(2000, 3)], coupon, AT)

    assert result["amounts"] == {
        "subtotal": 6000,
        "discount_amount": 1000,
        "discounted_subtotal": 5000,
        "shipping_fee": 0,
        "tax_amount": 500,
        "total": 5500,
    }


# trace: FR-026
def test_example5_fixed_discount_is_capped_by_subtotal():
    """計算例5：小計800円・定額1,000円 → 割引額800円（min）・割引後小計0円・合計550円。"""
    coupon = build_coupon(discount_value=1000, min_spend=0)

    result = calculate_amounts([(800, 1)], coupon, AT)

    assert result["amounts"] == {
        "subtotal": 800,
        "discount_amount": 800,
        "discounted_subtotal": 0,
        "shipping_fee": 500,
        "tax_amount": 50,
        "total": 550,
    }


# trace: FR-026
def test_example6_percentage_discount_truncates_fraction():
    """計算例6：小計1,999円・定率15% → 割引299円（299.85の切り捨て）・合計2,420円。"""
    coupon = build_coupon(discount_type=DISCOUNT_PERCENTAGE, discount_value=15)

    result = calculate_amounts([(1999, 1)], coupon, AT)

    assert result["amounts"] == {
        "subtotal": 1999,
        "discount_amount": 299,
        "discounted_subtotal": 1700,
        "shipping_fee": 500,
        "tax_amount": 220,
        "total": 2420,
    }


# trace: FR-026
def test_example7_empty_cart_with_coupon_reports_cart_empty():
    """計算例7：明細0件・クーポン適用中 → 全額0円、適用可否＝不可、理由＝CART_EMPTY。"""
    result = calculate_amounts([], build_coupon(), AT)

    assert result["amounts"] == {
        "subtotal": 0,
        "discount_amount": 0,
        "discounted_subtotal": 0,
        "shipping_fee": 0,
        "tax_amount": 0,
        "total": 0,
    }
    assert result["is_applicable"] is False
    assert result["not_applicable_reason"] == REASON_CART_EMPTY


# trace: FR-026
def test_empty_cart_without_coupon_has_no_applicability():
    """明細0件・クーポン未適用 → 全額0円、適用可否は判定しない。"""
    result = calculate_amounts([], None, AT)

    assert result["amounts"]["total"] == 0
    assert result["is_applicable"] is None
    assert result["not_applicable_reason"] is None


# trace: FR-026
@pytest.mark.parametrize(
    ("subtotal", "expected_shipping"),
    [(4999, 500), (5000, 0), (5001, 0)],
)
def test_free_shipping_boundary_is_5000_yen_inclusive(subtotal, expected_shipping):
    """送料は割引後小計5,000円以上で0円（境界値：4,999／5,000／5,001）。"""
    result = calculate_amounts([(subtotal, 1)], None, AT)

    assert result["amounts"]["shipping_fee"] == expected_shipping


# trace: FR-026
@pytest.mark.parametrize(
    ("at", "expected_applicable", "expected_reason"),
    [
        (AT - dt.timedelta(seconds=1), False, REASON_NOT_YET_VALID),
        (AT, True, None),
        (AT + dt.timedelta(days=1), True, None),
        (AT + dt.timedelta(days=1, seconds=1), False, REASON_EXPIRED),
    ],
)
def test_coupon_period_boundaries_include_both_ends(at, expected_applicable, expected_reason):
    """有効期間は両端を含む（開始前は COUPON_NOT_YET_VALID、終了後は COUPON_EXPIRED）。"""
    coupon = build_coupon(valid_from=AT, valid_until=AT + dt.timedelta(days=1))

    result = calculate_amounts([(5000, 1)], coupon, at)

    assert result["is_applicable"] is expected_applicable
    assert result["not_applicable_reason"] == expected_reason


# trace: FR-026
@pytest.mark.parametrize(
    ("subtotal", "expected_applicable", "expected_reason"),
    [(2999, False, REASON_MIN_SPEND), (3000, True, None), (3001, True, None)],
)
def test_minimum_spend_boundary_is_inclusive(subtotal, expected_applicable, expected_reason):
    """小計≧最低購入金額で適用可（境界値：2,999／3,000／3,001）。"""
    coupon = build_coupon(discount_value=100, min_spend=3000)

    result = calculate_amounts([(subtotal, 1)], coupon, AT)

    assert result["is_applicable"] is expected_applicable
    assert result["not_applicable_reason"] == expected_reason


# trace: FR-026
def test_period_is_checked_before_minimum_spend():
    """①有効期間を先に判定する（期間外かつ最低購入金額未達は期間の理由を返す）。"""
    coupon = build_coupon(
        discount_value=100,
        min_spend=10000,
        valid_from=AT + dt.timedelta(days=1),
        valid_until=AT + dt.timedelta(days=2),
    )

    result = calculate_amounts([(100, 1)], coupon, AT)

    assert result["not_applicable_reason"] == REASON_NOT_YET_VALID


# trace: FR-026
def test_subtotal_sums_price_multiplied_by_quantity_of_every_line():
    """小計＝Σ（税抜価格×数量）。"""
    result = calculate_amounts([(1200, 2), (300, 5)], None, AT)

    assert result["amounts"]["subtotal"] == 1200 * 2 + 300 * 5


# trace: FR-026
@pytest.mark.parametrize(
    ("discount_type", "discount_value", "subtotal", "expected"),
    [
        (DISCOUNT_FIXED, 1000, 6000, 1000),
        (DISCOUNT_FIXED, 1000, 800, 800),
        (DISCOUNT_PERCENTAGE, 10, 5550, 555),
        (DISCOUNT_PERCENTAGE, 15, 1999, 299),
        (DISCOUNT_PERCENTAGE, 100, 1000, 1000),
    ],
)
def test_discount_for_follows_discount_type(discount_type, discount_value, subtotal, expected):
    """割引額：定額＝min（割引値, 小計）、定率＝小計×割引率÷100 の切り捨て。"""
    assert discount_for(discount_type, discount_value, subtotal) == expected


# trace: FR-026
def test_discounted_subtotal_never_goes_below_zero():
    """割引後小計は0円未満にならない（事後条件 6.14.6）。"""
    coupon = build_coupon(discount_type=DISCOUNT_PERCENTAGE, discount_value=100)

    result = calculate_amounts([(2000, 1)], coupon, AT)

    assert result["amounts"]["discounted_subtotal"] == 0
    assert result["amounts"]["total"] == 0 + 500 + 50


# trace: FR-026
def test_amounts_satisfy_postcondition_identities():
    """事後条件：割引後小計＝小計−割引額、合計＝割引後小計＋送料＋消費税額。"""
    coupon = build_coupon(discount_type=DISCOUNT_PERCENTAGE, discount_value=7)

    amounts = calculate_amounts([(1234, 3)], coupon, AT)["amounts"]

    assert amounts["discounted_subtotal"] == amounts["subtotal"] - amounts["discount_amount"]
    assert amounts["total"] == (
        amounts["discounted_subtotal"] + amounts["shipping_fee"] + amounts["tax_amount"]
    )
    assert all(value >= 0 for value in amounts.values())
