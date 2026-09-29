import sys
from pathlib import Path

sys.path.insert(0, ".harness")
from runner import guards  # noqa: E402

plan = Path("plans/slug")
lock = plan / "run.lock"
metrics = Path("metrics.jsonl")
own = guards.runner_owned
assert own("plans/other/tasks.json", lock, plan, metrics)
assert own("plans/other/checks/check_t1.py", lock, plan, metrics)
assert not own("plans/slug/tasks.json", lock, plan, metrics)
assert not own("plans/slug/plan.md", lock, plan, metrics)
assert own("plans/slug/items/T1.report.md", lock, plan, metrics)
assert not own("plansx/a.py", lock, plan, metrics)
assert not own("src/app.py", lock, plan, metrics)
print("OK")
