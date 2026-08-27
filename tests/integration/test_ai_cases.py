"""AI Generated Integration Test Cases (origin=AI_GENERATED, stage=INITIAL)。

Requirements / Accepted ADR から期待結果を導出した AI 初期生成ケース。
External 確認前に生成・固定した Case Set に対応する自動テスト。
COMMON 観点に加え、External(自動化)側に存在しない AI_ONLY 観点
（ログアウト、他会員カート保護、空カート注文拒否、ロールバック原子性）を含む。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models.order import Order
from app.models.product import Product
from app.models.screening import Screening
from app.models.ticket import TicketPurchase
from app.models.user import User
from app.security import verify_password
from tests.integration._helpers import (
    add_to_cart,
    cart_item_id_of,
    login,
    logout,
    make_movie,
    make_product,
    make_screening,
    make_user,
    place_order,
    purchase_ticket,
    register,
    update_cart_item,
)

UTC = timezone.utc


# AI-01: 会員登録フロー（成功/必須不足/形式不一致/重複/ハッシュ保存）
def test_ai_01_registration_flow(client, session_factory):
    # 成功
    assert register(client, email="ai01@example.com", password="Passw0rd").status_code == 200
    with session_factory() as s:
        user = s.scalars(select(User).where(User.email == "ai01@example.com")).one()
        assert user.password_hash.startswith("$2")  # NFR-SEC-001 ハッシュ保存
        assert verify_password("Passw0rd", user.password_hash)

    # 必須不足
    assert client.post("/register", data={"name": "", "email": "", "password": "", "password_confirm": ""}).status_code == 400
    # 形式不正 + 確認不一致
    assert register(client, email="bad", password="Passw0rd", password_confirm="Other123").status_code == 400
    # 重複メール
    assert register(client, email="ai01@example.com", password="Passw0rd").status_code == 400
    with session_factory() as s:
        assert len(list(s.scalars(select(User).where(User.email == "ai01@example.com")))) == 1


# AI-02: ログイン（成功/認証失敗の汎用文言）
def test_ai_02_login_success_and_failure(client, session_factory):
    with session_factory() as s:
        make_user(s, email="ai02@example.com", password="password123")
        s.commit()

    assert login(client, "ai02@example.com").status_code == 200
    fail = login(client, "ai02@example.com", "bad", follow_redirects=False)
    assert fail.status_code == 401
    assert "メールアドレスまたはパスワードが正しくありません。" in fail.text


# AI-03: ログアウトでセッションが無効化される（AI_ONLY / FR-002 / ADR-005）
def test_ai_03_logout_invalidates_session(client, session_factory):
    with session_factory() as s:
        make_user(s, email="ai03@example.com")
        s.commit()
    login(client, "ai03@example.com")
    assert client.get("/history").status_code == 200  # 認証済み

    logout(client)
    after = client.get("/history", follow_redirects=False)
    assert after.status_code == 303
    assert after.headers["location"].startswith("/login")  # セッション無効化


# AI-04: 未認証ガードがログインへ誘導する（C-AUTH-003 / NFR-SEC-002）
def test_ai_04_auth_guard_redirect(client):
    res = client.get("/cart", follow_redirects=False)
    assert res.status_code == 303
    assert "/login" in res.headers["location"]


# AI-05: 映画検索（キーワード一致 / 非公開除外）
def test_ai_05_movie_search(client, session_factory):
    from app.constants import MovieStatus

    with session_factory() as s:
        make_movie(s, title="公開ヒーロー", genre="SF", status=MovieStatus.PUBLISHED)
        make_movie(s, title="非公開ヒーロー", genre="SF", status=MovieStatus.UNPUBLISHED)
        s.commit()

    res = client.get("/movies", params={"keyword": "ヒーロー"})
    assert "公開ヒーロー" in res.text
    assert "非公開ヒーロー" not in res.text


# AI-06: 映画詳細表示（作品情報/上映回/関連商品）
def test_ai_06_movie_detail(client, session_factory):
    with session_factory() as s:
        movie = make_movie(s, title="AI詳細映画", genre="ドラマ")
        make_product(s, name="AI関連商品", movie_id=movie.id)
        make_screening(s, movie_id=movie.id)
        mid = movie.id
        s.commit()

    res = client.get(f"/movies/{mid}")
    assert res.status_code == 200
    assert "AI詳細映画" in res.text
    assert "AI関連商品" in res.text


# AI-07: 商品閲覧制御（非公開/販売期間外/在庫0）
def test_ai_07_product_visibility_controls(client, session_factory):
    from app.constants import PublishStatus

    now = datetime.now(UTC)
    with session_factory() as s:
        published = make_product(s, name="公開販売中商品", stock=5).id
        make_product(s, name="非公開商品AI", publish_status=PublishStatus.UNPUBLISHED)
        out_of_period = make_product(
            s, name="販売期間前商品AI", sales_start_at=now + timedelta(days=3)
        ).id
        no_stock = make_product(s, name="在庫切れ商品AI", stock=0).id
        s.commit()

    listing = client.get("/products")
    assert "公開販売中商品" in listing.text
    assert "非公開商品AI" not in listing.text  # C-DATA-001

    assert "販売期間外" in client.get(f"/products/{out_of_period}").text  # C-DATA-002
    assert "在庫なし" in client.get(f"/products/{no_stock}").text  # C-DATA-003


# AI-08: カート追加（成功/加算/在庫非減算/在庫超過）
def test_ai_08_cart_add(client, session_factory):
    with session_factory() as s:
        uid = make_user(s, email="ai08@example.com").id
        pid = make_product(s, name="AIカート商品", stock=5).id
        s.commit()
    login(client, "ai08@example.com")

    assert add_to_cart(client, pid, 2).status_code == 200
    add_to_cart(client, pid, 1)  # 加算 -> 3
    with session_factory() as s:
        assert cart_item_id_of(s, uid, pid) is not None
        assert s.get(Product, pid).stock == 5  # 在庫非減算
    assert add_to_cart(client, pid, 10, follow_redirects=False).status_code == 409  # 在庫超過


# AI-09: カート更新（数量変更/0削除/在庫超過）
def test_ai_09_cart_update(client, session_factory):
    with session_factory() as s:
        uid = make_user(s, email="ai09@example.com").id
        pid = make_product(s, name="AI更新商品", stock=5).id
        s.commit()
    login(client, "ai09@example.com")
    add_to_cart(client, pid, 1)
    with session_factory() as s:
        item_id = cart_item_id_of(s, uid, pid)

    assert update_cart_item(client, item_id, 3).status_code == 200
    assert update_cart_item(client, item_id + 0, 99, follow_redirects=False).status_code == 409
    update_cart_item(client, item_id, 0)  # 削除
    with session_factory() as s:
        assert cart_item_id_of(s, uid, pid) is None


# AI-10: 他会員のカート明細を変更できない（AI_ONLY / C-AUTH-004 / NFR-SEC-003）
def test_ai_10_cart_owner_only(client, raw_client, session_factory):
    with session_factory() as s:
        make_user(s, email="ai10-a@example.com")
        make_user(s, email="ai10-b@example.com")
        uid_a = s.scalars(select(User).where(User.email == "ai10-a@example.com")).one().id
        pid = make_product(s, name="A所有商品", stock=5).id
        s.commit()

    login(client, "ai10-a@example.com")
    add_to_cart(client, pid, 1)
    with session_factory() as s:
        item_id = cart_item_id_of(s, uid_a, pid)

    # B が A のカート明細を変更しようとする
    login(raw_client, "ai10-b@example.com")
    res = update_cart_item(raw_client, item_id, 5, follow_redirects=False)
    assert res.status_code == 403  # 権限不足
    with session_factory() as s:
        from app.models.cart import CartItem

        assert s.get(CartItem, item_id).quantity == 1  # A の明細は不変


# AI-11: 商品注文（単一/複数/スナップショット/カートクリア）
def test_ai_11_order_success(client, session_factory):
    with session_factory() as s:
        uid = make_user(s, email="ai11@example.com").id
        pid1 = make_product(s, name="注文商品甲", price=1000, stock=5).id
        pid2 = make_product(s, name="注文商品乙", price=1500, stock=5).id
        s.commit()
    login(client, "ai11@example.com")
    add_to_cart(client, pid1, 1)
    add_to_cart(client, pid2, 2)

    assert place_order(client).status_code == 200
    with session_factory() as s:
        order = s.scalars(select(Order).where(Order.user_id == uid)).one()
        assert order.total_amount == 1000 + 1500 * 2
        assert {i.product_snapshot_name for i in order.items} == {"注文商品甲", "注文商品乙"}
        from app.repositories.cart_repository import CartRepository

        cart = CartRepository(s).get_cart(uid)
        assert cart is None or not cart.items  # カートクリア


# AI-12: 注文エラー（入力不備/在庫不足/空カート拒否 AI_ONLY）
def test_ai_12_order_errors(client, session_factory):
    with session_factory() as s:
        uid = make_user(s, email="ai12@example.com").id
        pid = make_product(s, name="AIエラー商品", stock=5).id
        s.commit()
    login(client, "ai12@example.com")

    # 空カートでの注文は拒否される（AI_ONLY）
    empty = place_order(client, follow_redirects=False)
    assert empty.status_code == 400

    add_to_cart(client, pid, 2)
    # 入力不備
    assert place_order(client, postal_code="xxx", phone="??", follow_redirects=False).status_code == 400
    # 在庫不足
    with session_factory() as s:
        s.get(Product, pid).stock = 1
        s.commit()
    assert place_order(client, follow_redirects=False).status_code == 409
    with session_factory() as s:
        assert list(s.scalars(select(Order).where(Order.user_id == uid))) == []


# AI-13: 注文の原子性とロールバック（AI_ONLY: 更新失敗時ロールバック / NFR-AVL-003 / ERR-005）
def test_ai_13_order_atomicity_and_rollback(raw_client, session_factory, monkeypatch):
    with session_factory() as s:
        uid = make_user(s, email="ai13@example.com").id
        pid = make_product(s, name="ロールバック商品", price=1000, stock=5).id
        s.commit()
    login(raw_client, "ai13@example.com")
    add_to_cart(raw_client, pid, 2)

    # 決済処理途中で失敗を注入し、ロールバックを検証
    def _boom(self, payment_method, amount):
        raise RuntimeError("payment failure injected")

    monkeypatch.setattr("app.payment.MockPayment.charge", _boom)
    res = place_order(raw_client, follow_redirects=False)
    assert res.status_code >= 500  # 更新失敗

    with session_factory() as s:
        # 不完全な Order は残らず、在庫も減算されない（片側更新なし）
        assert list(s.scalars(select(Order).where(Order.user_id == uid))) == []
        assert s.get(Product, pid).stock == 5


# AI-14: チケット購入（単一/複数）
def test_ai_14_ticket_success(client, session_factory):
    with session_factory() as s:
        uid = make_user(s, email="ai14@example.com").id
        movie = make_movie(s, title="AIチケット映画")
        sid = make_screening(s, movie_id=movie.id, seats_remaining=10).id
        s.commit()
    login(client, "ai14@example.com")

    assert purchase_ticket(client, screening_id=sid, ticket_type="GENERAL", quantity=2).status_code == 200
    with session_factory() as s:
        purchase = s.scalars(select(TicketPurchase).where(TicketPurchase.user_id == uid)).one()
        assert purchase.items[0].quantity == 2
        assert s.get(Screening, sid).seats_remaining == 8


# AI-15: チケットエラー（販売期間外/上映開始後/残席不足）
def test_ai_15_ticket_errors(client, session_factory):
    now = datetime.now(UTC)
    with session_factory() as s:
        make_user(s, email="ai15@example.com")
        movie = make_movie(s, title="AIチケットエラー映画")
        out_of_period = make_screening(
            s, movie_id=movie.id, sales_end_at=now - timedelta(days=1), seats_remaining=10
        ).id
        after_start = make_screening(
            s,
            movie_id=movie.id,
            starts_at=now - timedelta(hours=1),
            sales_start_at=now - timedelta(days=5),
            sales_end_at=now + timedelta(days=1),
            seats_remaining=10,
        ).id
        few_seats = make_screening(s, movie_id=movie.id, seats_remaining=1).id
        s.commit()
    login(client, "ai15@example.com")

    assert purchase_ticket(client, screening_id=out_of_period, follow_redirects=False).status_code == 409
    assert purchase_ticket(client, screening_id=after_start, follow_redirects=False).status_code == 409
    assert purchase_ticket(client, screening_id=few_seats, quantity=3, follow_redirects=False).status_code == 409


# AI-16: チケットの原子性とロールバック（AI_ONLY: 更新失敗時ロールバック / NFR-AVL-004 / ERR-005）
def test_ai_16_ticket_atomicity_and_rollback(client, raw_client, session_factory, monkeypatch):
    with session_factory() as s:
        uid = make_user(s, email="ai16@example.com").id
        movie = make_movie(s, title="AIロールバック映画")
        sid = make_screening(s, movie_id=movie.id, seats_remaining=5).id
        s.commit()

    # 正常時の原子性
    login(client, "ai16@example.com")
    assert purchase_ticket(client, screening_id=sid, ticket_type="GENERAL", quantity=1).status_code == 200
    with session_factory() as s:
        assert s.get(Screening, sid).seats_remaining == 4

    # 更新失敗時のロールバック
    def _boom(self, payment_method, amount):
        raise RuntimeError("payment failure injected")

    monkeypatch.setattr("app.payment.MockPayment.charge", _boom)
    login(raw_client, "ai16@example.com")
    res = purchase_ticket(raw_client, screening_id=sid, quantity=1, follow_redirects=False)
    assert res.status_code >= 500
    with session_factory() as s:
        assert s.get(Screening, sid).seats_remaining == 4  # 片側更新なし
        assert len(list(s.scalars(select(TicketPurchase).where(TicketPurchase.user_id == uid)))) == 1


# AI-17: 購入履歴（本人分表示/他会員不可視/スナップショット）
def test_ai_17_history(client, session_factory):
    from tests.integration._helpers import make_order

    with session_factory() as s:
        user_a = make_user(s, email="ai17-a@example.com")
        user_b = make_user(s, email="ai17-b@example.com")
        product = make_product(s, name="AI履歴旧名", price=1000)
        make_order(s, user_id=user_a.id, order_number="ORD-AI17A", items=[(product.id, "AI履歴旧名", 1000, 1)])
        make_order(s, user_id=user_b.id, order_number="ORD-AI17B", items=[(product.id, "B専用", 1000, 1)])
        pid = product.id
        s.commit()
    with session_factory() as s:
        s.get(Product, pid).name = "AI履歴新名"
        s.commit()

    login(client, "ai17-a@example.com")
    text = client.get("/history").text
    assert "ORD-AI17A" in text  # 本人分
    assert "ORD-AI17B" not in text  # 他会員不可視
    assert "AI履歴旧名" in text and "AI履歴新名" not in text  # スナップショット


# AI-18: セキュリティ（サーバー検証/SQLi/XSS）
def test_ai_18_security(client, session_factory):
    # サーバー側検証
    assert client.post(
        "/register",
        data={"name": "x" * 100, "email": "bad", "password": "no", "password_confirm": "no"},
    ).status_code == 400

    with session_factory() as s:
        make_movie(s, title="セキュリティ映画")
        pid = make_product(s, name="<b>XSS</b>商品").id
        s.commit()

    # SQLi はリテラル扱い（0件）
    assert "検索結果: 0件" in client.get("/movies", params={"keyword": "'; DROP TABLE movies;--"}).text
    # XSS はエスケープ
    detail = client.get(f"/products/{pid}")
    assert "<b>XSS</b>商品" not in detail.text
    assert "&lt;b&gt;XSS&lt;/b&gt;商品" in detail.text
