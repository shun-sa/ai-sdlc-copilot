# trace: ADDR-008
"""仕入先（D-02）・商品分類（D-03）・商品（D-04）・商品分類所属（D-05）・在庫単位（D-06）。

算出項目（税込価格・最低価格・在庫有無・低在庫）は列として保持せず、参照時に算出する
（ADDR-008 INV-003）。
"""

from __future__ import annotations

from django.db import models

LOW_STOCK_THRESHOLD = 5
TAX_NUMERATOR = 110
TAX_DENOMINATOR = 100


# trace: ADDR-008
def price_incl_tax(price: int) -> int:
    """税込価格（税抜価格×110÷100 の1円未満切り捨て）を算出する。"""
    return price * TAX_NUMERATOR // TAX_DENOMINATOR


# trace: ADDR-008
class Supplier(models.Model):
    """仕入先。来訪者・購入者には提供しない。"""

    supplier_code = models.CharField(max_length=20)
    name = models.CharField(max_length=100)

    class Meta:
        db_table = "suppliers"
        constraints = [
            models.UniqueConstraint(fields=["supplier_code"], name="uq_supplier_code"),
        ]

    def __str__(self) -> str:
        return self.supplier_code


# trace: ADDR-008
class Collection(models.Model):
    """商品分類（深さ1〜3の木構造）。"""

    collection_code = models.CharField(max_length=30)
    # 分類名の並べ替えは Unicode のコードポイント順とする（CMN-36）。
    name = models.CharField(max_length=50, db_collation="C")
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="children"
    )
    depth = models.PositiveSmallIntegerField()
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = "collections"
        constraints = [
            models.UniqueConstraint(fields=["collection_code"], name="uq_collection_code"),
            models.UniqueConstraint(
                fields=["parent", "name"],
                condition=models.Q(parent__isnull=False),
                name="uq_collection_parent_name",
            ),
            models.UniqueConstraint(
                fields=["name"],
                condition=models.Q(parent__isnull=True),
                name="uq_collection_root_name",
            ),
        ]

    def __str__(self) -> str:
        return self.collection_code


# trace: ADDR-008
class Item(models.Model):
    """商品。公開状態が false の商品は来訪者・購入者に提供しない。"""

    item_code = models.CharField(max_length=20)
    # 商品名の並べ替えは Unicode のコードポイント順とする（CMN-36）。
    name = models.CharField(max_length=100, db_collation="C")
    description = models.TextField(max_length=2000, blank=True, default="")
    is_public = models.BooleanField(default=True)
    created_at = models.DateTimeField()

    class Meta:
        db_table = "items"
        constraints = [
            models.UniqueConstraint(fields=["item_code"], name="uq_item_code"),
        ]
        indexes = [
            models.Index(fields=["is_public", "-created_at"], name="ix_item_public_created"),
            models.Index(fields=["name"], name="ix_item_name"),
        ]

    def __str__(self) -> str:
        return self.item_code


# trace: ADDR-008
class ItemCollection(models.Model):
    """商品分類所属（商品と商品分類の N:M）。"""

    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="item_collections")
    collection = models.ForeignKey(Collection, on_delete=models.PROTECT, related_name="item_collections")

    class Meta:
        db_table = "item_collections"
        constraints = [
            models.UniqueConstraint(fields=["item", "collection"], name="uq_item_collection"),
        ]

    def __str__(self) -> str:
        return f"ItemCollection({self.item_id},{self.collection_id})"


# trace: ADDR-008
class StockUnit(models.Model):
    """在庫単位（SKU単位の販売単位）。在庫数量は0未満にならない。"""

    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="stock_units")
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="stock_units")
    # SKU の並べ替えは Unicode のコードポイント順とする（CMN-36）。
    sku = models.CharField(max_length=32, db_collation="C")
    variant_name = models.CharField(max_length=50)
    price = models.PositiveIntegerField()
    quantity = models.PositiveIntegerField()
    updated_at = models.DateTimeField()

    class Meta:
        db_table = "stock_units"
        constraints = [
            models.UniqueConstraint(fields=["sku"], name="uq_stock_unit_sku"),
            models.CheckConstraint(
                condition=models.Q(quantity__gte=0),
                name="ck_stock_unit_quantity_non_negative",
            ),
        ]
        indexes = [
            models.Index(fields=["item", "sku"], name="ix_stock_unit_item_sku"),
            models.Index(fields=["quantity"], name="ix_stock_unit_quantity"),
        ]

    def __str__(self) -> str:
        return self.sku

    @property
    def price_incl_tax(self) -> int:
        return price_incl_tax(self.price)

    @property
    def in_stock(self) -> bool:
        return self.quantity >= 1

    @property
    def is_low_stock(self) -> bool:
        return self.quantity <= LOW_STOCK_THRESHOLD
