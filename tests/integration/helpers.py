"""結合試験 共通ヘルパ。

conftest.py は変更禁止のため、フロー操作/データ生成の補助関数を本モジュールへ集約する。
Presentation層(ルーター)経由の操作を httpx TestClient で行い、
DB検証用のモデル生成は使い捨てDBセッションへ直接行う。
"""

from __future__ import annotations

import re
import uuid
from datetime import timedelta

from app.models.order import Order, OrderItem
from app.models.ticket import TicketPurchase, TicketPurchaseItem

_CSRF_RE = re.compile(r'name="csrf_token"\s+value="([^"]+)"')

VALID_SHIPPING = {
    "name": "注文太郎",
    "postal_code": "100-0001",
    "prefecture": "東京都",
    "address_line": "千代田1-1-1",
    "phone": "03-1234-5678",
}


def csrf(client, url: str) -> str:
    resp = client.get(url)
    match = _CSRF_RE.search(resp.text)
    assert match, f"csrf token not found at {url} (status={resp.status_code})"
    return match.group(1)


# ---- 認証フロー -----------------------------------------------------------


def register(client, *, name: str, email: str, password: str = "Passw0rd", confirm=None):
    token = csrf(client, "/register")
    return client.post(
        "/register",
        data={
            "name": name,
            "email": email,
            "password": password,
            "password_confirm": confirm if confirm is not None else password,
            "csrf_token": token,
        },
    )


def login(client, email: str, password: str = "Passw0rd"):
    token = csrf(client, "/login")
    return client.post(
        "/login",
        data={"email": email, "password": password, "csrf_token": token},
    )


# ---- カート/注文/チケット操作 --------------------------------------------


def add_to_cart(client, product_id: int, quantity, from_url: str | None = None):
    url = from_url or f"/products/{product_id}"
    token = csrf(client, url)
    return client.post(
        "/cart/add",
        data={"product_id": product_id, "quantity": quantity, "csrf_token": token},
        follow_redirects=False,
    )


def update_cart_item(client, item_id: int, quantity):
    token = csrf(client, "/cart")
    return client.post(
        f"/cart/items/{item_id}",
        data={"quantity": quantity, "csrf_token": token},
        follow_redirects=False,
    )


def place_order(client, *, payment_method: str = "mock_credit_card", **override):
    token = csrf(client, "/orders/new")
    data = {**VALID_SHIPPING, "payment_method": payment_method, "csrf_token": token}
    data.update(override)
    return client.post("/orders", data=data, follow_redirects=False)


def purchase_ticket(
    client,
    screening_id: int,
    *,
    ticket_type: str = "general",
    quantity: int = 1,
    payment_method: str = "mock_credit_card",
    csrf_url: str | None = None,
):
    # 非販売上映回は購入フォーム(csrf)が描画されないため、同一セッションの
    # 別ページからcsrfを取得できるようにする(サーバー側拒否の検証用)。
    token = csrf(client, csrf_url or f"/tickets/screenings/{screening_id}")
    return client.post(
        "/tickets",
        data={
            "screening_id": screening_id,
            "ticket_type": ticket_type,
            "quantity": quantity,
            "payment_method": payment_method,
            "csrf_token": token,
        },
        follow_redirects=False,
    )


# ---- 日時ヘルパ -----------------------------------------------------------


def future(factory, hours: int = 72):
    return factory.now() + timedelta(hours=hours)


def past(factory, hours: int = 72):
    return factory.now() - timedelta(hours=hours)


# ---- 履歴データ直接生成 (他会員データ/履歴表示検証用) ---------------------


def make_order(db, user, *, items):
    """items: list[(product, quantity)] を購入時点スナップショットで注文化する。"""
    order_items = []
    total = 0
    for product, quantity in items:
        subtotal = product.price_tax_included * quantity
        total += subtotal
        order_items.append(
            OrderItem(
                product_id=product.id,
                product_snapshot_name=product.name,
                unit_price=product.price_tax_included,
                quantity=quantity,
                subtotal=subtotal,
            )
        )
    order = Order(
        order_number=f"ORD-{uuid.uuid4().hex[:12].upper()}",
        user_id=user.id,
        status="confirmed",
        shipping_address="〒100-0001 東京都千代田1-1 直接生成 03-1234-5678",
        payment_method="mock_credit_card",
        total_amount=total,
        items=order_items,
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


def make_ticket_purchase(
    db, user, screening, movie, *, ticket_type: str = "general", quantity: int = 1, unit_price: int = 1800
):
    subtotal = unit_price * quantity
    purchase = TicketPurchase(
        purchase_number=f"TKT-{uuid.uuid4().hex[:12].upper()}",
        user_id=user.id,
        total_amount=subtotal,
        items=[
            TicketPurchaseItem(
                screening_id=screening.id,
                ticket_type=ticket_type,
                unit_price=unit_price,
                quantity=quantity,
                subtotal=subtotal,
                movie_title_snapshot=movie.title,
                screening_starts_at_snapshot=screening.starts_at,
                theater_name_snapshot=screening.theater_name,
            )
        ],
    )
    db.add(purchase)
    db.commit()
    db.refresh(purchase)
    return purchase
