# lint-hardening

Hardened `lint()` in `.harness/runner/lint.py`:
- T1: build_gate calls the existing `_ancestors(t, by_id)` instead of an inline copy of its loop.
- T2: `import sys`; on win32 an acceptance starting with `!`, `test ` or `rm ` errors, suggesting `python -c`.
- T3: red-first acceptance runs in a throwaway `git worktree add --detach` of HEAD (new `_worktree` contextmanager), with the plan dir copied in so `checks/` scripts resolve; cwd restored and worktree removed in `finally`. Non-git/worktree failure -> WARN, no execution.

BUILD: pass