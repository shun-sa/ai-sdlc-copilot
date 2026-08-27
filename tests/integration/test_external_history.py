"""External Integration Test Cases: 購入履歴（IT-045〜IT-048）。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.constants import TicketType
from app.models.product import Product
from tests.integration._helpers import (
    login,
    make_movie,
    make_order,
    make_product,
    make_screening,
    make_ticket_purchase,
    make_user,
)

UTC = timezone.utc


# IT-045: 購入履歴：商品注文とチケット（FR-010 / AC-COM-005）
def test_it_045_history_shows_orders_and_tickets(client, session_factory):
    with session_factory() as s:
        user = make_user(s, email="it045@example.com")
        movie = make_movie(s, title="履歴映画")
        product = make_product(s, name="履歴商品")
        screening = make_screening(s, movie_id=movie.id)
        make_order(
            s,
            user_id=user.id,
            order_number="ORD-HIST045",
            items=[(product.id, "履歴商品", 1980, 1)],
        )
        make_ticket_purchase(
            s,
            user_id=user.id,
            purchase_number="TKT-HIST045",
            screening_id=screening.id,
            movie_title="履歴映画",
            starts_at=screening.starts_at,
        )
        s.commit()
    login(client, "it045@example.com")

    res = client.get("/history")
    assert res.status_code == 200
    assert "ORD-HIST045" in res.text  # 本人の商品注文
    assert "TKT-HIST045" in res.text  # 本人のチケット購入


# IT-046: 購入履歴：他会員データ参照禁止（FR-010 / C-AUTH-004 / NFR-SEC-003 / AC-COM-006）
def test_it_046_history_owner_only(client, session_factory):
    with session_factory() as s:
        user_a = make_user(s, email="it046-a@example.com")
        user_b = make_user(s, email="it046-b@example.com")
        product = make_product(s, name="B商品")
        make_order(
            s,
            user_id=user_b.id,
            order_number="ORD-USERB",
            items=[(product.id, "B商品", 1000, 1)],
        )
        s.commit()
    login(client, "it046-a@example.com")

    res = client.get("/history")
    assert res.status_code == 200
    assert "ORD-USERB" not in res.text  # 他会員データは表示されない
    assert "B商品" not in res.text


# IT-047: 購入履歴：降順（FR-010 / ADR-013）
def test_it_047_history_descending(client, session_factory):
    now = datetime.now(UTC)
    with session_factory() as s:
        user = make_user(s, email="it047@example.com")
        product = make_product(s, name="降順商品")
        make_order(
            s,
            user_id=user.id,
            order_number="ORD-OLDER",
            items=[(product.id, "降順商品", 1000, 1)],
            ordered_at=now - timedelta(days=5),
        )
        make_order(
            s,
            user_id=user.id,
            order_number="ORD-NEWER",
            items=[(product.id, "降順商品", 1000, 1)],
            ordered_at=now - timedelta(days=1),
        )
        s.commit()
    login(client, "it047@example.com")

    text = client.get("/history").text
    assert text.index("ORD-NEWER") < text.index("ORD-OLDER")  # 新しい順


# IT-048: 購入履歴：スナップショット（FR-010 / C-DATA-004 / ADR-008）
def test_it_048_history_snapshot(client, session_factory):
    with session_factory() as s:
        user = make_user(s, email="it048@example.com")
        product = make_product(s, name="履歴旧名", price=1000)
        make_order(
            s,
            user_id=user.id,
            order_number="ORD-SNAP048",
            items=[(product.id, "履歴旧名", 1000, 1)],
        )
        pid = product.id
        s.commit()

    # 注文後に元商品情報を変更
    with session_factory() as s:
        s.get(Product, pid).name = "履歴新名"
        s.commit()

    login(client, "it048@example.com")
    text = client.get("/history").text
    assert "履歴旧名" in text  # 購入時点の情報
    assert "履歴新名" not in text
