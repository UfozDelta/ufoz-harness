# Plan: stray-revert-retry
## Goal
Stray (out-of-scope) files no longer end the task at once. Revert them in the worktree, retry once with feedback naming allowed FILES and stray names. Second stray still fails. Report lists strays.

## Decisions
- `guards.revert_paths(paths)`: for each path, tracked (`git ls-files -- <p>` non-empty) -> `git checkout HEAD -- <p>`; else delete file (or dir tree). Only given paths. Never raises on missing path. Skip `GIT_MOVED` sentinel.
- `report.stray_feedback(allowed, stray)` returns brief text: "Attempt reverted: you touched files outside FILES." + sorted allowed list + sorted stray names + "use only the allowed paths exactly".
- `report.final_report(..., reverted=())` new trailing kwarg; adds line `reverted stray files: <list or none>` after `out-of-scope files:`. `summary_lines` unchanged.
- task_runner.run attempt loop: if `got.stray`, not `got.broken`, `GIT_MOVED` not in stray, and `attempt < RETRIES`: revert_paths(stray), record in `reverted`, write `stray_feedback(...)` followed by `report.retry_feedback(...)` (same args as the plain-failure path, so acceptance output is kept) to `items/T<id>.feedback.md`, continue. Else break as today. Timeout session reset logic kept.
- Reverting runs in cwd (worktree). Under `--parallel` only the already-attributed `got.stray` is reverted, never `unattributed`.
- RETRIES stays 1. No new CLI flag.
Verified: runner entry is `TaskRunner.run`, break at `if ok or got.broken or got.stray or attempt >= RETRIES` (`rg -n "got.stray" .harness/runner/task_runner.py`)
Verified: tests use `FakeExecutor` + `make_plan` in tests/test_task_runner.py
Later: update HARNESS.md Failures bullet "Report lists out-of-scope files" (dirty file, main session).

## interfaces
- `guards.revert_paths(paths: list[str]) -> None` (new)
- `report.stray_feedback(allowed, stray) -> str` (new)
- `report.final_report` gains `reverted=()` kwarg
- Executor.run(brief, log, timeout, feedback=None, session=None, rules=None, raw_prompt=None) -> ExecResult (unchanged)

## T1 revert helper
FILES: .harness/runner/guards.py
MUST: add `revert_paths` per Decisions; tracked restored from HEAD; untracked deleted; missing path ignored; touches nothing else.
TEST: temp-repo smoke (see tasks.json)

## T2 stray feedback
FILES: .harness/runner/report.py
MUST: add `stray_feedback`; add `reverted` kwarg and report line to `final_report`; existing callers still work.
TEST: import smoke

## T3 wire retry
FILES: .harness/runner/task_runner.py
DEPS: T1, T2
MUST: loop per Decisions (stray feedback text + retry_feedback appended, not replaced); second-attempt stray still fails; GIT_MOVED never reverted; pass `reverted` to final_report; strays from attempt 0 stay in the report.
TEST: python -m pytest tests/test_task_runner.py -q

## T4 stray tests
FILES: tests/test_task_runner.py
MUST: add `test_stray_revert_retry_passes` (first `git init` the tmp repo, set local `user.name`/`user.email`, make an initial commit, so `git_state()` is not None and `commit_task` works; FakeExecutor subclass writes done file plus `stray.txt` in cwd on call 1 only; use `monkeypatch.chdir` into a `git init` tmp repo; assert stray.txt gone, calls==2, retry feedback file names `stray.txt` and the done path, ok True, report has `reverted stray files`). Add `test_stray_revert_second_stray_fails` (stray both calls: ok False, calls==2, report names stray). No tracked-file test needed. Do not edit existing tests.
TEST: python -m pytest tests/test_task_runner.py -k stray_revert -q

## T5 write summary
FILES: .harness/plans/stray-revert-retry/SUMMARY.md
MUST: write <= 600 chars covering what was made, which files, and how it was wired; run the build if any and add a line `BUILD: pass` or `BUILD: fail <first error line>` to SUMMARY.md. The build result never fails the task.
TEST: summary existence/length check
