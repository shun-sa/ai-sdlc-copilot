# trace: ADDR-007, ADDR-009
"""画面に表示するメッセージの文言（SCR-002〜SCR-006、SCR-008、SCR-010、SCR-103、SCR-901）。

業務判定は services の単一実装のままとし、画面は同じ業務例外を捕捉して表示へ変換するだけとする
（ADDR-007 DD-008、ADDR-004 DD-002）。表示する数量・金額・日時は業務例外の context から取り出す。
支払（模擬決済）の否認（PAYMENT_DECLINED）と連携エラー（PAYMENT_SERVICE_ERROR）の区別と、
自動再送を行わず購入者の操作で再実行する案内は ADDR-009 の決定に従う。
文言の正本は docs/requirements/ui_report_requirements.md とする。
"""
from datetime import datetime
from typing import Any

from shop.common.errors import AppError
from shop.web.templatetags.display import STATUS_LABELS, UNSET, yen

# 注文確定でクーポンの条件が成立しない場合のエラーコード（SCR-006-OP01）。
COUPON_CONDITION_CODES = frozenset({"COUPON_NOT_YET_VALID", "COUPON_EXPIRED", "COUPON_MIN_SPEND_NOT_MET"})
# 支払済の注文状態（CD-02）。表示の分岐にのみ用いる。
PAID_STATUS = "paid"

# SCR-003-OP01 会員登録
REGISTERED_MESSAGE = "会員登録が完了しました。ログインしてください。"
EMAIL_ALREADY_REGISTERED_MESSAGE = "このメールアドレスは既に登録されています。"
# SCR-004-OP01 ログイン
INVALID_CREDENTIALS_MESSAGE = "メールアドレスまたはパスワードが正しくありません。"
# SCR-006-OP01 注文確定（カートが空の場合は SCR-005 で表示する）
CART_EMPTY_ON_CHECKOUT_MESSAGE = "カートに商品がありません。"
# SCR-008-OP01 支払（模擬決済）。API応答（api-contract 6.2）の message とは別の要件とする。
PAYMENT_DECLINED_MESSAGE = "決済が承認されませんでした。お支払いは完了していません。再度お支払いください。"
PAYMENT_SERVICE_ERROR_MESSAGE = (
    "決済サービスとの通信でエラーが発生しました。お支払いは完了していません。時間をおいて再度お支払いください。"
)
# 画面に表示する入力エラーの文言（項目名ごと）。SCR-005-OP03、SCR-008-OP01、SCR-103-OP01。
FIELD_ERROR_TEXTS = {
    "code": "クーポンコードは英字・数字・ハイフンの20文字以内で入力してください。",
    "mock_result": "模擬決済の結果を選択してください。",
    "tracking_number": "配送伝票番号は英数字とハイフンの30文字以内で入力してください。",
}
# SCR-010-OP02 注文キャンセル（購入者）
ORDER_CANCELLED_MESSAGE = "注文をキャンセルしました。"
BUYER_REFUND_NOTE = "返金は当社が5営業日以内に行います。"
# SCR-103-OP01〜OP03 出荷登録・配達完了登録・注文キャンセル（管理者）
SHIPPED_MESSAGE = "出荷登録しました。"
DELIVERED_MESSAGE = "配達完了を登録しました。"
ADMIN_ORDER_CANCELLED_MESSAGE = "注文をキャンセルしました。在庫を戻しました。"
# SCR-901-V01〜V03 エラー画面の見出しとメッセージ
NOT_FOUND_TITLE = "お探しのページ・データが見つかりません"
NOT_FOUND_MESSAGE = "指定されたページまたはデータは存在しないか、表示できません。一覧から選び直してください。"
PERMISSION_DENIED_TITLE = "この画面・操作を利用する権限がありません"
PERMISSION_DENIED_MESSAGE = "権限のある利用者でログインしてください。"
INTERNAL_ERROR_TITLE = "システムエラーが発生しました"
INTERNAL_ERROR_MESSAGE = "時間をおいて再度操作してください。解消しない場合は当社までお問い合わせください。"


