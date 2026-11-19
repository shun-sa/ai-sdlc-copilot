# trace: ADDR-011, ADDR-002
"""単体テスト共通のフィクスチャ（試験データの生成・時刻の固定・ログの捕捉）。

- DB を使うテストは pytest-django の使い捨て試験用データベース（Docker の PostgreSQL 16 コンテナ上の test_*）を使い、
  各テストのトランザクションはテスト終了時にロールバックされる（他テストの状態に依存しない）。
- 現在日時の固定は試験支援モジュールの試験用状態（ADDR-011）で行い、テスト終了時に必ず clear する（INV-003）。
- 本番・共有 DB の認証情報は使わない（接続先は環境変数 DB_* で与える）。
"""

import hashlib
import itertools
import json
import logging
import platform
import re
import secrets
import sys
from contextlib import contextmanager
from datetime import datetime, timedelta
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth.hashers import make_password

JST = ZoneInfo("Asia/Tokyo")
_SEQ = itertools.count(1)
_HASH_CACHE: dict[str, str] = {}
DEFAULT_PASSWORD = "Passw0rdTest"


# trace: ADDR-011
def jst(year: int, month: int, day: int, hour: int = 0, minute: int = 0, second: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, second, tzinfo=JST)


# trace: ADDR-011
def next_seq() -> int:
    return next(_SEQ)


# trace: ADDR-011
def hashed(password: str) -> str:
    """同じパスワードの保持値を使い回す（PBKDF2 の計算時間を抑える。照合は本物のハッシャーで行う）。"""
    if password not in _HASH_CACHE:
        _HASH_CACHE[password] = make_password(password)
    return _HASH_CACHE[password]


# trace: ADDR-011
RUNTIME_DISTRIBUTIONS = (
    "django",
    "djangorestframework",
    "psycopg",
    "psycopg-binary",
    "pytest",
    "pytest-django",
    "pytest-cov",
    "coverage",
)


# trace: ADDR-011
@pytest.fixture(scope="session", autouse=True)
def _runtime_versions(record_testsuite_property):
    """実行時の Python・主要依存の版を JUnit の testsuite property（runtime.*）に記録する。

    unit-test-evidence の runtime_environment に、同じ実行の結果として使う（固定版との一致の確認用）。
    """
    repo = Path(__file__).resolve().parents[3]
    prefix = Path(sys.prefix).resolve()
    record_testsuite_property("runtime.python", platform.python_version())
    record_testsuite_property("runtime.virtualenv", str(sys.prefix != sys.base_prefix).lower())
    record_testsuite_property(
        "runtime.prefix", prefix.relative_to(repo).as_posix() if prefix.is_relative_to(repo) else "outside-repository"
    )
    for dist in RUNTIME_DISTRIBUTIONS:
        try:
            installed = version(dist)
        except PackageNotFoundError:
            installed = "not-installed"
        record_testsuite_property(f"runtime.{dist}", installed)


# trace: ADDR-011
def snapshot_order(order, units=()) -> dict:
    """異常終了の事後条件の比較用に、注文と関連データの現在の内容を返す。

    注文の状態・各日時・配送伝票番号・各金額、注文明細、配送先、注文状態履歴、決済記録、
    指定した在庫単位の在庫数量・更新日時（FR-031・FR-034・FR-043〜FR-045 の「処理前から変化していない」）。
    """
    from catalog.models import StockUnit
    from orders.models import Order, OrderItem, OrderStatusHistory, PaymentRecord, ShippingAddress

    current = Order.objects.filter(pk=order.pk).values().get()
    return {
        "order": current,
        "items": list(OrderItem.objects.filter(order_id=order.pk).order_by("pk").values()),
        "address": list(ShippingAddress.objects.filter(order_id=order.pk).values()),
        "history": list(OrderStatusHistory.objects.filter(order_id=order.pk).order_by("pk").values()),
        "payments": list(PaymentRecord.objects.filter(order_id=order.pk).order_by("pk").values()),
        "stock": list(
            StockUnit.objects.filter(pk__in=[u.pk for u in units])
            .order_by("pk")
            .values_list("pk", "stock_quantity", "updated_at")
        ),
    }


