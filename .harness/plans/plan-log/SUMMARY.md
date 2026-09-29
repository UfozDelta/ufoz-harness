# plan-log

Plan lifecycle is now answerable from data, not mtimes or report scanning.

- `report.py`: `record_plan_event()` appends `{"ts","slug","kind":"plan_event","event",...}`
  rows to `.harness/metrics.jsonl`.
- `cli.py`: logs `created` after a headless `--plan` lints OK, `run_start` before the executor
  loop, `run_end` (result, duration_s, tasks_done) after a run that actually ran tasks.
- `planner.py`: `planner.json` gains `created_at`.
- `stats.py`: `--stats` skips `plan_event` rows in the totals and prints
  `<slug>: last run <ts> -> pass/fail` (latest `run_end`, sorted).
