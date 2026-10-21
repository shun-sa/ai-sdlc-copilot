# trace: FR-020, FR-021, FR-022, FR-023, FR-026, FR-OUT-10
# trace: ADDR-003, ADDR-008, ADDR-010, ADDR-011
"""カート操作と注文金額計算の結合試験（IT-AI-INIT-046〜068、IT-AI-GAP-020〜021）。

検証対象の連携は API → Service → ORM → PostgreSQL、注文金額計算 → カートService → DB、
トランザクション・同時実行制御 → PostgreSQL、画面 → Service → DB。

期待結果は FR-020〜FR-023・FR-026 の処理内容・例外、提供済みAPI契約 6.2/6.3（業務エラーの
エラーコードと context）、CMN-14/CMN-16/CMN-17/CMN-18/CMN-19/CMN-20/CMN-21/CMN-30/CMN-31、
ST-CART-01、SCR-002-OP01・UI-19（失敗時は本画面に留まり入力値を保持する）、
ADDR-003（在庫判定は行ロック後に再判定）から導出する。

末尾の IT-AI-GAP-020〜021 は origin=AI_GENERATED / generation_stage=GAP_FILL の観点追補で、
固定済みの AI INITIAL Case（IT-AI-INIT-046〜068）は変更していない。
"""

from __future__ import annotations

import re

import pytest
from rest_framework.test import APIClient

from carts.models import CART_CONVERTED, CART_OPEN, Cart, CartLine
from catalog.models import StockUnit

pytestmark = pytest.mark.django_db


# trace: FR-021
def test_it_ai_init_046_add_line_does_not_reserve_stock(api_as, buyer, f):
    """IT-AI-INIT-046 / COV-047：カート明細追加は明細を作成し、在庫数量は変化しない。"""
    unit = f.sellable(price=1000, quantity=10)
    client = api_as(buyer)

    response = client.post("/api/cart/lines", {"stock_unit_id": unit.pk, "quantity": 2}, format="json")

    assert response.status_code == 200
    body = response.json()
    assert len(body["lines"]) == 1
    line = body["lines"][0]
    assert line["stock_unit_id"] == unit.pk
    assert line["quantity"] == 2
    assert line["unit_price"] == 1000
    assert line["line_amount"] == 2000
    assert body["total_quantity"] == 2
    assert body["coupon"] is None
    assert body["amounts"]["subtotal"] == 2000
    assert CartLine.objects.filter(cart__user=buyer).count() == 1
    unit.refresh_from_db()
    assert unit.quantity == 10


# trace: FR-021
def test_it_ai_init_047_adding_same_stock_unit_sums_quantity(api_as, buyer, f):
    """IT-AI-INIT-047 / COV-048：同一在庫単位の追加は数量を合算し、合計10個まで受け付ける。"""
    unit = f.sellable(price=1000, quantity=10)
    client = api_as(buyer)

    client.post("/api/cart/lines", {"stock_unit_id": unit.pk, "quantity": 8}, format="json")
    response = client.post("/api/cart/lines", {"stock_unit_id": unit.pk, "quantity": 2}, format="json")

    assert response.status_code == 200
    body = response.json()
    assert len(body["lines"]) == 1
    assert body["lines"][0]["quantity"] == 10
    assert body["amounts"]["subtotal"] == 10000
    assert CartLine.objects.filter(cart__user=buyer).count() == 1


# trace: FR-021, ADDR-011
def test_it_ai_init_048_add_line_rejects_combined_quantity_over_limit(api_as, buyer, f, err):
    """IT-AI-INIT-048 / COV-049：合算11個となる追加は数量上限超過とし context を返す。"""
    unit = f.sellable(price=1000, quantity=20)
    client = api_as(buyer)
    client.post("/api/cart/lines", {"stock_unit_id": unit.pk, "quantity": 8}, format="json")

    response = client.post("/api/cart/lines", {"stock_unit_id": unit.pk, "quantity": 3}, format="json")

    assert response.status_code == 409
    assert err.code(response) == "QUANTITY_LIMIT_EXCEEDED"
    assert err.context(response) == {
        "stock_unit_id": unit.pk,
        "limit": 10,
        "current_quantity": 8,
        "requested_quantity": 11,
    }
    assert CartLine.objects.get(cart__user=buyer).quantity == 8


