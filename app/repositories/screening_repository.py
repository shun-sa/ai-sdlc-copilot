from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.screening import Screening, ScreeningTicketPrice


class ScreeningRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, screening_id: int) -> Screening | None:
        return self._session.get(Screening, screening_id)

    def get_for_update(self, screening_id: int) -> Screening | None:
        """残席行を悲観ロックで取得する（ADR-007）。"""
        stmt = select(Screening).where(Screening.id == screening_id).with_for_update()
        return self._session.scalars(stmt).first()

    def list_by_movie(self, movie_id: int) -> list[Screening]:
        stmt = (
            select(Screening)
            .where(Screening.movie_id == movie_id)
            .order_by(Screening.starts_at.asc())
        )
        return list(self._session.scalars(stmt).all())

    def get_price(self, screening_id: int, ticket_type) -> ScreeningTicketPrice | None:
        stmt = select(ScreeningTicketPrice).where(
            ScreeningTicketPrice.screening_id == screening_id,
            ScreeningTicketPrice.ticket_type == ticket_type,
        )
        return self._session.scalars(stmt).first()
