# trace: ENT-015, ADDR-004, ADDR-002
"""監査ログの記録（CMN-24・CMN-25、LOG-04）。

入力されたメールアドレス・パスワード、ログイン状態を示す情報、氏名・住所・電話番号は記録しない。
"""

import json
from datetime import datetime

from audit.models import AuditLog
from common.codes import AuditEventType, AuditResult


# trace: ENT-015, ADDR-002
def record_login_success(user_id: int, at: datetime) -> None:
    AuditLog.objects.create(
        occurred_at=at, event_type=AuditEventType.LOGIN_SUCCESS, target_user_id=user_id, result=AuditResult.SUCCESS
    )


# trace: ENT-015, ADDR-004
def record_login_failure(user_id: int | None, at: datetime) -> None:
    AuditLog.objects.create(
        occurred_at=at, event_type=AuditEventType.LOGIN_FAILURE, target_user_id=user_id, result=AuditResult.FAILURE
    )


# trace: ENT-015, ADDR-002
def record_logout(user_id: int, at: datetime) -> None:
    AuditLog.objects.create(
        occurred_at=at, event_type=AuditEventType.LOGOUT, target_user_id=user_id, result=AuditResult.SUCCESS
    )


# trace: ENT-015, ADDR-004
def record_initial_data_load(success: bool, counts: dict[str, int], at: datetime) -> None:
    """初期データ一括投入（対象の利用者＝値なし、詳細＝データ別の投入件数）。"""
    AuditLog.objects.create(
        occurred_at=at,
        event_type=AuditEventType.INITIAL_DATA_LOAD,
        target_user_id=None,
        result=AuditResult.SUCCESS if success else AuditResult.FAILURE,
        detail=json.dumps(counts, ensure_ascii=False, separators=(",", ":")),
    )
