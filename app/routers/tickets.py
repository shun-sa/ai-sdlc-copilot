"""チケット購入ルーター (FR-009)。要認証 (C-AUTH-002)。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.orm import Session

from app.constants import DEFAULT_PAYMENT_METHOD, PAYMENT_METHODS, TICKET_TYPE_LABELS, TICKET_TYPES
from app.database import get_db
from app.dependencies import get_current_session, require_user, verify_csrf
from app.errors import AppError
from app.models.movie import Movie
from app.models.session import SessionRecord
from app.models.user import User
from app.payment import get_payment_gateway
from app.repositories.screening_repository import ScreeningRepository
from app.schemas.commerce import TicketPurchaseInput
from app.services.ticket_service import TicketService
from app.templating import render

router = APIRouter(prefix="/tickets")


@router.get("/screenings/{screening_id}")
def ticket_form(
    request: Request,
    screening_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    session: SessionRecord | None = Depends(get_current_session),
):
    screening = ScreeningRepository(db).get(screening_id)
    if screening is None:
        raise HTTPException(status_code=404, detail="上映回が見つかりません。")
    movie = db.get(Movie, screening.movie_id)
    saleable = ScreeningRepository.is_saleable(screening)
    # NFR-USAB-004: 確定前に映画名・上映日時・券種・枚数・金額を確認可能
    return render(
        request,
        "tickets/new.html",
        {
            "user": user,
            "screening": screening,
            "movie": movie,
            "saleable": saleable,
            "ticket_types": TICKET_TYPES,
            "ticket_labels": TICKET_TYPE_LABELS,
            "payment_methods": PAYMENT_METHODS,
            "default_payment": DEFAULT_PAYMENT_METHOD,
            "csrf_token": session.csrf_token if session else "",
            "error": None,
        },
    )


@router.post("")
def purchase_ticket(
    request: Request,
    screening_id: int = Form(...),
    ticket_type: str = Form(...),
    quantity: int = Form(...),
    payment_method: str = Form(DEFAULT_PAYMENT_METHOD),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    _: None = Depends(verify_csrf),
):
    try:
        data = TicketPurchaseInput(
            screening_id=screening_id,
            ticket_type=ticket_type,
            quantity=quantity,
            payment_method=payment_method,
        )
    except PydanticValidationError:
        return RedirectResponse(
            url=f"/tickets/screenings/{screening_id}", status_code=303
        )

    service = TicketService(db, get_payment_gateway())
    try:
        purchase = service.purchase(user.id, data)
    except AppError as exc:
        return RedirectResponse(
            url=f"/tickets/screenings/{screening_id}?error={exc.message}", status_code=303
        )
    return RedirectResponse(url=f"/tickets/{purchase.id}/complete", status_code=303)


@router.get("/{purchase_id}/complete")
def ticket_complete(
    request: Request,
    purchase_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    from app.models.ticket import TicketPurchase

    purchase = db.get(TicketPurchase, purchase_id)
    # ADR-005: 所有者スコープ強制
    if purchase is None or purchase.user_id != user.id:
        raise HTTPException(status_code=404, detail="購入が見つかりません。")
    return render(request, "tickets/complete.html", {"user": user, "purchase": purchase})
