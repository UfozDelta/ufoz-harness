"""Acceptance check for plan-log T1. Hash-locked: the executor cannot edit this.

Cheap smoke, no nested executor call: unit-tests record_plan_event() directly, and
grep-checks cli.py/planner.py for the three call sites this task must wire up.
"""
import json
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, ".harness")

fail = []

# 1. record_plan_event() itself, in-process, no subprocess.
try:
    from runner.report import record_plan_event
except ImportError as e:
    print(f"FAIL: cannot import record_plan_event from runner.report: {e}")
    sys.exit(1)

with tempfile.TemporaryDirectory() as td:
    metrics = Path(td) / "metrics.jsonl"
    record_plan_event(metrics, "checktmp", "run_end", executor="pi", result="pass",
                       duration_s=1.2, tasks_done=1)
    lines = metrics.read_text(encoding="utf-8").strip().splitlines()
    if len(lines) != 1:
        fail.append(f"expected 1 line in metrics file, got {len(lines)}")
    else:
        row = json.loads(lines[0])
        if row.get("kind") != "plan_event":
            fail.append(f"kind: expected 'plan_event', got {row.get('kind')!r}")
        if row.get("event") != "run_end":
            fail.append(f"event: expected 'run_end', got {row.get('event')!r}")
        if row.get("slug") != "checktmp":
            fail.append(f"slug: expected 'checktmp', got {row.get('slug')!r}")
        if row.get("result") != "pass":
            fail.append(f"result: expected 'pass', got {row.get('result')!r}")
        if row.get("duration_s") != 1.2:
            fail.append(f"duration_s: expected 1.2, got {row.get('duration_s')!r}")
        if row.get("tasks_done") != 1:
            fail.append(f"tasks_done: expected 1, got {row.get('tasks_done')!r}")
        if not re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$", row.get("ts", "")):
            fail.append(f"ts: not an ISO timestamp: {row.get('ts')!r}")

# 2. cli.py wiring: all three events, and the `time` import record_plan_event's caller needs.
cli_src = Path(".harness/runner/cli.py").read_text(encoding="utf-8")
if "record_plan_event" not in cli_src:
    fail.append("cli.py never calls record_plan_event")
for event in ('"created"', '"run_start"', '"run_end"'):
    if event not in cli_src:
        fail.append(f"cli.py: no call site for {event}")
if not re.search(r"^import time$", cli_src, re.MULTILINE):
    fail.append("cli.py: missing 'import time'")

# 3. planner.py: created_at field on the planner.json record.
planner_src = Path(".harness/runner/planner.py").read_text(encoding="utf-8")
if "created_at" not in planner_src:
    fail.append("planner.py: planner.json record has no 'created_at' field")

if fail:
    print("FAIL")
    for f in fail:
        print("  -", f)
    sys.exit(1)

print("PASS: record_plan_event() writes a correct row; cli.py wires created/run_start/run_end; "
      "planner.json gets created_at")
