"""テンプレート環境と表示ヘルパ (C-UI-004 / C-UI-005 / ADR-012)。

Jinja2の自動エスケープを有効にしてXSSを構造的に抑止する (NFR-SEC-005)。
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi import Request
from fastapi.templating import Jinja2Templates

_TEMPLATE_DIR = Path(__file__).parent / "templates"

# autoescape はFastAPIのJinja2Templatesで既定有効。明示的に無効化しない (ADR-012)。
templates = Jinja2Templates(directory=str(_TEMPLATE_DIR))


def yen(value: int | None) -> str:
    """税込・3桁区切り円表記 (C-UI-004)。例: 1,980円。"""
    if value is None:
        return ""
    return f"{value:,}円"


def jdatetime(value: datetime | None) -> str:
    """YYYY/MM/DD HH:mm 形式 (C-UI-005)。"""
    if value is None:
        return ""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.strftime("%Y/%m/%d %H:%M")


def jdate(value) -> str:
    if value is None:
        return ""
    return value.strftime("%Y/%m/%d")


templates.env.filters["yen"] = yen
templates.env.filters["jdatetime"] = jdatetime
templates.env.filters["jdate"] = jdate


def render(request: Request, name: str, context: dict, status_code: int = 200):
    ctx = {"request": request, **context}
    return templates.TemplateResponse(name, ctx, status_code=status_code)
