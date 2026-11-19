# trace: FR-001, FR-002, FR-003, FR-004, NFR-SC-08, NFR-SC-15, NFR-SC-16, NFR-SC-18, NFR-SC-22, NFR-SC-23
# trace: ADDR-002, ADDR-003, ADDR-004, ADDR-012
"""会員・認証の業務処理（accounts.services、FR-001〜FR-004）と監査ログの単体テスト。

期待値は functional_requirements.md 6.1〜6.4（入力・処理内容・例外）、CMN-01・05・09・11・12・25、
NFR-SC-08/15/16/18/22/23、ADDR-002 DD-001〜DD-003、ADDR-003 DD-002・DD-004、
ADDR-004 DD-007・DD-013・DD-016 から導出する。
DB Test Strategy：CONTAINER（使い捨ての PostgreSQL 16。ORM・一意制約・トランザクションを含めて検証）。
システム障害の経路は DB 例外を差し込む（MOCK）。
"""

import hashlib
from datetime import timedelta
from unittest import mock

import pytest
from django.contrib.sessions.models import Session
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import DatabaseError, IntegrityError

from accounts import services
from accounts.backends import SessionUserBackend
from accounts.models import ApiLoginState, User
from audit.models import AppendOnlyError, AuditLog
from common import errors
from common.submit_token import TokenContext
from tests.unit.conftest import DEFAULT_PASSWORD, jst

NOW = jst(2027, 4, 10, 9, 30, 15)
pytestmark = pytest.mark.django_db


# trace: FR-001
def _register(**overrides):
    values = {
        "email": "  Taro.Yamada@Example.COM ",
        "password": "Passw0rd",
        "password_confirmation": "Passw0rd",
        "name": "\u3000山田 太郎 ",
    }
    values.update(overrides)
    return services.register(values["email"], values["password"], values["password_confirmation"], values["name"])


# trace: FR-001
def _fields(exc_info):
    return {(f.field, f.reason) for f in exc_info.value.fields}


# ---------------------------------------------------------------------------
# FR-001 会員登録
# ---------------------------------------------------------------------------


# trace: FR-001, NFR-SC-15, ADDR-003
def test_register_creates_buyer_with_normalized_values(freeze):
    freeze(NOW.replace(microsecond=456000))
    result = _register()
    user = User.objects.get(pk=result["user_id"])
    assert user.email == "taro.yamada@example.com"
    assert user.name == "山田 太郎"
    assert user.user_type == "buyer"
    assert user.registered_at == NOW  # 処理時刻（秒単位）
    assert result == {
        "user_id": user.pk,
        "email": "taro.yamada@example.com",
        "name": "山田 太郎",
        "user_type": "buyer",
        "user_type_label": "購入者",
        "registered_at": NOW,
    }
    # パスワードは平文で保持しない（CMN-06）。自動ログインしない（ログイン状態・監査ログを作らない）
    assert user.password.startswith("pbkdf2_sha256_sha256hex$") and "Passw0rd" not in user.password
    assert user.check_password("Passw0rd")
    assert ApiLoginState.objects.count() == 0 and Session.objects.count() == 0
    assert AuditLog.objects.count() == 0  # CMN-24：会員登録は監査ログに記録しない


# trace: FR-001
def test_register_reports_all_missing_items_at_once():
    with pytest.raises(errors.InputError) as info:
        services.register(None, "", None, "   ")
    assert info.value.code == "E-001-01"
    assert _fields(info) == {
        ("email", "required"),
        ("password", "required"),
        ("password_confirmation", "required"),
        ("name", "required"),
    }
    assert User.objects.count() == 0


# trace: FR-001
def test_register_rejects_non_string_values_by_type():
    with pytest.raises(errors.InputError) as info:
        services.register(123, 12345678, "x", ["n"])
    assert ("email", "invalid_type") in _fields(info)
    assert ("password", "invalid_type") in _fields(info)
    assert ("name", "invalid_type") in _fields(info)


