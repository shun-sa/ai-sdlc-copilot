# trace: ADDR-009
"""決済ゲートウェイの境界（IF-01-DAT-01〜08 の項目だけを受け渡す）。

実装の差し替えは本境界の別実装として行い、services 側を変更しない（NFR-PF-17）。
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

# 模擬決済指示（IF-01-DAT-04）。
APPROVE = "approve"
DECLINE = "decline"

# 決済結果（IF-01-DAT-05）。
RESULT_APPROVED = "approved"
RESULT_DECLINED = "declined"

# 否認理由コード（IF-01-DAT-07）。
DECLINED_REASON_CODE = "DECLINED"


# trace: ADDR-009
@dataclass(frozen=True)
class PaymentRequest:
    """決済要求（IF-01-DAT-01〜04）。モデルオブジェクトを保持しない。"""

    order_number: str
    amount: int
    currency: str
    mock_result: str


# trace: ADDR-009
@dataclass(frozen=True)
class PaymentResponse:
    """決済応答（IF-01-DAT-05〜08）。"""

    result: str
    transaction_ref: str | None
    declined_reason_code: str | None
    processed_at: datetime | None


# trace: ADDR-009
class PaymentGatewayError(Exception):
    """連携エラー（応答待ちの締切超過・呼び出し失敗・応答不正）。"""


# trace: ADDR-009
class PaymentGateway(Protocol):
    """決済ゲートウェイの呼び出し境界。"""

    def authorize(self, request: PaymentRequest) -> PaymentResponse:
        """決済要求を1回送信し、決済応答を返す。"""
        ...
