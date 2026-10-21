# trace: FR-001, FR-002, FR-003, FR-004, FR-010, FR-011, FR-012, FR-020, FR-021, FR-022
# trace: FR-023, FR-024, FR-025, FR-030, FR-031, FR-032, FR-033, FR-034, FR-040, FR-041
# trace: FR-042, FR-043, FR-044, FR-045, NFR-SC-03, NFR-SC-15, NFR-SC-24, ADDR-001, ADDR-002, ADDR-011
"""Web API（提供済みAPI契約 6.1）の応答の単体テスト。

期待結果は提供済みAPI契約 6.1（Method・Path・成功ステータス・利用できるロール）、
6.2（エラーコードとHTTPステータス）、各FRの出力項目、NFR-SC-03（未ログインは401、
権限なしは403、他の購入者のデータは404）から導出する。

DBは pytest-django が作成する使い捨てのテストDBだけを使用する。
"""

from __future__ import annotations

import pytest
from _helpers import (
    add_cart_line,
    make_collection,
    make_coupon,
    make_item,
    make_open_cart,
    make_stock_unit,
    make_user,
    shipping_input,
)
from accounts.models import ROLE_BUYER, User
from carts import services as cart_services
from carts.models import DISCOUNT_FIXED, DISCOUNT_PERCENTAGE
from orders import services as order_services

pytestmark = pytest.mark.django_db


# trace: FR-002
def auth(token: str) -> dict:
    """認証トークンを Authorization ヘッダーへ設定する（テスト補助）。"""
    return {"HTTP_AUTHORIZATION": f"Bearer {token}"}


# trace: FR-030
def create_order(user):
    """支払・キャンセルの対象となる注文を1件作成する（テスト補助）。"""
    unit = make_stock_unit(make_item(name="API商品"), price=3000, quantity=10)
    cart_services.add_line(user, {"stock_unit_id": unit.pk, "quantity": 2})
    return order_services.checkout(user, shipping_input()), unit


# trace: FR-024, FR-030
def create_order_with_coupon(user, *, code: str, discount_type: str, discount_value: int):
    """クーポンを適用した注文を1件作成する（テスト補助）。"""
    unit = make_stock_unit(make_item(name="クーポン対象商品"), price=5000, quantity=10)
    cart_services.add_line(user, {"stock_unit_id": unit.pk, "quantity": 1})
    coupon = make_coupon(code=code, discount_type=discount_type, discount_value=discount_value, min_spend=0)
    cart_services.apply_coupon(user, {"code": code})
    return order_services.checkout(user, shipping_input()), coupon


# trace: FR-001
def test_register_returns_201_with_user_payload(api_client):
    """FR-001：会員登録は201で利用者ID・メールアドレス・氏名・利用者区分・登録日時を返す。"""
    response = api_client.post(
        "/api/auth/register",
        {
            "email": "Api.User@Example.TEST",
            "password": "passw0rd",
            "password_confirmation": "passw0rd",
            "full_name": "API 太郎",
        },
        format="json",
    )

    assert response.status_code == 201
    assert set(response.data) == {"user_id", "email", "full_name", "role", "registered_at"}
    assert response.data["email"] == "api.user@example.test"
    assert response.data["role"] == "buyer"
    assert "password" not in response.data


