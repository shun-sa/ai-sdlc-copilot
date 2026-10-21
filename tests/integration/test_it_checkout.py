# trace: FR-026, FR-030, NFR-PF-07, NFR-LG-06, NFR-LG-09, NFR-US-09, FR-OUT-10
# trace: ADDR-003, ADDR-008, ADDR-010, ADDR-011
"""注文確定の結合試験（IT-AI-INIT-087〜103）。

検証対象の連携は カート → 注文 → 在庫 の複数FR連携、トランザクション・同時実行制御 →
PostgreSQL、注文金額計算 → 注文Service → DB、画面 → Service → DB。

期待結果は FR-030（処理内容・入力・出力・例外・排他）、FR-026（金額計算）、
CMN-14/CMN-19/CMN-20/CMN-21/CMN-23、ST-PO-01・ST-CART-02、提供済みAPI契約 6.2/6.3、
ADDR-003（在庫の一括引当とロック順序）から導出する。
"""

from __future__ import annotations

import datetime as dt

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from carts.models import CART_CONVERTED, Cart
from catalog.models import Item, StockUnit
from common import timeutils
from orders.models import STATUS_CREATED, PurchaseOrder

pytestmark = pytest.mark.django_db

SHIPPING = {
    "recipient_name": "結合 受取人",
    "postal_code": "1234567",
    "prefecture_code": "13",
    "address_line1": "千代田区1-1-1",
    "address_line2": "結合ビル101",
    "phone_number": "09012345678",
}


# trace: FR-030
def shipping(**overrides) -> dict:
    """配送先入力（架空の住所・電話番号）。"""
    payload = dict(SHIPPING)
    payload.update(overrides)
    return payload


# trace: FR-030
def add_line(client, stock_unit, quantity: int) -> dict:
    """カートへ明細を追加する（試験前提データの準備）。"""
    response = client.post(
        "/api/cart/lines", {"stock_unit_id": stock_unit.pk, "quantity": quantity}, format="json"
    )
    assert response.status_code == 200
    return response.json()


# trace: FR-030, ADDR-003
def test_it_ai_init_087_checkout_creates_order_and_reserves_stock(api_as, buyer, f):
    """IT-AI-INIT-087 / COV-074：注文確定は注文受付の注文を作成し、在庫を引き当てカートを注文済にする。"""
    first = f.sellable(price=1000, quantity=10)
    second = f.sellable(price=2000, quantity=10)
    client = api_as(buyer)
    add_line(client, first, 2)
    add_line(client, second, 1)

    response = client.post("/api/checkout", shipping(), format="json")

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == STATUS_CREATED
    assert body["order_number"].startswith("PO-")
    assert len(body["lines"]) == 2
    assert body["amounts"]["subtotal"] == 4000

    order = PurchaseOrder.objects.get(pk=body["purchase_order_id"])
    assert order.user_id == buyer.pk
    assert order.ordered_at is not None
    first.refresh_from_db()
    second.refresh_from_db()
    assert first.quantity == 8
    assert second.quantity == 9
    cart = Cart.objects.get(user=buyer)
    assert cart.status == CART_CONVERTED
    assert cart.converted_at is not None
    history = list(order.status_history.all())
    assert len(history) == 1
    assert history[0].from_status is None
    assert history[0].to_status == STATUS_CREATED
    assert history[0].actor_role == "buyer"


# trace: FR-026, FR-030
def test_it_ai_init_088_checkout_records_applied_coupon(api_as, buyer, f):
    """IT-AI-INIT-088 / COV-075：クーポン内容と割引額を注文へ記録し、割引後の金額で確定する。"""
    unit = f.sellable(price=6000, quantity=5)
    f.coupon(code="ORDERCPN01", discount_value=1000)
    client = api_as(buyer)
    add_line(client, unit, 1)
    client.post("/api/cart/apply-coupon", {"code": "ORDERCPN01"}, format="json")

    response = client.post("/api/checkout", shipping(), format="json")

    assert response.status_code == 201
    body = response.json()
    assert body["coupon"] == {"code": "ORDERCPN01", "discount_type": "fixed", "discount_value": 1000}
    assert body["amounts"] == {
        "subtotal": 6000,
        "discount_amount": 1000,
        "discounted_subtotal": 5000,
        "shipping_fee": 0,
        "tax_amount": 500,
        "total": 5500,
    }
    order = PurchaseOrder.objects.get(pk=body["purchase_order_id"])
    assert order.coupon_code == "ORDERCPN01"
    assert order.coupon_discount_type == "fixed"
    assert order.coupon_discount_value == 1000
    assert order.discount_amount == 1000


