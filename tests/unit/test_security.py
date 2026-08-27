"""app.security の単体テスト。

Requirement: NFR-SEC-001 / FR-001
ADR: ADR-004（bcrypt 一方向ハッシュ）
Criteria: security, normal-case, exception
"""

from __future__ import annotations

from app.security import hash_password, verify_password


class TestHashPassword:
    def test_hash_uses_bcrypt_prefix(self) -> None:
        # ADR-004: bcrypt でハッシュ化する。bcrypt ハッシュは $2b$ 等の接頭辞を持つ。
        hashed = hash_password("password123")
        assert hashed.startswith("$2")

    def test_hash_is_not_plaintext(self) -> None:
        # NFR-SEC-001 / ADR-004: 平文を保存してはならない。
        plain = "password123"
        hashed = hash_password(plain)
        assert hashed != plain
        assert plain not in hashed

    def test_hash_is_salted_unique(self) -> None:
        # bcrypt はソルト内蔵。同一平文でも毎回異なるハッシュになる（ADR-004）。
        assert hash_password("password123") != hash_password("password123")


class TestVerifyPassword:
    def test_correct_password_returns_true(self) -> None:
        hashed = hash_password("password123")
        assert verify_password("password123", hashed) is True

    def test_wrong_password_returns_false(self) -> None:
        hashed = hash_password("password123")
        assert verify_password("wrongpassword", hashed) is False

    def test_invalid_hash_returns_false(self) -> None:
        # 不正な形式のハッシュに対しても例外を送出せず False を返す（exception criterion）。
        assert verify_password("password123", "not-a-valid-bcrypt-hash") is False

    def test_empty_hash_returns_false(self) -> None:
        assert verify_password("password123", "") is False
