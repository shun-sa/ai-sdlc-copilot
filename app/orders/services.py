# trace: ADDR-003, ADDR-008, ADDR-009
"""注文の業務ロジック（FR-030〜FR-034、FR-041〜FR-045）。

更新系は対象注文行をロックしてから状態を再判定し、在庫単位は識別子の昇順でロックする
（ADDR-003 DD-002, DD-003）。決済要求はトランザクションの外で行う（ADDR-009 DD-004）。
"""

from __future__ import annotations

import datetime as dt
import logging
from typing import Any

from django.db import transaction
from django.db.models import Q, QuerySet

from accounts.models import ROLE_ADMIN, ROLE_BUYER, User
from carts import services as cart_services
from carts.models import CART_OPEN, QUANTITY_LIMIT
from common import timeutils
from common.exceptions import (
    CartEmpty,
    CouponExpired,
    CouponMinSpendNotMet,
    CouponNotYetValid,
    InsufficientStock,
    InvalidStatusTransition,
    ItemNotAvailable,
    NotFoundError,
    PaymentDeclined,
    PaymentServiceError,
    QuantityLimitExceeded,
    ValidationFailed,
)
from common.pagination import paginate
from common.validators import (
    ORDER_NUMBER_PATTERN,
    PHONE_PATTERN,
    POSTAL_CODE_PATTERN,
    TRACKING_NUMBER_PATTERN,
    ValidationCollector,
    normalize_text,
    parse_int,
    validate_page,
)
from orders.models import (
    PAYMENT_APPROVED,
    PAYMENT_DECLINED,
    PAYMENT_ERROR,
    STATUS_CANCELLED,
    STATUS_CREATED,
    STATUS_DELIVERED,
    STATUS_PAID,
    STATUS_SHIPPED,
    OrderNumberSequence,
    PaymentRecord,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseOrderStatusHistory,
    ShippingAddress,
)
from payments import services as payment_services
from payments.gateway import MOCK_APPROVE, PaymentGatewayError

logger = logging.getLogger("minicommerce.orders")

ORDER_PAGE_SIZE = 20
PREFECTURE_CODES = tuple(f"{number:02d}" for number in range(1, 48))
ORDER_STATUSES = (STATUS_CREATED, STATUS_PAID, STATUS_SHIPPED, STATUS_DELIVERED, STATUS_CANCELLED)


# trace: ADDR-003
def validate_shipping_input(payload: dict[str, Any]) -> dict[str, str]:
    """配送先の入力を判定し、登録する値へ整形する（FR-030 6.15.3）。"""
    collector = ValidationCollector()
    recipient_name = normalize_text(payload.get("recipient_name"))
    postal_code = normalize_text(payload.get("postal_code"))
    prefecture_code = normalize_text(payload.get("prefecture_code"))
    address_line1 = normalize_text(payload.get("address_line1"))
    address_line2 = normalize_text(payload.get("address_line2"))
    phone_number = normalize_text(payload.get("phone_number"))

    if not recipient_name:
        collector.add("recipient_name", "受取人氏名を入力してください。")
    elif len(recipient_name) > 50:
        collector.add("recipient_name", "受取人氏名は50文字以内で入力してください。")

    if not postal_code:
        collector.add("postal_code", "郵便番号を入力してください。")
    elif not POSTAL_CODE_PATTERN.match(postal_code):
        collector.add("postal_code", "郵便番号は「1234567」または「123-4567」の形式で入力してください。")

    if not prefecture_code:
        collector.add("prefecture_code", "都道府県を選択してください。")
    elif prefecture_code not in PREFECTURE_CODES:
        collector.add("prefecture_code", "都道府県の指定が正しくありません。")

    if not address_line1:
        collector.add("address_line1", "住所1（市区町村・番地）を入力してください。")
    elif len(address_line1) > 100:
        collector.add("address_line1", "住所1は100文字以内で入力してください。")

    if len(address_line2) > 100:
        collector.add("address_line2", "住所2は100文字以内で入力してください。")

    if not phone_number:
        collector.add("phone_number", "電話番号を入力してください。")
    elif not PHONE_PATTERN.match(phone_number) or not 10 <= len(phone_number.replace("-", "")) <= 11:
        collector.add("phone_number", "電話番号は数字10桁または11桁で入力してください。")

    collector.raise_if_any()
    return {
        "recipient_name": recipient_name,
        "postal_code": postal_code.replace("-", ""),
        "prefecture_code": prefecture_code,
        "address_line1": address_line1,
        "address_line2": address_line2,
        "phone_number": phone_number.replace("-", ""),
    }


