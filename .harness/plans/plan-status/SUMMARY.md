# plan-status

Read-only `--status` flag: where the plan is and what to run next.

- `runner/status.py`: `render(slug, plan_dir)` reads tasks.json, each report
  (pass/fail/none = pending) and metrics.json (attempts). One line per task, the
  first failed report's tail, then `next:`: `--relock-only` on LOCK-MISMATCH,
  `--land` when all pass, else a run.
- `runner/cli.py`: `--status` prints `watch_dir(slug)`.
- `tests/test_status.py`: states/tail/next, all-pass, LOCK-MISMATCH.
- `selftest.py`: the runner is copied by a `.harness/runner/**/*.py` glob, so
  new modules are never missed.

