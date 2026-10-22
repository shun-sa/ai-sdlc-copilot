# trace: FR-020, FR-021, FR-022, FR-023, FR-024, FR-025, ADDR-001
"""カート機能（FR-020〜FR-025）の単体テスト。

期待値は FR-020〜FR-025 の処理内容・例外、および FR-026 の金額計算から導出する。
"""
from datetime import timedelta

import pytest

from shop.common import timeutils
from shop.common.errors import (
    CartEmptyError,
    CouponAlreadyAppliedError,
    CouponExpiredError,
    CouponMinSpendNotMetError,
    CouponNotFoundError,
    CouponNotYetValidError,
    InsufficientStockError,
    NotFoundError,
    QuantityLimitExceededError,
    ValidationError,
)
from shop.models import Cart, CartLine, CartStatus, DiscountType
from shop.services import carts
from shop.tests.unit import _helpers

pytestmark = pytest.mark.django_db


# trace: FR-020
def test_view_cart_creates_open_cart_when_missing(buyer):
    """利用中カートが無い場合は空のカートを作成して返す（ST-CART-01）。"""
    result = carts.view_cart(buyer)

    cart = Cart.objects.get(user=buyer, status=CartStatus.OPEN)
    assert result["cart_id"] == cart.cart_id
    assert result["lines"] == []
    assert result["total_quantity"] == 0
    assert result["coupon"] is None
    assert result["amounts"]["total"] == 0


# trace: FR-020
def test_view_cart_reuses_existing_open_cart(buyer, stock_unit):
    """利用中カートが存在する場合は新たに作成しない（DQ-09）。"""
    cart = _helpers.make_cart(buyer)
    _helpers.add_cart_line(cart, stock_unit, quantity=2)

    result = carts.view_cart(buyer)

    assert Cart.objects.filter(user=buyer, status=CartStatus.OPEN).count() == 1
    assert result["cart_id"] == cart.cart_id
    assert result["total_quantity"] == 2


# trace: FR-020
def test_view_cart_returns_line_details_and_amounts(buyer, stock_unit):
    """カート内容は明細の在庫単位情報・小計・金額内訳を含む。"""
    cart = _helpers.make_cart(buyer)
    _helpers.add_cart_line(cart, stock_unit, quantity=3)

    result = carts.view_cart(buyer)

    line = result["lines"][0]
    assert line["stock_unit_id"] == stock_unit.stock_unit_id
    assert line["sku"] == stock_unit.sku
    assert line["item_name"] == stock_unit.item.name
    assert line["unit_price"] == 1000
    assert line["quantity"] == 3
    assert line["line_amount"] == 3000
    assert line["stock_quantity"] == 10
    assert result["amounts"] == {
        "subtotal": 3000,
        "discount_amount": 0,
        "discounted_subtotal": 3000,
        "shipping_fee": 500,
        "tax_amount": 350,
        "total": 3850,
    }


# trace: FR-020
def test_view_cart_orders_lines_by_added_at(buyer, item, supplier):
    """カート明細は追加日時の昇順で返す。"""
    cart = _helpers.make_cart(buyer)
    first = _helpers.make_stock_unit(item, supplier, sku="SKU-001")
    second = _helpers.make_stock_unit(item, supplier, sku="SKU-002")
    older = _helpers.add_cart_line(cart, second, quantity=1)
    older.added_at = timeutils.now() - timedelta(minutes=5)
    older.save(update_fields=["added_at"])
    _helpers.add_cart_line(cart, first, quantity=1)

    result = carts.view_cart(buyer)

    assert [line["sku"] for line in result["lines"]] == ["SKU-002", "SKU-001"]


# trace: FR-021
def test_add_line_creates_new_line(buyer, stock_unit):
    """在庫単位と数量を指定してカート明細を追加する。"""
    result = carts.add_line(buyer, stock_unit.stock_unit_id, 2)

    assert result["total_quantity"] == 2
    assert CartLine.objects.filter(stock_unit=stock_unit, quantity=2).exists()


