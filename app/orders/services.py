# trace: ADDR-001, ADDR-004, ADDR-005, ADDR-007, ADDR-008, ADDR-011, ADDR-012
# trace: ENT-001, ENT-006, ENT-007, ENT-010, ENT-011, ENT-012, ENT-013, ENT-014
"""注文の業務処理（FR-030〜FR-034、FR-041〜FR-045）。画面と Web API の双方から呼ばれる（ADDR-012）。

更新を伴う処理は1トランザクション（READ COMMITTED）で、親行（利用中カートまたは注文）→ 在庫単位（識別子昇順）
→ 注文番号の採番ロックの順にだけロックし、ロック取得後に読み直したデータで判定する（ADDR-004 DD-001〜DD-003）。
"""

import re
from datetime import date, datetime, time
from typing import Any

from django.db import DatabaseError, connection, transaction
from django.db.models import F, Sum

from carts import pricing
from carts.models import Cart, CartItem
from catalog.models import StockUnit
from common import clock, codes
from common.codes import CartStatus, DiscountType, OrderStatus, PaymentResult, UserType
from common.errors import (
    MSG_SEARCH_CONDITION_ERROR,
    BusinessError,
    FieldError,
    FieldErrors,
    InputError,
    IntegrationError,
    NotFoundError,
    ServiceError,
    from_record,
    system_failure,
)
from common.faults import order_fault_point
from common.logging import log_error
from common.normalize import has_unstorable_chars, is_blank, parse_identifier, strip_text, unstorable_message
from common.paging import build_page, parse_page, slice_queryset
from common.submit_token import NO_TOKEN, TokenContext
from orders.models import Order, OrderItem, OrderStatusHistory, PaymentRecord, ShippingAddress
from payments import client as payment_client

ORDER_PAGE_SIZE = 20
MAX_QUANTITY_PER_STOCK_UNIT = 10
# 注文番号の採番ロックの固定キー（ADDR-005 4.3。一括投入・送信トークンのキーと区別する）
ORDER_NUMBER_LOCK_KEY = 7_013_000_001
ORDER_NUMBER_SEQUENCE = "orders_order_number_seq"
ORDER_NUMBER_MAX = 99_999_999
_POSTAL = re.compile(r"^(?:[0-9]{7}|[0-9]{3}-[0-9]{4})\Z")
_PHONE = re.compile(r"^[0-9-]+\Z")
_ORDER_NUMBER = re.compile(r"^PO-[0-9]{8}\Z")
_DATE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")
_TRACKING = re.compile(r"^[A-Za-z0-9-]{1,30}\Z")
MSG_ORDER_NOT_FOUND = "指定した注文が見つかりません。"
ADDRESS_FIELDS = ("recipient_name", "postal_code", "prefecture", "address_line1", "address_line2", "phone_number")


# ---------------------------------------------------------------------------
# 注文詳細内容（6.18.5・6.22.5）
# ---------------------------------------------------------------------------


# trace: ENT-010, ADDR-007
def _status_label(value: str | None) -> str | None:
    return OrderStatus(value).label if value else None


# trace: ADDR-001, ENT-010, ENT-011, ENT-012, ENT-014
def order_detail(order: Order) -> dict[str, Any]:
    """注文詳細内容（購入者）。決済記録と状態履歴の実行者の利用者IDは含めない（MSG-04）。"""
    return _detail(order, for_admin=False)


# trace: ADDR-001, ENT-010, ENT-011, ENT-012, ENT-013, ENT-014
def admin_order_detail(order: Order) -> dict[str, Any]:
    """注文詳細（管理者）の内容。購入者情報・決済記録・出荷登録可否・配達完了登録可否を加える。"""
    return _detail(order, for_admin=True)


