# trace: NFR-SC-11, NFR-LG-01, NFR-SC-29, NFR-LG-07, NFR-SC-20, NFR-OM-02, NFR-OM-03, NFR-SC-26, NFR-MG-05
# trace: ADDR-001, ADDR-002, ADDR-003, ADDR-006, ADDR-008, ADDR-009, ADDR-010, ADDR-011, ADDR-012, ADDR-013
# trace: ADDR-014
"""結合試験：AI GAP_FILL（セキュリティ・個人情報・ログ・保存データ・通信範囲・移行の非機能要件の機械確認。Revision 5）。

GF-064〜GF-071（origin=AI_GENERATED、generation_stage=GAP_FILL）。AI INITIAL は変更しない。
FULL Traceability C10（UNRESOLVED-e1d9dfe900863622）修正 cycle=2/3 で、各 NFR の要件本文・測定条件・検証方法・代替確認を
読み直し、リポジトリと開発環境で機械的に確かめられる部分だけを確認する（nfr-verification-scope.json で PARTIAL_IT。
本番環境（ENV-02）の設定・運用記録・法令判断・脆弱性診断ツールによる診断は確認しない）。
- NFR-SC-11 の公開脆弱性情報との照合は、Steering（取得時のみ外部接続可）に従い、実行前に
  reports/integration-test/tools/fetch_dependency_vulns.py で取得・固定した照合結果を検証する
  （試験自体は外部へ接続しない）。
- NFR-SC-26 は Production Code・起動定義の範囲だけを確認する。compose.yaml（ENV-01）の公開範囲は既知の未解決
  UNRESOLVED-6de5eec64599b907（SEC-IMPL-002）の対象で、本要件の根拠に用いない。
定義ファイル・認証情報・個人情報はすべて架空の値で作る。
"""

import ast
import hashlib
import json
import logging
import math
import re
import socket
from pathlib import Path
from urllib.parse import quote

import pytest
from django.core.management import call_command, execute_from_command_line

from tests.integration._helpers import (
    ADDRESS,
    PASSWORD,
    add_item,
    api,
    body,
    form_fields,
    order_of,
    pay,
)

APP_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = APP_DIR.parent
OUT_DIR = REPO_DIR / "reports" / "integration-test"
OSV = OUT_DIR / "dependency-vulnerability-osv.json"
_SKIP_DIRS = {"tests", "migrations", "__pycache__", ".pytest_cache", ".ruff_cache", "staticfiles"}
_PIN = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([^\s\\]+)")
_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}\+09:00$")
_INTERNAL = (
    "Traceback",
    "psycopg",
    "django.db",
    "SELECT ",
    "INSERT INTO",
    'File "',
    "site-packages",
    "/srv/minicommerce",
    "C:\\",
    "Exception Value",
    "Django Version",
    "Python Version",
)


# trace: NFR-SC-20, NFR-OM-02, NFR-OM-03, NFR-LG-07, ADDR-014
def _production_sources():
    """Production Code（app/ のうち試験・マイグレーションを除く .py）。"""
    for path in sorted(APP_DIR.rglob("*.py")):
        if not _SKIP_DIRS.intersection(path.relative_to(APP_DIR).parts[:-1]):
            yield path


