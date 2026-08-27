"""External Integration Test Cases: セキュリティ・性能（IT-049, 050, 051, 053, 054）。"""

from __future__ import annotations

import time

from sqlalchemy import select

from app.models.user import User
from tests.integration._helpers import (
    add_to_cart,
    cart_item_id_of,
    login,
    make_movie,
    make_product,
    make_screening,
    make_user,
    place_order,
    purchase_ticket,
    update_cart_item,
)


# IT-049: サーバー側入力検証（NFR-SEC-004 / ERR-001）
def test_it_049_server_side_validation(client, session_factory):
    # UI 制御を回避し、形式・長さが不正なリクエストを直接送信する
    res = client.post(
        "/register",
        data={
            "name": "あ" * 100,  # 最大長超過
            "email": "invalid-email-format",  # 形式不正
            "password": "short",  # 桁数不足
            "password_confirm": "short",
        },
    )
    assert res.status_code == 400  # サーバー側で拒否
    with session_factory() as s:
        assert list(s.scalars(select(User))) == []  # 不正データは永続化されない


# IT-050: SQLインジェクション耐性（NFR-SEC-005）
def test_it_050_sql_injection_resistance(client, session_factory):
    with session_factory() as s:
        make_movie(s, title="正規の映画A")
        make_movie(s, title="正規の映画B")
        s.commit()

    payload = "' OR '1'='1"
    res = client.get("/movies", params={"keyword": payload})
    assert res.status_code == 200
    # 文字列がSQL構文として解釈されず、リテラル一致0件となる（全件返却されない）
    assert "検索結果: 0件" in res.text


# IT-051: XSS耐性（NFR-SEC-005 / ADR-009）
def test_it_051_xss_resistance(client, session_factory):
    with session_factory() as s:
        pid = make_product(s, name="<script>alert('xss')</script>").id
        s.commit()

    res = client.get(f"/products/{pid}")
    assert res.status_code == 200
    assert "<script>alert('xss')</script>" not in res.text  # 生スクリプトは出力されない
    assert "&lt;script&gt;" in res.text  # エスケープされて表示


# IT-053: 一覧初期表示性能（NFR-PERF-001）
def test_it_053_list_display_performance(client, session_factory):
    with session_factory() as s:
        user = make_user(s, email="it053@example.com")
        for i in range(30):
            make_product(s, name=f"性能商品{i:02d}")
            make_movie(s, title=f"性能映画{i:02d}")
        s.commit()
    login(client, "it053@example.com")

    for path in ("/movies", "/products", "/history"):
        start = time.perf_counter()
        res = client.get(path)
        elapsed = time.perf_counter() - start
        assert res.status_code == 200
        assert elapsed < 3.0  # 通常時3秒以内


# IT-054: 更新系応答性能（NFR-PERF-002）
def test_it_054_update_response_performance(client, session_factory):
    with session_factory() as s:
        uid = make_user(s, email="it054@example.com").id
        pid = make_product(s, name="性能更新商品", stock=20).id
        movie = make_movie(s, title="性能チケット映画")
        sid = make_screening(s, movie_id=movie.id, seats_remaining=20).id
        s.commit()
    login(client, "it054@example.com")

    def _timed(fn) -> float:
        start = time.perf_counter()
        res = fn()
        assert res.status_code == 200
        return time.perf_counter() - start

    assert _timed(lambda: add_to_cart(client, pid, 2)) < 5.0
    with session_factory() as s:
        item_id = cart_item_id_of(s, uid, pid)
    assert _timed(lambda: update_cart_item(client, item_id, 3)) < 5.0
    assert _timed(lambda: place_order(client)) < 5.0
    assert _timed(
        lambda: purchase_ticket(client, screening_id=sid, ticket_type="GENERAL", quantity=1)
    ) < 5.0
