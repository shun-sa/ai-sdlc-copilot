# trace: FR-021, FR-022, FR-030, FR-040, FR-041, FR-043, FR-060, NFR-SC-04, ADDR-001, ADDR-006, ADDR-007, ADDR-010
"""全角数字を半角数字として受理しないことを確認する回帰テスト（OBS-IT-001）。

期待値は次の要件本文から導出する（Production Code の挙動からは導出しない）。

- FR-030 6.15.3 入力：郵便番号は「半角数字7桁」または「半角数字3桁・ハイフン・半角数字4桁」、
  都道府県コードは「2桁の半角数字で "01" 以上 "47" 以下」、電話番号は「半角数字とハイフンのみ」。
- FR-021 6.9.3／FR-022 6.10.3 入力：数量は「1以上の整数であること（0以下・整数でない値は入力エラー）」。
- FR-032 6.17.3／FR-040 6.20.3／FR-041 6.21.3 入力：ページ番号は「1以上の整数」（CMN-35）。
- FR-041 6.21.3 入力：注文日（開始）・注文日（終了）は「YYYY-MM-DD 形式の実在する日付」、
  注文番号は「PO-」＋数字8桁（FR-030 手順12 で採番する注文番号の形式）。
- FR-043 6.23.3 入力：配送伝票番号は「半角の英字（大文字・小文字）・数字・ハイフンのみ」。
- FR-060 6.26.3 入力：定義ファイルの有効開始日時・有効終了日時は JST の日時であること。
- CMN-15（7.3 入力チェック共通方針）：「全角文字と半角文字の相互変換は行わない」。

したがって全角数字（０〜９）は半角数字へ変換されず、半角数字を求める項目では条件を満たさない値
（入力エラー）となり、整数として解釈することもできない。本テストは、半角数字が受理されること
（正常系）と、同じ値の全角表記が拒否されること（異常系）を対で検証する。

本テストは正規表現の文字クラスを Unicode 既定の `\\d`（全角数字にも一致する）へ戻した場合に
必ず失敗する。
"""
import pytest

from shop.common import pagination
from shop.common.errors import ValidationError
from shop.common.validators import (
    DATE_PATTERN,
    DIGITS_PATTERN,
    INTEGER_PATTERN,
    ORDER_NUMBER_PATTERN,
    PHONE_PATTERN,
    POSTAL_CODE_PATTERN,
    TRACKING_NUMBER_PATTERN,
    parse_int,
)
from shop.models import Cart, CartLine, CartStatus, PurchaseOrder, ShippingAddress, StockUnit
from shop.services import admin_orders, carts, orders, seeding
from shop.tests.unit import _helpers

FULLWIDTH_DIGITS = "０１２３４５６７８９"


# trace: FR-030
def _address(**overrides):
    """正常な配送先入力に上書きを適用して返す。"""
    data = dict(_helpers.VALID_ADDRESS)
    data.update(overrides)
    return data


# trace: FR-030, NFR-SC-04
def test_postal_code_pattern_accepts_halfwidth_and_rejects_fullwidth_digits():
    """郵便番号は半角数字の形式だけを満たす（FR-030 入力・CMN-15）。"""
    assert POSTAL_CODE_PATTERN.match("1234567") is not None
    assert POSTAL_CODE_PATTERN.match("123-4567") is not None

    assert POSTAL_CODE_PATTERN.match("１２３４５６７") is None
    assert POSTAL_CODE_PATTERN.match("１２３-４５６７") is None
    assert POSTAL_CODE_PATTERN.match("123４567") is None
    assert POSTAL_CODE_PATTERN.match("123－4567") is None


# trace: FR-030, NFR-SC-04
def test_digits_pattern_accepts_halfwidth_and_rejects_fullwidth_digits():
    """都道府県コードなどの数字項目は半角数字だけを満たす（FR-030 入力・CMN-15）。"""
    assert DIGITS_PATTERN.match("13") is not None
    assert DIGITS_PATTERN.match("01") is not None

    assert DIGITS_PATTERN.match("１３") is None
    assert DIGITS_PATTERN.match("1３") is None
    for digit in FULLWIDTH_DIGITS:
        assert DIGITS_PATTERN.match(digit) is None


