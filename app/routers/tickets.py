from dataclasses import dataclass
from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.constants import TicketType
from app.dependencies import get_db, require_user
from app.errors import NotFoundError
from app.models.user import User
from app.routers import render
from app.routers.auth import _field_errors
from app.repositories.movie_repository import MovieRepository
from app.repositories.screening_repository import ScreeningRepository
from app.schemas.commerce import TicketPurchaseInput
from app.services.ticket_service import TicketService

router = APIRouter()


@dataclass
class ScreeningView:
    id: int
    movie_title: str
    starts_at: datetime
    theater_name: str
    screen_name: str
    seats_remaining: int


def _build_screening_view(db: Session, screening_id: int) -> tuple[ScreeningView, dict]:
    screening = ScreeningRepository(db).get(screening_id)
    if screening is None:
        raise NotFoundError()
    movie = MovieRepository(db).get_published(screening.movie_id)
    prices = {p.ticket_type: p.unit_price for p in screening.prices}
    prices_full = {tt: prices.get(tt) for tt in TicketType}
    view = ScreeningView(
        id=screening.id,
        movie_title=movie.title if movie else "",
        starts_at=screening.starts_at,
        theater_name=screening.theater_name,
        screen_name=screening.screen_name,
        seats_remaining=screening.seats_remaining,
    )
    return view, prices_full


@router.get("/tickets/new")
def ticket_form(
    request: Request,
    screening_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
):
    view, prices = _build_screening_view(db, screening_id)
    # NFR-USAB-004: 確定前に映画名・上映日時・券種・枚数・金額を確認可能。
    return render(request, "ticket_form.html", current_user, screening=view, prices=prices)


@router.post("/tickets")
def purchase_ticket(
    request: Request,
    screening_id: int = Form(...),
    ticket_type: str = Form(""),
    quantity: int = Form(1),
    payment_method: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
):
    try:
        data = TicketPurchaseInput(
            screening_id=screening_id, ticket_type=ticket_type,
            quantity=quantity, payment_method=payment_method,
        )
    except ValidationError as exc:
        view, prices = _build_screening_view(db, screening_id)
        return render(
            request, "ticket_form.html", current_user,
            status_code=400, screening=view, prices=prices, field_errors=_field_errors(exc),
        )

    purchase = TicketService(db).purchase(current_user.id, data)
    return render(request, "ticket_done.html", current_user, purchase=purchase)