# trace: ADDR-007
def _format_datetime(value: Any) -> str:
    """ISO 8601 の日時を「YYYY/MM/DD HH:MM」の形式で表示する。"""
    if not value:
        return UNSET
    return datetime.fromisoformat(str(value)).strftime("%Y/%m/%d %H:%M")


# trace: ADDR-007
def _valid_period(error: AppError) -> str:
    """クーポンの有効期間の表示文字列を組み立てる（SCR-005-OP03、SCR-006-OP01）。"""
    valid_from = _format_datetime(error.context.get("valid_from"))
    valid_until = _format_datetime(error.context.get("valid_until"))
    return f"有効期間：{valid_from}〜{valid_until}"


# trace: ADDR-007
def _min_spend_condition(error: AppError) -> str:
    """最低購入金額未達の表示文字列を組み立てる（SCR-005-OP03、SCR-006-OP01）。"""
    return f"最低購入金額：{yen(error.context.get('min_spend'))}、現在の小計：{yen(error.context.get('subtotal'))}"


# trace: ADDR-007
def _coupon_condition(error: AppError) -> str:
    """注文確定でクーポンを適用できない理由の表示文字列を返す（SCR-006-OP01）。"""
    if error.code == "COUPON_MIN_SPEND_NOT_MET":
        return _min_spend_condition(error)
    return _valid_period(error)


# trace: ADDR-007
def _shortages(error: AppError) -> list[dict[str, Any]]:
    """在庫不足の対象（SKU・現在の在庫数量）の一覧を取り出す。"""
    shortages = error.context.get("shortages")
    return [item for item in shortages if isinstance(item, dict)] if isinstance(shortages, list) else []


# trace: ADDR-007
def _line_label(cart: dict[str, Any] | None, stock_unit_id: Any) -> str:
    """カート明細を「商品名（規格名）」の形式で表示する。"""
    for line in (cart or {}).get("lines", []):
        if str(line["stock_unit_id"]) == str(stock_unit_id):
            return f"{line['item_name']}（{line['variant_name']}）"
    return UNSET


# trace: ADDR-007
def cart_line_message(error: AppError) -> str:
    """カート明細追加・数量変更の業務エラーの文言（SCR-002-OP01、SCR-005-OP01）。"""
    if error.code == "QUANTITY_LIMIT_EXCEEDED" and "limit" in error.context:
        limit = error.context["limit"]
        current_quantity = error.context.get("current_quantity", 0)
        return f"同じ規格は1注文につき{limit}個までです（現在のカート内数量：{current_quantity}個）。"
    shortages = _shortages(error)
    if error.code == "INSUFFICIENT_STOCK" and shortages:
        return f"在庫が不足しています（現在の在庫数量：{shortages[0].get('available_quantity', 0)}個）。"
    return error.message


# trace: ADDR-007
def coupon_message(error: AppError, applied_coupon_code: Any = None) -> str:
    """クーポン適用の業務エラーの文言（SCR-005-OP03）。"""
    if error.code == "CART_EMPTY":
        return "カートに商品がないため、クーポンを適用できません。"
    if error.code == "COUPON_ALREADY_APPLIED":
        return (
            f"クーポンは1注文につき1枚までです（適用中のクーポン：{applied_coupon_code or UNSET}）。"
            "別のクーポンを使う場合は、適用中のクーポンを解除してください。"
        )
    if error.code == "COUPON_NOT_FOUND":
        return "入力したクーポンコードは存在しません。"
    if error.code == "COUPON_NOT_YET_VALID":
        return f"このクーポンは有効期間の開始前です（{_valid_period(error)}）。"
    if error.code == "COUPON_EXPIRED":
        return f"このクーポンは有効期間が終了しています（{_valid_period(error)}）。"
    if error.code == "COUPON_MIN_SPEND_NOT_MET":
        return f"小計が最低購入金額に達していません（{_min_spend_condition(error)}）。"
    return error.message


