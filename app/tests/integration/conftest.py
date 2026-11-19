# trace: ADDR-011
"""結合試験のフィクスチャ（試験データの生成・ログイン状態・試験用状態・ログの捕捉）。

- DB は pytest-django が使い捨ての PostgreSQL 16 上に作成・破棄する試験用データベース（test_*）を使う
  （ADDR-011 DD-006）。
- 複数の接続・スレッドを使う同時実行試験は transaction=True（コミット方式）で行う（ADDR-011 DD-010）。
- 試験用状態（現在日時・模擬決済・障害点）は各テストの終了時に必ず clear する。
- 認証情報・試験データはすべて架空の値で、本番・共有 DB を使わない。
"""

import hashlib
import itertools
import json
import logging
import secrets
import threading
from datetime import datetime, timedelta

import pytest
from django.contrib.auth.hashers import make_password

from tests.integration._helpers import JST, PASSWORD, jst

_SEQ = itertools.count(1)
_HASHES: dict[str, str] = {}
_HASH_LOCK = threading.Lock()


def _hashed(password: str) -> str:
    with _HASH_LOCK:
        if password not in _HASHES:
            _HASHES[password] = make_password(password)
        return _HASHES[password]


def next_seq() -> int:
    return next(_SEQ)


@pytest.fixture
def set_state(db):
    """試験用状態（固定の現在日時・模擬決済の遅延/応答・注文確定の障害点）を設定する。

    終了時に必ず clear する（ADDR-011 INV-003）。
    """
    from test_support import state

    yield state.set_state
    state.clear_state()


@pytest.fixture
def make_user(db):
    from accounts.models import User

    def _make(email=None, *, password=PASSWORD, name="試験 太郎", user_type="buyer"):
        n = next_seq()
        return User.objects.create(
            email=email or f"it-user{n}@example.test",
            name=name,
            user_type=user_type,
            registered_at=jst(2027, 4, 1, 9, 0, 0),
            password=_hashed(password),
        )

    return _make


@pytest.fixture
def buyer(make_user):
    return make_user(name="購入者 一郎")


@pytest.fixture
def other_buyer(make_user):
    return make_user(name="購入者 二郎")


@pytest.fixture
def admin(make_user):
    return make_user(name="管理者 花子", user_type="admin")


@pytest.fixture
def bearer(db):
    """Web API のログイン状態を直接発行する（ログイン処理そのものを試験しないケース用。照合値だけを保持）。"""
    from accounts.models import ApiLoginState
    from common import clock

    def _issue(user):
        token = secrets.token_urlsafe(32)
        at = clock.now_seconds()
        ApiLoginState.objects.create(
            token_hash=hashlib.sha256(token.encode("utf-8")).hexdigest(),
            user=user,
            logged_in_at=at,
            expires_at=at + timedelta(hours=24),
        )
        return f"Bearer {token}"

    return _issue


@pytest.fixture
def catalog(db):
    """商品カタログ（マスタ）の試験データ。本番では FR-060 で投入するデータを直接登録する。"""
    from catalog.models import Category, Product, ProductCategory, StockUnit, Supplier

    class Factory:
        def supplier(self, code=None, name="仕入先（架空）"):
            return Supplier.objects.create(supplier_code=code or f"SUP-{next_seq()}", name=name)

        def category(self, name=None, parent=None, display_order=0, code=None):
            n = next_seq()
            return Category.objects.create(
                category_code=code or f"cat-{n}",
                name=name or f"分類{n}",
                parent=parent,
                depth=(parent.depth + 1) if parent else 1,
                display_order=display_order,
            )

        def product(self, name=None, *, description="", is_public=True, registered_at=None, categories=(), code=None):
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

        def stock_unit(self, product=None, *, price=1000, stock=10, sku=None, variant_name=None, supplier=None):
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


@pytest.fixture
def make_coupon(db):
    from promotions.models import Coupon

    def _make(
        code=None,
        *,
        discount_type="fixed_amount",
        discount_value=500,
        minimum_purchase_amount=0,
        valid_from=None,
        valid_to=None,
        name="試験クーポン",
    ):
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


@pytest.fixture
def api_client():
    from rest_framework.test import APIClient

    return APIClient()


@pytest.fixture
def new_api_client():
    from rest_framework.test import APIClient

    return APIClient


@pytest.fixture
def web():
    """CSRF 検証を有効にした画面クライアントを作る（ブラウザと同じくフォームの CSRF トークンを送る）。"""
    from django.test import Client

    def _client():
        return Client(enforce_csrf_checks=True)

    return _client


class _Capture(logging.Handler):
    def __init__(self):
        super().__init__()
        from common.logging import JsonFormatter

        self.setFormatter(JsonFormatter())
        self.lines: list[str] = []
        self._lock = threading.Lock()

    def emit(self, record):
        line = self.format(record)
        with self._lock:
            self.lines.append(line)

    def records(self):
        return [json.loads(line) for line in self.lines]


@pytest.fixture
def app_logs():
    """アプリケーションログ（minicommerce ロガー）を JSON の行として捕捉する。"""
    handler = _Capture()
    logger = logging.getLogger("minicommerce")
    logger.addHandler(handler)
    try:
        yield handler
    finally:
        logger.removeHandler(handler)


@pytest.fixture
def now_jst():
    return lambda: datetime.now(tz=JST)
