# worktree-runs

`run_plan.py <slug> --worktree` runs a plan in its own git worktree `.worktrees/<slug>` on branch
`harness/<slug>`, base a snapshot of the current tree (uncommitted + untracked, non-ignored) built
with a temp index. `.worktrees/` in `.git/info/exclude`; `node_modules`/`.venv` junctioned;
`.harness/.env` copied. Nobody commits; the user merges or `git worktree remove`s by hand.

Files: `.harness/runner/worktree.py` (new), `cli.py` (`--worktree`, `watch_dir`), `guards.py`
(other plans' files are runner-owned), README/CLAUDE/MAIN.
