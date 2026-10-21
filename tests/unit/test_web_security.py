# trace: FR-003, FR-021, FR-022, FR-023, FR-024, FR-025, FR-030, FR-033, FR-034, FR-042
# trace: FR-043, FR-044, FR-045, NFR-SC-05, NFR-SC-10, NFR-SC-12, ADDR-006, ADDR-010, ADDR-011
"""画面の CSRF 対策と HTML エスケープ（NFR-SC-05／VUL-05・VUL-06）の単体テスト。

期待結果は非機能要件 NFR-SC-05（画面に出力する全ての値を HTML エスケープし、テンプレートの
自動エスケープを無効化しない。Cookie のログインセッションで認証する全ての更新要求で CSRF
対策用トークンを検証し、トークンが無い・一致しない要求を拒否する）、VUL-05（XSS）、
VUL-06（CSRF。更新操作は GET 以外のメソッドに限る）、NFR-SC-10（内部情報の非表示）、
ADDR-006 DD-005（CSRFミドルウェアを有効にし、全フォームにトークンを埋め込む。更新操作を
GETで提供しない）・INV-002（個別の画面・ビューで CSRF 検証を無効化しない）・INV-003 から導出する。

Django のテストクライアントは既定で CSRF 検証を省略するため、CSRF の検証が必要なテストでは
``enforce_csrf_checks=True`` のクライアントを用いて本番と同じ経路で確かめる。
DBは pytest-django が作成する使い捨てのテストDBだけを使用する。
"""

from __future__ import annotations

import pytest
from _helpers import (
    add_cart_line,
    make_coupon,
    make_item,
    make_open_cart,
    make_stock_unit,
    make_user,
    shipping_input,
)
from carts import services as cart_services
from carts.models import Cart
from django.conf import settings
from django.test import Client, RequestFactory
from orders import services as order_services
from web import support
from web.urls import urlpatterns as web_urlpatterns

pytestmark = pytest.mark.django_db

SCRIPT_VALUE = "<script>alert('xss')</script>"
ESCAPED_VALUE = "&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;"

POST_ONLY_SCREEN_PATHS = [
    "/logout/",
    "/cart/lines/add/",
    "/cart/lines/1/update/",
    "/cart/lines/1/delete/",
    "/cart/coupon/apply/",
    "/cart/coupon/remove/",
    "/orders/1/cancel/",
    "/admin-console/orders/1/ship/",
    "/admin-console/orders/1/deliver/",
    "/admin-console/orders/1/cancel/",
]


# trace: NFR-SC-05, ADDR-006
def csrf_checking_client(user) -> Client:
    """CSRF 検証を行う画面クライアントでログインセッションを開始する（テスト補助）。"""
    client = Client(enforce_csrf_checks=True)
    session = client.session
    session[support.SESSION_USER_ID] = user.pk
    session.save()
    return client


# trace: FR-024
def prepare_cart_with_coupon(user, *, code: str) -> None:
    """クーポン適用の対象となるカートとクーポンを用意する（テスト補助）。"""
    cart = make_open_cart(user)
    add_cart_line(cart, make_stock_unit(make_item(name="CSRF試験商品"), price=6000, quantity=5))
    make_coupon(code=code, discount_value=1000, min_spend=0)


# trace: FR-030
def place_order_with_script_values(user):
    """氏名・商品名・配送先に script タグを含む注文を1件作成する（テスト補助）。"""
    unit = make_stock_unit(make_item(name=f"{SCRIPT_VALUE}商品"), price=3000, quantity=10)
    cart_services.add_line(user, {"stock_unit_id": unit.pk, "quantity": 1})
    return order_services.checkout(user, shipping_input(recipient_name=SCRIPT_VALUE))


# trace: NFR-SC-05, ADDR-006
def test_screen_update_without_csrf_token_is_rejected(buyer):
    """NFR-SC-05／VUL-06：CSRF 対策用トークンの無い更新要求を拒否し、データを変更しない。"""
    prepare_cart_with_coupon(buyer, code="CSRF-1000")
    client = csrf_checking_client(buyer)

    response = client.post("/cart/coupon/apply/", {"code": "CSRF-1000"})

    assert response.status_code == 403
    assert Cart.objects.get(user=buyer, status="open").coupon_id is None


# trace: NFR-SC-05, ADDR-006
def test_screen_update_with_mismatched_csrf_token_is_rejected(buyer):
    """NFR-SC-05：CSRF 対策用トークンが一致しない更新要求も拒否する。"""
    prepare_cart_with_coupon(buyer, code="CSRF-MISMATCH")
    client = csrf_checking_client(buyer)
    client.get("/cart/")

    response = client.post(
        "/cart/coupon/apply/", {"code": "CSRF-MISMATCH", "csrfmiddlewaretoken": "invalid-token-value"}
    )

    assert response.status_code == 403
    assert Cart.objects.get(user=buyer, status="open").coupon_id is None


