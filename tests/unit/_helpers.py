"""単体テスト用の架空テストデータ生成ヘルパー（Production Data / Credential は使用しない）と、
画面応答の読み取り補助。

このモジュールはテスト補助であり、要件の期待結果は各テストファイル側で定義する。
画面応答の読み取り補助（input 要素・項目近傍の理由・メッセージ領域の取り出し）は、
共通レイアウトと共通部品の構造（ADDR-010 DD-002）に従って本文から該当箇所を切り出すだけで、
何を期待値とするかは各テストファイル側で定義する。
"""

from __future__ import annotations

import datetime as dt
import itertools
import re
from typing import Any

from accounts.models import ROLE_ADMIN, ROLE_BUYER, User
from accounts.services import hash_password
from carts.models import CART_OPEN, DISCOUNT_FIXED, Cart, CartLine, Coupon
from catalog.models import Collection, Item, ItemCollection, StockUnit, Supplier
from common import timeutils

_counter = itertools.count(1)


def unique_suffix() -> str:
    """テスト内で一意な連番（業務キーの重複を避けるために使う）。"""
    return f"{next(_counter):04d}"


def make_user(
    *,
    email: str | None = None,
    password: str = "passw0rd",
    full_name: str = "試験 購入者",
    role: str = ROLE_BUYER,
) -> User:
    """利用者を1件作成する（パスワードはハッシュ値で保持する）。"""
    suffix = unique_suffix()
    return User.objects.create(
        email=email or f"buyer{suffix}@example.test",
        password_hash=hash_password(password),
        full_name=full_name,
        role=role,
        registered_at=timeutils.now(),
    )


def make_admin(*, email: str | None = None, password: str = "passw0rd") -> User:
    """管理者を1件作成する。"""
    suffix = unique_suffix()
    return make_user(
        email=email or f"admin{suffix}@example.test",
        password=password,
        full_name="試験 管理者",
        role=ROLE_ADMIN,
    )


def make_supplier(*, supplier_code: str | None = None, name: str = "試験仕入先") -> Supplier:
    """仕入先を1件作成する。"""
    return Supplier.objects.create(supplier_code=supplier_code or f"SUP-{unique_suffix()}", name=name)


def make_collection(
    *,
    collection_code: str | None = None,
    name: str | None = None,
    parent: Collection | None = None,
    depth: int | None = None,
    sort_order: int = 0,
) -> Collection:
    """商品分類を1件作成する。"""
    suffix = unique_suffix()
    return Collection.objects.create(
        collection_code=collection_code or f"col-{suffix}",
        name=name or f"分類{suffix}",
        parent=parent,
        depth=depth if depth is not None else (1 if parent is None else parent.depth + 1),
        sort_order=sort_order,
    )


def make_item(
    *,
    item_code: str | None = None,
    name: str | None = None,
    description: str = "",
    is_public: bool = True,
    created_at: dt.datetime | None = None,
    collections: list[Collection] | None = None,
) -> Item:
    """商品を1件作成する（所属分類も合わせて登録する）。"""
    suffix = unique_suffix()
    item = Item.objects.create(
        item_code=item_code or f"ITEM-{suffix}",
        name=name or f"商品{suffix}",
        description=description,
        is_public=is_public,
        created_at=created_at or timeutils.now(),
    )
    for collection in collections or []:
        ItemCollection.objects.create(item=item, collection=collection)
    return item


def make_stock_unit(
    item: Item,
    *,
    supplier: Supplier | None = None,
    sku: str | None = None,
    variant_name: str = "標準",
    price: int = 1000,
    quantity: int = 10,
) -> StockUnit:
    """在庫単位を1件作成する。"""
    return StockUnit.objects.create(
        item=item,
        supplier=supplier or make_supplier(),
        sku=sku or f"SKU-{unique_suffix()}",
        variant_name=variant_name,
        price=price,
        quantity=quantity,
        updated_at=timeutils.now(),
    )


