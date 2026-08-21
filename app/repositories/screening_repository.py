"""Screening Repository (FR-004 / FR-009)。"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.screening import Screening


class ScreeningRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_by_movie(self, movie_id: int) -> list[Screening]:
        return list(
            self.db.execute(
                select(Screening)
                .where(Screening.movie_id == movie_id)
                .order_by(Screening.starts_at.asc())
            ).scalars()
        )

    def get(self, screening_id: int) -> Screening | None:
        return self.db.get(Screening, screening_id)

    def get_for_update(self, screening_id: int) -> Screening | None:
        """残席更新用に対象行を悲観ロックで取得する (ADR-007)。"""
        stmt = select(Screening).where(Screening.id == screening_id).with_for_update()
        return self.db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def is_saleable(screening: Screening, now: datetime | None = None) -> bool:
        """販売可能かを判定する (C-DATA-002 / FR-009: 上映開始前/販売期間内)。"""
        now = now or datetime.now(timezone.utc)
        starts = _aware(screening.starts_at)
        if starts <= now:  # 上映開始後は購入不可
            return False
        if screening.sales_start_at and _aware(screening.sales_start_at) > now:
            return False
        if screening.sales_end_at and _aware(screening.sales_end_at) < now:
            return False
        return True


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
