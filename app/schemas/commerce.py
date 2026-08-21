"""カート/注文/チケットの入力スキーマ (FR-006〜FR-009)。"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator

_POSTAL_RE = re.compile(r"^\d{3}-?\d{4}$")
_PHONE_RE = re.compile(r"^0\d{1,3}-?\d{2,4}-?\d{3,4}$")


class AddToCartInput(BaseModel):
    """カート追加入力 (FR-006)。数量は1以上。"""

    product_id: int = Field(ge=1)
    quantity: int = Field(ge=1)


class UpdateCartItemInput(BaseModel):
    """カート数量変更入力 (FR-007)。0は削除扱い。"""

    quantity: int = Field(ge=0)


class OrderInput(BaseModel):
    """注文確定入力 (FR-008)。"""

    name: str = Field(min_length=1, max_length=50)
    postal_code: str = Field(min_length=7, max_length=8)
    prefecture: str = Field(min_length=1, max_length=10)
    address_line: str = Field(min_length=1, max_length=200)
    phone: str = Field(min_length=10, max_length=13)
    payment_method: str = Field(min_length=1, max_length=50)

    @field_validator("postal_code")
    @classmethod
    def _postal(cls, v: str) -> str:
        if not _POSTAL_RE.match(v):
            raise ValueError("郵便番号の形式が正しくありません。")
        return v

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str) -> str:
        if not _PHONE_RE.match(v):
            raise ValueError("電話番号の形式が正しくありません。")
        return v


class TicketPurchaseInput(BaseModel):
    """チケット購入入力 (FR-009)。"""

    screening_id: int = Field(ge=1)
    ticket_type: str = Field(min_length=1, max_length=30)
    quantity: int = Field(ge=1)
    payment_method: str = Field(min_length=1, max_length=50)
