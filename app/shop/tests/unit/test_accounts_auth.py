# trace: FR-001, FR-002, FR-003, FR-004, NFR-SC-01, NFR-SC-03, NFR-SC-16, NFR-SC-18, ADDR-002
"""ログイン・ログアウト・ログイン利用者情報照会（FR-002〜FR-004）の単体テスト。

期待値は FR-002〜FR-004、共通機能要件（CMN-02、CMN-03、CMN-24）、ADDR-002 の決定内容から導出する。
"""
import hashlib
from datetime import timedelta

import pytest

from shop.common import timeutils
from shop.common.errors import (
    AuthenticationRequiredError,
    InvalidCredentialsError,
    PermissionDeniedError,
    ValidationError,
)
from shop.models import AuditEventType, AuditLog, AuthToken, Role
from shop.services import accounts
from shop.tests.unit import _helpers

pytestmark = pytest.mark.django_db

PASSWORD = "Passw0rd"


# trace: FR-002
def test_login_with_token_issues_token_valid_for_24_hours(buyer):
    """ログインで認証トークンを1件発行し、有効期限は発行時刻の24時間後とする。"""
    issued = accounts.login_with_token(buyer.email, PASSWORD)

    token = AuthToken.objects.get(user=buyer)
    assert issued.value
    assert token.expires_at - token.issued_at == timedelta(hours=24)
    assert issued.expires_at == token.expires_at
    assert issued.user.user_id == buyer.user_id


# trace: FR-002, NFR-SC-01
def test_login_with_token_stores_only_token_hash(buyer):
    """平文のトークン値は保持せず、ハッシュ値だけを保存する（ADDR-002 DD-001）。"""
    issued = accounts.login_with_token(buyer.email, PASSWORD)

    token = AuthToken.objects.get(user=buyer)
    assert token.token_hash != issued.value
    assert token.token_hash == hashlib.sha256(issued.value.encode("utf-8")).hexdigest()


# trace: FR-002
def test_login_with_token_records_login_success_audit_log(buyer):
    """ログイン成功を監査ログへ1件記録する（CMN-24）。"""
    accounts.login_with_token(buyer.email, PASSWORD)

    log = AuditLog.objects.get(event_type=AuditEventType.LOGIN_SUCCESS)
    assert log.user_id_value == buyer.user_id
    assert log.result == "success"
    assert log.detail is None


# trace: FR-002
def test_login_normalizes_email(buyer):
    """メールアドレスは正規化して照合する（前後空白・英大文字を許容する）。"""
    issued = accounts.login_with_token(f"  {buyer.email.upper()}  ", PASSWORD)

    assert issued.user.user_id == buyer.user_id


# trace: FR-002, NFR-SC-18
def test_login_does_not_revoke_existing_tokens(buyer):
    """ログインのたびに新しいトークンを発行し、既存の有効なトークンを無効化しない。"""
    first = accounts.login_with_token(buyer.email, PASSWORD)
    second = accounts.login_with_token(buyer.email, PASSWORD)

    assert first.value != second.value
    assert AuthToken.objects.filter(user=buyer, revoked_at__isnull=True).count() == 2


# trace: FR-002
def test_login_with_unknown_email_raises_invalid_credentials(db):
    """登録のないメールアドレスでは認証失敗とし、利用者IDなしの監査ログを記録する。"""
    with pytest.raises(InvalidCredentialsError) as exc:
        accounts.authenticate("unknown@example.com", PASSWORD)

    assert exc.value.http_status == 401
    log = AuditLog.objects.get(event_type=AuditEventType.LOGIN_FAILURE)
    assert log.user_id_value is None
    assert log.result == "failure"


# trace: FR-002
def test_login_with_wrong_password_raises_invalid_credentials(buyer):
    """パスワード誤りでは認証失敗とし、利用者IDつきの監査ログを記録する。"""
    with pytest.raises(InvalidCredentialsError):
        accounts.authenticate(buyer.email, "Wr0ngpass")

    log = AuditLog.objects.get(event_type=AuditEventType.LOGIN_FAILURE)
    assert log.user_id_value == buyer.user_id


# trace: FR-002
def test_invalid_credentials_message_does_not_reveal_which_field_is_wrong(buyer):
    """認証失敗のメッセージはメールアドレスとパスワードのどちらが誤りかを区別しない。"""
    with pytest.raises(InvalidCredentialsError) as unknown:
        accounts.authenticate("unknown@example.com", PASSWORD)
    with pytest.raises(InvalidCredentialsError) as wrong:
        accounts.authenticate(buyer.email, "Wr0ngpass")

    assert unknown.value.message == wrong.value.message


