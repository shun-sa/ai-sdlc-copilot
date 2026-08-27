from pathlib import Path

from fastapi.templating import Jinja2Templates

from app.constants import (
    PAYMENT_METHOD_LABELS,
    TICKET_TYPE_LABELS,
    PaymentMethod,
    TicketType,
)
from app.time_utils import format_datetime, format_yen

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


def create_templates() -> Jinja2Templates:
    """Jinja2の自動エスケープでXSSを防止する（ADR-009 / NFR-SEC-005）。"""
    templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))
    # C-UI-004 / C-UI-005: 金額・日時の表示フォーマット。
    templates.env.filters["yen"] = format_yen
    templates.env.filters["dt"] = format_datetime
    templates.env.filters["payment_label"] = lambda m: PAYMENT_METHOD_LABELS.get(m, str(m))
    templates.env.filters["ticket_label"] = lambda t: TICKET_TYPE_LABELS.get(t, str(t))
    templates.env.globals["payment_methods"] = list(PaymentMethod)
    templates.env.globals["ticket_types"] = list(TicketType)
    templates.env.globals["payment_labels"] = PAYMENT_METHOD_LABELS
    templates.env.globals["ticket_labels"] = TICKET_TYPE_LABELS
    return templates
