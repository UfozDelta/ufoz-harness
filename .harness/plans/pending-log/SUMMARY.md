# pending-log

`run_plan.py --pending` lists unlanded plan worktrees: new `.harness/runner/pending.py`
(`pending(root=".worktrees")` prints `<slug>  <passed>/<total> tasks passed  <n> changed files`
+ `  (running)` on `run.lock`; `no unlanded worktrees` when root is missing/empty), wired into
`cli.py` as an early return after `--stats`. Dirs without `.git` are skipped (no git call) and
`land.py` rmdirs an empty leftover after `git worktree remove --force`. Executors report quirks in
`items/T<n>.quirks.md` (runner-owned in `guards.py`); the main session logs its own in `log.md`.

BUILD: pass