# trace: FR-002
@pytest.mark.parametrize(
    ("email", "password", "expected_fields"),
    [
        ("", PASSWORD, {"email"}),
        ("buyer@example.com", "", {"password"}),
        ("", "", {"email", "password"}),
    ],
)
def test_login_requires_email_and_password(db, email, password, expected_fields):
    """メールアドレス・パスワード未入力は入力エラーとし、不備項目を列挙する。"""
    with pytest.raises(ValidationError) as exc:
        accounts.authenticate(email, password)

    assert {detail["field"] for detail in exc.value.details} == expected_fields
    assert AuditLog.objects.count() == 0


# trace: FR-002
def test_login_for_session_records_audit_log_without_token(buyer):
    """画面ログインでは監査ログを記録し、認証トークンは発行しない。"""
    user = accounts.login_for_session(buyer.email, PASSWORD)

    assert user.user_id == buyer.user_id
    assert AuthToken.objects.count() == 0
    assert AuditLog.objects.filter(event_type=AuditEventType.LOGIN_SUCCESS).count() == 1


# trace: FR-002, FR-004
def test_resolve_token_returns_user_for_valid_token(buyer):
    """有効な認証トークンから利用者を特定できる。"""
    issued = accounts.login_with_token(buyer.email, PASSWORD)

    user, token = accounts.resolve_token(issued.value)

    assert user.user_id == buyer.user_id
    assert token.revoked_at is None


# trace: FR-002
@pytest.mark.parametrize("token_value", ["", "unknown-token-value"])
def test_resolve_token_rejects_missing_or_unknown_token(buyer, token_value):
    """トークン未指定・不明なトークンは認証エラーとする。"""
    with pytest.raises(AuthenticationRequiredError) as exc:
        accounts.resolve_token(token_value)

    assert exc.value.http_status == 401


# trace: FR-003
def test_resolve_token_rejects_revoked_token(buyer):
    """無効化済みのトークンは認証エラーとする。"""
    issued = accounts.login_with_token(buyer.email, PASSWORD)
    _, token = accounts.resolve_token(issued.value)
    accounts.logout_token(token)

    with pytest.raises(AuthenticationRequiredError):
        accounts.resolve_token(issued.value)


# trace: FR-002
def test_resolve_token_rejects_expired_token(buyer):
    """有効期限に達したトークンは認証エラーとする（期限時刻を含めて無効）。"""
    issued = accounts.login_with_token(buyer.email, PASSWORD)
    token = AuthToken.objects.get(user=buyer)
    token.expires_at = timeutils.now()
    token.save(update_fields=["expires_at"])

    with pytest.raises(AuthenticationRequiredError):
        accounts.resolve_token(issued.value)


# trace: FR-002
def test_resolve_token_accepts_token_before_expiry(buyer):
    """有効期限より前のトークンは有効として扱う（境界の内側）。"""
    issued = accounts.login_with_token(buyer.email, PASSWORD)
    token = AuthToken.objects.get(user=buyer)
    token.expires_at = timeutils.now() + timedelta(seconds=1)
    token.save(update_fields=["expires_at"])

    user, _ = accounts.resolve_token(issued.value)

    assert user.user_id == buyer.user_id


# trace: FR-003
def test_logout_token_revokes_only_the_used_token(buyer):
    """ログアウトは要求に使われたトークンだけを無効化する。"""
    first = accounts.login_with_token(buyer.email, PASSWORD)
    second = accounts.login_with_token(buyer.email, PASSWORD)
    _, first_token = accounts.resolve_token(first.value)

    accounts.logout_token(first_token)

    assert AuthToken.objects.get(auth_token_id=first_token.auth_token_id).revoked_at is not None
    user, _ = accounts.resolve_token(second.value)
    assert user.user_id == buyer.user_id


# trace: FR-003
def test_logout_token_records_logout_audit_log(buyer):
    """ログアウトを監査ログへ1件記録する。"""
    issued = accounts.login_with_token(buyer.email, PASSWORD)
    _, token = accounts.resolve_token(issued.value)

    accounts.logout_token(token)

    log = AuditLog.objects.get(event_type=AuditEventType.LOGOUT)
    assert log.user_id_value == buyer.user_id
    assert log.result == "success"


# trace: FR-003
def test_logout_session_records_audit_log(buyer):
    """画面ログアウトでも監査ログを記録する。"""
    accounts.logout_session(buyer)

    assert AuditLog.objects.filter(event_type=AuditEventType.LOGOUT, user_id_value=buyer.user_id).count() == 1


# trace: FR-004
def test_user_payload_contains_only_public_fields(buyer):
    """ログイン利用者情報は利用者ID・メールアドレス・氏名・ロールだけを返す。"""
    payload = accounts.user_payload(buyer)

    assert payload == {
        "user_id": buyer.user_id,
        "email": buyer.email,
        "full_name": buyer.full_name,
        "role": Role.BUYER,
    }
    assert "password_hash" not in payload


