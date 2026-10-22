# trace: ADDR-001, ADDR-006
"""管理者機能（FR-040〜FR-045）の業務ロジック。"""
from datetime import date, datetime, time, timedelta
from typing import Any

from django.db import transaction
from django.utils import timezone

from shop.common import timeutils
from shop.common.errors import InvalidStatusTransitionError, NotFoundError, ValidationError
from shop.common.pagination import paginate
from shop.common.validators import (
    DATE_PATTERN,
    ORDER_NUMBER_PATTERN,
    TRACKING_NUMBER_PATTERN,
    ErrorCollector,
    parse_int,
    strip_value,
)
from shop.models import PurchaseOrder, PurchaseOrderStatus, StockUnit, Supplier, User
from shop.services import representations
from shop.services.orders import cancel_locked_order, record_status_change

STOCK_UNIT_PAGE_SIZE = 50
ORDER_PAGE_SIZE = 20
LOW_STOCK_THRESHOLD = 5
SKU_MAX_LENGTH = 32
ITEM_NAME_MAX_LENGTH = 100
EMAIL_MAX_LENGTH = 254
TRACKING_NUMBER_MAX_LENGTH = 30


# trace: ADDR-006
def _parse_page_value(raw_page: Any, errors: ErrorCollector) -> int:
    """ページ番号を判定する（他項目とあわせて全件通知するため例外を送出しない）。"""
    if strip_value(raw_page) == "":
        return 1
    parsed = parse_int(raw_page)
    if parsed is None or parsed < 1:
        errors.add("page", "ページ番号は1以上の整数で指定してください。")
        return 1
    return parsed


# trace: ADDR-006
def search_stock_units(
    raw_sku: Any = None,
    raw_item_name: Any = None,
    raw_supplier_id: Any = None,
    raw_low_stock_only: Any = None,
    raw_page: Any = None,
) -> dict[str, Any]:
    """在庫単位一覧照会（FR-040）。全在庫単位を SKU 昇順・50件/ページで返す。"""
    sku = strip_value(raw_sku)
    item_name = strip_value(raw_item_name)
    supplier_text = strip_value(raw_supplier_id)
    low_stock_text = strip_value(raw_low_stock_only).lower()
    errors = ErrorCollector()

    if len(sku) > SKU_MAX_LENGTH:
        errors.add("sku", "SKU は32文字以下で入力してください。")
    if len(item_name) > ITEM_NAME_MAX_LENGTH:
        errors.add("item_name", "商品名は100文字以下で入力してください。")

    supplier_id: int | None = None
    if supplier_text != "":
        supplier_id = parse_int(supplier_text)
        if supplier_id is None or not Supplier.objects.filter(supplier_id=supplier_id).exists():
            errors.add("supplier_id", "指定した仕入先が見つかりません。")

    low_stock_only = False
    if low_stock_text not in {"", "true", "false"}:
        errors.add("low_stock_only", "低在庫のみは true または false で指定してください。")
    else:
        low_stock_only = low_stock_text == "true"

    page = _parse_page_value(raw_page, errors)
    errors.raise_if_error()

    queryset = StockUnit.objects.select_related("item", "supplier").all()
    if sku:
        queryset = queryset.filter(sku__istartswith=sku)
    if item_name:
        queryset = queryset.filter(item__name__icontains=item_name)
    if supplier_id is not None:
        queryset = queryset.filter(supplier_id=supplier_id)
    if low_stock_only:
        queryset = queryset.filter(quantity__lte=LOW_STOCK_THRESHOLD)
    queryset = queryset.order_by("sku")

    page_data = paginate(queryset, page, STOCK_UNIT_PAGE_SIZE)
    page_data["results"] = [
        {
            "stock_unit_id": unit.stock_unit_id,
            "sku": unit.sku,
            "item_id": unit.item_id,
            "item_code": unit.item.item_code,
            "item_name": unit.item.name,
            "variant_name": unit.variant_name,
            "item_is_public": unit.item.is_public,
            "supplier_id": unit.supplier_id,
            "supplier_name": unit.supplier.name,
            "price": unit.price,
            "quantity": unit.quantity,
            "is_low_stock": unit.quantity <= LOW_STOCK_THRESHOLD,
        }
        for unit in page_data["results"]
    ]
    return page_data


