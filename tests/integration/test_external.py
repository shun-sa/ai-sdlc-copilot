"""External 結合試験ケース (IT-001〜075 のうち AUTOMATABLE な71件)。

origin=EXTERNAL。外部持込ケースの意味・Input・Steps・Expected Result は変更しない。
各テストは reports/integration-test/external-test-cases.normalized.json の case_id に1:1で対応する。
自動化用に httpx TestClient / 使い捨てDB でフロー変換しているが、検証観点は元ケースを維持する。

NOT_AUTOMATABLE (IT-038 / IT-047 / IT-067 / IT-068) は
「トランザクション途中の障害注入」を要し、外部ケースが execution_type=NOT_AUTOMATABLE と
宣言しているため、本ファイルでは自動化しない (AUTOMATION_BLOCKED として evidence に記録)。
"""

from __future__ import annotations

import re
import time
from urllib.parse import unquote

from sqlalchemy import func, select

import tests.integration.helpers as h
from app.models.cart import CartItem
from app.models.order import Order
from app.models.product import Product
from app.models.screening import Screening
from app.models.ticket import TicketPurchase
from app.models.user import User

_DT_RE = re.compile(r"\d{4}/\d{2}/\d{2} \d{2}:\d{2}")


def _elapsed(func_):
    start = time.perf_counter()
    result = func_()
    return result, time.perf_counter() - start


# ============================================================
# SC-001 会員登録〜ログイン
# ============================================================


def test_IT_001_register_success(client, db):
    resp = h.register(client, name="会員太郎", email="it001@example.com")
    assert resp.status_code == 200
    user = db.execute(select(User).where(User.email == "it001@example.com")).scalar_one()
    assert user.password_hash != "Passw0rd"
    assert user.password_hash.startswith("$2")


def test_IT_002_required_and_format_check(client, db):
    # 確認用不一致
    r1 = h.register(client, name="X", email="it002@example.com", confirm="Different9")
    assert r1.status_code == 400
    # メール形式不正
    r2 = h.register(client, name="X", email="bad-email")
    assert r2.status_code == 400
    assert db.execute(select(func.count()).select_from(User)).scalar_one() == 0


def test_IT_003_duplicate_email(client, db, factory):
    factory.make_user(db, name="既存", email="it003@example.com")
    resp = h.register(client, name="重複", email="it003@example.com")
    assert resp.status_code == 400
    assert db.execute(
        select(func.count()).select_from(User).where(User.email == "it003@example.com")
    ).scalar_one() == 1


def test_IT_004_login_success(client, db, factory):
    factory.make_user(db, name="会員", email="it004@example.com")
    resp = h.login(client, "it004@example.com")
    assert resp.status_code == 200
    assert client.get("/cart").status_code == 200


def test_IT_005_login_auth_failure_generic(client, db, factory):
    factory.make_user(db, name="会員", email="it005@example.com")
    r_wrong = h.login(client, "it005@example.com", "WrongPass9")
    r_unknown = h.login(client, "nobody@example.com", "Passw0rd")
    msg = "メールアドレスまたはパスワードが正しくありません。"
    assert r_wrong.status_code == 400 and msg in r_wrong.text
    assert r_unknown.status_code == 400 and msg in r_unknown.text


def test_IT_006_server_side_validation(client, db):
    # ブラウザ側制御を回避したリクエストでもサーバー側で拒否される
    resp = h.register(client, name="", email="not-email", password="short")
    assert resp.status_code == 400
    assert db.execute(select(func.count()).select_from(User)).scalar_one() == 0


# ============================================================
# SC-002 映画検索〜詳細
# ============================================================


def test_IT_007_movie_search_normal(client, db, factory):
    factory.make_movie(db, title="アクション大作", genre="アクション")
    factory.make_movie(db, title="恋愛物語", genre="ロマンス")
    body = client.get("/movies?keyword=アクション").text
    assert "アクション大作" in body
    assert "恋愛物語" not in body
    assert "件" in body  # 結果件数表示


def test_IT_008_zero_hit_search(client, db, factory):
    factory.make_movie(db, title="存在する映画")
    body = client.get("/movies?keyword=ありえない検索語XYZ").text
    assert "0件" in body