# trace: ADDR-001, ENT-010, ENT-011, ENT-012, ENT-013, ENT-014
def _detail(order: Order, *, for_admin: bool) -> dict[str, Any]:
    items = list(OrderItem.objects.filter(order=order).order_by("pk"))
    address = ShippingAddress.objects.filter(order=order).first()
    history = list(OrderStatusHistory.objects.filter(order=order).order_by("changed_at", "pk"))
    status = order.status
    data: dict[str, Any] = {
        "order_id": order.pk,
        "order_number": order.order_number,
        "status": status,
        "status_label": _status_label(status),
        "ordered_at": order.ordered_at,
        "paid_at": order.paid_at,
        "shipped_at": order.shipped_at,
        "delivered_at": order.delivered_at,
        "cancelled_at": order.cancelled_at,
        "tracking_number": order.tracking_number,
        "items": [
            {
                "stock_unit_id": i.stock_unit_id,
                "sku": i.sku,
                "product_name": i.product_name,
                "variant_name": i.variant_name,
                "unit_price_excluding_tax": i.unit_price,
                "quantity": i.quantity,
                "line_amount": i.line_amount,
            }
            for i in items
        ],
        "coupon": (
            {
                "coupon_code": order.coupon_code,
                "discount_type": order.discount_type,
                "discount_type_label": DiscountType(order.discount_type).label,
                "discount_value": order.discount_value,
            }
            if order.coupon_code
            else None
        ),
        "amounts": {
            "subtotal": order.subtotal,
            "discount_amount": order.discount_amount,
            "discounted_subtotal": order.discounted_subtotal,
            "shipping_fee": order.shipping_fee,
            "tax_amount": order.tax_amount,
            "total_amount": order.total_amount,
        },
        "shipping_address": (
            {
                "recipient_name": address.recipient_name,
                "postal_code": address.postal_code,
                "prefecture": address.prefecture,
                "prefecture_label": codes.PREFECTURE_NAMES.get(address.prefecture),
                "address_line1": address.address_line1,
                "address_line2": address.address_line2,
                "phone_number": address.phone_number,
            }
            if address
            else None
        ),
        "status_history": [],
        "can_pay": status == OrderStatus.ACCEPTED,
        "can_cancel": status in (OrderStatus.ACCEPTED, OrderStatus.PAID),
    }
    for h in history:
        entry: dict[str, Any] = {
            "from_status": h.from_status,
            "from_status_label": _status_label(h.from_status),
            "to_status": h.to_status,
            "to_status_label": _status_label(h.to_status),
            "changed_at": h.changed_at,
            "actor_user_type": h.actor_user_type,
            "actor_user_type_label": UserType(h.actor_user_type).label,
        }
        if for_admin:
            entry["actor_user_id"] = h.actor_id
        data["status_history"].append(entry)
    if for_admin:
        buyer = order.buyer
        payments = PaymentRecord.objects.filter(order=order).order_by("processed_at", "pk")
        data["buyer"] = {"user_id": buyer.pk, "email": buyer.email, "name": buyer.name}
        data["payments"] = [
            {
                "result": p.result,
                "result_label": PaymentResult(p.result).label,
                "amount": p.amount,
                "transaction_ref": p.transaction_ref,
                "processed_at": p.processed_at,
            }
            for p in payments
        ]
        data["can_ship"] = status == OrderStatus.PAID
        data["can_deliver"] = status == OrderStatus.SHIPPED
    return data


# ---------------------------------------------------------------------------
# FR-030 注文確定
# ---------------------------------------------------------------------------


