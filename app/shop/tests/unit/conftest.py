# trace: ADDR-004
"""単体テスト共通のフィクスチャ。

DB は pytest-django が作成・破棄する使い捨てテストDB（test_<DB_NAME>）だけを使う。
本番DB・本番データ・本番資格情報は使用しない。
"""
import pytest

from shop.common import request_context
from shop.tests.unit import _helpers


@pytest.fixture(autouse=True)
def reset_request_context():
    """要求コンテキスト（contextvars）をテストごとに初期化する。"""
    request_context.reset()
    yield
    request_context.reset()


@pytest.fixture
def buyer(db):
    """購入者を1件返す。"""
    return _helpers.make_user()


@pytest.fixture
def other_buyer(db):
    """別の購入者を1件返す。"""
    return _helpers.make_user(email="other@example.com", full_name="鈴木 次郎")


@pytest.fixture
def admin_user(db):
    """管理者を1件返す。"""
    return _helpers.make_admin()


@pytest.fixture
def supplier(db):
    """仕入先を1件返す。"""
    return _helpers.make_supplier()


@pytest.fixture
def item(db, supplier):
    """公開中の商品を1件返す。"""
    return _helpers.make_item()


@pytest.fixture
def stock_unit(db, item, supplier):
    """在庫10・税抜1,000円の在庫単位を1件返す。"""
    return _helpers.make_stock_unit(item, supplier)
