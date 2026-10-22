# trace: ADDR-001, ADDR-007
"""カート機能（FR-020〜FR-025）の業務ロジック。

同一カートへの同時操作は、カート行を FOR UPDATE でロックして直列化する（ADDR-001 DD-004）。
ロック順序は 注文 → カート → 在庫単位（ID昇順）に統一する（ADDR-001 DD-005）。
"""
from typing import Any

from django.db import IntegrityError, transaction

from shop.common import timeutils
from shop.common.errors import (
    CartEmptyError,
    CouponAlreadyAppliedError,
    CouponExpiredError,
    CouponMinSpendNotMetError,
    CouponNotFoundError,
    CouponNotYetValidError,
    InsufficientStockError,
    NotFoundError,
    QuantityLimitExceededError,
    ValidationError,
)
from shop.common.validators import UPPER_CODE_PATTERN, ErrorCollector, normalize_coupon_code, parse_int, strip_value
from shop.models import Cart, CartLine, CartStatus, Coupon, StockUnit, User
from shop.services.amounts import (
    REASON_EXPIRED,
    REASON_MIN_SPEND_NOT_MET,
    REASON_NOT_YET_VALID,
    AmountLine,
    calculate_amounts,
    coupon_not_applicable_reason,
)

QUANTITY_LIMIT = 10
COUPON_CODE_MAX_LENGTH = 20


# trace: ADDR-001
def get_or_create_open_cart(user: User) -> Cart:
    """利用中カートを取得し、無ければ1件作成する（ST-CART-01、DQ-09）。"""
    cart = Cart.objects.filter(user=user, status=CartStatus.OPEN).first()
    if cart is not None:
        return cart
    now = timeutils.now()
    try:
        with transaction.atomic():
            return Cart.objects.create(user=user, status=CartStatus.OPEN, created_at=now, updated_at=now)
    except IntegrityError:
        existing = Cart.objects.filter(user=user, status=CartStatus.OPEN).first()
        if existing is None:
            raise
        return existing


# trace: ADDR-001
def lock_open_cart(user: User) -> Cart | None:
    """利用中カート行をロックして取得する（存在しない場合は None）。"""
    return Cart.objects.select_for_update().filter(user=user, status=CartStatus.OPEN).first()


# trace: ADDR-001
def _lock_stock_unit(stock_unit_id: int) -> StockUnit | None:
    """在庫単位行をロックして取得する。"""
    return StockUnit.objects.select_for_update().select_related("item").filter(stock_unit_id=stock_unit_id).first()


# trace: ADDR-007
def cart_representation(cart: Cart, at: Any = None) -> dict[str, Any]:
    """カート内容（FR-020 6.8.5）を組み立てる。FR-021〜FR-025 も同じ内容を返す。"""
    calculated_at = at or timeutils.now()
    lines = list(cart.lines.select_related("stock_unit", "stock_unit__item").order_by("added_at", "cart_line_id"))
    amount_lines = [AmountLine(unit_price=line.stock_unit.price, quantity=line.quantity) for line in lines]
    amounts = calculate_amounts(amount_lines, cart.coupon, calculated_at)

    coupon_payload: dict[str, Any] | None = None
    if cart.coupon is not None:
        coupon_payload = {
            "code": cart.coupon.code,
            "name": cart.coupon.name,
            "discount_type": cart.coupon.discount_type,
            "discount_value": cart.coupon.discount_value,
            "min_spend": cart.coupon.min_spend,
            "valid_from": timeutils.jst(cart.coupon.valid_from),
            "valid_until": timeutils.jst(cart.coupon.valid_until),
            "is_applicable": bool(amounts.is_applicable),
            "not_applicable_reason": amounts.not_applicable_reason,
        }

    return {
        "cart_id": cart.cart_id,
        "lines": [
            {
                "cart_line_id": line.cart_line_id,
                "stock_unit_id": line.stock_unit_id,
                "sku": line.stock_unit.sku,
                "item_id": line.stock_unit.item_id,
                "item_name": line.stock_unit.item.name,
                "variant_name": line.stock_unit.variant_name,
                "unit_price": line.stock_unit.price,
                "quantity": line.quantity,
                "line_amount": line.stock_unit.price * line.quantity,
                "stock_quantity": line.stock_unit.quantity,
            }
            for line in lines
        ],
        "total_quantity": sum(line.quantity for line in lines),
        "coupon": coupon_payload,
        "amounts": amounts.as_amounts(),
    }