# trace: NFR-SC-29, NFR-LG-07, NFR-LG-01, ADDR-001, ADDR-012
def _record(name, key, data):
    path = OUT_DIR / name
    current = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    current[key] = data
    path.write_text(json.dumps(current, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# trace: NFR-SC-11
def _cvss3_base(vector):
    """CVSS v3.x のベクトルから基本値を計算する（仕様書 3.1 の式）。解釈できなければ None。"""
    parts = dict(p.split(":", 1) for p in vector.split("/")[1:] if ":" in p)
    try:
        av = {"N": 0.85, "A": 0.62, "L": 0.55, "P": 0.2}[parts["AV"]]
        ac = {"L": 0.77, "H": 0.44}[parts["AC"]]
        changed = parts["S"] == "C"
        pr = {"N": 0.85, "L": 0.68 if changed else 0.62, "H": 0.5 if changed else 0.27}[parts["PR"]]
        ui = {"N": 0.85, "R": 0.62}[parts["UI"]]
        cia = [{"H": 0.56, "L": 0.22, "N": 0.0}[parts[k]] for k in ("C", "I", "A")]
    except KeyError:
        return None
    iss = 1 - (1 - cia[0]) * (1 - cia[1]) * (1 - cia[2])
    impact = 7.52 * (iss - 0.029) - 3.25 * (iss - 0.02) ** 15 if changed else 6.42 * iss
    exploitability = 8.22 * av * ac * pr * ui
    if impact <= 0:
        return 0.0
    raw = min(1.08 * (impact + exploitability) if changed else impact + exploitability, 10)
    return math.ceil(raw * 10 - 1e-9) / 10


# trace: NFR-SC-11, ADDR-014
def test_gf_064_dependency_known_vulnerabilities():
    """GF-064 固定した全依存ライブラリを公開脆弱性情報（OSV）と照合し、CVSS 7.0 以上の既知の脆弱性が0件。"""
    data = json.loads(OSV.read_text(encoding="utf-8"))
    assert data["status"] == "FETCHED", data.get("reason")
    pins = set()
    for name, digest in data["requirements_sha256"].items():
        raw = (REPO_DIR / name).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == digest, f"{name} が照合後に変更された（再取得が必要）"
        for line in raw.decode("utf-8").splitlines():
            matched = _PIN.match(line)
            if matched:
                pins.add((matched.group(1).lower(), matched.group(2)))
    queried = {(p["name"], p["version"]) for p in data["packages"]}
    assert queried == pins and len(pins) >= 20, (sorted(pins - queried), sorted(queried - pins))
    assert all(p["pypi_status"] == 200 for p in data["packages"]), [
        p for p in data["packages"] if p["pypi_status"] != 200
    ]
    high, unknown, found = [], [], []
    for package in data["packages"]:
        for vuln in package["vulns"]:
            scores = [_cvss3_base(s["score"]) for s in vuln["severity"] if s.get("type") == "CVSS_V3"]
            scores = [s for s in scores if s is not None]
            label = (vuln.get("database_specific_severity") or "").upper()
            found.append(
                {
                    "package": package["name"],
                    "version": package["version"],
                    "id": vuln["id"],
                    "cvss3": max(scores) if scores else None,
                    "severity": label or None,
                }
            )
            if (scores and max(scores) >= 7.0) or label in ("HIGH", "CRITICAL"):
                high.append(found[-1])
            elif not scores and not label:
                unknown.append(found[-1])
    _record(
        "security-reference.json",
        "GF-064_dependency_vulnerabilities",
        {
            "fetched_at": data["fetched_at"],
            "packages": len(queried),
            "vulnerabilities": found,
            "high": high,
            "unknown_severity": unknown,
            "not_checked": "コンテナイメージ（python:3.12-slim・postgres:16）の OS パッケージ、"
            "リリース前の再照合（TASK-021）",
        },
    )
    assert not high, high
    assert not unknown, unknown


# trace: NFR-LG-01, ADDR-001, ADDR-012, ADDR-013
@pytest.mark.django_db
def test_gf_065_personal_information_handling(
    api_client, web, make_user, admin, bearer, catalog, app_logs, monkeypatch
):
    """GF-065 個人情報をログ・ファイル・外部へ出さず、
    参照は本人と管理者に限られる（NFR-LG-01 の安全管理措置の一部）。
    """
    from django.urls import get_resolver

    from orders.models import Order

    unit = catalog.stock_unit(price=2400, stock=20)
    pii = {
        "email": "lg01.kojin.taro@example.test",
        "name": "個人 情報子",
        "password": "Lg01Secret9x",
        "recipient": "受取 個人太郎",
        "address1": "個人区情報町9-8-7",
        "address2": "個人マンション101",
        "phone": "0399998888",
    }
    outbound = []
    real_connect = socket.socket.connect

    def connect(sock, address):
        host = address[0] if isinstance(address, tuple) else str(address)
        if host not in ("127.0.0.1", "::1", "localhost"):
            outbound.append(address)
        return real_connect(sock, address)

    monkeypatch.setattr(socket.socket, "connect", connect)
    responses = []

    def call(*args, **kwargs):
        response = api(api_client, *args, **kwargs)
        responses.append(response)
        return response

    registration = {
        "email": pii["email"],
        "password": pii["password"],
        "password_confirmation": pii["password"],
        "name": pii["name"],
    }
    assert (
        call("post", "/api/auth/register/", data={**registration, "password_confirmation": "Mismatch9x"}).status_code
        == 400
    )
    assert call("post", "/api/auth/register/", data=registration).status_code == 201
    assert call("post", "/api/auth/login/", data={"email": pii["email"], "password": "WrongPass9x"}).status_code == 401
    login = call("post", "/api/auth/login/", data={"email": pii["email"], "password": pii["password"]})
    token = f"Bearer {body(login)['token']}"
    assert add_item(api_client, token, unit.pk, 2).status_code == 200
    address = {
        **ADDRESS,
        "recipient_name": pii["recipient"],
        "address_line1": pii["address1"],
        "address_line2": pii["address2"],
        "phone_number": pii["phone"],
    }
    placed = call("post", "/api/orders/", token, {"shipping_address": address})
    assert placed.status_code == 201, placed.content
    order_id = body(placed)["order_id"]
    assert pay(api_client, token, order_id, "approved").status_code == 200
    assert call("get", f"/api/orders/{order_id}/", token).status_code == 200
    admin_token = bearer(admin)
    assert call("get", f"/api/admin/orders/?buyer_email={quote(pii['email'])}", admin_token).status_code == 200
    assert call("get", f"/api/admin/orders/{order_id}/", admin_token).status_code == 200

    page = web()
    fields = form_fields(page.get("/login/").content.decode("utf-8"), "/login/")
    fields.update({"email": pii["email"], "password": pii["password"]})
    assert page.post("/login/", fields).status_code == 302
    responses.append(page.get(f"/orders/{order_id}/"))
    assert responses[-1].status_code == 200 and pii["recipient"] in responses[-1].content.decode("utf-8")

    other = bearer(make_user(name="別 購入者"))
    denied = {
        "other_buyer_api": call("get", f"/api/orders/{order_id}/", other).status_code,
        "visitor_api": call("get", f"/api/orders/{order_id}/").status_code,
        "other_buyer_admin_api": call("get", f"/api/admin/orders/{order_id}/", other).status_code,
    }
    other_page = web()
    other_user = make_user(name="別 画面購入者")
    fields = form_fields(other_page.get("/login/").content.decode("utf-8"), "/login/")
    fields.update({"email": other_user.email, "password": PASSWORD})
    assert other_page.post("/login/", fields).status_code == 302
    denied["other_buyer_screen"] = other_page.get(f"/orders/{order_id}/").status_code
    denied["visitor_screen"] = web().get(f"/orders/{order_id}/").status_code

    logged = "\n".join(app_logs.lines)
    leaked = {key: value for key, value in pii.items() if value in logged}
    attachments = [r.get("Content-Disposition") for r in responses if r.get("Content-Disposition")]
    patterns = []

    def walk(resolver, prefix=""):
        for entry in resolver.url_patterns:
            if hasattr(entry, "url_patterns"):
                walk(entry, prefix + str(entry.pattern))
            else:
                patterns.append(prefix + str(entry.pattern))

    walk(get_resolver())
    export_like = [p for p in patterns if re.search(r"export|download|csv|report|pdf|print|backup|dump|file", p, re.I)]
    _record(
        "security-reference.json",
        "GF-065_personal_information",
        {
            "log_lines": len(app_logs.lines),
            "leaked": leaked,
            "attachments": attachments,
            "export_like_routes": export_like,
            "outbound_connections": [str(a) for a in outbound],
            "denied": denied,
            "url_patterns": len(patterns),
            "not_checked": "利用目的の特定・表示（本システム外）、"
            "本番の通信の暗号化（NFR-SC-02）、検証環境で本番データを使わない運用"
            "（NFR-SC-25）、法令適合の判断",
        },
    )
    assert app_logs.lines and not leaked, leaked
    assert not attachments and not export_like, (attachments, export_like)
    assert not outbound, outbound
    assert denied == {
        "other_buyer_api": 404,
        "visitor_api": 401,
        "other_buyer_admin_api": 403,
        "other_buyer_screen": 404,
        "visitor_screen": 302,
    }, denied
    assert Order.objects.get(pk=order_id).status == "paid"


# trace: NFR-SC-29, NFR-LG-07, ADDR-001, ADDR-012
_PAYLOADS = (
    "<script>alert('mc-xss')</script>",
    "\"><img src=x onerror=alert('mc-xss')>",
    "' OR '1'='1",
    "1; DROP TABLE orders_order;--",
    "../../../../etc/passwd",
    "${7*7}{{7*7}}",
    "a\x00b",
    "９" * 300,
)


# trace: NFR-SC-29, NFR-LG-07, ADDR-001, ADDR-012
def _inspect(response, label, findings):
    """1つの応答の診断（システムエラー・無害化されないスクリプトの反映・内部情報・セキュリティヘッダー）。"""
    content = response.content.decode("utf-8", "replace")
    if response.status_code >= 500:
        findings.append((label, "system_error", response.status_code))
    if "<script>alert('mc-xss')</script>" in content or "<img src=x onerror=alert('mc-xss')>" in content:
        findings.append((label, "unescaped_reflection", response.status_code))
    for marker in _INTERNAL:
        if marker in content:
            findings.append((label, f"internal_info:{marker}", response.status_code))
    if response.status_code < 300 or response.status_code >= 400:
        headers = {
            "X-Content-Type-Options": response.get("X-Content-Type-Options"),
            "X-Frame-Options": response.get("X-Frame-Options"),
            "Referrer-Policy": response.get("Referrer-Policy"),
        }
        if headers != {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "same-origin",
        }:
            findings.append((label, f"headers:{headers}", response.status_code))


# trace: NFR-SC-29, NFR-LG-07, NFR-LG-01, ADDR-002, ADDR-012
def _login(client, email, password=PASSWORD):
    """画面のログインフォームからログインする（CSRF トークン・送信トークンを含む）。"""
    fields = form_fields(client.get("/login/").content.decode("utf-8"), "/login/")
    fields.update({"email": email, "password": password})
    assert client.post("/login/", fields).status_code == 302
    return client


# trace: NFR-SC-29, NFR-LG-07, ADDR-001, ADDR-012
def _patterns():
    from django.urls import get_resolver

    found = []

    def walk(resolver, prefix=""):
        for entry in resolver.url_patterns:
            if hasattr(entry, "url_patterns"):
                walk(entry, prefix + str(entry.pattern))
            else:
                found.append("/" + prefix + str(entry.pattern))

    walk(get_resolver())
    return found


# 画面の更新操作（ADDR-012 の画面定義でフォームを POST で送る要求先）
_SCREEN_POSTS = (
    "/register/",
    "/login/",
    "/logout/",
    "/cart/items/add/",
    "/cart/items/<str:cart_item_id>/quantity/",
    "/cart/items/<str:cart_item_id>/delete/",
    "/cart/coupon/apply/",
    "/cart/coupon/remove/",
    "/checkout/",
    "/orders/<str:order_id>/payment/",
    "/orders/<str:order_id>/cancel/",
    "/manage/orders/<str:order_id>/ship/",
    "/manage/orders/<str:order_id>/deliver/",
    "/manage/orders/<str:order_id>/cancel/",
)


# trace: NFR-SC-29, NFR-LG-07, ADDR-001, ADDR-002, ADDR-012
@pytest.mark.django_db
def test_gf_066_dynamic_probe_all_screens_and_apis(api_client, web, make_user, admin, bearer, catalog, make_coupon):
    """GF-066 全画面・全 API
    への簡易な動的診断（アクセス制御・CSRF・注入・XSS・内部情報・ヘッダー）と外部要求の部品の不存在。
    """
    from django.test import Client

    from audit.models import AuditLog
    from carts.models import Cart, CartItem
    from orders.models import Order

    unit = catalog.stock_unit(price=1500, stock=50)
    make_coupon("PROBE-1")
    buyer, other = make_user(name="診断 購入者"), make_user(name="診断 別購入者")
    token, other_token, admin_token = bearer(buyer), bearer(other), bearer(admin)
    order_id = order_of(api_client, token, [(unit, 1)])["order_id"]
    paid_id = order_of(api_client, other_token, [(unit, 1)])["order_id"]
    assert pay(api_client, other_token, paid_id, "approved").status_code == 200
    item_id = body(add_item(api_client, token, unit.pk, 1))["items"][0]["cart_item_id"]
    findings, probes = [], 0
    patterns = _patterns()
    users = {"buyer": buyer, "other": other, "admin": admin}
    sessions = {role: _login(web(), user.email) for role, user in users.items()}

    def concrete(pattern, admin_side=False):
        values = {
            "product_id": str(unit.product_id),
            "order_id": str(paid_id if admin_side else order_id),
            "cart_item_id": str(item_id),
        }
        return re.sub(r"<str:(\w+)>", lambda m: values[m.group(1)], pattern)

    # (1) アクセス制御（VUL-01）：来訪者・購入者・別の購入者・管理者で全 API・全画面へ参照の要求を送る
    access = {}
    for pattern in patterns:
        path = concrete(pattern)
        row = {}
        for role, auth in (("visitor", None), ("buyer", token), ("other", other_token), ("admin", admin_token)):
            if path.startswith("/api/"):
                response = api(api_client, "get", path, auth)
            else:
                response = (web() if role == "visitor" else sessions[role]).get(path)
            probes += 1
            _inspect(response, f"access {role} GET {path}", findings)
            row[role] = response.status_code
        access[pattern] = row
        admin_only = pattern.startswith(("/api/admin/", "/manage/"))
        own = pattern.startswith(
            ("/api/cart", "/cart", "/checkout", "/orders", "/api/orders", "/api/auth/me", "/api/auth/logout")
        )
        if (admin_only or own) and row["visitor"] not in (401, 302, 405):
            findings.append((f"access {pattern}", f"visitor_not_rejected:{row['visitor']}", row["visitor"]))
        if admin_only and row["buyer"] not in (403, 405):
            findings.append((f"access {pattern}", f"buyer_not_forbidden:{row['buyer']}", row["buyer"]))
        if "<str:order_id>" in pattern and not admin_only and row["other"] not in (404, 405):
            findings.append((f"access {pattern}", f"other_buyer_not_not_found:{row['other']}", row["other"]))
    for method, path in (
        ("patch", f"/api/cart/items/{item_id}/"),
        ("delete", f"/api/cart/items/{item_id}/"),
        ("post", f"/api/orders/{order_id}/payment/"),
        ("post", f"/api/orders/{order_id}/cancel/"),
    ):
        response = api(api_client, method, path, other_token, {"quantity": 2} if method == "patch" else {})
        probes += 1
        _inspect(response, f"access other {method} {path}", findings)
        if response.status_code != 404:
            findings.append((f"access other {method} {path}", "other_buyer_update_not_not_found", response.status_code))
    updates = {}
    for method, path, data in (
        ("post", "/api/cart/items/", {"stock_unit_id": unit.pk, "quantity": 1}),
        ("patch", f"/api/cart/items/{item_id}/", {"quantity": 2}),
        ("delete", f"/api/cart/items/{item_id}/", {}),
        ("post", "/api/cart/coupon/", {"coupon_code": "PROBE-1"}),
        ("delete", "/api/cart/coupon/", {}),
        ("post", "/api/orders/", {"shipping_address": dict(ADDRESS)}),
        ("post", f"/api/orders/{order_id}/payment/", {"mock_instruction": "approved"}),
        ("post", f"/api/orders/{order_id}/cancel/", {}),
        ("post", f"/api/admin/orders/{paid_id}/ship/", {"tracking_number": "ACL-1"}),
        ("post", f"/api/admin/orders/{paid_id}/deliver/", {}),
        ("post", f"/api/admin/orders/{paid_id}/cancel/", {}),
    ):
        admin_only = path.startswith("/api/admin/")
        for role, auth, expected in (("visitor", None, 401), ("buyer", token if admin_only else None, 403)):
            if role == "buyer" and not admin_only:
                continue
            response = api(api_client, method, path, auth, data)
            probes += 1
            updates[f"{role} {method.upper()} {path}"] = response.status_code
            _inspect(response, f"access {role} {method} {path}", findings)
            if response.status_code != expected:
                findings.append((f"access {role} {method} {path}", f"not_rejected:{response.status_code}", expected))
    access["__updates__"] = updates

    # (2) CSRF（VUL-06）：ログイン状態の画面から CSRF トークンなしの更新要求。参照用の要求（GET）でも更新しない
    def state():
        return (
            Order.objects.get(pk=order_id).status,
            Order.objects.get(pk=paid_id).status,
            sorted(CartItem.objects.values_list("pk", "quantity")),
            sorted(Cart.objects.values_list("pk", "coupon_id", "status")),
            AuditLog.objects.filter(event_type="logout").count(),
        )

    before = state()
    csrf, reference = {}, {}
    for pattern in _SCREEN_POSTS:
        admin_side = pattern.startswith("/manage/")
        path = concrete(pattern, admin_side)
        user = admin if admin_side else buyer
        client = Client(enforce_csrf_checks=True)
        _login(client, user.email)
        fields = {
            "quantity": "3",
            "coupon_code": "PROBE-1",
            "tracking_number": "CSRF-1",
            **ADDRESS,
            "mock_instruction": "approved",
            "email": user.email,
            "password": PASSWORD,
            "stock_unit_id": str(unit.pk),
            "password_confirmation": PASSWORD,
            "name": "CSRF 試験",
        }
        response = client.post(path, fields)
        probes += 1
        csrf[path] = response.status_code
        _inspect(response, f"csrf POST {path}", findings)
        if response.status_code != 403:
            findings.append((f"csrf POST {path}", "accepted_without_token", response.status_code))
        got = client.get(path)
        probes += 1
        reference[path] = got.status_code
        _inspect(got, f"reference GET {path}", findings)
        still = client.get("/manage/orders/" if admin_side else "/cart/")
        if still.status_code != 200:
            findings.append((f"reference GET {path}", f"session_changed:{still.status_code}", still.status_code))
    after = state()
    if before != after:
        findings.append(("csrf/reference", f"data_changed:{before}->{after}", 0))

    # (3) 注入・XSS・内部情報（VUL-04・VUL-05・VUL-13）：検索条件・パス中の識別子・本文の各項目に攻撃文字列を入れる
    page, admin_page = sessions["buyer"], sessions["admin"]
    counts_before = {m.__name__: m.objects.count() for m in (Order, Cart, AuditLog)}
    for payload in _PAYLOADS:
        q, segment = quote(payload), quote(payload, safe="")
        gets = [
            (None, f"/api/products/?keyword={q}&category_id={q}&sort={q}&page={q}"),
            (admin_token, f"/api/admin/stock-units/?sku={q}&product_name={q}&supplier_code={q}&low_stock_only={q}"),
            (admin_token, f"/api/admin/orders/?order_number={q}&buyer_email={q}&status={q}&order_date_from={q}"),
            (None, f"/api/products/{segment}/"),
            (token, f"/api/orders/{segment}/"),
            (token, f"/api/cart/items/{segment}/"),
            (page, f"/?keyword={q}&category_id={q}&sort={q}&page={q}"),
            (page, f"/products/{segment}/"),
            (page, f"/orders/{segment}/"),
            (admin_page, f"/manage/stock-units/?sku={q}&product_name={q}&supplier_code={q}&low_stock_only={q}"),
            (admin_page, f"/manage/orders/?order_number={q}&buyer_email={q}&status={q}&order_date_from={q}"),
            (admin_page, f"/manage/orders/{segment}/"),
        ]
        for auth, path in gets:
            response = api(api_client, "get", path, auth) if path.startswith("/api/") else auth.get(path)
            probes += 1
            _inspect(response, f"inject GET {path[:70]}", findings)
        bodies = [
            (
                "post",
                "/api/auth/register/",
                None,
                {"email": payload, "password": payload, "password_confirmation": payload, "name": payload},
            ),
            ("post", "/api/auth/login/", None, {"email": payload, "password": payload}),
            ("post", "/api/cart/items/", token, {"stock_unit_id": payload, "quantity": payload}),
            ("patch", f"/api/cart/items/{item_id}/", token, {"quantity": payload}),
            ("post", "/api/cart/coupon/", token, {"coupon_code": payload}),
            ("post", "/api/orders/", token, {"shipping_address": dict.fromkeys(ADDRESS, payload)}),
            ("post", f"/api/orders/{order_id}/payment/", token, {"mock_instruction": payload}),
            ("post", f"/api/admin/orders/{paid_id}/ship/", admin_token, {"tracking_number": payload}),
        ]
        for method, path, auth, data in bodies:
            response = api(api_client, method, path, auth, data)
            probes += 1
            _inspect(response, f"inject {method.upper()} {path} {payload[:12]!r}", findings)
        forms = [
            (
                web(),
                "/register/",
                "/register/",
                {"email": payload, "password": payload, "password_confirmation": payload, "name": payload},
            ),
            (page, "/cart/", "/cart/coupon/apply/", {"coupon_code": payload}),
            (page, "/checkout/", "/checkout/", dict.fromkeys(ADDRESS, payload)),
            (admin_page, f"/manage/orders/{paid_id}/", f"/manage/orders/{paid_id}/ship/", {"tracking_number": payload}),
        ]
        for client, source, action, data in forms:
            try:
                values = form_fields(client.get(source).content.decode("utf-8"), action)
            except AssertionError:
                values = {}
            values.update(data)
            response = client.post(action, values)
            probes += 1
            _inspect(response, f"inject FORM {action} {payload[:12]!r}", findings)
    counts_after = {m.__name__: m.objects.count() for m in (Order, Cart, AuditLog)}
    if counts_after["Order"] != counts_before["Order"]:
        findings.append(("inject", f"orders_changed:{counts_before}->{counts_after}", 0))
    # 保存された値の表示（格納型 XSS）：スクリプトを含む氏名の利用者でログインした画面
    stored = make_user(name="<script>alert('mc-xss')</script>")
    stored_page = _login(web(), stored.email)
    for path in ("/", "/cart/", "/orders/"):
        probes += 1
        _inspect(stored_page.get(path), f"stored GET {path}", findings)

    # (4) SSRF（VUL-12）：Production Code が外部へ要求を送る部品を読み込まない
    network_modules = {
        "urllib.request",
        "http.client",
        "requests",
        "httpx",
        "urllib3",
        "socket",
        "ftplib",
        "smtplib",
        "xmlrpc.client",
        "aiohttp",
    }
    imported = []
    for path in _production_sources():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                names = [node.module] + [f"{node.module}.{a.name}" for a in node.names]
            imported += [(str(path.relative_to(APP_DIR)), n) for n in names if n in network_modules]
    _record(
        "security-reference.json",
        "GF-066_dynamic_probe",
        {
            "url_patterns": len(patterns),
            "probes": probes,
            "payloads": list(_PAYLOADS),
            "access_matrix": access,
            "csrf_without_token": csrf,
            "reference_get": reference,
            "network_client_imports": imported,
            "findings": [list(f) for f in findings],
            "not_checked": "脆弱性診断ツールによる網羅的な動的診断と指摘の対処・再診断（NFR-SC-29）、"
            "VUL-02/03/08/09/10/11 の診断（NFR-LG-07 の残り）",
        },
    )
    assert len(patterns) == 44, len(patterns)
    assert not imported, imported
    assert not findings, findings[:20]


# trace: NFR-SC-20, ADDR-002, ADDR-006, ADDR-013, ADDR-014
def test_gf_067_persistent_data_only_in_database():
    """GF-067
    保存データの所在がデータベースだけ（ファイルへの保存・ファイル型のセッション/キャッシュ・ログファイルなし）。
    """
    from django.apps import apps
    from django.conf import settings
    from django.contrib.sessions.backends.db import SessionStore as DatabaseSessionStore
    from django.db import models
    from django.utils.module_loading import import_string

    file_fields = [
        f"{m._meta.label}.{f.name}"
        for m in apps.get_models()
        for f in m._meta.get_fields()
        if isinstance(f, (models.FileField, models.FilePathField))
    ]
    session_store = import_string(f"{settings.SESSION_ENGINE}.SessionStore")
    cache_backends = {name: conf["BACKEND"] for name, conf in settings.CACHES.items()}
    handlers = {name: conf["class"] for name, conf in settings.LOGGING["handlers"].items()}
    writes = []
    for path in _production_sources():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
            if name in (
                "write_text",
                "write_bytes",
                "mkstemp",
                "NamedTemporaryFile",
                "TemporaryFile",
                "copyfile",
                "makedirs",
                "mkdir",
                "dump",
            ):
                writes.append((str(path.relative_to(APP_DIR)), node.lineno, name))
            if name == "open":
                modes = [a.value for a in node.args[1:2] if isinstance(a, ast.Constant)]
                modes += [k.value.value for k in node.keywords if k.arg == "mode" and isinstance(k.value, ast.Constant)]
                if any(set(str(m)) & set("wax+") for m in modes):
                    writes.append((str(path.relative_to(APP_DIR)), node.lineno, f"open:{modes}"))
    gunicorn = (APP_DIR / "gunicorn.conf.py").read_text(encoding="utf-8")
    _record(
        "security-reference.json",
        "GF-067_persistent_data_location",
        {
            "databases": sorted(settings.DATABASES),
            "engine": settings.DATABASES["default"]["ENGINE"],
            "file_fields": file_fields,
            "session_engine": settings.SESSION_ENGINE,
            "message_storage": settings.MESSAGE_STORAGE,
            "caches": cache_backends,
            "log_handlers": handlers,
            "file_writes_in_production_code": writes,
            "not_checked": "本番環境のデータベースの保存媒体・バックアップの暗号化の設定（ENV-02、DIF-07）",
        },
    )
    assert sorted(settings.DATABASES) == ["default"]
    assert settings.DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql"
    assert not file_fields, file_fields
    assert issubclass(session_store, DatabaseSessionStore)
    assert settings.MESSAGE_STORAGE == "django.contrib.messages.storage.session.SessionStorage"
    assert all("FileBasedCache" not in b and "DatabaseCache" not in b for b in cache_backends.values()), cache_backends
    assert set(handlers.values()) <= {"logging.StreamHandler", "logging.NullHandler"}, handlers
    assert not writes, writes
    assert re.search(r"^accesslog = None$", gunicorn, re.M) and re.search(r'^errorlog = "-"$', gunicorn, re.M)


# trace: NFR-OM-02, ADDR-008, ADDR-010, ADDR-013
@pytest.mark.django_db(transaction=True)
def test_gf_068_application_log_output(api_client, bearer, make_user, catalog, set_state, app_logs, capsys, tmp_path):
    """GF-068 アプリケーションログ（LOG-01〜03・05・06）は標準出力への1行1件の JSON（日時・種類付き）で、
    アプリ内で削除しない。
    """
    from django.conf import settings

    unit = catalog.stock_unit(price=1800, stock=10)
    token = bearer(make_user())
    assert api(api_client, "get", "/api/products/").status_code == 200
    assert api(api_client, "get", "/api/orders/999999/", token).status_code == 404
    order_id = order_of(api_client, token, [(unit, 1)])["order_id"]
    assert pay(api_client, token, order_id, "approved").status_code == 200
    add_item(api_client, token, unit.pk, 1)
    set_state(order_fault_point="after_stock_decrement")
    assert api(api_client, "post", "/api/orders/", token, {"shipping_address": dict(ADDRESS)}).status_code == 500
    set_state(order_fault_point="none")
    definition = tmp_path / "om02.json"
    definition.write_text(
        json.dumps({"suppliers": [{"supplier_code": "OM02-SUP", "name": "架空仕入先"}]}, ensure_ascii=False),
        encoding="utf-8",
    )
    # manage.py の起動経路（execute_from_command_line）はログ設定を読み直すため、捕捉を保つ call_command で実行する
    call_command("load_initial_data", str(definition))
    capsys.readouterr()

    logger = logging.getLogger("minicommerce")
    configured = [type(h).__name__ for h in logger.handlers if h is not app_logs]
    handlers = []
    for name in ["", *logging.Logger.manager.loggerDict]:
        for handler in getattr(logging.getLogger(name), "handlers", []):
            module = type(handler).__module__
            if handler is app_logs or module.startswith(("_pytest", "pytest", "tests.")):
                continue
            handlers.append(handler)
    all_handlers = {type(h).__name__ for h in handlers}
    file_handlers = [type(h).__name__ for h in handlers if isinstance(h, logging.FileHandler)]
    by_type = {}
    malformed = []
    for line in app_logs.lines:
        record = json.loads(line)
        if "\n" in line or not _TIMESTAMP.match(record.get("timestamp", "")) or not record.get("log_type"):
            malformed.append(line)
        by_type.setdefault(record["log_type"], []).append(record)
    deleting = []
    for path in _production_sources():
        text = path.read_text(encoding="utf-8")
        for token_name in (
            "RotatingFileHandler",
            "TimedRotatingFileHandler",
            "logging.handlers",
            "os.remove",
            "unlink(",
        ):
            if token_name in text:
                deleting.append((str(path.relative_to(APP_DIR)), token_name))
    gunicorn = (APP_DIR / "gunicorn.conf.py").read_text(encoding="utf-8")
    _record(
        "operations-reference.json",
        "GF-068_application_log_output",
        {
            "minicommerce_handlers": configured,
            "all_handlers": sorted(all_handlers),
            "stream": str(settings.LOGGING["handlers"]["stdout"].get("stream")),
            "log_types": {k: len(v) for k, v in sorted(by_type.items())},
            "malformed": malformed[:5],
            "log_deletion_in_production_code": deleting,
            "not_checked": "ENV-02 のログ基盤での90日保管と期間内の検索（稼働後90日経過時点の確認）",
        },
    )
    assert configured == ["StreamHandler"], configured
    assert all_handlers <= {"StreamHandler", "NullHandler"} and not file_handlers, (all_handlers, file_handlers)
    assert settings.LOGGING["handlers"]["stdout"]["stream"] == "ext://sys.stdout"
    assert {"LOG-01", "LOG-02", "LOG-03", "LOG-05", "LOG-06"} <= set(by_type), sorted(by_type)
    assert not malformed, malformed[:3]
    assert all(r.get("request_id") for t in ("LOG-01", "LOG-02", "LOG-03", "LOG-06") for r in by_type[t])
    assert not deleting, deleting
    assert re.search(r"^accesslog = None$", gunicorn, re.M) and re.search(r'^errorlog = "-"$', gunicorn, re.M)


# trace: NFR-OM-03, ADDR-006, ADDR-010, ADDR-012
@pytest.mark.django_db(transaction=True)
def test_gf_069_audit_log_retention_premise(api_client, make_user, capsys, tmp_path):
    """GF-069 監査ログは DB に追記のみで記録され、本システムのどの処理も削除・更新しない（1年保管の前提）。"""
    from django.db import connection

    from audit.models import AppendOnlyError, AuditLog

    user = make_user()
    assert (
        api(api_client, "post", "/api/auth/login/", data={"email": user.email, "password": "Wrong0Pass9"}).status_code
        == 401
    )
    login = api(api_client, "post", "/api/auth/login/", data={"email": user.email, "password": PASSWORD})
    assert api(api_client, "post", "/api/auth/logout/", f"Bearer {body(login)['token']}").status_code == 204
    before = list(AuditLog.objects.order_by("pk").values_list("pk", "occurred_at", "event_type"))
    definition = tmp_path / "om03.json"
    definition.write_text(
        json.dumps({"suppliers": [{"supplier_code": "OM03-SUP", "name": "架空仕入先"}]}, ensure_ascii=False),
        encoding="utf-8",
    )
    capsys.readouterr()
    try:
        execute_from_command_line(["manage.py", "load_initial_data", str(definition), "--reset"])
    except SystemExit as exc:
        assert exc.code in (0, None), exc.code
    capsys.readouterr()
    after = list(AuditLog.objects.order_by("pk").values_list("pk", "occurred_at", "event_type"))
    blocked = []
    for attempt in (
        lambda: AuditLog.objects.all().delete(),
        lambda: AuditLog.objects.all().update(result="failure"),
        lambda: AuditLog.objects.first().delete(),
        lambda: AuditLog.objects.first().save(),
    ):
        try:
            attempt()
        except AppendOnlyError:
            blocked.append(True)
        else:
            blocked.append(False)
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT count(*) FROM information_schema.table_constraints WHERE table_name = %s "
            "AND constraint_type = 'FOREIGN KEY'",
            [AuditLog._meta.db_table],
        )
        foreign_keys = cursor.fetchone()[0]
    fk_fields = [f.name for f in AuditLog._meta.get_fields() if f.is_relation]
    usages = []
    for path in _production_sources():
        text = path.read_text(encoding="utf-8")
        for pattern in (
            r"AuditLog\.objects\.[\w().]*\b(delete|update|_raw_delete)\b",
            r"(?i)delete\s+from\s+audit",
            r"(?i)truncate[^\n]*audit",
            r"audit_auditlog",
        ):
            for matched in re.finditer(pattern, text):
                usages.append((str(path.relative_to(APP_DIR)), matched.group(0)))
    _record(
        "operations-reference.json",
        "GF-069_audit_log_retention",
        {
            "audit_logs_before_reset": len(before),
            "audit_logs_after_reset": len(after),
            "append_only_blocked": blocked,
            "foreign_keys": foreign_keys,
            "relation_fields": fk_fields,
            "deletion_paths_in_production_code": usages,
            "not_checked": "ENV-02 での1年保管と、運用手順書の削除手順が1年以内の監査ログを削除しない条件であること",
        },
    )
    assert [e for _, _, e in before] == ["login_failure", "login_success", "logout"], before
    assert after[: len(before)] == before and len(after) == len(before) + 1, after
    assert after[-1][2] == "initial_data_load"
    assert all(at.tzinfo is not None for _, at, _ in after)
    assert blocked == [True, True, True, True], blocked
    assert foreign_keys == 0 and not fk_fields, (foreign_keys, fk_fields)
    assert not usages, usages


# trace: NFR-SC-26, ADDR-012, ADDR-014
@pytest.mark.django_db
def test_gf_070_single_https_user_service(client, catalog):
    """GF-070 利用者向けサービス（画面・API）は1つの待受けだけで提供し、
    本番プロファイルでは HTTPS 以外を拒否する。管理用の別口なし。
    """
    from django.conf import settings
    from django.test import override_settings
    from django.urls import get_resolver

    unit = catalog.stock_unit(price=1000, stock=5)
    patterns = []

    def walk(resolver, prefix=""):
        for entry in resolver.url_patterns:
            if hasattr(entry, "url_patterns"):
                walk(entry, prefix + str(entry.pattern))
            else:
                patterns.append("/" + prefix + str(entry.pattern))

    walk(get_resolver())
    paths = sorted({re.sub(r"<str:\w+>", str(unit.product_id), p) for p in patterns})
    rejected, served = {}, {}
    with override_settings(IS_PRODUCTION=True, ALLOWED_HOSTS=["shop.example.test"]):
        for path in paths:
            rejected[path] = client.get(path, HTTP_HOST="shop.example.test").status_code
        for path in ("/", "/api/products/", f"/products/{unit.product_id}/"):
            served[path] = client.get(path, HTTP_HOST="shop.example.test", secure=True).status_code
    dockerfile = (APP_DIR / "Dockerfile").read_text(encoding="utf-8")
    instructions = [line for line in dockerfile.splitlines() if line and not line.lstrip().startswith("#")]
    gunicorn = (APP_DIR / "gunicorn.conf.py").read_text(encoding="utf-8")
    binds = re.findall(r"^bind = (.+)$", gunicorn, re.M)
    exposes = [line for line in instructions if line.startswith("EXPOSE")]
    remote_login = [line for line in instructions if re.search(r"ssh|telnet|vnc|rdp", line, re.I)]
    admin_like = [p for p in patterns if re.search(r"^/(admin|__debug__|debug|static/|media/|phpmyadmin|pgadmin)", p)]
    _record(
        "security-reference.json",
        "GF-070_network_exposure_application_side",
        {
            "http_rejected_in_production": rejected,
            "https_served_in_production": served,
            "gunicorn_bind": binds,
            "dockerfile_expose": exposes,
            "remote_login_software": remote_login,
            "admin_like_routes": admin_like,
            "installed_apps_admin": "django.contrib.admin" in settings.INSTALLED_APPS,
            "relation_to_known_issue": "compose.yaml（ENV-01）のポート公開範囲は既知の未解決 "
            "UNRESOLVED-6de5eec64599b907 の "
            "SEC-IMPL-002（compose 公開範囲）の対象であり、本ケースの判定に用いない（新しいループにしない）",
            "not_checked": "本番環境（ENV-02）のネットワーク設定：外部から到達できる範囲が "
            "HTTPS の利用者向けサービスだけであること、"
            "データベースへ外部から到達できないこと、サーバーへのログインが社内ネットワークからに限られること",
        },
    )
    assert len(patterns) == 44
    assert all(code == 403 for code in rejected.values()), {p: c for p, c in rejected.items() if c != 403}
    assert served == {"/": 200, "/api/products/": 200, f"/products/{unit.product_id}/": 200}, served
    assert binds == ['"0.0.0.0:8000"'], binds
    assert exposes == ["EXPOSE 8000"], exposes
    assert not remote_login, remote_login
    assert not admin_like and "django.contrib.admin" not in settings.INSTALLED_APPS, admin_like
    assert any(line.startswith("USER ") and "root" not in line for line in instructions)


# trace: NFR-MG-05, ADDR-009, ADDR-010
@pytest.mark.django_db(transaction=True)
def test_gf_071_initial_load_reflects_stock_sheet(set_state, capsys, tmp_path):
    """GF-071 初期データ一括投入は投入時点の在庫数量（定義ファイルの値）をそのまま反映し、
    更新後の値で再投入すると置き換わる。
    """
    from catalog.models import StockUnit
    from tests.integration._helpers import jst

    def definition(name, stocks):
        data = {
            "users": [
                {
                    "email": "mg05.admin@example.test",
                    "password": "Mg05Admin9x",
                    "name": "移行 管理者",
                    "user_type": "admin",
                }
            ],
            "suppliers": [{"supplier_code": "MG05-SUP", "name": "架空仕入先"}],
            "categories": [{"category_code": "mg05-top", "name": "移行大分類", "display_order": 1}],
            "products": [
                {
                    "product_code": f"MG05-P{i}",
                    "name": f"移行商品{i}",
                    "description": "架空",
                    "category_codes": ["mg05-top"],
                    "registered_at": "2027-03-01T10:00:00+09:00",
                }
                for i in range(3)
            ],
            "stock_units": [
                {
                    "sku": f"MG05-P{i}-1",
                    "product_code": f"MG05-P{i}",
                    "supplier_code": "MG05-SUP",
                    "variant_name": "標準",
                    "price_excluding_tax": 1000 + i,
                    "stock_quantity": stock,
                }
                for i, stock in enumerate(stocks)
            ],
        }
        path = tmp_path / name
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return str(path)

    def load(path, at):
        set_state(fixed_now=at)
        capsys.readouterr()
        try:
            execute_from_command_line(["manage.py", "load_initial_data", path, "--reset"])
            code = 0
        except SystemExit as exc:
            code = exc.code if isinstance(exc.code, int) else 1
        capsys.readouterr()
        return code, {u.sku: u.stock_quantity for u in StockUnit.objects.order_by("sku")}

    noon = [12, 0, 7]
    evening = [9, 30, 0]
    code1, first = load(definition("sheet-1200.json", noon), jst(2027, 3, 29, 12, 30))
    code2, second = load(definition("sheet-1700.json", evening), jst(2027, 3, 31, 17, 30))
    _record(
        "operations-reference.json",
        "GF-071_initial_load_stock_sheet",
        {
            "load_1": {"at": "2027-03-29T12:30+09:00", "file_stock": noon, "stored": first, "exit_code": code1},
            "load_2": {"at": "2027-03-31T17:30+09:00", "file_stock": evening, "stored": second, "exit_code": code2},
            "not_checked": "移行計画の実施日（2027-03-29〜31）・実施者・在庫数量の確定時刻の記載（構成・設定レビュー）",
        },
    )
    assert code1 == 0 and code2 == 0, (code1, code2)
    assert first == {f"MG05-P{i}-1": s for i, s in enumerate(noon)}, first
    assert second == {f"MG05-P{i}-1": s for i, s in enumerate(evening)}, second
    assert StockUnit.objects.count() == 3
