# trace: FR-001, FR-002, FR-003, FR-010, FR-011, FR-012, FR-020, FR-021, FR-022, FR-023, FR-024, FR-025
# trace: FR-030, FR-031, FR-032, FR-033, FR-034, FR-040, FR-041, FR-042, FR-043, FR-044, FR-045
# trace: NFR-SC-03, NFR-SC-05, NFR-SC-09, NFR-SC-19, NFR-EN-05, NFR-LG-05
# trace: ADDR-001, ADDR-002, ADDR-004, ADDR-012
"""画面（*/views_web.py、common.web・common.views、テンプレート、表示ごとのカート作成）の単体テスト。

期待値：各 FR の画面表示（6.x.5）と例外時の画面遷移（6.x.7：SCR-004・SCR-901）、CMN-02・03・10・17・22、
NFR-SC-05（XSS：自動エスケープ。CSRF：他サイトからの更新要求を受け付けない＝VUL-05・VUL-06）、NFR-SC-09（無操作30分）、
NFR-SC-19（ログイン時のセッション識別子の再生成・HttpOnly）、NFR-EN-05（外部 CDN を参照しない）、
NFR-LG-05（カード情報の入力項目なし）、
ADDR-001 DD-015（購入者の画面表示で利用中カートを作成）、ADDR-002 DD-004・DD-005・DD-008、
ADDR-004 DD-010・DD-013・DD-016。
DB Test Strategy：CONTAINER（Django の試験用 Client で要求からテンプレート描画まで通す）。
"""

import re
from datetime import timedelta
from pathlib import Path

import pytest
from django.conf import settings
from django.test import Client

from accounts.models import User
from audit.models import AuditLog
from carts.models import Cart, CartItem
from catalog.models import StockUnit
from common.submit_token import issue_token
from orders.models import Order, PaymentRecord
from tests.unit.conftest import DEFAULT_PASSWORD, jst

pytestmark = pytest.mark.django_db
XSS = '<script>alert("x")</script>'
NOW = jst(2027, 4, 20, 10, 0, 0)
ADDRESS = {
    "recipient_name": "受取 太郎",
    "postal_code": "1234567",
    "prefecture": "13",
    "address_line1": "千代田区1-1",
    "address_line2": "",
    "phone_number": "0312345678",
}


# trace: ADDR-012
def _text(response) -> str:
    return response.content.decode("utf-8")


# trace: ADDR-002
def _login_redirect(response, next_path):
    assert response.status_code == 302
    assert response["Location"].startswith("/login/?required=1")
    assert f"next={next_path.replace('/', '%2F')}" in response["Location"]


# ---------------------------------------------------------------------------
# 会員登録・ログイン・ログアウト（SCR-003・SCR-004、FR-001〜FR-003）
# ---------------------------------------------------------------------------


# trace: FR-001, ADDR-012
def test_register_page_success_redirects_to_login_without_logging_in(web_client):
    assert web_client.get("/register/").status_code == 200
    response = web_client.post(
        "/register/",
        {"email": "web@example.test", "password": "Passw0rd", "password_confirmation": "Passw0rd", "name": "画面"},
        follow=True,
    )
    assert response.redirect_chain[-1][0] == "/login/"
    assert "会員登録が完了しました" in _text(response)
    assert User.objects.get(email="web@example.test").user_type == "buyer"
    assert "_auth_user_id" not in web_client.session  # 自動ログインしない


# trace: FR-001, ADDR-012
def test_register_page_errors_keep_values_except_passwords(web_client, make_user):
    make_user("taken@example.test")
    response = web_client.post(
        "/register/",
        {"email": "taken@example.test", "password": "Secret12", "password_confirmation": "Secret12", "name": "保持名"},
    )
    assert response.status_code == 422
    text = _text(response)
    assert "このメールアドレスは既に登録されています。" in text
    assert 'value="taken@example.test"' in text and "保持名" in text and "Secret12" not in text
    response = web_client.post("/register/", {"email": "", "name": ""})
    assert response.status_code == 400 and "メールアドレスを入力してください。" in _text(response)


