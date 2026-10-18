"""Acceptance T4: report shows cache hit, cost per pass, provisional marks, null handling."""
import sys

sys.path.insert(0, "bench/verify")
import report  # noqa: E402

base = {c: "" for c in report.COLUMNS}


def row(slug, o, p, e, status, **kw):
    fields = dict(base, slug=slug, orchestrator=o, planner=p, executor=e, status=status, rep="1",
                  rules_ok="true", plan_ok="true", wall_s="100", tasks_passed="3", tasks_total="3")
    fields.update(kw)
    return fields


rows = [
    row("s1", "claude", "pi", "pi", "pass", orch_cost="0.30", exec_cost="0.01",
        orch_in="10", orch_cache_read="90", exec_in="20", exec_cache_read="80", exec_cache_write="0"),
    row("s2", "claude", "pi", "pi", "fail", orch_cost="0.10", exec_cost="0.01", wall_s="200"),
    row("s3", "pi", "pi", "opencode", "pass"),  # no usage at all: must render with '-'
]
md = report.build_report(rows)
assert "cache hit" in md.lower() and "cost per pass" in md.lower(), md
assert "†" in md and "provisional" in md.lower(), md
assert "By axis" in md and "orchestrator" in md and "executor" in md
assert "| - |" in md or "| - " in md, "blank usage should show '-'"
assert "85" in md, md  # pooled cache hit (90+80)/(10+90+20+80)
assert "## Totals" in md

legacy = [dict(base, slug="x", orchestrator="pi", planner="pi", executor="pi", status="pass")]
assert report.build_report(legacy)
assert report.build_report([])
print("T4 OK")
