# trace: ADDR-001, ADDR-004, ADDR-012, ENT-008, ENT-009, ENT-006, ENT-007
"""カートの業務処理（FR-020〜FR-025。金額は FR-026：carts.pricing）。

更新を伴う処理は1トランザクションで実行し、利用中カート行をロックしてから判定する（ADDR-004 4.3 の4）。
カート操作では在庫数量を変更しない。
"""

import re
from datetime import datetime
from typing import Any

from django.db import DatabaseError, IntegrityError, transaction

from carts import pricing
from carts.models import Cart, CartItem
from catalog.models import StockUnit
from common import clock, codes
from common.codes import CartStatus, DiscountType
from common.errors import (
    BusinessError,
    FieldErrors,
    NotFoundError,
    ServiceError,
    from_record,
    system_failure,
)
from common.normalize import is_blank, parse_identifier, parse_int, strip_text
from common.submit_token import NO_TOKEN, TokenContext
from promotions.models import Coupon

MAX_QUANTITY_PER_STOCK_UNIT = 10
_COUPON_CODE = re.compile(r"^[A-Z0-9-]{1,20}\Z")
MSG_CART_ITEM_NOT_FOUND = "指定したカート明細が見つかりません。"


# trace: ENT-008, ADDR-004
def _lock_active_cart(user: Any) -> Cart | None:
    return (
        Cart.objects.select_for_update(of=("self",))
        .select_related("coupon")
        .filter(buyer=user, status=CartStatus.ACTIVE)
        .first()
    )


# trace: ENT-008, ADDR-004
def _lock_or_create_active_cart(user: Any, now: datetime) -> Cart:
    """利用中カートを取得（ロック）し、ない場合は明細0件・クーポンなしで作成する（ST-CART-01）。

    同時作成で一意違反となった側は作成済みの利用中カートを読み直して続ける（ADDR-004 4.3 の4）。
    """
    cart = _lock_active_cart(user)
    if cart is not None:
        return cart
    try:
        with transaction.atomic():
            return Cart.objects.create(buyer=user, status=CartStatus.ACTIVE, created_at=now, updated_at=now)
    except IntegrityError:
        cart = _lock_active_cart(user)
        if cart is None:
            raise
        return cart


# trace: ADDR-001, ENT-007, ENT-008, ENT-009
def cart_content(cart: Cart | None, at: datetime) -> dict[str, Any]:
    """カート内容（6.8.5。FR-020〜FR-025 で同じ内容を返す）。"""
    items: list[CartItem] = []
    coupon = None
    if cart is not None:
        items = list(cart.items.select_related("stock_unit__product").order_by("pk"))
        coupon = cart.coupon
    amounts = pricing.calculate([(i.stock_unit.price_excluding_tax, i.quantity) for i in items], coupon, at)
    coupon_data = None
    if coupon is not None:
        coupon_data = {
            "coupon_code": coupon.coupon_code,
            "name": coupon.name,
            "discount_type": coupon.discount_type,
            "discount_type_label": DiscountType(coupon.discount_type).label,
            "discount_value": coupon.discount_value,
            "minimum_purchase_amount": coupon.minimum_purchase_amount,
            "valid_from": coupon.valid_from,
            "valid_to": coupon.valid_to,
            "is_applicable": bool(amounts.is_coupon_applicable),
            "not_applicable_reason": amounts.not_applicable_reason,
        }
    return {
        "items": [
            {
                "cart_item_id": i.pk,
                "stock_unit_id": i.stock_unit_id,
                "sku": i.stock_unit.sku,
                "product_id": i.stock_unit.product_id,
                "product_name": i.stock_unit.product.name,
                "variant_name": i.stock_unit.variant_name,
                "unit_price_excluding_tax": i.stock_unit.price_excluding_tax,
                "quantity": i.quantity,
                "line_amount": i.stock_unit.price_excluding_tax * i.quantity,
                "stock_quantity": i.stock_unit.stock_quantity,
            }
            for i in items
        ],
        "total_quantity": sum(i.quantity for i in items),
        "coupon": coupon_data,
        "amounts": amounts.as_dict(),
    }


