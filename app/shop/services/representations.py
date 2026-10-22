# trace: ADDR-001, ADDR-007
"""注文の表現（FR-033 注文詳細内容、FR-042 管理者向け注文詳細内容）の組み立て。"""
from typing import Any

from shop.common import timeutils
from shop.models import PurchaseOrder, PurchaseOrderStatus


# trace: ADDR-001
def can_pay(order: PurchaseOrder) -> bool:
    """支払可否（注文受付のみ可）を返す。"""
    return order.status == PurchaseOrderStatus.CREATED


# trace: ADDR-001
def can_cancel(order: PurchaseOrder) -> bool:
    """キャンセル可否（注文受付・支払済のみ可）を返す。"""
    return order.status in {PurchaseOrderStatus.CREATED, PurchaseOrderStatus.PAID}


# trace: ADDR-001
def can_ship(order: PurchaseOrder) -> bool:
    """出荷登録可否（支払済のみ可）を返す。"""
    return order.status == PurchaseOrderStatus.PAID


# trace: ADDR-001
def can_deliver(order: PurchaseOrder) -> bool:
    """配達完了登録可否（出荷済のみ可）を返す。"""
    return order.status == PurchaseOrderStatus.SHIPPED


# trace: ADDR-007
def _lines(order: PurchaseOrder) -> list[dict[str, Any]]:
    """注文明細を注文明細IDの昇順で組み立てる。"""
    return [
        {
            "purchase_order_line_id": line.purchase_order_line_id,
            "stock_unit_id": line.stock_unit_id,
            "sku": line.sku,
            "item_name": line.item_name,
            "variant_name": line.variant_name,
            "unit_price": line.unit_price,
            "quantity": line.quantity,
            "line_amount": line.line_amount,
        }
        for line in order.lines.order_by("purchase_order_line_id")
    ]


# trace: ADDR-007
def _coupon(order: PurchaseOrder) -> dict[str, Any] | None:
    """注文に複写したクーポン情報を組み立てる（未適用は None）。"""
    if not order.coupon_code:
        return None
    return {
        "code": order.coupon_code,
        "discount_type": order.coupon_discount_type,
        "discount_value": order.coupon_discount_value,
    }


# trace: ADDR-007
def _amounts(order: PurchaseOrder) -> dict[str, int]:
    """注文確定時に確定した金額内訳を返す。"""
    return {
        "subtotal": order.subtotal,
        "discount_amount": order.discount_amount,
        "discounted_subtotal": order.discounted_subtotal,
        "shipping_fee": order.shipping_fee,
        "tax_amount": order.tax_amount,
        "total": order.total,
    }


# trace: ADDR-007
def _shipping_address(order: PurchaseOrder) -> dict[str, Any]:
    """配送先を組み立てる。"""
    address = order.shipping_address
    return {
        "recipient_name": address.recipient_name,
        "postal_code": address.postal_code,
        "prefecture_code": address.prefecture_code,
        "address_line1": address.address_line1,
        "address_line2": address.address_line2,
        "phone_number": address.phone_number,
    }


# trace: ADDR-007
def _status_history(order: PurchaseOrder, include_actor_user_id: bool) -> list[dict[str, Any]]:
    """注文状態履歴を変更日時の昇順で組み立てる。"""
    history: list[dict[str, Any]] = []
    for entry in order.status_history.order_by("changed_at", "status_history_id"):
        row: dict[str, Any] = {
            "from_status": entry.from_status,
            "to_status": entry.to_status,
            "changed_at": timeutils.jst(entry.changed_at),
            "actor_role": entry.actor_role,
        }
        if include_actor_user_id:
            row["actor_user_id"] = entry.actor_user_id
        history.append(row)
    return history


# trace: ADDR-007
def order_detail(order: PurchaseOrder) -> dict[str, Any]:
    """注文詳細内容（FR-033 6.18.5）。決済記録・実行者の利用者IDは含めない。"""
    return {
        "purchase_order_id": order.purchase_order_id,
        "order_number": order.order_number,
        "status": order.status,
        "ordered_at": timeutils.jst(order.ordered_at),
        "paid_at": timeutils.jst(order.paid_at),
        "shipped_at": timeutils.jst(order.shipped_at),
        "delivered_at": timeutils.jst(order.delivered_at),
        "cancelled_at": timeutils.jst(order.cancelled_at),
        "tracking_number": order.tracking_number,
        "lines": _lines(order),
        "coupon": _coupon(order),
        "amounts": _amounts(order),
        "shipping_address": _shipping_address(order),
        "status_history": _status_history(order, include_actor_user_id=False),
        "can_pay": can_pay(order),
        "can_cancel": can_cancel(order),
    }


# trace: ADDR-007
def admin_order_detail(order: PurchaseOrder) -> dict[str, Any]:
    """管理者向け注文詳細内容（FR-042 6.22.5）。購入者・決済記録を含める。"""
    detail = {
        "purchase_order_id": order.purchase_order_id,
        "order_number": order.order_number,
        "status": order.status,
        "ordered_at": timeutils.jst(order.ordered_at),
        "paid_at": timeutils.jst(order.paid_at),
        "shipped_at": timeutils.jst(order.shipped_at),
        "delivered_at": timeutils.jst(order.delivered_at),
        "cancelled_at": timeutils.jst(order.cancelled_at),
        "tracking_number": order.tracking_number,
        "lines": _lines(order),
        "coupon": _coupon(order),
        "amounts": _amounts(order),
        "shipping_address": _shipping_address(order),
        "status_history": _status_history(order, include_actor_user_id=True),
        "can_pay": can_pay(order),
        "can_cancel": can_cancel(order),
        "buyer": {
            "user_id": order.user.user_id,
            "email": order.user.email,
            "full_name": order.user.full_name,
        },
        "payment_records": [
            {
                "result": record.result,
                "amount": record.amount,
                "transaction_ref": record.transaction_ref,
                "processed_at": timeutils.jst(record.processed_at),
            }
            for record in order.payment_records.order_by("processed_at", "payment_record_id")
        ],
        "can_ship": can_ship(order),
        "can_deliver": can_deliver(order),
    }
    return detail
