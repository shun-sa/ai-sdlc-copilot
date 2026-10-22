# trace: ADDR-001, ADDR-006
"""カート関連のモデル（D-08 カート、D-09 カート明細）。"""
from django.db import models

from shop.models.accounts import User
from shop.models.catalog import Coupon, StockUnit


# trace: ADDR-001
class CartStatus(models.TextChoices):
    """カート状態（CD-04）。"""

    OPEN = "open", "利用中"
    CONVERTED = "converted", "注文済"


# trace: ADDR-001, ADDR-006
class Cart(models.Model):
    """カート（D-08）。利用中のカートは購入者1名につき最大1件（DQ-09）。"""

    cart_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="carts")
    coupon = models.ForeignKey(Coupon, on_delete=models.PROTECT, null=True, blank=True, related_name="carts")
    status = models.CharField(max_length=9, choices=CartStatus.choices, default=CartStatus.OPEN)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()
    converted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "cart"
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=models.Q(status="open"),
                name="cart_open_per_user_uniq",
            ),
        ]
        indexes = [models.Index(fields=["user", "status"], name="cart_user_status_idx")]

    def __str__(self) -> str:
        """カートIDを返す。"""
        return f"Cart(cart_id={self.cart_id})"


# trace: ADDR-001
class CartLine(models.Model):
    """カート明細（D-09）。同一カート内で在庫単位は一意（DQ-10）。"""

    cart_line_id = models.AutoField(primary_key=True)
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="lines")
    stock_unit = models.ForeignKey(StockUnit, on_delete=models.PROTECT, related_name="cart_lines")
    quantity = models.PositiveSmallIntegerField()
    added_at = models.DateTimeField()

    class Meta:
        db_table = "cart_line"
        constraints = [
            models.UniqueConstraint(fields=["cart", "stock_unit"], name="cart_line_cart_stock_unit_uniq"),
            models.CheckConstraint(
                condition=models.Q(quantity__gte=1) & models.Q(quantity__lte=10),
                name="cart_line_quantity_range",
            ),
        ]
        indexes = [models.Index(fields=["cart", "added_at"], name="cart_line_cart_added_idx")]

    def __str__(self) -> str:
        """カート明細IDを返す。"""
        return f"CartLine(cart_line_id={self.cart_line_id})"