# trace: FR-002, NFR-SC-19, ADDR-002
def test_login_page_success_regenerates_session_and_redirects_by_user_type(web_client, buyer, admin):
    session = web_client.session
    session["pre"] = 1
    session.save()
    before = web_client.cookies[settings.SESSION_COOKIE_NAME].value
    response = web_client.post("/login/", {"email": buyer.email, "password": DEFAULT_PASSWORD})
    assert response.status_code == 302 and response["Location"] == "/"
    after = web_client.cookies[settings.SESSION_COOKIE_NAME]
    assert after.value != before and after["httponly"]
    assert AuditLog.objects.get().event_type == "login_success"
    admin_client = Client()
    response = admin_client.post("/login/", {"email": admin.email, "password": DEFAULT_PASSWORD})
    assert response["Location"] == "/manage/orders/"


# trace: FR-002, NFR-SC-19, ADDR-002
def test_pre_login_session_value_is_treated_as_not_logged_in_after_login(web_client, buyer):
    """NFR-SC-19（セッション固定化の防止）：ログイン前に送信していたセッションの値で要求すると、ログイン後も未ログインとして扱う。"""
    session = web_client.session
    session["pre"] = 1
    session.save()
    pre_login_value = web_client.cookies[settings.SESSION_COOKIE_NAME].value
    response = web_client.post("/login/", {"email": buyer.email, "password": DEFAULT_PASSWORD})
    assert response.status_code == 302
    assert web_client.get("/cart/").status_code == 200  # ログインした利用者自身は新しい値でログイン中
    attacker = Client()
    attacker.cookies[settings.SESSION_COOKIE_NAME] = pre_login_value
    _login_redirect(attacker.get("/cart/"), "/cart/")
    _login_redirect(attacker.get("/orders/"), "/orders/")
    assert "_auth_user_id" not in attacker.session


# trace: FR-002, ADDR-002
@pytest.mark.parametrize(
    ("next_value", "expected"),
    [
        ("/orders/", "/orders/"),
        ("//evil.example", "/"),
        ("https://evil.example/", "/"),
        ("/a\\b", "/"),
        ("/x\x00", "/"),
    ],
)
def test_login_page_returns_only_to_same_site_paths(web_client, buyer, next_value, expected):
    response = web_client.post("/login/", {"email": buyer.email, "password": DEFAULT_PASSWORD, "next": next_value})
    assert response["Location"] == expected


# trace: FR-002, ADDR-012
def test_login_page_failure_shows_message_and_keeps_email(web_client, buyer):
    response = web_client.post("/login/", {"email": buyer.email, "password": "Wrong123"})
    assert response.status_code == 401
    text = _text(response)
    assert "メールアドレスまたはパスワードが正しくありません。" in text and f'value="{buyer.email}"' in text
    assert web_client.get("/login/?required=1&next=/cart/").status_code == 200


# trace: FR-002, ADDR-004
def test_login_resubmission_with_same_token_does_not_authenticate_again(web_client, buyer):
    """ADDR-004 DD-013・DD-016：使用済みトークンのログインは照合・監査ログを行わず先着の結果を通知する。"""
    token = issue_token()
    first = web_client.post("/login/", {"email": buyer.email, "password": DEFAULT_PASSWORD, "submit_token": token})
    second = web_client.post("/login/", {"email": "", "password": "", "submit_token": token})
    assert first["Location"] == second["Location"] == "/"
    assert AuditLog.objects.filter(event_type="login_success").count() == 1
    failed_token = issue_token()
    Client().post("/login/", {"email": buyer.email, "password": "Wrong123", "submit_token": failed_token})
    again = Client().post("/login/", {"email": buyer.email, "password": DEFAULT_PASSWORD, "submit_token": failed_token})
    assert again.status_code == 401  # 先着の結果（認証失敗）を正しい入力でも通知する
    assert AuditLog.objects.filter(event_type="login_failure").count() == 1