# trace: ADDR-001, ENT-012
def _validate_address(address: Any) -> dict[str, Any]:
    """配送先の全項目を判定する（FR-030 手順3）。誤りは全項目分をまとめて通知する（E-030-03）。"""
    source = address if isinstance(address, dict) else {}
    errors = FieldErrors()
    values: dict[str, Any] = {}
    prefix = "shipping_address."

    def text(key: str) -> Any:
        return strip_text(source.get(key))

    name = text("recipient_name")
    if is_blank(name):
        errors.add(prefix + "recipient_name", codes.FIELD_REQUIRED, "受取人氏名を入力してください。")
    elif not isinstance(name, str):
        errors.add(prefix + "recipient_name", codes.FIELD_INVALID_TYPE, "受取人氏名は文字列で入力してください。")
    elif has_unstorable_chars(name):
        errors.add(prefix + "recipient_name", codes.FIELD_INVALID_FORMAT, unstorable_message("受取人氏名"))
    elif len(name) > 50:
        errors.add(prefix + "recipient_name", codes.FIELD_INVALID_LENGTH, "受取人氏名は50文字以内で入力してください。")
    values["recipient_name"] = name

    postal = text("postal_code")
    if is_blank(postal):
        errors.add(prefix + "postal_code", codes.FIELD_REQUIRED, "郵便番号を入力してください。")
    elif not isinstance(postal, str) or not _POSTAL.match(postal):
        errors.add(
            prefix + "postal_code",
            codes.FIELD_INVALID_FORMAT,
            "郵便番号は「1234567」または「123-4567」の形式で入力してください。",
        )
    else:
        values["postal_code"] = postal.replace("-", "")

    prefecture = text("prefecture")
    if is_blank(prefecture):
        errors.add(prefix + "prefecture", codes.FIELD_REQUIRED, "都道府県を選択してください。")
    elif not isinstance(prefecture, str) or prefecture not in codes.PREFECTURE_NAMES:
        errors.add(prefix + "prefecture", codes.FIELD_INVALID_CHOICE, "都道府県を選択してください。")
    values["prefecture"] = prefecture

    line1 = text("address_line1")
    if is_blank(line1):
        errors.add(prefix + "address_line1", codes.FIELD_REQUIRED, "住所1（市区町村・番地）を入力してください。")
    elif not isinstance(line1, str):
        errors.add(prefix + "address_line1", codes.FIELD_INVALID_TYPE, "住所1は文字列で入力してください。")
    elif has_unstorable_chars(line1):
        errors.add(prefix + "address_line1", codes.FIELD_INVALID_FORMAT, unstorable_message("住所1"))
    elif len(line1) > 100:
        errors.add(prefix + "address_line1", codes.FIELD_INVALID_LENGTH, "住所1は100文字以内で入力してください。")
    values["address_line1"] = line1

    line2 = text("address_line2")
    if line2 is None or line2 == "":
        values["address_line2"] = None
    elif not isinstance(line2, str):
        errors.add(prefix + "address_line2", codes.FIELD_INVALID_TYPE, "住所2は文字列で入力してください。")
    elif has_unstorable_chars(line2):
        errors.add(prefix + "address_line2", codes.FIELD_INVALID_FORMAT, unstorable_message("住所2"))
    elif len(line2) > 100:
        errors.add(prefix + "address_line2", codes.FIELD_INVALID_LENGTH, "住所2は100文字以内で入力してください。")
    else:
        values["address_line2"] = line2

    phone = text("phone_number")
    if is_blank(phone):
        errors.add(prefix + "phone_number", codes.FIELD_REQUIRED, "電話番号を入力してください。")
    elif not isinstance(phone, str) or not _PHONE.match(phone) or len(phone.replace("-", "")) not in (10, 11):
        errors.add(
            prefix + "phone_number",
            codes.FIELD_INVALID_FORMAT,
            "電話番号は数字（ハイフン可）で、ハイフンを除いて10桁または11桁で入力してください。",
        )
    else:
        values["phone_number"] = phone.replace("-", "")
    errors.raise_if_any("E-030-03")
    return values


# trace: ADDR-005
def _issue_order_number() -> str:
    """注文番号の払い出し（固定キーのトランザクション単位アドバイザリロック取得後に専用シーケンスから。ADDR-005）。"""
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", [ORDER_NUMBER_LOCK_KEY])
        cursor.execute("SELECT nextval(%s)", [ORDER_NUMBER_SEQUENCE])
        value = int(cursor.fetchone()[0])
    if value > ORDER_NUMBER_MAX:
        raise DatabaseError("order number exhausted")
    return f"PO-{value:08d}"


