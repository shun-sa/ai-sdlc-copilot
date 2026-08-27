"""結合試験共通ヘルパー。

ADR-003 に従い、テストは使い捨ての in-memory SQLite を使用し、
Production DB / Credential / Data を一切使用しない。
Test Data は各テストが独立して投入する。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from app.constants import (
    MovieStatus,
    OrderStatus,
    PaymentMethod,
    PublishStatus,
    TicketType,
    UserStatus,
)
from app.models.movie import Movie
from app.models.order import Order, OrderItem
from app.models.product import Product
from app.models.screening import Screening, ScreeningTicketPrice
from app.models.ticket import TicketPurchase, TicketPurchaseItem
from app.models.user import User
from app.security import hash_password

UTC = timezone.utc

DEFAULT_PASSWORD = "password123"


# --------------------------------------------------------------------------
# Data 生成ヘルパー
# --------------------------------------------------------------------------


def make_user(
    session: Session,
    *,
    email: str = "member@example.com",
    name: str = "会員太郎",
    password: str = DEFAULT_PASSWORD,
    status: UserStatus = UserStatus.ACTIVE,
) -> User:
    user = User(
        name=name,
        email=email,
        password_hash=hash_password(password),
        status=status,
    )
    session.add(user)
    session.flush()
    return user


def make_movie(
    session: Session,
    *,
    title: str = "サンプル映画",
    genre: str = "アクション",
    synopsis: str = "あらすじ本文",
    status: MovieStatus = MovieStatus.PUBLISHED,
    release_date: datetime | None = None,
    runtime_minutes: int | None = 120,
) -> Movie:
    movie = Movie(
        title=title,
        genre=genre,
        synopsis=synopsis,
        status=status,
        release_date=release_date.date() if isinstance(release_date, datetime) else release_date,
        runtime_minutes=runtime_minutes,
    )
    session.add(movie)
    session.flush()
    return movie


def make_product(
    session: Session,
    *,
    name: str = "パンフレット",
    price: int = 1980,
    stock: int = 10,
    publish_status: PublishStatus = PublishStatus.PUBLISHED,
    sales_start_at: datetime | None = None,
    sales_end_at: datetime | None = None,
    movie_id: int | None = None,
) -> Product:
    now = datetime.now(UTC)
    product = Product(
        name=name,
        price_tax_included=price,
        stock=stock,
        publish_status=publish_status,
        sales_start_at=sales_start_at if sales_start_at is not None else now - timedelta(days=1),
        sales_end_at=sales_end_at if sales_end_at is not None else now + timedelta(days=30),
        movie_id=movie_id,
    )
    session.add(product)
    session.flush()
    return product


def make_screening(
    session: Session,
    *,
    movie_id: int,
    starts_at: datetime | None = None,
    seats_remaining: int = 20,
    sales_start_at: datetime | None = None,
    sales_end_at: datetime | None = None,
    prices: dict[TicketType, int] | None = None,
) -> Screening:
    now = datetime.now(UTC)
    screening = Screening(
        movie_id=movie_id,
        starts_at=starts_at if starts_at is not None else now + timedelta(days=3),
        theater_name="シアター1",
        screen_name="スクリーンA",
        seats_remaining=seats_remaining,
        sales_start_at=sales_start_at if sales_start_at is not None else now - timedelta(days=1),
        sales_end_at=sales_end_at if sales_end_at is not None else now + timedelta(days=2),
    )
    session.add(screening)
    session.flush()
    price_map = prices or {
        TicketType.GENERAL: 1900,
        TicketType.STUDENT: 1500,
        TicketType.SENIOR: 1200,
    }
    for ticket_type, unit_price in price_map.items():
        session.add(
            ScreeningTicketPrice(
                screening_id=screening.id,
                ticket_type=ticket_type,
                unit_price=unit_price,
            )
        )
    session.flush()
    return screening


def make_order(
    session: Session,
    *,
    user_id: int,
    order_number: str,
    items: list[tuple[int, str, int, int]],
    ordered_at: datetime | None = None,
    payment_method: PaymentMethod = PaymentMethod.CREDIT_CARD_MOCK,
) -> Order:
    """items は (product_id, snapshot_name, unit_price, quantity) のリスト。"""
    total = sum(unit_price * qty for _, _, unit_price, qty in items)
    order = Order(
        order_number=order_number,
        user_id=user_id,
        ordered_at=ordered_at if ordered_at is not None else datetime.now(UTC),
        status=OrderStatus.CONFIRMED,
        shipping_address="〒100-0001 東京都千代田区1-1",
        recipient_name="会員太郎",
        postal_code="100-0001",
        prefecture="東京都",
        city_address="千代田区1-1",
        phone="03-1234-5678",
        payment_method=payment_method,
        total_amount=total,
    )
    for product_id, name, unit_price, qty in items:
        order.items.append(
            OrderItem(
                product_id=product_id,
                product_snapshot_name=name,  # ADR-008: 確定時点スナップショット
                unit_price=unit_price,
                quantity=qty,
                subtotal=unit_price * qty,
            )
        )
    session.add(order)
    session.flush()
    return order


def make_ticket_purchase(
    session: Session,
    *,
    user_id: int,
    purchase_number: str,
    screening_id: int,
    movie_title: str,
    starts_at: datetime,
    ticket_type: TicketType = TicketType.GENERAL,
    unit_price: int = 1900,
    quantity: int = 1,
    purchased_at: datetime | None = None,
) -> TicketPurchase:
    purchase = TicketPurchase(
        purchase_number=purchase_number,
        user_id=user_id,
        purchased_at=purchased_at if purchased_at is not None else datetime.now(UTC),
        total_amount=unit_price * quantity,
    )
    purchase.items.append(
        TicketPurchaseItem(
            screening_id=screening_id,
            movie_title_snapshot=movie_title,
            screening_starts_at_snapshot=starts_at,
            ticket_type=ticket_type,
            unit_price=unit_price,
            quantity=quantity,
            subtotal=unit_price * quantity,
        )
    )
    session.add(purchase)
    session.flush()
    return purchase


# --------------------------------------------------------------------------
# HTTP 操作ヘルパー
# --------------------------------------------------------------------------


def register(
    client: TestClient,
    *,
    name: str = "登録太郎",
    email: str = "new@example.com",
    password: str = "Passw0rd",
    password_confirm: str | None = None,
    follow_redirects: bool = True,
):
    return client.post(
        "/register",
        data={
            "name": name,
            "email": email,
            "password": password,
            "password_confirm": password_confirm if password_confirm is not None else password,
        },
        follow_redirects=follow_redirects,
    )


def login(
    client: TestClient,
    email: str,
    password: str = DEFAULT_PASSWORD,
    *,
    follow_redirects: bool = True,
):
    return client.post(
        "/login",
        data={"email": email, "password": password},
        follow_redirects=follow_redirects,
    )


def logout(client: TestClient, *, follow_redirects: bool = True):
    return client.post("/logout", follow_redirects=follow_redirects)


def add_to_cart(client: TestClient, product_id: int, quantity: int = 1, *, follow_redirects: bool = True):
    return client.post(
        "/cart/add",
        data={"product_id": product_id, "quantity": quantity},
        follow_redirects=follow_redirects,
    )


def update_cart_item(client: TestClient, item_id: int, quantity: int, *, follow_redirects: bool = True):
    return client.post(
        f"/cart/items/{item_id}",
        data={"quantity": quantity},
        follow_redirects=follow_redirects,
    )


def place_order(
    client: TestClient,
    *,
    recipient_name: str = "配送太郎",
    postal_code: str = "100-0001",
    prefecture: str = "東京都",
    city_address: str = "千代田区1-1-1",
    phone: str = "03-1234-5678",
    payment_method: str = PaymentMethod.CREDIT_CARD_MOCK.value,
    follow_redirects: bool = True,
):
    return client.post(
        "/orders",
        data={
            "recipient_name": recipient_name,
            "postal_code": postal_code,
            "prefecture": prefecture,
            "city_address": city_address,
            "phone": phone,
            "payment_method": payment_method,
        },
        follow_redirects=follow_redirects,
    )


def purchase_ticket(
    client: TestClient,
    *,
    screening_id: int,
    ticket_type: str = TicketType.GENERAL.value,
    quantity: int = 1,
    payment_method: str = PaymentMethod.CREDIT_CARD_MOCK.value,
    follow_redirects: bool = True,
):
    return client.post(
        "/tickets",
        data={
            "screening_id": screening_id,
            "ticket_type": ticket_type,
            "quantity": quantity,
            "payment_method": payment_method,
        },
        follow_redirects=follow_redirects,
    )


# --------------------------------------------------------------------------
# 検証ヘルパー
# --------------------------------------------------------------------------


def cart_item_id_of(session: Session, user_id: int, product_id: int) -> int | None:
    from app.repositories.cart_repository import CartRepository

    carts = CartRepository(session)
    cart = carts.get_cart(user_id)
    if cart is None:
        return None
    item = carts.get_item(cart.id, product_id)
    return item.id if item is not None else None
