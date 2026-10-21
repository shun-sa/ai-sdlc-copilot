# trace: FR-001, FR-002, FR-003, FR-004, FR-020, FR-040, NFR-SC-01, NFR-SC-08, NFR-SC-18, FR-OUT-11
# trace: ADDR-001, ADDR-002, ADDR-003, ADDR-006, ADDR-007, ADDR-008, ADDR-010, ADDR-011
"""会員登録・認証・認可の結合試験（IT-AI-INIT-001〜032）。

検証対象の連携は API(DRF View) → Serializer → Service → ORM → PostgreSQL、
認証トークン検証 → API → トークン永続化、ロール判定 → 業務機能API、
画面(Django View) → Service → PostgreSQL、画面セッション → 画面機能。

期待結果は FR-001〜FR-004（処理内容・入力・出力・例外）、7章 共通機能要件（CMN-03/05/06/08/
09/11/12/14/16/17/19/24/29）、NFR-SC-01/08/18、提供済みAPI契約 6.1〜6.3、
ACTIVE な ADDR-001/002/003/006/007/008/010/011 から導出する。Production Code の
現在の挙動からは導出しない。
"""

from __future__ import annotations

import datetime as dt

import pytest
from rest_framework.test import APIClient

from accounts.models import (
    EVENT_LOGIN_FAILURE,
    EVENT_LOGIN_SUCCESS,
    EVENT_LOGOUT,
    ROLE_ADMIN,
    ROLE_BUYER,
    AuditLog,
    User,
)
from common import timeutils

pytestmark = pytest.mark.django_db

VALID_PASSWORD = "Passw0rdA"


# trace: FR-001, ADDR-001, ADDR-008
def register_payload(**overrides) -> dict:
    """会員登録の正当な要求本文（テストデータは架空の値のみ）。"""
    payload = {
        "email": "buyer-new@example.test",
        "password": VALID_PASSWORD,
        "password_confirmation": VALID_PASSWORD,
        "full_name": "山田 太郎",
    }
    payload.update(overrides)
    return payload


# trace: FR-001, ADDR-001, ADDR-008
def test_it_ai_init_001_register_creates_buyer(api, f):
    """IT-AI-INIT-001 / COV-001：会員登録APIは購入者を1件登録し、自動ログインしない。"""
    before = User.objects.count()

    response = api.post("/api/auth/register", register_payload(), format="json")

    assert response.status_code == 201
    body = response.json()
    assert User.objects.count() == before + 1
    user = User.objects.get(email="buyer-new@example.test")
    assert user.role == ROLE_BUYER
    assert user.registered_at is not None
    assert body["user_id"] == user.pk
    assert body["email"] == "buyer-new@example.test"
    assert body["full_name"] == "山田 太郎"
    assert body["role"] == ROLE_BUYER
    assert body["registered_at"] == timeutils.to_iso(user.registered_at)
    # 自動ログインしない（認証トークンを応答へ含めない）。
    assert "token" not in body
    assert user.auth_tokens.count() == 0


# trace: FR-001, ADDR-008
def test_it_ai_init_002_register_normalizes_email_and_name(api):
    """IT-AI-INIT-002 / COV-002：メールアドレスは前後空白除去・英小文字化、氏名は前後空白除去で保存する。"""
    response = api.post(
        "/api/auth/register",
        register_payload(email="  Buyer.Norm@EXAMPLE.com  ", full_name="  山田 花子  "),
        format="json",
    )

    assert response.status_code == 201
    user = User.objects.get(email="buyer.norm@example.com")
    assert user.full_name == "山田 花子"
    assert response.json()["email"] == "buyer.norm@example.com"


# trace: FR-001
def test_it_ai_init_003_register_rejects_duplicated_email(api, f, err):
    """IT-AI-INIT-003 / COV-003：正規化後に重複するメールアドレスは業務エラーとする。"""
    f.user(email="buyer.dup@example.com")
    before = User.objects.count()

    response = api.post(
        "/api/auth/register", register_payload(email="BUYER.DUP@example.com"), format="json"
    )

    assert response.status_code == 409
    assert err.code(response) == "EMAIL_ALREADY_REGISTERED"
    assert User.objects.count() == before


