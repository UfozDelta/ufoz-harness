"""Acceptance: report.build_report renders a combo table and totals, and tolerates no rows."""
import sys

sys.path.insert(0, "bench/verify")
import report  # noqa: E402

base = {c: "" for c in report.COLUMNS}
rows = [dict(base, ts="t", orchestrator="pi", planner="pi", executor="pi", rep="1",
             status="pass", rules_ok="true", plan_ok="true", wall_s="1",
             tasks_passed="2", tasks_total="2", plan_cost="0", exec_cost="0",
             harness_sha="x", model="m", seed="0")]
md = report.build_report(rows)
assert "pi" in md and "pass" in md.lower(), md
assert report.build_report([])
print("REPORT OK")
