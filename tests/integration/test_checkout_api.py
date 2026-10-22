# trace: FR-030, ADDR-001, ADDR-003, ADDR-007
"""注文確定（FR-030）の結合試験。

期待結果は機能要件定義書 6.15（処理内容・出力・事後条件・例外 E-030-03〜E-030-10）と
api-contract 6.2・6.3、ADDR-001（トランザクション・ロック）・ADDR-003（注文番号採番）から導出する。
"""
import re
from datetime import timedelta

import pytest
from django.db import connection

from shop.common import timeutils
from shop.models import (
    Cart,
    CartLine,
    CartStatus,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseOrderStatus,
    PurchaseOrderStatusHistory,
    ShippingAddress,
)
from tests.integration import _helpers

pytestmark = pytest.mark.django_db

ORDER_NUMBER_PATTERN = re.compile(r"^PO-[0-9]{8}$")


# trace: FR-030
def _buyer(api, email="buyer@example.com"):
    """購入者を作成し、認証トークンを返す。"""
    _helpers.make_user(email=email)
    return api.login(email)


# trace: FR-030
def _stock_unit(sku="SKU-001", price=1000, quantity=10, is_public=True):
    """在庫単位を1件作成する。"""
    supplier = _helpers.make_supplier(supplier_code=f"SUP-{sku}")
    item = _helpers.make_item(item_code=f"ITEM-{sku}", name=f"商品{sku}", is_public=is_public)
    return item, _helpers.make_stock_unit(item, supplier, sku=sku, price=price, quantity=quantity)


# trace: FR-030, ADDR-001, ADDR-003
@pytest.mark.case("IT-AI-031")
def test_checkout_commits_stock_order_address_history_and_cart(api):
    """注文確定で在庫引当・注文/明細/配送先/履歴の登録・カートの注文済化が一括で成立する（ST-PO-01、ST-CART-02）。"""
    token = _buyer(api)
    _item, unit = _stock_unit()
    api.post("/api/cart/lines", {"stock_unit_id": unit.stock_unit_id, "quantity": 2}, token=token)

    response = api.post("/api/checkout", dict(_helpers.VALID_ADDRESS), token=token)

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == PurchaseOrderStatus.CREATED
    assert ORDER_NUMBER_PATTERN.match(body["order_number"])
    assert body["amounts"] == {
        "subtotal": 2000,
        "discount_amount": 0,
        "discounted_subtotal": 2000,
        "shipping_fee": 500,
        "tax_amount": 250,
        "total": 2750,
    }
    assert body["can_pay"] is True
    assert body["can_cancel"] is True
    assert "payment_records" not in body

    unit.refresh_from_db()
    assert unit.quantity == 8

    order = PurchaseOrder.objects.get()
    line = PurchaseOrderLine.objects.get()
    assert line.purchase_order_id == order.purchase_order_id
    assert line.quantity == 2
    assert line.unit_price == 1000
    assert line.line_amount == 2000
    assert line.sku == unit.sku

    address = ShippingAddress.objects.get()
    assert address.postal_code == "1234567"
    assert address.phone_number == "09012345678"
    assert address.address_line2 == _helpers.VALID_ADDRESS["address_line2"]

    history = list(PurchaseOrderStatusHistory.objects.all())
    assert len(history) == 1
    assert history[0].from_status is None
    assert history[0].to_status == PurchaseOrderStatus.CREATED
    assert history[0].actor_role == "buyer"

    cart = Cart.objects.get()
    assert cart.status == CartStatus.CONVERTED
    assert cart.converted_at is not None
    assert Cart.objects.filter(status=CartStatus.OPEN).count() == 0


# trace: FR-030, ADDR-007
@pytest.mark.case("IT-AI-032")
def test_checkout_reports_all_invalid_address_fields(api):
    """配送先の入力エラーは全項目を通知し、在庫・カート・注文を変更しない（E-030-03）。"""
    token = _buyer(api)
    _item, unit = _stock_unit()
    api.post("/api/cart/lines", {"stock_unit_id": unit.stock_unit_id, "quantity": 2}, token=token)

    response = api.post(
        "/api/checkout",
        {
            "recipient_name": "",
            "postal_code": "12345",
            "prefecture_code": "99",
            "address_line1": "",
            "phone_number": "03-12",
        },
        token=token,
    )

    assert response.status_code == 400
    assert _helpers.error_code(response) == "VALIDATION_ERROR"
    assert _helpers.error_fields(response) == {
        "recipient_name",
        "postal_code",
        "prefecture_code",
        "address_line1",
        "phone_number",
    }
    unit.refresh_from_db()
    assert unit.quantity == 10
    assert PurchaseOrder.objects.count() == 0
    assert Cart.objects.get().status == CartStatus.OPEN


