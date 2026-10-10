# Plan: lint-hardening
## Goal
Harden `lint()` in `.harness/runner/lint.py`: red-first runs in a throwaway worktree, flag POSIX-only acceptance starts on win32, dedupe `_ancestors`.

## Decisions
- All 3 code tasks edit `.harness/runner/lint.py`: chain deps T1 -> T2 -> T3, no parallel.
- Overlap: slug `red-first-default-off` (not yet planned, no dir) also edits `lint.py` (red_first default flips off; the line `t.get("red_first", True)` in the final red-first loop). Run it AFTER this plan lands (this plan first; it depends on T3's loop shape). T3 must keep that loop's skip condition untouched, only wrap the execution.
- Skip-when-off already exists (loop skips `red_first` falsy). Do not change it.
- T3: no change to `acceptance.py`/`cli.py`. In `lint()`, before the red-first loop, if any task needs execution: `git worktree add --detach <tempfile.mkdtemp()/wt> HEAD`, copy the plan dir into it if it lies under cwd (`shutil.copytree(..., dirs_exist_ok=True)`, same relative path), `os.chdir` there, run `run_acceptance`, and in `finally` chdir back + `git worktree remove --force` + rmtree temp. Not in a git repo or worktree add fails: print a `WARN` line, skip red-first (no execution in main tree).
- T2: `import sys`; on `sys.platform == "win32"` error `"{tid}: acceptance starts with POSIX '{tok}' which cmd.exe cannot run; use python -c"` when acceptance matches `^\s*(!|test\s|rm\s)`.
- T1: replace the inline ancestor loop in the build_gate block with `_ancestors(t, by_id)`; same errors.
- Checks live in `checks/`, not in any task's files.

Verified: lint.py duplicates `_ancestors` at the build_gate block (`python -c "import re;print(open('.harness/runner/lint.py').read().count('pending.extend'))"` gives 2)
Verified: `run_acceptance` uses `os.getcwd()` for PYTHONPATH and inherits cwd (`.harness/runner/acceptance.py:34`)
Unverified: Windows `git worktree remove` may need a retry when files are locked; warn, don't fail.
Later: dedupe `by_id` built twice in `lint()`.

## interfaces
- `lint(plan, tasks, passed) -> int` unchanged signature and output format (`ERROR `/`WARN `/`lint OK`).
- `_ancestors(task, by_id) -> set` existing, reused.

## T1 dedupe ancestors
FILES: .harness/runner/lint.py
MUST:
- build_gate block calls `_ancestors(t, by_id)`; inline loop removed.
- Behavior and error text unchanged.
- `pending.extend` appears exactly once in lint.py afterwards.
TEST: python -m pytest -q tests/test_lint.py && python -c "assert open('.harness/runner/lint.py').read().count('pending.extend')==1"

## T2 win32 posix check
FILES: .harness/runner/lint.py
MUST:
- Add `import sys` at top of lint.py (not imported today).
- Error per Decisions for acceptance starting `!`, `test `, `rm ` when `sys.platform == "win32"`.
- No error on other platforms or when those words appear mid-command (`python -c "..."`).
- Existing tests still pass.
TEST: python .harness/plans/lint-hardening/checks/check_t2.py

## T3 lint worktree
FILES: .harness/runner/lint.py
MUST:
- Red-first execution only happens in the throwaway worktree; main tree cwd restored and worktree removed even on exception.
- Plan dir copied in so `checks/` scripts resolve.
- Non-git or worktree failure: `WARN`, no execution.
- Each acceptance still runs exactly once; "check-invalid" error unchanged.
TEST: python .harness/plans/lint-hardening/checks/check_t3.py

## T4 write summary
FILES: .harness/plans/lint-hardening/SUMMARY.md
MUST: write <= 600 chars covering what was made, which files, and how it was wired; run the build if any and add a line `BUILD: pass` or `BUILD: fail <first error line>` to SUMMARY.md. The build result never fails the task.
TEST: summary existence/length check
