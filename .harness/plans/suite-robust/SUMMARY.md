suite-robust: failed cells keep logs (`cells._preserve_failed` copies items/logs to
`harness-suite/failed/<slug>/` before cleanup, wired into `run_cell`/`_run_multi`);
`cleanup_cell` retries `worktree remove --force` and warns on a surviving branch,
`prepare_cell` drops a stale unused one; acceptance timeouts kill the process tree instead
of blocking on a grandchild-held pipe; `_poll_until` gives cells a wall-clock timeout;
opencode got a `HARNESS_OPENCODE_IDLE_S` watchdog.
Files: cells.py, .gitignore, runner/acceptance.py, executors/opencode.py, tests/*.
BUILD: pass