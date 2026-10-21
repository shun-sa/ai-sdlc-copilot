# trace: ADDR-011
"""画面側の入力エラー・業務エラーの整形（APIと同じ例外を再利用する）。

エラーコード・判定は common の例外をそのまま用い、画面独自のエラーコードは定義しない
（ADDR-011 DD-005）。表示は画面要件の文言・形式に合わせる（UI-23 日時、UI-24 金額、
UI-27 状態の表示名、MSG-05 判定に用いた値の補足）。
"""

from __future__ import annotations

from typing import Any

from common import errors
from common.exceptions import MiniCommerceError
from orders.models import STATUS_LABELS
from web.templatetags.display import format_datetime, format_yen

# INVALID_STATUS_TRANSITION の操作別の文言（SCR-008-OP01、SCR-010-OP02、SCR-103-OP01〜OP03）。
OPERATION_PAY = "pay"
OPERATION_CANCEL = "cancel"
OPERATION_SHIP = "ship"
OPERATION_DELIVER = "deliver"
OPERATION_LABELS = {
    OPERATION_PAY: "支払",
    OPERATION_CANCEL: "キャンセル",
    OPERATION_SHIP: "出荷登録",
    OPERATION_DELIVER: "配達完了登録",
}

# 注文手続き（SCR-006-OP01）の失敗時の文言。
CHECKOUT_COUPON_MESSAGE = (
    "適用中のクーポンは利用できません（{reason}）。"
    "カートでクーポンを解除するか、条件を満たしてから注文してください。"
)
CHECKOUT_QUANTITY_MESSAGE = (
    "同じ規格は1注文につき10個までです（対象：{target}、カート内数量：{quantity}個）。"
    "カートで数量を変更してください。"
)
CHECKOUT_STOCK_MESSAGE = "在庫が不足している商品があります。カートで数量を変更してください。"

# クーポン適用（SCR-005-OP03）でカートが空の場合の文言。
COUPON_CART_EMPTY_MESSAGE = "カートに商品がないため、クーポンを適用できません。"

# 支払済の注文をキャンセルしたときの返金の案内（SCR-010-OP02）。
REFUND_NOTICE_BUYER = "返金は当社が5営業日以内に行います。"


# trace: ADDR-011
def field_errors(error: MiniCommerceError) -> dict[str, list[str]]:
    """入力エラーを項目名ごとの理由へ整形する（項目の近傍に表示する）。"""
    errors_by_field: dict[str, list[str]] = {}
    for detail in error.details:
        errors_by_field.setdefault(detail.get("field", ""), []).append(detail.get("reason", ""))
    return errors_by_field


# trace: ADDR-011
def with_detail(message: str, detail: str) -> str:
    """文末の「。」の前へ補足を差し込む（「…です（補足）。」の形式）。"""
    if not detail:
        return message
    head, separator, tail = message.partition("。")
    if not separator:
        return f"{message}（{detail}）"
    return f"{head}（{detail}）。{tail}"


# trace: ADDR-011
def coupon_period(context: dict[str, Any]) -> str:
    """クーポンの有効期間を「有効期間：YYYY/MM/DD HH:MM〜YYYY/MM/DD HH:MM」で表す（UI-23）。"""
    return f"有効期間：{format_datetime(context.get('valid_from'))}〜{format_datetime(context.get('valid_until'))}"


# trace: ADDR-011
def coupon_min_spend(context: dict[str, Any]) -> str:
    """最低購入金額未達の理由を表す（UI-24）。"""
    return f"最低購入金額：{format_yen(context.get('min_spend'))}、現在の小計：{format_yen(context.get('subtotal'))}"


