"""Implementation工程のスモーク確認用スクリプト（使い捨てin-memory DB / ADR-003）。

本番DB・本番Credential・本番データは使用しない。テスト設計は後続Test Agentの責務。
"""
from datetime import timedelta

from fastapi.testclient import TestClient

from app.config import Settings
from app.constants import MovieStatus, PublishStatus, TicketType
from app.main import create_app
from app.models.movie import Movie
from app.models.product import Product
from app.models.screening import Screening, ScreeningTicketPrice
from app.time_utils import now_utc


def seed(app):
    now = now_utc()
    with app.state.session_factory() as s:
        m = Movie(title="スモーク映画", synopsis="x", genre="ドラマ", status=MovieStatus.PUBLISHED)
        s.add(m)
        s.flush()
        p = Product(
            name="スモーク商品", price_tax_included=1980, stock=5,
            publish_status=PublishStatus.PUBLISHED,
            sales_start_at=now - timedelta(days=1), sales_end_at=now + timedelta(days=10),
            movie_id=m.id,
        )
        s.add(p)
        sc = Screening(
            movie_id=m.id, starts_at=now + timedelta(days=2), theater_name="T", screen_name="S1",
            seats_remaining=10, sales_start_at=now - timedelta(days=1), sales_end_at=now + timedelta(days=1),
        )
        s.add(sc)
        s.flush()
        s.add(ScreeningTicketPrice(screening_id=sc.id, ticket_type=TicketType.GENERAL, unit_price=1900))
        s.commit()
        return p.id, sc.id


def main():
    app = create_app(Settings(
        secret_key="smoke-test-key", database_url="sqlite://",
        session_cookie_name="session", cookie_secure=False, page_size=20,
    ))
    product_id, screening_id = seed(app)
    client = TestClient(app, follow_redirects=False)

    # 未認証でカートへ -> ログインへ遷移（C-AUTH-003）
    r = client.get("/cart")
    assert r.status_code == 303 and "/login" in r.headers["location"], r.status_code
    print("C-AUTH-003 redirect OK")

    # 会員登録（FR-001）
    r = client.post("/register", data={
        "name": "テスト太郎", "email": "taro@example.com",
        "password": "password123", "password_confirm": "password123",
    })
    assert r.status_code == 303, r.text
    assert app.state.settings.session_cookie_name in client.cookies
    print("FR-001 register OK")

    # 重複メール（ERR-001）
    r = client.post("/register", data={
        "name": "別人", "email": "taro@example.com",
        "password": "password123", "password_confirm": "password123",
    })
    assert r.status_code == 400
    print("ERR-001 duplicate email OK")

    # 認証失敗は汎用文言（ERR-002/NFR-SEC-006）
    fresh = TestClient(app, follow_redirects=False)
    r = fresh.post("/login", data={"email": "taro@example.com", "password": "wrongpass"})
    assert r.status_code == 401 and "正しくありません" in r.text
    print("ERR-002 generic auth failure OK")

    # 商品検索（FR-005）
    r = client.get("/products")
    assert r.status_code == 200 and "スモーク商品" in r.text
    print("FR-005 product search OK")

    # カート追加（FR-006） -> 注文確定（FR-008）
    r = client.post("/cart/add", data={"product_id": product_id, "quantity": 2})
    assert r.status_code == 303
    r = client.post("/orders", data={
        "recipient_name": "テスト太郎", "postal_code": "123-4567", "prefecture": "東京都",
        "city_address": "千代田区1-1", "phone": "0312345678", "payment_method": "CREDIT_CARD_MOCK",
    })
    assert r.status_code == 200 and "注文番号" in r.text, r.status_code
    print("FR-006/FR-008 order OK")

    # 在庫確認: 5 - 2 = 3
    with app.state.session_factory() as s:
        assert s.get(Product, product_id).stock == 3
    print("NFR-AVL-001 stock decrement OK")

    # チケット購入（FR-009）
    r = client.post("/tickets", data={
        "screening_id": screening_id, "ticket_type": "GENERAL",
        "quantity": 3, "payment_method": "CREDIT_CARD_MOCK",
    })
    assert r.status_code == 200 and "購入番号" in r.text, r.status_code
    with app.state.session_factory() as s:
        assert s.get(Screening, screening_id).seats_remaining == 7
    print("FR-009 ticket purchase OK")

    # 在庫不足でロールバック（ERR-003/ERR-005）
    r = client.post("/cart/add", data={"product_id": product_id, "quantity": 99})
    assert r.status_code == 409, r.status_code
    print("ERR-003 stock shortage OK")

    # 購入履歴（FR-010）
    r = client.get("/history")
    assert r.status_code == 200 and "注文番号" in r.text and "購入番号" in r.text
    print("FR-010 history OK")

    print("\nALL SMOKE CHECKS PASSED")


if __name__ == "__main__":
    main()
