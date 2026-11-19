# trace: FR-020, FR-021, FR-022, FR-023, FR-024, FR-025, FR-026, ADDR-001, ADDR-004, ADDR-006, ADDR-011, ADDR-012
"""結合試験：カート（Web API／画面→業務処理→金額計算→DB）。

IT-016〜IT-022（AI INITIAL）。期待結果は FR-020〜FR-026、CMN-29〜CMN-34、MSG-07、UI-05/15/24〜26、
ADDR-001（項目キー・業務エラーの reason/values）・ADDR-004（カートのロック・一意制約）から導出する。
"""

from datetime import timedelta

import pytest

from tests.integration._helpers import api, body, error_of, form_fields, jst, text

pytestmark = pytest.mark.django_db


# trace: FR-020, ADDR-001, ADDR-004
def test_it_016_get_cart_creates_single_active_cart(api_client, buyer, bearer):
    """IT-016 カート照会で空の利用中カートを1件だけ作成（冪等）。"""
    from carts.models import Cart

    token = bearer(buyer)
    assert Cart.objects.filter(buyer=buyer).count() == 0
    first = api(api_client, "get", "/api/cart/", token)
    assert first.status_code == 200
    data = body(first)
    assert data["items"] == [] and data["coupon"] is None and data["total_quantity"] == 0
    assert data["amounts"] == {
        "subtotal": 0,
        "discount_amount": 0,
        "discounted_subtotal": 0,
        "shipping_fee": 0,
        "tax_amount": 0,
        "total_amount": 0,
    }
    second = api(api_client, "get", "/api/cart/", token)
    assert body(second) == data
    assert Cart.objects.filter(buyer=buyer, status="active").count() == 1
    assert Cart.objects.filter(buyer=buyer).count() == 1


# trace: FR-021, FR-026, ADDR-001, ADDR-004
def test_it_017_add_item_merge_limit_stock(api_client, buyer, bearer, catalog):
    """IT-017 カート明細追加の合算・数量上限・在庫不足・対象なしと DB 反映。"""
    from carts.models import CartItem
    from catalog.models import StockUnit

    a = catalog.stock_unit(price=1000, stock=20)
    b = catalog.stock_unit(price=500, stock=3)
    c = catalog.stock_unit(price=500, stock=0)
    e = catalog.stock_unit(price=500, stock=20)
    d = catalog.stock_unit(catalog.product(is_public=False), stock=10)
    token = bearer(buyer)

    def add(unit_id, quantity):
        return api(api_client, "post", "/api/cart/items/", token, {"stock_unit_id": unit_id, "quantity": quantity})

    r1 = add(a.pk, 8)
    assert r1.status_code == 200
    items = body(r1)["items"]
    assert [(i["stock_unit_id"], i["quantity"]) for i in items] == [(a.pk, 8)]
    assert StockUnit.objects.get(pk=a.pk).stock_quantity == 20

    r2 = add(a.pk, 2)
    assert r2.status_code == 200
    assert [(i["stock_unit_id"], i["quantity"]) for i in body(r2)["items"]] == [(a.pk, 10)]
    assert body(r2)["amounts"]["subtotal"] == 10000

    r3 = add(a.pk, 1)
    assert r3.status_code == 422
    err = error_of(r3)
    assert err["type"] == "business_error" and err["reason"] == "quantity_limit_exceeded"
    assert err["values"]["stock_unit_id"] == a.pk and err["values"]["max_quantity"] == 10
    assert err["values"]["current_quantity"] == 10 and err["values"]["resulting_quantity"] == 11

    r4 = add(e.pk, 11)
    assert r4.status_code == 422 and error_of(r4)["reason"] == "quantity_limit_exceeded"
    assert error_of(r4)["values"]["current_quantity"] == 0

    r5 = add(b.pk, 4)
    assert r5.status_code == 422 and error_of(r5)["reason"] == "insufficient_stock"
    assert error_of(r5)["values"]["stock_units"] == [
        {"stock_unit_id": b.pk, "sku": b.sku, "requested_quantity": 4, "stock_quantity": 3}
    ]
    r6 = add(c.pk, 1)
    assert r6.status_code == 422 and error_of(r6)["reason"] == "insufficient_stock"

    for target in (d.pk, 99999999):
        missing = add(target, 1)
        assert missing.status_code == 404 and error_of(missing)["type"] == "not_found"

    assert list(CartItem.objects.values_list("stock_unit_id", "quantity")) == [(a.pk, 10)]
    assert [StockUnit.objects.get(pk=u.pk).stock_quantity for u in (a, b, c, d, e)] == [20, 3, 0, 10, 20]