# trace: ADDR-011
def business_detail(error: MiniCommerceError) -> str:
    """業務エラーの判定に用いた値を、画面要件の表記で組み立てる（MSG-05）。"""
    context: dict[str, Any] = error.context or {}
    if error.code == errors.QUANTITY_LIMIT_EXCEEDED:
        return f"現在のカート内数量：{context.get('current_quantity')}個"
    if error.code == errors.INSUFFICIENT_STOCK:
        shortages = context.get("shortages") or []
        if shortages:
            return f"現在の在庫数量：{shortages[0].get('available_quantity')}個"
        return ""
    if error.code in (errors.COUPON_NOT_YET_VALID, errors.COUPON_EXPIRED):
        return coupon_period(context)
    if error.code == errors.COUPON_MIN_SPEND_NOT_MET:
        return coupon_min_spend(context)
    if error.code == errors.INVALID_STATUS_TRANSITION:
        return f"現在の状態：{status_label(context.get('current_status'))}"
    return ""


# trace: ADDR-011
def status_label(status: Any) -> str:
    """注文状態をコード値ではなく表示名で表す（UI-27）。"""
    return STATUS_LABELS.get(str(status), str(status))


# trace: ADDR-011
def business_message(error: MiniCommerceError) -> str:
    """業務エラーのメッセージへ、判定に用いた値を画面要件の形式で補足する（MSG-05）。"""
    return with_detail(error.message, business_detail(error))


# trace: ADDR-011
def status_transition_message(current_status: Any, operation: str) -> str:
    """状態不正を操作別の文言で表す（SCR-008-OP01、SCR-010-OP02、SCR-103-OP01〜OP03）。"""
    return f"この注文は{OPERATION_LABELS[operation]}できません（現在の状態：{status_label(current_status)}）。"


# trace: ADDR-011
def invalid_status_message(error: MiniCommerceError, operation: str) -> str:
    """状態不正の業務例外を、操作別の画面メッセージへ変換する。"""
    context: dict[str, Any] = error.context or {}
    return status_transition_message(context.get("current_status"), operation)


# trace: ADDR-011
def coupon_already_applied_message(error: MiniCommerceError, applied_code: str | None) -> str:
    """適用済みクーポンの文言へ、適用中のクーポンコードを補う（SCR-005-OP03）。"""
    detail = f"適用中のクーポン：{applied_code}" if applied_code else ""
    return with_detail(error.message, detail)


# trace: ADDR-011
def line_label(line: dict[str, Any]) -> str:
    """明細を「商品名（規格名）」で表す（SCR-006-OP01）。"""
    return f"{line.get('item_name')}（{line.get('variant_name')}）"


# trace: ADDR-011
def checkout_message(error: MiniCommerceError, lines: list[dict[str, Any]]) -> str:
    """注文確定の失敗を、注文手続き画面の文言で表す（SCR-006-OP01）。"""
    context: dict[str, Any] = error.context or {}
    labels = {line.get("stock_unit_id"): line_label(line) for line in lines}
    if error.code == errors.ITEM_NOT_AVAILABLE:
        targets = "、".join(
            labels.get(stock_unit_id, str(stock_unit_id)) for stock_unit_id in context.get("stock_unit_ids", [])
        )
        return f"{error.message}対象：{targets}" if targets else error.message
    if error.code == errors.QUANTITY_LIMIT_EXCEEDED:
        stock_unit_id = context.get("stock_unit_id")
        return CHECKOUT_QUANTITY_MESSAGE.format(
            target=labels.get(stock_unit_id, str(stock_unit_id)),
            quantity=context.get("current_quantity"),
        )
    if error.code in (errors.COUPON_NOT_YET_VALID, errors.COUPON_EXPIRED):
        return CHECKOUT_COUPON_MESSAGE.format(reason=coupon_period(context))
    if error.code == errors.COUPON_MIN_SPEND_NOT_MET:
        return CHECKOUT_COUPON_MESSAGE.format(reason=coupon_min_spend(context))
    if error.code == errors.INSUFFICIENT_STOCK:
        shortages = "、".join(
            f"{shortage.get('sku')}（現在の在庫数量：{shortage.get('available_quantity')}個）"
            for shortage in context.get("shortages", [])
        )
        return f"{CHECKOUT_STOCK_MESSAGE}不足する規格：{shortages}" if shortages else CHECKOUT_STOCK_MESSAGE
    return business_message(error)
