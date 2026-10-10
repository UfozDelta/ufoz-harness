# Plan: tidy-runner
## Goal
Behavior-preserving cleanup of the runner after the flag prune: one PLANS_ROOT constant, `args.warm` -> `not args.fresh`, split `cli._run`.

## Decisions
- `plan.PLANS_ROOT = ".harness/plans"` (relative: lock keys are cwd-relative). Replace the literal in cli.py, check.py, planner.py, watch.py. Leave worktree.py, pending.py, land.py (git pathspecs, no plan import).
- Drop `args.warm`; readers use `not args.fresh` (scheduler.py x2, task_runner.py, report.py). Tests that set `warm` switch to `fresh` (inverted).
- `cli.main()` returns an int exit code; `sys.exit` only in `run_plan.py` (`sys.exit(main())`). `_run` and its helpers return ints (None -> 0). The run-lock `finally` stays in `main`.
- `_run` splits into: `_info(ap, args)` (stats, pending, land, relock-only, status, plan: returns code or None), `_enter_worktree(args)`, `_execute(plan, args, metrics)`, `_review(...)`. Same order and messages as today.
- NOT done (verified unsafe or not worth it): run-lock context manager (worktree lock precedes Plan), `get(model=None)` (overrides claude's default sonnet), relock_only chdir (fine).
- `opts = {"model": ...} if args.executor_model` stays; only fix the misplaced comments above the skills code.

Unverified: report.py:106 reads args.warm for a label only; no dedicated test (test_task_runner covers the call path).

## T1 PLANS_ROOT
FILES: .harness/runner/plan.py, .harness/runner/cli.py, .harness/runner/check.py, .harness/runner/planner.py, .harness/runner/watch.py
MUST:
- plan.py: module constant `PLANS_ROOT = ".harness/plans"`; `Plan.__init__` default uses it.
- cli/check/planner/watch: import it (`from .plan import PLANS_ROOT`; watch.py imports lazily inside `watch_dir`, since the file also runs as a bare script) and replace every `".harness/plans"` literal.
TEST: acceptance command in tasks.json.

## T2 drop args.warm
FILES: .harness/runner/cli.py, .harness/runner/scheduler.py, .harness/runner/task_runner.py, .harness/runner/report.py, tests/test_task_runner.py
MUST:
- Delete `args.warm = not args.fresh` in cli.main; readers use `not args.fresh`.
- tests/test_task_runner.py: `warm=False` -> `fresh=True`, `args.warm = True` -> `args.fresh = False`.
TEST: acceptance command in tasks.json.

## T3 split _run
FILES: .harness/runner/cli.py, .harness/run_plan.py, tests/test_log_fixes.py
MUST:
- Split `_run` per Decisions; every branch returns an int; `main()` returns it (None -> 0) after the `finally`.
- run_plan.py: `sys.exit(main())`.
- Move the misplaced skills/model comments next to the code they describe.
- tests/test_log_fixes.py ~L74: `main([...])` now returns 0 instead of raising SystemExit.
TEST: acceptance command in tasks.json.

## T4 write summary
FILES: .harness/plans/tidy-runner/SUMMARY.md
MUST: <= 600 chars: what, which files, how wired. Add line `BUILD: pass` or `BUILD: fail <first error line>`; never fails the task.
