# trace: ADDR-009
"""決済ゲートウェイ実装の解決（設定値で固定し、要求内容では切り替えない）。"""

from __future__ import annotations

from django.conf import settings
from django.utils.module_loading import import_string

from payments.gateway import PaymentGateway


def get_payment_gateway() -> PaymentGateway:
    """設定値 ``PAYMENT_GATEWAY`` から決済ゲートウェイ実装を生成する。"""
    gateway_class = import_string(settings.PAYMENT_GATEWAY)
    return gateway_class()


def payment_timeout_seconds() -> int:
    """決済結果の応答待ち時間（最大10秒。自動再送は行わない）。"""
    return int(settings.PAYMENT_TIMEOUT_SECONDS)
