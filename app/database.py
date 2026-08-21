"""DBエンジン/セッション管理 (ADR-002 / ADR-010).

接続文字列は設定注入 (config) 経由でのみ受け取り、
テスト時はDATABASE_URLの差し替えでDockerコンテナ等の
使い捨てDBへ接続できる。本番DBへ固定依存しない。
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    """全ORMモデルの基底クラス。"""


def _build_engine():
    settings = get_settings()
    connect_args: dict = {}
    # SQLite（テスト簡便化用の代替）を使う場合のみ必要な引数を付与する。
    if settings.database_url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
        future=True,
        connect_args=connect_args,
    )


engine = _build_engine()

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    future=True,
)


def get_db() -> Iterator[Session]:
    """リクエストスコープのDBセッションを供給するDI関数。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_all() -> None:
    """全テーブルを作成する (テストDB/初期化用)。

    ORM (ADR-002) のメタデータからスキーマを再現するため、
    Dockerコンテナ等の使い捨てDBに対して同一スキーマを再構築できる。
    """
    # モデル定義を確実に読み込む
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)