# trace: FR-001
def test_it_ai_init_004_password_length_boundaries(api, err):
    """IT-AI-INIT-004 / COV-004：パスワードは8文字以上64文字以下のみ受け付ける。"""
    cases = {
        "pass7@example.test": ("Pass123", 400),
        "pass8@example.test": ("Passw0rd", 201),
        "pass64@example.test": ("A1" * 32, 201),
        "pass65@example.test": ("A1" * 32 + "b", 400),
    }

    for email, (password, expected_status) in cases.items():
        response = api.post(
            "/api/auth/register",
            register_payload(email=email, password=password, password_confirmation=password),
            format="json",
        )
        assert response.status_code == expected_status, email
        if expected_status == 201:
            assert User.objects.filter(email=email).exists()
        else:
            assert err.code(response) == "VALIDATION_ERROR"
            assert "password" in err.fields(response)
            assert not User.objects.filter(email=email).exists()


# trace: FR-001
def test_it_ai_init_005_password_requires_alphabet_and_digit(api, err):
    """IT-AI-INIT-005 / COV-004：英字のみ・数字のみのパスワードを拒否する。"""
    for email, password, expected_reason in (
        ("alpha-only@example.test", "Password", "数字"),
        ("digit-only@example.test", "12345678", "英字"),
    ):
        response = api.post(
            "/api/auth/register",
            register_payload(email=email, password=password, password_confirmation=password),
            format="json",
        )

        assert response.status_code == 400
        assert err.code(response) == "VALIDATION_ERROR"
        assert "password" in err.fields(response)
        assert expected_reason in err.reasons(response)
        assert not User.objects.filter(email=email).exists()


# trace: FR-001
def test_it_ai_init_006_password_must_differ_from_email(api, err):
    """IT-AI-INIT-006 / COV-004：メールアドレスと同一のパスワードを拒否する。"""
    email = "user1@example.com"

    response = api.post(
        "/api/auth/register",
        register_payload(email=email, password=email, password_confirmation=email),
        format="json",
    )

    assert response.status_code == 400
    assert err.code(response) == "VALIDATION_ERROR"
    assert "password" in err.fields(response)
    assert not User.objects.filter(email=email).exists()


# trace: FR-001
def test_it_ai_init_007_password_confirmation_must_match(api, err):
    """IT-AI-INIT-007 / COV-005：確認用パスワードの不一致を入力エラーとする。"""
    email = "confirm@example.test"

    response = api.post(
        "/api/auth/register",
        register_payload(email=email, password_confirmation="Passw0rdB"),
        format="json",
    )

    assert response.status_code == 400
    assert err.code(response) == "VALIDATION_ERROR"
    assert "password_confirmation" in err.fields(response)
    assert not User.objects.filter(email=email).exists()


# trace: FR-001
def test_it_ai_init_008_full_name_boundaries(api, err):
    """IT-AI-INIT-008 / COV-006：氏名は前後空白除去後の1〜50文字のみ受け付ける。"""
    cases = [
        ("name-empty@example.test", "", 400),
        ("name-50@example.test", "名" * 50, 201),
        ("name-51@example.test", "名" * 51, 400),
        ("name-pad@example.test", "  " + "名" * 50 + "  ", 201),
    ]

    for email, full_name, expected_status in cases:
        response = api.post(
            "/api/auth/register", register_payload(email=email, full_name=full_name), format="json"
        )
        assert response.status_code == expected_status, email
        if expected_status == 201:
            assert User.objects.get(email=email).full_name == "名" * 50
        else:
            assert err.code(response) == "VALIDATION_ERROR"
            assert "full_name" in err.fields(response)