# trace: FR-021
def test_it_ai_init_049_add_line_rejects_quantity_over_limit(api_as, buyer, f, err):
    """IT-AI-INIT-049 / COV-049：新規追加の数量11は数量上限超過とし明細を作成しない。"""
    unit = f.sellable(price=1000, quantity=20)

    response = api_as(buyer).post(
        "/api/cart/lines", {"stock_unit_id": unit.pk, "quantity": 11}, format="json"
    )

    assert response.status_code == 409
    assert err.code(response) == "QUANTITY_LIMIT_EXCEEDED"
    assert err.context(response)["requested_quantity"] == 11
    assert not CartLine.objects.filter(cart__user=buyer).exists()


# trace: FR-022, FR-026
def test_it_ai_init_050_change_quantity_recalculates_amounts(api_as, buyer, f):
    """IT-AI-INIT-050 / COV-050：数量変更は金額内訳を再計算する。"""
    unit = f.sellable(price=1000, quantity=10)
    client = api_as(buyer)
    line_id = client.post(
        "/api/cart/lines", {"stock_unit_id": unit.pk, "quantity": 2}, format="json"
    ).json()["lines"][0]["cart_line_id"]

    response = client.patch(f"/api/cart/lines/{line_id}", {"quantity": 10}, format="json")

    assert response.status_code == 200
    body = response.json()
    assert body["lines"][0]["quantity"] == 10
    assert body["amounts"] == {
        "subtotal": 10000,
        "discount_amount": 0,
        "discounted_subtotal": 10000,
        "shipping_fee": 0,
        "tax_amount": 1000,
        "total": 11000,
    }


# trace: FR-022
def test_it_ai_init_051_change_quantity_rejects_over_limit(api_as, buyer, f, err):
    """IT-AI-INIT-051 / COV-049：10→11 の数量変更は数量上限超過とし数量は変わらない。"""
    unit = f.sellable(price=1000, quantity=20)
    client = api_as(buyer)
    line_id = client.post(
        "/api/cart/lines", {"stock_unit_id": unit.pk, "quantity": 10}, format="json"
    ).json()["lines"][0]["cart_line_id"]

    response = client.patch(f"/api/cart/lines/{line_id}", {"quantity": 11}, format="json")

    assert response.status_code == 409
    assert err.code(response) == "QUANTITY_LIMIT_EXCEEDED"
    assert err.context(response)["limit"] == 10
    assert CartLine.objects.get(pk=line_id).quantity == 10


# trace: FR-021
def test_it_ai_init_052_quantity_limit_is_counted_per_stock_unit(api_as, buyer, f):
    """IT-AI-INIT-052 / COV-048：数量上限は在庫単位ごとに数える。"""
    item = f.item(name="複数規格商品")
    first = f.stock_unit(item, sku="SKU-LIMIT-A", price=1000, quantity=10)
    second = f.stock_unit(item, sku="SKU-LIMIT-B", price=1000, quantity=10)
    client = api_as(buyer)

    client.post("/api/cart/lines", {"stock_unit_id": first.pk, "quantity": 10}, format="json")
    response = client.post("/api/cart/lines", {"stock_unit_id": second.pk, "quantity": 10}, format="json")

    assert response.status_code == 200
    body = response.json()
    assert len(body["lines"]) == 2
    assert sorted(line["quantity"] for line in body["lines"]) == [10, 10]
    assert body["total_quantity"] == 20


# trace: FR-021
def test_it_ai_init_053_add_line_accepts_quantity_equal_to_stock(api_as, buyer, f):
    """IT-AI-INIT-053 / COV-051：合算数量が在庫数量と一致する追加は受け付ける。"""
    unit = f.sellable(price=1000, quantity=5)
    client = api_as(buyer)
    client.post("/api/cart/lines", {"stock_unit_id": unit.pk, "quantity": 3}, format="json")

    response = client.post("/api/cart/lines", {"stock_unit_id": unit.pk, "quantity": 2}, format="json")

    assert response.status_code == 200
    assert response.json()["lines"][0]["quantity"] == 5
    unit.refresh_from_db()
    assert unit.quantity == 5