# trace: FR-001
@pytest.mark.parametrize(
    ("email", "ok"),
    [
        ("a" * 64 + "@" + "b" * 189, True),  # 254文字
        ("a" * 64 + "@" + "b" * 190, False),  # 255文字
        ("no-at-sign.example.com", False),
        ("two@@example.com", False),
        ("sp ace@example.com", False),
        ("nul\x00@example.com", False),
    ],
    ids=["254-chars", "255-chars", "no-at", "double-at", "space", "nul"],
)
def test_register_email_length_and_format(email, ok):
    if ok:
        assert _register(email=email)["email"] == email
    else:
        with pytest.raises(errors.InputError) as info:
            _register(email=email)
        assert {f for f, _ in _fields(info)} == {"email"}


# trace: FR-001, NFR-SC-16, ADDR-003
@pytest.mark.parametrize(
    ("password", "ok"),
    [
        ("Passw0r", False),  # 7文字
        ("Passw0rd", True),  # 8文字
        ("a1" * 32, True),  # 64文字
        ("a1" * 32 + "b", False),  # 65文字
        ("Password", False),  # 英字のみ
        ("12345678", False),  # 数字のみ
        ("ab1@example.com", False),  # メールアドレスと同一
        ("AB1@EXAMPLE.COM", False),  # メールアドレスを英大文字にした文字列
        (" Passw0rd ", True),  # 前後の空白は除去しない（10文字）
        ("Passw0rd\x00\x07", True),  # NUL・制御文字を理由に拒否しない（ADDR-003 DD-007）
    ],
    ids=["7", "8", "64", "65", "letters-only", "digits-only", "same-as-email", "upper-email", "spaces", "nul-control"],
)
def test_register_password_rules(password, ok):
    kwargs = {"email": "ab1@example.com", "password": password, "password_confirmation": password}
    if ok:
        user = User.objects.get(pk=_register(**kwargs)["user_id"])
        assert user.check_password(password)  # 入力どおり（変換なし）で照合できる
    else:
        with pytest.raises(errors.InputError) as info:
            _register(**kwargs)
        assert info.value.code == "E-001-01"
        assert {f for f, _ in _fields(info)} == {"password"}


# trace: FR-001
def test_register_password_with_surrogate_is_type_error():
    with pytest.raises(errors.InputError) as info:
        _register(password="Passw0rd\ud800", password_confirmation="Passw0rd\ud800")
    assert ("password", "invalid_type") in _fields(info)


# trace: FR-001
def test_register_password_confirmation_must_match_without_trimming():
    with pytest.raises(errors.InputError) as info:
        _register(password="Passw0rd", password_confirmation="Passw0rd ")
    assert _fields(info) == {("password_confirmation", "mismatch")}


# trace: FR-001
@pytest.mark.parametrize(
    ("name", "ok"), [("名" * 50, True), (" " + "名" * 50 + " ", True), ("名" * 51, False), ("名\x00", False)]
)
def test_register_name_length_after_trimming(name, ok):
    if ok:
        assert _register(name=name)["name"] == "名" * 50
    else:
        with pytest.raises(errors.InputError) as info:
            _register(name=name)
        assert {f for f, _ in _fields(info)} == {"name"}


# trace: FR-001
def test_register_duplicate_email_is_business_error_case_insensitively(make_user):
    make_user("taro.yamada@example.com", user_type="admin")
    with pytest.raises(errors.BusinessError) as info:
        _register()
    assert info.value.code == "E-001-02"
    assert info.value.reason == "email_already_registered"
    assert User.objects.count() == 1


# trace: FR-001, ADDR-012
def test_register_input_error_is_judged_before_registered_email(make_user):
    """AC-UC-001-013：登録済みのメールアドレスでもパスワードの入力不備（7文字）が先に通知され、登録済みの旨は通知しない。"""
    make_user("hanako.sato@example.com")
    before = User.objects.count()
    with pytest.raises(errors.InputError) as info:
        services.register("hanako.sato@example.com", "Passw0r", "Passw0r", "佐藤 花子")
    assert info.value.code == "E-001-01"
    assert {f for f, _ in _fields(info)} == {"password"}
    assert all(f.message for f in info.value.fields)
    assert "既に登録されています" not in info.value.message
    assert all("既に登録されています" not in f.message for f in info.value.fields)
    assert User.objects.count() == before