# trace: FR-021
def test_add_line_merges_quantity_for_same_stock_unit(buyer, stock_unit):
    """同一在庫単位の追加は既存明細へ加算する。"""
    carts.add_line(buyer, stock_unit.stock_unit_id, 2)

    result = carts.add_line(buyer, stock_unit.stock_unit_id, 3)

    assert CartLine.objects.filter(stock_unit=stock_unit).count() == 1
    assert result["lines"][0]["quantity"] == 5


# trace: FR-021
@pytest.mark.parametrize("quantity", [1, 10])
def test_add_line_accepts_quantity_within_limit(buyer, stock_unit, quantity):
    """数量は1個以上10個以下を受け付ける（境界値）。"""
    result = carts.add_line(buyer, stock_unit.stock_unit_id, quantity)

    assert result["lines"][0]["quantity"] == quantity


# trace: FR-021
def test_add_line_rejects_merged_quantity_over_limit(buyer, stock_unit):
    """合算数量が10個を超える場合は数量上限超過とする（境界の外側）。"""
    carts.add_line(buyer, stock_unit.stock_unit_id, 10)

    with pytest.raises(QuantityLimitExceededError) as exc:
        carts.add_line(buyer, stock_unit.stock_unit_id, 1)

    assert exc.value.http_status == 409
    assert exc.value.context["limit"] == 10
    assert exc.value.context["current_quantity"] == 10
    assert exc.value.context["requested_quantity"] == 11
    assert CartLine.objects.get(stock_unit=stock_unit).quantity == 10


# trace: FR-021
def test_add_line_rejects_quantity_over_stock(buyer, item, supplier):
    """合算数量が在庫数量を超える場合は在庫不足とする。"""
    unit = _helpers.make_stock_unit(item, supplier, sku="SKU-010", quantity=2)

    with pytest.raises(InsufficientStockError) as exc:
        carts.add_line(buyer, unit.stock_unit_id, 3)

    shortage = exc.value.context["shortages"][0]
    assert shortage["stock_unit_id"] == unit.stock_unit_id
    assert shortage["requested_quantity"] == 3
    assert shortage["available_quantity"] == 2
    assert CartLine.objects.count() == 0


# trace: FR-021
def test_add_line_accepts_quantity_equal_to_stock(buyer, item, supplier):
    """合算数量が在庫数量と等しい場合は追加できる（境界値）。"""
    unit = _helpers.make_stock_unit(item, supplier, sku="SKU-010", quantity=2)

    result = carts.add_line(buyer, unit.stock_unit_id, 2)

    assert result["lines"][0]["quantity"] == 2


# trace: FR-021
@pytest.mark.parametrize(
    ("raw_stock_unit_id", "raw_quantity", "expected_fields"),
    [
        (None, 1, {"stock_unit_id"}),
        ("", 1, {"stock_unit_id"}),
        ("abc", 1, {"stock_unit_id"}),
        (1, 0, {"quantity"}),
        (1, -1, {"quantity"}),
        (1, "abc", {"quantity"}),
        (None, None, {"stock_unit_id", "quantity"}),
    ],
)
def test_add_line_rejects_invalid_input(buyer, raw_stock_unit_id, raw_quantity, expected_fields):
    """在庫単位・数量の入力不備は全項目を列挙した入力エラーとする。"""
    with pytest.raises(ValidationError) as exc:
        carts.add_line(buyer, raw_stock_unit_id, raw_quantity)

    assert {detail["field"] for detail in exc.value.details} == expected_fields


# trace: FR-021
def test_add_line_rejects_unknown_stock_unit(buyer):
    """存在しない在庫単位は対象なしとする。"""
    with pytest.raises(NotFoundError):
        carts.add_line(buyer, 999999, 1)


