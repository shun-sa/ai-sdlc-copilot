"""AI INITIAL 結合試験ケース (IT-AI-001〜027)。

origin=AI_GENERATED / generation_stage=INITIAL。
期待結果は Requirements / Accepted ADR から導出しており、Production Code からの逆算はしない。
各テスト関数は reports/integration-test/ai-initial-cases.json の case_id に1:1で対応する。
"""

from __future__ import annotations

from urllib.parse import unquote

from sqlalchemy import func, select

import tests.integration.helpers as h
from app.models.cart import Cart, CartItem
from app.models.order import Order
from app.models.product import Product
from app.models.ticket import TicketPurchase
from app.models.user import User


# ============================================================
# 認証・会員 (FR-001 / FR-002)
# ============================================================


def test_IT_AI_001_register_success_password_hashed(client, db):
    resp = h.register(client, name="テスト太郎", email="new@example.com")
    assert resp.status_code == 200  # /register/complete まで追従

    user = db.execute(
        select(User).where(User.email == "new@example.com")
    ).scalar_one()
    assert user.password_hash != "Passw0rd"
    assert user.password_hash.startswith("$2")  # bcrypt (ADR-006)


def test_IT_AI_002_register_duplicate_email_rejected(client, db, factory):
    factory.make_user(db, name="既存", email="existing@example.com")
    resp = h.register(client, name="重複", email="existing@example.com")
    assert resp.status_code == 400
    count = db.execute(
        select(func.count()).select_from(User).where(User.email == "existing@example.com")
    ).scalar_one()
    assert count == 1  # 重複作成されない


def test_IT_AI_003_register_password_mismatch_rejected(client, db):
    resp = h.register(client, name="不一致", email="mismatch@example.com", confirm="Different1")
    assert resp.status_code == 400
    count = db.execute(
        select(func.count()).select_from(User).where(User.email == "mismatch@example.com")
    ).scalar_one()
    assert count == 0


def test_IT_AI_004_login_success_session(client, db, factory):
    factory.make_user(db, name="会員", email="member@example.com")
    resp = h.login(client, "member@example.com")
    assert resp.status_code == 200
    # ログイン後は要認証ページへアクセスできる (セッション確立)
    cart = client.get("/cart")
    assert cart.status_code == 200


def test_IT_AI_005_login_generic_failure_message(client, db, factory):
    factory.make_user(db, name="会員", email="member@example.com")
    r_unknown = h.login(client, "unknown@example.com", "Passw0rd")
    r_wrong = h.login(client, "member@example.com", "WrongPass9")
    assert r_unknown.status_code == 400
    assert r_wrong.status_code == 400
    msg = "メールアドレスまたはパスワードが正しくありません。"
    assert msg in r_unknown.text
    assert msg in r_wrong.text  # 存在可否を推測させない同一文言


def test_IT_AI_006_register_then_login(client, db):
    h.register(client, name="連続", email="flow@example.com")
    # 明示的に再ログインして連続成立を確認
    resp = h.login(client, "flow@example.com")
    assert resp.status_code == 200
    assert client.get("/history").status_code == 200


# ============================================================
# 認証・認可境界 (C-AUTH-003 / NFR-SEC-003 / ADR-005)
# ============================================================


def test_IT_AI_007_unauthenticated_redirect(client, db, factory):
    movie = factory.make_movie(db, title="上映作品")
    screening = factory.make_screening(db, movie_id=movie.id, starts_at=h.future(factory))
    for url in ["/cart", "/orders/new", "/history", f"/tickets/screenings/{screening.id}"]:
        resp = client.get(url, follow_redirects=False)
        assert resp.status_code == 303, url
        assert resp.headers["location"] == "/login", url


def test_IT_AI_008_other_user_data_forbidden(client, db, factory):
    user_a = factory.make_user(db, name="A", email="a@example.com")
    user_b = factory.make_user(db, name="B", email="b@example.com")
    product = factory.make_product(db, name="商品", stock=10)
    movie = factory.make_movie(db, title="映画")
    screening = factory.make_screening(db, movie_id=movie.id, starts_at=h.future(factory))
    order_b = h.make_order(db, user_b, items=[(product, 1)])
    purchase_b = h.make_ticket_purchase(db, user_b, screening, movie)

    h.login(client, "a@example.com")
    assert client.get(f"/history/orders/{order_b.id}", follow_redirects=False).status_code == 403
    assert client.get(f"/tickets/{purchase_b.id}/complete", follow_redirects=False).status_code == 404


# ============================================================
# カタログ (FR-005 / FR-004)
# ============================================================


