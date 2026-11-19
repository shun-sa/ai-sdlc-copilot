# trace: ADDR-008
"""決済ゲートウェイの抽象境界（ADDR-008 4.3 の1、DD-001）。

要求は order_number・amount・currency（JPY 固定）・mock_instruction の4項目に限る（個人情報・カード情報を含めない）。
応答は result・transaction_ref・decline_reason・processed_at の4項目（検証は呼出し側：client）。
支払の業務処理は本境界の型だけに依存し、模擬実装を直接参照しない（ADDR-012 DD-005）。
"""

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

CURRENCY_JPY = "JPY"


# trace: ADDR-008
@dataclass(frozen=True)
class PaymentRequest:
    order_number: str
    amount: int
    currency: str
    mock_instruction: str


# trace: ADDR-008
class PaymentGateway(ABC):
    """決済サービスへの送信操作を用意する境界。"""

    @abstractmethod
    def prepare(self, request: PaymentRequest) -> Callable[[], dict[str, Any]]:
        """要求を処理しているスレッドで呼ばれ、別スレッドで実行する送信操作を返す。

        送信操作はデータベースに接続しない（ADDR-008 DD-002・INV-002）。必要な状態は本メソッドで読み取り、
        不変の値として送信操作へ渡す。
        """


# trace: ADDR-008
def get_gateway() -> PaymentGateway:
    """使用する実装はプログラム内の既定で模擬機能に固定する（利用者の入力・要求で変えられない：DD-005）。"""
    from payments.mock import MockPaymentGateway

    return MockPaymentGateway()
