# trace: ADDR-008
"""注文の応答表現（購入者向け 6.18.5／管理者向け 6.22.5）。"""

from __future__ import annotations

from typing import Any

from common import timeutils
from orders.models import PurchaseOrder, PurchaseOrderLine


def order_line_payload(line: PurchaseOrderLine) -> dict[str, Any]:
    """注文明細1件（注文確定時のスナップショット）。"""
    return {
        "purchase_order_line_id": line.pk,
        "stock_unit_id": line.stock_unit_id,
        "sku": line.sku,
        "item_name": line.item_name,
        "variant_name": line.variant_name,
        "unit_price": line.unit_price,
        "quantity": line.quantity,
        "line_amount": line.line_amount,
    }


def order_coupon_payload(order: PurchaseOrder) -> dict[str, Any] | None:
    """注文に適用したクーポン（未適用は null）。"""
    if not order.coupon_code:
        return None
    return {
        "code": order.coupon_code,
        "discount_type": order.coupon_discount_type,
        "discount_value": order.coupon_discount_value,
    }


def order_amounts_payload(order: PurchaseOrder) -> dict[str, int]:
    """注文の金額内訳。"""
    return {
        "subtotal": order.subtotal,
        "discount_amount": order.discount_amount,
        "discounted_subtotal": order.discounted_subtotal,
        "shipping_fee": order.shipping_fee,
        "tax_amount": order.tax_amount,
        "total": order.total,
    }


def shipping_address_payload(order: PurchaseOrder) -> dict[str, Any] | None:
    """配送先。"""
    address = getattr(order, "shipping_address", None)
    if address is None:
        return None
    return {
        "recipient_name": address.recipient_name,
        "postal_code": address.postal_code,
        "prefecture_code": address.prefecture_code,
        "address_line1": address.address_line1,
        "address_line2": address.address_line2 or None,
        "phone_number": address.phone_number,
    }


def sorted_lines(order: PurchaseOrder) -> list[PurchaseOrderLine]:
    """注文明細を注文明細IDの昇順に並べる。"""
    return sorted(order.lines.all(), key=lambda line: line.pk)


def status_history_payload(order: PurchaseOrder, *, include_actor_user_id: bool) -> list[dict[str, Any]]:
    """注文状態履歴（変更日時の昇順、同値は履歴IDの昇順）。"""
    histories = sorted(order.status_history.all(), key=lambda history: (history.changed_at, history.pk))
    payload = []
    for history in histories:
        item = {
            "from_status": history.from_status,
            "to_status": history.to_status,
            "changed_at": timeutils.to_iso(history.changed_at),
            "actor_role": history.actor_role,
        }
        if include_actor_user_id:
            item["actor_user_id"] = history.actor_user_id
        payload.append(item)
    return payload


def payment_records_payload(order: PurchaseOrder) -> list[dict[str, Any]]:
    """決済記録（処理日時の昇順、同値は決済記録IDの昇順）。管理者のみに返す。"""
    records = sorted(order.payment_records.all(), key=lambda record: (record.processed_at, record.pk))
    return [
        {
            "result": record.result,
            "amount": record.amount,
            "transaction_ref": record.transaction_ref,
            "processed_at": timeutils.to_iso(record.processed_at),
        }
        for record in records
    ]


def order_base_payload(order: PurchaseOrder) -> dict[str, Any]:
    """購入者・管理者で共通の注文詳細項目。"""
    return {
        "purchase_order_id": order.pk,
        "order_number": order.order_number,
        "status": order.status,
        "ordered_at": timeutils.to_iso(order.ordered_at),
        "paid_at": timeutils.to_iso(order.paid_at),
        "shipped_at": timeutils.to_iso(order.shipped_at),
        "delivered_at": timeutils.to_iso(order.delivered_at),
        "cancelled_at": timeutils.to_iso(order.cancelled_at),
        "tracking_number": order.tracking_number,
        "lines": [order_line_payload(line) for line in sorted_lines(order)],
        "coupon": order_coupon_payload(order),
        "amounts": order_amounts_payload(order),
        "shipping_address": shipping_address_payload(order),
        "can_pay": order.can_pay,
        "can_cancel": order.can_cancel,
    }


def buyer_order_payload(order: PurchaseOrder) -> dict[str, Any]:
    """注文詳細内容（購入者）。決済記録・実行者の利用者IDは返さない（MSG-04）。"""
    payload = order_base_payload(order)
    payload["status_history"] = status_history_payload(order, include_actor_user_id=False)
    return payload


def admin_order_payload(order: PurchaseOrder) -> dict[str, Any]:
    """注文詳細（管理者）の内容。購入者情報・決済記録・操作可否を含む。"""
    payload = order_base_payload(order)
    payload["status_history"] = status_history_payload(order, include_actor_user_id=True)
    payload["buyer"] = {
        "user_id": order.user_id,
        "email": order.user.email,
        "full_name": order.user.full_name,
    }
    payload["payment_records"] = payment_records_payload(order)
    payload["can_ship"] = order.can_ship
    payload["can_deliver"] = order.can_deliver
    return payload


def order_summary_payload(order: PurchaseOrder) -> dict[str, Any]:
    """注文履歴一覧の1件（FR-032 手順6）。"""
    return {
        "purchase_order_id": order.pk,
        "order_number": order.order_number,
        "ordered_at": timeutils.to_iso(order.ordered_at),
        "status": order.status,
        "total": order.total,
        "total_quantity": sum(line.quantity for line in order.lines.all()),
    }


def admin_order_summary_payload(order: PurchaseOrder) -> dict[str, Any]:
    """注文一覧検索（管理者）の1件（FR-041 6.21.5）。"""
    payload = order_summary_payload(order)
    payload["buyer_email"] = order.user.email
    payload["buyer_name"] = order.user.full_name
    return payload