# trace: FR-021
def test_add_line_rejects_stock_unit_of_private_item(buyer, supplier):
    """非公開商品の在庫単位は対象なしとする。"""
    private_item = _helpers.make_item("ITEM-900", "非公開商品", is_public=False)
    unit = _helpers.make_stock_unit(private_item, supplier, sku="SKU-900")

    with pytest.raises(NotFoundError):
        carts.add_line(buyer, unit.stock_unit_id, 1)


# trace: FR-022
def test_update_line_quantity_replaces_quantity(buyer, stock_unit):
    """カート明細の数量を指定した値へ変更する（加算ではない）。"""
    carts.add_line(buyer, stock_unit.stock_unit_id, 2)
    line = CartLine.objects.get()

    result = carts.update_line_quantity(buyer, line.cart_line_id, 5)

    assert result["lines"][0]["quantity"] == 5
    assert CartLine.objects.get().quantity == 5


# trace: FR-022
def test_update_line_quantity_rejects_over_limit(buyer, stock_unit):
    """変更後の数量が10個を超える場合は数量上限超過とする。"""
    carts.add_line(buyer, stock_unit.stock_unit_id, 1)
    line = CartLine.objects.get()

    with pytest.raises(QuantityLimitExceededError) as exc:
        carts.update_line_quantity(buyer, line.cart_line_id, 11)

    assert exc.value.context["requested_quantity"] == 11
    assert CartLine.objects.get().quantity == 1


# trace: FR-022
def test_update_line_quantity_rejects_over_stock(buyer, item, supplier):
    """変更後の数量が在庫数量を超える場合は在庫不足とする。"""
    unit = _helpers.make_stock_unit(item, supplier, sku="SKU-010", quantity=3)
    carts.add_line(buyer, unit.stock_unit_id, 1)
    line = CartLine.objects.get()

    with pytest.raises(InsufficientStockError) as exc:
        carts.update_line_quantity(buyer, line.cart_line_id, 4)

    assert exc.value.context["shortages"][0]["available_quantity"] == 3


# trace: FR-022
@pytest.mark.parametrize("quantity", [0, -1, "abc", None, ""])
def test_update_line_quantity_rejects_invalid_quantity(buyer, stock_unit, quantity):
    """数量が1以上の整数でない場合は入力エラーとする。"""
    carts.add_line(buyer, stock_unit.stock_unit_id, 1)
    line = CartLine.objects.get()

    with pytest.raises(ValidationError) as exc:
        carts.update_line_quantity(buyer, line.cart_line_id, quantity)

    assert exc.value.details[0]["field"] == "quantity"


# trace: FR-022
def test_update_line_quantity_rejects_unknown_line(buyer, stock_unit):
    """利用中カートに存在しない明細は対象なしとする。"""
    carts.add_line(buyer, stock_unit.stock_unit_id, 1)

    with pytest.raises(NotFoundError):
        carts.update_line_quantity(buyer, 999999, 1)


# trace: FR-022
def test_update_line_quantity_rejects_other_users_line(buyer, other_buyer, stock_unit):
    """他の購入者のカート明細は対象なしとする。"""
    carts.add_line(buyer, stock_unit.stock_unit_id, 1)
    line = CartLine.objects.get()

    with pytest.raises(NotFoundError):
        carts.update_line_quantity(other_buyer, line.cart_line_id, 2)


# trace: FR-023
def test_remove_line_deletes_line(buyer, stock_unit):
    """カート明細を削除する。"""
    carts.add_line(buyer, stock_unit.stock_unit_id, 2)
    line = CartLine.objects.get()

    result = carts.remove_line(buyer, line.cart_line_id)

    assert CartLine.objects.count() == 0
    assert result["lines"] == []
    assert result["total_quantity"] == 0