def make_sellable_stock_unit(*, price: int = 1000, quantity: int = 10, **item_kwargs: Any) -> StockUnit:
    """公開商品に属する在庫単位を1件作成する。"""
    item = make_item(**item_kwargs)
    return make_stock_unit(item, price=price, quantity=quantity)


def make_coupon(
    *,
    code: str | None = None,
    name: str = "試験クーポン",
    discount_type: str = DISCOUNT_FIXED,
    discount_value: int = 1000,
    min_spend: int = 0,
    valid_from: dt.datetime | None = None,
    valid_until: dt.datetime | None = None,
) -> Coupon:
    """クーポンを1件作成する（既定は現在時刻を含む有効期間）。"""
    now = timeutils.now()
    return Coupon.objects.create(
        code=code or f"CPN-{unique_suffix()}",
        name=name,
        discount_type=discount_type,
        discount_value=discount_value,
        min_spend=min_spend,
        valid_from=valid_from or (now - dt.timedelta(days=1)),
        valid_until=valid_until or (now + dt.timedelta(days=1)),
    )


def make_open_cart(user: User, *, coupon: Coupon | None = None) -> Cart:
    """利用中カートを1件作成する。"""
    now = timeutils.now()
    return Cart.objects.create(user=user, coupon=coupon, status=CART_OPEN, created_at=now, updated_at=now)


def add_cart_line(cart: Cart, stock_unit: StockUnit, *, quantity: int = 1) -> CartLine:
    """カート明細を1行追加する。"""
    return CartLine.objects.create(
        cart=cart, stock_unit=stock_unit, quantity=quantity, added_at=timeutils.now()
    )


SHIPPING_INPUT = {
    "recipient_name": "試験 受取人",
    "postal_code": "1234567",
    "prefecture_code": "13",
    "address_line1": "千代田区1-1-1",
    "address_line2": "試験ビル101",
    "phone_number": "09012345678",
}


def shipping_input(**overrides: Any) -> dict[str, Any]:
    """配送先入力（架空の住所・電話番号）。"""
    payload = dict(SHIPPING_INPUT)
    payload.update(overrides)
    return payload


def input_element(body: str, name: str, *, after: str = "", value: str | None = None) -> str:
    """応答本文から入力欄（input 要素）を1つ取り出す。

    after を指定した場合はその文字列より後ろを、value を指定した場合は value 属性が一致する
    要素を探す（同名の入力欄が明細ごと・規格ごとに並ぶ画面で対象を特定するために使う）。
    """
    start = body.index(after) + len(after) if after else 0
    for match in re.finditer(rf'<input[^>]*name="{re.escape(name)}"[^>]*>', body[start:]):
        element = match.group(0)
        if value is None or f'value="{value}"' in element:
            return element
    raise AssertionError(f"入力欄が応答に存在しない（name={name}, value={value}）")


def field_error_reasons(body: str, *, after: str = "") -> list[str]:
    """指定した位置より後ろの最初の入力エラー表示（項目の近傍）にある理由を取り出す。"""
    start = body.index(after) + len(after) if after else 0
    block = re.search(r'<ul class="field-errors">(.*?)</ul>', body[start:], re.S)
    if block is None:
        return []
    return [re.sub(r"\s+", " ", reason).strip() for reason in re.findall(r"<li>(.*?)</li>", block.group(1), re.S)]


def message_area_error(body: str) -> str:
    """メッセージ領域（画面上部）に表示された業務エラーの文言を取り出す。"""
    match = re.search(r'<p class="message message-error">(.*?)</p>', body, re.S)
    return "" if match is None else re.sub(r"\s+", " ", match.group(1)).strip()


def fake_token_resolver(raw_token: str):
    """認証トークン解決の差し替え用（common は機能アプリを import しないため設定で結び付ける）。"""
    from accounts.services import resolve_auth_token

    return resolve_auth_token(raw_token)
