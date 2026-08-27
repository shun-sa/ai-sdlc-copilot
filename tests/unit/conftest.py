"""Unit Test 共通フィクスチャ。

ADR-003 に従い、テストは使い捨ての in-memory SQLite を使用し、
Production DB / Credential / Data を一切使用しない。
各テストごとに独立した DB を生成し、テスト間で状態を共有しない。
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from app.constants import (
    MovieStatus,
    PublishStatus,
    TicketType,
    UserStatus,
)
from app.database import create_all, create_db_engine, create_session_factory
from app.models.movie import Movie
from app.models.product import Product
from app.models.screening import Screening, ScreeningTicketPrice
from app.models.user import User
from app.security import hash_password

UTC = timezone.utc


@pytest.fixture()
def db_session() -> Iterator[Session]:
    """使い捨て in-memory SQLite の Session を提供する（テストごとに独立）。"""
    engine = create_db_engine("sqlite://")
    create_all(engine)
    factory = create_session_factory(engine)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


# --------------------------------------------------------------------------
# データ生成ヘルパー（Test Data は各テストが独立して投入する）
# --------------------------------------------------------------------------


def make_user(
    session: Session,
    *,
    email: str = "member@example.com",
    name: str = "会員太郎",
    password: str = "password123",
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
    status: MovieStatus = MovieStatus.PUBLISHED,
) -> Movie:
    movie = Movie(title=title, genre=genre, synopsis="あらすじ", status=status)
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
