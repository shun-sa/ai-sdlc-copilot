# trace: ENT-002, ENT-003, ENT-004, ENT-005, ENT-006, ADDR-004, ADDR-006
"""商品カタログ（仕入先・商品分類・商品・商品分類所属・在庫単位。ENT-002〜ENT-006）。

登録・更新は初期データ一括投入だけで行う（CMN-38）。在庫数量は0以上の検査制約を持つ（ADDR-004 DD-004）。
"""

from django.db import models


# trace: ENT-002
class Supplier(models.Model):
    supplier_code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)


# trace: ENT-003, ADDR-006
class Category(models.Model):
    category_code = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=50)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="children")
    depth = models.PositiveSmallIntegerField()
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(depth__gte=1, depth__lte=3), name="category_depth_range"),
            models.CheckConstraint(
                condition=models.Q(display_order__gte=0, display_order__lte=999), name="category_display_order_range"
            ),
            # 同じ親の中で分類名が一意（親分類が値なしの最上位どうしを含む：IDF-ENT-003-003、LDC-ENT-003-003）
            models.UniqueConstraint(fields=["parent", "name"], name="category_parent_name_uniq", nulls_distinct=False),
        ]


# trace: ENT-004, ADDR-006
class Product(models.Model):
    product_code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=2000, blank=True, default="")
    is_public = models.BooleanField(default=True)
    registered_at = models.DateTimeField()


# trace: ENT-005, ADDR-006
class ProductCategory(models.Model):
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="product_categories")
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="product_categories")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["product", "category"], name="product_category_uniq"),
        ]


# trace: ENT-006, ADDR-004, ADDR-006
class StockUnit(models.Model):
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="stock_units")
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="stock_units")
    sku = models.CharField(max_length=32, unique=True)
    variant_name = models.CharField(max_length=50)
    price_excluding_tax = models.IntegerField()
    stock_quantity = models.IntegerField()
    updated_at = models.DateTimeField()

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(stock_quantity__gte=0, stock_quantity__lte=99999), name="stock_quantity_range"
            ),
            models.CheckConstraint(
                condition=models.Q(price_excluding_tax__gte=0, price_excluding_tax__lte=9999999),
                name="stock_unit_price_range",
            ),
        ]
