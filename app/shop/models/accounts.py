# trace: ADDR-002, ADDR-006, ADDR-008
"""利用者・認証トークン・監査ログのモデル（D-01、D-15 および ADDR-002 の認証トークン）。"""
from django.db import models


# trace: ADDR-002
class Role(models.TextChoices):
    """利用者ロール（CD-01）。"""

    BUYER = "buyer", "購入者"
    ADMIN = "admin", "管理者"


# trace: ADDR-002
class AuditEventType(models.TextChoices):
    """監査イベント種別（CD-07）。"""

    LOGIN_SUCCESS = "login_success", "ログイン成功"
    LOGIN_FAILURE = "login_failure", "ログイン失敗"
    LOGOUT = "logout", "ログアウト"
    INITIAL_DATA_LOAD = "initial_data_load", "初期データ一括投入"


# trace: ADDR-006, ADDR-008
class User(models.Model):
    """利用者（D-01）。パスワードはソルト付き一方向ハッシュで保持する。"""

    user_id = models.AutoField(primary_key=True)
    email = models.CharField(max_length=254, unique=True)
    password_hash = models.CharField(max_length=255)
    full_name = models.CharField(max_length=50)
    role = models.CharField(max_length=5, choices=Role.choices)
    registered_at = models.DateTimeField()

    class Meta:
        db_table = "user"

    def __str__(self) -> str:
        """識別子だけを返す（個人情報をログ・表示へ出さない）。"""
        return f"User(user_id={self.user_id})"


# trace: ADDR-002
class AuthToken(models.Model):
    """Web API の認証トークン（ADDR-002 DD-001）。平文のトークン値は保持しない。"""

    auth_token_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="auth_tokens")
    token_hash = models.CharField(max_length=64, unique=True)
    issued_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "auth_token"
        indexes = [models.Index(fields=["user", "expires_at"], name="auth_token_user_idx")]

    def __str__(self) -> str:
        """識別子だけを返す（トークン値・ハッシュを出力しない）。"""
        return f"AuthToken(auth_token_id={self.auth_token_id})"


# trace: ADDR-002
class AuditLog(models.Model):
    """監査ログ（D-15）。利用者削除後も記録を残すため利用者IDを値として保持する。"""

    audit_log_id = models.AutoField(primary_key=True)
    occurred_at = models.DateTimeField()
    event_type = models.CharField(max_length=20, choices=AuditEventType.choices)
    user_id_value = models.IntegerField(null=True, blank=True, db_column="user_id")
    result = models.CharField(max_length=7)
    detail = models.CharField(max_length=1000, null=True, blank=True)

    class Meta:
        db_table = "audit_log"
        indexes = [models.Index(fields=["occurred_at"], name="audit_log_occurred_idx")]

    def __str__(self) -> str:
        """識別子と種別だけを返す。"""
        return f"AuditLog(audit_log_id={self.audit_log_id}, event_type={self.event_type})"
