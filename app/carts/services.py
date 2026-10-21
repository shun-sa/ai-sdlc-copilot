# trace: ADDR-003, ADDR-008
"""カート・クーポン・注文金額計算の業務ロジック（FR-020〜FR-026）。

在庫数量の判定は対象の在庫単位行をロックした状態で行い、ロックは
「在庫単位（識別子の昇順）→ カート」の順に取得する（ADDR-003 DD-001, DD-002）。
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from django.db import IntegrityError, transaction

from carts.models import (
    CART_CONVERTED,
    CART_OPEN,
    DISCOUNT_FIXED,
    QUANTITY_LIMIT,
    Cart,
    CartLine,
    Coupon,
)
from catalog.models import StockUnit
from catalog.services import get_public_stock_unit
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
)
from common.validators import (
    COUPON_CODE_PATTERN,
    ValidationCollector,
    normalize_coupon_code,
    parse_int,
)

FREE_SHIPPING_THRESHOLD = 5000
SHIPPING_FEE = 500
TAX_RATE_NUMERATOR = 10
TAX_RATE_DENOMINATOR = 100

REASON_CART_EMPTY = "CART_EMPTY"
REASON_NOT_YET_VALID = "COUPON_NOT_YET_VALID"
REASON_EXPIRED = "COUPON_EXPIRED"
REASON_MIN_SPEND = "COUPON_MIN_SPEND_NOT_MET"


# trace: ADDR-008
def calculate_amounts(
    line_inputs: list[tuple[int, int]],
    coupon: Coupon | None,
    at: dt.datetime,
) -> dict[str, Any]:
    """注文金額計算（FR-026）。金額内訳とクーポンの適用可否を返す。"""
    subtotal = sum(price * quantity for price, quantity in line_inputs)
    is_applicable: bool | None = None
    not_applicable_reason: str | None = None

    if not line_inputs:
        if coupon is not None:
            is_applicable = False
            not_applicable_reason = REASON_CART_EMPTY
        return {
            "amounts": {
                "subtotal": 0,
                "discount_amount": 0,
                "discounted_subtotal": 0,
                "shipping_fee": 0,
                "tax_amount": 0,
                "total": 0,
            },
            "is_applicable": is_applicable,
            "not_applicable_reason": not_applicable_reason,
        }

    discount_amount = 0
    if coupon is not None:
        if at < coupon.valid_from:
            is_applicable, not_applicable_reason = False, REASON_NOT_YET_VALID
        elif at > coupon.valid_until:
            is_applicable, not_applicable_reason = False, REASON_EXPIRED
        elif subtotal < coupon.min_spend:
            is_applicable, not_applicable_reason = False, REASON_MIN_SPEND
        else:
            is_applicable = True
            discount_amount = discount_for(coupon.discount_type, coupon.discount_value, subtotal)

    discounted_subtotal = subtotal - discount_amount
    shipping_fee = 0 if discounted_subtotal >= FREE_SHIPPING_THRESHOLD else SHIPPING_FEE
    tax_amount = (discounted_subtotal + shipping_fee) * TAX_RATE_NUMERATOR // TAX_RATE_DENOMINATOR
    total = discounted_subtotal + shipping_fee + tax_amount
    return {
        "amounts": {
            "subtotal": subtotal,
            "discount_amount": discount_amount,
            "discounted_subtotal": discounted_subtotal,
            "shipping_fee": shipping_fee,
            "tax_amount": tax_amount,
            "total": total,
        },
        "is_applicable": is_applicable,
        "not_applicable_reason": not_applicable_reason,
    }


# trace: ADDR-008
def discount_for(discount_type: str, discount_value: int, subtotal: int) -> int:
    """割引額を求める（定額は min(割引値, 小計)、定率は1円未満切り捨て）。"""
    if discount_type == DISCOUNT_FIXED:
        return min(discount_value, subtotal)
    return subtotal * discount_value // 100


# trace: ADDR-003
def get_open_cart(user: Any) -> Cart | None:
    """購入者の利用中カートを取得する（ない場合は None）。"""
    return Cart.objects.filter(user=user, status=CART_OPEN).first()


# trace: ADDR-003
def get_or_create_open_cart(user: Any) -> Cart:
    """利用中カートを取得し、ない場合は1件だけ作成する（ST-CART-01、DQ-09）。

    カートの作成は呼出し元のトランザクション境界の内側で行う（異常終了時に作成済みの
    利用中カートを残さないため。CMN-21）。
    """
    cart = get_open_cart(user)
    if cart is not None:
        return cart
    now = timeutils.now()
    try:
        with transaction.atomic():
            return Cart.objects.create(user=user, status=CART_OPEN, created_at=now, updated_at=now)
    except IntegrityError:
        cart = get_open_cart(user)
        if cart is None:
            raise
        return cart


# trace: ADDR-003
def load_lines(cart: Cart) -> list[CartLine]:
    """カート明細を追加日時の昇順で取得する（関連データは結合取得する）。"""
    return list(
        cart.lines.select_related("stock_unit", "stock_unit__item").order_by("added_at", "id")
    )


# trace: ADDR-003
def lock_stock_units(stock_unit_ids: list[int]) -> dict[int, StockUnit]:
    """在庫単位行を識別子の昇順でロックして取得する（ADDR-003 INV-004）。"""
    ordered_ids = sorted(set(stock_unit_ids))
    locked = list(StockUnit.objects.select_for_update().filter(pk__in=ordered_ids).order_by("id"))
    return {unit.pk: unit for unit in locked}


# trace: ADDR-003
def lock_cart(cart: Cart) -> Cart:
    """カート行をロックして取得する。"""
    return Cart.objects.select_for_update().get(pk=cart.pk)


# trace: ADDR-008
def cart_view(cart: Cart, lines: list[CartLine], at: dt.datetime) -> dict[str, Any]:
    """カート内容（6.8.5）の算出結果を返す。"""
    line_inputs = [(line.stock_unit.price, line.quantity) for line in lines]
    calculated = calculate_amounts(line_inputs, cart.coupon, at)
    return {
        "cart": cart,
        "lines": lines,
        "total_quantity": sum(line.quantity for line in lines),
        "amounts": calculated["amounts"],
        "is_applicable": calculated["is_applicable"],
        "not_applicable_reason": calculated["not_applicable_reason"],
    }


# trace: ADDR-003
def show_cart(user: Any) -> dict[str, Any]:
    """カート照会（FR-020）。利用中カートがない場合は作成する。"""
    # 異常終了時は作成した利用中カートも残さない（FR-020 6.8.6、CMN-21）。
    with transaction.atomic():
        cart = get_or_create_open_cart(user)
        lines = load_lines(cart)
        return cart_view(cart, lines, timeutils.now())


# trace: ADDR-003
def add_line(user: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """カート明細追加（FR-021）。在庫は引き当てない。"""
    collector = ValidationCollector()
    stock_unit_id = parse_int(payload.get("stock_unit_id"))
    quantity = parse_int(payload.get("quantity"))
    if stock_unit_id is None:
        collector.add("stock_unit_id", "在庫単位IDは整数で指定してください。")
    if quantity is None or quantity < 1:
        collector.add("quantity", "数量は1以上の整数で入力してください。")
    collector.raise_if_any()

    stock_unit = get_public_stock_unit(stock_unit_id)
    now = timeutils.now()
    # カートの作成も含めて1つのトランザクションで行い、異常終了時は作成した利用中カートも
    # 残さない（FR-021 6.9.6、CMN-21）。ロックは在庫単位→カートの順で取得する（ADDR-003 DD-002）。
    with transaction.atomic():
        locked_units = lock_stock_units([stock_unit.pk])
        locked_unit = locked_units[stock_unit.pk]
        cart = get_or_create_open_cart(user)
        cart = lock_cart(cart)
        line = cart.lines.filter(stock_unit_id=locked_unit.pk).first()
        current_quantity = line.quantity if line is not None else 0
        combined = current_quantity + quantity
        if combined > QUANTITY_LIMIT:
            raise QuantityLimitExceeded(
                context={
                    "stock_unit_id": locked_unit.pk,
                    "limit": QUANTITY_LIMIT,
                    "current_quantity": current_quantity,
                    "requested_quantity": combined,
                }
            )
        if combined > locked_unit.quantity:
            raise InsufficientStock(
                context={
                    "shortages": [
                        {
                            "stock_unit_id": locked_unit.pk,
                            "sku": locked_unit.sku,
                            "requested_quantity": combined,
                            "available_quantity": locked_unit.quantity,
                        }
                    ]
                }
            )
        if line is None:
            CartLine.objects.create(cart=cart, stock_unit=locked_unit, quantity=quantity, added_at=now)
        else:
            line.quantity = combined
            line.save(update_fields=["quantity"])
        cart.updated_at = now
        cart.save(update_fields=["updated_at"])
        lines = load_lines(cart)
    return cart_view(cart, lines, now)


# trace: ADDR-003
def change_line_quantity(user: Any, cart_line_id: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """カート明細数量変更（FR-022）。"""
    collector = ValidationCollector()
    quantity = parse_int(payload.get("quantity"))
    if quantity is None or quantity < 1:
        collector.add("quantity", "数量は1以上の整数で入力してください。")
    collector.raise_if_any()

    line = find_own_line(user, cart_line_id)
    now = timeutils.now()
    with transaction.atomic():
        locked_units = lock_stock_units([line.stock_unit_id])
        cart = lock_cart(line.cart)
        line = cart.lines.select_related("stock_unit").filter(pk=line.pk).first()
        if line is None or cart.status != CART_OPEN:
            raise NotFoundError()
        locked_unit = locked_units[line.stock_unit_id]
        if quantity > QUANTITY_LIMIT:
            raise QuantityLimitExceeded(
                context={
                    "stock_unit_id": locked_unit.pk,
                    "limit": QUANTITY_LIMIT,
                    "current_quantity": line.quantity,
                    "requested_quantity": quantity,
                }
            )
        if quantity > locked_unit.quantity:
            raise InsufficientStock(
                context={
                    "shortages": [
                        {
                            "stock_unit_id": locked_unit.pk,
                            "sku": locked_unit.sku,
                            "requested_quantity": quantity,
                            "available_quantity": locked_unit.quantity,
                        }
                    ]
                }
            )
        line.quantity = quantity
        line.save(update_fields=["quantity"])
        cart.updated_at = now
        cart.save(update_fields=["updated_at"])
        lines = load_lines(cart)
    return cart_view(cart, lines, now)


# trace: ADDR-003
def delete_line(user: Any, cart_line_id: Any) -> dict[str, Any]:
    """カート明細削除（FR-023）。クーポンの適用は変更しない。"""
    line = find_own_line(user, cart_line_id)
    now = timeutils.now()
    with transaction.atomic():
        cart = lock_cart(line.cart)
        deleted, _ = cart.lines.filter(pk=line.pk).delete()
        if not deleted:
            raise NotFoundError()
        cart.updated_at = now
        cart.save(update_fields=["updated_at"])
        lines = load_lines(cart)
    return cart_view(cart, lines, now)


# trace: ADDR-003
def find_own_line(user: Any, cart_line_id: Any) -> CartLine:
    """ログイン中の購入者の利用中カートの明細を取得する（CMN-18）。"""
    identifier = parse_int(cart_line_id)
    if identifier is None:
        raise NotFoundError()
    line = (
        CartLine.objects.select_related("cart", "stock_unit")
        .filter(pk=identifier, cart__user=user, cart__status=CART_OPEN)
        .first()
    )
    if line is None:
        raise NotFoundError()
    return line


# trace: ADDR-003
def apply_coupon(user: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """クーポン適用（FR-024）。1カートにつき1枚まで。"""
    collector = ValidationCollector()
    code = normalize_coupon_code(payload.get("code"))
    if not COUPON_CODE_PATTERN.match(code):
        collector.add("code", "クーポンコードは英字・数字・ハイフンの20文字以内で入力してください。")
    collector.raise_if_any()

    now = timeutils.now()
    cart = get_open_cart(user)
    if cart is None:
        raise CartEmpty()
    with transaction.atomic():
        locked_cart = lock_cart(cart)
        lines = load_lines(locked_cart)
        if not lines:
            raise CartEmpty()
        if locked_cart.coupon_id is not None:
            raise CouponAlreadyApplied(context={})
        coupon = Coupon.objects.filter(code=code).first()
        if coupon is None:
            raise CouponNotFound()
        if now < coupon.valid_from:
            raise CouponNotYetValid(
                context={
                    "valid_from": timeutils.to_iso(coupon.valid_from),
                    "valid_until": timeutils.to_iso(coupon.valid_until),
                }
            )
        if now > coupon.valid_until:
            raise CouponExpired(
                context={
                    "valid_from": timeutils.to_iso(coupon.valid_from),
                    "valid_until": timeutils.to_iso(coupon.valid_until),
                }
            )
        subtotal = sum(line.stock_unit.price * line.quantity for line in lines)
        if subtotal < coupon.min_spend:
            raise CouponMinSpendNotMet(context={"min_spend": coupon.min_spend, "subtotal": subtotal})
        locked_cart.coupon = coupon
        locked_cart.updated_at = now
        locked_cart.save(update_fields=["coupon", "updated_at"])
        lines = load_lines(locked_cart)
    return cart_view(locked_cart, lines, now)


# trace: ADDR-003
def remove_coupon(user: Any) -> dict[str, Any]:
    """クーポン解除（FR-025）。未適用でも正常終了する。"""
    now = timeutils.now()
    # 異常終了時は作成した利用中カートも残さない（FR-025 6.13.6、CMN-21）。
    with transaction.atomic():
        cart = get_or_create_open_cart(user)
        locked_cart = lock_cart(cart)
        if locked_cart.coupon_id is not None:
            locked_cart.coupon = None
            locked_cart.updated_at = now
            locked_cart.save(update_fields=["coupon", "updated_at"])
        lines = load_lines(locked_cart)
    return cart_view(locked_cart, lines, now)


# trace: ADDR-003
def mark_converted(cart: Cart, at: dt.datetime) -> None:
    """注文確定の成功時にカートを注文済へ変更する（ST-CART-02）。"""
    cart.status = CART_CONVERTED
    cart.converted_at = at
    cart.updated_at = at
    cart.save(update_fields=["status", "converted_at", "updated_at"])
