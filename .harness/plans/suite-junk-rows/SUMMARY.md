Quota give-up and infra error tracking.

**T1** (base.py, task_runner.py): `wait_for_quota()` returns bool. Checks HARNESS_QUOTA_MAX_WAIT env var (default 6h). In task_runner's retry loop, on False adds usage and breaks, failing the task.

**T2** (cells.py): Sets HARNESS_QUOTA_MAX_WAIT=180s. Implements `_junk_status(row)` to reclassify timeout or fail (wall_s<20) with 0/blank tokens as infra_error. Called in _run_single, _run_multi, _run_project before returning rows.
