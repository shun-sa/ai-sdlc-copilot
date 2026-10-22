# trace: FR-001, FR-002, FR-003, FR-004, FR-020, FR-040, ADDR-002, ADDR-007, ADDR-008
"""認証・利用者機能（FR-001〜FR-004）と共通の認証・権限判定（CMN-02、CMN-03）の結合試験。

期待結果は機能要件定義書（FR-001〜FR-004、7章 共通機能要件）、
api-contract 6.1〜6.3、ADDR-002・ADDR-007・ADDR-008 から導出する。
"""
import hashlib
from datetime import datetime, timedelta

import pytest

from shop.common import timeutils
from shop.models import AuditEventType, AuditLog, AuthToken, Cart, User
from tests.integration import _helpers

pytestmark = pytest.mark.django_db


# trace: FR-001, ADDR-008
@pytest.mark.case("IT-AI-001")
def test_register_persists_buyer_without_auto_login(api):
    """会員登録が成功し、利用者が正規化された値とハッシュ化パスワードで永続化される。"""
    response = api.post(
        "/api/auth/register",
        {
            "email": " Buyer1@Example.com ",
            "password": _helpers.TEST_PASSWORD,
            "password_confirmation": _helpers.TEST_PASSWORD,
            "full_name": " 山田 太郎 ",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "buyer1@example.com"
    assert body["full_name"] == "山田 太郎"
    assert body["role"] == "buyer"
    assert body["registered_at"] is not None
    assert "token" not in body
    assert "password" not in body and "password_hash" not in body

    assert User.objects.count() == 1
    user = User.objects.get()
    assert user.email == "buyer1@example.com"
    assert user.password_hash != _helpers.TEST_PASSWORD
    assert user.password_hash.startswith("pbkdf2_sha256$")
    assert AuthToken.objects.count() == 0


# trace: FR-001, ADDR-007
@pytest.mark.case("IT-AI-002")
def test_register_reports_all_invalid_fields(api):
    """会員登録の入力エラーは条件を満たさない全項目をまとめて通知する（E-001-01、CMN-16）。"""
    response = api.post(
        "/api/auth/register",
        {
            "email": "not-an-email",
            "password": "short",
            "password_confirmation": "mismatch",
            "full_name": "",
        },
    )

    assert response.status_code == 400
    assert _helpers.error_code(response) == "VALIDATION_ERROR"
    assert _helpers.error_fields(response) == {"email", "password", "password_confirmation", "full_name"}
    assert User.objects.count() == 0


# trace: FR-001, ADDR-007
@pytest.mark.case("IT-AI-003")
def test_register_rejects_duplicated_email_after_normalization(api):
    """正規化後に重複するメールアドレスの会員登録は 409 となる（E-001-02）。"""
    _helpers.make_user(email="buyer@example.com")

    response = api.post(
        "/api/auth/register",
        {
            "email": " BUYER@Example.com ",
            "password": _helpers.TEST_PASSWORD,
            "password_confirmation": _helpers.TEST_PASSWORD,
            "full_name": "別人",
        },
    )

    assert response.status_code == 409
    assert _helpers.error_code(response) == "EMAIL_ALREADY_REGISTERED"
    assert User.objects.count() == 1


# trace: FR-002, FR-004, ADDR-002, ADDR-008
@pytest.mark.case("IT-AI-004")
def test_login_issues_token_and_records_audit_log(api):
    """ログイン成功でトークン・有効期限・利用者情報を返し、監査ログを1件記録する（CMN-24）。"""
    user = _helpers.make_user(email="buyer@example.com")
    requested_at = timeutils.now()

    response = api.post("/api/auth/login", {"email": "BUYER@example.com ", "password": _helpers.TEST_PASSWORD})

    assert response.status_code == 200
    body = response.json()
    assert body["user"] == {
        "user_id": user.user_id,
        "email": "buyer@example.com",
        "full_name": user.full_name,
        "role": "buyer",
    }
    expires_at = datetime.fromisoformat(body["expires_at"])
    assert abs((expires_at - (requested_at + timedelta(hours=24))).total_seconds()) <= 60

    token_row = AuthToken.objects.get()
    assert token_row.token_hash == hashlib.sha256(body["token"].encode("utf-8")).hexdigest()
    assert token_row.token_hash != body["token"]
    assert token_row.revoked_at is None

    logs = list(AuditLog.objects.all())
    assert len(logs) == 1
    assert logs[0].event_type == AuditEventType.LOGIN_SUCCESS
    assert logs[0].user_id_value == user.user_id
    assert (logs[0].detail or "") == ""

    me = api.get("/api/auth/me", token=body["token"])
    assert me.status_code == 200
    assert me.json()["user_id"] == user.user_id


# trace: FR-002, ADDR-002, ADDR-007
@pytest.mark.case("IT-AI-005")
def test_login_failure_is_indistinguishable_and_audited(api):
    """認証失敗はメールアドレスとパスワードの誤りを区別せず、失敗を監査ログへ記録する（E-002-02、CMN-25）。"""
    user = _helpers.make_user(email="buyer@example.com")

    wrong_password = api.post("/api/auth/login", {"email": "buyer@example.com", "password": "WrongPass1"})
    unknown_email = api.post("/api/auth/login", {"email": "nobody@example.com", "password": _helpers.TEST_PASSWORD})

    assert wrong_password.status_code == 401
    assert unknown_email.status_code == 401
    assert _helpers.error_code(wrong_password) == "INVALID_CREDENTIALS"
    assert wrong_password.json()["error"] == unknown_email.json()["error"]

    logs = list(AuditLog.objects.order_by("audit_log_id"))
    assert [log.event_type for log in logs] == [AuditEventType.LOGIN_FAILURE, AuditEventType.LOGIN_FAILURE]
    assert [log.user_id_value for log in logs] == [user.user_id, None]
    assert all("example.com" not in (log.detail or "") for log in logs)
    assert all(_helpers.TEST_PASSWORD not in (log.detail or "") for log in logs)
    assert AuthToken.objects.count() == 0


# trace: FR-002, ADDR-007
@pytest.mark.case("IT-AI-006")
def test_login_without_input_is_validation_error_and_not_audited(api):
    """ログインの未入力は入力エラーとし、監査ログを記録しない（E-002-01）。"""
    response = api.post("/api/auth/login", {"email": "   ", "password": ""})

    assert response.status_code == 400
    assert _helpers.error_code(response) == "VALIDATION_ERROR"
    assert _helpers.error_fields(response) == {"email", "password"}
    assert AuditLog.objects.count() == 0


# trace: FR-002, FR-003, ADDR-002
@pytest.mark.case("IT-AI-007")
def test_logout_revokes_only_the_used_token(api):
    """多重ログインの各トークンは独立し、ログアウトは要求に使ったトークンのみ無効化する（CMN-11、CMN-12）。"""
    _helpers.make_user(email="buyer@example.com")
    token_a = api.login("buyer@example.com")
    token_b = api.login("buyer@example.com")

    assert token_a != token_b
    assert AuthToken.objects.count() == 2

    logout = api.post("/api/auth/logout", token=token_a)
    assert logout.status_code == 204

    with_a = api.get("/api/auth/me", token=token_a)
    with_b = api.get("/api/auth/me", token=token_b)
    assert with_a.status_code == 401
    assert _helpers.error_code(with_a) == "AUTHENTICATION_REQUIRED"
    assert with_b.status_code == 200


# trace: FR-004, FR-020, FR-040, ADDR-002
@pytest.mark.case("IT-AI-008")
def test_authentication_required_apis_reject_missing_and_invalid_token(api):
    """認証必須APIは未認証・不正トークンの要求を処理しない（CMN-02、ERR-04）。"""
    _helpers.make_user(email="buyer@example.com")
    paths = ["/api/auth/me", "/api/cart", "/api/admin/stock-units"]

    for path in paths:
        without_token = api.get(path)
        invalid_token = api.get(path, token="invalid-token-value")
        assert without_token.status_code == 401, path
        assert invalid_token.status_code == 401, path
        assert _helpers.error_code(without_token) == "AUTHENTICATION_REQUIRED"
        assert _helpers.error_code(invalid_token) == "AUTHENTICATION_REQUIRED"

    assert Cart.objects.count() == 0


# trace: FR-004, ADDR-002
@pytest.mark.case("IT-AI-009")
def test_expired_token_is_rejected(api):
    """有効期限日時を過ぎた認証トークンは認証エラーとなる（CMN-09）。"""
    _helpers.make_user(email="buyer@example.com")
    token = api.login("buyer@example.com")
    row = AuthToken.objects.get()
    row.expires_at = timeutils.now() - timedelta(seconds=1)
    row.save(update_fields=["expires_at"])

    response = api.get("/api/auth/me", token=token)

    assert response.status_code == 401
    assert _helpers.error_code(response) == "AUTHENTICATION_REQUIRED"


# trace: FR-004, ADDR-002
@pytest.mark.case("IT-AI-010")
def test_me_returns_own_profile(api):
    """ログイン利用者情報照会は本人の情報を返す。"""
    user = _helpers.make_user(email="buyer@example.com")
    token = api.login("buyer@example.com")

    response = api.get("/api/auth/me", token=token)

    assert response.status_code == 200
    assert response.json() == {
        "user_id": user.user_id,
        "email": user.email,
        "full_name": user.full_name,
        "role": "buyer",
    }


# trace: FR-020, FR-040, ADDR-002, ADDR-007
@pytest.mark.case("IT-AI-011")
def test_role_restricted_apis_return_permission_denied(api):
    """ロールに許可されていないAPIは権限エラーとなる（CMN-03、ERR-03）。"""
    _helpers.make_user(email="buyer@example.com")
    _helpers.make_admin(email="admin@example.com")
    buyer_token = api.login("buyer@example.com")
    admin_token = api.login("admin@example.com")

    for path in ["/api/admin/stock-units", "/api/admin/purchase-orders"]:
        response = api.get(path, token=buyer_token)
        assert response.status_code == 403, path
        assert _helpers.error_code(response) == "PERMISSION_DENIED"

    cart = api.get("/api/cart", token=admin_token)
    checkout = api.post("/api/checkout", dict(_helpers.VALID_ADDRESS), token=admin_token)
    assert cart.status_code == 403
    assert checkout.status_code == 403
    assert _helpers.error_code(cart) == "PERMISSION_DENIED"
    assert _helpers.error_code(checkout) == "PERMISSION_DENIED"
    assert Cart.objects.count() == 0
