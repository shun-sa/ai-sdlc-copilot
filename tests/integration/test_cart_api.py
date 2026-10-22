# trace: FR-020, FR-021, FR-022, FR-023, FR-024, FR-025, FR-026, ADDR-001, ADDR-004, ADDR-007
"""カート機能と注文金額計算（FR-020〜FR-026）の結合試験。

期待結果は機能要件定義書 6.8〜6.14（処理内容・計算例・例外）と
api-contract 6.2・6.3、ADDR-001・ADDR-004・ADDR-007 から導出する。
"""
from datetime import timedelta

import pytest

from shop.common import timeutils
from shop.models import Cart, CartLine, CartStatus, DiscountType
from tests.integration import _helpers

pytestmark = pytest.mark.django_db


# trace: FR-020, FR-021
def _buyer_with_cart(api, email="buyer@example.com", price=1000, quantity=10, add_quantity=None, sku="SKU-001"):
    """購入者・トークン・在庫単位を用意し、必要に応じてカート明細を1件追加する。"""
    _helpers.make_user(email=email)
    token = api.login(email)
    supplier = _helpers.make_supplier(supplier_code=f"SUP-{sku}")
    item = _helpers.make_item(item_code=f"ITEM-{sku}", name=f"商品{sku}")
    unit = _helpers.make_stock_unit(item, supplier, sku=sku, price=price, quantity=quantity)
    if add_quantity:
        response = api.post(
            "/api/cart/lines", {"stock_unit_id": unit.stock_unit_id, "quantity": add_quantity}, token=token
        )
        assert response.status_code == 200, response.content
    return token, item, unit


# trace: FR-020, ADDR-001
@pytest.mark.case("IT-AI-019")
def test_cart_view_creates_open_cart_once(api):
    """利用中カートがない場合は空のカートを1件作成し、再照会しても増えない（ST-CART-01）。"""
    _helpers.make_user(email="buyer@example.com")
    token = api.login("buyer@example.com")

    first = api.get("/api/cart", token=token)
    second = api.get("/api/cart", token=token)

    assert first.status_code == 200
    body = first.json()
    assert body["lines"] == []
    assert body["coupon"] is None
    assert body["total_quantity"] == 0
    assert body["amounts"] == {
        "subtotal": 0,
        "discount_amount": 0,
        "discounted_subtotal": 0,
        "shipping_fee": 0,
        "tax_amount": 0,
        "total": 0,
    }
    assert second.status_code == 200
    assert Cart.objects.filter(status=CartStatus.OPEN).count() == 1


# trace: FR-021, ADDR-001, ADDR-004
@pytest.mark.case("IT-AI-020")
def test_cart_line_add_merges_same_stock_unit(api):
    """同一在庫単位の明細は1行に合算され、DBへ反映される（FR-021 手順9）。"""
    token, item, unit = _buyer_with_cart(api)

    first = api.post("/api/cart/lines", {"stock_unit_id": unit.stock_unit_id, "quantity": 2}, token=token)
    second = api.post("/api/cart/lines", {"stock_unit_id": unit.stock_unit_id, "quantity": 3}, token=token)

    assert first.status_code == 200
    assert second.status_code == 200
    body = second.json()
    assert len(body["lines"]) == 1
    line = body["lines"][0]
    assert line["quantity"] == 5
    assert line["unit_price"] == 1000
    assert line["line_amount"] == 5000
    assert line["item_name"] == item.name
    assert line["stock_quantity"] == 10
    assert body["total_quantity"] == 5
    assert body["amounts"]["subtotal"] == 5000

    stored = CartLine.objects.get()
    assert stored.quantity == 5
    unit.refresh_from_db()
    assert unit.quantity == 10