# trace: FR-021, FR-022
def test_it_ai_init_054_insufficient_stock_is_rejected_with_shortages(api_as, buyer, f, err):
    """IT-AI-INIT-054 / COV-051：在庫数量を超える追加・変更は在庫不足とし context.shortages を返す。"""
    unit = f.sellable(price=1000, quantity=3)
    client = api_as(buyer)

    add = client.post("/api/cart/lines", {"stock_unit_id": unit.pk, "quantity": 4}, format="json")

    assert add.status_code == 409
    assert err.code(add) == "INSUFFICIENT_STOCK"
    assert err.context(add)["shortages"] == [
        {
            "stock_unit_id": unit.pk,
            "sku": unit.sku,
            "requested_quantity": 4,
            "available_quantity": 3,
        }
    ]
    assert not CartLine.objects.filter(cart__user=buyer).exists()

    plenty = f.sellable(price=1000, quantity=10)
    line_id = client.post(
        "/api/cart/lines", {"stock_unit_id": plenty.pk, "quantity": 5}, format="json"
    ).json()["lines"][0]["cart_line_id"]
    StockUnit.objects.filter(pk=plenty.pk).update(quantity=3)

    change = client.patch(f"/api/cart/lines/{line_id}", {"quantity": 4}, format="json")

    assert change.status_code == 409
    assert err.code(change) == "INSUFFICIENT_STOCK"
    assert err.context(change)["shortages"] == [
        {
            "stock_unit_id": plenty.pk,
            "sku": plenty.sku,
            "requested_quantity": 4,
            "available_quantity": 3,
        }
    ]
    assert CartLine.objects.get(pk=line_id).quantity == 5


# trace: FR-021
def test_it_ai_init_055_add_line_rejects_sold_out_stock_unit(api_as, buyer, f, err):
    """IT-AI-INIT-055 / COV-051：在庫数量0の在庫単位の追加は在庫不足とする。"""
    unit = f.sellable(price=1000, quantity=0)

    response = api_as(buyer).post(
        "/api/cart/lines", {"stock_unit_id": unit.pk, "quantity": 1}, format="json"
    )

    assert response.status_code == 409
    assert err.code(response) == "INSUFFICIENT_STOCK"
    assert err.context(response)["shortages"][0]["available_quantity"] == 0
    assert not CartLine.objects.filter(cart__user=buyer).exists()


# trace: FR-021, FR-022
def test_it_ai_init_056_invalid_quantity_is_detected_before_target(api_as, buyer, err):
    """IT-AI-INIT-056 / COV-052：数量の形式不正は対象の存在判定より先に入力エラーとする（CMN-14）。"""
    client = api_as(buyer)

    for quantity in (0, -1, "abc"):
        response = client.post(
            "/api/cart/lines", {"stock_unit_id": 999999, "quantity": quantity}, format="json"
        )

        assert response.status_code == 400, quantity
        assert err.code(response) == "VALIDATION_ERROR"
        assert "quantity" in err.fields(response)


# trace: FR-021
def test_it_ai_init_057_add_line_rejects_unknown_or_hidden_stock_unit(api_as, buyer, f, err):
    """IT-AI-INIT-057 / COV-052：存在しない・非公開商品の在庫単位は対象なしとする。"""
    hidden = f.item(name="非公開カート商品", is_public=False)
    hidden_unit = f.stock_unit(hidden, price=1000, quantity=5)
    client = api_as(buyer)

    responses = [
        client.post("/api/cart/lines", {"stock_unit_id": 999999, "quantity": 1}, format="json"),
        client.post("/api/cart/lines", {"stock_unit_id": hidden_unit.pk, "quantity": 1}, format="json"),
    ]

    for response in responses:
        assert response.status_code == 404
        assert err.code(response) == "NOT_FOUND"
    assert not CartLine.objects.filter(cart__user=buyer).exists()


