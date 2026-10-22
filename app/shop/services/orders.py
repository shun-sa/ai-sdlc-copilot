# trace: ADDR-001, ADDR-003, ADDR-009, ADDR-013
"""注文確定・支払・注文照会・キャンセル（FR-030〜FR-034）の業務ロジック。

更新はすべて単一トランザクション内で行い、ロック順序は 注文 → カート → 在庫単位（ID昇順）とする。
支払では注文行をロックしてから状態を判定し、決済サービスの呼び出しと結果反映を
同一トランザクション・同一ロック保持区間で確定する（ADDR-013 DD-001・DD-003、ADDR-009 DD-005）。
ロック保持区間には外部ネットワーク通信・スリープ・他プロセスへの待ちを置かない（ADDR-001 DD-007）。
"""
import logging
from typing import Any

from django.db import transaction

from shop.common import timeutils
from shop.common.errors import (
    AppError,
    CartEmptyError,
    CouponExpiredError,
    CouponMinSpendNotMetError,
    CouponNotYetValidError,
    InsufficientStockError,
    InvalidStatusTransitionError,
    ItemNotAvailableError,
    NotFoundError,
    PaymentDeclinedError,
    PaymentServiceError,
    QuantityLimitExceededError,
    ValidationError,
)
from shop.common.logging import build_extra
from shop.common.pagination import paginate, parse_page
from shop.common.validators import (
    DIGITS_PATTERN,
    PHONE_PATTERN,
    POSTAL_CODE_PATTERN,
    ErrorCollector,
    parse_int,
    strip_value,
)
from shop.models import (
    Cart,
    CartStatus,
    PaymentRecord,
    PaymentResult,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseOrderStatus,
    PurchaseOrderStatusHistory,
    ShippingAddress,
    StockUnit,
    User,
)
from shop.payments import client as payment_client
from shop.payments.gateway import APPROVE, DECLINE, RESULT_APPROVED, PaymentGatewayError, PaymentRequest
from shop.services import representations
from shop.services.amounts import (
    REASON_EXPIRED,
    REASON_MIN_SPEND_NOT_MET,
    REASON_NOT_YET_VALID,
    AmountLine,
    calculate_amounts,
    coupon_not_applicable_reason,
)
from shop.services.carts import QUANTITY_LIMIT
from shop.services.order_numbers import next_order_number

logger = logging.getLogger("shop.orders")

ORDER_PAGE_SIZE = 20
CURRENCY_JPY = "JPY"
PREFECTURE_MIN = 1
PREFECTURE_MAX = 47
RECIPIENT_NAME_MAX = 50
ADDRESS_LINE1_MAX = 100
ADDRESS_LINE2_MAX = 100
PHONE_DIGITS_MIN = 10
PHONE_DIGITS_MAX = 11


# trace: ADDR-001
def validate_shipping_address(data: dict[str, Any]) -> dict[str, Any]:
    """配送先の入力を検証し、登録する値へ整形する（FR-030 手順3）。"""
    errors = ErrorCollector()
    recipient_name = strip_value(data.get("recipient_name"))
    postal_code = strip_value(data.get("postal_code"))
    prefecture_code = strip_value(data.get("prefecture_code"))
    address_line1 = strip_value(data.get("address_line1"))
    address_line2 = strip_value(data.get("address_line2"))
    phone_number = strip_value(data.get("phone_number"))

    if recipient_name == "":
        errors.add("recipient_name", "受取人氏名を入力してください。")
    elif len(recipient_name) > RECIPIENT_NAME_MAX:
        errors.add("recipient_name", "受取人氏名は50文字以下で入力してください。")

    if postal_code == "":
        errors.add("postal_code", "郵便番号を入力してください。")
    elif not POSTAL_CODE_PATTERN.match(postal_code):
        errors.add("postal_code", "郵便番号は「1234567」または「123-4567」の形式で入力してください。")

    if prefecture_code == "":
        errors.add("prefecture_code", "都道府県を選択してください。")
    elif not _is_prefecture_code(prefecture_code):
        errors.add("prefecture_code", "都道府県の指定が正しくありません。")

    if address_line1 == "":
        errors.add("address_line1", "市区町村・番地を入力してください。")
    elif len(address_line1) > ADDRESS_LINE1_MAX:
        errors.add("address_line1", "市区町村・番地は100文字以下で入力してください。")

    if len(address_line2) > ADDRESS_LINE2_MAX:
        errors.add("address_line2", "建物名・部屋番号は100文字以下で入力してください。")

    if phone_number == "":
        errors.add("phone_number", "電話番号を入力してください。")
    elif not PHONE_PATTERN.match(phone_number) or not (
        PHONE_DIGITS_MIN <= len(phone_number.replace("-", "")) <= PHONE_DIGITS_MAX
    ):
        errors.add("phone_number", "電話番号は数字10桁または11桁で入力してください。")

    errors.raise_if_error()

    return {
        "recipient_name": recipient_name,
        "postal_code": postal_code.replace("-", ""),
        "prefecture_code": prefecture_code,
        "address_line1": address_line1,
        "address_line2": address_line2 or None,
        "phone_number": phone_number.replace("-", ""),
    }