# trace: ADDR-001, ADDR-004, ADDR-005, ADDR-011, ENT-010, ENT-011, ENT-012, ENT-014
def place_order(user: Any, shipping_address: Any) -> dict[str, Any]:
    """FR-030 注文確定。数量上限・クーポン条件・在庫を再判定し全明細を一括で引き当てる。"""
    address = _validate_address(shipping_address)
    now = clock.now_seconds()
    try:
        with transaction.atomic():
            cart = Cart.objects.select_for_update().filter(buyer=user, status=CartStatus.ACTIVE).first()
            items = list(CartItem.objects.filter(cart=cart).order_by("pk")) if cart is not None else []
            if not items:
                raise BusinessError(
                    "E-030-04", "カートに商品がないため、注文を確定できません。", reason=codes.REASON_CART_EMPTY
                )
            stock_ids = sorted({i.stock_unit_id for i in items})
            locked = {s.pk: s for s in StockUnit.objects.select_for_update().filter(pk__in=stock_ids).order_by("pk")}
            products = {s.pk: s.product for s in StockUnit.objects.select_related("product").filter(pk__in=stock_ids)}
            unavailable = [i for i in items if not products[i.stock_unit_id].is_public]
            if unavailable:
                names = "、".join(
                    f"{products[i.stock_unit_id].name}（{locked[i.stock_unit_id].variant_name}）" for i in unavailable
                )
                raise BusinessError(
                    "E-030-05",
                    f"販売を終了した商品がカートに含まれています。カートから削除してください。（{names}）",
                    reason=codes.REASON_UNAVAILABLE_PRODUCT,
                    values={"unavailable_stock_unit_ids": [i.stock_unit_id for i in unavailable]},
                )
            over = next((i for i in items if i.quantity > MAX_QUANTITY_PER_STOCK_UNIT), None)
            if over is not None:
                unit = locked[over.stock_unit_id]
                raise BusinessError(
                    "E-030-06",
                    f"同じ規格は1注文につき10個までです（対象：{products[unit.pk].name}（{unit.variant_name}）、"
                    f"カート内数量：{over.quantity}個）。カートで数量を変更してください。",
                    reason=codes.REASON_QUANTITY_LIMIT_EXCEEDED,
                    values={
                        "stock_unit_id": unit.pk,
                        "max_quantity": MAX_QUANTITY_PER_STOCK_UNIT,
                        "current_quantity": over.quantity,
                        "resulting_quantity": over.quantity,
                    },
                )
            coupon = cart.coupon
            lines = [(locked[i.stock_unit_id].price_excluding_tax, i.quantity) for i in items]
            if coupon is not None:
                _check_coupon(coupon, sum(price * qty for price, qty in lines), now)
            shortages = [i for i in items if i.quantity > locked[i.stock_unit_id].stock_quantity]
            if shortages:
                detail = "、".join(
                    f"{locked[i.stock_unit_id].sku}：在庫数量{locked[i.stock_unit_id].stock_quantity}個"
                    for i in shortages
                )
                raise BusinessError(
                    "E-030-10",
                    f"在庫が不足している商品があります。カートで数量を変更してください。（{detail}）",
                    reason=codes.REASON_INSUFFICIENT_STOCK,
                    values={
                        "stock_units": [
                            {
                                "stock_unit_id": i.stock_unit_id,
                                "sku": locked[i.stock_unit_id].sku,
                                "requested_quantity": i.quantity,
                                "stock_quantity": locked[i.stock_unit_id].stock_quantity,
                            }
                            for i in shortages
                        ]
                    },
                )
            for item in items:
                StockUnit.objects.filter(pk=item.stock_unit_id).update(
                    stock_quantity=F("stock_quantity") - item.quantity, updated_at=now
                )
            order_fault_point("after_stock_decrement")
            amounts = pricing.calculate(lines, coupon, now)
            order = Order.objects.create(
                order_number=_issue_order_number(),
                buyer=user,
                status=OrderStatus.ACCEPTED,
                coupon=coupon,
                coupon_code=coupon.coupon_code if coupon else None,
                discount_type=coupon.discount_type if coupon else None,
                discount_value=coupon.discount_value if coupon else None,
                subtotal=amounts.subtotal,
                discount_amount=amounts.discount_amount,
                discounted_subtotal=amounts.discounted_subtotal,
                shipping_fee=amounts.shipping_fee,
                tax_amount=amounts.tax_amount,
                total_amount=amounts.total_amount,
                ordered_at=now,
            )
            order_fault_point("after_order_insert")
            for item in items:
                unit = locked[item.stock_unit_id]
                OrderItem.objects.create(
                    order=order,
                    stock_unit=unit,
                    sku=unit.sku,
                    product_name=products[unit.pk].name,
                    variant_name=unit.variant_name,
                    unit_price=unit.price_excluding_tax,
                    quantity=item.quantity,
                    line_amount=unit.price_excluding_tax * item.quantity,
                )
            ShippingAddress.objects.create(order=order, **address)
            OrderStatusHistory.objects.create(
                order=order,
                from_status=None,
                to_status=OrderStatus.ACCEPTED,
                changed_at=now,
                actor=user,
                actor_user_type=UserType.BUYER,
            )
            cart.status = CartStatus.ORDERED
            cart.ordered_at = now
            cart.save(update_fields=["status", "ordered_at"])
            return order_detail(order)
    except ServiceError:
        raise
    except DatabaseError as exc:
        raise system_failure("E-030-11") from exc