# trace: FR-004
def test_find_user_returns_user_or_none(buyer):
    """利用者IDから利用者を取得し、該当なしは None を返す。"""
    assert accounts.find_user(buyer.user_id).user_id == buyer.user_id
    assert accounts.find_user(buyer.user_id + 1000) is None


# trace: FR-004
@pytest.mark.parametrize("raw_user_id", [None, "", 0])
def test_find_user_returns_none_for_empty_identifier(db, raw_user_id):
    """利用者IDが未設定の場合は None を返す。"""
    assert accounts.find_user(raw_user_id) is None


# trace: NFR-SC-03
def test_require_authenticated_rejects_anonymous(db):
    """未認証では認証エラーとする（CMN-02）。"""
    with pytest.raises(AuthenticationRequiredError):
        accounts.require_authenticated(None)


# trace: NFR-SC-03
def test_require_buyer_allows_buyer_and_rejects_admin(buyer, admin_user):
    """購入者専用機能は購入者のみ許可し、管理者は権限エラーとする（CMN-03）。"""
    assert accounts.require_buyer(buyer).user_id == buyer.user_id

    with pytest.raises(PermissionDeniedError) as exc:
        accounts.require_buyer(admin_user)
    assert exc.value.http_status == 403


# trace: NFR-SC-03
def test_require_admin_allows_admin_and_rejects_buyer(buyer, admin_user):
    """管理者専用機能は管理者のみ許可し、購入者は権限エラーとする（CMN-03）。"""
    assert accounts.require_admin(admin_user).user_id == admin_user.user_id

    with pytest.raises(PermissionDeniedError):
        accounts.require_admin(buyer)


# trace: NFR-SC-03
@pytest.mark.parametrize("required", [accounts.require_buyer, accounts.require_admin])
def test_role_check_requires_authentication_first(db, required):
    """ロール判定の前に認証を要求する。"""
    with pytest.raises(AuthenticationRequiredError):
        required(None)


# trace: FR-004
def test_is_admin(buyer, admin_user):
    """管理者判定は管理者のみ真を返す。"""
    assert accounts.is_admin(admin_user) is True
    assert accounts.is_admin(buyer) is False
    assert accounts.is_admin(None) is False


# trace: NFR-SC-16
def test_validate_password_collects_multiple_reasons():
    """パスワード条件の不備は理由を積み上げて通知する。"""
    from shop.common.validators import ErrorCollector

    errors = ErrorCollector()
    accounts.validate_password("あいうえおかきく", "user@example.com", errors)

    assert len(errors.details) == 2
    assert all(detail["field"] == "password" for detail in errors.details)


# trace: FR-002
def test_issue_token_generates_unique_values(buyer):
    """発行するトークン値は毎回異なる。"""
    values = {accounts.issue_token(buyer).value for _ in range(3)}

    assert len(values) == 3
    assert AuthToken.objects.filter(user=buyer).count() == 3


# trace: FR-001
def test_hash_password_uses_salt(db):
    """同じパスワードでもソルトにより異なるハッシュ値となる。"""
    first = accounts.hash_password(PASSWORD)
    second = accounts.hash_password(PASSWORD)

    assert first != second
    assert accounts.verify_password(PASSWORD, first) is True
    assert accounts.verify_password("Other123", first) is False


# trace: FR-002
def test_authenticate_returns_user_without_issuing_token(buyer):
    """認証だけを行う場合はトークンを発行しない。"""
    user = accounts.authenticate(buyer.email, PASSWORD)

    assert user.user_id == buyer.user_id
    assert AuthToken.objects.count() == 0


# trace: FR-002
def test_login_with_token_for_admin_user(admin_user):
    """管理者もログインでき、利用者情報のロールは admin となる。"""
    issued = accounts.login_with_token(admin_user.email, "Adminpass1")

    assert accounts.user_payload(issued.user)["role"] == Role.ADMIN


# trace: FR-001
def test_register_then_login(db):
    """登録直後の利用者はそのパスワードでログインできる。"""
    user = accounts.register_user(
        email="new.user@example.com",
        password="Newpass12",
        password_confirmation="Newpass12",
        full_name="新規 利用者",
    )

    issued = accounts.login_with_token("new.user@example.com", "Newpass12")

    assert issued.user.user_id == user.user_id


# trace: FR-002
def test_helpers_create_distinct_users(buyer, other_buyer):
    """テストデータの利用者は架空のメールアドレスで一意に作成される。"""
    assert buyer.email != other_buyer.email
    assert buyer.email.endswith("@example.com")
    assert _helpers.hashed(PASSWORD) == _helpers.hashed(PASSWORD)
