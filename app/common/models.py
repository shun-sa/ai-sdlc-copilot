# trace: ADDR-004
"""画面の1回限りの送信トークンの記録（ADDR-004 DD-010。業務データではない技術データ）。

（操作種別、トークンの SHA-256 照合値）の組を一意に登録し、先着の要求が通知した結果を記録する。
トークンの値そのもの・入力値・ログイン状態を示す情報は記録しない。
"""

from django.db import models


# trace: ADDR-004
class SubmitToken(models.Model):
    operation = models.CharField(max_length=40)
    token_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField()
    outcome = models.JSONField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["operation", "token_hash"], name="submit_token_operation_hash_uniq"),
        ]
