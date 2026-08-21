"""模擬決済ゲートウェイ単体テスト (FR-008 / FR-009 / ADR-009 / CON-002)。

対象: app/payment.py
検証Requirement: CON-002 (決済は常に成功する模擬決済), ADR-009 (失敗系を捏造しない)。
DB Strategy: NOT_APPLICABLE。
"""

from __future__ import annotations

from app.payment import MockPaymentGateway, PaymentResult, get_payment_gateway


class TestMockPaymentGateway:
    # CON-002 / ADR-009: 模擬決済は常に成功する
    def test_charge_always_succeeds(self) -> None:
        result = MockPaymentGateway().charge(1000, "mock_credit_card")
        assert isinstance(result, PaymentResult)
        assert result.success is True

    def test_charge_zero_amount_succeeds(self) -> None:
        assert MockPaymentGateway().charge(0, "mock_credit_card").success is True

    # DIプロバイダは模擬決済実装を返す
    def test_provider_returns_mock(self) -> None:
        assert isinstance(get_payment_gateway(), MockPaymentGateway)
