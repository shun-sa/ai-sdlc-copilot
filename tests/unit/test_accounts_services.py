# trace: FR-001, FR-002, FR-003, FR-004, NFR-SC-01, NFR-SC-08, NFR-SC-15, NFR-SC-18, NFR-SC-22
# trace: NFR-SC-23, ADDR-002
"""会員登録・認証・ログアウト（FR-001〜FR-004）の単体テスト。

期待結果は機能要件 6.1（会員登録）・6.2（ログイン）・6.3（ログアウト）・6.4（利用者情報照会）、
提供済みAPI契約 6.2（エラーコード）、ADDR-002（パスワードのハッシュ保存・トークンの
ハッシュ保存・要求に使われたトークンのみ無効化）から導出する。

DB は pytest-django が作成する使い捨てのテストDB（Dockerコンテナ）だけを使用する。
"""

from __future__ import annotations

import datetime as dt

import pytest
from _helpers import make_user
from accounts import services
from accounts.models import (
    EVENT_LOGIN_FAILURE,
    EVENT_LOGIN_SUCCESS,
    EVENT_LOGOUT,
    RESULT_FAILURE,
    RESULT_SUCCESS,
    ROLE_ADMIN,
    ROLE_BUYER,
    AuditLog,
    AuthToken,
    User,
)
from common import timeutils
from common.exceptions import EmailAlreadyRegistered, InvalidCredentials, NotFoundError, ValidationFailed
from django.contrib.auth.hashers import check_password
from django.db import IntegrityError

pytestmark = pytest.mark.django_db

VALID_REGISTRATION = {
    "email": "  New.User@Example.TEST ",
    "password": "passw0rd",
    "password_confirmation": "passw0rd",
    "full_name": "  試験 太郎  ",
}


# trace: FR-001
def test_register_user_stores_normalized_values():
    """FR-001 手順1〜5：メールアドレスは正規化、氏名は空白除去、利用者区分は購入者。"""
    user = services.register_user(dict(VALID_REGISTRATION))

    stored = User.objects.get(pk=user.pk)
    assert stored.email == "new.user@example.test"
    assert stored.full_name == "試験 太郎"
    assert stored.role == ROLE_BUYER
    assert stored.registered_at is not None


# trace: NFR-SC-15
def test_register_user_ignores_role_in_payload():
    """NFR-SC-15：会員登録の入力に利用者区分を含めても購入者として登録する（管理者は作成できない）。"""
    payload = dict(VALID_REGISTRATION)
    payload.update({"role": ROLE_ADMIN, "is_admin": True})

    user = services.register_user(payload)

    assert user.role == ROLE_BUYER
    assert User.objects.filter(role=ROLE_ADMIN).count() == 0


# trace: FR-001
def test_register_user_records_registered_at_as_registration_time(fixed_now):
    """FR-001 手順5：登録日時は登録を行った時刻とする。"""
    at = fixed_now(dt.datetime(2026, 4, 1, 12, 0, 0, tzinfo=dt.UTC))

    user = services.register_user(dict(VALID_REGISTRATION))

    assert User.objects.get(pk=user.pk).registered_at == at


# trace: FR-001
def test_register_user_stores_password_as_hash_only():
    """FR-001 手順4：パスワードは一方向ハッシュ値で保持し、平文を保存しない。"""
    user = services.register_user(dict(VALID_REGISTRATION))

    assert user.password_hash != "passw0rd"
    assert check_password("passw0rd", user.password_hash) is True


# trace: FR-001
def test_register_user_does_not_log_in_automatically():
    """FR-001 手順6：自動ログインしない（認証トークンを発行しない）。"""
    user = services.register_user(dict(VALID_REGISTRATION))

    assert AuthToken.objects.filter(user=user).count() == 0


# trace: NFR-SC-01
def test_passwords_are_stored_with_per_user_salt():
    """NFR-SC-01：パスワードはソルト付き一方向ハッシュで保存する（同じ値でも利用者ごとに異なる）。"""
    first = services.register_user(dict(VALID_REGISTRATION))
    second_payload = dict(VALID_REGISTRATION)
    second_payload["email"] = "second@example.test"
    second = services.register_user(second_payload)

    assert first.password_hash != "passw0rd"
    assert second.password_hash != "passw0rd"
    assert first.password_hash != second.password_hash
    assert check_password("passw0rd", second.password_hash) is True


