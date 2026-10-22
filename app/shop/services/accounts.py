# trace: ADDR-002, ADDR-008
"""認証・利用者機能（FR-001〜FR-004）の業務ロジック。"""
import hashlib
import secrets
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from django.contrib.auth.hashers import check_password, make_password
from django.db import IntegrityError, transaction

from shop.common import timeutils
from shop.common.errors import (
    AuthenticationRequiredError,
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
    PermissionDeniedError,
)
from shop.common.validators import EMAIL_PATTERN, ErrorCollector, normalize_email, strip_value
from shop.models import AuthToken, Role, User
from shop.services import audit

TOKEN_BYTES = 32
TOKEN_LIFETIME = timedelta(hours=24)
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 64
EMAIL_MAX_LENGTH = 254
FULL_NAME_MAX_LENGTH = 50


# trace: ADDR-002
@dataclass(frozen=True)
class IssuedToken:
    """発行した認証トークン（平文は応答にのみ用いる）。"""

    value: str
    expires_at: object
    user: User


# trace: ADDR-008
def validate_password(password: str, normalized_email: str, errors: ErrorCollector, field: str = "password") -> None:
    """パスワードの文字数・文字種の条件を判定する（NFR-SC-16。ハッシュ化の前に行う）。"""
    if password == "":
        errors.add(field, "パスワードを入力してください。")
        return
    if len(password) < PASSWORD_MIN_LENGTH or len(password) > PASSWORD_MAX_LENGTH:
        errors.add(field, "パスワードは8文字以上64文字以下で入力してください。")
        return
    if not any(char.isascii() and char.isalpha() for char in password):
        errors.add(field, "パスワードは英字を1文字以上含めてください。")
    if not any(char.isascii() and char.isdigit() for char in password):
        errors.add(field, "パスワードは数字を1文字以上含めてください。")
    if password.lower() == normalized_email:
        errors.add(field, "パスワードにメールアドレスと同じ値は使用できません。")


# trace: ADDR-008
def hash_password(password: str) -> str:
    """パスワードをソルト付き一方向ハッシュへ変換する（ADDR-008 DD-002）。"""
    return make_password(password)


# trace: ADDR-008
def verify_password(password: str, password_hash: str) -> bool:
    """パスワードとハッシュ値を標準関数で照合する。"""
    return check_password(password, password_hash)


# trace: ADDR-008
def register_user(
    email: str,
    password: str,
    password_confirmation: str,
    full_name: str,
) -> User:
    """会員登録（FR-001）。購入者として1件登録する。"""
    normalized_email = normalize_email(email)
    normalized_name = strip_value(full_name)

    errors = ErrorCollector()
    if normalized_email == "":
        errors.add("email", "メールアドレスを入力してください。")
    elif len(normalized_email) > EMAIL_MAX_LENGTH:
        errors.add("email", "メールアドレスは254文字以下で入力してください。")
    elif not EMAIL_PATTERN.match(normalized_email):
        errors.add("email", "メールアドレスの形式で入力してください。")

    validate_password(password or "", normalized_email, errors)

    if (password_confirmation or "") == "":
        errors.add("password_confirmation", "パスワード（確認）を入力してください。")
    elif password_confirmation != password:
        errors.add("password_confirmation", "パスワードとパスワード（確認）が一致しません。")

    if normalized_name == "":
        errors.add("full_name", "氏名を入力してください。")
    elif len(normalized_name) > FULL_NAME_MAX_LENGTH:
        errors.add("full_name", "氏名は50文字以下で入力してください。")

    errors.raise_if_error()

    if User.objects.filter(email=normalized_email).exists():
        raise EmailAlreadyRegisteredError()

    try:
        with transaction.atomic():
            return User.objects.create(
                email=normalized_email,
                password_hash=hash_password(password),
                full_name=normalized_name,
                role=Role.BUYER,
                registered_at=timeutils.now(),
            )
    except IntegrityError as exc:
        raise EmailAlreadyRegisteredError() from exc


# trace: ADDR-002
def _hash_token(token_value: str) -> str:
    """トークン値の SHA-256 ハッシュ（16進文字列）を返す。"""
    return hashlib.sha256(token_value.encode("utf-8")).hexdigest()


