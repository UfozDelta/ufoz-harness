# verify-failreason

What: every verify-bench cell now records a short `fail_reason` (blank on pass) and keeps all its logs.

Files:
- bench/verify/backends.py: COLUMNS gains fail_reason, tests_passed, tests_total, regression_passed, regression_total, logs_dir.
- bench/verify/verify.py: _score_reason(scored), _save_logs(repo_root, slug, src, sub, stamp); finish(status, reason) at every non-pass return.

How wired: run_cell copies the worktree plan dir before --land (or in finally if the cell stopped earlier) to bench/verify/logs/<slug>__<stamp>/wt, and the project plan dir to .../project in finally. logs_dir holds that repo-relative path. Copy errors are skipped.

BUILD: pass