# trace: ADDR-001
def _is_prefecture_code(value: str) -> bool:
    """都道府県コード（半角数字2桁の01〜47）かどうかを判定する。"""
    if len(value) != 2 or not DIGITS_PATTERN.match(value):
        return False
    return PREFECTURE_MIN <= int(value) <= PREFECTURE_MAX


# trace: ADDR-001, ADDR-003
def checkout(user: User, address_input: dict[str, Any]) -> dict[str, Any]:
    """注文確定（FR-030）。再判定・在庫引当・注文登録を1トランザクションで確定する。"""
    address = validate_shipping_address(address_input)
    confirmed_at = timeutils.now()

    with transaction.atomic():
        cart = Cart.objects.select_for_update().filter(user=user, status=CartStatus.OPEN).first()
        lines = (
            list(cart.lines.select_related("stock_unit", "stock_unit__item").order_by("added_at", "cart_line_id"))
            if cart
            else []
        )
        if cart is None or not lines:
            raise CartEmptyError(message="カートに商品がないため注文を確定できません。")

        unavailable = [line.stock_unit_id for line in lines if not line.stock_unit.item.is_public]
        if unavailable:
            raise ItemNotAvailableError(context={"stock_unit_ids": unavailable})

        for line in lines:
            if line.quantity > QUANTITY_LIMIT:
                raise QuantityLimitExceededError(
                    context={
                        "stock_unit_id": line.stock_unit_id,
                        "limit": QUANTITY_LIMIT,
                        "current_quantity": line.quantity,
                        "requested_quantity": line.quantity,
                    }
                )

        coupon = cart.coupon
        subtotal = sum(line.stock_unit.price * line.quantity for line in lines)
        if coupon is not None:
            _raise_coupon_error(coupon, subtotal, confirmed_at)

        locked_units = _lock_stock_units([line.stock_unit_id for line in lines])
        shortages = [
            {
                "stock_unit_id": line.stock_unit_id,
                "sku": locked_units[line.stock_unit_id].sku,
                "requested_quantity": line.quantity,
                "available_quantity": locked_units[line.stock_unit_id].quantity,
            }
            for line in lines
            if line.quantity > locked_units[line.stock_unit_id].quantity
        ]
        if shortages:
            raise InsufficientStockError(context={"shortages": shortages})

        for line in lines:
            unit = locked_units[line.stock_unit_id]
            unit.quantity -= line.quantity
            unit.updated_at = confirmed_at
            unit.save(update_fields=["quantity", "updated_at"])

        amounts = calculate_amounts(
            [AmountLine(unit_price=line.stock_unit.price, quantity=line.quantity) for line in lines],
            coupon,
            confirmed_at,
        )

        order = PurchaseOrder.objects.create(
            order_number=next_order_number(),
            user=user,
            status=PurchaseOrderStatus.CREATED,
            coupon=coupon,
            coupon_code=coupon.code if coupon else None,
            coupon_discount_type=coupon.discount_type if coupon else None,
            coupon_discount_value=coupon.discount_value if coupon else None,
            subtotal=amounts.subtotal,
            discount_amount=amounts.discount_amount,
            discounted_subtotal=amounts.discounted_subtotal,
            shipping_fee=amounts.shipping_fee,
            tax_amount=amounts.tax_amount,
            total=amounts.total,
            ordered_at=confirmed_at,
        )

        PurchaseOrderLine.objects.bulk_create(
            [
                PurchaseOrderLine(
                    purchase_order=order,
                    stock_unit=line.stock_unit,
                    sku=line.stock_unit.sku,
                    item_name=line.stock_unit.item.name,
                    variant_name=line.stock_unit.variant_name,
                    unit_price=line.stock_unit.price,
                    quantity=line.quantity,
                    line_amount=line.stock_unit.price * line.quantity,
                )
                for line in lines
            ]
        )

        ShippingAddress.objects.create(purchase_order=order, **address)
        record_status_change(order, None, PurchaseOrderStatus.CREATED, confirmed_at, user)

        cart.status = CartStatus.CONVERTED
        cart.converted_at = confirmed_at
        cart.updated_at = confirmed_at
        cart.save(update_fields=["status", "converted_at", "updated_at"])

    logger.info("checkout", extra=build_extra(event="checkout", order_number=order.order_number))
    return representations.order_detail(order)