# trace: FR-001
def test_register_concurrent_duplicate_integrity_error_becomes_e_001_02():
    """CMN-19：同一メールアドレスの同時登録で他方が先に確定した場合も E-001-02。"""
    with mock.patch.object(User, "save", side_effect=IntegrityError("dup")):
        with pytest.raises(errors.BusinessError) as info:
            _register()
    assert info.value.code == "E-001-02"


# trace: FR-001
def test_register_database_failure_is_system_error_without_partial_data():
    with mock.patch.object(User, "save", side_effect=DatabaseError("down")):
        with pytest.raises(errors.SystemFailureError) as info:
            _register()
    assert info.value.code == "E-001-03"
    assert User.objects.count() == 0


# ---------------------------------------------------------------------------
# FR-002 ログイン（照合・監査ログ）
# ---------------------------------------------------------------------------


# trace: FR-002, NFR-SC-22
def test_login_requires_both_items_and_records_no_audit_log():
    with pytest.raises(errors.InputError) as info:
        services.verify_credentials(" \u3000", "")
    assert info.value.code == "E-002-01"
    assert _fields(info) == {("email", "required"), ("password", "required")}
    assert AuditLog.objects.count() == 0


# trace: FR-002
def test_login_rejects_non_string_values_as_input_error():
    with pytest.raises(errors.InputError) as info:
        services.verify_credentials(5, ["x"])
    assert _fields(info) == {("email", "invalid_type"), ("password", "invalid_type")}


# trace: FR-002, NFR-SC-22, ADDR-003
def test_login_unknown_email_fails_with_dummy_hash_and_audit_without_user(freeze):
    freeze(NOW)
    with mock.patch("accounts.services.check_password", wraps=services.check_password) as checked:
        with pytest.raises(errors.AuthenticationFailedError) as info:
            services.verify_credentials("nobody@example.com", "Passw0rd")
    assert checked.call_count == 1  # ADDR-003 DD-004：同じハッシャーの照合計算を1回行う
    assert info.value.code == "E-002-02"
    assert info.value.message == services.MSG_AUTH_FAILED
    log = AuditLog.objects.get()
    assert (log.event_type, log.result, log.target_user_id, log.occurred_at) == ("login_failure", "failure", None, NOW)
    assert log.detail is None  # 入力されたメールアドレス・パスワードを記録しない（CMN-25）


# trace: FR-002, NFR-SC-22
def test_login_wrong_password_fails_with_same_message_and_audit_with_user(buyer):
    with pytest.raises(errors.AuthenticationFailedError) as info:
        services.verify_credentials(buyer.email, DEFAULT_PASSWORD + "x")
    assert info.value.message == services.MSG_AUTH_FAILED  # どちらが誤りかを区別しない（CMN-05）
    log = AuditLog.objects.get()
    assert (log.event_type, log.target_user_id) == ("login_failure", buyer.pk)


# trace: FR-002
def test_login_does_not_judge_email_format():
    """6.2.3：未入力の場合のみ入力エラーとし、形式の判定は行わない。"""
    with pytest.raises(errors.AuthenticationFailedError):
        services.verify_credentials("not-an-email", "x")


# trace: FR-002, ADDR-003
def test_login_email_with_nul_is_treated_as_no_user(buyer):
    with pytest.raises(errors.AuthenticationFailedError):
        services.verify_credentials(buyer.email + "\x00", DEFAULT_PASSWORD)
    assert AuditLog.objects.get().target_user_id is None


# trace: FR-002, ADDR-003
def test_login_with_surrogate_password_fails_for_existing_user(buyer):
    with pytest.raises(errors.AuthenticationFailedError):
        services.verify_credentials(buyer.email, "Passw0rd\ud800")
    assert AuditLog.objects.get().target_user_id == buyer.pk


