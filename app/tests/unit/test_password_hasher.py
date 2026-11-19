# trace: NFR-SC-01, NFR-SC-16, FR-001, FR-002, ADDR-003
"""ADDR-003 r2 パスワード（照合用）の保持方式（accounts.hashers）の単体テスト。

期待値：ADDR-003 DD-001（方式名 pbkdf2_sha256_sha256hex・SHA-256 16進鍵・既定の反復回数）、
DD-003（反復回数を下げない）、
DD-006（他のハッシャーを置かない・旧方式名は照合不成立）、DD-007（NUL・制御文字を変換・拒否しない）、
INV-004（文字列として異なる入力では照合不成立）、NFR-SC-01（同じパスワードでも保存値が異なり平文と一致しない）。
DB を使わない（DB Test Strategy：NOT_APPLICABLE）。
"""

import hashlib

import pytest
from django.conf import settings
from django.contrib.auth.hashers import PBKDF2PasswordHasher, check_password, identify_hasher, make_password

from accounts.hashers import PBKDF2SHA256HexKeyPasswordHasher

PASSWORD = "Passw0rdTest"


# trace: NFR-SC-01, ADDR-003
def test_only_the_sha256hex_hasher_is_configured():
    """DD-006：PASSWORD_HASHERS に DD-001 のハッシャー以外を置かない。"""
    assert settings.PASSWORD_HASHERS == ["accounts.hashers.PBKDF2SHA256HexKeyPasswordHasher"]


# trace: NFR-SC-01, ADDR-003
def test_make_password_uses_method_name_and_standard_format_with_default_iterations():
    encoded = make_password(PASSWORD)
    algorithm, iterations, salt, digest = encoded.split("$")
    assert algorithm == "pbkdf2_sha256_sha256hex"
    assert int(iterations) >= PBKDF2PasswordHasher.iterations  # DD-003：Django 既定値より小さくしない
    assert salt and digest
    assert PASSWORD not in encoded
    assert isinstance(identify_hasher(encoded), PBKDF2SHA256HexKeyPasswordHasher)


# trace: NFR-SC-01, ADDR-003
def test_key_is_sha256_hex_of_utf8_password():
    """DD-001：鍵＝UTF-8 で符号化したパスワードの SHA-256 小文字16進64文字を PBKDF2-HMAC-SHA256 に渡す。"""
    hasher = PBKDF2SHA256HexKeyPasswordHasher()
    salt = "fixedsaltvalue12"
    encoded = hasher.encode("日本語Pass1", salt, iterations=1000)
    key = hashlib.sha256("日本語Pass1".encode()).hexdigest()
    expected = PBKDF2PasswordHasher().encode(key, salt, iterations=1000).split("$", 1)[1]
    assert encoded == "pbkdf2_sha256_sha256hex$" + expected


# trace: NFR-SC-01, ADDR-003
def test_same_password_produces_different_stored_values():
    """NFR-SC-01：同じパスワードの利用者どうしでも保存された値が互いに異なる（利用者ごとのソルト）。"""
    first, second = make_password(PASSWORD), make_password(PASSWORD)
    assert first != second
    assert check_password(PASSWORD, first) and check_password(PASSWORD, second)


# trace: FR-002, ADDR-003
@pytest.mark.parametrize(
    ("registered", "attempt"),
    [
        ("Passw0rdTest", "Passw0rdTest\x00"),
        ("Passw0rdTest\x00", "Passw0rdTest"),
        ("Pass\x00w0rdTest", "Passw0rdTest"),
        ("Passw0rdTest", "passw0rdtest"),
        ("Passw0rdTest", " Passw0rdTest"),
        ("a1" * 32, "a1" * 32 + "\x00"),
    ],
    ids=["nul-appended", "nul-removed", "nul-inserted-removed", "case", "leading-space", "64-chars-plus-nul"],
)
def test_strings_that_differ_never_match(registered, attempt):
    """INV-004：p と文字列として異なる入力（NUL の付加・挿入・削除を含む）では照合不成立、p 自身では成立。"""
    encoded = make_password(registered)
    assert check_password(registered, encoded) is True
    assert check_password(attempt, encoded) is False


# trace: FR-002, ADDR-003
@pytest.mark.parametrize(
    ("password", "utf8_bytes"),
    [
        ("Kounyu01Pass", 12),  # 64バイト以下
        ("a1" * 32, 64),  # ちょうど64バイト（HMAC のブロック長）
        ("a1" * 32 + "b", 65),  # 65バイト
        ("x1" * 50, 100),  # 65バイト以上
        ("日本語Pass1", 14),  # 多バイト文字を含む（64バイト以下）
        ("あ" * 20 + "a1a1", 64),  # 多バイト文字を含みちょうど64バイト
        ("あ" * 30 + "a1", 92),  # 多バイト文字を含み65バイト以上
    ],
    ids=["short", "64-bytes", "65-bytes", "100-bytes", "multibyte-short", "multibyte-64-bytes", "multibyte-92-bytes"],
)
def test_nul_appended_prepended_or_inserted_encodes_differently(password, utf8_bytes):
    """ADDR-003 6章 F(2)：同じソルト・反復回数で p と p＋NUL、NUL＋p、途中に NUL を挟んだ文字列の encode 結果が異なり、
    p 自身では verify が成立する（64バイト以下・ちょうど64バイト・65バイト以上・多バイト文字を含む場合）。"""
    assert len(password.encode("utf-8")) == utf8_bytes
    hasher = PBKDF2SHA256HexKeyPasswordHasher()
    salt, iterations = "fixedsaltvalue12", 1000
    encoded = hasher.encode(password, salt, iterations=iterations)
    middle = len(password) // 2
    variants = {
        "appended": password + "\x00",
        "prepended": "\x00" + password,
        "inserted": password[:middle] + "\x00" + password[middle:],
    }
    assert hasher.verify(password, encoded) is True
    for name, variant in variants.items():
        assert hasher.encode(variant, salt, iterations=iterations) != encoded, name
        assert hasher.verify(variant, encoded) is False, name
        assert hasher.verify(password, hasher.encode(variant, salt, iterations=iterations)) is False, name


# trace: FR-002, ADDR-003
def test_legacy_pbkdf2_sha256_values_do_not_match():
    """DD-006：旧方式名 pbkdf2_sha256 の保持値は照合不成立（自動移行もしない）。"""
    legacy = PBKDF2PasswordHasher().encode(PASSWORD, "legacysalt123456", iterations=1000)
    assert legacy.startswith("pbkdf2_sha256$")
    assert check_password(PASSWORD, legacy) is False


# trace: FR-002, ADDR-003
def test_verify_rejects_empty_and_other_method_values():
    hasher = PBKDF2SHA256HexKeyPasswordHasher()
    encoded = hasher.encode(PASSWORD, "s" * 16, iterations=1000)
    assert hasher.verify(PASSWORD, encoded) is True
    assert hasher.verify(PASSWORD + "x", encoded) is False
    with pytest.raises((AssertionError, ValueError, TypeError)):
        hasher.encode(None, "s" * 16)  # 継承元の引数検査（パスワードが文字列でない）


# trace: FR-001, ADDR-003
def test_surrogate_password_cannot_be_encoded():
    """Unicode のスカラー値でない値は UTF-8 に符号化できないため例外のまま返す（変換しない：INV-005）。"""
    with pytest.raises(UnicodeEncodeError):
        PBKDF2SHA256HexKeyPasswordHasher().encode("Pass1\ud800", "s" * 16, iterations=1000)
