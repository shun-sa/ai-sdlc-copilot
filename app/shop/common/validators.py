# trace: ADDR-007
"""入力値の共通検証（CMN-13、CMN-15、NFR-SC-04）。

不備のある全項目を列挙できるよう、検証は項目ごとに結果を積み上げる方式とする。
数字・日付・整数の判定は半角（ASCII）の文字だけを受け付ける。全角数字などの
半角以外の数字は、全角文字と半角文字の相互変換を行わない定め（CMN-15）に従い、
条件を満たさない値として扱う。
"""
import re
from typing import Any

from shop.common.errors import ValidationError

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
UPPER_CODE_PATTERN = re.compile(r"^[A-Z0-9-]+$")
POSTAL_CODE_PATTERN = re.compile(r"^([0-9]{7}|[0-9]{3}-[0-9]{4})$")
PHONE_PATTERN = re.compile(r"^[0-9-]+$")
TRACKING_NUMBER_PATTERN = re.compile(r"^[A-Za-z0-9-]+$")
ORDER_NUMBER_PATTERN = re.compile(r"^PO-[0-9]{8}$")
DATE_PATTERN = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
DIGITS_PATTERN = re.compile(r"^[0-9]+$")
INTEGER_PATTERN = re.compile(r"^[+-]?[0-9]+$")
WHITESPACE = " \t\r\n\u3000"


# trace: ADDR-007
def strip_value(value: Any) -> str:
    """文字列の前後の空白（半角・全角・タブ・改行）を除去する（CMN-15）。"""
    if value is None:
        return ""
    return str(value).strip(WHITESPACE)


# trace: ADDR-007
class ErrorCollector:
    """不備のある全項目を集めて1回で通知するための収集器（CMN-16）。"""

    def __init__(self) -> None:
        """収集結果を初期化する。"""
        self.details: list[dict[str, str]] = []

    def add(self, field: str, reason: str) -> None:
        """項目名と理由を追加する。"""
        self.details.append({"field": field, "reason": reason})

    @property
    def has_error(self) -> bool:
        """1件以上の不備があるかを返す。"""
        return bool(self.details)

    def raise_if_error(self) -> None:
        """不備がある場合に入力エラーを送出する。"""
        if self.details:
            raise ValidationError(details=self.details)


# trace: ADDR-007
def parse_int(value: Any) -> int | None:
    """整数として解釈できる場合に整数を返す（できない場合は None）。

    文字列は半角数字（符号は任意）だけで構成される場合に限り整数として扱い、
    全角数字など半角以外の数字は整数として扱わない（CMN-15）。
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    text = strip_value(value)
    if not INTEGER_PATTERN.match(text):
        return None
    return int(text)


# trace: ADDR-007
def normalize_email(value: Any) -> str:
    """メールアドレスを前後空白除去・英小文字化で正規化する（D-01-02）。"""
    return strip_value(value).lower()


# trace: ADDR-007
def normalize_coupon_code(value: Any) -> str:
    """クーポンコードを前後空白除去・英大文字化で正規化する（D-07-02）。"""
    return strip_value(value).upper()
