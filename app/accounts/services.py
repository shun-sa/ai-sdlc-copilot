# trace: ADDR-002, ADDR-003, ADDR-004, ADDR-001, ADDR-012, ENT-001, ENT-015
"""会員・認証の業務処理（FR-001〜FR-004）。画面と Web API の双方から呼ばれる（ADDR-012）。"""

import hashlib
import re
import secrets
from collections.abc import Callable
from datetime import timedelta
from typing import Any

from django.contrib.auth.hashers import check_password, make_password
from django.db import DatabaseError, IntegrityError, transaction

from accounts.models import ApiLoginState, User
from audit import services as audit
from common import clock, codes
from common.codes import UserType
from common.errors import (
    AuthenticationFailedError,
    BusinessError,
    FieldErrors,
    authentication_required,
    from_record,
    system_failure,
)
from common.normalize import has_surrogates, has_unstorable_chars, strip_text, unstorable_message
from common.submit_token import NO_TOKEN, TokenContext

API_LOGIN_LIFETIME = timedelta(hours=24)
_EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\Z")
_LETTER = re.compile(r"[A-Za-z]")
_DIGIT = re.compile(r"[0-9]")
_DUMMY_HASH: list[str] = []
# ダミー照合で UTF-8 に符号化できない入力の代わりに用いる固定値（入力から導かない：ADDR-003 INV-005）
_UNENCODABLE_STANDIN = "\ufffd"

MSG_AUTH_FAILED = "メールアドレスまたはパスワードが正しくありません。"
MSG_EMAIL_REGISTERED = "このメールアドレスは既に登録されています。"


# trace: ADDR-003, ENT-001
def normalize_email(raw: Any) -> Any:
    """前後の空白を除去し全体を英小文字にする（CMN-01、CMN-15）。文字列以外はそのまま返す。"""
    value = strip_text(raw)
    if isinstance(value, str):
        return value.lower()
    return value


# trace: ENT-001, ADDR-012
def email_violations(email: Any) -> list[tuple[str, str]]:
    """メールアドレスの値域（正規化後254文字以下・形式）の違反を返す。"""
    if email is None or email == "":
        return [(codes.FIELD_REQUIRED, "メールアドレスを入力してください。")]
    if not isinstance(email, str):
        return [(codes.FIELD_INVALID_TYPE, "メールアドレスは文字列で入力してください。")]
    if has_unstorable_chars(email):
        # 制御文字（NUL）・文字でない値はメールアドレスの形式に当たらない（保存前に入力エラーとする）
        return [(codes.FIELD_INVALID_FORMAT, "メールアドレスの形式で入力してください。")]
    if len(email) > 254:
        return [(codes.FIELD_INVALID_LENGTH, "メールアドレスは254文字以内で入力してください。")]
    if not _EMAIL_PATTERN.match(email):
        return [(codes.FIELD_INVALID_FORMAT, "メールアドレスの形式で入力してください。")]
    return []


# trace: ADDR-003, ENT-001
def password_violations(password: Any, normalized_email: Any) -> list[tuple[str, str]]:
    """パスワードの条件（8〜64文字、英字・数字を各1文字以上、メールアドレスと同一でない）の違反を返す。

    前後の空白は除去せず、大文字小文字の変換もしない（ADDR-003 INV-002）。
    NUL・制御文字を理由とする入力エラー・除去・正規化は行わない（ADDR-003 DD-007。入力規則は要件の条件だけ）。
    Unicode の文字でない値（対になっていないサロゲート）は Unicode のスカラー値の列でなく文字列として扱えない
    （UTF-8 に符号化できず保持値を生成できない）ため型の誤りとする（ADDR-003 DC-005 の対象外）。
    """
    if password is None or password == "":
        return [(codes.FIELD_REQUIRED, "パスワードを入力してください。")]
    if not isinstance(password, str) or has_surrogates(password):
        return [(codes.FIELD_INVALID_TYPE, "パスワードは文字列で入力してください。")]
    violations: list[tuple[str, str]] = []
    if len(password) < 8 or len(password) > 64:
        violations.append((codes.FIELD_INVALID_LENGTH, "パスワードは8〜64文字で入力してください。"))
    if not _LETTER.search(password) or not _DIGIT.search(password):
        violations.append((codes.FIELD_INVALID_FORMAT, "パスワードには英字と数字をそれぞれ1文字以上含めてください。"))
    if isinstance(normalized_email, str) and normalized_email and password.lower() == normalized_email:
        violations.append((codes.FIELD_INVALID_FORMAT, "メールアドレスと同じ文字列はパスワードに使用できません。"))
    return violations


# trace: ENT-001, ADDR-012
def name_violations(name: Any) -> list[tuple[str, str]]:
    """氏名（前後の空白除去後に1〜50文字）の違反を返す。"""
    if name is None or name == "":
        return [(codes.FIELD_REQUIRED, "氏名を入力してください。")]
    if not isinstance(name, str):
        return [(codes.FIELD_INVALID_TYPE, "氏名は文字列で入力してください。")]
    if has_unstorable_chars(name):
        return [(codes.FIELD_INVALID_FORMAT, unstorable_message("氏名"))]
    if len(name) > 50:
        return [(codes.FIELD_INVALID_LENGTH, "氏名は50文字以内で入力してください。")]
    return []


