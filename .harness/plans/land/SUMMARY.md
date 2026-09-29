RESULT: pass

`run_plan.py <slug> --land` is the user's one command to land a finished run: `.harness/runner/land.py` builds a binary patch of the worktree's code changes (plan records excluded), always keeps it at `.harness/plans/<slug>/land.patch`, and applies it only when `git apply --check` is clean (on conflict nothing changes, worktree and branch kept). Then it copies the plan records and drops the junctions, worktree and branch. cli.py adds `--land`; README, CLAUDE.md and MAIN.md document it as the user's command.
