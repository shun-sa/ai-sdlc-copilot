# trace: ADDR-002, ADDR-003
"""会員登録・認証・監査ログの業務ロジック（FR-001〜FR-004）。"""

from __future__ import annotations

import datetime as dt
import hashlib
import secrets
from typing import Any

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import IntegrityError, transaction

from accounts.models import (
    EVENT_LOGIN_FAILURE,
    EVENT_LOGIN_SUCCESS,
    EVENT_LOGOUT,
    RESULT_FAILURE,
    RESULT_SUCCESS,
    ROLE_BUYER,
    AuditLog,
    AuthToken,
    User,
)
from common import timeutils
from common.exceptions import (
    EmailAlreadyRegistered,
    InvalidCredentials,
    NotFoundError,
    business_error_for_integrity,
)
from common.validators import (
    ValidationCollector,
    is_email_format,
    normalize_email,
    normalize_text,
    password_violations,
)


# trace: ADDR-002
def hash_token(raw_token: str) -> str:
    """認証トークンの平文を SHA-256 ハッシュへ変換する。"""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


# trace: ADDR-002
def hash_password(raw_password: str) -> str:
    """パスワードを Django 標準の PBKDF2-HMAC-SHA256 でハッシュ化する。"""
    return make_password(raw_password)


# trace: ADDR-002
def record_audit(
    *,
    event_type: str,
    result: str,
    user_id: int | None = None,
    detail: str = "",
    occurred_at: dt.datetime | None = None,
) -> AuditLog:
    """監査ログを1件記録する（個人情報・パスワード・トークンは記録しない）。"""
    return AuditLog.objects.create(
        occurred_at=occurred_at or timeutils.now(),
        event_type=event_type,
        user_id=user_id,
        result=result,
        detail=detail,
    )


# trace: ADDR-002, ADDR-003
def register_user(payload: dict[str, Any]) -> User:
    """会員登録（FR-001）。購入者として1件登録する。"""
    email = normalize_email(payload.get("email"))
    full_name = normalize_text(payload.get("full_name"))
    password = payload.get("password") or ""
    password_confirmation = payload.get("password_confirmation") or ""

    collector = ValidationCollector()
    if not email:
        collector.add("email", "メールアドレスを入力してください。")
    elif len(email) > 254:
        collector.add("email", "メールアドレスは254文字以内で入力してください。")
    elif not is_email_format(email):
        collector.add("email", "メールアドレスの形式で入力してください。")
    if not password:
        collector.add("password", "パスワードを入力してください。")
    else:
        for reason in password_violations(password, email):
            collector.add("password", reason)
    if not password_confirmation:
        collector.add("password_confirmation", "パスワード（確認）を入力してください。")
    elif password and password_confirmation != password:
        collector.add("password_confirmation", "パスワードと一致しません。")
    if not full_name:
        collector.add("full_name", "氏名を入力してください。")
    elif len(full_name) > 50:
        collector.add("full_name", "氏名は50文字以内で入力してください。")
    collector.raise_if_any()

    if User.objects.filter(email=email).exists():
        raise EmailAlreadyRegistered()
    try:
        with transaction.atomic():
            return User.objects.create(
                email=email,
                password_hash=hash_password(password),
                full_name=full_name,
                role=ROLE_BUYER,
                registered_at=timeutils.now(),
            )
    except IntegrityError as exc:
        converted = business_error_for_integrity(exc)
        if converted is not None:
            raise converted
        raise


# trace: ADDR-002
def authenticate(email_input: Any, password_input: Any) -> User:
    """メールアドレスとパスワードを照合する（FR-002 手順1〜8）。"""
    email = normalize_email(email_input)
    password = password_input or ""

    collector = ValidationCollector()
    if not email:
        collector.add("email", "メールアドレスを入力してください。")
    if not password:
        collector.add("password", "パスワードを入力してください。")
    collector.raise_if_any()

    user = User.objects.filter(email=email).first()
    if user is None:
        record_audit(event_type=EVENT_LOGIN_FAILURE, result=RESULT_FAILURE, user_id=None)
        raise InvalidCredentials()
    if not check_password(password, user.password_hash):
        record_audit(event_type=EVENT_LOGIN_FAILURE, result=RESULT_FAILURE, user_id=user.pk)
        raise InvalidCredentials()
    record_audit(event_type=EVENT_LOGIN_SUCCESS, result=RESULT_SUCCESS, user_id=user.pk)
    return user


# trace: ADDR-002
def issue_token(user: User) -> tuple[str, AuthToken]:
    """認証トークンを1件発行する（平文は応答にのみ用いる）。"""
    raw_token = secrets.token_urlsafe(32)
    issued_at = timeutils.now()
    token = AuthToken.objects.create(
        token_hash=hash_token(raw_token),
        user=user,
        issued_at=issued_at,
        expires_at=issued_at + dt.timedelta(hours=settings.AUTH_TOKEN_LIFETIME_HOURS),
    )
    return raw_token, token


# trace: ADDR-002
def login_api(email_input: Any, password_input: Any) -> tuple[User, str, AuthToken]:
    """API のログイン（FR-002）。利用者の照合と認証トークンの発行を行う。"""
    user = authenticate(email_input, password_input)
    raw_token, token = issue_token(user)
    return user, raw_token, token


# trace: ADDR-002
def resolve_auth_token(raw_token: str) -> tuple[User, AuthToken] | None:
    """提示されたトークンを検証する（ハッシュ一致・有効期限内・未無効化）。"""
    token = (
        AuthToken.objects.select_related("user")
        .filter(token_hash=hash_token(raw_token), revoked_at__isnull=True)
        .first()
    )
    if token is None:
        return None
    if token.expires_at <= timeutils.now():
        return None
    return token.user, token


# trace: ADDR-002
def logout(token: AuthToken) -> None:
    """要求に使われた認証トークンだけを無効化する（FR-003）。"""
    with transaction.atomic():
        token.revoked_at = timeutils.now()
        token.save(update_fields=["revoked_at"])
        record_audit(event_type=EVENT_LOGOUT, result=RESULT_SUCCESS, user_id=token.user_id)


# trace: ADDR-002
def logout_session(user: User) -> None:
    """画面のログアウト（ログインセッションの終了に伴う監査ログ）。"""
    record_audit(event_type=EVENT_LOGOUT, result=RESULT_SUCCESS, user_id=user.pk)


# trace: ADDR-002
def get_user(user_id: int) -> User:
    """利用者を取得する（存在しない場合は対象なし）。"""
    user = User.objects.filter(pk=user_id).first()
    if user is None:
        raise NotFoundError()
    return user
