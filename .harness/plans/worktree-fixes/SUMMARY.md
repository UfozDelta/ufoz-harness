# worktree-fixes

Fixed two bugs in `.harness/runner/worktree.py`:
- `_exclude_worktrees` takes the exclude file from `git rev-parse --git-path
  info/exclude` (fallback `.git/info/exclude`), so it works inside a linked worktree.
- `_link` resolves the shared dir from the main worktree root (parent of the absolute
  `--git-common-dir`) and runs `check-ignore` there; falls back to the cwd-relative dir.
  Existing targets are never deleted or replaced.

Wiring unchanged: `ensure` still calls both. New real-git tests in
`tests/test_worktree.py` cover all three cases.

BUILD: pass
