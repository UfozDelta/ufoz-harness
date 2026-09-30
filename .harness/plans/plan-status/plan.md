# plan-status
Decisions:
- New read-only flag `run_plan.py <slug> --status`: one screen answering "where is this plan and what do I run next". Runs nothing, stdlib only.
- Plan dir = `cli.watch_dir(slug)` (worktree copy when it exists, else `.harness/plans/<slug>`).
- Task state from files only: `items/T<n>.report.md` containing `RESULT: pass` = pass; report exists without it = fail; no report = pending. Attempts from `items/T<n>.metrics.json` key `attempts` when present.
- Interface: `status.render(slug: str, plan_dir: Path) -> str`.
- Output: one line per task in tasks.json order: `T1 pass (1 attempt)` / `T2 FAIL (2 attempts)` / `T3 pending`. Then, for the FIRST failed task only, its report's last 15 lines, indented. Last line starts with `next: `:
  - a failed report containing `LOCK-MISMATCH` -> `next: python .harness/run_plan.py <slug> --relock-only`
  - any other fail or any pending -> `next: python .harness/run_plan.py <slug>`
  - all pass -> `next: python .harness/run_plan.py <slug> --land`

## T1
FILES: .harness/runner/status.py, .harness/runner/cli.py
MUST: status.py implements render per Decisions. cli.py: add `--status` (store_true, help "Show task states, the first failure's tail and the next command; runs nothing.") and in `_run`, right after the `args.watch` branch: `if args.status: print(status.render(args.slug, watch_dir(args.slug))); return`. Import like the other runner modules. No other cli change.
TEST: `--status` on suite-robust lists T1 and a `next:` line.

## T2
FILES: tests/test_status.py
MUST: unittest/pytest with tmp_path: tasks.json with T1,T2,T3; T1 report has `RESULT: pass`, T2 report has `RESULT: fail` + 20 lines, T3 no report. Assert: `T1 pass`, `T2 FAIL`, `T3 pending`, T2's last line present and its first line absent (tail 15), last line `next: python .harness/run_plan.py <slug>`. Second case: all pass -> ends with `--land`. Third: T2 report contains LOCK-MISMATCH -> `--relock-only`.

## T3
FILES: .harness/plans/plan-status/SUMMARY.md
MUST: SUMMARY.md <= 600 chars: what, which files, how wired.

## T4
FILES: .harness/selftest.py, .harness/runner/cli.py, .harness/plans/plan-status/SUMMARY.md
MUST: Root cause of the selftest failure: `selftest.py` COPY hardcodes each `.harness/runner/*.py`, so any new runner module (pending.py, status.py) is missing from the scratch copy. Fix: build the runner part of COPY with a glob over `.harness/runner/**/*.py` (sorted, posix paths, skip `__pycache__`); keep the non-runner entries literal. Then undo the lazy-import workaround in cli.py: top-level `from . import land, pending, planner, scheduler, status, watch, worktree`, and drop the two function-local imports and their comments. Add one line to SUMMARY.md about the selftest glob (stay <= 600 chars).
TEST: selftest passes with top-level imports.