# trace: FR-001
def test_it_ai_init_009_email_format_and_length_boundaries(api, err):
    """IT-AI-INIT-009 / COV-006：メールアドレスは形式と254文字以内の両方を満たす必要がある。"""
    domain = "@example.test"
    email_254 = "a" * (254 - len(domain)) + domain
    email_255 = "b" * (255 - len(domain)) + domain

    assert len(email_254) == 254 and len(email_255) == 255

    ok = api.post("/api/auth/register", register_payload(email=email_254), format="json")
    too_long = api.post("/api/auth/register", register_payload(email=email_255), format="json")
    malformed = api.post("/api/auth/register", register_payload(email="bad-address"), format="json")

    assert ok.status_code == 201
    assert User.objects.filter(email=email_254).exists()
    for response in (too_long, malformed):
        assert response.status_code == 400
        assert err.code(response) == "VALIDATION_ERROR"
        assert "email" in err.fields(response)
    assert not User.objects.filter(email=email_255).exists()


# trace: FR-001, ADDR-011
def test_it_ai_init_010_validation_lists_all_invalid_fields(api):
    """IT-AI-INIT-010 / COV-007：入力不備は1回の応答で全項目を field と reason で列挙する（CMN-16）。"""
    response = api.post(
        "/api/auth/register",
        {"email": "bad", "password": "abc", "password_confirmation": "xyz", "full_name": ""},
        format="json",
    )

    assert response.status_code == 400
    body = response.json()
    # 提供済みAPI契約・Steering 6章のエラー応答形式（封筒 error と details[].field/reason）。
    assert set(body) == {"error"}
    error = body["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert {str(item["field"]) for item in error["details"]} >= {
        "email",
        "password",
        "password_confirmation",
        "full_name",
    }
    assert all(str(item["reason"]).strip() for item in error["details"])


# trace: FR-001
def test_it_ai_init_011_validation_precedes_duplicate_check(api, f, err):
    """IT-AI-INIT-011 / COV-008：入力判定を登録済み判定より先に行う（CMN-14）。"""
    f.user(email="buyer.dup2@example.com")

    response = api.post(
        "/api/auth/register",
        register_payload(email="buyer.dup2@example.com", password="abc", password_confirmation="abc"),
        format="json",
    )

    assert response.status_code == 400
    assert err.code(response) == "VALIDATION_ERROR"


# trace: FR-001, ADDR-002, NFR-SC-01
def test_it_ai_init_012_password_is_stored_as_salted_hash(api):
    """IT-AI-INIT-012 / COV-010：パスワードは利用者ごとに異なるソルト付きハッシュで保存する。"""
    for email in ("hash1@example.test", "hash2@example.test"):
        assert (
            api.post(
                "/api/auth/register",
                register_payload(email=email, password="SharedPw0rd", password_confirmation="SharedPw0rd"),
                format="json",
            ).status_code
            == 201
        )

    first = User.objects.get(email="hash1@example.test")
    second = User.objects.get(email="hash2@example.test")

    assert "SharedPw0rd" not in first.password_hash
    assert "SharedPw0rd" not in second.password_hash
    assert first.password_hash != second.password_hash


# trace: FR-001, ADDR-002
def test_it_ai_init_013_register_is_allowed_for_any_authentication_state(api, api_as, buyer, admin_user):
    """IT-AI-INIT-013 / COV-009：認証状態によらず登録でき、ロールは常に buyer となる（CMN-08）。"""
    clients = {
        "anon-reg@example.test": api,
        "buyer-reg@example.test": api_as(buyer),
        "admin-reg@example.test": api_as(admin_user),
    }

    for email, client in clients.items():
        response = client.post("/api/auth/register", register_payload(email=email), format="json")

        assert response.status_code == 201, email
        assert response.json()["role"] == ROLE_BUYER
        assert User.objects.get(email=email).role == ROLE_BUYER