# trace: FR-022, FR-023
def test_it_ai_init_058_other_or_converted_cart_lines_are_not_found(
    api_as, buyer, other_buyer, f, err
):
    """IT-AI-INIT-058 / COV-052：他購入者・存在しない・注文済カートの明細は対象なしとする（ST-CART-02）。"""
    unit = f.sellable(price=1000, quantity=10)
    other_line = f.cart_line(f.open_cart(other_buyer), unit, quantity=1)
    converted_cart = f.open_cart(buyer)
    converted_line = f.cart_line(converted_cart, unit, quantity=1)
    converted_cart.status = CART_CONVERTED
    converted_cart.save(update_fields=["status"])
    client = api_as(buyer)

    targets = [other_line.pk, 999999, converted_line.pk]
    for target in targets:
        patched = client.patch(f"/api/cart/lines/{target}", {"quantity": 2}, format="json")
        deleted = client.delete(f"/api/cart/lines/{target}")

        assert patched.status_code == 404, target
        assert err.code(patched) == "NOT_FOUND"
        assert deleted.status_code == 404, target
        assert err.code(deleted) == "NOT_FOUND"

    assert CartLine.objects.get(pk=other_line.pk).quantity == 1
    assert CartLine.objects.filter(pk=converted_line.pk).exists()


# trace: FR-023, FR-026
def test_it_ai_init_059_delete_line_recalculates_amounts(api_as, buyer, f):
    """IT-AI-INIT-059 / COV-053：明細削除は金額を再計算し、在庫数量は変えない。"""
    first = f.sellable(price=1000, quantity=10)
    second = f.sellable(price=2000, quantity=10)
    client = api_as(buyer)
    client.post("/api/cart/lines", {"stock_unit_id": first.pk, "quantity": 1}, format="json")
    body = client.post(
        "/api/cart/lines", {"stock_unit_id": second.pk, "quantity": 1}, format="json"
    ).json()
    target = next(line for line in body["lines"] if line["stock_unit_id"] == first.pk)

    response = client.delete(f"/api/cart/lines/{target['cart_line_id']}")

    assert response.status_code == 200
    remaining = response.json()
    assert [line["stock_unit_id"] for line in remaining["lines"]] == [second.pk]
    assert remaining["amounts"]["subtotal"] == 2000
    first.refresh_from_db()
    second.refresh_from_db()
    assert (first.quantity, second.quantity) == (10, 10)


