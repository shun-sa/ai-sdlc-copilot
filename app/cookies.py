"""Session Cookie操作 (ADR-004)。HttpOnly/Secure/SameSite を付与し署名する。"""

from __future__ import annotations

from fastapi import Response

from app.config import get_settings
from app.security import sign_value


def set_session_cookie(response: Response, session_id: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.session_cookie_name,
        value=sign_value(session_id),  # 署名付き (改ざん検知)
        max_age=settings.session_max_age_seconds,
        httponly=True,  # ADR-004: JSからのアクセスを不可に
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(key=settings.session_cookie_name, path="/")
