"""Log report: parse log lines, summarize them, and render the summary as text.

Each log line has the form ``YYYY-MM-DD LEVEL message NNNms``. Lines that do
not match that shape are skipped.
"""

import re
from collections import Counter

LINE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}) (\w+) (.*) (\d+)ms$")


def parse_lines(text):
    """Turn log text into a list of record dicts, skipping lines that do not match."""
    records = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        match = LINE_RE.match(line)
        if match is None:
            continue
        date, level, message, ms = match.groups()
        records.append({"date": date, "level": level, "message": message, "ms": int(ms)})
    return records


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


def render(summary):
    """Render a summary dict as a plain-text block ending in a newline."""
    lines = [
        f"records: {summary['total']}",
        f"first: {summary['first'] or '-'}",
        f"last: {summary['last'] or '-'}",
        f"total_ms: {summary['total_ms']}",
        f"max_ms: {summary['max_ms']}",
        f"slowest: {summary['slowest'] or '-'}",
        "levels:",
    ]
    for name, count in summary["levels"].items():
        lines.append(f"  {name}: {count}")
    return "\n".join(lines) + "\n"


def build(text):
    """Full pipeline: parse the log text, summarize it, and render the result."""
    return render(summarize(parse_lines(text)))
