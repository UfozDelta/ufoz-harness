# Plan: claude-homog

Goal: Claude mode and runner mode share ONE worktree (`.worktrees/<slug>`), one check, one land.

## Decisions
- New flag `--prepare` on run_plan.py: `cli.prepare(slug) -> int`: if not `worktree.in_git_repo()` print `not a git repo` and return 1; else `main = Path.cwd(); target = worktree.ensure(slug); worktree.sync_plan(slug, target, main); print(f"worktree: {target}"); return 0`. Runs nothing else, takes no run.lock. Dispatched in `_run` right after the `--relock-only` branch: `if args.prepare: sys.exit(prepare(args.slug))`.
- `--check` takes an OPTIONAL dir: `nargs="?", const=""`; dispatch uses `args.check is not None` and `check.check(args.slug, args.check or str(worktree.path_for(args.slug)))`. So `run_plan.py <slug> --check` grades `.worktrees/<slug>`.
- Do not touch land.py or check.py.

## T1 cli
FILES: .harness/runner/cli.py
MUST: as Decisions. Update the `--check` help text to say DIR defaults to the plan's worktree; add the `--prepare` help ("create the plan's worktree and print its path; run nothing; for executors that edit outside the runner").
TEST: smoke in tasks.json.

## T2 test
FILES: tests/test_prepare.py
MUST: pytest that builds a temp git repo (git init, one commit, a `.harness/plans/p/tasks.json` untracked), chdirs into it, imports `runner.cli` from the repo's `.harness`, calls `cli.prepare("p")`, asserts it returns 0, `.worktrees/p/.harness/plans/p/tasks.json` exists, and a second call also returns 0. Restore cwd in a finally. Also assert `build_parser().parse_args(["p","--check"]).check == ""` and `["p","--check","d"]` gives `"d"`.
TEST: smoke in tasks.json.

## T3 summary
FILES: .harness/plans/claude-homog/SUMMARY.md
MUST: <=600 chars: what, files, wiring. Then BUILD line from `python -m pytest -q tests/test_prepare.py tests/test_git_guard.py`.
Unverified: worktree.ensure inside a throwaway temp repo works with SHARED_DIRS links when node_modules is absent.
