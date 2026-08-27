from urllib.parse import quote

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse

from app.config import Settings, load_settings
from app.cookies import SessionCookieCodec
from app.database import create_all, create_db_engine, create_session_factory
from app.errors import AppError, AuthenticationRequiredError, ErrorCategory
from app.routers import auth, cart, history, movies, orders, pages, products, tickets
from app.templating import create_templates

# ADR-010: エラー分類 -> HTTPステータスの対応。
_STATUS_BY_CATEGORY = {
    ErrorCategory.INPUT_INVALID: 400,
    ErrorCategory.AUTH_FAILURE: 401,
    ErrorCategory.PERMISSION_DENIED: 403,
    ErrorCategory.STOCK_SHORTAGE: 409,
    ErrorCategory.OUT_OF_SALES_PERIOD: 409,
}


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    app = FastAPI(title="映画館EC Webシステム")

    # ADR-003: DB接続はDIで供給。接続先URLはsettings（環境変数）から注入する。
    engine = create_db_engine(settings.database_url)
    create_all(engine)

    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = create_session_factory(engine)
    app.state.session_codec = SessionCookieCodec(settings.secret_key)
    app.state.templates = create_templates()

    app.include_router(pages.router)
    app.include_router(auth.router)
    app.include_router(movies.router)
    app.include_router(products.router)
    app.include_router(cart.router)
    app.include_router(orders.router)
    app.include_router(tickets.router)
    app.include_router(history.router)

    _register_exception_handlers(app)
    return app


def _register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AuthenticationRequiredError)
    async def _auth_required_handler(request: Request, exc: AuthenticationRequiredError):
        # C-AUTH-003 / NFR-SEC-002: 未認証の要認証アクセスはログイン画面へ遷移。
        next_path = quote(request.url.path, safe="/")
        return RedirectResponse(url=f"/login?next={next_path}", status_code=303)

    @app.exception_handler(AppError)
    async def _app_error_handler(request: Request, exc: AppError):
        status_code = _STATUS_BY_CATEGORY.get(exc.category, 400)
        templates = request.app.state.templates
        # ADR-010: 例外詳細を露出せず、分類ごとの定義済みメッセージを表示する。
        return templates.TemplateResponse(
            request, "error.html", {"current_user": None, "error_message": exc.message},
            status_code=status_code,
        )


app = create_app()
