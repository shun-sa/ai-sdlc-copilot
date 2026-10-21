# trace: ADDR-002, ADDR-008
"""利用者（D-01）・認証トークン・監査ログ（D-15）のモデル。"""

from __future__ import annotations

from django.db import models

ROLE_BUYER = "buyer"
ROLE_ADMIN = "admin"
ROLE_CHOICES = [
    (ROLE_BUYER, "購入者"),
    (ROLE_ADMIN, "管理者"),
]

EVENT_LOGIN_SUCCESS = "login_success"
EVENT_LOGIN_FAILURE = "login_failure"
EVENT_LOGOUT = "logout"
EVENT_INITIAL_DATA_LOAD = "initial_data_load"
EVENT_CHOICES = [
    (EVENT_LOGIN_SUCCESS, "ログイン成功"),
    (EVENT_LOGIN_FAILURE, "ログイン失敗"),
    (EVENT_LOGOUT, "ログアウト"),
    (EVENT_INITIAL_DATA_LOAD, "初期データ一括投入"),
]

RESULT_SUCCESS = "success"
RESULT_FAILURE = "failure"


# trace: ADDR-002, ADDR-008
class User(models.Model):
    """利用者（購入者・管理者）。パスワードはハッシュ値のみを保持する。"""

    email = models.CharField(max_length=254)
    password_hash = models.CharField(max_length=255)
    full_name = models.CharField(max_length=50)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default=ROLE_BUYER)
    registered_at = models.DateTimeField()

    class Meta:
        db_table = "users"
        constraints = [
            models.UniqueConstraint(fields=["email"], name="uq_user_email"),
        ]

    def __str__(self) -> str:
        return f"User({self.pk})"

    @property
    def is_buyer(self) -> bool:
        return self.role == ROLE_BUYER

    @property
    def is_admin(self) -> bool:
        return self.role == ROLE_ADMIN


# trace: ADDR-002, ADDR-008
class AuthToken(models.Model):
    """API の認証トークン。平文は保存せず SHA-256 ハッシュのみを保持する。"""

    token_hash = models.CharField(max_length=64)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="auth_tokens")
    issued_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "auth_tokens"
        constraints = [
            models.UniqueConstraint(fields=["token_hash"], name="uq_auth_token_hash"),
        ]

    def __str__(self) -> str:
        return f"AuthToken({self.pk})"


# trace: ADDR-008
class AuditLog(models.Model):
    """監査ログ（D-15）。追記のみとし、更新・削除の手段を設けない。"""

    occurred_at = models.DateTimeField()
    event_type = models.CharField(max_length=32, choices=EVENT_CHOICES)
    user_id = models.BigIntegerField(null=True, blank=True)
    result = models.CharField(max_length=7)
    detail = models.CharField(max_length=1000, blank=True, default="")

    class Meta:
        db_table = "audit_logs"
        indexes = [
            models.Index(fields=["occurred_at"], name="ix_audit_log_occurred_at"),
        ]

    def __str__(self) -> str:
        return f"AuditLog({self.pk})"
