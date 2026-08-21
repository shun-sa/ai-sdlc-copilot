"""ドメイン定数。

一部はOpen Questions (未確定事項) に対する暫定値であり、
確定仕様として扱わない。要件確定後に見直す。
"""

from __future__ import annotations

# OQ-REQ-001 (未確定 / 暫定): 注文時の支払方法。
# 外部決済は実連携しない模擬決済 (CON-002/ADR-009) のため、
# 暫定として模擬クレジットカードのみを提供する。
PAYMENT_METHODS: dict[str, str] = {
    "mock_credit_card": "クレジットカード（模擬）",
}
DEFAULT_PAYMENT_METHOD = "mock_credit_card"

# OQ-REQ-002 (未確定 / 暫定): チケット券種と価格。
# 初期ラインナップ/価格ルールは未確定のため、暫定の券種・価格を定義する。
TICKET_TYPES: dict[str, int] = {
    "general": 1800,
    "student": 1500,
    "senior": 1200,
}
TICKET_TYPE_LABELS: dict[str, str] = {
    "general": "一般",
    "student": "学生",
    "senior": "シニア",
}

# OQ-REQ-003 (未確定 / 暫定): 購入履歴の保持期間・表示件数上限。
# 保持期間は未確定のため削除は行わない。表示件数はページング標準 (NFR-PERF-003)
# に合わせ暫定で1ページ20件とする。
HISTORY_PAGE_SIZE = 20
