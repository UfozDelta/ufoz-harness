What: Claude-mode and runner-mode share one worktree per plan (.worktrees/<slug>), one check, one land.
Files: .harness/runner/cli.py (new --prepare flag and prepare(); --check takes an optional DIR, defaulting to the plan's worktree); tests/test_prepare.py (prepare idempotency, flag parsing).
Wiring: --prepare creates the worktree, syncs plan files, prints its path, runs nothing, takes no run.lock. Claude-mode edits in that path, then --check grades it, and --land applies it.
BUILD: python -m pytest -q tests/test_prepare.py tests/test_git_guard.py
