# trace: ADDR-008
"""注文（D-10）・注文明細（D-11）・配送先（D-12）・決済記録（D-13）・注文状態履歴（D-14）。"""

from __future__ import annotations

from django.db import models

STATUS_CREATED = "created"
STATUS_PAID = "paid"
STATUS_SHIPPED = "shipped"
STATUS_DELIVERED = "delivered"
STATUS_CANCELLED = "cancelled"
STATUS_CHOICES = [
    (STATUS_CREATED, "注文受付"),
    (STATUS_PAID, "支払済"),
    (STATUS_SHIPPED, "出荷済"),
    (STATUS_DELIVERED, "配達完了"),
    (STATUS_CANCELLED, "キャンセル済"),
]
STATUS_LABELS = dict(STATUS_CHOICES)

PAYMENT_APPROVED = "approved"
PAYMENT_DECLINED = "declined"
PAYMENT_ERROR = "error"
PAYMENT_RESULT_CHOICES = [
    (PAYMENT_APPROVED, "承認"),
    (PAYMENT_DECLINED, "否認"),
    (PAYMENT_ERROR, "連携エラー"),
]
PAYMENT_RESULT_LABELS = dict(PAYMENT_RESULT_CHOICES)

ORDER_NUMBER_PREFIX = "PO-"


# trace: ADDR-008
class OrderNumberSequence(models.Model):
    """注文番号の採番用の通番（確定の順に大きくなる。欠番は許容する）。"""

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "order_number_sequence"

    def __str__(self) -> str:
        return f"OrderNumberSequence({self.pk})"

    @property
    def order_number(self) -> str:
        return f"{ORDER_NUMBER_PREFIX}{self.pk:08d}"


# trace: ADDR-008
class PurchaseOrder(models.Model):
    """注文。金額は注文確定時点で確定し、以後変更しない。"""

    order_number = models.CharField(max_length=11)
    user = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="purchase_orders")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_CREATED)
    coupon = models.ForeignKey(
        "carts.Coupon", null=True, blank=True, on_delete=models.PROTECT, related_name="purchase_orders"
    )
    coupon_code = models.CharField(max_length=20, null=True, blank=True)
    coupon_discount_type = models.CharField(max_length=16, null=True, blank=True)
    coupon_discount_value = models.PositiveIntegerField(null=True, blank=True)
    subtotal = models.PositiveIntegerField()
    discount_amount = models.PositiveIntegerField(default=0)
    discounted_subtotal = models.PositiveIntegerField()
    shipping_fee = models.PositiveIntegerField()
    tax_amount = models.PositiveIntegerField()
    total = models.PositiveIntegerField()
    ordered_at = models.DateTimeField()
    paid_at = models.DateTimeField(null=True, blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    tracking_number = models.CharField(max_length=30, null=True, blank=True)

    class Meta:
        db_table = "purchase_orders"
        constraints = [
            models.UniqueConstraint(fields=["order_number"], name="uq_purchase_order_number"),
        ]
        indexes = [
            models.Index(fields=["user", "-ordered_at"], name="ix_order_user_ordered"),
            models.Index(fields=["status", "-ordered_at"], name="ix_order_status_ordered"),
        ]

    def __str__(self) -> str:
        return self.order_number

    @property
    def status_label(self) -> str:
        return STATUS_LABELS.get(self.status, self.status)

    @property
    def can_pay(self) -> bool:
        return self.status == STATUS_CREATED

    @property
    def can_cancel(self) -> bool:
        return self.status in (STATUS_CREATED, STATUS_PAID)

    @property
    def can_ship(self) -> bool:
        return self.status == STATUS_PAID

    @property
    def can_deliver(self) -> bool:
        return self.status == STATUS_SHIPPED


# trace: ADDR-008
class PurchaseOrderLine(models.Model):
    """注文明細（注文確定時点のスナップショット）。"""

    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name="lines")
    stock_unit = models.ForeignKey(
        "catalog.StockUnit", on_delete=models.PROTECT, related_name="purchase_order_lines"
    )
    sku = models.CharField(max_length=32)
    item_name = models.CharField(max_length=100)
    variant_name = models.CharField(max_length=50)
    unit_price = models.PositiveIntegerField()
    quantity = models.PositiveSmallIntegerField()
    line_amount = models.PositiveIntegerField()

    class Meta:
        db_table = "purchase_order_lines"
        constraints = [
            models.UniqueConstraint(
                fields=["purchase_order", "stock_unit"], name="uq_order_line_order_stock_unit"
            ),
        ]
        indexes = [
            models.Index(fields=["purchase_order"], name="ix_order_line_order"),
        ]

    def __str__(self) -> str:
        return f"PurchaseOrderLine({self.pk})"


