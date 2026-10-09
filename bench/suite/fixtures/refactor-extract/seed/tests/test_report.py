from report import build, parse_lines, render, summarize

SAMPLE = (
    "2024-05-01 INFO started job 120ms\n"
    "2024-05-01 ERROR disk full 300ms\n"
    "not a log line\n"
    "\n"
    "2024-05-02 INFO finished job 45ms\n"
    "2024-05-03 WARN slow query 210ms\n"
)

GOLDEN = (
    "records: 4\n"
    "first: 2024-05-01\n"
    "last: 2024-05-03\n"
    "total_ms: 675\n"
    "max_ms: 300\n"
    "slowest: disk full\n"
    "levels:\n"
    "  ERROR: 1\n"
    "  INFO: 2\n"
    "  WARN: 1\n"
)


def test_parse_lines_skips_bad_lines():
    records = parse_lines(SAMPLE)
    assert len(records) == 4
    assert records[0] == {"date": "2024-05-01", "level": "INFO",
                          "message": "started job", "ms": 120}


def test_summarize_counts_levels_and_durations():
    summary = summarize(parse_lines(SAMPLE))
    assert summary["total"] == 4
    assert summary["levels"] == {"ERROR": 1, "INFO": 2, "WARN": 1}
    assert summary["total_ms"] == 675
    assert summary["max_ms"] == 300


def test_render_contains_levels_block():
    text = render(summarize(parse_lines(SAMPLE)))
    assert text.endswith("levels:\n  ERROR: 1\n  INFO: 2\n  WARN: 1\n")


def test_build_matches_golden_output():
    assert build(SAMPLE) == GOLDEN