# trace: FR-023, FR-024
def test_remove_line_keeps_applied_coupon(buyer, stock_unit):
    """明細削除ではクーポンの適用状態を変更しない。"""
    coupon = _helpers.make_coupon(code="SAVE100", discount_value=100)
    carts.add_line(buyer, stock_unit.stock_unit_id, 2)
    carts.apply_coupon(buyer, coupon.code)
    line = CartLine.objects.get()

    result = carts.remove_line(buyer, line.cart_line_id)

    assert result["coupon"]["code"] == "SAVE100"
    assert result["coupon"]["is_applicable"] is False
    assert result["coupon"]["not_applicable_reason"] == "CART_EMPTY"


# trace: FR-023
def test_remove_line_rejects_unknown_line(buyer):
    """存在しないカート明細の削除は対象なしとする。"""
    with pytest.raises(NotFoundError):
        carts.remove_line(buyer, 999999)


# trace: FR-024
def test_apply_coupon_applies_discount(buyer, stock_unit):
    """クーポンを適用すると割引額が金額内訳へ反映される。"""
    _helpers.make_coupon(code="SAVE500", discount_value=500)
    carts.add_line(buyer, stock_unit.stock_unit_id, 2)

    result = carts.apply_coupon(buyer, "SAVE500")

    assert result["coupon"]["code"] == "SAVE500"
    assert result["coupon"]["is_applicable"] is True
    assert result["amounts"]["discount_amount"] == 500
    assert result["amounts"]["discounted_subtotal"] == 1500


# trace: FR-024
def test_apply_coupon_normalizes_code(buyer, stock_unit):
    """クーポンコードは前後空白除去・英大文字化して照合する（D-07-02）。"""
    _helpers.make_coupon(code="SAVE500", discount_value=500)
    carts.add_line(buyer, stock_unit.stock_unit_id, 1)

    result = carts.apply_coupon(buyer, "  save500  ")

    assert result["coupon"]["code"] == "SAVE500"


# trace: FR-024
def test_apply_coupon_rejects_second_coupon(buyer, stock_unit):
    """クーポンは1カートにつき1枚までとする（E-024-05）。"""
    _helpers.make_coupon(code="SAVE500", discount_value=500)
    _helpers.make_coupon(code="SAVE100", discount_value=100)
    carts.add_line(buyer, stock_unit.stock_unit_id, 1)
    carts.apply_coupon(buyer, "SAVE500")

    with pytest.raises(CouponAlreadyAppliedError) as exc:
        carts.apply_coupon(buyer, "SAVE100")

    assert "SAVE500" in exc.value.message
    assert exc.value.http_status == 409


# trace: FR-024
def test_apply_coupon_rejects_empty_cart(buyer):
    """カートが空の場合はクーポンを適用できない。"""
    with pytest.raises(CartEmptyError) as exc:
        carts.apply_coupon(buyer, "SAVE500")

    assert exc.value.http_status == 409


# trace: FR-024
def test_apply_coupon_rejects_unknown_code(buyer, stock_unit):
    """存在しないクーポンコードは E-024-06 とする。"""
    carts.add_line(buyer, stock_unit.stock_unit_id, 1)

    with pytest.raises(CouponNotFoundError):
        carts.apply_coupon(buyer, "NOTEXIST")


# trace: FR-024
@pytest.mark.parametrize("code", ["", "   ", "save_500", "あいう", "A" * 21])
def test_apply_coupon_rejects_invalid_code_format(buyer, stock_unit, code):
    """クーポンコードは英大文字・数字・ハイフンで20文字以下とする（境界値・形式）。"""
    carts.add_line(buyer, stock_unit.stock_unit_id, 1)

    with pytest.raises(ValidationError) as exc:
        carts.apply_coupon(buyer, code)

    assert exc.value.details[0]["field"] == "code"


# trace: FR-024
def test_apply_coupon_accepts_max_length_code(buyer, stock_unit):
    """クーポンコードの20文字は受け付ける（境界値）。"""
    code = "A" * 20
    _helpers.make_coupon(code=code, discount_value=100)
    carts.add_line(buyer, stock_unit.stock_unit_id, 1)

    assert carts.apply_coupon(buyer, code)["coupon"]["code"] == code