# trace: FR-003, ADDR-002
def test_logout_page_ends_session_and_records_audit(login_web, buyer):
    client = login_web(buyer)
    response = client.post("/logout/", {"submit_token": issue_token()}, follow=True)
    assert response.redirect_chain[0][0] == "/"
    assert "ログアウトしました。" in _text(response)
    assert "_auth_user_id" not in client.session
    assert AuditLog.objects.get().event_type == "logout"
    assert client.get("/logout/").status_code == 405  # 更新操作は POST だけ
    anonymous = Client().post("/logout/")
    assert anonymous.status_code == 302 and anonymous["Location"].startswith("/login/")


# ---------------------------------------------------------------------------
# 無操作30分の切断（NFR-SC-09、ADDR-002 DD-004）
# ---------------------------------------------------------------------------


# trace: NFR-SC-09, FR-020, ADDR-002
def test_idle_29_minutes_continues_and_30_minutes_disconnects(login_web, buyer, freeze):
    client = login_web(buyer)
    freeze(NOW)
    assert client.get("/cart/").status_code == 200
    freeze(NOW + timedelta(minutes=29, seconds=59))
    assert client.get("/cart/").status_code == 200
    freeze(NOW + timedelta(minutes=29, seconds=59) + timedelta(minutes=30))
    _login_redirect(client.get("/cart/"), "/cart/")
    assert "_auth_user_id" not in client.session


# ---------------------------------------------------------------------------
# 認証・権限の画面遷移（CMN-02・03、NFR-SC-03）
# ---------------------------------------------------------------------------


# trace: NFR-SC-03, ADDR-002, ADDR-012
@pytest.mark.parametrize(
    "path",
    [
        "/cart/",
        "/checkout/",
        "/orders/",
        "/orders/1/",
        "/orders/1/complete/",
        "/orders/1/payment/",
        "/manage/orders/",
        "/manage/orders/1/",
        "/manage/stock-units/",
    ],
)
def test_pages_requiring_login_redirect_visitors_to_login(web_client, path):
    _login_redirect(web_client.get(path), path)
    assert not Cart.objects.exists()


# trace: NFR-SC-03, ADDR-012
def test_role_mismatch_shows_permission_error_page(login_web, buyer, admin):
    buyer_client, admin_client = login_web(buyer), login_web(admin)
    for path in ("/manage/orders/", "/manage/orders/1/", "/manage/stock-units/"):
        response = buyer_client.get(path)
        assert response.status_code == 403 and "この画面・操作を利用する権限がありません" in _text(response)
    for path in ("/cart/", "/checkout/", "/orders/", "/orders/1/"):
        assert admin_client.get(path).status_code == 403
    for path in ("/cart/items/add/", "/cart/coupon/apply/", "/orders/1/cancel/"):
        assert admin_client.post(path, {"stock_unit_id": "1", "quantity": "1"}).status_code == 403
    assert buyer_client.post("/manage/orders/1/ship/").status_code == 403
    assert not Cart.objects.filter(buyer=admin).exists()


# trace: FR-033, NFR-SC-03, ADDR-012
def test_other_buyers_order_page_is_not_found(login_web, buyer, other_buyer, catalog, make_order):
    order = make_order(other_buyer, [(catalog.stock_unit(), 1)])
    client = login_web(buyer)
    for path in (f"/orders/{order.pk}/", f"/orders/{order.pk}/complete/", f"/orders/{order.pk}/payment/", "/orders/x/"):
        response = client.get(path)
        assert response.status_code == 404 and "お探しのページ・データが見つかりません" in _text(response)
    assert client.get("/no-such-page/").status_code == 404


# ---------------------------------------------------------------------------
# XSS・CSRF（NFR-SC-05、VUL-05・VUL-06）
# ---------------------------------------------------------------------------


