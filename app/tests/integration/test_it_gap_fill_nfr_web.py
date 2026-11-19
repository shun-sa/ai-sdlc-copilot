# trace: FR-001, FR-002, FR-011, FR-012, FR-020, FR-021, FR-023, FR-030, FR-031, FR-033, FR-034, FR-043, FR-044
# trace: NFR-PF-01, NFR-PF-02, NFR-PF-08, NFR-PF-09, NFR-SC-12, NFR-US-03, NFR-US-04, NFR-US-05, NFR-US-07
# trace: NFR-US-08, NFR-US-09, NFR-LG-02, NFR-LG-08, NFR-LG-09
# trace: ADDR-001, ADDR-002, ADDR-003, ADDR-012
"""結合試験：AI GAP_FILL（性能の参考計測・一覧件数・認証手段・画面の表示と操作性の非機能要件。Revision 2）。

GF-022・GF-023・GF-028〜GF-033・GF-036・GF-037（origin=AI_GENERATED、generation_stage=GAP_FILL）。
AI INITIAL は変更しない。期待結果は各 NFR の目標値・測定条件・検証方法と ADDR-001（API 契約）・
ADDR-012（画面）から導出する。
- 応答時間（GF-022）は単一利用者・小データ量での参考計測で、ピーク負荷・3年後データ量の判定ではない
  （性能試験で判定する）。
- 画面の適合レベル A・キーボード操作・確認ダイアログ（GF-031・GF-033）は HTML の機械判定できる範囲だけを確認し、
  ブラウザでの操作・チェックリストによる確認は互換性・操作性テストで行う（nfr-verification-scope.json に記録）。
"""

import html as html_lib
import json
import math
import re
import time
from datetime import datetime
from pathlib import Path

import pytest

from tests.integration._helpers import (
    ADDRESS,
    JST,
    PASSWORD,
    add_item,
    api,
    body,
    error_of,
    field_names,
    form_fields,
    input_value,
    order_of,
    pay,
    place,
    text,
)

pytestmark = pytest.mark.django_db

REPO_DIR = Path(__file__).resolve().parents[3]
SAMPLES = 100
JIS3 = "𠮟"  # JIS X 0213 第3水準（1-47-52）
JIS4 = "𩸽"  # JIS X 0213 第4水準（2-93-87）


# trace: NFR-PF-01, NFR-PF-02, NFR-PF-09, ADDR-001
def _p95(values):
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * 0.95) - 1)]


# trace: NFR-PF-01, NFR-PF-02, NFR-PF-09, ADDR-001
class _Meter:
    """API 種別ごとに要求の送信から応答の受信完了までの時間（試験クライアントの処理を含む上限側の値）を記録する。"""

    def __init__(self, client):
        self.client = client
        self.samples: dict[str, list[tuple[float, int]]] = {}

    def __call__(self, kind, method, path, token=None, data=None):
        start = time.perf_counter()
        response = api(self.client, method, path, token, data)
        self.samples.setdefault(kind, []).append((time.perf_counter() - start, response.status_code))
        return response