# trace: ENT-001, ADDR-001
def user_summary(user: User) -> dict[str, Any]:
    return {
        "user_id": user.pk,
        "email": user.email,
        "name": user.name,
        "user_type": user.user_type,
        "user_type_label": UserType(user.user_type).label,
    }


# trace: ADDR-003, ADDR-004, ENT-001, ADDR-001
def register(email: Any, password: Any, password_confirmation: Any, name: Any) -> dict[str, Any]:
    """FR-001 会員登録。利用者区分は購入者に固定し、要求の他の項目は反映しない（ADDR-001 DD-008）。"""
    normalized_email = normalize_email(email)
    normalized_name = strip_text(name)
    errors = FieldErrors()
    for reason, message in email_violations(normalized_email):
        errors.add("email", reason, message)
    for reason, message in password_violations(password, normalized_email):
        errors.add("password", reason, message)
    if password_confirmation is None or password_confirmation == "":
        errors.add("password_confirmation", codes.FIELD_REQUIRED, "パスワード（確認）を入力してください。")
    elif password_confirmation != password:
        errors.add("password_confirmation", codes.FIELD_MISMATCH, "パスワード（確認）がパスワードと一致しません。")
    for reason, message in name_violations(normalized_name):
        errors.add("name", reason, message)
    errors.raise_if_any("E-001-01")

    if User.objects.filter(email=normalized_email).exists():
        raise BusinessError("E-001-02", MSG_EMAIL_REGISTERED, reason=codes.REASON_EMAIL_ALREADY_REGISTERED)
    now = clock.now_seconds()
    try:
        with transaction.atomic():
            user = User(
                email=normalized_email,
                name=normalized_name,
                user_type=UserType.BUYER,
                registered_at=now,
                password=make_password(password),
            )
            user.save()
    except IntegrityError:
        # 同一メールアドレスの同時登録で他方が先に確定した（ADDR-004 DD-009）
        raise BusinessError("E-001-02", MSG_EMAIL_REGISTERED, reason=codes.REASON_EMAIL_ALREADY_REGISTERED) from None
    except DatabaseError as exc:
        raise system_failure("E-001-03") from exc
    result = user_summary(user)
    result["registered_at"] = user.registered_at
    return result


# trace: ADDR-003
def _dummy_hash() -> str:
    if not _DUMMY_HASH:
        _DUMMY_HASH.append(make_password(secrets.token_urlsafe(16)))
    return _DUMMY_HASH[0]


# trace: ADDR-003, ADDR-004, ENT-015
def verify_credentials(email: Any, password: Any) -> User:
    """FR-002 手順1〜6。照合した要求は成否の監査ログを必ず1件記録する（ADDR-004 DD-016）。

    入力エラー（E-002-01）は未入力の場合だけとし、形式・文字の判定は行わない（FR-002 6.2.3）。
    データベースが受理しない文字（NUL 等）を含むメールアドレスは照会せず該当する利用者なし（手順4）として扱う。
    パスワードは NUL・制御文字を含んでも変換・判定せず check_password の結果だけで一致を判定する
    （ADDR-003 INV-001・DD-007）。Unicode の文字でない値を含むパスワードは登録・投入で型の誤りとなり
    保持されることがないため、登録されたどのパスワードとも一致しない（手順6の不一致）。
    """
    normalized_email = normalize_email(email)
    errors = FieldErrors()
    if normalized_email is None or normalized_email == "":
        errors.add("email", codes.FIELD_REQUIRED, "メールアドレスを入力してください。")
    elif not isinstance(normalized_email, str):
        errors.add("email", codes.FIELD_INVALID_TYPE, "メールアドレスを入力してください。")
    if password is None or password == "":
        errors.add("password", codes.FIELD_REQUIRED, "パスワードを入力してください。")
    elif not isinstance(password, str):
        errors.add("password", codes.FIELD_INVALID_TYPE, "パスワードを入力してください。")
    errors.raise_if_any("E-002-01")

    user = None
    if not has_unstorable_chars(normalized_email):
        try:
            user = User.objects.filter(email=normalized_email).first()
        except DatabaseError as exc:
            raise system_failure("E-002-03") from exc
    if user is None:
        _dummy_check(password)  # 同じ方式の照合計算を1回行う（ADDR-003 DD-004）
        _record_failure(None)
        raise AuthenticationFailedError("E-002-02", MSG_AUTH_FAILED)
    if has_surrogates(password):
        _dummy_check(password)  # 不一致が確定していても照合計算を1回行う
        _record_failure(user.pk)
        raise AuthenticationFailedError("E-002-02", MSG_AUTH_FAILED)
    if not user.check_password(password):
        _record_failure(user.pk)
        raise AuthenticationFailedError("E-002-02", MSG_AUTH_FAILED)
    return user


