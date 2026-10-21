# trace: ADDR-011
"""入力検証の共通処理（不備のある全項目を列挙してから送出する）。"""

from __future__ import annotations

import re
from typing import Any

from common.exceptions import ValidationFailed

WHITESPACE = " \u3000\t\r\n"
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+$")
COUPON_CODE_PATTERN = re.compile(r"^[A-Z0-9-]{1,20}$")
TRACKING_NUMBER_PATTERN = re.compile(r"^[A-Za-z0-9-]{1,30}$")
POSTAL_CODE_PATTERN = re.compile(r"^(?:[0-9]{7}|[0-9]{3}-[0-9]{4})$")
PHONE_PATTERN = re.compile(r"^[0-9-]+$")
ORDER_NUMBER_PATTERN = re.compile(r"^PO-[0-9]{8}$")
HAS_ALPHA = re.compile(r"[A-Za-z]")
HAS_DIGIT = re.compile(r"[0-9]")


class ValidationCollector:
    """項目ごとの入力エラーを集めて1回で通知する（CMN-16）。"""

    def __init__(self) -> None:
        self.details: list[dict[str, str]] = []

    def add(self, field: str, reason: str) -> None:
        self.details.append({"field": field, "reason": reason})

    @property
    def has_errors(self) -> bool:
        return bool(self.details)

    def raise_if_any(self) -> None:
        if self.details:
            raise ValidationFailed(details=list(self.details))


def normalize_text(value: Any) -> str:
    """文字列の前後の空白（半角・全角スペース、タブ、改行）を除去する（CMN-15）。"""
    if value is None:
        return ""
    if not isinstance(value, str):
        return str(value).strip(WHITESPACE)
    return value.strip(WHITESPACE)


def normalize_email(value: Any) -> str:
    """メールアドレスを前後空白除去・英小文字化して正規化する（D-01-02）。"""
    return normalize_text(value).lower()


def normalize_coupon_code(value: Any) -> str:
    """クーポンコードを前後空白除去・英大文字化して正規化する（D-07-02）。"""
    return normalize_text(value).upper()


def is_email_format(value: str) -> bool:
    """メールアドレスの形式（ローカル部@ドメイン部、空白なし）か判定する。"""
    return bool(EMAIL_PATTERN.match(value))


def parse_int(value: Any) -> int | None:
    """整数として解釈する（解釈できない場合は None）。真偽値は整数として扱わない。"""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    text = normalize_text(value)
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def parse_bool(value: Any) -> bool | None:
    """true／false として解釈する（解釈できない場合は None）。"""
    if isinstance(value, bool):
        return value
    text = normalize_text(value).lower()
    if text in {"true"}:
        return True
    if text in {"false"}:
        return False
    return None


def password_violations(password: str, normalized_email: str) -> list[str]:
    """パスワードの条件違反の理由を返す（FR-001 6.1.3）。"""
    reasons: list[str] = []
    if len(password) < 8 or len(password) > 64:
        reasons.append("パスワードは8文字以上64文字以下で入力してください。")
    if not HAS_ALPHA.search(password):
        reasons.append("パスワードには英字を1文字以上含めてください。")
    if not HAS_DIGIT.search(password):
        reasons.append("パスワードには数字を1文字以上含めてください。")
    if normalized_email and password.lower() == normalized_email:
        reasons.append("パスワードにメールアドレスと同じ文字列は使用できません。")
    return reasons


def validate_page(value: Any, collector: ValidationCollector, field: str = "page") -> int:
    """ページ番号を検証する（省略時は1。CMN-35）。"""
    if value is None or normalize_text(value) == "":
        return 1
    page = parse_int(value)
    if page is None or page < 1:
        collector.add(field, "ページ番号は1以上の整数で指定してください。")
        return 1
    return page