# trace: NFR-SC-05, FR-011, FR-012, FR-042, ADDR-002
def test_values_with_script_are_escaped_on_all_pages(login_web, make_user, admin, catalog, make_order):
    product = catalog.product(XSS, description=XSS)
    unit = catalog.stock_unit(product, variant_name=XSS)
    evil = make_user(name=XSS)
    order = make_order(evil, [(unit, 1)])
    order.shipping_address.recipient_name = XSS
    order.shipping_address.save()
    pages = [
        (Client(), "/"),
        (Client(), f"/products/{product.pk}/"),
        (login_web(evil), "/cart/"),
        (login_web(evil), f"/orders/{order.pk}/"),
        (login_web(admin), f"/manage/orders/{order.pk}/"),
        (login_web(admin), "/manage/orders/"),
        (login_web(admin), "/manage/stock-units/"),
        (Client(), f"/?keyword={XSS}"),
    ]
    for client, path in pages:
        text = _text(client.get(path))
        assert XSS not in text, path
    assert "&lt;script&gt;" in _text(Client().get("/"))


# trace: NFR-SC-05, FR-021, ADDR-002
@pytest.mark.parametrize(
    ("path", "data"),
    [
        ("/cart/items/add/", {"stock_unit_id": "1", "quantity": "1"}),
        ("/cart/coupon/remove/", {}),
        ("/checkout/", ADDRESS),
        ("/logout/", {}),
        ("/login/", {"email": "a@b.c", "password": "x"}),
        ("/register/", {"email": "a@b.c"}),
    ],
)
def test_post_without_csrf_token_is_rejected(login_web, buyer, catalog, path, data):
    """VUL-06：他のサイトから送信させた更新要求（CSRF トークンなし）は拒否され、データは変化しない。"""
    client = login_web(buyer, enforce_csrf=True)
    catalog.stock_unit()
    response = client.post(path, data)
    assert response.status_code == 403
    assert "権限がありません" in _text(response)
    assert not CartItem.objects.exists() and not Order.objects.exists()
    assert not AuditLog.objects.exists() and User.objects.count() == 1


# trace: NFR-SC-05, FR-031, FR-034, FR-043, FR-044, FR-045, ADDR-002
@pytest.mark.parametrize(
    ("actor", "action", "status", "data"),
    [
        ("admin", "manage/orders/{pk}/ship", "paid", {"tracking_number": "TRK-1"}),
        ("admin", "manage/orders/{pk}/deliver", "shipped", {}),
        ("admin", "manage/orders/{pk}/cancel", "accepted", {}),
        ("buyer", "orders/{pk}/payment", "accepted", {"mock_instruction": "approved"}),
        ("buyer", "orders/{pk}/cancel", "accepted", {}),
    ],
    ids=["admin-ship", "admin-deliver", "admin-cancel", "buyer-payment", "buyer-cancel"],
)
def test_order_operations_without_csrf_token_are_rejected(
    login_web, buyer, admin, catalog, make_order, actor, action, status, data
):
    """VUL-06：管理者の出荷登録・配達完了・キャンセル、購入者の支払・キャンセルも CSRF トークンなしでは拒否する。

    いずれも注文の状態・状態履歴・決済記録・在庫数量は変化しない。
    """
    unit = catalog.stock_unit(stock=5)
    order = make_order(buyer, [(unit, 2)], status=status)
    client = login_web(admin if actor == "admin" else buyer, enforce_csrf=True)
    response = client.post("/" + action.format(pk=order.pk) + "/", {**data, "submit_token": issue_token()})
    assert response.status_code == 403
    assert "権限がありません" in _text(response)
    order.refresh_from_db()
    assert order.status == status
    assert (order.shipped_at is None) == (status in ("accepted", "paid"))
    assert order.delivered_at is None and order.cancelled_at is None
    assert order.status_history.count() == 1
    assert not PaymentRecord.objects.exists()
    assert StockUnit.objects.get(pk=unit.pk).stock_quantity == 5


# trace: NFR-SC-05, ADDR-002
def test_session_cookie_is_httponly_and_csrf_check_passes_with_token(login_web, buyer, catalog):
    client = login_web(buyer, enforce_csrf=True)
    unit = catalog.stock_unit(stock=5)
    page = client.get(f"/products/{unit.product_id}/")
    token = client.cookies[settings.CSRF_COOKIE_NAME].value
    response = client.post(
        "/cart/items/add/",
        {
            "product_id": str(unit.product_id),
            "stock_unit_id": str(unit.pk),
            "quantity": "1",
            "csrfmiddlewaretoken": token,
        },
    )
    assert page.status_code == 200 and response.status_code == 302
    assert CartItem.objects.get().quantity == 1


