# trace: ADDR-004
"""テンプレート用の表示整形（UI-23〜UI-27、UI-32、UI-33）。"""
from typing import Any

from django import template

from shop.services.amounts import tax_included_price
from shop.web.prefectures import PREFECTURE_NAMES

register = template.Library()

# 表示名の対応（CD-02、CD-05、CD-03、CD-01 の値）。値の定義は services の応答に従う。
STATUS_LABELS = {
    "created": "注文受付",
    "paid": "支払済",
    "shipped": "出荷済",
    "delivered": "配達完了",
    "cancelled": "キャンセル済",
}
PAYMENT_RESULT_LABELS = {"approved": "承認", "declined": "否認", "error": "連携エラー"}
DISCOUNT_TYPE_LABELS = {"fixed": "定額", "percentage": "定率"}
ROLE_LABELS = {"buyer": "購入者", "admin": "管理者"}
UNSET = "－"


# trace: ADDR-004
@register.filter
def yen(value: Any) -> str:
    """金額を「1,234円」の形式で表示する。"""
    if value is None:
        return UNSET
    return f"{int(value):,}円"


# trace: ADDR-004
@register.filter
def tax_included(value: Any) -> str:
    """税抜価格から税込価格を求めて表示する。"""
    if value is None:
        return UNSET
    return f"{tax_included_price(int(value)):,}円"


# trace: ADDR-004
@register.filter
def order_status(value: Any) -> str:
    """注文状態を表示名で表示する。"""
    return STATUS_LABELS.get(value, UNSET)


# trace: ADDR-004
@register.filter
def payment_result(value: Any) -> str:
    """決済結果を表示名で表示する。"""
    return PAYMENT_RESULT_LABELS.get(value, UNSET)


# trace: ADDR-004
@register.filter
def discount_type(value: Any) -> str:
    """割引方式を表示名で表示する。"""
    return DISCOUNT_TYPE_LABELS.get(value, UNSET)


# trace: ADDR-004
@register.filter
def actor_role(value: Any) -> str:
    """実行者の利用者区分を表示名で表示する。"""
    return ROLE_LABELS.get(value, UNSET)


# trace: ADDR-004
@register.filter
def prefecture(value: Any) -> str:
    """都道府県コードを都道府県名で表示する。"""
    return PREFECTURE_NAMES.get(value, UNSET)


# trace: ADDR-004
@register.filter
def postal_code(value: Any) -> str:
    """郵便番号を「123-4567」の形式で表示する。"""
    if not value:
        return UNSET
    text = str(value)
    return f"{text[:3]}-{text[3:]}" if len(text) == 7 else text


# trace: ADDR-004
@register.filter
def unset(value: Any) -> Any:
    """未設定の値を「－」で表示する。"""
    if value in (None, "", []):
        return UNSET
    return value


# trace: ADDR-004
@register.filter
def field_errors(details: Any, field_name: str) -> list[str]:
    """指定した項目の入力エラー理由を返す（項目の近傍表示に用いる）。"""
    if not details:
        return []
    return [item["reason"] for item in details if item.get("field") == field_name]