# trace: ADDR-007
def checkout_message(error: AppError, cart: dict[str, Any] | None = None) -> tuple[str, list[str]]:
    """注文確定の業務エラーの文言と、メッセージ領域に併記する一覧（SCR-006-OP01）。"""
    if error.code == "ITEM_NOT_AVAILABLE":
        labels = [_line_label(cart, stock_unit_id) for stock_unit_id in error.context.get("stock_unit_ids", [])]
        return "販売を終了した商品がカートに含まれています。カートから削除してください。", labels
    if error.code == "QUANTITY_LIMIT_EXCEEDED" and "limit" in error.context:
        limit = error.context["limit"]
        label = _line_label(cart, error.context.get("stock_unit_id"))
        current_quantity = error.context.get("current_quantity", 0)
        message = (
            f"同じ規格は1注文につき{limit}個までです（対象：{label}、カート内数量：{current_quantity}個）。"
            "カートで数量を変更してください。"
        )
        return message, []
    if error.code == "INSUFFICIENT_STOCK":
        shortages = [
            f"{shortage.get('sku', UNSET)}（現在の在庫数量：{shortage.get('available_quantity', 0)}個）"
            for shortage in _shortages(error)
        ]
        return "在庫が不足している商品があります。カートで数量を変更してください。", shortages
    if error.code in COUPON_CONDITION_CODES:
        message = (
            f"適用中のクーポンは利用できません（{_coupon_condition(error)}）。"
            "カートでクーポンを解除するか、条件を満たしてから注文してください。"
        )
        return message, []
    return error.message, []


# trace: ADDR-007
def field_error_details(error: AppError) -> list[dict[str, str]]:
    """入力エラーの details を画面の文言へ変換する（SCR-005-OP03、SCR-008-OP01、SCR-103-OP01）。

    業務判定・検証は services の単一実装のままとし、画面は同じ入力エラーの項目名を表示の文言へ
    読み替えるだけとする（ADDR-007 DD-008）。対応する文言がない項目は業務例外の理由をそのまま表示する。
    """
    return [
        {
            "field": detail.get("field", ""),
            "reason": FIELD_ERROR_TEXTS.get(detail.get("field", ""), detail.get("reason", "")),
        }
        for detail in error.details
    ]


# trace: ADDR-009
def payment_message(error: AppError) -> str:
    """支払（模擬決済）の業務エラーの文言（SCR-008-OP01）。"""
    if error.code == "PAYMENT_DECLINED":
        return PAYMENT_DECLINED_MESSAGE
    if error.code == "PAYMENT_SERVICE_ERROR":
        return PAYMENT_SERVICE_ERROR_MESSAGE
    return error.message


# trace: ADDR-007
def operation_unavailable_message(current_status: Any, operation: str) -> str:
    """注文の状態では操作できないことの文言（SCR-008-OP01、SCR-010-OP02、SCR-103-OP01〜OP03）。"""
    return f"この注文は{operation}できません（現在の状態：{STATUS_LABELS.get(current_status, UNSET)}）。"


# trace: ADDR-007
def status_transition_message(error: AppError, operation: str) -> str:
    """注文の状態不正の文言（SCR-008-OP01、SCR-010-OP02、SCR-103-OP01〜OP03）。"""
    current_status = error.context.get("current_status")
    if error.code != "INVALID_STATUS_TRANSITION" or current_status is None:
        return error.message
    return operation_unavailable_message(current_status, operation)


# trace: ADDR-007
def buyer_cancel_message(order: dict[str, Any]) -> str:
    """購入者の注文キャンセル成功時の文言（SCR-010-OP02）。支払済だった注文には返金の案内を併記する。"""
    history = order.get("status_history") or []
    previous_status = history[-1].get("from_status") if history else None
    if previous_status == PAID_STATUS:
        return f"{ORDER_CANCELLED_MESSAGE}{BUYER_REFUND_NOTE}"
    return ORDER_CANCELLED_MESSAGE


# trace: ADDR-007
def error_screen_text(error: AppError) -> tuple[str, str]:
    """SCR-901 の見出しとメッセージを返す（内部情報は表示しない）。"""
    if error.code == "PERMISSION_DENIED":
        return PERMISSION_DENIED_TITLE, PERMISSION_DENIED_MESSAGE
    if error.code == "NOT_FOUND":
        return NOT_FOUND_TITLE, NOT_FOUND_MESSAGE
    return INTERNAL_ERROR_TITLE, INTERNAL_ERROR_MESSAGE
