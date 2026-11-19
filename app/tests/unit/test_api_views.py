# trace: FR-001, FR-002, FR-003, FR-004, FR-010, FR-011, FR-012, FR-020, FR-021, FR-022, FR-023, FR-024, FR-025
# trace: FR-030, FR-031, FR-032, FR-033, FR-034, FR-040, FR-041, FR-042, FR-043, FR-044, FR-045
# trace: NFR-SC-03, NFR-SC-06, NFR-SC-08, NFR-SC-10, NFR-SC-15, ADDR-001, ADDR-002, ADDR-012
"""Web API 層（*/views_api.py、accounts.authentication、common.api）の単体テスト。

期待値：ADDR-001 4.3 の1〜8（パス・成功ステータス・エラー封筒・HTTP ステータス・ページング）、
DD-007（識別子・他者データは同じ 404）、DD-008（未定義項目の無視）、
INV-003（/api/ で Cookie セッション認証を受け付けない）、ADDR-002 DD-001〜DD-003、
CMN-02・03・14（認証→権限→入力の判定順序）、NFR-SC-03・06・08・10・15。
DB Test Strategy：CONTAINER（ビューから業務処理・DB まで1要求で通す。外部通信なし）。
"""

import json
from unittest import mock

import pytest

from accounts.models import ApiLoginState, User
from carts.models import Cart, CartItem
from common.errors import MSG_SYSTEM_ERROR
from orders.models import Order
from tests.unit.conftest import DEFAULT_PASSWORD

pytestmark = pytest.mark.django_db
ADDRESS = {
    "recipient_name": "受取 太郎",
    "postal_code": "123-4567",
    "prefecture": "27",
    "address_line1": "大阪市北区1-1",
    "phone_number": "06-1234-5678",
}


# trace: ADDR-001
def _error(response):
    body = response.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"type", "reason", "message", "fields", "values"}
    return body["error"]


# trace: ADDR-001
def _json(client, method, path, auth=None, body=None):
    kwargs = {"format": "json"} if body is not None else {}
    if auth:
        kwargs["HTTP_AUTHORIZATION"] = auth
    return (
        getattr(client, method)(path, body, **kwargs)
        if body is not None
        else getattr(client, method)(path, **kwargs)
    )


# ---------------------------------------------------------------------------
# 会員・認証（FR-001〜FR-004）
# ---------------------------------------------------------------------------


# trace: FR-001, NFR-SC-15, ADDR-001
def test_register_api_returns_201_and_ignores_user_type(api_client):
    response = api_client.post(
        "/api/auth/register/",
        {
            "email": "New@Example.test",
            "password": "Passw0rd",
            "password_confirmation": "Passw0rd",
            "name": "新規",
            "user_type": "admin",
        },
        format="json",
    )
    assert response.status_code == 201
    body = response.json()
    assert body["user_type"] == "buyer" and body["user_type_label"] == "購入者"
    assert body["registered_at"].endswith("+09:00")
    assert "password" not in body
    assert User.objects.get(email="new@example.test").user_type == "buyer"


# trace: FR-001, ADDR-001
def test_register_api_input_error_lists_fields(api_client):
    response = api_client.post("/api/auth/register/", {}, format="json")
    assert response.status_code == 400
    error = _error(response)
    assert error["type"] == "input_error" and error["reason"] is None and error["values"] == {}
    assert {f["field"] for f in error["fields"]} == {"email", "password", "password_confirmation", "name"}


# trace: FR-001, ADDR-001, ADDR-012
def test_register_api_input_error_precedes_registered_email(api_client, make_user):
    """AC-UC-001-013（Web API）：入力不備（パスワード7文字）は登録済みメールアドレスの判定より優先する。"""
    make_user("hanako.sato@example.com")
    before = User.objects.count()
    response = api_client.post(
        "/api/auth/register/",
        {
            "email": "hanako.sato@example.com",
            "password": "Passw0r",
            "password_confirmation": "Passw0r",
            "name": "佐藤 花子",
        },
        format="json",
    )
    assert response.status_code == 400
    error = _error(response)
    assert error["type"] == "input_error" and error["reason"] is None
    assert [f["field"] for f in error["fields"]] == ["password"] and error["fields"][0]["message"]
    assert "既に登録されています" not in response.content.decode("utf-8")
    assert User.objects.count() == before