# trace: ADDR-003
def checkout(user: User, payload: dict[str, Any]) -> PurchaseOrder:
    """注文確定（FR-030）。在庫を一括で引き当て、注文を1件作成する。"""
    shipping = validate_shipping_input(payload)
    at = timeutils.now()
    with transaction.atomic():
        cart = cart_services.get_open_cart(user)
        if cart is None:
            raise CartEmpty()
        lines = cart_services.load_lines(cart)
        if not lines:
            raise CartEmpty()
        locked_units = cart_services.lock_stock_units([line.stock_unit_id for line in lines])
        cart = cart_services.lock_cart(cart)
        if cart.status != CART_OPEN:
            raise CartEmpty()
        lines = cart_services.load_lines(cart)
        if not lines:
            raise CartEmpty()
        if any(line.stock_unit_id not in locked_units for line in lines):
            locked_units = cart_services.lock_stock_units([line.stock_unit_id for line in lines])

        unavailable = [line.stock_unit_id for line in lines if not line.stock_unit.item.is_public]
        if unavailable:
            raise ItemNotAvailable(context={"stock_unit_ids": unavailable})

        for line in lines:
            if line.quantity > QUANTITY_LIMIT:
                raise QuantityLimitExceeded(
                    context={
                        "stock_unit_id": line.stock_unit_id,
                        "limit": QUANTITY_LIMIT,
                        "current_quantity": line.quantity,
                        "requested_quantity": line.quantity,
                    }
                )

        line_inputs = [(locked_units[line.stock_unit_id].price, line.quantity) for line in lines]
        coupon = cart.coupon
        subtotal = sum(price * quantity for price, quantity in line_inputs)
        if coupon is not None:
            period = {
                "valid_from": timeutils.to_iso(coupon.valid_from),
                "valid_until": timeutils.to_iso(coupon.valid_until),
            }
            if at < coupon.valid_from:
                raise CouponNotYetValid(context=period)
            if at > coupon.valid_until:
                raise CouponExpired(context=period)
            if subtotal < coupon.min_spend:
                raise CouponMinSpendNotMet(context={"min_spend": coupon.min_spend, "subtotal": subtotal})

        shortages = []
        for line in lines:
            unit = locked_units[line.stock_unit_id]
            if line.quantity > unit.quantity:
                shortages.append(
                    {
                        "stock_unit_id": unit.pk,
                        "sku": unit.sku,
                        "requested_quantity": line.quantity,
                        "available_quantity": unit.quantity,
                    }
                )
        if shortages:
            raise InsufficientStock(context={"shortages": shortages})

        for line in lines:
            unit = locked_units[line.stock_unit_id]
            unit.quantity -= line.quantity
            unit.updated_at = at
            unit.save(update_fields=["quantity", "updated_at"])

        calculated = cart_services.calculate_amounts(line_inputs, coupon, at)
        amounts = calculated["amounts"]
        sequence = OrderNumberSequence.objects.create()
        order = PurchaseOrder.objects.create(
            order_number=sequence.order_number,
            user=user,
            status=STATUS_CREATED,
            coupon=coupon,
            coupon_code=coupon.code if coupon else None,
            coupon_discount_type=coupon.discount_type if coupon else None,
            coupon_discount_value=coupon.discount_value if coupon else None,
            subtotal=amounts["subtotal"],
            discount_amount=amounts["discount_amount"],
            discounted_subtotal=amounts["discounted_subtotal"],
            shipping_fee=amounts["shipping_fee"],
            tax_amount=amounts["tax_amount"],
            total=amounts["total"],
            ordered_at=at,
        )
        PurchaseOrderLine.objects.bulk_create(
            [
                PurchaseOrderLine(
                    purchase_order=order,
                    stock_unit_id=line.stock_unit_id,
                    sku=line.stock_unit.sku,
                    item_name=line.stock_unit.item.name,
                    variant_name=line.stock_unit.variant_name,
                    unit_price=locked_units[line.stock_unit_id].price,
                    quantity=line.quantity,
                    line_amount=locked_units[line.stock_unit_id].price * line.quantity,
                )
                for line in lines
            ]
        )
        ShippingAddress.objects.create(purchase_order=order, **shipping)
        PurchaseOrderStatusHistory.objects.create(
            purchase_order=order,
            from_status=None,
            to_status=STATUS_CREATED,
            changed_at=at,
            actor_user=user,
            actor_role=ROLE_BUYER,
        )
        cart_services.mark_converted(cart, at)
    return load_order(order.pk)


