# trace: FR-001, FR-002, FR-003, FR-004, FR-010, FR-011, FR-012, FR-020, FR-021, FR-022, FR-023
# trace: FR-024, FR-025, FR-030, FR-031, FR-032, FR-033, FR-034, FR-040, FR-041, FR-042
# trace: FR-043, FR-044, FR-045, ADDR-007
"""Web API のビュー（api-contract 6.1）の単体テスト。

期待値は api-contract の要求・応答仕様（HTTPステータス・応答本文）と各FRから導出する。
"""
import pytest
from rest_framework.test import APIRequestFactory, force_authenticate

from shop.api import views_admin, views_auth, views_cart, views_catalog, views_orders
from shop.models import AuthToken, PurchaseOrder, PurchaseOrderStatus, User
from shop.services import accounts, carts
from shop.tests.unit import _helpers

pytestmark = pytest.mark.django_db

FACTORY = APIRequestFactory()


# trace: ADDR-007
def _call(view_class, method, path, data=None, user=None, token=None, **kwargs):
    """APIビューを呼び出して応答を返す。"""
    request = getattr(FACTORY, method)(path, data or {}, format="json")
    if user is not None:
        force_authenticate(request, user=user, token=token)
    return view_class.as_view()(request, **kwargs)


# trace: FR-001
def test_register_api_returns_201_with_user(db):
    """会員登録は201で利用者情報を返し、トークンを返さない。"""
    response = _call(
        views_auth.RegisterView,
        "post",
        "/api/auth/register",
        {
            "email": "hanako.sato@example.com",
            "password": "Passw0rd",
            "password_confirmation": "Passw0rd",
            "full_name": "佐藤 花子",
        },
    )

    assert response.status_code == 201
    assert response.data["email"] == "hanako.sato@example.com"
    assert response.data["role"] == "buyer"
    assert "token" not in response.data
    assert "password" not in response.data
    assert "password_hash" not in response.data
    assert User.objects.count() == 1


# trace: FR-001
def test_register_api_returns_400_for_invalid_input(db):
    """入力不備は400で全項目の理由を返す。"""
    response = _call(views_auth.RegisterView, "post", "/api/auth/register", {})

    assert response.status_code == 400
    assert response.data["error"]["code"] == "VALIDATION_ERROR"
    assert len(response.data["error"]["details"]) >= 3


# trace: FR-001
def test_register_api_returns_409_for_duplicate_email(buyer):
    """登録済みメールアドレスは409を返す。"""
    response = _call(
        views_auth.RegisterView,
        "post",
        "/api/auth/register",
        {
            "email": buyer.email,
            "password": "Passw0rd",
            "password_confirmation": "Passw0rd",
            "full_name": "山田 太郎",
        },
    )

    assert response.status_code == 409
    assert response.data["error"]["code"] == "EMAIL_ALREADY_REGISTERED"


# trace: FR-002
def test_login_api_returns_token(buyer):
    """ログインは認証トークン・有効期限・利用者情報を返す。"""
    response = _call(views_auth.LoginView, "post", "/api/auth/login", {"email": buyer.email, "password": "Passw0rd"})

    assert response.status_code == 200
    assert response.data["token"]
    assert response.data["expires_at"] is not None
    assert response.data["user"]["user_id"] == buyer.user_id


# trace: FR-002
def test_login_api_returns_401_for_invalid_credentials(buyer):
    """認証失敗は401を返す。"""
    response = _call(
        views_auth.LoginView, "post", "/api/auth/login", {"email": buyer.email, "password": "Wr0ngpass"}
    )

    assert response.status_code == 401
    assert response.data["error"]["code"] == "INVALID_CREDENTIALS"


# trace: FR-003
def test_logout_api_returns_204(buyer):
    """ログアウトは204を返し、使用したトークンを無効化する。"""
    issued = accounts.login_with_token(buyer.email, "Passw0rd")
    _, token = accounts.resolve_token(issued.value)

    response = _call(views_auth.LogoutView, "post", "/api/auth/logout", user=buyer, token=token)

    assert response.status_code == 204
    assert AuthToken.objects.get(pk=token.pk).revoked_at is not None


