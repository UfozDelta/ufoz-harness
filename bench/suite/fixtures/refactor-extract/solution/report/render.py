"""Render a summary dict as plain text."""


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