# trace: FR-001
def test_register_user_reports_every_missing_field():
    """E-001-01／CMN-16：条件を満たさない全項目を1回で通知する。"""
    with pytest.raises(ValidationFailed) as error:
        services.register_user({})

    fields = [detail["field"] for detail in error.value.details]
    assert set(fields) == {"email", "password", "password_confirmation", "full_name"}


# trace: FR-001
@pytest.mark.parametrize(
    ("payload_override", "expected_field"),
    [
        ({"email": "a" * 243 + "@example.test"}, "email"),
        ({"email": "invalid-email"}, "email"),
        ({"password": "short1"}, "password"),
        ({"password_confirmation": "different1"}, "password_confirmation"),
        ({"full_name": "あ" * 51}, "full_name"),
    ],
)
def test_register_user_rejects_values_outside_fr001_conditions(payload_override, expected_field):
    """E-001-01：6.1.3 の条件を満たさない入力は入力エラーとする。"""
    payload = dict(VALID_REGISTRATION)
    payload.update(payload_override)

    with pytest.raises(ValidationFailed) as error:
        services.register_user(payload)

    assert expected_field in [detail["field"] for detail in error.value.details]
    assert User.objects.count() == 0


# trace: FR-001
@pytest.mark.parametrize("length", [50, 1])
def test_register_user_accepts_full_name_within_boundary(length):
    """FR-001 6.1.3：氏名は1文字以上50文字以下（境界値）。"""
    payload = dict(VALID_REGISTRATION)
    payload["full_name"] = "あ" * length

    user = services.register_user(payload)

    assert user.full_name == "あ" * length


# trace: FR-001
def test_register_user_accepts_email_of_254_characters():
    """FR-001 6.1.3：メールアドレスは正規化後254文字以下（境界値）。"""
    local = "a" * (254 - len("@example.test"))
    payload = dict(VALID_REGISTRATION)
    payload["email"] = f"{local}@example.test"

    user = services.register_user(payload)

    assert len(user.email) == 254


# trace: FR-001
def test_register_user_rejects_password_equal_to_email():
    """FR-001 6.1.3：英小文字化したパスワードがメールアドレスと一致してはならない。"""
    payload = {
        "email": "user1@example.test",
        "password": "User1@Example.test",
        "password_confirmation": "User1@Example.test",
        "full_name": "試験 太郎",
    }

    with pytest.raises(ValidationFailed) as error:
        services.register_user(payload)

    assert any(detail["field"] == "password" for detail in error.value.details)


# trace: FR-001
def test_register_user_rejects_already_registered_email():
    """E-001-02：正規化後のメールアドレスが登録済みの場合は業務エラーとする。"""
    make_user(email="taken@example.test")
    payload = dict(VALID_REGISTRATION)
    payload["email"] = " TAKEN@example.test "

    with pytest.raises(EmailAlreadyRegistered) as error:
        services.register_user(payload)

    assert error.value.status_code == 409
    assert User.objects.filter(email="taken@example.test").count() == 1


# trace: FR-001
def test_register_user_converts_unique_constraint_violation(monkeypatch):
    """E-001-02：同時登録で制約違反になった場合も業務エラーへ変換する。"""

    def raise_integrity(**kwargs):
        raise IntegrityError("duplicate key value violates unique constraint uq_user_email")

    monkeypatch.setattr(User.objects, "create", raise_integrity)

    with pytest.raises(EmailAlreadyRegistered):
        services.register_user(dict(VALID_REGISTRATION))


# trace: FR-001
def test_register_user_propagates_unknown_integrity_error(monkeypatch):
    """対応表にない整合性例外は業務エラーへ変換せず、システムエラーとして扱う。"""

    def raise_integrity(**kwargs):
        raise IntegrityError("violates unique constraint uq_other")

    monkeypatch.setattr(User.objects, "create", raise_integrity)

    with pytest.raises(IntegrityError):
        services.register_user(dict(VALID_REGISTRATION))


