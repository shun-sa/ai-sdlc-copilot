# trace: ADDR-011
"""業務例外クラス階層と、DB整合性例外から業務例外への対応表。

ビュー・サービスはエラー応答の本文を直接組み立てず、ここで定義した例外を送出する
（ADDR-011 INV-001）。
"""

from __future__ import annotations

from typing import Any

from common import errors


class MiniCommerceError(Exception):
    """利用者へ返すエラーの基底クラス。"""

    code: str = errors.INTERNAL_ERROR

    def __init__(
        self,
        message: str | None = None,
        *,
        details: list[dict[str, str]] | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        self.message = message or errors.ERROR_MESSAGES[self.code]
        self.details = details or []
        self.context = context or {}
        super().__init__(self.message)

    @property
    def status_code(self) -> int:
        return errors.ERROR_STATUS[self.code]


class AuthenticationRequired(MiniCommerceError):
    """認証情報が提示されていない・無効・期限切れ（ERR-04）。"""

    code = errors.AUTHENTICATION_REQUIRED


class InvalidCredentials(MiniCommerceError):
    """提示された資格情報の照合に失敗（ERR-05）。認証例外とは別の型とする。"""

    code = errors.INVALID_CREDENTIALS


class PermissionDeniedError(MiniCommerceError):
    """ロールに権限がない（ERR-03）。"""

    code = errors.PERMISSION_DENIED


class ValidationFailed(MiniCommerceError):
    """入力エラー（ERR-01）。不備のある全項目を details に列挙する。"""

    code = errors.VALIDATION_ERROR


class NotFoundError(MiniCommerceError):
    """対象なしエラー（ERR-06）。"""

    code = errors.NOT_FOUND


class BusinessError(MiniCommerceError):
    """業務エラー（ERR-02）の基底クラス。"""


class EmailAlreadyRegistered(BusinessError):
    code = errors.EMAIL_ALREADY_REGISTERED


class QuantityLimitExceeded(BusinessError):
    code = errors.QUANTITY_LIMIT_EXCEEDED


class InsufficientStock(BusinessError):
    code = errors.INSUFFICIENT_STOCK


class ItemNotAvailable(BusinessError):
    code = errors.ITEM_NOT_AVAILABLE


class CartEmpty(BusinessError):
    code = errors.CART_EMPTY


class CouponAlreadyApplied(BusinessError):
    code = errors.COUPON_ALREADY_APPLIED


class CouponNotFound(BusinessError):
    code = errors.COUPON_NOT_FOUND


class CouponNotYetValid(BusinessError):
    code = errors.COUPON_NOT_YET_VALID


class CouponExpired(BusinessError):
    code = errors.COUPON_EXPIRED


class CouponMinSpendNotMet(BusinessError):
    code = errors.COUPON_MIN_SPEND_NOT_MET


class InvalidStatusTransition(BusinessError):
    code = errors.INVALID_STATUS_TRANSITION


class PaymentDeclined(BusinessError):
    code = errors.PAYMENT_DECLINED


class PaymentServiceError(MiniCommerceError):
    """外部連携エラー（ERR-07）。"""

    code = errors.PAYMENT_SERVICE_ERROR


class InternalError(MiniCommerceError):
    """システムエラー（ERR-08）。"""

    code = errors.INTERNAL_ERROR


# DB整合性例外（制約名）→ 業務例外の対応表。制約名の正本はマイグレーションの制約定義
# （ADDR-008 DD-008）であり、名称を変更する場合は本対応表も同時に更新する。
CONSTRAINT_ERROR_MAP: dict[str, type[MiniCommerceError]] = {
    "uq_user_email": EmailAlreadyRegistered,
}


def constraint_name_of(exc: BaseException) -> str | None:
    """DB整合性例外から違反した制約名を取り出す（取得できない場合は None）。"""
    cause: BaseException | None = exc
    while cause is not None:
        diag = getattr(cause, "diag", None)
        name = getattr(diag, "constraint_name", None)
        if name:
            return str(name)
        cause = cause.__cause__
    text = str(exc)
    for constraint in CONSTRAINT_ERROR_MAP:
        if constraint in text:
            return constraint
    return None


def business_error_for_integrity(exc: BaseException) -> MiniCommerceError | None:
    """整合性例外に対応する業務例外を返す（対応表にない場合は None）。"""
    name = constraint_name_of(exc)
    if not name:
        return None
    error_class = CONSTRAINT_ERROR_MAP.get(name)
    if error_class is None:
        return None
    return error_class()
