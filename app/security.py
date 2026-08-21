"""セキュリティユーティリティ (ADR-004 / ADR-006).

- パスワードハッシュ: ソルト付きbcrypt / 定数時間比較
- セッションID/CSRFトークン: CSPRNG生成
- Cookie署名: 設定注入のシークレットで署名
"""

from __future__ import annotations

import hmac
import secrets

from itsdangerous import BadSignature, URLSafeSerializer
from passlib.context import CryptContext

from app.config import get_settings

_pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=get_settings().bcrypt_rounds,
)


def hash_password(plain: str) -> str:
    """平文パスワードをソルト付きbcryptでハッシュ化する (ADR-006)。"""
    return _pwd_context.hash(plain)


def verify_password(plain: str, password_hash: str) -> bool:
    """パスワードを定数時間比較で検証する (ADR-006)。"""
    try:
        return _pwd_context.verify(plain, password_hash)
    except ValueError:
        return False


def generate_token(nbytes: int = 32) -> str:
    """CSPRNGでURLセーフなトークンを生成する (セッションID/CSRF用)。"""
    return secrets.token_urlsafe(nbytes)


def constant_time_equals(a: str, b: str) -> bool:
    """CSRFトークン等の定数時間比較。"""
    return hmac.compare_digest(a, b)


def _serializer() -> URLSafeSerializer:
    return URLSafeSerializer(get_settings().secret_key, salt="session")


def sign_value(value: str) -> str:
    """Cookieへ格納する値を署名付きにする (ADR-004)。"""
    return _serializer().dumps(value)


def unsign_value(signed: str) -> str | None:
    """署名付きCookie値を検証し復号する。改ざん時はNone。"""
    try:
        return _serializer().loads(signed)
    except BadSignature:
        return None
