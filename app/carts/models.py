# trace: ENT-008, ENT-009, ADDR-004, ADDR-006, ADDR-007
"""カート（ENT-008）とカート明細（ENT-009）。

購入者ごとの利用中カートは条件付き一意制約で最大1件（ADDR-004 DD-005）。
カート明細の数量は1〜10、同一在庫単位の明細は1カートに1行。明細の並びは識別子の昇順（ADDR-006 DD-003）。
"""

from django.conf import settings
from django.db import models

from common.codes import CartStatus


# trace: ENT-008, ADDR-004, ADDR-007
class Cart(models.Model):
    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="carts")
    coupon = models.ForeignKey("promotions.Coupon", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    status = models.CharField(max_length=16, choices=CartStatus.choices, default=CartStatus.ACTIVE)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()
    ordered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["buyer"], condition=models.Q(status=CartStatus.ACTIVE), name="cart_one_active_per_buyer"
            ),
            models.CheckConstraint(condition=models.Q(status__in=CartStatus.values), name="cart_status_valid"),
            models.CheckConstraint(
                condition=models.Q(status=CartStatus.ACTIVE, ordered_at__isnull=True)
                | models.Q(status=CartStatus.ORDERED, ordered_at__isnull=False),
                name="cart_status_ordered_at",
            ),
        ]


# trace: ENT-009, ADDR-006
class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    stock_unit = models.ForeignKey("catalog.StockUnit", on_delete=models.PROTECT, related_name="+")
    quantity = models.PositiveSmallIntegerField()
    added_at = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["cart", "stock_unit"], name="cart_item_one_per_stock_unit"),
            models.CheckConstraint(
                condition=models.Q(quantity__gte=1, quantity__lte=10), name="cart_item_quantity_range"
            ),
        ]