# trace: FR-021, ADDR-007
@pytest.mark.case("IT-AI-021")
def test_cart_line_add_rejects_quantity_over_limit(api):
    """合算数量が10を超える追加は数量上限エラーとなり、カートは変化しない（E-021-05）。"""
    token, _item, unit = _buyer_with_cart(api, quantity=20, add_quantity=8)

    response = api.post("/api/cart/lines", {"stock_unit_id": unit.stock_unit_id, "quantity": 3}, token=token)

    assert response.status_code == 409
    assert _helpers.error_code(response) == "QUANTITY_LIMIT_EXCEEDED"
    assert response.json()["error"]["context"] == {
        "stock_unit_id": unit.stock_unit_id,
        "limit": 10,
        "current_quantity": 8,
        "requested_quantity": 11,
    }
    assert CartLine.objects.get().quantity == 8


# trace: FR-021, ADDR-001, ADDR-007
@pytest.mark.case("IT-AI-022")
def test_cart_line_add_rejects_insufficient_stock(api):
    """在庫数量を超える追加は在庫不足エラーとなり、在庫・カートは変化しない（E-021-06）。"""
    token, _item, unit = _buyer_with_cart(api, quantity=2)

    response = api.post("/api/cart/lines", {"stock_unit_id": unit.stock_unit_id, "quantity": 3}, token=token)

    assert response.status_code == 409
    assert _helpers.error_code(response) == "INSUFFICIENT_STOCK"
    assert response.json()["error"]["context"]["shortages"] == [
        {
            "stock_unit_id": unit.stock_unit_id,
            "sku": unit.sku,
            "requested_quantity": 3,
            "available_quantity": 2,
        }
    ]
    unit.refresh_from_db()
    assert unit.quantity == 2
    assert CartLine.objects.count() == 0


# trace: FR-022, ADDR-001
@pytest.mark.case("IT-AI-023")
def test_cart_line_quantity_change_updates_amounts(api):
    """カート明細の数量変更が明細と金額内訳へ反映される（FR-022）。"""
    token, _item, unit = _buyer_with_cart(api, add_quantity=2)
    cart_line_id = CartLine.objects.get().cart_line_id

    response = api.patch(f"/api/cart/lines/{cart_line_id}", {"quantity": 4}, token=token)

    assert response.status_code == 200
    body = response.json()
    assert body["lines"][0]["quantity"] == 4
    assert body["lines"][0]["line_amount"] == 4000
    assert body["amounts"]["subtotal"] == 4000
    assert CartLine.objects.get().quantity == 4


# trace: FR-022, ADDR-007
@pytest.mark.case("IT-AI-024")
def test_cart_line_quantity_change_rejects_invalid_targets(api):
    """数量上限超過・在庫超過・他の購入者の明細指定はいずれも拒否される（E-022-05、E-022-06、E-022-04）。"""
    token, _item, _unit = _buyer_with_cart(api, quantity=5, add_quantity=2)
    cart_line_id = CartLine.objects.get().cart_line_id
    other_token, _other_item, other_unit = _buyer_with_cart(
        api, email="other@example.com", sku="SKU-002", add_quantity=1
    )
    other_line_id = CartLine.objects.exclude(cart_line_id=cart_line_id).get().cart_line_id

    over_limit = api.patch(f"/api/cart/lines/{cart_line_id}", {"quantity": 11}, token=token)
    over_stock = api.patch(f"/api/cart/lines/{cart_line_id}", {"quantity": 6}, token=token)
    other_line = api.patch(f"/api/cart/lines/{other_line_id}", {"quantity": 2}, token=token)

    assert over_limit.status_code == 409
    assert _helpers.error_code(over_limit) == "QUANTITY_LIMIT_EXCEEDED"
    assert over_stock.status_code == 409
    assert _helpers.error_code(over_stock) == "INSUFFICIENT_STOCK"
    assert other_line.status_code == 404
    assert _helpers.error_code(other_line) == "NOT_FOUND"

    assert CartLine.objects.get(cart_line_id=cart_line_id).quantity == 2
    assert CartLine.objects.get(cart_line_id=other_line_id).quantity == 1
    assert other_token is not None and other_unit is not None


