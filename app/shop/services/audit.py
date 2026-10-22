# trace: ADDR-005
"""監査ログ（D-15）の記録。アプリケーションログとは別経路で DB へ記録する。"""
from shop.common import timeutils
from shop.models import AuditEventType, AuditLog

RESULT_SUCCESS = "success"
RESULT_FAILURE = "failure"


# trace: ADDR-005
def record(event_type: str, result: str, user_id: int | None = None, detail: str | None = None) -> AuditLog:
    """監査ログを1件記録する（個人情報・パスワード・トークンは記録しない）。"""
    return AuditLog.objects.create(
        occurred_at=timeutils.now(),
        event_type=event_type,
        user_id_value=user_id,
        result=result,
        detail=detail,
    )


# trace: ADDR-005
def record_login_success(user_id: int) -> AuditLog:
    """ログイン成功を記録する（CMN-24）。"""
    return record(AuditEventType.LOGIN_SUCCESS, RESULT_SUCCESS, user_id=user_id)


# trace: ADDR-005
def record_login_failure(user_id: int | None) -> AuditLog:
    """ログイン失敗を記録する（利用者を特定できない場合は利用者IDなし）。"""
    return record(AuditEventType.LOGIN_FAILURE, RESULT_FAILURE, user_id=user_id)


# trace: ADDR-005
def record_logout(user_id: int) -> AuditLog:
    """ログアウトを記録する。"""
    return record(AuditEventType.LOGOUT, RESULT_SUCCESS, user_id=user_id)


# trace: ADDR-005
def record_initial_data_load(result: str, detail: str) -> AuditLog:
    """初期データ一括投入の実行を記録する（利用者IDは空）。"""
    return record(AuditEventType.INITIAL_DATA_LOAD, result, user_id=None, detail=detail)