# trace: ADDR-011
_WRITE_SQL = re.compile(r'^\s*(UPDATE|INSERT INTO|DELETE FROM)\s+"([^"]+)"', re.IGNORECASE)


# trace: ADDR-011
@pytest.fixture
def fail_sql(db):
    """指定したモデルのテーブルへの更新系 SQL（UPDATE・INSERT）の n 回目で DatabaseError を発生させる。

    DB 障害の差し込み。SQL は DB へ送らずに例外とする。差し込みまでに実行された更新系 SQL を
    executed に (種類, テーブル) で記録し、
    障害の前に在庫戻し等の更新が実際に行われていたこと（取り消しの対象があったこと）をテストで確認できるようにする。
    """
    from django.db import DatabaseError, connection

    @contextmanager
    def _fail(model, verb: str, occurrence: int = 1):
        table = model._meta.db_table
        verb = verb.upper()
        state = SimpleNamespace(executed=[], injected=False)
        seen = 0

        def wrapper(execute, sql, params, many, context):
            nonlocal seen
            match = _WRITE_SQL.match(sql)
            kind = match.group(1).split()[0].upper() if match else None
            if match and kind == verb and match.group(2) == table:
                seen += 1
                if seen == occurrence:
                    state.injected = True
                    raise DatabaseError(f"injected fault: {verb} {table} #{occurrence}")
            result = execute(sql, params, many, context)
            if match:
                state.executed.append((kind, match.group(2)))
            return result

        with connection.execute_wrapper(wrapper):
            yield state

    return _fail


# trace: ADDR-011
@pytest.fixture(autouse=True)
def _database_statements(request):
    """各テストが試験用 DB へ発行した SQL 文の数を JUnit の property（database_statements）に記録する。

    unit-test-evidence の database Criterion の分類（DB を実際に使ったテストだけを対象にする）に、
    同じ実行の結果として使う。
    """
    from django.db import connections

    count = 0

    def _count(execute, sql, params, many, context):
        nonlocal count
        count += 1
        return execute(sql, params, many, context)

    with connections["default"].execute_wrapper(_count):
        yield
    request.node.user_properties.append(("database_statements", count))


# trace: ADDR-011
@pytest.fixture
def freeze(db):
    """試験用状態の固定の現在日時を設定する（ADDR-011）。テスト終了時に clear する。"""
    from test_support import state

    def _freeze(moment: datetime) -> datetime:
        state.set_state(fixed_now=moment)
        return moment

    yield _freeze
    state.clear_state()


# trace: ADDR-011
@pytest.fixture
def test_state(db):
    """試験用状態（模擬決済の応答モード・遅延・注文確定の障害点）を設定する。"""
    from test_support import state

    yield state.set_state
    state.clear_state()


# trace: ADDR-011
@pytest.fixture
def make_user(db):
    from accounts.models import User

    def _make(
        email: str | None = None,
        *,
        password: str = DEFAULT_PASSWORD,
        name: str = "試験 太郎",
        user_type: str = "buyer",
        registered_at: datetime | None = None,
    ) -> User:
        n = next_seq()
        return User.objects.create(
            email=email or f"user{n}@example.test",
            name=name,
            user_type=user_type,
            registered_at=registered_at or jst(2027, 4, 1, 9, 0, 0),
            password=hashed(password),
        )

    return _make


# trace: ADDR-011
@pytest.fixture
def buyer(make_user):
    return make_user(name="購入者 一郎")


# trace: ADDR-011
@pytest.fixture
def other_buyer(make_user):
    return make_user(name="購入者 二郎")


# trace: ADDR-011
@pytest.fixture
def admin(make_user):
    return make_user(name="管理者 花子", user_type="admin")


