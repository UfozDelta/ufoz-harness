# Plan: default-worktree

## Goal
A real run uses its own worktree and opens the live window by default. Opt out per run with
`--no-worktree` / `--no-window`, or globally with `HARNESS_WORKTREE=0` / `HARNESS_WINDOW=0`.

## Decisions
1. `--worktree` and `--window` become `argparse.BooleanOptionalAction`, default None. Resolved by
   `cli.use_worktree(args)` / `cli.use_window(args)`: explicit flag wins; else env `HARNESS_WORKTREE` /
   `HARNESS_WINDOW` != "0" (unset = on; existing `HARNESS_WINDOW=1` still means on).
2. Worktree only for real runs, never for `--lint`/`--plan`/`--stats`/`--watch`. Not inside a git repo
   (`worktree.in_git_repo()` false) -> print `not a git repo: running in place` and run in place.
3. Window only when `os.name == "nt"`; otherwise silently skipped.
4. Every worktree run calls `worktree.sync_plan(slug, target, source_root)` AFTER it holds the worktree's
   run lock (a second run of the same slug must exit before anything is copied): copies
   `source_root/.harness/plans/<slug>/plan.md`, `tasks.json`, and the whole `checks/` dir (when present)
   into `target/.harness/plans/<slug>/`, overwriting. Never copies items/, logs/, plan.lock.json, SUMMARY.md. A changed
   tasks.json/check then hits the normal lock-mismatch -> `--relock`, as today.
5. selftest.py and bench.py drive `run_plan.py` in scratch dirs: every real-run invocation there adds
   `--no-worktree`, `--no-window` (lint-only calls unchanged).
6. `worktree.ensure`: `git worktree add` is retried up to 3 attempts, 1 s apart, when its stderr contains
   `.lock` (10 plans starting at once contend on git lock files).
7. Window = one shared Windows Terminal window with a tab per plan: `watch.window_command` with wt returns
   `["wt", "-w", "harness", "new-tab", "--title", f"harness {slug}", "-d", os.getcwd(), *tail]`
   (cmd fallback unchanged).
Verified: callers = selftest.py:181, bench.py:266, bench.py:510 (grep). cli.py order: watch/plan exit
before the executor check; worktree chdir sits right before `Plan(...)`.
Later: `--stats` does not see metrics written inside worktrees.

## interfaces
- worktree.py: `in_git_repo() -> bool` (`git rev-parse --is-inside-work-tree` == "true");
  `sync_plan(slug: str, target: Path, source_root: Path) -> None` (Decision 4).
- cli.py: `use_worktree(args) -> bool`, `use_window(args) -> bool` (Decision 1, env read at call time).

## T1 worktree helpers
FILES: .harness/runner/worktree.py
MUST: add the two functions; Decision 6 retry in `ensure`; nothing else in `ensure` changes.
TEST: python .harness/plans/default-worktree/checks/check_t1.py

## T2 cli defaults
FILES: .harness/runner/cli.py, .harness/runner/watch.py
MUST: Decisions 1-4, 7. In a real run, when use_worktree and in_git_repo: `main = Path.cwd()`,
`target = worktree.ensure(slug)`, `os.chdir(target)`, mkdir `.harness/plans/<slug>` (parents ok), take the run
lock on `.harness/plans/<slug>/run.lock` via `_acquire_run_lock` (set `_ACTIVE_RUN_LOCK`), THEN
`worktree.sync_plan(slug, target, main)`, THEN `Plan(...)`; do not take the lock a second time.
Window after the run lock, as today, but via `use_window(args) and os.name == "nt"`. Help texts mention
the env opt-outs.
TEST: python .harness/plans/default-worktree/checks/check_t2.py

## T3 bench/selftest opt-out
FILES: .harness/selftest.py, .harness/bench/bench.py
MUST: Decision 5 only; no other edits.
TEST: python .harness/plans/default-worktree/checks/check_t3.py

## T4 docs + summary
FILES: README.md, CLAUDE.md, .harness/MAIN.md, .harness/.env.example, .harness/plans/default-worktree/SUMMARY.md
MUST: README: worktree + window are default, opt-outs (flags + env), reports/logs live in
`.worktrees/<slug>/.harness/plans/<slug>/`. CLAUDE.md + MAIN.md: step 4 says runs default to a worktree +
window; step 5 (Verify) reads reports/SUMMARY there and reviews with `git -C .worktrees/<slug> diff`.
`.env.example`: commented `# HARNESS_WORKTREE=0` and `# HARNESS_WINDOW=0` lines. SUMMARY.md <= 600 chars.
TEST: python .harness/plans/default-worktree/checks/check_t4.py
