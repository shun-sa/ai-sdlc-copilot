# trace: FR-001, FR-002, FR-011, FR-012, FR-021, FR-024, FR-030, FR-031, FR-032, FR-033, FR-041, FR-042
# trace: FR-043, FR-044, ADDR-001, ADDR-002, ADDR-004, ADDR-008, ADDR-012
# ruff: noqa: E501
"""結合試験：一連の業務フロー（Web API・画面）と画面の二重送信。

IT-048〜IT-050（AI INITIAL）。期待結果は UC-001〜UC-011 の基本フロー、FR-001〜FR-044、CMN-22/23/26、
MSG-02、UI-05/15、ADDR-001・ADDR-002・ADDR-004（送信トークン DD-010/013）・ADDR-008・ADDR-012 から導出する。
定義直前の trace 注釈は1行で記載する必要があり（複数行に分割できない）、本ファイルだけ E501 を除外する。
"""

import re

import pytest

from tests.integration._helpers import ADDRESS, PASSWORD, add_item, api, body, form_fields, text

pytestmark = pytest.mark.django_db


# trace: FR-002, ADDR-002, ADDR-012
def _web_login(client, email):
    fields = form_fields(text(client.get("/login/")), "/login/")
    fields.update({"email": email, "password": PASSWORD})
    response = client.post("/login/", fields)
    assert response.status_code == 302, response.content
    return response


# trace: FR-001, FR-002, FR-011, FR-012, FR-021, FR-024, FR-030, FR-031, FR-032, FR-033, FR-041, FR-042, FR-043, FR-044, ADDR-001, ADDR-002, ADDR-004, ADDR-008
def test_it_048_api_full_business_flow(api_client, admin, catalog, make_coupon):
    """IT-048 Web API による全業務フロー（会員登録から配達完了・購入者の照会まで）。"""
    from catalog.models import StockUnit

    category = catalog.category("マグカップ")
    mug = catalog.product("Blue Mug", categories=(category,))
    mug_unit = catalog.stock_unit(mug, price=1200, stock=10, sku="BM-01")
    plate = catalog.product("Plate")
    plate_unit = catalog.stock_unit(plate, price=2000, stock=5, sku="PL-01")
    make_coupon("TENOFF", discount_type="percentage", discount_value=10)

    assert (
        api(
            api_client,
            "post",
            "/api/auth/register/",
            data={
                "email": "flow@example.test",
                "password": PASSWORD,
                "password_confirmation": PASSWORD,
                "name": "流れ 太郎",
            },
        ).status_code
        == 201
    )
    login = body(api(api_client, "post", "/api/auth/login/", data={"email": "flow@example.test", "password": PASSWORD}))
    token = f"Bearer {login['token']}"

    found = body(api(api_client, "get", f"/api/products/?keyword=mug&category_id={category.pk}", token))
    assert [i["product_id"] for i in found["items"]] == [mug.pk]
    detail = body(api(api_client, "get", f"/api/products/{mug.pk}/", token))
    unit_id = detail["stock_units"][0]["stock_unit_id"]
    assert unit_id == mug_unit.pk

    assert add_item(api_client, token, unit_id, 2).status_code == 200
    assert add_item(api_client, token, plate_unit.pk, 1).status_code == 200
    coupon = api(api_client, "post", "/api/cart/coupon/", token, {"coupon_code": "TENOFF"})
    assert coupon.status_code == 200
    cart = body(api(api_client, "get", "/api/cart/", token))
    assert cart["amounts"] == {
        "subtotal": 4400,
        "discount_amount": 440,
        "discounted_subtotal": 3960,
        "shipping_fee": 500,
        "tax_amount": 446,
        "total_amount": 4906,
    }
    assert cart["total_quantity"] == 3

    placed = api(api_client, "post", "/api/orders/", token, {"shipping_address": ADDRESS})
    assert placed.status_code == 201
    order = body(placed)
    assert order["amounts"] == cart["amounts"]
    assert order["coupon"]["coupon_code"] == "TENOFF"
    assert StockUnit.objects.get(pk=mug_unit.pk).stock_quantity == 8
    assert StockUnit.objects.get(pk=plate_unit.pk).stock_quantity == 4

    paid = api(api_client, "post", f"/api/orders/{order['order_id']}/payment/", token, {"mock_instruction": "approved"})
    assert paid.status_code == 200 and body(paid)["status"] == "paid"

    admin_login = body(api(api_client, "post", "/api/auth/login/", data={"email": admin.email, "password": PASSWORD}))
    admin_token = f"Bearer {admin_login['token']}"
    listed = body(api(api_client, "get", "/api/admin/orders/?buyer_email=flow@example&status=paid", admin_token))
    assert [i["order_number"] for i in listed["items"]] == [order["order_number"]]
    assert listed["items"][0]["total_amount"] == 4906 and listed["items"][0]["total_quantity"] == 3
    admin_detail = body(api(api_client, "get", f"/api/admin/orders/{order['order_id']}/", admin_token))
    assert admin_detail["buyer"]["email"] == "flow@example.test"
    assert [p["result"] for p in admin_detail["payments"]] == ["approved"]
    shipped = api(
        api_client, "post", f"/api/admin/orders/{order['order_id']}/ship/", admin_token, {"tracking_number": "FLOW-1"}
    )
    assert shipped.status_code == 200
    delivered = api(api_client, "post", f"/api/admin/orders/{order['order_id']}/deliver/", admin_token)
    assert delivered.status_code == 200

    history = body(api(api_client, "get", "/api/orders/", token))
    assert [(i["order_id"], i["status"]) for i in history["items"]] == [(order["order_id"], "delivered")]
    final = body(api(api_client, "get", f"/api/orders/{order['order_id']}/", token))
    assert final["status"] == "delivered" and final["tracking_number"] == "FLOW-1"
    assert [(h["from_status"], h["to_status"], h["actor_user_type"]) for h in final["status_history"]] == [
        (None, "accepted", "buyer"),
        ("accepted", "paid", "buyer"),
        ("paid", "shipped", "admin"),
        ("shipped", "delivered", "admin"),
    ]
    assert final["can_pay"] is False and final["can_cancel"] is False