# trace: ADDR-003
def load_order(order_id: int) -> PurchaseOrder:
    """注文詳細の表示に必要な関連データをまとめて取得する。"""
    order = (
        PurchaseOrder.objects.select_related("shipping_address", "user")
        .prefetch_related("lines", "status_history", "payment_records")
        .filter(pk=order_id)
        .first()
    )
    if order is None:
        raise NotFoundError()
    return order


# trace: ADDR-003
def find_buyer_order(user: User, order_id: Any) -> PurchaseOrder:
    """購入者本人の注文を取得する（他の購入者の注文は対象なしとする。PRM-01）。"""
    identifier = parse_int(order_id)
    if identifier is None:
        raise NotFoundError()
    order = PurchaseOrder.objects.filter(pk=identifier, user=user).first()
    if order is None:
        raise NotFoundError()
    return order


# trace: ADDR-003
def find_any_order(order_id: Any) -> PurchaseOrder:
    """全購入者の注文から取得する（管理者向け）。"""
    identifier = parse_int(order_id)
    if identifier is None:
        raise NotFoundError()
    order = PurchaseOrder.objects.filter(pk=identifier).first()
    if order is None:
        raise NotFoundError()
    return order


# trace: ADDR-003
def list_buyer_orders(user: User, params: dict[str, Any]) -> tuple[list[PurchaseOrder], dict[str, int]]:
    """注文履歴一覧照会（FR-032）。本人の注文のみを注文日時の降順で返す。"""
    collector = ValidationCollector()
    page = validate_page(params.get("page"), collector)
    collector.raise_if_any()
    queryset = (
        PurchaseOrder.objects.filter(user=user)
        .prefetch_related("lines")
        .order_by("-ordered_at", "-id")
    )
    return paginate(queryset, page, ORDER_PAGE_SIZE)


# trace: ADDR-003
def get_buyer_order(user: User, order_id: Any) -> PurchaseOrder:
    """注文詳細照会（購入者）（FR-033）。"""
    order = find_buyer_order(user, order_id)
    return load_order(order.pk)


# trace: ADDR-009
def pay(user: User, order_id: Any, payload: dict[str, Any]) -> PurchaseOrder:
    """支払（模擬決済）（FR-031）。承認された場合に注文を支払済にする。"""
    mock_result = normalize_text(payload.get("mock_result")) or MOCK_APPROVE
    if not payment_services.is_valid_mock_result(mock_result):
        raise ValidationFailed(
            details=[{"field": "mock_result", "reason": "模擬決済の結果を選択してください。"}]
        )

    order = find_buyer_order(user, order_id)
    with transaction.atomic():
        locked = PurchaseOrder.objects.select_for_update().get(pk=order.pk)
        if locked.status != STATUS_CREATED:
            raise InvalidStatusTransition(context={"current_status": locked.status})
        order_number = locked.order_number
        amount = locked.total

    try:
        result = payment_services.authorize(order_number, amount, mock_result)
    except PaymentGatewayError:
        logger.warning("payment gateway error", extra={"order_id": order.pk})
        with transaction.atomic():
            PaymentRecord.objects.create(
                purchase_order_id=order.pk,
                result=PAYMENT_ERROR,
                amount=amount,
                transaction_ref=None,
                processed_at=timeutils.now(),
            )
        raise PaymentServiceError()

    if not result.approved:
        with transaction.atomic():
            PaymentRecord.objects.create(
                purchase_order_id=order.pk,
                result=PAYMENT_DECLINED,
                amount=amount,
                transaction_ref=None,
                processed_at=result.processed_at,
            )
        raise PaymentDeclined()

    at = timeutils.now()
    with transaction.atomic():
        locked = PurchaseOrder.objects.select_for_update().get(pk=order.pk)
        if locked.status != STATUS_CREATED:
            raise InvalidStatusTransition(context={"current_status": locked.status})
        PaymentRecord.objects.create(
            purchase_order=locked,
            result=PAYMENT_APPROVED,
            amount=amount,
            transaction_ref=result.transaction_ref,
            processed_at=result.processed_at,
        )
        locked.status = STATUS_PAID
        locked.paid_at = at
        locked.save(update_fields=["status", "paid_at"])
        PurchaseOrderStatusHistory.objects.create(
            purchase_order=locked,
            from_status=STATUS_CREATED,
            to_status=STATUS_PAID,
            changed_at=at,
            actor_user=user,
            actor_role=ROLE_BUYER,
        )
    return load_order(order.pk)


