# trace: FR-001, FR-002, FR-003, FR-004, FR-020, FR-021, FR-030, FR-040, FR-041, ADDR-001, ADDR-002, ADDR-003
# trace: ADDR-004, ADDR-011
"""結合試験：会員・認証の Web API（Web API→認証→業務処理→DB→監査ログ）。

IT-001〜IT-006（AI INITIAL）。期待結果は FR-001〜FR-004、CMN-02/03/05/09/11/12/14/24/25、5.1 権限表、
ADDR-001（電文・エラー封筒）・ADDR-002（Bearer の保持・失効）・ADDR-003（パスワード保持）から導出する。
"""

from datetime import datetime, timedelta

import pytest

from tests.integration._helpers import PASSWORD, api, body, error_of, field_names, jst

pytestmark = pytest.mark.django_db


# trace: FR-001, FR-002, FR-003, FR-004, ADDR-001, ADDR-002, ADDR-003
def test_it_001_register_login_me_logout(api_client):
    """IT-001 会員登録→ログイン→利用者情報照会→ログアウトの連携。"""
    from accounts.models import ApiLoginState, User
    from audit.models import AuditLog

    reg = api(
        api_client,
        "post",
        "/api/auth/register/",
        data={
            "email": "  NewBuyer@Example.TEST ",
            "password": "Passw0rdIt1",
            "password_confirmation": "Passw0rdIt1",
            "name": " 新規 会員 ",
        },
    )
    assert reg.status_code == 201, reg.content
    created = body(reg)
    created_user = created.get("user", created)
    assert created_user["email"] == "newbuyer@example.test"
    assert created_user["name"] == "新規 会員"
    assert created_user["user_type"] == "buyer"

    user = User.objects.get(email="newbuyer@example.test")
    assert user.user_type == "buyer"
    assert "Passw0rdIt1" not in user.password
    assert user.check_password("Passw0rdIt1")

    before = datetime.now().astimezone()
    login = api(
        api_client, "post", "/api/auth/login/", data={"email": "NEWBUYER@example.test", "password": "Passw0rdIt1"}
    )
    assert login.status_code == 200, login.content
    data = body(login)
    assert isinstance(data["token"], str) and len(data["token"]) >= 32
    assert {k: data["user"][k] for k in ("user_id", "email", "name", "user_type")} == {
        "user_id": user.pk,
        "email": "newbuyer@example.test",
        "name": "新規 会員",
        "user_type": "buyer",
    }
    expires = datetime.fromisoformat(data["expires_at"])
    assert expires.utcoffset() == timedelta(hours=9)
    state = ApiLoginState.objects.get(user=user)
    assert state.expires_at - state.logged_in_at == timedelta(hours=24)
    assert abs(expires - (before + timedelta(hours=24))) < timedelta(seconds=5)
    assert data["token"] not in state.token_hash

    token = f"Bearer {data['token']}"
    me = api(api_client, "get", "/api/auth/me/", token)
    assert me.status_code == 200
    me_data = body(me)
    assert me_data["user_id"] == user.pk
    assert me_data["email"] == "newbuyer@example.test"
    assert me_data["name"] == "新規 会員"
    assert me_data["user_type"] == "buyer"

    success = AuditLog.objects.filter(event_type="login_success")
    assert success.count() == 1
    log = success.get()
    assert log.target_user_id == user.pk and log.result == "success"
    assert data["token"] not in (log.detail or "") and "Passw0rdIt1" not in (log.detail or "")
    assert "newbuyer@example.test" not in (log.detail or "")

    out = api(api_client, "post", "/api/auth/logout/", token)
    assert out.status_code == 204
    assert not out.content
    assert AuditLog.objects.filter(event_type="logout", target_user_id=user.pk, result="success").count() == 1

    after = api(api_client, "get", "/api/auth/me/", token)
    assert after.status_code == 401
    assert error_of(after)["type"] == "authentication_required"


# trace: FR-002, ADDR-001, ADDR-002, ADDR-004
def test_it_002_login_failure_indistinguishable_and_audited(api_client, buyer):
    """IT-002 ログイン失敗の非区別と監査ログ。"""
    from accounts.models import ApiLoginState
    from audit.models import AuditLog

    wrong = api(api_client, "post", "/api/auth/login/", data={"email": buyer.email, "password": "Wrong0Password"})
    unknown = api(api_client, "post", "/api/auth/login/", data={"email": "nobody@example.test", "password": PASSWORD})
    for response in (wrong, unknown):
        assert response.status_code == 401
        err = error_of(response)
        assert err["type"] == "authentication_failed"
        assert "token" not in body(response)
    assert error_of(wrong)["message"] == error_of(unknown)["message"]
    assert error_of(wrong) == error_of(unknown)

    failures = list(AuditLog.objects.filter(event_type="login_failure").order_by("pk"))
    assert len(failures) == 2
    assert failures[0].target_user_id == buyer.pk and failures[0].result == "failure"
    assert failures[1].target_user_id is None and failures[1].result == "failure"
    for log in failures:
        assert "nobody@example.test" not in (log.detail or "") and buyer.email not in (log.detail or "")
        assert "Wrong0Password" not in (log.detail or "")
    assert ApiLoginState.objects.count() == 0


