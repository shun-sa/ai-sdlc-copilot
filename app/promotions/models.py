# trace: ENT-007, ADDR-006, ADDR-007
"""クーポン（ENT-007）。業務キーはクーポンコード、物理上の代替キーを持つ（ADDR-006 4.3）。"""

from django.db import models

from common.codes import DiscountType


# trace: ENT-007, ADDR-006, ADDR-007
class Coupon(models.Model):
    coupon_code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=50)
    discount_type = models.CharField(max_length=16, choices=DiscountType.choices)
    discount_value = models.IntegerField()
    minimum_purchase_amount = models.IntegerField(default=0)
    valid_from = models.DateTimeField()
    valid_to = models.DateTimeField()

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(discount_type__in=DiscountType.values), name="coupon_discount_type_valid"
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        discount_type=DiscountType.FIXED_AMOUNT, discount_value__gte=1, discount_value__lte=9999999
                    )
                    | models.Q(discount_type=DiscountType.PERCENTAGE, discount_value__gte=1, discount_value__lte=100)
                ),
                name="coupon_discount_value_range",
            ),
            models.CheckConstraint(
                condition=models.Q(minimum_purchase_amount__gte=0, minimum_purchase_amount__lte=9999999),
                name="coupon_minimum_purchase_amount_range",
            ),
            models.CheckConstraint(
                condition=models.Q(valid_from__lte=models.F("valid_to")), name="coupon_valid_period"
            ),
        ]
