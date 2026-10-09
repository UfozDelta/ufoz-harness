"""Summarize parsed log records."""

from collections import Counter


def summarize(records):
    """Count records per level, total and max their durations, and find the slowest one."""
    if not records:
        return {
            "total": 0,
            "first": None,
            "last": None,
            "levels": {},
            "total_ms": 0,
            "max_ms": 0,
            "slowest": None,
        }
    levels = Counter(record["level"] for record in records)
    durations = [record["ms"] for record in records]
    slowest = max(records, key=lambda record: record["ms"])
    dates = [record["date"] for record in records]
    return {
        "total": len(records),
        "first": min(dates),
        "last": max(dates),
        "levels": {name: levels[name] for name in sorted(levels)},
        "total_ms": sum(durations),
        "max_ms": max(durations),
        "slowest": slowest["message"],
    }