# trace: FR-002
def test_login_normalizes_email_but_not_password(make_user):
    user = make_user("hanako@example.com", password=" Spaced1 ")
    assert services.verify_credentials("  HANAKO@Example.com\t", " Spaced1 ") == user
    with pytest.raises(errors.AuthenticationFailedError):
        services.verify_credentials("hanako@example.com", "Spaced1")


# trace: FR-002, NFR-SC-08, NFR-SC-18, ADDR-002
def test_login_api_issues_random_token_and_stores_only_its_hash(buyer, freeze):
    freeze(NOW)
    first = services.login_api(buyer.email, DEFAULT_PASSWORD)
    second = services.login_api(buyer.email, DEFAULT_PASSWORD)
    assert first["token"] and first["token"] != second["token"]
    assert len(first["token"]) >= 43  # 256ビットの乱数（URL safe Base64）
    assert first["expires_at"] == NOW + timedelta(hours=24)
    assert first["user"] == {
        "user_id": buyer.pk,
        "email": buyer.email,
        "name": buyer.name,
        "user_type": "buyer",
        "user_type_label": "購入者",
    }
    states = ApiLoginState.objects.filter(user=buyer)
    assert states.count() == 2  # 多重ログイン（CMN-11）
    hashes = set(states.values_list("token_hash", flat=True))
    assert hashlib.sha256(first["token"].encode()).hexdigest() in hashes
    assert first["token"] not in hashes
    assert list(AuditLog.objects.values_list("event_type", flat=True)) == ["login_success", "login_success"]


# trace: FR-002, ADDR-002
def test_login_api_database_failure_is_system_error_and_nothing_recorded(buyer):
    with mock.patch.object(ApiLoginState.objects, "create", side_effect=DatabaseError("x")):
        with pytest.raises(errors.SystemFailureError) as info:
            services.login_api(buyer.email, DEFAULT_PASSWORD)
    assert info.value.code == "E-002-03"
    assert not AuditLog.objects.filter(event_type="login_success").exists()


# trace: FR-002
def test_login_user_lookup_failure_is_system_error():
    with mock.patch.object(User.objects, "filter", side_effect=DatabaseError("x")):
        with pytest.raises(errors.SystemFailureError) as info:
            services.verify_credentials("a@example.com", "Passw0rd")
    assert info.value.code == "E-002-03"


# trace: FR-002, ADDR-004
def test_login_failure_audit_failure_is_system_error():
    with mock.patch("audit.services.record_login_failure", side_effect=DatabaseError("x")):
        with pytest.raises(errors.SystemFailureError) as info:
            services.verify_credentials("nobody@example.com", "Passw0rd")
    assert info.value.code == "E-002-03"


# trace: FR-002, NFR-SC-22, ADDR-002, ADDR-004
def test_login_web_starts_session_and_records_success(buyer, freeze):
    freeze(NOW)
    started = []
    user = services.login_web(buyer.email, DEFAULT_PASSWORD, TokenContext(), started.append)
    assert user == buyer and started == [buyer]
    log = AuditLog.objects.get()
    assert (log.event_type, log.result, log.target_user_id, log.occurred_at) == (
        "login_success",
        "success",
        buyer.pk,
        NOW,
    )


# trace: FR-002, ADDR-004
def test_login_web_session_failure_rolls_back_success_audit(buyer):
    def failing(_user):
        raise DatabaseError("session store down")

    with pytest.raises(errors.SystemFailureError) as info:
        services.login_web(buyer.email, DEFAULT_PASSWORD, TokenContext(), failing)
    assert info.value.code == "E-002-03"
    assert AuditLog.objects.count() == 0