# trace: FR-001, ADDR-001
@pytest.mark.parametrize(
    ("body", "content_type"),
    [("{broken", "application/json"), ("[1, 2]", "application/json"), ("a=b", "text/plain")],
)
def test_unparseable_or_non_object_body_is_400_input_error(api_client, body, content_type):
    response = api_client.post("/api/auth/register/", body, content_type=content_type)
    assert response.status_code == 400
    assert _error(response)["type"] == "input_error"


# trace: FR-002, NFR-SC-08, ADDR-001, ADDR-002
def test_login_api_returns_token_and_logout_invalidates_only_that_token(api_client, buyer):
    login = lambda: api_client.post(  # noqa: E731
        "/api/auth/login/", {"email": buyer.email.upper(), "password": DEFAULT_PASSWORD}, format="json"
    )
    first, second = login(), login()
    assert first.status_code == 200
    body = first.json()
    assert set(body) == {"token", "expires_at", "user"} and body["expires_at"].endswith("+09:00")
    assert body["user"]["user_id"] == buyer.pk
    auth1, auth2 = f"Bearer {body['token']}", f"Bearer {second.json()['token']}"
    assert _json(api_client, "get", "/api/auth/me/", auth1).json()["email"] == buyer.email
    response = _json(api_client, "post", "/api/auth/logout/", auth1)
    assert response.status_code == 204 and response.content == b""
    again = _json(api_client, "get", "/api/auth/me/", auth1)
    assert again.status_code == 401 and again["WWW-Authenticate"] == 'Bearer realm="api"'
    assert _json(api_client, "get", "/api/auth/me/", auth2).status_code == 200  # 他のログイン状態は有効


# trace: FR-002, ADDR-001
def test_login_api_failure_is_401_authentication_failed(api_client, buyer):
    response = api_client.post("/api/auth/login/", {"email": buyer.email, "password": "wrong"}, format="json")
    assert response.status_code == 401
    assert _error(response)["type"] == "authentication_failed"
    response = api_client.post("/api/auth/login/", {"email": "", "password": ""}, format="json")
    assert response.status_code == 400


# trace: FR-003, FR-004, ADDR-002
@pytest.mark.parametrize(
    "auth",
    [None, "Bearer", "Bearer ", "Token abc", "Bearer a b", "Bearer unknown-token", "bearer xyz"],
)
def test_authentication_required_apis_reject_missing_or_invalid_tokens(api_client, auth):
    for method, path in (("get", "/api/auth/me/"), ("post", "/api/auth/logout/"), ("get", "/api/cart/")):
        response = _json(api_client, method, path, auth)
        assert response.status_code == 401, path
        assert _error(response)["type"] == "authentication_required"


# trace: FR-020, ADDR-001
def test_cookie_session_is_not_accepted_on_api(login_web, buyer):
    """ADDR-001 INV-003：/api/ で Cookie によるセッション認証を受け付けない。"""
    client = login_web(buyer)
    response = client.get("/api/cart/")
    assert response.status_code == 401
    assert not Cart.objects.exists()


# trace: FR-010, FR-011, FR-012, ADDR-001
def test_public_apis_treat_invalid_token_as_visitor(api_client, catalog):
    product = catalog.product("公開")
    catalog.stock_unit(product)
    for path in ("/api/categories/", "/api/products/", f"/api/products/{product.pk}/"):
        response = _json(api_client, "get", path, "Bearer invalid")
        assert response.status_code == 200, path
    assert api_client.get("/api/categories/").json() == {"items": []}


# ---------------------------------------------------------------------------
# 商品カタログ・在庫単位（FR-010〜FR-012、FR-040）
# ---------------------------------------------------------------------------


# trace: FR-011, FR-012, ADDR-001
def test_catalog_api_errors_and_paging(api_client, catalog):
    response = api_client.get("/api/products/?page=0&sort=bad&keyword=" + "a" * 51)
    assert response.status_code == 400
    assert {f["field"] for f in _error(response)["fields"]} == {"page", "sort", "keyword"}
    empty = api_client.get("/api/products/?page=5").json()
    assert empty == {"items": [], "page": 5, "page_size": 20, "total_count": 0, "total_pages": 0}
    for product_id in ("abc", "0", "999999"):
        response = api_client.get(f"/api/products/{product_id}/")
        assert response.status_code == 404 and _error(response)["type"] == "not_found"


