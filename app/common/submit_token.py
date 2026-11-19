# trace: ADDR-004
"""画面の二重送信防止（ADDR-004 4.3 の11、DD-010・DD-013・DD-015〜DD-017）の共通部品。

① 操作種別とトークンから導いたキーでセッション単位のアドバイザリロックを待機取得する
② 独立した短いトランザクションで（操作種別、トークンの照合値）を一意登録してコミットする
   （登録できた要求＝先着、一意違反＝同じ操作種別の使用済みトークン）
③ 業務処理（業務処理層の1トランザクション）を行う
④ 終了時に通知した結果を独立したトランザクションで記録する
⑤ finally でアドバイザリロックを解放する
トークンなし・形式不正のトークンの要求は通常どおり全手順を行う（Web API はトークンを渡さない）。
"""

import hashlib
import re
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from django.db import IntegrityError, connection, transaction

from common import clock
from common.errors import ServiceError
from common.models import SubmitToken

# 送信トークン専用のアドバイザリロックの名前空間（2引数形式の第1引数。一括投入・採番の固定キーと区別する）
SUBMIT_TOKEN_LOCK_NAMESPACE = 1296236545
_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{22,128}\Z")


# trace: ADDR-004
@dataclass(frozen=True)
class TokenContext:
    """業務処理へ渡す送信トークンの状態。"""

    active: bool = False  # トークン付きの画面の要求か
    used: bool = False  # 同じ操作種別で使用済みのトークンか
    prior: dict[str, Any] | None = None  # 先着の要求が通知した結果（記録がなければ None）


NO_TOKEN = TokenContext()


# trace: ADDR-004
def issue_token() -> str:
    """フォーム表示ごとに暗号論的乱数で1回限りの送信トークンを生成する（192ビット）。"""
    return secrets.token_urlsafe(24)


# trace: ADDR-004
def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# trace: ADDR-004
def _lock_key(operation: str, token_hash: str) -> int:
    digest = hashlib.sha256(f"{operation}:{token_hash}".encode()).digest()
    return int.from_bytes(digest[:4], "big", signed=True)


# trace: ADDR-004
def _record_outcome(operation: str, token_hash: str, outcome: dict[str, Any]) -> None:
    with transaction.atomic():
        SubmitToken.objects.filter(operation=operation, token_hash=token_hash, outcome__isnull=True).update(
            outcome=outcome
        )


# trace: ADDR-004
def run_with_token[T](
    operation: str,
    raw_token: Any,
    body: Callable[[TokenContext], T],
    outcome_of: Callable[[T], dict[str, Any]],
) -> T:
    """送信トークンの直列化・消費の確定・結果の記録を行って業務処理を実行する。"""
    if not isinstance(raw_token, str) or not _TOKEN_PATTERN.match(raw_token):
        return body(NO_TOKEN)

    token_hash = _token_hash(raw_token)
    key = _lock_key(operation, token_hash)
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_lock(%s, %s)", [SUBMIT_TOKEN_LOCK_NAMESPACE, key])
    try:
        used = False
        try:
            with transaction.atomic():
                SubmitToken.objects.create(operation=operation, token_hash=token_hash, created_at=clock.now_seconds())
        except IntegrityError:
            used = True
        prior = None
        if used:
            row = SubmitToken.objects.filter(operation=operation, token_hash=token_hash).only("outcome").first()
            prior = row.outcome if row is not None else None
        context = TokenContext(active=True, used=used, prior=prior)
        try:
            result = body(context)
        except ServiceError as exc:
            if not used:
                _record_outcome(operation, token_hash, exc.to_record())
            raise
        except Exception:
            if not used:
                _record_outcome(operation, token_hash, {"status": "error", "type": "system_error"})
            raise
        if not used:
            _record_outcome(operation, token_hash, outcome_of(result))
        return result
    finally:
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_unlock(%s, %s)", [SUBMIT_TOKEN_LOCK_NAMESPACE, key])
        except Exception:  # noqa: BLE001 - 接続が切れた場合は PostgreSQL がロックを解放する
            pass
