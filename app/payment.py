from dataclasses import dataclass

from app.constants import PaymentMethod


@dataclass(frozen=True)
class PaymentResult:
    success: bool
    payment_method: PaymentMethod


class MockPayment:
    """模擬決済。外部決済サービスへは連携せず、常に成功扱いとする（CON-002 / ADR-011 / OOS-001）。"""

    def charge(self, payment_method: PaymentMethod, amount: int) -> PaymentResult:
        return PaymentResult(success=True, payment_method=payment_method)
