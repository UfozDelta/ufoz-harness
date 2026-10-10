# worktree-commits: Real branches, real commits

Worktrees start at clean HEAD with real commits; `--land` uses `git merge --ff-only`.

**T1:** Clean-tree gate + HEAD base (`worktree.py`).
**T2:** Per-task commits in `task_runner.py`. `HARNESS_COMMIT_STYLE` env var.
**T3:** Guard regression tests (`test_worktree_commits.py`).
**T4:** Merge landing (`land.py`). `--land` runs `git merge --ff-only harness/<slug>`.
**T5:** Docs updated: clean-tree, merge behavior, `HARNESS_COMMIT_STYLE`.

Landing is now ordinary `git merge --ff-only` instead of synthesized patch.
