# trace: ADDR-013
"""アプリケーションログ（LOG-01〜LOG-03・LOG-05・LOG-06）の出力部品（ADDR-013）。

- 1行1件の JSON（UTF-8）を標準出力へ出力する。
- 全行に timestamp（日本時間・ミリ秒まで、実時刻）・level・log_type・request_id を付ける。
- 出力項目は log_type ごとの許可リストだけとし、要求本文・ヘッダー・クエリ文字列・個人情報・
  パスワード・ログイン状態を示す情報・例外の文言を出力しない（DD-003・DD-004、INV-001）。
"""

import contextvars
import json
import logging
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from types import TracebackType
from typing import Any
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")
LOGGER_NAME = "minicommerce"

_request_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("minicommerce_request_id", default=None)

_ALLOWED_FIELDS: dict[str, tuple[str, ...]] = {
    "LOG-01": ("user_id", "operation", "result", "event"),
    "LOG-02": ("user_id", "error_type", "exception_class", "location"),
    "LOG-03": ("method", "path", "status", "user_id", "duration_ms"),
    "LOG-05": ("job", "result", "counts", "violations"),
    "LOG-06": ("order_number", "amount", "currency", "result", "transaction_ref", "duration_ms", "phase"),
}

_logger = logging.getLogger(LOGGER_NAME)


# trace: ADDR-013
def new_request_id() -> str:
    """要求の識別子をサーバーで生成する（要求ヘッダーの値は採用しない：DD-002）。"""
    return str(uuid.uuid4())


# trace: ADDR-013
def set_request_id(value: str | None) -> contextvars.Token:
    return _request_id.set(value)


# trace: ADDR-013
def reset_request_id(token: contextvars.Token) -> None:
    _request_id.reset(token)


# trace: ADDR-013
def current_request_id() -> str | None:
    return _request_id.get()


# trace: ADDR-013
class JsonFormatter(logging.Formatter):
    """許可リストの項目だけを JSON で整形する。メッセージ本文・例外の文言は出力しない。"""

    def format(self, record: logging.LogRecord) -> str:
        log_type = getattr(record, "mc_log_type", None)
        fields = getattr(record, "mc_fields", None) or {}
        timestamp = datetime.fromtimestamp(record.created, tz=JST).isoformat(timespec="milliseconds")
        payload: dict[str, Any] = {
            "timestamp": timestamp,
            "level": record.levelname,
            "log_type": log_type or ("LOG-02" if record.levelno >= logging.ERROR else "LOG-01"),
            "request_id": getattr(record, "mc_request_id", None) or current_request_id(),
        }
        if log_type in _ALLOWED_FIELDS:
            for key in _ALLOWED_FIELDS[log_type]:
                if key in fields:
                    payload[key] = fields[key]
        else:
            # 本システム以外のロガーの出力：本文を出さず発生元の名前だけを示す
            payload["operation"] = record.name
            payload["result"] = "suppressed"
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


# trace: ADDR-013
def _emit(level: int, log_type: str, fields: dict[str, Any]) -> None:
    try:
        _logger.log(level, log_type, extra={"mc_log_type": log_type, "mc_fields": fields})
    except Exception:  # noqa: BLE001 - ログ出力の失敗で業務処理を失敗させない（ADDR-013 6章）
        pass


# trace: ADDR-013
def log_operation(operation: str, event: str, result: str, user_id: int | None) -> None:
    """LOG-01 アプリケーションログ（処理の開始・終了・エラー応答）。"""
    _emit(logging.INFO, "LOG-01", {"operation": operation, "event": event, "result": result, "user_id": user_id})


# trace: ADDR-013
def exception_location(exc: BaseException) -> str:
    """例外の発生箇所（モジュール・関数・行）。ファイルパス・例外の文言は含めない。"""
    tb: TracebackType | None = exc.__traceback__
    last: TracebackType | None = None
    while tb is not None:
        last = tb
        tb = tb.tb_next
    if last is None:
        return "unknown"
    frame = last.tb_frame
    module = frame.f_globals.get("__name__", "unknown")
    return f"{module}:{frame.f_code.co_name}:{last.tb_lineno}"


# trace: ADDR-013
def log_error(error_type: str, exc: BaseException | None, user_id: int | None) -> None:
    """LOG-02 エラーログ（system_error・integration_error）。例外の種類と発生箇所だけを出力する。"""
    fields: dict[str, Any] = {"error_type": error_type, "user_id": user_id}
    if exc is not None:
        # 業務処理層がシステムエラーへ変換した場合は原因の例外の種類と発生箇所を出力する（文言・値は出さない）
        origin = exc.__cause__ if exc.__cause__ is not None else exc
        fields["exception_class"] = f"{type(origin).__module__}.{type(origin).__name__}"
        fields["location"] = exception_location(origin)
    _emit(logging.ERROR, "LOG-02", fields)


# trace: ADDR-013
def log_access(method: str, path: str, status: int, user_id: int | None, duration_ms: int) -> None:
    """LOG-03 アクセスログ（要求先は検索条件を除いたパス：DD-005）。"""
    _emit(
        logging.INFO,
        "LOG-03",
        {"method": method, "path": path, "status": status, "user_id": user_id, "duration_ms": duration_ms},
    )


# trace: ADDR-013
def log_job(result: str, counts: dict[str, int], violations: list[dict[str, Any]]) -> None:
    """LOG-05 ジョブ実行ログ（初期データ一括投入。違反内容は値を含めない）。"""
    _emit(
        logging.INFO if result == "success" else logging.WARNING,
        "LOG-05",
        {"job": "initial_data_load", "result": result, "counts": counts, "violations": violations},
    )


# trace: ADDR-013
def log_integration(phase: str, order_number: str, amount: int, currency: str, **extra: Any) -> None:
    """LOG-06 外部連携ログ（送信時 request・受信時 response）。"""
    fields: dict[str, Any] = {
        "phase": phase,
        "order_number": order_number,
        "amount": amount,
        "currency": currency,
    }
    fields.update(extra)
    _emit(logging.INFO, "LOG-06", fields)


# trace: ADDR-013
@contextmanager
def request_scope(request_id: str) -> Iterator[str]:
    token = set_request_id(request_id)
    try:
        yield request_id
    finally:
        reset_request_id(token)


# trace: ADDR-013
@contextmanager
def operation_log(operation: str, user_id: int | None) -> Iterator[None]:
    """業務処理1回の開始・終了を LOG-01 に出力する。業務エラーは種類だけを出力する。"""
    from common.errors import ServiceError, is_request_parse_error

    log_operation(operation, "start", "-", user_id)
    try:
        yield
    except ServiceError as exc:
        result = exc.error_type if exc.reason is None else f"{exc.error_type}:{exc.reason}"
        log_operation(operation, "end", result, user_id)
        exc.mc_logged = True
        raise
    except Exception as exc:
        # 要求そのものを解釈できない場合は入力エラー（ERR-01）として記録する
        result = "input_error" if is_request_parse_error(exc) else "system_error"
        log_operation(operation, "end", result, user_id)
        raise
    log_operation(operation, "end", "success", user_id)


# trace: ADDR-013
def monotonic_ms(start: float) -> int:
    return int((time.monotonic() - start) * 1000)
