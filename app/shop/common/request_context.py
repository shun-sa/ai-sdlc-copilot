# trace: ADDR-005
"""要求ID・利用者IDを要求単位で保持するコンテキスト（contextvars）。"""
from contextvars import ContextVar

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
_user_id: ContextVar[int | None] = ContextVar("user_id", default=None)


# trace: ADDR-005
def set_request_id(request_id: str | None) -> None:
    """要求IDを設定する。"""
    _request_id.set(request_id)


# trace: ADDR-005
def get_request_id() -> str | None:
    """要求IDを取得する。"""
    return _request_id.get()


# trace: ADDR-005
def set_user_id(user_id: int | None) -> None:
    """ログイン中の利用者IDを設定する（未ログインは None）。"""
    _user_id.set(user_id)


# trace: ADDR-005
def get_user_id() -> int | None:
    """ログイン中の利用者IDを取得する。"""
    return _user_id.get()


# trace: ADDR-005
def reset() -> None:
    """要求の終了時にコンテキストを初期化する。"""
    _request_id.set(None)
    _user_id.set(None)
