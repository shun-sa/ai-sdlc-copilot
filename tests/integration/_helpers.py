"""結合試験のテストデータ生成と API 呼び出しの補助（架空データのみを用いる）。

本番データ・本番資格情報は使用しない。日時・金額の期待値は各テスト側で要件から導出する。
"""
import json
from datetime import timedelta
from typing import Any

from shop.common import timeutils
from shop.models import (
    Collection,
    Coupon,
    DiscountType,
    Item,
    ItemCollection,
    Role,
    StockUnit,
    Supplier,
    User,
)
from shop.services.accounts import hash_password

# 架空のテスト用パスワード（FR-001 6.1.3 の条件を満たす値。本番資格情報ではない）
TEST_PASSWORD = "Passw0rd1"

VALID_ADDRESS: dict[str, Any] = {
    "recipient_name": "佐藤 花子",
    "postal_code": "123-4567",
    "prefecture_code": "13",
    "address_line1": "千代田区一番町1-1",
    "address_line2": "サンプルビル101",
    "phone_number": "090-1234-5678",
}


class ApiClient:
    """Web API を HTTP 経由で呼び出す（URL ルーティング・認証・例外ハンドラを通す）。"""

    def __init__(self, client):
        """Django のテストクライアントを保持する。"""
        self.client = client

    def _headers(self, token):
        """認証トークンを Authorization ヘッダーへ組み立てる。"""
        return {"authorization": f"Bearer {token}"} if token else {}

    def get(self, path, query=None, token=None):
        """GET 要求を送信する。"""
        return self.client.get(path, data=query or {}, headers=self._headers(token))

    def post(self, path, data=None, token=None):
        """POST 要求を JSON で送信する。"""
        return self.client.post(
            path,
            data=json.dumps(data if data is not None else {}),
            content_type="application/json",
            headers=self._headers(token),
        )

    def patch(self, path, data=None, token=None):
        """PATCH 要求を JSON で送信する。"""
        return self.client.patch(
            path,
            data=json.dumps(data if data is not None else {}),
            content_type="application/json",
            headers=self._headers(token),
        )

    def delete(self, path, token=None):
        """DELETE 要求を送信する。"""
        return self.client.delete(path, headers=self._headers(token))

    def login(self, email, password=TEST_PASSWORD):
        """ログイン API で認証トークンを取得する。"""
        response = self.post("/api/auth/login", {"email": email, "password": password})
        assert response.status_code == 200, response.content
        return response.json()["token"]


def make_user(email="buyer@example.com", password=TEST_PASSWORD, full_name="山田 太郎", role=Role.BUYER):
    """利用者を1件作成する（パスワードは本番と同じハッシュ関数で保存する）。"""
    return User.objects.create(
        email=email,
        password_hash=hash_password(password),
        full_name=full_name,
        role=role,
        registered_at=timeutils.now(),
    )


def make_admin(email="admin@example.com", full_name="管理 太郎"):
    """管理者を1件作成する。"""
    return make_user(email=email, full_name=full_name, role=Role.ADMIN)


def make_supplier(supplier_code="SUP-001", name="サンプル商事"):
    """仕入先を1件作成する。"""
    return Supplier.objects.create(supplier_code=supplier_code, name=name)


def make_collection(collection_code="books", name="書籍", parent=None, sort_order=0):
    """商品分類を1件作成する。"""
    depth = 1 if parent is None else parent.depth + 1
    return Collection.objects.create(
        collection_code=collection_code,
        name=name,
        parent_collection=parent,
        depth=depth,
        sort_order=sort_order,
    )


def make_item(
    item_code="ITEM-001",
    name="サンプル商品",
    is_public=True,
    description="説明文",
    created_at=None,
    collections=None,
):
    """商品を1件作成する（所属分類も合わせて作成する）。"""
    item = Item.objects.create(
        item_code=item_code,
        name=name,
        description=description,
        is_public=is_public,
        created_at=created_at or timeutils.now(),
    )
    for collection in collections or []:
        ItemCollection.objects.create(item=item, collection=collection)
    return item


def make_stock_unit(item, supplier, sku="SKU-001", variant_name="標準", price=1000, quantity=10):
    """在庫単位を1件作成する。"""
    return StockUnit.objects.create(
        item=item,
        supplier=supplier,
        sku=sku,
        variant_name=variant_name,
        price=price,
        quantity=quantity,
        updated_at=timeutils.now(),
    )


def make_coupon(
    code="SAVE1000",
    name="1000円割引",
    discount_type=DiscountType.FIXED,
    discount_value=1000,
    min_spend=0,
    valid_from=None,
    valid_until=None,
):
    """クーポンを1件作成する（既定は現在時刻を含む有効期間）。"""
    now = timeutils.now()
    return Coupon.objects.create(
        code=code,
        name=name,
        discount_type=discount_type,
        discount_value=discount_value,
        min_spend=min_spend,
        valid_from=valid_from or now - timedelta(days=1),
        valid_until=valid_until or now + timedelta(days=1),
    )


def catalog(price=1000, quantity=10):
    """購入導線で使う最小の商品データ（仕入先・商品・在庫単位）を作成する。"""
    supplier = make_supplier()
    item = make_item()
    unit = make_stock_unit(item, supplier, price=price, quantity=quantity)
    return item, unit


def error_code(response):
    """エラー応答のエラーコードを返す。"""
    return response.json()["error"]["code"]


def error_fields(response):
    """エラー応答の details に含まれる項目名の集合を返す。"""
    return {detail["field"] for detail in response.json()["error"]["details"]}