# trace: FR-026, FR-030
def test_it_ai_init_089_shipping_fee_follows_discounted_subtotal(api_as, buyer, other_buyer, f):
    """IT-AI-INIT-089 / COV-075：送料は割引後小計で判定し、消費税は（割引後小計＋送料）×10÷100 とする。"""
    unit = f.sellable(price=5000, quantity=10)
    f.coupon(code="ONEYEN01", discount_value=1)
    short_client = api_as(buyer)
    add_line(short_client, unit, 1)
    short_client.post("/api/cart/apply-coupon", {"code": "ONEYEN01"}, format="json")

    below = short_client.post("/api/checkout", shipping(), format="json")

    assert below.status_code == 201
    assert below.json()["amounts"] == {
        "subtotal": 5000,
        "discount_amount": 1,
        "discounted_subtotal": 4999,
        "shipping_fee": 500,
        "tax_amount": 549,
        "total": 6048,
    }

    free_client = api_as(other_buyer)
    add_line(free_client, unit, 1)
    at_threshold = free_client.post("/api/checkout", shipping(), format="json")

    assert at_threshold.status_code == 201
    assert at_threshold.json()["amounts"] == {
        "subtotal": 5000,
        "discount_amount": 0,
        "discounted_subtotal": 5000,
        "shipping_fee": 0,
        "tax_amount": 500,
        "total": 5500,
    }


# trace: FR-030
def test_it_ai_init_090_order_lines_are_snapshots(api_as, buyer, f):
    """IT-AI-INIT-090 / COV-076：注文明細は確定時点のスナップショットのまま変化しない。"""
    unit = f.sellable(price=1000, quantity=10, name="確定時商品名")
    client = api_as(buyer)
    add_line(client, unit, 2)
    created = client.post("/api/checkout", shipping(), format="json").json()

    StockUnit.objects.filter(pk=unit.pk).update(price=5000)
    Item.objects.filter(pk=unit.item_id).update(name="変更後商品名")

    detail = client.get(f"/api/purchase-orders/{created['purchase_order_id']}")

    line = detail.json()["lines"][0]
    assert line["unit_price"] == 1000
    assert line["item_name"] == "確定時商品名"
    assert line["line_amount"] == 2000
    assert detail.json()["amounts"] == created["amounts"]


# trace: FR-030, ADDR-008, NFR-LG-09
def test_it_ai_init_091_shipping_address_is_normalized(api_as, buyer, other_buyer, f):
    """IT-AI-INIT-091 / COV-077：配送先は正規化して保存し、各項目の上限値を受け付ける。"""
    unit = f.sellable(price=1000, quantity=10)
    client = api_as(buyer)
    add_line(client, unit, 1)

    normalized = client.post(
        "/api/checkout",
        shipping(postal_code="123-4567", phone_number="090-1234-5678", recipient_name="  結合 太郎  "),
        format="json",
    )

    assert normalized.status_code == 201
    address = normalized.json()["shipping_address"]
    assert address["postal_code"] == "1234567"
    assert address["phone_number"] == "09012345678"
    assert address["recipient_name"] == "結合 太郎"

    max_client = api_as(other_buyer)
    add_line(max_client, unit, 1)
    maximum = max_client.post(
        "/api/checkout",
        shipping(
            recipient_name="名" * 50,
            address_line1="住" * 100,
            address_line2="建" * 100,
            prefecture_code="47",
            phone_number="09012345678",
            postal_code="1234567",
        ),
        format="json",
    )

    assert maximum.status_code == 201
    max_address = maximum.json()["shipping_address"]
    assert max_address["recipient_name"] == "名" * 50
    assert max_address["address_line1"] == "住" * 100
    assert max_address["address_line2"] == "建" * 100
    assert max_address["prefecture_code"] == "47"


