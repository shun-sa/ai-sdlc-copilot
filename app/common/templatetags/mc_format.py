# trace: ADDR-012
"""画面の表示規約（UI-23〜UI-33）のテンプレートフィルタ。値はエスケープ済みの文字列として返す。"""

from datetime import datetime
from typing import Any

from django import template

from common import clock
from common.codes import NOT_APPLICABLE_LABELS, PREFECTURE_NAMES
from common.tax import price_including_tax

register = template.Library()


# trace: ADDR-012
@register.filter
def yen(value: Any) -> str:
    """金額を「1,234円」の形式にする（UI-24）。"""
    if value is None:
        return "－"
    return f"{int(value):,}円"


# trace: ADDR-012
@register.filter
def number(value: Any) -> str:
    if value is None:
        return "－"
    return f"{int(value):,}"


# trace: ADDR-012
@register.filter
def jst(value: Any) -> str:
    """日時を「YYYY/MM/DD HH:MM」（日本時間、秒は表示しない）にする（UI-23）。未設定は「－」。"""
    if not isinstance(value, datetime):
        return "－"
    return clock.to_jst(value).strftime("%Y/%m/%d %H:%M")


# trace: ADDR-012
@register.filter
def dash(value: Any) -> Any:
    """未設定の値は「－」と表示する（UI-32）。"""
    if value is None or value == "":
        return "－"
    return value


# trace: ADDR-012
@register.filter
def postal(value: Any) -> str:
    """郵便番号を「123-4567」の形式にする（UI-33）。"""
    if not isinstance(value, str) or len(value) != 7:
        return "－" if not value else str(value)
    return f"{value[:3]}-{value[3:]}"


# trace: ADDR-012
@register.filter
def prefecture_name(value: Any) -> str:
    return PREFECTURE_NAMES.get(str(value), "－")


# trace: ADDR-012
@register.filter
def price_pair(price_excluding_tax: Any) -> str:
    """商品価格を「1,100円（税込）／1,000円（税抜）」の形式にする（UI-25、CMN-32）。"""
    if price_excluding_tax is None:
        return "－"
    excluding = int(price_excluding_tax)
    including = price_including_tax(excluding)
    return f"{including:,}円（税込）／{excluding:,}円（税抜）"


# trace: ADDR-012
@register.filter
def discount_text(coupon: Any) -> str:
    """割引内容を「1,000円引き」「10%引き」の形式にする（SCR-005-V12）。"""
    if not coupon:
        return "－"
    if coupon.get("discount_type") == "percentage":
        return f"{coupon.get('discount_value')}%引き"
    return f"{int(coupon.get('discount_value') or 0):,}円引き"


# trace: ADDR-012
@register.filter
def get_item(mapping: Any, key: Any) -> Any:
    if isinstance(mapping, dict):
        return mapping.get(key)
    return None


# trace: ADDR-012
@register.filter
def reason_label(value: Any) -> str:
    """クーポンの適用不可理由の表示名（MSG-07）。"""
    return NOT_APPLICABLE_LABELS.get(str(value), "－")