# trace: ADDR-002, ADDR-008
def authenticate(email: str, password: str) -> User:
    """メールアドレスとパスワードで利用者を認証する（FR-002 手順1〜6）。"""
    normalized_email = normalize_email(email)
    errors = ErrorCollector()
    if normalized_email == "":
        errors.add("email", "メールアドレスを入力してください。")
    if (password or "") == "":
        errors.add("password", "パスワードを入力してください。")
    errors.raise_if_error()

    user = User.objects.filter(email=normalized_email).first()
    if user is None:
        audit.record_login_failure(None)
        raise InvalidCredentialsError()
    if not verify_password(password, user.password_hash):
        audit.record_login_failure(user.user_id)
        raise InvalidCredentialsError()
    return user


# trace: ADDR-002
def issue_token(user: User) -> IssuedToken:
    """認証トークンを新規に1件発行する（既存トークンは無効化しない）。"""
    token_value = secrets.token_urlsafe(TOKEN_BYTES)
    issued_at = timeutils.now()
    expires_at = issued_at + TOKEN_LIFETIME
    AuthToken.objects.create(
        user=user,
        token_hash=_hash_token(token_value),
        issued_at=issued_at,
        expires_at=expires_at,
    )
    return IssuedToken(value=token_value, expires_at=expires_at, user=user)


# trace: ADDR-002
def login_with_token(email: str, password: str) -> IssuedToken:
    """ログイン（FR-002）。認証トークンを発行し、監査ログを記録する。"""
    user = authenticate(email, password)
    with transaction.atomic():
        issued = issue_token(user)
        audit.record_login_success(user.user_id)
    return issued


# trace: ADDR-002
def login_for_session(email: str, password: str) -> User:
    """画面ログイン（FR-002）。利用者を認証し、監査ログを記録する。"""
    user = authenticate(email, password)
    audit.record_login_success(user.user_id)
    return user


# trace: ADDR-002
def resolve_token(token_value: str) -> tuple[User, AuthToken]:
    """認証トークンを検証し、利用者とトークンを返す（無効なら認証エラー）。"""
    if not token_value:
        raise AuthenticationRequiredError()
    token = AuthToken.objects.select_related("user").filter(token_hash=_hash_token(token_value)).first()
    if token is None or token.revoked_at is not None or timeutils.now() >= token.expires_at:
        raise AuthenticationRequiredError()
    return token.user, token


# trace: ADDR-002
def logout_token(token: AuthToken) -> None:
    """ログアウト（FR-003）。要求に使われたトークンのみ無効化する。"""
    with transaction.atomic():
        token.revoked_at = timeutils.now()
        token.save(update_fields=["revoked_at"])
        audit.record_logout(token.user_id)


# trace: ADDR-002
def logout_session(user: User) -> None:
    """画面ログアウト（FR-003）。監査ログを記録する（セッション破棄は web 層が行う）。"""
    audit.record_logout(user.user_id)


# trace: ADDR-002
def find_user(raw_user_id: Any) -> User | None:
    """利用者IDから利用者を取得する（該当なしは None）。画面のセッション復元に用いる。"""
    if not raw_user_id:
        return None
    return User.objects.filter(user_id=raw_user_id).first()


# trace: ADDR-002
def require_authenticated(user: User | None) -> User:
    """認証済みであることを判定する（CMN-02）。"""
    if user is None:
        raise AuthenticationRequiredError()
    return user


# trace: ADDR-002
def is_admin(user: User | None) -> bool:
    """利用者が管理者かどうかを返す（表示の切替に用いる）。"""
    return user is not None and user.role == Role.ADMIN


# trace: ADDR-002
def require_buyer(user: User | None) -> User:
    """購入者だけが利用できる機能の権限判定を行う（CMN-03）。"""
    require_authenticated(user)
    if user.role != Role.BUYER:
        raise PermissionDeniedError()
    return user


# trace: ADDR-002
def require_admin(user: User | None) -> User:
    """管理者だけが利用できる機能の権限判定を行う（CMN-03）。"""
    require_authenticated(user)
    if user.role != Role.ADMIN:
        raise PermissionDeniedError()
    return user


# trace: ADDR-002
def user_payload(user: User) -> dict[str, object]:
    """ログイン利用者情報（FR-004）の応答内容を組み立てる。"""
    return {
        "user_id": user.user_id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
    }
