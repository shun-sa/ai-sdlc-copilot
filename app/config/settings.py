# trace: ADDR-002, ADDR-004, ADDR-005, ADDR-007, ADDR-008, ADDR-011, ADDR-012
"""MiniCommerce の Django 設定。

環境ごとに異なる値（DB 接続・秘密鍵・Cookie の Secure 属性・ログ水準）は
すべて環境変数から読み込む（ADDR-004 DD-006）。既定値に秘密情報を書かない。
"""
import os
import secrets
from pathlib import Path

# trace: ADDR-004
BASE_DIR = Path(__file__).resolve().parent.parent


# trace: ADDR-004
def _env_bool(name: str, default: bool = False) -> bool:
    """環境変数を真偽値として読み込む。"""
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


# trace: ADDR-004
def _env_list(name: str, default: str = "") -> list[str]:
    """環境変数をカンマ区切りの一覧として読み込む。"""
    raw = os.environ.get(name) or default
    return [value.strip() for value in raw.split(",") if value.strip()]


# 秘密鍵は環境変数で与える（NFR-SC-07）。未設定時はプロセス起動ごとの一時値を生成し、
# ソースコードへ固定値を埋め込まない。
# trace: ADDR-011
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY") or secrets.token_urlsafe(64)

# trace: ADDR-011
DEBUG = _env_bool("DJANGO_DEBUG", False)

# trace: ADDR-011
ALLOWED_HOSTS = _env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")

# trace: ADDR-004
INSTALLED_APPS = [
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "rest_framework",
    "shop",
]

# 共通ミドルウェアはミドルウェア列の最外側に置く（ADDR-005 4.3）。
# trace: ADDR-005, ADDR-011
MIDDLEWARE = [
    "shop.common.middleware.RequestLogMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# trace: ADDR-004
ROOT_URLCONF = "config.urls"

# trace: ADDR-004
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "shop" / "web" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "shop.web.context_processors.layout",
            ],
            "libraries": {
                "display": "shop.web.templatetags.display",
            },
        },
    },
]

# trace: ADDR-011
WSGI_APPLICATION = "config.wsgi.application"

# DB 接続情報はすべて環境変数から読み込む。テスト実行時は pytest-django が
# 同一接続情報で test_<DB_NAME> を作成・破棄する（使い捨てテストDB）。
# コンテナ内のテスト実行では compose の既定値（DB_HOST=db、DB_PORT=5432）を用い、
# 本番DB・本番資格情報へは接続しない（ADDR-012 DD-005、INV-006）。
# trace: ADDR-004, ADDR-012
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "HOST": os.environ.get("DB_HOST", "localhost"),
        "PORT": os.environ.get("DB_PORT", "5432"),
        "NAME": os.environ.get("DB_NAME", "minicommerce"),
        "USER": os.environ.get("DB_USER", "minicommerce"),
        "PASSWORD": os.environ.get("DB_PASSWORD", ""),
        "CONN_MAX_AGE": int(os.environ.get("DB_CONN_MAX_AGE", "0")),
        "TEST": {"NAME": os.environ.get("TEST_DB_NAME", "")} if os.environ.get("TEST_DB_NAME") else {},
    }
}

# trace: ADDR-004
DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

# パスワードは Django 標準の PBKDF2-HMAC-SHA256（既定反復回数）で保存する（ADDR-008 DD-001）。
# trace: ADDR-008
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

# 画面のログインセッションは DB セッション（ADDR-002 DD-005）。
# trace: ADDR-002
SESSION_ENGINE = "django.contrib.sessions.backends.db"
# trace: ADDR-002
SESSION_COOKIE_HTTPONLY = True
# trace: ADDR-002
SESSION_COOKIE_SECURE = _env_bool("SESSION_COOKIE_SECURE", False)
# trace: ADDR-002
SESSION_COOKIE_SAMESITE = "Lax"
# trace: ADDR-002
SESSION_COOKIE_AGE = 1800
# trace: ADDR-002
SESSION_SAVE_EVERY_REQUEST = True
# trace: ADDR-002
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

# trace: ADDR-002
CSRF_COOKIE_SECURE = _env_bool("SESSION_COOKIE_SECURE", False)
# trace: ADDR-002
CSRF_COOKIE_HTTPONLY = False

# trace: ADDR-004
LANGUAGE_CODE = "ja"
# trace: ADDR-004
TIME_ZONE = "Asia/Tokyo"
# trace: ADDR-004
USE_I18N = False
# trace: ADDR-004
USE_TZ = True

# trace: ADDR-011
STATIC_URL = "static/"
# trace: ADDR-011
STATIC_ROOT = BASE_DIR / "staticfiles"
# trace: ADDR-011
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# 業務エラーの応答生成は単一の例外ハンドラへ集約する（ADDR-007 DD-002）。
# 権限判定の既定は拒否とし、認証不要のエンドポイント（api-contract 6.1 の
# register・login・collections・items・item-detail）だけが各ビューで明示的に許可する（VUL-01）。
# trace: ADDR-002, ADDR-007
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["shop.api.authentication.ApiTokenAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["shop.api.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "EXCEPTION_HANDLER": "shop.common.exception_handler.api_exception_handler",
    "UNAUTHENTICATED_USER": None,
}

# アプリケーションログは標準出力へ JSON Lines で出力する（ADDR-005 DD-001、DD-006）。
# trace: ADDR-005
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json_lines": {"()": "shop.common.logging.JsonLinesFormatter"},
    },
    "filters": {
        "request_context": {"()": "shop.common.logging.RequestContextFilter"},
    },
    "handlers": {
        "stdout": {
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
            "formatter": "json_lines",
            "filters": ["request_context"],
        },
    },
    "root": {
        "handlers": ["stdout"],
        "level": os.environ.get("DJANGO_LOG_LEVEL", "INFO"),
    },
    "loggers": {
        "django": {"handlers": ["stdout"], "level": os.environ.get("DJANGO_LOG_LEVEL", "INFO"), "propagate": False},
    },
}

# 決済ゲートウェイの実装は設定で選択する。既定は模擬実装（ADDR-009 4.3）。
# trace: ADDR-009
PAYMENT_GATEWAY = os.environ.get("PAYMENT_GATEWAY", "mock")
# trace: ADDR-009
PAYMENT_TIMEOUT_SECONDS = float(os.environ.get("PAYMENT_TIMEOUT_SECONDS", "10"))