# trace: ADDR-011
@pytest.fixture
def catalog(db):
    """商品カタログの試験データの生成部品。"""
    from catalog.models import Category, Product, ProductCategory, StockUnit, Supplier

    class Factory:
        def supplier(self, code: str | None = None, name: str = "仕入先") -> Supplier:
            return Supplier.objects.create(supplier_code=code or f"SUP-{next_seq()}", name=name)

        def category(
            self,
            name: str | None = None,
            parent: Category | None = None,
            display_order: int = 0,
            code: str | None = None,
        ) -> Category:
            n = next_seq()
            return Category.objects.create(
                category_code=code or f"cat-{n}",
                name=name or f"分類{n}",
                parent=parent,
                depth=(parent.depth + 1) if parent else 1,
                display_order=display_order,
            )

        def product(
            self,
            name: str | None = None,
            *,
            description: str = "",
            is_public: bool = True,
            registered_at: datetime | None = None,
            categories: tuple = (),
            code: str | None = None,
        ) -> Product:
            n = next_seq()
            product = Product.objects.create(
                product_code=code or f"P-{n}",
                name=name or f"商品{n}",
                description=description,
                is_public=is_public,
                registered_at=registered_at or jst(2027, 1, 1) + timedelta(minutes=n),
            )
            for category in categories:
                ProductCategory.objects.create(product=product, category=category)
            return product

        def stock_unit(
            self,
            product: Product | None = None,
            *,
            price: int = 1000,
            stock: int = 10,
            sku: str | None = None,
            variant_name: str | None = None,
            supplier: Supplier | None = None,
        ) -> StockUnit:
            n = next_seq()
            return StockUnit.objects.create(
                product=product or self.product(),
                supplier=supplier or self.supplier(),
                sku=sku or f"SKU-{n:05d}",
                variant_name=variant_name or f"規格{n}",
                price_excluding_tax=price,
                stock_quantity=stock,
                updated_at=jst(2027, 1, 1),
            )

    return Factory()


# trace: ADDR-011
@pytest.fixture
def make_coupon(db):
    from promotions.models import Coupon

    def _make(
        code: str | None = None,
        *,
        discount_type: str = "fixed_amount",
        discount_value: int = 500,
        minimum_purchase_amount: int = 0,
        valid_from: datetime | None = None,
        valid_to: datetime | None = None,
        name: str = "試験クーポン",
    ) -> Coupon:
        return Coupon.objects.create(
            coupon_code=code or f"CPN-{next_seq()}",
            name=name,
            discount_type=discount_type,
            discount_value=discount_value,
            minimum_purchase_amount=minimum_purchase_amount,
            valid_from=valid_from or jst(2020, 1, 1),
            valid_to=valid_to or jst(2099, 12, 31, 23, 59, 59),
        )

    return _make


# trace: ADDR-011
@pytest.fixture
def make_cart(db):
    """利用中カートと明細を直接作成する（FR-020〜FR-025 の事前状態）。"""
    from carts.models import Cart, CartItem

    def _make(user, items=(), coupon=None, created_at: datetime | None = None) -> Cart:
        at = created_at or jst(2027, 4, 1, 10, 0, 0)
        cart = Cart.objects.create(buyer=user, status="active", coupon=coupon, created_at=at, updated_at=at)
        for offset, (unit, quantity) in enumerate(items):
            CartItem.objects.create(
                cart=cart, stock_unit=unit, quantity=quantity, added_at=at + timedelta(seconds=offset)
            )
        return cart

    return _make