def test_IT_009_non_public_movie_excluded(client, db, factory):
    factory.make_movie(db, title="公開作品N")
    factory.make_movie(db, title="非公開作品N", status="draft")
    body = client.get("/movies").text
    assert "公開作品N" in body
    assert "非公開作品N" not in body


def test_IT_010_movie_pagination(client, db, factory):
    for i in range(21):
        factory.make_movie(db, title=f"ページング映画{i:02d}")
    page1 = client.get("/movies").text
    assert "21 件" in page1
    assert "1 / 2" in page1
    page2 = client.get("/movies?page=2").text
    assert "2 / 2" in page2


def test_IT_011_movie_detail_display(client, db, factory):
    movie = factory.make_movie(db, title="詳細映画", genre="SF")
    factory.make_product(db, name="詳細関連商品", stock=5, movie_id=movie.id)
    factory.make_screening(db, movie_id=movie.id, starts_at=h.future(factory))
    body = client.get(f"/movies/{movie.id}").text
    assert "詳細映画" in body
    assert "詳細関連商品" in body
    assert "SF" in body
    assert _DT_RE.search(body)  # YYYY/MM/DD HH:mm


def test_IT_012_ended_screening_no_purchase_link(client, db, factory):
    movie = factory.make_movie(db, title="上映終了映画")
    ended = factory.make_screening(
        db, movie_id=movie.id, starts_at=h.past(factory), seats_remaining=10
    )
    factory.make_user(db, name="会員", email="it012@example.com")
    h.login(client, "it012@example.com")
    body = client.get(f"/movies/{movie.id}").text
    # 上映終了回はチケット購入導線を表示しない (FR-004 制約)
    assert f"/tickets/screenings/{ended.id}" not in body


def test_IT_013_movie_search_performance(client, db, factory):
    for i in range(21):
        factory.make_movie(db, title=f"性能映画{i:02d}")
    _, elapsed = _elapsed(lambda: client.get("/movies"))
    assert elapsed < 3.0  # NFR-PERF-001


# ============================================================
# SC-003 商品検索〜カート追加
# ============================================================


def test_IT_014_product_search_normal(client, db, factory):
    factory.make_product(db, name="検索対象商品", stock=5, category="goods")
    factory.make_product(db, name="別カテゴリ商品", stock=5, category="food")
    body = client.get("/products?keyword=検索対象").text
    assert "検索対象商品" in body
    assert "件" in body


def test_IT_015_product_price_format(client, db, factory):
    factory.make_product(db, name="価格商品", price=1980, stock=5)
    body = client.get("/products?keyword=価格商品").text
    assert "1,980円" in body  # 税込・3桁区切り・円


def test_IT_016_non_public_product_excluded(client, db, factory):
    factory.make_product(db, name="公開商品P", stock=5)
    factory.make_product(db, name="非公開商品P", stock=5, publish_status="draft")
    body = client.get("/products").text
    assert "公開商品P" in body
    assert "非公開商品P" not in body


def test_IT_017_out_of_stock_display(client, db, factory):
    product = factory.make_product(db, name="在庫0商品", stock=0)
    body = client.get(f"/products/{product.id}").text
    assert "在庫なし" in body


def test_IT_018_out_of_sales_control(client, db, factory):
    before = factory.make_product(db, name="販売開始前", stock=5, sales_start_at=h.future(factory))
    after = factory.make_product(db, name="販売終了後", stock=5, sales_end_at=h.past(factory))
    assert "現在購入できません" in client.get(f"/products/{before.id}").text
    assert "現在購入できません" in client.get(f"/products/{after.id}").text
    factory.make_user(db, name="会員", email="it018@example.com")
    h.login(client, "it018@example.com")
    resp = h.add_to_cart(client, before.id, 1, from_url="/orders/new")
    assert resp.status_code == 303 and "error=" in resp.headers["location"]
    assert db.execute(select(func.count()).select_from(CartItem)).scalar_one() == 0


def test_IT_019_cart_add_normal(client, db, factory):
    factory.make_user(db, name="会員", email="it019@example.com")
    product = factory.make_product(db, name="カート対象", stock=10)
    h.login(client, "it019@example.com")
    assert h.add_to_cart(client, product.id, 2).status_code == 303
    item = db.execute(select(CartItem).where(CartItem.product_id == product.id)).scalar_one()
    assert item.quantity == 2
    db.expire_all()
    assert db.get(Product, product.id).stock == 10  # 在庫は減算しない
    assert "カート対象" in client.get("/cart").text


