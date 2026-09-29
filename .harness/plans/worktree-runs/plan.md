# Plan: worktree-runs

## Goal
`run_plan.py <slug> --worktree` runs a plan in its own git worktree `.worktrees/<slug>` so several plans
can run at once. The runner only creates the worktree and runs there; the user reviews and merges by hand.

## Decisions
1. Location `.worktrees/<slug>`, branch `harness/<slug>`. `.worktrees/` is added to `.git/info/exclude`
   (local, no tracked-file edit), so the main tree's guard snapshot and git status never see it.
2. Base = snapshot of the current tree incl. uncommitted + untracked non-ignored files, built with a
   TEMP index so the user's index, HEAD and branches are untouched:
   `GIT_INDEX_FILE=<tmp> git read-tree HEAD`, `git add -A`, `git write-tree`, then
   `git commit-tree <tree> -p HEAD -m "harness snapshot for <slug>"` (env sets GIT_AUTHOR_NAME/EMAIL and
   GIT_COMMITTER_NAME/EMAIL = `harness` / `harness@localhost`), then
   `git worktree add -b harness/<slug> .worktrees/<slug> <sha>`.
3. Existing `.worktrees/<slug>` that `git worktree list --porcelain` knows -> reuse, no new snapshot.
   Dir exists but not a worktree, or branch `harness/<slug>` exists without the dir -> print why and exit 1.
4. Shared, gitignored dirs are linked, not copied: for `node_modules`, `.venv`, `.opencode/node_modules`,
   if the main dir exists AND `git check-ignore -q <name>` succeeds, create a junction
   `cmd /c mklink /J <wt>\<name> <main>\<name>`. Copy `.harness/.env` if it exists. Windows only.
5. Runner behavior inside is unchanged: cli does `os.chdir(worktree)` before loading the plan.
6. Guard fix: files under another plan's dir (`<plans_root>/<other>/...`) count as runner-owned, so a
   concurrent plan's files never fail a task.
7. Nobody commits. All git calls live in worktree.py and run via `subprocess.run(..., check=False)`.
Verified: cli.py builds all paths relative to cwd; guards.snapshot uses `git ls-files -co --exclude-standard`
(honors info/exclude). git 2.54.
Unverified: none.

## interfaces
- guards.py `runner_owned(f, run_lock, plan, metrics)`: unchanged signature; add the Decision 6 rule.
- new `.harness/runner/worktree.py`:
  - `path_for(slug: str) -> Path` = `Path(".worktrees") / slug`
  - `ensure(slug: str) -> Path`: Decisions 1-4, returns absolute worktree path; errors -> `sys.exit(msg)`.
- cli.py: `--worktree` (store_true). `watch_dir(slug) -> Path`: `.worktrees/<slug>/.harness/plans/<slug>` if
  it exists, else `.harness/plans/<slug>`; `--watch` uses it.

## T1 guard other plans
FILES: .harness/runner/guards.py
MUST: Decision 6 only; own plan dir rules unchanged (own plan.md/tasks.json still NOT owned).
TEST: python .harness/plans/worktree-runs/checks/check_t1.py

## T2 worktree module
FILES: .harness/runner/worktree.py
MUST: interfaces + Decisions 1-4, 7. Stdlib only. Never touch the user's index/HEAD/refs besides creating
`harness/<slug>`.
TEST: python .harness/plans/worktree-runs/checks/check_t2.py

## T3 cli wiring
FILES: .harness/runner/cli.py
MUST:
- `--worktree`: in a real run or `--lint`, before `Plan(...)`: `os.chdir(worktree.ensure(args.slug))`.
  Not with --stats/--plan/--watch.
- `--watch` reads `watch_dir(args.slug)`. Keep every existing flag working.
TEST: python .harness/plans/worktree-runs/checks/check_t3.py

## T4 docs + summary
FILES: README.md, CLAUDE.md, .harness/MAIN.md, .harness/plans/worktree-runs/SUMMARY.md
MUST: README documents `--worktree` (location, branch, snapshot base, user merges/removes by hand:
`git worktree remove .worktrees/<slug>`). CLAUDE.md + MAIN.md step 4: one sentence: use `--worktree` to run
plans in parallel. SUMMARY.md <= 600 chars.
TEST: python .harness/plans/worktree-runs/checks/check_t4.py