# trace: FR-023, ADDR-001
@pytest.mark.case("IT-AI-025")
def test_cart_line_delete_removes_line_and_recalculates(api):
    """カート明細削除で明細が消え金額が再計算され、再操作は対象なしとなる（FR-023）。"""
    token, _item, unit = _buyer_with_cart(api, add_quantity=2)
    second_supplier = _helpers.make_supplier(supplier_code="SUP-002")
    second_item = _helpers.make_item(item_code="ITEM-002", name="商品2")
    second_unit = _helpers.make_stock_unit(second_item, second_supplier, sku="SKU-002", price=500, quantity=5)
    api.post("/api/cart/lines", {"stock_unit_id": second_unit.stock_unit_id, "quantity": 1}, token=token)
    target = CartLine.objects.get(stock_unit=unit).cart_line_id

    response = api.delete(f"/api/cart/lines/{target}", token=token)
    again = api.delete(f"/api/cart/lines/{target}", token=token)

    assert response.status_code == 200
    body = response.json()
    assert [line["stock_unit_id"] for line in body["lines"]] == [second_unit.stock_unit_id]
    assert body["amounts"]["subtotal"] == 500
    assert CartLine.objects.count() == 1
    assert again.status_code == 404
    assert _helpers.error_code(again) == "NOT_FOUND"


# trace: FR-024, FR-026, ADDR-001
@pytest.mark.case("IT-AI-026")
def test_apply_coupon_reflects_discount(api):
    """有効なクーポンの適用で割引額と金額内訳が更新される（FR-024、FR-026 計算例4）。"""
    token, _item, _unit = _buyer_with_cart(api, price=3000, add_quantity=2)
    coupon = _helpers.make_coupon(code="SAVE1000", discount_value=1000, min_spend=3000)

    response = api.post("/api/cart/apply-coupon", {"code": "save1000"}, token=token)

    assert response.status_code == 200
    body = response.json()
    assert body["coupon"]["code"] == coupon.code
    assert body["coupon"]["name"] == coupon.name
    assert body["coupon"]["discount_type"] == DiscountType.FIXED
    assert body["coupon"]["discount_value"] == 1000
    assert body["coupon"]["min_spend"] == 3000
    assert body["coupon"]["valid_from"] is not None
    assert body["coupon"]["valid_until"] is not None
    assert body["coupon"]["is_applicable"] is True
    assert body["coupon"]["not_applicable_reason"] is None
    assert body["amounts"] == {
        "subtotal": 6000,
        "discount_amount": 1000,
        "discounted_subtotal": 5000,
        "shipping_fee": 0,
        "tax_amount": 500,
        "total": 5500,
    }


# trace: FR-024, ADDR-007
@pytest.mark.case("IT-AI-027")
def test_apply_coupon_business_errors(api):
    """クーポン適用の各業務エラーが条件ごとに正しいコード・contextで返る（E-024-04〜E-024-09）。"""
    now = timeutils.now()
    token, _item, _unit = _buyer_with_cart(api, price=1000, add_quantity=2)
    _helpers.make_coupon(code="VALID", discount_value=100, min_spend=0)
    _helpers.make_coupon(
        code="FUTURE",
        discount_value=100,
        valid_from=now + timedelta(days=1),
        valid_until=now + timedelta(days=2),
    )
    _helpers.make_coupon(
        code="PAST",
        discount_value=100,
        valid_from=now - timedelta(days=2),
        valid_until=now - timedelta(days=1),
    )
    _helpers.make_coupon(code="HIGHMIN", discount_value=100, min_spend=9000)

    unknown = api.post("/api/cart/apply-coupon", {"code": "NOTEXIST"}, token=token)
    not_yet = api.post("/api/cart/apply-coupon", {"code": "FUTURE"}, token=token)
    expired = api.post("/api/cart/apply-coupon", {"code": "PAST"}, token=token)
    min_spend = api.post("/api/cart/apply-coupon", {"code": "HIGHMIN"}, token=token)
    applied = api.post("/api/cart/apply-coupon", {"code": "VALID"}, token=token)
    already = api.post("/api/cart/apply-coupon", {"code": "VALID"}, token=token)

    empty_token, _empty_item, _empty_unit = _buyer_with_cart(api, email="empty@example.com", sku="SKU-002")
    empty_cart = api.post("/api/cart/apply-coupon", {"code": "VALID"}, token=empty_token)

    assert _helpers.error_code(unknown) == "COUPON_NOT_FOUND"
    assert unknown.status_code == 409
    assert _helpers.error_code(not_yet) == "COUPON_NOT_YET_VALID"
    assert set(not_yet.json()["error"]["context"]) == {"valid_from", "valid_until"}
    assert _helpers.error_code(expired) == "COUPON_EXPIRED"
    assert set(expired.json()["error"]["context"]) == {"valid_from", "valid_until"}
    assert _helpers.error_code(min_spend) == "COUPON_MIN_SPEND_NOT_MET"
    assert min_spend.json()["error"]["context"] == {"min_spend": 9000, "subtotal": 2000}
    assert applied.status_code == 200
    assert _helpers.error_code(already) == "COUPON_ALREADY_APPLIED"
    assert _helpers.error_code(empty_cart) == "CART_EMPTY"

    cart = Cart.objects.get(status=CartStatus.OPEN, user__email="buyer@example.com")
    assert cart.coupon.code == "VALID"