# trace: FR-001, ADDR-003
@pytest.mark.django_db(transaction=True)
def test_it_ai_init_014_concurrent_registration_creates_single_user(run_parallel):
    """IT-AI-INIT-014 / COV-012：同一メールアドレスの同時登録で成功は1件だけとなる（CMN-19）。"""
    email = "race-register@example.test"

    def register():
        return APIClient().post("/api/auth/register", register_payload(email=email), format="json")

    try:
        results = run_parallel(register, register)

        statuses = sorted(response.status_code for response in results)
        assert statuses == [201, 409]
        failed = next(response for response in results if response.status_code == 409)
        body = failed.json()
        assert (body.get("error") or body)["code"] == "EMAIL_ALREADY_REGISTERED"
        assert User.objects.filter(email=email).count() == 1
    finally:
        User.objects.filter(email=email).delete()


# trace: FR-001, ADDR-010
def test_it_ai_init_015_screen_register_redirects_to_login(screen):
    """IT-AI-INIT-015 / COV-013：画面の会員登録完了後はログイン画面へ遷移し完了を知らせる。"""
    response = screen.post(
        "/register/",
        {
            "email": "screen-reg@example.test",
            "password": VALID_PASSWORD,
            "password_confirmation": VALID_PASSWORD,
            "full_name": "画面 太郎",
        },
    )

    assert response.status_code == 302
    assert response["Location"] == "/login/"
    assert User.objects.filter(email="screen-reg@example.test").count() == 1

    followed = screen.get(response["Location"])
    body = followed.content.decode()
    assert "完了" in body
    assert "ログイン" in body


# trace: FR-001, ADDR-010
def test_it_ai_init_016_screen_register_shows_errors_and_keeps_input(screen, f):
    """IT-AI-INIT-016 / COV-014：入力不備は項目の近傍、業務エラーは画面上部に表示し入力値を保持する（CMN-17）。"""
    invalid = screen.post(
        "/register/",
        {
            "email": "keep@example.test",
            "password": "abc",
            "password_confirmation": "abc",
            "full_name": "画面 花子",
        },
    )

    assert invalid.status_code == 400
    invalid_body = invalid.content.decode()
    assert 'name="email"' in invalid_body and "keep@example.test" in invalid_body
    assert "画面 花子" in invalid_body
    assert "abc" not in invalid_body  # パスワードは保持しない
    assert "field-errors" in invalid_body

    f.user(email="exists@example.test")
    duplicated = screen.post(
        "/register/",
        {
            "email": "exists@example.test",
            "password": VALID_PASSWORD,
            "password_confirmation": VALID_PASSWORD,
            "full_name": "画面 次郎",
        },
    )

    assert duplicated.status_code == 409
    duplicated_body = duplicated.content.decode()
    assert "messages" in duplicated_body
    assert "exists@example.test" in duplicated_body
    assert User.objects.filter(email="exists@example.test").count() == 1


# trace: FR-002, ADDR-002, NFR-SC-08
def test_it_ai_init_017_login_issues_token_for_buyer(api, f, fixed_now):
    """IT-AI-INIT-017 / COV-015：ログインは token・expires_at（発行+24時間）・user を返す。"""
    now = fixed_now(dt.datetime(2027, 4, 1, 10, 0, 0, tzinfo=timeutils.JST))
    buyer = f.user(email="login-buyer@example.test", password=VALID_PASSWORD)

    response = api.post(
        "/api/auth/login",
        {"email": "login-buyer@example.test", "password": VALID_PASSWORD},
        format="json",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["expires_at"] == timeutils.to_iso(now + dt.timedelta(hours=24))
    assert body["user"] == {
        "user_id": buyer.pk,
        "email": "login-buyer@example.test",
        "full_name": buyer.full_name,
        "role": ROLE_BUYER,
    }

    authorized = APIClient()
    authorized.credentials(HTTP_AUTHORIZATION=f"Bearer {body['token']}")
    assert authorized.get("/api/auth/me").status_code == 200


# trace: FR-002, ADDR-002
def test_it_ai_init_018_login_issues_admin_token(api, f):
    """IT-AI-INIT-018 / COV-016：管理者のログインは role=admin を返し管理者APIを利用できる。"""
    f.admin(email="login-admin@example.test", password=VALID_PASSWORD)

    response = api.post(
        "/api/auth/login",
        {"email": "login-admin@example.test", "password": VALID_PASSWORD},
        format="json",
    )

    assert response.status_code == 200
    assert response.json()["user"]["role"] == ROLE_ADMIN

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.json()['token']}")
    assert client.get("/api/admin/stock-units").status_code == 200


