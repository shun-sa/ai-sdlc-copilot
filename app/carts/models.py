# trace: ADDR-008
"""クーポン（D-07）・カート（D-08）・カート明細（D-09）。

金額・合計点数・適用可否は保持せず、参照のたびに算出する（ADDR-008 INV-003）。
"""

from __future__ import annotations

from django.db import models

DISCOUNT_FIXED = "fixed"
DISCOUNT_PERCENTAGE = "percentage"
DISCOUNT_TYPE_CHOICES = [
    (DISCOUNT_FIXED, "定額"),
    (DISCOUNT_PERCENTAGE, "定率"),
]

CART_OPEN = "open"
CART_CONVERTED = "converted"
CART_STATUS_CHOICES = [
    (CART_OPEN, "利用中"),
    (CART_CONVERTED, "注文済"),
]

QUANTITY_LIMIT = 10


# trace: ADDR-008
class Coupon(models.Model):
    """クーポン（割引方式・割引値・最低購入金額・有効期間）。"""

    code = models.CharField(max_length=20)
    name = models.CharField(max_length=50)
    discount_type = models.CharField(max_length=16, choices=DISCOUNT_TYPE_CHOICES)
    discount_value = models.PositiveIntegerField()
    min_spend = models.PositiveIntegerField(default=0)
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField()

    class Meta:
        db_table = "coupons"
        constraints = [
            models.UniqueConstraint(fields=["code"], name="uq_coupon_code"),
        ]

    def __str__(self) -> str:
        return self.code


# trace: ADDR-008
class Cart(models.Model):
    """カート。利用中のカートは購入者1名につき最大1件（DQ-09）。"""

    user = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="carts")
    coupon = models.ForeignKey(Coupon, null=True, blank=True, on_delete=models.PROTECT, related_name="carts")
    status = models.CharField(max_length=16, choices=CART_STATUS_CHOICES, default=CART_OPEN)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()
    converted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "carts"
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=models.Q(status=CART_OPEN),
                name="uq_cart_open_per_user",
            ),
        ]

    def __str__(self) -> str:
        return f"Cart({self.pk})"


# trace: ADDR-008
class CartLine(models.Model):
    """カート明細。1カートに同一在庫単位の明細は1件（DQ-10）。"""

    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="lines")
    stock_unit = models.ForeignKey("catalog.StockUnit", on_delete=models.PROTECT, related_name="cart_lines")
    quantity = models.PositiveSmallIntegerField()
    added_at = models.DateTimeField()

    class Meta:
        db_table = "cart_lines"
        constraints = [
            models.UniqueConstraint(fields=["cart", "stock_unit"], name="uq_cart_line_cart_stock_unit"),
        ]
        indexes = [
            models.Index(fields=["cart", "added_at"], name="ix_cart_line_cart_added"),
        ]

    def __str__(self) -> str:
        return f"CartLine({self.pk})"
