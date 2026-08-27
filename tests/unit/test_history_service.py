"""HistoryService の単体テスト（使い捨て in-memory SQLite）。

Requirement: FR-010 / NFR-SEC-003 / C-AUTH-004 / NFR-PERF-003
ADR: ADR-006（本人絞り込み）/ ADR-008（スナップショット表示）/ ADR-013（降順・20件ページング）
Criteria: normal-case, security, database, boundary-value
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.order import Order, OrderItem
from app.models.ticket import TicketPurchase, TicketPurchaseItem
from app.constants import TicketType
from app.services.history_service import HistoryService

from .conftest import make_movie, make_product, make_screening, make_user

UTC = timezone.utc


def _add_order(
    session: Session, user_id: int, number: str, ordered_at: datetime, product_id: int
) -> Order:
    order = Order(
        order_number=number,
        user_id=user_id,
        ordered_at=ordered_at,
        shipping_address="住所",
        recipient_name="受取",
        postal_code="150-0001",
        prefecture="東京都",
        city_address="渋谷区1-1-1",
        phone="0312345678",
        payment_method="CREDIT_CARD_MOCK",
        total_amount=1000,
    )
    order.items.append(
        OrderItem(
            product_id=product_id,
            product_snapshot_name="商品",
            unit_price=1000,
            quantity=1,
            subtotal=1000,
        )
    )
    session.add(order)
    session.flush()
    return order


def _add_ticket(
    session: Session, user_id: int, number: str, purchased_at: datetime, screening_id: int
) -> TicketPurchase:
    purchase = TicketPurchase(
        purchase_number=number,
        user_id=user_id,
        purchased_at=purchased_at,
        total_amount=1900,
    )
    purchase.items.append(
        TicketPurchaseItem(
            screening_id=screening_id,
            movie_title_snapshot="映画",
            screening_starts_at_snapshot=datetime.now(UTC),
            ticket_type=TicketType.GENERAL,
            unit_price=1900,
            quantity=1,
            subtotal=1900,
        )
    )
    session.add(purchase)
    session.flush()
    return purchase


class TestListHistoryOwnership:
    def test_only_own_orders_and_tickets(self, db_session: Session) -> None:
        # NFR-SEC-003 / ADR-006 / C-AUTH-004: 本人分のみ表示。
        me = make_user(db_session, email="me@example.com")
        other = make_user(db_session, email="other@example.com")
        product = make_product(db_session)
        movie = make_movie(db_session)
        screening = make_screening(db_session, movie_id=movie.id)
        now = datetime.now(UTC)
        _add_order(db_session, me.id, "ORD-ME", now, product.id)
        _add_order(db_session, other.id, "ORD-OTHER", now, product.id)
        _add_ticket(db_session, me.id, "TKT-ME", now, screening.id)
        _add_ticket(db_session, other.id, "TKT-OTHER", now, screening.id)
        db_session.commit()

        view = HistoryService(db_session).list_history(me.id)
        assert [o.order_number for o in view.orders] == ["ORD-ME"]
        assert [t.purchase_number for t in view.tickets] == ["TKT-ME"]
        assert view.orders_total == 1
        assert view.tickets_total == 1


class TestListHistoryOrderingAndPaging:
    def test_orders_sorted_desc_by_date(self, db_session: Session) -> None:
        # ADR-013: 注文日降順。
        me = make_user(db_session)
        product = make_product(db_session)
        base = datetime(2026, 1, 1, tzinfo=UTC)
        _add_order(db_session, me.id, "ORD-OLD", base, product.id)
        _add_order(db_session, me.id, "ORD-NEW", base + timedelta(days=5), product.id)
        db_session.commit()
        view = HistoryService(db_session).list_history(me.id)
        assert [o.order_number for o in view.orders] == ["ORD-NEW", "ORD-OLD"]

    def test_pagination_page_size_20(self, db_session: Session) -> None:
        # NFR-PERF-003 / ADR-013: 1ページ20件。
        me = make_user(db_session)
        product = make_product(db_session)
        base = datetime(2026, 1, 1, tzinfo=UTC)
        for i in range(25):
            _add_order(db_session, me.id, f"ORD-{i:02d}", base + timedelta(minutes=i), product.id)
        db_session.commit()
        view = HistoryService(db_session).list_history(me.id, page=1)
        assert view.orders_total == 25
        assert len(view.orders) == 20
        assert view.page_size == 20

    def test_second_page(self, db_session: Session) -> None:
        me = make_user(db_session)
        product = make_product(db_session)
        base = datetime(2026, 1, 1, tzinfo=UTC)
        for i in range(25):
            _add_order(db_session, me.id, f"ORD-{i:02d}", base + timedelta(minutes=i), product.id)
        db_session.commit()
        view = HistoryService(db_session).list_history(me.id, page=2)
        assert len(view.orders) == 5

    def test_snapshot_displayed_from_items(self, db_session: Session) -> None:
        # ADR-008: 履歴表示は明細スナップショットを用いる。
        me = make_user(db_session)
        product = make_product(db_session)
        _add_order(db_session, me.id, "ORD-SNAP", datetime.now(UTC), product.id)
        db_session.commit()
        view = HistoryService(db_session).list_history(me.id)
        assert view.orders[0].items[0].product_snapshot_name == "商品"
