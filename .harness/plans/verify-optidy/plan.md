# Plan: verify-optidy
## Goal
Stop opencode's runtime files tripping the worktree scope/clean checks, and stop headless planners reading `.pi/`.

## Decisions
- Root cause 1: `.opencode/package*.json` are ignored in the main tree only by the untracked `.opencode/.gitignore` (opencode writes it); worktrees lack it, so the files show as untracked and block commit/land. Fix: copy `.opencode/.gitignore` into the worktree with the other gitignored files (`worktree.OPENCODE_PKG`). Do not touch `guards.py`.
- Root cause 2: opencode planners explore the project and read `.pi/executor.md`, which `check_rules` flags. Fix: one sentence in `verify._plan_brief` telling the planner not to read anything under `.pi/`. The `rules_ok` check stays the enforcement.

## interfaces
- `worktree.OPENCODE_PKG` gains `".opencode/.gitignore"` (first entry).

## T1 worktree gitignore
FILES: .harness/runner/worktree.py
MUST:
- Add `".opencode/.gitignore"` to `OPENCODE_PKG`; nothing else changes. `python .harness/selftest.py` still exits 0.
TEST: python .harness/plans/verify-optidy/checks/check_t1.py

## T2 brief
FILES: bench/verify/verify.py
MUST:
- `_plan_brief` text gains: `Do not read anything under .pi/.` placed next to the existing "Work only inside the current directory" sentence.
TEST: python .harness/plans/verify-optidy/checks/check_t2.py

## T3 summary
FILES: .harness/plans/verify-optidy/SUMMARY.md
MUST:
- SUMMARY.md (<= 600 chars: what, files, how wired) ending `BUILD: pass` after `python bench/verify/verify.py --dry` exits 0. Write it with a bash heredoc.
TEST: python .harness/plans/verify-optidy/checks/check_t3.py