# trace: FR-002, FR-012, FR-021, FR-030, FR-031, FR-033, FR-043, FR-044, ADDR-012, ADDR-004, ADDR-008
def test_it_049_web_full_business_flow(web, buyer, admin, catalog):
    """IT-049 画面による全業務フロー（購入者の購入・支払、管理者の出荷・配達完了）。"""
    from orders.models import Order, PaymentRecord

    product = catalog.product("土鍋")
    unit = catalog.stock_unit(product, price=3000, stock=5, variant_name="大")
    client = web()
    _web_login(client, buyer.email)

    fields = form_fields(text(client.get(f"/products/{product.pk}/")), "/cart/items/add/")
    fields.update({"stock_unit_id": str(unit.pk), "quantity": "2"})
    assert client.post("/cart/items/add/", fields).status_code == 302

    checkout = text(client.get("/checkout/"))
    fields = form_fields(checkout, "/checkout/")
    fields.update({**ADDRESS, "prefecture": "13"})
    done = client.post("/checkout/", fields)
    assert done.status_code == 302
    match = re.fullmatch(r"/orders/(\d+)/complete/", done["Location"])
    assert match
    order = Order.objects.get(pk=int(match.group(1)))
    complete = text(client.get(done["Location"]))
    assert order.order_number in complete and f"{order.total_amount:,}円" in complete
    assert "カート（0点）" in complete

    pay_path = f"/orders/{order.pk}/payment/"
    fields = form_fields(text(client.get(pay_path)), pay_path)
    fields["mock_instruction"] = "declined"
    declined = client.post(pay_path, fields)
    assert declined.status_code == 422
    assert "否認" in text(declined)
    order.refresh_from_db()
    assert order.status == "accepted"

    fields = form_fields(text(client.get(pay_path)), pay_path)
    fields["mock_instruction"] = "approved"
    approved = client.post(pay_path, fields)
    assert approved.status_code == 302 and approved["Location"] == f"/orders/{order.pk}/"
    assert "支払が完了しました。" in text(client.get(approved["Location"]))
    assert list(PaymentRecord.objects.filter(order=order).order_by("pk").values_list("result", flat=True)) == [
        "declined",
        "approved",
    ]

    admin_client = web()
    _web_login(admin_client, admin.email)
    path = f"/manage/orders/{order.pk}/"
    fields = form_fields(text(admin_client.get(path)), f"{path}ship/")
    assert admin_client.post(f"{path}ship/", fields).status_code == 302
    fields = form_fields(text(admin_client.get(path)), f"{path}deliver/")
    assert admin_client.post(f"{path}deliver/", fields).status_code == 302
    assert "配達完了を登録しました。" in text(admin_client.get(path))

    final = text(client.get(f"/orders/{order.pk}/"))
    for label in ("配達完了", "出荷済", "支払済", "注文受付"):
        assert label in final, label
    order.refresh_from_db()
    assert order.status == "delivered"


# trace: FR-030, FR-031, ADDR-004
def test_it_050_web_double_submit_place_and_pay(api_client, web, buyer, bearer, catalog):
    """IT-050 画面の二重送信（同じ送信トークンでの注文確定・支払）。"""
    from catalog.models import StockUnit
    from orders.models import Order, PaymentRecord

    unit = catalog.stock_unit(stock=5)
    assert add_item(api_client, bearer(buyer), unit.pk, 1).status_code == 200
    client = web()
    client.force_login(buyer, backend="accounts.backends.SessionUserBackend")

    fields = form_fields(text(client.get("/checkout/")), "/checkout/")
    fields.update(ADDRESS)
    first = client.post("/checkout/", fields)
    second = client.post("/checkout/", fields)
    assert first.status_code == 302 and first["Location"].endswith("/complete/")
    # 2回目（同じ送信トークン）は受付時点のデータで再判定し E-030-04（カートが空）：SCR-005 へ遷移し理由を表示
    assert second.status_code == 302 and second["Location"] == "/cart/"
    assert "カートに商品がありません。" in text(client.get(second["Location"]))
    assert Order.objects.filter(buyer=buyer).count() == 1
    assert StockUnit.objects.get(pk=unit.pk).stock_quantity == 4

    order = Order.objects.get(buyer=buyer)
    pay_path = f"/orders/{order.pk}/payment/"
    fields = form_fields(text(client.get(pay_path)), pay_path)
    fields["mock_instruction"] = "declined"
    one = client.post(pay_path, fields)
    two = client.post(pay_path, fields)
    assert one.status_code == 422 and two.status_code == 422
    assert "否認" in text(two)
    assert PaymentRecord.objects.filter(order=order).count() == 1
    order.refresh_from_db()
    assert order.status == "accepted"
