# trace: NFR-PF-06, NFR-PF-05, NFR-PF-04, NFR-PF-14, NFR-PF-15, NFR-PF-03, NFR-PF-11
# trace: ADDR-001, ADDR-004, ADDR-011, ADDR-012, ADDR-014
"""結合試験：AI
GAP_FILL（性能の参考計測：3年後データ量・同時利用者・処理能力・資源使用量・長時間・超過負荷。Revision 5）。

GF-061〜GF-063（origin=AI_GENERATED、generation_stage=GAP_FILL）。AI INITIAL は変更しない。
FULL Traceability C10（UNRESOLVED-e1d9dfe900863622）修正 cycle=2/3 で、NFR-PF-04/05/06/11/14/15 の測定条件
（12章 VDC-01〜VDC-03、DIF-01・DIF-09）を読み直し、開発環境の PC 1台で実施できる部分を測定条件に沿って行う。
- いずれも参考計測で、性能要件の合否判定ではない（nfr-verification-scope.json
  で PARTIAL_IT）。ENV-01（compose・Gunicorn）
  ではなく Django の試験用サーバー（live_server）と使い捨ての PostgreSQL 16 で行い、時間は要件の測定時間より短い。
- 判定するのは、測定条件に近い条件でも成り立つべき必要条件（システムエラー0件、業務エラーにならない条件での要求の成功、
  在庫・金額の整合、目標値の範囲内の95パーセンタイル）だけ。満たさない場合は要件を満たさない根拠として FAIL にする。
- 計測値は reports/integration-test/performance-reference.json に記録する。
"""

import json
import os
import random
import threading
import time
from pathlib import Path

import pytest

from tests.integration._bulk import OFFSET, generate
from tests.integration._helpers import ADDRESS, PASSWORD, add_item, api, body, form_fields, jst, order_of, pay
from tests.integration._load import HttpUser, Recorder, ResourceSampler, p95, summarize

REPO_DIR = Path(__file__).resolve().parents[3]
REFERENCE = REPO_DIR / "reports" / "integration-test" / "performance-reference.json"
_WRITE_LOCK = threading.Lock()
LIMITS = {"read": 1.0, "update": 2.0, "auth": 2.0, "screen": 2.0}