# trace: FR-030, ADDR-011, NFR-LG-09
def test_it_ai_init_092_shipping_address_validation(api_as, buyer, f, err):
    """IT-AI-INIT-092 / COV-078：配送先の形式不正・未入力・文字数超過は入力エラーとし注文を作成しない。"""
    unit = f.sellable(price=1000, quantity=10)
    client = api_as(buyer)
    add_line(client, unit, 1)

    single_cases = [
        ({"postal_code": "123456"}, "postal_code"),
        ({"postal_code": "12345678"}, "postal_code"),
        ({"postal_code": "1234-567"}, "postal_code"),
        ({"postal_code": "123 4567"}, "postal_code"),
        ({"postal_code": "〒1234567"}, "postal_code"),
        ({"prefecture_code": "00"}, "prefecture_code"),
        ({"prefecture_code": "48"}, "prefecture_code"),
        ({"phone_number": "090123456"}, "phone_number"),
        ({"phone_number": "090123456789"}, "phone_number"),
        ({"recipient_name": "名" * 51}, "recipient_name"),
        ({"address_line1": "住" * 101}, "address_line1"),
        ({"address_line2": "建" * 101}, "address_line2"),
        ({"recipient_name": ""}, "recipient_name"),
        ({"address_line1": ""}, "address_line1"),
    ]
    for override, field in single_cases:
        response = client.post("/api/checkout", shipping(**override), format="json")

        assert response.status_code == 400, override
        assert err.code(response) == "VALIDATION_ERROR"
        assert field in err.fields(response), override

    combined = client.post(
        "/api/checkout",
        shipping(recipient_name="", postal_code="12345", prefecture_code="99", phone_number="abc"),
        format="json",
    )

    assert combined.status_code == 400
    assert set(err.fields(combined)) >= {
        "recipient_name",
        "postal_code",
        "prefecture_code",
        "phone_number",
    }
    assert not PurchaseOrder.objects.exists()
    unit.refresh_from_db()
    assert unit.quantity == 10
    assert Cart.objects.get(user=buyer).status == "open"


# trace: FR-030
def test_it_ai_init_093_empty_cart_checkout(api_as, buyer, err):
    """IT-AI-INIT-093 / COV-079：空カートの注文確定は入力判定を先に行い、業務エラーとする。"""
    client = api_as(buyer)
    client.get("/api/cart")

    invalid = client.post("/api/checkout", shipping(postal_code="xxx"), format="json")
    valid = client.post("/api/checkout", shipping(), format="json")

    assert invalid.status_code == 400
    assert err.code(invalid) == "VALIDATION_ERROR"
    assert valid.status_code == 409
    assert err.code(valid) == "CART_EMPTY"
    assert not PurchaseOrder.objects.exists()


# trace: FR-030, ADDR-003
def test_it_ai_init_094_checkout_rejects_unavailable_item(api_as, buyer, f, err):
    """IT-AI-INIT-094 / COV-080：確定時点で非公開の商品を含む場合は業務エラーとし何も変更しない。"""
    unit = f.sellable(price=1000, quantity=10)
    client = api_as(buyer)
    add_line(client, unit, 2)
    Item.objects.filter(pk=unit.item_id).update(is_public=False)

    response = client.post("/api/checkout", shipping(), format="json")

    assert response.status_code == 409
    assert err.code(response) == "ITEM_NOT_AVAILABLE"
    assert err.context(response) == {"stock_unit_ids": [unit.pk]}
    unit.refresh_from_db()
    assert unit.quantity == 10
    assert not PurchaseOrder.objects.exists()
    assert Cart.objects.get(user=buyer).status == "open"


