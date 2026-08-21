"""Unit Test 共通設定 / Fixture。

DBは ADR-010 に従い設定注入で使い捨てDB (in-memory SQLite) へ切り替える。
Production DB / Credential / Data は使用しない。
セッション署名鍵は実行時にランダム生成し設定注入する (ハードコードしない)。
"""

from __future__ import annotations

import os
import secrets
from collections.abc import Callable, Iterator
from datetime import datetime, timedelta, timezone

# --- 設定注入 (app import より前に実施) ---------------------------------
# ADR-010: 本番DBへ固定依存しない。使い捨てDBへ設定注入で切替。
os.environ.setdefault("DATABASE_URL", "sqlite://")
# ADR-004 / ADR-010: セッション機密はハードコードせず実行時に注入。
os.environ.setdefault("SECRET_KEY", secrets.token_urlsafe(32))
# ADR-006: bcrypt を維持しつつテスト高速化のためコストのみ下げる。
os.environ.setdefault("BCRYPT_ROUNDS", "4")

import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

import app.models  # noqa: E402,F401  (全モデルをメタデータへ登録)
from app.database import Base  # noqa: E402
from app.models.movie import Movie  # noqa: E402
from app.models.product import Product  # noqa: E402
from app.models.screening import Screening  # noqa: E402
from app.models.user import User  # noqa: E402
from app.payment import MockPaymentGateway, PaymentGateway  # noqa: E402
from app.security import hash_password  # noqa: E402


@pytest.fixture()
def db() -> Iterator[Session]:
    """使い捨て in-memory SQLite に対する独立したセッション。

    各テストごとにスキーマを再構築し破棄することで状態を隔離する
    (ADR-010: disposable / isolated)。
    """
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, future=True
    )
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def payment() -> PaymentGateway:
    """ADR-009: 常に成功する模擬決済。"""
    return MockPaymentGateway()


@pytest.fixture()
def now() -> datetime:
    return datetime.now(timezone.utc)


# --- ファクトリ Fixture ---------------------------------------------------


@pytest.fixture()
def make_user(db: Session) -> Callable[..., User]:
    def _make(
        *,
        name: str = "テスト会員",
        email: str | None = None,
        password: str = "password1",
        status: str = "active",
    ) -> User:
        email = email or f"user{secrets.token_hex(4)}@example.com"
        user = User(
            name=name,
            email=email,
            password_hash=hash_password(password),
            status=status,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    return _make


@pytest.fixture()
def make_movie(db: Session) -> Callable[..., Movie]:
    def _make(*, title: str = "サンプル映画", status: str = "published") -> Movie:
        movie = Movie(title=title, status=status)
        db.add(movie)
        db.commit()
        db.refresh(movie)
        return movie

    return _make


@pytest.fixture()
def make_product(db: Session) -> Callable[..., Product]:
    def _make(
        *,
        name: str = "サンプル商品",
        price: int = 1000,
        stock: int = 10,
        publish_status: str = "published",
        sales_start_at: datetime | None = None,
        sales_end_at: datetime | None = None,
        category: str = "",
        movie_id: int | None = None,
    ) -> Product:
        product = Product(
            name=name,
            price_tax_included=price,
            stock=stock,
            publish_status=publish_status,
            sales_start_at=sales_start_at,
            sales_end_at=sales_end_at,
            category=category,
            movie_id=movie_id,
        )
        db.add(product)
        db.commit()
        db.refresh(product)
        return product

    return _make


@pytest.fixture()
def make_screening(db: Session, make_movie: Callable[..., Movie]) -> Callable[..., Screening]:
    def _make(
        *,
        movie_id: int | None = None,
        starts_at: datetime | None = None,
        seats_remaining: int = 10,
        sales_start_at: datetime | None = None,
        sales_end_at: datetime | None = None,
        theater_name: str = "シアター1",
        screen_name: str = "スクリーンA",
    ) -> Screening:
        if movie_id is None:
            movie_id = make_movie().id
        if starts_at is None:
            starts_at = datetime.now(timezone.utc) + timedelta(days=1)
        screening = Screening(
            movie_id=movie_id,
            starts_at=starts_at,
            theater_name=theater_name,
            screen_name=screen_name,
            seats_remaining=seats_remaining,
            sales_start_at=sales_start_at,
            sales_end_at=sales_end_at,
        )
        db.add(screening)
        db.commit()
        db.refresh(screening)
        return screening

    return _make
