"""環境スモークテスト (本体テスト前の疎通確認)。"""

from __future__ import annotations

from datetime import timedelta


def test_smoke_guest_pages(client):
    assert client.get("/").status_code == 200
    assert client.get("/movies").status_code == 200
    assert client.get("/products").status_code == 200
    assert client.get("/register").status_code == 200
    assert client.get("/login").status_code == 200


def test_smoke_register_login_cart(client, db, factory):
    movie = factory.make_movie(db, title="スモーク映画")
    product = factory.make_product(db, name="スモーク商品", stock=5, movie_id=movie.id)

    resp = factory.register(client, name="太郎", email="smoke@example.com")
    assert resp.status_code == 200  # follows redirect to /register/complete

    # 追加
    csrf = factory.get_csrf(client, f"/products/{product.id}")
    add = client.post(
        "/cart/add",
        data={"product_id": product.id, "quantity": 2, "csrf_token": csrf},
    )
    assert add.status_code == 200
    cart = client.get("/cart")
    assert "スモーク商品" in cart.text