# trace: NFR-SC-05, FR-021, ADDR-001
@pytest.mark.parametrize(
    "path",
    ["/cart/items/add/", "/cart/coupon/apply/", "/cart/coupon/remove/", "/orders/1/cancel/", "/manage/orders/1/ship/"],
)
def test_update_operations_cannot_be_executed_by_get(login_web, buyer, path):
    assert login_web(buyer).get(path).status_code == 405


# ---------------------------------------------------------------------------
# 商品一覧・詳細（SCR-001・SCR-002）と表示ごとのカート作成（ADDR-001 DD-015）
# ---------------------------------------------------------------------------


# trace: FR-010, FR-011, ADDR-012
def test_product_list_page_shows_results_and_errors(web_client, catalog):
    category = catalog.category("食器")
    product = catalog.product("湯呑", categories=(category,))
    catalog.stock_unit(product, price=1000)
    text = _text(web_client.get(f"/?category_id={category.pk}&sort=price_asc"))
    assert "湯呑" in text and "1,100円（税込）／1,000円（税抜）" in text and "食器" in text
    response = web_client.get("/?keyword=" + "a" * 51)
    assert response.status_code == 400
    response = web_client.get("/?sort=bad&page=0")
    assert response.status_code == 400 and "検索条件に誤りがあります" in _text(response)


# trace: FR-012, ADDR-012
def test_product_detail_page_hides_cart_for_admin_and_404_for_hidden(web_client, login_web, admin, catalog):
    product = catalog.product("ポット")
    catalog.stock_unit(product, stock=2)
    visitor = _text(web_client.get(f"/products/{product.pk}/"))
    assert 'action="/cart/items/add/"' in visitor
    admin_view = _text(login_web(admin).get(f"/products/{product.pk}/"))
    assert 'action="/cart/items/add/"' not in admin_view
    sold_out = catalog.product("完売")
    catalog.stock_unit(sold_out, stock=0)
    assert 'action="/cart/items/add/"' not in _text(web_client.get(f"/products/{sold_out.pk}/"))
    hidden = catalog.product(is_public=False)
    catalog.stock_unit(hidden)
    assert web_client.get(f"/products/{hidden.pk}/").status_code == 404


# trace: FR-020, ADDR-001
def test_buyer_page_view_creates_cart_once_and_shows_count(login_web, web_client, buyer, admin, catalog):
    client = login_web(buyer)
    assert "カート（0点）" in _text(client.get("/"))
    client.get("/")
    assert Cart.objects.filter(buyer=buyer, status="active").count() == 1
    web_client.get("/")
    login_web(admin).get("/")
    assert Cart.objects.count() == 1  # 来訪者・管理者では作成しない


# ---------------------------------------------------------------------------
# カート画面（SCR-005、FR-020〜FR-025）
# ---------------------------------------------------------------------------


# trace: FR-021, ADDR-004, ADDR-012
def test_add_to_cart_page_flow_and_double_submit(login_web, buyer, catalog):
    client = login_web(buyer)
    unit = catalog.stock_unit(stock=3, variant_name="Mサイズ")
    token = issue_token()
    data = {"product_id": str(unit.product_id), "stock_unit_id": str(unit.pk), "quantity": " 2 ", "submit_token": token}
    response = client.post("/cart/items/add/", data, follow=True)
    assert response.redirect_chain[0][0] == f"/products/{unit.product_id}/"
    assert "カートに追加しました（Mサイズ、2個）。" in _text(response)
    client.post("/cart/items/add/", data)  # 同じトークンの再送信は加算しない（CMN-22）
    assert CartItem.objects.get().quantity == 2
    response = client.post("/cart/items/add/", {**data, "submit_token": issue_token()})
    assert response.status_code == 422 and "在庫が不足しています（現在の在庫数量：3個）。" in _text(response)
    response = client.post("/cart/items/add/", {**data, "quantity": "0", "submit_token": issue_token()})
    assert response.status_code == 400 and "数量は1以上の整数で入力してください。" in _text(response)
    response = client.post("/cart/items/add/", {"product_id": "abc", "stock_unit_id": "99999", "quantity": "1"})
    assert response.status_code == 404