# trace: FR-002, FR-003, FR-004, ADDR-002
def test_it_003_multi_login_and_logout_scope(api_client, buyer):
    """IT-003 多重ログインとログアウトの範囲。"""
    first = body(api(api_client, "post", "/api/auth/login/", data={"email": buyer.email, "password": PASSWORD}))
    second = body(api(api_client, "post", "/api/auth/login/", data={"email": buyer.email, "password": PASSWORD}))
    token_a, token_b = f"Bearer {first['token']}", f"Bearer {second['token']}"
    assert first["token"] != second["token"]
    assert api(api_client, "get", "/api/auth/me/", token_a).status_code == 200
    assert api(api_client, "get", "/api/auth/me/", token_b).status_code == 200

    assert api(api_client, "post", "/api/auth/logout/", token_a).status_code == 204
    gone = api(api_client, "get", "/api/auth/me/", token_a)
    assert gone.status_code == 401 and error_of(gone)["type"] == "authentication_required"
    still = api(api_client, "get", "/api/auth/me/", token_b)
    assert still.status_code == 200 and body(still)["user_id"] == buyer.pk


# trace: FR-002, FR-004, ADDR-002, ADDR-011
def test_it_004_bearer_expires_exactly_24h(api_client, buyer, set_state):
    """IT-004 Web API ログイン状態の有効期限（ログイン時刻+24時間ちょうどで無効）。"""
    start = jst(2027, 4, 10, 10, 0, 0)
    set_state(fixed_now=start)
    login = api(api_client, "post", "/api/auth/login/", data={"email": buyer.email, "password": PASSWORD})
    assert login.status_code == 200
    data = body(login)
    assert data["expires_at"] == "2027-04-11T10:00:00+09:00"
    token = f"Bearer {data['token']}"

    set_state(fixed_now=start + timedelta(hours=23, minutes=59, seconds=59))
    assert api(api_client, "get", "/api/auth/me/", token).status_code == 200

    set_state(fixed_now=start + timedelta(hours=24))
    expired = api(api_client, "get", "/api/auth/me/", token)
    assert expired.status_code == 401
    assert error_of(expired)["type"] == "authentication_required"


# trace: FR-001, ADDR-001, ADDR-004
def test_it_005_register_input_errors_and_duplicate(api_client, make_user):
    """IT-005 会員登録の入力エラー全項目通知と正規化後重複の業務エラー。"""
    from accounts.models import User

    make_user("user@example.test")
    bad = api(
        api_client,
        "post",
        "/api/auth/register/",
        data={
            "email": "not-an-email",
            "password": "Pass0rd",
            "password_confirmation": "Other0rd1",
            "name": "あ" * 51,
        },
    )
    assert bad.status_code == 400
    err = error_of(bad)
    assert err["type"] == "input_error"
    assert {"email", "password", "password_confirmation", "name"} <= field_names(bad)

    dup = api(
        api_client,
        "post",
        "/api/auth/register/",
        data={
            "email": " USER@EXAMPLE.TEST ",
            "password": PASSWORD,
            "password_confirmation": PASSWORD,
            "name": "重複 太郎",
        },
    )
    assert dup.status_code == 422
    err = error_of(dup)
    assert err["type"] == "business_error" and err["reason"] == "email_already_registered"
    assert User.objects.count() == 1


# trace: FR-004, FR-020, FR-021, FR-030, FR-040, FR-041, ADDR-001, ADDR-002
def test_it_006_permission_matrix_api(api_client, buyer, admin, bearer):
    """IT-006 利用者区分×機能の権限判定（Web API）。"""
    from django.test import Client

    from carts.models import Cart

    for method, path in (
        ("get", "/api/auth/me/"),
        ("get", "/api/cart/"),
        ("get", "/api/orders/"),
        ("get", "/api/admin/stock-units/"),
        ("get", "/api/admin/orders/"),
    ):
        response = api(api_client, method, path)
        assert response.status_code == 401, path
        assert error_of(response)["type"] == "authentication_required"
    invalid = api(api_client, "post", "/api/cart/items/", data={"stock_unit_id": "x", "quantity": "abc"})
    assert invalid.status_code == 401 and error_of(invalid)["type"] == "authentication_required"

    buyer_token = bearer(buyer)
    for path in ("/api/admin/stock-units/", "/api/admin/orders/"):
        response = api(api_client, "get", path, buyer_token)
        assert response.status_code == 403, path
        assert error_of(response)["type"] == "permission_denied"

    admin_token = bearer(admin)
    cart = api(api_client, "get", "/api/cart/", admin_token)
    assert cart.status_code == 403 and error_of(cart)["type"] == "permission_denied"
    order = api(api_client, "post", "/api/orders/", admin_token, data={"shipping_address": {}})
    assert order.status_code == 403 and error_of(order)["type"] == "permission_denied"
    assert Cart.objects.filter(buyer=admin).count() == 0

    browser = Client()
    browser.force_login(buyer, backend="accounts.backends.SessionUserBackend")
    cookie_only = browser.get("/api/cart/")
    assert cookie_only.status_code == 401
    assert error_of(cookie_only)["type"] == "authentication_required"
