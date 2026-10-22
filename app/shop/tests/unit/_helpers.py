# trace: ADDR-004
"""単体テスト用の架空データ生成（Production Data・実在の個人情報を使用しない）。

生成するデータは seed の架空値（example.com など）に倣う。
"""
from datetime import timedelta
from functools import lru_cache
from typing import Any

from shop.common import timeutils
from shop.models import (
    Cart,
    CartLine,
    Collection,
    Coupon,
    DiscountType,
    Item,
    ItemCollection,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseOrderStatus,
    Role,
    ShippingAddress,
    StockUnit,
    Supplier,
    User,
)
from shop.services.accounts import hash_password

VALID_ADDRESS: dict[str, Any] = {
    "recipient_name": "佐藤 花子",
    "postal_code": "123-4567",
    "prefecture_code": "13",
    "address_line1": "千代田区一番町1-1",
    "address_line2": "サンプルビル101",
    "phone_number": "090-1234-5678",
}


@lru_cache(maxsize=8)
def hashed(password: str) -> str:
    """同一パスワードのハッシュ化結果を再利用する（本番と同じハッシュ関数を使う）。"""
    return hash_password(password)


def make_user(
    email: str = "buyer@example.com",
    password: str = "Passw0rd",
    full_name: str = "山田 太郎",
    role: str = Role.BUYER,
) -> User:
    """利用者を1件作成する。"""
    return User.objects.create(
        email=email,
        password_hash=hashed(password),
        full_name=full_name,
        role=role,
        registered_at=timeutils.now(),
    )


def make_admin(email: str = "admin@example.com", password: str = "Adminpass1") -> User:
    """管理者を1件作成する。"""
    return make_user(email=email, password=password, full_name="管理 太郎", role=Role.ADMIN)


def make_supplier(supplier_code: str = "SUP-001", name: str = "サンプル商事") -> Supplier:
    """仕入先を1件作成する。"""
    return Supplier.objects.create(supplier_code=supplier_code, name=name)


def make_collection(
    collection_code: str = "books",
    name: str = "書籍",
    parent: Collection | None = None,
    sort_order: int = 0,
) -> Collection:
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
    item_code: str = "ITEM-001",
    name: str = "サンプル商品",
    is_public: bool = True,
    description: str = "説明文",
    created_at: Any = None,
    collections: list[Collection] | None = None,
) -> Item:
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


def make_stock_unit(
    item: Item,
    supplier: Supplier,
    sku: str = "SKU-001",
    variant_name: str = "標準",
    price: int = 1000,
    quantity: int = 10,
) -> StockUnit:
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
    code: str = "SAVE1000",
    name: str = "1000円割引",
    discount_type: str = DiscountType.FIXED,
    discount_value: int = 1000,
    min_spend: int = 0,
    valid_from: Any = None,
    valid_until: Any = None,
) -> Coupon:
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


def make_cart(user: User, coupon: Coupon | None = None) -> Cart:
    """利用中カートを1件作成する。"""
    now = timeutils.now()
    return Cart.objects.create(user=user, coupon=coupon, created_at=now, updated_at=now)


def add_cart_line(cart: Cart, stock_unit: StockUnit, quantity: int = 1) -> CartLine:
    """カート明細を1件作成する。"""
    return CartLine.objects.create(
        cart=cart,
        stock_unit=stock_unit,
        quantity=quantity,
        added_at=timeutils.now(),
    )


def make_order(
    user: User,
    stock_unit: StockUnit,
    quantity: int = 1,
    status: str = PurchaseOrderStatus.CREATED,
    order_number: str = "PO-00000001",
    total: int | None = None,
) -> PurchaseOrder:
    """注文（明細・配送先つき）を1件作成する。"""
    now = timeutils.now()
    subtotal = stock_unit.price * quantity
    shipping_fee = 0 if subtotal >= 5000 else 500
    tax_amount = (subtotal + shipping_fee) * 10 // 100
    order = PurchaseOrder.objects.create(
        order_number=order_number,
        user=user,
        status=status,
        subtotal=subtotal,
        discount_amount=0,
        discounted_subtotal=subtotal,
        shipping_fee=shipping_fee,
        tax_amount=tax_amount,
        total=total if total is not None else subtotal + shipping_fee + tax_amount,
        ordered_at=now,
    )
    PurchaseOrderLine.objects.create(
        purchase_order=order,
        stock_unit=stock_unit,
        sku=stock_unit.sku,
        item_name=stock_unit.item.name,
        variant_name=stock_unit.variant_name,
        unit_price=stock_unit.price,
        quantity=quantity,
        line_amount=stock_unit.price * quantity,
    )
    ShippingAddress.objects.create(
        purchase_order=order,
        recipient_name="佐藤 花子",
        postal_code="1234567",
        prefecture_code="13",
        address_line1="千代田区一番町1-1",
        address_line2=None,
        phone_number="09012345678",
    )
    return order