# trace: FR-022, FR-023, ADDR-001, ADDR-006
def test_it_018_change_delete_and_ownership(api_client, buyer, other_buyer, bearer, catalog):
    """IT-018 カート明細の数量変更・削除と他人・存在しない明細。"""
    from carts.models import CartItem

    x = catalog.stock_unit(price=1000, stock=20)
    y = catalog.stock_unit(price=300, stock=20)
    mine, theirs = bearer(buyer), bearer(other_buyer)
    api(api_client, "post", "/api/cart/items/", mine, {"stock_unit_id": x.pk, "quantity": 2})
    cart = body(api(api_client, "post", "/api/cart/items/", mine, {"stock_unit_id": y.pk, "quantity": 1}))
    other = body(api(api_client, "post", "/api/cart/items/", theirs, {"stock_unit_id": x.pk, "quantity": 1}))
    item_x = next(i["cart_item_id"] for i in cart["items"] if i["stock_unit_id"] == x.pk)
    item_y = next(i["cart_item_id"] for i in cart["items"] if i["stock_unit_id"] == y.pk)
    item_z = other["items"][0]["cart_item_id"]

    changed = api(api_client, "patch", f"/api/cart/items/{item_x}/", mine, {"quantity": 10})
    assert changed.status_code == 200
    data = body(changed)
    line = next(i for i in data["items"] if i["cart_item_id"] == item_x)
    assert line["quantity"] == 10 and line["line_amount"] == 10000
    assert data["amounts"]["subtotal"] == 10300

    deleted = api(api_client, "delete", f"/api/cart/items/{item_y}/", mine)
    assert deleted.status_code == 200
    assert [i["cart_item_id"] for i in body(deleted)["items"]] == [item_x]
    assert body(deleted)["amounts"]["subtotal"] == 10000

    for method, payload in (("patch", {"quantity": 1}), ("delete", None)):
        response = api(api_client, method, f"/api/cart/items/{item_z}/", mine, payload)
        assert response.status_code == 404 and error_of(response)["type"] == "not_found"
    assert CartItem.objects.get(pk=item_z).quantity == 1
    missing = api(api_client, "patch", "/api/cart/items/99999999/", mine, {"quantity": 1})
    assert missing.status_code == 404


# trace: FR-026, FR-020, FR-022, ADDR-001
def test_it_019_amounts_shipping_threshold_and_tax(api_client, buyer, bearer, catalog):
    """IT-019 カート金額内訳（送料しきい値・消費税）。"""
    p1 = catalog.stock_unit(price=4999, stock=5)
    p2 = catalog.stock_unit(price=1000, stock=10)
    token = bearer(buyer)
    item = body(api(api_client, "post", "/api/cart/items/", token, {"stock_unit_id": p1.pk, "quantity": 1}))["items"][0]
    amounts = body(api(api_client, "get", "/api/cart/", token))["amounts"]
    assert amounts == {
        "subtotal": 4999,
        "discount_amount": 0,
        "discounted_subtotal": 4999,
        "shipping_fee": 500,
        "tax_amount": 549,
        "total_amount": 6048,
    }

    api(api_client, "delete", f"/api/cart/items/{item['cart_item_id']}/", token)
    item2 = body(api(api_client, "post", "/api/cart/items/", token, {"stock_unit_id": p2.pk, "quantity": 4}))["items"][
        0
    ]
    api(api_client, "patch", f"/api/cart/items/{item2['cart_item_id']}/", token, {"quantity": 5})
    amounts = body(api(api_client, "get", "/api/cart/", token))["amounts"]
    assert amounts == {
        "subtotal": 5000,
        "discount_amount": 0,
        "discounted_subtotal": 5000,
        "shipping_fee": 0,
        "tax_amount": 500,
        "total_amount": 5500,
    }


