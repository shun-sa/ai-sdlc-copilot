"""受け入れ試験ケース AT-001〜AT-032 の AGENT_DRIVEN 実行。

入力仕様: movie-ec-acceptance-test-cases.json (HUMAN_ACCEPTANCE_TEST_SPEC)。
各テストは仕様の steps を実操作へ写像し、expected_result を検証する。
ケース・期待結果の意味は変更しない。判定は PASS / FAIL / BLOCKED。
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.constants import PaymentMethod, PublishStatus, TicketType
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
    make_movie,
    make_product,
    make_screening,
    make_user,
    place_order,
    purchase_ticket,
    register,
)

UTC = timezone.utc
PAY = PaymentMethod.CREDIT_CARD_MOCK.value


# ==========================================================================
# 機能要件（正常系）
# ==========================================================================


@pytest.mark.acceptance(
    case_id="AT-001", requirement_id="FR-001", requirement_type="FUNCTIONAL",
    title="会員登録を完了できる",
)
def test_at_001_register(client, session_factory):
    res = register(client, name="受入太郎", email="at001@example.com", password="Passw0rd")
    assert res.status_code == 200
    with session_factory() as s:
        assert s.scalars(select(User).where(User.email == "at001@example.com")).one()
    # 以後会員として扱われる（会員専用機能へアクセスできる）。
    assert client.get("/history").status_code == 200


@pytest.mark.acceptance(
    case_id="AT-002", requirement_id="FR-002", requirement_type="FUNCTIONAL",
    title="登録済みユーザーがログインできる",
)
def test_at_002_login(client, session_factory):
    with session_factory() as s:
        make_user(s, email="at002@example.com")
        s.commit()
    res = login(client, "at002@example.com")
    assert res.status_code == 200
    assert client.get("/history").status_code == 200  # 会員向け機能を利用できる


@pytest.mark.acceptance(
    case_id="AT-003", requirement_id="FR-003", requirement_type="FUNCTIONAL",
    title="映画を検索して目的の作品を見つけられる",
)
def test_at_003_movie_search(client, session_factory):
    with session_factory() as s:
        make_movie(s, title="宇宙大戦争", genre="SF")
        make_movie(s, title="宇宙の詩", genre="ドラマ")
        make_movie(s, title="草原の休日", genre="ドラマ")
        s.commit()
    res = client.get("/movies", params={"keyword": "宇宙"})
    assert res.status_code == 200
    assert "宇宙大戦争" in res.text
    assert "宇宙の詩" in res.text
    assert "草原の休日" not in res.text  # 目的外は含まれない


@pytest.mark.acceptance(
    case_id="AT-004", requirement_id="FR-004", requirement_type="FUNCTIONAL",
    title="映画詳細から関連商品・購入可能な上映回を確認できる",
)
def test_at_004_movie_detail(client, session_factory):
    with session_factory() as s:
        make_user(s, email="at004@example.com")
        movie = make_movie(s, title="関連商品映画")
        make_product(s, name="パンフレットA", movie_id=movie.id)
        sid = make_screening(s, movie_id=movie.id, seats_remaining=10).id
        mid = movie.id
        s.commit()
    login(client, "at004@example.com")  # 購入導線は会員かつ販売中で表示
    res = client.get(f"/movies/{mid}")
    assert res.status_code == 200
    assert "関連商品映画" in res.text
    assert "パンフレットA" in res.text  # 関連商品
    assert "上映スケジュール" in res.text
    assert f"/tickets/new?screening_id={sid}" in res.text  # 購入可能な導線


@pytest.mark.acceptance(
    case_id="AT-005", requirement_id="FR-005", requirement_type="FUNCTIONAL",
    title="商品を検索・閲覧できる",
)
def test_at_005_product_search_and_detail(client, session_factory):
    with session_factory() as s:
        pid = make_product(s, name="限定マグカップ").id
        make_product(s, name="通常タオル")
        s.commit()
    res = client.get("/products", params={"keyword": "マグカップ"})
    assert res.status_code == 200
    assert "限定マグカップ" in res.text
    assert "通常タオル" not in res.text
    detail = client.get(f"/products/{pid}")
    assert detail.status_code == 200
    assert "限定マグカップ" in detail.text  # 商品詳細を確認できる


@pytest.mark.acceptance(
    case_id="AT-006", requirement_id="FR-008", requirement_type="FUNCTIONAL",
    title="商品購入シナリオ1：単一商品",
)
def test_at_006_order_single(client, session_factory):
    with session_factory() as s:
        uid = make_user(s, email="at006@example.com").id
        pid = make_product(s, name="単品商品", price=1500, stock=5).id
        s.commit()
    login(client, "at006@example.com")
    add_to_cart(client, pid, 1)
    res = place_order(client)
    assert res.status_code == 200
    assert "注文番号" in res.text
    with session_factory() as s:
        order = s.scalars(select(Order).where(Order.user_id == uid)).one()
        assert order.order_number.startswith("ORD-")
    history = client.get("/history")
    assert "単品商品" in history.text  # 購入履歴に反映


@pytest.mark.acceptance(
    case_id="AT-007", requirement_id="FR-008", requirement_type="FUNCTIONAL",
    title="商品購入シナリオ2：複数種類の商品",
)
def test_at_007_order_multiple_products(client, session_factory):
    with session_factory() as s:
        uid = make_user(s, email="at007@example.com").id
        p1 = make_product(s, name="商品X", price=1000, stock=5).id
        p2 = make_product(s, name="商品Y", price=2000, stock=5).id
        s.commit()
    login(client, "at007@example.com")
    add_to_cart(client, p1, 1)
    add_to_cart(client, p2, 2)
    place_order(client)
    with session_factory() as s:
        order = s.scalars(select(Order).where(Order.user_id == uid)).one()
        assert {i.product_snapshot_name for i in order.items} == {"商品X", "商品Y"}
        assert order.total_amount == 1000 + 2000 * 2  # 正しい数量・金額で1注文


@pytest.mark.acceptance(
    case_id="AT-008", requirement_id="FR-008", requirement_type="FUNCTIONAL",
    title="商品購入シナリオ3：同一商品の複数量",
)
def test_at_008_order_same_product_multiple(client, session_factory):
    with session_factory() as s:
        uid = make_user(s, email="at008@example.com").id
        pid = make_product(s, name="複数量商品", price=800, stock=10).id
        s.commit()
    login(client, "at008@example.com")
    add_to_cart(client, pid, 3)
    place_order(client)
    with session_factory() as s:
        order = s.scalars(select(Order).where(Order.user_id == uid)).one()
        assert order.items[0].quantity == 3
        assert s.get(Product, pid).stock == 7  # 在庫と注文内容が整合


@pytest.mark.acceptance(
    case_id="AT-009", requirement_id="FR-009", requirement_type="FUNCTIONAL",
    title="チケット購入シナリオ1：1枚",
)
def test_at_009_ticket_single(client, session_factory):
    with session_factory() as s:
        uid = make_user(s, email="at009@example.com").id
        movie = make_movie(s, title="チケット映画1")
        sid = make_screening(s, movie_id=movie.id, seats_remaining=20).id
        s.commit()
    login(client, "at009@example.com")
    res = purchase_ticket(client, screening_id=sid, quantity=1)
    assert res.status_code == 200
    assert "購入番号" in res.text
    with session_factory() as s:
        purchase = s.scalars(select(TicketPurchase).where(TicketPurchase.user_id == uid)).one()
        assert purchase.purchase_number.startswith("TKT-")
    assert client.get("/history").status_code == 200


@pytest.mark.acceptance(
    case_id="AT-010", requirement_id="FR-009", requirement_type="FUNCTIONAL",
    title="チケット購入シナリオ2：複数枚",
)
def test_at_010_ticket_multiple(client, session_factory):
    with session_factory() as s:
        make_user(s, email="at010@example.com")
        movie = make_movie(s, title="チケット映画2")
        sid = make_screening(s, movie_id=movie.id, seats_remaining=20).id
        s.commit()
    login(client, "at010@example.com")
    purchase_ticket(client, screening_id=sid, quantity=3)
    with session_factory() as s:
        assert s.get(Screening, sid).seats_remaining == 17  # 残席が同数減少


@pytest.mark.acceptance(
    case_id="AT-011", requirement_id="FR-009", requirement_type="FUNCTIONAL",
    title="チケット購入シナリオ3：別映画・別上映回",
)
def test_at_011_ticket_other_movie(client, session_factory):
    with session_factory() as s:
        uid = make_user(s, email="at011@example.com").id
        make_movie(s, title="旧作映画")
        movie2 = make_movie(s, title="新作映画Z")
        sid = make_screening(s, movie_id=movie2.id, seats_remaining=10).id
        s.commit()
    login(client, "at011@example.com")
    found = client.get("/movies", params={"keyword": "新作映画Z"})
    assert "新作映画Z" in found.text
    purchase_ticket(client, screening_id=sid, quantity=1)
    history = client.get("/history")
    assert "新作映画Z" in history.text  # 正しい上映情報で履歴反映
    with session_factory() as s:
        assert len(list(s.scalars(select(TicketPurchase).where(TicketPurchase.user_id == uid)))) == 1


@pytest.mark.acceptance(
    case_id="AT-012", requirement_id="FR-010", requirement_type="FUNCTIONAL",
    title="購入履歴で商品注文とチケット購入を確認できる",
)
def test_at_012_history_shows_both(client, session_factory):
    with session_factory() as s:
        make_user(s, email="at012@example.com")
        pid = make_product(s, name="履歴確認商品", stock=5).id
        movie = make_movie(s, title="履歴確認映画")
        sid = make_screening(s, movie_id=movie.id, seats_remaining=10).id
        s.commit()
    login(client, "at012@example.com")
    add_to_cart(client, pid, 1)
    place_order(client)
    purchase_ticket(client, screening_id=sid, quantity=1)
    history = client.get("/history")
    assert history.status_code == 200
    assert "履歴確認商品" in history.text  # 商品注文1件以上
    assert "履歴確認映画" in history.text  # チケット購入1件以上


# ==========================================================================
# 機能要件（異常系）
# ==========================================================================


@pytest.mark.acceptance(
    case_id="AT-013", requirement_id="FR-001", requirement_type="FUNCTIONAL",
    title="異常分類：入力不備",
)
def test_at_013_input_invalid(client, session_factory):
    res = client.post(
        "/register",
        data={"name": "", "email": "not-an-email", "password": "abc", "password_confirm": "xyz"},
    )
    assert res.status_code == 400  # 処理は成立しない
    with session_factory() as s:
        assert list(s.scalars(select(User))) == []  # 登録されない


@pytest.mark.acceptance(
    case_id="AT-014", requirement_id="FR-008", requirement_type="FUNCTIONAL",
    title="異常分類：在庫不足",
)
def test_at_014_stock_shortage(client, session_factory):
    with session_factory() as s:
        uid = make_user(s, email="at014@example.com").id
        pid = make_product(s, name="在庫不足商品", stock=5).id
        s.commit()
    login(client, "at014@example.com")
    add_to_cart(client, pid, 3)
    with session_factory() as s:  # カート投入後に在庫を必要数未満へ
        s.get(Product, pid).stock = 1
        s.commit()
    res = place_order(client, follow_redirects=False)
    assert res.status_code == 409  # 注文は成立しない
    with session_factory() as s:
        assert list(s.scalars(select(Order).where(Order.user_id == uid))) == []  # 不完全注文が残らない
        assert s.get(Product, pid).stock == 1  # DB整合（減算されない）


@pytest.mark.acceptance(
    case_id="AT-015", requirement_id="FR-010", requirement_type="FUNCTIONAL",
    title="異常分類：権限不足",
)
def test_at_015_permission_denied(client, session_factory):
    with session_factory() as s:
        make_user(s, email="at015a@example.com")  # 会員A
        b = make_user(s, email="at015b@example.com")  # 会員B
        pid = make_product(s, name="B専用商品", stock=5).id
        from tests.integration._helpers import make_order

        make_order(s, user_id=b.id, order_number="ORD-B0001",
                   items=[(pid, "B専用商品", 1000, 1)])
        s.commit()
    login(client, "at015a@example.com")
    history = client.get("/history")
    assert history.status_code == 200
    assert "B専用商品" not in history.text  # 他会員データを参照できない
    assert "ORD-B0001" not in history.text


@pytest.mark.acceptance(
    case_id="AT-016", requirement_id="FR-002", requirement_type="FUNCTIONAL",
    title="異常分類：認証失敗",
)
def test_at_016_auth_failure(client, session_factory):
    with session_factory() as s:
        make_user(s, email="at016@example.com", password="password123")
        s.commit()
    res = login(client, "at016@example.com", "wrongpassword", follow_redirects=False)
    assert res.status_code == 401  # ログインできない
    # アカウント存在有無を推測できない汎用メッセージ
    assert "メールアドレスまたはパスワードが正しくありません。" in res.text


@pytest.mark.acceptance(
    case_id="AT-017", requirement_id="FR-005", requirement_type="FUNCTIONAL",
    title="異常分類：販売期間外",
)
def test_at_017_out_of_sales_period(client, session_factory):
    now = datetime.now(UTC)
    with session_factory() as s:
        uid = make_user(s, email="at017@example.com").id
        pid = make_product(
            s, name="販売終了商品", stock=5,
            sales_start_at=now - timedelta(days=10), sales_end_at=now - timedelta(days=1),
        ).id
        s.commit()
    # 閲覧は可能
    assert client.get(f"/products/{pid}").status_code == 200
    login(client, "at017@example.com")
    add_to_cart(client, pid, 1)
    res = place_order(client, follow_redirects=False)
    assert res.status_code == 409  # 購入できない
    with session_factory() as s:
        assert list(s.scalars(select(Order).where(Order.user_id == uid))) == []


# ==========================================================================
# 非機能要件：性能
# ==========================================================================


@pytest.mark.acceptance(
    case_id="AT-018", requirement_id="NFR-PERF-001", requirement_type="NON_FUNCTIONAL",
    title="映画検索の初期表示性能",
)
def test_at_018_movie_list_perf(client, session_factory):
    with session_factory() as s:
        for i in range(30):
            make_movie(s, title=f"性能映画{i:02d}")
        s.commit()
    start = time.perf_counter()
    res = client.get("/movies")
    elapsed = time.perf_counter() - start
    assert res.status_code == 200
    assert elapsed < 3.0


@pytest.mark.acceptance(
    case_id="AT-019", requirement_id="NFR-PERF-001", requirement_type="NON_FUNCTIONAL",
    title="商品検索の初期表示性能",
)
def test_at_019_product_list_perf(client, session_factory):
    with session_factory() as s:
        for i in range(30):
            make_product(s, name=f"性能商品{i:02d}")
        s.commit()
    start = time.perf_counter()
    res = client.get("/products")
    elapsed = time.perf_counter() - start
    assert res.status_code == 200
    assert elapsed < 3.0


@pytest.mark.acceptance(
    case_id="AT-020", requirement_id="NFR-PERF-001", requirement_type="NON_FUNCTIONAL",
    title="購入履歴の初期表示性能",
)
def test_at_020_history_perf(client, session_factory):
    with session_factory() as s:
        uid = make_user(s, email="at020@example.com").id
        from tests.integration._helpers import make_order

        for i in range(20):
            pid = make_product(s, name=f"履歴商品{i:02d}", stock=5).id
            make_order(s, user_id=uid, order_number=f"ORD-P{i:04d}",
                       items=[(pid, f"履歴商品{i:02d}", 1000, 1)])
        s.commit()
    login(client, "at020@example.com")
    start = time.perf_counter()
    res = client.get("/history")
    elapsed = time.perf_counter() - start
    assert res.status_code == 200
    assert elapsed < 3.0


@pytest.mark.acceptance(
    case_id="AT-021", requirement_id="NFR-PERF-002", requirement_type="NON_FUNCTIONAL",
    title="商品注文確定の応答性能",
)
def test_at_021_order_response_perf(client, session_factory):
    with session_factory() as s:
        make_user(s, email="at021@example.com")
        pid = make_product(s, name="注文性能商品", stock=10).id
        s.commit()
    login(client, "at021@example.com")
    add_to_cart(client, pid, 2)
    start = time.perf_counter()
    res = place_order(client)
    elapsed = time.perf_counter() - start
    assert res.status_code == 200
    assert elapsed < 5.0


@pytest.mark.acceptance(
    case_id="AT-022", requirement_id="NFR-PERF-002", requirement_type="NON_FUNCTIONAL",
    title="チケット購入確定の応答性能",
)
def test_at_022_ticket_response_perf(client, session_factory):
    with session_factory() as s:
        make_user(s, email="at022@example.com")
        movie = make_movie(s, title="チケット性能映画")
        sid = make_screening(s, movie_id=movie.id, seats_remaining=20).id
        s.commit()
    login(client, "at022@example.com")
    start = time.perf_counter()
    res = purchase_ticket(client, screening_id=sid, quantity=1)
    elapsed = time.perf_counter() - start
    assert res.status_code == 200
    assert elapsed < 5.0


# ==========================================================================
# 非機能要件：セキュリティ
# ==========================================================================


@pytest.mark.acceptance(
    case_id="AT-023", requirement_id="NFR-SEC-001", requirement_type="NON_FUNCTIONAL",
    title="パスワードを平文保存しない",
)
def test_at_023_password_hashed(client, session_factory):
    register(client, name="ハッシュ太郎", email="at023@example.com", password="Passw0rd")
    with session_factory() as s:
        user = s.scalars(select(User).where(User.email == "at023@example.com")).one()
        assert user.password_hash != "Passw0rd"  # 平文が保存されない
        assert verify_password("Passw0rd", user.password_hash)  # ハッシュ値が保持される


@pytest.mark.acceptance(
    case_id="AT-024", requirement_id="NFR-SEC-002", requirement_type="NON_FUNCTIONAL",
    title="未認証アクセスを拒否する",
)
def test_at_024_unauthenticated_denied(client):
    for path in ("/orders/new", "/tickets/new?screening_id=1", "/history"):
        res = client.get(path, follow_redirects=False)
        assert res.status_code == 303  # 会員専用機能を利用できない
        assert res.headers["location"].startswith("/login")  # ログイン要求


@pytest.mark.acceptance(
    case_id="AT-025", requirement_id="NFR-SEC-003", requirement_type="NON_FUNCTIONAL",
    title="他会員データを参照・変更できない",
)
def test_at_025_cross_user_isolation(client, session_factory):
    with session_factory() as s:
        make_user(s, email="at025a@example.com")  # 会員A
        b = make_user(s, email="at025b@example.com")  # 会員B
        pid = make_product(s, name="B購入商品", stock=5).id
        s.commit()
        b_id = b.id
    # B がカートに商品を入れる
    login(client, "at025b@example.com")
    add_to_cart(client, pid, 1)
    with session_factory() as s:
        b_item_id = cart_item_id_of(s, b_id, pid)
    client.post("/logout")
    # A がログインし、B のカート明細を変更しようとする
    login(client, "at025a@example.com")
    res = client.post(f"/cart/items/{b_item_id}", data={"quantity": 9}, follow_redirects=False)
    assert res.status_code in (403, 404)  # 参照・変更できない
    with session_factory() as s:  # B のカートは不変
        from app.repositories.cart_repository import CartRepository

        item = CartRepository(s).get_item_by_id(b_item_id)
        assert item is not None and item.quantity == 1


@pytest.mark.acceptance(
    case_id="AT-026", requirement_id="NFR-SEC-005", requirement_type="NON_FUNCTIONAL",
    title="SQLインジェクション/XSSの代表攻撃を防止する",
)
def test_at_026_sqli_and_xss(client, session_factory):
    with session_factory() as s:
        make_movie(s, title="正規映画A")
        make_movie(s, title="正規映画B")
        pid = make_product(s, name="<script>alert('xss')</script>").id
        s.commit()
    # SQLi: 構文として解釈されず全件返却されない
    sqli = client.get("/movies", params={"keyword": "' OR '1'='1"})
    assert sqli.status_code == 200
    assert "検索結果: 0件" in sqli.text
    # XSS: 生スクリプトは出力されずエスケープされる
    xss = client.get(f"/products/{pid}")
    assert "<script>alert('xss')</script>" not in xss.text
    assert "&lt;script&gt;" in xss.text


# ==========================================================================
# 非機能要件：整合性
# ==========================================================================


@pytest.mark.acceptance(
    case_id="AT-027", requirement_id="NFR-AVL-001", requirement_type="NON_FUNCTIONAL",
    title="注文と在庫の整合性",
)
def test_at_027_order_stock_consistency(client, session_factory):
    with session_factory() as s:
        uid = make_user(s, email="at027@example.com").id
        pid = make_product(s, name="整合性商品", price=1200, stock=5).id
        s.commit()
    login(client, "at027@example.com")
    add_to_cart(client, pid, 2)
    place_order(client)
    with session_factory() as s:
        order = s.scalars(select(Order).where(Order.user_id == uid)).one()
        assert order.total_amount == 2400
        assert s.get(Product, pid).stock == 3  # 注文と在庫減算が一致（片側更新なし）


@pytest.mark.acceptance(
    case_id="AT-028", requirement_id="NFR-AVL-002", requirement_type="NON_FUNCTIONAL",
    title="チケット購入と残席の整合性",
)
def test_at_028_ticket_seat_consistency(client, session_factory):
    with session_factory() as s:
        uid = make_user(s, email="at028@example.com").id
        movie = make_movie(s, title="残席整合映画")
        sid = make_screening(s, movie_id=movie.id, seats_remaining=10).id
        s.commit()
    login(client, "at028@example.com")
    purchase_ticket(client, screening_id=sid, quantity=3)
    with session_factory() as s:
        purchase = s.scalars(select(TicketPurchase).where(TicketPurchase.user_id == uid)).one()
        assert purchase.items[0].quantity == 3
        assert s.get(Screening, sid).seats_remaining == 7  # 購入枚数と残席減算が一致


# ==========================================================================
# 非機能要件：ユーザビリティ / 制約
# ==========================================================================


@pytest.mark.acceptance(
    case_id="AT-029", requirement_id="NFR-USAB-001", requirement_type="NON_FUNCTIONAL",
    title="トップから主要機能へ到達できる",
)
def test_at_029_top_navigation(client, session_factory):
    with session_factory() as s:
        make_user(s, email="at029@example.com")
        s.commit()
    guest = client.get("/")  # ゲスト
    assert guest.status_code == 200
    assert 'href="/movies"' in guest.text
    assert 'href="/products"' in guest.text
    assert 'href="/login"' in guest.text
    login(client, "at029@example.com")  # 会員
    member = client.get("/")
    assert 'href="/cart"' in member.text
    assert 'href="/history"' in member.text


@pytest.mark.acceptance(
    case_id="AT-030", requirement_id="NFR-USAB-003", requirement_type="NON_FUNCTIONAL",
    title="注文確定前に必要情報を確認できる",
)
def test_at_030_order_confirmation(client, session_factory):
    with session_factory() as s:
        make_user(s, email="at030@example.com")
        pid = make_product(s, name="確認画面商品", price=1500, stock=5).id
        s.commit()
    login(client, "at030@example.com")
    add_to_cart(client, pid, 2)
    res = client.get("/orders/new")  # 最終確定直前の画面
    assert res.status_code == 200
    assert "確認画面商品" in res.text
    assert "合計" in res.text  # 金額
    assert "配送先" in res.text or "氏名" in res.text  # 配送先
    assert "支払方法" in res.text  # 支払


@pytest.mark.acceptance(
    case_id="AT-031", requirement_id="NFR-USAB-004", requirement_type="NON_FUNCTIONAL",
    title="チケット確定前に必要情報を確認できる",
)
def test_at_031_ticket_confirmation(client, session_factory):
    with session_factory() as s:
        make_user(s, email="at031@example.com")
        movie = make_movie(s, title="確認チケット映画")
        sid = make_screening(s, movie_id=movie.id, seats_remaining=10).id
        s.commit()
    login(client, "at031@example.com")
    res = client.get("/tickets/new", params={"screening_id": sid})
    assert res.status_code == 200
    assert "確認チケット映画" in res.text  # 映画名
    assert "上映日時" in res.text  # 上映日時
    assert "券種" in res.text  # 券種
    assert "枚数" in res.text  # 枚数


@pytest.mark.acceptance(
    case_id="AT-032", requirement_id="CON-004", requirement_type="NON_FUNCTIONAL",
    title="座席指定を行わず残席数で購入する",
)
def test_at_032_no_seat_selection(client, session_factory):
    with session_factory() as s:
        make_user(s, email="at032@example.com")
        movie = make_movie(s, title="残席方式映画")
        sid = make_screening(s, movie_id=movie.id, seats_remaining=10).id
        s.commit()
    login(client, "at032@example.com")
    form = client.get("/tickets/new", params={"screening_id": sid})
    assert form.status_code == 200
    assert "残席" in form.text  # 残席数で扱う
    assert 'name="seat' not in form.text  # 個別座席指定を要求しない
    # 上映回と枚数のみで購入できる
    res = purchase_ticket(client, screening_id=sid, quantity=2)
    assert res.status_code == 200