# trace: NFR-PF-01, NFR-PF-02, NFR-PF-09, ADDR-001
def test_gf_022_response_time_p95_reference(api_client, make_user, admin, bearer, catalog, make_coupon):
    """GF-022 照会系・更新系・認証系 API の種別ごとの応答時間の95パーセンタイル（参考計測）。"""
    meter = _Meter(api_client)
    parent = catalog.category("計測分類")
    child = catalog.category("計測小分類", parent=parent)
    units = []
    for i in range(40):
        product = catalog.product(f"計測商品{i:02d}", description="応答時間の計測用", categories=(child,))
        units += [catalog.stock_unit(product, price=1000 + i * 10, stock=1000) for _ in range(2)]
    make_coupon("PERF-10", discount_type="percentage", discount_value=10)
    buyer = make_user(name="計測 購入者")
    token, admin_token = bearer(buyer), bearer(admin)
    for path in ("/api/categories/", "/api/products/", f"/api/products/{units[0].product_id}/"):
        api(api_client, "get", path)
    api(api_client, "get", "/api/cart/", token)
    api(api_client, "get", "/api/admin/stock-units/", admin_token)

    tokens = []
    for i in range(SAMPLES):
        data = {
            "email": f"perf{i:03d}@example.test",
            "password": PASSWORD,
            "password_confirmation": PASSWORD,
            "name": "計測 会員",
        }
        meter("auth.register", "post", "/api/auth/register/", data=data)
    for i in range(SAMPLES):
        login = meter(
            "auth.login", "post", "/api/auth/login/", data={"email": f"perf{i:03d}@example.test", "password": PASSWORD}
        )
        tokens.append(f"Bearer {body(login)['token']}")
    for member in tokens:
        meter("auth.me", "get", "/api/auth/me/", member)
    for member in tokens:
        meter("auth.logout", "post", "/api/auth/logout/", member)

    for i in range(SAMPLES):
        added = meter(
            "update.cart_add", "post", "/api/cart/items/", token, {"stock_unit_id": units[i % 80].pk, "quantity": 1}
        )
        item_id = body(added)["items"][0]["cart_item_id"]
        meter("update.cart_change", "patch", f"/api/cart/items/{item_id}/", token, {"quantity": 2})
        meter("update.cart_delete", "delete", f"/api/cart/items/{item_id}/", token)
    kept = body(add_item(api_client, token, units[0].pk, 1))["items"][0]["cart_item_id"]
    for _ in range(SAMPLES):
        meter("update.coupon_apply", "post", "/api/cart/coupon/", token, {"coupon_code": "PERF-10"})
        meter("update.coupon_remove", "delete", "/api/cart/coupon/", token)
    api(api_client, "delete", f"/api/cart/items/{kept}/", token)

    placed = []
    for i in range(3 * SAMPLES):
        for k, quantity in ((0, 2), (1, 2), (2, 1)):
            add_item(api_client, token, units[(i * 3 + k) % 80].pk, quantity)
        if i % 2 == 0:
            api(api_client, "post", "/api/cart/coupon/", token, {"coupon_code": "PERF-10"})
        placed.append(
            body(meter("update.place", "post", "/api/orders/", token, {"shipping_address": ADDRESS}))["order_id"]
        )
    for oid in placed[:SAMPLES]:
        meter("update.pay", "post", f"/api/orders/{oid}/payment/", token, {"mock_instruction": "approved"})
    for oid in placed[:SAMPLES]:
        meter("update.ship", "post", f"/api/admin/orders/{oid}/ship/", admin_token, {"tracking_number": "PERF-1"})
    for oid in placed[:SAMPLES]:
        meter("update.deliver", "post", f"/api/admin/orders/{oid}/deliver/", admin_token)
    for oid in placed[SAMPLES : 2 * SAMPLES]:
        meter("update.buyer_cancel", "post", f"/api/orders/{oid}/cancel/", token)
    for oid in placed[2 * SAMPLES :]:
        meter("update.admin_cancel", "post", f"/api/admin/orders/{oid}/cancel/", admin_token)

    for k, quantity in ((0, 2), (1, 2), (2, 1)):
        add_item(api_client, token, units[k].pk, quantity)
    today = datetime.now(tz=JST).date().isoformat()
    product_queries = [
        "",
        f"?category_id={child.pk}",
        "?keyword=計測",
        "?sort=price_asc",
        "?sort=price_desc",
        "?sort=name",
        "?page=2",
    ]
    stock_queries = ["", "?sku=SKU", "?product_name=計測", "?low_stock_only=true", "?page=2"]
    order_queries = [
        "",
        "?status=paid",
        f"?buyer_email={buyer.email}",
        f"?order_date_from={today}&order_date_to={today}",
    ]
    for i in range(SAMPLES):
        meter("read.categories", "get", "/api/categories/")
        meter("read.products", "get", "/api/products/" + product_queries[i % len(product_queries)])
        meter("read.product_detail", "get", f"/api/products/{units[(i * 7) % 80].product_id}/")
        meter("read.cart", "get", "/api/cart/", token)
        meter("read.order_history", "get", f"/api/orders/?page={1 + i % 2}", token)
        meter("read.order_detail", "get", f"/api/orders/{placed[i]}/", token)
        meter("read.stock_units", "get", "/api/admin/stock-units/" + stock_queries[i % len(stock_queries)], admin_token)
        meter("read.admin_orders", "get", "/api/admin/orders/" + order_queries[i % len(order_queries)], admin_token)
        meter("read.admin_order_detail", "get", f"/api/admin/orders/{placed[-1 - i]}/", admin_token)

    limits = {"read": 1.0, "update": 2.0, "auth": 2.0}
    summary = {}
    for kind, samples in sorted(meter.samples.items()):
        statuses = sorted({status for _, status in samples})
        seconds = [elapsed for elapsed, _ in samples]
        summary[kind] = {
            "requests": len(samples),
            "p95_seconds": round(_p95(seconds), 4),
            "max_seconds": round(max(seconds), 4),
            "limit_seconds": limits[kind.split(".")[0]],
            "statuses": statuses,
        }
    (REPO_DIR / "reports" / "integration-test" / "response-time-reference.json").write_text(
        json.dumps(
            {
                "condition": "結合試験の参考計測（単一利用者・逐次・小データ量、試験クライアントの処理時間を含む）。"
                "NFR-PF-01/02/09 の測定条件（ピーク負荷 同時155利用者・3年後データ量）の判定ではない",
                "measured_at": datetime.now(tz=JST).isoformat(timespec="seconds"),
                "summary": summary,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    assert len(summary) == 24
    for kind, row in summary.items():
        assert row["requests"] >= SAMPLES, kind
        assert all(200 <= s < 300 for s in row["statuses"]), (kind, row["statuses"])
        assert row["p95_seconds"] <= row["limit_seconds"], (kind, row)


# trace: NFR-PF-08, ADDR-001
def test_gf_023_list_response_cap(api_client, buyer, admin, bearer, catalog):
    """GF-023 分割表示の一覧は先頭・最終ページとも1回の応答が50件以下、商品分類一覧は分割しない（NFR-PF-08）。"""
    parent = catalog.category("件数分類")
    catalog.category("件数小分類", parent=parent)
    products = [catalog.product(f"件数商品{i:02d}") for i in range(45)]
    units = [catalog.stock_unit(p, stock=100) for p in products]
    units += [catalog.stock_unit(products[i], stock=100) for i in range(10)]
    token, admin_token = bearer(buyer), bearer(admin)
    for i in range(21):
        order_of(api_client, token, [(units[i], 1)])

    def pages(path, auth=None):
        first = body(api(api_client, "get", path, auth))
        last_page = max(first["total_pages"], 1)
        last = body(api(api_client, "get", f"{path}{'&' if '?' in path else '?'}page={last_page}", auth))
        return first, last

    checks = {
        "/api/products/": (None, 20, 45),
        "/api/orders/": (token, 20, 21),
        "/api/admin/stock-units/": (admin_token, 50, 55),
        "/api/admin/orders/": (admin_token, None, 21),
    }
    for path, (auth, size, total) in checks.items():
        first, last = pages(path, auth)
        assert first["total_count"] == total, (path, first["total_count"])
        assert first["page_size"] <= 50 and (size is None or first["page_size"] == size), path
        assert len(first["items"]) == min(first["page_size"], total) <= 50, path
        remainder = total - first["page_size"] * (first["total_pages"] - 1)
        assert len(last["items"]) == remainder <= 50, (path, len(last["items"]))
    categories = body(api(api_client, "get", "/api/categories/"))
    assert len(categories["items"]) == 2 and "page" not in categories


# trace: NFR-SC-12, FR-002, FR-011, FR-012, ADDR-002, ADDR-003
def test_gf_028_auth_means(api_client, web, buyer, admin, catalog):
    """GF-028 購入者・管理者はメールアドレス＋パスワードで認証、失敗は区別しない、来訪者は認証不要。"""
    product = catalog.product("認証確認商品")
    catalog.stock_unit(product)
    for user, user_type in ((buyer, "buyer"), (admin, "admin")):
        ok = api(api_client, "post", "/api/auth/login/", data={"email": user.email, "password": PASSWORD})
        assert ok.status_code == 200 and body(ok)["user"]["user_type"] == user_type
    wrong_password = api(api_client, "post", "/api/auth/login/", data={"email": buyer.email, "password": "Wrong0Pass9"})
    unknown_email = api(
        api_client, "post", "/api/auth/login/", data={"email": "nobody@example.test", "password": PASSWORD}
    )
    assert wrong_password.status_code == unknown_email.status_code == 401
    assert body(wrong_password) == body(unknown_email)
    assert error_of(wrong_password)["type"] == "authentication_failed"

    pages = []
    for email, password in ((buyer.email, "Wrong0Pass9"), ("nobody@example.test", PASSWORD)):
        client = web()
        fields = form_fields(text(client.get("/login/")), "/login/")
        fields.update({"email": email, "password": password})
        response = client.post("/login/", fields)
        assert response.status_code == 401
        pages.append(re.search(r'<p class="message error" role="alert">(.*?)</p>', text(response), re.S).group(1))
    assert pages[0] == pages[1] and "メールアドレスまたはパスワード" in pages[0]

    for path in ("/api/categories/", "/api/products/", f"/api/products/{product.pk}/"):
        assert api(api_client, "get", path).status_code == 200, path
    visitor = web()
    assert visitor.get("/").status_code == 200 and visitor.get(f"/products/{product.pk}/").status_code == 200


# trace: NFR-US-03, FR-001, FR-002, FR-030, FR-033, ADDR-012
def test_gf_029_jis_level3_4_roundtrip(api_client, web, catalog):
    """GF-029 氏名・配送先の JIS 第3・第4水準の漢字が画面・API で同じ文字で表示される（NFR-US-03）。"""
    from accounts.models import User
    from orders.models import Order, ShippingAddress

    name = f"{JIS3}{JIS4} 太郎"
    product = catalog.product("文字確認商品")
    unit = catalog.stock_unit(product, stock=10)
    client = web()
    fields = form_fields(text(client.get("/register/")), "/register/")
    fields.update({"email": "jis@example.test", "password": PASSWORD, "password_confirmation": PASSWORD, "name": name})
    assert client.post("/register/", fields).status_code == 302
    user = User.objects.get(email="jis@example.test")
    assert user.name == name
    login_fields = form_fields(text(client.get("/login/")), "/login/")
    login_fields.update({"email": "jis@example.test", "password": PASSWORD})
    assert client.post("/login/", login_fields).status_code == 302
    home = client.get("/")
    assert home["Content-Type"].lower().replace(" ", "") == "text/html;charset=utf-8"
    page = text(home)
    assert '<html lang="ja">' in page and f"{name}さん" in page

    add_fields = form_fields(text(client.get(f"/products/{product.pk}/")), "/cart/items/add/")
    add_fields.update({"stock_unit_id": str(unit.pk), "quantity": "1"})
    assert client.post("/cart/items/add/", add_fields).status_code == 302
    checkout = form_fields(text(client.get("/checkout/")), "/checkout/")
    checkout.update(
        {
            **ADDRESS,
            "recipient_name": f"受取 {JIS4}{JIS3}",
            "address_line1": f"{JIS3}町1-1",
            "address_line2": f"{JIS4}荘101",
        }
    )
    assert client.post("/checkout/", checkout).status_code == 302
    order = Order.objects.get(buyer=user)
    address = ShippingAddress.objects.get(order=order)
    assert (address.recipient_name, address.address_line1, address.address_line2) == (
        f"受取 {JIS4}{JIS3}",
        f"{JIS3}町1-1",
        f"{JIS4}荘101",
    )
    detail = text(client.get(f"/orders/{order.pk}/"))
    for value in (f"受取 {JIS4}{JIS3}", f"{JIS3}町1-1", f"{JIS4}荘101"):
        assert value in detail, value
    login = body(api(api_client, "post", "/api/auth/login/", data={"email": "jis@example.test", "password": PASSWORD}))
    assert login["user"]["name"] == name
    shown = body(api(api_client, "get", f"/api/orders/{order.pk}/", f"Bearer {login['token']}"))["shipping_address"]
    assert (shown["recipient_name"], shown["address_line1"], shown["address_line2"]) == (
        f"受取 {JIS4}{JIS3}",
        f"{JIS3}町1-1",
        f"{JIS4}荘101",
    )


# trace: NFR-US-04, FR-001, FR-030, ADDR-012
def _row_errors(page):
    """フォームの行ごとに（入力部品の name → その行に表示された理由の文言）を返す。"""
    rows = {}
    for row in re.findall(r'<div class="form-row">(.*?)</div>', page, re.S):
        names = re.findall(r'<(?:input|select)\b[^>]*\bname="([^"]+)"', row)
        errors = [html_lib.unescape(e) for e in re.findall(r'class="field-error">(.*?)</span>', row, re.S)]
        for control in names:
            rows[control] = errors
    return rows


# trace: NFR-US-04, FR-001, FR-030, ADDR-012
def test_gf_030_input_error_identifiable_all(api_client, web, buyer, bearer, catalog):
    """GF-030 複数項目の入力エラーを、誤りのある全項目分、項目を識別できる形で1回で表示し入力値を保持（NFR-US-04）。"""
    client = web()
    fields = form_fields(text(client.get("/register/")), "/register/")
    fields.update({"email": "not-mail", "password": "short", "password_confirmation": "other", "name": ""})
    page = client.post("/register/", fields)
    assert page.status_code == 400
    html = text(page)
    rows = _row_errors(html)
    labels = {"email": "メールアドレス：", "password": "パスワード：", "name": "氏名："}
    for control, label in labels.items():
        assert rows[control] and all(e.startswith(label) for e in rows[control]), (control, rows[control])
    assert input_value(html, "email") == "not-mail" and input_value(html, "password") == ""

    unit = catalog.stock_unit(stock=5)
    add_item(api_client, bearer(buyer), unit.pk, 1)
    shop = web()
    shop.force_login(buyer, backend="accounts.backends.SessionUserBackend")
    fields = form_fields(text(shop.get("/checkout/")), "/checkout/")
    fields.update(
        {
            "recipient_name": "",
            "postal_code": "12-34",
            "prefecture": "99",
            "address_line1": "千代田1",
            "phone_number": "abc",
        }
    )
    page = shop.post("/checkout/", fields)
    assert page.status_code == 400
    html = text(page)
    rows = _row_errors(html)
    expected = {
        "recipient_name": "受取人氏名：",
        "postal_code": "郵便番号：",
        "prefecture": "都道府県：",
        "phone_number": "電話番号：",
    }
    for control, label in expected.items():
        assert rows[control] and all(e.startswith(label) for e in rows[control]), (control, rows[control])
    assert rows["address_line1"] == [] and input_value(html, "address_line1") == "千代田1"
    assert input_value(html, "postal_code") == "12-34" and input_value(html, "phone_number") == "abc"


# trace: NFR-US-05, NFR-US-07, NFR-LG-08, ADDR-012
def _accessibility_issues(path, page):
    issues = []
    if '<html lang="ja">' not in page:
        issues.append("html lang")
    title = re.search(r"<title>(.*?)</title>", page, re.S)
    if not title or not title.group(1).split("｜")[0].strip():
        issues.append("title")
    labelled = set(re.findall(r'<label\b[^>]*\bfor="([^"]+)"', page))
    wrapped = " ".join(re.findall(r"<label\b[^>]*>(.*?)</label>", page, re.S))
    for tag in re.findall(r"<(?:input|select|textarea)\b[^>]*>", page):
        if re.search(r'type="(hidden|submit)"', tag):
            continue
        control_id = re.search(r'\bid="([^"]+)"', tag)
        if not ((control_id and control_id.group(1) in labelled) or tag in wrapped):
            issues.append(f"label: {tag[:80]}")
    for button in re.findall(r"<button\b[^>]*>(.*?)</button>", page, re.S):
        if not re.sub(r"<[^>]+>", "", button).strip():
            issues.append("button text")
    for link in re.findall(r"<a\b[^>]*>(.*?)</a>", page, re.S):
        if not re.sub(r"<[^>]+>", "", link).strip():
            issues.append("link text")
    for value in re.findall(r'tabindex="(-?\d+)"', page):
        if int(value) > 0:
            issues.append(f"tabindex {value}")
    if re.search(r"\son(click|keydown|keyup|keypress|mousedown|mouseup|mouseover)=", page, re.I):
        issues.append("inline event handler")
    for table in re.findall(r"<table\b.*?</table>", page, re.S):
        if "<th" not in table:
            issues.append("table without th")
    for img in re.findall(r"<img\b[^>]*>", page):
        if "alt=" not in img:
            issues.append("img alt")
    return [f"{path}: {issue}" for issue in issues]


# trace: NFR-US-05, NFR-US-07, NFR-LG-08, ADDR-012
def test_gf_031_accessible_html_structure(api_client, web, buyer, admin, bearer, catalog):
    """GF-031 全画面の HTML が適合レベル A の機械判定可能な達成基準とキーボード操作可能な部品構成を満たす。"""
    product = catalog.product("表示確認商品")
    unit = catalog.stock_unit(product, stock=10)
    token = bearer(buyer)
    order = order_of(api_client, token, [(unit, 1)])
    add_item(api_client, token, unit.pk, 1)
    visitor, shopper, manager = web(), web(), web()
    shopper.force_login(buyer, backend="accounts.backends.SessionUserBackend")
    manager.force_login(admin, backend="accounts.backends.SessionUserBackend")
    oid = order["order_id"]
    screens = [
        (visitor, "/"),
        (visitor, f"/products/{product.pk}/"),
        (visitor, "/register/"),
        (visitor, "/login/"),
        (shopper, "/cart/"),
        (shopper, "/checkout/"),
        (shopper, f"/orders/{oid}/complete/"),
        (shopper, f"/orders/{oid}/payment/"),
        (shopper, "/orders/"),
        (shopper, f"/orders/{oid}/"),
        (manager, "/manage/stock-units/"),
        (manager, "/manage/orders/"),
        (manager, f"/manage/orders/{oid}/"),
        (shopper, "/manage/orders/"),
    ]
    issues = []
    for client, path in screens:
        response = client.get(path)
        assert response.status_code in (200, 403), (path, response.status_code)
        issues += _accessibility_issues(path, text(response))
    assert issues == []


# trace: NFR-US-08, FR-011, FR-012, FR-021, FR-030, FR-031, FR-033, ADDR-012
def test_gf_032_purchase_screen_count(web, buyer, catalog):
    """GF-032 商品一覧から支払完了までを画面のリンク・フォームだけで操作し、経由する画面は7画面以内（NFR-US-08）。"""
    from orders.models import Order

    product = catalog.product("手順確認商品")
    unit = catalog.stock_unit(product, price=1000, stock=10)
    client = web()
    client.force_login(buyer, backend="accounts.backends.SessionUserBackend")
    visited = []

    def show(path):
        response = client.get(path)
        assert response.status_code == 200, path
        page = text(response)
        visited.append(re.search(r"<title>(.*?)｜", page).group(1))
        return page

    def link(page, pattern):
        match = re.search(rf'href="({pattern})"', page)
        assert match, pattern
        return match.group(1)

    listing = show("/")
    detail = show(link(listing, rf"/products/{product.pk}/"))
    fields = form_fields(detail, "/cart/items/add/")
    fields.update({"stock_unit_id": str(unit.pk), "quantity": "1"})
    added = client.post("/cart/items/add/", fields)
    assert added.status_code == 302 and added["Location"] == f"/products/{product.pk}/"
    cart = show(link(text(client.get(added["Location"])), "/cart/"))
    checkout = show(link(cart, "/checkout/"))
    fields = form_fields(checkout, "/checkout/")
    fields.update(ADDRESS)
    confirmed = client.post("/checkout/", fields)
    order = Order.objects.get(buyer=buyer)
    assert confirmed.status_code == 302 and confirmed["Location"] == f"/orders/{order.pk}/complete/"
    complete = show(confirmed["Location"])
    payment = show(link(complete, f"/orders/{order.pk}/payment/"))
    fields = form_fields(payment, f"/orders/{order.pk}/payment/")
    fields["mock_instruction"] = "approved"
    paid = client.post(f"/orders/{order.pk}/payment/", fields)
    assert paid.status_code == 302 and paid["Location"] == f"/orders/{order.pk}/"
    final = show(paid["Location"])
    assert "支払済" in final
    assert len(visited) <= 7 and len(set(visited)) == len(visited), visited
    assert visited == [
        "商品一覧",
        "商品詳細",
        "カート",
        "注文手続き（配送先入力・確認）",
        "注文完了",
        "支払（模擬決済）",
        "注文詳細",
    ], visited


# trace: NFR-US-09, FR-023, FR-030, FR-034, FR-043, FR-044, ADDR-012
def test_gf_033_confirm_before_irreversible(api_client, web, buyer, admin, bearer, catalog):
    """GF-033 取消できない5操作のフォームに確認文言があり確認の補助が読み込まれる（ダイアログ操作は対象外）。"""
    unit = catalog.stock_unit(stock=20)
    token = bearer(buyer)
    accepted = order_of(api_client, token, [(unit, 1)])
    shipped = order_of(api_client, token, [(unit, 1)])
    paid = order_of(api_client, token, [(unit, 1)])
    admin_token = bearer(admin)
    for oid in (shipped["order_id"], paid["order_id"]):
        assert pay(api_client, token, oid, "approved").status_code == 200
    assert api(api_client, "post", f"/api/admin/orders/{shipped['order_id']}/ship/", admin_token, {}).status_code == 200
    add_item(api_client, token, unit.pk, 1)
    shopper, manager = web(), web()
    shopper.force_login(buyer, backend="accounts.backends.SessionUserBackend")
    manager.force_login(admin, backend="accounts.backends.SessionUserBackend")

    def confirm_of(page, action_pattern):
        match = re.search(rf'<form method="post" action="{action_pattern}"[^>]*\bdata-confirm="([^"]+)"', page)
        assert match, action_pattern
        return html_lib.unescape(match.group(1))

    targets = [
        (shopper, "/checkout/", r"/checkout/"),
        (shopper, f"/orders/{accepted['order_id']}/", rf"/orders/{accepted['order_id']}/cancel/"),
        (shopper, "/cart/", r"/cart/items/\d+/delete/"),
        (manager, f"/manage/orders/{paid['order_id']}/", rf"/manage/orders/{paid['order_id']}/ship/"),
        (manager, f"/manage/orders/{shipped['order_id']}/", rf"/manage/orders/{shipped['order_id']}/deliver/"),
    ]
    for client, path, action in targets:
        page = text(client.get(path))
        assert '<script src="/static/common/site.js" defer></script>' in page, path
        message = confirm_of(page, action)
        assert "よろしいですか？" in message, (path, message)
    script = (REPO_DIR / "app" / "common" / "static" / "common" / "site.js").read_text(encoding="utf-8")
    assert 'getAttribute("data-confirm")' in script and "window.confirm(message)" in script
    assert "event.preventDefault()" in script


# trace: NFR-LG-02, FR-011, FR-012, FR-020, FR-030, FR-033, ADDR-012
def test_gf_036_tax_inclusive_display(api_client, web, buyer, bearer, catalog):
    """GF-036 商品価格は税込を主に税抜を併記、カート・注文の内訳に消費税額と税込の合計（NFR-LG-02）。"""
    product = catalog.product("総額表示商品")
    unit = catalog.stock_unit(product, price=1000, stock=10)
    client = web()
    client.force_login(buyer, backend="accounts.backends.SessionUserBackend")
    pair = "1,100円（税込）／1,000円（税抜）"
    for path in ("/", f"/products/{product.pk}/"):
        assert pair in text(client.get(path)), path
    add_item(api_client, bearer(buyer), unit.pk, 2)
    cart = text(client.get("/cart/"))
    assert pair in cart
    # 小計2,000円（5,000円未満）→送料500円、消費税額 (2,000+500)×10% = 250円、合計2,750円（FR-026）
    for page in (cart, text(client.get("/checkout/"))):
        assert re.search(r"消費税額</th><td>250円</td>", page) and re.search(r"合計（税込）</th><td>2,750円</td>", page)
    fields = form_fields(text(client.get("/checkout/")), "/checkout/")
    fields.update(ADDRESS)
    confirmed = client.post("/checkout/", fields)
    complete = text(client.get(confirmed["Location"]))
    assert "<dt>合計（税込）</dt><dd>2,750円</dd>" in complete
    order_path = confirmed["Location"].replace("complete/", "")
    detail = text(client.get(order_path))
    assert pair in detail
    assert re.search(r"消費税額</th><td>250円</td>", detail) and re.search(r"合計（税込）</th><td>2,750円</td>", detail)


# trace: NFR-LG-09, FR-030, FR-033, ADDR-001, ADDR-012
def test_gf_037_jis_x0401_prefectures(api_client, web, buyer, bearer, catalog):
    """GF-037 配送先の都道府県は JIS X 0401 の47コードだけを受け付け、名称で表示する（NFR-LG-09）。"""
    unit = catalog.stock_unit(stock=50)
    token = bearer(buyer)
    for code, label in (("01", "北海道"), ("13", "東京都"), ("47", "沖縄県")):
        add_item(api_client, token, unit.pk, 1)
        placed = place(api_client, token, {**ADDRESS, "prefecture": code})
        assert placed.status_code == 201, code
        assert body(placed)["shipping_address"]["prefecture_label"] == label
    for invalid in ("00", "48", "1", "東京都", 13, "JP-13"):
        add_item(api_client, token, unit.pk, 1)
        rejected = place(api_client, token, {**ADDRESS, "prefecture": invalid})
        assert rejected.status_code == 400, invalid
        assert "shipping_address.prefecture" in field_names(rejected), invalid
    client = web()
    client.force_login(buyer, backend="accounts.backends.SessionUserBackend")
    checkout = text(client.get("/checkout/"))
    select = re.search(r'<select id="prefecture" name="prefecture">(.*?)</select>', checkout, re.S).group(1)
    options = re.findall(r'<option value="([^"]*)"', select)
    assert options == [""] + [f"{n:02d}" for n in range(1, 48)]
