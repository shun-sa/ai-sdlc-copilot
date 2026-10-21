# trace: ADDR-011
"""エラーコード・HTTPステータス・利用者向け文言の対応（単一モジュール）。

提供済みAPI契約（docs/specifications/api-contract.md 6.2）にないエラーコードは追加しない。
"""

VALIDATION_ERROR = "VALIDATION_ERROR"
EMAIL_ALREADY_REGISTERED = "EMAIL_ALREADY_REGISTERED"
QUANTITY_LIMIT_EXCEEDED = "QUANTITY_LIMIT_EXCEEDED"
INSUFFICIENT_STOCK = "INSUFFICIENT_STOCK"
ITEM_NOT_AVAILABLE = "ITEM_NOT_AVAILABLE"
CART_EMPTY = "CART_EMPTY"
COUPON_ALREADY_APPLIED = "COUPON_ALREADY_APPLIED"
COUPON_NOT_FOUND = "COUPON_NOT_FOUND"
COUPON_NOT_YET_VALID = "COUPON_NOT_YET_VALID"
COUPON_EXPIRED = "COUPON_EXPIRED"
COUPON_MIN_SPEND_NOT_MET = "COUPON_MIN_SPEND_NOT_MET"
INVALID_STATUS_TRANSITION = "INVALID_STATUS_TRANSITION"
PAYMENT_DECLINED = "PAYMENT_DECLINED"
PERMISSION_DENIED = "PERMISSION_DENIED"
AUTHENTICATION_REQUIRED = "AUTHENTICATION_REQUIRED"
INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
NOT_FOUND = "NOT_FOUND"
PAYMENT_SERVICE_ERROR = "PAYMENT_SERVICE_ERROR"
INTERNAL_ERROR = "INTERNAL_ERROR"

ERROR_STATUS: dict[str, int] = {
    VALIDATION_ERROR: 400,
    EMAIL_ALREADY_REGISTERED: 409,
    QUANTITY_LIMIT_EXCEEDED: 409,
    INSUFFICIENT_STOCK: 409,
    ITEM_NOT_AVAILABLE: 409,
    CART_EMPTY: 409,
    COUPON_ALREADY_APPLIED: 409,
    COUPON_NOT_FOUND: 409,
    COUPON_NOT_YET_VALID: 409,
    COUPON_EXPIRED: 409,
    COUPON_MIN_SPEND_NOT_MET: 409,
    INVALID_STATUS_TRANSITION: 409,
    PAYMENT_DECLINED: 409,
    PERMISSION_DENIED: 403,
    AUTHENTICATION_REQUIRED: 401,
    INVALID_CREDENTIALS: 401,
    NOT_FOUND: 404,
    PAYMENT_SERVICE_ERROR: 502,
    INTERNAL_ERROR: 500,
}

ERROR_MESSAGES: dict[str, str] = {
    VALIDATION_ERROR: "入力内容に誤りがあります。",
    EMAIL_ALREADY_REGISTERED: "このメールアドレスは既に登録されています。",
    QUANTITY_LIMIT_EXCEEDED: "同じ規格は1注文につき10個までです。",
    INSUFFICIENT_STOCK: "在庫が不足しています。",
    ITEM_NOT_AVAILABLE: "販売を終了した商品がカートに含まれています。カートから削除してください。",
    CART_EMPTY: "カートに商品がありません。",
    COUPON_ALREADY_APPLIED: (
        "クーポンは1注文につき1枚までです。別のクーポンを使う場合は、適用中のクーポンを解除してください。"
    ),
    COUPON_NOT_FOUND: "入力したクーポンコードは存在しません。",
    COUPON_NOT_YET_VALID: "このクーポンは有効期間の開始前です。",
    COUPON_EXPIRED: "このクーポンは有効期間が終了しています。",
    COUPON_MIN_SPEND_NOT_MET: "小計が最低購入金額に達していません。",
    INVALID_STATUS_TRANSITION: "現在の注文状態ではこの操作を実行できません。",
    PAYMENT_DECLINED: "決済が承認されませんでした。お支払いは完了していません。再度お支払いください。",
    PERMISSION_DENIED: "この操作を行う権限がありません。",
    AUTHENTICATION_REQUIRED: (
        "ログインが必要です。ログインしていないか、30分間操作がなかったためログインが切れています。"
    ),
    INVALID_CREDENTIALS: "メールアドレスまたはパスワードが正しくありません。",
    NOT_FOUND: "指定されたページまたはデータは存在しないか、表示できません。",
    PAYMENT_SERVICE_ERROR: (
        "決済サービスとの通信でエラーが発生しました。お支払いは完了していません。時間をおいて再度お支払いください。"
    ),
    INTERNAL_ERROR: (
        "システムエラーが発生しました。時間をおいて再度操作してください。解消しない場合は当社までお問い合わせください。"
    ),
}