# trace: ADDR-001, ENT-007
def _check_coupon(coupon: Any, subtotal: int, now: datetime) -> None:
    """FR-030 手順7・8：確定時刻とクーポンの有効期間（秒単位、両端を含む）、最低購入金額を判定する。"""
    period = pricing.coupon_period_state(coupon, now)
    period_text = f"有効期間：{clock.format_display(coupon.valid_from)}〜{clock.format_display(coupon.valid_to)}"
    suffix = "カートでクーポンを解除するか、条件を満たしてから注文してください。"
    values = {"valid_from": coupon.valid_from, "valid_to": coupon.valid_to}
    if period == codes.NOT_APPLICABLE_NOT_YET_VALID:
        raise BusinessError(
            "E-030-07",
            f"適用中のクーポンは利用できません（{period_text}）。{suffix}",
            reason=codes.REASON_COUPON_NOT_YET_VALID,
            values=values,
        )
    if period == codes.NOT_APPLICABLE_EXPIRED:
        raise BusinessError(
            "E-030-08",
            f"適用中のクーポンは利用できません（{period_text}）。{suffix}",
            reason=codes.REASON_COUPON_EXPIRED,
            values=values,
        )
    if subtotal < coupon.minimum_purchase_amount:
        raise BusinessError(
            "E-030-09",
            f"適用中のクーポンは利用できません（最低購入金額：{coupon.minimum_purchase_amount:,}円、"
            f"現在の小計：{subtotal:,}円）。{suffix}",
            reason=codes.REASON_BELOW_MINIMUM_PURCHASE_AMOUNT,
            values={"minimum_purchase_amount": coupon.minimum_purchase_amount, "subtotal": subtotal},
        )


# ---------------------------------------------------------------------------
# FR-031 支払（模擬決済）
# ---------------------------------------------------------------------------


# trace: ENT-010
def _invalid_status(code: str, action: str, status: str) -> BusinessError:
    label = OrderStatus(status).label
    return BusinessError(
        code,
        f"この注文は{action}できません（現在の状態：{label}）。",
        reason=codes.REASON_INVALID_STATUS,
        values={"current_status": status, "current_status_label": label},
    )


# trace: ADDR-001, ADDR-004, ADDR-008, ENT-010, ENT-013, ENT-014
def pay_order(user: Any, order_id: Any, mock_instruction: Any, replay: TokenContext = NO_TOKEN) -> dict[str, Any]:
    """FR-031 支払。注文行のロックを保持したまま決済要求を1回送信し結果を反映する（ADDR-004 DD-006）。

    否認・連携エラーは決済記録だけを登録してコミットしたうえで E-031-06・E-031-07 を通知する（DD-007）。
    画面の使用済みトークンの要求は、注文受付でも決済要求を送信せず先着の結果を通知する（DD-013）。
    """
    instruction = strip_text(mock_instruction)
    if instruction is None or instruction == "":
        instruction = codes.MockInstruction.APPROVED
    if instruction not in codes.MockInstruction.values:
        raise InputError(
            "E-031-03",
            "模擬決済の結果を選択してください。",
            fields=[_field("mock_instruction", codes.FIELD_INVALID_CHOICE, "模擬決済の結果を選択してください。")],
        )
    pk = parse_identifier(order_id)
    now = clock.now_seconds()
    failure: ServiceError | None = None
    integration_cause: BaseException | None = None
    try:
        with transaction.atomic():
            order = Order.objects.select_for_update().filter(pk=pk, buyer=user).first() if pk else None
            if order is None:
                raise NotFoundError("E-031-04", MSG_ORDER_NOT_FOUND)
            if order.status != OrderStatus.ACCEPTED:
                raise _invalid_status("E-031-05", "支払", order.status)
            if replay.used:
                if not replay.prior:
                    raise system_failure("E-031-08")
                if replay.prior.get("status") == "success":
                    return order_detail(order)
                raise from_record(replay.prior)
            outcome = payment_client.request_payment(order.order_number, order.total_amount, instruction)
            if outcome.result == PaymentResult.APPROVED:
                PaymentRecord.objects.create(
                    order=order,
                    result=PaymentResult.APPROVED,
                    amount=order.total_amount,
                    transaction_ref=outcome.transaction_ref,
                    processed_at=outcome.processed_at,
                )
                order.status = OrderStatus.PAID
                order.paid_at = now
                order.save(update_fields=["status", "paid_at"])
                OrderStatusHistory.objects.create(
                    order=order,
                    from_status=OrderStatus.ACCEPTED,
                    to_status=OrderStatus.PAID,
                    changed_at=now,
                    actor=user,
                    actor_user_type=UserType.BUYER,
                )
                return order_detail(order)
            if outcome.result == PaymentResult.DECLINED:
                PaymentRecord.objects.create(
                    order=order,
                    result=PaymentResult.DECLINED,
                    amount=order.total_amount,
                    transaction_ref=None,
                    processed_at=outcome.processed_at,
                )
                failure = BusinessError(
                    "E-031-06",
                    "決済が承認されませんでした。お支払いは完了していません。再度お支払いください。",
                    reason=codes.REASON_PAYMENT_DECLINED,
                )
            else:
                PaymentRecord.objects.create(
                    order=order,
                    result=PaymentResult.INTEGRATION_ERROR,
                    amount=order.total_amount,
                    transaction_ref=None,
                    processed_at=now,
                )
                integration_cause = outcome.error
                failure = IntegrationError(
                    "E-031-07",
                    "決済サービスとの通信でエラーが発生しました。お支払いは完了していません。時間をおいて再度お支払いください。",
                )
    except ServiceError:
        raise
    except DatabaseError as exc:
        raise system_failure("E-031-08") from exc
    if isinstance(failure, IntegrationError):
        log_error("integration_error", integration_cause or failure, getattr(user, "pk", None))
    if failure is not None:
        raise failure
    raise system_failure("E-031-08")


