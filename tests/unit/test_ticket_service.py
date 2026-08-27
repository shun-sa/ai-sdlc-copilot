"""TicketService の単体テスト（使い捨て in-memory SQLite）。

Requirement: FR-009 / C-DATA-004 / ERR-003 / ERR-005 / NFR-AVL-002 / NFR-AVL-004
ADR: ADR-007（トランザクション整合）/ ADR-008（スナップショット）/ ADR-012（券種・価格）
Criteria: normal-case, boundary-value, exception, database, security
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from app.constants import PaymentMethod, TicketType
from app.errors import InputInvalidError, OutOfSalesPeriodError, StockShortageError
from app.models.screening import Screening
from app.models.ticket import TicketPurchase
from app.schemas.commerce import TicketPurchaseInput
from app.services.ticket_service import TicketService

from .conftest import make_movie, make_screening, make_user

UTC = timezone.utc


def _purchase_input(screening_id: int, **overrides: object) -> TicketPurchaseInput:
    data = {
        "screening_id": screening_id,
        "ticket_type": TicketType.GENERAL,
        "quantity": 2,
        "payment_method": PaymentMethod.CREDIT_CARD_MOCK,
    }
    data.update(overrides)
    return TicketPurchaseInput(**data)


class TestPurchaseNormal:
    def test_purchase_issues_number_and_amount(self, db_session: Session) -> None:
        # FR-009 / ADR-012: 金額はサーバー側単価×枚数で算出。
        user = make_user(db_session)
        movie = make_movie(db_session)
        screening = make_screening(
            db_session, movie_id=movie.id, seats_remaining=20,
            prices={TicketType.GENERAL: 1900},
        )
        purchase = TicketService(db_session).purchase(user.id, _purchase_input(screening.id, quantity=2))
        assert purchase.purchase_number
        assert purchase.total_amount == 1900 * 2

    def test_seats_decremented(self, db_session: Session) -> None:
        # NFR-AVL-002: 購入登録と残席減算の整合。
        user = make_user(db_session)
        movie = make_movie(db_session)
        screening = make_screening(db_session, movie_id=movie.id, seats_remaining=20)
        TicketService(db_session).purchase(user.id, _purchase_input(screening.id, quantity=3))
        assert db_session.get(Screening, screening.id).seats_remaining == 17

    def test_purchase_up_to_remaining_boundary(self, db_session: Session) -> None:
        # 境界: 残席ちょうどまで購入可能。
        user = make_user(db_session)
        movie = make_movie(db_session)
        screening = make_screening(db_session, movie_id=movie.id, seats_remaining=4)
        TicketService(db_session).purchase(user.id, _purchase_input(screening.id, quantity=4))
        assert db_session.get(Screening, screening.id).seats_remaining == 0

    def test_snapshot_immutable_after_master_change(self, db_session: Session) -> None:
        # C-DATA-004 / ADR-008: 券種単価・映画名を確定時点スナップショットで保持。
        user = make_user(db_session)
        movie = make_movie(db_session, title="旧タイトル")
        screening = make_screening(
            db_session, movie_id=movie.id, seats_remaining=10,
            prices={TicketType.GENERAL: 1900},
        )
        purchase = TicketService(db_session).purchase(user.id, _purchase_input(screening.id, quantity=1))
        item = purchase.items[0]
        assert item.movie_title_snapshot == "旧タイトル"
        assert item.unit_price == 1900

        movie.title = "新タイトル"
        db_session.commit()
        stored = db_session.get(TicketPurchase, purchase.id)
        assert stored.items[0].movie_title_snapshot == "旧タイトル"


class TestPurchaseFailure:
    def test_unknown_ticket_type_price_rejected(self, db_session: Session) -> None:
        # ADR-012: 単価設定のない券種は購入不可。
        user = make_user(db_session)
        movie = make_movie(db_session)
        screening = make_screening(
            db_session, movie_id=movie.id, seats_remaining=10,
            prices={TicketType.GENERAL: 1900},  # STUDENT の価格未設定
        )
        db_session.commit()
        with pytest.raises(InputInvalidError):
            TicketService(db_session).purchase(
                user.id, _purchase_input(screening.id, ticket_type=TicketType.STUDENT, quantity=1)
            )

    def test_insufficient_seats_rolls_back(self, db_session: Session) -> None:
        # ERR-003 / NFR-AVL-004: 残席不足で購入失敗し、残席は減算されない。
        user = make_user(db_session)
        movie = make_movie(db_session)
        screening = make_screening(db_session, movie_id=movie.id, seats_remaining=1)
        db_session.commit()
        with pytest.raises(StockShortageError):
            TicketService(db_session).purchase(user.id, _purchase_input(screening.id, quantity=2))
        assert db_session.get(Screening, screening.id).seats_remaining == 1
        assert db_session.query(TicketPurchase).count() == 0

    def test_out_of_sales_period_rejected(self, db_session: Session) -> None:
        # C-DATA-002 / ERR-004: 販売期間外は購入不可。
        user = make_user(db_session)
        movie = make_movie(db_session)
        now = datetime.now(UTC)
        screening = make_screening(
            db_session,
            movie_id=movie.id,
            seats_remaining=10,
            sales_start_at=now - timedelta(days=5),
            sales_end_at=now - timedelta(days=1),  # 販売終了済み
            starts_at=now + timedelta(days=1),
        )
        db_session.commit()
        with pytest.raises(OutOfSalesPeriodError):
            TicketService(db_session).purchase(user.id, _purchase_input(screening.id, quantity=1))

    def test_after_screening_started_rejected(self, db_session: Session) -> None:
        # FR-009: 上映開始後は購入不可。
        user = make_user(db_session)
        movie = make_movie(db_session)
        now = datetime.now(UTC)
        screening = make_screening(
            db_session,
            movie_id=movie.id,
            seats_remaining=10,
            sales_start_at=now - timedelta(days=5),
            sales_end_at=now + timedelta(days=5),
            starts_at=now - timedelta(hours=1),  # すでに上映開始
        )
        db_session.commit()
        with pytest.raises(OutOfSalesPeriodError):
            TicketService(db_session).purchase(user.id, _purchase_input(screening.id, quantity=1))