# trace: FR-030, ADDR-007
@pytest.mark.case("IT-AI-033")
def test_checkout_rejects_empty_cart_and_double_submission(api):
    """空カート・同一カートの二重確定は CART_EMPTY となり、注文は1件だけ作成される（E-030-04、CMN-23）。"""
    empty_token = _buyer(api, email="empty@example.com")
    empty = api.post("/api/checkout", dict(_helpers.VALID_ADDRESS), token=empty_token)

    token = _buyer(api)
    _item, unit = _stock_unit()
    api.post("/api/cart/lines", {"stock_unit_id": unit.stock_unit_id, "quantity": 1}, token=token)
    first = api.post("/api/checkout", dict(_helpers.VALID_ADDRESS), token=token)
    second = api.post("/api/checkout", dict(_helpers.VALID_ADDRESS), token=token)

    assert empty.status_code == 409
    assert _helpers.error_code(empty) == "CART_EMPTY"
    assert first.status_code == 201
    assert second.status_code == 409
    assert _helpers.error_code(second) == "CART_EMPTY"
    assert PurchaseOrder.objects.count() == 1
    unit.refresh_from_db()
    assert unit.quantity == 9


# trace: FR-030, ADDR-007
@pytest.mark.case("IT-AI-034")
def test_checkout_rejects_private_item(api):
    """非公開商品を含むカートの注文確定は ITEM_NOT_AVAILABLE となる（E-030-05）。"""
    token = _buyer(api)
    item, unit = _stock_unit()
    api.post("/api/cart/lines", {"stock_unit_id": unit.stock_unit_id, "quantity": 2}, token=token)
    item.is_public = False
    item.save(update_fields=["is_public"])

    response = api.post("/api/checkout", dict(_helpers.VALID_ADDRESS), token=token)

    assert response.status_code == 409
    assert _helpers.error_code(response) == "ITEM_NOT_AVAILABLE"
    assert response.json()["error"]["context"]["stock_unit_ids"] == [unit.stock_unit_id]
    unit.refresh_from_db()
    assert unit.quantity == 10
    assert PurchaseOrder.objects.count() == 0
    assert CartLine.objects.count() == 1


# trace: FR-030, ADDR-001, ADDR-007
@pytest.mark.case("IT-AI-035")
def test_checkout_allocates_nothing_when_any_line_is_short(api):
    """一部明細の在庫不足で全在庫を引き当てず、注文関連データも作成しない（E-030-10、CMN-21）。"""
    token = _buyer(api)
    _item_a, unit_a = _stock_unit(sku="SKU-A", quantity=5)
    _item_b, unit_b = _stock_unit(sku="SKU-B", quantity=5)
    _item_c, unit_c = _stock_unit(sku="SKU-C", quantity=5)
    for unit, quantity in [(unit_a, 3), (unit_b, 2), (unit_c, 4)]:
        assert (
            api.post(
                "/api/cart/lines", {"stock_unit_id": unit.stock_unit_id, "quantity": quantity}, token=token
            ).status_code
            == 200
        )
    unit_b.quantity = 1
    unit_b.save(update_fields=["quantity"])
    unit_c.quantity = 0
    unit_c.save(update_fields=["quantity"])

    response = api.post("/api/checkout", dict(_helpers.VALID_ADDRESS), token=token)

    assert response.status_code == 409
    assert _helpers.error_code(response) == "INSUFFICIENT_STOCK"
    assert response.json()["error"]["context"]["shortages"] == [
        {
            "stock_unit_id": unit_b.stock_unit_id,
            "sku": unit_b.sku,
            "requested_quantity": 2,
            "available_quantity": 1,
        },
        {
            "stock_unit_id": unit_c.stock_unit_id,
            "sku": unit_c.sku,
            "requested_quantity": 4,
            "available_quantity": 0,
        },
    ]
    unit_a.refresh_from_db()
    unit_b.refresh_from_db()
    unit_c.refresh_from_db()
    assert [unit_a.quantity, unit_b.quantity, unit_c.quantity] == [5, 1, 0]
    assert PurchaseOrder.objects.count() == 0
    assert PurchaseOrderLine.objects.count() == 0
    assert ShippingAddress.objects.count() == 0
    assert PurchaseOrderStatusHistory.objects.count() == 0


