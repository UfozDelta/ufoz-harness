# Benchmark arm D — run_plan.py drives opencode on a slim plan (plan.md sections, no checks)

A frozen plan is already at `.harness/plans/bench-plan/` in a layout `run_plan.py`
expects (plan.md, tasks.json). Run, in the foreground so you can
report its output: `python .harness/run_plan.py bench-plan`. Do not implement any task
yourself. Do not use the Agent tool. Report the runner's summary and the contents of any
failed task's report.
