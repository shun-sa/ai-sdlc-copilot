# trace: ADDR-007
"""標準出力へ 1行1JSON で出力するログフォーマッタと、相関IDの保持。

禁止項目（パスワード・認証トークン・メールアドレス・氏名・住所・電話番号・要求本文・
Authorization ヘッダー・クエリ文字列）はログレコードへ渡さない（ADDR-007 INV-004）。
例外は種類と発生箇所（ファイル名・行番号・関数名）だけを出力し、例外メッセージ本文
（項目値・SQLのパラメータ値を含み得る）は出力しない（LOG-02、NFR-SC-06、CLS-03）。
相関ID（request_id）は共通ミドルウェアが設定し、1件の要求に関する全ログ行へ同じ値を
出力する（ADDR-007 DD-003、INV-003、ADDR-011 DD-003）。
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import traceback
from contextvars import ContextVar, Token
from types import TracebackType
from typing import Any

STANDARD_ATTRS = frozenset(
    {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "module",
        "msecs",
        "message",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "taskName",
        "thread",
        "threadName",
    }
)

JST = dt.timezone(dt.timedelta(hours=9), "JST")

# 要求・応答オブジェクト（クエリ文字列・要求本文・Authorization ヘッダーを保持する）と、
# SQL文・SQLのパラメータ値を持つ属性は、フレームワークが extra で渡しても出力しない。
DENIED_ATTRS = frozenset({"request", "response", "sql", "params"})

REQUEST_ID_FIELD = "request_id"

_request_id: ContextVar[str] = ContextVar("minicommerce_request_id", default="")


# trace: ADDR-007
def set_request_id(request_id: str) -> Token[str]:
    """現在の実行文脈へ相関IDを設定する（ADDR-007 DD-003）。"""
    return _request_id.set(request_id)


# trace: ADDR-007
def reset_request_id(token: Token[str]) -> None:
    """相関IDを設定前の状態へ戻す。"""
    _request_id.reset(token)


# trace: ADDR-007
def current_request_id() -> str:
    """現在の実行文脈の相関IDを返す（未設定の場合は空文字）。"""
    return _request_id.get()


# trace: ADDR-007
def is_json_safe(value: Any) -> bool:
    """JSONの基本型だけで構成された値か判定する（オブジェクトはログへ出力しない）。"""
    if value is None or isinstance(value, str | bool | int | float):
        return True
    if isinstance(value, list | tuple):
        return all(is_json_safe(element) for element in value)
    if isinstance(value, dict):
        return all(isinstance(key, str) and is_json_safe(element) for key, element in value.items())
    return False


# trace: ADDR-007
def exception_fields(
    exc_info: tuple[type[BaseException], BaseException, TracebackType | None] | tuple[None, None, None],
) -> dict[str, object]:
    """例外の種類と発生箇所だけを組み立てる（例外メッセージ本文は出力しない。LOG-02）。"""
    _exc_type, exc_value, exc_traceback = exc_info
    if exc_value is None:
        return {}
    types: list[str] = []
    cause: BaseException | None = exc_value
    while cause is not None and len(types) < 5:
        types.append(f"{type(cause).__module__}.{type(cause).__qualname__}")
        cause = cause.__cause__ or cause.__context__
    location = [
        {"file": frame.filename, "line": frame.lineno, "function": frame.name}
        for frame in traceback.extract_tb(exc_traceback)
    ]
    return {
        "exception_type": types[0],
        "exception_chain": types[1:],
        "exception_location": location,
    }


class RequestIdFilter(logging.Filter):
    """相関IDを持たないログレコードへ request_id を補うフィルタ。

    フレームワークが応答確定後に出力する 4xx/5xx のログ行（``django.request``）は、
    要求ごとの実行文脈を抜けた後に記録されるため ContextVar から相関IDを得られない。
    その場合は Django がレコードへ添える要求オブジェクトの ``request_id`` を用いる
    （要求オブジェクト自体は DENIED_ATTRS によりログへ出力しない。ADDR-007 INV-003）。
    """

    # trace: ADDR-007
    def filter(self, record: logging.LogRecord) -> bool:
        """レコードへ相関IDを設定する（出力の可否は変えない）。"""
        if getattr(record, REQUEST_ID_FIELD, ""):
            return True
        request_id = current_request_id()
        if not request_id:
            request = getattr(record, "request", None)
            request_id = str(getattr(request, REQUEST_ID_FIELD, "") or "") if request is not None else ""
        if request_id:
            setattr(record, REQUEST_ID_FIELD, request_id)
        return True


class JsonLinesFormatter(logging.Formatter):
    """ログレコードを JSON Lines（UTF-8）へ整形する。"""

    # trace: ADDR-007
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": dt.datetime.fromtimestamp(record.created, tz=JST).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key in STANDARD_ATTRS or key in DENIED_ATTRS or key.startswith("_"):
                continue
            if not is_json_safe(value):
                continue
            payload[key] = value
        if not payload.get(REQUEST_ID_FIELD):
            request_id = current_request_id()
            if request_id:
                payload[REQUEST_ID_FIELD] = request_id
        if record.exc_info:
            payload.update(exception_fields(record.exc_info))
        return json.dumps(payload, ensure_ascii=False, default=str)