# trace: FR-030, ADDR-003
def test_it_ai_init_095_insufficient_stock_keeps_every_line(api_as, buyer, f, err):
    """IT-AI-INIT-095 / COV-081：1明細でも在庫不足なら全明細の在庫を変更しない（CMN-21）。"""
    enough_a = f.sellable(price=1000, quantity=10)
    enough_b = f.sellable(price=1000, quantity=10)
    short = f.sellable(price=1000, quantity=10)
    client = api_as(buyer)
    add_line(client, enough_a, 1)
    add_line(client, enough_b, 1)
    add_line(client, short, 5)
    StockUnit.objects.filter(pk=short.pk).update(quantity=2)

    response = client.post("/api/checkout", shipping(), format="json")

    assert response.status_code == 409
    assert err.code(response) == "INSUFFICIENT_STOCK"
    assert err.context(response)["shortages"] == [
        {
            "stock_unit_id": short.pk,
            "sku": short.sku,
            "requested_quantity": 5,
            "available_quantity": 2,
        }
    ]
    for unit, expected in ((enough_a, 10), (enough_b, 10), (short, 2)):
        unit.refresh_from_db()
        assert unit.quantity == expected
    assert not PurchaseOrder.objects.exists()


# trace: FR-030
def test_it_ai_init_096_all_shortages_are_reported(api_as, buyer, f, err):
    """IT-AI-INIT-096 / COV-081：複数明細の在庫不足は context.shortages へ全件列挙する。"""
    enough = f.sellable(price=1000, quantity=10)
    short_a = f.sellable(price=1000, quantity=10)
    short_b = f.sellable(price=1000, quantity=10)
    client = api_as(buyer)
    add_line(client, enough, 1)
    add_line(client, short_a, 4)
    add_line(client, short_b, 3)
    StockUnit.objects.filter(pk=short_a.pk).update(quantity=1)
    StockUnit.objects.filter(pk=short_b.pk).update(quantity=0)

    response = client.post("/api/checkout", shipping(), format="json")

    assert response.status_code == 409
    shortages = {row["stock_unit_id"]: row for row in err.context(response)["shortages"]}
    assert set(shortages) == {short_a.pk, short_b.pk}
    assert shortages[short_a.pk] == {
        "stock_unit_id": short_a.pk,
        "sku": short_a.sku,
        "requested_quantity": 4,
        "available_quantity": 1,
    }
    assert shortages[short_b.pk]["available_quantity"] == 0


# trace: FR-030
def test_it_ai_init_097_coupon_conditions_are_rechecked_at_checkout(
    api_as, buyer, other_buyer, f, monkeypatch, err
):
    """IT-AI-INIT-097 / COV-082：確定時のクーポン条件違反は何も変更せず業務エラーとする。"""
    end = dt.datetime(2027, 7, 31, 23, 59, 59, tzinfo=timeutils.JST)
    clock = {"value": end - dt.timedelta(minutes=1)}
    monkeypatch.setattr(timezone, "now", lambda: clock["value"])
    unit = f.sellable(price=6000, quantity=10)
    expiring = f.coupon(
        code="CHECKEXP01",
        discount_value=1000,
        valid_from=end - dt.timedelta(days=10),
        valid_until=end,
    )
    client = api_as(buyer)
    add_line(client, unit, 1)
    client.post("/api/cart/apply-coupon", {"code": expiring.code}, format="json")

    clock["value"] = end + dt.timedelta(seconds=1)
    expired = client.post("/api/checkout", shipping(), format="json")

    assert expired.status_code == 409
    assert err.code(expired) == "COUPON_EXPIRED"
    unit.refresh_from_db()
    assert unit.quantity == 10
    assert not PurchaseOrder.objects.exists()

    clock["value"] = end.replace(microsecond=400000)
    same_second = client.post("/api/checkout", shipping(), format="json")

    assert same_second.status_code == 201
    unit.refresh_from_db()
    assert unit.quantity == 9

    min_spend_client = api_as(other_buyer)
    min_unit = f.sellable(price=1000, quantity=10)
    f.coupon(
        code="CHECKMIN01",
        discount_value=100,
        min_spend=5000,
        valid_from=end - dt.timedelta(days=10),
        valid_until=end + dt.timedelta(days=10),
    )
    line_id = add_line(min_spend_client, min_unit, 5)["lines"][0]["cart_line_id"]
    min_spend_client.post("/api/cart/apply-coupon", {"code": "CHECKMIN01"}, format="json")
    min_spend_client.patch(f"/api/cart/lines/{line_id}", {"quantity": 4}, format="json")

    not_met = min_spend_client.post("/api/checkout", shipping(), format="json")

    assert not_met.status_code == 409
    assert err.code(not_met) == "COUPON_MIN_SPEND_NOT_MET"
    min_unit.refresh_from_db()
    assert min_unit.quantity == 10