# trace: FR-023, FR-026
def test_it_ai_init_060_deleting_all_lines_keeps_coupon_and_zero_amounts(api_as, buyer, f):
    """IT-AI-INIT-060 / COV-053：全明細を削除してもクーポン適用は維持し、金額はすべて0円となる。"""
    unit = f.sellable(price=6000, quantity=5)
    coupon = f.coupon(code="KEEPCPN", discount_value=1000)
    client = api_as(buyer)
    client.post("/api/cart/lines", {"stock_unit_id": unit.pk, "quantity": 1}, format="json")
    client.post("/api/cart/apply-coupon", {"code": coupon.code}, format="json")
    line_id = client.get("/api/cart").json()["lines"][0]["cart_line_id"]

    response = client.delete(f"/api/cart/lines/{line_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["lines"] == []
    assert body["coupon"] is not None
    assert body["coupon"]["code"] == "KEEPCPN"
    assert body["coupon"]["is_applicable"] is False
    assert body["amounts"] == {
        "subtotal": 0,
        "discount_amount": 0,
        "discounted_subtotal": 0,
        "shipping_fee": 0,
        "tax_amount": 0,
        "total": 0,
    }


# trace: FR-026
def test_it_ai_init_061_amounts_below_free_shipping_threshold(api_as, buyer, f):
    """IT-AI-INIT-061 / COV-054：小計4,999円は送料500円・消費税549円・合計6,048円となる。"""
    unit = f.sellable(price=4999, quantity=5)
    client = api_as(buyer)
    client.post("/api/cart/lines", {"stock_unit_id": unit.pk, "quantity": 1}, format="json")

    response = client.get("/api/cart")

    assert response.status_code == 200
    assert response.json()["amounts"] == {
        "subtotal": 4999,
        "discount_amount": 0,
        "discounted_subtotal": 4999,
        "shipping_fee": 500,
        "tax_amount": 549,
        "total": 6048,
    }


# trace: FR-026
def test_it_ai_init_062_amounts_at_free_shipping_threshold(api_as, buyer, f):
    """IT-AI-INIT-062 / COV-054：小計5,000円は送料0円・消費税500円・合計5,500円となる。"""
    unit = f.sellable(price=5000, quantity=5)
    client = api_as(buyer)
    client.post("/api/cart/lines", {"stock_unit_id": unit.pk, "quantity": 1}, format="json")

    response = client.get("/api/cart")

    assert response.json()["amounts"] == {
        "subtotal": 5000,
        "discount_amount": 0,
        "discounted_subtotal": 5000,
        "shipping_fee": 0,
        "tax_amount": 500,
        "total": 5500,
    }


# trace: FR-020
def test_it_ai_init_063_cart_uses_current_price(api_as, buyer, f):
    """IT-AI-INIT-063 / COV-055：カート照会の単価・金額は照会時点の税抜価格で算出する。"""
    unit = f.sellable(price=1000, quantity=10)
    client = api_as(buyer)
    client.post("/api/cart/lines", {"stock_unit_id": unit.pk, "quantity": 2}, format="json")

    StockUnit.objects.filter(pk=unit.pk).update(price=1500)
    response = client.get("/api/cart")

    line = response.json()["lines"][0]
    assert line["unit_price"] == 1500
    assert line["line_amount"] == 3000
    assert response.json()["amounts"]["subtotal"] == 3000


# trace: FR-020
def test_it_ai_init_064_cart_is_created_once_for_buyer(api_as, buyer):
    """IT-AI-INIT-064 / COV-055：利用中カートがない購入者の照会は空カートを1件だけ作成する（ST-CART-01）。"""
    client = api_as(buyer)

    first = client.get("/api/cart")
    second = client.get("/api/cart")

    assert first.status_code == 200 and second.status_code == 200
    body = first.json()
    assert body["lines"] == []
    assert body["coupon"] is None
    assert body["total_quantity"] == 0
    assert body["amounts"]["total"] == 0
    assert second.json()["cart_id"] == body["cart_id"]
    assert Cart.objects.filter(user=buyer, status=CART_OPEN).count() == 1


# trace: FR-020, FR-021, FR-022, FR-023, FR-OUT-10
def test_it_ai_init_065_cart_requires_buyer_role(api, api_as, admin_user, f, err):
    """IT-AI-INIT-065 / COV-056：未ログインは認証エラーを入力判定より先に返し、管理者は権限エラーとする。"""
    unit = f.sellable(price=1000, quantity=5)
    admin_client = api_as(admin_user)

    anonymous = [
        api.get("/api/cart"),
        api.post("/api/cart/lines", {"stock_unit_id": "abc", "quantity": 0}, format="json"),
    ]
    for response in anonymous:
        assert response.status_code == 401
        assert err.code(response) == "AUTHENTICATION_REQUIRED"

    for response in (
        admin_client.get("/api/cart"),
        admin_client.post("/api/cart/lines", {"stock_unit_id": unit.pk, "quantity": 1}, format="json"),
    ):
        assert response.status_code == 403
        assert err.code(response) == "PERMISSION_DENIED"
    assert not CartLine.objects.exists()


# trace: FR-021, ADDR-003
@pytest.mark.django_db(transaction=True)
def test_it_ai_init_066_concurrent_add_keeps_quantity_limit(f, token_for, run_parallel):
    """IT-AI-INIT-066 / COV-057：同一在庫単位の同時追加でも合算数量は10個を超えない（CMN-19/CMN-20）。"""
    buyer = f.user(email="race-cart@example.test")
    unit = f.sellable(price=1000, quantity=50)
    f.fill_cart(buyer, (unit, 8))
    token = token_for(buyer)

    def add():
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        return client.post("/api/cart/lines", {"stock_unit_id": unit.pk, "quantity": 2}, format="json")

    try:
        results = run_parallel(add, add)

        statuses = sorted(response.status_code for response in results)
        assert statuses == [200, 409]
        failed = next(response for response in results if response.status_code == 409)
        body = failed.json()
        assert (body.get("error") or body)["code"] == "QUANTITY_LIMIT_EXCEEDED"
        assert CartLine.objects.get(cart__user=buyer).quantity == 10
    finally:
        CartLine.objects.filter(cart__user=buyer).delete()
        Cart.objects.filter(user=buyer).delete()
        unit.item.stock_units.all().delete()


# trace: FR-021
def test_it_ai_init_067_quantity_limit_precedes_insufficient_stock(api_as, buyer, f, err):
    """IT-AI-INIT-067 / COV-058：数量上限超過と在庫不足の双方に該当する場合は数量上限超過を返す。"""
    unit = f.sellable(price=1000, quantity=5)
    f.fill_cart(buyer, (unit, 8))

    response = api_as(buyer).post(
        "/api/cart/lines", {"stock_unit_id": unit.pk, "quantity": 3}, format="json"
    )

    assert response.status_code == 409
    assert err.code(response) == "QUANTITY_LIMIT_EXCEEDED"


# trace: FR-020, FR-021, ADDR-010
def test_it_ai_init_068_screen_cart_shows_message_and_amounts(screen_as, buyer, f):
    """IT-AI-INIT-068 / COV-059：画面はカート投入メッセージ・合計点数・金額内訳を表示する。"""
    item = f.item(name="画面カート商品")
    unit = f.stock_unit(item, variant_name="赤", price=4999, quantity=10)
    client = screen_as(buyer)

    added = client.post(
        "/cart/lines/add/", {"item_id": item.pk, "stock_unit_id": unit.pk, "quantity": 1}
    )
    assert added.status_code == 302
    detail = client.get(added["Location"])
    detail_body = detail.content.decode()
    assert "カートに追加しました" in detail_body
    assert "赤" in detail_body
    assert "カート（1点）" in detail_body

    cart_screen = client.get("/cart/")
    body = cart_screen.content.decode()

    assert cart_screen.status_code == 200
    assert "合計点数：1点" in body
    assert "5,498円" in body  # 税込単価（4,999×110÷100の切り捨て）
    assert "4,999円" in body  # 小計（税抜）
    assert "500円" in body  # 送料
    assert "549円" in body  # 消費税額
    assert "6,048円" in body  # 合計（税込）


# ----------------------------------------------------------------------
# AI GAP_FILL（origin=AI_GENERATED / generation_stage=GAP_FILL）
# SCR-002-OP01 の失敗時（本画面に留まる・入力値を保持する・カートを変更しない）を追補する。
# ----------------------------------------------------------------------

QUANTITY_FIELD_MESSAGE = "数量は1以上の整数で入力してください。"


# trace: FR-021, ADDR-010
def quantity_field_area(body: str) -> str:
    """数量欄の近傍（数量入力欄から送信ボタンまで）を取り出す（CMN-16 の表示位置の確認用）。"""
    start = body.index('id="quantity"')
    end = body.index("カートに入れる", start)
    return body[start:end]


# trace: FR-021, ADDR-010
def message_area(body: str) -> str:
    """メッセージ領域を取り出す（業務エラーの表示位置の確認用）。"""
    start = body.index('class="messages"')
    return body[start : body.index("</div>", start)]


# trace: FR-020, FR-021
def cart_state(user) -> list[tuple[int, int, int]]:
    """利用中カートの明細（明細ID・在庫単位ID・数量）を比較可能な形で取り出す。"""
    return sorted(
        CartLine.objects.filter(cart__user=user, cart__status=CART_OPEN).values_list(
            "pk", "stock_unit_id", "quantity"
        )
    )


# trace: FR-021, ADDR-010
def assert_stays_on_item_detail(response, item) -> str:
    """応答が SCR-002 の再表示であること（遷移していないこと）を確認し、本文を返す。"""
    assert "Location" not in response
    assert "buyer/item_detail.html" in [template.name for template in response.templates]
    body = response.content.decode()
    assert item.name in body
    assert f"商品コード：{item.item_code}" in body
    return body


# trace: FR-021, ADDR-010, ADDR-011
def test_it_ai_gap_020_screen_add_line_invalid_quantity_keeps_input_and_cart(screen_as, buyer, f):
    """IT-AI-GAP-020 / COV-059：数量の入力エラーは SCR-002 に留まり、数量欄の近傍に理由を表示し、
    入力値を保持し、カートを変更しない（SCR-002-OP01、CMN-16、CMN-17、UI-19、CMN-21）。"""
    item = f.item(name="追補カート商品")
    unit = f.stock_unit(item, variant_name="青", price=1000, quantity=10)
    other_unit = f.stock_unit(item, variant_name="緑", price=1000, quantity=10)
    client = screen_as(buyer)
    f.fill_cart(buyer, (unit, 2))
    before = cart_state(buyer)
    assert before and len(before) == 1

    for entered in ("0", "abc", ""):
        response = client.post(
            "/cart/lines/add/",
            {"item_id": item.pk, "stock_unit_id": other_unit.pk, "quantity": entered},
        )

        assert response.status_code == 400
        body = assert_stays_on_item_detail(response, item)
        # 理由は数量欄の近傍に表示する。
        assert QUANTITY_FIELD_MESSAGE in quantity_field_area(body)
        assert "field-errors" in quantity_field_area(body)
        # 入力した数量と選択した規格を保持して再表示する。
        assert re.search(rf'id="quantity"[^>]*value="{entered}"', body)
        assert re.search(
            rf'name="stock_unit_id" value="{other_unit.pk}"[^>]*checked', body, re.DOTALL
        )
        # カートは変更しない（明細の追加・数量変更が起きない）。
        assert cart_state(buyer) == before
        assert Cart.objects.filter(user=buyer, status=CART_OPEN).count() == 1

    other_unit.refresh_from_db()
    assert other_unit.quantity == 10  # 在庫数量も変えない


# trace: FR-021, ADDR-010, ADDR-011
def test_it_ai_gap_021_screen_add_line_business_error_keeps_input_and_cart(screen_as, buyer, f):
    """IT-AI-GAP-021 / COV-059：数量上限超過・在庫不足は SCR-002 に留まり、メッセージ領域に理由を
    表示し、入力値を保持し、カートを変更しない（SCR-002-OP01、MSG-05、CMN-17、UI-19、CMN-21）。"""
    item = f.item(name="追補カート商品2")
    limited = f.stock_unit(item, variant_name="上限", price=1000, quantity=20)
    scarce = f.stock_unit(item, variant_name="僅少", price=1000, quantity=3)
    client = screen_as(buyer)
    f.fill_cart(buyer, (limited, 10))
    before = cart_state(buyer)

    over_limit = client.post(
        "/cart/lines/add/", {"item_id": item.pk, "stock_unit_id": limited.pk, "quantity": "1"}
    )

    assert over_limit.status_code == 409
    body = assert_stays_on_item_detail(over_limit, item)
    assert "同じ規格は1注文につき10個までです（現在のカート内数量：10個）。" in message_area(body)
    assert re.search(r'id="quantity"[^>]*value="1"', body)
    assert re.search(rf'name="stock_unit_id" value="{limited.pk}"[^>]*checked', body, re.DOTALL)
    assert cart_state(buyer) == before

    short_stock = client.post(
        "/cart/lines/add/", {"item_id": item.pk, "stock_unit_id": scarce.pk, "quantity": "5"}
    )

    assert short_stock.status_code == 409
    short_body = assert_stays_on_item_detail(short_stock, item)
    assert "在庫が不足しています（現在の在庫数量：3個）。" in message_area(short_body)
    assert re.search(r'id="quantity"[^>]*value="5"', short_body)
    assert re.search(rf'name="stock_unit_id" value="{scarce.pk}"[^>]*checked', short_body, re.DOTALL)
    assert cart_state(buyer) == before
    assert Cart.objects.filter(user=buyer, status=CART_OPEN).count() == 1

    limited.refresh_from_db()
    scarce.refresh_from_db()
    assert (limited.quantity, scarce.quantity) == (20, 3)  # 在庫数量は変えない