# trace: NFR-PF-06, NFR-PF-05, NFR-PF-11, ADDR-011
def _record(key, data):
    with _WRITE_LOCK:
        current = json.loads(REFERENCE.read_text(encoding="utf-8")) if REFERENCE.exists() else {}
        current[key] = data
        REFERENCE.write_text(json.dumps(current, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# trace: NFR-PF-06, ADDR-001
@pytest.mark.django_db
def test_gf_061_three_year_data_volume_reference(api_client, web, bearer):
    """GF-061 3年後データ量（VDC-01〜VDC-03）での API・画面の応答時間（単一利用者の参考計測）。"""
    from accounts.models import User
    from orders.models import Order

    started = time.monotonic()
    counts = generate(1.0)
    generation_seconds = round(time.monotonic() - started, 1)
    expected = {"User": 10_007, "Supplier": 35, "Category": 45, "Product": 600, "StockUnit": 1_600, "Coupon": 150}
    for name, value in expected.items():
        assert counts[name] == value, (name, counts[name])
    for name, value in (
        ("Order", 110_000),
        ("OrderItem", 330_000),
        ("ShippingAddress", 110_000),
        ("PaymentRecord", 120_000),
        ("OrderStatusHistory", 330_000),
    ):
        assert abs(counts[name] - value) <= value * 0.10, (name, counts[name])

    buyer = User.objects.get(pk=OFFSET + 1)
    admin = User.objects.get(pk=OFFSET + 10_000)
    token, admin_token = bearer(buyer), bearer(admin)
    own = list(Order.objects.filter(buyer=buyer).values_list("pk", flat=True))
    sample_orders = list(Order.objects.filter(pk__gte=OFFSET).order_by("?").values_list("pk", flat=True)[:50])
    samples = {}

    def measure(kind, call, *args, ok=(200,)):
        start = time.perf_counter()
        response = call(*args)
        samples.setdefault(kind, []).append(time.perf_counter() - start)
        assert response.status_code in ok, (kind, response.status_code, response.content[:300])
        return response

    rounds = 50
    product_queries = [
        "",
        f"?category_id={OFFSET + 15}",
        "?keyword=架空商品01",
        "?sort=price_asc",
        "?sort=name",
        "?page=5",
    ]
    admin_queries = [
        "",
        "?status=paid",
        f"?buyer_email={buyer.email}",
        "?order_date_from=2026-01-01&order_date_to=2026-03-31",
        "?page=50",
        "?status=delivered&page=20",
    ]
    stock_queries = ["", "?sku=V-SKU01", "?product_name=架空商品", "?low_stock_only=true", "?page=10"]
    for i in range(rounds):
        measure("read.categories", api, api_client, "get", "/api/categories/")
        measure("read.products", api, api_client, "get", "/api/products/" + product_queries[i % 6])
        measure("read.product_detail", api, api_client, "get", f"/api/products/{OFFSET + (i * 7) % 600}/")
        measure("read.cart", api, api_client, "get", "/api/cart/", token)
        measure("read.order_history", api, api_client, "get", "/api/orders/", token)
        measure("read.order_detail", api, api_client, "get", f"/api/orders/{own[i % len(own)]}/", token)
        measure(
            "read.stock_units", api, api_client, "get", "/api/admin/stock-units/" + stock_queries[i % 5], admin_token
        )
        measure("read.admin_orders", api, api_client, "get", "/api/admin/orders/" + admin_queries[i % 6], admin_token)
        measure(
            "read.admin_order_detail", api, api_client, "get", f"/api/admin/orders/{sample_orders[i]}/", admin_token
        )
    placed = []
    for i in range(rounds):
        for k, quantity in ((0, 2), (1, 2), (2, 1)):
            measure("update.cart_add", add_item, api_client, token, OFFSET + (i * 3 + k) % 1600, quantity)
        response = measure(
            "update.place",
            api,
            api_client,
            "post",
            "/api/orders/",
            token,
            {"shipping_address": dict(ADDRESS)},
            ok=(201,),
        )
        placed.append(body(response)["order_id"])
    for oid in placed:
        measure("update.pay", pay, api_client, token, oid, "approved")
    for oid in placed:
        measure(
            "update.ship",
            api,
            api_client,
            "post",
            f"/api/admin/orders/{oid}/ship/",
            admin_token,
            {"tracking_number": "VOL-1"},
        )

    page, admin_page = web(), web()
    for client, user in ((page, buyer), (admin_page, admin)):
        fields = form_fields(client.get("/login/").content.decode("utf-8"), "/login/")
        fields.update({"email": user.email, "password": PASSWORD})
        assert client.post("/login/", fields).status_code == 302
    for i in range(rounds):
        measure("screen.SCR-001", page.get, "/" + product_queries[i % 6])
        measure("screen.SCR-002", page.get, f"/products/{OFFSET + (i * 11) % 600}/")
        measure("screen.SCR-009", page.get, "/orders/")
        measure("screen.SCR-010", page.get, f"/orders/{own[i % len(own)]}/")
        measure("screen.SCR-101", admin_page.get, "/manage/stock-units/" + stock_queries[i % 5])
        measure("screen.SCR-102", admin_page.get, "/manage/orders/" + admin_queries[i % 6])
        measure("screen.SCR-103", admin_page.get, f"/manage/orders/{sample_orders[i]}/")

    summary = {}
    for kind, values in sorted(samples.items()):
        group = kind.split(".")[0]
        summary[kind] = {
            "requests": len(values),
            "p95_seconds": round(p95(values), 4),
            "max_seconds": round(max(values), 4),
            "limit_seconds": LIMITS[group],
        }
    _record(
        "GF-061_three_year_data_volume",
        {
            "condition": "3年後データ量（VDC-01〜VDC-03 の件数）を COPY "
            "で生成し ANALYZE 後、単一利用者・逐次で計測（試験クライアント、"
            "試験用トランザクション内）。ピーク負荷（同時155利用者）・ENV-01・ブラウザの資源読込は含まない参考計測",
            "measured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "generated_counts": counts,
            "generation_seconds": generation_seconds,
            "summary": summary,
        },
    )
    for kind, row in summary.items():
        assert row["p95_seconds"] <= row["limit_seconds"], (kind, row)


# trace: NFR-PF-05, NFR-PF-04, NFR-PF-11, ADDR-011
def _base_catalog(units=200, stock=99_999):
    from catalog.models import Category, Product, ProductCategory, StockUnit, Supplier
    from promotions.models import Coupon

    supplier = Supplier.objects.create(supplier_code="LOAD-SUP", name="負荷試験仕入先")
    top = Category.objects.create(category_code="load-top", name="負荷大分類", depth=1)
    child = Category.objects.create(category_code="load-sub", name="負荷小分類", parent=top, depth=2)
    created = []
    for i in range(units):
        if i % 2 == 0:
            product = Product.objects.create(
                product_code=f"LOAD-P{i:04d}",
                name=f"負荷商品{i:04d}",
                description="負荷試験用",
                registered_at=jst(2027, 1, 1),
            )
            ProductCategory.objects.create(product=product, category=child)
        created.append(
            StockUnit.objects.create(
                product=product,
                supplier=supplier,
                sku=f"LOAD-{i:05d}",
                variant_name=f"規格{i % 2 + 1}",
                price_excluding_tax=800 + (i % 30) * 50,
                stock_quantity=stock,
                updated_at=jst(2027, 1, 1),
            )
        )
    Coupon.objects.create(
        coupon_code="LOAD-CPN",
        name="負荷試験クーポン",
        discount_type="fixed_amount",
        discount_value=300,
        minimum_purchase_amount=0,
        valid_from=jst(2020, 1, 1),
        valid_to=jst(2099, 12, 31),
    )
    return child, created


# trace: NFR-PF-05, NFR-PF-04, NFR-PF-11, ADDR-011
def _users(make_user, count, prefix, user_type="buyer"):
    return [
        make_user(f"{prefix}{i:04d}@example.test", name=f"負荷 利用者{i:04d}", user_type=user_type)
        for i in range(count)
    ]


# trace: NFR-PF-05, NFR-PF-11, ADDR-001
class _Buyer(threading.Thread):
    """購入者の仮想利用者（照会：更新＝8：2、あわせて認証系。業務エラーにならない条件だけで要求する）。"""

    def __init__(
        self,
        base_url,
        recorder,
        user,
        units,
        category_id,
        deadline,
        seed,
        *,
        start_delay,
        think=(5.0, 15.0),
        tolerate_business_errors=False,
    ):
        super().__init__(daemon=True)
        self.http = HttpUser(base_url, recorder)
        self.email = user.email
        self.units = units
        self.category_id = category_id
        self.deadline = deadline
        self.rng = random.Random(seed)
        self.start_delay = start_delay
        self.think = think
        self.tolerate = tolerate_business_errors
        self.cart = {}
        self.coupon = False
        self.accepted = []
        self.orders = []
        self.unexpected = []

    def _check(self, kind, status, ok):
        if status in ok:
            return True
        if status >= 500 or status == 0 or not self.tolerate:
            self.unexpected.append((kind, status))
        return False

    def _login(self):
        status, payload = self.http.request(
            "login", "auth", "post", "/api/auth/login/", {"email": self.email, "password": PASSWORD}
        )
        if self._check("login", status, (200,)):
            self.http.token = f"Bearer {payload['token']}"

    def _sync(self, payload):
        """カートの応答（明細・適用中のクーポン）から状態を同期する（クーポンは明細の削除では外れない）。"""
        if isinstance(payload, dict) and "items" in payload:
            self.cart = {i["stock_unit_id"]: (i["cart_item_id"], i["quantity"]) for i in payload["items"]}
            self.coupon = bool(payload.get("coupon"))
            return True
        return False

    def _refresh_cart(self):
        status, payload = self.http.request("cart", "read", "get", "/api/cart/")
        if status == 200:
            self._sync(payload)

    def _read(self):
        choice = self.rng.randrange(6)
        if choice == 0:
            status, _ = self.http.request("categories", "read", "get", "/api/categories/")
        elif choice == 1:
            query = self.rng.choice(
                ["", f"?category_id={self.category_id}", "?keyword=負荷", "?sort=price_desc", "?page=2"]
            )
            status, _ = self.http.request("products", "read", "get", "/api/products/" + query)
        elif choice == 2:
            unit = self.rng.choice(self.units)
            status, _ = self.http.request("product_detail", "read", "get", f"/api/products/{unit[1]}/")
        elif choice == 3:
            status, payload = self.http.request("cart", "read", "get", "/api/cart/")
            if status == 200:
                self._sync(payload)
        elif choice == 4 or not self.orders:
            status, _ = self.http.request("order_history", "read", "get", "/api/orders/")
        else:
            status, _ = self.http.request("order_detail", "read", "get", f"/api/orders/{self.rng.choice(self.orders)}/")
        self._check("read", status, (200,))

    def _update(self):
        options = []
        if len(self.cart) < 3:
            options.append("cart_add")
        if self.cart:
            options += ["cart_change", "cart_delete", "place", "place"]
            options.append("coupon_remove" if self.coupon else "coupon_apply")
        if self.accepted:
            options += ["pay", "pay", "buyer_cancel"]
        kind = self.rng.choice(options)
        if kind == "cart_add":
            unit = self.rng.choice([u for u in self.units if u[0] not in self.cart])
            status, payload = self.http.request(
                kind,
                "update",
                "post",
                "/api/cart/items/",
                {"stock_unit_id": unit[0], "quantity": self.rng.randint(1, 2)},
            )
            if self._check(kind, status, (200,)):
                self._sync(payload)
        elif kind == "cart_change":
            unit = self.rng.choice(list(self.cart))
            item_id, _ = self.cart[unit]
            quantity = self.rng.randint(1, 3)
            status, payload = self.http.request(
                kind, "update", "patch", f"/api/cart/items/{item_id}/", {"quantity": quantity}
            )
            if self._check(kind, status, (200,)) and not self._sync(payload):
                self.cart[unit] = (item_id, quantity)
        elif kind == "cart_delete":
            unit = self.rng.choice(list(self.cart))
            status, payload = self.http.request(kind, "update", "delete", f"/api/cart/items/{self.cart[unit][0]}/")
            if self._check(kind, status, (200, 204)) and not self._sync(payload):
                self.cart.pop(unit)
        elif kind == "coupon_apply":
            status, payload = self.http.request(
                kind, "update", "post", "/api/cart/coupon/", {"coupon_code": "LOAD-CPN"}
            )
            if self._check(kind, status, (200,)) and not self._sync(payload):
                self.coupon = True
        elif kind == "coupon_remove":
            status, payload = self.http.request(kind, "update", "delete", "/api/cart/coupon/")
            if self._check(kind, status, (200, 204)) and not self._sync(payload):
                self.coupon = False
        elif kind == "place":
            status, payload = self.http.request(
                kind, "update", "post", "/api/orders/", {"shipping_address": dict(ADDRESS)}
            )
            if self._check(kind, status, (201,)):
                self.accepted.append(payload["order_id"])
                self.orders.append(payload["order_id"])
                self.cart, self.coupon = {}, False
            else:
                self._refresh_cart()
        elif kind == "pay":
            oid = self.accepted.pop(0)
            status, _ = self.http.request(
                kind, "update", "post", f"/api/orders/{oid}/payment/", {"mock_instruction": "approved"}
            )
            self._check(kind, status, (200,))
        else:
            oid = self.accepted.pop(0)
            status, _ = self.http.request(kind, "update", "post", f"/api/orders/{oid}/cancel/")
            self._check(kind, status, (200,))

    def _auth(self):
        choice = self.rng.randrange(3)
        if choice == 0:
            status, _ = self.http.request("me", "auth", "get", "/api/auth/me/")
            self._check("me", status, (200,))
        elif choice == 1:
            status, _ = self.http.request("logout", "auth", "post", "/api/auth/logout/")
            self._check("logout", status, (200, 204))
            self.http.token = None
            self._login()
        else:
            email = f"load-new-{self.rng.randrange(10**9):09d}-{id(self)}@example.test"
            status, _ = self.http.request(
                "register",
                "auth",
                "post",
                "/api/auth/register/",
                {"email": email, "password": PASSWORD, "password_confirmation": PASSWORD, "name": "負荷 新規会員"},
            )
            self._check("register", status, (201,))

    def run(self):
        time.sleep(self.start_delay)
        self._login()
        while time.monotonic() < self.deadline:
            time.sleep(self.rng.uniform(*self.think))
            if time.monotonic() >= self.deadline:
                break
            if self.http.token is None:
                self._login()
                continue
            roll = self.rng.random()
            if roll < 0.08:
                self._auth()
            elif roll < 0.08 + 0.92 * 0.8:
                self._read()
            else:
                self._update()


# trace: NFR-PF-05, ADDR-001
class _Admin(threading.Thread):
    """管理者の仮想利用者（注文一覧検索・注文詳細・出荷登録・配達完了登録・管理者キャンセル・在庫単位一覧）。"""

    def __init__(self, base_url, recorder, token, queues, deadline, seed, *, start_delay, think=(5.0, 15.0)):
        super().__init__(daemon=True)
        self.http = HttpUser(base_url, recorder)
        self.http.token = token
        self.queues = queues
        self.deadline = deadline
        self.rng = random.Random(seed)
        self.start_delay = start_delay
        self.think = think
        self.unexpected = []

    def _pop(self, name):
        with self.queues["lock"]:
            return self.queues[name].pop(0) if self.queues[name] else None

    def run(self):
        time.sleep(self.start_delay)
        while time.monotonic() < self.deadline:
            time.sleep(self.rng.uniform(*self.think))
            if time.monotonic() >= self.deadline:
                break
            kind = self.rng.choice(
                ["admin_orders", "admin_orders", "admin_order_detail", "stock_units", "ship", "deliver", "admin_cancel"]
            )
            status, ok = None, (200,)
            if kind == "admin_orders":
                query = self.rng.choice(["", "?status=paid", "?status=accepted", "?page=2"])
                status, _ = self.http.request(kind, "read", "get", "/api/admin/orders/" + query)
            elif kind == "admin_order_detail":
                with self.queues["lock"]:
                    oid = self.rng.choice(self.queues["all"])
                status, _ = self.http.request(kind, "read", "get", f"/api/admin/orders/{oid}/")
            elif kind == "stock_units":
                status, _ = self.http.request(kind, "read", "get", "/api/admin/stock-units/?page=2")
            elif kind == "ship" and (oid := self._pop("paid")) is not None:
                status, _ = self.http.request(
                    kind, "update", "post", f"/api/admin/orders/{oid}/ship/", {"tracking_number": f"LOAD-{oid}"}
                )
                if status == 200:
                    with self.queues["lock"]:
                        self.queues["shipped"].append(oid)
            elif kind == "deliver" and (oid := self._pop("shipped")) is not None:
                status, _ = self.http.request(kind, "update", "post", f"/api/admin/orders/{oid}/deliver/")
            elif kind == "admin_cancel" and (oid := self._pop("accepted")) is not None:
                status, _ = self.http.request(kind, "update", "post", f"/api/admin/orders/{oid}/cancel/")
            else:
                status, _ = self.http.request("admin_orders", "read", "get", "/api/admin/orders/")
            if status not in ok:
                self.unexpected.append((kind, status))


# trace: NFR-PF-05, NFR-PF-04, ADDR-001
def _admin_queues(api_client, bearer, make_user, units, paid=40, accepted=20):
    owner = make_user("load-owner@example.test", name="負荷 注文者")
    token = bearer(owner)
    queues = {"lock": threading.Lock(), "paid": [], "accepted": [], "shipped": [], "all": []}
    for i in range(paid + accepted):
        detail = order_of(api_client, token, [(units[i % len(units)], 1), (units[(i + 7) % len(units)], 2)])
        oid = detail["order_id"]
        if i < paid:
            assert pay(api_client, token, oid, "approved").status_code == 200
            queues["paid"].append(oid)
        else:
            queues["accepted"].append(oid)
        queues["all"].append(oid)
    return queues


# trace: NFR-PF-04, ADDR-001
def _arrivals(base_url, recorder, tokens, units, interval, deadline, results):
    """注文確定の一定間隔の到着（要求ごとに異なる購入者、3明細・5点のカート）。"""
    http = HttpUser(base_url, recorder)
    start = time.monotonic()
    for n, token in enumerate(tokens):
        due = start + n * interval
        if due >= deadline:
            break
        time.sleep(max(0.0, due - time.monotonic()))
        for k, quantity in ((0, 2), (1, 2), (2, 1)):
            status, _ = http.request(
                "arrival_cart_add",
                "update",
                "post",
                "/api/cart/items/",
                {"stock_unit_id": units[(n * 3 + k) % len(units)].pk, "quantity": quantity},
                token=token,
            )
            results["cart"].append(status)
        before = time.monotonic()
        status, payload = http.request(
            "arrival_place", "update", "post", "/api/orders/", {"shipping_address": dict(ADDRESS)}, token=token
        )
        results["place"].append(
            {
                "status": status,
                "elapsed": round(time.monotonic() - before, 4),
                "at": round(before - start, 1),
                "order_id": payload.get("order_id") if isinstance(payload, dict) else None,
            }
        )


# trace: NFR-PF-05, NFR-PF-03, ADDR-012
def _browser_watch(base_url, email, product_id, deadline, results):
    """負荷をかけた状態で、ブラウザ（Microsoft Edge）から購入者の画面を繰り返し表示し表示完了時間を記録する。"""
    from tests.integration._browser import Browser

    try:
        browser = Browser("edge", disable_cache=True)
    except AssertionError as exc:
        results["error"] = str(exc)
        return
    try:
        browser.open(f"{base_url}/login/")
        browser.submit("main form[action='/login/']", {"email": email, "password": PASSWORD})
        screens = {"SCR-001": "/", "SCR-002": f"/products/{product_id}/", "SCR-005": "/cart/", "SCR-009": "/orders/"}
        while time.monotonic() < deadline:
            for screen, path in screens.items():
                report = browser.open(base_url + path)
                timing = browser.timing()
                results["loads"].append(
                    {
                        "screen": screen,
                        "status": (report["document"] or {}).get("status"),
                        "display_complete_ms": round(timing["display_complete_ms"], 1),
                    }
                )
            time.sleep(1.0)
    except AssertionError as exc:
        results["error"] = str(exc)
    finally:
        browser.close()


# trace: NFR-PF-05, NFR-PF-04, NFR-PF-14, NFR-PF-15, NFR-PF-03, ADDR-001, ADDR-011
@pytest.mark.django_db(transaction=True)
def test_gf_062_concurrent_users_reference(live_server, api_client, make_user, bearer):
    """GF-062
    同時155利用者（思考時間5〜15秒）の負荷での応答時間・注文確定の処理能力・資源使用量・応答時間の推移（参考計測）。
    """
    duration = float(os.environ.get("IT_LOAD_SECONDS", "300"))
    container = os.environ.get("IT_DB_CONTAINER")
    assert container, "IT_DB_CONTAINER（run_integration.py が設定する使い捨て DB のコンテナ名）が必要"
    base_url = live_server.url.replace("localhost", "127.0.0.1")
    category, units = _base_catalog()
    unit_pairs = [(u.pk, u.product_id) for u in units]
    buyers = _users(make_user, 150, "load-buyer")
    admins = [bearer(u) for u in _users(make_user, 5, "load-admin", user_type="admin")]
    arrival_tokens = [bearer(u) for u in _users(make_user, int(duration // 15) + 1, "load-arrival")]
    queues = _admin_queues(api_client, bearer, make_user, units)
    watcher_user = make_user("load-watch@example.test", name="負荷 画面確認")

    recorder = Recorder()
    deadline = time.monotonic() + duration
    sampler = ResourceSampler(container)
    sampler.start()
    rng = random.Random(62)
    threads = [
        _Buyer(base_url, recorder, user, unit_pairs, category.pk, deadline, 1000 + i, start_delay=rng.uniform(0, 10))
        for i, user in enumerate(buyers)
    ]
    threads += [
        _Admin(base_url, recorder, token, queues, deadline, 2000 + i, start_delay=rng.uniform(0, 10))
        for i, token in enumerate(admins)
    ]
    arrivals = {"cart": [], "place": []}
    browser_results = {"loads": [], "error": None}
    helpers = [
        threading.Thread(
            target=_arrivals, args=(base_url, recorder, arrival_tokens, units, 15.0, deadline, arrivals), daemon=True
        ),
        threading.Thread(
            target=_browser_watch,
            args=(base_url, watcher_user.email, units[0].product_id, deadline, browser_results),
            daemon=True,
        ),
    ]
    for thread in threads + helpers:
        thread.start()
    for thread in threads + helpers:
        thread.join(timeout=duration + 300)
    resources = sampler.stop()
    assert all(not t.is_alive() for t in threads + helpers)

    samples = recorder.snapshot()
    summary = summarize(samples)
    system_errors = [s for s in samples if s["status"] >= 500 or s["status"] == 0]
    unexpected = [u for t in threads for u in t.unexpected]
    window = 60.0

    def trend(group=None):
        rows = [s for s in samples if group is None or s["group"] == group]
        head = p95([s["elapsed"] for s in rows if s["at"] <= window])
        tail = p95([s["elapsed"] for s in rows if s["at"] >= duration - window])
        return {
            "first_window_p95": head,
            "last_window_p95": tail,
            "degradation_ratio": round(tail / head - 1, 4) if head and tail else None,
        }

    trends = {"all": trend(), "read": trend("read"), "update": trend("update"), "auth": trend("auth")}
    screen_rows = {}
    for row in browser_results["loads"]:
        screen_rows.setdefault(row["screen"], []).append(row)
    screens = {
        screen: {
            "loads": len(rows),
            "p95_display_complete_ms": round(p95([r["display_complete_ms"] for r in rows]), 1),
            "statuses": sorted({r["status"] for r in rows}),
        }
        for screen, rows in sorted(screen_rows.items())
    }
    memory = [r["app_working_set_bytes"] for r in resources if r.get("app_working_set_bytes")]
    db_memory = [r["db"]["mem_percent"] for r in resources if r.get("db")]
    _record(
        "GF-062_concurrent_users",
        {
            "condition": "仮想利用者 155（購入者 150・管理者 5）、思考時間 "
            f"5〜15秒、{int(duration)}秒間、照会：更新＝8：2＋認証系。"
            "注文確定の到着 4件/分（要求ごとに異なる購入者、3明細・5点）。live_server（Django "
            "の試験用サーバー）と使い捨て PostgreSQL 16、"
            "小データ量（在庫単位 200）、負荷の発生元・ブラウザは同じ "
            "PC（DIF-09）。要件の測定時間（NFR-PF-04 60分・NFR-PF-15 2時間）"
            "・3年後データ量・ENV-01 の判定ではない参考計測",
            "measured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "duration_seconds": duration,
            "virtual_users": {"buyers": len(buyers), "admins": len(admins)},
            "requests": len(samples),
            "system_errors": len(system_errors),
            "unexpected_responses": unexpected[:50],
            "summary": summary,
            "pf04_arrivals": {
                "interval_seconds": 15.0,
                "placed": arrivals["place"],
                "succeeded": sum(1 for r in arrivals["place"] if r["status"] == 201),
                "p95_seconds": p95([r["elapsed"] for r in arrivals["place"]]),
            },
            "pf15_trend": {
                "window_seconds": window,
                "by_group": trends,
                "app_working_set_first_last": [memory[0], memory[-1]] if memory else None,
                "db_mem_percent_first_last": [db_memory[0], db_memory[-1]] if db_memory else None,
            },
            "pf14_resources": {
                "cpu_count": os.cpu_count(),
                "physical_memory_bytes": sampler.physical_memory,
                "samples": resources,
            },
            "pf03_browser_under_load": {"browser": "edge", "error": browser_results["error"], "screens": screens},
        },
    )
    assert not system_errors, system_errors[:10]
    assert not unexpected, unexpected[:20]
    assert all(not t.unexpected for t in threads)
    assert len(arrivals["place"]) >= int(duration // 15)
    assert all(r["status"] == 201 for r in arrivals["place"]), arrivals["place"]
    assert all(s == 200 for s in arrivals["cart"])
    for group in ("read", "update", "auth"):
        assert summary[group]["p95_seconds"] <= LIMITS[group], (group, summary[group])
    assert browser_results["error"] is None, browser_results["error"]
    assert set(screens) == {"SCR-001", "SCR-002", "SCR-005", "SCR-009"}
    for screen, row in screens.items():
        assert row["statuses"] == [200], (screen, row)
        assert row["p95_display_complete_ms"] <= LIMITS["screen"] * 1000, (screen, row)
    assert len(resources) >= 3 and all(r.get("db") for r in resources), resources


# trace: NFR-PF-11, ADDR-004, ADDR-011
@pytest.mark.django_db(transaction=True)
def test_gf_063_overload_consistency_reference(live_server, api_client, make_user, bearer):
    """GF-063 想定の2倍（310仮想利用者）の負荷で、システムエラー率・在庫数量・金額整合を確認する（参考計測）。"""
    from catalog.models import StockUnit
    from orders.models import Order, OrderItem

    duration = float(os.environ.get("IT_OVERLOAD_SECONDS", "120"))
    base_url = live_server.url.replace("localhost", "127.0.0.1")
    category, units = _base_catalog(units=40, stock=5)
    initial = {u.pk: u.stock_quantity for u in units}
    unit_pairs = [(u.pk, u.product_id) for u in units]
    buyers = _users(make_user, 300, "over-buyer")
    admins = [bearer(u) for u in _users(make_user, 10, "over-admin", user_type="admin")]
    queues = _admin_queues(api_client, bearer, make_user, units, paid=30, accepted=10)
    recorder = Recorder()
    deadline = time.monotonic() + duration
    rng = random.Random(63)
    threads = [
        _Buyer(
            base_url,
            recorder,
            user,
            unit_pairs,
            category.pk,
            deadline,
            3000 + i,
            start_delay=rng.uniform(0, 10),
            tolerate_business_errors=True,
        )
        for i, user in enumerate(buyers)
    ]
    threads += [
        _Admin(base_url, recorder, token, queues, deadline, 4000 + i, start_delay=rng.uniform(0, 10))
        for i, token in enumerate(admins)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=duration + 300)
    assert all(not t.is_alive() for t in threads)

    samples = recorder.snapshot()
    system_errors = [s for s in samples if s["status"] >= 500 or s["status"] == 0]
    business = [s for s in samples if 400 <= s["status"] < 500]
    negative = list(StockUnit.objects.filter(stock_quantity__lt=0).values_list("sku", flat=True))
    broken = []
    for order in Order.objects.all():
        if order.discounted_subtotal != order.subtotal - order.discount_amount or (
            order.total_amount != order.discounted_subtotal + order.shipping_fee + order.tax_amount
        ):
            broken.append(order.order_number)
    conservation = []
    for unit_id, quantity in initial.items():
        reserved = sum(
            OrderItem.objects.filter(stock_unit_id=unit_id)
            .exclude(order__status="cancelled")
            .values_list("quantity", flat=True)
        )
        current = StockUnit.objects.get(pk=unit_id).stock_quantity
        if quantity - current != reserved:
            conservation.append(
                {"stock_unit_id": unit_id, "initial": quantity, "current": current, "reserved": reserved}
            )
    ratio = len(system_errors) / len(samples) if samples else None
    _record(
        "GF-063_overload",
        {
            "condition": "仮想利用者 310（購入者 300・管理者 10。想定 155 の2倍）、思考時間 "
            f"5〜15秒、{int(duration)}秒間。在庫数量 5 の"
            "在庫単位 40 件に注文を集中させ在庫不足（業務エラー）を発生させる。live_server "
            "と使い捨て PostgreSQL 16。要件の 10分間・"
            "3年後データ量・ENV-01 の判定ではない参考計測",
            "measured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "duration_seconds": duration,
            "requests": len(samples),
            "system_errors": len(system_errors),
            "system_error_ratio": ratio,
            "business_errors": len(business),
            "orders": Order.objects.count(),
            "negative_stock_units": negative,
            "amount_inconsistent_orders": broken,
            "stock_conservation_violations": conservation,
            "summary": summarize(samples),
        },
    )
    assert samples and ratio <= 0.01, (len(system_errors), len(samples), system_errors[:10])
    assert business, "在庫不足（業務エラー）が発生する条件になっていない"
    assert not negative, negative
    assert not broken, broken[:20]
    assert not conservation, conservation[:10]
    assert Order.objects.filter(status__in=["accepted", "paid", "shipped", "delivered"]).exists()
