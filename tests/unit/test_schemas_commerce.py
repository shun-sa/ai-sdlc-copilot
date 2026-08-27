"""app.schemas.commerce の入力検証テスト（サーバー側検証）。

Requirement: FR-006 / FR-007 / FR-008 / FR-009 / NFR-SEC-004
ADR: ADR-009（サーバー側検証）/ ADR-011（支払方法enum）/ ADR-012（券種enum）
Criteria: invalid-input, boundary-value, normal-case
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.constants import PaymentMethod, TicketType
from app.schemas.commerce import (
    CartAddInput,
    CartUpdateInput,
    OrderInput,
    TicketPurchaseInput,
)


class TestCartAddInput:
    def test_valid(self) -> None:
        model = CartAddInput(product_id=1, quantity=1)
        assert model.quantity == 1

    def test_quantity_min_1(self) -> None:
        # FR-006: 数量は1以上。
        assert CartAddInput(product_id=1, quantity=1).quantity == 1

    def test_quantity_zero_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CartAddInput(product_id=1, quantity=0)

    def test_negative_quantity_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CartAddInput(product_id=1, quantity=-1)

    def test_product_id_below_1_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CartAddInput(product_id=0, quantity=1)


class TestCartUpdateInput:
    def test_quantity_zero_allowed_as_delete(self) -> None:
        # FR-007: 0 は削除扱いとして許可される。
        assert CartUpdateInput(quantity=0).quantity == 0

    def test_negative_quantity_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CartUpdateInput(quantity=-1)


def _valid_order(**overrides: object) -> dict:
    data = {
        "recipient_name": "受取太郎",
        "postal_code": "150-0001",
        "prefecture": "東京都",
        "city_address": "渋谷区1-1-1",
        "phone": "03-1234-5678",
        "payment_method": PaymentMethod.CREDIT_CARD_MOCK,
    }
    data.update(overrides)
    return data


class TestOrderInput:
    def test_valid(self) -> None:
        model = OrderInput(**_valid_order())
        assert model.payment_method is PaymentMethod.CREDIT_CARD_MOCK

    def test_postal_code_without_hyphen_allowed(self) -> None:
        assert OrderInput(**_valid_order(postal_code="1500001"))

    @pytest.mark.parametrize("bad_postal", ["1500001x", "150-00001", "abc-defg", "12-3456"])
    def test_invalid_postal_code(self, bad_postal: str) -> None:
        # NFR-SEC-004: 郵便番号形式をサーバー側で検証。
        with pytest.raises(ValidationError):
            OrderInput(**_valid_order(postal_code=bad_postal))

    def test_invalid_phone_rejected(self) -> None:
        with pytest.raises(ValidationError):
            OrderInput(**_valid_order(phone="03(1234)5678"))

    def test_name_required(self) -> None:
        with pytest.raises(ValidationError):
            OrderInput(**_valid_order(recipient_name=""))

    def test_payment_method_enum_only(self) -> None:
        # ADR-011: 支払方法は定義済み enum のみ受理。自由入力不可。
        with pytest.raises(ValidationError):
            OrderInput(**_valid_order(payment_method="BANK_TRANSFER"))


class TestTicketPurchaseInput:
    def test_valid(self) -> None:
        model = TicketPurchaseInput(
            screening_id=1,
            ticket_type=TicketType.GENERAL,
            quantity=2,
            payment_method=PaymentMethod.CREDIT_CARD_MOCK,
        )
        assert model.ticket_type is TicketType.GENERAL

    def test_quantity_zero_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TicketPurchaseInput(
                screening_id=1,
                ticket_type=TicketType.GENERAL,
                quantity=0,
                payment_method=PaymentMethod.CREDIT_CARD_MOCK,
            )

    def test_ticket_type_enum_only(self) -> None:
        # ADR-012: 券種は定義済み enum のみ受理。自由入力不可。
        with pytest.raises(ValidationError):
            TicketPurchaseInput(
                screening_id=1,
                ticket_type="VIP",
                quantity=1,
                payment_method=PaymentMethod.CREDIT_CARD_MOCK,
            )