# trace: FR-021, FR-022, NFR-SC-04
def test_integer_pattern_accepts_halfwidth_and_rejects_fullwidth_digits():
    """整数として解釈する値は半角数字（符号は任意）だけを満たす（CMN-15）。"""
    assert INTEGER_PATTERN.match("12") is not None
    assert INTEGER_PATTERN.match("+12") is not None
    assert INTEGER_PATTERN.match("-12") is not None

    assert INTEGER_PATTERN.match("１２") is None
    assert INTEGER_PATTERN.match("+１２") is None
    assert INTEGER_PATTERN.match("1２") is None


# trace: FR-021, FR-022, NFR-SC-04
@pytest.mark.parametrize(
    ("value", "expected"),
    [("1", 1), ("10", 10), (" 10 ", 10), ("+10", 10), ("-10", -10)],
)
def test_parse_int_returns_value_for_halfwidth_digits(value, expected):
    """半角数字の文字列は整数として解釈する。"""
    assert parse_int(value) == expected


# trace: FR-021, FR-022, NFR-SC-04
@pytest.mark.parametrize("value", ["１", "１０", " １０ ", "+１０", "-１０", "1０", "１0"])
def test_parse_int_rejects_fullwidth_digits(value):
    """全角数字の文字列は整数として解釈しない（CMN-15：全角と半角の相互変換を行わない）。"""
    assert parse_int(value) is None


# trace: FR-041, NFR-SC-04
def test_date_pattern_accepts_halfwidth_and_rejects_fullwidth_digits():
    """注文日の YYYY-MM-DD は半角数字だけを満たす（FR-041 入力・CMN-15）。"""
    assert DATE_PATTERN.match("2027-04-10") is not None

    assert DATE_PATTERN.match("２０２７-０４-１０") is None
    assert DATE_PATTERN.match("2027-０4-10") is None
    assert DATE_PATTERN.match("2027-04-１0") is None


# trace: FR-041, NFR-SC-04
def test_order_number_pattern_accepts_halfwidth_and_rejects_fullwidth_digits():
    """注文番号「PO-」＋数字8桁は半角数字だけを満たす（FR-030 手順12・FR-041 入力）。"""
    assert ORDER_NUMBER_PATTERN.match("PO-00000001") is not None

    assert ORDER_NUMBER_PATTERN.match("PO-０００００００１") is None
    assert ORDER_NUMBER_PATTERN.match("PO-0000000１") is None


# trace: FR-030, FR-043, NFR-SC-04
def test_phone_and_tracking_number_patterns_reject_fullwidth_characters():
    """電話番号・配送伝票番号は半角の文字だけを満たす（FR-030・FR-043 入力）。"""
    assert PHONE_PATTERN.match("090-1234-5678") is not None
    assert TRACKING_NUMBER_PATTERN.match("TRK-0001") is not None

    assert PHONE_PATTERN.match("０９０-１２３４-５６７８") is None
    assert PHONE_PATTERN.match("090－1234－5678") is None
    assert TRACKING_NUMBER_PATTERN.match("ＴＲＫ-0001") is None
    assert TRACKING_NUMBER_PATTERN.match("TRK-０００１") is None


# trace: FR-030
@pytest.mark.parametrize(
    ("overrides", "expected_field"),
    [
        ({"postal_code": "１２３４５６７"}, "postal_code"),
        ({"postal_code": "１２３-４５６７"}, "postal_code"),
        ({"postal_code": "123４567"}, "postal_code"),
        ({"prefecture_code": "１３"}, "prefecture_code"),
        ({"prefecture_code": "０１"}, "prefecture_code"),
        ({"prefecture_code": "4７"}, "prefecture_code"),
        ({"phone_number": "０９０１２３４５６７８"}, "phone_number"),
        ({"phone_number": "０９０-１２３４-５６７８"}, "phone_number"),
    ],
)
def test_validate_shipping_address_rejects_fullwidth_digits(overrides, expected_field):
    """全角数字の郵便番号・都道府県コード・電話番号は入力エラーとする（FR-030 手順3・E-030-03）。"""
    with pytest.raises(ValidationError) as exc:
        orders.validate_shipping_address(_address(**overrides))

    assert any(detail["field"] == expected_field for detail in exc.value.details)


