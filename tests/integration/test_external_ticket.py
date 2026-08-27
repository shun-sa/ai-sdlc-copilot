"""External Integration Test Cases: 映画チケット購入（IT-037〜IT-043）。

IT-044（チケット更新失敗時のロールバック）は NOT_AUTOMATABLE のため plan には含めず
external_case_disposition に記録する（AI 側で rollback を自動検証）。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models.screening import Screening
from app.models.ticket import TicketPurchase
from tests.integration._helpers import (
    login,
    make_movie,
    make_screening,
    make_user,
    purchase_ticket,
)

UTC = timezone.utc


def _member(session_factory, email="ticket-member@example.com"):
    with session_factory() as s:
        uid = make_user(s, email=email).id
        s.commit()
        return uid


def _purchases(session_factory, user_id):
    with session_factory() as s:
        return list(s.scalars(select(TicketPurchase).where(TicketPurchase.user_id == user_id)))


# IT-037: チケット購入：1枚（FR-009 / AC-COM-004 / NFR-USAB-004）
def test_it_037_ticket_single(client, session_factory):
    uid = _member(session_factory)
    with session_factory() as s:
        movie = make_movie(s, title="チケット映画")
        sid = make_screening(s, movie_id=movie.id, seats_remaining=20).id
        s.commit()
    login(client, "ticket-member@example.com")

    res = purchase_ticket(client, screening_id=sid, ticket_type="GENERAL", quantity=1)
    assert res.status_code == 200
    with session_factory() as s:
        purchase = s.scalars(select(TicketPurchase).where(TicketPurchase.user_id == uid)).one()
        assert purchase.purchase_number.startswith("TKT-")
        assert s.get(Screening, sid).seats_remaining == 19  # 残席が1減る


# IT-038: チケット購入：複数枚（FR-009 / AC-COM-004）
def test_it_038_ticket_multiple(client, session_factory):
    uid = _member(session_factory)
    with session_factory() as s:
        movie = make_movie(s, title="複数枚映画")
        sid = make_screening(s, movie_id=movie.id, seats_remaining=20).id
        s.commit()
    login(client, "ticket-member@example.com")

    purchase_ticket(client, screening_id=sid, ticket_type="GENERAL", quantity=3)
    with session_factory() as s:
        purchase = s.scalars(select(TicketPurchase).where(TicketPurchase.user_id == uid)).one()
        assert purchase.items[0].quantity == 3
        assert s.get(Screening, sid).seats_remaining == 17  # 指定枚数分減算


# IT-039: 映画詳細からチケット購入（FR-009 / AC-COM-004）
def test_it_039_ticket_from_movie_detail(client, session_factory):
    uid = _member(session_factory)
    with session_factory() as s:
        movie = make_movie(s, title="導線映画")
        sid = make_screening(s, movie_id=movie.id, seats_remaining=10).id
        mid = movie.id
        s.commit()
    login(client, "ticket-member@example.com")

    detail = client.get(f"/movies/{mid}")
    assert f"/tickets/new?screening_id={sid}" in detail.text  # 詳細に購入導線
    form = client.get("/tickets/new", params={"screening_id": sid})
    assert form.status_code == 200
    res = purchase_ticket(client, screening_id=sid, ticket_type="GENERAL", quantity=1)
    assert res.status_code == 200
    # 購入履歴へ反映
    assert client.get("/history").status_code == 200
    assert len(_purchases(session_factory, uid)) == 1


# IT-040: チケット：販売期間外（FR-009 / ERR-004 / AC-COM-006）
def test_it_040_ticket_out_of_sales_period(client, session_factory):
    uid = _member(session_factory)
    now = datetime.now(UTC)
    with session_factory() as s:
        movie = make_movie(s, title="販売終了映画")
        sid = make_screening(
            s,
            movie_id=movie.id,
            starts_at=now + timedelta(days=5),
            sales_start_at=now - timedelta(days=10),
            sales_end_at=now - timedelta(days=1),  # 販売終了後
            seats_remaining=10,
        ).id
        s.commit()
    login(client, "ticket-member@example.com")

    res = purchase_ticket(client, screening_id=sid, quantity=1, follow_redirects=False)
    assert res.status_code == 409
    assert _purchases(session_factory, uid) == []


# IT-041: チケット：上映開始後（FR-009 / ERR-004）
def test_it_041_ticket_after_start(client, session_factory):
    uid = _member(session_factory)
    now = datetime.now(UTC)
    with session_factory() as s:
        movie = make_movie(s, title="開始済み映画")
        sid = make_screening(
            s,
            movie_id=movie.id,
            starts_at=now - timedelta(hours=1),  # 開始時刻を過ぎている
            sales_start_at=now - timedelta(days=5),
            sales_end_at=now + timedelta(days=1),
            seats_remaining=10,
        ).id
        s.commit()
    login(client, "ticket-member@example.com")

    res = purchase_ticket(client, screening_id=sid, quantity=1, follow_redirects=False)
    assert res.status_code == 409
    assert _purchases(session_factory, uid) == []


# IT-042: チケット：残席不足（FR-009 / ERR-003 / AC-COM-006）
def test_it_042_ticket_seat_shortage(client, session_factory):
    uid = _member(session_factory)
    with session_factory() as s:
        movie = make_movie(s, title="残席僅少映画")
        sid = make_screening(s, movie_id=movie.id, seats_remaining=2).id
        s.commit()
    login(client, "ticket-member@example.com")

    res = purchase_ticket(client, screening_id=sid, quantity=5, follow_redirects=False)
    assert res.status_code == 409
    assert _purchases(session_factory, uid) == []
    with session_factory() as s:
        assert s.get(Screening, sid).seats_remaining == 2  # 不整合が残らない


# IT-043: チケット購入登録と残席減算の原子性（FR-009 / NFR-AVL-002）
def test_it_043_ticket_atomicity(client, session_factory):
    uid = _member(session_factory)
    with session_factory() as s:
        movie = make_movie(s, title="原子性映画")
        sid = make_screening(s, movie_id=movie.id, seats_remaining=8).id
        s.commit()
    login(client, "ticket-member@example.com")

    purchase_ticket(client, screening_id=sid, ticket_type="GENERAL", quantity=2)
    with session_factory() as s:
        purchase = s.scalars(select(TicketPurchase).where(TicketPurchase.user_id == uid)).one()
        # 購入登録と残席減算が整合した一つの結果として完了
        assert purchase.total_amount == purchase.items[0].subtotal
        assert s.get(Screening, sid).seats_remaining == 6
