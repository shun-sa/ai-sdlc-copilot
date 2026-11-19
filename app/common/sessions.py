# trace: ADDR-002
"""画面のログイン状態のセッション保存（ADDR-002：Django のセッションをデータベースに保持する）。

Cookie で受け取ったセッションキーにデータベースが受理しない文字（NUL 等）が含まれる場合は、
データベースを照会せずに存在しないセッションとして扱う（来訪者として処理する。NFR-SC-04）。
"""

from typing import Any

from django.contrib.sessions.backends.db import SessionStore as DatabaseSessionStore

from common.normalize import has_unstorable_chars


# trace: ADDR-002
class SessionStore(DatabaseSessionStore):
    """django.contrib.sessions.backends.db と同じ保存方式で、セッションキーの文字だけを追加で検査する。"""

    def _validate_session_key(self, key: Any) -> bool:
        return bool(super()._validate_session_key(key)) and not has_unstorable_chars(key)
