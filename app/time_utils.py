from datetime import datetime, timezone


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


_as_aware = ensure_aware


def is_within_period(
    reference: datetime,
    start: datetime | None,
    end: datetime | None,
) -> bool:
    """referenceが[start, end]の販売期間内かを判定する。"""
    reference = _as_aware(reference)
    if start is not None and reference < _as_aware(start):
        return False
    if end is not None and reference > _as_aware(end):
        return False
    return True


def format_datetime(value: datetime) -> str:
    """C-UI-005: YYYY/MM/DD HH:mm 形式で表示する。"""
    return _as_aware(value).strftime("%Y/%m/%d %H:%M")


def format_yen(amount: int) -> str:
    """C-UI-004: 税込・3桁区切り円表記で表示する（例: 1,980円）。"""
    return f"{amount:,}円"
