"""FastAPIアプリケーション (Presentationエントリポイント)。

レイヤードアーキテクチャ (ADR-003) のPresentation層として、
ルーター登録・例外→エラー仕様 (ERR-001〜005) のマッピングを行う。
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import RedirectResponse

from app.dependencies import AuthRedirect, CsrfError
from app.errors import (
    AppError,
    AuthError,
    ForbiddenError,
    NotSaleableError,
    OutOfStockError,
    ValidationError,
)
from app.routers import auth, cart, history, movies, orders, pages, products, tickets
from app.templating import render


def create_app() -> FastAPI:
    app = FastAPI(title="映画館EC Webシステム")

    app.include_router(pages.router)
    app.include_router(auth.router)
    app.include_router(movies.router)
    app.include_router(products.router)
    app.include_router(cart.router)
    app.include_router(orders.router)
    app.include_router(tickets.router)
    app.include_router(history.router)

    _register_error_handlers(app)
    return app


def _register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AuthRedirect)
    async def _auth_redirect(request: Request, exc: AuthRedirect):
        # C-AUTH-003 / NFR-SEC-002: 未認証は必ずログイン画面へ
        return RedirectResponse(url="/login", status_code=303)

    @app.exception_handler(CsrfError)
    async def _csrf_error(request: Request, exc: CsrfError):
        return render(
            request,
            "error.html",
            {"user": None, "message": "セッションの検証に失敗しました。再度お試しください。"},
            status_code=403,
        )

    @app.exception_handler(ForbiddenError)
    async def _forbidden(request: Request, exc: ForbiddenError):
        # ERR-004 / NFR-SEC-003: 権限不足は操作不可として通知
        return render(
            request, "error.html", {"user": None, "message": exc.message}, status_code=403
        )

    @app.exception_handler(AuthError)
    async def _auth_error(request: Request, exc: AuthError):
        return render(
            request, "error.html", {"user": None, "message": exc.message}, status_code=400
        )

    @app.exception_handler(NotSaleableError)
    async def _not_saleable(request: Request, exc: NotSaleableError):
        return render(
            request, "error.html", {"user": None, "message": exc.message}, status_code=409
        )

    @app.exception_handler(OutOfStockError)
    async def _out_of_stock(request: Request, exc: OutOfStockError):
        return render(
            request, "error.html", {"user": None, "message": exc.message}, status_code=409
        )

    @app.exception_handler(ValidationError)
    async def _validation(request: Request, exc: ValidationError):
        return render(
            request, "error.html", {"user": None, "message": exc.message}, status_code=400
        )

    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError):
        return render(
            request, "error.html", {"user": None, "message": exc.message}, status_code=400
        )

    @app.exception_handler(RequestValidationError)
    async def _request_validation(request: Request, exc: RequestValidationError):
        # ERR-001: 入力形式不正
        return render(
            request,
            "error.html",
            {"user": None, "message": "入力値が正しくありません。"},
            status_code=400,
        )


app = create_app()
