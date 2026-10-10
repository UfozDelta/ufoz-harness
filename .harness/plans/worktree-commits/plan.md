# Plan: worktree-commits

## Goal
Give every plan's worktree a real branch with real commits, so landing is an ordinary `git merge`
instead of a synthesized patch, and reviewing as you go is `git log`/`git diff`. `--land` stays, but
becomes a thin `--ff-only` merge.

Today `worktree.ensure()` bases the branch on a synthetic snapshot commit that contains the user's
uncommitted edits and untracked files (worktree.py `_snapshot`). Because that base is not
representable in normal history, nothing can be merged and `land.land()` builds a patch instead.
Require a clean tree instead: the branch then starts at real HEAD and everything downstream is
ordinary git.

## Decisions
1. **Clean-tree gate, hard refuse.** In `worktree.ensure()`, when neither `exclude` nor `orphan` is
   given: if `git status --porcelain` is non-empty, `sys.exit` with a message naming the dirty paths
   and telling the user to commit or stash, then rerun. No autostash, no `--force`. The gate runs
   before `git worktree add`.
2. **Base = HEAD.** With a clean tree the snapshot commit is redundant, so the default path is
   `git worktree add -b harness/<slug> <path> HEAD`. Callers that pass `exclude` or `orphan` keep the
   old `_snapshot()` path unchanged — `bench/suite/cells.py:238` does exactly this and must keep
   working. `_snapshot()` and its temp-index dance stay in the module for those callers.
3. **Prune stale worktree dirs.** `ensure()` currently `sys.exit`s (worktree.py:155) when
   `.worktrees/<slug>` exists but git does not know it. Instead: `git worktree prune`, and if the
   directory still exists afterwards, remove it with `shutil.rmtree` when it holds no `.git` file,
   else `sys.exit` with the same message as today. Never touch a directory git knows.
4. **Runner commits each passing task.** New module-level function in `task_runner.py`:
   `commit_task(slug, tid, title, files) -> str | None`. It runs `git add -A -- <files>` then
   `git commit -m <message>` in the current directory (the runner chdirs into the worktree at
   cli.py:239), with `worktree.IDENTITY` in the env. Returns the new sha, or `None` when there was
   nothing to commit. `files` is `t.norm_files` only — never `.harness/plans/`, which
   `guards.runner_owned` treats as runner-owned.
4b. **`HARNESS_COMMIT_STYLE` picks the message.** Read from the environment inside `commit_task`, no
   CLI flag. `full` (default, and the only fallback for an unrecognized value):
   `harness(<slug>): <tid> <title>`. `short`: `<tid>: <title>` — the branch already names the slug.
   Document the var in `.harness/.env.example` as part of T5.
5. **Commit only on pass.** `TaskRunner.run()` calls `commit_task` after `result = "pass"`, and never
   on fail, so a failed task stays uncommitted and repair/retry keep working against a dirty tree.
   The sha is appended to the summary line from `report.summary_lines`.
6. **The scope guard survives on its own.** `task_runner.run()` already re-takes `before = snapshot()`
   and `st.git0 = git_state()` per task (task_runner.py:200-201), so a commit landing between tasks is
   absorbed into the next task's baseline. T3 exists to *prove* that rather than to change it: the
   executor must still be unable to commit, and an out-of-scope edit plus a `GIT_MOVED` must still be
   caught when HEAD moved before the task started. If T3 finds a real gap, fix it inside
   `task_runner.py`/`guards.py` and add those files to T3's FILES.
7. **`--land` becomes `--ff-only`.** `land.land()`: refuse as today when the worktree is unknown or
   `run.lock` exists; copy the worktree's plan records into `.harness/plans/<slug>/` first (they are
   gitignored-ish records, not code); then `git merge --ff-only harness/<slug>` in the main tree. On
   success unlink the `SHARED_DIRS` junctions, `git worktree remove --force`, `git branch -d`, print
   `landed <slug>`. On `merge --ff-only` failure (main moved) print git's message, leave the worktree
   and the branch in place, return 1. `land.patch` is no longer written.
8. **`land_from` is unchanged** — it lands a worktree the runner never made commits in, so it must
   stay patch-based. Update the `--land` help text in `cli.py` to describe a merge, and drop the now
   unused `--yes` note only if nothing else references it; `--yes` itself stays (claude mode and
   `land_from` still need the terminal guard).
9. **Known consequence.** `.harness/plans/land/checks/check_t1.py` asserts the old patch behavior
   (`land.patch` exists, conflict keeps a patch) and will fail after T4. T4 rewrites it for merge
   semantics, which invalidates the `land` plan's lock: the user runs
   `python .harness/run_plan.py land --relock-only` after landing this plan. That is a user command,
   not the executor's.

## T1 clean-tree gate, HEAD base, prune
FILES: .harness/runner/worktree.py
MUST: Decisions 1-3. The `exclude`/`orphan` path (bench) must be byte-for-byte unchanged in behavior.
TEST: python .harness/plans/worktree-commits/checks/check_t1.py

## T2 runner commits each passing task
FILES: .harness/runner/task_runner.py
MUST: Decisions 4-4b-5. `commit_task` is module-level and importable; called once per passing task,
after the final report is written. Never on fail. `HARNESS_COMMIT_STYLE` is read from the
environment only; no new CLI flag.
TEST: python .harness/plans/worktree-commits/checks/check_t2.py

## T3 guard regression under a moving HEAD
FILES: tests/test_worktree_commits.py
MUST: Decision 6. Cover: an executor-side commit is still GIT_MOVED; an out-of-scope edit is still a
stray when a prior task's commit moved HEAD; a task touching only its listed files after a commit is
clean. Match the existing style in `tests/test_git_guard.py`.
TEST: python .harness/plans/worktree-commits/checks/check_t3.py

## T4 --land as --ff-only merge
FILES: .harness/runner/land.py, .harness/runner/cli.py, .harness/plans/land/checks/check_t1.py
MUST: Decisions 7-9. `land_from` unchanged.
TEST: python .harness/plans/worktree-commits/checks/check_t4.py

## T5 docs + summary
FILES: README.md, CLAUDE.md, .harness/MAIN.md, docs/FLOWS.md, docs/ARCHITECTURE.md,
.harness/.env.example, packages/ufoz-harness/README.md, packages/ufoz-harness/kit_readme.md,
.harness/plans/worktree-commits/SUMMARY.md
MUST: every doc that describes the worktree base now says the tree must be clean and the branch
starts at HEAD; `--land` is documented as a `--ff-only` merge and no longer writes `land.patch`.
CLAUDE.md and MAIN.md state that a run needs a clean tree. `.env.example` documents
`HARNESS_COMMIT_STYLE` (`full` | `short`) alongside the other vars. SUMMARY.md <= 600 chars.
TEST: python .harness/plans/worktree-commits/checks/check_t5.py