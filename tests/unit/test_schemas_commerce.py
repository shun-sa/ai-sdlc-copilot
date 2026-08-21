"""カート/注文/チケット入力スキーマ バリデーション単体テスト。

対象: app/schemas/commerce.py
検証Requirement: FR-006 (数量1以上), FR-007 (数量0以上), FR-008 (配送先/形式),
FR-009 (上映回/券種/枚数), ERR-001 (入力不備/形式不正), NFR-SEC-004。
DB Strategy: NOT_APPLICABLE (純粋バリデーション)。
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.schemas.commerce import (
    AddToCartInput,
    OrderInput,
    TicketPurchaseInput,
    UpdateCartItemInput,
)


class TestAddToCartInput:
    # FR-006: 数量は1以上
    def test_valid(self) -> None:
        model = AddToCartInput(product_id=1, quantity=1)
        assert model.quantity == 1

    # 境界: 数量0は不可 (下限1)
    def test_quantity_zero_rejected(self) -> None:
        with pytest.raises(PydanticValidationError):
            AddToCartInput(product_id=1, quantity=0)

    def test_negative_quantity_rejected(self) -> None:
        with pytest.raises(PydanticValidationError):
            AddToCartInput(product_id=1, quantity=-1)


class TestUpdateCartItemInput:
    # FR-007: 数量0は削除扱いのため0を許容する
    def test_quantity_zero_allowed(self) -> None:
        assert UpdateCartItemInput(quantity=0).quantity == 0

    def test_negative_rejected(self) -> None:
        with pytest.raises(PydanticValidationError):
            UpdateCartItemInput(quantity=-1)


def _order(**overrides: object) -> OrderInput:
    data = {
        "name": "山田太郎",
        "postal_code": "150-0001",
        "prefecture": "東京都",
        "address_line": "渋谷区1-2-3",
        "phone": "03-1234-5678",
        "payment_method": "mock_credit_card",
    }
    data.update(overrides)
    return OrderInput(**data)  # type: ignore[arg-type]


class TestOrderInput:
    # FR-008 正常系: 妥当な配送先入力
    def test_valid_order(self) -> None:
        model = _order()
        assert model.prefecture == "東京都"

    # ERR-001: 郵便番号形式不正
    @pytest.mark.parametrize("postal", ["1500001x", "abc-defg", "12-3456"])
    def test_invalid_postal_code(self, postal: str) -> None:
        with pytest.raises(PydanticValidationError):
            _order(postal_code=postal)

    # 形式許容: ハイフンなし7桁も許容
    def test_postal_without_hyphen(self) -> None:
        assert _order(postal_code="1500001").postal_code == "1500001"

    # ERR-001: 電話番号形式不正
    @pytest.mark.parametrize("phone", ["1234", "abcd-efgh-ijkl", "123456789012345"])
    def test_invalid_phone(self, phone: str) -> None:
        with pytest.raises(PydanticValidationError):
            _order(phone=phone)

    # ERR-001: 氏名必須 (空文字不可)
    def test_name_required(self) -> None:
        with pytest.raises(PydanticValidationError):
            _order(name="")


class TestTicketPurchaseInput:
    # FR-009 正常系
    def test_valid(self) -> None:
        model = TicketPurchaseInput(
            screening_id=1, ticket_type="general", quantity=2, payment_method="mock_credit_card"
        )
        assert model.quantity == 2

    # 境界: 枚数0は不可 (下限1)
    def test_quantity_zero_rejected(self) -> None:
        with pytest.raises(PydanticValidationError):
            TicketPurchaseInput(
                screening_id=1, ticket_type="general", quantity=0, payment_method="mock_credit_card"
            )

    # ERR-001: 券種空文字は不可
    def test_ticket_type_required(self) -> None:
        with pytest.raises(PydanticValidationError):
            TicketPurchaseInput(
                screening_id=1, ticket_type="", quantity=1, payment_method="mock_credit_card"
            )
