# trace: NFR-SC-25, NFR-OM-17, NFR-EN-03, NFR-EN-07
# trace: FR-060, ADDR-004, ADDR-010, ADDR-011, ADDR-012
"""検証データの扱い・環境別設定・実行基盤の非依存性に関する非機能要件の結合試験。

期待結果は非機能要件定義書 8章（NFR-SC-25 本番以外の環境での利用）、6章（NFR-OM-17 設定変更の
容易さ）、10章（NFR-EN-03 実行基盤、NFR-EN-07 OS）の「要件内容」「目標値」「検証方法」欄、
および 12.1 検証環境（ENV-01）・12.2 検証データ条件（VDC-01・VDC-04 の「架空の値」）から導出する。

いずれも要件本文の検証方法は「構成・設定レビュー」または「運用テスト」であるが、レビュー対象の
うち app イメージの中に実体がある部分（初期データ定義ファイルの内容、環境変数で与える設定、
app のソースと実行時の設定）は、結合試験環境の中で機械的に判定できる。本番環境（ENV-02）の
構成・ホスト側のファイル（compose.yaml・README.md・.env.example）・移行計画などイメージに
同梱されない対象は判定せず、残る確認内容を
reports/integration-test/non-automatable-requirements.md へ申し送りとして記録している。
"""
import ast
import hashlib
import importlib.metadata
import importlib.util
import json
import os
import re
from io import StringIO
from pathlib import Path
from unittest import mock

import pytest
from django.conf import settings
from django.core.management import call_command
from django.db import connection

from shop.models import Supplier, User

pytestmark = pytest.mark.django_db

# app のソースツリーの根（コンテナ内では /app）。
APP_ROOT = Path(settings.BASE_DIR)

# 走査から除外するディレクトリ（第三者資産・キャッシュ・読取り専用マウント）。
EXCLUDED_DIRS = {
    "staticfiles",
    "__pycache__",
    ".ruff_cache",
    ".pytest_cache",
    "migrations",
    "tests",
    "reports",
}

# 本文を走査する対象の拡張子。
TEXT_SUFFIXES = {".py", ".html", ".css", ".js", ".json", ".toml", ".cfg", ".ini", ".txt"}

# 稼働開始時の初期データ定義ファイル（VDC-04 と同じ形式。NFR-SC-25 の検証方法が指す対象）。
SEED_DEFINITION = APP_ROOT / "seed" / "initial_data.json"

# 文書用に予約され、実在の利用者へ到達しないドメイン（RFC 2606 / RFC 6761。12.2 は example.com を指定）。
RESERVED_EMAIL_DOMAINS = {"example.com", "example.net", "example.org", "example.jp", "example.test", "invalid"}

# メールアドレス・電話番号・郵便番号の検出（本番の個人情報が混入していないことの判定に用いる）。
EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_PATTERN = re.compile(r"\b0\d{1,4}-\d{1,4}-\d{4}\b")
POSTAL_PATTERN = re.compile(r"\b\d{3}-\d{4}\b")

# 環境ごとに異なる設定（NFR-OM-17 の要件内容が列挙する項目）と、それを与える環境変数。
ENVIRONMENT_SETTINGS = {
    "DB_HOST": "DATABASES.default.HOST",
    "DB_PORT": "DATABASES.default.PORT",
    "DB_NAME": "DATABASES.default.NAME",
    "DB_USER": "DATABASES.default.USER",
    "DB_PASSWORD": "DATABASES.default.PASSWORD",
    "DJANGO_SECRET_KEY": "SECRET_KEY",
    "DJANGO_ALLOWED_HOSTS": "ALLOWED_HOSTS",
    "DJANGO_DEBUG": "DEBUG",
    "SESSION_COOKIE_SECURE": "SESSION_COOKIE_SECURE",
}

