"""アプリケーション設定 (ADR-010 / ADR-004).

DB接続情報・セッション署名鍵/シークレット・Cookie属性は
すべて環境変数から注入する。コード/テストへハードコードしない。
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """環境変数から注入される設定値。

    本番DBエンドポイントやCredential、セッション機密は
    ソースへ埋め込まず、必ず環境から供給する (ADR-010)。
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # DB接続文字列 (例: postgresql+psycopg://user:pass@host:5432/dbname)
    # 既定値はローカル/テスト用の切替を容易にするためのプレースホルダであり、
    # 本番接続先ではない。実行時は環境変数 DATABASE_URL で上書きする。
    database_url: str = Field(
        default="postgresql+psycopg://cinema:cinema@localhost:5432/cinema",
    )

    # セッションCookie署名用シークレット (ADR-004)。
    # 本番では必ず環境変数 SECRET_KEY で強度の高い値を注入する。
    secret_key: str = Field(default="dev-insecure-secret-change-me")

    # Cookie属性 (ADR-004): HttpOnlyは常時True。
    session_cookie_name: str = "session_id"
    session_cookie_secure: bool = True
    session_cookie_samesite: str = "lax"
    session_max_age_seconds: int = 60 * 60 * 8  # 8時間

    # bcryptコストファクタ (ADR-006)
    bcrypt_rounds: int = 12

    # 一覧ページング標準件数 (NFR-PERF-003)
    page_size: int = 20


@lru_cache
def get_settings() -> Settings:
    """設定シングルトンを返す。"""
    return Settings()
