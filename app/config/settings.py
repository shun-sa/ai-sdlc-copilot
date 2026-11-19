# trace: ADDR-014, ADDR-011, ADDR-012, ADDR-002, ADDR-003, ADDR-006, ADDR-013, ADDR-001
"""MiniCommerce の単一の設定モジュール（ADDR-014 4.3 の1）。

全ての設定値は環境変数から読み取る。秘密鍵・DB 接続の利用者名・パスワードは既定値を持たない。
本番プロファイル（MINICOMMERCE_ENV=production）では安全側の設定を起動時に強制する。
"""

from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

from config import env

BASE_DIR = Path(__file__).resolve().parent.parent

# --- 環境・本番プロファイル（ADDR-014 DD-002・DD-011、ADDR-011 DD-001） ---
MINICOMMERCE_ENV = env.read_environment_name()
IS_PRODUCTION = MINICOMMERCE_ENV == env.ENV_PRODUCTION

SECRET_KEY = env.read_required("DJANGO_SECRET_KEY")
DEBUG = env.read_bool("DJANGO_DEBUG")
MINICOMMERCE_DEV_FEATURES = env.read_bool("MINICOMMERCE_DEV_FEATURES")

if IS_PRODUCTION and DEBUG:
    raise ImproperlyConfigured("DJANGO_DEBUG must not be true when MINICOMMERCE_ENV=production.")
if IS_PRODUCTION and MINICOMMERCE_DEV_FEATURES:
    raise ImproperlyConfigured("MINICOMMERCE_DEV_FEATURES must not be true when MINICOMMERCE_ENV=production.")

ALLOWED_HOSTS = env.read_list(
    "DJANGO_ALLOWED_HOSTS",
    [] if IS_PRODUCTION else ["localhost", "127.0.0.1"],
)

# --- アプリケーション構成（ADDR-012 DD-001・DD-010：管理サイトを含めない） ---
INSTALLED_APPS = [
    # accounts は createsuperuser・changepassword を置き換えるため django.contrib.auth より前に置く
    "accounts",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "common",
    "audit",
    "catalog",
    "promotions",
    "carts",
    "orders",
    "payments",
    "initial_data",
]
if MINICOMMERCE_DEV_FEATURES:
    # 試験支援モジュールは開発用機能フラグが true のときだけ組み込む（ADDR-011 DD-001）
    INSTALLED_APPS.append("test_support")

MIDDLEWARE = [
    "common.middleware.RequestIdMiddleware",
    "common.middleware.AccessLogMiddleware",
    "common.middleware.HttpsOnlyMiddleware",
    "common.middleware.RequestCharsetMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "common.middleware.IdleTimeoutMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "common.middleware.WebExceptionMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            # 自動エスケープは既定どおり有効（ADDR-012 DD-007）
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "common.context_processors.site_header",
                # 共通表示（UI-05）の合計点数は FR-020 の業務処理を持つ carts が供給する（ADDR-001 4.3 の14 r4）
                "carts.context_processors.header_cart_count",
            ],
        },
    },
]

# --- データベース（ADDR-014 DD-007、ADDR-011 DD-006：環境変数だけで接続先を切り替える） ---
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "HOST": env.read_optional("DB_HOST", "localhost"),
        "PORT": env.read_optional("DB_PORT", "5432"),
        "NAME": env.read_optional("DB_NAME", "minicommerce"),
        "USER": env.read_required("DB_USER"),
        "PASSWORD": env.read_required("DB_PASSWORD"),
        "ATOMIC_REQUESTS": False,  # トランザクション境界は業務処理層で明示する（ADDR-004 4.3 の1）
        "CONN_MAX_AGE": 0,
        "TEST": {"NAME": None},  # pytest-django が test_ で始まる使い捨ての試験用データベースを作成・破棄する
    }
}

