"""認証ルーター (FR-001 会員登録 / FR-002 ログイン)。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.orm import Session

from app.cookies import clear_session_cookie, set_session_cookie
from app.database import get_db
from app.dependencies import get_current_session, get_optional_user, verify_csrf
from app.errors import AppError
from app.models.session import SessionRecord
from app.models.user import User
from app.schemas.auth import LoginInput, RegisterInput
from app.services.auth_service import AuthService
from app.templating import render

router = APIRouter()


def _ensure_session(db: Session, session: SessionRecord | None) -> SessionRecord:
    """CSRFトークン供給のためゲストにもセッションを発行する。"""
    if session is not None:
        return session
    return AuthService(db).create_session(user_id=None)


@router.get("/register")
def register_form(
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
    session: SessionRecord | None = Depends(get_current_session),
):
    session = _ensure_session(db, session)
    resp = render(
        request,
        "auth/register.html",
        {"user": user, "csrf_token": session.csrf_token, "errors": {}, "values": {}},
    )
    set_session_cookie(resp, session.id)
    return resp


@router.post("/register")
def register_submit(
    request: Request,
    name: str = Form(""),
    email: str = Form(""),
    password: str = Form(""),
    password_confirm: str = Form(""),
    db: Session = Depends(get_db),
    _: None = Depends(verify_csrf),
    session: SessionRecord | None = Depends(get_current_session),
):
    session = _ensure_session(db, session)
    values = {"name": name, "email": email}
    try:
        data = RegisterInput(
            name=name, email=email, password=password, password_confirm=password_confirm
        )
    except PydanticValidationError as exc:
        return _register_error(request, session, values, _field_errors(exc))

    service = AuthService(db)
    try:
        service.register(data)
    except AppError as exc:
        return _register_error(request, session, values, {"email": exc.message})

    # 登録完了で自動ログイン（セッションID再生成）
    new_session = service.login(
        LoginInput(email=email, password=password), existing_session_id=session.id
    )
    resp = RedirectResponse(url="/register/complete", status_code=303)
    set_session_cookie(resp, new_session.id)
    return resp


@router.get("/register/complete")
def register_complete(
    request: Request, user: User | None = Depends(get_optional_user)
):
    return render(request, "auth/register_complete.html", {"user": user})


@router.get("/login")
def login_form(
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
    session: SessionRecord | None = Depends(get_current_session),
):
    session = _ensure_session(db, session)
    resp = render(
        request,
        "auth/login.html",
        {"user": user, "csrf_token": session.csrf_token, "error": None},
    )
    set_session_cookie(resp, session.id)
    return resp


@router.post("/login")
def login_submit(
    request: Request,
    email: str = Form(""),
    password: str = Form(""),
    db: Session = Depends(get_db),
    _: None = Depends(verify_csrf),
    session: SessionRecord | None = Depends(get_current_session),
):
    session = _ensure_session(db, session)
    service = AuthService(db)
    try:
        data = LoginInput(email=email, password=password)
        new_session = service.login(data, existing_session_id=session.id)
    except (PydanticValidationError, AppError):
        # ERR-002 / NFR-SEC-006: 原因を区別しない汎用メッセージ
        resp = render(
            request,
            "auth/login.html",
            {
                "user": None,
                "csrf_token": session.csrf_token,
                "error": "メールアドレスまたはパスワードが正しくありません。",
            },
            status_code=400,
        )
        set_session_cookie(resp, session.id)
        return resp

    resp = RedirectResponse(url="/", status_code=303)
    set_session_cookie(resp, new_session.id)
    return resp


@router.post("/logout")
def logout(
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(verify_csrf),
    session: SessionRecord | None = Depends(get_current_session),
):
    if session is not None:
        AuthService(db).logout(session.id)
    resp = RedirectResponse(url="/", status_code=303)
    clear_session_cookie(resp)
    return resp


def _register_error(request, session, values, errors):
    resp = render(
        request,
        "auth/register.html",
        {
            "user": None,
            "csrf_token": session.csrf_token,
            "errors": errors,
            "values": values,
        },
        status_code=400,
    )
    set_session_cookie(resp, session.id)
    return resp


def _field_errors(exc: PydanticValidationError) -> dict:
    """Pydantic検証エラーを項目単位メッセージへ変換 (ERR-001 / C-UI-002)。"""
    errors: dict[str, str] = {}
    for err in exc.errors():
        loc = err["loc"]
        field = str(loc[-1]) if loc else "form"
        errors[field] = err.get("msg", "入力値が正しくありません。")
    return errors
