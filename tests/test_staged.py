import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".harness" / "bench"))
import staged


def test_parse_score_counts_stage_only():
    text = """PASSED _hidden_tests/test_s1.py::passes
FAILED _hidden_tests/test_s2.py::fails - mismatch
ERROR _hidden_tests/test_s2.py::errors
PASSED _hidden_tests/test_s11.py::other_stage
"""
    assert staged.parse_score(text, 1) == {
        "all_passed": 2,
        "all_failed": 2,
        "stage_passed": 1,
        "stage_failed": 0,
    }


def test_transcript_usage_window_dedup_cache_and_context():
    start = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    end = datetime(2026, 1, 1, 12, 10, tzinfo=timezone.utc)
    lines = [
        '{"timestamp":"2026-01-01T11:59:59Z","requestId":"old","message":{"usage":{"input_tokens":100,"output_tokens":10},"model":"fake"}}',
        '{"timestamp":"2026-01-01T12:01:00Z","subtype":"compact_boundary","requestId":"compact","message":{}}',
        '{"timestamp":"2026-01-01T12:02:00Z","requestId":"five","message":{"usage":{"input_tokens":10,"output_tokens":5,"cache_creation":{"ephemeral_5m_input_tokens":100,"ephemeral_1h_input_tokens":200},"cache_read_input_tokens":1000},"model":"fake"}}',
        '{"timestamp":"2026-01-01T12:03:00Z","requestId":"fallback","message":{"usage":{"input_tokens":20,"output_tokens":10,"cache_creation_input_tokens":300,"cache_read_input_tokens":2000},"model":"fake"}}',
        '{"timestamp":"2026-01-01T12:04:00Z","requestId":"replace","message":{"usage":{"input_tokens":999,"output_tokens":999},"model":"fake"}}',
        '{"timestamp":"2026-01-01T12:05:00Z","requestId":"replace","message":{"usage":{"input_tokens":40,"output_tokens":20,"cache_creation_input_tokens":400,"cache_read_input_tokens":3000},"model":"fake"}}',
        '{"timestamp":"2026-01-01T12:11:00Z","requestId":"late","message":{"usage":{"input_tokens":7,"output_tokens":7},"model":"fake"}}',
    ]
    result = staged.transcript_usage(
        lines, start, end, {"fake": (2.0, 10.0, 0.2)}
    )
    assert result["main_input"] == 10 + 20 + 40
    assert result["main_output"] == 5 + 10 + 20
    assert result["main_cache_write"] == 300 + 300 + 400
    assert result["main_cache_read"] == 1000 + 2000 + 3000
    # 70 input/output/cache reads, 5m writes priced at 1.25x, and 1h at 2x.
    assert result["main_usd_est"] == (
        70 * 2.0 + 35 * 10.0 + 6000 * 0.2 + 800 * 1.25 * 2.0 + 200 * 2.0 * 2.0
    ) / 1_000_000
    assert result["ctx_end_tokens"] == 40 + 3000 + 400
    assert result["compactions"] == 1


def test_transcript_usage_dedup_and_unknown_price():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = datetime(2026, 1, 1, 0, 0, 10, tzinfo=timezone.utc)
    lines = [
        '{"timestamp":"2026-01-01T00:00:01Z","requestId":"dupe","message":{"usage":{"input_tokens":100,"output_tokens":100},"model":"known"}}',
        '{"timestamp":"2026-01-01T00:00:09Z","requestId":"dupe","message":{"usage":{"input_tokens":2,"output_tokens":3,"cache_creation_input_tokens":4,"cache_read_input_tokens":5},"model":"unknown"}}',
        '{"timestamp":"2026-01-01T00:00:02Z","isCompactSummary":true,"message":{}}',
    ]
    result = staged.transcript_usage(lines, start, end, {"known": (1, 2, 3)})
    assert result["main_input"] == 2
    assert result["main_output"] == 3
    assert result["main_cache_write"] == 4
    assert result["main_cache_read"] == 5
    assert result["main_usd_est"] == 0.0
    assert result["ctx_end_tokens"] == 2 + 4 + 5
    assert result["compactions"] == 1


def test_csv_line_uses_columns_and_replaces_commas():
    row = {column: index for index, column in enumerate(staged.COLUMNS)}
    row["note"] = "plan, then verify"
    parts = staged.csv_line(row).split(",")
    assert len(parts) == len(staged.COLUMNS)
    assert parts == [str(row[column]).replace(",", ";") for column in staged.COLUMNS]
    assert parts[-1] == "plan; then verify"


def test_claude_call_returns_error_note(monkeypatch, tmp_path):
    monkeypatch.setattr(
        staged.bench,
        "_claude",
        lambda *args: {"is_error": True, "_s": 60},
    )

    _, _, _, note_add = staged._claude_call(
        "prompt", tmp_path, None, "plan", 1, ""
    )

    assert note_add == "plan error; "


def test_score_returns_crash_note(monkeypatch, tmp_path):
    (tmp_path / "stage_runs").mkdir()
    monkeypatch.setattr(
        staged.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args, 2, stdout="pytest crashed\n", stderr=""
        ),
    )

    counts, note_add = staged._score(tmp_path, "shop", 1, "")

    assert counts == {
        "all_passed": 0,
        "all_failed": 1,
        "stage_passed": 0,
        "stage_failed": 1,
    }
    assert note_add == "score crashed; "