# trace: ENT-009, ADDR-012
def shortage_item_ids(content: dict[str, Any]) -> list[int]:
    """明細の数量が現在の在庫数量を超える明細（SCR-005-V08 の在庫不足の警告の対象）。"""
    return [item["cart_item_id"] for item in content["items"] if item["quantity"] > item["stock_quantity"]]


# trace: ADDR-001, ADDR-004, ENT-008
def get_cart(user: Any) -> dict[str, Any]:
    """FR-020 カート照会。利用中カートがない場合は明細0件・クーポンなしで作成する（ST-CART-01）。"""
    now = clock.now_seconds()
    try:
        with transaction.atomic():
            cart = Cart.objects.select_related("coupon").filter(buyer=user, status=CartStatus.ACTIVE).first()
            if cart is None:
                cart = _lock_or_create_active_cart(user, now)
            return cart_content(cart, now)
    except ServiceError:
        raise
    except DatabaseError as exc:
        raise system_failure("E-020-03") from exc


# trace: ADDR-001
def _quantity_violations(raw: Any) -> tuple[int | None, list[tuple[str, str]]]:
    if is_blank(raw):
        return None, [(codes.FIELD_REQUIRED, "数量は1以上の整数で入力してください。")]
    value = parse_int(raw)
    if value is None:
        return None, [(codes.FIELD_INVALID_TYPE, "数量は1以上の整数で入力してください。")]
    if value <= 0:
        return None, [(codes.FIELD_OUT_OF_RANGE, "数量は1以上の整数で入力してください。")]
    return value, []


# trace: ADDR-001
def _limit_error(code: str, stock_unit_id: int, current: int, resulting: int) -> BusinessError:
    return BusinessError(
        code,
        f"同じ規格は1注文につき10個までです（現在のカート内数量：{current}個）。",
        reason=codes.REASON_QUANTITY_LIMIT_EXCEEDED,
        values={
            "stock_unit_id": stock_unit_id,
            "max_quantity": MAX_QUANTITY_PER_STOCK_UNIT,
            "current_quantity": current,
            "resulting_quantity": resulting,
        },
    )


# trace: ADDR-001
def _stock_error(code: str, stock_unit: StockUnit, requested: int) -> BusinessError:
    return BusinessError(
        code,
        f"在庫が不足しています（現在の在庫数量：{stock_unit.stock_quantity}個）。",
        reason=codes.REASON_INSUFFICIENT_STOCK,
        values={
            "stock_units": [
                {
                    "stock_unit_id": stock_unit.pk,
                    "sku": stock_unit.sku,
                    "requested_quantity": requested,
                    "stock_quantity": stock_unit.stock_quantity,
                }
            ]
        },
    )


# trace: ADDR-001, ADDR-004, ENT-006, ENT-008, ENT-009
def add_item(user: Any, stock_unit_id: Any, quantity: Any, replay: TokenContext = NO_TOKEN) -> dict[str, Any]:
    """FR-021 カート明細追加（在庫は引き当てない）。

    画面の使用済みトークンの要求は、再判定が手順9に至っても加算せず先着の結果を通知する（ADDR-004 DD-013）。
    """
    errors = FieldErrors()
    stock_unit_pk: int | None = None
    if is_blank(stock_unit_id):
        errors.add("stock_unit_id", codes.FIELD_REQUIRED, "規格を選択してください。")
    else:
        stock_unit_pk = parse_int(stock_unit_id)
        if stock_unit_pk is None:
            errors.add("stock_unit_id", codes.FIELD_INVALID_TYPE, "規格の指定に誤りがあります。")
    quantity_value, violations = _quantity_violations(quantity)
    for reason, message in violations:
        errors.add("quantity", reason, message)
    errors.raise_if_any("E-021-03")
    if quantity_value is None or stock_unit_pk is None:
        raise system_failure("E-021-07")

    now = clock.now_seconds()
    try:
        with transaction.atomic():
            target_pk = parse_identifier(stock_unit_pk)
            stock_unit = StockUnit.objects.select_related("product").filter(pk=target_pk).first() if target_pk else None
            if stock_unit is None or not stock_unit.product.is_public:
                raise NotFoundError("E-021-04", "指定した商品の規格が見つかりません。")
            cart = _lock_or_create_active_cart(user, now)
            existing = CartItem.objects.filter(cart=cart, stock_unit=stock_unit).first()
            current = existing.quantity if existing else 0
            resulting = current + quantity_value
            if resulting > MAX_QUANTITY_PER_STOCK_UNIT:
                raise _limit_error("E-021-05", stock_unit.pk, current, resulting)
            stock_unit = StockUnit.objects.get(pk=stock_unit.pk)
            if resulting > stock_unit.stock_quantity:
                raise _stock_error("E-021-06", stock_unit, resulting)
            if replay.used:
                if not replay.prior:
                    raise system_failure("E-021-07")
                if replay.prior.get("status") != "success":
                    raise from_record(replay.prior)
                return cart_content(cart, now)
            if existing is not None:
                existing.quantity = resulting
                existing.save(update_fields=["quantity"])
            else:
                CartItem.objects.create(cart=cart, stock_unit=stock_unit, quantity=quantity_value, added_at=now)
            cart.updated_at = now
            cart.save(update_fields=["updated_at"])
            return cart_content(cart, now)
    except ServiceError:
        raise
    except DatabaseError as exc:
        raise system_failure("E-021-07") from exc