# trace: ADDR-003
def cancel_order(order: PurchaseOrder, actor: User, actor_role: str) -> PurchaseOrder:
    """注文をキャンセルし、全明細の数量を在庫数量へ戻す（FR-034、FR-045）。"""
    at = timeutils.now()
    with transaction.atomic():
        locked = PurchaseOrder.objects.select_for_update().get(pk=order.pk)
        if locked.status not in (STATUS_CREATED, STATUS_PAID):
            raise InvalidStatusTransition(context={"current_status": locked.status})
        lines = list(locked.lines.all())
        locked_units = cart_services.lock_stock_units([line.stock_unit_id for line in lines])
        from_status = locked.status
        for line in lines:
            unit = locked_units[line.stock_unit_id]
            unit.quantity += line.quantity
            unit.updated_at = at
            unit.save(update_fields=["quantity", "updated_at"])
        locked.status = STATUS_CANCELLED
        locked.cancelled_at = at
        locked.save(update_fields=["status", "cancelled_at"])
        PurchaseOrderStatusHistory.objects.create(
            purchase_order=locked,
            from_status=from_status,
            to_status=STATUS_CANCELLED,
            changed_at=at,
            actor_user=actor,
            actor_role=actor_role,
        )
    return load_order(order.pk)


# trace: ADDR-003
def cancel_by_buyer(user: User, order_id: Any) -> PurchaseOrder:
    """注文キャンセル（購入者）（FR-034）。"""
    order = find_buyer_order(user, order_id)
    return cancel_order(order, user, ROLE_BUYER)


# trace: ADDR-003
def cancel_by_admin(admin_user: User, order_id: Any) -> PurchaseOrder:
    """注文キャンセル（管理者）（FR-045）。"""
    order = find_any_order(order_id)
    return cancel_order(order, admin_user, ROLE_ADMIN)


# trace: ADDR-003
def ship(admin_user: User, order_id: Any, payload: dict[str, Any]) -> PurchaseOrder:
    """出荷登録（FR-043）。支払済の注文を出荷済にする。"""
    tracking_number = normalize_text(payload.get("tracking_number"))
    if tracking_number and not TRACKING_NUMBER_PATTERN.match(tracking_number):
        raise ValidationFailed(
            details=[
                {
                    "field": "tracking_number",
                    "reason": "配送伝票番号は英数字とハイフンの30文字以内で入力してください。",
                }
            ]
        )
    order = find_any_order(order_id)
    at = timeutils.now()
    with transaction.atomic():
        locked = PurchaseOrder.objects.select_for_update().get(pk=order.pk)
        if locked.status != STATUS_PAID:
            raise InvalidStatusTransition(context={"current_status": locked.status})
        locked.status = STATUS_SHIPPED
        locked.shipped_at = at
        if tracking_number:
            locked.tracking_number = tracking_number
        locked.save(update_fields=["status", "shipped_at", "tracking_number"])
        PurchaseOrderStatusHistory.objects.create(
            purchase_order=locked,
            from_status=STATUS_PAID,
            to_status=STATUS_SHIPPED,
            changed_at=at,
            actor_user=admin_user,
            actor_role=ROLE_ADMIN,
        )
    return load_order(order.pk)