def test_IT_AI_009_product_search_visibility(client, db, factory):
    visible = factory.make_product(db, name="公開在庫商品", stock=5)
    factory.make_product(db, name="非公開商品", stock=5, publish_status="draft")
    out_of_stock = factory.make_product(db, name="在庫切れ商品", stock=0)
    out_of_sales = factory.make_product(
        db, name="販売期間外商品", stock=5, sales_end_at=h.past(factory)
    )

    listing = client.get("/products").text
    assert "公開在庫商品" in listing
    assert "非公開商品" not in listing  # C-DATA-001

    in_stock = client.get("/products?in_stock_only=true").text
    assert "在庫切れ商品" not in in_stock  # C-DATA-003

    assert "在庫なし" in client.get(f"/products/{out_of_stock.id}").text
    assert "現在購入できません" in client.get(f"/products/{out_of_sales.id}").text  # C-DATA-002
    assert "公開在庫商品" in visible.name


# ============================================================
# カート (FR-006 / FR-007)
# ============================================================


def test_IT_AI_010_cart_add_no_stock_decrement(client, db, factory):
    factory.make_user(db, name="会員", email="cart@example.com")
    product = factory.make_product(db, name="カート商品", stock=10)
    h.login(client, "cart@example.com")

    assert h.add_to_cart(client, product.id, 2).status_code == 303
    assert h.add_to_cart(client, product.id, 2).status_code == 303

    item = db.execute(select(CartItem).where(CartItem.product_id == product.id)).scalar_one()
    assert item.quantity == 4  # 同一商品は数量加算
    assert db.get(Product, product.id).stock == 10  # 投入時点で在庫は減算しない


def test_IT_AI_011_cart_add_over_stock_rejected(client, db, factory):
    factory.make_user(db, name="会員", email="over@example.com")
    product = factory.make_product(db, name="在庫僅少", stock=3)
    h.login(client, "over@example.com")

    resp = h.add_to_cart(client, product.id, 5)
    assert resp.status_code == 303
    location = unquote(resp.headers["location"])
    assert f"/products/{product.id}" in location
    assert "在庫" in location  # ERR-003
    count = db.execute(select(func.count()).select_from(CartItem)).scalar_one()
    assert count == 0


def test_IT_AI_012_cart_update_recalculate(client, db, factory):
    factory.make_user(db, name="会員", email="upd@example.com")
    p1 = factory.make_product(db, name="商品1", price=1000, stock=10)
    p2 = factory.make_product(db, name="商品2", price=2000, stock=10)
    h.login(client, "upd@example.com")
    h.add_to_cart(client, p1.id, 1)
    h.add_to_cart(client, p2.id, 1)

    cart = db.execute(select(Cart)).scalar_one()
    item1 = db.execute(select(CartItem).where(CartItem.product_id == p1.id)).scalar_one()
    item2 = db.execute(select(CartItem).where(CartItem.product_id == p2.id)).scalar_one()

    assert h.update_cart_item(client, item1.id, 3).status_code == 303
    assert h.update_cart_item(client, item2.id, 0).status_code == 303  # 0は削除

    db.expire_all()
    remaining = db.execute(select(CartItem).where(CartItem.cart_id == cart.id)).scalars().all()
    assert len(remaining) == 1
    assert remaining[0].quantity == 3
    # 合計再計算: 1000*3 = 3000
    assert "3,000円" in client.get("/cart").text


# ============================================================
# 注文 (FR-008 / ADR-007 / ADR-008 / ADR-009)
# ============================================================


def test_IT_AI_013_order_confirm_decrement_number_clear(client, db, factory):
    factory.make_user(db, name="会員", email="order@example.com")
    product = factory.make_product(db, name="注文商品", price=1500, stock=10)
    h.login(client, "order@example.com")
    h.add_to_cart(client, product.id, 2)

    resp = h.place_order(client)
    assert resp.status_code == 303
    assert "/orders/" in resp.headers["location"]

    db.expire_all()
    order = db.execute(select(Order)).scalar_one()
    assert order.order_number.startswith("ORD-")
    assert order.total_amount == 3000
    assert order.items[0].product_snapshot_name == "注文商品"  # ADR-008 スナップショット
    assert db.get(Product, product.id).stock == 8  # 確定時に減算
    cart_items = db.execute(select(func.count()).select_from(CartItem)).scalar_one()
    assert cart_items == 0  # カートクリア

    complete = client.get(resp.headers["location"])
    assert order.order_number in complete.text


