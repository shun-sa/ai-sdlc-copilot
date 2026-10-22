# trace: ADDR-007
"""注文金額計算（FR-026）。カートと注文確定から共通に呼び出す単一の業務ロジック。"""
from dataclasses import dataclass
from datetime import datetime

from shop.models import Coupon, DiscountType

TAX_RATE_NUMERATOR = 10
TAX_RATE_DENOMINATOR = 100
TAX_INCLUSIVE_NUMERATOR = 110
SHIPPING_FEE = 500
SHIPPING_FREE_THRESHOLD = 5000

REASON_NOT_YET_VALID = "COUPON_NOT_YET_VALID"
REASON_EXPIRED = "COUPON_EXPIRED"
REASON_MIN_SPEND_NOT_MET = "COUPON_MIN_SPEND_NOT_MET"
REASON_CART_EMPTY = "CART_EMPTY"


# trace: ADDR-007
@dataclass(frozen=True)
class AmountLine:
    """金額計算の対象となる明細（税抜単価と数量）。"""

    unit_price: int
    quantity: int


# trace: ADDR-007
@dataclass(frozen=True)
class AmountResult:
    """金額内訳とクーポンの適用可否（FR-026 の出力）。"""

    subtotal: int
    discount_amount: int
    discounted_subtotal: int
    shipping_fee: int
    tax_amount: int
    total: int
    is_applicable: bool | None
    not_applicable_reason: str | None

    def as_amounts(self) -> dict[str, int]:
        """応答・画面表示に用いる金額内訳を返す。"""
        return {
            "subtotal": self.subtotal,
            "discount_amount": self.discount_amount,
            "discounted_subtotal": self.discounted_subtotal,
            "shipping_fee": self.shipping_fee,
            "tax_amount": self.tax_amount,
            "total": self.total,
        }


# trace: ADDR-007
def tax_included_price(price: int) -> int:
    """税込価格（税抜価格×110÷100 の1円未満切り捨て）を返す（CMN-32）。"""
    return price * TAX_INCLUSIVE_NUMERATOR // TAX_RATE_DENOMINATOR


# trace: ADDR-007
def calculate_amounts(lines: list[AmountLine], coupon: Coupon | None, calculated_at: datetime) -> AmountResult:
    """FR-026 の手順1〜8に従って金額内訳とクーポンの適用可否を算出する。"""
    subtotal = sum(line.unit_price * line.quantity for line in lines)

    if not lines:
        return AmountResult(
            subtotal=0,
            discount_amount=0,
            discounted_subtotal=0,
            shipping_fee=0,
            tax_amount=0,
            total=0,
            is_applicable=False if coupon else None,
            not_applicable_reason=REASON_CART_EMPTY if coupon else None,
        )

    discount_amount = 0
    is_applicable: bool | None = None
    not_applicable_reason: str | None = None

    if coupon is not None:
        reason = coupon_not_applicable_reason(coupon, subtotal, calculated_at)
        if reason is None:
            discount_amount = calculate_discount_amount(coupon, subtotal)
            is_applicable = True
        else:
            is_applicable = False
            not_applicable_reason = reason

    discounted_subtotal = subtotal - discount_amount
    shipping_fee = 0 if discounted_subtotal >= SHIPPING_FREE_THRESHOLD else SHIPPING_FEE
    tax_amount = (discounted_subtotal + shipping_fee) * TAX_RATE_NUMERATOR // TAX_RATE_DENOMINATOR
    total = discounted_subtotal + shipping_fee + tax_amount
    return AmountResult(
        subtotal=subtotal,
        discount_amount=discount_amount,
        discounted_subtotal=discounted_subtotal,
        shipping_fee=shipping_fee,
        tax_amount=tax_amount,
        total=total,
        is_applicable=is_applicable,
        not_applicable_reason=not_applicable_reason,
    )


# trace: ADDR-007
def coupon_not_applicable_reason(coupon: Coupon, subtotal: int, calculated_at: datetime) -> str | None:
    """クーポンの適用不可理由を返す（有効期間→最低購入金額の順で判定する）。"""
    if calculated_at < coupon.valid_from:
        return REASON_NOT_YET_VALID
    if calculated_at > coupon.valid_until:
        return REASON_EXPIRED
    if subtotal < coupon.min_spend:
        return REASON_MIN_SPEND_NOT_MET
    return None


# trace: ADDR-007
def calculate_discount_amount(coupon: Coupon, subtotal: int) -> int:
    """割引額を求める（定額は min(割引値, 小計)、定率は1円未満切り捨て）。"""
    if coupon.discount_type == DiscountType.FIXED:
        return min(coupon.discount_value, subtotal)
    return subtotal * coupon.discount_value // TAX_RATE_DENOMINATOR