# trace: NFR-SC-05, FR-024
def test_screen_update_with_valid_csrf_token_is_accepted(buyer):
    """ADDR-006 DD-005：全フォームへ埋め込んだトークンを伴う更新要求は受け付ける。"""
    prepare_cart_with_coupon(buyer, code="CSRF-VALID")
    client = csrf_checking_client(buyer)
    page = client.get("/cart/")
    token = client.cookies["csrftoken"].value

    response = client.post("/cart/coupon/apply/", {"code": "CSRF-VALID", "csrfmiddlewaretoken": token})

    assert "csrfmiddlewaretoken" in page.content.decode()
    assert response.status_code == 302
    assert Cart.objects.get(user=buyer, status="open").coupon.code == "CSRF-VALID"


# trace: NFR-SC-10, ADDR-006
def test_csrf_rejection_does_not_expose_internal_details(buyer):
    """ADDR-006（拒否時の振る舞い）／NFR-SC-10：拒否の応答に内部情報を含めない。"""
    prepare_cart_with_coupon(buyer, code="CSRF-HIDE")
    client = csrf_checking_client(buyer)

    body = client.post("/cart/coupon/apply/", {"code": "CSRF-HIDE"}).content.decode()

    assert "Traceback" not in body
    assert "SELECT" not in body
    assert "config.settings" not in body


# trace: NFR-SC-05, ADDR-006
def test_no_screen_view_disables_csrf_protection():
    """ADDR-006 INV-002：個別の画面・ビューで CSRF 検証を無効化しない。"""
    exempted = [
        pattern.callback.__name__
        for pattern in web_urlpatterns
        if getattr(pattern.callback, "csrf_exempt", False)
    ]

    assert exempted == []
    assert "django.middleware.csrf.CsrfViewMiddleware" in settings.MIDDLEWARE


# trace: NFR-SC-05, ADDR-006
@pytest.mark.parametrize("path", POST_ONLY_SCREEN_PATHS)
def test_update_screens_do_not_accept_get(path, buyer):
    """VUL-06／ADDR-006 INV-003：更新操作は GET で提供しない。"""
    client = csrf_checking_client(buyer)

    assert client.get(path).status_code == 405


# trace: NFR-SC-05, FR-033
def test_buyer_order_detail_escapes_script_tags(buyer, logged_in_screen_client):
    """NFR-SC-05／VUL-05：商品名・配送先に script タグを含む値を登録しても画面ではエスケープして出力する。"""
    order = place_order_with_script_values(buyer)
    client = logged_in_screen_client(buyer)

    body = client.get(f"/orders/{order.pk}/").content.decode()

    assert SCRIPT_VALUE not in body
    assert body.count(ESCAPED_VALUE) >= 2


# trace: NFR-SC-05, FR-042
def test_admin_order_detail_escapes_script_tags(admin_user, logged_in_screen_client):
    """NFR-SC-05／VUL-05：購入者が入力した氏名・配送先を管理者画面でもエスケープして出力する。"""
    scripted_buyer = make_user(email="xss-buyer@example.test", full_name=SCRIPT_VALUE)
    order = place_order_with_script_values(scripted_buyer)
    client = logged_in_screen_client(admin_user)

    body = client.get(f"/admin-console/orders/{order.pk}/").content.decode()

    assert SCRIPT_VALUE not in body
    assert body.count(ESCAPED_VALUE) >= 3


# trace: NFR-SC-05, ADDR-010
def test_templates_do_not_disable_auto_escaping():
    """NFR-SC-05：テンプレートの自動エスケープを無効化しない。"""
    template_root = settings.TEMPLATES[0]["DIRS"][0]
    disabled = [
        str(path)
        for path in sorted(template_root.rglob("*.html"))
        if "autoescape off" in path.read_text(encoding="utf-8")
        or "|safe" in path.read_text(encoding="utf-8")
        or "safeseq" in path.read_text(encoding="utf-8")
    ]

    assert disabled == []


# trace: NFR-SC-12, ADDR-006
def test_remember_next_path_ignores_protocol_relative_path():
    """ADDR-006 INV-004：復帰先に外部URL（プロトコル相対パス）を受け付けない。"""
    request = RequestFactory().get("/items/")
    request.path = "//evil.example.test/items/"
    request.session = {}

    support.remember_next_path(request)

    assert support.SESSION_NEXT_PATH not in request.session


# trace: NFR-SC-05
def test_api_responses_use_json_content_type(api_client, buyer, token_for):
    """VUL-05：API の応答の Content-Type は application/json とする。"""
    response = api_client.get(
        "/api/cart", HTTP_AUTHORIZATION=f"Bearer {token_for(buyer)}"
    )

    assert response.status_code == 200
    assert response["Content-Type"].startswith("application/json")
