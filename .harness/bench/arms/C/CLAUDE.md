# Benchmark arm C — run_plan.py drives opencode directly

A frozen plan is already at `.harness/plans/bench-plan/` in the exact layout `run_plan.py`
expects (plan.md, tasks.json, items/T<n>.md, checks/). Run, in the foreground so you can
report its output: `python .harness/run_plan.py bench-plan`. Do not implement any task
yourself. Do not use the Agent tool. Report the runner's summary and the contents of any
failed task's report.
