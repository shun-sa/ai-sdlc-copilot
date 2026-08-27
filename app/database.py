from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    """全ORMエンティティの共通宣言ベース。"""


def create_db_engine(database_url: str) -> Engine:
    """接続先URLからEngineを生成する。SQLiteはテスト用in-memoryにも対応する。

    接続先はDIで注入され、コードへ固定ハードコードしない（ADR-003）。
    """
    connect_args: dict = {}
    engine_kwargs: dict = {}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        is_memory = ":memory:" in database_url or database_url in ("sqlite://", "sqlite:///:memory:")
        if is_memory:
            # 使い捨てin-memory DBを単一接続で共有し、テスト内で同一DBを参照する。
            engine_kwargs["poolclass"] = StaticPool

    engine = create_engine(database_url, connect_args=connect_args, **engine_kwargs)

    if database_url.startswith("sqlite"):
        _enable_sqlite_foreign_keys(engine)

    return engine


def _enable_sqlite_foreign_keys(engine: Engine) -> None:
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, class_=Session)


def create_all(engine: Engine) -> None:
    # モデル登録のため、メタデータ生成前に全モデルを読み込む。
    from app import models  # noqa: F401

    Base.metadata.create_all(engine)


def session_scope(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