# trace: FR-025, ADDR-001
@pytest.mark.case("IT-AI-028")
def test_remove_coupon_restores_amounts(api):
    """クーポン解除で割引が取り消され金額が再計算される（FR-025）。"""
    token, _item, _unit = _buyer_with_cart(api, price=3000, add_quantity=2)
    _helpers.make_coupon(code="SAVE1000", discount_value=1000)
    api.post("/api/cart/apply-coupon", {"code": "SAVE1000"}, token=token)

    response = api.post("/api/cart/remove-coupon", token=token)

    assert response.status_code == 200
    body = response.json()
    assert body["coupon"] is None
    assert body["amounts"]["discount_amount"] == 0
    assert body["amounts"]["discounted_subtotal"] == 6000
    assert Cart.objects.get(status=CartStatus.OPEN).coupon_id is None


# trace: FR-026, ADDR-004
@pytest.mark.case("IT-AI-029")
def test_shipping_and_tax_boundary_at_5000(api):
    """割引後小計5,000円の境界で送料・消費税が要件どおり算出される（FR-026 計算例1・2）。"""
    under_token, _under_item, _under_unit = _buyer_with_cart(api, price=4999, add_quantity=1)
    exact_token, _exact_item, _exact_unit = _buyer_with_cart(
        api, email="exact@example.com", sku="SKU-002", price=5000, add_quantity=1
    )

    under = api.get("/api/cart", token=under_token)
    exact = api.get("/api/cart", token=exact_token)

    assert under.json()["amounts"] == {
        "subtotal": 4999,
        "discount_amount": 0,
        "discounted_subtotal": 4999,
        "shipping_fee": 500,
        "tax_amount": 549,
        "total": 6048,
    }
    assert exact.json()["amounts"] == {
        "subtotal": 5000,
        "discount_amount": 0,
        "discounted_subtotal": 5000,
        "shipping_fee": 0,
        "tax_amount": 500,
        "total": 5500,
    }


# trace: FR-026, ADDR-004
@pytest.mark.case("IT-AI-030")
def test_discount_amount_for_percentage_and_fixed_coupons(api):
    """定率は1円未満切り捨て、定額は min(割引値, 小計) で割引額を求める（FR-026 計算例5・6）。"""
    rate_token, _rate_item, _rate_unit = _buyer_with_cart(api, price=1999, add_quantity=1)
    fixed_token, _fixed_item, _fixed_unit = _buyer_with_cart(
        api, email="fixed@example.com", sku="SKU-002", price=800, add_quantity=1
    )
    _helpers.make_coupon(
        code="RATE15", name="15%割引", discount_type=DiscountType.PERCENTAGE, discount_value=15, min_spend=0
    )
    _helpers.make_coupon(code="FIXED1000", discount_value=1000, min_spend=0)

    rate = api.post("/api/cart/apply-coupon", {"code": "RATE15"}, token=rate_token)
    fixed = api.post("/api/cart/apply-coupon", {"code": "FIXED1000"}, token=fixed_token)

    assert rate.json()["amounts"] == {
        "subtotal": 1999,
        "discount_amount": 299,
        "discounted_subtotal": 1700,
        "shipping_fee": 500,
        "tax_amount": 220,
        "total": 2420,
    }
    assert fixed.json()["amounts"] == {
        "subtotal": 800,
        "discount_amount": 800,
        "discounted_subtotal": 0,
        "shipping_fee": 500,
        "tax_amount": 50,
        "total": 550,
    }


