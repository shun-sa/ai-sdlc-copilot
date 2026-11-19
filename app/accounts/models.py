# trace: ENT-001, ADDR-003, ADDR-002, ADDR-006, ADDR-007, ADDR-012
"""利用者（ENT-001）と Web API のログイン状態（技術的な保持データ：ADDR-002 DD-007）。"""

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models

from common.codes import UserType


# trace: ENT-001, ADDR-012
class UserManager(BaseUserManager):
    """管理者の作成・利用者区分の変更は初期データ一括投入だけで行う（ADDR-012 DD-012）。"""

    use_in_migrations = False

    def get_by_natural_key(self, username: str):  # noqa: ANN201
        return self.get(email=username)


# trace: ENT-001, ADDR-003, ADDR-006, ADDR-007, ADDR-012
class User(AbstractBaseUser):
    """利用者（購入者・管理者）。is_staff・is_superuser・グループ・個別権限を持たない（ADDR-012 DD-011）。

    password は Django 標準形式（方式＄反復回数＄ソルト＄ハッシュ）の保持値で、方式名は
    pbkdf2_sha256_sha256hex（ADDR-003 r2 DD-001。最大99文字程度で max_length=128 に収まる）。
    """

    email = models.CharField(max_length=254, unique=True)
    name = models.CharField(max_length=50)
    user_type = models.CharField(max_length=16, choices=UserType.choices)
    registered_at = models.DateTimeField()
    last_login = None  # ENT-001 に存在しない属性のため持たない

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["name"]

    objects = UserManager()

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(user_type__in=UserType.values), name="user_type_valid"),
        ]

    def __str__(self) -> str:
        return f"user:{self.pk}"

    @property
    def is_buyer(self) -> bool:
        return self.user_type == UserType.BUYER

    @property
    def is_admin_user(self) -> bool:
        return self.user_type == UserType.ADMIN


# trace: ADDR-002, ENT-001
class ApiLoginState(models.Model):
    """Web API のログイン状態（1ログイン1行）。値そのものは保持せず SHA-256 照合値だけを保持する（DD-001）。"""

    token_hash = models.CharField(max_length=64, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="api_login_states")
    logged_in_at = models.DateTimeField()
    expires_at = models.DateTimeField()
