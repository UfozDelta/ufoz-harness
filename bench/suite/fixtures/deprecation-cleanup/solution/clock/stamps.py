from datetime import datetime, timezone


def now_utc() -> datetime:
    """Current UTC time as a naive datetime."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def from_timestamp(ts: float) -> datetime:
    """Naive UTC datetime for a POSIX timestamp."""
    return datetime.fromtimestamp(ts, timezone.utc).replace(tzinfo=None)


def age_seconds(then: datetime, now: datetime | None = None) -> float:
    """Seconds between `then` and `now` (default: now_utc())."""
    if now is None:
        now = now_utc()
    return (now - then).total_seconds()