# trace: FR-021, ADDR-007
@pytest.mark.case("IT-AI-GF-002")
def test_cart_line_add_hides_unknown_and_private_stock_units(api):
    """存在しない・非公開商品の在庫単位は対象なし、整数でない値は入力エラーとなる（E-021-03、E-021-04）。"""
    token, _item, _unit = _buyer_with_cart(api)
    hidden_supplier = _helpers.make_supplier(supplier_code="SUP-HID")
    hidden_item = _helpers.make_item(item_code="ITEM-HID", name="非公開商品", is_public=False)
    hidden_unit = _helpers.make_stock_unit(hidden_item, hidden_supplier, sku="SKU-HID")

    unknown = api.post("/api/cart/lines", {"stock_unit_id": 999999, "quantity": 1}, token=token)
    private = api.post("/api/cart/lines", {"stock_unit_id": hidden_unit.stock_unit_id, "quantity": 1}, token=token)
    malformed = api.post("/api/cart/lines", {"stock_unit_id": "not-an-id", "quantity": 1}, token=token)

    assert unknown.status_code == 404
    assert _helpers.error_code(unknown) == "NOT_FOUND"
    assert private.status_code == 404
    assert private.json()["error"] == unknown.json()["error"]
    assert malformed.status_code == 400
    assert _helpers.error_code(malformed) == "VALIDATION_ERROR"
    assert "stock_unit_id" in _helpers.error_fields(malformed)
    assert CartLine.objects.count() == 0


# trace: FR-026, ADDR-004
@pytest.mark.case("IT-AI-GF-003")
def test_inapplicable_coupon_stays_applied_with_reason(api):
    """適用中クーポンが条件を満たさない場合も自動で外さず、適用不可理由を返す（FR-026 手順1・3）。"""
    token, _item, _unit = _buyer_with_cart(api, price=1000, add_quantity=2)
    coupon = _helpers.make_coupon(code="SAVE100", discount_value=100, min_spend=0)
    assert api.post("/api/cart/apply-coupon", {"code": "SAVE100"}, token=token).status_code == 200

    coupon.min_spend = 9000
    coupon.save(update_fields=["min_spend"])
    min_spend = api.get("/api/cart", token=token)

    coupon.min_spend = 0
    coupon.valid_until = timeutils.now() - timedelta(seconds=1)
    coupon.valid_from = coupon.valid_until - timedelta(days=1)
    coupon.save(update_fields=["min_spend", "valid_from", "valid_until"])
    expired = api.get("/api/cart", token=token)

    api.delete(f"/api/cart/lines/{CartLine.objects.get().cart_line_id}", token=token)
    empty = api.get("/api/cart", token=token)

    assert min_spend.json()["coupon"]["is_applicable"] is False
    assert min_spend.json()["coupon"]["not_applicable_reason"] == "COUPON_MIN_SPEND_NOT_MET"
    assert min_spend.json()["amounts"]["discount_amount"] == 0
    assert min_spend.json()["amounts"]["subtotal"] == 2000

    assert expired.json()["coupon"]["not_applicable_reason"] == "COUPON_EXPIRED"
    assert expired.json()["amounts"]["discount_amount"] == 0

    assert empty.json()["coupon"]["is_applicable"] is False
    assert empty.json()["coupon"]["not_applicable_reason"] == "CART_EMPTY"
    assert empty.json()["amounts"] == {
        "subtotal": 0,
        "discount_amount": 0,
        "discounted_subtotal": 0,
        "shipping_fee": 0,
        "tax_amount": 0,
        "total": 0,
    }
    assert Cart.objects.get(status=CartStatus.OPEN).coupon_id == coupon.coupon_id
