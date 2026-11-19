# trace: NFR-PF-12, NFR-AV-01, NFR-SC-28, NFR-SC-13, NFR-SC-14, NFR-SC-17, NFR-LG-04, NFR-SC-27, NFR-AV-10
# trace: NFR-LG-10, NFR-EN-03, NFR-OM-05, NFR-EN-08, NFR-EN-07, NFR-SC-21, NFR-EN-10, NFR-EN-12, NFR-EN-11
# trace: NFR-PF-16, NFR-SC-25, NFR-OM-19, NFR-LG-03
# trace: ADDR-001, ADDR-002, ADDR-003, ADDR-004, ADDR-008, ADDR-009, ADDR-010, ADDR-011, ADDR-012, ADDR-014
"""結合試験：AI GAP_FILL（Required Coverage Revision 4。NFR のうちリポジトリ内の成果物・実行環境で確かめられる範囲）。

GF-044〜GF-058（origin=AI_GENERATED、generation_stage=GAP_FILL）。AI INITIAL は変更しない。
FULL Traceability C10（NFR 60件にテスト到達なし）への対応で、各 NFR の要件本文・測定条件・
検証方法を読み直して導出した。
- 要件が「該当なし」と定める NFR（NFR-PF-12・NFR-SC-28・NFR-SC-13・NFR-SC-14・NFR-SC-17・
  NFR-SC-27・NFR-AV-10・NFR-LG-10・NFR-LG-04）は、要件の根拠に書かれた前提（バッチ・ファイル
  アップロード・多要素認証・アカウントロック・パスワード変更・送信元単位の制限・外部の決済サービス・
  特定商取引法の表記の機能が無い）だけを確認する。要件の合否は判定しない。
- 構成・設定レビュー／静的解析を検証方法とする NFR は、リポジトリの起動定義・依存の固定・設定値・
  手順書・ソースコードから確かめられる部分だけを確認する（本番環境・運用記録・法令判断・ブラウザ操作は
  確認しない。nfr-verification-scope.json に記録）。
定義ファイル・認証情報はすべて架空の値で作る。
"""

import ast
import io
import json
import os
import re
import runpy
import subprocess
import sys
from contextlib import contextmanager
from importlib import metadata
from pathlib import Path

import pytest
from django.core.management import execute_from_command_line

from tests.integration._helpers import PASSWORD, add_item, api, body, error_of, form_fields, order_of, pay, text

APP_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = APP_DIR.parent
_SKIP_DIRS = {"tests", "migrations", "__pycache__", ".pytest_cache", ".ruff_cache", "staticfiles"}
_REQ_LINE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([^\s\\]+)\s*\\?\s*$")
_HASH_LINE = re.compile(r"^\s+--hash=sha256:[0-9a-f]{64}\s*\\?\s*$")
_DIGEST = r"@sha256:[0-9a-f]{64}"


