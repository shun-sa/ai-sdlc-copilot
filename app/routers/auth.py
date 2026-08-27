from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.config import Settings
from app.cookies import SessionCookieCodec
from app.dependencies import (
    get_current_user,
    get_db,
    get_session_codec,
    get_settings,
)
from app.errors import AppError
from app.models.user import User
from app.routers import render
from app.schemas.auth import LoginInput, RegisterInput
from app.services.auth_service import AuthService

router = APIRouter()


def _field_errors(exc: ValidationError) -> dict[str, str]:
    errors: dict[str, str] = {}
    for err in exc.errors():
        loc = err.get("loc", ())
        field = str(loc[-1]) if loc else "__root__"
        errors[field] = err.get("msg", "入力内容に誤りがあります。")
    return errors


def _set_session_cookie(
    response: RedirectResponse, settings: Settings, codec: SessionCookieCodec, token: str
) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=codec.encode(token),
        httponly=True,  # ADR-005: HttpOnly
        secure=settings.cookie_secure,
        samesite="lax",
    )


@router.get("/register")
def register_form(request: Request, current_user: User | None = Depends(get_current_user)):
    return render(request, "register.html", current_user, field_errors={}, form=None)


@router.post("/register")
def register(
    request: Request,
    name: str = Form(""),
    email: str = Form(""),
    password: str = Form(""),
    password_confirm: str = Form(""),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    codec: SessionCookieCodec = Depends(get_session_codec),
):
    form = {"name": name, "email": email}
    try:
        data = RegisterInput(
            name=name, email=email, password=password, password_confirm=password_confirm
        )
    except ValidationError as exc:
        # ERR-001 / NFR-SEC-004: 項目単位のエラー表示。
        return render(
            request, "register.html", None,
            status_code=400, field_errors=_field_errors(exc), form=form,
        )

    service = AuthService(db)
    try:
        user = service.register(data)
    except AppError as exc:
        return render(
            request, "register.html", None,
            status_code=400, field_errors=exc.field_errors or {}, form=form,
            error_message=exc.message,
        )

    # 登録完了、自動ログイン（FR-001）。
    record = service.create_session(user.id)
    response = RedirectResponse(url="/", status_code=303)
    _set_session_cookie(response, settings, codec, record.token)
    return response


@router.get("/login")
def login_form(
    request: Request,
    next: str | None = None,
    current_user: User | None = Depends(get_current_user),
):
    return render(request, "login.html", current_user, form=None, next_url=next)


@router.post("/login")
def login(
    request: Request,
    email: str = Form(""),
    password: str = Form(""),
    next: str = Form("/"),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    codec: SessionCookieCodec = Depends(get_session_codec),
):
    try:
        data = LoginInput(email=email, password=password)
    except ValidationError:
        return render(
            request, "login.html", None,
            status_code=400, form={"email": email}, next_url=next,
            error_message="メールアドレスまたはパスワードが正しくありません。",
        )

    service = AuthService(db)
    try:
        user = service.authenticate(data)
    except AppError as exc:
        # ERR-002 / NFR-SEC-006: 汎用文言。存在可否を推測させない。
        return render(
            request, "login.html", None,
            status_code=401, form={"email": email}, next_url=next,
            error_message=exc.message,
        )

    record = service.create_session(user.id)
    redirect_to = next if next and next.startswith("/") else "/"
    response = RedirectResponse(url=redirect_to, status_code=303)
    _set_session_cookie(response, settings, codec, record.token)
    return response


@router.post("/logout")
def logout(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    codec: SessionCookieCodec = Depends(get_session_codec),
):
    cookie_value = request.cookies.get(settings.session_cookie_name)
    if cookie_value:
        token = codec.decode(cookie_value)
        AuthService(db).logout(token)
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie(settings.session_cookie_name)
    return response