# 検証環境A・Bの環境変数（値はすべて架空。NFR-SC-25 に従い本番の資格情報は用いない）。
ENV_PROFILE_A = {
    "DB_HOST": "db-profile-a",
    "DB_PORT": "15432",
    "DB_NAME": "minicommerce_a",
    "DB_USER": "app_user_a",
    "DB_PASSWORD": "fictitious-password-a",
    "DJANGO_SECRET_KEY": "fictitious-secret-key-a-0123456789abcdef0123456789abcdef",
    "DJANGO_ALLOWED_HOSTS": "shop-a.example.com,shop-a2.example.com",
    "DJANGO_DEBUG": "true",
    "SESSION_COOKIE_SECURE": "false",
}
ENV_PROFILE_B = {
    "DB_HOST": "db-profile-b",
    "DB_PORT": "25432",
    "DB_NAME": "minicommerce_b",
    "DB_USER": "app_user_b",
    "DB_PASSWORD": "fictitious-password-b",
    "DJANGO_SECRET_KEY": "fictitious-secret-key-b-fedcba9876543210fedcba9876543210",
    "DJANGO_ALLOWED_HOSTS": "shop-b.example.com",
    "DJANGO_DEBUG": "false",
    "SESSION_COOKIE_SECURE": "true",
}

# ホスト OS 固有の絶対パス（NFR-EN-07：ホストの OS に依存しない）。
HOST_SPECIFIC_PATHS = (
    "/home/",
    "/Users/",
    "/root/",
    "/mnt/",
    "/media/",
    "/opt/",
    "/usr/local/lib/python",
    "/private/",
    "/var/tmp/",
)

# ドライブレター表記（Windows 固有のパス）。
DRIVE_LETTER_PATTERN = re.compile(r"\b[A-Za-z]:[\\/]{1,2}")

# 実行環境の種類で処理を分ける記述（NFR-EN-07：OS に依存しない）。
PLATFORM_BRANCH_PATTERN = re.compile(r"\bos\.name\b|\bsys\.platform\b|platform\.system\(|platform\.uname\(")

# 文字コードの既定値がホストの設定に左右される呼び出し（テキストモードでの読み書き）。
TEXT_IO_FUNCTIONS = {"open", "read_text", "write_text"}

# ファイルの位置を組み立てる呼び出し（引数の文字列がパス表記かどうかを判定する対象）。
PATH_FUNCTIONS = {"Path", "open", "join", "fspath", "read_text", "write_text"}

# app・db 以外の実行基盤サービスを示す設定名（NFR-EN-03：サービスは app・db の2つ）。
EXTRA_SERVICE_SETTINGS = re.compile(
    r"CELERY|BROKER|REDIS|MEMCACHED|RABBIT|KAFKA|ELASTICSEARCH|MONGO|DYNAMODB|AWS|AZURE|GCP|GOOGLE_CLOUD"
)

# 本番基盤（クラウド）固有の SDK（NFR-EN-03：本リリースの実装は本番基盤に依存しない）。
PLATFORM_SDK_PREFIXES = (
    "boto",
    "awscli",
    "google-cloud",
    "google-api",
    "azure",
    "oci",
    "aliyun",
    "ibm-cloud",
)

# app が要求してよいアプリケーション（Django 本体・DRF・本システムのみ）。
ALLOWED_APP_PREFIXES = ("django.", "rest_framework", "shop")

# 外部サービスを要さないキャッシュ方式（NFR-EN-03：app・db 以外のサービスを持たない）。
LOCAL_CACHE_BACKENDS = {
    "django.core.cache.backends.locmem.LocMemCache",
    "django.core.cache.backends.dummy.DummyCache",
    "django.core.cache.backends.filebased.FileBasedCache",
}


# trace: NFR-EN-07, NFR-EN-03
def _source_files(suffixes=None) -> list[Path]:
    """app イメージへ同梱されたソース・設定ファイルの一覧を返す。"""
    targets = suffixes or TEXT_SUFFIXES
    found = []
    for path in sorted(APP_ROOT.rglob("*")):
        if not path.is_file() or path.suffix not in targets:
            continue
        if set(path.relative_to(APP_ROOT).parts) & EXCLUDED_DIRS:
            continue
        found.append(path)
    return found


# trace: NFR-OM-17
def _load_settings(environment: dict[str, str]):
    """config/settings.py を指定した環境変数だけで読み込む（app の再起動に相当する）。"""
    spec = importlib.util.spec_from_file_location("settings_probe", APP_ROOT / "config" / "settings.py")
    module = importlib.util.module_from_spec(spec)
    with mock.patch.dict(os.environ, environment, clear=True):
        spec.loader.exec_module(module)
    return module


