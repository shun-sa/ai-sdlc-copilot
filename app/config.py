import os
from dataclasses import dataclass

# 開発用のデフォルト値。Production環境ではAPP_SECRET_KEY/DATABASE_URLを必ず環境変数で上書きする。
_DEV_SECRET_KEY = "dev-insecure-secret-key-do-not-use-in-production"
_DEV_DATABASE_URL = "sqlite:///./app.db"


@dataclass(frozen=True)
class Settings:
    secret_key: str
    database_url: str
    session_cookie_name: str
    cookie_secure: bool
    page_size: int


def load_settings() -> Settings:
    return Settings(
        secret_key=os.environ.get("APP_SECRET_KEY", _DEV_SECRET_KEY),
        database_url=os.environ.get("DATABASE_URL", _DEV_DATABASE_URL),
        session_cookie_name=os.environ.get("SESSION_COOKIE_NAME", "session"),
        cookie_secure=os.environ.get("COOKIE_SECURE", "false").lower() == "true",
        page_size=int(os.environ.get("PAGE_SIZE", "20")),
    )