# trace: ADDR-011
@pytest.fixture
def make_order(db):
    """注文を指定した状態で直接作成する（FR-031〜FR-045 の事前状態）。"""
    from orders.models import Order, OrderItem, OrderStatusHistory, ShippingAddress

    def _make(
        buyer,
        lines,
        *,
        status: str = "accepted",
        ordered_at: datetime | None = None,
        total_amount: int | None = None,
    ) -> Order:
        n = next_seq()
        at = ordered_at or jst(2027, 4, 10, 12, 0, 0)
        subtotal = sum(unit.price_excluding_tax * quantity for unit, quantity in lines)
        shipping = 0 if subtotal >= 5000 else 500
        tax = (subtotal + shipping) * 10 // 100
        timestamps = {}
        if status in ("paid", "shipped", "delivered"):
            timestamps["paid_at"] = at + timedelta(minutes=1)
        if status in ("shipped", "delivered"):
            timestamps["shipped_at"] = at + timedelta(minutes=2)
        if status == "delivered":
            timestamps["delivered_at"] = at + timedelta(minutes=3)
        if status == "cancelled":
            timestamps["cancelled_at"] = at + timedelta(minutes=1)
        order = Order.objects.create(
            order_number=f"PO-{90000000 + n:08d}",
            buyer=buyer,
            status=status,
            subtotal=subtotal,
            discount_amount=0,
            discounted_subtotal=subtotal,
            shipping_fee=shipping,
            tax_amount=tax,
            total_amount=total_amount if total_amount is not None else subtotal + shipping + tax,
            ordered_at=at,
            **timestamps,
        )
        for unit, quantity in lines:
            OrderItem.objects.create(
                order=order,
                stock_unit=unit,
                sku=unit.sku,
                product_name=unit.product.name,
                variant_name=unit.variant_name,
                unit_price=unit.price_excluding_tax,
                quantity=quantity,
                line_amount=unit.price_excluding_tax * quantity,
            )
        ShippingAddress.objects.create(
            order=order,
            recipient_name="受取 太郎",
            postal_code="1000001",
            prefecture="13",
            address_line1="千代田区千代田1-1",
            address_line2=None,
            phone_number="0312345678",
        )
        OrderStatusHistory.objects.create(
            order=order, from_status=None, to_status="accepted", changed_at=at, actor=buyer, actor_user_type="buyer"
        )
        return order

    return _make


# trace: ADDR-011, ADDR-002
@pytest.fixture
def bearer(db):
    """Web API のログイン状態（ADDR-002 DD-001：SHA-256 照合値だけを保持）を作成し Authorization ヘッダー値を返す。"""
    from accounts.models import ApiLoginState

    def _issue(user, logged_in_at: datetime | None = None) -> str:
        token = secrets.token_urlsafe(32)
        at = logged_in_at or datetime.now(tz=JST).replace(microsecond=0)
        ApiLoginState.objects.create(
            token_hash=hashlib.sha256(token.encode("utf-8")).hexdigest(),
            user=user,
            logged_in_at=at,
            expires_at=at + timedelta(hours=24),
        )
        return f"Bearer {token}"

    return _issue


# trace: ADDR-011
@pytest.fixture
def api_client():
    from rest_framework.test import APIClient

    return APIClient()


# trace: ADDR-011
@pytest.fixture
def web_client():
    from django.test import Client

    return Client()


# trace: ADDR-011
@pytest.fixture
def login_web():
    """画面のログイン状態（Django セッション）を開始した Client を返す。"""
    from django.test import Client

    def _login(user, *, enforce_csrf: bool = False) -> Client:
        client = Client(enforce_csrf_checks=enforce_csrf)
        client.force_login(user, backend="accounts.backends.SessionUserBackend")
        return client

    return _login


# trace: ADDR-011
class _Capture(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        from common.logging import JsonFormatter

        self.setFormatter(JsonFormatter())
        self.lines: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(self.format(record))

    def records(self) -> list[dict]:
        return [json.loads(line) for line in self.lines]


# trace: ADDR-011
@pytest.fixture
def app_logs():
    """アプリケーションログ（minicommerce ロガー：LOG-01〜LOG-06）を JSON の行として捕捉する。"""
    handler = _Capture()
    logger = logging.getLogger("minicommerce")
    logger.addHandler(handler)
    try:
        yield handler
    finally:
        logger.removeHandler(handler)
