# trace: ADDR-009
"""決済ゲートウェイのインターフェースとデータ構造（IF-01）。

決済要求には注文番号・決済金額・通貨・模擬決済指示だけを渡し、個人情報を渡さない
（ADDR-009 INV-004）。
"""

from __future__ import annotations

import abc
import datetime as dt
from dataclasses import dataclass

CURRENCY_JPY = "JPY"
MOCK_APPROVE = "approve"
MOCK_DECLINE = "decline"
MOCK_RESULT_CHOICES = (MOCK_APPROVE, MOCK_DECLINE)

RESULT_APPROVED = "approved"
RESULT_DECLINED = "declined"
DECLINE_REASON_CODE = "DECLINED"


@dataclass(frozen=True)
class PaymentRequest:
    """決済要求（注文番号・決済金額・通貨・模擬決済指示）。"""

    order_number: str
    amount: int
    currency: str
    mock_result: str


@dataclass(frozen=True)
class PaymentResult:
    """決済結果（承認／否認・取引参照番号・否認理由コード・処理日時）。"""

    result: str
    processed_at: dt.datetime
    transaction_ref: str | None = None
    decline_reason_code: str | None = None

    @property
    def approved(self) -> bool:
        return self.result == RESULT_APPROVED


class PaymentGatewayError(Exception):
    """決済ゲートウェイの応答なし・応答不正を表す例外。"""


class PaymentGateway(abc.ABC):
    """決済ゲートウェイのインターフェース。実装は設定値で解決する。"""

    @abc.abstractmethod
    def authorize(self, request: PaymentRequest, *, timeout_seconds: int) -> PaymentResult:
        """決済（売上確定）を要求し、決済結果を返す。"""
        raise NotImplementedError
