# trace: ADDR-008
"""カート内容（6.8.5）の応答表現。"""

from __future__ import annotations

from typing import Any

from carts.models import Cart, CartLine
from common import timeutils


def cart_line_payload(line: CartLine) -> dict[str, Any]:
    """カート明細1件（現在の税抜単価・明細金額・在庫数量を含む）。"""
    stock_unit = line.stock_unit
    return {
        "cart_line_id": line.pk,
        "stock_unit_id": stock_unit.pk,
        "sku": stock_unit.sku,
        "item_id": stock_unit.item_id,
        "item_name": stock_unit.item.name,
        "variant_name": stock_unit.variant_name,
        "unit_price": stock_unit.price,
        "quantity": line.quantity,
        "line_amount": stock_unit.price * line.quantity,
        "stock_quantity": stock_unit.quantity,
    }


def coupon_payload(cart: Cart, is_applicable: bool | None, not_applicable_reason: str | None) -> dict[str, Any] | None:
    """適用中クーポンの表現（未適用は null）。"""
    coupon = cart.coupon
    if coupon is None:
        return None
    return {
        "code": coupon.code,
        "name": coupon.name,
        "discount_type": coupon.discount_type,
        "discount_value": coupon.discount_value,
        "min_spend": coupon.min_spend,
        "valid_from": timeutils.to_iso(coupon.valid_from),
        "valid_until": timeutils.to_iso(coupon.valid_until),
        "is_applicable": is_applicable,
        "not_applicable_reason": not_applicable_reason,
    }


def cart_payload(view: dict[str, Any]) -> dict[str, Any]:
    """カート内容（FR-020〜FR-025 の共通応答）。"""
    cart: Cart = view["cart"]
    return {
        "cart_id": cart.pk,
        "lines": [cart_line_payload(line) for line in view["lines"]],
        "total_quantity": view["total_quantity"],
        "coupon": coupon_payload(cart, view["is_applicable"], view["not_applicable_reason"]),
        "amounts": view["amounts"],
    }