# trace: FR-030
def test_validate_shipping_address_reports_every_fullwidth_digit_field():
    """全角数字の項目は、条件を満たさない全項目としてまとめて通知する（E-030-03）。"""
    with pytest.raises(ValidationError) as exc:
        orders.validate_shipping_address(
            _address(
                postal_code="１２３４５６７",
                prefecture_code="１３",
                phone_number="０９０１２３４５６７８",
            )
        )

    assert {detail["field"] for detail in exc.value.details} == {
        "postal_code",
        "prefecture_code",
        "phone_number",
    }


# trace: FR-030
def test_validate_shipping_address_registers_halfwidth_values_without_conversion():
    """半角数字の配送先は受理し、値を変換せずに登録用の値とする（FR-030 手順15・CMN-15）。"""
    result = orders.validate_shipping_address(
        _address(postal_code="123-4567", prefecture_code="13", phone_number="090-1234-5678")
    )

    assert result["postal_code"] == "1234567"
    assert result["prefecture_code"] == "13"
    assert result["phone_number"] == "09012345678"


# trace: FR-030, ADDR-001
@pytest.mark.django_db
def test_checkout_rejects_fullwidth_address_digits_without_creating_order(buyer, stock_unit):
    """全角数字の配送先では注文を作成せず、在庫・カートも変更しない（FR-030 手順3・E-030-03）。"""
    carts.add_line(buyer, stock_unit.stock_unit_id, 1)

    with pytest.raises(ValidationError) as exc:
        orders.checkout(
            buyer,
            _address(postal_code="１２３４５６７", prefecture_code="１３"),
        )

    assert {detail["field"] for detail in exc.value.details} == {"postal_code", "prefecture_code"}
    assert PurchaseOrder.objects.count() == 0
    assert ShippingAddress.objects.count() == 0
    assert StockUnit.objects.get(pk=stock_unit.pk).quantity == 10
    assert Cart.objects.get(user=buyer).status == CartStatus.OPEN


# trace: FR-030, ADDR-001
@pytest.mark.django_db
def test_checkout_stores_halfwidth_address_as_entered(buyer, stock_unit):
    """半角数字の配送先は注文確定で受理し、入力どおりの半角数字で登録する（FR-030 手順15）。"""
    carts.add_line(buyer, stock_unit.stock_unit_id, 1)

    orders.checkout(buyer, _address(postal_code="123-4567", prefecture_code="13"))

    address = ShippingAddress.objects.get()
    assert address.postal_code == "1234567"
    assert address.prefecture_code == "13"
    assert address.phone_number == "09012345678"


# trace: FR-021, ADDR-001
@pytest.mark.django_db
def test_add_line_rejects_fullwidth_quantity_and_stock_unit_id(buyer, stock_unit):
    """全角数字の数量・在庫単位IDはカート明細追加の入力エラーとする（FR-021 入力・E-021-03）。"""
    with pytest.raises(ValidationError) as exc:
        carts.add_line(buyer, stock_unit.stock_unit_id, "１")
    assert any(detail["field"] == "quantity" for detail in exc.value.details)

    with pytest.raises(ValidationError) as exc:
        carts.add_line(buyer, str(stock_unit.stock_unit_id).translate(str.maketrans("0123456789", FULLWIDTH_DIGITS)), 1)
    assert any(detail["field"] == "stock_unit_id" for detail in exc.value.details)

    assert CartLine.objects.count() == 0


# trace: FR-021, ADDR-001
@pytest.mark.django_db
def test_add_line_accepts_halfwidth_quantity(buyer, stock_unit):
    """半角数字の数量はカート明細追加で受理する（FR-021 入力）。"""
    result = carts.add_line(buyer, str(stock_unit.stock_unit_id), "2")

    assert [line["quantity"] for line in result["lines"]] == [2]