def test_IT_020_same_product_add(client, db, factory):
    factory.make_user(db, name="会員", email="it020@example.com")
    product = factory.make_product(db, name="加算商品", stock=10)
    h.login(client, "it020@example.com")
    h.add_to_cart(client, product.id, 2)
    h.add_to_cart(client, product.id, 3)
    items = db.execute(select(CartItem).where(CartItem.product_id == product.id)).scalars().all()
    assert len(items) == 1  # 重複明細を作らない
    assert items[0].quantity == 5


def test_IT_021_over_stock_cart_add(client, db, factory):
    factory.make_user(db, name="会員", email="it021@example.com")
    product = factory.make_product(db, name="在庫3商品", stock=3)
    h.login(client, "it021@example.com")
    resp = h.add_to_cart(client, product.id, 4)
    assert resp.status_code == 303
    assert "在庫" in unquote(resp.headers["location"])
    assert db.execute(select(func.count()).select_from(CartItem)).scalar_one() == 0


def test_IT_022_guest_cart_add_redirect(client, db, factory):
    product = factory.make_product(db, name="ゲスト商品", stock=5)
    # ゲストは商品詳細にカート追加フォームが出ない → 機能アクセスでログイン要求
    resp = client.get("/cart", follow_redirects=False)
    assert resp.status_code == 303 and resp.headers["location"] == "/login"
    detail = client.get(f"/products/{product.id}").text
    assert "ログインするとカートに追加できます" in detail


def test_IT_023_product_search_performance(client, db, factory):
    for i in range(21):
        factory.make_product(db, name=f"性能商品{i:02d}", stock=5)
    _, elapsed = _elapsed(lambda: client.get("/products"))
    assert elapsed < 3.0


def test_IT_024_cart_add_performance(client, db, factory):
    factory.make_user(db, name="会員", email="it024@example.com")
    product = factory.make_product(db, name="性能カート商品", stock=10)
    h.login(client, "it024@example.com")
    _, elapsed = _elapsed(lambda: h.add_to_cart(client, product.id, 1))
    assert elapsed < 5.0  # NFR-PERF-002


# ============================================================
# SC-004 カート内容変更
# ============================================================


def _login_with_cart(client, db, factory, email, *, stock=10, qty=2, price=1000, name="カート商品"):
    factory.make_user(db, name="会員", email=email)
    product = factory.make_product(db, name=name, price=price, stock=stock)
    h.login(client, email)
    h.add_to_cart(client, product.id, qty)
    item = db.execute(select(CartItem).where(CartItem.product_id == product.id)).scalar_one()
    return product, item


def test_IT_025_quantity_change(client, db, factory):
    product, item = _login_with_cart(client, db, factory, "it025@example.com", price=1500)
    assert h.update_cart_item(client, item.id, 3).status_code == 303
    db.expire_all()
    assert db.get(CartItem, item.id).quantity == 3
    assert "4,500円" in client.get("/cart").text  # 1500*3 再計算


def test_IT_026_delete_by_zero_quantity(client, db, factory):
    product, item = _login_with_cart(client, db, factory, "it026@example.com")
    assert h.update_cart_item(client, item.id, 0).status_code == 303
    db.expunge_all()
    assert db.get(CartItem, item.id) is None
    assert "カートは空です" in client.get("/cart").text


def test_IT_027_explicit_delete(client, db, factory):
    product, item = _login_with_cart(client, db, factory, "it027@example.com")
    # 削除フォームも quantity=0 を送る
    assert h.update_cart_item(client, item.id, 0).status_code == 303
    assert db.execute(select(func.count()).select_from(CartItem)).scalar_one() == 0


def test_IT_028_over_stock_update(client, db, factory):
    product, item = _login_with_cart(client, db, factory, "it028@example.com", stock=5, qty=2)
    resp = h.update_cart_item(client, item.id, 9)
    assert resp.status_code == 303
    db.expire_all()
    assert db.get(CartItem, item.id).quantity == 2  # 超過数量は確定保存されない


