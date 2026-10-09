"""Log report package: parse log lines, summarize them, and render the summary as text."""

from report.parse import parse_lines
from report.render import render
from report.summarize import summarize

__all__ = ["build", "parse_lines", "render", "summarize"]


def build(text):
    """Full pipeline: parse the log text, summarize it, and render the result."""
    return render(summarize(parse_lines(text)))