# trace: FR-004
def test_me_api_returns_user(buyer):
    """ログイン利用者情報照会は利用者情報を返す。"""
    response = _call(views_auth.MeView, "get", "/api/auth/me", user=buyer)

    assert response.status_code == 200
    assert response.data == {
        "user_id": buyer.user_id,
        "email": buyer.email,
        "full_name": buyer.full_name,
        "role": "buyer",
    }


# trace: FR-004
def test_me_api_returns_401_without_authentication(db):
    """未認証の要求は401を返す。"""
    response = _call(views_auth.MeView, "get", "/api/auth/me")

    assert response.status_code == 401
    assert response.data["error"]["code"] == "AUTHENTICATION_REQUIRED"


# trace: FR-010
def test_collections_api_returns_all_collections(db):
    """商品分類一覧は認証不要で全件を配列で返す。"""
    _helpers.make_collection("books", "書籍")

    response = _call(views_catalog.CollectionListView, "get", "/api/collections")

    assert response.status_code == 200
    assert [row["collection_code"] for row in response.data] == ["books"]


# trace: FR-011
def test_items_api_returns_page(db, supplier):
    """商品一覧検索は認証不要でページ情報つきの一覧を返す。"""
    item = _helpers.make_item("ITEM-001", "商品")
    _helpers.make_stock_unit(item, supplier, sku="SKU-001")

    response = _call(views_catalog.ItemListView, "get", "/api/items")

    assert response.status_code == 200
    assert response.data["total_count"] == 1
    assert response.data["page_size"] == 20


# trace: FR-011
def test_items_api_returns_400_for_invalid_sort(db):
    """並び順の指定が不正な場合は400を返す。"""
    request = FACTORY.get("/api/items", {"sort": "unknown"})
    response = views_catalog.ItemListView.as_view()(request)

    assert response.status_code == 400


# trace: FR-012
def test_item_detail_api_returns_404_for_unknown_item(db):
    """存在しない商品は404を返す。"""
    response = _call(views_catalog.ItemDetailView, "get", "/api/items/999999", item_id="999999")

    assert response.status_code == 404
    assert response.data["error"]["code"] == "NOT_FOUND"


# trace: FR-020
def test_cart_api_returns_cart(buyer):
    """カート照会は利用中カートの内容を返す。"""
    response = _call(views_cart.CartView, "get", "/api/cart", user=buyer)

    assert response.status_code == 200
    assert response.data["lines"] == []


# trace: FR-020
def test_cart_api_rejects_admin(admin_user):
    """管理者のカート照会は403を返す。"""
    response = _call(views_cart.CartView, "get", "/api/cart", user=admin_user)

    assert response.status_code == 403
    assert response.data["error"]["code"] == "PERMISSION_DENIED"


# trace: FR-021
def test_cart_lines_api_adds_line(buyer, stock_unit):
    """カート明細追加は更新後のカート内容を返す。"""
    response = _call(
        views_cart.CartLineListView,
        "post",
        "/api/cart/lines",
        {"stock_unit_id": stock_unit.stock_unit_id, "quantity": 2},
        user=buyer,
    )

    assert response.status_code == 200
    assert response.data["total_quantity"] == 2


# trace: FR-021
def test_cart_lines_api_returns_409_for_stock_shortage(buyer, item, supplier):
    """在庫不足は409（INSUFFICIENT_STOCK）を返し、不足情報を context に含める。"""
    unit = _helpers.make_stock_unit(item, supplier, sku="SKU-010", quantity=1)

    response = _call(
        views_cart.CartLineListView,
        "post",
        "/api/cart/lines",
        {"stock_unit_id": unit.stock_unit_id, "quantity": 2},
        user=buyer,
    )

    assert response.status_code == 409
    assert response.data["error"]["code"] == "INSUFFICIENT_STOCK"
    assert response.data["error"]["context"]["shortages"][0]["available_quantity"] == 1


# trace: FR-022
def test_cart_line_api_updates_quantity(buyer, stock_unit):
    """カート明細数量変更は更新後のカート内容を返す。"""
    carts.add_line(buyer, stock_unit.stock_unit_id, 1)
    from shop.models import CartLine

    line = CartLine.objects.get()

    response = _call(
        views_cart.CartLineDetailView,
        "patch",
        f"/api/cart/lines/{line.cart_line_id}",
        {"quantity": 3},
        user=buyer,
        cart_line_id=str(line.cart_line_id),
    )

    assert response.status_code == 200
    assert response.data["lines"][0]["quantity"] == 3