# trace: FR-030, ADDR-003, NFR-PF-07, NFR-LG-06
@pytest.mark.django_db(transaction=True)
def test_it_ai_init_098_concurrent_checkout_for_last_item(f, token_for, run_parallel):
    """IT-AI-INIT-098 / COV-083：在庫数量1への同時確定は1件だけ成功し、在庫は0未満にならない。"""
    unit = f.sellable(price=1000, quantity=1)
    buyers = [f.user(email=f"race-checkout{index}@example.test") for index in range(2)]
    tokens = []
    for user in buyers:
        f.fill_cart(user, (unit, 1))
        tokens.append(token_for(user))

    def checkout(token: str):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        return client.post("/api/checkout", SHIPPING, format="json")

    try:
        results = run_parallel(lambda: checkout(tokens[0]), lambda: checkout(tokens[1]))

        statuses = sorted(response.status_code for response in results)
        assert statuses == [201, 409]
        failed = next(response for response in results if response.status_code == 409)
        body = failed.json()
        assert (body.get("error") or body)["code"] == "INSUFFICIENT_STOCK"
        unit.refresh_from_db()
        assert unit.quantity == 0
        assert PurchaseOrder.objects.count() == 1
    finally:
        PurchaseOrder.objects.all().delete()
        Cart.objects.all().delete()


# trace: FR-030, ADDR-003, NFR-PF-07, NFR-LG-06
@pytest.mark.django_db(transaction=True)
def test_it_ai_init_099_ten_parallel_checkouts_never_oversell(f, token_for, run_parallel):
    """IT-AI-INIT-099 / COV-083：10並列の注文確定でも引当合計が在庫数量を超えない。"""
    unit = f.sellable(price=1000, quantity=5)
    tokens = []
    for index in range(10):
        user = f.user(email=f"race-ten{index}@example.test")
        f.fill_cart(user, (unit, 1))
        tokens.append(token_for(user))

    def checkout(token: str):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        return client.post("/api/checkout", SHIPPING, format="json")

    try:
        results = run_parallel(*[(lambda token=token: checkout(token)) for token in tokens])

        created = [response for response in results if response.status_code == 201]
        rejected = [response for response in results if response.status_code != 201]
        assert len(created) <= 5
        assert len(created) == PurchaseOrder.objects.count()
        for response in rejected:
            assert response.status_code == 409
            body = response.json()
            assert (body.get("error") or body)["code"] == "INSUFFICIENT_STOCK"
        unit.refresh_from_db()
        assert unit.quantity == 5 - len(created)
        assert unit.quantity >= 0
    finally:
        PurchaseOrder.objects.all().delete()
        Cart.objects.all().delete()


# trace: FR-030
def test_it_ai_init_100_double_submit_creates_single_order(api_as, buyer, f, err):
    """IT-AI-INIT-100 / COV-084：同一カートの二重送信で注文は1件だけ作成される（CMN-23）。"""
    unit = f.sellable(price=1000, quantity=10)
    client = api_as(buyer)
    add_line(client, unit, 1)

    first = client.post("/api/checkout", shipping(), format="json")
    second = client.post("/api/checkout", shipping(), format="json")

    assert first.status_code == 201
    assert second.status_code == 409
    assert err.code(second) == "CART_EMPTY"
    assert PurchaseOrder.objects.filter(user=buyer).count() == 1
    unit.refresh_from_db()
    assert unit.quantity == 9