# trace: ADDR-003
def _dummy_check(password: str) -> None:
    """不一致が確定している要求で、同じハッシャーの照合計算を1回だけ行う（ADDR-003 DD-004）。結果は使わない。

    UTF-8 に符号化できない値（対になっていないサロゲート）を含む入力は、入力から導かない固定の代替値で計算する
    （パスワードを変換して照合に用いない：ADDR-003 INV-005）。
    """
    check_password(_UNENCODABLE_STANDIN if has_surrogates(password) else password, _dummy_hash())


# trace: ENT-015, ADDR-004
def _record_failure(user_id: int | None) -> None:
    """ログイン失敗の監査ログはエラー終了時も残るよう別にコミットする（ADDR-004 DD-007）。"""
    try:
        with transaction.atomic():
            audit.record_login_failure(user_id, clock.now_seconds())
    except DatabaseError as exc:
        raise system_failure("E-002-03") from exc


# trace: ADDR-002, ADDR-004, ENT-015
def login_web(
    email: Any,
    password: Any,
    replay: TokenContext,
    start_session: Callable[[User], None],
) -> User | None:
    """FR-002 ログイン（画面）。

    使用済みトークンの要求では手順1〜9をいずれも行わず、先着の記録済みの結果だけを通知する
    （ADDR-004 DD-013・DD-016・DD-017）。先着が成功していた場合は None を返し、新たなログイン状態を作らない。
    """
    if replay.used:
        prior = replay.prior
        if not prior:
            raise system_failure("E-002-03")
        if prior.get("status") == "success":
            return None
        raise from_record(prior)
    user = verify_credentials(email, password)
    try:
        with transaction.atomic():
            start_session(user)
            audit.record_login_success(user.pk, clock.now_seconds())
    except DatabaseError as exc:
        raise system_failure("E-002-03") from exc
    return user


# trace: ADDR-002, ENT-015, ADDR-001
def login_api(email: Any, password: Any) -> dict[str, Any]:
    """FR-002 ログイン（Web API）。256ビットの乱数の値を発行し照合値だけを保持する（ADDR-002 DD-001）。"""
    user = verify_credentials(email, password)
    now = clock.now_seconds()
    token = secrets.token_urlsafe(32)
    expires_at = now + API_LOGIN_LIFETIME
    try:
        with transaction.atomic():
            ApiLoginState.objects.create(
                token_hash=_hash_token(token), user=user, logged_in_at=now, expires_at=expires_at
            )
            audit.record_login_success(user.pk, now)
    except DatabaseError as exc:
        raise system_failure("E-002-03") from exc
    return {"token": token, "expires_at": expires_at, "user": user_summary(user)}


# trace: ADDR-002
def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# trace: ADDR-002
def resolve_api_token(token: str) -> tuple[User, ApiLoginState] | None:
    """判定時刻（秒単位切り捨て）＜有効期限日時の場合だけ有効（ADDR-002 DD-002）。"""
    state = ApiLoginState.objects.select_related("user").filter(token_hash=_hash_token(token)).first()
    if state is None:
        return None
    if not clock.now_seconds() < state.expires_at:
        return None
    return state.user, state


# trace: ADDR-002, ENT-015
def logout_api(user: Any, state: Any) -> None:
    """FR-003 ログアウト（Web API）。要求に使われたログイン状態だけを削除する（ADDR-002 DD-003）。"""
    if user is None or state is None:
        raise authentication_required("E-003-01")
    try:
        with transaction.atomic():
            locked = ApiLoginState.objects.select_for_update().filter(pk=state.pk).first()
            if locked is None:
                raise authentication_required("E-003-01")
            locked.delete()
            audit.record_logout(user.pk, clock.now_seconds())
    except DatabaseError as exc:
        raise system_failure("E-003-02") from exc


# trace: ADDR-002, ENT-015
def logout_web(user: Any, end_session: Callable[[], None], replay: TokenContext = NO_TOKEN) -> None:
    """FR-003 ログアウト（画面）。セッションの破棄と監査ログの記録を1トランザクションで行う。"""
    if user is None:
        raise authentication_required("E-003-01")
    try:
        with transaction.atomic():
            audit.record_logout(user.pk, clock.now_seconds())
            end_session()
    except DatabaseError as exc:
        raise system_failure("E-003-02") from exc


# trace: ENT-001, ADDR-001
def me(user: Any) -> dict[str, Any]:
    """FR-004 ログイン利用者情報照会（本人の利用者ID・メールアドレス・氏名・利用者区分）。"""
    if user is None:
        raise authentication_required("E-004-01")
    try:
        fresh = User.objects.get(pk=user.pk)
    except User.DoesNotExist:
        raise authentication_required("E-004-01") from None
    except DatabaseError as exc:
        raise system_failure("E-004-02") from exc
    return user_summary(fresh)


# trace: ADDR-002
def delete_all_login_states() -> None:
    """削除指定付きの一括投入で全ログイン状態（API・画面）を削除する（ADDR-002 DD-006）。"""
    from django.contrib.sessions.models import Session

    ApiLoginState.objects.all()._raw_delete(ApiLoginState.objects.db)
    Session.objects.all()._raw_delete(Session.objects.db)