# trace: NFR-OM-17
def _setting_value(module, dotted: str):
    """ドット区切りの設定名（DATABASES.default.HOST など）の値を取り出す。"""
    parts = dotted.split(".")
    value = getattr(module, parts[0])
    for key in parts[1:]:
        value = value[key]
    return value


# trace: NFR-EN-07
def _text_io_calls(tree: ast.AST) -> list[ast.Call]:
    """テキストモードでファイルを読み書きする呼び出しを集める（バイナリモードは除く）。"""
    calls = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            name = node.func.attr
        else:
            continue
        if name not in TEXT_IO_FUNCTIONS:
            continue
        modes = [argument.value for argument in node.args if isinstance(argument, ast.Constant)]
        modes += [
            keyword.value.value
            for keyword in node.keywords
            if keyword.arg == "mode" and isinstance(keyword.value, ast.Constant)
        ]
        if any(isinstance(mode, str) and "b" in mode for mode in modes):
            continue
        calls.append(node)
    return calls


# trace: NFR-EN-07
def _path_literals(tree: ast.AST) -> list[tuple[int, str]]:
    """ファイルの位置を組み立てる呼び出しへ渡す文字列定数を集める。"""
    literals = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            name = node.func.attr
        else:
            continue
        if name not in PATH_FUNCTIONS:
            continue
        for argument in node.args:
            if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                literals.append((argument.lineno, argument.value))
    return literals


# trace: NFR-SC-25
def _emails_in(text: str) -> list[str]:
    """文字列に含まれるメールアドレスを返す。"""
    return EMAIL_PATTERN.findall(text)


# trace: NFR-SC-25, FR-060, ADDR-010, ADDR-012
@pytest.mark.case("IT-AI-GF-081")
def test_verification_data_is_fictitious_and_no_production_data_is_used():
    """初期データ定義ファイルと結合試験の接続先が架空の値・使い捨てDBに限られる（NFR-SC-25）。"""
    raw = SEED_DEFINITION.read_text(encoding="utf-8")
    definition = json.loads(raw)

    # 定義ファイルの全メールアドレスが、実在の利用者へ到達しない予約ドメインである（12.2 VDC-04）。
    emails = _emails_in(raw)
    assert emails, "初期データ定義ファイルにメールアドレスが含まれない（走査対象が誤っている）"
    for email in emails:
        domain = email.split("@")[1].lower()
        assert domain in RESERVED_EMAIL_DOMAINS, f"実在ドメインのメールアドレスが含まれる: {email}"
    assert {row["email"] for row in definition["users"]} == set(emails)

    # 本番の個人情報（電話番号・郵便番号・住所）を持ち込んでいない。
    assert PHONE_PATTERN.search(raw) is None, "初期データ定義ファイルに電話番号が含まれる"
    assert POSTAL_PATTERN.search(raw) is None, "初期データ定義ファイルに郵便番号が含まれる"
    assert set(definition) <= {"users", "suppliers", "collections", "items", "stock_units", "coupons"}
    for personal in ("shipping_addresses", "purchase_orders", "payment_records", "carts"):
        assert personal not in definition, f"個人情報を含む業務データが定義ファイルにある: {personal}"

    # 定義ファイルを実際に投入しても、登録されるのは架空の利用者だけである。
    out, err = StringIO(), StringIO()
    with pytest.raises(SystemExit) as exit_code:
        call_command("load_initial_data", str(SEED_DEFINITION), "--reset", stdout=out, stderr=err)
    assert int(exit_code.value.code) == 0, err.getvalue()
    assert User.objects.count() == len(definition["users"])
    for stored in User.objects.all():
        assert stored.email.split("@")[1].lower() in RESERVED_EMAIL_DOMAINS, stored.email
        assert PHONE_PATTERN.search(stored.full_name) is None
    assert Supplier.objects.count() == len(definition["suppliers"])

    # 結合試験が接続する DB は pytest-django が作る使い捨てのテストDBで、本番DBではない。
    test_database = connection.settings_dict["NAME"]
    configured = os.environ.get("DB_NAME", "minicommerce")
    assert test_database.startswith("test_"), f"使い捨てのテストDBではない: {test_database}"
    assert test_database == f"test_{configured}", f"想定外のDBへ接続している: {test_database}"
    assert connection.settings_dict["HOST"] in {"db", "localhost", "127.0.0.1"}, "ENV-01 以外の DB へ接続している"