# trace: ADDR-001
def _raise_coupon_error(coupon: Any, subtotal: int, calculated_at: Any) -> None:
    """注文確定時のクーポン再判定で、適用できない場合に業務エラーを送出する。"""
    reason = coupon_not_applicable_reason(coupon, subtotal, calculated_at)
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


# trace: ADDR-001
def _lock_stock_units(stock_unit_ids: list[int]) -> dict[int, StockUnit]:
    """在庫単位行を在庫単位IDの昇順でロックして取得する（ADDR-001 DD-005）。"""
    unique_ids = sorted(set(stock_unit_ids))
    units = StockUnit.objects.select_for_update().filter(stock_unit_id__in=unique_ids).order_by("stock_unit_id")
    return {unit.stock_unit_id: unit for unit in units}


# trace: ADDR-001
def record_status_change(
    order: PurchaseOrder,
    from_status: str | None,
    to_status: str,
    changed_at: Any,
    actor: User,
) -> None:
    """注文状態履歴を1件記録する（CMN-26）。"""
    PurchaseOrderStatusHistory.objects.create(
        purchase_order=order,
        from_status=from_status,
        to_status=to_status,
        changed_at=changed_at,
        actor_user=actor,
        actor_role=actor.role,
    )


# trace: ADDR-001
def _get_own_order(user: User, raw_order_id: Any, lock: bool = False) -> PurchaseOrder:
    """購入者本人の注文を取得する（他の購入者の注文は対象なしとする）。"""
    order_id = parse_int(raw_order_id)
    if order_id is None:
        raise NotFoundError(message="指定した注文が見つかりません。")
    queryset = PurchaseOrder.objects.select_for_update() if lock else PurchaseOrder.objects.all()
    order = queryset.filter(purchase_order_id=order_id, user=user).first()
    if order is None:
        raise NotFoundError(message="指定した注文が見つかりません。")
    return order


# trace: ADDR-001
def list_orders(user: User, raw_page: Any = None) -> dict[str, Any]:
    """注文履歴一覧照会（FR-032）。本人の注文のみを注文日時の降順で返す。"""
    page = parse_page(raw_page)
    queryset = (
        PurchaseOrder.objects.filter(user=user).prefetch_related("lines").order_by("-ordered_at", "-purchase_order_id")
    )
    page_data = paginate(queryset, page, ORDER_PAGE_SIZE)
    page_data["results"] = [
        {
            "purchase_order_id": order.purchase_order_id,
            "order_number": order.order_number,
            "ordered_at": timeutils.jst(order.ordered_at),
            "status": order.status,
            "total": order.total,
            "total_quantity": sum(line.quantity for line in order.lines.all()),
        }
        for order in page_data["results"]
    ]
    return page_data


# trace: ADDR-001
def get_order_detail(user: User, raw_order_id: Any) -> dict[str, Any]:
    """注文詳細照会（FR-033）。本人の注文のみを返す。"""
    order = _get_own_order(user, raw_order_id)
    return representations.order_detail(order)