def test_IT_029_unorderable_item_mixed(client, db, factory):
    factory.make_user(db, name="会員", email="it029@example.com")
    ok = factory.make_product(db, name="正常商品", stock=10)
    ng = factory.make_product(db, name="不可商品", stock=10)
    h.login(client, "it029@example.com")
    h.add_to_cart(client, ok.id, 1)
    h.add_to_cart(client, ng.id, 1)
    # カート投入後に注文不可状態へ
    p = db.get(Product, ng.id)
    p.publish_status = "draft"
    db.commit()
    body = client.get("/cart").text
    assert "注文できない商品が含まれています" in body
    assert "/orders/new" not in body  # 注文手続きへ進めない


def test_IT_030_other_user_cart_forbidden(client, db, factory):
    _, item_a = _login_with_cart(client, db, factory, "it030a@example.com")
    factory.make_user(db, name="B", email="it030b@example.com")
    h.login(client, "it030b@example.com")
    resp = h.update_cart_item(client, item_a.id, 1)
    assert resp.status_code == 303  # 拒否 (見つからない扱い)
    db.expire_all()
    assert db.get(CartItem, item_a.id).quantity == 2  # A のカートは変更されない


def test_IT_031_cart_update_performance(client, db, factory):
    product, item = _login_with_cart(client, db, factory, "it031@example.com", stock=10)
    _, elapsed = _elapsed(lambda: h.update_cart_item(client, item.id, 3))
    assert elapsed < 5.0


# ============================================================
# SC-005 商品注文確定
# ============================================================


def _order_setup(client, db, factory, email, *, products):
    factory.make_user(db, name="会員", email=email)
    made = [factory.make_product(db, name=n, price=p, stock=s) for (n, p, s) in products]
    h.login(client, email)
    return made


def test_IT_032_single_product_order(client, db, factory):
    (product,) = _order_setup(client, db, factory, "it032@example.com", products=[("商品A", 1000, 10)])
    h.add_to_cart(client, product.id, 1)
    resp = h.place_order(client)
    assert resp.status_code == 303
    db.expire_all()
    order = db.execute(select(Order)).scalar_one()
    assert order.order_number.startswith("ORD-")
    assert db.get(Product, product.id).stock == 9
    assert db.execute(select(func.count()).select_from(CartItem)).scalar_one() == 0
    assert order.order_number in client.get(resp.headers["location"]).text


def test_IT_033_multi_product_order(client, db, factory):
    a, b = _order_setup(
        client, db, factory, "it033@example.com", products=[("商品A", 1000, 10), ("商品B", 2000, 10)]
    )
    h.add_to_cart(client, a.id, 1)
    h.add_to_cart(client, b.id, 1)
    resp = h.place_order(client)
    assert resp.status_code == 303
    db.expire_all()
    order = db.execute(select(Order)).scalar_one()
    assert len(order.items) == 2
    assert order.total_amount == 3000
    assert db.get(Product, a.id).stock == 9 and db.get(Product, b.id).stock == 9


def test_IT_034_multi_quantity_order(client, db, factory):
    (product,) = _order_setup(client, db, factory, "it034@example.com", products=[("商品A", 1200, 10)])
    h.add_to_cart(client, product.id, 3)
    resp = h.place_order(client)
    assert resp.status_code == 303
    db.expire_all()
    order = db.execute(select(Order)).scalar_one()
    assert order.items[0].quantity == 3
    assert order.items[0].subtotal == 3600
    assert order.total_amount == 3600
    assert db.get(Product, product.id).stock == 7


def test_IT_035_order_input_error(client, db, factory):
    (product,) = _order_setup(client, db, factory, "it035@example.com", products=[("商品A", 1000, 10)])
    h.add_to_cart(client, product.id, 1)
    resp = h.place_order(client, postal_code="")  # 必須不足
    assert resp.status_code == 400
    assert db.execute(select(func.count()).select_from(Order)).scalar_one() == 0


def test_IT_036_stock_shortage_before_order(client, db, factory):
    (product,) = _order_setup(client, db, factory, "it036@example.com", products=[("商品A", 1000, 5)])
    h.add_to_cart(client, product.id, 5)
    p = db.get(Product, product.id)
    p.stock = 2
    db.commit()
    resp = h.place_order(client)
    assert resp.status_code == 400
    assert db.execute(select(func.count()).select_from(Order)).scalar_one() == 0
    db.expire_all()
    assert db.get(Product, product.id).stock == 2


