# trace: ADDR-001, ADDR-012
"""業務例外とエラー種別（ERR-01〜ERR-08）の共通定義（ADDR-012 4.3 の2、ADDR-001 4.3 の6・7）。

業務処理層は本モジュールの例外を送出し、画面と Web API はそれぞれ共通の変換部品で通知に変える。
code は要件の例外ID（例 E-021-05）で、画面の文言・送信トークンの結果の記録に用いる（応答には含めない）。
"""

from dataclasses import dataclass, field
from typing import Any


# trace: ADDR-001
@dataclass(frozen=True)
class FieldError:
    """入力エラーの1項目（fields[] の field・reason・message）。"""

    field: str
    reason: str
    message: str


# trace: ADDR-001, ADDR-012
class ServiceError(Exception):
    """業務処理層が送出する例外の基底。"""

    error_type = "system_error"
    http_status = 500

    def __init__(
        self,
        code: str,
        message: str,
        *,
        reason: str | None = None,
        fields: list[FieldError] | tuple[FieldError, ...] = (),
        values: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.message = message
        self.reason = reason
        self.fields = list(fields)
        self.values = dict(values or {})

    def to_record(self) -> dict[str, Any]:
        """送信トークンの結果として記録する内容（入力値・ログイン状態を示す情報を含めない）。"""
        return {
            "status": "error",
            "type": self.error_type,
            "code": self.code,
            "message": self.message,
            "reason": self.reason,
            "fields": [{"field": f.field, "reason": f.reason, "message": f.message} for f in self.fields],
            "values": self.values,
        }


# trace: ADDR-001
class InputError(ServiceError):
    """ERR-01 入力エラー（400 input_error）。"""

    error_type = "input_error"
    http_status = 400


# trace: ADDR-001
class BusinessError(ServiceError):
    """ERR-02 業務エラー（422 business_error）。"""

    error_type = "business_error"
    http_status = 422


# trace: ADDR-001
class PermissionDeniedError(ServiceError):
    """ERR-03 権限エラー（403 permission_denied）。"""

    error_type = "permission_denied"
    http_status = 403


# trace: ADDR-001
class AuthenticationRequiredError(ServiceError):
    """ERR-04 認証エラー（401 authentication_required）。"""

    error_type = "authentication_required"
    http_status = 401


# trace: ADDR-001
class AuthenticationFailedError(ServiceError):
    """ERR-05 認証失敗（401 authentication_failed）。"""

    error_type = "authentication_failed"
    http_status = 401


# trace: ADDR-001
class NotFoundError(ServiceError):
    """ERR-06 対象なしエラー（404 not_found）。"""

    error_type = "not_found"
    http_status = 404


# trace: ADDR-001
class IntegrationError(ServiceError):
    """ERR-07 外部連携エラー（502 integration_error）。"""

    error_type = "integration_error"
    http_status = 502


# trace: ADDR-001
class SystemFailureError(ServiceError):
    """ERR-08 システムエラー（500 system_error）。内部の詳細を含めない。"""

    error_type = "system_error"
    http_status = 500


_TYPES: dict[str, type[ServiceError]] = {
    cls.error_type: cls
    for cls in (
        InputError,
        BusinessError,
        PermissionDeniedError,
        AuthenticationRequiredError,
        AuthenticationFailedError,
        NotFoundError,
        IntegrationError,
        SystemFailureError,
    )
}

MSG_SYSTEM_ERROR = (
    "システムエラーが発生しました。時間をおいて再度操作してください。解消しない場合は当社までお問い合わせください。"
)
MSG_NOT_FOUND = "指定されたページまたはデータは存在しないか、表示できません。一覧から選び直してください。"
MSG_PERMISSION_DENIED = "この画面・操作を利用する権限がありません。権限のある利用者でログインしてください。"
MSG_AUTH_REQUIRED = "ログインが必要です。ログインしていないか、30分間操作がなかったためログインが切れています。"
MSG_INPUT_ERROR = "入力内容に誤りがあります。"
MSG_SEARCH_CONDITION_ERROR = "検索条件に誤りがあります。条件を指定し直してください。"


# trace: ADDR-001
def system_failure(code: str) -> SystemFailureError:
    return SystemFailureError(code, MSG_SYSTEM_ERROR)


# trace: ADDR-001
def not_found(code: str) -> NotFoundError:
    return NotFoundError(code, MSG_NOT_FOUND)


# trace: ADDR-001
def permission_denied(code: str) -> PermissionDeniedError:
    return PermissionDeniedError(code, MSG_PERMISSION_DENIED)


# trace: ADDR-001
def authentication_required(code: str) -> AuthenticationRequiredError:
    return AuthenticationRequiredError(code, MSG_AUTH_REQUIRED)


# 要求の解釈に失敗した例外であることを示す属性（Web API の本文の解釈の失敗に付ける）
REQUEST_PARSE_ERROR_ATTR = "mc_request_parse_error"


# trace: ADDR-001, ADDR-012
def is_request_parse_error(exc: BaseException) -> bool:
    """要求そのもの（クエリ・フォーム・本文・ヘッダー）を解釈できない例外か判定する。

    クエリ・フォームの項目数・大きさの上限超過、不正なマルチパート、読み取れない本文、不正な Host 等は
    外部入力の誤りであり、ERR-01 入力エラー（400 input_error）として扱う（ADDR-001 4.3 の7、NFR-SC-04）。
    システムエラー（ERR-08）・LOG-02 の対象にしない。
    """
    from django.core.exceptions import BadRequest, SuspiciousOperation
    from django.http import UnreadablePostError
    from django.http.multipartparser import MultiPartParserError

    if getattr(exc, REQUEST_PARSE_ERROR_ATTR, False):
        return True
    return isinstance(exc, SuspiciousOperation | BadRequest | MultiPartParserError | UnreadablePostError)


# trace: ADDR-001
def from_record(record: dict[str, Any]) -> ServiceError:
    """送信トークンに記録した先着の結果（エラー）から同じ通知の例外を復元する（ADDR-004 DD-013）。"""
    cls = _TYPES.get(str(record.get("type")), SystemFailureError)
    return cls(
        str(record.get("code") or ""),
        str(record.get("message") or MSG_SYSTEM_ERROR),
        reason=record.get("reason"),
        fields=[
            FieldError(str(item.get("field")), str(item.get("reason")), str(item.get("message")))
            for item in record.get("fields") or []
        ],
        values=record.get("values") or {},
    )


# trace: ADDR-001, ADDR-012
@dataclass
class FieldErrors:
    """全項目分の入力エラーを集約して1回で通知する（CMN-16、ADDR-001 DD-003）。"""

    items: list[FieldError] = field(default_factory=list)

    def add(self, field_name: str, reason: str, message: str) -> None:
        self.items.append(FieldError(field_name, reason, message))

    def has(self, field_name: str) -> bool:
        return any(item.field == field_name for item in self.items)

    def __bool__(self) -> bool:
        return bool(self.items)

    def raise_if_any(self, code: str, message: str = MSG_INPUT_ERROR) -> None:
        if self.items:
            raise InputError(code, message, fields=self.items)