# trace: FR-002, ADDR-004
def test_login_web_used_token_with_prior_success_does_nothing(buyer):
    """ADDR-004 DD-013・DD-016・DD-017：使用済みトークンは手順1〜9を行わず、照合・監査ログの記録をしない。"""
    started = []
    replay = TokenContext(active=True, used=True, prior={"status": "success", "redirect": "/"})
    with mock.patch("accounts.services.verify_credentials") as verify:
        assert services.login_web("", "", replay, started.append) is None
    verify.assert_not_called()
    assert started == [] and AuditLog.objects.count() == 0


# trace: FR-002, ADDR-004
def test_login_web_used_token_with_prior_error_reports_prior_error_regardless_of_input(buyer):
    prior = errors.AuthenticationFailedError("E-002-02", services.MSG_AUTH_FAILED).to_record()
    replay = TokenContext(active=True, used=True, prior=prior)
    with pytest.raises(errors.AuthenticationFailedError):
        services.login_web(buyer.email, DEFAULT_PASSWORD, replay, lambda _u: None)  # 正しい入力でも先着の結果
    assert AuditLog.objects.count() == 0


# trace: FR-002, ADDR-004
def test_login_web_used_token_without_record_is_system_error():
    with pytest.raises(errors.SystemFailureError) as info:
        services.login_web("a", "b", TokenContext(active=True, used=True, prior=None), lambda _u: None)
    assert info.value.code == "E-002-03"


# ---------------------------------------------------------------------------
# Web API のログイン状態の判定（CMN-09、ADDR-002 DD-002）
# ---------------------------------------------------------------------------


# trace: FR-004, NFR-SC-08, ADDR-002
def test_api_token_is_valid_only_before_expiry(buyer, freeze):
    freeze(NOW)
    token = services.login_api(buyer.email, DEFAULT_PASSWORD)["token"]
    freeze(NOW + timedelta(hours=24) - timedelta(seconds=1))
    assert services.resolve_api_token(token)[0] == buyer
    freeze(NOW + timedelta(hours=24) - timedelta(microseconds=1))  # 秒単位切捨てで期限の1秒前
    assert services.resolve_api_token(token) is not None
    freeze(NOW + timedelta(hours=24))  # 有効期限日時ちょうどは無効
    assert services.resolve_api_token(token) is None
    freeze(NOW + timedelta(hours=25))
    assert services.resolve_api_token(token) is None
    assert services.resolve_api_token("unknown-token") is None


# ---------------------------------------------------------------------------
# FR-003 ログアウト
# ---------------------------------------------------------------------------


# trace: FR-003, NFR-SC-18, NFR-SC-22, ADDR-002
def test_logout_api_ends_only_the_used_login_state(buyer, freeze):
    freeze(NOW)
    first = services.login_api(buyer.email, DEFAULT_PASSWORD)["token"]
    second = services.login_api(buyer.email, DEFAULT_PASSWORD)["token"]
    user, state = services.resolve_api_token(first)
    services.logout_api(user, state)
    assert services.resolve_api_token(first) is None
    assert services.resolve_api_token(second) is not None  # CMN-12：他のログイン状態は有効のまま
    log = AuditLog.objects.filter(event_type="logout").get()
    assert (log.target_user_id, log.result, log.occurred_at) == (buyer.pk, "success", NOW)


# trace: FR-003
def test_logout_api_without_valid_state_is_authentication_error(buyer):
    with pytest.raises(errors.AuthenticationRequiredError) as info:
        services.logout_api(None, None)
    assert info.value.code == "E-003-01"
    gone = ApiLoginState(pk=999999, user=buyer)
    with pytest.raises(errors.AuthenticationRequiredError):
        services.logout_api(buyer, gone)
    assert AuditLog.objects.count() == 0


# trace: FR-003
def test_logout_api_database_failure_keeps_state(buyer):
    token = services.login_api(buyer.email, DEFAULT_PASSWORD)["token"]
    user, state = services.resolve_api_token(token)
    with mock.patch("audit.services.record_logout", side_effect=DatabaseError("x")):
        with pytest.raises(errors.SystemFailureError) as info:
            services.logout_api(user, state)
    assert info.value.code == "E-003-02"
    assert services.resolve_api_token(token) is not None  # ログイン状態は有効のまま


