from pydantic import BaseModel, Field

from app.constants import PaymentMethod, TicketType

# FR-006〜009: カート・注文・チケット購入の入力検証（NFR-SEC-004 / ADR-009）。
# 金額・単価はサーバー側で算出し、クライアント入力値を信頼しない（ADR-012）。


class CartAddInput(BaseModel):
    product_id: int = Field(ge=1)
    quantity: int = Field(ge=1)


class CartUpdateInput(BaseModel):
    quantity: int = Field(ge=0)  # 0は削除扱い（FR-007）


class OrderInput(BaseModel):
    recipient_name: str = Field(min_length=1, max_length=50)
    postal_code: str = Field(min_length=1, max_length=8, pattern=r"^\d{3}-?\d{4}$")
    prefecture: str = Field(min_length=1, max_length=20)
    city_address: str = Field(min_length=1, max_length=200)
    phone: str = Field(min_length=1, max_length=20, pattern=r"^[0-9\-]+$")
    payment_method: PaymentMethod


class TicketPurchaseInput(BaseModel):
    screening_id: int = Field(ge=1)
    ticket_type: TicketType
    quantity: int = Field(ge=1)
    payment_method: PaymentMethod
