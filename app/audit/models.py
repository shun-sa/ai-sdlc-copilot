# trace: ENT-015, ADDR-006, ADDR-007, ADDR-012
"""監査ログ（ENT-015。追記のみ：NFR-SC-23、ADDR-012 DD-009、ADDR-004 INV-002）。

対象の利用者は利用者の識別子の値を保持し、利用者の削除後も値を残すため外部キーを定義しない（ADDR-006 DD-004）。
更新・削除の操作を業務処理に公開しない（保存期間経過分の削除は運用手順書による運用者の作業）。
"""

from django.db import models

from common.codes import AuditEventType, AuditResult


# trace: ENT-015, ADDR-012
class AppendOnlyError(Exception):
    """追記のみの記録を更新・削除しようとした。"""


# trace: ENT-015, ADDR-012
class AuditLogQuerySet(models.QuerySet):
    def update(self, **kwargs):  # noqa: ANN001, ANN201
        raise AppendOnlyError("audit logs are append-only")

    def delete(self):  # noqa: ANN201
        raise AppendOnlyError("audit logs are append-only")


# trace: ENT-015, ADDR-006, ADDR-007, ADDR-012
class AuditLog(models.Model):
    occurred_at = models.DateTimeField()
    event_type = models.CharField(max_length=32, choices=AuditEventType.choices)
    target_user_id = models.BigIntegerField(null=True, blank=True)
    result = models.CharField(max_length=16, choices=AuditResult.choices)
    detail = models.CharField(max_length=1000, null=True, blank=True)

    objects = AuditLogQuerySet.as_manager()

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(event_type__in=AuditEventType.values), name="audit_event_type_valid"
            ),
            models.CheckConstraint(condition=models.Q(result__in=AuditResult.values), name="audit_result_valid"),
        ]

    def save(self, *args, **kwargs):  # noqa: ANN002, ANN003, ANN201
        if not self._state.adding:
            raise AppendOnlyError("audit logs are append-only")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):  # noqa: ANN002, ANN003, ANN201
        raise AppendOnlyError("audit logs are append-only")
