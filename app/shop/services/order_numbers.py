# trace: ADDR-001, ADDR-003
"""注文番号の採番（ADDR-003）。専用シーケンスの払い出し値だけから生成する。"""
from django.db import connection

from shop.common.errors import InternalError

SEQUENCE_NAME = "purchase_order_number_seq"
NEXTVAL_SQL = "SELECT nextval('purchase_order_number_seq')"
ORDER_NUMBER_PREFIX = "PO-"
ORDER_NUMBER_DIGITS = 8
ORDER_NUMBER_MAX = 99999999


# trace: ADDR-003
def next_order_number() -> str:
    """注文番号（PO-＋8桁ゼロ埋め）を採番する。桁あふれはシステムエラーとする。"""
    with connection.cursor() as cursor:
        cursor.execute(NEXTVAL_SQL)
        value = cursor.fetchone()[0]
    if value > ORDER_NUMBER_MAX:
        raise InternalError()
    return f"{ORDER_NUMBER_PREFIX}{value:0{ORDER_NUMBER_DIGITS}d}"