# trace: ADDR-006
def _parse_date(raw_value: str, field_name: str, errors: ErrorCollector) -> date | None:
    """YYYY-MM-DD 形式の実在する日付を解釈する。"""
    if not DATE_PATTERN.match(raw_value):
        errors.add(field_name, "日付は YYYY-MM-DD の形式で入力してください。")
        return None
    try:
        return date.fromisoformat(raw_value)
    except ValueError:
        errors.add(field_name, "実在する日付を入力してください。")
        return None


# trace: ADDR-006
def _jst_datetime(value: date) -> datetime:
    """JST の日付境界（00:00:00）を日時へ変換する。"""
    return timezone.make_aware(datetime.combine(value, time.min), timezone.get_current_timezone())


# trace: ADDR-006
def search_orders(
    raw_order_number: Any = None,
    raw_statuses: Any = None,
    raw_ordered_from: Any = None,
    raw_ordered_to: Any = None,
    raw_buyer_email: Any = None,
    raw_page: Any = None,
) -> dict[str, Any]:
    """注文一覧検索（FR-041）。全購入者の注文を注文日時の降順・20件/ページで返す。"""
    order_number = strip_value(raw_order_number)
    buyer_email = strip_value(raw_buyer_email)
    ordered_from_text = strip_value(raw_ordered_from)
    ordered_to_text = strip_value(raw_ordered_to)
    statuses = [strip_value(value) for value in (raw_statuses or []) if strip_value(value) != ""]
    statuses = list(dict.fromkeys(statuses))
    errors = ErrorCollector()

    if order_number and not ORDER_NUMBER_PATTERN.match(order_number):
        errors.add("order_number", "注文番号は PO- に続けて数字8桁で入力してください。")

    valid_statuses = {choice.value for choice in PurchaseOrderStatus}
    if any(status not in valid_statuses for status in statuses):
        errors.add("status", "注文状態の指定が正しくありません。")

    ordered_from = _parse_date(ordered_from_text, "ordered_from", errors) if ordered_from_text else None
    ordered_to = _parse_date(ordered_to_text, "ordered_to", errors) if ordered_to_text else None
    if ordered_from and ordered_to and ordered_from > ordered_to:
        errors.add("ordered_to", "注文日（終了）は注文日（開始）以降の日付を入力してください。")

    if len(buyer_email) > EMAIL_MAX_LENGTH:
        errors.add("buyer_email", "購入者のメールアドレスは254文字以下で入力してください。")

    page = _parse_page_value(raw_page, errors)
    errors.raise_if_error()

    queryset = PurchaseOrder.objects.select_related("user").prefetch_related("lines")
    if order_number:
        queryset = queryset.filter(order_number=order_number)
    if statuses:
        queryset = queryset.filter(status__in=statuses)
    if ordered_from:
        queryset = queryset.filter(ordered_at__gte=_jst_datetime(ordered_from))
    if ordered_to:
        queryset = queryset.filter(ordered_at__lt=_jst_datetime(ordered_to + timedelta(days=1)))
    if buyer_email:
        queryset = queryset.filter(user__email__icontains=buyer_email)
    queryset = queryset.order_by("-ordered_at", "-purchase_order_id")

    page_data = paginate(queryset, page, ORDER_PAGE_SIZE)
    page_data["results"] = [
        {
            "purchase_order_id": order.purchase_order_id,
            "order_number": order.order_number,
            "ordered_at": timeutils.jst(order.ordered_at),
            "buyer_email": order.user.email,
            "buyer_name": order.user.full_name,
            "status": order.status,
            "total": order.total,
            "total_quantity": sum(line.quantity for line in order.lines.all()),
        }
        for order in page_data["results"]
    ]
    return page_data


