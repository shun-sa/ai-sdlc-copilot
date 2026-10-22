# trace: ADDR-006
"""商品カタログ関連のモデル。

D-02 仕入先、D-03 商品分類、D-04 商品、D-05 商品分類所属、D-06 在庫単位、D-07 クーポン。
"""
from django.db import models


# trace: ADDR-006
class DiscountType(models.TextChoices):
    """割引方式（CD-03）。"""

    FIXED = "fixed", "定額"
    PERCENTAGE = "percentage", "定率"


# trace: ADDR-006
class Supplier(models.Model):
    """仕入先（D-02）。"""

    supplier_id = models.AutoField(primary_key=True)
    supplier_code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)

    class Meta:
        db_table = "supplier"

    def __str__(self) -> str:
        """仕入先コードを返す。"""
        return self.supplier_code


# trace: ADDR-006
class Collection(models.Model):
    """商品分類（D-03）。最大3階層の木構造。"""

    collection_id = models.AutoField(primary_key=True)
    collection_code = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=50, db_collation="C")
    parent_collection = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="children"
    )
    depth = models.PositiveSmallIntegerField()
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = "collection"
        constraints = [
            models.UniqueConstraint(fields=["parent_collection", "name"], name="collection_parent_name_uniq"),
        ]
        indexes = [models.Index(fields=["parent_collection", "sort_order"], name="collection_parent_sort_idx")]

    def __str__(self) -> str:
        """分類コードを返す。"""
        return self.collection_code


# trace: ADDR-006
class Item(models.Model):
    """商品（D-04）。税込価格・最低価格・在庫有無は保持せず参照時に算出する。"""

    item_id = models.AutoField(primary_key=True)
    item_code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100, db_collation="C")
    description = models.TextField(max_length=2000, blank=True, default="")
    is_public = models.BooleanField(default=True)
    created_at = models.DateTimeField()
    collections = models.ManyToManyField(Collection, through="ItemCollection", related_name="items")

    class Meta:
        db_table = "item"
        indexes = [
            models.Index(fields=["is_public", "-created_at", "-item_id"], name="item_public_created_idx"),
            models.Index(fields=["name"], name="item_name_idx"),
        ]

    def __str__(self) -> str:
        """商品コードを返す。"""
        return self.item_code


# trace: ADDR-006
class ItemCollection(models.Model):
    """商品分類所属（D-05）。"""

    item_collection_id = models.AutoField(primary_key=True)
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="item_collections")
    collection = models.ForeignKey(Collection, on_delete=models.PROTECT, related_name="item_collections")

    class Meta:
        db_table = "item_collection"
        constraints = [
            models.UniqueConstraint(fields=["item", "collection"], name="item_collection_uniq"),
        ]
        indexes = [models.Index(fields=["collection", "item"], name="item_collection_coll_idx")]

    def __str__(self) -> str:
        """商品IDと分類IDを返す。"""
        return f"ItemCollection(item_id={self.item_id}, collection_id={self.collection_id})"


# trace: ADDR-006
class StockUnit(models.Model):
    """在庫単位（D-06）。SKU 単位の価格と在庫数量を保持する。"""

    stock_unit_id = models.AutoField(primary_key=True)
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="stock_units")
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="stock_units")
    sku = models.CharField(max_length=32, unique=True, db_collation="C")
    variant_name = models.CharField(max_length=50)
    price = models.PositiveIntegerField()
    quantity = models.PositiveIntegerField()
    updated_at = models.DateTimeField()

    class Meta:
        db_table = "stock_unit"
        constraints = [
            models.CheckConstraint(condition=models.Q(price__lte=9999999), name="stock_unit_price_max"),
            models.CheckConstraint(condition=models.Q(quantity__lte=99999), name="stock_unit_quantity_max"),
        ]
        indexes = [
            models.Index(fields=["item"], name="stock_unit_item_idx"),
            models.Index(fields=["supplier"], name="stock_unit_supplier_idx"),
            models.Index(fields=["price"], name="stock_unit_price_idx"),
        ]

    def __str__(self) -> str:
        """SKU を返す。"""
        return self.sku


# trace: ADDR-006
class Coupon(models.Model):
    """クーポン（D-07）。"""

    coupon_id = models.AutoField(primary_key=True)
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=50)
    discount_type = models.CharField(max_length=10, choices=DiscountType.choices)
    discount_value = models.PositiveIntegerField()
    min_spend = models.PositiveIntegerField(default=0)
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField()

    class Meta:
        db_table = "coupon"
        constraints = [
            models.CheckConstraint(condition=models.Q(valid_from__lte=models.F("valid_until")), name="coupon_period"),
        ]

    def __str__(self) -> str:
        """クーポンコードを返す。"""
        return self.code
