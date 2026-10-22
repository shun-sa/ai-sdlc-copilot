# trace: ADDR-005
"""アプリケーションログ（JSON Lines）の整形と要求コンテキストの注入。

禁止項目（パスワード・認証トークン・セッション識別子・メールアドレス・氏名・住所・電話番号）を
出力しないため、ログへ渡せる項目をあらかじめ定めた許可項目に限る（ADDR-005 DD-004）。
例外情報は、例外の種類と発生箇所（ファイル名・行番号・関数名）だけを出力し、
例外メッセージ（項目値・SQL のパラメータ値を含みうる）は出力しない（LOG-02、NFR-SC-06）。
"""
import json
import logging
import traceback
from datetime import datetime
from typing import Any

from django.utils import timezone

from shop.common import request_context

# ログの追加項目として渡せる許可項目（ADDR-005 4.3）。
# trace: ADDR-005
ALLOWED_EXTRA_FIELDS = frozenset(
    {
        "event",
        "method",
        "path",
        "status",
        "duration_ms",
        "order_number",
        "stock_unit_id",
        "purchase_order_id",
        "error_code",
        "exception_class",
        "result",
        "count",
    }
)


# trace: ADDR-005
class RequestContextFilter(logging.Filter):
    """contextvars の request_id・user_id をログレコードへ注入する。"""

    def filter(self, record: logging.LogRecord) -> bool:
        """レコードへ要求コンテキストを設定する（常に出力を許可する）。"""
        record.request_id = request_context.get_request_id()
        record.context_user_id = request_context.get_user_id()
        return True


# trace: ADDR-005
class JsonLinesFormatter(logging.Formatter):
    """1イベント1行の JSON（JSON Lines）へ整形する。"""

    def format(self, record: logging.LogRecord) -> str:
        """ログレコードを JSON 文字列へ整形する。"""
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "request_id": getattr(record, "request_id", None),
            "logger": record.name,
            "message": record.getMessage(),
        }
        user_id = getattr(record, "context_user_id", None)
        if user_id is not None:
            payload["user_id"] = user_id
        for key in ALLOWED_EXTRA_FIELDS:
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            exception_class = _exception_class(record.exc_info)
            if exception_class and "exception_class" not in payload:
                payload["exception_class"] = exception_class
            payload["stack_trace"] = _stack_trace(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        """発生時刻を ISO 8601（+09:00 付き）で返す（NFR-OM-01）。"""
        occurred_at = datetime.fromtimestamp(record.created, tz=timezone.get_current_timezone())
        if datefmt:
            return occurred_at.strftime(datefmt)
        return occurred_at.isoformat(timespec="milliseconds")


# trace: ADDR-005
def _exception_class(exc_info: Any) -> str | None:
    """例外の種類（クラス名）を返す（LOG-02）。"""
    exc_type = exc_info[0] if isinstance(exc_info, tuple) else None
    return exc_type.__name__ if exc_type is not None else None


# trace: ADDR-005
def _stack_trace(exc_info: Any) -> list[str]:
    """発生箇所（ファイル名・行番号・関数名）だけのスタックトレースを返す（LOG-02）。

    例外メッセージとソース行は、項目値・SQL のパラメータ値を含みうるため出力しない。
    """
    if not isinstance(exc_info, tuple) or len(exc_info) < 3:
        return []
    return [
        f"{frame.filename}:{frame.lineno} in {frame.name}" for frame in traceback.extract_tb(exc_info[2])
    ]


# trace: ADDR-005
def build_extra(**fields: Any) -> dict[str, Any]:
    """許可項目だけを残したログ追加項目を作る。"""
    return {key: value for key, value in fields.items() if key in ALLOWED_EXTRA_FIELDS}