# trace: FR-021, ADDR-002
def test_add_to_cart_requires_login_and_returns_to_detail(web_client, catalog):
    unit = catalog.stock_unit()
    response = web_client.post(
        "/cart/items/add/", {"product_id": str(unit.product_id), "stock_unit_id": str(unit.pk), "quantity": "1"}
    )
    _login_redirect(response, f"/products/{unit.product_id}/")


# trace: FR-020, FR-022, FR-023, FR-024, FR-025, ADDR-012
def test_cart_page_operations(login_web, buyer, catalog, make_cart, make_coupon):
    client = login_web(buyer)
    unit = catalog.stock_unit(price=6000, stock=1, variant_name="大")
    make_coupon("WELCOME", discount_value=1000, name="ようこそ")
    cart = make_cart(buyer, [(unit, 2)])
    item = CartItem.objects.get(cart=cart)
    page = _text(client.get("/cart/"))
    assert "大" in page and "在庫" in page
    response = client.post(f"/cart/items/{item.pk}/quantity/", {"quantity": "1"}, follow=True)
    assert "数量を変更しました。" in _text(response)
    response = client.post(f"/cart/items/{item.pk}/quantity/", {"quantity": "11"})
    assert (
        response.status_code == 422
        and "同じ規格は1注文につき10個までです（現在のカート内数量：1個）。" in _text(response)
    )
    response = client.post("/cart/coupon/apply/", {"coupon_code": "@@"})
    assert response.status_code == 400 and 'value="@@"' in _text(response)  # 入力値を保持して再表示（CMN-17）
    assert "クーポンコード：クーポンコードは英字・数字・ハイフンの20文字以内で入力してください。" in _text(response)
    response = client.post("/cart/coupon/apply/", {"coupon_code": "welcome"}, follow=True)
    assert "クーポンを適用しました。" in _text(response) and "1,000円引き" in _text(response)
    response = client.post("/cart/coupon/apply/", {"coupon_code": "OTHER"})
    assert response.status_code == 422 and "クーポンは1注文につき1枚までです" in _text(response)
    response = client.post("/cart/coupon/remove/", follow=True)
    assert "クーポンを解除しました。" in _text(response)
    response = client.post(f"/cart/items/{item.pk}/delete/", follow=True)
    assert "カートから削除しました。" in _text(response)
    assert client.post(f"/cart/items/{item.pk}/delete/").status_code == 404


# ---------------------------------------------------------------------------
# 注文手続き・注文完了・支払・注文履歴・注文詳細（SCR-006〜SCR-010）
# ---------------------------------------------------------------------------


# trace: FR-022, ADDR-001, ADDR-012
@pytest.mark.parametrize("quantity", ["0", "x", ""])
def test_cart_page_quantity_input_error_shows_item_reason(login_web, buyer, catalog, make_cart, quantity):
    """E-022-03 の通知内容は「項目名（数量）と理由」（6.10.7）。
    AC-UC-004-012 要求6：数量について不備の理由が通知される。

    画面と Web API は同じ通知内容に従う（CMN-34、ADDR-001 INV-001）。入力値を保持して再表示する（CMN-17）。
    """
    client = login_web(buyer)
    unit = catalog.stock_unit(stock=5)
    item = CartItem.objects.get(cart=make_cart(buyer, [(unit, 2)]))
    response = client.post(f"/cart/items/{item.pk}/quantity/", {"quantity": quantity})
    assert response.status_code == 400
    text = _text(response)
    assert "数量は1以上の整数で入力してください。" in text
    assert CartItem.objects.get(pk=item.pk).quantity == 2