# trace: FR-002, ADDR-008
def test_it_ai_init_019_login_normalizes_email_and_keeps_password_case(api, f, err):
    """IT-AI-INIT-019 / COV-017：メールアドレスは正規化して照合し、パスワードは大文字小文字を区別する。"""
    f.user(email="buyer@example.com", password=VALID_PASSWORD)

    normalized = api.post(
        "/api/auth/login",
        {"email": "  BUYER@Example.com  ", "password": VALID_PASSWORD},
        format="json",
    )
    wrong_case = api.post(
        "/api/auth/login",
        {"email": "buyer@example.com", "password": VALID_PASSWORD.lower()},
        format="json",
    )

    assert normalized.status_code == 200
    assert wrong_case.status_code == 401
    assert err.code(wrong_case) == "INVALID_CREDENTIALS"


# trace: FR-002
def test_it_ai_init_020_login_failures_are_indistinguishable(api, f, err):
    """IT-AI-INIT-020 / COV-018：誤パスワード・未登録・形式不正を区別せず認証失敗とする（CMN-05）。"""
    f.user(email="known@example.com", password=VALID_PASSWORD)

    responses = [
        api.post("/api/auth/login", {"email": "known@example.com", "password": "Wrongpw0rd"}, format="json"),
        api.post("/api/auth/login", {"email": "unknown@example.com", "password": VALID_PASSWORD}, format="json"),
        api.post("/api/auth/login", {"email": "not-an-email", "password": VALID_PASSWORD}, format="json"),
    ]

    messages = set()
    for response in responses:
        assert response.status_code == 401
        assert err.code(response) == "INVALID_CREDENTIALS"
        assert err.details(response) == []
        messages.add(err.message(response))
    assert len(messages) == 1


# trace: FR-002
def test_it_ai_init_021_login_requires_email_and_password(api, err):
    """IT-AI-INIT-021 / COV-019：未入力は入力エラーとし未入力項目を列挙する。"""
    response = api.post("/api/auth/login", {}, format="json")

    assert response.status_code == 400
    assert err.code(response) == "VALIDATION_ERROR"
    assert set(err.fields(response)) >= {"email", "password"}


# trace: FR-003, ADDR-002
def test_it_ai_init_022_logout_revokes_token(api, token_for, buyer, err):
    """IT-AI-INIT-022 / COV-022：ログアウトは204を返し、以後そのトークンは認証エラーとなる。"""
    token = token_for(buyer)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    logout = client.post("/api/auth/logout")

    assert logout.status_code == 204
    assert not logout.content
    after = client.get("/api/auth/me")
    assert after.status_code == 401
    assert err.code(after) == "AUTHENTICATION_REQUIRED"


# trace: FR-002, FR-003, ADDR-002, NFR-SC-18
def test_it_ai_init_023_logout_revokes_only_requested_token(api, f, err):
    """IT-AI-INIT-023 / COV-023：多重ログインを認め、ログアウトは要求に使ったトークンのみ無効化する。"""
    f.user(email="multi@example.test", password=VALID_PASSWORD)
    credentials = {"email": "multi@example.test", "password": VALID_PASSWORD}

    token_a = api.post("/api/auth/login", credentials, format="json").json()["token"]
    token_b = api.post("/api/auth/login", credentials, format="json").json()["token"]
    assert token_a != token_b

    client_a, client_b = APIClient(), APIClient()
    client_a.credentials(HTTP_AUTHORIZATION=f"Bearer {token_a}")
    client_b.credentials(HTTP_AUTHORIZATION=f"Bearer {token_b}")
    assert client_a.get("/api/auth/me").status_code == 200
    assert client_b.get("/api/auth/me").status_code == 200

    assert client_a.post("/api/auth/logout").status_code == 204

    revoked = client_a.get("/api/auth/me")
    assert revoked.status_code == 401
    assert err.code(revoked) == "AUTHENTICATION_REQUIRED"
    assert client_b.get("/api/auth/me").status_code == 200


