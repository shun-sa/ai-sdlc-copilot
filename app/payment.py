"""決済ゲートウェイ抽象 (ADR-009 / CON-001 / CON-002)。

外部決済サービスとは実連携しない。決済は常に成功する模擬決済とする。
本番相当の失敗系・課金処理は実装しない。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class PaymentResult:
    success: bool
    transaction_id: str


class PaymentGateway(ABC):
    """決済インターフェース。注文/購入確定はこのインターフェース経由で行う。"""

    @abstractmethod
    def charge(self, amount: int, method: str) -> PaymentResult:
        """指定金額を決済する。"""


class MockPaymentGateway(PaymentGateway):
    """常に成功する模擬決済 (CON-002)。"""

    def charge(self, amount: int, method: str) -> PaymentResult:
        # 模擬決済のため常に成功を返す。失敗系は捏造しない (ADR-009)。
        return PaymentResult(success=True, transaction_id="MOCK-PAYMENT")


def get_payment_gateway() -> PaymentGateway:
    """決済ゲートウェイのDIプロバイダ。"""
    return MockPaymentGateway()