# trace: ADDR-008
class ShippingAddress(models.Model):
    """配送先（注文1件につき1件）。全項目を機密（個人情報）として扱う。"""

    purchase_order = models.OneToOneField(
        PurchaseOrder, on_delete=models.CASCADE, related_name="shipping_address"
    )
    recipient_name = models.CharField(max_length=50)
    postal_code = models.CharField(max_length=7)
    prefecture_code = models.CharField(max_length=2)
    address_line1 = models.CharField(max_length=100)
    address_line2 = models.CharField(max_length=100, blank=True, default="")
    phone_number = models.CharField(max_length=11)

    class Meta:
        db_table = "shipping_addresses"

    def __str__(self) -> str:
        return f"ShippingAddress({self.pk})"


# trace: ADDR-008
class PaymentRecord(models.Model):
    """決済記録。承認の決済記録は1注文につき最大1件（DQ-14）。"""

    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name="payment_records")
    result = models.CharField(max_length=16, choices=PAYMENT_RESULT_CHOICES)
    amount = models.PositiveIntegerField()
    transaction_ref = models.CharField(max_length=21, null=True, blank=True)
    processed_at = models.DateTimeField()

    class Meta:
        db_table = "payment_records"
        constraints = [
            models.UniqueConstraint(
                fields=["purchase_order"],
                condition=models.Q(result=PAYMENT_APPROVED),
                name="uq_payment_record_approved_per_order",
            ),
        ]
        indexes = [
            models.Index(fields=["purchase_order", "processed_at"], name="ix_payment_order_processed"),
        ]

    def __str__(self) -> str:
        return f"PaymentRecord({self.pk})"

    @property
    def result_label(self) -> str:
        return PAYMENT_RESULT_LABELS.get(self.result, self.result)


# trace: ADDR-008
class PurchaseOrderStatusHistory(models.Model):
    """注文状態履歴（状態が変わるたびに1件記録する。CMN-26）。"""

    purchase_order = models.ForeignKey(
        PurchaseOrder, on_delete=models.CASCADE, related_name="status_history"
    )
    from_status = models.CharField(max_length=16, choices=STATUS_CHOICES, null=True, blank=True)
    to_status = models.CharField(max_length=16, choices=STATUS_CHOICES)
    changed_at = models.DateTimeField()
    actor_user = models.ForeignKey(
        "accounts.User", on_delete=models.PROTECT, related_name="status_changes"
    )
    actor_role = models.CharField(max_length=10)

    class Meta:
        db_table = "purchase_order_status_histories"
        indexes = [
            models.Index(fields=["purchase_order", "changed_at"], name="ix_status_history_order"),
        ]

    def __str__(self) -> str:
        return f"PurchaseOrderStatusHistory({self.pk})"

    @property
    def from_status_label(self) -> str | None:
        if not self.from_status:
            return None
        return STATUS_LABELS.get(self.from_status, self.from_status)

    @property
    def to_status_label(self) -> str:
        return STATUS_LABELS.get(self.to_status, self.to_status)