def test_IT_037_order_snapshot(client, db, factory):
    (product,) = _order_setup(client, db, factory, "it037@example.com", products=[("旧商品名", 1000, 10)])
    h.add_to_cart(client, product.id, 1)
    resp = h.place_order(client)
    assert resp.status_code == 303
    db.expire_all()
    order = db.execute(select(Order)).scalar_one()
    # 注文後にマスタを変更
    p = db.get(Product, product.id)
    p.name = "新商品名"
    p.price_tax_included = 9999
    db.commit()
    detail = client.get(f"/history/orders/{order.id}").text
    assert "旧商品名" in detail  # 購入時点スナップショット
    assert "新商品名" not in detail
    assert "1,000円" in detail


def test_IT_039_order_performance(client, db, factory):
    (product,) = _order_setup(client, db, factory, "it039@example.com", products=[("商品A", 1000, 10)])
    h.add_to_cart(client, product.id, 1)
    _, elapsed = _elapsed(lambda: h.place_order(client))
    assert elapsed < 5.0


# ============================================================
# SC-006 チケット購入
# ============================================================


def _screening_setup(client, db, factory, email, *, seats=50, starts=None, sales_end=None, login=True):
    factory.make_user(db, name="会員", email=email)
    movie = factory.make_movie(db, title=f"上映作品_{email}")
    screening = factory.make_screening(
        db,
        movie_id=movie.id,
        starts_at=starts if starts is not None else h.future(factory),
        seats_remaining=seats,
        sales_end_at=sales_end,
    )
    if login:
        h.login(client, email)
    return movie, screening


def test_IT_040_ticket_single_purchase(client, db, factory):
    movie, screening = _screening_setup(client, db, factory, "it040@example.com", seats=10)
    resp = h.purchase_ticket(client, screening.id, quantity=1)
    assert resp.status_code == 303
    db.expire_all()
    purchase = db.execute(select(TicketPurchase)).scalar_one()
    assert purchase.purchase_number.startswith("TKT-")
    assert db.get(Screening, screening.id).seats_remaining == 9


def test_IT_041_ticket_multiple_quantity(client, db, factory):
    movie, screening = _screening_setup(client, db, factory, "it041@example.com", seats=10)
    resp = h.purchase_ticket(client, screening.id, ticket_type="general", quantity=3)
    assert resp.status_code == 303
    db.expire_all()
    purchase = db.execute(select(TicketPurchase)).scalar_one()
    assert purchase.items[0].quantity == 3
    assert purchase.items[0].subtotal == purchase.items[0].unit_price * 3
    assert purchase.total_amount == purchase.items[0].subtotal
    assert db.get(Screening, screening.id).seats_remaining == 7


def test_IT_042_ticket_type_variation(client, db, factory):
    # 実装は複数券種 (一般/学生/シニア) を提供する。券種ごとの単価整合を確認する。
    movie, screening = _screening_setup(client, db, factory, "it042@example.com", seats=10)
    resp = h.purchase_ticket(client, screening.id, ticket_type="student", quantity=2)
    assert resp.status_code == 303
    db.expire_all()
    purchase = db.execute(select(TicketPurchase)).scalar_one()
    assert purchase.items[0].ticket_type == "student"
    assert purchase.items[0].unit_price == 1500
    assert purchase.items[0].subtotal == 3000
    assert db.get(Screening, screening.id).seats_remaining == 8


def test_IT_043_insufficient_seats(client, db, factory):
    movie, screening = _screening_setup(client, db, factory, "it043@example.com", seats=1)
    resp = h.purchase_ticket(client, screening.id, quantity=2)
    assert resp.status_code == 303
    assert "error=" in resp.headers["location"]
    assert db.execute(select(func.count()).select_from(TicketPurchase)).scalar_one() == 0
    db.expire_all()
    assert db.get(Screening, screening.id).seats_remaining == 1


def test_IT_044_out_of_sales_period(client, db, factory):
    movie, screening = _screening_setup(
        client, db, factory, "it044@example.com", seats=10, sales_end=h.past(factory)
    )
    resp = h.purchase_ticket(client, screening.id, csrf_url="/orders/new")
    assert resp.status_code == 303
    assert "error=" in resp.headers["location"]
    assert db.execute(select(func.count()).select_from(TicketPurchase)).scalar_one() == 0