# trace: FR-002, ADDR-002, NFR-SC-08
def test_it_ai_init_024_token_expires_24_hours_after_issue(api, f, fixed_now, err):
    """IT-AI-INIT-024 / COV-024：有効期限日時ちょうど以降のトークンは認証エラーとする（CMN-09/CMN-29）。"""
    issued = fixed_now(dt.datetime(2027, 4, 1, 9, 0, 0, tzinfo=timeutils.JST))
    f.user(email="expiry@example.test", password=VALID_PASSWORD)
    token = api.post(
        "/api/auth/login", {"email": "expiry@example.test", "password": VALID_PASSWORD}, format="json"
    ).json()["token"]
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    fixed_now(issued + dt.timedelta(hours=24) - dt.timedelta(seconds=1))
    assert client.get("/api/auth/me").status_code == 200

    fixed_now(issued + dt.timedelta(hours=24))
    exactly = client.get("/api/auth/me")
    fixed_now(issued + dt.timedelta(hours=24, seconds=1))
    after = client.get("/api/auth/me")

    assert exactly.status_code == 401
    assert err.code(exactly) == "AUTHENTICATION_REQUIRED"
    assert after.status_code == 401
    assert err.code(after) == "AUTHENTICATION_REQUIRED"


# trace: FR-004, ADDR-002
def test_it_ai_init_025_missing_or_unknown_token_is_rejected(api, err):
    """IT-AI-INIT-025 / COV-025：トークンなし・未発行トークンは認証エラーとする。"""
    without_header = api.get("/api/auth/me")

    unknown = APIClient()
    unknown.credentials(HTTP_AUTHORIZATION="Bearer not-issued-token-value")
    unknown_token = unknown.get("/api/auth/me")

    for response in (without_header, unknown_token):
        assert response.status_code == 401
        assert err.code(response) == "AUTHENTICATION_REQUIRED"


# trace: FR-004
def test_it_ai_init_026_me_returns_logged_in_user(api_as, buyer, admin_user):
    """IT-AI-INIT-026 / COV-026：ログイン利用者情報照会は自分自身の情報を返す。"""
    for user in (buyer, admin_user):
        response = api_as(user).get("/api/auth/me")

        assert response.status_code == 200
        assert response.json() == {
            "user_id": user.pk,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
        }


# trace: FR-020, FR-040, ADDR-001
def test_it_ai_init_027_role_based_permission_is_enforced(api_as, buyer, admin_user, f, err):
    """IT-AI-INIT-027 / COV-027：購入者の管理機能・管理者の購入機能は権限エラーとする（CMN-03）。"""
    unit = f.sellable(price=1000, quantity=5)
    buyer_client = api_as(buyer)
    admin_client = api_as(admin_user)

    buyer_requests = [
        buyer_client.get("/api/admin/stock-units"),
        buyer_client.get("/api/admin/purchase-orders"),
    ]
    admin_requests = [
        admin_client.get("/api/cart"),
        admin_client.post("/api/cart/lines", {"stock_unit_id": unit.pk, "quantity": 1}, format="json"),
        admin_client.post("/api/checkout", {"recipient_name": "管理 太郎"}, format="json"),
        admin_client.get("/api/purchase-orders"),
    ]

    for response in buyer_requests + admin_requests:
        assert response.status_code == 403
        assert err.code(response) == "PERMISSION_DENIED"
    unit.refresh_from_db()
    assert unit.quantity == 5
    assert not admin_user.carts.exists()