# trace: FR-030, FR-033, ADDR-012
def test_checkout_flow(login_web, buyer, catalog, make_cart):
    client = login_web(buyer)
    response = client.get("/checkout/", follow=True)
    assert response.redirect_chain[0][0] == "/cart/" and "カートに商品がありません。" in _text(response)
    unit = catalog.stock_unit(price=1000, stock=2)
    from carts import services as cart_services

    cart_services.add_item(buyer, unit.pk, 1)  # 表示時に作成された利用中カートへ追加する
    page = client.get("/checkout/")
    assert page.status_code == 200 and buyer.name in _text(page)
    response = client.post("/checkout/", {**ADDRESS, "postal_code": "12-34", "address_line1": "保持住所"})
    assert response.status_code == 400 and "保持住所" in _text(response)
    assert "郵便番号は「1234567」または「123-4567」の形式で入力してください。" in _text(response)
    response = client.post("/checkout/", ADDRESS)
    order = Order.objects.get()
    assert response.status_code == 302 and response["Location"] == f"/orders/{order.pk}/complete/"
    complete = _text(client.get(response["Location"]))
    assert order.order_number in complete
    response = client.post("/checkout/", ADDRESS, follow=True)  # 2回目はカートが空（業務エラー）
    assert response.redirect_chain[0][0] == "/cart/"
    assert Order.objects.count() == 1


# trace: FR-030, ADDR-012
def test_checkout_business_error_keeps_address(login_web, buyer, catalog, make_cart):
    client = login_web(buyer)
    unit = catalog.stock_unit(stock=0)
    make_cart(buyer, [(unit, 1)])
    response = client.post("/checkout/", {**ADDRESS, "recipient_name": "保持氏名"})
    assert response.status_code == 422
    assert "在庫が不足している商品があります" in _text(response) and "保持氏名" in _text(response)


# trace: FR-031, NFR-LG-05, ADDR-004, ADDR-012
def test_payment_page_flow(login_web, buyer, catalog, make_order):
    client = login_web(buyer)
    order = make_order(buyer, [(catalog.stock_unit(), 1)])
    page = _text(client.get(f"/orders/{order.pk}/payment/"))
    names = set(re.findall(r'name="([^"]+)"', page.split('action="/orders/')[1].split("</form>")[0]))
    assert names == {"csrfmiddlewaretoken", "submit_token", "mock_instruction"}  # カード情報の入力項目なし
    response = client.post(f"/orders/{order.pk}/payment/", {"mock_instruction": "declined"})
    assert response.status_code == 422 and "決済が承認されませんでした。" in _text(response)
    response = client.post(f"/orders/{order.pk}/payment/", {"mock_instruction": "maybe"})
    assert response.status_code == 400
    token = issue_token()
    response = client.post(
        f"/orders/{order.pk}/payment/", {"mock_instruction": "approved", "submit_token": token}, follow=True
    )
    assert response.redirect_chain[0][0] == f"/orders/{order.pk}/" and "支払が完了しました。" in _text(response)
    client.post(f"/orders/{order.pk}/payment/", {"mock_instruction": "approved", "submit_token": token})
    assert PaymentRecord.objects.filter(order=order, result="approved").count() == 1  # 決済要求は1回分だけ
    response = client.get(f"/orders/{order.pk}/payment/", follow=True)
    assert "この注文は支払できません（現在の状態：支払済）。" in _text(response)
    response = client.post(f"/orders/{order.pk}/payment/", {"mock_instruction": "approved"}, follow=True)
    assert "この注文は支払できません" in _text(response)


# trace: FR-032, FR-033, FR-034, ADDR-012
def test_history_detail_and_cancel_pages(login_web, buyer, catalog, make_order):
    client = login_web(buyer)
    unit = catalog.stock_unit(stock=1)
    order = make_order(buyer, [(unit, 2)], status="paid")
    history = _text(client.get("/orders/"))
    assert order.order_number in history and "支払済" in history
    assert client.get("/orders/?page=0").status_code == 400
    detail = _text(client.get(f"/orders/{order.pk}/"))
    assert order.order_number in detail and "MOCK-" not in detail
    response = client.post(f"/orders/{order.pk}/cancel/", follow=True)
    assert "注文をキャンセルしました。返金は当社が5営業日以内に行います。" in _text(response)
    response = client.post(f"/orders/{order.pk}/cancel/", follow=True)
    assert "この注文はキャンセルできません（現在の状態：キャンセル済）。" in _text(response)


