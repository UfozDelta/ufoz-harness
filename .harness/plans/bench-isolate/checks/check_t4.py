import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, ".harness/plans/bench-isolate/checks")
from _common import cells, cell, fake_kit, subjects  # noqa: E402

cells.PLAN_CACHE = Path(tempfile.mkdtemp(prefix="plancache"))
calls = []


def runner(cmd, cwd=None, **kw):
    calls.append(cmd)
    slug = cmd[2]
    d = Path(cwd) / ".harness" / "plans" / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / "plan.md").write_text("# Plan: " + slug, encoding="utf-8")
    (d / "tasks.json").write_text(json.dumps({"slug": slug, "tasks": []}), encoding="utf-8")
    (d / "planner.json").write_text(json.dumps({"cost": 0.7}), encoding="utf-8")
    return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()


made = []
try:
    c0 = cell(97)  # fixture mode
    p0 = cells.make_project(c0, kit=fake_kit())
    made.append(c0)
    assert cells.plan_for_project(c0, p0, kit_hash="fake1234") == 0.0
    assert (p0 / ".harness/plans" / c0["slug"] / "tasks.json").is_file()
    assert subjects(p0)[0] == "plan" and c0["base_commit"]
    extra = dict(plan_source="planner", planner="claude", planner_model="sonnet")
    costs = []
    for rep in (95, 96):
        c = cell(rep, **extra)
        p = cells.make_project(c, kit=fake_kit())
        made.append(c)
        costs.append(cells.plan_for_project(c, p, kit_hash="fake1234", runner=runner))
        t = json.loads((p / ".harness/plans" / c["slug"] / "tasks.json").read_text(encoding="utf-8"))
        assert t["slug"] == c["slug"], t
    assert costs == [0.7, 0.0], costs
    assert len(calls) == 1, calls
finally:
    for c in made:
        cells.cleanup_project(c)
print("T4 OK")