# trace: FR-024
def test_apply_coupon_rejects_not_yet_valid_coupon(buyer, stock_unit):
    """有効期間前のクーポンは COUPON_NOT_YET_VALID とする。"""
    now = timeutils.now()
    _helpers.make_coupon(
        code="FUTURE", discount_value=100, valid_from=now + timedelta(days=1), valid_until=now + timedelta(days=2)
    )
    carts.add_line(buyer, stock_unit.stock_unit_id, 1)

    with pytest.raises(CouponNotYetValidError) as exc:
        carts.apply_coupon(buyer, "FUTURE")

    assert "valid_from" in exc.value.context
    assert Cart.objects.get(user=buyer).coupon_id is None


# trace: FR-024
def test_apply_coupon_rejects_expired_coupon(buyer, stock_unit):
    """有効期間終了後のクーポンは COUPON_EXPIRED とする。"""
    now = timeutils.now()
    _helpers.make_coupon(
        code="PAST", discount_value=100, valid_from=now - timedelta(days=2), valid_until=now - timedelta(seconds=1)
    )
    carts.add_line(buyer, stock_unit.stock_unit_id, 1)

    with pytest.raises(CouponExpiredError):
        carts.apply_coupon(buyer, "PAST")


# trace: FR-024
def test_apply_coupon_rejects_min_spend_not_met(buyer, stock_unit):
    """小計が最低購入金額未満の場合は COUPON_MIN_SPEND_NOT_MET とする。"""
    _helpers.make_coupon(code="BIG", discount_value=100, min_spend=5000)
    carts.add_line(buyer, stock_unit.stock_unit_id, 2)

    with pytest.raises(CouponMinSpendNotMetError) as exc:
        carts.apply_coupon(buyer, "BIG")

    assert exc.value.context == {"min_spend": 5000, "subtotal": 2000}


# trace: FR-024
def test_apply_percentage_coupon(buyer, stock_unit):
    """定率クーポンの割引額は小計×割引率÷100 の切り捨てとなる。"""
    _helpers.make_coupon(code="OFF10", discount_type=DiscountType.PERCENTAGE, discount_value=10)
    carts.add_line(buyer, stock_unit.stock_unit_id, 3)

    result = carts.apply_coupon(buyer, "OFF10")

    assert result["amounts"]["discount_amount"] == 300


# trace: FR-025
def test_remove_coupon_clears_applied_coupon(buyer, stock_unit):
    """クーポン解除で適用中のクーポンを外す。"""
    _helpers.make_coupon(code="SAVE500", discount_value=500)
    carts.add_line(buyer, stock_unit.stock_unit_id, 1)
    carts.apply_coupon(buyer, "SAVE500")

    result = carts.remove_coupon(buyer)

    assert result["coupon"] is None
    assert result["amounts"]["discount_amount"] == 0
    assert Cart.objects.get(user=buyer).coupon_id is None


# trace: FR-025
def test_remove_coupon_succeeds_when_not_applied(buyer):
    """クーポン未適用でもクーポン解除は正常終了する。"""
    result = carts.remove_coupon(buyer)

    assert result["coupon"] is None


# trace: FR-020
def test_open_cart_total_quantity(buyer, stock_unit):
    """共通ヘッダー用の合計点数を返す（未ログイン・カートなしは0）。"""
    assert carts.open_cart_total_quantity(None) == 0
    assert carts.open_cart_total_quantity(buyer) == 0

    carts.add_line(buyer, stock_unit.stock_unit_id, 3)

    assert carts.open_cart_total_quantity(buyer) == 3


# trace: FR-024
def test_strip_code_removes_surrounding_whitespace():
    """画面再表示用のクーポンコードは前後空白を除去する。"""
    assert carts.strip_code("  SAVE500 ") == "SAVE500"
    assert carts.strip_code(None) == ""