# trace: FR-040, NFR-SC-03, ADDR-001
def test_stock_unit_api_is_admin_only(api_client, bearer, buyer, admin, catalog):
    catalog.stock_unit(sku="ONLY-1")
    assert api_client.get("/api/admin/stock-units/").status_code == 401
    response = _json(api_client, "get", "/api/admin/stock-units/", bearer(buyer))
    assert response.status_code == 403 and _error(response)["type"] == "permission_denied"
    response = _json(api_client, "get", "/api/admin/stock-units/?low_stock_only=TRUE", bearer(admin))
    assert response.status_code == 400
    response = _json(api_client, "get", "/api/admin/stock-units/?sku=only", bearer(admin))
    assert response.status_code == 200 and response.json()["items"][0]["sku"] == "ONLY-1"


# ---------------------------------------------------------------------------
# カート・注文の一連の操作（FR-020〜FR-034）
# ---------------------------------------------------------------------------


# trace: FR-020, FR-021, FR-022, FR-023, FR-024, FR-025, FR-030, FR-031, FR-032, FR-033, FR-034, ADDR-001
def test_buyer_api_flow_from_cart_to_cancel(api_client, bearer, buyer, catalog, make_coupon):
    auth = bearer(buyer)
    unit = catalog.stock_unit(price=3000, stock=5)
    other = catalog.stock_unit(price=100, stock=5)
    make_coupon("OFF", discount_value=500)
    assert _json(api_client, "get", "/api/cart/", auth).json()["total_quantity"] == 0
    added = _json(api_client, "post", "/api/cart/items/", auth, {"stock_unit_id": unit.pk, "quantity": 2})
    assert added.status_code == 200 and added.json()["total_quantity"] == 2
    _json(api_client, "post", "/api/cart/items/", auth, {"stock_unit_id": other.pk, "quantity": 1})
    item_id = CartItem.objects.get(stock_unit=unit).pk
    other_id = CartItem.objects.get(stock_unit=other).pk
    changed = _json(api_client, "patch", f"/api/cart/items/{item_id}/", auth, {"quantity": 1})
    assert changed.json()["items"][0]["quantity"] == 1
    deleted = _json(api_client, "delete", f"/api/cart/items/{other_id}/", auth)
    assert deleted.status_code == 200 and len(deleted.json()["items"]) == 1
    applied = _json(api_client, "post", "/api/cart/coupon/", auth, {"coupon_code": "off"})
    assert applied.json()["coupon"]["coupon_code"] == "OFF"
    removed = _json(api_client, "delete", "/api/cart/coupon/", auth)
    assert removed.json()["coupon"] is None
    placed = _json(api_client, "post", "/api/orders/", auth, {"shipping_address": ADDRESS})
    assert placed.status_code == 201
    order = placed.json()
    assert order["status"] == "accepted" and order["shipping_address"]["postal_code"] == "1234567"
    paid = _json(api_client, "post", f"/api/orders/{order['order_id']}/payment/", auth, {})
    assert paid.status_code == 200 and paid.json()["status"] == "paid"
    listed = _json(api_client, "get", "/api/orders/", auth).json()
    assert listed["items"][0]["order_id"] == order["order_id"] and listed["page_size"] == 20
    detail = _json(api_client, "get", f"/api/orders/{order['order_id']}/", auth).json()
    assert "payments" not in detail and "actor_user_id" not in json.dumps(detail)
    cancelled = _json(api_client, "post", f"/api/orders/{order['order_id']}/cancel/", auth)
    assert cancelled.json()["status"] == "cancelled"
    again = _json(api_client, "post", f"/api/orders/{order['order_id']}/cancel/", auth)
    assert again.status_code == 422
    error = _error(again)
    assert error["reason"] == "invalid_status" and error["values"]["current_status"] == "cancelled"


# trace: FR-021, FR-024, FR-031, ADDR-001
def test_business_and_integration_errors_map_to_422_and_502(api_client, bearer, buyer, catalog, make_order, test_state):
    auth = bearer(buyer)
    unit = catalog.stock_unit(stock=1)
    response = _json(api_client, "post", "/api/cart/items/", auth, {"stock_unit_id": unit.pk, "quantity": 2})
    assert response.status_code == 422
    error = _error(response)
    assert error["reason"] == "insufficient_stock" and error["values"]["stock_units"][0]["stock_quantity"] == 1
    response = _json(api_client, "post", "/api/cart/coupon/", auth, {"coupon_code": "!!"})
    assert response.status_code == 400 and _error(response)["fields"][0]["field"] == "coupon_code"
    order = make_order(buyer, [(unit, 1)])
    declined = _json(api_client, "post", f"/api/orders/{order.pk}/payment/", auth, {"mock_instruction": "declined"})
    assert declined.status_code == 422 and _error(declined)["reason"] == "payment_declined"
    test_state(payment_mode="missing_result")
    failed = _json(api_client, "post", f"/api/orders/{order.pk}/payment/", auth, {"mock_instruction": "approved"})
    assert failed.status_code == 502
    assert _error(failed)["type"] == "integration_error" and _error(failed)["reason"] is None


