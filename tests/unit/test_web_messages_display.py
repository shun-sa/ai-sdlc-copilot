# trace: FR-021, FR-024, FR-030, FR-031, FR-033, FR-034, FR-041, FR-043, NFR-LG-02, NFR-US-04, ADDR-010, ADDR-011
"""画面の表示整形（UI-23 日時・UI-24 金額・UI-27 表示名・UI-32／UI-33）と
業務エラーの画面メッセージ（MSG-05）の単体テスト。

期待結果は画面・帳票要件（UI-23, UI-24, UI-27, UI-32, UI-33）、MSG-05（判定に用いた値の補足）、
提供済みAPI契約 6.3（業務エラーの context）、ADDR-011（画面独自のエラーコードを定義しない）
から導出する。DBは使用しない。
"""

from __future__ import annotations

import pytest
from carts.models import DISCOUNT_FIXED, DISCOUNT_PERCENTAGE
from common import errors
from common.exceptions import (
    CouponAlreadyApplied,
    CouponExpired,
    CouponMinSpendNotMet,
    CouponNotYetValid,
    InsufficientStock,
    InvalidStatusTransition,
    ItemNotAvailable,
    QuantityLimitExceeded,
    ValidationFailed,
)
from web.prefectures import PREFECTURE_NAMES, PREFECTURES
from web.templatetags import display
from web.views import messages


# trace: NFR-LG-02
@pytest.mark.parametrize(
    ("value", "expected"),
    [(0, "0円"), (1234, "1,234円"), (1234567, "1,234,567円"), ("1000", "1,000円"), (None, "－")],
)
def test_yen_format(value, expected):
    """UI-24：金額は「1,234円」の形式で表示する。"""
    assert display.yen(value) == expected


# trace: FR-033
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2027-04-10T12:34:56+09:00", "2027/04/10 12:34"),
        ("2027-04-10T03:34:56Z", "2027/04/10 12:34"),
        ("", "－"),
        (None, "－"),
        ("不正な日時", "－"),
    ],
)
def test_datetime_jst_format(value, expected):
    """UI-23：日時は「YYYY/MM/DD HH:MM」（JST）で表示する。"""
    assert display.datetime_jst(value) == expected


# trace: FR-041
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("created", "注文受付"),
        ("paid", "支払済"),
        ("shipped", "出荷済"),
        ("delivered", "配達完了"),
        ("cancelled", "キャンセル済"),
        ("", "－"),
        ("unknown", "unknown"),
    ],
)
def test_order_status_label(value, expected):
    """UI-27：注文状態はコード値ではなく表示名で表示する。"""
    assert display.order_status(value) == expected


# trace: FR-031
@pytest.mark.parametrize(
    ("value", "expected"),
    [("approved", "承認"), ("declined", "否認"), ("error", "連携エラー"), (None, "－"), ("x", "x")],
)
def test_payment_result_label(value, expected):
    """UI-27：決済結果は表示名で表示する。"""
    assert display.payment_result(value) == expected


# trace: FR-033
@pytest.mark.parametrize(("value", "expected"), [("buyer", "購入者"), ("admin", "管理者"), ("", "－")])
def test_actor_role_label(value, expected):
    """UI-27：実行者区分は表示名で表示する。"""
    assert display.actor_role(value) == expected


# trace: FR-030
@pytest.mark.parametrize(
    ("value", "expected"),
    [("13", "東京都"), ("01", "北海道"), ("47", "沖縄県"), ("", "－"), ("99", "99")],
)
def test_prefecture_label(value, expected):
    """UI-27：都道府県コードは都道府県名で表示する（CD-06）。"""
    assert display.prefecture(value) == expected


# trace: FR-030
def test_prefecture_master_has_47_entries():
    """CD-06：都道府県は01〜47の47件とする。"""
    assert len(PREFECTURES) == 47
    assert len(PREFECTURE_NAMES) == 47
    assert PREFECTURES[0] == ("01", "北海道")


# trace: FR-030
@pytest.mark.parametrize(("value", "expected"), [("1234567", "123-4567"), ("", "－"), (None, "－"), ("123", "123")])
def test_postal_code_format(value, expected):
    """UI-33：郵便番号は「123-4567」の形式で表示する。"""
    assert display.postal_code(value) == expected


# trace: FR-024
@pytest.mark.parametrize(
    ("coupon", "expected"),
    [
        ({"discount_type": DISCOUNT_FIXED, "discount_value": 1000}, "1,000円引き"),
        ({"discount_type": DISCOUNT_PERCENTAGE, "discount_value": 10}, "10%引き"),
        (None, "－"),
    ],
)
def test_discount_label(coupon, expected):
    """割引内容は「1,000円引き」「10%引き」の形式で表示する。"""
    assert display.discount_label(coupon) == expected


