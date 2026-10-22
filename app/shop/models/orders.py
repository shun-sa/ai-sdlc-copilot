# trace: ADDR-001, ADDR-003, ADDR-006
"""注文関連のモデル（D-10 注文、D-11 注文明細、D-12 配送先、D-13 決済記録、D-14 注文状態履歴）。"""
from django.db import models

from shop.models.accounts import Role, User
from shop.models.catalog import Coupon, DiscountType, StockUnit


# trace: ADDR-001
class PurchaseOrderStatus(models.TextChoices):
    """注文状態（CD-02）。"""

    CREATED = "created", "注文受付"
    PAID = "paid", "支払済"
    SHIPPED = "shipped", "出荷済"
    DELIVERED = "delivered", "配達完了"
    CANCELLED = "cancelled", "キャンセル済"


# trace: ADDR-001
class PaymentResult(models.TextChoices):
    """決済結果（CD-05）。"""

    APPROVED = "approved", "承認"
    DECLINED = "declined", "否認"
    ERROR = "error", "連携エラー"


# trace: ADDR-003, ADDR-006
class PurchaseOrder(models.Model):
    """注文（D-10）。注文番号は専用シーケンスから採番する（ADDR-003）。"""

    purchase_order_id = models.AutoField(primary_key=True)
    order_number = models.CharField(max_length=11, unique=True)
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="purchase_orders")
    status = models.CharField(max_length=9, choices=PurchaseOrderStatus.choices)
    coupon = models.ForeignKey(Coupon, on_delete=models.PROTECT, null=True, blank=True, related_name="purchase_orders")
    coupon_code = models.CharField(max_length=20, null=True, blank=True)
    coupon_discount_type = models.CharField(max_length=10, choices=DiscountType.choices, null=True, blank=True)
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
        db_table = "purchase_order"
        indexes = [
            models.Index(fields=["-ordered_at", "-purchase_order_id"], name="po_ordered_at_idx"),
            models.Index(fields=["status"], name="po_status_idx"),
            models.Index(fields=["user", "-ordered_at"], name="po_user_ordered_idx"),
        ]

    def __str__(self) -> str:
        """注文番号を返す。"""
        return self.order_number


# trace: ADDR-001
class PurchaseOrderLine(models.Model):
    """注文明細（D-11）。注文確定時点の値を複写する。"""

    purchase_order_line_id = models.AutoField(primary_key=True)
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name="lines")
    stock_unit = models.ForeignKey(StockUnit, on_delete=models.PROTECT, related_name="purchase_order_lines")
    sku = models.CharField(max_length=32)
    item_name = models.CharField(max_length=100)
    variant_name = models.CharField(max_length=50)
    unit_price = models.PositiveIntegerField()
    quantity = models.PositiveSmallIntegerField()
    line_amount = models.PositiveIntegerField()

    class Meta:
        db_table = "purchase_order_line"
        constraints = [
            models.UniqueConstraint(fields=["purchase_order", "stock_unit"], name="po_line_po_stock_unit_uniq"),
            models.CheckConstraint(
                condition=models.Q(quantity__gte=1) & models.Q(quantity__lte=10),
                name="po_line_quantity_range",
            ),
        ]

    def __str__(self) -> str:
        """注文明細IDを返す。"""
        return f"PurchaseOrderLine(purchase_order_line_id={self.purchase_order_line_id})"


# trace: ADDR-001
class ShippingAddress(models.Model):
    """配送先（D-12）。注文1件につき1件。"""

    purchase_order = models.OneToOneField(
        PurchaseOrder, on_delete=models.CASCADE, primary_key=True, related_name="shipping_address"
    )
    recipient_name = models.CharField(max_length=50)
    postal_code = models.CharField(max_length=7)
    prefecture_code = models.CharField(max_length=2)
    address_line1 = models.CharField(max_length=100)
    address_line2 = models.CharField(max_length=100, null=True, blank=True)
    phone_number = models.CharField(max_length=11)

    class Meta:
        db_table = "shipping_address"

    def __str__(self) -> str:
        """注文IDを返す（個人情報を出力しない）。"""
        return f"ShippingAddress(purchase_order_id={self.purchase_order_id})"


# trace: ADDR-001
class PaymentRecord(models.Model):
    """決済記録（D-13）。承認の決済記録は1注文につき最大1件（DQ-14）。"""

    payment_record_id = models.AutoField(primary_key=True)
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name="payment_records")
    result = models.CharField(max_length=8, choices=PaymentResult.choices)
    amount = models.PositiveIntegerField()
    transaction_ref = models.CharField(max_length=21, null=True, blank=True)
    processed_at = models.DateTimeField()

    class Meta:
        db_table = "payment_record"
        constraints = [
            models.UniqueConstraint(
                fields=["purchase_order"],
                condition=models.Q(result="approved"),
                name="payment_record_approved_uniq",
            ),
        ]
        indexes = [models.Index(fields=["purchase_order", "processed_at"], name="payment_record_po_idx")]

    def __str__(self) -> str:
        """決済記録IDを返す。"""
        return f"PaymentRecord(payment_record_id={self.payment_record_id})"


# trace: ADDR-001
class PurchaseOrderStatusHistory(models.Model):
    """注文状態履歴（D-14）。状態変更ごとに1件記録する（CMN-26）。"""

    status_history_id = models.AutoField(primary_key=True)
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name="status_history")
    from_status = models.CharField(max_length=9, choices=PurchaseOrderStatus.choices, null=True, blank=True)
    to_status = models.CharField(max_length=9, choices=PurchaseOrderStatus.choices)
    changed_at = models.DateTimeField()
    actor_user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="status_changes")
    actor_role = models.CharField(max_length=5, choices=Role.choices)

    class Meta:
        db_table = "purchase_order_status_history"
        indexes = [models.Index(fields=["purchase_order", "changed_at"], name="po_history_po_idx")]

    def __str__(self) -> str:
        """状態履歴IDを返す。"""
        return f"PurchaseOrderStatusHistory(status_history_id={self.status_history_id})"