# trace: FR-030, FR-033, NFR-SC-03, ADDR-001
def test_admin_cannot_use_buyer_apis_and_nothing_changes(api_client, bearer, admin, buyer, catalog, make_order):
    auth = bearer(admin)
    order = make_order(buyer, [(catalog.stock_unit(), 1)])
    for method, path, body in (
        ("get", "/api/cart/", None),
        ("post", "/api/cart/items/", {"stock_unit_id": 1, "quantity": 1}),
        ("patch", "/api/cart/items/1/", {"quantity": 1}),
        ("delete", "/api/cart/items/1/", None),
        ("post", "/api/cart/coupon/", {"coupon_code": "X"}),
        ("delete", "/api/cart/coupon/", None),
        ("get", "/api/orders/", None),
        ("post", "/api/orders/", {"shipping_address": ADDRESS}),
        ("get", f"/api/orders/{order.pk}/", None),
        ("post", f"/api/orders/{order.pk}/payment/", {}),
        ("post", f"/api/orders/{order.pk}/cancel/", None),
    ):
        response = _json(api_client, method, path, auth, body)
        assert response.status_code == 403, path
        assert _error(response)["type"] == "permission_denied"
    order.refresh_from_db()
    assert order.status == "accepted" and not Cart.objects.exists()


# trace: FR-033, FR-034, NFR-SC-03, ADDR-001
def test_other_buyers_order_is_404_like_missing(api_client, bearer, buyer, other_buyer, catalog, make_order):
    order = make_order(other_buyer, [(catalog.stock_unit(), 1)])
    auth = bearer(buyer)
    for method, path in (
        ("get", f"/api/orders/{order.pk}/"),
        ("post", f"/api/orders/{order.pk}/payment/"),
        ("post", f"/api/orders/{order.pk}/cancel/"),
        ("get", "/api/orders/abc/"),
    ):
        response = _json(api_client, method, path, auth, {} if method == "post" else None)
        assert response.status_code == 404 and _error(response)["type"] == "not_found"
    order.refresh_from_db()
    assert order.status == "accepted"


# ---------------------------------------------------------------------------
# 管理者の注文 API（FR-041〜FR-045）
# ---------------------------------------------------------------------------


# trace: FR-041, FR-042, FR-043, FR-044, FR-045, NFR-SC-03, ADDR-001
def test_admin_order_apis(api_client, bearer, admin, buyer, catalog, make_order):
    auth = bearer(admin)
    paid = make_order(buyer, [(catalog.stock_unit(), 1)], status="paid")
    accepted_unit = catalog.stock_unit(stock=8)
    accepted = make_order(buyer, [(accepted_unit, 2)])
    listed = _json(api_client, "get", "/api/admin/orders/?status=paid&status=shipped", auth).json()
    assert [i["order_id"] for i in listed["items"]] == [paid.pk]
    bad = _json(api_client, "get", "/api/admin/orders/?order_date_from=2027-04-10&order_date_to=2027-04-09", auth)
    assert bad.status_code == 400 and _error(bad)["fields"][0]["reason"] == "invalid_range"
    detail = _json(api_client, "get", f"/api/admin/orders/{paid.pk}/", auth).json()
    assert detail["can_ship"] is True and detail["buyer"]["user_id"] == buyer.pk
    shipped = _json(api_client, "post", f"/api/admin/orders/{paid.pk}/ship/", auth, {"tracking_number": "TRK-1"})
    assert shipped.json()["status"] == "shipped" and shipped.json()["tracking_number"] == "TRK-1"
    delivered = _json(api_client, "post", f"/api/admin/orders/{paid.pk}/deliver/", auth)
    assert delivered.json()["status"] == "delivered"
    cancelled = _json(api_client, "post", f"/api/admin/orders/{accepted.pk}/cancel/", auth)
    assert cancelled.json()["status"] == "cancelled"
    accepted_unit.refresh_from_db()
    assert accepted_unit.stock_quantity == 10  # AC-UC-012-001：注文受付の管理者キャンセルで在庫数量 8→10
    again = _json(api_client, "post", f"/api/admin/orders/{accepted.pk}/cancel/", auth)
    assert again.status_code == 422 and _error(again)["values"]["current_status"] == "cancelled"
    accepted_unit.refresh_from_db()
    assert accepted_unit.stock_quantity == 10  # 再送信で在庫を2回戻さない
    assert _json(api_client, "get", "/api/admin/orders/9999999/", auth).status_code == 404
    buyer_auth = bearer(buyer)
    for method, path in (
        ("get", "/api/admin/orders/"),
        ("get", f"/api/admin/orders/{paid.pk}/"),
        ("post", f"/api/admin/orders/{accepted.pk}/ship/"),
        ("post", f"/api/admin/orders/{accepted.pk}/deliver/"),
        ("post", f"/api/admin/orders/{accepted.pk}/cancel/"),
    ):
        response = _json(api_client, method, path, buyer_auth, {} if method == "post" else None)
        assert response.status_code == 403, path