# trace: FR-022, ADDR-001
@pytest.mark.django_db
def test_update_line_quantity_rejects_fullwidth_quantity(buyer, stock_unit):
    """全角数字の数量はカート明細数量変更の入力エラーとし、数量を変更しない（FR-022 入力・E-022-03）。"""
    added = carts.add_line(buyer, stock_unit.stock_unit_id, 1)
    cart_line_id = added["lines"][0]["cart_line_id"]

    with pytest.raises(ValidationError) as exc:
        carts.update_line_quantity(buyer, cart_line_id, "３")

    assert any(detail["field"] == "quantity" for detail in exc.value.details)
    assert Cart.objects.get(user=buyer).lines.get().quantity == 1


# trace: FR-040, FR-041, ADDR-006
def test_parse_page_rejects_fullwidth_digits():
    """全角数字のページ番号は入力エラーとする（CMN-35・各一覧機能の入力条件）。"""
    assert pagination.parse_page("2") == 2

    with pytest.raises(ValidationError) as exc:
        pagination.parse_page("１")

    assert [detail["field"] for detail in exc.value.details] == ["page"]


# trace: FR-041, ADDR-006
@pytest.mark.django_db
@pytest.mark.parametrize(
    ("kwargs", "expected_field"),
    [
        ({"raw_ordered_from": "２０２７-０４-１０"}, "ordered_from"),
        ({"raw_ordered_to": "２０２７-０４-１０"}, "ordered_to"),
        ({"raw_ordered_from": "2027-０4-10"}, "ordered_from"),
        ({"raw_order_number": "PO-０００００００１"}, "order_number"),
        ({"raw_page": "１"}, "page"),
    ],
)
def test_search_orders_rejects_fullwidth_digits(db, kwargs, expected_field):
    """全角数字の注文日・注文番号・ページ番号は入力エラーとする（FR-041 手順4・E-041-03）。"""
    with pytest.raises(ValidationError) as exc:
        admin_orders.search_orders(**kwargs)

    assert any(detail["field"] == expected_field for detail in exc.value.details)


# trace: FR-041, ADDR-006
@pytest.mark.django_db
def test_search_orders_accepts_halfwidth_date_and_page(db):
    """半角数字の注文日・ページ番号は受理する（FR-041 入力）。"""
    result = admin_orders.search_orders(raw_ordered_from="2027-04-10", raw_ordered_to="2027-04-10", raw_page="1")

    assert result["page"] == 1


# trace: FR-040, ADDR-006
@pytest.mark.django_db
def test_search_stock_units_rejects_fullwidth_page_and_supplier_id(db):
    """全角数字のページ番号・仕入先IDは入力エラーとする（FR-040 手順4・E-040-03）。"""
    with pytest.raises(ValidationError) as exc:
        admin_orders.search_stock_units(raw_page="１")
    assert any(detail["field"] == "page" for detail in exc.value.details)

    with pytest.raises(ValidationError) as exc:
        admin_orders.search_stock_units(raw_supplier_id="１")
    assert any(detail["field"] == "supplier_id" for detail in exc.value.details)


# trace: FR-060, ADDR-010
@pytest.mark.django_db
@pytest.mark.parametrize(
    "value",
    ["２０２７-０４-０１T００:００:００+09:00", "2027-０4-01T00:00:00+09:00", "2027-04-01T００:00:00+09:00"],
)
def test_seed_definition_rejects_fullwidth_datetime(value):
    """定義ファイルの全角数字の日時は日時として解釈せず違反とする（FR-060 入力・CMN-15）。"""
    data = {
        "users": [],
        "suppliers": [],
        "collections": [],
        "items": [],
        "stock_units": [],
        "coupons": [
            {
                "code": "SAVE500",
                "name": "500円割引",
                "discount_type": "fixed",
                "discount_value": 500,
                "min_spend": 3000,
                "valid_from": value,
                "valid_until": "2027-04-30T23:59:59+09:00",
            }
        ],
    }

    loader = seeding.SeedLoader(data, reset=False)
    loader.validate()

    assert any(violation.field_name == "valid_from" for violation in loader.violations)
