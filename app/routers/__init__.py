from typing import Any

from fastapi import Request
from fastapi.responses import HTMLResponse

from app.models.user import User


def render(
    request: Request,
    template_name: str,
    current_user: User | None = None,
    *,
    status_code: int = 200,
    **context: Any,
) -> HTMLResponse:
    templates = request.app.state.templates
    ctx = {"current_user": current_user}
    ctx.update(context)
    return templates.TemplateResponse(request, template_name, ctx, status_code=status_code)
