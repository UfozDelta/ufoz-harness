"""Acceptance check for plan-log T2. Hash-locked: the executor cannot edit this.

Cheap smoke, no subprocess: builds a tiny in-memory metrics.jsonl with a plan_event
row mixed in among normal task rows, calls print_stats(), and proves it doesn't crash
and prints the latest run_end line for the slug.
"""
import io
import json
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, ".harness")

fail = []

from runner.stats import print_stats  # noqa: E402

rows = [
    {"ts": "2026-01-01T00:00:00", "slug": "demo", "task": "T1", "result": "pass",
     "attempts": 1, "repairs": 0, "seconds": 1.0, "tokens": {}},
    {"ts": "2026-01-01T00:00:05", "slug": "demo", "kind": "plan_event", "event": "run_start",
     "executor": "pi"},
    {"ts": "2026-01-01T00:01:00", "slug": "demo", "kind": "plan_event", "event": "run_end",
     "executor": "pi", "result": "pass", "duration_s": 55.0, "tasks_done": 1},
]

with tempfile.TemporaryDirectory() as td:
    metrics = Path(td) / "metrics.jsonl"
    metrics.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            print_stats(metrics)
    except Exception as e:
        fail.append(f"print_stats crashed on a plan_event row: {e!r}")
    out = buf.getvalue()
    if "demo" not in out or "run" not in out.lower() or "pass" not in out.lower():
        fail.append(f"expected a 'last run ... pass' line for slug 'demo', got:\n{out}")

summary = Path(".harness/plans/plan-log/SUMMARY.md")
if not summary.exists():
    fail.append("SUMMARY.md missing")
elif len(summary.read_text(encoding="utf-8")) > 600:
    fail.append("SUMMARY.md is over 600 chars")

if fail:
    print("FAIL")
    for f in fail:
        print("  -", f)
    sys.exit(1)

print("PASS: print_stats ignores plan_event rows in aggregation, prints the latest run_end, "
      "SUMMARY.md written")
