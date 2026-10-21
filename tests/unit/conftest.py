"""単体テストの共通設定とフィクスチャ。

DBを使うテストは pytest-django が作成する使い捨てのテストDB（Dockerコンテナ上の
PostgreSQL 16）だけを使用する。Production DB・共有DB・Production Data は使用しない。
"""

from __future__ import annotations

import datetime as dt

import pytest
from common import timeutils


@pytest.fixture
def buyer(db):
    """購入者1名（FR-002 以降のテストの前提）。"""
    from _helpers import make_user

    return make_user()


@pytest.fixture
def admin_user(db):
    """管理者1名。"""
    from _helpers import make_admin

    return make_admin()


@pytest.fixture
def fixed_now(monkeypatch):
    """処理時刻を固定する（境界値・日時の判定を決定論的にする）。"""

    def _fix(value: dt.datetime) -> dt.datetime:
        monkeypatch.setattr(timeutils, "now", lambda: value.replace(microsecond=0))
        return value.replace(microsecond=0)

    return _fix


@pytest.fixture
def api_client():
    """API 要求用のクライアント。"""
    from rest_framework.test import APIClient

    return APIClient()


@pytest.fixture
def screen_client():
    """画面要求用のクライアント。"""
    from django.test import Client

    return Client()


@pytest.fixture
def logged_in_screen_client(screen_client):
    """ログインセッションを開始した画面クライアントを返すファクトリ。"""

    def _login(user):
        session = screen_client.session
        session["login_user_id"] = user.pk
        session.save()
        return screen_client

    return _login


@pytest.fixture
def token_for(db, settings):
    """利用者の認証トークン（平文）を発行するファクトリ。"""
    settings.AUTH_TOKEN_RESOLVER = "accounts.services.resolve_auth_token"

    def _issue(user) -> str:
        from accounts.services import issue_token

        raw_token, _token = issue_token(user)
        return raw_token

    return _issue