# trace: FR-030
def test_it_ai_init_101_checkout_error_priority(api_as, buyer, other_buyer, f, err):
    """IT-AI-INIT-101 / COV-089：非公開→クーポン→在庫の順に先に該当したエラーのみを返す。"""
    hidden_unit = f.sellable(price=1000, quantity=10)
    short_unit = f.sellable(price=1000, quantity=10)
    f.coupon(code="PRIORITY01", discount_value=100, min_spend=100000)
    client = api_as(buyer)
    add_line(client, hidden_unit, 1)
    add_line(client, short_unit, 2)
    f.coupon(code="APPLIED02", discount_value=100)
    client.post("/api/cart/apply-coupon", {"code": "APPLIED02"}, format="json")
    Item.objects.filter(pk=hidden_unit.item_id).update(is_public=False)
    StockUnit.objects.filter(pk=short_unit.pk).update(quantity=0)

    first = client.post("/api/checkout", shipping(), format="json")

    assert first.status_code == 409
    assert err.code(first) == "ITEM_NOT_AVAILABLE"

    coupon_client = api_as(other_buyer)
    coupon_unit = f.sellable(price=1000, quantity=10)
    add_line(coupon_client, coupon_unit, 5)
    coupon_client.post("/api/cart/apply-coupon", {"code": "PRIORITY01"}, format="json")
    f.coupon(code="MINSPEND02", discount_value=100, min_spend=100000)
    Cart.objects.filter(user=other_buyer).update(
        coupon=f.coupon(code="LATEMIN01", discount_value=100, min_spend=100000)
    )
    StockUnit.objects.filter(pk=coupon_unit.pk).update(quantity=1)

    second = coupon_client.post("/api/checkout", shipping(), format="json")

    assert second.status_code == 409
    assert err.code(second) == "COUPON_MIN_SPEND_NOT_MET"
    coupon_unit.refresh_from_db()
    assert coupon_unit.quantity == 1


# trace: FR-030, FR-OUT-10
def test_it_ai_init_102_checkout_requires_buyer(api, api_as, admin_user, err):
    """IT-AI-INIT-102 / COV-087：未ログインは認証エラー、管理者は権限エラーとする。"""
    anonymous = api.post("/api/checkout", SHIPPING, format="json")
    administrator = api_as(admin_user).post("/api/checkout", SHIPPING, format="json")

    assert anonymous.status_code == 401
    assert err.code(anonymous) == "AUTHENTICATION_REQUIRED"
    assert administrator.status_code == 403
    assert err.code(administrator) == "PERMISSION_DENIED"
    assert not PurchaseOrder.objects.exists()


# trace: FR-030, ADDR-010, NFR-US-09
def test_it_ai_init_103_screen_checkout_confirms_before_creating_order(screen_as, buyer, f):
    """IT-AI-INIT-103 / COV-088：画面の注文手続きは確認を経た送信でのみ注文を作成する。"""
    item = f.item(name="画面確定商品")
    unit = f.stock_unit(item, price=4000, quantity=10)
    client = screen_as(buyer)
    client.post("/cart/lines/add/", {"item_id": item.pk, "stock_unit_id": unit.pk, "quantity": 1})

    form_screen = client.get("/checkout/")
    form_body = form_screen.content.decode()

    assert form_screen.status_code == 200
    # 確認ダイアログを経ずに注文は作成されない（取消時は要求が送信されない）。
    assert "data-confirm" in form_body
    assert "4,950円" in form_body
    assert not PurchaseOrder.objects.filter(user=buyer).exists()

    invalid = client.post("/checkout/", {**SHIPPING, "postal_code": "12345"})
    invalid_body = invalid.content.decode()

    assert invalid.status_code == 400
    assert "field-errors" in invalid_body
    assert "結合 受取人" in invalid_body  # 入力値を保持して再表示する
    assert not PurchaseOrder.objects.filter(user=buyer).exists()

    accepted = client.post("/checkout/", SHIPPING)

    assert accepted.status_code == 302
    order = PurchaseOrder.objects.get(user=buyer)
    assert accepted["Location"] == f"/orders/{order.pk}/complete/"
    complete = client.get(accepted["Location"])
    complete_body = complete.content.decode()
    assert order.order_number in complete_body
    assert "4,950円" in complete_body
    unit.refresh_from_db()
    assert unit.quantity == 9
