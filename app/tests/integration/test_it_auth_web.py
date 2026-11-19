# trace: FR-001, FR-002, FR-003, FR-020, FR-021, FR-040, FR-041, ADDR-001, ADDR-002, ADDR-004, ADDR-011, ADDR-012
"""結合試験：会員・認証の画面（画面→CSRF→送信トークン→セッション→業務処理→DB）。

IT-007〜IT-010（AI INITIAL）。期待結果は FR-001〜FR-003、CMN-02/03/10、UI-16〜UI-20、MSG-02、
NFR-SC-05/09/19、ADDR-002（セッション・CSRF）・ADDR-004（送信トークン）・ADDR-012 から導出する。
画面クライアントは CSRF 検証を有効にし、フォームの CSRF トークン・送信トークンを送る。
"""

from datetime import timedelta
from urllib.parse import parse_qs, urlparse

import pytest

from tests.integration._helpers import PASSWORD, form_fields, jst, text

pytestmark = pytest.mark.django_db


# trace: FR-002, ADDR-002, ADDR-012
def _web_login(client, email, password=PASSWORD, login_page="/login/"):
    page = client.get(login_page)
    assert page.status_code == 200
    fields = form_fields(text(page), "/login/")
    fields.update({"email": email, "password": password})
    return client.post("/login/", fields)


# trace: FR-001, FR-002, FR-003, ADDR-002, ADDR-004, ADDR-012
def test_it_007_web_register_login_logout(web):
    """IT-007 画面の会員登録→ログイン→ログアウト（CSRF 有効）。"""
    from accounts.models import User
    from audit.models import AuditLog

    client = web()
    page = client.get("/register/")
    fields = form_fields(text(page), "/register/")
    assert fields.get("csrfmiddlewaretoken") and fields.get("submit_token")
    fields.update(
        {"email": "WebBuyer@Example.test", "password": PASSWORD, "password_confirmation": PASSWORD, "name": "画面 花子"}
    )
    done = client.post("/register/", fields)
    assert done.status_code == 302 and done["Location"] == "/login/"
    user = User.objects.get(email="webbuyer@example.test")
    assert user.user_type == "buyer"

    login_page = client.get("/login/")
    assert "会員登録が完了しました" in text(login_page)
    fields = form_fields(text(login_page), "/login/")
    fields.update({"email": "webbuyer@example.test", "password": PASSWORD})
    logged = client.post("/login/", fields)
    assert logged.status_code == 302 and logged["Location"] == "/"
    cookie = logged.cookies["sessionid"]
    assert cookie["httponly"]
    assert cookie["samesite"] == "Lax"

    home = client.get("/")
    html = text(home)
    assert "画面 花子さん" in html
    assert "カート（0点）" in html

    fields = form_fields(html, "/logout/")
    out = client.post("/logout/", fields)
    assert out.status_code == 302 and out["Location"] == "/"
    assert "ログアウトしました。" in text(client.get("/"))
    assert AuditLog.objects.filter(event_type="logout", target_user_id=user.pk, result="success").count() == 1

    protected = client.get("/cart/")
    assert protected.status_code == 302
    location = urlparse(protected["Location"])
    assert location.path == "/login/" and parse_qs(location.query).get("required") == ["1"]


# trace: FR-002, FR-020, FR-040, FR-041, ADDR-002, ADDR-012
def test_it_008_web_return_to_original_and_permission(web, buyer, admin):
    """IT-008 画面の保護画面→ログイン→元画面への復帰、利用者区分別の遷移先と権限なし。"""
    client = web()
    first = client.get("/cart/")
    assert first.status_code == 302
    location = urlparse(first["Location"])
    query = parse_qs(location.query)
    assert location.path == "/login/" and query["required"] == ["1"] and query["next"] == ["/cart/"]

    login_page = client.get(first["Location"])
    html = text(login_page)
    assert "ログインが必要です" in html
    fields = form_fields(html, "/login/")
    assert fields["next"] == "/cart/"
    fields.update({"email": buyer.email, "password": PASSWORD})
    back = client.post("/login/", fields)
    assert back.status_code == 302 and back["Location"] == "/cart/"
    assert client.get("/cart/").status_code == 200

    denied = client.get("/manage/stock-units/")
    assert denied.status_code == 403
    assert "権限がありません" in text(denied)

    admin_client = web()
    admin_login = _web_login(admin_client, admin.email)
    assert admin_login.status_code == 302 and admin_login["Location"] == "/manage/orders/"
    admin_cart = admin_client.get("/cart/")
    assert admin_cart.status_code == 403
    assert "権限がありません" in text(admin_cart)


# trace: FR-002, FR-020, ADDR-002, ADDR-011
def test_it_009_web_idle_timeout_30min(web, buyer, set_state):
    """IT-009 画面のログイン状態の無操作30分タイムアウト。"""
    start = jst(2027, 4, 10, 10, 0, 0)
    set_state(fixed_now=start)
    client = web()
    assert _web_login(client, buyer.email).status_code == 302

    second = start + timedelta(minutes=29, seconds=59)
    set_state(fixed_now=second)
    assert client.get("/cart/").status_code == 200

    set_state(fixed_now=second + timedelta(minutes=30))
    expired = client.get("/cart/")
    assert expired.status_code == 302
    location = urlparse(expired["Location"])
    assert location.path == "/login/" and parse_qs(location.query).get("required") == ["1"]
    assert "30分間操作がなかった" in text(client.get(expired["Location"]))
    assert client.get("/cart/").status_code == 302


# trace: FR-021, FR-003, ADDR-002, ADDR-001
def test_it_010_csrf_rejects_update_without_token(web, buyer, catalog):
    """IT-010 CSRF トークンのない画面更新要求の拒否。"""
    from carts.models import CartItem

    unit = catalog.stock_unit(stock=10)
    client = web()
    client.force_login(buyer, backend="accounts.backends.SessionUserBackend")
    page = client.get(f"/products/{unit.product_id}/")
    fields = form_fields(text(page), "/cart/items/add/")
    fields.pop("csrfmiddlewaretoken")
    fields.update({"stock_unit_id": str(unit.pk), "quantity": "1"})
    rejected = client.post("/cart/items/add/", fields)
    assert rejected.status_code == 403
    assert CartItem.objects.count() == 0

    logout = client.post("/logout/", {"submit_token": fields["submit_token"]})
    assert logout.status_code == 403
    assert client.get("/cart/").status_code == 200