# trace: FR-002
def test_authenticate_succeeds_with_registered_credentials():
    """FR-002 手順1〜8：メールアドレスとパスワードが一致した場合に利用者を返す。"""
    user = make_user(email="login@example.test", password="passw0rd")

    authenticated = services.authenticate("  LOGIN@example.TEST  ", "passw0rd")

    assert authenticated.pk == user.pk


# trace: NFR-SC-22
def test_authenticate_records_success_audit_log():
    """監査ログ（D-15）へログイン成功を1件記録する。"""
    user = make_user(email="audit@example.test", password="passw0rd")

    services.authenticate("audit@example.test", "passw0rd")

    log = AuditLog.objects.latest("pk")
    assert log.event_type == EVENT_LOGIN_SUCCESS
    assert log.result == RESULT_SUCCESS
    assert log.user_id == user.pk
    assert log.detail == ""


# trace: FR-002
def test_authenticate_rejects_unknown_email_without_revealing_existence():
    """E-002-02：メールアドレスとパスワードのどちらが誤りかを区別しない。"""
    with pytest.raises(InvalidCredentials) as error:
        services.authenticate("unknown@example.test", "passw0rd")

    assert error.value.code == "INVALID_CREDENTIALS"
    log = AuditLog.objects.latest("pk")
    assert log.event_type == EVENT_LOGIN_FAILURE
    assert log.result == RESULT_FAILURE
    assert log.user_id is None


# trace: FR-002
def test_authenticate_rejects_wrong_password_and_records_failure():
    """E-002-02：パスワード不一致も同じエラーとし、失敗を監査ログへ記録する。"""
    user = make_user(email="wrong@example.test", password="passw0rd")

    with pytest.raises(InvalidCredentials):
        services.authenticate("wrong@example.test", "other123")

    log = AuditLog.objects.latest("pk")
    assert log.event_type == EVENT_LOGIN_FAILURE
    assert log.user_id == user.pk


# trace: FR-002
@pytest.mark.parametrize(
    ("email", "password", "expected_fields"),
    [
        ("", "passw0rd", {"email"}),
        ("user@example.test", "", {"password"}),
        ("", "", {"email", "password"}),
    ],
)
def test_authenticate_reports_missing_input_as_validation_error(email, password, expected_fields):
    """E-002-01：未入力のみ VALIDATION_ERROR とする（API契約 6.2）。"""
    with pytest.raises(ValidationFailed) as error:
        services.authenticate(email, password)

    assert {detail["field"] for detail in error.value.details} == expected_fields


# trace: FR-002
def test_issue_token_stores_hash_and_24_hour_expiry(settings):
    """FR-002 出力：認証トークンは平文を保存せず、有効期限は発行時刻＋24時間とする。"""
    user = make_user()

    raw_token, token = services.issue_token(user)

    assert token.token_hash == services.hash_token(raw_token)
    assert token.token_hash != raw_token
    assert token.expires_at - token.issued_at == dt.timedelta(hours=settings.AUTH_TOKEN_LIFETIME_HOURS)
    assert token.revoked_at is None


# trace: FR-002
def test_login_api_returns_user_token_and_record():
    """FR-002：照合と認証トークンの発行を行う。"""
    user = make_user(email="api@example.test", password="passw0rd")

    authenticated, raw_token, token = services.login_api("api@example.test", "passw0rd")

    assert authenticated.pk == user.pk
    assert token.user_id == user.pk
    assert raw_token


# trace: FR-004
def test_resolve_auth_token_returns_user_for_valid_token():
    """有効なトークンは利用者と認証トークンへ解決する。"""
    user = make_user()
    raw_token, token = services.issue_token(user)

    resolved_user, resolved_token = services.resolve_auth_token(raw_token)

    assert resolved_user.pk == user.pk
    assert resolved_token.pk == token.pk


# trace: FR-004
def test_resolve_auth_token_rejects_unknown_token():
    """未知のトークンは解決しない。"""
    assert services.resolve_auth_token("unknown-token") is None


