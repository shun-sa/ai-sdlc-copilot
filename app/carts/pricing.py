# trace: ADDR-012, ENT-007, ENT-008, ENT-010
"""注文金額計算（FR-026）。画面と Web API で共通の業務処理として同じ規則で算出する（ADDR-012 INV-001）。

小計・割引額・割引後小計・送料・消費税額・合計と、適用中クーポンの適用可否を整数の円で算出する。
データを更新しない。同じ入力と計算時刻に対しては同じ結果を返す。
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from common import codes
from common.codes import DiscountType
from common.tax import consumption_tax

FREE_SHIPPING_THRESHOLD = 5000
SHIPPING_FEE = 500


# trace: ADDR-012, ENT-008
@dataclass(frozen=True)
class Amounts:
    subtotal: int
    discount_amount: int
    discounted_subtotal: int
    shipping_fee: int
    tax_amount: int
    total_amount: int
    is_coupon_applicable: bool | None
    not_applicable_reason: str | None

    def as_dict(self) -> dict[str, int]:
        return {
            "subtotal": self.subtotal,
            "discount_amount": self.discount_amount,
            "discounted_subtotal": self.discounted_subtotal,
            "shipping_fee": self.shipping_fee,
            "tax_amount": self.tax_amount,
            "total_amount": self.total_amount,
        }


# trace: ADDR-012, ENT-007
def coupon_period_state(coupon: Any, at: datetime) -> str | None:
    """有効期間の判定（有効開始日時≦計算時刻≦有効終了日時、両端を含む。秒単位）。"""
    moment = at.replace(microsecond=0)
    if moment < coupon.valid_from:
        return codes.NOT_APPLICABLE_NOT_YET_VALID
    if moment > coupon.valid_to:
        return codes.NOT_APPLICABLE_EXPIRED
    return None


# trace: ADDR-012, ENT-007, ENT-010
def calculate(lines: list[tuple[int, int]], coupon: Any | None, at: datetime) -> Amounts:
    """FR-026 手順1〜8。lines は（現在の税抜単価, 数量）の並び。"""
    if not lines:
        reason = codes.NOT_APPLICABLE_EMPTY_CART if coupon is not None else None
        return Amounts(0, 0, 0, 0, 0, 0, False if coupon is not None else None, reason)
    subtotal = sum(price * quantity for price, quantity in lines)
    discount = 0
    applicable: bool | None = None
    reason: str | None = None
    if coupon is not None:
        reason = coupon_period_state(coupon, at)
        if reason is None and subtotal < coupon.minimum_purchase_amount:
            reason = codes.NOT_APPLICABLE_BELOW_MINIMUM
        if reason is None:
            if coupon.discount_type == DiscountType.FIXED_AMOUNT:
                discount = min(coupon.discount_value, subtotal)
            else:
                discount = subtotal * coupon.discount_value // 100
            applicable = True
        else:
            applicable = False
    discounted = max(subtotal - discount, 0)
    shipping = 0 if discounted >= FREE_SHIPPING_THRESHOLD else SHIPPING_FEE
    tax = consumption_tax(discounted + shipping)
    total = discounted + shipping + tax
    return Amounts(subtotal, discount, discounted, shipping, tax, total, applicable, reason)