# trace: ADDR-001, ADDR-007
def view_cart(user: User) -> dict[str, Any]:
    """カート照会（FR-020）。利用中カートが無い場合は作成して返す。"""
    cart = get_or_create_open_cart(user)
    return cart_representation(cart)


# trace: ADDR-001, ADDR-007
def add_line(user: User, raw_stock_unit_id: Any, raw_quantity: Any) -> dict[str, Any]:
    """カート明細追加（FR-021）。同一在庫単位は既存明細へ加算する。"""
    errors = ErrorCollector()
    stock_unit_id = parse_int(raw_stock_unit_id)
    if stock_unit_id is None:
        errors.add("stock_unit_id", "規格を選択してください。")
    quantity = parse_int(raw_quantity)
    if quantity is None:
        errors.add("quantity", "数量は1以上の整数で入力してください。")
    elif quantity < 1:
        errors.add("quantity", "数量は1以上の整数で入力してください。")
    errors.raise_if_error()

    get_or_create_open_cart(user)
    with transaction.atomic():
        cart = lock_open_cart(user)
        if cart is None:
            cart = get_or_create_open_cart(user)
            cart = lock_open_cart(user) or cart
        stock_unit = _lock_stock_unit(stock_unit_id)
        if stock_unit is None or not stock_unit.item.is_public:
            raise NotFoundError(message="指定した商品の規格が見つかりません。")

        line = cart.lines.filter(stock_unit_id=stock_unit_id).first()
        current_quantity = line.quantity if line else 0
        merged_quantity = current_quantity + quantity

        if merged_quantity > QUANTITY_LIMIT:
            raise QuantityLimitExceededError(
                context={
                    "stock_unit_id": stock_unit.stock_unit_id,
                    "limit": QUANTITY_LIMIT,
                    "current_quantity": current_quantity,
                    "requested_quantity": merged_quantity,
                }
            )
        if merged_quantity > stock_unit.quantity:
            raise InsufficientStockError(
                context={
                    "shortages": [
                        {
                            "stock_unit_id": stock_unit.stock_unit_id,
                            "sku": stock_unit.sku,
                            "requested_quantity": merged_quantity,
                            "available_quantity": stock_unit.quantity,
                        }
                    ]
                }
            )

        now = timeutils.now()
        if line is None:
            CartLine.objects.create(cart=cart, stock_unit=stock_unit, quantity=quantity, added_at=now)
        else:
            line.quantity = merged_quantity
            line.save(update_fields=["quantity"])
        cart.updated_at = now
        cart.save(update_fields=["updated_at"])
        return cart_representation(cart, now)


# trace: ADDR-001, ADDR-007
def update_line_quantity(user: User, raw_cart_line_id: Any, raw_quantity: Any) -> dict[str, Any]:
    """カート明細数量変更（FR-022）。"""
    quantity = parse_int(raw_quantity)
    if quantity is None or quantity < 1:
        raise ValidationError(details=[{"field": "quantity", "reason": "数量は1以上の整数で入力してください。"}])

    cart_line_id = parse_int(raw_cart_line_id)
    with transaction.atomic():
        cart = lock_open_cart(user)
        line = _find_line(cart, cart_line_id)
        stock_unit = _lock_stock_unit(line.stock_unit_id)
        if stock_unit is None:
            raise NotFoundError(message="指定したカート明細が見つかりません。")

        if quantity > QUANTITY_LIMIT:
            raise QuantityLimitExceededError(
                context={
                    "stock_unit_id": stock_unit.stock_unit_id,
                    "limit": QUANTITY_LIMIT,
                    "current_quantity": line.quantity,
                    "requested_quantity": quantity,
                }
            )
        if quantity > stock_unit.quantity:
            raise InsufficientStockError(
                context={
                    "shortages": [
                        {
                            "stock_unit_id": stock_unit.stock_unit_id,
                            "sku": stock_unit.sku,
                            "requested_quantity": quantity,
                            "available_quantity": stock_unit.quantity,
                        }
                    ]
                }
            )

        now = timeutils.now()
        line.quantity = quantity
        line.save(update_fields=["quantity"])
        cart.updated_at = now
        cart.save(update_fields=["updated_at"])
        return cart_representation(cart, now)


