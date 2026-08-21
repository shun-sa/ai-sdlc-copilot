"""セキュリティユーティリティ単体テスト。

対象: app/security.py
検証Requirement: NFR-SEC-001 (ハッシュ化), ERR-002/NFR-SEC-006 (定数時間比較),
ADR-004 (署名Cookie / CSPRNGトークン), ADR-006 (bcrypt)。
DB Strategy: NOT_APPLICABLE (純粋ロジック)。
期待結果は Requirements / ADR から導出する (Production Code から逆算しない)。
"""

from __future__ import annotations

from app.security import (
    constant_time_equals,
    generate_token,
    hash_password,
    sign_value,
    unsign_value,
    verify_password,
)


class TestPasswordHashing:
    # ADR-006 / NFR-SEC-001: bcrypt (ソルト付き一方向) でハッシュ化する
    def test_hash_uses_bcrypt_prefix(self) -> None:
        digest = hash_password("abcd1234")
        assert digest.startswith("$2")  # bcrypt識別子

    # NFR-SEC-001: 平文をそのまま保存しない (ハッシュ != 平文)
    def test_hash_is_not_plaintext(self) -> None:
        plain = "abcd1234"
        assert hash_password(plain) != plain

    # ADR-006: ソルトにより同一平文でも毎回異なるハッシュとなる
    def test_hash_is_salted_unique(self) -> None:
        assert hash_password("abcd1234") != hash_password("abcd1234")

    # 正常系: 正しいパスワードは検証成功
    def test_verify_correct_password(self) -> None:
        digest = hash_password("abcd1234")
        assert verify_password("abcd1234", digest) is True

    # 異常系: 誤ったパスワードは検証失敗
    def test_verify_wrong_password(self) -> None:
        digest = hash_password("abcd1234")
        assert verify_password("wrongpass", digest) is False

    # 例外系: 不正なハッシュ形式でも例外を送出せず False を返す
    def test_verify_invalid_hash_returns_false(self) -> None:
        assert verify_password("abcd1234", "not-a-valid-hash") is False


class TestTokenGeneration:
    # ADR-004: CSPRNGでトークンを生成し、毎回異なる値になる
    def test_tokens_are_unique(self) -> None:
        assert generate_token() != generate_token()

    def test_token_is_non_empty_urlsafe(self) -> None:
        token = generate_token()
        assert token
        assert "/" not in token and "+" not in token


class TestConstantTimeEquals:
    def test_equal_values(self) -> None:
        assert constant_time_equals("abc", "abc") is True

    def test_different_values(self) -> None:
        assert constant_time_equals("abc", "abd") is False


class TestSignedCookie:
    # ADR-004: Cookie値は署名して格納し、改ざんを検出できる
    def test_sign_unsign_roundtrip(self) -> None:
        signed = sign_value("session-123")
        assert unsign_value(signed) == "session-123"

    def test_signed_value_differs_from_plain(self) -> None:
        assert sign_value("session-123") != "session-123"

    # 改ざん検出: 署名を壊すと None を返す
    def test_tampered_value_rejected(self) -> None:
        signed = sign_value("session-123")
        tampered = signed[:-1] + ("A" if signed[-1] != "A" else "B")
        assert unsign_value(tampered) is None