# システム付与識別子は64ビット整数の自動採番（ADDR-006 DD-001）
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- 認証・セッション（ADDR-002、ADDR-003、ADDR-012 DD-011） ---
AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = ["accounts.backends.SessionUserBackend"]
# ADDR-003 r2 DD-001・DD-006：独自方式名 pbkdf2_sha256_sha256hex のハッシャー1件だけを置く。
# Django 標準の PBKDF2・PBKDF2SHA1・Scrypt 等を置かない（旧方式名 pbkdf2_sha256 の保持値は照合不成立・移行しない）
PASSWORD_HASHERS = ["accounts.hashers.PBKDF2SHA256HexKeyPasswordHasher"]
AUTH_PASSWORD_VALIDATORS: list[dict] = []
LOGIN_URL = "/login/"

# データベース保持（django.contrib.sessions.backends.db）にセッションキーの文字検査を加えたもの
SESSION_ENGINE = "common.sessions"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 60 * 60 * 24  # 無操作30分の判定は IdleTimeoutMiddleware が判定時刻で行う
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_FAILURE_VIEW = "common.views.csrf_failure"
MESSAGE_STORAGE = "django.contrib.messages.storage.session.SessionStorage"

# 本番では Secure Cookie・HSTS を有効にし、HTTPS でない要求を業務処理の前に拒否する（ADDR-014 DD-003）
SESSION_COOKIE_SECURE = IS_PRODUCTION
CSRF_COOKIE_SECURE = IS_PRODUCTION
SECURE_HSTS_SECONDS = 31536000 if IS_PRODUCTION else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = IS_PRODUCTION
SECURE_PROXY_SSL_HEADER = env.read_proxy_ssl_header("MINICOMMERCE_TRUSTED_PROXY_SSL_HEADER")
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
# HTTPS への自動転送は行わず HttpsOnlyMiddleware で拒否するため、転送設定の推奨警告は対象外とする
SILENCED_SYSTEM_CHECKS = ["security.W008"]

# --- Web API（ADDR-001、ADDR-002 INV-003：Cookie セッション認証を有効にしない） ---
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["accounts.authentication.BearerAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["common.parsers.JsonBodyParser"],
    "EXCEPTION_HANDLER": "common.api.exception_handler",
    # OPTIONS のメタデータ（ビュー名・説明文）を返さない。OPTIONS は許可しないメソッド（405）とする（NFR-SC-10）
    "DEFAULT_METADATA_CLASS": None,
    "UNAUTHENTICATED_USER": "django.contrib.auth.models.AnonymousUser",
}

# --- 国際化・日時（NFR-EN-04：Asia/Tokyo・UTF-8） ---
LANGUAGE_CODE = "ja"
TIME_ZONE = "Asia/Tokyo"
USE_I18N = True
USE_TZ = True
DEFAULT_CHARSET = "utf-8"

# --- 静的ファイル（ADDR-014 DD-005：WhiteNoise でアプリケーションから配信） ---
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR.parent / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
if DEBUG or MINICOMMERCE_DEV_FEATURES:
    # 開発・試験時は collectstatic なしでも静的ファイルを参照できるようにする
    STORAGES["staticfiles"] = {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}
    WHITENOISE_USE_FINDERS = True

# --- ログ（ADDR-013：1行1件の JSON を標準出力へ。既定ロガーの出力を置き換える） ---
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"json": {"()": "common.logging.JsonFormatter"}},
    "handlers": {
        "stdout": {
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
            "formatter": "json",
        },
        "null": {"class": "logging.NullHandler"},
    },
    "loggers": {
        "minicommerce": {"handlers": ["stdout"], "level": "INFO", "propagate": False},
        "django": {"handlers": ["null"], "level": "INFO", "propagate": False},
        "django.request": {"handlers": ["null"], "level": "ERROR", "propagate": False},
        "django.server": {"handlers": ["null"], "level": "INFO", "propagate": False},
        "django.security": {"handlers": ["null"], "level": "INFO", "propagate": False},
    },
    "root": {"handlers": ["stdout"], "level": "WARNING"},
}
