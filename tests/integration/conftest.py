"""結合試験 共通設定 / Fixture。

Presentation層 (routers) を通した結合試験を FastAPI TestClient (httpx) で実行する。

DBは ADR-010 に従い設定注入で使い捨てDB (in-memory SQLite / StaticPool) へ切り替える。
Production DB / Credential / Data は使用しない。
セッション署名鍵は実行時にランダム生成し設定注入する (ハードコードしない)。
Cookie Secure 属性はHTTPテストクライアントでも往復させるため設定注入で無効化する
(本番既定は Secure=True のまま。テスト環境限定の設定注入)。
"""

from __future__ import annotations

import os
import re
import secrets
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone

# --- 設定注入 (app import より前に実施 / ADR-010) ---------------------------
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("SECRET_KEY", secrets.token_urlsafe(32))
os.environ.setdefault("BCRYPT_ROUNDS", "4")
# テストクライアントは http のため Secure Cookie を往復させる目的で無効化する。
os.environ.setdefault("SESSION_COOKIE_SECURE", "false")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

import app.models  # noqa: E402,F401  (全モデルをメタデータへ登録)
from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.movie import Movie  # noqa: E402
from app.models.product import Product  # noqa: E402
from app.models.screening import Screening  # noqa: E402
from app.models.user import User  # noqa: E402
from app.security import hash_password  # noqa: E402


UTC = timezone.utc


def _now() -> datetime:
    return datetime.now(UTC)


@pytest.fixture()
def engine():
    """使い捨て in-memory SQLite エンジン (StaticPoolで全接続が同一DBを共有)。"""
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(bind=eng)
    yield eng
    Base.metadata.drop_all(bind=eng)
    eng.dispose()


@pytest.fixture()
def session_factory(engine):
    return sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        future=True,
    )


@pytest.fixture()
def db(session_factory) -> Iterator[Session]:
    """シード投入・検証用のセッション。"""
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(session_factory) -> Iterator[TestClient]:
    """get_db を使い捨てDBへ差し替えた TestClient。"""

    def override_get_db() -> Iterator[Session]:
        s = session_factory()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = override_get_db
    # https ベースURLで Secure Cookie を往復させる (本番Cookie属性を変えずに検証)。
    with TestClient(app, base_url="https://testserver") as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


# ============================================================
# データファクトリ
# ============================================================


def make_user(db: Session, *, name: str, email: str, password: str = "Passw0rd") -> User:
    user = User(name=name, email=email, password_hash=hash_password(password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def make_movie(
    db: Session,
    *,
    title: str,
    genre: str = "アクション",
    status: str = "published",
    release_date=None,
) -> Movie:
    movie = Movie(
        title=title,
        synopsis=f"{title} のあらすじ",
        genre=genre,
        release_date=release_date,
        runtime_minutes=120,
        status=status,
    )
    db.add(movie)
    db.commit()
    db.refresh(movie)
    return movie


def make_product(
    db: Session,
    *,
    name: str,
    price: int = 1980,
    stock: int = 10,
    publish_status: str = "published",
    category: str = "goods",
    movie_id: int | None = None,
    sales_start_at: datetime | None = None,
    sales_end_at: datetime | None = None,
) -> Product:
    product = Product(
        name=name,
        price_tax_included=price,
        stock=stock,
        publish_status=publish_status,
        category=category,
        movie_id=movie_id,
        sales_start_at=sales_start_at,
        sales_end_at=sales_end_at,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def make_screening(
    db: Session,
    *,
    movie_id: int,
    starts_at: datetime,
    seats_remaining: int = 50,
    theater_name: str = "シアター1",
    screen_name: str = "スクリーンA",
    sales_start_at: datetime | None = None,
    sales_end_at: datetime | None = None,
) -> Screening:
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


# ============================================================
# 認証・CSRF ヘルパ
# ============================================================

_CSRF_RE = re.compile(r'name="csrf_token"\s+value="([^"]+)"')


def get_csrf(client: TestClient, url: str) -> str:
    """指定URLをGETし、レンダリングされたCSRFトークンを抽出する。"""
    resp = client.get(url)
    match = _CSRF_RE.search(resp.text)
    assert match, f"CSRF token not found at {url} (status={resp.status_code})"
    return match.group(1)


def login(client: TestClient, email: str, password: str = "Passw0rd") -> None:
    """実際のログインエンドポイントを通じてセッションを確立する。"""
    csrf = get_csrf(client, "/login")
    resp = client.post(
        "/login",
        data={"email": email, "password": password, "csrf_token": csrf},
    )
    assert resp.status_code == 200, f"login failed: {resp.status_code}"


def register(
    client: TestClient,
    *,
    name: str,
    email: str,
    password: str = "Passw0rd",
) -> "object":
    """会員登録エンドポイントを通じて登録する。レスポンスを返す。"""
    csrf = get_csrf(client, "/register")
    return client.post(
        "/register",
        data={
            "name": name,
            "email": email,
            "password": password,
            "password_confirm": password,
            "csrf_token": csrf,
        },
    )


@pytest.fixture()
def factory():
    """テスト内からデータ生成/認証ヘルパへアクセスするための集約。"""

    class _F:
        make_user = staticmethod(make_user)
        make_movie = staticmethod(make_movie)
        make_product = staticmethod(make_product)
        make_screening = staticmethod(make_screening)
        get_csrf = staticmethod(get_csrf)
        login = staticmethod(login)
        register = staticmethod(register)
        now = staticmethod(_now)

    return _F()