# trace: ADDR-001
def _field(name: str, reason: str, message: str) -> FieldError:
    return FieldError(name, reason, message)


# ---------------------------------------------------------------------------
# FR-032 注文履歴一覧・FR-033 注文詳細（購入者）
# ---------------------------------------------------------------------------


# trace: ADDR-001, ENT-010, ENT-011
def list_my_orders(user: Any, page: Any) -> dict[str, Any]:
    """FR-032 ログイン中の購入者本人の注文を注文日時の降順（同値は注文番号の降順）で20件ずつ返す。"""
    errors = FieldErrors()
    page_number = parse_page(page, errors)
    errors.raise_if_any("E-032-03", MSG_SEARCH_CONDITION_ERROR)
    queryset = (
        Order.objects.filter(buyer=user)
        .annotate(total_quantity=Sum("items__quantity"))
        .order_by("-ordered_at", "-order_number")
    )
    info = build_page(page_number, ORDER_PAGE_SIZE, Order.objects.filter(buyer=user).count())
    items = [
        {
            "order_id": o.pk,
            "order_number": o.order_number,
            "ordered_at": o.ordered_at,
            "status": o.status,
            "status_label": _status_label(o.status),
            "total_amount": o.total_amount,
            "total_quantity": o.total_quantity or 0,
        }
        for o in slice_queryset(queryset, info)
    ]
    return {"items": items, **info.as_dict()}


# trace: ADDR-001, ENT-010
def get_my_order(user: Any, order_id: Any) -> dict[str, Any]:
    """FR-033 本人の注文の詳細。他の購入者の注文は存在しない場合と同じ対象なし（CMN-04）。"""
    pk = parse_identifier(order_id)
    order = Order.objects.filter(pk=pk, buyer=user).first() if pk else None
    if order is None:
        raise NotFoundError("E-033-03", MSG_ORDER_NOT_FOUND)
    return order_detail(order)


# ---------------------------------------------------------------------------
# FR-034・FR-045 キャンセル（在庫戻し）、FR-043 出荷登録、FR-044 配達完了登録
# ---------------------------------------------------------------------------


# trace: ADDR-004, ENT-006, ENT-010, ENT-014
def _cancel(order: Order, actor: Any, actor_type: str, now: datetime) -> None:
    previous = order.status
    order.status = OrderStatus.CANCELLED
    order.cancelled_at = now
    order.save(update_fields=["status", "cancelled_at"])
    items = list(OrderItem.objects.filter(order=order).order_by("pk"))
    stock_ids = sorted({i.stock_unit_id for i in items})
    list(StockUnit.objects.select_for_update().filter(pk__in=stock_ids).order_by("pk"))
    for item in items:
        StockUnit.objects.filter(pk=item.stock_unit_id).update(
            stock_quantity=F("stock_quantity") + item.quantity, updated_at=now
        )
    OrderStatusHistory.objects.create(
        order=order,
        from_status=previous,
        to_status=OrderStatus.CANCELLED,
        changed_at=now,
        actor=actor,
        actor_user_type=actor_type,
    )


# trace: ADDR-001, ADDR-004, ENT-010, ENT-014
def cancel_my_order(user: Any, order_id: Any) -> dict[str, Any]:
    """FR-034 注文キャンセル（購入者）。注文受付・支払済の本人の注文をキャンセル済にし在庫を戻す。"""
    pk = parse_identifier(order_id)
    now = clock.now_seconds()
    try:
        with transaction.atomic():
            order = Order.objects.select_for_update().filter(pk=pk, buyer=user).first() if pk else None
            if order is None:
                raise NotFoundError("E-034-03", MSG_ORDER_NOT_FOUND)
            if order.status not in (OrderStatus.ACCEPTED, OrderStatus.PAID):
                raise _invalid_status("E-034-04", "キャンセル", order.status)
            _cancel(order, user, UserType.BUYER, now)
            return order_detail(order)
    except ServiceError:
        raise
    except DatabaseError as exc:
        raise system_failure("E-034-05") from exc