# trace: FR-043, ADDR-001
def test_authentication_is_judged_before_role_and_input(api_client, bearer, buyer):
    """CMN-14：①認証→②権限→③入力の順。未ログインは入力が誤っていても 401、購入者は 403。"""
    response = api_client.post("/api/admin/orders/1/ship/", {"tracking_number": "!!"}, format="json")
    assert response.status_code == 401
    response = _json(api_client, "post", "/api/admin/orders/1/ship/", bearer(buyer), {"tracking_number": "!!"})
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# 共通の応答（404・405・500、内部情報の非表示、ログ）
# ---------------------------------------------------------------------------


# trace: NFR-SC-10, ADDR-001
def test_unknown_path_and_disallowed_method(api_client):
    response = api_client.get("/api/no-such/")
    assert response.status_code == 404 and _error(response)["type"] == "not_found"
    response = api_client.options("/api/products/")
    assert response.status_code == 405
    response = api_client.put("/api/products/", {}, format="json")
    assert response.status_code == 405


# trace: FR-011, NFR-SC-10, ADDR-001
def test_unexpected_exception_returns_500_without_internal_details(api_client, app_logs):
    secret = 'psycopg.errors.UndefinedTable: relation "x" SELECT * FROM catalog_product /srv/app'
    with mock.patch("catalog.services.search_products", side_effect=RuntimeError(secret)):
        response = api_client.get("/api/products/")
    assert response.status_code == 500
    error = _error(response)
    assert error["type"] == "system_error" and error["message"] == MSG_SYSTEM_ERROR
    assert "SELECT" not in response.content.decode() and "Traceback" not in response.content.decode()
    assert any(r["log_type"] == "LOG-02" for r in app_logs.records())


# trace: FR-041, NFR-SC-06
def test_logs_do_not_contain_query_strings_tokens_or_personal_data(api_client, bearer, admin, app_logs):
    auth = bearer(admin)
    token = auth.split(" ")[1]
    _json(api_client, "get", "/api/admin/orders/?buyer_email=secret.person@example.test", auth)
    lines = "\n".join(app_logs.lines)
    access = [r for r in app_logs.records() if r["log_type"] == "LOG-03"]
    assert access[-1]["path"] == "/api/admin/orders/" and access[-1]["user_id"] == admin.pk
    assert "secret.person" not in lines and token not in lines
    response = api_client.get("/api/categories/")
    assert response["X-Request-ID"]


# trace: FR-002, NFR-SC-06
def test_login_logs_do_not_contain_credentials(api_client, buyer, app_logs):
    api_client.post("/api/auth/login/", {"email": buyer.email, "password": DEFAULT_PASSWORD}, format="json")
    api_client.post("/api/auth/login/", {"email": buyer.email, "password": "WrongPass9"}, format="json")
    lines = "\n".join(app_logs.lines)
    assert buyer.email not in lines and DEFAULT_PASSWORD not in lines and "WrongPass9" not in lines
    token_hash = ApiLoginState.objects.get().token_hash
    assert token_hash not in lines


# trace: FR-030, ADDR-001
def test_place_order_api_requires_object_shipping_address(api_client, bearer, buyer):
    response = _json(api_client, "post", "/api/orders/", bearer(buyer), {"shipping_address": "x"})
    assert response.status_code == 400
    assert {f["field"] for f in _error(response)["fields"]} >= {"shipping_address.postal_code"}
    assert not Order.objects.exists()