# trace: FR-024, FR-025, FR-026, ADDR-001, ADDR-011
def test_it_020_coupon_apply_validity_recalc_remove(api_client, buyer, bearer, catalog, make_coupon, set_state):
    """IT-020 クーポン適用・解除と有効期間（秒単位）・最低購入金額・適用不可の再計算。"""
    start, end = jst(2027, 4, 1, 0, 0, 0), jst(2027, 4, 30, 23, 59, 59)
    make_coupon("SPRING-500", discount_value=500, minimum_purchase_amount=3000, valid_from=start, valid_to=end)
    u = catalog.stock_unit(price=1000, stock=20)
    v = catalog.stock_unit(price=999, stock=20)
    w = catalog.stock_unit(price=1, stock=20)
    session = {}

    def at(moment):
        # 固定した現在日時でログイン状態を発行し直す（Bearer の有効期限は発行時刻+24時間：CMN-09）
        set_state(fixed_now=moment)
        session["token"] = bearer(buyer)
        return session["token"]

    token = at(jst(2027, 4, 15, 12, 0, 0))

    def apply(code):
        return api(api_client, "post", "/api/cart/coupon/", session["token"], {"coupon_code": code})

    empty = apply("SPRING-500")
    assert empty.status_code == 422 and error_of(empty)["reason"] == "cart_empty"

    u_item = body(api(api_client, "post", "/api/cart/items/", token, {"stock_unit_id": u.pk, "quantity": 2}))["items"][
        0
    ]
    api(api_client, "post", "/api/cart/items/", token, {"stock_unit_id": v.pk, "quantity": 1})
    below = apply("SPRING-500")
    assert below.status_code == 422 and error_of(below)["reason"] == "below_minimum_purchase_amount"
    assert error_of(below)["values"]["minimum_purchase_amount"] == 3000
    assert error_of(below)["values"]["subtotal"] == 2999

    api(api_client, "post", "/api/cart/items/", token, {"stock_unit_id": w.pk, "quantity": 1})
    token = at(start - timedelta(seconds=1))
    early = apply("SPRING-500")
    assert early.status_code == 422 and error_of(early)["reason"] == "coupon_not_yet_valid"
    assert error_of(early)["values"]["valid_from"] == "2027-04-01T00:00:00+09:00"
    assert error_of(early)["values"]["valid_to"] == "2027-04-30T23:59:59+09:00"

    token = at(start)
    applied = apply("  spring-500 ")
    assert applied.status_code == 200
    data = body(applied)
    assert data["coupon"]["coupon_code"] == "SPRING-500" and data["coupon"]["is_applicable"] is True
    assert data["amounts"]["subtotal"] == 3000 and data["amounts"]["discount_amount"] == 500

    for code in ("SPRING-500", "NOPE-1"):
        again = apply(code)
        assert again.status_code == 422 and error_of(again)["reason"] == "coupon_already_applied"
    assert body(api(api_client, "get", "/api/cart/", token))["coupon"]["coupon_code"] == "SPRING-500"

    api(api_client, "patch", f"/api/cart/items/{u_item['cart_item_id']}/", token, {"quantity": 1})
    lowered = body(api(api_client, "get", "/api/cart/", token))
    assert lowered["coupon"]["coupon_code"] == "SPRING-500"
    assert lowered["coupon"]["is_applicable"] is False
    assert lowered["coupon"]["not_applicable_reason"] == "below_minimum_purchase_amount"
    assert lowered["amounts"]["discount_amount"] == 0

    api(api_client, "patch", f"/api/cart/items/{u_item['cart_item_id']}/", token, {"quantity": 2})
    restored = body(api(api_client, "get", "/api/cart/", token))
    assert restored["coupon"]["is_applicable"] is True and restored["amounts"]["discount_amount"] == 500

    token = at(end.replace(microsecond=900000))
    at_end = body(api(api_client, "get", "/api/cart/", token))
    assert at_end["amounts"]["discount_amount"] == 500 and at_end["coupon"]["is_applicable"] is True

    token = at(end + timedelta(seconds=1))
    after_end = body(api(api_client, "get", "/api/cart/", token))
    assert after_end["coupon"]["is_applicable"] is False
    assert after_end["coupon"]["not_applicable_reason"] == "expired"
    assert after_end["amounts"]["discount_amount"] == 0

    removed = api(api_client, "delete", "/api/cart/coupon/", token)
    assert removed.status_code == 200
    assert body(removed)["coupon"] is None and body(removed)["amounts"]["discount_amount"] == 0
    again = api(api_client, "delete", "/api/cart/coupon/", token)
    assert again.status_code == 200 and body(again)["coupon"] is None