# trace: NFR-US-04
@pytest.mark.parametrize(("value", "expected"), [(None, "－"), ("", "－"), ("値", "値"), (0, 0)])
def test_or_dash_shows_placeholder_for_unset_value(value, expected):
    """UI-32：未設定値は「－」で表示する。"""
    assert display.or_dash(value) == expected


# trace: NFR-US-04
def test_get_item_reads_mapping_entry():
    """入力エラーの項目別表示のために辞書から項目を取り出す。"""
    assert display.get_item({"email": ["必須です。"]}, "email") == ["必須です。"]
    assert display.get_item({}, "email") is None
    assert display.get_item(None, "email") is None


# trace: NFR-US-04
def test_field_errors_groups_messages_by_field():
    """入力エラーは項目名ごとの理由へ整形する（項目の近傍に表示する）。"""
    error = ValidationFailed(
        details=[
            {"field": "password", "reason": "8文字以上で入力してください。"},
            {"field": "password", "reason": "数字を含めてください。"},
            {"field": "email", "reason": "必須です。"},
        ]
    )

    assert messages.field_errors(error) == {
        "password": ["8文字以上で入力してください。", "数字を含めてください。"],
        "email": ["必須です。"],
    }


# trace: NFR-US-04
@pytest.mark.parametrize(
    ("message", "detail", "expected"),
    [
        ("在庫が不足しています。", "現在の在庫数量：3個", "在庫が不足しています（現在の在庫数量：3個）。"),
        ("補足なし。", "", "補足なし。"),
        ("句点のない文言", "補足", "句点のない文言（補足）"),
    ],
)
def test_with_detail_inserts_supplement_before_period(message, detail, expected):
    """MSG-05：文末の「。」の前へ判定に用いた値を差し込む。"""
    assert messages.with_detail(message, detail) == expected


# trace: FR-021
def test_business_message_for_quantity_limit_shows_current_quantity():
    """MSG-05：上限超過には現在のカート内数量を補足する。"""
    error = QuantityLimitExceeded(
        context={"stock_unit_id": 1, "limit": 10, "current_quantity": 8, "requested_quantity": 11}
    )

    assert messages.business_message(error) == (
        "同じ規格は1注文につき10個までです（現在のカート内数量：8個）。"
    )


# trace: FR-021
def test_business_message_for_insufficient_stock_shows_available_quantity():
    """MSG-05：在庫不足には現在の在庫数量を補足する。"""
    error = InsufficientStock(
        context={
            "shortages": [
                {"stock_unit_id": 1, "sku": "SKU-1", "requested_quantity": 5, "available_quantity": 3}
            ]
        }
    )

    assert messages.business_message(error) == "在庫が不足しています（現在の在庫数量：3個）。"


# trace: FR-021
def test_business_detail_is_empty_without_shortages():
    """不足情報がない場合は補足を付けない。"""
    assert messages.business_detail(InsufficientStock(context={"shortages": []})) == ""


# trace: FR-024
def test_business_message_for_coupon_period_shows_valid_period():
    """MSG-05：有効期間の開始前・終了後には有効期間を補足する（UI-23）。"""
    context = {"valid_from": "2027-04-01T00:00:00+09:00", "valid_until": "2027-04-30T23:59:59+09:00"}

    not_yet = messages.business_message(CouponNotYetValid(context=context))
    expired = messages.business_message(CouponExpired(context=context))

    assert "有効期間：2027/04/01 00:00〜2027/04/30 23:59" in not_yet
    assert "有効期間：2027/04/01 00:00〜2027/04/30 23:59" in expired


# trace: FR-024
def test_business_message_for_minimum_spend_shows_amounts():
    """MSG-05：最低購入金額未達には最低購入金額と現在の小計を補足する（UI-24）。"""
    error = CouponMinSpendNotMet(context={"min_spend": 3000, "subtotal": 2000})

    assert messages.business_message(error) == (
        "小計が最低購入金額に達していません（最低購入金額：3,000円、現在の小計：2,000円）。"
    )


# trace: FR-034
def test_business_message_for_invalid_status_shows_status_label():
    """MSG-05：状態不正には現在の状態を表示名で補足する（UI-27）。"""
    error = InvalidStatusTransition(context={"current_status": "shipped"})

    assert messages.business_message(error) == (
        "現在の注文状態ではこの操作を実行できません（現在の状態：出荷済）。"
    )


# trace: FR-024
def test_business_message_without_context_has_no_supplement():
    """context を持たない業務エラーは補足なしの文言とする。"""
    error = CouponAlreadyApplied()

    assert messages.business_message(error) == errors.ERROR_MESSAGES[errors.COUPON_ALREADY_APPLIED]