def test_IT_045_after_screening_start(client, db, factory):
    movie, screening = _screening_setup(
        client, db, factory, "it045@example.com", seats=10, starts=h.past(factory)
    )
    resp = h.purchase_ticket(client, screening.id, csrf_url="/orders/new")
    assert resp.status_code == 303
    assert "error=" in resp.headers["location"]
    db.expire_all()
    assert db.get(Screening, screening.id).seats_remaining == 10
    assert db.execute(select(func.count()).select_from(TicketPurchase)).scalar_one() == 0


def test_IT_046_guest_ticket_purchase_redirect(client, db, factory):
    movie, screening = _screening_setup(client, db, factory, "it046@example.com", seats=10, login=False)
    resp = client.get(f"/tickets/screenings/{screening.id}", follow_redirects=False)
    assert resp.status_code == 303 and resp.headers["location"] == "/login"


def test_IT_048_ticket_purchase_performance(client, db, factory):
    movie, screening = _screening_setup(client, db, factory, "it048@example.com", seats=10)
    _, elapsed = _elapsed(lambda: h.purchase_ticket(client, screening.id, quantity=1))
    assert elapsed < 5.0


# ============================================================
# SC-007 購入履歴
# ============================================================


def test_IT_049_history_list_normal(client, db, factory):
    user = factory.make_user(db, name="A", email="it049@example.com")
    product = factory.make_product(db, name="履歴商品", stock=5)
    movie = factory.make_movie(db, title="履歴映画")
    screening = factory.make_screening(db, movie_id=movie.id, starts_at=h.future(factory))
    order = h.make_order(db, user, items=[(product, 1)])
    purchase = h.make_ticket_purchase(db, user, screening, movie)
    h.login(client, "it049@example.com")
    body = client.get("/history").text
    assert order.order_number in body
    assert purchase.purchase_number in body


def test_IT_050_history_order_desc(client, db, factory):
    user = factory.make_user(db, name="A", email="it050@example.com")
    product = factory.make_product(db, name="商品", stock=10)
    old = h.make_order(db, user, items=[(product, 1)])
    new = h.make_order(db, user, items=[(product, 1)])
    old.ordered_at = h.past(factory, hours=48)
    new.ordered_at = h.past(factory, hours=1)
    db.commit()
    h.login(client, "it050@example.com")
    body = client.get("/history").text
    assert body.index(new.order_number) < body.index(old.order_number)  # 降順


def test_IT_051_history_detail(client, db, factory):
    user = factory.make_user(db, name="A", email="it051@example.com")
    product = factory.make_product(db, name="詳細商品", price=1500, stock=5)
    movie = factory.make_movie(db, title="詳細映画")
    screening = factory.make_screening(db, movie_id=movie.id, starts_at=h.future(factory))
    order = h.make_order(db, user, items=[(product, 2)])
    h.make_ticket_purchase(db, user, screening, movie, ticket_type="general", quantity=1)
    h.login(client, "it051@example.com")
    detail = client.get(f"/history/orders/{order.id}").text
    assert "詳細商品" in detail and "数量" in detail
    hist = client.get("/history").text
    assert "詳細映画" in hist and "general" in hist  # チケット購入内容


def test_IT_052_history_display_format(client, db, factory):
    user = factory.make_user(db, name="A", email="it052@example.com")
    product = factory.make_product(db, name="金額商品", price=2500, stock=5)
    h.make_order(db, user, items=[(product, 1)])
    h.login(client, "it052@example.com")
    body = client.get("/history").text
    assert "2,500円" in body
    assert _DT_RE.search(body)


def test_IT_053_other_user_history_forbidden(client, db, factory):
    user_a = factory.make_user(db, name="A", email="it053a@example.com")
    user_b = factory.make_user(db, name="B", email="it053b@example.com")
    product = factory.make_product(db, name="商品", stock=5)
    order_b = h.make_order(db, user_b, items=[(product, 1)])
    h.login(client, "it053a@example.com")
    assert client.get(f"/history/orders/{order_b.id}", follow_redirects=False).status_code == 403