# trace: FR-002, FR-003, ADDR-007
def test_it_ai_init_028_authentication_events_are_audited(api, f):
    """IT-AI-INIT-028 / COV-020：ログイン成功・失敗・ログアウトを監査ログへ記録する（CMN-24）。"""
    user = f.user(email="audit@example.test", password=VALID_PASSWORD)
    AuditLog.objects.all().delete()

    token = api.post(
        "/api/auth/login", {"email": "audit@example.test", "password": VALID_PASSWORD}, format="json"
    ).json()["token"]
    api.post("/api/auth/login", {"email": "audit@example.test", "password": "Wrongpw0rd"}, format="json")
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    client.post("/api/auth/logout")

    logs = {log.event_type: log for log in AuditLog.objects.all()}
    assert set(logs) == {EVENT_LOGIN_SUCCESS, EVENT_LOGIN_FAILURE, EVENT_LOGOUT}
    assert AuditLog.objects.count() == 3
    assert logs[EVENT_LOGIN_SUCCESS].result == "success"
    assert logs[EVENT_LOGIN_SUCCESS].user_id == user.pk
    assert logs[EVENT_LOGIN_FAILURE].result == "failure"
    assert logs[EVENT_LOGOUT].user_id == user.pk
    assert all(log.occurred_at is not None for log in logs.values())


# trace: FR-002, FR-OUT-11
def test_it_ai_init_029_repeated_failures_do_not_lock_account(api, f, err):
    """IT-AI-INIT-029 / COV-032：認証の連続失敗でアカウントをロックしない（CMN-05）。"""
    f.user(email="nolock@example.test", password=VALID_PASSWORD)

    for _ in range(10):
        response = api.post(
            "/api/auth/login", {"email": "nolock@example.test", "password": "Wrongpw0rd"}, format="json"
        )
        assert response.status_code == 401
        assert err.code(response) == "INVALID_CREDENTIALS"

    success = api.post(
        "/api/auth/login", {"email": "nolock@example.test", "password": VALID_PASSWORD}, format="json"
    )

    assert success.status_code == 200
    assert success.json()["token"]


# trace: FR-002, ADDR-010
def test_it_ai_init_030_screen_login_redirects_by_role(screen, f):
    """IT-AI-INIT-030 / COV-030：画面ログイン後はロール別の画面へ遷移する。"""
    f.user(email="screen-buyer@example.test", password=VALID_PASSWORD)
    f.admin(email="screen-admin@example.test", password=VALID_PASSWORD)

    buyer_response = screen.post(
        "/login/", {"email": "screen-buyer@example.test", "password": VALID_PASSWORD}
    )
    assert buyer_response.status_code == 302
    assert buyer_response["Location"] == "/"

    screen.post("/logout/")
    admin_response = screen.post(
        "/login/", {"email": "screen-admin@example.test", "password": VALID_PASSWORD}
    )
    assert admin_response.status_code == 302
    assert admin_response["Location"] == "/admin-console/orders/"


# trace: FR-002, ADDR-010
def test_it_ai_init_031_screen_login_failure_keeps_email_only(screen, f):
    """IT-AI-INIT-031 / COV-030：画面ログイン失敗はメッセージを表示しメールアドレスだけ保持する。"""
    f.user(email="screen-fail@example.test", password=VALID_PASSWORD)

    response = screen.post(
        "/login/", {"email": "screen-fail@example.test", "password": "Wrongpw0rd"}
    )

    assert response.status_code == 401
    body = response.content.decode()
    assert "メールアドレスまたはパスワード" in body
    assert "screen-fail@example.test" in body
    assert "Wrongpw0rd" not in body
    assert not response.client.session.get("login_user_id")


# trace: FR-003, ADDR-006
def test_it_ai_init_032_screen_logout_requires_login_again(screen_as, buyer):
    """IT-AI-INIT-032 / COV-031：画面ログアウト後は認証要画面がログイン画面へ遷移する。"""
    client = screen_as(buyer)
    assert client.get("/cart/").status_code == 200

    logout = client.post("/logout/")

    assert logout.status_code == 302
    assert not client.session.get("login_user_id")
    after = client.get("/cart/")
    assert after.status_code == 302
    assert after["Location"] == "/login/"
    assert "ログインが必要です" in client.get("/login/").content.decode()