# trace: ADDR-001, ADDR-007
def remove_line(user: User, raw_cart_line_id: Any) -> dict[str, Any]:
    """カート明細削除（FR-023）。クーポンの適用は変更しない。"""
    cart_line_id = parse_int(raw_cart_line_id)
    with transaction.atomic():
        cart = lock_open_cart(user)
        line = _find_line(cart, cart_line_id)
        now = timeutils.now()
        line.delete()
        cart.updated_at = now
        cart.save(update_fields=["updated_at"])
        return cart_representation(cart, now)


# trace: ADDR-007
def _find_line(cart: Cart | None, cart_line_id: int | None) -> CartLine:
    """利用中カートの明細を取得する（無い場合は対象なしとする）。"""
    if cart is None or cart_line_id is None:
        raise NotFoundError(message="指定したカート明細が見つかりません。")
    line = cart.lines.select_related("stock_unit").filter(cart_line_id=cart_line_id).first()
    if line is None:
        raise NotFoundError(message="指定したカート明細が見つかりません。")
    return line


# trace: ADDR-001, ADDR-007
def apply_coupon(user: User, raw_code: Any) -> dict[str, Any]:
    """クーポン適用（FR-024）。1カートにつき1枚まで適用できる。"""
    code = normalize_coupon_code(raw_code)
    if code == "" or len(code) > COUPON_CODE_MAX_LENGTH or not UPPER_CODE_PATTERN.match(code):
        reason = "クーポンコードは英大文字・数字・ハイフンで20文字以下で入力してください。"
        raise ValidationError(details=[{"field": "code", "reason": reason}])

    with transaction.atomic():
        cart = lock_open_cart(user)
        if cart is None or not cart.lines.exists():
            raise CartEmptyError(message="カートに商品がないためクーポンを適用できません。")
        if cart.coupon_id is not None:
            raise CouponAlreadyAppliedError(
                message=(
                    f"クーポン {cart.coupon.code} が適用中です。"
                    "クーポンは1枚まで適用できます。別のクーポンを適用するには、適用中のクーポンを解除してください。"
                ),
                context={},
            )

        coupon = Coupon.objects.filter(code=code).first()
        if coupon is None:
            raise CouponNotFoundError()

        now = timeutils.now()
        subtotal = sum(line.stock_unit.price * line.quantity for line in cart.lines.select_related("stock_unit"))
        reason = coupon_not_applicable_reason(coupon, subtotal, now)
        if reason == REASON_NOT_YET_VALID:
            raise CouponNotYetValidError(
                context={
                    "valid_from": timeutils.to_iso(coupon.valid_from),
                    "valid_until": timeutils.to_iso(coupon.valid_until),
                }
            )
        if reason == REASON_EXPIRED:
            raise CouponExpiredError(
                context={
                    "valid_from": timeutils.to_iso(coupon.valid_from),
                    "valid_until": timeutils.to_iso(coupon.valid_until),
                }
            )
        if reason == REASON_MIN_SPEND_NOT_MET:
            raise CouponMinSpendNotMetError(context={"min_spend": coupon.min_spend, "subtotal": subtotal})

        cart.coupon = coupon
        cart.updated_at = now
        cart.save(update_fields=["coupon", "updated_at"])
        return cart_representation(cart, now)


# trace: ADDR-001, ADDR-007
def remove_coupon(user: User) -> dict[str, Any]:
    """クーポン解除（FR-025）。未適用の場合も正常終了する。"""
    get_or_create_open_cart(user)
    with transaction.atomic():
        cart = lock_open_cart(user)
        if cart is None:
            cart = get_or_create_open_cart(user)
            cart = lock_open_cart(user) or cart
        now = timeutils.now()
        if cart.coupon_id is not None:
            cart.coupon = None
            cart.updated_at = now
            cart.save(update_fields=["coupon", "updated_at"])
        return cart_representation(cart, now)


# trace: ADDR-007
def open_cart_total_quantity(user: User | None) -> int:
    """共通ヘッダーに表示する利用中カートの合計点数を返す。"""
    if user is None:
        return 0
    cart = Cart.objects.filter(user=user, status=CartStatus.OPEN).first()
    if cart is None:
        return 0
    return sum(line.quantity for line in cart.lines.all())


# trace: ADDR-007
def strip_code(raw_code: Any) -> str:
    """クーポンコードの前後の空白を除去する（画面での再表示に用いる）。"""
    return strip_value(raw_code)