# trace: NFR-OM-17, ADDR-004, ADDR-011
@pytest.mark.case("IT-AI-GF-082")
def test_environment_specific_settings_change_by_environment_variables_only():
    """環境ごとに異なる設定が環境変数の変更と再起動だけで切り替わる（NFR-OM-17 の目標値）。"""
    source = (APP_ROOT / "config" / "settings.py").read_bytes()
    digest_before = hashlib.sha256(source).hexdigest()

    profile_a = _load_settings(ENV_PROFILE_A)
    profile_b = _load_settings(ENV_PROFILE_B)

    # 列挙された設定項目がすべて環境変数の値を反映する。
    for variable, dotted in ENVIRONMENT_SETTINGS.items():
        value_a = _setting_value(profile_a, dotted)
        value_b = _setting_value(profile_b, dotted)
        assert value_a != value_b, f"{dotted} が環境変数 {variable} で変わらない"

    assert _setting_value(profile_a, "DATABASES.default.HOST") == ENV_PROFILE_A["DB_HOST"]
    assert _setting_value(profile_a, "DATABASES.default.PORT") == ENV_PROFILE_A["DB_PORT"]
    assert _setting_value(profile_a, "DATABASES.default.NAME") == ENV_PROFILE_A["DB_NAME"]
    assert _setting_value(profile_a, "DATABASES.default.USER") == ENV_PROFILE_A["DB_USER"]
    assert _setting_value(profile_a, "DATABASES.default.PASSWORD") == ENV_PROFILE_A["DB_PASSWORD"]
    assert profile_a.SECRET_KEY == ENV_PROFILE_A["DJANGO_SECRET_KEY"]
    assert profile_a.ALLOWED_HOSTS == ["shop-a.example.com", "shop-a2.example.com"]
    assert profile_a.DEBUG is True
    assert profile_a.SESSION_COOKIE_SECURE is False
    assert profile_a.CSRF_COOKIE_SECURE is False

    assert profile_b.ALLOWED_HOSTS == ["shop-b.example.com"]
    assert profile_b.DEBUG is False
    assert profile_b.SESSION_COOKIE_SECURE is True
    assert profile_b.CSRF_COOKIE_SECURE is True

    # 環境変数を与えない場合は安全側（デバッグ表示なし・ホスト限定）の既定値になる。
    default = _load_settings({})
    assert default.DEBUG is False
    assert default.SESSION_COOKIE_SECURE is False
    assert default.ALLOWED_HOSTS == ["localhost", "127.0.0.1"]

    # 設定の切り替えにプログラムの変更を伴わない（同一のソースのまま値だけが変わる）。
    assert hashlib.sha256((APP_ROOT / "config" / "settings.py").read_bytes()).hexdigest() == digest_before
    text = source.decode("utf-8")
    # 真偽値（true / false）は読み取り方の定義としてソースに現れるため、固有の値だけを照合する。
    boolean_variables = {"DJANGO_DEBUG", "SESSION_COOKIE_SECURE"}
    specific_values = [
        value
        for profile in (ENV_PROFILE_A, ENV_PROFILE_B)
        for variable, value in profile.items()
        if variable not in boolean_variables
    ]
    for value in specific_values:
        assert value not in text, f"環境固有の値がソースへ書かれている: {value}"
    for variable in ENVIRONMENT_SETTINGS:
        assert variable in text, f"{variable} を読み込んでいない"