# trace: ADDR-001, ADDR-004, ENT-010, ENT-014
def admin_cancel_order(admin: Any, order_id: Any) -> dict[str, Any]:
    """FR-045 注文キャンセル（管理者）。全購入者の注文が対象、実行者は管理者。"""
    pk = parse_identifier(order_id)
    now = clock.now_seconds()
    try:
        with transaction.atomic():
            order = Order.objects.select_for_update().filter(pk=pk).first() if pk else None
            if order is None:
                raise NotFoundError("E-045-03", MSG_ORDER_NOT_FOUND)
            if order.status not in (OrderStatus.ACCEPTED, OrderStatus.PAID):
                raise _invalid_status("E-045-04", "キャンセル", order.status)
            _cancel(order, admin, UserType.ADMIN, now)
            return admin_order_detail(order)
    except ServiceError:
        raise
    except DatabaseError as exc:
        raise system_failure("E-045-05") from exc


# trace: ADDR-001, ADDR-004, ENT-010, ENT-014
def ship_order(admin: Any, order_id: Any, tracking_number: Any) -> dict[str, Any]:
    """FR-043 出荷登録（支払済→出荷済。配送伝票番号は任意）。"""
    tracking = strip_text(tracking_number)
    if tracking is None or tracking == "":
        tracking = None
    elif not isinstance(tracking, str) or not _TRACKING.match(tracking):
        raise InputError(
            "E-043-03",
            "配送伝票番号は英数字とハイフンの30文字以内で入力してください。",
            fields=[
                _field(
                    "tracking_number",
                    codes.FIELD_INVALID_FORMAT,
                    "配送伝票番号は英数字とハイフンの30文字以内で入力してください。",
                )
            ],
        )
    pk = parse_identifier(order_id)
    now = clock.now_seconds()
    try:
        with transaction.atomic():
            order = Order.objects.select_for_update().filter(pk=pk).first() if pk else None
            if order is None:
                raise NotFoundError("E-043-04", MSG_ORDER_NOT_FOUND)
            if order.status != OrderStatus.PAID:
                raise _invalid_status("E-043-05", "出荷登録", order.status)
            order.status = OrderStatus.SHIPPED
            order.shipped_at = now
            order.tracking_number = tracking
            order.save(update_fields=["status", "shipped_at", "tracking_number"])
            OrderStatusHistory.objects.create(
                order=order,
                from_status=OrderStatus.PAID,
                to_status=OrderStatus.SHIPPED,
                changed_at=now,
                actor=admin,
                actor_user_type=UserType.ADMIN,
            )
            return admin_order_detail(order)
    except ServiceError:
        raise
    except DatabaseError as exc:
        raise system_failure("E-043-06") from exc


# trace: ADDR-001, ADDR-004, ENT-010, ENT-014
def deliver_order(admin: Any, order_id: Any) -> dict[str, Any]:
    """FR-044 配達完了登録（出荷済→配達完了）。"""
    pk = parse_identifier(order_id)
    now = clock.now_seconds()
    try:
        with transaction.atomic():
            order = Order.objects.select_for_update().filter(pk=pk).first() if pk else None
            if order is None:
                raise NotFoundError("E-044-03", MSG_ORDER_NOT_FOUND)
            if order.status != OrderStatus.SHIPPED:
                raise _invalid_status("E-044-04", "配達完了登録", order.status)
            order.status = OrderStatus.DELIVERED
            order.delivered_at = now
            order.save(update_fields=["status", "delivered_at"])
            OrderStatusHistory.objects.create(
                order=order,
                from_status=OrderStatus.SHIPPED,
                to_status=OrderStatus.DELIVERED,
                changed_at=now,
                actor=admin,
                actor_user_type=UserType.ADMIN,
            )
            return admin_order_detail(order)
    except ServiceError:
        raise
    except DatabaseError as exc:
        raise system_failure("E-044-05") from exc


# ---------------------------------------------------------------------------
# FR-041 注文一覧検索（管理者）・FR-042 注文詳細照会（管理者）
# ---------------------------------------------------------------------------


# trace: ADDR-001
def _parse_date(raw: Any, field_name: str, errors: FieldErrors) -> date | None:
    value = strip_text(raw)
    if value is None or value == "":
        return None
    if not isinstance(value, str) or not _DATE.match(value):
        errors.add(field_name, codes.FIELD_INVALID_FORMAT, "日付を正しく入力してください。")
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        errors.add(field_name, codes.FIELD_INVALID_FORMAT, "日付を正しく入力してください。")
        return None