# trace: ADDR-001
def _get_order(raw_order_id: Any, lock: bool = False) -> PurchaseOrder:
    """注文を取得する（購入者を問わない）。"""
    order_id = parse_int(raw_order_id)
    if order_id is None:
        raise NotFoundError(message="指定した注文が見つかりません。")
    queryset = PurchaseOrder.objects.select_for_update() if lock else PurchaseOrder.objects.select_related("user")
    order = queryset.filter(purchase_order_id=order_id).first()
    if order is None:
        raise NotFoundError(message="指定した注文が見つかりません。")
    return order


# trace: ADDR-001
def get_order_detail(raw_order_id: Any) -> dict[str, Any]:
    """注文詳細照会（管理者）（FR-042）。"""
    order = _get_order(raw_order_id)
    return representations.admin_order_detail(order)


# trace: ADDR-001
def validate_tracking_number(raw_value: Any) -> str | None:
    """配送伝票番号を検証する（任意項目。0文字は指定なし）。"""
    value = strip_value(raw_value)
    if value == "":
        return None
    if len(value) > TRACKING_NUMBER_MAX_LENGTH or not TRACKING_NUMBER_PATTERN.match(value):
        raise ValidationError(
            details=[
                {"field": "tracking_number", "reason": "配送伝票番号は英数字とハイフンで30文字以下で入力してください。"}
            ]
        )
    return value


# trace: ADDR-001
def ship_order(admin: User, raw_order_id: Any, raw_tracking_number: Any = None) -> dict[str, Any]:
    """出荷登録（FR-043）。支払済の注文のみ出荷済へ遷移する。"""
    tracking_number = validate_tracking_number(raw_tracking_number)
    with transaction.atomic():
        order = _get_order(raw_order_id, lock=True)
        if order.status != PurchaseOrderStatus.PAID:
            raise InvalidStatusTransitionError(
                message="出荷登録できるのは支払済の注文に限ります。",
                context={"current_status": order.status},
            )
        shipped_at = timeutils.now()
        order.status = PurchaseOrderStatus.SHIPPED
        order.shipped_at = shipped_at
        if tracking_number is not None:
            order.tracking_number = tracking_number
        order.save(update_fields=["status", "shipped_at", "tracking_number"])
        record_status_change(order, PurchaseOrderStatus.PAID, PurchaseOrderStatus.SHIPPED, shipped_at, admin)
    return representations.admin_order_detail(_get_order(order.purchase_order_id))


# trace: ADDR-001
def deliver_order(admin: User, raw_order_id: Any) -> dict[str, Any]:
    """配達完了登録（FR-044）。出荷済の注文のみ配達完了へ遷移する。"""
    with transaction.atomic():
        order = _get_order(raw_order_id, lock=True)
        if order.status != PurchaseOrderStatus.SHIPPED:
            raise InvalidStatusTransitionError(
                message="配達完了登録できるのは出荷済の注文に限ります。",
                context={"current_status": order.status},
            )
        delivered_at = timeutils.now()
        order.status = PurchaseOrderStatus.DELIVERED
        order.delivered_at = delivered_at
        order.save(update_fields=["status", "delivered_at"])
        record_status_change(order, PurchaseOrderStatus.SHIPPED, PurchaseOrderStatus.DELIVERED, delivered_at, admin)
    return representations.admin_order_detail(_get_order(order.purchase_order_id))


# trace: ADDR-001
def cancel_order(admin: User, raw_order_id: Any) -> dict[str, Any]:
    """注文キャンセル（管理者）（FR-045）。出荷前の注文のみキャンセルし在庫を戻す。"""
    with transaction.atomic():
        order = _get_order(raw_order_id, lock=True)
        cancel_locked_order(order, admin)
    return representations.admin_order_detail(_get_order(order.purchase_order_id))


# trace: ADDR-006
def list_suppliers() -> list[Supplier]:
    """画面の検索条件に表示する仕入先を仕入先コード昇順で返す。"""
    return list(Supplier.objects.order_by("supplier_code"))


# trace: ADDR-006
def list_order_statuses() -> list[tuple[str, str]]:
    """画面の検索条件に表示する注文状態（CD-02）の値と表示名を返す。"""
    return [(choice.value, choice.label) for choice in PurchaseOrderStatus]
