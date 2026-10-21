# trace: ADDR-002
"""利用者・認証の応答表現（API と画面で同じ値を用いる）。"""

from __future__ import annotations

from typing import Any

from accounts.models import AuthToken, User
from common import timeutils


def user_payload(user: User) -> dict[str, Any]:
    """利用者情報（利用者ID・メールアドレス・氏名・ロール）。"""
    return {
        "user_id": user.pk,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
    }


def registered_user_payload(user: User) -> dict[str, Any]:
    """会員登録の応答（FR-001 出力）。"""
    payload = user_payload(user)
    payload["registered_at"] = timeutils.to_iso(user.registered_at)
    return payload


def login_payload(user: User, raw_token: str, token: AuthToken) -> dict[str, Any]:
    """ログインの応答（FR-002 出力）。"""
    return {
        "token": raw_token,
        "expires_at": timeutils.to_iso(token.expires_at),
        "user": user_payload(user),
    }
