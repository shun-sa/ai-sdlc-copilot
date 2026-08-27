"""app.cookies.SessionCookieCodec の単体テスト。

Requirement: NFR-SEC-002 / C-AUTH-003 / FR-002
ADR: ADR-005（署名付きセッションCookie。改ざん検知）
Criteria: security, normal-case, invalid-input
"""

from __future__ import annotations

from app.cookies import SessionCookieCodec


class TestEncodeDecode:
    def test_roundtrip_returns_token(self) -> None:
        codec = SessionCookieCodec("secret-key")
        encoded = codec.encode("session-token-abc")
        assert codec.decode(encoded) == "session-token-abc"

    def test_encoded_value_is_not_raw_token(self) -> None:
        # ADR-005: Cookie 値はサーバー署名される。生トークンをそのまま格納しない。
        codec = SessionCookieCodec("secret-key")
        encoded = codec.encode("session-token-abc")
        assert encoded != "session-token-abc"


class TestTamperDetection:
    def test_tampered_value_rejected(self) -> None:
        # ADR-005: 改ざんされた Cookie 値は署名検証で拒否し None を返す。
        codec = SessionCookieCodec("secret-key")
        encoded = codec.encode("session-token-abc")
        tampered = encoded[:-1] + ("A" if encoded[-1] != "A" else "B")
        assert codec.decode(tampered) is None

    def test_different_secret_key_rejected(self) -> None:
        # 別の署名鍵で生成された Cookie は信頼しない（改ざん・なりすまし防止）。
        issuer = SessionCookieCodec("secret-key-1")
        verifier = SessionCookieCodec("secret-key-2")
        encoded = issuer.encode("session-token-abc")
        assert verifier.decode(encoded) is None

    def test_garbage_value_returns_none(self) -> None:
        codec = SessionCookieCodec("secret-key")
        assert codec.decode("garbage-value") is None
