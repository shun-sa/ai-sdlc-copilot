"""結合試験の共通フィクスチャ。

使い捨て in-memory SQLite（StaticPool）でアプリ全体を構築し、
starlette TestClient で HTTP 境界から DB までの結合を検証する（ADR-003）。
Production DB / Credential / Data は一切使用しない。
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from sqlalchemy.orm import Session, sessionmaker
from starlette.testclient import TestClient

from app.config import Settings
from app.main import create_app


def _test_settings() -> Settings:
    return Settings(
        secret_key="integration-test-secret-key-not-production",
        database_url="sqlite://",  # 使い捨て in-memory（StaticPoolで単一接続共有）
        session_cookie_name="session",
        cookie_secure=False,
        page_size=20,
    )


@pytest.fixture()
def app() -> Iterator[FastAPI]:
    application = create_app(_test_settings())
    try:
        yield application
    finally:
        application.state.engine.dispose()


@pytest.fixture()
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def raw_client(app: FastAPI) -> Iterator[TestClient]:
    """サーバー例外を伝播させずレスポンス化するクライアント（ロールバック検証用）。"""
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture()
def session_factory(app: FastAPI) -> sessionmaker[Session]:
    """テスト側でのデータ投入・状態検証に使うセッションファクトリ。"""
    return app.state.session_factory