# trace: FR-023
def test_cart_line_api_deletes_line(buyer, stock_unit):
    """カート明細削除は更新後のカート内容を返す。"""
    carts.add_line(buyer, stock_unit.stock_unit_id, 1)
    from shop.models import CartLine

    line = CartLine.objects.get()

    response = _call(
        views_cart.CartLineDetailView,
        "delete",
        f"/api/cart/lines/{line.cart_line_id}",
        user=buyer,
        cart_line_id=str(line.cart_line_id),
    )

    assert response.status_code == 200
    assert response.data["lines"] == []


# trace: FR-024
def test_apply_coupon_api_returns_409_for_unknown_code(buyer, stock_unit):
    """存在しないクーポンコードは409を返す。"""
    carts.add_line(buyer, stock_unit.stock_unit_id, 1)

    response = _call(
        views_cart.ApplyCouponView, "post", "/api/cart/apply-coupon", {"code": "NOTEXIST"}, user=buyer
    )

    assert response.status_code == 409
    assert response.data["error"]["code"] == "COUPON_NOT_FOUND"


# trace: FR-025
def test_remove_coupon_api_returns_cart(buyer):
    """クーポン解除はカート内容を返す。"""
    response = _call(views_cart.RemoveCouponView, "post", "/api/cart/remove-coupon", user=buyer)

    assert response.status_code == 200
    assert response.data["coupon"] is None


# trace: FR-030
def test_checkout_api_returns_201(buyer, stock_unit):
    """注文確定は201で注文詳細内容を返す。"""
    carts.add_line(buyer, stock_unit.stock_unit_id, 1)

    response = _call(views_orders.CheckoutView, "post", "/api/checkout", dict(_helpers.VALID_ADDRESS), user=buyer)

    assert response.status_code == 201
    assert response.data["order_number"].startswith("PO-")


# trace: FR-030
def test_checkout_api_returns_409_for_empty_cart(buyer):
    """カートが空の注文確定は409を返す。"""
    response = _call(views_orders.CheckoutView, "post", "/api/checkout", dict(_helpers.VALID_ADDRESS), user=buyer)

    assert response.status_code == 409
    assert response.data["error"]["code"] == "CART_EMPTY"


# trace: FR-032
def test_purchase_orders_api_returns_own_orders(buyer, stock_unit):
    """注文履歴一覧は本人の注文を返す。"""
    _helpers.make_order(buyer, stock_unit, order_number="PO-00000001")

    response = _call(views_orders.PurchaseOrderListView, "get", "/api/purchase-orders", user=buyer)

    assert response.status_code == 200
    assert response.data["total_count"] == 1


# trace: FR-033
def test_purchase_order_detail_api_returns_404_for_other_buyer(buyer, other_buyer, stock_unit):
    """他の購入者の注文詳細は404を返す。"""
    order = _helpers.make_order(buyer, stock_unit, order_number="PO-00000001")

    response = _call(
        views_orders.PurchaseOrderDetailView,
        "get",
        f"/api/purchase-orders/{order.purchase_order_id}",
        user=other_buyer,
        purchase_order_id=str(order.purchase_order_id),
    )

    assert response.status_code == 404


# trace: FR-031
def test_pay_api_approves_payment(buyer, stock_unit):
    """支払（承認）は更新後の注文詳細内容を返す。"""
    order = _helpers.make_order(buyer, stock_unit, order_number="PO-00000001")

    response = _call(
        views_orders.PayView,
        "post",
        f"/api/purchase-orders/{order.purchase_order_id}/pay",
        {"mock_result": "approve"},
        user=buyer,
        purchase_order_id=str(order.purchase_order_id),
    )

    assert response.status_code == 200
    assert response.data["status"] == PurchaseOrderStatus.PAID


# trace: FR-031
def test_pay_api_returns_409_for_declined_payment(buyer, stock_unit):
    """支払（否認）は409（PAYMENT_DECLINED）を返す。"""
    order = _helpers.make_order(buyer, stock_unit, order_number="PO-00000001")

    response = _call(
        views_orders.PayView,
        "post",
        f"/api/purchase-orders/{order.purchase_order_id}/pay",
        {"mock_result": "decline"},
        user=buyer,
        purchase_order_id=str(order.purchase_order_id),
    )

    assert response.status_code == 409
    assert response.data["error"]["code"] == "PAYMENT_DECLINED"


