"""Parse log lines of the form ``YYYY-MM-DD LEVEL message NNNms``."""

import re

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
