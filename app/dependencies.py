from collections.abc import Iterator

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.config import Settings
from app.cookies import SessionCookieCodec
from app.errors import AuthenticationRequiredError
from app.models.user import User
from app.services.auth_service import AuthService


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_session_codec(request: Request) -> SessionCookieCodec:
    return request.app.state.session_codec


def get_db(request: Request) -> Iterator[Session]:
    session_factory = request.app.state.session_factory
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    codec: SessionCookieCodec = Depends(get_session_codec),
) -> User | None:
    """署名Cookieからセッションtokenを検証し、対応するユーザーを解決する（ADR-005）。"""
    cookie_value = request.cookies.get(settings.session_cookie_name)
    if not cookie_value:
        return None
    token = codec.decode(cookie_value)  # 署名検証。改ざん時はNone。
    if token is None:
        return None
    return AuthService(db).resolve_user(token)


def require_user(current_user: User | None = Depends(get_current_user)) -> User:
    """要認証機能のガード（C-AUTH-003 / NFR-SEC-002）。未認証はログイン画面へ遷移させる。"""
    if current_user is None:
        raise AuthenticationRequiredError()
    return current_user
