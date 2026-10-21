# trace: ADDR-010
"""表示整形用のテンプレートフィルタ（業務判定は行わない）。"""

from __future__ import annotations

from typing import Any

from django import template

from carts.models import DISCOUNT_FIXED
from common import timeutils
from orders.models import PAYMENT_RESULT_LABELS, STATUS_LABELS
from web.prefectures import PREFECTURE_NAMES

register = template.Library()

ROLE_LABELS = {"buyer": "購入者", "admin": "管理者"}
NOT_SET = "－"


def format_yen(value: Any) -> str:
    """金額を「1,234円」の形式で表す（UI-24）。画面・メッセージの双方で用いる。"""
    if value is None:
        return NOT_SET
    return f"{int(value):,}円"


def format_datetime(value: Any) -> str:
    """ISO 8601 の日時を「YYYY/MM/DD HH:MM」で表す（UI-23）。画面・メッセージの双方で用いる。"""
    if not value:
        return NOT_SET
    parsed = timeutils.parse_datetime(str(value))
    if parsed is None:
        return NOT_SET
    return timeutils.to_jst(parsed).strftime("%Y/%m/%d %H:%M")


@register.filter
def yen(value: Any) -> str:
    """金額を「1,234円」の形式で表示する（UI-24）。"""
    return format_yen(value)


@register.filter
def datetime_jst(value: Any) -> str:
    """ISO 8601 の日時を「YYYY/MM/DD HH:MM」で表示する（UI-23）。"""
    return format_datetime(value)


@register.filter
def order_status(value: Any) -> str:
    """注文状態を表示名で表示する（UI-27、MSG-06）。"""
    if not value:
        return NOT_SET
    return STATUS_LABELS.get(str(value), str(value))


@register.filter
def payment_result(value: Any) -> str:
    """決済結果を表示名で表示する（UI-27）。"""
    if not value:
        return NOT_SET
    return PAYMENT_RESULT_LABELS.get(str(value), str(value))


@register.filter
def actor_role(value: Any) -> str:
    """実行者区分を表示名で表示する（UI-27）。"""
    if not value:
        return NOT_SET
    return ROLE_LABELS.get(str(value), str(value))


@register.filter
def prefecture(value: Any) -> str:
    """都道府県コードを都道府県名で表示する（UI-27）。"""
    if not value:
        return NOT_SET
    return PREFECTURE_NAMES.get(str(value), str(value))


@register.filter
def postal_code(value: Any) -> str:
    """郵便番号を「123-4567」の形式で表示する（UI-33）。"""
    text = str(value or "")
    if len(text) != 7:
        return text or NOT_SET
    return f"{text[:3]}-{text[3:]}"


@register.filter
def discount_label(coupon: Any) -> str:
    """割引内容を「1,000円引き」「10%引き」の形式で表示する。"""
    if not coupon:
        return NOT_SET
    value = coupon.get("discount_value")
    if coupon.get("discount_type") == DISCOUNT_FIXED:
        return f"{int(value):,}円引き"
    return f"{int(value)}%引き"


@register.filter
def or_dash(value: Any) -> Any:
    """未設定値を「－」で表示する（UI-32）。"""
    if value is None or value == "":
        return NOT_SET
    return value


@register.filter
def get_item(mapping: Any, key: str) -> Any:
    """辞書から項目を取り出す（入力エラーの項目別表示に用いる）。"""
    if not mapping:
        return None
    return mapping.get(key)