# trace: FR-003
def test_resolve_auth_token_rejects_revoked_token():
    """ログアウト済みのトークンは解決しない（FR-003 事後条件）。"""
    user = make_user()
    raw_token, token = services.issue_token(user)
    services.logout(token)

    assert services.resolve_auth_token(raw_token) is None


# trace: FR-004
@pytest.mark.parametrize("offset_seconds", [0, -1])
def test_resolve_auth_token_rejects_expired_token(offset_seconds):
    """有効期限に達したトークンは解決しない（境界値：期限ちょうど・期限経過）。"""
    user = make_user()
    raw_token, token = services.issue_token(user)
    token.expires_at = timeutils.now() + dt.timedelta(seconds=offset_seconds)
    token.save(update_fields=["expires_at"])

    assert services.resolve_auth_token(raw_token) is None


# trace: FR-004
def test_resolve_auth_token_accepts_token_before_expiry():
    """有効期限前のトークンは解決する（境界値：期限の1秒前）。"""
    user = make_user()
    raw_token, token = services.issue_token(user)
    token.expires_at = timeutils.now() + dt.timedelta(seconds=1)
    token.save(update_fields=["expires_at"])

    assert services.resolve_auth_token(raw_token) is not None


# trace: FR-003, NFR-SC-18
def test_logout_revokes_only_the_token_used_for_the_request():
    """FR-003：要求に使われた認証トークンだけを無効化する。"""
    user = make_user()
    first_raw, first_token = services.issue_token(user)
    second_raw, _second_token = services.issue_token(user)

    services.logout(first_token)

    assert services.resolve_auth_token(first_raw) is None
    assert services.resolve_auth_token(second_raw) is not None


# trace: NFR-SC-22
def test_logout_records_audit_log():
    """監査ログへログアウトを1件記録する。"""
    user = make_user()
    _raw, token = services.issue_token(user)

    services.logout(token)

    log = AuditLog.objects.latest("pk")
    assert log.event_type == EVENT_LOGOUT
    assert log.result == RESULT_SUCCESS
    assert log.user_id == user.pk


# trace: FR-003
def test_logout_session_records_audit_log_for_screen():
    """画面のログアウトでも監査ログを1件記録する。"""
    user = make_user()

    services.logout_session(user)

    assert AuditLog.objects.latest("pk").event_type == EVENT_LOGOUT


# trace: FR-004
def test_get_user_returns_registered_user():
    """FR-004：ログイン中の利用者情報を取得する。"""
    user = make_user(role=ROLE_ADMIN)

    assert services.get_user(user.pk).pk == user.pk


# trace: FR-004
def test_get_user_raises_not_found_for_unknown_id():
    """存在しない利用者は対象なしエラーとする。"""
    with pytest.raises(NotFoundError):
        services.get_user(999999)


# trace: NFR-SC-08
def test_hash_token_is_deterministic_sha256():
    """ADDR-002：認証トークンは SHA-256 ハッシュで保存する。"""
    import hashlib

    assert services.hash_token("abc") == hashlib.sha256(b"abc").hexdigest()
    assert services.hash_token("abc") == services.hash_token("abc")
    assert services.hash_token("abc") != services.hash_token("abd")


# trace: NFR-SC-23
def test_record_audit_keeps_detail_without_personal_information():
    """監査ログは追記のみで、個人情報・パスワード・トークンを記録しない。"""
    user = make_user()

    log = services.record_audit(
        event_type=EVENT_LOGIN_SUCCESS, result=RESULT_SUCCESS, user_id=user.pk, detail="users=1"
    )

    assert log.pk is not None
    assert user.email not in log.detail
    assert log.occurred_at is not None


# trace: FR-001
def test_user_role_properties_distinguish_buyer_and_admin():
    """利用者区分（購入者・管理者）を判定できる。"""
    buyer = make_user()
    admin = make_user(email="admin-role@example.test", role=ROLE_ADMIN)

    assert (buyer.is_buyer, buyer.is_admin) == (True, False)
    assert (admin.is_buyer, admin.is_admin) == (False, True)
    assert str(buyer) == f"User({buyer.pk})"
