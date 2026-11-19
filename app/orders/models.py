# trace: ENT-010, ENT-011, ENT-012, ENT-013, ENT-014, ADDR-004, ADDR-005, ADDR-006, ADDR-007, ADDR-012
"""注文（ENT-010）・注文明細（ENT-011）・配送先（ENT-012）・決済記録（ENT-013）・注文状態履歴（ENT-014）。

- 注文番号は一意制約を持ち、専用シーケンスから採番する（ADDR-005 DD-001・DD-004）。
- 承認の決済記録は注文ごとに最大1件（条件付き一意：ADDR-004 DD-005）。
- 決済記録・注文状態履歴は追記のみ（ADDR-012 DD-009、ADDR-004 INV-002）。
"""

from django.conf import settings
from django.db import models

from common.codes import PREFECTURES, DiscountType, OrderStatus, PaymentResult, UserType


# trace: ENT-013, ENT-014, ADDR-012
class AppendOnlyError(Exception):
    """追記のみの記録を更新・削除しようとした。"""


# trace: ENT-013, ENT-014, ADDR-012
class AppendOnlyQuerySet(models.QuerySet):
    """更新・削除を業務処理に公開しない（一括投入の削除指定は initial_data が _raw_delete で行う）。"""

    def update(self, **kwargs):  # noqa: ANN001, ANN201
        raise AppendOnlyError("records are append-only")

    def delete(self):  # noqa: ANN201
        raise AppendOnlyError("records are append-only")


# trace: ENT-013, ENT-014, ADDR-012
class AppendOnlyModel(models.Model):
    class Meta:
        abstract = True

    def save(self, *args, **kwargs):  # noqa: ANN002, ANN003, ANN201
        if not self._state.adding:
            raise AppendOnlyError("records are append-only")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):  # noqa: ANN002, ANN003, ANN201
        raise AppendOnlyError("records are append-only")


# trace: ENT-010, ADDR-005, ADDR-006, ADDR-007
class Order(models.Model):
    order_number = models.CharField(max_length=11, unique=True)
    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="orders")
    status = models.CharField(max_length=16, choices=OrderStatus.choices, default=OrderStatus.ACCEPTED)
    coupon = models.ForeignKey("promotions.Coupon", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    coupon_code = models.CharField(max_length=20, null=True, blank=True)
    discount_type = models.CharField(max_length=16, choices=DiscountType.choices, null=True, blank=True)
    discount_value = models.IntegerField(null=True, blank=True)
    subtotal = models.BigIntegerField()
    discount_amount = models.BigIntegerField(default=0)
    discounted_subtotal = models.BigIntegerField()
    shipping_fee = models.IntegerField()
    tax_amount = models.BigIntegerField()
    total_amount = models.BigIntegerField()
    ordered_at = models.DateTimeField()
    paid_at = models.DateTimeField(null=True, blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    tracking_number = models.CharField(max_length=30, null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(status__in=OrderStatus.values), name="order_status_valid"),
            models.CheckConstraint(condition=models.Q(shipping_fee__in=[0, 500]), name="order_shipping_fee_valid"),
            models.CheckConstraint(
                condition=models.Q(
                    subtotal__gte=0, discount_amount__gte=0, discounted_subtotal__gte=0, tax_amount__gte=0
                )
                & models.Q(discount_amount__lte=models.F("subtotal")),
                name="order_amounts_valid",
            ),
            models.CheckConstraint(
                condition=~models.Q(status__in=[OrderStatus.PAID, OrderStatus.SHIPPED, OrderStatus.DELIVERED])
                | models.Q(paid_at__isnull=False),
                name="order_paid_at_required",
            ),
            models.CheckConstraint(
                condition=~models.Q(status__in=[OrderStatus.SHIPPED, OrderStatus.DELIVERED])
                | models.Q(shipped_at__isnull=False),
                name="order_shipped_at_required",
            ),
            models.CheckConstraint(
                condition=~models.Q(status=OrderStatus.DELIVERED) | models.Q(delivered_at__isnull=False),
                name="order_delivered_at_required",
            ),
            models.CheckConstraint(
                condition=~models.Q(status=OrderStatus.CANCELLED) | models.Q(cancelled_at__isnull=False),
                name="order_cancelled_at_required",
            ),
        ]


# trace: ENT-011, ADDR-006
class OrderItem(models.Model):
    """確定時点の値の複写（並びは識別子の昇順で再現：ADDR-006 DD-005）。"""

    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="items")
    stock_unit = models.ForeignKey("catalog.StockUnit", on_delete=models.PROTECT, related_name="+")
    sku = models.CharField(max_length=32)
    product_name = models.CharField(max_length=100)
    variant_name = models.CharField(max_length=50)
    unit_price = models.IntegerField()
    quantity = models.PositiveSmallIntegerField()
    line_amount = models.BigIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["order", "stock_unit"], name="order_item_one_per_stock_unit"),
            models.CheckConstraint(
                condition=models.Q(quantity__gte=1, quantity__lte=10), name="order_item_quantity_range"
            ),
        ]


# trace: ENT-012
class ShippingAddress(models.Model):
    order = models.OneToOneField(Order, on_delete=models.PROTECT, related_name="shipping_address")
    recipient_name = models.CharField(max_length=50)
    postal_code = models.CharField(max_length=7)
    prefecture = models.CharField(max_length=2, choices=PREFECTURES)
    address_line1 = models.CharField(max_length=100)
    address_line2 = models.CharField(max_length=100, null=True, blank=True)
    phone_number = models.CharField(max_length=11)


# trace: ENT-013, ADDR-004, ADDR-007, ADDR-012
class PaymentRecord(AppendOnlyModel):
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="payments")
    result = models.CharField(max_length=24, choices=PaymentResult.choices)
    amount = models.BigIntegerField()
    transaction_ref = models.CharField(max_length=21, null=True, blank=True)
    processed_at = models.DateTimeField()

    objects = AppendOnlyQuerySet.as_manager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["order"],
                condition=models.Q(result=PaymentResult.APPROVED),
                name="payment_one_approved_per_order",
            ),
            models.CheckConstraint(condition=models.Q(result__in=PaymentResult.values), name="payment_result_valid"),
            models.CheckConstraint(
                condition=models.Q(result=PaymentResult.APPROVED, transaction_ref__isnull=False)
                | (~models.Q(result=PaymentResult.APPROVED) & models.Q(transaction_ref__isnull=True)),
                name="payment_transaction_ref_condition",
            ),
        ]


# trace: ENT-014, ADDR-007, ADDR-012
class OrderStatusHistory(AppendOnlyModel):
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="status_history")
    from_status = models.CharField(max_length=16, choices=OrderStatus.choices, null=True, blank=True)
    to_status = models.CharField(max_length=16, choices=OrderStatus.choices)
    changed_at = models.DateTimeField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    actor_user_type = models.CharField(max_length=16, choices=UserType.choices)

    objects = AppendOnlyQuerySet.as_manager()