# trace: NFR-PF-12, NFR-EN-03, NFR-OM-05, NFR-EN-08, ADDR-014
def _compose():
    """compose.yaml を Docker Compose 自身の解釈で JSON にする（変数は展開しない。秘密情報を渡さない）。"""
    completed = subprocess.run(
        ["docker", "compose", "-f", str(REPO_DIR / "compose.yaml"), "config", "--format", "json", "--no-interpolate"],
        cwd=REPO_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


# trace: NFR-SC-21, NFR-EN-10, NFR-EN-12, NFR-PF-12, NFR-EN-03, ADDR-014
def _pinned(name):
    """pip-compile が生成した requirements*.txt の固定（名前→(版, ハッシュ数)）。固定でない行があれば失敗にする。"""
    pins = {}
    current = None
    for line in (APP_DIR / name).read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        matched = _REQ_LINE.match(line)
        if matched:
            current = matched.group(1).lower().replace("_", "-")
            pins[current] = [matched.group(2), 0]
            continue
        assert _HASH_LINE.match(line) and current is not None, f"{name}: 版固定・ハッシュ以外の行 {line!r}"
        pins[current][1] += 1
    return {key: (version, hashes) for key, (version, hashes) in pins.items()}


# trace: NFR-SC-28, NFR-EN-07, NFR-AV-10, NFR-LG-10, ADDR-014
def _production_sources():
    """Production Code（app/ のうち試験・マイグレーションを除く .py）。"""
    for path in sorted(APP_DIR.rglob("*.py")):
        if not _SKIP_DIRS.intersection(path.relative_to(APP_DIR).parts[:-1]):
            yield path


# trace: NFR-EN-07, NFR-AV-10, NFR-LG-10, ADDR-014
def _imports(path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module.split(".")[0])
    return names


# trace: NFR-SC-13, NFR-SC-17, NFR-LG-04, ADDR-001, ADDR-012
def _url_patterns(resolver=None, prefix=""):
    from django.urls import URLPattern, URLResolver, get_resolver

    for entry in (resolver or get_resolver()).url_patterns:
        if isinstance(entry, URLResolver):
            yield from _url_patterns(entry, prefix + str(entry.pattern))
        elif isinstance(entry, URLPattern):
            yield prefix + str(entry.pattern)


# trace: NFR-OM-19, ADDR-010
def _cli(capsys, *args):
    """`manage.py load_initial_data ...` を実行し (終了コード, 標準出力) を返す。"""
    capsys.readouterr()
    code = 0
    try:
        execute_from_command_line(["manage.py", "load_initial_data", *args])
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
    return code, capsys.readouterr().out


# trace: NFR-OM-05, NFR-EN-08, ADDR-014
@contextmanager
def _without_connection_reset():
    """WSGI 処理の要求開始・終了の接続の整理を一時停止する（試験のトランザクションを保つ）。"""
    from django.core.signals import request_finished, request_started
    from django.db import close_old_connections

    request_started.disconnect(close_old_connections)
    request_finished.disconnect(close_old_connections)
    try:
        yield
    finally:
        request_started.connect(close_old_connections)
        request_finished.connect(close_old_connections)


# trace: NFR-OM-05, NFR-EN-08, ADDR-014
def _call_wsgi(application, path):
    environ = {
        "REQUEST_METHOD": "GET",
        "PATH_INFO": path,
        "QUERY_STRING": "",
        "SERVER_NAME": "localhost",
        "SERVER_PORT": "8000",
        "HTTP_HOST": "localhost",
        "SERVER_PROTOCOL": "HTTP/1.1",
        "wsgi.input": io.BytesIO(b""),
        "wsgi.errors": sys.stderr,
        "wsgi.url_scheme": "http",
        "wsgi.version": (1, 0),
        "wsgi.multithread": False,
        "wsgi.multiprocess": True,
        "wsgi.run_once": False,
    }
    status = {}

    def start_response(value, headers, exc_info=None):
        status["value"] = value
        return lambda data: None

    with _without_connection_reset():
        chunks = application(environ, start_response)
        content = b"".join(chunks)
        if hasattr(chunks, "close"):
            chunks.close()
    return int(status["value"].split()[0]), content.decode("utf-8")


# trace: NFR-PF-12, NFR-AV-01, ADDR-014
def test_gf_044_no_scheduled_batch(settings):
    """GF-044 定期的に実行するバッチ処理・定期ジョブの定義が無い（NFR-PF-12 の前提、NFR-AV-01 の代替確認の一部）。"""
    from django.core.management import get_commands

    compose = _compose()
    assert set(compose["services"]) == {"app", "db"}
    start = " ".join(compose["services"]["app"]["command"])
    assert re.fullmatch(
        r"sh -c python manage\.py migrate --noinput && python manage\.py collectstatic --noinput --verbosity 0"
        r" && exec gunicorn --config gunicorn\.conf\.py",
        start,
    ), start
    assert "command" not in compose["services"]["db"] and "entrypoint" not in compose["services"]["db"]
    dockerfile = (APP_DIR / "Dockerfile").read_text(encoding="utf-8")
    assert not re.search(r"cron|crontab|systemd|supervisor|schedul", dockerfile, re.I)

    scheduler_packages = {
        "celery", "django-celery-beat", "apscheduler", "django-apscheduler", "django-crontab", "django-cron",
        "django-q", "django-q2", "rq", "rq-scheduler", "django-rq", "huey", "schedule", "dramatiq", "arq", "kombu",
    }
    pinned = set(_pinned("requirements.txt")) | set(_pinned("requirements-dev.txt"))
    assert pinned & scheduler_packages == set()
    assert not [a for a in settings.INSTALLED_APPS if re.search(r"celery|cron|schedul|django_q|huey|django_rq", a)]

    project_commands = {
        name: app for name, app in get_commands().items() if not app.startswith(("django", "rest_framework"))
    }
    # 運用者・試験者が手動で実行する初期データ一括投入・試験用状態と、無効化した Django 付属の2コマンドだけ
    assert project_commands == {
        "changepassword": "accounts",
        "createsuperuser": "accounts",
        "load_initial_data": "initial_data",
        "test_state": "test_support",
    }


# trace: NFR-SC-28, ADDR-001, ADDR-012
def test_gf_045_no_file_upload(api_client, buyer, bearer, catalog, settings):
    """GF-045 画面・API にファイルをアップロードする機能が無い（NFR-SC-28 の前提）。"""
    from django.apps import apps
    from django.core.files.uploadedfile import SimpleUploadedFile
    from django.db import models
    from django.utils.module_loading import import_string

    from accounts.models import User
    from carts.models import CartItem

    file_fields = [
        f"{model._meta.label}.{field.name}"
        for model in apps.get_models()
        for field in model._meta.get_fields()
        if isinstance(field, models.FileField)
    ]
    assert file_fields == []
    for template in sorted(APP_DIR.glob("*/templates/**/*.html")):
        content = template.read_text(encoding="utf-8").lower()
        assert 'type="file"' not in content and "multipart/form-data" not in content, template
    uses_files = []
    for path in _production_sources():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        if any(isinstance(node, ast.Attribute) and node.attr == "FILES" for node in ast.walk(tree)):
            uses_files.append(str(path.relative_to(APP_DIR)))
    assert uses_files == []
    parsers = [import_string(p) for p in settings.REST_FRAMEWORK["DEFAULT_PARSER_CLASSES"]]
    assert [p.media_type for p in parsers] == ["application/json"]

    users_before = User.objects.count()
    upload = SimpleUploadedFile("evil.html", b"<script>alert(1)</script>", content_type="text/html")
    registered = api_client.post(
        "/api/auth/register/",
        {"email": "upload@example.test", "password": PASSWORD, "password_confirmation": PASSWORD, "name": "添付 太郎",
         "attachment": upload},
        format="multipart",
    )
    assert registered.status_code == 400 and error_of(registered)["type"] == "input_error"
    assert User.objects.count() == users_before

    unit = catalog.stock_unit(stock=5)
    token = bearer(buyer)
    upload = SimpleUploadedFile("cart.csv", b"stock_unit_id,quantity\n1,1\n", content_type="text/csv")
    added = api_client.post(
        "/api/cart/items/", {"stock_unit_id": unit.pk, "quantity": 1, "file": upload}, format="multipart",
        HTTP_AUTHORIZATION=token,
    )
    assert added.status_code == 400 and error_of(added)["type"] == "input_error"
    assert CartItem.objects.count() == 0


# trace: NFR-SC-13, NFR-SC-14, ADDR-002, ADDR-003
def test_gf_046_single_factor_login_without_lockout(api_client, web, buyer):
    """GF-046 メールアドレス＋パスワードだけでログインが完了し、失敗を続けてもロックしない。

    NFR-SC-13・NFR-SC-14 の「該当なし」の前提。
    """
    from audit.models import AuditLog

    def failures():
        return AuditLog.objects.filter(event_type="login_failure", target_user_id=buyer.pk).count()

    before = failures()
    for _ in range(10):
        wrong = api(api_client, "post", "/api/auth/login/", data={"email": buyer.email, "password": "Wrong0Pass9"})
        assert wrong.status_code == 401 and error_of(wrong)["type"] == "authentication_failed"
    ok = api(api_client, "post", "/api/auth/login/", data={"email": buyer.email, "password": PASSWORD})
    assert ok.status_code == 200
    assert set(body(ok)) == {"token", "expires_at", "user"}  # 追加の認証要素を求める項目・状態が無い
    me = api(api_client, "get", "/api/auth/me/", f"Bearer {body(ok)['token']}")
    assert me.status_code == 200 and body(me)["email"] == buyer.email

    client = web()
    page = text(client.get("/login/"))
    form = re.search(r'<form\b[^>]*action="/login/"[^>]*>(.*?)</form>', page, re.S).group(1)
    visible = sorted(
        re.search(r'name="([^"]+)"', tag).group(1)
        for tag in re.findall(r"<input\b[^>]*>", form)
        if 'type="hidden"' not in tag and 'type="submit"' not in tag and "name=" in tag
    )
    assert visible == ["email", "password"]
    for _ in range(10):
        fields = form_fields(text(client.get("/login/")), "/login/")
        fields.update({"email": buyer.email, "password": "Wrong0Pass9"})
        assert client.post("/login/", fields).status_code == 401
    fields = form_fields(text(client.get("/login/")), "/login/")
    fields.update({"email": buyer.email, "password": PASSWORD})
    logged_in = client.post("/login/", fields)
    assert logged_in.status_code == 302 and logged_in["Location"] == "/"
    assert client.get("/cart/").status_code == 200

    assert failures() - before == 20
    assert AuditLog.objects.filter(event_type="login_success", target_user_id=buyer.pk).count() == 2


# trace: NFR-SC-13, NFR-SC-17, NFR-LG-04, ADDR-001, ADDR-012
def test_gf_047_out_of_scope_functions_absent(api_client, web, buyer):
    """GF-047 多要素認証・パスワードの変更／再設定・特定商取引法の表記の要求先が無い。

    NFR-SC-13・NFR-SC-17・NFR-LG-04 の「該当なし」の前提。
    """
    from django.core.management import call_command
    from django.core.management.base import CommandError

    from accounts.models import User

    patterns = list(_url_patterns())
    assert len(patterns) >= 40
    forbidden = re.compile(r"password|passwd|reset|otp|mfa|2fa|two.?factor|totp|tokushoho|tokutei|legal|law", re.I)
    assert [p for p in patterns if forbidden.search(p)] == []
    client = web()
    for path in ("/password_change/", "/password_reset/", "/accounts/password/reset/", "/mfa/", "/tokushoho/"):
        assert client.get(path).status_code == 404, path
    for path in ("/api/auth/password/", "/api/auth/password-reset/", "/api/auth/mfa/", "/api/auth/otp/"):
        assert api(api_client, "post", path, data={"email": buyer.email}).status_code == 404, path

    stored = User.objects.get(pk=buyer.pk).password
    with pytest.raises(CommandError):
        call_command("changepassword", buyer.email)
    assert User.objects.get(pk=buyer.pk).password == stored

    for template in sorted(APP_DIR.glob("*/templates/**/*.html")):
        assert "特定商取引" not in template.read_text(encoding="utf-8"), template


# trace: NFR-SC-27, ADDR-001
def test_gf_048_no_per_source_rate_limit(api_client, web, catalog, settings):
    """GF-048 同一の送信元からの連続要求を送信元単位で制限しない（NFR-SC-27 の前提）。"""
    catalog.stock_unit(catalog.product("連続要求確認"))
    assert not {k for k in settings.REST_FRAMEWORK if "THROTTLE" in k}
    assert not [m for m in settings.MIDDLEWARE if re.search(r"throttl|ratelimit|rate_limit", m, re.I)]
    statuses = [api(api_client, "get", "/api/products/", None).status_code for _ in range(120)]
    client = web()
    statuses += [client.get("/").status_code for _ in range(60)]
    unknown = {"email": "nobody@example.test", "password": "Wrong0Pass9"}
    statuses += [api(api_client, "post", "/api/auth/login/", data=unknown).status_code for _ in range(30)]
    assert statuses.count(429) == 0
    assert statuses[:180] == [200] * 180 and statuses[180:] == [401] * 30


# trace: NFR-AV-10, NFR-LG-10, ADDR-008
def test_gf_049_payment_is_in_process_mock(api_client, buyer, bearer, catalog):
    """GF-049 決済サービスは本システム内の模擬機能で、外部の決済サービスへの接続の設定・手段を持たない。

    NFR-AV-10・NFR-LG-10 の「該当なし」の前提（外部通信0件は GF-015 で確認）。
    """
    from orders.models import PaymentRecord
    from payments.gateway import get_gateway
    from payments.mock import MockPaymentGateway

    gateway = get_gateway()
    assert type(gateway) is MockPaymentGateway
    assert Path(sys.modules[type(gateway).__module__].__file__).resolve().is_relative_to(APP_DIR / "payments")

    network = {"socket", "ssl", "http", "urllib", "urllib3", "requests", "httpx", "aiohttp", "smtplib", "grpc"}
    for path in sorted((APP_DIR / "payments").glob("*.py")):
        assert _imports(path) & network == set(), path
    pinned = set(_pinned("requirements.txt"))
    assert pinned & {"requests", "httpx", "aiohttp", "urllib3", "stripe", "paypalrestsdk", "grpcio"} == set()
    example = (REPO_DIR / ".env.example").read_text(encoding="utf-8")
    keys = {line.split("=", 1)[0] for line in example.splitlines() if line and not line.startswith("#") and "=" in line}
    assert not [k for k in keys if re.search(r"PAY|GATEWAY|MERCHANT|API_KEY|ENDPOINT|URL", k)]

    unit = catalog.stock_unit(price=1200, stock=5)
    token = bearer(buyer)
    order = order_of(api_client, token, [(unit, 1)])
    paid = pay(api_client, token, order["order_id"], "approved")
    assert paid.status_code == 200 and body(paid)["status"] == "paid"
    refs = list(PaymentRecord.objects.filter(order_id=order["order_id"]).values_list("result", "transaction_ref"))
    assert len(refs) == 1 and refs[0][0] == "approved" and re.fullmatch(r"MOCK-[A-Za-z0-9]{16}", refs[0][1])


# trace: NFR-EN-03, NFR-OM-05, NFR-EN-08, ADDR-014
def test_gf_050_compose_single_start_gunicorn(catalog):
    """GF-050 1回の起動操作で app・db を起動する定義、起動は Gunicorn、WSGI が商品一覧画面を返す。"""
    compose = _compose()
    services = compose["services"]
    assert set(services) == {"app", "db"}
    assert re.fullmatch(r"postgres:16" + _DIGEST, services["db"]["image"])
    assert "pg_isready" in " ".join(services["db"]["healthcheck"]["test"])
    app = services["app"]
    assert app["build"]["dockerfile"] == "app/Dockerfile"
    assert app["depends_on"] == {"db": {"condition": "service_healthy", "required": True}}
    assert app["environment"]["DB_HOST"] == "db"
    start = app["command"][-1]
    steps = [step.strip() for step in start.split("&&")]
    assert steps == [
        "python manage.py migrate --noinput",
        "python manage.py collectstatic --noinput --verbosity 0",
        "exec gunicorn --config gunicorn.conf.py",
    ]
    assert [p["target"] for p in app["ports"]] == [8000]
    assert "runserver" not in json.dumps(compose)

    dockerfile = (APP_DIR / "Dockerfile").read_text(encoding="utf-8")
    instructions = [line for line in dockerfile.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    assert not [line for line in instructions if "runserver" in line]
    cmd = [line for line in instructions if line.startswith("CMD ")]
    assert len(cmd) == 1 and "exec gunicorn --config gunicorn.conf.py" in cmd[0]
    conf = runpy.run_path(str(APP_DIR / "gunicorn.conf.py"))
    assert (conf["wsgi_app"], conf["bind"], conf["worker_class"]) == ("config.wsgi:application", "0.0.0.0:8000", "sync")
    assert "gunicorn" in _pinned("requirements.txt")
    cloud = re.compile(r"^(boto3?|botocore|aws|google-cloud|google-api|azure|django-storages|oci|ibm-)")
    pinned = set(_pinned("requirements.txt")) | set(_pinned("requirements-dev.txt"))
    assert [p for p in pinned if cloud.match(p)] == []

    module_name, attr = conf["wsgi_app"].split(":")
    __import__(module_name)
    application = getattr(sys.modules[module_name], attr)
    catalog.stock_unit(catalog.product("起動確認の商品"))
    status, page = _call_wsgi(application, "/")
    assert status == 200 and "起動確認の商品" in page and "<title>" in page


# trace: NFR-EN-07, ADDR-014
def test_gf_051_os_independent_code():
    """GF-051 Production Code が特定の OS に固有のモジュール・パス表記に依存しない（NFR-EN-07 の一部）。"""
    os_specific = {
        "fcntl", "termios", "tty", "pty", "pwd", "grp", "resource", "posix", "syslog", "crypt",
        "msvcrt", "winreg", "_winapi", "winsound", "nt", "win32api", "win32con", "pywintypes",
    }
    found = {}
    literal_paths = []
    for path in _production_sources():
        hits = _imports(path) & os_specific
        if hits:
            found[str(path.relative_to(APP_DIR))] = sorted(hits)
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if re.match(r"^[A-Za-z]:\\|^/(srv|home|usr|var|opt|tmp|etc)/", node.value):
                    literal_paths.append((str(path.relative_to(APP_DIR)), node.value))
    assert found == {}
    assert literal_paths == []
    dockerfile = (APP_DIR / "Dockerfile").read_text(encoding="utf-8")
    assert re.search(r"^FROM python:3\.12-slim" + _DIGEST + r"$", dockerfile, re.M)


# trace: NFR-SC-21, NFR-EN-10, ADDR-014
def test_gf_052_pinned_reproducible_dependencies():
    """GF-052 依存・実行環境の取得元と版が特定でき同じ構成を再現できる（VUL-10）。

    採用製品の版が NFR-EN-10 のサポート期限の前提とする版である。
    """
    runtime = _pinned("requirements.txt")
    dev = _pinned("requirements-dev.txt")
    assert runtime and dev
    for name, (version, hashes) in {**runtime, **dev}.items():
        assert hashes >= 1, name
        assert metadata.version(name) == version, (name, metadata.version(name), version)
    dockerfile = (APP_DIR / "Dockerfile").read_text(encoding="utf-8")
    assert re.search(r"^FROM python:3\.12-slim" + _DIGEST + r"$", dockerfile, re.M)
    assert "pip install --require-hashes -r requirements.txt" in dockerfile
    assert "pip install --require-hashes -r requirements-dev.txt" in dockerfile
    compose_text = (REPO_DIR / "compose.yaml").read_text(encoding="utf-8")
    assert re.search(r"^\s+image: postgres:16" + _DIGEST + r"$", compose_text, re.M)
    assert not re.search(r"^\s+image: (?!postgres:16@sha256:)", compose_text, re.M)

    # NFR-EN-10 が稼働開始時点のサポート期限の前提とする版（Django 5.2 LTS、Python 3.12、PostgreSQL 16）
    assert runtime["django"][0].startswith("5.2.")
    inventory = (REPO_DIR / "docs/operations/dependency-inventory.md").read_text(encoding="utf-8")
    table = [line for line in inventory.splitlines() if line.startswith("| ") and "---" not in line]
    rows = {line.split("|")[1].strip(): line for line in table}
    assert "2028-04" in rows["Django"] and runtime["django"][0] in rows["Django"]
    assert "2028-10" in next(v for k, v in rows.items() if k.startswith("Python（python:3.12"))
    assert "2028-11" in next(v for k, v in rows.items() if k.startswith("PostgreSQL（postgres:16"))
    for name, (version, _) in runtime.items():
        row = next((v for k, v in rows.items() if k.lower() == name), None)
        assert row is not None and f"| {version} |" in row, (name, version)


# trace: NFR-EN-12, ADDR-014
def test_gf_053_dependency_licenses():
    """GF-053 固定した全依存ライブラリのライセンスがメタデータから特定でき（不明0件）、AGPL のものが無い。"""
    licenses = {}
    for name in sorted({**_pinned("requirements.txt"), **_pinned("requirements-dev.txt")}):
        meta = metadata.metadata(name)
        license_text = (meta.get("License") or "").strip()
        declared = [meta.get("License-Expression") or "", license_text.splitlines()[0] if license_text else ""]
        declared += [c for c in (meta.get_all("Classifier") or []) if c.startswith("License ::")]
        declared = [d.strip() for d in declared if d and d.strip() and d.strip().upper() not in ("UNKNOWN", "NONE")]
        licenses[name] = declared
    assert [n for n, d in licenses.items() if not d] == []
    assert [n for n, d in licenses.items() if re.search(r"AGPL|Affero", " ".join(d), re.I)] == []


# trace: NFR-EN-11, ADDR-014
def test_gf_054_static_analysis_zero():
    """GF-054 リポジトリの規約設定（ruff.toml）で全ソースコードを静的解析し違反0件（NFR-EN-11 の一部）。"""
    config = (REPO_DIR / "ruff.toml").read_text(encoding="utf-8")
    selected = re.search(r"^select = \[(.*)\]$", config, re.M).group(1)
    assert {'"E"', '"W"'} <= {s.strip() for s in selected.split(",")}
    completed = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "--no-cache", "--output-format", "concise", "."],
        cwd=REPO_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=300,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "All checks passed" in completed.stdout


# trace: NFR-PF-16, ADDR-002, ADDR-014
@pytest.mark.django_db(transaction=True)
def test_gf_055_scale_out_keeps_user_state(api_client, web, buyer, catalog, monkeypatch, settings):
    """GF-055 プロセス数を環境変数だけで増強でき、ログイン状態・カートを別のプロセスからも参照できる。

    NFR-PF-16 の一部（構成の追加・プロセスの増加で利用者の状態が失われない）。
    """
    from django.contrib.sessions.backends.db import SessionStore as DbSessionStore
    from django.db import connection
    from django.utils.module_loading import import_string

    monkeypatch.delenv("GUNICORN_WORKERS", raising=False)
    assert runpy.run_path(str(APP_DIR / "gunicorn.conf.py"))["workers"] == 2
    monkeypatch.setenv("GUNICORN_WORKERS", "6")
    assert runpy.run_path(str(APP_DIR / "gunicorn.conf.py"))["workers"] == 6
    monkeypatch.delenv("GUNICORN_WORKERS")
    assert issubclass(import_string(settings.SESSION_ENGINE + ".SessionStore"), DbSessionStore)

    unit = catalog.stock_unit(catalog.product("増強確認の商品"), stock=10)
    login = api(api_client, "post", "/api/auth/login/", data={"email": buyer.email, "password": PASSWORD})
    token = f"Bearer {body(login)['token']}"
    assert add_item(api_client, token, unit.pk, 2).status_code == 200
    client = web()
    fields = form_fields(text(client.get("/login/")), "/login/")
    fields.update({"email": buyer.email, "password": PASSWORD})
    assert client.post("/login/", fields).status_code == 302
    session_key = client.cookies[settings.SESSION_COOKIE_NAME].value

    script = (
        "import json, django\n"
        "django.setup()\n"
        "from django.conf import settings\n"
        "from django.test import Client\n"
        "c = Client()\n"
        f"c.cookies[settings.SESSION_COOKIE_NAME] = {session_key!r}\n"
        "web = c.get('/cart/', HTTP_HOST='localhost')\n"
        f"api = Client().get('/api/cart/', HTTP_HOST='localhost', HTTP_AUTHORIZATION={token!r})\n"
        "items = json.loads(api.content.decode('utf-8'))['items'] if api.status_code == 200 else None\n"
        "print(json.dumps({'web': web.status_code, 'web_has_item': '増強確認の商品' in web.content.decode('utf-8'),"
        " 'api': api.status_code, 'api_quantities': [i['quantity'] for i in items or []]}, ensure_ascii=False))\n"
    )
    env = dict(os.environ)
    env.update(
        {
            "DJANGO_SETTINGS_MODULE": "tests.settings_test",
            "DB_NAME": connection.settings_dict["NAME"],
            "PYTHONIOENCODING": "utf-8",
        }
    )
    completed = subprocess.run(
        [sys.executable, "-c", script], cwd=APP_DIR, env=env, capture_output=True, text=True, encoding="utf-8",
        timeout=180, check=False,
    )
    assert completed.returncode == 0, completed.stderr
    other = json.loads(completed.stdout.strip().splitlines()[-1])
    assert other == {"web": 200, "web_has_item": True, "api": 200, "api_quantities": [2]}, other


# trace: NFR-SC-25, ADDR-009, ADDR-011
def test_gf_056_fictional_initial_data(make_user):
    """GF-056 リポジトリの初期データ・試験用利用者は架空の値（予約済みドメイン）だけで作る（NFR-SC-25 の一部）。"""
    seed_text = (APP_DIR / "seed" / "initial_data.json").read_text(encoding="utf-8")
    seed = json.loads(seed_text)
    emails = [row["email"] for row in seed["users"]]
    assert emails and all(e.endswith("@example.com") for e in emails)
    domains = set(re.findall(r"@([A-Za-z0-9.-]+)", seed_text))
    assert domains == {"example.com"}
    assert make_user().email.endswith("@example.test")


# trace: NFR-OM-19, ADDR-010, ADDR-014
@pytest.mark.django_db(transaction=True)
def test_gf_057_dev_procedure_document(capsys):
    """GF-057 開発・検証環境向けの手順書に必要な手順があり、参照先が存在し、初期データ一括投入の手順が成功する。

    NFR-OM-19 の一部（本番運用手順書・compose での構築・起動の実施は対象外）。
    """
    from django.core.management import get_commands

    lines, in_code = [], False
    for index, line in enumerate((REPO_DIR / "README.md").read_text(encoding="utf-8").splitlines()):
        if line.startswith("```"):
            in_code = not in_code
        elif index > 0 and not in_code and line.startswith("# "):
            break  # 次の最上位の見出し（コードブロック外）まで
        lines.append(line)
    section = "\n".join(lines)
    assert section.startswith("# MiniCommerce（開発・検証環境の手順）")
    required = {
        "設定の作成": "cp .env.example .env",
        "構築・起動": "docker compose up -d --build",
        "停止": "docker compose down",
        "データベースの初期化": "docker compose down -v",
        "初期データ一括投入": "python manage.py load_initial_data seed/initial_data.json",
        "自動テスト": "docker compose exec app pytest",
        "静的解析": "ruff check .",
    }
    assert [k for k, v in required.items() if v not in section] == []
    for name in ("DJANGO_SECRET_KEY", "DB_USER", "DB_PASSWORD", "MINICOMMERCE_ENV"):
        assert f"`{name}`" in section and name in (REPO_DIR / ".env.example").read_text(encoding="utf-8")
    assert set(_compose()["services"]) == {"app", "db"}
    assert {"load_initial_data", "test_state"} <= set(get_commands())
    for path in ("app/seed/initial_data.json", "app/pytest.ini", "ruff.toml", "compose.yaml", ".env.example"):
        assert (REPO_DIR / path).is_file(), path

    code, out = _cli(capsys, str(APP_DIR / "seed" / "initial_data.json"), "--reset")
    assert code == 0 and "初期データ一括投入が成功しました。" in out, out


# trace: NFR-LG-03, ADDR-004, ADDR-012
def test_gf_058_order_records_immutable(api_client, buyer, admin, bearer, catalog):
    """GF-058 注文明細・配送先・決済記録・注文状態履歴は登録後に変わらず、注文の更新は状態・日時・伝票番号だけ。

    NFR-LG-03 の対応方針の一部（7年保存・削除手順は対象外）。
    """
    from orders.models import Order, OrderItem, OrderStatusHistory, PaymentRecord, ShippingAddress

    def rows(model, order_id):
        fields = [f.attname for f in model._meta.concrete_fields]
        return [tuple(r) for r in model.objects.filter(order_id=order_id).order_by("pk").values_list(*fields)]

    def snapshot(order_id):
        order = Order.objects.filter(pk=order_id).values()[0]
        return {
            "order": order,
            "items": rows(OrderItem, order_id),
            "address": rows(ShippingAddress, order_id),
            "payments": rows(PaymentRecord, order_id),
            "history": rows(OrderStatusHistory, order_id),
        }

    mutable = {"status", "paid_at", "shipped_at", "delivered_at", "cancelled_at", "tracking_number"}

    def check(before, after, payments_added, history_added):
        assert after["items"] == before["items"] and after["items"]
        assert after["address"] == before["address"] and len(after["address"]) == 1
        assert after["payments"][: len(before["payments"])] == before["payments"]
        assert len(after["payments"]) == len(before["payments"]) + payments_added
        assert after["history"][: len(before["history"])] == before["history"]
        assert len(after["history"]) == len(before["history"]) + history_added
        changed = {k for k in after["order"] if after["order"][k] != before["order"][k]}
        assert changed <= mutable, changed

    unit = catalog.stock_unit(price=1800, stock=10)
    buyer_token, admin_token = bearer(buyer), bearer(admin)

    first = order_of(api_client, buyer_token, [(unit, 2)])["order_id"]
    admin_path = f"/api/admin/orders/{first}/"
    state = snapshot(first)
    assert len(state["history"]) == 1
    steps = [
        (lambda: pay(api_client, buyer_token, first, "declined"), 422, 1, 0),
        (lambda: pay(api_client, buyer_token, first, "approved"), 200, 1, 1),
        (lambda: api(api_client, "post", f"{admin_path}ship/", admin_token, {"tracking_number": "LG03-1"}), 200, 0, 1),
        (lambda: api(api_client, "post", f"{admin_path}deliver/", admin_token), 200, 0, 1),
    ]
    for action, status, payments_added, history_added in steps:
        response = action()
        assert response.status_code == status, response.content
        after = snapshot(first)
        check(state, after, payments_added, history_added)
        state = after
    assert state["order"]["status"] == "delivered" and state["order"]["tracking_number"] == "LG03-1"

    second = order_of(api_client, buyer_token, [(unit, 1)])["order_id"]
    state = snapshot(second)
    assert pay(api_client, buyer_token, second, "approved").status_code == 200
    after = snapshot(second)
    check(state, after, 1, 1)
    state = after
    cancelled = api(api_client, "post", f"/api/admin/orders/{second}/cancel/", admin_token)
    assert cancelled.status_code == 200, cancelled.content
    after = snapshot(second)
    check(state, after, 0, 1)
    assert after["order"]["status"] == "cancelled"
