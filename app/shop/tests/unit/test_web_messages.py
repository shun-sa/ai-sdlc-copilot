# trace: FR-021, FR-022, FR-024, FR-030, FR-031, FR-034, ADDR-007, ADDR-009
"""画面の表示文言へ変換する処理（shop.web.messages）の単体テスト。

期待値は docs/requirements/ui_report_requirements.md の SCR 定義（SCR-002-OP01、SCR-005-OP01、
SCR-005-OP03、SCR-006-OP01、SCR-008-OP01）と共通の画面要件（UI-29、UI-32、UI-34）から導出する。
画面の表示文言は services の業務判定とは別の要件であり、画面は同じ業務例外を表示へ変換する
（ADDR-007 DD-008）。本テストは変換だけを対象とし、DB・外部通信を使用しない。

データ制約（D-09-04：カート明細の数量は1以上10以下、DQ-19：同一在庫単位の数量は10以下）により、
注文確定時の数量上限超過（SCR-006-OP01 の QUANTITY_LIMIT_EXCEEDED）はカート明細を作って再現できない
（UT-DEF-001）。そのため当該表示は、業務例外と表示用のカート内容を与えて変換だけを確認する。
"""
import pytest

from shop.common.errors import (
    CartEmptyError,
    CouponAlreadyAppliedError,
    CouponExpiredError,
    CouponNotYetValidError,
    InsufficientStockError,
    InvalidStatusTransitionError,
    ItemNotAvailableError,
    QuantityLimitExceededError,
)
from shop.web import messages

# UI-32：値が未設定の項目は「－」と表示する。
UNSET_TEXT = "－"
# SCR-005-OP01・SCR-006-OP01 が文言に明記する1注文あたりの数量上限（DQ-19）。
QUANTITY_LIMIT = 10


# trace: ADDR-007
def _cart(stock_unit_id=11, item_name="サンプル商品", variant_name="赤"):
    """表示に用いるカート内容（SCR-005-V02、SCR-006-V01 の明細）を組み立てる。"""
    return {
        "lines": [
            {
                "stock_unit_id": stock_unit_id,
                "item_name": item_name,
                "variant_name": variant_name,
            }
        ]
    }


# trace: FR-030
def test_checkout_message_shows_quantity_limit_with_target_label_of_scr_006():
    """注文確定の数量上限超過は SCR-006-OP01 の文言を対象の明細ラベルつきで表示する。

    SCR-006-OP01：数量上限超過（QUANTITY_LIMIT_EXCEEDED）は
    「同じ規格は1注文につき10個までです（対象：商品名（規格名）、カート内数量：n個）。
    カートで数量を変更してください。」をメッセージ領域に表示する。
    """
    error = QuantityLimitExceededError(
        context={"stock_unit_id": 11, "limit": QUANTITY_LIMIT, "current_quantity": 11}
    )

    message, items = messages.checkout_message(error, _cart())

    assert message == (
        "同じ規格は1注文につき10個までです（対象：サンプル商品（赤）、カート内数量：11個）。"
        "カートで数量を変更してください。"
    )
    assert items == []


# trace: FR-030
def test_checkout_message_lists_all_unavailable_lines_of_scr_006():
    """販売終了は SCR-006-OP01 の文言と、該当するすべての明細の商品名（規格名）を併記する。

    カートから既に削除された明細など対象を特定できない場合は、UI-32 に従って「－」と表示する。
    """
    error = ItemNotAvailableError(context={"stock_unit_ids": [11, 99]})

    message, items = messages.checkout_message(error, _cart())

    assert message == "販売を終了した商品がカートに含まれています。カートから削除してください。"
    assert items == ["サンプル商品（赤）", UNSET_TEXT]


# trace: FR-030
def test_checkout_message_lists_shortages_of_scr_006():
    """在庫不足は SCR-006-OP01 の文言と、不足するすべての規格の SKU・在庫数量を併記する。"""
    error = InsufficientStockError(
        context={
            "shortages": [
                {"sku": "SKU-001", "available_quantity": 1},
                {"sku": "SKU-002", "available_quantity": 0},
            ]
        }
    )

    message, items = messages.checkout_message(error, _cart())

    assert message == "在庫が不足している商品があります。カートで数量を変更してください。"
    assert items == ["SKU-001（現在の在庫数量：1個）", "SKU-002（現在の在庫数量：0個）"]