# trace: ADDR-003
def deliver(admin_user: User, order_id: Any) -> PurchaseOrder:
    """配達完了登録（FR-044）。出荷済の注文を配達完了にする。"""
    order = find_any_order(order_id)
    at = timeutils.now()
    with transaction.atomic():
        locked = PurchaseOrder.objects.select_for_update().get(pk=order.pk)
        if locked.status != STATUS_SHIPPED:
            raise InvalidStatusTransition(context={"current_status": locked.status})
        locked.status = STATUS_DELIVERED
        locked.delivered_at = at
        locked.save(update_fields=["status", "delivered_at"])
        PurchaseOrderStatusHistory.objects.create(
            purchase_order=locked,
            from_status=STATUS_SHIPPED,
            to_status=STATUS_DELIVERED,
            changed_at=at,
            actor_user=admin_user,
            actor_role=ROLE_ADMIN,
        )
    return load_order(order.pk)


# trace: ADDR-003
def get_admin_order(order_id: Any) -> PurchaseOrder:
    """注文詳細照会（管理者）（FR-042）。"""
    order = find_any_order(order_id)
    return load_order(order.pk)


# trace: ADDR-008
def admin_order_queryset(conditions: dict[str, Any]) -> QuerySet[PurchaseOrder]:
    """管理者向け注文検索の問い合わせを組み立てる。"""
    queryset = PurchaseOrder.objects.select_related("user").prefetch_related("lines")
    if conditions["order_number"]:
        queryset = queryset.filter(order_number=conditions["order_number"])
    if conditions["statuses"]:
        queryset = queryset.filter(status__in=conditions["statuses"])
    if conditions["ordered_from"]:
        queryset = queryset.filter(ordered_at__gte=timeutils.start_of_day(conditions["ordered_from"]))
    if conditions["ordered_to"]:
        queryset = queryset.filter(ordered_at__lt=timeutils.start_of_next_day(conditions["ordered_to"]))
    if conditions["buyer_email"]:
        queryset = queryset.filter(Q(user__email__icontains=conditions["buyer_email"]))
    return queryset.order_by("-ordered_at", "-id")


# trace: ADDR-008
def admin_search_orders(
    params: dict[str, Any],
) -> tuple[list[PurchaseOrder], dict[str, int], dict[str, Any]]:
    """注文一覧検索（管理者）（FR-041）。"""
    collector = ValidationCollector()
    order_number = normalize_text(params.get("order_number"))
    buyer_email = normalize_text(params.get("buyer_email"))
    raw_statuses = params.get("status") or []
    if isinstance(raw_statuses, str):
        raw_statuses = [raw_statuses]
    statuses: list[str] = []
    for raw in raw_statuses:
        value = normalize_text(raw)
        if not value:
            continue
        if value not in ORDER_STATUSES:
            collector.add("status", "注文状態の指定が正しくありません。")
        elif value not in statuses:
            statuses.append(value)

    if order_number and not ORDER_NUMBER_PATTERN.match(order_number):
        collector.add("order_number", "注文番号は「PO-」と数字8桁で入力してください。")
    if len(buyer_email) > 254:
        collector.add("buyer_email", "購入者のメールアドレスは254文字以内で入力してください。")

    ordered_from = parse_date_condition(params.get("ordered_from"), "ordered_from", collector)
    ordered_to = parse_date_condition(params.get("ordered_to"), "ordered_to", collector)
    if ordered_from and ordered_to and ordered_from > ordered_to:
        collector.add("ordered_from", "注文日（開始）には注文日（終了）以前の日付を指定してください。")
    page = validate_page(params.get("page"), collector)
    collector.raise_if_any()

    conditions = {
        "order_number": order_number,
        "statuses": statuses,
        "ordered_from": ordered_from,
        "ordered_to": ordered_to,
        "buyer_email": buyer_email,
    }
    orders, meta = paginate(admin_order_queryset(conditions), page, ORDER_PAGE_SIZE)
    return orders, meta, conditions


# trace: ADDR-008
def parse_date_condition(value: Any, field: str, collector: ValidationCollector) -> dt.date | None:
    """YYYY-MM-DD 形式の検索条件を解釈する。"""
    text = normalize_text(value)
    if not text:
        return None
    parsed = timeutils.parse_date(text)
    if parsed is None:
        collector.add(field, "日付を正しく入力してください。")
    return parsed