def test_IT_AI_014_order_insufficient_stock_rollback(client, db, factory):
    factory.make_user(db, name="会員", email="oos@example.com")
    product = factory.make_product(db, name="在庫変動商品", price=1000, stock=5)
    h.login(client, "oos@example.com")
    h.add_to_cart(client, product.id, 5)

    # 注文直前に在庫が減少 (最新在庫確認で失敗させる)
    p = db.get(Product, product.id)
    p.stock = 2
    db.commit()

    resp = h.place_order(client)
    assert resp.status_code == 400  # 注文不成立
    assert db.execute(select(func.count()).select_from(Order)).scalar_one() == 0  # ロールバック
    db.expire_all()
    assert db.get(Product, product.id).stock == 2  # 在庫は不正減算されない
    assert db.execute(select(func.count()).select_from(CartItem)).scalar_one() == 1  # カート保持


def test_IT_AI_015_product_purchase_full_flow(client, db, factory):
    factory.make_user(db, name="会員", email="full@example.com")
    product = factory.make_product(db, name="通し商品", price=1200, stock=10)
    h.login(client, "full@example.com")

    assert "通し商品" in client.get("/products?keyword=通し").text
    h.add_to_cart(client, product.id, 1)
    item = db.execute(select(CartItem)).scalar_one()
    h.update_cart_item(client, item.id, 2)
    resp = h.place_order(client)
    assert resp.status_code == 303

    db.expire_all()
    order = db.execute(select(Order)).scalar_one()
    assert db.get(Product, product.id).stock == 8
    history = client.get("/history").text
    assert order.order_number in history  # 履歴反映


# ============================================================
# 映画詳細 (FR-004)
# ============================================================


def test_IT_AI_016_movie_detail_screenings(client, db, factory):
    movie = factory.make_movie(db, title="公開映画")
    factory.make_product(db, name="関連グッズ", stock=5, movie_id=movie.id)
    factory.make_screening(db, movie_id=movie.id, starts_at=h.future(factory))
    hidden = factory.make_movie(db, title="非公開映画", status="draft")

    detail = client.get(f"/movies/{movie.id}")
    assert detail.status_code == 200
    assert "公開映画" in detail.text
    assert "関連グッズ" in detail.text
    assert "上映スケジュール" in detail.text
    assert client.get(f"/movies/{hidden.id}").status_code == 404  # C-DATA-001


# ============================================================
# チケット (FR-009 / ADR-007 / ADR-008)
# ============================================================


def test_IT_AI_017_ticket_purchase_decrement_number(client, db, factory):
    factory.make_user(db, name="会員", email="tk@example.com")
    movie = factory.make_movie(db, title="上映作品")
    screening = factory.make_screening(
        db, movie_id=movie.id, starts_at=h.future(factory), seats_remaining=50
    )
    h.login(client, "tk@example.com")

    resp = h.purchase_ticket(client, screening.id, ticket_type="general", quantity=2)
    assert resp.status_code == 303
    assert "/tickets/" in resp.headers["location"]

    db.expire_all()
    purchase = db.execute(select(TicketPurchase)).scalar_one()
    assert purchase.purchase_number.startswith("TKT-")
    from app.models.screening import Screening

    assert db.get(Screening, screening.id).seats_remaining == 48  # 残席減算


def test_IT_AI_018_ticket_insufficient_seats_rollback(client, db, factory):
    factory.make_user(db, name="会員", email="seat@example.com")
    movie = factory.make_movie(db, title="残席僅少作品")
    screening = factory.make_screening(
        db, movie_id=movie.id, starts_at=h.future(factory), seats_remaining=1
    )
    h.login(client, "seat@example.com")

    resp = h.purchase_ticket(client, screening.id, quantity=3)
    assert resp.status_code == 303
    assert "error=" in resp.headers["location"]
    assert db.execute(select(func.count()).select_from(TicketPurchase)).scalar_one() == 0
    from app.models.screening import Screening

    db.expire_all()
    assert db.get(Screening, screening.id).seats_remaining == 1  # 残席は不正減算されない


def test_IT_AI_019_ticket_out_of_sales_period(client, db, factory):
    factory.make_user(db, name="会員", email="oosales@example.com")
    movie = factory.make_movie(db, title="上映開始済作品")
    # 上映開始後 (starts_at が過去) は購入不可 (C-DATA-002 / FR-009)
    screening = factory.make_screening(
        db, movie_id=movie.id, starts_at=h.past(factory), seats_remaining=10
    )
    h.login(client, "oosales@example.com")

    resp = h.purchase_ticket(client, screening.id, csrf_url="/orders/new")
    assert resp.status_code == 303
    assert "error=" in resp.headers["location"]
    assert db.execute(select(func.count()).select_from(TicketPurchase)).scalar_one() == 0