# ---------------------------------------------------------------------------
# 管理画面（SCR-101〜SCR-103、FR-040〜FR-045）
# ---------------------------------------------------------------------------


# trace: FR-040, ADDR-012
def test_stock_unit_admin_page(login_web, admin, catalog):
    client = login_web(admin)
    catalog.stock_unit(catalog.product(is_public=False), sku="HID-1", stock=0)
    text = _text(client.get("/manage/stock-units/?low_stock_only=true"))
    assert "HID-1" in text and "非公開" in text
    response = client.get("/manage/stock-units/?supplier_code=NOPE&page=2")
    assert response.status_code == 400 and "指定した仕入先は登録されていません。" in _text(response)


# trace: FR-041, FR-042, FR-043, FR-044, FR-045, ADDR-004, ADDR-012
def test_admin_order_pages(login_web, admin, buyer, catalog, make_order):
    client = login_web(admin)
    paid = make_order(buyer, [(catalog.stock_unit(), 1)], status="paid")
    accepted_unit = catalog.stock_unit(stock=8)
    accepted = make_order(buyer, [(accepted_unit, 2)])
    listing = client.get("/manage/orders/?status=paid")
    assert paid.order_number in _text(listing) and accepted.order_number not in _text(listing)
    assert client.get("/manage/orders/?order_date_from=bad").status_code == 400
    detail = _text(client.get(f"/manage/orders/{paid.pk}/"))
    assert "/manage/orders/?status=paid" in detail and buyer.email in detail  # 検索条件を引き継いで戻る
    response = client.post(f"/manage/orders/{paid.pk}/ship/", {"tracking_number": "bad_no"})
    assert response.status_code == 400 and 'value="bad_no"' in _text(response)
    token = issue_token()
    response = client.post(
        f"/manage/orders/{paid.pk}/ship/", {"tracking_number": "TRK-9", "submit_token": token}, follow=True
    )
    assert "出荷登録しました。" in _text(response)
    response = client.post(
        f"/manage/orders/{paid.pk}/ship/", {"tracking_number": "TRK-9", "submit_token": token}, follow=True
    )
    assert "この注文は出荷登録できません（現在の状態：出荷済）。" in _text(response)  # 使用済みは再判定の結果
    response = client.post(f"/manage/orders/{paid.pk}/deliver/", follow=True)
    assert "配達完了を登録しました。" in _text(response)
    response = client.post(f"/manage/orders/{accepted.pk}/cancel/", follow=True)
    assert "注文をキャンセルしました。在庫を戻しました。" in _text(response)
    accepted_unit.refresh_from_db()
    assert accepted_unit.stock_quantity == 10  # AC-UC-012-001：注文受付の管理者キャンセルで在庫数量 8→10
    response = client.post(f"/manage/orders/{accepted.pk}/cancel/", follow=True)
    assert "この注文はキャンセルできません（現在の状態：キャンセル済）。" in _text(response)
    accepted_unit.refresh_from_db()
    assert accepted_unit.stock_quantity == 10  # 連続操作の2回目以降で在庫を2回戻さない
    assert client.get("/manage/orders/999999/").status_code == 404


# ---------------------------------------------------------------------------
# 外部への依存（NFR-EN-05）
# ---------------------------------------------------------------------------


# trace: NFR-EN-05
def test_templates_do_not_reference_external_urls():
    """NFR-EN-05：画面は外部 CDN に依存しない（テンプレートが外部の URL を参照しない）。"""
    app_dir = Path(settings.BASE_DIR)
    offenders = []
    for template in app_dir.glob("*/templates/**/*.html"):
        text = template.read_text(encoding="utf-8")
        if re.search(r"""(src|href|action)\s*=\s*["']?\s*(https?:)?//""", text, re.IGNORECASE):
            offenders.append(template.name)
    assert offenders == []
