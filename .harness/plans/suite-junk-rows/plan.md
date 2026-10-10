# suite-junk-rows
Decisions: rate-limit give-up and 0-token instant fails must not count as model failures. report.py already drops `infra_error` from pass-rate math. Env `HARNESS_QUOTA_MAX_WAIT` (seconds) caps Executor.wait_for_quota; default stays 6h so normal runs are unchanged. Suite sets it to 180 for its cells. No backfill of old rows.

Interfaces:
- `Executor.wait_for_quota(log, max_wait=None) -> bool`: True once probe ok, False on give-up. max_wait None = env var, else 6*3600.
- `cells._junk_status(row)`: if status is timeout, or fail with wall_s < 20, and input+output tokens are 0/blank, set status `infra_error`.

## T1
FILES: .harness/runner/executors/base.py, .harness/runner/task_runner.py
MUST: wait_for_quota per interface (return bool). task_runner.py _attempt (~line 124): when it returns False, add usage and break out of the loop instead of rerunning (task then fails on the rate-limit code). No other change.
TEST: grep HARNESS_QUOTA_MAX_WAIT base.py; pytest tests/test_task_runner.py.

## T2
FILES: bench/suite/cells.py
MUST: `os.environ.setdefault("HARNESS_QUOTA_MAX_WAIT", "180")` near the top. Add `_junk_status(row)` per interface and call it just before each return of a row in _run_single (~718), _run_project (~846) and per row in _run_multi (~770; before the `row["status"] != "pass"` preserve check). No other change.
TEST: smoke below; `_junk_status(row)` appears exactly 4 times in cells.py (def + 3 calls).

## T3
FILES: .harness/plans/suite-junk-rows/SUMMARY.md
MUST: SUMMARY.md <= 600 chars: what, which files, how wired.
MUST also: write ONLY SUMMARY.md; touch no other file (a prior run wrongly edited cells.py and dropped a _junk_status call).
TEST: size check + pytest tests/test_task_runner.py tests/test_harness_suite.py.