def test_IT_AI_020_ticket_purchase_full_flow(client, db, factory):
    factory.make_user(db, name="会員", email="tkfull@example.com")
    movie = factory.make_movie(db, title="通し上映作品")
    screening = factory.make_screening(
        db, movie_id=movie.id, starts_at=h.future(factory), seats_remaining=20
    )
    h.login(client, "tkfull@example.com")

    assert "通し上映作品" in client.get(f"/movies/{movie.id}").text
    resp = h.purchase_ticket(client, screening.id, quantity=2)
    assert resp.status_code == 303

    db.expire_all()
    purchase = db.execute(select(TicketPurchase)).scalar_one()
    from app.models.screening import Screening

    assert db.get(Screening, screening.id).seats_remaining == 18
    assert purchase.purchase_number in client.get("/history").text  # 履歴反映


# ============================================================
# 購入履歴 (FR-010 / ADR-005 / ADR-008)
# ============================================================


def test_IT_AI_021_history_reflects_order_and_ticket(client, db, factory):
    user = factory.make_user(db, name="会員", email="hist@example.com")
    product = factory.make_product(db, name="履歴商品", stock=5)
    movie = factory.make_movie(db, title="履歴映画")
    screening = factory.make_screening(db, movie_id=movie.id, starts_at=h.future(factory))
    order = h.make_order(db, user, items=[(product, 1)])
    purchase = h.make_ticket_purchase(db, user, screening, movie)

    h.login(client, "hist@example.com")
    history = client.get("/history").text
    assert order.order_number in history
    assert purchase.purchase_number in history


def test_IT_AI_022_history_owner_only(client, db, factory):
    user_a = factory.make_user(db, name="A", email="ha@example.com")
    user_b = factory.make_user(db, name="B", email="hb@example.com")
    product = factory.make_product(db, name="商品", stock=5)
    order_a = h.make_order(db, user_a, items=[(product, 1)])
    order_b = h.make_order(db, user_b, items=[(product, 1)])

    h.login(client, "ha@example.com")
    history = client.get("/history").text
    assert order_a.order_number in history
    assert order_b.order_number not in history  # 本人分のみ
    assert client.get(f"/history/orders/{order_b.id}", follow_redirects=False).status_code == 403


# ============================================================
# 共通エラー分類 (AC-COM-006 / ERR-001〜004)
# ============================================================


def test_IT_AI_023_error_class_input_invalid(client, db):
    resp = h.register(client, name="", email="not-an-email", password="short")
    assert resp.status_code == 400  # 項目単位エラー (ERR-001)


def test_IT_AI_024_error_class_stock_shortage(client, db, factory):
    factory.make_user(db, name="会員", email="ss@example.com")
    product = factory.make_product(db, name="在庫僅少", stock=1)
    h.login(client, "ss@example.com")
    resp = h.add_to_cart(client, product.id, 3)
    assert resp.status_code == 303
    assert "在庫" in unquote(resp.headers["location"])  # ERR-003


def test_IT_AI_025_error_class_permission_denied(client, db, factory):
    user_b = factory.make_user(db, name="B", email="pb@example.com")
    factory.make_user(db, name="A", email="pa@example.com")
    product = factory.make_product(db, name="商品", stock=5)
    order_b = h.make_order(db, user_b, items=[(product, 1)])
    h.login(client, "pa@example.com")
    resp = client.get(f"/history/orders/{order_b.id}", follow_redirects=False)
    assert resp.status_code == 403  # ERR-004 / NFR-SEC-003


def test_IT_AI_026_error_class_auth_failure(client, db, factory):
    factory.make_user(db, name="会員", email="af@example.com")
    resp = h.login(client, "af@example.com", "WrongPass9")
    assert resp.status_code == 400
    assert "メールアドレスまたはパスワードが正しくありません。" in resp.text  # ERR-002


def test_IT_AI_027_error_class_out_of_sales_period(client, db, factory):
    factory.make_user(db, name="会員", email="osp@example.com")
    product = factory.make_product(
        db, name="販売前商品", stock=5, sales_start_at=h.future(factory)
    )
    h.login(client, "osp@example.com")
    # 販売期間外商品はカート追加できない (ERR-004 / C-DATA-002)
    resp = h.add_to_cart(client, product.id, 1, from_url="/orders/new")
    assert resp.status_code == 303
    assert "error=" in resp.headers["location"]
    assert db.execute(select(func.count()).select_from(CartItem)).scalar_one() == 0
