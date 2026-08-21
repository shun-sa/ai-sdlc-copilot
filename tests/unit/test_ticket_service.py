"""映画チケット購入サービス単体テスト (FR-009)。

対象: app/services/ticket_service.py
検証Requirement:
- FR-009 チケット購入 (残席減算, 購入番号発行, 販売期間/上映開始前/残席チェック)
- ADR-007 / NFR-AVL-002 (残席確認と減算の原子性)
- ADR-008 (上映スナップショット保持・確定後不変)
- ERR-003 (残席不足で購入失敗) / ERR-004 (販売期間外は購入不可)
- ERR-005 / NFR-AVL-004 (更新失敗時に不整合を残さない)
DB Strategy: CONTAINER (使い捨てSQLite。残席整合性の実挙動を検証)。
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.constants import TICKET_TYPES
from app.errors import NotSaleableError, OutOfStockError, ValidationError
from app.models.movie import Movie
from app.models.screening import Screening
from app.models.ticket import TicketPurchase
from app.models.user import User
from app.payment import PaymentGateway
from app.schemas.commerce import TicketPurchaseInput
from app.services.ticket_service import TicketService


def _ticket_input(screening_id: int, **overrides: object) -> TicketPurchaseInput:
    data = {
        "screening_id": screening_id,
        "ticket_type": "general",
        "quantity": 2,
        "payment_method": "mock_credit_card",
    }
    data.update(overrides)
    return TicketPurchaseInput(**data)  # type: ignore[arg-type]


def _purchase_count(db: Session) -> int:
    return db.execute(select(func.count()).select_from(TicketPurchase)).scalar_one()


class TestPurchaseNormal:
    # FR-009 正常系: 購入番号が発行され残席が減算される
    def test_purchase_issues_number_and_decrements_seats(
        self,
        db: Session,
        payment: PaymentGateway,
        make_user: Callable[..., User],
        make_screening: Callable[..., Screening],
    ) -> None:
        user = make_user()
        screening = make_screening(seats_remaining=10)

        purchase = TicketService(db, payment).purchase(user.id, _ticket_input(screening.id))
        assert purchase.purchase_number.startswith("TKT-")
        assert purchase.total_amount == TICKET_TYPES["general"] * 2

        db.refresh(screening)
        assert screening.seats_remaining == 8  # 10 - 2

    # ADR-008: 上映スナップショット(映画名/上映日時/劇場)を保持する
    def test_snapshot_saved(
        self,
        db: Session,
        payment: PaymentGateway,
        make_user: Callable[..., User],
        make_movie: Callable[..., Movie],
        make_screening: Callable[..., Screening],
    ) -> None:
        user = make_user()
        movie = make_movie(title="名作映画")
        screening = make_screening(
            movie_id=movie.id, seats_remaining=10, theater_name="劇場X"
        )

        purchase = TicketService(db, payment).purchase(user.id, _ticket_input(screening.id))
        item = purchase.items[0]
        assert item.movie_title_snapshot == "名作映画"
        assert item.theater_name_snapshot == "劇場X"
        assert item.ticket_type == "general"
        assert item.unit_price == TICKET_TYPES["general"]

    # ADR-008: 確定後にマスタを変更してもスナップショットは不変
    def test_snapshot_immutable_after_master_change(
        self,
        db: Session,
        payment: PaymentGateway,
        make_user: Callable[..., User],
        make_movie: Callable[..., Movie],
        make_screening: Callable[..., Screening],
    ) -> None:
        user = make_user()
        movie = make_movie(title="旧タイトル")
        screening = make_screening(movie_id=movie.id, seats_remaining=10, theater_name="旧劇場")
        purchase = TicketService(db, payment).purchase(user.id, _ticket_input(screening.id))

        movie.title = "新タイトル"
        screening.theater_name = "新劇場"
        db.commit()
        db.refresh(purchase)

        assert purchase.items[0].movie_title_snapshot == "旧タイトル"
        assert purchase.items[0].theater_name_snapshot == "旧劇場"

    # 境界: 残席ちょうどまでは購入可
    def test_purchase_up_to_remaining_boundary(
        self,
        db: Session,
        payment: PaymentGateway,
        make_user: Callable[..., User],
        make_screening: Callable[..., Screening],
    ) -> None:
        user = make_user()
        screening = make_screening(seats_remaining=2)
        TicketService(db, payment).purchase(user.id, _ticket_input(screening.id, quantity=2))
        db.refresh(screening)
        assert screening.seats_remaining == 0


class TestPurchaseFailure:
    # ERR-003 / NFR-AVL-004: 残席不足時は購入失敗し残席は変化しない
    def test_insufficient_seats_rolls_back(
        self,
        db: Session,
        payment: PaymentGateway,
        make_user: Callable[..., User],
        make_screening: Callable[..., Screening],
    ) -> None:
        user = make_user()
        screening = make_screening(seats_remaining=1)

        with pytest.raises(OutOfStockError):
            TicketService(db, payment).purchase(user.id, _ticket_input(screening.id, quantity=2))

        assert _purchase_count(db) == 0
        db.refresh(screening)
        assert screening.seats_remaining == 1  # 減算されていない

    # ERR-004: 上映開始後は購入不可 (残席は変化しない)
    def test_after_start_rejected(
        self,
        db: Session,
        payment: PaymentGateway,
        make_user: Callable[..., User],
        make_screening: Callable[..., Screening],
    ) -> None:
        user = make_user()
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        screening = make_screening(seats_remaining=10, starts_at=past)

        with pytest.raises(NotSaleableError):
            TicketService(db, payment).purchase(user.id, _ticket_input(screening.id))

        assert _purchase_count(db) == 0
        db.refresh(screening)
        assert screening.seats_remaining == 10

    # ERR-004 / C-DATA-002: 販売終了後は購入不可
    def test_after_sales_end_rejected(
        self,
        db: Session,
        payment: PaymentGateway,
        make_user: Callable[..., User],
        make_screening: Callable[..., Screening],
    ) -> None:
        user = make_user()
        now = datetime.now(timezone.utc)
        screening = make_screening(
            seats_remaining=10,
            starts_at=now + timedelta(days=2),
            sales_end_at=now - timedelta(hours=1),
        )
        with pytest.raises(NotSaleableError):
            TicketService(db, payment).purchase(user.id, _ticket_input(screening.id))

    # ERR-001: 未定義券種は購入不可
    def test_invalid_ticket_type_rejected(
        self,
        db: Session,
        payment: PaymentGateway,
        make_user: Callable[..., User],
        make_screening: Callable[..., Screening],
    ) -> None:
        user = make_user()
        screening = make_screening(seats_remaining=10)
        with pytest.raises(ValidationError):
            TicketService(db, payment).purchase(
                user.id, _ticket_input(screening.id, ticket_type="vip_unknown")
            )

    # ERR-004: 存在しない上映回は購入不可
    def test_missing_screening_rejected(
        self, db: Session, payment: PaymentGateway, make_user: Callable[..., User]
    ) -> None:
        user = make_user()
        with pytest.raises(ValidationError):
            TicketService(db, payment).purchase(user.id, _ticket_input(999999))