# trace: FR-034
def test_cancel_api_cancels_order(buyer, stock_unit):
    """注文キャンセルはキャンセル後の注文詳細内容を返す。"""
    order = _helpers.make_order(buyer, stock_unit, order_number="PO-00000001")

    response = _call(
        views_orders.CancelView,
        "post",
        f"/api/purchase-orders/{order.purchase_order_id}/cancel",
        user=buyer,
        purchase_order_id=str(order.purchase_order_id),
    )

    assert response.status_code == 200
    assert response.data["status"] == PurchaseOrderStatus.CANCELLED
    assert PurchaseOrder.objects.get(pk=order.pk).status == PurchaseOrderStatus.CANCELLED


# trace: FR-040
def test_admin_stock_units_api_requires_admin(buyer, admin_user, stock_unit):
    """在庫単位一覧は管理者のみ参照できる。"""
    denied = _call(views_admin.StockUnitListView, "get", "/api/admin/stock-units", user=buyer)
    allowed = _call(views_admin.StockUnitListView, "get", "/api/admin/stock-units", user=admin_user)

    assert denied.status_code == 403
    assert allowed.status_code == 200
    assert allowed.data["total_count"] == 1


# trace: FR-041
def test_admin_purchase_orders_api_lists_all_orders(admin_user, buyer, stock_unit):
    """注文一覧（管理者）は全購入者の注文を返す。"""
    _helpers.make_order(buyer, stock_unit, order_number="PO-00000001")

    response = _call(views_admin.AdminPurchaseOrderListView, "get", "/api/admin/purchase-orders", user=admin_user)

    assert response.status_code == 200
    assert response.data["results"][0]["buyer_email"] == buyer.email


# trace: FR-042
def test_admin_purchase_order_detail_api(admin_user, buyer, stock_unit):
    """注文詳細（管理者）は購入者情報を含む詳細を返す。"""
    order = _helpers.make_order(buyer, stock_unit, order_number="PO-00000001")

    response = _call(
        views_admin.AdminPurchaseOrderDetailView,
        "get",
        f"/api/admin/purchase-orders/{order.purchase_order_id}",
        user=admin_user,
        purchase_order_id=str(order.purchase_order_id),
    )

    assert response.status_code == 200
    assert response.data["buyer"]["email"] == buyer.email


# trace: FR-043
def test_admin_ship_api(admin_user, buyer, stock_unit):
    """出荷登録は出荷済の注文詳細を返す。"""
    order = _helpers.make_order(buyer, stock_unit, status=PurchaseOrderStatus.PAID, order_number="PO-00000001")

    response = _call(
        views_admin.ShipView,
        "post",
        f"/api/admin/purchase-orders/{order.purchase_order_id}/ship",
        {"tracking_number": "TRACK-1"},
        user=admin_user,
        purchase_order_id=str(order.purchase_order_id),
    )

    assert response.status_code == 200
    assert response.data["status"] == PurchaseOrderStatus.SHIPPED
    assert response.data["tracking_number"] == "TRACK-1"


# trace: FR-044
def test_admin_deliver_api(admin_user, buyer, stock_unit):
    """配達完了登録は配達完了の注文詳細を返す。"""
    order = _helpers.make_order(buyer, stock_unit, status=PurchaseOrderStatus.SHIPPED, order_number="PO-00000001")

    response = _call(
        views_admin.DeliverView,
        "post",
        f"/api/admin/purchase-orders/{order.purchase_order_id}/deliver",
        user=admin_user,
        purchase_order_id=str(order.purchase_order_id),
    )

    assert response.status_code == 200
    assert response.data["status"] == PurchaseOrderStatus.DELIVERED


# trace: FR-045
def test_admin_cancel_api_returns_409_for_shipped_order(admin_user, buyer, stock_unit):
    """出荷済の注文のキャンセルは409を返す。"""
    order = _helpers.make_order(buyer, stock_unit, status=PurchaseOrderStatus.SHIPPED, order_number="PO-00000001")

    response = _call(
        views_admin.AdminCancelView,
        "post",
        f"/api/admin/purchase-orders/{order.purchase_order_id}/cancel",
        user=admin_user,
        purchase_order_id=str(order.purchase_order_id),
    )

    assert response.status_code == 409
    assert response.data["error"]["code"] == "INVALID_STATUS_TRANSITION"