def test_IT_054_guest_history_redirect(client, db):
    resp = client.get("/history", follow_redirects=False)
    assert resp.status_code == 303 and resp.headers["location"] == "/login"


def test_IT_055_history_performance(client, db, factory):
    user = factory.make_user(db, name="A", email="it055@example.com")
    product = factory.make_product(db, name="商品", stock=50)
    for _ in range(10):
        h.make_order(db, user, items=[(product, 1)])
    h.login(client, "it055@example.com")
    _, elapsed = _elapsed(lambda: client.get("/history"))
    assert elapsed < 3.0


# ============================================================
# SC-008 認証・認可とデータ分離
# ============================================================


def test_IT_056_guest_allowed_features(client, db, factory):
    movie = factory.make_movie(db, title="ゲスト映画")
    product = factory.make_product(db, name="ゲスト商品", stock=5)
    for url in ["/movies", f"/movies/{movie.id}", "/products", f"/products/{product.id}", "/register", "/login"]:
        assert client.get(url).status_code == 200, url


def test_IT_057_guest_disallowed_features(client, db, factory):
    movie = factory.make_movie(db, title="要認証映画")
    screening = factory.make_screening(db, movie_id=movie.id, starts_at=h.future(factory))
    for url in ["/cart", "/orders/new", f"/tickets/screenings/{screening.id}", "/history"]:
        resp = client.get(url, follow_redirects=False)
        assert resp.status_code == 303 and resp.headers["location"] == "/login", url


def test_IT_058_member_allowed_features(client, db, factory):
    factory.make_user(db, name="会員", email="it058@example.com")
    movie = factory.make_movie(db, title="会員映画")
    screening = factory.make_screening(db, movie_id=movie.id, starts_at=h.future(factory))
    h.login(client, "it058@example.com")
    for url in ["/cart", "/orders/new", f"/tickets/screenings/{screening.id}", "/history"]:
        assert client.get(url).status_code == 200, url


def test_IT_059_other_user_order_forbidden(client, db, factory):
    user_a = factory.make_user(db, name="A", email="it059a@example.com")
    user_b = factory.make_user(db, name="B", email="it059b@example.com")
    product = factory.make_product(db, name="商品", stock=5)
    order_b = h.make_order(db, user_b, items=[(product, 1)])
    h.login(client, "it059a@example.com")
    assert client.get(f"/history/orders/{order_b.id}", follow_redirects=False).status_code == 403


def test_IT_060_other_user_ticket_forbidden(client, db, factory):
    user_a = factory.make_user(db, name="A", email="it060a@example.com")
    user_b = factory.make_user(db, name="B", email="it060b@example.com")
    movie = factory.make_movie(db, title="映画")
    screening = factory.make_screening(db, movie_id=movie.id, starts_at=h.future(factory))
    purchase_b = h.make_ticket_purchase(db, user_b, screening, movie)
    h.login(client, "it060a@example.com")
    assert client.get(f"/tickets/{purchase_b.id}/complete", follow_redirects=False).status_code == 404


def test_IT_061_other_user_cart_change_forbidden(client, db, factory):
    _, item_a = _login_with_cart(client, db, factory, "it061a@example.com")
    factory.make_user(db, name="B", email="it061b@example.com")
    h.login(client, "it061b@example.com")
    resp = h.update_cart_item(client, item_a.id, 1)
    assert resp.status_code == 303
    db.expire_all()
    assert db.get(CartItem, item_a.id).quantity == 2  # A のカートは変更されない


# ============================================================
# SC-009 共通エラー制御
# ============================================================


def test_IT_062_input_invalid(client, db):
    resp = h.register(client, name="", email="bad", password="x")
    assert resp.status_code == 400
    assert db.execute(select(func.count()).select_from(User)).scalar_one() == 0


def test_IT_063_stock_shortage(client, db, factory):
    factory.make_user(db, name="会員", email="it063@example.com")
    product = factory.make_product(db, name="在庫僅少", stock=1)
    h.login(client, "it063@example.com")
    resp = h.add_to_cart(client, product.id, 5)
    assert resp.status_code == 303
    assert "在庫" in unquote(resp.headers["location"])
    assert db.execute(select(func.count()).select_from(CartItem)).scalar_one() == 0