# trace: ADDR-001, ADDR-004, ENT-006, ENT-008, ENT-009
def change_quantity(user: Any, cart_item_id: Any, quantity: Any) -> dict[str, Any]:
    """FR-022 カート明細数量変更（10個以下かつ在庫数量以下）。"""
    quantity_value, violations = _quantity_violations(quantity)
    errors = FieldErrors()
    for reason, message in violations:
        errors.add("quantity", reason, message)
    errors.raise_if_any("E-022-03")
    if quantity_value is None:
        raise system_failure("E-022-07")

    now = clock.now_seconds()
    try:
        with transaction.atomic():
            cart = _lock_active_cart(user)
            item_pk = parse_identifier(cart_item_id)
            item = None
            if cart is not None and item_pk is not None:
                item = CartItem.objects.select_related("stock_unit").filter(cart=cart, pk=item_pk).first()
            if item is None:
                raise NotFoundError("E-022-04", MSG_CART_ITEM_NOT_FOUND)
            if quantity_value > MAX_QUANTITY_PER_STOCK_UNIT:
                raise _limit_error("E-022-05", item.stock_unit_id, item.quantity, quantity_value)
            stock_unit = StockUnit.objects.get(pk=item.stock_unit_id)
            if quantity_value > stock_unit.stock_quantity:
                raise _stock_error("E-022-06", stock_unit, quantity_value)
            item.quantity = quantity_value
            item.save(update_fields=["quantity"])
            cart.updated_at = now
            cart.save(update_fields=["updated_at"])
            return cart_content(cart, now)
    except ServiceError:
        raise
    except DatabaseError as exc:
        raise system_failure("E-022-07") from exc


# trace: ADDR-001, ADDR-004, ENT-008, ENT-009
def delete_item(user: Any, cart_item_id: Any) -> dict[str, Any]:
    """FR-023 カート明細削除（クーポンの適用は変更しない）。"""
    now = clock.now_seconds()
    try:
        with transaction.atomic():
            cart = _lock_active_cart(user)
            item_pk = parse_identifier(cart_item_id)
            item = None
            if cart is not None and item_pk is not None:
                item = CartItem.objects.filter(cart=cart, pk=item_pk).first()
            if item is None:
                raise NotFoundError("E-023-03", MSG_CART_ITEM_NOT_FOUND)
            item.delete()
            cart.updated_at = now
            cart.save(update_fields=["updated_at"])
            return cart_content(cart, now)
    except ServiceError:
        raise
    except DatabaseError as exc:
        raise system_failure("E-023-04") from exc


