"""External Integration Test Cases: 認証・会員登録（IT-001〜IT-009）。

origin=EXTERNAL。外部項目表の意味・Input・Steps・Expected Result を変更せず、
自動実行可能な形へ変換して検証する。期待結果は Requirements / ADR から導出する。
"""

from __future__ import annotations

from sqlalchemy import select

from app.models.user import User
from app.security import verify_password
from tests.integration._helpers import login, make_user, register


def _users(session_factory) -> list[User]:
    with session_factory() as s:
        return list(s.scalars(select(User)).all())


# IT-001: 会員登録：正常登録（FR-001 / AC-COM-001）
def test_it_001_register_success(client, session_factory):
    res = register(client, name="新規太郎", email="it001@example.com", password="Passw0rd")
    assert res.status_code == 200

    users = _users(session_factory)
    matched = [u for u in users if u.email == "it001@example.com"]
    assert len(matched) == 1  # User が1件作成され、メールは一意


# IT-002: 会員登録：必須入力不足（ERR-001 / C-UI-002 / NFR-SEC-004）
def test_it_002_register_required_missing(client, session_factory):
    res = client.post(
        "/register",
        data={"name": "", "email": "", "password": "", "password_confirm": ""},
    )
    assert res.status_code == 400  # サーバー側で登録拒否
    assert _users(session_factory) == []


# IT-003: 会員登録：形式不正・確認不一致（ERR-001 / NFR-SEC-004）
def test_it_003_register_format_and_mismatch(client, session_factory):
    res = client.post(
        "/register",
        data={
            "name": "誤り太郎",
            "email": "not-an-email",
            "password": "abc",  # 桁数不足かつ確認不一致
            "password_confirm": "different",
        },
    )
    assert res.status_code == 400
    assert _users(session_factory) == []


# IT-004: 会員登録：メール重複（ERR-001）
def test_it_004_register_duplicate_email(client, session_factory):
    with session_factory() as s:
        make_user(s, email="dup@example.com")
        s.commit()

    res = register(client, name="重複太郎", email="dup@example.com", password="Passw0rd")
    assert res.status_code == 400

    users = _users(session_factory)
    assert len([u for u in users if u.email == "dup@example.com"]) == 1  # 重複作成されない


# IT-005: パスワードのハッシュ保存（NFR-SEC-001 / DM-001 / ADR-004）
def test_it_005_password_is_hashed(client, session_factory):
    register(client, name="ハッシュ太郎", email="it005@example.com", password="Passw0rd")

    users = _users(session_factory)
    user = next(u for u in users if u.email == "it005@example.com")
    assert user.password_hash != "Passw0rd"  # 平文保存されない
    assert user.password_hash.startswith("$2")  # bcrypt ハッシュ
    assert verify_password("Passw0rd", user.password_hash)


# IT-006: ログイン：正常（AC-COM-002 / FR-002）
def test_it_006_login_success(client, session_factory):
    with session_factory() as s:
        make_user(s, email="it006@example.com")
        s.commit()

    res = login(client, "it006@example.com")
    assert res.status_code == 200
    # 認証状態で会員専用機能へアクセスできる
    history = client.get("/history")
    assert history.status_code == 200


# IT-007: ログイン：認証失敗（ERR-002 / NFR-SEC-006 / AC-COM-006）
def test_it_007_login_auth_failure(client, session_factory):
    with session_factory() as s:
        make_user(s, email="it007@example.com", password="password123")
        s.commit()

    res = login(client, "it007@example.com", "wrongpassword", follow_redirects=False)
    assert res.status_code == 401
    assert "メールアドレスまたはパスワードが正しくありません。" in res.text


# IT-008: ログイン：未登録メール（ERR-002 / NFR-SEC-006）
def test_it_008_login_unknown_email(client, session_factory):
    with session_factory() as s:
        make_user(s, email="it008-known@example.com", password="password123")
        s.commit()

    wrong = login(client, "it008-known@example.com", "wrongpassword", follow_redirects=False)
    unknown = login(client, "it008-unknown@example.com", "whatever", follow_redirects=False)

    assert unknown.status_code == 401
    # 存在有無を推測できない共通メッセージ（IT-007と同等）
    generic = "メールアドレスまたはパスワードが正しくありません。"
    assert generic in wrong.text
    assert generic in unknown.text


# IT-009: 未ログインで会員専用機能へアクセス（C-AUTH-003 / NFR-SEC-002 / AC-COM-006）
def test_it_009_guest_redirected_to_login(client):
    for path in ("/cart", "/orders/new", "/history"):
        res = client.get(path, follow_redirects=False)
        assert res.status_code == 303
        assert res.headers["location"].startswith("/login")