# trace: FR-030, ADDR-007
@pytest.mark.case("IT-AI-036")
def test_checkout_revalidates_coupon_without_removing_it(api):
    """確定時にクーポン条件を満たさない場合は業務エラーとなり、クーポンも自動で外れない（E-030-08、E-030-09）。"""
    token = _buyer(api)
    _item, unit = _stock_unit(price=1000)
    api.post("/api/cart/lines", {"stock_unit_id": unit.stock_unit_id, "quantity": 2}, token=token)
    coupon = _helpers.make_coupon(code="SAVE100", discount_value=100, min_spend=0)
    assert api.post("/api/cart/apply-coupon", {"code": "SAVE100"}, token=token).status_code == 200

    coupon.valid_until = timeutils.now() - timedelta(seconds=1)
    coupon.valid_from = coupon.valid_until
    coupon.save(update_fields=["valid_from", "valid_until"])
    expired = api.post("/api/checkout", dict(_helpers.VALID_ADDRESS), token=token)

    coupon.valid_from = timeutils.now() - timedelta(days=1)
    coupon.valid_until = timeutils.now() + timedelta(days=1)
    coupon.min_spend = 9000
    coupon.save(update_fields=["valid_from", "valid_until", "min_spend"])
    min_spend = api.post("/api/checkout", dict(_helpers.VALID_ADDRESS), token=token)

    assert expired.status_code == 409
    assert _helpers.error_code(expired) == "COUPON_EXPIRED"
    assert set(expired.json()["error"]["context"]) == {"valid_from", "valid_until"}
    assert min_spend.status_code == 409
    assert _helpers.error_code(min_spend) == "COUPON_MIN_SPEND_NOT_MET"
    assert min_spend.json()["error"]["context"] == {"min_spend": 9000, "subtotal": 2000}

    unit.refresh_from_db()
    assert unit.quantity == 10
    assert PurchaseOrder.objects.count() == 0
    cart = Cart.objects.get(status=CartStatus.OPEN)
    assert cart.coupon_id == coupon.coupon_id


# trace: FR-030, ADDR-007
@pytest.mark.case("IT-AI-GF-004")
def test_checkout_rejects_line_quantity_over_limit(api):
    """数量が10を超える明細を含むカートの注文確定は数量上限エラーとなる（E-030-06）。

    データ要件（DQ-10）の数量上限は使い捨てテストDBの制約として実装されているため、
    本ケースでは当該制約のみを一時的に外して「数量11の明細」を作り、
    注文確定側の再判定（FR-030 手順6）が働くことを確認する。
    """
    token = _buyer(api)
    _item, unit = _stock_unit(quantity=20)
    api.post("/api/cart/lines", {"stock_unit_id": unit.stock_unit_id, "quantity": 5}, token=token)
    with connection.cursor() as cursor:
        cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
        cursor.execute("ALTER TABLE cart_line DROP CONSTRAINT cart_line_quantity_range")
    CartLine.objects.update(quantity=11)

    response = api.post("/api/checkout", dict(_helpers.VALID_ADDRESS), token=token)

    assert response.status_code == 409
    assert _helpers.error_code(response) == "QUANTITY_LIMIT_EXCEEDED"
    assert response.json()["error"]["context"] == {
        "stock_unit_id": unit.stock_unit_id,
        "limit": 10,
        "current_quantity": 11,
        "requested_quantity": 11,
    }
    unit.refresh_from_db()
    assert unit.quantity == 20
    assert PurchaseOrder.objects.count() == 0


# trace: FR-030, ADDR-003
@pytest.mark.case("IT-AI-GF-005")
def test_order_numbers_are_unique_and_increasing(api):
    """注文番号は PO-＋8桁ゼロ埋めで一意、確定順に大きくなる（FR-030 手順12、ADDR-003）。"""
    token = _buyer(api)
    _item_a, unit_a = _stock_unit(sku="SKU-A")
    _item_b, unit_b = _stock_unit(sku="SKU-B")

    api.post("/api/cart/lines", {"stock_unit_id": unit_a.stock_unit_id, "quantity": 1}, token=token)
    first = api.post("/api/checkout", dict(_helpers.VALID_ADDRESS), token=token)
    api.post("/api/cart/lines", {"stock_unit_id": unit_b.stock_unit_id, "quantity": 1}, token=token)
    second = api.post("/api/checkout", dict(_helpers.VALID_ADDRESS), token=token)

    first_number = first.json()["order_number"]
    second_number = second.json()["order_number"]
    assert ORDER_NUMBER_PATTERN.match(first_number)
    assert ORDER_NUMBER_PATTERN.match(second_number)
    assert first_number != second_number
    assert second_number > first_number
    assert PurchaseOrder.objects.values("order_number").distinct().count() == 2