# trace: ADDR-001, ADDR-004, ENT-007, ENT-008
def apply_coupon(user: Any, coupon_code: Any) -> dict[str, Any]:
    """FR-024 クーポン適用（1カートにつき1枚。利用回数は制限しない）。"""
    code = strip_text(coupon_code)
    if isinstance(code, str):
        code = code.upper()
    errors = FieldErrors()
    if is_blank(code):
        errors.add(
            "coupon_code", codes.FIELD_REQUIRED, "クーポンコードは英字・数字・ハイフンの20文字以内で入力してください。"
        )
    elif not isinstance(code, str):
        errors.add(
            "coupon_code",
            codes.FIELD_INVALID_TYPE,
            "クーポンコードは英字・数字・ハイフンの20文字以内で入力してください。",
        )
    elif len(code) > 20:
        errors.add(
            "coupon_code",
            codes.FIELD_INVALID_LENGTH,
            "クーポンコードは英字・数字・ハイフンの20文字以内で入力してください。",
        )
    elif not _COUPON_CODE.match(code):
        errors.add(
            "coupon_code",
            codes.FIELD_INVALID_FORMAT,
            "クーポンコードは英字・数字・ハイフンの20文字以内で入力してください。",
        )
    errors.raise_if_any("E-024-03")

    now = clock.now_seconds()
    try:
        with transaction.atomic():
            cart = _lock_active_cart(user)
            if cart is None or not CartItem.objects.filter(cart=cart).exists():
                raise BusinessError(
                    "E-024-04", "カートに商品がないため、クーポンを適用できません。", reason=codes.REASON_CART_EMPTY
                )
            if cart.coupon_id is not None:
                raise BusinessError(
                    "E-024-05",
                    f"クーポンは1注文につき1枚までです（適用中のクーポン：{cart.coupon.coupon_code}）。"
                    "別のクーポンを使う場合は、適用中のクーポンを解除してください。",
                    reason=codes.REASON_COUPON_ALREADY_APPLIED,
                )
            coupon = Coupon.objects.filter(coupon_code=code).first()
            if coupon is None:
                raise BusinessError(
                    "E-024-06", "入力したクーポンコードは存在しません。", reason=codes.REASON_COUPON_NOT_FOUND
                )
            period = pricing.coupon_period_state(coupon, now)
            period_text = f"{clock.format_display(coupon.valid_from)}〜{clock.format_display(coupon.valid_to)}"
            period_values = {"valid_from": coupon.valid_from, "valid_to": coupon.valid_to}
            if period == codes.NOT_APPLICABLE_NOT_YET_VALID:
                raise BusinessError(
                    "E-024-07",
                    f"このクーポンは有効期間の開始前です（有効期間：{period_text}）。",
                    reason=codes.REASON_COUPON_NOT_YET_VALID,
                    values=period_values,
                )
            if period == codes.NOT_APPLICABLE_EXPIRED:
                raise BusinessError(
                    "E-024-08",
                    f"このクーポンは有効期間が終了しています（有効期間：{period_text}）。",
                    reason=codes.REASON_COUPON_EXPIRED,
                    values=period_values,
                )
            subtotal = sum(
                item.stock_unit.price_excluding_tax * item.quantity
                for item in CartItem.objects.filter(cart=cart).select_related("stock_unit")
            )
            if subtotal < coupon.minimum_purchase_amount:
                raise BusinessError(
                    "E-024-09",
                    f"小計が最低購入金額に達していません（最低購入金額：{coupon.minimum_purchase_amount:,}円、"
                    f"現在の小計：{subtotal:,}円）。",
                    reason=codes.REASON_BELOW_MINIMUM_PURCHASE_AMOUNT,
                    values={"minimum_purchase_amount": coupon.minimum_purchase_amount, "subtotal": subtotal},
                )
            cart.coupon = coupon
            cart.updated_at = now
            cart.save(update_fields=["coupon", "updated_at"])
            return cart_content(cart, now)
    except ServiceError:
        raise
    except DatabaseError as exc:
        raise system_failure("E-024-10") from exc


# trace: ADDR-001, ADDR-004, ENT-008
def remove_coupon(user: Any) -> dict[str, Any]:
    """FR-025 クーポン解除（未適用の場合も正常終了。利用中カートがなければ作成する）。"""
    now = clock.now_seconds()
    try:
        with transaction.atomic():
            cart = _lock_or_create_active_cart(user, now)
            if cart.coupon_id is not None:
                cart.coupon = None
                cart.updated_at = now
                cart.save(update_fields=["coupon", "updated_at"])
            return cart_content(cart, now)
    except ServiceError:
        raise
    except DatabaseError as exc:
        raise system_failure("E-025-03") from exc
