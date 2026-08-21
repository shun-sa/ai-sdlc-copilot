"""セッションレコード / セッション管理の追加単体テスト (ADR-004)。

対象: app/models/session.py, app/services/auth_service.py の get_session/logout 分岐
検証Requirement: ADR-004 (セッション有効期限・失効・破棄)。
DB Strategy: CONTAINER (使い捨てSQLite) / NOT_APPLICABLE (is_expired純粋判定)。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.session import SessionRecord
from app.services.auth_service import AuthService


class TestIsExpired:
    # ADR-004: 期限内セッションは失効していない
    def test_not_expired(self) -> None:
        record = SessionRecord(
            id="s1",
            user_id=1,
            csrf_token="c",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        assert record.is_expired() is False

    # ADR-004: 期限切れセッションは失効している
    def test_expired(self) -> None:
        record = SessionRecord(
            id="s2",
            user_id=1,
            csrf_token="c",
            expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        )
        assert record.is_expired() is True

    # naive datetime でも UTC とみなして判定する
    def test_expired_naive_datetime(self) -> None:
        naive_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        record = SessionRecord(
            id="s3",
            user_id=1,
            csrf_token="c",
            expires_at=naive_utc - timedelta(seconds=1),
        )
        assert record.is_expired() is True


class TestSessionLookup:
    # 未知IDやNoneは None を返す
    def test_get_session_none(self, db: Session) -> None:
        service = AuthService(db)
        assert service.get_session(None) is None
        assert service.get_session("does-not-exist") is None

    # ADR-004: 期限切れセッションは取得時に破棄され None を返す
    def test_expired_session_purged(self, db: Session) -> None:
        service = AuthService(db)
        record = SessionRecord(
            id="expired-token",
            user_id=1,
            csrf_token="c",
            expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        )
        service.sessions.add(record)
        db.commit()

        assert service.get_session("expired-token") is None
        # 破棄されている
        assert service.sessions.get("expired-token") is None

    # logout(None) は何もしない
    def test_logout_none_noop(self, db: Session) -> None:
        AuthService(db).logout(None)
