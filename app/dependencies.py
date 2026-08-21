"""Presentation層の共通依存 (認証・認可・CSRF / ADR-004 / ADR-005)。"""

from __future__ import annotations

from fastapi import Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models.session import SessionRecord
from app.models.user import User
from app.security import constant_time_equals, unsign_value
from app.services.auth_service import AuthService


class AuthRedirect(Exception):
    """未認証時にログイン画面へ遷移させるためのシグナル (C-AUTH-003)。"""


class CsrfError(Exception):
    """CSRFトークン検証失敗 (ADR-004)。"""


def _read_session(request: Request, db: Session) -> SessionRecord | None:
    settings = get_settings()
    signed = request.cookies.get(settings.session_cookie_name)
    if not signed:
        return None
    session_id = unsign_value(signed)  # 署名検証 (改ざん検知)
    if not session_id:
        return None
    return AuthService(db).get_session(session_id)


def get_current_session(
    request: Request, db: Session = Depends(get_db)
) -> SessionRecord | None:
    return _read_session(request, db)


def get_optional_user(
    request: Request, db: Session = Depends(get_db)
) -> User | None:
    session = _read_session(request, db)
    if session is None or session.user_id is None:
        return None
    return db.get(User, session.user_id)


def require_user(
    request: Request, db: Session = Depends(get_db)
) -> User:
    """要認証機能のガード (NFR-SEC-002 / C-AUTH-003)。

    未認証時はサーバー側で拒否し、ログイン画面へ遷移させる。
    """
    session = _read_session(request, db)
    if session is None or session.user_id is None:
        raise AuthRedirect()
    user = db.get(User, session.user_id)
    if user is None or user.status != "active":
        raise AuthRedirect()
    return user


def verify_csrf(
    request: Request,
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
) -> None:
    """状態変更操作のCSRFトークン検証 (ADR-004)。"""
    session = _read_session(request, db)
    if session is None or not constant_time_equals(csrf_token, session.csrf_token):
        raise CsrfError()


def login_redirect() -> RedirectResponse:
    return RedirectResponse(url="/login", status_code=303)