# trace: FR-003, NFR-SC-22
def test_logout_web_records_audit_and_ends_session(admin):
    ended = []
    services.logout_web(admin, lambda: ended.append(True))
    assert ended == [True]
    assert AuditLog.objects.get().event_type == "logout"  # NFR-SC-15：管理者のログアウトも記録


# trace: FR-003
def test_logout_web_failures(buyer):
    with pytest.raises(errors.AuthenticationRequiredError):
        services.logout_web(None, lambda: None)

    def failing():
        raise DatabaseError("x")

    with pytest.raises(errors.SystemFailureError) as info:
        services.logout_web(buyer, failing)
    assert info.value.code == "E-003-02"
    assert AuditLog.objects.count() == 0  # 記録も取り消す


# ---------------------------------------------------------------------------
# FR-004 ログイン利用者情報照会
# ---------------------------------------------------------------------------


# trace: FR-004
def test_me_returns_own_information_only(buyer):
    assert services.me(buyer) == {
        "user_id": buyer.pk,
        "email": buyer.email,
        "name": buyer.name,
        "user_type": "buyer",
        "user_type_label": "購入者",
    }


# trace: FR-004
def test_me_errors(buyer):
    with pytest.raises(errors.AuthenticationRequiredError) as info:
        services.me(None)
    assert info.value.code == "E-004-01"
    ghost = User(pk=987654321)
    with pytest.raises(errors.AuthenticationRequiredError):
        services.me(ghost)
    with mock.patch.object(User.objects, "get", side_effect=DatabaseError("x")):
        with pytest.raises(errors.SystemFailureError) as info:
            services.me(buyer)
    assert info.value.code == "E-004-02"


# ---------------------------------------------------------------------------
# 監査ログの改ざん防止（NFR-SC-23）・特権の管理（NFR-SC-15）・その他
# ---------------------------------------------------------------------------


# trace: NFR-SC-23
def test_audit_log_is_append_only(buyer):
    services.logout_web(buyer, lambda: None)
    log = AuditLog.objects.get()
    log.result = "failure"
    with pytest.raises(AppendOnlyError):
        log.save()
    with pytest.raises(AppendOnlyError):
        log.delete()
    with pytest.raises(AppendOnlyError):
        AuditLog.objects.all().update(result="failure")
    with pytest.raises(AppendOnlyError):
        AuditLog.objects.all().delete()
    assert AuditLog.objects.get().result == "success"


# trace: NFR-SC-15
@pytest.mark.parametrize("command", ["createsuperuser", "changepassword"])
def test_management_commands_cannot_create_admin_or_change_password(command):
    """NFR-SC-15：管理者の作成手段は初期データ一括投入のみ（Django 付属コマンドは何もせずエラー終了）。"""
    with pytest.raises(CommandError):
        call_command(command)
    assert User.objects.count() == 0


# trace: FR-002, ADDR-002
def test_session_backend_restores_user_only_by_id(buyer):
    backend = SessionUserBackend()
    assert backend.authenticate(None, username=buyer.email, password=DEFAULT_PASSWORD) is None
    assert backend.get_user(buyer.pk) == buyer
    assert backend.get_user(999999999) is None
    assert backend.get_user("abc") is None


# trace: FR-002, ADDR-002
def test_delete_all_login_states_removes_api_and_web_states(buyer, bearer, login_web):
    bearer(buyer)
    login_web(buyer)
    assert ApiLoginState.objects.exists() and Session.objects.exists()
    services.delete_all_login_states()
    assert not ApiLoginState.objects.exists() and not Session.objects.exists()


# trace: FR-001, ADDR-002
def test_user_model_helpers(buyer, admin):
    assert buyer.is_buyer and not buyer.is_admin_user
    assert admin.is_admin_user and not admin.is_buyer
    assert str(buyer) == f"user:{buyer.pk}"
    assert User.objects.get_by_natural_key(buyer.email) == buyer