# trace: NFR-EN-07, ADDR-004, ADDR-011
@pytest.mark.case("IT-AI-GF-083")
def test_application_source_does_not_depend_on_the_host_operating_system():
    """app のソース・設定がホスト OS 固有のパス・分岐・文字コード既定値に依存しない（NFR-EN-07）。"""
    scanned = _source_files()
    assert len(scanned) >= 50, f"走査対象が少なすぎる: {len(scanned)}件"

    for path in scanned:
        relative = path.relative_to(APP_ROOT)
        text = path.read_text(encoding="utf-8", errors="ignore")
        for marker in HOST_SPECIFIC_PATHS:
            assert marker not in text, f"{relative} にホスト固有の絶対パスがある: {marker}"
        drive = DRIVE_LETTER_PATTERN.search(text)
        assert drive is None, f"{relative} にドライブレター表記がある: {drive.group(0) if drive else ''}"

    for path in _source_files({".py"}):
        relative = path.relative_to(APP_ROOT)
        text = path.read_text(encoding="utf-8")
        branch = PLATFORM_BRANCH_PATTERN.search(text)
        assert branch is None, f"{relative} に実行環境による分岐がある: {branch.group(0) if branch else ''}"

        tree = ast.parse(text)
        for call in _text_io_calls(tree):
            keywords = {keyword.arg for keyword in call.keywords}
            assert "encoding" in keywords, f"{relative}:{call.lineno} が文字コードの既定値に依存している"
        # パス文字列にホスト OS の区切り文字（バックスラッシュ）を使っていない。
        for lineno, literal in _path_literals(tree):
            assert "\\" not in literal, f"{relative}:{lineno} のパス表記にバックスラッシュがある: {literal}"
            assert DRIVE_LETTER_PATTERN.search(literal) is None, f"{relative}:{lineno} にドライブレターがある"

    # ファイルの位置は実行時に解決した BASE_DIR から組み立てる（固定の絶対パスを持たない）。
    assert isinstance(settings.BASE_DIR, Path)
    assert settings.BASE_DIR.is_absolute()
    assert (settings.BASE_DIR / "manage.py").is_file()
    for configured in [settings.STATIC_ROOT, *settings.TEMPLATES[0]["DIRS"], *settings.STATICFILES_DIRS]:
        assert Path(configured).is_absolute()
        Path(configured).relative_to(settings.BASE_DIR)
    assert SEED_DEFINITION.is_file()
    assert "\\" not in str(SEED_DEFINITION)


# trace: NFR-EN-03, ADDR-011, ADDR-012
@pytest.mark.case("IT-AI-GF-084")
def test_runtime_requires_only_the_app_and_db_services_and_no_platform_sdk():
    """実行基盤が app・db の2サービスだけで成立し、本番基盤固有の製品に依存しない（NFR-EN-03）。"""
    # app が接続する実行基盤サービスは db の1つ（接続先は環境変数で与える）。
    assert set(settings.DATABASES) == {"default"}
    assert settings.DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql"
    assert connection.vendor == "postgresql"
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        assert cursor.fetchone() == (1,)

    # app・db 以外のサービス（キャッシュ・メッセージ基盤・外部ストレージ）を要求しない。
    for alias, config in settings.CACHES.items():
        assert config["BACKEND"] in LOCAL_CACHE_BACKENDS, f"{alias} が外部のキャッシュサービスを使う"
    assert settings.SESSION_ENGINE == "django.contrib.sessions.backends.db"
    assert settings.STORAGES["default"]["BACKEND"] == "django.core.files.storage.FileSystemStorage"
    assert "whitenoise" in settings.STORAGES["staticfiles"]["BACKEND"]
    extra = [name for name in dir(settings) if name.isupper() and EXTRA_SERVICE_SETTINGS.search(name)]
    assert extra == [], f"app・db 以外のサービスの設定がある: {extra}"
    for application in settings.INSTALLED_APPS:
        assert application.startswith(ALLOWED_APP_PREFIXES), f"追加のサービスを要するアプリがある: {application}"

    # 本番基盤（クラウド）固有の SDK を導入も参照もしていない。
    installed = sorted({(dist.metadata["Name"] or "").lower() for dist in importlib.metadata.distributions()})
    platform_sdk = [name for name in installed if name.startswith(PLATFORM_SDK_PREFIXES)]
    assert platform_sdk == [], f"本番基盤固有の SDK が導入されている: {platform_sdk}"
    for path in _source_files({".py"}):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            for name in names:
                root = name.split(".")[0].replace("_", "-")
                assert not root.startswith(PLATFORM_SDK_PREFIXES), f"{path.name} が {name} を参照している"

    # app は単一の WSGI アプリケーションとして提供する（起動するプロセスは app の1種類）。
    assert settings.WSGI_APPLICATION == "config.wsgi.application"
    assert (APP_ROOT / "config" / "wsgi.py").is_file()
    assert not (APP_ROOT / "config" / "celery.py").exists()
    assert not (APP_ROOT / "config" / "asgi.py").exists()