# trace: NFR-SC-15
def test_register_ignores_role_given_in_request_body(api_client):
    """NFR-SC-15：会員登録の要求に利用者区分を含めても、購入者として登録する。"""
    response = api_client.post(
        "/api/auth/register",
        {
            "email": "mass.assign@example.test",
            "password": "passw0rd",
            "password_confirmation": "passw0rd",
            "full_name": "API 花子",
            "role": "admin",
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.data["role"] == "buyer"
    assert User.objects.get(email="mass.assign@example.test").role == ROLE_BUYER


# trace: FR-001
def test_register_returns_400_with_all_invalid_fields(api_client):
    """E-001-01：入力エラーは400で全項目の項目名と理由を返す。"""
    response = api_client.post("/api/auth/register", {}, format="json")

    assert response.status_code == 400
    assert response.data["error"]["code"] == "VALIDATION_ERROR"
    assert len(response.data["error"]["details"]) >= 4
    assert all(set(detail) == {"field", "reason"} for detail in response.data["error"]["details"])
    assert all(detail["reason"] for detail in response.data["error"]["details"])


# trace: FR-001, ADDR-011
def test_error_response_uses_the_contract_error_envelope(api_client):
    """DEF-IT-001 再発防止：エラー応答は error 封筒で返し、平坦な本文としない。

    提供済みAPI契約 6.2：{"error": {"code", "message", "details": [{"field", "reason"}], "context"}}。
    """
    response = api_client.post("/api/auth/register", {}, format="json")

    assert response.status_code == 400
    assert set(response.data) == {"error"}
    assert set(response.data["error"]) == {"code", "message", "details", "context"}
    assert "code" not in response.data
    assert response.data["error"]["message"]
    assert response.data["error"]["context"] == {}


# trace: NFR-SC-03, ADDR-011
def test_error_response_without_details_uses_empty_details_and_context(api_client):
    """API契約 6.2・6.3：該当なしの details は空配列、context は空オブジェクトで返す。"""
    response = api_client.post("/api/auth/logout")

    assert response.status_code == 401
    assert set(response.data) == {"error"}
    assert response.data["error"]["code"] == "AUTHENTICATION_REQUIRED"
    assert response.data["error"]["details"] == []
    assert response.data["error"]["context"] == {}


# trace: FR-001
def test_register_returns_409_for_registered_email(api_client):
    """E-001-02：登録済みメールアドレスは409とする。"""
    make_user(email="dup@example.test")

    response = api_client.post(
        "/api/auth/register",
        {
            "email": "dup@example.test",
            "password": "passw0rd",
            "password_confirmation": "passw0rd",
            "full_name": "API 太郎",
        },
        format="json",
    )

    assert response.status_code == 409
    assert response.data["error"]["code"] == "EMAIL_ALREADY_REGISTERED"


# trace: FR-001
def test_register_rejects_non_object_body(api_client):
    """要求本文がオブジェクトでない場合も入力エラーとして扱う。"""
    response = api_client.post("/api/auth/register", [], format="json")

    assert response.status_code == 400


# trace: FR-002
def test_login_returns_token_and_user(api_client):
    """FR-002：ログインは200で token・expires_at・user を返す。"""
    make_user(email="login-api@example.test", password="passw0rd")

    response = api_client.post(
        "/api/auth/login", {"email": "login-api@example.test", "password": "passw0rd"}, format="json"
    )

    assert response.status_code == 200
    assert set(response.data) == {"token", "expires_at", "user"}
    assert set(response.data["user"]) == {"user_id", "email", "full_name", "role"}


# trace: FR-002
def test_login_returns_401_for_wrong_credentials(api_client):
    """E-002-02：資格情報の照合に失敗した場合は401 INVALID_CREDENTIALS とする。"""
    make_user(email="login-ng@example.test", password="passw0rd")

    response = api_client.post(
        "/api/auth/login", {"email": "login-ng@example.test", "password": "wrong123"}, format="json"
    )

    assert response.status_code == 401
    assert response.data["error"]["code"] == "INVALID_CREDENTIALS"


# trace: FR-002
def test_login_returns_400_for_missing_input(api_client):
    """E-002-01：未入力のみ400 VALIDATION_ERROR とする。"""
    response = api_client.post("/api/auth/login", {}, format="json")

    assert response.status_code == 400
    assert response.data["error"]["code"] == "VALIDATION_ERROR"


# trace: FR-003
def test_logout_returns_204_and_revokes_token(api_client, buyer, token_for):
    """FR-003：ログアウトは204とし、以後そのトークンは使えない。"""
    token = token_for(buyer)

    response = api_client.post("/api/auth/logout", **auth(token))
    after = api_client.get("/api/auth/me", **auth(token))

    assert response.status_code == 204
    assert after.status_code == 401
    assert after.data["error"]["code"] == "AUTHENTICATION_REQUIRED"


# trace: NFR-SC-03
def test_logout_requires_authentication(api_client):
    """認証情報がない要求は401とする。"""
    response = api_client.post("/api/auth/logout")

    assert response.status_code == 401
    assert response.data["error"]["code"] == "AUTHENTICATION_REQUIRED"


# trace: FR-004
def test_me_returns_logged_in_user(api_client, buyer, token_for):
    """FR-004：ログイン利用者情報を返す。"""
    response = api_client.get("/api/auth/me", **auth(token_for(buyer)))

    assert response.status_code == 200
    assert response.data["user_id"] == buyer.pk
    assert response.data["role"] == "buyer"


# trace: FR-004
def test_me_rejects_invalid_token(api_client):
    """無効なトークンは401とする。"""
    response = api_client.get("/api/auth/me", **auth("invalid-token"))

    assert response.status_code == 401


# trace: FR-010
def test_collections_are_returned_without_authentication(api_client):
    """FR-010：商品分類一覧は認証不要・ページングなしで全件を返す。"""
    root = make_collection(collection_code="api-root", name="ルート")
    make_collection(collection_code="api-child", name="子", parent=root)

    response = api_client.get("/api/collections")

    assert response.status_code == 200
    assert [item["collection_code"] for item in response.data] == ["api-root", "api-child"]
    assert set(response.data[0]) == {
        "collection_id",
        "collection_code",
        "name",
        "parent_collection_id",
        "depth",
        "sort_order",
    }


# trace: FR-011
def test_items_are_returned_in_paging_format(api_client):
    """FR-011：商品一覧検索はページング形式（20件/ページ）で返す。"""
    collection = make_collection(collection_code="api-col", name="分類")
    item = make_item(name="API商品", collections=[collection])
    make_stock_unit(item, price=1000, quantity=1)

    response = api_client.get("/api/items")

    assert response.status_code == 200
    assert response.data["page"] == 1
    assert response.data["page_size"] == 20
    assert response.data["total_count"] == 1
    assert response.data["total_pages"] == 1
    result = response.data["results"][0]
    assert result["min_price"] == 1000
    assert result["min_price_incl_tax"] == 1100
    assert result["in_stock"] is True
    assert result["collections"] == [{"collection_id": collection.pk, "name": "分類"}]


# trace: FR-011
def test_items_returns_400_for_invalid_sort(api_client):
    """E-011-01：並び順が4種類のいずれでもない場合は400とする。"""
    response = api_client.get("/api/items?sort=unknown")

    assert response.status_code == 400
    assert response.data["error"]["code"] == "VALIDATION_ERROR"


# trace: FR-012
def test_item_detail_returns_stock_units(api_client):
    """FR-012：商品詳細は在庫単位を SKU 昇順で返す（仕入先は含めない）。"""
    item = make_item(name="詳細商品", description="説明")
    make_stock_unit(item, sku="SKU-B", price=1000, quantity=0, variant_name="赤")
    make_stock_unit(item, sku="SKU-A", price=2000, quantity=3, variant_name="青")

    response = api_client.get(f"/api/items/{item.pk}")

    assert response.status_code == 200
    assert [unit["sku"] for unit in response.data["stock_units"]] == ["SKU-A", "SKU-B"]
    assert response.data["stock_units"][0]["price_incl_tax"] == 2200
    assert response.data["stock_units"][0]["in_stock"] is True
    assert response.data["stock_units"][1]["in_stock"] is False
    assert "supplier_id" not in response.data["stock_units"][0]


# trace: FR-012
def test_item_detail_returns_404_for_hidden_item(api_client):
    """E-012-01：非公開の商品は404とし、存在有無を明かさない。"""
    item = make_item(is_public=False)
    make_stock_unit(item)

    response = api_client.get(f"/api/items/{item.pk}")

    assert response.status_code == 404
    assert response.data["error"]["code"] == "NOT_FOUND"


# trace: FR-020
def test_cart_requires_buyer_role(api_client, admin_user, token_for):
    """FR-020：管理者が購入者専用APIを要求した場合は403とする。"""
    response = api_client.get("/api/cart", **auth(token_for(admin_user)))

    assert response.status_code == 403
    assert response.data["error"]["code"] == "PERMISSION_DENIED"


# trace: FR-020
def test_cart_returns_cart_payload(api_client, buyer, token_for):
    """FR-020：カート内容（明細・合計点数・クーポン・金額内訳）を返す。"""
    response = api_client.get("/api/cart", **auth(token_for(buyer)))

    assert response.status_code == 200
    assert set(response.data) == {"cart_id", "lines", "total_quantity", "coupon", "amounts"}
    assert response.data["coupon"] is None
    assert response.data["amounts"]["total"] == 0


# trace: FR-021
def test_add_cart_line_returns_updated_cart(api_client, buyer, token_for):
    """FR-021：明細追加は更新後のカート内容を返す。"""
    unit = make_stock_unit(make_item(name="カート商品"), price=1500, quantity=5)

    response = api_client.post(
        "/api/cart/lines", {"stock_unit_id": unit.pk, "quantity": 2}, format="json", **auth(token_for(buyer))
    )

    assert response.status_code == 200
    line = response.data["lines"][0]
    assert line["stock_unit_id"] == unit.pk
    assert line["unit_price"] == 1500
    assert line["line_amount"] == 3000
    assert line["stock_quantity"] == 5
    assert response.data["total_quantity"] == 2


# trace: FR-021
def test_add_cart_line_returns_409_for_insufficient_stock(api_client, buyer, token_for):
    """E-021-06：在庫不足は409と shortages を返す（API契約 6.3）。"""
    unit = make_stock_unit(make_item(), quantity=1, sku="SKU-API-SHORT")

    response = api_client.post(
        "/api/cart/lines", {"stock_unit_id": unit.pk, "quantity": 2}, format="json", **auth(token_for(buyer))
    )

    assert response.status_code == 409
    assert response.data["error"]["code"] == "INSUFFICIENT_STOCK"
    assert response.data["error"]["context"]["shortages"][0]["sku"] == "SKU-API-SHORT"


# trace: FR-022
def test_update_cart_line_changes_quantity(api_client, buyer, token_for):
    """FR-022：数量変更は更新後のカート内容を返す。"""
    unit = make_stock_unit(make_item(), quantity=10)
    line = cart_services.add_line(buyer, {"stock_unit_id": unit.pk, "quantity": 1})["lines"][0]

    response = api_client.patch(
        f"/api/cart/lines/{line.pk}", {"quantity": 3}, format="json", **auth(token_for(buyer))
    )

    assert response.status_code == 200
    assert response.data["lines"][0]["quantity"] == 3


# trace: FR-023
def test_delete_cart_line_removes_line(api_client, buyer, token_for):
    """FR-023：明細削除は更新後のカート内容を返す。"""
    unit = make_stock_unit(make_item(), quantity=10)
    line = cart_services.add_line(buyer, {"stock_unit_id": unit.pk, "quantity": 1})["lines"][0]

    response = api_client.delete(f"/api/cart/lines/{line.pk}", **auth(token_for(buyer)))

    assert response.status_code == 200
    assert response.data["lines"] == []


# trace: NFR-SC-03
def test_cart_line_of_other_buyer_is_not_found(api_client, buyer, token_for):
    """CMN-18：他の購入者のカート明細は404とする。"""
    other = make_user(email="other-api@example.test")
    unit = make_stock_unit(make_item(), quantity=10)
    line = cart_services.add_line(other, {"stock_unit_id": unit.pk, "quantity": 1})["lines"][0]

    response = api_client.delete(f"/api/cart/lines/{line.pk}", **auth(token_for(buyer)))

    assert response.status_code == 404


# trace: FR-024
def test_apply_coupon_returns_cart_with_coupon(api_client, buyer, token_for):
    """FR-024：クーポン適用後のカート内容（クーポンの適用可否を含む）を返す。"""
    make_coupon(code="API-1000", discount_value=1000, min_spend=0)
    unit = make_stock_unit(make_item(), price=6000, quantity=5)
    cart_services.add_line(buyer, {"stock_unit_id": unit.pk, "quantity": 1})

    response = api_client.post(
        "/api/cart/apply-coupon", {"code": "api-1000"}, format="json", **auth(token_for(buyer))
    )

    assert response.status_code == 200
    coupon = response.data["coupon"]
    assert coupon["code"] == "API-1000"
    assert coupon["is_applicable"] is True
    assert coupon["not_applicable_reason"] is None
    assert response.data["amounts"]["discount_amount"] == 1000


# trace: FR-024
def test_apply_unknown_coupon_returns_409(api_client, buyer, token_for):
    """E-024-06：存在しないクーポンコードは409とする。"""
    unit = make_stock_unit(make_item(), quantity=5)
    cart_services.add_line(buyer, {"stock_unit_id": unit.pk, "quantity": 1})

    response = api_client.post(
        "/api/cart/apply-coupon", {"code": "NOT-EXIST"}, format="json", **auth(token_for(buyer))
    )

    assert response.status_code == 409
    assert response.data["error"]["code"] == "COUPON_NOT_FOUND"


# trace: FR-025
def test_remove_coupon_clears_coupon(api_client, buyer, token_for):
    """FR-025：クーポン解除後のカート内容を返す。"""
    coupon = make_coupon(code="API-REMOVE")
    cart = make_open_cart(buyer, coupon=coupon)
    add_cart_line(cart, make_stock_unit(make_item(), quantity=5))

    response = api_client.post("/api/cart/remove-coupon", **auth(token_for(buyer)))

    assert response.status_code == 200
    assert response.data["coupon"] is None


# trace: FR-030
def test_checkout_returns_201_with_order_payload(api_client, buyer, token_for):
    """FR-030：注文確定は201で注文詳細内容（FR-033 と同じ形）を返す。"""
    unit = make_stock_unit(make_item(name="注文商品"), price=3000, quantity=10)
    cart_services.add_line(buyer, {"stock_unit_id": unit.pk, "quantity": 2})

    response = api_client.post(
        "/api/checkout", shipping_input(), format="json", **auth(token_for(buyer))
    )

    assert response.status_code == 201
    assert response.data["status"] == "created"
    assert response.data["amounts"]["total"] == 6600
    assert response.data["shipping_address"]["postal_code"] == "1234567"
    assert response.data["can_pay"] is True
    assert response.data["can_cancel"] is True
    assert "payment_records" not in response.data
    assert "actor_user_id" not in response.data["status_history"][0]


# trace: FR-030
def test_checkout_returns_409_for_empty_cart(api_client, buyer, token_for):
    """E-030-04：カートが空の場合は409 CART_EMPTY とする。"""
    response = api_client.post("/api/checkout", shipping_input(), format="json", **auth(token_for(buyer)))

    assert response.status_code == 409
    assert response.data["error"]["code"] == "CART_EMPTY"


# trace: FR-031, NFR-SC-24
def test_pay_returns_paid_order(api_client, buyer, token_for):
    """FR-031：承認時は200で更新後の注文詳細内容を返す（決済記録は返さない）。"""
    order, _unit = create_order(buyer)

    response = api_client.post(
        f"/api/purchase-orders/{order.pk}/pay", {"mock_result": "approve"}, format="json", **auth(token_for(buyer))
    )

    assert response.status_code == 200
    assert response.data["status"] == "paid"
    assert response.data["paid_at"] is not None
    assert "payment_records" not in response.data


# trace: FR-031
def test_pay_declined_returns_409(api_client, buyer, token_for):
    """E-031-06：否認は409 PAYMENT_DECLINED とする。"""
    order, _unit = create_order(buyer)

    response = api_client.post(
        f"/api/purchase-orders/{order.pk}/pay", {"mock_result": "decline"}, format="json", **auth(token_for(buyer))
    )

    assert response.status_code == 409
    assert response.data["error"]["code"] == "PAYMENT_DECLINED"


# trace: FR-032
def test_purchase_order_list_returns_own_orders(api_client, buyer, token_for):
    """FR-032：注文履歴一覧はページング形式で本人の注文のみを返す。"""
    order, _unit = create_order(buyer)

    response = api_client.get("/api/purchase-orders", **auth(token_for(buyer)))

    assert response.status_code == 200
    assert response.data["page_size"] == 20
    assert response.data["results"][0]["purchase_order_id"] == order.pk
    assert response.data["results"][0]["total_quantity"] == 2


# trace: FR-033
def test_purchase_order_detail_returns_order(api_client, buyer, token_for):
    """FR-033：注文詳細照会（購入者）は注文詳細内容を返す。"""
    order, _unit = create_order(buyer)

    response = api_client.get(f"/api/purchase-orders/{order.pk}", **auth(token_for(buyer)))

    assert response.status_code == 200
    assert response.data["order_number"] == order.order_number
    assert response.data["lines"][0]["quantity"] == 2


# trace: FR-033
def test_purchase_order_detail_returns_applied_coupon(api_client, buyer, token_for):
    """FR-033 6.18.5⑦：クーポンを適用した注文は、コード・割引方式・割引値を返す。"""
    order, _coupon = create_order_with_coupon(
        buyer, code="ORD-PCT-10", discount_type=DISCOUNT_PERCENTAGE, discount_value=10
    )

    response = api_client.get(f"/api/purchase-orders/{order.pk}", **auth(token_for(buyer)))

    assert response.status_code == 200
    assert response.data["coupon"] == {
        "code": "ORD-PCT-10",
        "discount_type": "percentage",
        "discount_value": 10,
    }


# trace: FR-033
def test_purchase_order_detail_keeps_coupon_snapshot_after_master_is_changed(api_client, buyer, token_for):
    """FR-033 6.18.5⑦：返すクーポンは注文確定時のスナップショットの値とする。"""
    order, coupon = create_order_with_coupon(
        buyer, code="ORD-FIX-500", discount_type=DISCOUNT_FIXED, discount_value=500
    )
    coupon.code = "ORD-FIX-CHANGED"
    coupon.discount_type = DISCOUNT_PERCENTAGE
    coupon.discount_value = 30
    coupon.save(update_fields=["code", "discount_type", "discount_value"])

    response = api_client.get(f"/api/purchase-orders/{order.pk}", **auth(token_for(buyer)))

    assert response.status_code == 200
    assert response.data["coupon"] == {
        "code": "ORD-FIX-500",
        "discount_type": "fixed",
        "discount_value": 500,
    }


# trace: NFR-SC-03
def test_purchase_order_of_other_buyer_returns_404(api_client, buyer, token_for):
    """PRM-01：他の購入者の注文は404とし、存在有無を明かさない。"""
    other = make_user(email="other-order@example.test")
    order, _unit = create_order(other)

    response = api_client.get(f"/api/purchase-orders/{order.pk}", **auth(token_for(buyer)))

    assert response.status_code == 404


# trace: FR-034
def test_cancel_order_returns_cancelled_order(api_client, buyer, token_for):
    """FR-034：注文キャンセル（購入者）は更新後の注文詳細内容を返す。"""
    order, unit = create_order(buyer)

    response = api_client.post(f"/api/purchase-orders/{order.pk}/cancel", **auth(token_for(buyer)))

    unit.refresh_from_db()
    assert response.status_code == 200
    assert response.data["status"] == "cancelled"
    assert unit.quantity == 10


# trace: FR-040
def test_admin_stock_units_require_admin_role(api_client, buyer, token_for):
    """FR-040：購入者が管理者専用APIを要求した場合は403とする。"""
    response = api_client.get("/api/admin/stock-units", **auth(token_for(buyer)))

    assert response.status_code == 403
    assert response.data["error"]["code"] == "PERMISSION_DENIED"


# trace: FR-040
def test_admin_stock_units_returns_paging_format(api_client, admin_user, token_for):
    """FR-040：在庫単位一覧は50件/ページで、商品・仕入先・低在庫を含めて返す。"""
    unit = make_stock_unit(make_item(name="管理商品"), sku="SKU-ADMIN", price=1000, quantity=5)

    response = api_client.get("/api/admin/stock-units?sku=sku-adm", **auth(token_for(admin_user)))

    assert response.status_code == 200
    assert response.data["page_size"] == 50
    result = response.data["results"][0]
    assert result["stock_unit_id"] == unit.pk
    assert result["item_name"] == "管理商品"
    assert result["supplier_name"] == unit.supplier.name
    assert result["item_is_public"] is True
    assert result["is_low_stock"] is True


# trace: FR-041
def test_admin_purchase_orders_filter_by_status(api_client, buyer, admin_user, token_for):
    """FR-041：注文状態の複数指定は同じクエリ名を繰り返して指定する。"""
    order, _unit = create_order(buyer)

    response = api_client.get(
        "/api/admin/purchase-orders?status=created&status=paid", **auth(token_for(admin_user))
    )

    assert response.status_code == 200
    result = response.data["results"][0]
    assert result["purchase_order_id"] == order.pk
    assert result["buyer_email"] == buyer.email
    assert result["buyer_name"] == buyer.full_name


# trace: FR-042
def test_admin_purchase_order_detail_includes_payment_records(api_client, buyer, admin_user, token_for):
    """FR-042：管理者向け注文詳細は購入者情報・決済記録・操作可否を含む。"""
    order, _unit = create_order(buyer)
    order_services.pay(buyer, order.pk, {"mock_result": "approve"})

    response = api_client.get(f"/api/admin/purchase-orders/{order.pk}", **auth(token_for(admin_user)))

    assert response.status_code == 200
    assert response.data["buyer"] == {
        "user_id": buyer.pk,
        "email": buyer.email,
        "full_name": buyer.full_name,
    }
    assert response.data["payment_records"][0]["result"] == "approved"
    assert response.data["can_ship"] is True
    assert response.data["can_deliver"] is False
    assert response.data["status_history"][0]["actor_user_id"] == buyer.pk


# trace: FR-042
def test_admin_purchase_order_detail_returns_applied_coupon(api_client, buyer, admin_user, token_for):
    """FR-042 6.22.5⑦：管理者向け注文詳細も注文確定時のクーポンを同じ項目で返す。"""
    order, _coupon = create_order_with_coupon(
        buyer, code="ADM-FIX-1000", discount_type=DISCOUNT_FIXED, discount_value=1000
    )

    response = api_client.get(f"/api/admin/purchase-orders/{order.pk}", **auth(token_for(admin_user)))

    assert response.status_code == 200
    assert response.data["coupon"] == {
        "code": "ADM-FIX-1000",
        "discount_type": "fixed",
        "discount_value": 1000,
    }


# trace: FR-043
def test_admin_ship_marks_order_shipped(api_client, buyer, admin_user, token_for):
    """FR-043：出荷登録は管理者向け注文詳細表現を返す。"""
    order, _unit = create_order(buyer)
    order_services.pay(buyer, order.pk, {"mock_result": "approve"})

    response = api_client.post(
        f"/api/admin/purchase-orders/{order.pk}/ship",
        {"tracking_number": "TRACK-9999"},
        format="json",
        **auth(token_for(admin_user)),
    )

    assert response.status_code == 200
    assert response.data["status"] == "shipped"
    assert response.data["tracking_number"] == "TRACK-9999"


# trace: FR-044
def test_admin_deliver_marks_order_delivered(api_client, buyer, admin_user, token_for):
    """FR-044：配達完了登録は管理者向け注文詳細表現を返す。"""
    order, _unit = create_order(buyer)
    order_services.pay(buyer, order.pk, {"mock_result": "approve"})
    order_services.ship(admin_user, order.pk, {})

    response = api_client.post(
        f"/api/admin/purchase-orders/{order.pk}/deliver", **auth(token_for(admin_user))
    )

    assert response.status_code == 200
    assert response.data["status"] == "delivered"


# trace: FR-044
def test_admin_deliver_returns_409_for_invalid_status(api_client, buyer, admin_user, token_for):
    """E-044-05：出荷済以外の注文は409 INVALID_STATUS_TRANSITION とする。"""
    order, _unit = create_order(buyer)

    response = api_client.post(
        f"/api/admin/purchase-orders/{order.pk}/deliver", **auth(token_for(admin_user))
    )

    assert response.status_code == 409
    assert response.data["error"]["code"] == "INVALID_STATUS_TRANSITION"
    assert response.data["error"]["context"] == {"current_status": "created"}


# trace: FR-045
def test_admin_cancel_restores_stock(api_client, buyer, admin_user, token_for):
    """FR-045：管理者のキャンセルは在庫を戻し、管理者向け注文詳細表現を返す。"""
    order, unit = create_order(buyer)

    response = api_client.post(
        f"/api/admin/purchase-orders/{order.pk}/cancel", **auth(token_for(admin_user))
    )

    unit.refresh_from_db()
    assert response.status_code == 200
    assert response.data["status"] == "cancelled"
    assert unit.quantity == 10


# trace: FR-012, ADDR-001
def test_unknown_api_path_returns_not_found(api_client):
    """提供済みAPI契約にないパスは404とする。"""
    response = api_client.get("/api/unknown")

    assert response.status_code == 404