# trace: FR-024
def test_coupon_already_applied_message_shows_applied_code():
    """SCR-005-OP03：適用中のクーポンコードを補足する。"""
    error = CouponAlreadyApplied()

    with_code = messages.coupon_already_applied_message(error, "SAVE-1000")
    without_code = messages.coupon_already_applied_message(error, None)

    assert "適用中のクーポン：SAVE-1000" in with_code
    assert without_code == error.message


# trace: FR-031
@pytest.mark.parametrize(
    ("operation", "expected"),
    [
        (messages.OPERATION_PAY, "この注文は支払できません（現在の状態：支払済）。"),
        (messages.OPERATION_CANCEL, "この注文はキャンセルできません（現在の状態：支払済）。"),
        (messages.OPERATION_SHIP, "この注文は出荷登録できません（現在の状態：支払済）。"),
        (messages.OPERATION_DELIVER, "この注文は配達完了登録できません（現在の状態：支払済）。"),
    ],
)
def test_status_transition_message_per_operation(operation, expected):
    """SCR-008-OP01／SCR-010-OP02／SCR-103-OP01〜OP03：操作別の文言で表す。"""
    error = InvalidStatusTransition(context={"current_status": "paid"})

    assert messages.invalid_status_message(error, operation) == expected
    assert messages.status_transition_message("paid", operation) == expected


# trace: FR-030
def test_checkout_message_for_item_not_available_lists_targets():
    """SCR-006-OP01：販売終了の商品は「商品名（規格名）」で対象を示す。"""
    error = ItemNotAvailable(context={"stock_unit_ids": [1, 2]})
    lines = [
        {"stock_unit_id": 1, "item_name": "商品A", "variant_name": "青"},
        {"stock_unit_id": 2, "item_name": "商品B", "variant_name": "赤"},
    ]

    assert messages.checkout_message(error, lines) == (
        f"{error.message}対象：商品A（青）、商品B（赤）"
    )


# trace: FR-030
def test_checkout_message_for_item_not_available_without_targets():
    """対象が特定できない場合は共通の文言だけを表示する。"""
    error = ItemNotAvailable(context={"stock_unit_ids": []})

    assert messages.checkout_message(error, []) == error.message


# trace: FR-030
def test_checkout_message_for_quantity_limit_shows_target_and_quantity():
    """SCR-006-OP01：上限超過は対象とカート内数量を示す。"""
    error = QuantityLimitExceeded(
        context={"stock_unit_id": 1, "limit": 10, "current_quantity": 11, "requested_quantity": 11}
    )
    lines = [{"stock_unit_id": 1, "item_name": "商品A", "variant_name": "青"}]

    assert messages.checkout_message(error, lines) == (
        "同じ規格は1注文につき10個までです（対象：商品A（青）、カート内数量：11個）。"
        "カートで数量を変更してください。"
    )


# trace: FR-030
def test_checkout_message_for_coupon_errors_explains_reason():
    """SCR-006-OP01：クーポンが利用できない場合は理由を示して解除を促す。"""
    period = messages.checkout_message(
        CouponExpired(context={"valid_from": "2027-04-01T00:00:00+09:00", "valid_until": "2027-04-30T00:00:00+09:00"}),
        [],
    )
    min_spend = messages.checkout_message(CouponMinSpendNotMet(context={"min_spend": 3000, "subtotal": 10}), [])

    assert "有効期間：" in period
    assert "カートでクーポンを解除する" in period
    assert "最低購入金額：3,000円" in min_spend


# trace: FR-030
def test_checkout_message_for_insufficient_stock_lists_skus():
    """SCR-006-OP01：不足する規格を SKU と在庫数量で示す。"""
    error = InsufficientStock(
        context={
            "shortages": [
                {"stock_unit_id": 1, "sku": "SKU-1", "requested_quantity": 5, "available_quantity": 2}
            ]
        }
    )

    assert messages.checkout_message(error, []) == (
        "在庫が不足している商品があります。カートで数量を変更してください。"
        "不足する規格：SKU-1（現在の在庫数量：2個）"
    )


# trace: FR-030
def test_checkout_message_for_insufficient_stock_without_details():
    """不足情報がない場合は共通の文言だけを表示する。"""
    error = InsufficientStock(context={"shortages": []})

    assert messages.checkout_message(error, []) == messages.CHECKOUT_STOCK_MESSAGE


# trace: FR-043
def test_checkout_message_falls_back_to_business_message():
    """注文手続き以外の業務エラーは共通の業務エラー文言とする。"""
    error = InvalidStatusTransition(context={"current_status": "paid"})

    assert messages.checkout_message(error, []) == messages.business_message(error)