# trace: FR-020, FR-021, FR-022, FR-023, FR-024, FR-025, ADDR-012, ADDR-004, ADDR-001
def test_it_021_web_cart_operations(web, buyer, catalog, make_coupon):
    """IT-021 画面のカート操作（カートに入れる→数量変更→クーポン適用・解除→削除）。"""
    from carts.models import CartItem

    make_coupon("WEB-500", discount_value=500)
    product = catalog.product("湯呑")
    unit = catalog.stock_unit(product, price=1500, stock=20, variant_name="藍")
    client = web()
    client.force_login(buyer, backend="accounts.backends.SessionUserBackend")

    detail = text(client.get(f"/products/{product.pk}/"))
    fields = form_fields(detail, "/cart/items/add/")
    fields.update({"stock_unit_id": str(unit.pk), "quantity": "2"})
    added = client.post("/cart/items/add/", fields)
    assert added.status_code == 302 and added["Location"] == f"/products/{product.pk}/"
    after_add = text(client.get(f"/products/{product.pk}/"))
    assert "カートに追加しました" in after_add and "カート（2点）" in after_add

    item = CartItem.objects.get(cart__buyer=buyer)
    cart_page = text(client.get("/cart/"))
    fields = form_fields(cart_page, f"/cart/items/{item.pk}/quantity/")
    fields["quantity"] = "4"
    changed = client.post(f"/cart/items/{item.pk}/quantity/", fields)
    assert changed.status_code == 302 and changed["Location"] == "/cart/"
    cart_page = text(client.get("/cart/"))
    assert "数量を変更しました。" in cart_page
    assert "1,650円（税込）" in cart_page and "6,000円" in cart_page
    assert "カート（4点）" in cart_page

    fields = form_fields(cart_page, "/cart/coupon/apply/")
    fields["coupon_code"] = "web-500"
    applied = client.post("/cart/coupon/apply/", fields)
    assert applied.status_code == 302
    cart_page = text(client.get("/cart/"))
    assert "クーポンを適用しました。" in cart_page and "WEB-500" in cart_page
    assert "5,500円" in cart_page  # 割引後小計 6,000−500

    fields = form_fields(cart_page, "/cart/coupon/remove/")
    removed = client.post("/cart/coupon/remove/", fields)
    assert removed.status_code == 302
    cart_page = text(client.get("/cart/"))
    assert "クーポンを解除しました。" in cart_page and "WEB-500" not in cart_page

    fields = form_fields(cart_page, f"/cart/items/{item.pk}/delete/")
    deleted = client.post(f"/cart/items/{item.pk}/delete/", fields)
    assert deleted.status_code == 302
    cart_page = text(client.get("/cart/"))
    assert "カートから削除しました。" in cart_page and "カートに商品がありません。" in cart_page
    assert CartItem.objects.filter(cart__buyer=buyer).count() == 0


# trace: FR-021, ADDR-012, ADDR-001
def test_it_022_same_rule_web_and_api(api_client, web, buyer, other_buyer, bearer, catalog):
    """IT-022 画面と Web API で同じ数量上限・在庫の判定。"""
    from carts.models import CartItem

    product = catalog.product()
    unit = catalog.stock_unit(product, stock=5)
    token = bearer(buyer)
    api_over = api(api_client, "post", "/api/cart/items/", token, {"stock_unit_id": unit.pk, "quantity": 11})
    api_short = api(api_client, "post", "/api/cart/items/", token, {"stock_unit_id": unit.pk, "quantity": 6})
    assert api_over.status_code == 422 and error_of(api_over)["reason"] == "quantity_limit_exceeded"
    assert api_short.status_code == 422 and error_of(api_short)["reason"] == "insufficient_stock"

    client = web()
    client.force_login(other_buyer, backend="accounts.backends.SessionUserBackend")
    for quantity, api_response in (("11", api_over), ("6", api_short)):
        fields = form_fields(text(client.get(f"/products/{product.pk}/")), "/cart/items/add/")
        fields.update({"stock_unit_id": str(unit.pk), "quantity": quantity})
        page = client.post("/cart/items/add/", fields)
        assert page.status_code == 422
        assert error_of(api_response)["message"] in text(page)
    assert CartItem.objects.count() == 0