# trace: ADDR-001, ENT-001, ENT-010, ENT-011
def admin_list_orders(
    order_number: Any,
    statuses: list[Any] | None,
    order_date_from: Any,
    order_date_to: Any,
    buyer_email: Any,
    page: Any,
) -> dict[str, Any]:
    """FR-041 全注文を注文番号・注文状態・注文日・購入者のメールアドレスで検索し20件ずつ返す。"""
    errors = FieldErrors()
    number = strip_text(order_number) if order_number is not None else ""
    if not isinstance(number, str):
        errors.add("order_number", codes.FIELD_INVALID_TYPE, "注文番号は「PO-」と数字8桁で入力してください。")
        number = ""
    elif number and not _ORDER_NUMBER.match(number):
        errors.add("order_number", codes.FIELD_INVALID_FORMAT, "注文番号は「PO-」と数字8桁で入力してください。")
    status_values: list[str] = []
    for raw in statuses or []:
        value = strip_text(raw)
        if value is None or value == "":
            continue
        if value not in OrderStatus.values:
            if not errors.has("status"):
                errors.add("status", codes.FIELD_INVALID_CHOICE, "注文状態の指定に誤りがあります。")
            continue
        if value not in status_values:
            status_values.append(value)
    date_from = _parse_date(order_date_from, "order_date_from", errors)
    date_to = _parse_date(order_date_to, "order_date_to", errors)
    if date_from is not None and date_to is not None and date_from > date_to:
        errors.add(
            "order_date_from",
            codes.FIELD_INVALID_RANGE,
            "注文日（開始）には注文日（終了）以前の日付を指定してください。",
        )
    email = strip_text(buyer_email) if buyer_email is not None else ""
    if not isinstance(email, str):
        errors.add("buyer_email", codes.FIELD_INVALID_TYPE, "購入者のメールアドレスは文字列で入力してください。")
        email = ""
    elif has_unstorable_chars(email):
        errors.add("buyer_email", codes.FIELD_INVALID_FORMAT, unstorable_message("購入者のメールアドレス"))
        email = ""
    elif len(email) > 254:
        errors.add("buyer_email", codes.FIELD_INVALID_LENGTH, "購入者のメールアドレスは254文字以内で入力してください。")
    page_number = parse_page(page, errors)
    errors.raise_if_any("E-041-03", MSG_SEARCH_CONDITION_ERROR)

    queryset = Order.objects.select_related("buyer")
    if number:
        queryset = queryset.filter(order_number=number)
    if status_values:
        queryset = queryset.filter(status__in=status_values)
    if date_from is not None:
        queryset = queryset.filter(ordered_at__gte=datetime.combine(date_from, time.min, tzinfo=clock.JST))
    if date_to is not None:
        # 注文日（終了）の当日中（日本時間の 23:59:59.999999 まで）を含める。翌日 00:00 を計算しないため
        # 実在する最大の日付（9999-12-31）でも日付の範囲を超えない（NFR-SC-04）
        queryset = queryset.filter(ordered_at__lte=datetime.combine(date_to, time.max, tzinfo=clock.JST))
    if email:
        queryset = queryset.filter(buyer__email__icontains=email)
    total = queryset.count()
    queryset = queryset.annotate(total_quantity=Sum("items__quantity")).order_by("-ordered_at", "-order_number")
    info = build_page(page_number, ORDER_PAGE_SIZE, total)
    items = [
        {
            "order_id": o.pk,
            "order_number": o.order_number,
            "ordered_at": o.ordered_at,
            "buyer_email": o.buyer.email,
            "buyer_name": o.buyer.name,
            "status": o.status,
            "status_label": _status_label(o.status),
            "total_amount": o.total_amount,
            "total_quantity": o.total_quantity or 0,
        }
        for o in slice_queryset(queryset, info)
    ]
    return {"items": items, **info.as_dict()}


# trace: ADDR-001, ENT-010
def admin_get_order(order_id: Any) -> dict[str, Any]:
    """FR-042 注文詳細照会（管理者。購入者を問わない）。"""
    pk = parse_identifier(order_id)
    order = Order.objects.select_related("buyer").filter(pk=pk).first() if pk else None
    if order is None:
        raise NotFoundError("E-042-03", MSG_ORDER_NOT_FOUND)
    return admin_order_detail(order)
