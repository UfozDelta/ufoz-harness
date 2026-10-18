"""Acceptance T3: exec usage reader, CSV migration, and the headless default planner list."""
import csv
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, "bench/verify")
import backends  # noqa: E402
import verify  # noqa: E402

tmp = Path(tempfile.mkdtemp())

# _exec_usage reads metrics.jsonl + counts toolCall lines in T*.pi.log
wt = tmp / "wt"
(wt / ".harness" / "plans" / "s" / "logs").mkdir(parents=True)
row = {"slug": "s", "task": "T1", "result": "pass", "attempts": 1, "seconds": 2,
       "tokens": {"input": 1, "output": 2, "reasoning": 3, "cache_read": 4, "cache_write": 5, "cost": 0.5}}
(wt / ".harness" / "metrics.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
(wt / ".harness" / "plans" / "s" / "logs" / "T1.pi.log").write_text(
    "[toolCall Read] a\ntext\n[toolCall Edit] b\n", encoding="utf-8")
u = verify._exec_usage("s", wt)
assert (u["in"], u["out"], u["reason"], u["cache_read"], u["cache_write"]) == (1, 2, 3, 4, 5), u
assert u["tool_calls"] == 2 and u["attempts"] == 1, u

# migrate_csv keeps old values and adopts the new header; _append_row migrates first
old = tmp / "old.csv"
with open(old, "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(["slug", "ts", "status", "wall_s", "exec_cost"])
    w.writerow(["a", "t1", "pass", "1.5", "0.01"])
verify.migrate_csv(old)
rows = list(csv.DictReader(open(old, newline="", encoding="utf-8")))
assert list(rows[0].keys()) == backends.CSV_FIELDS, list(rows[0].keys())
assert rows[0]["slug"] == "a" and rows[0]["exec_cost"] == "0.01" and rows[0]["orch_cost"] == ""
verify._append_row(old, {"slug": "b", "status": "pass", "orch_cost": "0.2"})
rows = list(csv.DictReader(open(old, newline="", encoding="utf-8")))
assert [r["slug"] for r in rows] == ["a", "b"] and rows[1]["orch_cost"] == "0.2"

# headless default drops the dead planner axis; runner mode keeps all three
cells = verify._matrix(verify.parse_args(["--dry"]))
assert len(cells) == 9 and {c["planner"] for c in cells} == {"pi"}, len(cells)
cells = verify._matrix(verify.parse_args(["--dry", "--plan-via", "runner"]))
assert len(cells) == 27
cells = verify._matrix(verify.parse_args(["--dry", "--planners", "claude,pi,opencode"]))
assert len(cells) == 27
print("T3 OK")