# trace: FR-024
@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (
            CouponNotYetValidError(context={}),
            f"このクーポンは有効期間の開始前です（有効期間：{UNSET_TEXT}〜{UNSET_TEXT}）。",
        ),
        (
            CouponExpiredError(context={}),
            f"このクーポンは有効期間が終了しています（有効期間：{UNSET_TEXT}〜{UNSET_TEXT}）。",
        ),
    ],
)
def test_coupon_message_shows_unset_period_as_dash_of_ui_32(error, expected):
    """有効期間の値が未設定の場合でも、SCR-005-OP03 の文言のまま UI-32 の「－」で表示する。

    UI-34：画面に内部のエラー詳細（エラーコード・context）を表示しない。
    """
    message = messages.coupon_message(error)

    assert message == expected
    assert error.code not in message


# trace: FR-024
def test_coupon_message_shows_unset_applied_code_as_dash_of_ui_32():
    """適用中のクーポンコードを取得できない場合も SCR-005-OP03 の文言を維持する（UI-32）。"""
    error = CouponAlreadyAppliedError()

    message = messages.coupon_message(error, None)

    assert message == (
        f"クーポンは1注文につき1枚までです（適用中のクーポン：{UNSET_TEXT}）。"
        "別のクーポンを使う場合は、適用中のクーポンを解除してください。"
    )


# trace: FR-021, FR-022, FR-024, FR-030, FR-031, FR-034
@pytest.mark.parametrize(
    ("convert", "error"),
    [
        (
            lambda error: messages.cart_line_message(error),
            CartEmptyError(message="カートに商品がありません。", context={"cart_id": 1}),
        ),
        (
            lambda error: messages.coupon_message(error, "SAVE500"),
            InsufficientStockError(message="カートに商品がありません。", context={"cart_id": 1}),
        ),
        (
            lambda error: messages.checkout_message(error, _cart())[0],
            CartEmptyError(message="カートに商品がありません。", context={"cart_id": 1}),
        ),
        (
            lambda error: messages.payment_message(error),
            CartEmptyError(message="カートに商品がありません。", context={"cart_id": 1}),
        ),
        (
            lambda error: messages.status_transition_message(error, "支払"),
            CartEmptyError(message="カートに商品がありません。", context={"cart_id": 1}),
        ),
    ],
)
def test_messages_fall_back_to_business_error_message_without_internal_details(convert, error):
    """SCR に表示文言の定めがない業務エラーは、業務例外のメッセージをそのまま表示する。

    UI-29：業務エラーはメッセージ領域に理由と求める操作を含めて表示する。
    UI-34：画面にスタックトレース・SQL・内部のエラー詳細（エラーコード・context）を表示しない。
    """
    message = convert(error)

    assert message == "カートに商品がありません。"
    assert error.code not in message
    assert "cart_id" not in message


# trace: FR-021
def test_cart_line_message_without_shortage_context_keeps_business_message():
    """在庫不足の対象が得られない場合は、SCR の文言を組み立てず業務例外のメッセージを表示する。

    数量・在庫数量を伴わない「（現在の在庫数量：n個）」は表示しない（UI-29、UI-34）。
    """
    error = InsufficientStockError(message="在庫が不足しています。", context={})

    message = messages.cart_line_message(error)

    assert message == "在庫が不足しています。"
    assert "現在の在庫数量" not in message


# trace: FR-034
def test_status_transition_message_without_current_status_keeps_business_message():
    """現在の状態が得られない状態不正は、状態名を補わず業務例外のメッセージを表示する（UI-32、UI-34）。"""
    error = InvalidStatusTransitionError(message="この注文は操作できません。", context={})

    message = messages.status_transition_message(error, "キャンセル")

    assert message == "この注文は操作できません。"
    assert "現在の状態" not in message
