"""app.payment.MockPayment の単体テスト。

Requirement: CON-002 / OOS-001
ADR: ADR-011（模擬決済。外部連携なし・常に成功）
Criteria: normal-case
"""

from __future__ import annotations

from app.constants import PaymentMethod
from app.payment import MockPayment


class TestMockPayment:
    def test_charge_always_succeeds(self) -> None:
        # CON-002 / ADR-011: 模擬決済は常に成功扱い。
        result = MockPayment().charge(PaymentMethod.CREDIT_CARD_MOCK, 5000)
        assert result.success is True
        assert result.payment_method is PaymentMethod.CREDIT_CARD_MOCK

    def test_charge_cash_on_delivery_succeeds(self) -> None:
        result = MockPayment().charge(PaymentMethod.CASH_ON_DELIVERY_MOCK, 0)
        assert result.success is True
        assert result.payment_method is PaymentMethod.CASH_ON_DELIVERY_MOCK