def test_IT_064_permission_denied(client, db, factory):
    user_a = factory.make_user(db, name="A", email="it064a@example.com")
    user_b = factory.make_user(db, name="B", email="it064b@example.com")
    product = factory.make_product(db, name="商品", stock=5)
    order_b = h.make_order(db, user_b, items=[(product, 1)])
    h.login(client, "it064a@example.com")
    resp = client.get(f"/history/orders/{order_b.id}", follow_redirects=False)
    assert resp.status_code == 403


def test_IT_065_auth_failure(client, db, factory):
    factory.make_user(db, name="会員", email="it065@example.com")
    resp = h.login(client, "it065@example.com", "WrongPass9")
    assert resp.status_code == 400
    assert "メールアドレスまたはパスワードが正しくありません。" in resp.text


def test_IT_066_out_of_sales_period_common(client, db, factory):
    factory.make_user(db, name="会員", email="it066@example.com")
    product = factory.make_product(db, name="販売前商品", stock=5, sales_start_at=h.future(factory))
    movie = factory.make_movie(db, title="販売期間外映画")
    screening = factory.make_screening(
        db, movie_id=movie.id, starts_at=h.future(factory), seats_remaining=10, sales_end_at=h.past(factory)
    )
    h.login(client, "it066@example.com")
    r_product = h.add_to_cart(client, product.id, 1, from_url="/orders/new")
    assert r_product.status_code == 303 and "error=" in r_product.headers["location"]
    r_ticket = h.purchase_ticket(client, screening.id, csrf_url="/orders/new")
    assert r_ticket.status_code == 303 and "error=" in r_ticket.headers["location"]


# ============================================================
# SC-010 共通UI・入力安全性
# ============================================================


def test_IT_069_common_header_navigation(client, db, factory):
    factory.make_user(db, name="会員", email="it069@example.com")
    factory.make_movie(db, title="ヘッダー映画")
    factory.make_product(db, name="ヘッダー商品", stock=5)
    h.login(client, "it069@example.com")
    for url in ["/", "/movies", "/products", "/cart", "/history"]:
        body = client.get(url).text
        assert "映画館EC" in body  # ブランド/ヘッダー
        assert 'href="/movies"' in body and 'href="/cart"' in body
        assert 'action="/movies"' in body  # 検索導線


def test_IT_070_input_error_display(client, db):
    resp = h.register(client, name="X", email="bad-format", password="Passw0rd")
    assert resp.status_code == 400
    assert "field-error" in resp.text  # 項目近傍のエラー表示


def test_IT_071_list_common_pagination(client, db, factory):
    for i in range(21):
        factory.make_product(db, name=f"一覧商品{i:02d}", stock=5)
    body = client.get("/products").text
    assert "21 件" in body
    assert "1 / 2" in body  # 標準ページサイズ20件


def test_IT_072_amount_display(client, db, factory):
    factory.make_product(db, name="金額確認商品", price=12345, stock=5)
    body = client.get("/products?keyword=金額確認").text
    assert "12,345円" in body


def test_IT_073_datetime_display(client, db, factory):
    movie = factory.make_movie(db, title="日時映画")
    factory.make_screening(db, movie_id=movie.id, starts_at=h.future(factory))
    body = client.get(f"/movies/{movie.id}").text
    assert _DT_RE.search(body)  # YYYY/MM/DD HH:mm


def test_IT_074_sql_injection_defense(client, db, factory):
    factory.make_user(db, name="被害者", email="victim@example.com")
    factory.make_product(db, name="通常商品", stock=5)
    payload = "'; DROP TABLE users; --"
    resp = client.get("/products", params={"keyword": payload})
    assert resp.status_code == 200
    # users テーブルが破壊されていない (パラメータ化により未実行)
    assert db.execute(select(func.count()).select_from(User)).scalar_one() == 1


def test_IT_075_xss_defense(client, db, factory):
    factory.make_product(db, name="通常商品", stock=5)
    payload = "<script>alert('xss')</script>"
    resp = client.get("/products", params={"keyword": payload})
    assert resp.status_code == 200
    assert payload not in resp.text  # 生スクリプトは出力されない
    assert "&lt;script&gt;" in resp.text  # エスケープ済み (NFR-SEC-005)
