# trace: ADDR-001, ADDR-002, ADDR-006, ADDR-007, ADDR-009, ADDR-010, ADDR-011
"""MiniCommerce の Django 設定。

環境ごとに異なる値（デバッグ表示・許可ホスト名・Cookie の Secure 属性・DB 接続情報・
秘密鍵・決済ゲートウェイ実装）はすべて環境変数から読み取る（NFR-OM-17、NFR-SC-07）。
"""

import os
from pathlib import Path

from django.core.management.utils import get_random_secret_key

BASE_DIR = Path(__file__).resolve().parent.parent

TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
FALSE_VALUES = frozenset({"0", "false", "no", "off"})


# trace: ADDR-006
def env_flag(name: str, *, default: bool) -> bool:
    """環境変数を真偽値として読み取る。

    未設定・空・解釈できない値の場合は ``default`` を返す（ADDR-006 INV-005）。
    """
    raw = os.environ.get(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in TRUE_VALUES:
        return True
    if value in FALSE_VALUES:
        return False
    return default


# trace: ADDR-001
def env_list(name: str, *, default: str = "") -> list[str]:
    """カンマ区切りの環境変数を文字列の一覧として読み取る。"""
    raw = os.environ.get(name) or default
    return [item.strip() for item in raw.split(",") if item.strip()]


# trace: ADDR-001
def env_int(name: str, *, default: int) -> int:
    """環境変数を整数として読み取る（解釈できない場合は既定値）。"""
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw.strip())
    except ValueError:
        return default


# セキュリティ -----------------------------------------------------------------
# 秘密鍵はソースコードへ埋め込まず、環境変数から読み取る（NFR-SC-07）。
# 未設定の場合は起動のたびに使い捨ての鍵を生成する（運用では必ず環境変数で与える）。
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY") or get_random_secret_key()

# デバッグ表示は既定で無効（ADDR-011 DD-006、NFR-SC-10）。
DEBUG = env_flag("DJANGO_DEBUG", default=False)

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", default="localhost,127.0.0.1")

# Cookie の Secure 属性は未設定・空・解釈不能時に真（付与）とする（ADDR-006 DD-003）。
SECURE_COOKIES = env_flag("DJANGO_SECURE_COOKIES", default=True)

SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = SECURE_COOKIES
SESSION_COOKIE_AGE = 1800
SESSION_SAVE_EVERY_REQUEST = True
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = SECURE_COOKIES

# アプリケーション ---------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "rest_framework",
    "common",
    "accounts",
    "catalog",
    "carts",
    "orders",
    "payments",
    "seeding",
    "web",
]

MIDDLEWARE = [
    "common.middleware.RequestLogMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "web" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.template.context_processors.static",
                "web.context_processors.layout",
            ],
        },
    },
]

# データベース -------------------------------------------------------------------
# 接続情報はすべて環境変数から解決する（テスト時は同じ設定で使い捨てのテストDBを作成する）。
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "minicommerce"),
        "USER": os.environ.get("POSTGRES_USER", "minicommerce"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
        "HOST": os.environ.get("POSTGRES_HOST", "db"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        "ATOMIC_REQUESTS": False,
        "TEST": {
            "NAME": os.environ.get("POSTGRES_TEST_DB") or None,
        },
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# パスワードは Django 標準の PBKDF2-HMAC-SHA256 で保存する（ADDR-002 DD-001）。
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

# 認証トークンの解決先（common は機能アプリを import しないため設定で結び付ける）。
AUTH_TOKEN_RESOLVER = "accounts.services.resolve_auth_token"
AUTH_TOKEN_LIFETIME_HOURS = 24

# 決済ゲートウェイ（注文側は実装を直接参照しない。ADDR-009 DD-002, DD-003）。
PAYMENT_GATEWAY = os.environ.get("PAYMENT_GATEWAY") or "payments.mock.MockPaymentGateway"
PAYMENT_TIMEOUT_SECONDS = env_int("PAYMENT_TIMEOUT_SECONDS", default=10)

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "common.authentication.BearerTokenAuthentication",
    ],
    # 既定は拒否（ログイン必須）とし、認証不要のAPIだけが明示的に許可を上書きする（VUL-01、NFR-SC-03）。
    "DEFAULT_PERMISSION_CLASSES": [
        "common.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
    ],
    "UNAUTHENTICATED_USER": None,
    "EXCEPTION_HANDLER": "common.exception_handler.api_exception_handler",
}

# 国際化・日時 -------------------------------------------------------------------
LANGUAGE_CODE = "ja"
TIME_ZONE = "Asia/Tokyo"
USE_I18N = False
USE_TZ = True
DEFAULT_CHARSET = "utf-8"

# 静的ファイル（外部CDNを使わず本システムから配信する。ADDR-010 DD-004）。
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "web" / "static"]

# 静的ファイルを本アプリケーションから配信するか（前段のWebサーバーが配信する環境では
# 環境変数で無効化し、不要な配信経路を結線しない。VUL-08、NFR-EN-08）。
SERVE_STATIC_FILES = env_flag("DJANGO_SERVE_STATIC", default=True)

# ログ（標準出力へ JSON Lines。ADDR-007 DD-001, DD-002）。
LOG_LEVEL = os.environ.get("DJANGO_LOG_LEVEL", "INFO").strip().upper() or "INFO"
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json_lines": {
            "()": "common.logging.JsonLinesFormatter",
        },
    },
    # 応答確定後にフレームワークが出力する 4xx/5xx のログ行にも相関IDを付ける（ADDR-007 INV-003）。
    "filters": {
        "request_id": {
            "()": "common.logging.RequestIdFilter",
        },
    },
    "handlers": {
        "stdout": {
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
            "formatter": "json_lines",
            "filters": ["request_id"],
        },
    },
    "root": {
        "handlers": ["stdout"],
        "level": LOG_LEVEL,
    },
    "loggers": {
        "django": {
            "handlers": ["stdout"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "minicommerce": {
            "handlers": ["stdout"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
    },
}
