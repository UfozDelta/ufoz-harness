# Plan: verify-failreason
## Goal
Every verify-bench cell records why it did not pass and keeps all its logs.

## Decisions
- New trailing columns in `backends.COLUMNS`: `fail_reason`, `tests_passed`, `tests_total`, `regression_passed`, `regression_total`, `logs_dir`. Blank on pass for `fail_reason`.
- `fail_reason` is a short code: `skipped_preflight`, `plan_error`, `timeout_<phase>` (phase = orch|lint|exec|land), `no_plan_files`, `lint_failed`, `land_failed`, `no_reports`, `tests_failed`, `regression_failed`, `tasks_failed`, `cell_exception`. Set at the same sites that call `finish(status)`; a non-pass status from `score_project` is classified by `_score_reason(scored)`.
- Logs: every cell (pass or fail) copies its plan dir into `bench/verify/logs/<slug>__<stamp>/`. Worktree logs vanish at `--land`, so copy `<wt>/.harness/plans/<slug>` BEFORE land into `.../wt/`; copy `<project>/.harness/plans/<slug>` (plan.md, tasks.json, logs, items) in `finally` before cleanup into `.../project/`. `logs_dir` = repo-relative posix path. `bench/verify/logs/` is gitignored already.
- Copy failures never fail a cell.

## interfaces
- `verify._score_reason(scored) -> str` ("" when status pass).
- `verify._save_logs(repo_root, slug, src, sub, stamp) -> None`.

## T1 columns
FILES: bench/verify/backends.py
MUST:
- Append the six names from Decisions to `COLUMNS` after `usage_json`.
TEST: python .harness/plans/verify-failreason/checks/check_t1.py

## T2 reasons and logs
FILES: bench/verify/verify.py
MUST:
- Implement `_score_reason`, `_save_logs`; set `row["fail_reason"]` at every non-pass return in `run_cell`; copy `tests_*`/`regression_*` from `scored` (already in the key loop); save logs per Decisions and set `logs_dir`.
- `migrate_csv` already handles the wider header; do not change it.
TEST: python .harness/plans/verify-failreason/checks/check_t2.py

## T3 summary
FILES: .harness/plans/verify-failreason/SUMMARY.md
MUST:
- Write SUMMARY.md (<= 600 chars: what, files, how wired) ending with `BUILD: pass` after running `python bench/verify/verify.py --dry` (exit 0).
TEST: python .harness/plans/verify-failreason/checks/check_t3.py
