from datetime import datetime


def now_utc() -> datetime:
    """Current UTC time as a naive datetime."""
    return datetime.utcnow()


def from_timestamp(ts: float) -> datetime:
    """Naive UTC datetime for a POSIX timestamp."""
    return datetime.utcfromtimestamp(ts)


def age_seconds(then: datetime, now: datetime | None = None) -> float:
    """Seconds between `then` and `now` (default: now_utc())."""
    if now is None:
        now = now_utc()
    return (now - then).total_seconds()