# trace: ADDR-001, ADDR-009, ADDR-013
def pay_order(user: User, raw_order_id: Any, raw_mock_result: Any = None) -> dict[str, Any]:
    """支払（FR-031）。注文行をロックしてから状態を判定し、送信と結果反映を同一トランザクションで確定する。"""
    mock_result = strip_value(raw_mock_result) or APPROVE
    if mock_result not in {APPROVE, DECLINE}:
        raise ValidationError(
            details=[{"field": "mock_result", "reason": "模擬決済の結果は approve または decline を指定してください。"}]
        )

    with transaction.atomic():
        # 手順4・手順5：注文行のロックを取得し、ロック取得後に読み直した状態だけで判定する（ADDR-013 DD-001、INV-002）。
        order = _get_own_order(user, raw_order_id, lock=True)
        if order.status != PurchaseOrderStatus.CREATED:
            # 決済ゲートウェイを呼び出さずに終了する（FR-031 E-031-05、ADDR-013 DD-002）。
            raise InvalidStatusTransitionError(
                message="現在の注文状態では支払できません。",
                context={"current_status": order.status},
            )
        failure = _authorize_locked_order(order, mock_result, user)
    # 否認・連携エラーの業務例外は決済記録のコミット完了後に送出する（ADDR-013 DD-004、INV-006）。
    if failure is not None:
        raise failure
    return representations.order_detail(order)


# trace: ADDR-009, ADDR-013
def _authorize_locked_order(order: PurchaseOrder, mock_result: str, actor: User) -> AppError | None:
    """ロック保持区間で決済要求を送信し、結果を同一トランザクションへ反映する（送出すべき業務例外を返す）。"""
    request = PaymentRequest(
        order_number=order.order_number,
        amount=order.total,
        currency=CURRENCY_JPY,
        mock_result=mock_result,
    )
    try:
        response = payment_client.authorize(request)
    except PaymentGatewayError:
        _record_payment(order, PaymentResult.ERROR, order.total, None, timeutils.now())
        return PaymentServiceError()

    if response.result != RESULT_APPROVED:
        _record_payment(order, PaymentResult.DECLINED, order.total, None, response.processed_at)
        return PaymentDeclinedError()

    # 手順8：承認の結果反映。状態の再判定は行わない（判定はロック取得後の1回だけ。ADDR-013 決定内容）。
    paid_at = timeutils.now()
    PaymentRecord.objects.create(
        purchase_order=order,
        result=PaymentResult.APPROVED,
        amount=order.total,
        transaction_ref=response.transaction_ref,
        processed_at=response.processed_at,
    )
    order.status = PurchaseOrderStatus.PAID
    order.paid_at = paid_at
    order.save(update_fields=["status", "paid_at"])
    record_status_change(order, PurchaseOrderStatus.CREATED, PurchaseOrderStatus.PAID, paid_at, actor)
    return None


# trace: ADDR-009, ADDR-013
def _record_payment(
    order: PurchaseOrder,
    result: str,
    amount: int,
    transaction_ref: str | None,
    processed_at: Any,
) -> None:
    """決済記録を1件登録する（否認・連携エラーでも登録する）。呼び出し元のトランザクションで確定する。"""
    PaymentRecord.objects.create(
        purchase_order=order,
        result=result,
        amount=amount,
        transaction_ref=transaction_ref,
        processed_at=processed_at or timeutils.now(),
    )


# trace: ADDR-001
def cancel_order(user: User, raw_order_id: Any) -> dict[str, Any]:
    """注文キャンセル（FR-034）。在庫を戻し、状態履歴を記録する。"""
    with transaction.atomic():
        order = _get_own_order(user, raw_order_id, lock=True)
        cancel_locked_order(order, user)
    return representations.order_detail(order)


# trace: ADDR-001
def cancel_locked_order(order: PurchaseOrder, actor: User) -> None:
    """ロック済みの注文をキャンセルし、全明細の在庫を戻す（FR-034、FR-045 共通）。"""
    if order.status not in {PurchaseOrderStatus.CREATED, PurchaseOrderStatus.PAID}:
        raise InvalidStatusTransitionError(
            message="現在の注文状態ではキャンセルできません。",
            context={"current_status": order.status},
        )
    cancelled_at = timeutils.now()
    previous_status = order.status
    lines = list(order.lines.order_by("stock_unit_id"))
    locked_units = _lock_stock_units([line.stock_unit_id for line in lines])
    for line in lines:
        unit = locked_units[line.stock_unit_id]
        unit.quantity += line.quantity
        unit.updated_at = cancelled_at
        unit.save(update_fields=["quantity", "updated_at"])

    order.status = PurchaseOrderStatus.CANCELLED
    order.cancelled_at = cancelled_at
    order.save(update_fields=["status", "cancelled_at"])
    record_status_change(order, previous_status, PurchaseOrderStatus.CANCELLED, cancelled_at, actor)
